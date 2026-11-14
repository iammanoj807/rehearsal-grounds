"""Terrain fingerprint: pure, unit-tested functions on one elevation patch.

Every function takes a 2-D elevation array ``z`` in metres on a square grid
with spacing ``res`` metres. All features are rotation-invariant (they do not
change when the patch is rotated by 90 degrees), because Moon, Mars and Earth
patches share no common orientation.

Feature groups used for similarity and for the explanation bars:

* relief: ``relief_m``, ``hypsometric_integral``
* slope: ``slope_mean``, ``slope_p50``, ``slope_p90``, ``slope_std``,
  ``slope_hist_0`` ... ``slope_hist_7``, ``slope_p50_120m``, ``slope_p90_120m``
* roughness: ``rough_std_m``, ``tri_m``
* shape: ``curv_abs``, ``bowl_index``
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

SLOPE_BINS_DEG = (0, 2, 5, 10, 15, 20, 30, 45, 90)

FEATURE_GROUPS: dict[str, list[str]] = {
    "relief": ["relief_m", "hypsometric_integral"],
    "slope": [
        "slope_mean", "slope_p50", "slope_p90", "slope_std",
        *[f"slope_hist_{i}" for i in range(len(SLOPE_BINS_DEG) - 1)],
        "slope_p50_120m", "slope_p90_120m",
    ],
    "roughness": ["rough_std_m", "tri_m"],
    "shape": ["curv_abs", "bowl_index"],
}
FEATURE_NAMES: list[str] = [name for names in FEATURE_GROUPS.values() for name in names]

# Features that get log1p before scaling (heavy-tailed, strictly >= 0).
LOG_FEATURES = ("relief_m", "rough_std_m", "tri_m", "curv_abs")
# curv_abs is stored in 1/m; it is multiplied by this factor (-> 1/km) before
# log1p so the log actually compresses its tail.
CURV_LOG_SCALE = 1000.0


def slope_deg(z: np.ndarray, res: float) -> np.ndarray:
    """Slope in degrees: arctan of the gradient magnitude from ``np.gradient``."""
    gy, gx = np.gradient(z.astype(np.float64), res)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def hillshade(z: np.ndarray, res: float, azimuth_deg: float = 315.0, altitude_deg: float = 45.0) -> np.ndarray:
    """Hillshade in [0, 1] with no vertical exaggeration (standard GIS formula).

    Rows run north to south and columns west to east, as in a north-up raster.
    """
    gy, gx = np.gradient(z.astype(np.float64), res)
    # np.gradient's row axis increases southwards; flip so dz/dy points north.
    dzdx, dzdy = gx, -gy
    az, alt = np.radians(azimuth_deg), np.radians(altitude_deg)
    light = np.array([np.sin(az) * np.cos(alt), np.cos(az) * np.cos(alt), np.sin(alt)])
    norm = np.sqrt(dzdx**2 + dzdy**2 + 1.0)
    shade = (-dzdx * light[0] - dzdy * light[1] + light[2]) / norm
    return np.clip(shade, 0.0, 1.0)


def relief_m(z: np.ndarray) -> float:
    """95th minus 5th percentile elevation."""
    p5, p95 = np.percentile(z, [5, 95])
    return float(p95 - p5)


def hypsometric_integral(z: np.ndarray) -> float:
    """(mean - min) / (max - min); 0.5 for a flat or symmetric patch."""
    zmin, zmax = float(z.min()), float(z.max())
    if zmax - zmin < 1e-9:
        return 0.5
    return float((z.mean() - zmin) / (zmax - zmin))


def plane_residuals(z: np.ndarray) -> np.ndarray:
    """Residuals of ``z`` after a least-squares plane fit."""
    rows, cols = np.indices(z.shape, dtype=np.float64)
    design = np.column_stack([np.ones(z.size), rows.ravel(), cols.ravel()])
    coef, *_ = np.linalg.lstsq(design, z.ravel().astype(np.float64), rcond=None)
    return (z.astype(np.float64) - (design @ coef).reshape(z.shape))


def rough_std_m(z: np.ndarray) -> float:
    """Standard deviation of plane-fit residuals (m)."""
    return float(plane_residuals(z).std())


def tri_m(z: np.ndarray) -> float:
    """Terrain ruggedness index: mean absolute difference from the 8 neighbours."""
    z = z.astype(np.float64)
    centre = z[1:-1, 1:-1]
    diffs = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nb = z[1 + dr: z.shape[0] - 1 + dr, 1 + dc: z.shape[1] - 1 + dc]
            diffs.append(np.abs(nb - centre))
    return float(np.mean(np.stack(diffs)))


def curv_abs(z: np.ndarray, res: float) -> float:
    """Mean absolute Laplacian of ``z`` divided by ``res**2`` (units 1/m)."""
    lap = ndimage.laplace(z.astype(np.float64), mode="reflect")
    return float(np.mean(np.abs(lap)) / res**2)


def _radius_grid(shape: tuple[int, int]) -> np.ndarray:
    """Distance of each pixel centre from the patch centre, in pixels."""
    rows, cols = np.indices(shape, dtype=np.float64)
    rc, cc = (shape[0] - 1) / 2.0, (shape[1] - 1) / 2.0
    return np.hypot(rows - rc, cols - cc)


def bowl_index(z: np.ndarray, relief: float | None = None, inner_px: float = 16.0) -> float:
    """(mean z of the outer ring - mean z of the central disk) / relief.

    The central disk has radius ``inner_px`` (16 px = 960 m at 60 m). The outer
    ring is the band from 1.5x that radius out to the inscribed circle. The
    index is positive for bowls (craters) and negative for domes and cones.
    """
    rel = relief_m(z) if relief is None else relief
    if rel < 1e-6:
        return 0.0
    radius = _radius_grid(z.shape)
    outer_max = min(z.shape) / 2.0
    disk = radius <= inner_px
    ring = (radius >= 1.5 * inner_px) & (radius <= outer_max)
    return float((z[ring].mean() - z[disk].mean()) / rel)


def downsample2(z: np.ndarray) -> np.ndarray:
    """2 x 2 block mean (drops a trailing odd row or column)."""
    h, w = (z.shape[0] // 2) * 2, (z.shape[1] // 2) * 2
    zz = z[:h, :w].astype(np.float64)
    return zz.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))


def slope_stats(slope: np.ndarray) -> dict[str, float]:
    """Mean, median, 90th percentile, std and 8-bin histogram shares of slope."""
    flat = slope.ravel()
    hist, _ = np.histogram(np.clip(flat, 0, 90), bins=SLOPE_BINS_DEG)
    out = {
        "slope_mean": float(flat.mean()),
        "slope_p50": float(np.percentile(flat, 50)),
        "slope_p90": float(np.percentile(flat, 90)),
        "slope_std": float(flat.std()),
    }
    shares = hist / max(flat.size, 1)
    out.update({f"slope_hist_{i}": float(v) for i, v in enumerate(shares)})
    return out


def compute_features(z: np.ndarray, res: float) -> dict[str, float]:
    """Full terrain fingerprint of one patch (raw, untransformed values)."""
    if not np.all(np.isfinite(z)):
        raise ValueError("patch contains non-finite values; fill gaps first")
    slope = slope_deg(z, res)
    rel = relief_m(z)
    feats: dict[str, float] = {"relief_m": rel, "hypsometric_integral": hypsometric_integral(z)}
    feats.update(slope_stats(slope))
    slope120 = slope_deg(downsample2(z), 2 * res)
    feats["slope_p50_120m"] = float(np.percentile(slope120, 50))
    feats["slope_p90_120m"] = float(np.percentile(slope120, 90))
    feats["rough_std_m"] = rough_std_m(z)
    feats["tri_m"] = tri_m(z)
    feats["curv_abs"] = curv_abs(z, res)
    feats["bowl_index"] = bowl_index(z, rel)
    return {name: feats[name] for name in FEATURE_NAMES}


def transform_features(values: np.ndarray, names: list[str] | None = None) -> np.ndarray:
    """Apply the log1p transforms to a (n, n_features) array of raw features."""
    names = names or FEATURE_NAMES
    out = values.astype(np.float64).copy()
    for i, name in enumerate(names):
        if name in LOG_FEATURES:
            col = np.maximum(out[:, i], 0.0)
            if name == "curv_abs":
                col = col * CURV_LOG_SCALE
            out[:, i] = np.log1p(col)
    return out


def fill_gaps(z: np.ndarray) -> np.ndarray:
    """Replace non-finite pixels by their nearest finite neighbour."""
    mask = ~np.isfinite(z)
    if not mask.any():
        return z
    if mask.all():
        raise ValueError("patch has no finite pixels")
    idx = ndimage.distance_transform_edt(mask, return_distances=False, return_indices=True)
    return z[tuple(idx)]


def detrended_unit(z: np.ndarray) -> np.ndarray:
    """Plane-detrended elevation scaled to [0, 1] within the patch."""
    resid = plane_residuals(z)
    lo, hi = resid.min(), resid.max()
    if hi - lo < 1e-9:
        return np.full(z.shape, 0.5)
    return (resid - lo) / (hi - lo)
