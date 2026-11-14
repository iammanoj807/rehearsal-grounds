"""Step 09: climate, land cover and novelty for every kept site.

For each site in ``work/results/<target>.parquet``:

* NASA POWER climatology (annual values, cached in ``data/cache/power/``):
  mean, maximum and minimum 2 m temperature, mean daily range, corrected
  precipitation, relative humidity and all-sky surface sunlight.
* ESA WorldCover 2021 class shares within ``env_radius_km`` of the site
  centre, read from the fetched ~20 m mosaic: bare ground, snow and ice,
  vegetation/crops/buildings and open water.
* Novelty: great-circle distance to the nearest entry of
  ``config/known_analogs.yaml``; within ``novelty_km`` -> ``well_studied``.

Outputs ``work/results/environment.parquet`` and ``novelty.parquet``.
"""

from __future__ import annotations

import math
import sys
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds

from common import CACHE_DIR, RAW_DIR, get_logger, load_config, load_yaml, record_source, results_dir, selected_targets
from grids import haversine_km
from power import API, PowerError, annual_values, fetch_climatology

log = get_logger("09_environment")
VEG_CLASSES = (10, 20, 30, 40, 50, 90, 95, 100)  # trees, shrubs, grass, crops, built-up, wetland, mangrove, moss


def worldcover_shares(region_id: str, lat: float, lon: float, radius_km: float) -> dict[str, float] | None:
    """WorldCover class shares within ``radius_km`` of a point, or None without coverage."""
    path = RAW_DIR / "earth" / f"{region_id}_wc.tif"
    if not path.exists():
        return None
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.05))
    with rasterio.open(path) as src:
        win = from_bounds(lon - dlon, lat - dlat, lon + dlon, lat + dlat, src.transform)
        arr = src.read(1, window=win, boundless=True, fill_value=0)
        tf = src.window_transform(win)
    rows, cols = np.indices(arr.shape)
    xs = tf.c + (cols + 0.5) * tf.a
    ys = tf.f + (rows + 0.5) * tf.e
    dy = (ys - lat) * 111.32
    dx = (xs - lon) * 111.32 * math.cos(math.radians(lat))
    inside = (dx**2 + dy**2 <= radius_km**2) & (arr > 0)
    n = int(inside.sum())
    if n == 0:
        return None
    vals = arr[inside]
    return {
        "bare_fraction": float(np.mean(vals == 60)),
        "snow_ice_fraction": float(np.mean(vals == 70)),
        "vegetation_fraction": float(np.isin(vals, VEG_CLASSES).mean()),
        "water_fraction": float(np.mean(vals == 80)),
    }


def novelty(lat: float, lon: float, catalogue: list[dict[str, Any]], threshold_km: float) -> dict[str, Any]:
    """Nearest catalogued analog and the resulting status."""
    best = min(catalogue, key=lambda a: haversine_km(lat, lon, a["lat"], a["lon"]))
    dist = haversine_km(lat, lon, best["lat"], best["lon"])
    return {"status": "well_studied" if dist <= threshold_km else "less_studied",
            "nearest_known_analog": best["name"], "distance_km": dist, "source_url": best["source_url"]}


def main() -> int:
    """Compute environment and novelty tables for all kept sites."""
    cfg = load_config()
    catalogue = load_yaml("known_analogs.yaml")["analogs"]
    sites = pd.concat([pd.read_parquet(results_dir() / f"{t['id']}.parquet")
                       for t in selected_targets(load_yaml("targets.yaml")["targets"])], ignore_index=True)
    sites = sites.drop_duplicates("site_id")[["site_id", "region_id", "lat", "lon"]]
    env_rows, nov_rows, failures = [], [], []
    for s in sites.itertuples():
        rec: dict[str, Any] = {"site_id": s.site_id}
        try:
            ann = annual_values(fetch_climatology(s.lat, s.lon, CACHE_DIR / "power"))
            rec.update({
                "t2m_mean_c": ann["T2M"], "t2m_max_c": ann["T2M_MAX"], "t2m_min_c": ann["T2M_MIN"],
                "t2m_range_c": ann["T2M_RANGE"], "precip_mm_per_day": ann["PRECTOTCORR"],
                "rh_pct": ann["RH2M"], "solar_kwh_m2_day": ann["ALLSKY_SFC_SW_DWN"],
                "power_source": "NASA POWER climatology API v2 (MERRA-2 / CERES, 2001-2025), community RE",
            })
        except PowerError as exc:
            log.error("%s", exc)
            failures.append(s.site_id)
        wc = worldcover_shares(s.region_id, s.lat, s.lon, float(cfg["env_radius_km"]))
        rec["worldcover_available"] = wc is not None
        rec.update(wc or {})
        env_rows.append(rec)
        nov_rows.append({"site_id": s.site_id, **novelty(s.lat, s.lon, catalogue, float(cfg["novelty_km"]))})
    record_source(url=API, dataset="NASA POWER climatology (point API)", licence="NASA open data",
                  note=f"{len(sites)} sites; responses cached in data/cache/power")
    env = pd.DataFrame(env_rows)
    nov = pd.DataFrame(nov_rows)
    env.to_parquet(results_dir() / "environment.parquet", index=False)
    nov.to_parquet(results_dir() / "novelty.parquet", index=False)
    log.info("%d sites: %d with climate, %d with land cover; %d less studied, %d well studied",
             len(env), int(env.get("t2m_mean_c", pd.Series(dtype=float)).notna().sum()),
             int(env["worldcover_available"].sum()), int((nov["status"] == "less_studied").sum()),
             int((nov["status"] == "well_studied").sum()))
    if failures:
        log.error("POWER failed for %d sites; they show land cover only", len(failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
