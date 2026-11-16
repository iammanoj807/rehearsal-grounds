# Decisions ("our choice")

Values below are not set by any source. Each one is our choice, made before the results it affects were seen.

| Where | Choice | Why |
| --- | --- | --- |
| Stage 1 rows | Earth = the app's searchable (`search_ok`) grid patches of non-crater regions | the app's own search space |
| Stage 1 inner CV | 3 grouped folds; C in {0.001, 0.01, 0.1, 1, 10}; HGB lr {0.05, 0.1} x leaves {15, 31}, 200 iterations, l2 1.0 | small grid, enough to regularise |
| Stage 1 T1 bootstrap | 2,000 resamples over craters | stable 95% bounds |
| Stage 1 T3 | Earth top 1% by out-of-fold log-odds | as named in the programme; the cut itself is ours |
| Stage 1 export | 10 km NMS between sites; site = mean of its top 3 patches | as in the app's step 08 |
| E1 negatives | no catalogued crater >= 0.8 km within the central 2 km | the programme marks these as our choice |
| Extra-tile TEST share | 20% by hash of the tile name | matches the region rule |
| Earth VAL regions | atacama_yungay, namib, qaidam (3 of 18, seed 42) | VAL is needed for selection and early stopping |
| E1 | leave out candidates overlapping the query window | otherwise self-retrieval |
| E4 | 300 Earth queries; noise sigma 0.5 m; sun 315 -> 135 deg | small, fixed nuisance changes |
| Stage 3 Moon | SLDEM: 4 latitude bands x 22,500, 30% mare; blocks 30 x 13.4 km, 8 per band read | spread across latitudes and mare/highland |
| Stage 3 polar | 30 m copies for 25% of LOLA patches; VAL = 20 km blocks hashed < 0.10 | for the multi-scale ablation |
| Stage 3 Earth | candidate cell: land >= 50%; polar: snow/ice < 50%; WorldCover 8x overview at 16 x 16 points per patch for main's rule; every valid stride-32 window kept | data volume |
| Stage 3 Earth VAL | 'val:' + tile hashes < 0.125 | about 10% of non-test tiles |
| Mars | zero-shot (CTX DTMs are downloadable without a login, but Stage 5 batches are half Moon / half Earth) | programme's batch rule |
| Stage 4 | ejecta amplitude = Pike rim height (continuous at the rim); ejecta cut at 5 R; degradation time uniform 0-3,000 Myr; centres placed over the patch plus a 2 km margin; b = 3 shown as sensitivity | profile continuity, range of the cited average |
| Stage 5 | epoch = 80 steps (Mac), 40 epochs, warm-up 10, patience 6; ablations 60 steps x 20 epochs; AdamW weight decay 1e-4; channels not colour-normalised; small-angle rotation +-10 deg; noise sigma 0-1 m | fits the 3-hour Mac budget |
| Stage 5 early stopping | VAL E1 AUC + VAL E4 aggregate top-10 | the two pre-registered VAL criteria, equal weight |
