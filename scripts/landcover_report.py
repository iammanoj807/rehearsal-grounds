"""Phase 0 report: searchable patches per region and vegetated shares of top sites.

    python scripts/landcover_report.py data/work/baselines/<name>

Reads the current step-05 features (search_ok per region), the baseline's
regions.json, and step 08/09 results (vegetation within 2 km of each kept site).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from common import load_yaml, results_dir, run_dir, selected_targets  # noqa: E402

VEG_LIMIT = 0.20


def main() -> int:
    baseline = Path(sys.argv[1])
    before = {r["id"]: r["n_searchable"] for r in json.loads((baseline / "regions.json").read_text())}
    feats = pd.read_parquet(run_dir() / "features.parquet")
    earth = feats[feats["body"] == "earth"]
    after = earth.groupby("source_id")["search_ok"].sum().astype(int).to_dict()
    total = earth.groupby("source_id").size().to_dict()
    precip = earth.groupby("source_id")["precip_mm_yr"].median().round(0).to_dict()
    regions = {r["id"]: r for r in load_yaml("regions.yaml")["regions"]}
    rows = [{"region": rid, "set": regions[rid]["set"], "patches": total[rid], "median_precip_mm_yr": precip.get(rid),
             "searchable_before": before.get(rid), "searchable_after": after.get(rid, 0),
             "change": after.get(rid, 0) - (before.get(rid) or 0)} for rid in sorted(total)]
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    print(f"\nTOTAL searchable before {sum(v for v in before.values())}, after {sum(after.values())}")

    env = pd.read_parquet(results_dir() / "environment.parquet").set_index("site_id")
    print(f"\nShare of kept sites with more than {VEG_LIMIT:.0%} vegetation within 2 km (WorldCover, all vegetated classes):")
    out = []
    for t in selected_targets(load_yaml("targets.yaml")["targets"]):
        sites = pd.read_parquet(results_dir() / f"{t['id']}.parquet").sort_values("rank")
        veg = sites["site_id"].map(env["vegetation_fraction"])
        for k in (10, 50):
            v = veg.head(k)
            out.append({"target": t["id"], "top": k, "vegetated": int((v > VEG_LIMIT).sum()),
                        "share": round(float((v > VEG_LIMIT).mean()), 3), "no_landcover": int(v.isna().sum())})
    rep = pd.DataFrame(out)
    print(rep.to_string(index=False))
    t10 = rep[rep["top"] == 10]
    print(f"\nAll targets, top 10: {int(t10['vegetated'].sum())} of {10 * len(t10)} sites "
          f"({t10['vegetated'].sum() / (10 * len(t10)):.1%}) are more than {VEG_LIMIT:.0%} vegetated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
