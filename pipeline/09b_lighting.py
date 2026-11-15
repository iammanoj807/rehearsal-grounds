"""Step 09b: low-sun lighting analog, rehearsal calendar and suggested months.

For every Moon target the noon Sun band follows from its latitude (lighting.sun_band).
For every exported site of a Moon target:

* shadow fingerprints S(e) of the Earth patch and of its best target patch, from a
  context window of ``margin_px`` around the patch on the 60 m grid, averaged over
  ``n_azimuths`` Sun azimuths (cast and attached shadows, body curvature included).
  The Moon site maps are small, so a target patch often sees less than the full
  margin. The Earth window is therefore given the same footprint as its target's
  window (pixels missing around the target are blanked around the Earth patch too),
  so both sides see the same surroundings;
* lighting similarity = 100 x (1 - mean |S_target(e) - S_earth(e)|) over the
  fingerprint elevations inside the band (a separate panel, never part of the
  similarity score);
* a low-sun preview: hillshade at the band's middle elevation and azimuth
  ``preview_azimuth_deg`` with cast shadows, saved as an array for step 11.

For every exported site (Moon and Mars targets) the 12-month calendar combines the
Sun hours on the 15th of each month (daylight; low-sun hours for Moon targets) with
NASA POWER monthly climatology already cached by step 09, and the suggested months
follow config/rehearsal.yaml. Step 09b also runs the lighting self-checks shown on
the Validation page.

Outputs ``work/results/lighting.json`` and ``work/lighting/lowsun_<patch>.npy``.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from typing import Any

import numpy as np
import pandas as pd
import rasterio

from common import CACHE_DIR, RAW_DIR, get_logger, grids_dir, load_config, load_yaml, results_dir, run_dir, selected_targets
from features import hillshade
from lighting import (R_EARTH_M, R_MOON_M, band_elevations, cast_shadow_mask, horizon_angles, lighting_similarity,
                      monthly_sun_hours, read_window, shadow_fractions, solar_elevation, sun_band)
from precip import fetch_regional, nearest_monthly

log = get_logger("09b_lighting")
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def lowsun_dir():
    """Folder for the low-sun preview arrays of this run."""
    d = run_dir() / "lighting"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Grids:
    """Lazy cache of the 60 m elevation grids."""

    def __init__(self) -> None:
        self._g: dict[str, np.ndarray] = {}

    def get(self, source_id: str) -> np.ndarray:
        if source_id not in self._g:
            with rasterio.open(grids_dir() / f"{source_id}_dem.tif") as src:
                self._g[source_id] = src.read(1).astype(np.float64)
        return self._g[source_id]


def patch_window(meta: pd.DataFrame, patch_id: str, grids: Grids, patch: int, margin: int) -> tuple[np.ndarray, bool]:
    """Context window of one patch and its edge-limited flag."""
    row = meta.loc[meta["patch_id"] == patch_id].iloc[0]
    return read_window(grids.get(row["source_id"]), int(row["row"]), int(row["col"]), patch, margin)


def monthly_climate(region_id: str, lat: float, lon: float) -> list[dict[str, float | None]]:
    """NASA POWER monthly climatology at the grid cell nearest a site: mean daily low and high, and rain.

    T2M_MIN_AVG / T2M_MAX_AVG are the monthly means of the daily minimum and maximum
    (T2M_MIN / T2M_MAX would be the coldest and warmest hour of the month). The regional
    endpoint takes one parameter per request, so each is fetched and cached per region:
    data/cache/power_regional (rain, shared with step 04) and power_regional_<PARAM>.
    """
    bounds = json.loads((RAW_DIR / "earth" / "fetch_log.json").read_text())[region_id]["bounds"]

    def grid(param: str) -> dict[str, Any]:
        folder = "power_regional" if param == "PRECTOTCORR" else f"power_regional_{param}"
        return fetch_regional(region_id, bounds, CACHE_DIR / folder, parameters=param)

    lows = nearest_monthly(grid("T2M_MIN_AVG"), lat, lon, "T2M_MIN_AVG")
    highs = nearest_monthly(grid("T2M_MAX_AVG"), lat, lon, "T2M_MAX_AVG")
    rain = nearest_monthly(grid("PRECTOTCORR"), lat, lon, "PRECTOTCORR")
    return [{"t2m_min_avg_c": lo, "t2m_max_avg_c": hi, "precip_mm_per_day": r} for lo, hi, r in zip(lows, highs, rain)]


def best_months(calendar: list[dict[str, Any]], rules: dict[str, Any], key: str) -> tuple[list[int], str]:
    """Suggested months under config/rehearsal.yaml, and a one-line statement of the outcome.

    A month is eligible when it passes BOTH the rain and the temperature rule. Months are
    suggested only when the best eligible month has at least ``min_gain_min`` more minutes
    of ``key`` (low-sun or daylight time) per day than the median eligible month; then the
    eligible months that clear that bar, best first, up to ``n_best_months``. There is no
    fallback: otherwise no month is suggested and the reason is stated.
    """
    limit = float(rules["max_precip_mm_per_day"])
    tmin, tmax = float(rules["min_t2m_min_c"]), float(rules["max_t2m_max_c"])
    gain, n = float(rules["min_gain_min"]), int(rules["n_best_months"])
    label = "low-sun time" if key == "low_sun_h" else "daylight"

    def dry(c: dict[str, Any]) -> bool:
        return c["precip_mm_per_day"] is not None and c["precip_mm_per_day"] <= limit

    def not_cold(c: dict[str, Any]) -> bool:
        return c["t2m_min_avg_c"] is not None and c["t2m_min_avg_c"] >= tmin

    def not_hot(c: dict[str, Any]) -> bool:
        return c["t2m_max_avg_c"] is not None and c["t2m_max_avg_c"] <= tmax

    eligible = [c for c in calendar if dry(c) and not_cold(c) and not_hot(c)]
    if not eligible:
        reasons = []
        if not any(dry(c) for c in calendar):
            reasons.append(f"too wet: no month averages {limit:g} mm of rain a day or less")
        if not any(not_cold(c) for c in calendar):
            reasons.append(f"too cold: no month has a mean daily low of {tmin:g} °C or warmer")
        if not any(not_hot(c) for c in calendar):
            reasons.append(f"too hot: no month has a mean daily high of {tmax:g} °C or cooler")
        if not reasons:
            reasons.append("the dry months are too cold or too hot")
        return [], f"No month passes our rules ({'; '.join(reasons)})."
    minutes = {c["month"]: 60.0 * (c[key] or 0.0) for c in calendar}
    vals = np.array([minutes[c["month"]] for c in eligible])
    med = float(np.median(vals))
    if vals.max() - med < gain:
        names = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        when = ("all year" if len(eligible) == 12 else
                "in the months that pass our rain and temperature rules ("
                + ", ".join(names[c["month"] - 1] for c in eligible) + ")")
        return [], (f"No suggested month: {label} is about {med:.0f} min a day {when}; no month stands out by "
                    f"{gain:g} min.")
    ranked = sorted((c for c in eligible if minutes[c["month"]] - med >= gain),
                    key=lambda c: (-minutes[c["month"]], c["precip_mm_per_day"]))
    return (sorted(c["month"] for c in ranked[:n]),
            f"Our rule: months with at most {limit:g} mm of rain a day, a mean daily low of at least {tmin:g} °C and "
            f"a mean daily high of at most {tmax:g} °C, and at least {gain:g} more minutes of {label} a day than the "
            "median such month.")


def self_checks(lcfg: dict[str, Any]) -> list[dict[str, Any]]:
    """The lighting checks shown on the Validation page, computed here."""
    m, p = int(lcfg["margin_px"]), 64
    checks = []
    flat = np.zeros((p + 2 * m, p + 2 * m))
    hor = horizon_angles(flat, 60.0, 90.0, R_EARTH_M, m, p)
    checks.append({"check": "A flat plane casts no shadow at a 1 degree Sun", "passed": bool(not (hor > 1.0).any()),
                   "detail": f"highest horizon angle {hor.max():.3f} deg (curvature makes it slightly negative)"})
    wall = np.zeros((p + 2 * m, p + 2 * m))
    wall[:, m + 40:] = 100.0
    row = horizon_angles(wall, 60.0, 90.0, 1e12, m, p)[p // 2]
    length = 40 - int(np.flatnonzero(row[:40] > 10.0).min())
    expected = 100.0 / np.tan(np.radians(10.0)) / 60.0
    checks.append({"check": "A 100 m step casts a shadow of length h / tan(e) at a 10 degree Sun (within one 60 m pixel)",
                   "passed": bool(abs(length - expected) <= 1.0),
                   "detail": f"{length} px measured vs {expected:.2f} px expected"})
    drop = 10_000.0**2 / (2 * R_MOON_M)
    checks.append({"check": "Lunar curvature drop at 10 km is d^2 / 2R = 28.8 m", "passed": bool(abs(drop - 28.78) < 0.05),
                   "detail": f"{drop:.2f} m (Earth: {10_000.0**2 / (2 * R_EARTH_M):.2f} m)"})
    e = solar_elevation(39.742476, -105.1786, dt.datetime(2003, 10, 17, 19, 30, 30, tzinfo=dt.timezone.utc))
    checks.append({"check": "Solar elevation matches the published NREL SPA example (unrefracted) within 0.05 degrees",
                   "passed": bool(abs(e - 39.872046) <= 0.05),
                   "detail": f"ours {e:.4f} deg true elevation; NREL SPA e0 = 39.8720 deg topocentric without refraction "
                             "(39.8884 deg with refraction); Reda and Andreas 2004, NREL/TP-560-34302"})
    return checks


def main() -> int:
    """Lighting fingerprints, previews, calendars and suggested months for all exported sites."""
    cfg = load_config()
    lcfg = load_yaml("lighting.yaml")
    rules = load_yaml("rehearsal.yaml")
    meta = pd.read_parquet(run_dir() / "features.parquet")
    patch, margin = int(cfg["patch_px"]), int(lcfg["margin_px"])
    res = float(cfg["resolution_m"])
    elevs = tuple(float(e) for e in lcfg["elevations_deg"])
    n_az = int(lcfg["n_azimuths"])
    grids = Grids()
    cache: dict[Any, tuple[dict[float, float], bool]] = {}
    previews: set[str] = set()
    doc: dict[str, Any] = {"targets": {}, "sites": {}, "checks": self_checks(lcfg),
                           "settings": {k: lcfg[k] for k in ("elevations_deg", "n_azimuths", "margin_px",
                                                             "preview_azimuth_deg", "sun_hours_year")},
                           "rules": rules}

    def fingerprint(pid: str, radius: float, footprint_of: str | None = None) -> tuple[dict[float, float], bool]:
        """Shadow fractions of a patch; with ``footprint_of`` the window is blanked wherever that patch's window is."""
        key = (pid, footprint_of)
        if key not in cache:
            window, edge = patch_window(meta, pid, grids, patch, margin)
            if footprint_of is not None:
                ref, ref_edge = patch_window(meta, footprint_of, grids, patch, margin)
                window = np.where(np.isfinite(ref), window, np.nan)
                edge = edge or ref_edge
            cache[key] = (shadow_fractions(window, res, radius, margin, patch, elevs, n_az), edge)
        return cache[key]

    def preview(pid: str, radius: float, elev: float) -> None:
        if pid in previews:
            return
        window, _ = patch_window(meta, pid, grids, patch, margin)
        filled = np.where(np.isfinite(window), window, np.nanmedian(window))
        core = filled[margin:margin + patch, margin:margin + patch]
        az = float(lcfg["preview_azimuth_deg"])
        shade = hillshade(core, res, azimuth_deg=az, altitude_deg=elev)
        dark = cast_shadow_mask(window, res, radius, margin, patch, az, elev)
        np.save(lowsun_dir() / f"lowsun_{pid.replace(':', '_')}.npy", np.where(dark, 0.0, shade).astype(np.float32))
        previews.add(pid)

    jett5 = next((r for r in load_yaml("regions.yaml")["regions"] if r.get("field_test")), None)
    for t in selected_targets(load_yaml("targets.yaml")["targets"]):
        tid = t["id"]
        sites = pd.read_parquet(results_dir() / f"{tid}.parquet").sort_values("rank")
        tmeta = meta[meta["source_id"] == tid]
        moon = t["body"] == "moon"
        tinfo: dict[str, Any] = {"applicable": moon}
        if moon:
            lat = float(tmeta["lat"].mean())
            band = sun_band(lat, float(lcfg["moon_obliquity_deg"]))
            used = band_elevations(band, elevs)
            tinfo.update(latitude_deg=lat, low_deg=band[0], high_deg=band[1], elevations_used=used,
                         preview_elevation_deg=float(np.clip((band[0] + band[1]) / 2.0, 0.5, None)))
        if moon and jett5 is not None:
            hrs = monthly_sun_hours(jett5["lat"], jett5["lon"], int(lcfg["sun_hours_year"]), tinfo["high_deg"],
                                    int(lcfg["sun_hours_step_min"]))
            tinfo.update(jett5_region_id=jett5["id"], jett5_low_sun_min=[60.0 * h["low_sun_h"] for h in hrs])
        doc["targets"][tid] = tinfo
        out_sites: dict[str, Any] = {}
        for r in sites.itertuples():
            rec: dict[str, Any] = {}
            if moon:
                s_t, edge_t = fingerprint(r.target_patch_id, R_MOON_M)
                s_e, edge_e = fingerprint(r.site_id, R_EARTH_M, footprint_of=r.target_patch_id)
                used = tinfo["elevations_used"]
                rec["lighting"] = {
                    "similarity": lighting_similarity(s_t, s_e, used), "elevations": used,
                    "shadow": [{"elevation_deg": e, "target": s_t[e], "earth": s_e[e]} for e in elevs],
                    "edge_limited_target": edge_t, "edge_limited_earth": edge_e,
                    "footprint_matched": True,
                }
                preview(r.target_patch_id, R_MOON_M, tinfo["preview_elevation_deg"])
                preview(r.site_id, R_EARTH_M, tinfo["preview_elevation_deg"])
            upper = tinfo["high_deg"] if moon else 0.0
            hours = monthly_sun_hours(float(r.lat), float(r.lon), int(lcfg["sun_hours_year"]), upper,
                                      int(lcfg["sun_hours_step_min"]))
            clim = monthly_climate(r.region_id, float(r.lat), float(r.lon))
            cal = [{**h, **c, "low_sun_h": h["low_sun_h"] if moon else None} for h, c in zip(hours, clim)]
            months, rule = best_months(cal, rules, "low_sun_h" if moon else "daylight_h")
            rec.update(calendar=cal, best_months=months, best_months_rule=rule)
            out_sites[r.site_id] = rec
        doc["sites"][tid] = out_sites
        sims = [v["lighting"]["similarity"] for v in out_sites.values() if "lighting" in v]
        log.info("%s: %s; %d sites%s", tid,
                 f"band {tinfo['low_deg']:.2f}-{tinfo['high_deg']:.2f} deg, elevations {tinfo['elevations_used']}"
                 if moon else "lighting not applicable (Mars)", len(out_sites),
                 f", lighting similarity {min(sims):.0f}-{max(sims):.0f}" if sims else "")
    (results_dir() / "lighting.json").write_text(json.dumps(doc, indent=1))
    for c in doc["checks"]:
        log.info("check %s: %s (%s)", "PASS" if c["passed"] else "FAIL", c["check"], c["detail"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
