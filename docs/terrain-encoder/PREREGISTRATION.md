# Pre-registration: terrain-trained encoder ("landform under the craters") and a Moon-likeness model

Registered 2026-11-15, before any download, model fit or training for this programme. Stage 1 lives on branch
`feat/moon-likeness`; Stages 2-8 on `exp/terrain-encoder` (this folder). Main and the live app stay working at every
stage. Later changes go only in **Deviations**, dated, with a reason. Thresholds that no source sets are marked
"our choice" here and in `DECISIONS.md`. Physical constants are read from their sources at Stage 4. None are typed in
from memory here.

## Hold-outs and splits (`splits.json`, `make_splits.py`, seed 42)

Never used for training:
- the Moon targets plus a 30 km buffer, and Jezero plus 30 km;
- the crater-benchmark regions plus 10 km: `crater_lonar`, `crater_pingualuit`, `crater_roter_kamm`,
  `crater_tenoumer`, `crater_tswaing`, `crater_wolfe_creek`, `meteor_crater`;
- 20% of the Earth analog regions: `askja`, `haughton`, `mcmurdo_dry_valleys`, `pilbara`, `upper_mustang`. This is the
  same rule and draw as the earlier experiment;
- 20% of the extra Stage 3 Copernicus tiles, by the hash rule in `splits.json`.

Moon targets, split 3 VAL / 5 TEST (seed 42), as a deviation from "9", see below:
- VAL: `moon_dm2_nobile_rim_2`, `moon_site11_de_gerlache_rim`, `moon_site23_malapert`.
- TEST: `moon_haworth`, `moon_site01_connecting_ridge`, `moon_site04_shackleton_rim`, `moon_site06_nobile_rim_1`,
  `moon_site20_leibnitz_beta`.

Jezero (`mars_jezero`) is TEST only and zero-shot.

Models and settings are chosen on VAL only. TEST is used once per model, for reporting.

## Stage 1: Moon-likeness model (existing data only, no downloads)

- **Idea.** Label each patch by its body only (Moon target = 1, Earth = 0). The log-odds of a probabilistic
  classifier estimates log[p_Moon(x) / p_Earth(x)] plus a constant: the density-ratio trick (Sugiyama, Suzuki and
  Kanamori 2012, *Density Ratio Estimation in Machine Learning*, Cambridge University Press).
- **Rows.** Moon = the 635 Moon-target patches, plus their 3 extra quarter-turn embeddings (`embeddings_rot.npy`
  slots 1-3; slot 0 equals the base embedding) as extra rows in the same target group. Mars is not used. Earth = the
  app's searchable (`search_ok`) grid patches of non-crater regions (our choice: the app's own search space). Crater
  regions and crater-centred extras are never trained on. The 20 features are rotation-invariant, so in arm A the
  rotation rows are exact duplicates that only reweight the Moon class.
- **Inputs.** Arm A: the 20 terrain features (`features.parquet`), standardised inside the pipeline. Arm B: features +
  the 64-d embedding (`embeddings.npy` / `embeddings_rot.npy`). Arm C: HistGradientBoostingClassifier on B's inputs.
  All use `class_weight="balanced"`.
- **Out-of-fold scores** for everything reported:
  - Earth: GroupKFold by Earth region (5 folds). Each fold's model is trained on all Moon rows plus the other folds'
    Earth regions.
  - Moon: leave one target out. The model is trained on the other 7 targets plus all non-crater Earth.
  - Crater-region patches: scored by the model trained on everything else (they are never in training).
- **Regularisation by inner grouped CV on log loss** (groups = Earth regions and Moon targets, 3 folds, our choice),
  with balanced sample weights in the scoring:
  - A and B: C in {0.001, 0.01, 0.1, 1, 10};
  - C: (learning_rate, max_leaf_nodes) in {0.05, 0.1} x {15, 31}, max_iter 200, l2_regularization 1.0 (our choice).
- **Baselines** (same out-of-fold scheme where they are fitted):
  - the existing similarity score (maximum app score S over all 635 Moon-target patches, each target's own sigma, as
    the app computes it);
  - `relief_m` alone (a one-feature logistic regression, out of fold);
  - random.
