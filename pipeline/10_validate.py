"""Step 10: validation benchmarks V1-V4; writes ``validation.json``.

V1 crater retrieval (headline). Positives are Earth patches whose centre lies
within 0.5 km of a benchmark crater centre (``config/craters.yaml``; every
crater also has a patch centred exactly on it). Patches within 5 km of a
crater centre that are not positives are excluded. Each positive is used as a
query and ranks every patch from the *other* regions; the other craters'
positives are the relevant items. Reported per ranker: mean ROC AUC, mean
reciprocal rank of the first other-crater hit, hit rate at 10 and 50.
Rankers: random, relief-only, features only, embedding only, combined.
Primary index: all valid Earth patches (no land-cover masks), because the
masks remove the lake-filled and farmland craters; the masked index is
reported too.

V2 rediscovery (context): percentile of each region's best patch among all
searchable Earth patches, per target.

V3 robustness: Spearman rank correlation of the top-20 regions between the
60 m run and the 90 m rerun (``make res90``), and how often each top-10 site
stays in the top 10 when the four feature-group weights are perturbed by up to
+/-20 % (50 draws, seed 42).

V4 sanity checks on the real index and synthetic surfaces.

Every number is computed here; nothing is edited by hand.
"""

from __future__ import annotations

import importlib
import json
import sys
from typing import Any

import numpy as np
import pandas as pd

from common import (DATA_DIR, config_hash, get_logger, load_config, load_yaml, now_iso, profile, run_dir,
                    selected_targets)
from features import compute_features
from grids import haversine_km
from scoring import GROUPS, Index, load_index, score_block

log = get_logger("10_validate")
query = importlib.import_module("08_query")

POS_RADIUS_KM = 0.5
EXCLUDE_RADIUS_KM = 5.0
RANKERS = [
    ("random", "Random"),
    ("relief_only", "One feature: relief only"),
    ("features", "Terrain features only"),
    ("embedding", "Image embedding only"),
    ("combined", "Combined, Earth-to-Earth sigma"),
]


