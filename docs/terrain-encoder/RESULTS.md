# Results: terrain-trained encoders and the Moon-likeness model (2026-11-16)

Pre-registration and every deviation are in `PREREGISTRATION.md`, and choices no source sets are in `DECISIONS.md`.
Run records: `runs/eval_*`, `runs/stage6_probe`, `runs/stage7_moonlike`, `runs/stage8_decision`. Every model was chosen
on VAL and tested once on TEST.

## Stage 8 verdict: keep the ImageNet ResNet-18 in the app
- **Encoder-F is not adopted.**
  - E3 does not improve: -0.060 [-0.125, +0.004].
  - E1 drops by 0.035 and E2 by 0.144, both more than the allowed 0.02.
- **Encoder-L is not offered.**
  - Its E6 rate beats both F and ImageNet, with no overlap between the intervals.
  - But E3 is much worse: -0.348 [-0.396, -0.297].

## TEST results (point estimate [95% interval])

| Arm | E1 Moon->Moon AUC | E2 Earth craters AUC | E3 Moon->Earth AUC | E4 invariance top-10 | E6 crater invariance top-10 | E7 slope p90 / share<=15 / relief | E8 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B1 ImageNet (app) | 0.567 [0.548, 0.585] | 0.976 | 0.625 [0.579, 0.668] | 0.769 | 0.498 [0.454, 0.542] | 1.12 / 0.031 / 58.6 | 0.9998 |
| Encoder-F | 0.531 [0.502, 0.562] | 0.833 | 0.564 [0.512, 0.610] | 0.995 | 0.418 [0.376, 0.462] | 1.13 / 0.034 / 48.3 | 0.996 |
| Encoder-L | 0.506 [0.477, 0.535] | 0.745 | 0.277 [0.259, 0.294] | 0.992 | 0.952 [0.930, 0.968] | 1.08 / 0.032 / 47.9 | 0.9996 |
| F scratch (ablation) | 0.637 [0.605, 0.671] | 0.688 | 0.405 [0.371, 0.440] | 0.992 | 0.486 [0.443, 0.530] | 1.16 / 0.031 / 45.5 | 0.997 |
| F Earth-only (ablation) | 0.541 [0.522, 0.560] | 0.779 | 0.513 [0.486, 0.539] | 0.990 | 0.470 [0.427, 0.514] | 1.11 / 0.032 / 55.8 | 0.998 |
| F multi-scale (ablation) | 0.730 [0.678, 0.780] | 0.843 | 0.593 [0.550, 0.637] | 0.989 | 0.414 [0.372, 0.458] | 1.17 / 0.032 / 48.6 | (see run) |

Notes on the tests:
- **E5** (Moon source robustness) is 100% top-1 for every arm. Both LOLA-derived sources agree at 60 m, so the test
  cannot separate the arms.
- **Sample sizes:**
  - E1: 65 TEST crater queries.
  - E2: 7 craters (the extended set was skipped).
  - E3: 65 queries, 11 positives.
  - E4: 724 queries.
  - E6: 500 queries.
  - E7: 5 TEST targets.

## Ablations
- **ImageNet start vs scratch.** Scratch is better on Moon-to-Moon craters (E1), but much worse on Earth craters (E2)
  and Moon-to-Earth craters (E3). The ImageNet start is better overall.
- **Moon + Earth vs Earth only.** Moon data improves E3 (Earth-only minus Moon+Earth: -0.051 [-0.096, -0.006]) and
  E2. The Earth-only run used the smaller ablation budget, so part of the gap may come from that.
- **Multi-scale 30/60 m positives.**
  - VAL E1 rose from 0.547 (Encoder-F) to 0.725, so by the pre-registered rule the idea is kept.
  - On TEST it is the best trained arm on E1 (0.730), E2 (0.843) and E3 (0.593).
  - It still fails adoption on the E2 drop.

## Stage 6 probe (R^2 for predicting injected crater density from frozen embeddings, Earth VAL)
| B1 | Encoder-F | Encoder-L |
| --- | --- | --- |
| 0.58 | 0.63 | 0.33 |

F still "sees" craters; L largely ignores them, as intended.

## Stage 7: Moon-likeness on the new embeddings (Stage 1 rule: T1 lower bound > 0.5 and T4 >= 0.7)

| Embedding + arm | T1 as registered (2 searchable crater patches) | T1, all 11 crater patches (new test) | T4 | T5 |
| --- | --- | --- | --- | --- |
| Encoder-F, logistic (B) | 0.538 [0.095, 0.981] | 0.785 [0.539, 0.920] | 0.960 | 0.998 |
| Encoder-F, boosting (C) | 0.625 [0.274, 0.975] | 0.878 [0.665, 0.957] | 0.466 | 0.997 |
| **Encoder-L, logistic (B)** | **0.748 [0.669, 0.827] (passes)** | 0.695 [0.609, 0.780] | **0.988** | 0.998 |
| Encoder-L, boosting (C) | 0.266 [0.197, 0.335] | 0.162 [0.107, 0.251] | 0.640 | 0.999 |

- **Held-out Moon TEST targets** score at the 99.7-100th percentile among Earth patches for every embedding and arm.
- **Encoder-L + logistic passes the Stage 1 rule.** It is not integrated without the user's decision:
  - the registered T1 rests on 2 crater patches;
  - the boosting arm on the same embedding scores 0.27;
  - Encoder-L itself is not adopted for ranking.
- **Most Moon-like Earth regions** are again Hawaii (Kilauea / Mauna Kea) and the McMurdo Dry Valleys. The
  well-studied vs discovery difference is not significant here (p 0.16-0.85).

## Next (not done)
- Gentler fine-tuning (lower learning rate, frozen early layers) to keep ImageNet's crater features.
- Concatenating the ImageNet and Encoder-F embeddings.
- The multi-scale variant as the base for both.
- A larger crater benchmark (more positives for T1/E2/E3).
- Human E1 ratings.
