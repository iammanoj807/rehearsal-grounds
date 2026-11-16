"""Synthetic simple lunar craters added to Earth elevation patches (the "Earth with lunar craters (simulated)" view).

Profile of one crater of rim-crest diameter D (metres), radius R = D / 2:
- apparent depth (rim crest to floor) d = 0.196 D^1.01 with D, d in km, for D < 15 km: Pike (1977), as quoted by
  Feoktistova and Ipatov (arXiv:2103.00291, Eq. 1);
- rim height above the surroundings h = 0.036 D for simple craters: Pike, as quoted by the IMPACTS program paper
  (arXiv:2203.07476, Sect. on rim height);
- inside the rim a parabolic bowl, z(r) = (h - d) + d (r / R)^2, so z(0) = h - d and z(R) = h;
- outside the rim the ejecta falls as (r / R)^-3: McGetchin, Settle and Head (1973), quoted as t = 0.14 R^0.74 (r/R)^-3
  in arXiv:2511.14442 (Eq. 4). The exponent is used with Pike's rim height as the amplitude, so the profile is
  continuous at the rim (our choice). The ejecta is cut at 5 R (our choice).
Degradation: linear diffusion of each crater's own relief for a random time, i.e. a Gaussian of variance 2 kappa t;
kappa = 5.5 m^2/Myr is the lunar average of Fassett and Thomson (2014, JGR Planets 119, 2255), t uniform in
0-3,000 Myr (our choice, the period that average covers).
Sizes: 240 m - 2 km from N(>D) proportional to D^-b with b = 2, the equilibrium slope of small lunar craters
(Minton et al. 2019, arXiv:1902.07746). Positions uniform; overlapping craters add. The relief is computed on a 2x
supersampled grid and area-averaged to the patch resolution.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

D_MIN, D_MAX = 240.0, 2000.0
B_SLOPE = 2.0
KAPPA = 5.5                 # m^2 / Myr
T_MAX_MYR = 3000.0          # our choice
EJECTA_CUT = 5.0            # radii, our choice


def depth_m(D: float) -> float:
    return 0.196 * (D / 1000.0) ** 1.01 * 1000.0


def rim_m(D: float) -> float:
    return 0.036 * D


def profile(r: np.ndarray, D: float) -> np.ndarray:
    """Relief (m) at distance r (m) from the centre of a fresh crater of diameter D (m)."""
    R, d, h = D / 2.0, depth_m(D), rim_m(D)
    inside = (h - d) + d * (r / R) ** 2
    with np.errstate(divide="ignore"):
        outside = np.where(r <= EJECTA_CUT * R, h * (np.maximum(r, R) / R) ** -3.0, 0.0)
    return np.where(r <= R, inside, outside)


def diffuse(z: np.ndarray, kappa_t: float, res: float) -> np.ndarray:
    """Linear diffusion for kappa * t (m^2): Gaussian smoothing with sigma = sqrt(2 kappa t)."""
    if kappa_t <= 0:
        return z
    return ndimage.gaussian_filter(z, np.sqrt(2.0 * kappa_t) / res, mode="constant")


def sample_diameters(n: int, rng: np.random.Generator, b: float = B_SLOPE) -> np.ndarray:
    """Inverse CDF of a power law N(>D) ~ D^-b truncated to [D_MIN, D_MAX]."""
    u = rng.random(n)
    a = 1.0 - (D_MIN / D_MAX) ** b
    return D_MIN * (1.0 - u * a) ** (-1.0 / b)


def crater_field(shape: tuple[int, int], res: float, density_km2: float, rng: np.random.Generator,
                 degrade: bool = True) -> tuple[np.ndarray, int]:
    """Relief (m) of injected craters on a grid of ``shape`` at ``res`` m, plus the count placed.

    ``density_km2`` is the number of craters with D >= 240 m per km2. Centres are placed over the patch plus a margin
    of D_MAX (so craters cut by the edge appear at the right rate); the count is Poisson.
    """
    H, W = shape
    sup = 2
    hs, ws, rs = H * sup, W * sup, res / sup
    field = np.zeros((hs, ws))
    if density_km2 <= 0:
        return field.reshape(H, sup, W, sup).mean(axis=(1, 3)), 0
    m = D_MAX
    area_km2 = (H * res + 2 * m) * (W * res + 2 * m) / 1e6
    n = int(rng.poisson(density_km2 * area_km2))
    ys, xs = np.mgrid[0:hs, 0:ws]
    xs = (xs + 0.5) * rs; ys = (ys + 0.5) * rs
    placed = 0
    for D in sample_diameters(n, rng):
        cx = rng.uniform(-m, W * res + m); cy = rng.uniform(-m, H * res + m)
        reach = EJECTA_CUT * D / 2 + (np.sqrt(2 * KAPPA * T_MAX_MYR) * 3 if degrade else 0)
        r0, r1 = int(max(0, (cy - reach) / rs)), int(min(hs, (cy + reach) / rs + 1))
        c0, c1 = int(max(0, (cx - reach) / rs)), int(min(ws, (cx + reach) / rs + 1))
        if r0 >= r1 or c0 >= c1:
            continue
        sub = profile(np.hypot(xs[r0:r1, c0:c1] - cx, ys[r0:r1, c0:c1] - cy), D)
        if degrade:
            sub = diffuse(sub, KAPPA * rng.uniform(0, T_MAX_MYR), rs)
        field[r0:r1, c0:c1] += sub
        if 0 <= cx < W * res and 0 <= cy < H * res:
            placed += 1
    return field.reshape(H, sup, W, sup).mean(axis=(1, 3)), placed


def inject(z: np.ndarray, res: float, density_km2: float, seed: int, degrade: bool = True) -> np.ndarray:
    """The patch with craters added (zero density returns the input unchanged)."""
    if density_km2 <= 0:
        return z
    f, _ = crater_field(z.shape, res, density_km2, np.random.default_rng(seed), degrade)
    return z + f
