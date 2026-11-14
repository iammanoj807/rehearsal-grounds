"""Step 08: rank Earth patches against each Moon and Mars target.

For each target, every searchable Earth patch is scored against every target
patch with the similarity S (``scoring.py``). An Earth patch's score is the
mean of its top-3 similarities across the target's patches. Patches are then
ranked, non-maximum suppression keeps sites at least ``nms_km`` apart, and the
top ``top_k_sites`` sites are kept.

For each site the best-matching target patch is recorded together with the
explanation bars (per-group percentiles) and the terrain values of both
patches. Output: ``work/results/<target_id>.parquet`` and ``summary.json``.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import numpy as np
import pandas as pd

from common import config_hash, get_logger, load_config, load_yaml, now_iso, results_dir, selected_targets
from grids import haversine_km
from scoring import GROUPS, Index, load_index, percentile_score, score_block, target_sigma

log = get_logger("08_query")
TERRAIN_KEYS = ["relief_m", "hypsometric_integral", "slope_mean", "slope_p50", "slope_p90", "rough_std_m",
                "tri_m", "curv_abs", "bowl_index"]
TOP_N_PER_PATCH = 3


def nms(lats: np.ndarray, lons: np.ndarray, order: np.ndarray, min_km: float, k: int) -> list[int]:
    """Greedy non-maximum suppression: keep ranked items at least ``min_km`` apart."""
    kept: list[int] = []
    for i in order:
        if all(haversine_km(lats[i], lons[i], lats[j], lons[j]) >= min_km for j in kept):
            kept.append(int(i))
            if len(kept) == k:
                break
    return kept


def candidate_rows(index: Index) -> np.ndarray:
    """Rows of Earth patches eligible as analog candidates."""
    m = index.meta
    return np.flatnonzero(((m["body"] == "earth") & m["search_ok"]).to_numpy())


def rank_target(index: Index, target_id: str, cfg: dict[str, Any],
                group_weights: dict[str, float] | None = None,
                sigma: float | None = None,
                weights: dict[str, float] | None = None) -> dict[str, Any]:
    """Patch scores for one target; returns arrays for downstream use.

    ``weights`` overrides the morph/embed split (validation only; the app uses the config).
    """
    m = index.meta
    q_rows = np.flatnonzero((m["source_id"] == target_id).to_numpy())
    e_rows = candidate_rows(index)
    sig = target_sigma(index, q_rows, e_rows, group_weights) if sigma is None else sigma
    res = score_block(index, q_rows, e_rows, group_weights=group_weights, sigma=sig, weights=weights)
    s = res["S"]
    top = np.sort(s, axis=0)[-TOP_N_PER_PATCH:, :]
    patch_score = top.mean(axis=0)
    best_t = s.argmax(axis=0)
    return {"q_rows": q_rows, "e_rows": e_rows, "patch_score": patch_score, "best_t": best_t, "sigma": sig, **res}


def build_sites(index: Index, ranked: dict[str, Any], cfg: dict[str, Any]) -> pd.DataFrame:
    """Apply NMS and assemble one row per kept site."""
    m = index.meta
    e_rows, score = ranked["e_rows"], ranked["patch_score"]
    lats, lons = m["lat"].to_numpy()[e_rows], m["lon"].to_numpy()[e_rows]
    order = np.argsort(-score, kind="stable")
    kept = nms(lats, lons, order, float(cfg["nms_km"]), int(cfg["top_k_sites"]))
    rows = []
    for rank, j in enumerate(kept, start=1):
        e, t = e_rows[j], ranked["q_rows"][ranked["best_t"][j]]
        ti = ranked["best_t"][j]
        rec: dict[str, Any] = {
            "rank": rank, "site_id": m.at[e, "patch_id"], "region_id": m.at[e, "source_id"],
            "lat": float(m.at[e, "lat"]), "lon": float(m.at[e, "lon"]),
            "score": float(score[j]), "best_pair_score": float(ranked["S"][ti, j]),
            "s_morph": float(np.exp(-ranked["d2"][ti, j] / (2 * ranked["sigma"] ** 2))),
            "s_embed": float((1 + ranked["cos"][ti, j]) / 2), "target_patch_id": m.at[t, "patch_id"],
            "earth_row": int(e), "target_row": int(t),
        }
        for g in GROUPS:
            rec[f"sub_{g}"] = float(percentile_score(np.sqrt(ranked["gsq"][g][ti, j]), index.quantiles[g]))
        rec["sub_embedding"] = float(percentile_score(1.0 - ranked["cos"][ti, j], index.quantiles["embedding"]))
        for key in TERRAIN_KEYS:
            rec[f"earth_{key}"] = float(m.at[e, key])
            rec[f"target_{key}"] = float(m.at[t, key])
        for col in [c for c in m.columns if c.startswith("frac_")] + ["wc_available"]:
            rec[f"earth_{col}"] = m.at[e, col]
        rows.append(rec)
    return pd.DataFrame(rows)


def coverage(index: Index, ranked: dict[str, Any]) -> dict[str, float]:
    """How much of the target has a close Earth terrain match.

    For each target patch, the nearest Earth candidate's terrain distance is
    turned into a percentile against random Earth pairs (100 = closer than all).
    """
    best = np.sqrt(ranked["d2"].min(axis=1))
    pct = percentile_score(best, index.quantiles["morph"])
    return {
        "share_close_90": float(np.mean(pct >= 90)),
        "share_close_99": float(np.mean(pct >= 99)),
        "median_best_percentile": float(np.median(pct)),
    }


def main() -> int:
    """Rank Earth sites for every selected target."""
    cfg = load_config()
    index = load_index()
    out = results_dir()
    summary: dict[str, Any] = {"generated_at": now_iso(), "config_hash": config_hash(), "targets": {}}
    for target in selected_targets(load_yaml("targets.yaml")["targets"]):
        ranked = rank_target(index, target["id"], cfg)
        sites = build_sites(index, ranked, cfg)
        sites.to_parquet(out / f"{target['id']}.parquet", index=False)
        np.save(out / f"{target['id']}_patch_scores.npy",
                np.stack([ranked["e_rows"].astype(np.float64), ranked["patch_score"]]))
        summary["targets"][target["id"]] = {
            "sigma": ranked["sigma"], "n_target_patches": int(len(ranked["q_rows"])),
            "n_candidates": int(len(ranked["e_rows"])), "n_sites": int(len(sites)),
            "coverage": coverage(index, ranked),
        }
        log.info("%s: sigma %.3f, %d target patches x %d candidates -> %d sites; top: %s",
                 target["id"], ranked["sigma"], len(ranked["q_rows"]), len(ranked["e_rows"]), len(sites),
                 ", ".join(f"{r.region_id} {r.score:.1f}" for r in sites.head(5).itertuples()))
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