- **Tests:**
  - T1: crater-benchmark AUC. Positives are V1's positive rule (grid patches whose window fully contains a benchmark
    crater). Negatives are V1's negatives (other Earth grid patches; patches within 5 km of a crater centre that do
    not contain it are left out), restricted to searchable patches. 95% interval by bootstrap over craters (2,000
    resamples).
  - T2: leave-one-target-out AUC of each Moon target's out-of-fold scores against the Earth out-of-fold scores, per
    target and mean.
  - T3: each region's share of its patches in the Earth top 1% (our choice) by out-of-fold log-odds, for well_studied
    against discovery regions (crater regions excluded), Mann-Whitney U, two-sided. Reported as "consistent with, not
    proof of".
  - T4: refit without `rough_std_m`, `tri_m`, `curv_abs`. Report the Spearman correlation of the Earth rankings and
    the change in T1.
  - T5: overall Moon-vs-Earth out-of-fold AUC. If it is near 1, show percentiles and log-odds. Never "probability of
    being the Moon".
- **Adoption.** T1 lower 95% bound above 0.5 and T4 Spearman >= 0.7. Prefer A when its T1 point AUC is within 0.02
  of the best arm's.
- **If adopted** (on `feat/moon-likeness`):
  - `web/public/data/moonlike.json`, generated by a pipeline step, never hand-edited: percentile and out-of-fold
    log-odds per searchable patch; the top 50 sites after 10 km NMS (our choice), each site = mean of its top 3
    patches; for each site the 3 features pushing most towards "Moon" (arm A coefficient x standardised value) and the
    nearest Moon target by the existing score;
  - an Explore mode "Most Moon-like on Earth", a site-page badge, a Validation entry with limits ("Moon-like" means
    like the lunar south-pole targets; only our regions were searched), and a Methods paragraph;
  - existing scores must not change: the regression report must be identical.

## Stage 2: tests (baseline = the current ImageNet ResNet-18)

- **E1, Moon-to-Moon crater retrieval.** USGS Moon Crater Database v1 (Robbins 2019) craters with D 1-3.5 km inside
  the Moon target DEMs.
  - Query: a patch centred on a catalogued crater.
  - Positive: a grid patch whose central 1 km contains a catalogued crater centre with D 1-3.5 km.
  - Negative: a grid patch with no catalogued crater >= 0.8 km within its central 2 km. The 0.8 km and 2 km values
    are our choice; the catalogue is complete only to about 1-2 km.
  - Metrics: AUC, MRR, hit@10/50, with bootstrap 95% intervals over query craters. VAL targets for selection, TEST
    targets for reporting.
- **E2, Earth crater retrieval.** Main's V1 unchanged, plus the extended set: every Earth Impact Database crater
  0.8-3.5 km with a depression in Copernicus GLO-30, exclusions listed with reasons. TEST only.
- **E3, Moon-to-Earth crater retrieval.** Queries from the E1 TEST targets; candidates are all Earth patches;
  positives by V1's rule. AUC, MRR, hit@10/50, bootstrap intervals.
- **E4, invariance.** Self-retrieval rank among VAL patches under a 90-degree rotation, a flip, a hillshade sun change,
  2x down-up resampling, small noise and a 4 px shift.
- **E5, source robustness (Moon).** In the target areas, the same place from the 5 m site DEM and from the LOLA
  80-90 S 20 m polar DEM (official page found first), both at 60 m. Rank of the true location among all patches.
- **E6, crater invariance** (after Stage 4). Held-out Earth patches with injected craters: rank of the clean original
  among 1,000 clean distractors; top-1 and top-10 rates with Wilson 95% intervals.
- **E7, functional agreement.** For each target's top 10 matches, the mean absolute Moon-Earth difference in slope
  p90, share of slope <= 15 deg, and relief (lower is better).
- **E8, domain probe.** Logistic regression Moon vs Earth on the embedding; diagnostic only, never optimised.

## Stage 3: training data

