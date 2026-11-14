"""Step 08b: how the usual analog sites compare, per target.

For every well-studied region and every target this reports, using the app's own
similarity score and the target's own sigma from step 08 (nothing new is mixed
into the score):

* the region's best patch among searchable patches, its score and its rank among
  all searchable Earth patches (1 = best);
* the same with the land-cover masks off (every valid Earth grid patch, including
  vegetated, wet, icy and flat ones), and a flag when the region's best patch is
  one the masks remove.

For the region that holds a cited field test (``field_test`` in regions.yaml: the
SP Crater region in the San Francisco Volcanic Field, where NASA's JETT5 ran) it
also lists the top three shortlisted sites that score higher, and the terrain
groups where each one is closer to the target than the field-test patch.
Wording in the app: "closer terrain match on our fingerprint".

Output: ``work/results/usual_sites.json`` (validated by schemas.UsualSites in step 11).
"""

from __future__ import annotations

import importlib
import json
import sys
from typing import Any

import numpy as np
import pandas as pd

from common import get_logger, load_config, load_yaml, results_dir, selected_targets
from scoring import GROUPS, Index, load_index, percentile_score, score_block

log = get_logger("08b_usual_sites")
query = importlib.import_module("08_query")
TOP_N_PER_PATCH = query.TOP_N_PER_PATCH
CHUNK = 8000
N_OUTRANK = 3


def patch_scores(index: Index, q_rows: np.ndarray, e_rows: np.ndarray, sigma: float) -> np.ndarray:
    """App score of each candidate patch: mean of its top-3 similarities over the target's patches."""
    out = np.empty(len(e_rows))
    for i in range(0, len(e_rows), CHUNK):
        chunk = e_rows[i:i + CHUNK]
        s = score_block(index, q_rows, chunk, sigma=sigma)["S"]
        out[i:i + CHUNK] = np.sort(s, axis=0)[-TOP_N_PER_PATCH:, :].mean(axis=0)
    return out


def sub_scores(index: Index, q_rows: np.ndarray, e: int, sigma: float) -> dict[str, float]:
    """Explanation bars of one Earth patch against its best-matching target patch (as in step 08)."""
    res = score_block(index, q_rows, np.array([e]), sigma=sigma)
    ti = int(np.argmax(res["S"][:, 0]))
    out = {g: float(percentile_score(np.sqrt(res["gsq"][g][ti, 0]), index.quantiles[g])) for g in GROUPS}
    out["embedding"] = float(percentile_score(1.0 - res["cos"][ti, 0], index.quantiles["embedding"]))
    return out


def rank_of(score: float, all_scores: np.ndarray) -> int:
    """1-based rank of a score among all scores (ties share the better rank)."""
    return int((all_scores > score).sum()) + 1


def region_rows(index: Index, regions: list[dict[str, Any]], e_all: np.ndarray, s_all: np.ndarray,
                searchable: np.ndarray) -> list[dict[str, Any]]:
    """Best-patch score and rank per well-studied region, masks on and off."""
    src = index.meta["source_id"].to_numpy()[e_all]
    s_masked = s_all[searchable]
    rows = []
    for reg in regions:
        sel = src == reg["id"]
        if not sel.any():
            continue
        j_all = np.flatnonzero(sel)[np.argmax(s_all[sel])]
        sel_m = sel & searchable
        rec: dict[str, Any] = {
            "region_id": reg["id"], "name": reg["name"],
            "best_score_masks_off": float(s_all[j_all]), "rank_masks_off": rank_of(s_all[j_all], s_all),
            "n_candidates_masks_off": int(len(s_all)),
            "best_patch_masked": bool(not searchable[j_all]),
            "best_score": None, "rank": None, "best_patch_id": None,
            "n_candidates": int(searchable.sum()),
            "field_test": reg.get("field_test", {}).get("name"),
        }
        if sel_m.any():
            j = np.flatnonzero(sel_m)[np.argmax(s_all[sel_m])]
            rec.update(best_score=float(s_all[j]), rank=rank_of(s_all[j], s_masked),
                       best_patch_id=str(index.meta.at[int(e_all[j]), "patch_id"]))
        rows.append(rec)
    return sorted(rows, key=lambda r: (r["rank"] is None, r["rank"] or 0))


def outranking(index: Index, sites: pd.DataFrame, field_score: float, field_subs: dict[str, float]) -> list[dict[str, Any]]:
    """Top shortlisted sites scoring above the field-test patch, with the groups where each is closer."""
    out = []
    for r in sites.sort_values("rank").itertuples():
        if r.score <= field_score:
            break
        subs = {g: float(getattr(r, f"sub_{g}")) for g in (*GROUPS, "embedding")}
        closer = [g for g in subs if subs[g] > field_subs[g]]
        out.append({"rank": int(r.rank), "site_id": r.site_id, "region_id": r.region_id, "score": float(r.score),
                    "sub_scores": subs, "closer_groups": closer})
        if len(out) == N_OUTRANK:
            break
    return out


def main() -> int:
    """Compare the usual analog regions for every target."""
    cfg = load_config()
    index = load_index()
    m = index.meta
    summary = json.loads((results_dir() / "summary.json").read_text())["targets"]
    regions = [r for r in load_yaml("regions.yaml")["regions"] if r["set"] == "well_studied"]
    field = next((r for r in regions if r.get("field_test")), None)
    earth_grid = ((m["body"] == "earth") & (m["crater_centre_of"].fillna("") == "")).to_numpy()
    e_all = np.flatnonzero(earth_grid)
    searchable = m["search_ok"].to_numpy()[e_all].astype(bool)
    doc: dict[str, Any] = {"field_test": field.get("field_test") if field else None,
                           "field_test_region_id": field["id"] if field else None, "targets": {}}
    for t in selected_targets(load_yaml("targets.yaml")["targets"]):
        tid = t["id"]
        sigma = float(summary[tid]["sigma"])
        q_rows = np.flatnonzero((m["source_id"] == tid).to_numpy())
        s_all = patch_scores(index, q_rows, e_all, sigma)
        rows = region_rows(index, regions, e_all, s_all, searchable)
        entry: dict[str, Any] = {"sigma": sigma, "regions": rows, "field_test": None}
        frow = next((r for r in rows if field and r["region_id"] == field["id"]), None)
        if frow and frow["best_patch_id"]:
            e = int(m.index[m["patch_id"] == frow["best_patch_id"]][0])
            fsubs = sub_scores(index, q_rows, e, sigma)
            sites = pd.read_parquet(results_dir() / f"{tid}.parquet")
            entry["field_test"] = {"region_id": field["id"], "best_patch_id": frow["best_patch_id"],
                                   "score": frow["best_score"], "rank": frow["rank"], "sub_scores": fsubs,
                                   "outranked_by": outranking(index, sites, frow["best_score"], fsubs)}
        doc["targets"][tid] = entry
        log.info("%s: %s", tid, ", ".join(f"{r['region_id']} #{r['rank']}" for r in rows[:4]))
    (results_dir() / "usual_sites.json").write_text(json.dumps(doc, indent=1))
    log.info("wrote %s", results_dir() / "usual_sites.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
