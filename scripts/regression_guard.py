"""Compare each target's top-20 sites with a saved baseline export.

    python scripts/regression_guard.py data/work/baselines/<name>           # vs web/public/data
    python scripts/regression_guard.py data/work/baselines/<name> --work    # vs step-08 results (before export)

For every target in the baseline it prints whether the top-20 site ids are
identical and in the same order, how many ids entered or left, and the largest
score change among sites present in both. Targets only in the new run are
listed as new. Nothing here is a pass/fail threshold: the point is to make every
difference visible so its cause can be stated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TOP = 20


def load_export(results_dir: Path) -> dict[str, list[tuple[str, float]]]:
    """Top-20 (site_id, score) per target from exported results JSON files."""
    out = {}
    for f in sorted(results_dir.glob("*.json")):
        doc = json.loads(f.read_text())
        out[doc["target_id"]] = [(m["site_id"], float(m["score"])) for m in doc["matches"][:TOP]]
    return out


def load_work(results_dir: Path) -> dict[str, list[tuple[str, float]]]:
    """Top-20 (site_id, score) per target from step-08 parquet results."""
    out = {}
    for f in sorted(results_dir.glob("*.parquet")):
        if f.stem in ("environment", "novelty"):
            continue
        df = pd.read_parquet(f).sort_values("rank").head(TOP)
        out[f.stem] = list(zip(df["site_id"], df["score"].astype(float)))
    return out


def compare(base: dict[str, list[tuple[str, float]]], new: dict[str, list[tuple[str, float]]]) -> list[dict]:
    """One row per target describing how its top 20 changed."""
    rows = []
    for tid in sorted(set(base) | set(new)):
        if tid not in base:
            rows.append({"target": tid, "status": "new target"})
            continue
        if tid not in new:
            rows.append({"target": tid, "status": "missing in new run"})
            continue
        b_ids, n_ids = [s for s, _ in base[tid]], [s for s, _ in new[tid]]
        b_sc, n_sc = dict(base[tid]), dict(new[tid])
        common = set(b_ids) & set(n_ids)
        max_diff = max((abs(b_sc[s] - n_sc[s]) for s in common), default=0.0)
        same = b_ids == n_ids and max_diff < 1e-9
        rows.append({
            "target": tid, "status": "identical" if same else "changed",
            "entered": len(set(n_ids) - set(b_ids)), "left": len(set(b_ids) - set(n_ids)),
            "same_order": b_ids == n_ids, "max_score_change": round(max_diff, 4),
            "top1_before": f"{b_ids[0]} {base[tid][0][1]:.1f}", "top1_after": f"{n_ids[0]} {new[tid][0][1]:.1f}",
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("baseline", type=Path, help="folder holding a saved results/ export")
    ap.add_argument("--work", action="store_true", help="compare with data/work/results (step 08) instead of the export")
    args = ap.parse_args()
    base = load_export(args.baseline / "results")
    new = load_work(ROOT / "data" / "work" / "results") if args.work else load_export(ROOT / "web" / "public" / "data" / "results")
    rows = compare(base, new)
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
