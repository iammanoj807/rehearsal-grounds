"""Step 05: compute the terrain fingerprint of every patch.

Reads ``patches/<source>.npy`` and ``.parquet`` for every selected source,
fills the few missing pixels (at most 5 % by construction) from their nearest
neighbour, and computes the features in ``features.py``. It also sets:

* ``relief_ok``: relief >= ``min_relief_m`` (drops sea, lakes and salt pans);
* ``search_ok``: Earth patches usable as analog candidates
  (``wc_ok`` and ``relief_ok``); always True for targets.

Output: ``features.parquet`` (one row per patch, metadata plus raw features).
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from common import get_logger, load_config, load_yaml, patches_dir, run_dir, selected_regions, selected_targets
from features import FEATURE_NAMES, compute_features, fill_gaps

log = get_logger("05_features")


def features_for_array(args: tuple[np.ndarray, float]) -> np.ndarray:
    """Feature matrix (n, n_features) for a stack of patches."""
    arrays, res = args
    out = np.empty((len(arrays), len(FEATURE_NAMES)), dtype=np.float64)
    for i, z in enumerate(arrays):
        feats = compute_features(fill_gaps(z), res)
        out[i] = [feats[name] for name in FEATURE_NAMES]
    return out


def source_ids() -> list[str]:
    """Ids of every selected target and region, targets first."""
    targets = [t["id"] for t in selected_targets(load_yaml("targets.yaml")["targets"])]
    regions = [r["id"] for r in selected_regions(load_yaml("regions.yaml")["regions"])]
    return targets + regions


def main() -> int:
    """Compute features for all patches and write ``features.parquet``."""
    cfg = load_config()
    res = float(cfg["resolution_m"])
    pdir = patches_dir()
    tables, jobs = [], []
    for sid in source_ids():
        arrays = np.load(pdir / f"{sid}.npy")
        table = pd.read_parquet(pdir / f"{sid}.parquet")
        tables.append(table)
        for chunk in np.array_split(arrays, max(1, len(arrays) // 256)):
            jobs.append((chunk, res))
    with ProcessPoolExecutor() as pool:
        feats = np.concatenate(list(pool.map(features_for_array, jobs)), axis=0)
    meta = pd.concat(tables, ignore_index=True)
    if len(meta) != len(feats):
        raise RuntimeError(f"row mismatch: {len(meta)} metadata rows vs {len(feats)} feature rows")
    df = pd.concat([meta, pd.DataFrame(feats, columns=FEATURE_NAMES)], axis=1)
    if not np.isfinite(df[FEATURE_NAMES].to_numpy()).all():
        raise RuntimeError("non-finite feature values")
    df["relief_ok"] = df["relief_m"] >= float(cfg["min_relief_m"])
    is_earth = df["body"] == "earth"
    df["search_ok"] = ~is_earth | (df["wc_ok"].fillna(True).astype(bool) & df["relief_ok"])
    out = run_dir() / "features.parquet"
    df.to_parquet(out, index=False)
    for body, group in df.groupby("body"):
        log.info("%s: %d patches; slope_p50 median %.1f deg; relief median %.0f m; search_ok %d",
                 body, len(group), group["slope_p50"].median(), group["relief_m"].median(), int(group["search_ok"].sum()))
    log.info("wrote %s (%d rows, %d features)", out, len(df), len(FEATURE_NAMES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
