# Terrain-encoder experiment (archived record)

An experiment run on 15-16 November 2026 asked whether models trained on Moon and Earth terrain match landforms
better than the ImageNet ResNet-18 this app uses. The answer, under rules fixed in advance, was no: the trained
models became steadier under rotation, Sun direction and resampling, but recognised impact craters less well. The
app therefore keeps the ImageNet model.

This folder keeps the written record:
- `RESULTS.md`: every test and ablation, with intervals;
- `PREREGISTRATION.md`: the tests, splits and rules fixed before training, plus every dated deviation;
- `DECISIONS.md`: the choices no source sets;
- `MODEL_CARD.md`;
- `SOURCES.md`;
- `results/`: the metric records the Validation page table is exported from (`scripts/export_model_comparison.py`).

The training code, the training data and the model weights were removed after the evaluation. Paths such as
`runs/` and `cache/` in these files refer to that removed experiment folder.