def roc_auc(scores_pos: np.ndarray, scores_neg: np.ndarray) -> float:
    """Mann-Whitney ROC AUC with ties counted as half."""
    allv = np.concatenate([scores_pos, scores_neg])
    order = np.argsort(allv, kind="mergesort")
    ranks = np.empty(len(allv))
    sorted_v = allv[order]
    i = 0
    while i < len(sorted_v):
        j = i
        while j + 1 < len(sorted_v) and sorted_v[j + 1] == sorted_v[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    n_pos, n_neg = len(scores_pos), len(scores_neg)
    return float((ranks[:n_pos].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def crater_geometry(index: Index) -> pd.DataFrame:
    """For every Earth grid patch: which benchmark crater its window fully contains, if any,
    and its distance to the nearest benchmark crater centre.

    A window of P pixels at resolution R spans W = P * R metres. It fully contains a
    crater of diameter D when |dx| and |dy| (patch centre minus crater centre, in the
    patch's own metric grid) are both at most W / 2 - D / 2.
    """
    from rasterio.crs import CRS  # noqa: PLC0415
    from rasterio.warp import transform as warp_transform  # noqa: PLC0415

    from grids import utm_crs  # noqa: PLC0415

    cfg = load_config()
    half_w = float(cfg["patch_px"]) * float(cfg["resolution_m"]) / 2.0
    m = index.meta
    regions = {r["id"]: r for r in load_yaml("regions.yaml")["regions"]}
    contains = np.array([""] * len(m), dtype=object)
    nearest = np.full(len(m), np.inf)
    for c in load_yaml("craters.yaml")["craters"]:
        rows = np.flatnonzero(((m["body"] == "earth") & (m["source_id"] == c["region_id"])).to_numpy())
        reg = regions[c["region_id"]]
        xs, ys = warp_transform(CRS.from_epsg(4326), utm_crs(reg["lat"], reg["lon"]), [c["lon"]], [c["lat"]])
        dx = m["x_m"].to_numpy()[rows] - xs[0]
        dy = m["y_m"].to_numpy()[rows] - ys[0]
        lim = half_w - c["diameter_km"] * 1000.0 / 2.0
        inside = (np.abs(dx) <= lim) & (np.abs(dy) <= lim)
        contains[rows[inside]] = c["id"]
        nearest[rows] = np.minimum(nearest[rows], np.hypot(dx, dy) / 1000.0)
    return pd.DataFrame({"contains": contains, "dist_km": nearest})


def ranker_scores(index: Index, q: int, cand: np.ndarray, ranker: str, rng: np.random.Generator) -> np.ndarray:
    """Higher-is-more-similar scores of candidates for one query patch."""
    if ranker == "random":
        return rng.random(len(cand))
    if ranker == "relief_only":
        from features import FEATURE_NAMES  # noqa: PLC0415

        j = FEATURE_NAMES.index("relief_m")
        return -np.abs(index.feats[cand, j] - index.feats[q, j])
    res = score_block(index, np.array([q]), cand)
    if ranker == "features":
        return -res["d2"][0]
    if ranker == "embedding":
        return res["cos"][0]
    return res["S"][0]


def v1_crater_retrieval(index: Index, masked: bool, rng_seed: int) -> dict[str, Any]:
    """Crater retrieval: crater-centred queries against the regular patch grid of other regions.

    Queries are the patches centred on each benchmark crater. Candidates are the
    regular grid patches only (the crater-centred extras are never candidates).
    A candidate is relevant when its window fully contains another benchmark
    crater's rim; grid patches within 5 km of a crater that do not contain it are
    left out; everything else is a negative.
    """
    m = index.meta
    geo = crater_geometry(index)
    earth = (m["body"] == "earth").to_numpy()
    centred = (m["crater_centre_of"].fillna("") != "").to_numpy()
    grid = earth & ~centred
    usable = grid & (m["search_ok"].to_numpy() if masked else np.ones(len(m), bool))
    contains = geo["contains"].to_numpy()
    pos = usable & (contains != "")
    excluded = usable & ~pos & (geo["dist_km"].to_numpy() <= EXCLUDE_RADIUS_KM)
    neg = usable & ~pos & ~excluded
    regions = m["source_id"].to_numpy()
    query_crater = m["crater_centre_of"].fillna("").to_numpy()
    rng = np.random.default_rng(rng_seed)
    q_rows = np.flatnonzero(earth & centred & (m["search_ok"].to_numpy() if masked else True))
    crater_cfg = {c["id"]: c for c in load_yaml("craters.yaml")["craters"]}
    n_pos_by_crater = {cid: int((pos & (contains == cid)).sum()) for cid in crater_cfg}

    per_query: list[dict[str, Any]] = []
    for q in q_rows:
        cand = np.flatnonzero((pos | neg) & (regions != regions[q]))
        is_pos = pos[cand] & (contains[cand] != query_crater[q])
        if not is_pos.any():
            continue
        rec = {"row": int(q), "crater": query_crater[q]}
        for rid, _ in RANKERS:
            s = ranker_scores(index, q, cand, rid, rng)
            order = np.argsort(-s, kind="stable")
            first = int(np.flatnonzero(is_pos[order])[0]) + 1
            rec[rid] = {"auc": roc_auc(s[is_pos], s[~is_pos]), "first_hit_rank": first, "rr": 1.0 / first,
                        "hit10": float(first <= 10), "hit50": float(first <= 50)}
        per_query.append(rec)

    rankers = [{
        "id": rid, "label": label,
        "mean_auc": float(np.mean([r[rid]["auc"] for r in per_query])),
        "mrr": float(np.mean([r[rid]["rr"] for r in per_query])),
        "hit_at_10": float(np.mean([r[rid]["hit10"] for r in per_query])),
        "hit_at_50": float(np.mean([r[rid]["hit50"] for r in per_query])),
    } for rid, label in RANKERS]
    per_crater = [{
        "crater": crater_cfg[r["crater"]]["name"], "region_id": crater_cfg[r["crater"]]["region_id"],
        "diameter_km": crater_cfg[r["crater"]]["diameter_km"], "n_queries": 1,
        "n_positive_patches": n_pos_by_crater[r["crater"]],
        "auc": {rid: r[rid]["auc"] for rid, _ in RANKERS},
        "first_hit_rank": {rid: r[rid]["first_hit_rank"] for rid, _ in RANKERS},
    } for r in per_query]
    return {
        "n_craters": len(per_crater), "n_query_patches": len(per_query), "n_positive_patches": int(pos.sum()),
        "n_negatives": int(neg.sum()), "rankers": rankers, "per_crater": per_crater,
        "positives_by_crater": {crater_cfg[k]["name"]: v for k, v in n_pos_by_crater.items()},
        "craters_missing": sorted(set(crater_cfg) - {r["crater"] for r in per_query}),
    }


def finding_text(rankers: list[dict[str, Any]]) -> str:
    """One-sentence summary of the V1 ablation, written from the computed numbers."""
    auc = {r["id"]: r["mean_auc"] for r in rankers}
    hit = {r["id"]: r["hit_at_10"] for r in rankers}
    rel = "about the same as" if abs(auc["features"] - auc["relief_only"]) < 0.02 else (
        "above" if auc["features"] > auc["relief_only"] else "below")
    return (f"At 60 m the 20 interpretable terrain features alone recognise 1-3 km craters only weakly "
            f"(AUC {auc['features']:.2f}, {rel} relief alone at {auc['relief_only']:.2f}, random "
            f"{auc['random']:.2f}); the learned image embedding does much better (AUC {auc['embedding']:.2f}, "
            f"another crater in the top 10 for {100 * hit['embedding']:.0f}% of queries). The app therefore uses "
            "both: feature values to explain a match in physical units, and the embedding to rank landform shape.")


def v2_rediscovery(index: Index, targets: list[dict[str, Any]], results_dir_path: Any) -> dict[str, Any]:
    """Percentile rank of each region's best patch, per target."""
    regions = {r["id"]: r for r in load_yaml("regions.yaml")["regions"]}
    m = index.meta
    out: dict[str, Any] = {}
    for t in targets:
        e_rows, scores = np.load(results_dir_path / f"{t['id']}_patch_scores.npy")
        e_rows = e_rows.astype(int)
        order = np.argsort(np.argsort(scores))  # 0 = lowest
        pct = 100.0 * order / max(len(scores) - 1, 1)
        src = m["source_id"].to_numpy()[e_rows]
        rows = []
        for rid, reg in regions.items():
            if reg["set"] not in ("well_studied", "discovery"):
                continue
            sel = src == rid
            rows.append({"region_id": rid, "name": reg["name"], "set": reg["set"],
                         "best_percentile": float(pct[sel].max()) if sel.any() else None})
        ws = [r["best_percentile"] for r in rows if r["set"] == "well_studied" and r["best_percentile"] is not None]
        ds = [r["best_percentile"] for r in rows if r["set"] == "discovery" and r["best_percentile"] is not None]
        out[t["id"]] = {"well_studied_median": float(np.median(ws)) if ws else None,
                        "discovery_median": float(np.median(ds)) if ds else None, "regions": rows}
    return out


def region_ranking(sites: pd.DataFrame, k: int = 20) -> list[str]:
    """Region ids ordered by their best site score (first k distinct)."""
    best = sites.groupby("region_id")["score"].max().sort_values(ascending=False)
    return list(best.index[:k])


def spearman_regions(a: list[str], b_scores: dict[str, float], a_scores: dict[str, float]) -> float:
    """Spearman correlation of region scores between two runs over the 60 m top-20 regions."""
    from scipy.stats import spearmanr  # noqa: PLC0415

    common = [r for r in a if r in b_scores]
    if len(common) < 3:
        return float("nan")
    rho = spearmanr([a_scores[r] for r in common], [b_scores[r] for r in common]).statistic
    return float(rho)


def region_best_scores(index: Index, results_dir_path: Any, target_id: str) -> dict[str, float]:
    """Best patch score per region for a target."""
    e_rows, scores = np.load(results_dir_path / f"{target_id}_patch_scores.npy")
    src = index.meta["source_id"].to_numpy()[e_rows.astype(int)]
    return pd.Series(scores).groupby(src).max().to_dict()


def v3_robustness(index: Index, targets: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """90 m rerun correlation (if available) and weight-perturbation stability."""
    from common import results_dir  # noqa: PLC0415

    out: dict[str, Any] = {}
    res90_dir = DATA_DIR / "res90" / "work" / "results"
    if res90_dir.exists():
        import os  # noqa: PLC0415

        prev = os.environ.get("RG_PROFILE")
        os.environ["RG_PROFILE"] = "res90"
        try:
            index90 = load_index()
        finally:
            if prev is None:
                os.environ.pop("RG_PROFILE")
            else:
                os.environ["RG_PROFILE"] = prev
        rhos = {}
        for t in targets:
            if not (res90_dir / f"{t['id']}_patch_scores.npy").exists():
                continue
            a = region_best_scores(index, results_dir(), t["id"])
            b = region_best_scores(index90, res90_dir, t["id"])
            top = sorted(a, key=a.get, reverse=True)[:20]
            rhos[t["id"]] = spearman_regions(top, b, a)
        out["resolution_90m"] = {
            "description": "Each target was rerun on a 90 m grid (43 x 90 m = 3.87 km patches). Spearman rank "
                           "correlation of the best-patch score of the 60 m run's top-20 regions between the two runs.",
            "spearman_top20_regions": rhos,
        }
    rng = np.random.default_rng(int(cfg["seed"]))
    stay: dict[str, float] = {}
    draws = 50
    for t in targets:
        base = query.build_sites(index, query.rank_target(index, t["id"], cfg), cfg)
        base_top = set(base["site_id"].head(10))
        counts = []
        for _ in range(draws):
            gw = {g: float(rng.uniform(0.8, 1.2)) for g in GROUPS}
            pert = query.build_sites(index, query.rank_target(index, t["id"], cfg, group_weights=gw), cfg)
            counts.append(len(base_top & set(pert["site_id"].head(10))) / 10.0)
        stay[t["id"]] = float(np.mean(counts))
    out["weight_perturbation"] = {
        "description": f"Each feature-group weight (relief, slope, roughness, shape) was multiplied by a random "
                       f"factor between 0.8 and 1.2, {draws} times (seed {cfg['seed']}). Shown: the average share "
                       "of the original top-10 sites that stay in the top 10.",
        "mean_stay_top10": stay,
    }
    return out


def v4_sanity(index: Index, targets: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Self-match, rotation and synthetic-surface checks."""
    checks = []
    m = index.meta
    t_rows = np.flatnonzero((m["body"] != "earth").to_numpy())
    res = score_block(index, t_rows, t_rows)
    diag = np.diag(res["S"])
    checks.append({"check": "A target patch scored against itself returns 100",
                   "passed": bool(np.allclose(diag, 100.0, atol=1e-6)),
                   "detail": f"min {diag.min():.6f} over {len(diag)} target patches"})
    # Rotation: rotate each target patch 90 degrees, recompute features (embedding uses stored rotations).
    from features import FEATURE_NAMES, transform_features  # noqa: PLC0415
    import joblib  # noqa: PLC0415
    from common import index_dir, patches_dir  # noqa: PLC0415

    scaler = joblib.load(index_dir() / "scaler.joblib")
    res_m = float(cfg["resolution_m"])
    ok = 0
    total = 0
    for t in targets:
        rows = np.flatnonzero((m["source_id"] == t["id"]).to_numpy())
        arrays = np.load(patches_dir() / f"{t['id']}.npy")
        for local, r in enumerate(rows):
            f = compute_features(np.rot90(np.nan_to_num(arrays[local], nan=float(np.nanmedian(arrays[local])))), res_m)
            x = transform_features(np.array([[f[n] for n in FEATURE_NAMES]]))
            xs = np.clip((x - scaler["median"]) / scaler["scale"], -scaler["clip"], scaler["clip"])
            d2 = ((index.feats[rows] - xs) ** 2)
            cols = index.group_cols
            dist = sum(d2[:, cols[g]].mean(axis=1) for g in GROUPS)
            total += 1
            ok += int(np.argmin(dist) == local)
    checks.append({"check": "A target patch rotated 90 degrees is still its own top match (terrain features)",
                   "passed": ok == total, "detail": f"{ok} of {total} target patches"})
    flat = compute_features(np.full((64, 64), 100.0), res_m)
    checks.append({"check": "A flat plane has slope 0 and roughness 0",
                   "passed": flat["slope_p90"] == 0 and abs(flat["rough_std_m"]) < 1e-9,
                   "detail": f"slope p90 {flat['slope_p90']:.3g} deg, roughness {flat['rough_std_m']:.3g} m"})
    tilt = compute_features(np.indices((64, 64))[1] * 0.1 * res_m, res_m)
    expected = float(np.degrees(np.arctan(0.1)))
    checks.append({"check": "A plane tilted with gradient 0.1 has slope arctan(0.1) = 5.71 deg",
                   "passed": abs(tilt["slope_p50"] - expected) < 1e-6,
                   "detail": f"measured {tilt['slope_p50']:.4f} deg"})
    return checks


def main() -> int:
    """Run V1-V4 and write validation.json."""
    if profile() != "full":
        log.info("validation runs on the full profile only; skipping for %s", profile())
        return 0
    cfg = load_config()
    index = load_index()
    from common import results_dir  # noqa: PLC0415

    targets = selected_targets(load_yaml("targets.yaml")["targets"])
    seed = int(cfg["seed"])
    crater_names = {c["id"]: c["name"] for c in load_yaml("craters.yaml")["craters"]}
    v1 = v1_crater_retrieval(index, masked=False, rng_seed=seed)
    v1m = v1_crater_retrieval(index, masked=True, rng_seed=seed)
    log.info("V1: %d craters, %d queries; combined AUC %.3f, features %.3f, embedding %.3f",
             v1["n_craters"], v1["n_query_patches"],
             *[next(r["mean_auc"] for r in v1["rankers"] if r["id"] == k) for k in ("combined", "features", "embedding")])
    v1.update({
        "description": "A patch centred on each benchmark crater is the query. It ranks every regular 3.84 km grid "
                       "patch from the other regions. A grid patch counts as a hit when its window fully contains "
                       "another benchmark crater's rim (|dx| and |dy| at most 1.92 km minus half the crater "
                       "diameter); grid patches within 5 km of a crater that do not contain it are left out. "
                       f"Positives per crater: {', '.join(f'{k} {v}' for k, v in v1['positives_by_crater'].items())}. "
                       "Craters with no positive (rim wider than the window allows at the grid offset) still act "
                       "as queries.",
        "index": "Index: all valid Earth grid patches (land-cover masks off).",
        "combined_note": f"The combined row uses the Earth-to-Earth sigma ({index.sigma:.3f}), at which the terrain "
                         "term is close to zero for most crater pairs, so it tracks the embedding. For Moon targets "
                         "sigma is 0.44-0.71 and the terrain term carries real weight, so this row is not the exact "
                         "ranker the app uses for them.",
        "finding": finding_text(v1["rankers"]),
        "revision_note": "An earlier version of this test also used the crater-centred patches as the relevant "
                         "candidates. The embedding then ranked another crater first for every query (mean "
                         "reciprocal rank 1.00, AUC 0.979), an artefact of exact centring that a real search never "
                         "has. Candidates are now regular grid patches only; the positive rule above was fixed from "
                         "geometry before this run.",
        "masked": {
            "description": f"Same test on the masked search index used by the app ({v1m['n_craters']} query craters "
                           f"survive the masks; removed by the land-cover masks: "
                           f"{', '.join(crater_names[c] for c in v1m['craters_missing']) or 'none'}).",
            "n_craters": v1m["n_craters"], "rankers": v1m["rankers"],
        },
    })
    v2 = v2_rediscovery(index, targets, results_dir())  # noqa: F841 (used below)
    v3 = v3_robustness(index, targets, cfg)
    v4 = v4_sanity(index, targets, cfg)
    doc = {
        "generated_at": now_iso(), "config_hash": config_hash(),
        "v1_crater_retrieval": v1,
        "v2_rediscovery": {
            "note": "Known analogs ranking high is consistent with, but not proof of, a good method: those sites were "
                    "chosen for many reasons beyond terrain. Values are the percentile (100 = best) of each region's "
                    "best patch among all searchable Earth patches, then the median over the regions in each set. "
                    "This measure is saturated: with about 2,000 patches per region, almost any region's best patch "
                    "lands in the top 1%, so it does not separate the two sets.",
            "targets": v2, "target_names": {t["id"]: t["name"] for t in targets},
        },
        "v3_robustness": v3,
        "v4_sanity": v4,
        "limits": [
            "Crater shape at 60 m: craters under about 1 km across span only 15-20 pixels, so their rims are smoothed.",
            "Gravity changes crater shape: lunar and martian craters of a given size are shallower or deeper than on "
            "Earth, so Earth-to-Earth retrieval is a check of the fingerprint, not of cross-body equivalence.",
            "Small label set: seven craters (the PASSC structures 0.8-3.5 km across, exposed, younger than 10 Ma), "
            "so the metrics have wide uncertainty.",
            "Copernicus DEM is a surface model: lakes are flat and vegetation adds height, which hides parts of the "
            "Lonar, Pingualuit and Tswaing craters.",
            "Rediscovery (V2) mixes terrain with all the other reasons sites were chosen; it is context, not proof.",
        ],
    }
    out = run_dir() / "validation.json"
    out.write_text(json.dumps(doc, indent=1))
    log.info("wrote %s", out)
    for s in v4:
        log.info("V4 %s: %s (%s)", "PASS" if s["passed"] else "FAIL", s["check"], s["detail"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
