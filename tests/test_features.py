"""Unit tests for the terrain fingerprint (SPEC: Testing and guardrails)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from features import (  # noqa: E402
    FEATURE_NAMES, bowl_index, compute_features, fill_gaps, hillshade, rough_std_m, slope_deg,
)

RES = 60.0
N = 64


def _grid() -> tuple[np.ndarray, np.ndarray]:
    rows, cols = np.indices((N, N), dtype=np.float64)
    return rows, cols


def test_flat_plane_has_zero_slope_and_roughness() -> None:
    z = np.full((N, N), 1234.0)
    feats = compute_features(z, RES)
    assert feats["slope_mean"] == pytest.approx(0.0, abs=1e-12)
    assert feats["slope_p90"] == pytest.approx(0.0, abs=1e-12)
    assert feats["rough_std_m"] == pytest.approx(0.0, abs=1e-9)
    assert feats["tri_m"] == pytest.approx(0.0, abs=1e-12)
    assert feats["relief_m"] == pytest.approx(0.0, abs=1e-12)


def test_tilted_plane_slope_matches_gradient() -> None:
    _, cols = _grid()
    z = 0.1 * cols * RES  # gradient 0.1 m/m eastwards
    slope = slope_deg(z, RES)
    assert np.allclose(slope, math.degrees(math.atan(0.1)), atol=1e-9)
    assert math.degrees(math.atan(0.1)) == pytest.approx(5.71, abs=0.01)
    assert rough_std_m(z) == pytest.approx(0.0, abs=1e-6)


def _radial(shape_fn) -> np.ndarray:
    rows, cols = _grid()
    r = np.hypot(rows - (N - 1) / 2, cols - (N - 1) / 2) * RES
    return shape_fn(r)


def test_bowl_positive_cone_negative() -> None:
    bowl = _radial(lambda r: 200.0 * (r / 1900.0) ** 2)
    cone = _radial(lambda r: 500.0 - 0.25 * r)
    assert bowl_index(bowl) > 0.3
    assert bowl_index(cone) < -0.3


@pytest.mark.parametrize("k", [1, 2, 3])
def test_features_rotation_invariant(k: int) -> None:
    rng = np.random.default_rng(42)
    from scipy.ndimage import gaussian_filter
    z = gaussian_filter(rng.normal(size=(N, N)), 3) * 400 + np.indices((N, N))[1] * 5.0
    a = compute_features(z, RES)
    b = compute_features(np.rot90(z, k), RES)
    for name in FEATURE_NAMES:
        assert a[name] == pytest.approx(b[name], abs=1e-6, rel=1e-6), name


def test_fill_gaps_uses_neighbours() -> None:
    z = np.arange(16, dtype=float).reshape(4, 4)
    z[1, 1] = np.nan
    filled = fill_gaps(z)
    assert np.isfinite(filled).all()
    assert filled[1, 1] in {z[0, 1], z[1, 0], z[1, 2], z[2, 1], z[0, 0], z[0, 2], z[2, 0], z[2, 2]}


def test_hillshade_lights_northwest_facing_slopes() -> None:
    rows, cols = _grid()
    # Elevation rising to the south-east: slope faces north-west, toward the light.
    facing_nw = (rows + cols) * 10.0
    facing_se = -(rows + cols) * 10.0
    assert hillshade(facing_nw, RES).mean() > hillshade(facing_se, RES).mean()
    flat = hillshade(np.zeros((N, N)), RES)
    assert np.allclose(flat, math.sin(math.radians(45)))