- **Moon:**
  - the PGDA product 78 5 m site DEMs that are not targets (the list is taken from the product page at Stage 3;
    Site20v2 excluded; nothing within 30 km of a target);
  - the LOLA 80-90 S 20 m DEM outside the target buffers;
  - SLDEM2015 (512 px/deg) sampled across latitudes and highland/mare.
  - Every tile is warped to a local metric grid at 60 m (R = 1,737.4 km).
- **Earth:** main's regions minus hold-outs, plus about 150 extra Copernicus GLO-30 tiles from dry land (NASA POWER
  annual rainfall < 500 mm) and ice-free polar land, keeping patches that pass main's vegetation rule with ESA
  WorldCover. UTM grid, 60 m.
- **Mars:** zero-shot unless more CTX DTMs can be downloaded without a login (stated at Stage 3).
- **Format:** 64 x 64 px at 60 m, stride 32, float32 elevation shards with metadata (body, source, lat, lon, region,
  split). Aim: >= 150,000 Moon and >= 150,000 Earth training patches.
- **Inputs:** plane-detrended elevation / 100 m clipped to +-5, slope / 45 deg, and hillshade (random sun in
  training; azimuth 315, elevation 45 at inference, as main).

## Stage 4: crater injection

- **Profile:** parabolic bowl, with depth/diameter and rim height from Pike (1977) for fresh lunar simple craters;
  ejecta thickness falling as (r/R)^-3 (McGetchin, Settle and Head 1973); random degradation by linear diffusion with
  the lunar diffusivity scale from Fassett and Thomson (2014). All coefficients are read from the papers at Stage 4.
- **Sizes and placement:** 240 m-2 km from N(>D) proportional to D^-b, with b from a checked lunar size-frequency
  source (or a range marked our choice); uniform positions; overlapping craters superpose; 2x supersampled, then
  area-averaged to 60 m.
- **Tests:**
  - an isolated crater has the specified depth, rim height and diameter within one pixel;
  - diffusion matches the analytic Gaussian solution;
  - counts match the density within Poisson error;
  - zero density returns the input exactly.
- **Calibration per Moon target:** the Robbins count of D >= 1 km, extrapolated below 1 km with the power law, with
  its uncertainty.
- **Display:** "Earth with lunar craters (simulated)" for every top match (fixed seed).

## Stage 5: Encoder-F

- **Model:** ResNet-18 from ImageNet weights, stem adapted to 64 px (conv1 kept, max-pool removed), 512-d output.
- **Training:**
  - VICReg (Bardes, Ponce and LeCun, ICLR 2022) via Lightly, loss weights (25, 25, 1), projector 2048-2048-2048;
  - batch 256, half Moon / half Earth;
  - AdamW 1e-3, 10-epoch warm-up, cosine decay;
  - early stopping on VAL E1 and E4;
  - per-dimension embedding std logged.
- **Augmentations (nuisance factors only):**
  - 90-degree rotations and flips; small-angle rotation with reflect padding;
  - sun azimuth 0-360 and elevation 20-60;
  - blur sigma 0-1.5 px, 2x down-up p = 0.3, small noise;
  - vertical scale 0.85-1.15; crop scale 0.85-1.0 resized to 64.
- No domain-adversarial or alignment losses.
- **Ablations** (one smaller run each):
  - scratch vs ImageNet start;
  - Earth-only vs Moon + Earth;
  - an extra positive pair from the same place at 30 m and 60 m (kept only if VAL improves).
- **Search embedding:** 512-d, L2, PCA 64 fitted on Earth training patches. Run E1-E5, E7, E8.
- **Budget:** a Mac config that finishes a full run in under 3 hours.

## Stage 6: Encoder-L

Encoder-F plus per-view crater injection: p = 0.8, density uniform from 0 to the highest target density, independent
seeds per view.
- A linear probe on frozen Encoder-F predicts injected density (R^2 on held-out patches).
- Run E1-E7; E6 is the key test.
- Explanation line per match: "Landform match X. The Moon site has about N more craters >= 240 m per km^2 (see
  simulated panel); slope p90 differs by Y deg."

## Stage 7: Moon-likeness on the new embeddings

