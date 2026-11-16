"""Tests for crater injection: geometry, diffusion, counts, identity at zero density."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import craters  # noqa: E402


def isolated(D: float, res: float = 30.0, n: int = 256) -> np.ndarray:
    ys, xs = np.mgrid[0:n, 0:n]
    c = (n / 2) * res
    return craters.profile(np.hypot((xs + 0.5) * res - c, (ys + 0.5) * res - c), D)


def test_isolated_crater_depth_rim_and_diameter_within_one_pixel() -> None:
    D, res = 2000.0, 30.0
    z = isolated(D, res)
    row = z[z.shape[0] // 2]
    R, h, d = D / 2, craters.rim_m(D), craters.depth_m(D)
    assert craters.profile(np.array([R]), D)[0] == pytest.approx(h)                # rim height exactly at r = R
    assert craters.profile(np.array([0.0]), D)[0] == pytest.approx(h - d)          # floor: apparent depth below the rim
    near = craters.profile(np.array([R - res, R + res]), D)
    assert near.min() <= row.max() <= h                                           # gridded rim within one pixel of the crest
    assert row.max() - z.min() == pytest.approx(d, rel=0.03)                      # apparent depth on the grid
    left, right = np.argmax(row[: len(row) // 2]), len(row) // 2 + np.argmax(row[len(row) // 2:])
    assert abs((right - left) * res - D) <= res                                   # rim-crest diameter within one pixel
    assert craters.depth_m(1000.0) == pytest.approx(196.0, rel=1e-6)              # Pike: 0.196 D^1.01 (D, d in km)


def test_diffusion_matches_analytic_gaussian() -> None:
    res, s, kt = 30.0, 90.0, 4000.0
    n = 201; ys, xs = np.mgrid[0:n, 0:n]
    r2 = ((xs - n // 2) * res) ** 2 + ((ys - n // 2) * res) ** 2
    bump = np.exp(-r2 / (2 * s * s))
    out = craters.diffuse(bump, kt, res)
    expected_peak = s * s / (s * s + 2 * kt)                                       # 2-D heat equation on a Gaussian
    assert out.max() == pytest.approx(expected_peak, rel=0.02)
    assert out.sum() == pytest.approx(bump.sum(), rel=1e-3)                       # mass conserved


def test_counts_match_density_within_poisson_error() -> None:
    rng = np.random.default_rng(0)
    res, shape, dens = 60.0, (64, 64), 3.0
    counts = [craters.crater_field(shape, res, dens, rng, degrade=False)[1] for _ in range(300)]
    expected = dens * (64 * 60 / 1000) ** 2
    se = np.sqrt(expected / len(counts))
    assert abs(np.mean(counts) - expected) < 4 * se


def test_size_distribution_slope() -> None:
    d = craters.sample_diameters(200000, np.random.default_rng(1))
    assert d.min() >= craters.D_MIN and d.max() <= craters.D_MAX
    frac = (d >= 480).mean() / 1.0
    expected = ((480 / 240) ** -2 - (240 / 2000) ** 2) / (1 - (240 / 2000) ** 2)
    assert frac == pytest.approx(expected, rel=0.02)


def test_zero_density_returns_input_exactly() -> None:
    z = np.random.default_rng(2).normal(0, 10, (64, 64))
    assert craters.inject(z, 60.0, 0.0, seed=1) is z
    assert np.array_equal(craters.inject(z, 60.0, 0.0, seed=1), z)
