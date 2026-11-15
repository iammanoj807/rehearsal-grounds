"""NASA POWER regional climatology: annual precipitation on the native grid.

The regional endpoint returns every grid cell in a box (MERRA-2 native grid,
0.5 degrees of latitude by 0.625 degrees of longitude) and needs a box at least
2 degrees on each side, so each region's box is widened symmetrically to that
minimum. One request per region, cached in ``data/cache/power_regional/``.
Each Earth patch takes the annual value of the nearest grid-cell centre.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import requests

API = "https://power.larc.nasa.gov/api/temporal/climatology/regional"
MIN_SPAN_DEG = 2.0
SPAN_MARGIN_DEG = 0.02  # a box of exactly 2.000 degrees can be rejected after float rounding
DAYS_PER_YEAR = 365.25
FILL = -999.0


class PowerRegionalError(RuntimeError):
    """Raised when the regional request cannot be completed after all retries."""


def request_box(bounds: list[float], min_span: float = MIN_SPAN_DEG) -> tuple[float, float, float, float]:
    """(west, south, east, north) widened symmetrically to at least ``min_span`` degrees per side."""
    w, s, e, n = bounds
    cx, cy = (w + e) / 2.0, (s + n) / 2.0
    need = min_span + SPAN_MARGIN_DEG
    half_x = max((e - w) / 2.0, need / 2.0)
    half_y = max((n - s) / 2.0, need / 2.0)
    south, north = max(cy - half_y, -90.0), min(cy + half_y, 90.0)
    if north - south < need:  # near a pole: shift the box instead of shrinking it
        south, north = (north - need, north) if north >= 90.0 else (south, south + need)
    return (round(cx - half_x, 3), round(south, 3), round(cx + half_x, 3), round(north, 3))


def fetch_regional(region_id: str, bounds: list[float], cache_dir: Path, *, parameters: str = "PRECTOTCORR",
                   retries: int = 3, backoff_s: float = 2.0,
                   timeout_s: float = 120.0, get: Callable[..., Any] = requests.get,
                   sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Climatology of ``parameters`` for every grid cell around a region, cached per region."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{region_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    w, s, e, n = request_box(bounds)
    params = {"parameters": parameters, "community": "RE", "longitude-min": f"{w:.3f}",
              "longitude-max": f"{e:.3f}", "latitude-min": f"{s:.3f}", "latitude-max": f"{n:.3f}", "format": "JSON"}
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = get(API, params=params, timeout=timeout_s)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("features"):
                raise ValueError(f"no grid cells returned: {data.get('messages')}")
            path.write_text(json.dumps(data))
            return data
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt < retries:
                sleep(backoff_s * 2 ** (attempt - 1))
    raise PowerRegionalError(f"NASA POWER regional request failed for {region_id} after {retries} attempts: {last}")


def grid_cells(data: dict[str, Any]) -> np.ndarray:
    """(n x 3) array of lon, lat and annual precipitation in mm per year; fill values dropped."""
    rows = []
    for f in data["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        ann = f["properties"]["parameter"]["PRECTOTCORR"].get("ANN")
        if ann is None or ann == FILL:
            continue
        rows.append((float(lon), float(lat), float(ann) * DAYS_PER_YEAR))
    return np.asarray(rows, dtype=float).reshape(-1, 3)


def nearest_annual_mm(lats: np.ndarray, lons: np.ndarray, cells: np.ndarray) -> np.ndarray:
    """Annual precipitation (mm/yr) of the nearest grid-cell centre for each point."""
    if len(cells) == 0:
        return np.full(len(lats), np.nan)
    coslat = np.cos(np.radians(np.asarray(lats, dtype=float)))[:, None]
    dx = (np.asarray(lons, dtype=float)[:, None] - cells[None, :, 0]) * coslat
    dy = np.asarray(lats, dtype=float)[:, None] - cells[None, :, 1]
    return cells[np.argmin(dx**2 + dy**2, axis=1), 2]


MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def nearest_monthly(data: dict[str, Any], lat: float, lon: float, parameter: str) -> list[float | None]:
    """Twelve monthly values of ``parameter`` at the grid cell nearest to (lat, lon)."""
    feats = data["features"]
    coords = np.array([f["geometry"]["coordinates"][:2] for f in feats], dtype=float)
    d2 = ((coords[:, 0] - lon) * np.cos(np.radians(lat))) ** 2 + (coords[:, 1] - lat) ** 2
    vals = feats[int(np.argmin(d2))]["properties"]["parameter"][parameter]
    return [None if vals.get(m) in (None, FILL) else float(vals[m]) for m in MONTHS]

