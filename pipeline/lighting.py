"""Low-sun lighting: sun band, cast and attached shadows, and the Earth sun position.

Concepts in plain words:

* Sun band. The Moon's spin axis is tilted about 1.54 degrees, so over a year the
  noon Sun at latitude phi stays within 1.54 degrees of 90 - |phi|. Near the south
  pole that is a few degrees at most: long shadows all day.
* Shadow fingerprint. For a given Sun direction a pixel is dark if the terrain
  between it and the Sun rises above the Sun (cast shadow) or if its own slope
  faces away from the Sun (attached shadow). Rays are marched toward the Sun over
  the grid around the patch; the far terrain drops by d^2 / (2R) because the body
  is round. The share of dark pixels at a set of low Sun elevations, averaged over
  Sun azimuths, is the patch's shadow fingerprint.
* Earth Sun position. NOAA's solar-position equations (after Meeus) give the true
  (unrefracted) solar elevation for any place and time; daylight hours with the Sun
  between 0 degrees and the target band's upper limit are "low-sun hours".
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np

MOON_OBLIQUITY_DEG = 1.54  # lunar spin-axis tilt to the ecliptic, as used in the brief
R_MOON_M = 1_737_400.0
R_EARTH_M = 6_371_000.0


# ---------------------------------------------------------------- sun band
def sun_band(lat_deg: float, obliquity_deg: float = MOON_OBLIQUITY_DEG) -> tuple[float, float]:
    """(low, high) noon Sun elevation over a year at a lunar latitude, clipped at 0."""
    colat = 90.0 - abs(lat_deg)
    return max(colat - obliquity_deg, 0.0), max(colat + obliquity_deg, 0.0)


def band_elevations(band: tuple[float, float], elevations: tuple[float, ...]) -> list[float]:
    """Fingerprint elevations inside the band; the nearest one when none falls inside."""
    lo, hi = band
    inside = [e for e in elevations if lo <= e <= hi]
    if inside:
        return inside
    mid = (lo + hi) / 2.0
    return [min(elevations, key=lambda e: abs(e - mid))]


# ---------------------------------------------------------------- shadows
def horizon_angles(window: np.ndarray, res: float, azimuth_deg: float, radius_m: float, margin: int,
                   patch: int) -> np.ndarray:
    """Horizon elevation angle (degrees) toward ``azimuth_deg`` for each pixel of the central patch.

    ``window`` is the patch plus ``margin`` pixels on every side (NaN where the grid
    ends). Rows run north to south and columns west to east; azimuth is clockwise
    from grid north. Samples use the nearest pixel along the ray; the ray stops at
    the window edge, so a cut-off margin can only miss distant terrain.
    """
    az = np.radians(azimuth_deg)
    dcol, drow = np.sin(az), -np.cos(az)
    r0 = np.arange(margin, margin + patch)[:, None] * np.ones((1, patch))
    c0 = np.ones((patch, 1)) * np.arange(margin, margin + patch)[None, :]
    z0 = window[margin:margin + patch, margin:margin + patch]
    best = np.full((patch, patch), -90.0)
    n_rows, n_cols = window.shape
    for k in range(1, margin + 1):
        rr = np.rint(r0 + k * drow).astype(int)
        cc = np.rint(c0 + k * dcol).astype(int)
        ok = (rr >= 0) & (rr < n_rows) & (cc >= 0) & (cc < n_cols)
        if not ok.any():
            break
        zk = np.full((patch, patch), np.nan)
        zk[ok] = window[rr[ok], cc[ok]]
        d = k * res
        ang = np.degrees(np.arctan2(zk - z0 - d * d / (2.0 * radius_m), d))
        best = np.where(np.isfinite(ang), np.maximum(best, ang), best)
    return best


def attached_shadow(z: np.ndarray, res: float, azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    """True where the surface faces away from the Sun (its normal points below the Sun)."""
    gy, gx = np.gradient(z.astype(np.float64), res)
    dzdx, dzdy = gx, -gy  # rows run south, so flip for a north-pointing y
    az = np.radians(azimuth_deg)
    rise_toward_sun = dzdx * np.sin(az) + dzdy * np.cos(az)
    return rise_toward_sun >= np.tan(np.radians(elevation_deg))


def shadow_fractions(window: np.ndarray, res: float, radius_m: float, margin: int, patch: int,
                     elevations: tuple[float, ...], n_azimuths: int) -> dict[float, float]:
    """Shadow share of the central patch at each elevation, averaged over Sun azimuths."""
    filled = np.where(np.isfinite(window), window, np.nanmedian(window))
    core = filled[margin:margin + patch, margin:margin + patch]
    sums = {e: 0.0 for e in elevations}
    for i in range(n_azimuths):
        az = 360.0 * i / n_azimuths
        hor = horizon_angles(window, res, az, radius_m, margin, patch)
        for e in elevations:
            dark = (hor > e) | attached_shadow(core, res, az, e)
            sums[e] += float(dark.mean())
    return {e: sums[e] / n_azimuths for e in elevations}


def lighting_similarity(s_target: dict[float, float], s_earth: dict[float, float], elevations: list[float]) -> float:
    """100 x (1 - mean |S_target(e) - S_earth(e)|) over the given elevations."""
    return float(100.0 * (1.0 - np.mean([abs(s_target[e] - s_earth[e]) for e in elevations])))


def cast_shadow_mask(window: np.ndarray, res: float, radius_m: float, margin: int, patch: int, azimuth_deg: float,
                     elevation_deg: float) -> np.ndarray:
    """Cast or attached shadow of the central patch for one Sun direction (for the preview)."""
    filled = np.where(np.isfinite(window), window, np.nanmedian(window))
    core = filled[margin:margin + patch, margin:margin + patch]
    hor = horizon_angles(window, res, azimuth_deg, radius_m, margin, patch)
    return (hor > elevation_deg) | attached_shadow(core, res, azimuth_deg, elevation_deg)


def read_window(grid: np.ndarray, row: int, col: int, patch: int, margin: int) -> tuple[np.ndarray, bool]:
    """Patch plus margin from a grid (NaN outside it) and whether the margin was cut off."""
    out = np.full((patch + 2 * margin, patch + 2 * margin), np.nan, dtype=np.float64)
    r0, c0 = row - margin, col - margin
    rs, cs = max(r0, 0), max(c0, 0)
    re_, ce = min(r0 + patch + 2 * margin, grid.shape[0]), min(c0 + patch + 2 * margin, grid.shape[1])
    out[rs - r0:re_ - r0, cs - c0:ce - c0] = grid[rs:re_, cs:ce]
    edge_limited = bool(r0 < 0 or c0 < 0 or r0 + patch + 2 * margin > grid.shape[0]
                        or c0 + patch + 2 * margin > grid.shape[1] or np.isnan(out).any())
    return out, edge_limited


# ---------------------------------------------------------------- Earth sun position (NOAA)
def _julian_century(t: dt.datetime) -> float:
    jd = t.timestamp() / 86400.0 + 2440587.5
    return (jd - 2451545.0) / 36525.0


def solar_elevation(lat_deg: float, lon_deg: float, t_utc: dt.datetime) -> float:
    """True (unrefracted) solar elevation in degrees, NOAA solar calculator equations."""
    jc = _julian_century(t_utc)
    l0 = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360.0
    m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    ecc = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    mr = np.radians(m)
    center = (np.sin(mr) * (1.914602 - jc * (0.004817 + 0.000014 * jc)) + np.sin(2 * mr) * (0.019993 - 0.000101 * jc)
              + np.sin(3 * mr) * 0.000289)
    true_long = l0 + center
    omega = 125.04 - 1934.136 * jc
    app_long = true_long - 0.00569 - 0.00478 * np.sin(np.radians(omega))
    obliq0 = 23.0 + (26.0 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60.0) / 60.0
    obliq = obliq0 + 0.00256 * np.cos(np.radians(omega))
    decl = np.degrees(np.arcsin(np.sin(np.radians(obliq)) * np.sin(np.radians(app_long))))
    y = np.tan(np.radians(obliq / 2.0)) ** 2
    l0r = np.radians(l0)
    eq_time = 4.0 * np.degrees(y * np.sin(2 * l0r) - 2 * ecc * np.sin(mr) + 4 * ecc * y * np.sin(mr) * np.cos(2 * l0r)
                               - 0.5 * y * y * np.sin(4 * l0r) - 1.25 * ecc * ecc * np.sin(2 * mr))
    minutes = t_utc.hour * 60.0 + t_utc.minute + t_utc.second / 60.0
    true_solar = (minutes + eq_time + 4.0 * lon_deg) % 1440.0
    hour_angle = true_solar / 4.0 - 180.0 if true_solar / 4.0 >= 0 else true_solar / 4.0 + 180.0
    lat, dec, ha = np.radians(lat_deg), np.radians(decl), np.radians(hour_angle)
    cos_zen = np.sin(lat) * np.sin(dec) + np.cos(lat) * np.cos(dec) * np.cos(ha)
    return float(90.0 - np.degrees(np.arccos(np.clip(cos_zen, -1.0, 1.0))))


def monthly_sun_hours(lat_deg: float, lon_deg: float, year: int, upper_deg: float,
                      step_min: int = 5) -> list[dict[str, Any]]:
    """For the 15th of each month: daylight hours and hours with 0 < elevation <= upper_deg."""
    out = []
    for month in range(1, 13):
        start = dt.datetime(year, month, 15, tzinfo=dt.timezone.utc)
        # Centre the 24 h window on local solar midnight so one local day is counted whole.
        offset = dt.timedelta(minutes=-4.0 * lon_deg)
        day, low = 0, 0
        for k in range(0, 24 * 60, step_min):
            t = start + offset + dt.timedelta(minutes=k)
            e = solar_elevation(lat_deg, lon_deg, t)
            if e > 0.0:
                day += 1
                if e <= upper_deg:
                    low += 1
        out.append({"month": month, "daylight_h": day * step_min / 60.0, "low_sun_h": low * step_min / 60.0})
    return out
