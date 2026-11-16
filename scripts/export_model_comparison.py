"""Export the terrain-encoder experiment's results for the Validation page (web/public/data/model_comparison.json).

    python scripts/export_model_comparison.py

Reads the archived run records of the terrain-encoder experiment (docs/terrain-encoder/results/: eval_*,
stage6_probe, stage8_decision) and copies the numbers, unchanged, into one file the web app reads. The write-up,
pre-registration and deviations are in docs/terrain-encoder/. No score of the app depends on this file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = [("B1_imagenet_resnet18", "ImageNet ResNet-18 (in the app)"), ("Encoder_F", "Encoder-F (terrain-trained)"),
        ("Encoder_L", "Encoder-L (trained to ignore small craters)"), ("Encoder_F_multiscale", "Encoder-F + 30/60 m pairs"),
        ("Encoder_F_scratch", "Encoder-F from scratch"), ("Encoder_F_earthonly", "Encoder-F, Earth data only")]


def main() -> None:
    runs = ROOT / "docs" / "terrain-encoder" / "results"
    rows = []
    for key, label in ARMS:
        m = json.loads((runs / f"eval_{key}" / "run.json").read_text())["metrics"]
        rows.append({"arm": key, "label": label,
                     "e1_moon_craters_auc": m["E1"]["test"]["auc"], "e1_n": m["E1"]["test"]["n_queries"],
                     "e2_earth_craters_auc": round(m["E2"]["mean_auc"], 3), "e2_n_craters": m["E2"]["n_craters"],
                     "e3_moon_to_earth_auc": m["E3"]["auc"], "e3_n": m["E3"]["n_queries"],
                     "e4_invariance_top10": round(m["E4"]["test"]["aggregate_top10"], 3),
                     "e6_crater_invariance_top10": m["E6"]["top10"], "e6_n": m["E6"]["n"],
                     "e7_slope_p90_diff_deg": round(m["E7"]["test"]["slope_p90"], 2),
                     "e7_relief_diff_m": round(m["E7"]["test"]["relief_m"], 1)})
    d8 = json.loads((runs / "stage8_decision" / "run.json").read_text())["metrics"]
    probe = json.loads((runs / "stage6_probe" / "run.json").read_text())["metrics"]
    doc = {"source": "docs/terrain-encoder/RESULTS.md in the code repository",
           "verdict": d8["verdict"], "arms": rows,
           "crater_probe_r2": {k: v["r2_val"] for k, v in probe.items()},
           "rules": {"encoder_F": "replaces the ImageNet model only if, on held-out data, Moon-to-Earth crater matching "
                                  "clearly improves (95% interval of the gain above 0), the Moon and Earth crater tests "
                                  "drop by no more than 0.02, and steadiness and slope and relief agreement are not worse",
                     "encoder_L": "is offered only if it finds the same place after adding small craters clearly more "
                                  "often than both other models (non-overlapping 95% intervals), and Moon-to-Earth crater "
                                  "matching and slope and relief agreement are not worse"}}
    (ROOT / "web" / "public" / "data" / "model_comparison.json").write_text(json.dumps(doc, indent=1))
    print("wrote model_comparison.json:", doc["verdict"])


if __name__ == "__main__":
    main()