- Stage 1's model rerun with the Encoder-F and Encoder-L embeddings: T1-T5, plus a check that held-out Moon TEST
  targets score high.
- Optional human check (only with at least 3 people): judge.html with 40 TEST queries, ImageNet vs the best new
  encoder, 5% attention checks, Wilson intervals.

## Stage 8: adoption rules (verbatim)

- Encoder-F replaces ImageNet in the main ranking only if, on TEST:
  - E3 AUC improves, with the bootstrap 95% interval of the difference above 0;
  - E1 and E2 AUC drop by no more than 0.02;
  - E4 and E7 are not worse.
  Otherwise keep ImageNet and report honestly.
- Encoder-L appears as a "Landform match (ignores small craters)" option only if:
  - its E6 top-10 rate beats both F and ImageNet with non-overlapping 95% Wilson intervals;
  - E3 and E7 are not worse than ImageNet.
- The Moon-likeness model follows Stage 1's rule.
- Integrate whatever passes:
  - embedding version 2 behind a config flag;
  - a full pipeline run and the regression report;
  - the simulated-craters swipe panel and the Landform match option;
  - "Most Moon-like on Earth";
  - the Validation "Model comparison" table;
  - a Methods page;
  - MODEL_CARD.md per model and a README section.
- Show the diff before merging into main.

## Deviations

**2026-11-15, registered at Stage 0.**
- The programme says "9 Moon targets"; main has 8 Moon targets plus Jezero. The split is therefore 3 VAL / 5 TEST
  (seed 42), with Jezero TEST-only and zero-shot.
- The programme names about 27 PGDA product 78 sites. The list actually used is whatever the product page lists at
  Stage 3, recorded then.
- Re-used from the earlier experiment, byte-identical: the Robbins 2019 catalogue zip (sha256
  694137e141138892555d0f976446875331d3317ea506ddf055d91b917ca307ab). Nothing else is re-used without being rebuilt
  under these rules.

**2026-11-15, Stage 1 outcome and the user's go-ahead.** Stage 1: no arm adopted (results in `docs/moonlike_results.md`
on `feat/moon-likeness`). The user asked for all remaining stages to run without stopping. T1 is kept as registered.
The all-crater-patch version of T1 is added as a new test at Stage 7, not used to change the Stage 1 verdict.

**2026-11-15, Stage 2 clarifications (written before any Stage 2 number was computed).**
- **Earth VAL.** Earth VAL regions (needed by E4 and early stopping) are 3 of the 18 non-test, non-crater analog
  regions (seed 42): `atacama_yungay`, `namib`, `qaidam` (our choice). Earth TEST = the 5 test regions.
- **E1.**
  - Candidates are the Moon grid patches of the same split's targets. Patches overlapping the query window are left
    out (centre offset under 3.84 km in x and y, in the shared polar stereographic metres; our choice), as are
    patches that are neither positive nor negative.
  - Query: the best cosine over the query's 4 quarter-turns, as the app does.
  - Counts: 29 VAL and 65 TEST crater windows; 30 positive and 504 negative grid patches.
- **E2 extended set: skipped.** The Earth Impact Database site (passc.net) now returns only a parked-domain page, so
  its terms cannot be read on an official page.
- **E3.** Queries are the 65 TEST crater windows. Candidates and positives are V1's unmasked gallery (11 positive
  patches).
- **E4.**
  - Gallery: VAL (or TEST) Earth searchable patches plus the Moon patches of the VAL (or TEST) targets.
  - Queries: 300 Earth patches (seed 42) and every Moon patch of the split.
  - Noise: sigma 0.5 m (our choice). Sun change: 315 -> 135 deg azimuth at 45 deg.
  - Reported as top-1/top-10 rates with Wilson intervals, plus the per-query share of transforms with rank <= 10.
