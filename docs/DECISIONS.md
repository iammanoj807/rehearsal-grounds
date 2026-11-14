# Decision log

Choices made while building, newest first. Each entry says what changed from the original plan and why.

| Date | Decision | Why |
| --- | --- | --- |
| 14 Nov | Added the de Gerlache rim (Site11) and Leibnitz beta plateau (Site20) targets after the core app was complete. | Both use the same PGDA LOLA product, so the pipeline needed no changes. |
| 14 Nov | Client-side "priorities" sliders re-rank only the exported top-50 shortlist by weighted explanation bars. | Planners weigh terrain factors differently. The similarity search itself is unchanged, and the UI says so. |
| 14 Nov | V1 crater benchmark: the queries are patches centred on each crater. The candidates are regular grid patches only. A hit is a grid patch whose 3.84 km window fully contains another crater's rim (\|dx\|, \|dy\| ≤ 1.92 km − D/2). | The first version also used the crater-centred patches as answers. The embedding then ranked another crater first for every query, which is an artefact of exact centring. The rule was fixed from geometry before rerunning. Both versions are disclosed on the Validation page. |
| 14 Nov | V1's combined row is labelled "Earth-to-Earth σ". | With σ = 0.163 the terrain term is near zero for crater pairs, so that row tracks the embedding. It is not the exact ranker used for Moon targets. |
| 14 Nov | Novelty is "well studied" within 50 km of a catalogued analog. The catalogue has 21 points: 14 whose Wikipedia article states an analog or astronaut-training use (sentence quoted), plus the 7 remaining well-studied regions from the project list. | This is a transparent, sourced rule. Qaidam Basin is in the catalogue because its article says the China Geological Survey studies it as a Mars analogue, even though the original plan listed it as less studied. |
| 14 Nov | σ in s_morph = exp(−d²/2σ²) is the median distance from the *query's* patches to their nearest candidate. For Earth-to-Earth queries, neighbours in the same region are excluded. | Using the plan's Earth-only nearest-neighbour σ (0.163), s_morph was 0.001–0.05 for every Moon match. The steep lunar massifs sit far from all Earth terrain, so the ranking would have been embedding-only. Fixed before any benchmark run. |
| 14 Nov | The explanation bars are percentiles against 200,000 random cross-region Earth patch pairs. | A Gaussian kernel per group collapses in low dimension. A percentile reads directly: 90 = closer than 90% of random Earth pairs. |
| 14 Nov | Equal group weights are applied as the mean squared difference within each group. | The slope group has 14 features and relief has 2. Plain Euclidean distance would let slope dominate. |
| 14 Nov | Hillshade images are contrast-stretched (1st–99th percentile) for display only. | A uniform 19° lunar slope facing the light rendered almost white. Features are unaffected. |
| 14 Nov | Each Earth region is a 100 km × 100 km box centred on its cited coordinate (60 km for crater tiles), mosaicked from all intersecting Copernicus tiles. Patches in overlapping boxes go to the nearer centre. | 1° tiles cut through features and shrink with latitude. Equal-area boxes keep regions comparable. |
| 14 Nov | WorldCover is read at about 20 m, then mode-resampled to 60 m. | Reading 10 m windows at Svalbard latitudes needs more than 600 MB per region. 20 m is still three times finer than the analysis grid. |
| 14 Nov | McMurdo Dry Valleys runs without land-cover masks. | ESA WorldCover has no Antarctic tiles. The region is flagged in the data and in the app. |
| 14 Nov | Benchmark craters: every PASSC structure 0.8–3.5 km across, exposed, and younger than 10 Ma. Seven pass. The crater centres use Wikipedia coordinates, which agree with PASSC's arc-minute values. | This is an objective rule set before any results. passc.net is offline (parked domain), so the tables were read from Internet Archive snapshots. |
| 14 Nov | The Yungay (Atacama) centre comes from the PANGAEA dataset of the Yungay hyperarid soil site. | No Wikipedia article gives coordinates for the Yungay research area. |
| 14 Nov | Earth imagery in the app uses NASA GIBS Landsat WELD (2000 annual composite, about 38 m). | It is the sharpest true-colour layer GIBS serves globally in Web Mercator. |
| 14 Nov | Static site on GitHub Pages; FastAPI only as a stretch goal. | No server can fail during judging. |
| 14 Nov | Common 60 m grid and 3.84 km patches. | LOLA 5 m pixels are mostly interpolated, and one grid makes slopes comparable across bodies. |
