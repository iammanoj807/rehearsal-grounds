"""Similarity scoring shared by the query (08) and validation (10) steps.

For a target patch t and an Earth patch e:

* ``d_g^2`` = mean squared difference of the robust-scaled features in group g
  (relief, slope, roughness, shape). Using the group mean gives every group the
  same weight however many features it has ("equal group weights").
* ``d^2 = sum_g w_g d_g^2`` with ``w_g = 1`` by default.
* ``s_morph = exp(-d^2 / (2 sigma^2))`` where sigma is the median distance from
  a query patch to its nearest candidate patch. For Earth-to-Earth queries
  (the crater benchmark) candidates exclude the query's own region, because
  neighbours in the same region overlap by 50 % and would shrink sigma towards
  zero; that gives the global Earth sigma stored by step 07. For a Moon or Mars
  target, sigma is computed from that target's own patches against the Earth
  candidates (``target_sigma``): lunar polar massifs are steeper than almost
  all Earth terrain, and the Earth-to-Earth sigma would push s_morph to ~0 for
  every Moon match, leaving the embedding to decide the ranking alone.
* ``s_embed = (1 + cos(e_t, e_e)) / 2``, taking the best of four 90-degree
  rotations of the target patch.
* ``S = 100 (w_morph s_morph + w_embed s_embed)``.

Explanation bars (0-100) are percentiles: 100 x the share of random pairs of
Earth patches from different regions that are *further apart* in that group
than this pair. 90 means "closer than 90 % of random Earth pairs".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from common import index_dir, load_config, run_dir
from features import FEATURE_GROUPS, FEATURE_NAMES

GROUPS: tuple[str, ...] = tuple(FEATURE_GROUPS)
SUB_SCORE_KEYS: tuple[str, ...] = (*GROUPS, "embedding")


@dataclass
class Index:
    """Everything a query needs, loaded from the index folder."""

    meta: pd.DataFrame
    feats: np.ndarray          # robust-scaled features, n x n_features
    emb: np.ndarray            # L2-normalised embeddings, n x 64
    rot: dict[int, np.ndarray]  # row -> 4 x 64 rotated embeddings (targets, crater queries)
    group_cols: dict[str, np.ndarray]
    sigma: float
    quantiles: dict[str, np.ndarray]
    weights: dict[str, float]


def group_columns() -> dict[str, np.ndarray]:
    """Column indices of each feature group."""
    pos = {name: i for i, name in enumerate(FEATURE_NAMES)}
    return {g: np.array([pos[n] for n in names]) for g, names in FEATURE_GROUPS.items()}


def group_sq_dists(a: np.ndarray, b: np.ndarray, cols: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Per-group mean squared differences between rows of a (m x f) and b (n x f): m x n each."""
    out = {}
    for g, idx in cols.items():
        aa, bb = a[:, idx], b[:, idx]
        sq = (aa**2).sum(1)[:, None] + (bb**2).sum(1)[None, :] - 2.0 * aa @ bb.T
        out[g] = np.maximum(sq, 0.0) / len(idx)
    return out


def morph_sq_dist(gsq: dict[str, np.ndarray], group_weights: dict[str, float] | None = None) -> np.ndarray:
    """Weighted sum of group squared distances."""
    w = group_weights or {}
    return sum(w.get(g, 1.0) * v for g, v in gsq.items())


def best_cos(query_rot: np.ndarray, emb: np.ndarray) -> np.ndarray:
    """Best cosine over the rotations of each query: (m x 4 x d) vs (n x d) -> m x n."""
    sims = np.einsum("mrd,nd->mrn", query_rot, emb)
    return sims.max(axis=1)


def combine(d2: np.ndarray, cos: np.ndarray, sigma: float, weights: dict[str, float]) -> np.ndarray:
    """Similarity score S in 0-100."""
    s_morph = np.exp(-d2 / (2.0 * sigma**2))
    s_embed = (1.0 + cos) / 2.0
    return 100.0 * (weights["morph"] * s_morph + weights["embed"] * s_embed)


def percentile_score(values: np.ndarray, quantiles: np.ndarray) -> np.ndarray:
    """100 x share of random Earth pairs further apart than ``values`` (distances)."""
    ranks = np.searchsorted(quantiles, values, side="left") / (len(quantiles) - 1)
    return 100.0 * (1.0 - np.clip(ranks, 0.0, 1.0))


def query_rotations(index: Index, rows: np.ndarray) -> np.ndarray:
    """(m x 4 x d) rotated embeddings for query rows (falls back to no rotation)."""
    out = []
    for r in rows:
        out.append(index.rot[int(r)] if int(r) in index.rot else np.repeat(index.emb[r][None], 4, axis=0))
    return np.stack(out)


def load_index() -> Index:
    """Load the scaled features, embeddings and calibration written by step 07."""
    cfg = load_config()
    idir = index_dir()
    meta = pd.read_parquet(run_dir() / "features.parquet")
    feats = np.load(idir / "features_scaled.npy")
    emb = np.load(idir / "embeddings_l2.npy")
    rot_rows = np.load(idir / "embeddings_rot_rows.npy")
    rot = np.load(idir / "embeddings_rot_l2.npy")
    calib = json.loads((idir / "calibration.json").read_text())
    quantiles = {k: np.asarray(v) for k, v in calib["quantiles"].items()}
    return Index(meta=meta, feats=feats, emb=emb, rot={int(r): rot[i] for i, r in enumerate(rot_rows)},
                 group_cols=group_columns(), sigma=float(calib["sigma"]), quantiles=quantiles,
                 weights=dict(cfg["weights"]))


def target_sigma(index: Index, q_rows: np.ndarray, e_rows: np.ndarray,
                 group_weights: dict[str, float] | None = None) -> float:
    """Median distance from each query patch to its nearest candidate patch."""
    gsq = group_sq_dists(index.feats[q_rows], index.feats[e_rows], index.group_cols)
    d2 = morph_sq_dist(gsq, group_weights)
    return float(np.median(np.sqrt(d2.min(axis=1))))


def score_block(index: Index, q_rows: np.ndarray, e_rows: np.ndarray,
                group_weights: dict[str, float] | None = None,
                weights: dict[str, float] | None = None,
                sigma: float | None = None) -> dict[str, Any]:
    """Score query rows against candidate rows; returns S, d2, cos and group d^2 matrices."""
    gsq = group_sq_dists(index.feats[q_rows], index.feats[e_rows], index.group_cols)
    d2 = morph_sq_dist(gsq, group_weights)
    cos = best_cos(query_rotations(index, q_rows), index.emb[e_rows])
    s = combine(d2, cos, index.sigma if sigma is None else sigma, weights or index.weights)
    return {"S": s, "d2": d2, "cos": cos, "gsq": gsq}
