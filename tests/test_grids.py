"""Tests for resampling and the Mars projection (SPEC: Testing and guardrails)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform as warp_transform

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from grids import MARS_RADIUS_M, haversine_km, mars_aeqd_crs, mars_geographic_crs, utm_crs  # noqa: E402


def test_average_resampling_preserves_mean_elevation() -> None:
    rng = np.random.default_rng(42)
    src = (1500 + rng.normal(0, 80, size=(400, 400))).astype(np.float32)
    crs = CRS.from_epsg(32612)
    src_tf = from_origin(500_000, 3_900_000, 30, 30)
    dst = np.full((200, 200), np.nan, dtype=np.float32)
    reproject(src, dst, src_transform=src_tf, src_crs=crs, dst_transform=from_origin(500_000, 3_900_000, 60, 60),
              dst_crs=crs, resampling=Resampling.average, dst_nodata=np.nan)
    assert abs(float(np.nanmean(dst)) - float(src.mean())) < 1.0


def test_mars_aeqd_one_km_east_west_at_jezero() -> None:
    lat0, lon0 = 18.4447, 77.4508  # approximate Jezero centre; any value works
    crs = mars_aeqd_crs(lat0, lon0)
    dlon = math.degrees(1000.0 / (MARS_RADIUS_M * math.cos(math.radians(lat0))))
    xs, ys = warp_transform(mars_geographic_crs(), crs, [lon0 - dlon / 2, lon0 + dlon / 2], [lat0, lat0])
    dist = math.hypot(xs[1] - xs[0], ys[1] - ys[0])
    assert abs(dist - 1000.0) / 1000.0 < 0.01


def test_equirectangular_would_stretch_east_west() -> None:
    """Documents why the warp is needed: eqc (lat_ts=0) stretches by 1/cos(lat)."""
    lat0 = 18.4447
    eqc = CRS.from_proj4(f"+proj=eqc +lat_ts=0 +lon_0=0 +R={MARS_RADIUS_M:.0f} +units=m +no_defs")
    dlon = math.degrees(1000.0 / (MARS_RADIUS_M * math.cos(math.radians(lat0))))
    xs, _ = warp_transform(mars_geographic_crs(), eqc, [77.0, 77.0 + dlon], [lat0, lat0])
    assert (xs[1] - xs[0]) > 1040.0


def test_utm_zone_and_haversine() -> None:
    assert utm_crs(35.03, -111.02).to_epsg() == 32612
    assert utm_crs(-24.1, -70.01).to_epsg() == 32719
    assert abs(haversine_km(0, 0, 0, 1) - 111.195) < 0.01
