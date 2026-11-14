"""Step 07: scale features, normalise embeddings, build the search index.

* Features: log1p transforms, then robust scaling with the median and
  interquartile range of *Earth* patches. Columns whose IQR is ~0 (e.g. the
  45-90 degree slope bin) fall back to the standard deviation, then to 1.
  Scaled values are clipped to +/-8 so a single extreme column cannot dominate.
* Embeddings: L2-normalised again after PCA.
* A FAISS inner-product index over Earth embeddings (exact, ``IndexFlatIP``)
  is saved for fast embedding-only lookups; full scoring is exact NumPy.
* Calibration: sigma for ``s_morph`` and the random-pair distance quantiles
  behind the explanation bars (see ``scoring.py``).

Outputs in ``work/index/``: ``features_scaled.npy``, ``embeddings_l2.npy``,
``embeddings_rot_l2.npy``, ``scaler.joblib``, ``faiss_earth.index``,
``calibration.json``.
"""

from __future__ import annotations

import json
import sys

import joblib
import numpy as np
import pandas as pd

from common import config_hash, get_logger, index_dir, load_config, now_iso, run_dir
from features import FEATURE_NAMES, transform_features
from scoring import GROUPS, group_columns, group_sq_dists, morph_sq_dist

log = get_logger("07_index")
CLIP = 8.0
N_SIGMA_QUERIES = 5000
N_RANDOM_PAIRS = 200_000
N_QUANTILES = 1001


def robust_scaler(x_earth: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Median and scale (IQR, falling back to std, then 1) per column."""
    med = np.median(x_earth, axis=0)
    q75, q25 = np.percentile(x_earth, [75, 25], axis=0)
    scale = q75 - q25
    std = x_earth.std(axis=0)
    scale = np.where(scale > 1e-9, scale, np.where(std > 1e-9, std, 1.0))
    return med, scale


def l2n(x: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalisation (works on any leading shape)."""
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)


def cross_region_nn_sigma(feats: np.ndarray, regions: np.ndarray, rng: np.random.Generator) -> float:
    """Median distance from sampled Earth patches to their nearest patch in another region."""
    cols = group_columns()
    n = len(feats)
    sample = rng.choice(n, size=min(N_SIGMA_QUERIES, n), replace=False)
    nn = np.empty(len(sample))
    for start in range(0, len(sample), 250):
        q = sample[start:start + 250]
        d2 = morph_sq_dist(group_sq_dists(feats[q], feats, cols))
        d2[regions[q][:, None] == regions[None, :]] = np.inf
        nn[start:start + 250] = np.sqrt(d2.min(axis=1))
    return float(np.median(nn))


def random_pair_quantiles(feats: np.ndarray, emb: np.ndarray, regions: np.ndarray,
                          rng: np.random.Generator) -> dict[str, list[float]]:
    """Quantiles of group distances and embedding distance (1 - cos) over random cross-region pairs."""
    cols = group_columns()
    n = len(feats)
    a = rng.integers(0, n, size=N_RANDOM_PAIRS * 2)
    b = rng.integers(0, n, size=N_RANDOM_PAIRS * 2)
    keep = regions[a] != regions[b]
    a, b = a[keep][:N_RANDOM_PAIRS], b[keep][:N_RANDOM_PAIRS]
    qs = np.linspace(0, 1, N_QUANTILES)
    out: dict[str, list[float]] = {}
    for g in GROUPS:
        idx = cols[g]
        d = np.sqrt(((feats[a][:, idx] - feats[b][:, idx]) ** 2).mean(axis=1))
        out[g] = np.quantile(d, qs).tolist()
    cos = (emb[a] * emb[b]).sum(axis=1)
    out["embedding"] = np.quantile(1.0 - cos, qs).tolist()
    total = np.sqrt(sum(((feats[a][:, cols[g]] - feats[b][:, cols[g]]) ** 2).mean(axis=1) for g in GROUPS))
    out["morph"] = np.quantile(total, qs).tolist()
    return out


def main() -> int:
    """Build scaled features, embeddings, FAISS index and calibration."""
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["seed"]))
    idir = index_dir()
    meta = pd.read_parquet(run_dir() / "features.parquet")
    earth = (meta["body"] == "earth").to_numpy()

    x = transform_features(meta[FEATURE_NAMES].to_numpy())
    med, scale = robust_scaler(x[earth])
    feats = np.clip((x - med) / scale, -CLIP, CLIP).astype(np.float64)
    joblib.dump({"median": med, "scale": scale, "names": FEATURE_NAMES, "clip": CLIP}, idir / "scaler.joblib")
    np.save(idir / "features_scaled.npy", feats)

    emb = l2n(np.load(idir / "embeddings.npy").astype(np.float64))
    rot = l2n(np.load(idir / "embeddings_rot.npy").astype(np.float64))
    np.save(idir / "embeddings_l2.npy", emb)
    np.save(idir / "embeddings_rot_l2.npy", rot)

    try:
        import faiss  # noqa: PLC0415

        index = faiss.IndexFlatIP(emb.shape[1])
        index.add(emb[earth].astype(np.float32))
        faiss.write_index(index, str(idir / "faiss_earth.index"))
        log.info("FAISS index: %d Earth vectors", index.ntotal)
    except ImportError:
        log.warning("faiss not installed; NumPy search only")

    regions = meta["source_id"].to_numpy()
    e_rows = np.flatnonzero(earth)
    sigma = cross_region_nn_sigma(feats[e_rows], regions[e_rows], rng)
    quantiles = random_pair_quantiles(feats[e_rows], emb[e_rows], regions[e_rows], rng)
    calib = {
        "generated_at": now_iso(), "config_hash": config_hash(), "sigma": sigma,
        "sigma_rule": "median distance from 5000 random Earth patches to their nearest patch in a different region",
        "n_random_pairs": N_RANDOM_PAIRS, "quantiles": quantiles,
    }
    (idir / "calibration.json").write_text(json.dumps(calib))
    log.info("sigma = %.3f; random-pair median morph distance = %.3f", sigma, np.median(quantiles["morph"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
