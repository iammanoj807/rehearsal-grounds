"""Tests for the low-sun lighting computations."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import lighting  # noqa: E402

RES = 60.0
MARGIN, PATCH = 64, 64


def test_sun_band_near_the_pole() -> None:
    lo, hi = lighting.sun_band(-86.0)
    assert lo == pytest.approx(2.46) and hi == pytest.approx(5.54)
    assert lighting.sun_band(-89.9) == (0.0, pytest.approx(1.64))
    assert lighting.band_elevations((2.46, 5.54), (1, 2, 3, 5, 10)) == [3, 5]
    assert lighting.band_elevations((0.2, 0.8), (1, 2, 3, 5, 10)) == [1]


def test_flat_plane_has_no_cast_shadow() -> None:
    window = np.zeros((PATCH + 2 * MARGIN, PATCH + 2 * MARGIN))
    for e in (1.0, 5.0):
        hor = lighting.horizon_angles(window, RES, 90.0, lighting.R_EARTH_M, MARGIN, PATCH)
        assert not (hor > e).any()
        assert not lighting.attached_shadow(window[MARGIN:-MARGIN, MARGIN:-MARGIN], RES, 90.0, e).any()


def test_vertical_step_casts_shadow_of_length_h_over_tan_e() -> None:
    # A 100 m wall along a column, Sun in the east: the shadow falls west of the wall.
    h, e = 100.0, 10.0
    window = np.zeros((PATCH + 2 * MARGIN, PATCH + 2 * MARGIN))
    wall_col = MARGIN + 40
    window[:, wall_col:] = h
    hor = lighting.horizon_angles(window, RES, 90.0, 1e12, MARGIN, PATCH)  # flat world: no curvature
    row = hor[PATCH // 2]
    shadowed = np.flatnonzero(row[: wall_col - MARGIN] > e)
    length_px = (wall_col - MARGIN) - shadowed.min()
    expected_px = h / np.tan(np.radians(e)) / RES
    assert abs(length_px - expected_px) <= 1.0


def test_curvature_drop_at_10_km() -> None:
    d = 10_000.0
    assert d * d / (2 * lighting.R_EARTH_M) == pytest.approx(7.848, abs=0.01)
    assert d * d / (2 * lighting.R_MOON_M) == pytest.approx(28.778, abs=0.01)
    # On a sphere-flat grid, a point 10 km away at the same height sits below the horizontal by d / (2R).
    window = np.zeros((1, 200))
    ang = np.degrees(np.arctan2(0.0 - d * d / (2 * lighting.R_MOON_M), d))
    assert ang == pytest.approx(-np.degrees(d / (2 * lighting.R_MOON_M)), rel=1e-3)
    assert window.shape == (1, 200)


def test_lighting_similarity_bounds() -> None:
    s = {1.0: 0.4, 3.0: 0.2}
    assert lighting.lighting_similarity(s, s, [1.0, 3.0]) == pytest.approx(100.0)
    assert lighting.lighting_similarity({1.0: 1.0}, {1.0: 0.0}, [1.0]) == pytest.approx(0.0)


def test_solar_elevation_matches_published_spa_example() -> None:
    # NREL Solar Position Algorithm example (Reda and Andreas 2004, NREL/TP-560-34302): 2003-10-17
    # 12:30:30 local time (UTC-7) at 39.742476 N, 105.1786 W. The report gives the topocentric
    # elevation without refraction e0 = 39.872046 deg (and 39.888378 deg with refraction).
    t = dt.datetime(2003, 10, 17, 19, 30, 30, tzinfo=dt.timezone.utc)
    e = lighting.solar_elevation(39.742476, -105.1786, t)
    assert e == pytest.approx(39.872046, abs=0.05)


def test_monthly_sun_hours_shape_and_polar_night() -> None:
    hours = lighting.monthly_sun_hours(78.0, 15.0, 2025, 5.0, step_min=15)
    assert [h["month"] for h in hours] == list(range(1, 13))
    assert hours[11]["daylight_h"] == 0.0  # Svalbard in December: polar night
    assert all(0.0 <= h["low_sun_h"] <= h["daylight_h"] <= 24.0 for h in hours)


def test_low_sun_minutes_are_not_quantised() -> None:
    # Mid-latitude site (the JETT5 area, 35.6 N): low-sun time changes smoothly from day to day,
    # and the 1-minute sampling agrees with a 10-second reference within 2 minutes.
    lat, lon, upper = 35.58, -111.63, 5.58
    days = [dt.date(2025, 3, d) for d in range(10, 21)]
    lows = [lighting.day_sun_hours(lat, lon, d, upper, 60.0)[1] * 60.0 for d in days]
    assert max(abs(a - b) for a, b in zip(lows, lows[1:])) < 2.0
    for month in (1, 4, 7, 10):
        d = dt.date(2025, month, 15)
        coarse = lighting.day_sun_hours(lat, lon, d, upper, 60.0)[1] * 60.0
        fine = lighting.day_sun_hours(lat, lon, d, upper, 10.0)[1] * 60.0
        assert abs(coarse - fine) < 2.0


def test_read_window_flags_edges() -> None:
    grid = np.arange(400.0).reshape(20, 20)
    w, edge = lighting.read_window(grid, 5, 5, 4, 3)
    assert w.shape == (10, 10) and not edge
    w2, edge2 = lighting.read_window(grid, 0, 0, 4, 3)
    assert edge2 and np.isnan(w2[0, 0])