- **E5.**
  - Second source: PGDA product 90 `LDEM_80S_20MPP_ADJ.TIF` (LOLA 80-90 S, 20 m, cloud-optimised GeoTIFF; page
    https://pgda.gsfc.nasa.gov/products/90). It is averaged onto each target's own 60 m grid.
  - Query: the 20 m-derived patch. Gallery: all of main's patches (66,386). The true location is the 5 m-derived
    patch at the same row and column.
- **E7.** Uses each target's top-10 sites from main's own ranking code with the arm's embedding swapped in. Share of
  slope <= 15 deg = `slope_hist_0` + ... + `slope_hist_3` (the 0-2, 2-5, 5-10 and 10-15 deg bins).

**2026-11-15, Stage 3-4 notes (after building the data; before any encoder result).**
- **PGDA product 78 lists 27 sites.**
  - Kept: the 8 sites at least 30 km from every target (Site42, Shoemaker, NPA, NPB, NPC, LM3, LM6, LM7).
  - Excluded: the 8 targets, Site20v2, and the 9 sites within 30 km of a target (Site07, DM1, SL2, SL3, NPD, LM1,
    LM2, LM4, LM5).
  - Skipped: LM8, which returns HTTP 403.
- **Training counts.** Moon TRAIN 162,112 (aim >= 150,000 met). Earth TRAIN 135,401: the aim of 150,000 is missed
  by about 10%. Main's land-cover rule rejects about half of the candidate windows, and the tile count was kept at
  the programme's "about 150". A first Earth build capped at 1,500 patches per tile was replaced by one that keeps
  every valid window.
- **Mars:** zero-shot, see `DECISIONS.md`.
- **E5 saturates:** both Moon sources are LOLA-derived, so the 20 m and 5 m versions agree at 60 m. B1 scores 100%
  top-1, and E5 cannot separate models.
- **E2 extended set:** skipped (see above).
- **Stage 4 constants** were read from open secondary sources that quote the primaries (`SOURCES.md`). The rim
  height is used as h = 0.036 D, the linear form quoted.

**2026-11-15, Stage 8 operational definitions (clarification, written before any encoder was evaluated).** All
comparisons are paired against B1 on TEST, with the same queries, 10,000 bootstrap resamples and seed 42.
- **"E3 AUC improves":** the 95% interval of the mean per-query AUC difference (arm - B1) over the 65 TEST crater
  queries lies above 0.
- **"E1 and E2 AUC drop by no more than 0.02":** the TEST point estimates.
- **"E4 not worse":** the per-query aggregate top-10 share over the TEST queries. Worse if the 95% interval of the
  difference lies wholly below 0, or the mean drop exceeds 0.03 (our choice).
- **"E7 not worse":** the mean over the 5 TEST targets of each E7 measure (lower is better). Worse if slope p90 or
  relief is more than 10% above B1's, or the share of slope <= 15 deg differs from the target by more than 0.02
  beyond B1's (our choice).
- **"E3 not worse"** (for Encoder-L): worse if the interval lies wholly below 0, or the mean drop exceeds 0.02
  (our choice).
- **"E6 non-overlapping Wilson intervals":** the arm's top-10 lower bound is above the other model's upper bound.

**2026-11-15, how the encoders were trained (deviation, recorded before any of them was evaluated).**
- Encoder-F was trained on the Mac with the Mac config. Early stopping (patience 6) ended it at epoch 17; the best
  VAL epoch was 11.
- At the user's request, Encoder-L and the three ablations were trained on the user's GPU server instead (SDSU
  JupyterHub, NRP Nautilus; NVIDIA A100 MIG 1g.10gb slices, 8 CPUs). The script was `colab/rg_train_colab.py`, with
  the same model, loss, inputs, augmentations and step settings as the Mac config.
  - Encoder-L: 40 epochs x 80 steps.
  - Ablations: 20 epochs x 60 steps.
- **Differences:**
  - That script has no in-loop early stopping. It saves every epoch, and the best epoch after the warm-up is chosen
    on VAL afterwards (`colab_select.py`, same VAL score as the Mac). Encoder-L therefore had epochs 11-40 to choose
    from, while Encoder-F stopped at 17.
  - Encoder-L was stopped once at epoch 7 and resumed from its saved state with 7 instead of 2 data workers, which
    changes the random draws of patches and augmentations.
  - Batches were passed as numpy arrays through pipes, because the server's shared memory was small. This does not
    change the data.

