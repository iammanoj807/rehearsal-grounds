# Submission text: Rehearsal Grounds

Text for the Space Apps project page. Every number comes from `web/public/data/validation.json`,
`web/public/data/meta.json` and the results files of the run dated 2026-11-14.

## Title

Rehearsal Grounds: finding where on Earth to rehearse the Moon and Mars

## Team and challenge

- Team: Rehearsal Grounds
- Member: Manoj Kumar Thapa
- Challenge: Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars (2026 NASA Space Apps
  Challenge, Universal Event)

## Links

- Demo video (30 s): **[ADD LINK]**
- Backup demo, 7-slide deck (use this if there is no video):
  https://github.com/iammanoj807/rehearsal-grounds/blob/main/docs/rehearsal-grounds-slides.pdf
- Live app: https://iammanoj807.github.io/rehearsal-grounds/
- Code: https://github.com/iammanoj807/rehearsal-grounds

## High-level summary

Before astronauts and rovers work on the Moon's south pole or in Jezero crater, teams rehearse on Earth. Existing
analog screening works at tens of kilometres; Rehearsal Grounds works at the scale of a crater rim or lava field. It
turns NASA LRO LOLA lunar terrain, USGS Mars CTX terrain and ESA Copernicus Earth elevation into 3.84 km terrain
fingerprints, adds a learned image embedding, and searches 35,417 Earth patches for the closest matches. Each
candidate gets a scorecard of what matches, where the analogy breaks down, and which tests it suits. The image
embedding finds impact craters across continents with a mean ROC AUC of 0.976, also against hard negatives from
other crater landscapes; the terrain features alone reach 0.63, and the combined score as used for the Moon
targets reaches 0.885.

## Project details

**What it does.** A field-test planner picks one of six targets, such as the Malapert massif (named among NASA's candidate Artemis
III landing regions, October 2024) or the Jezero landing area. The app shows the 50 best-matching Earth sites on a map and in a
ranked list, each at least 10 km from the next. Every site opens a dossier with:

- the target patch and the Earth patch as hillshades at the same scale;
- five explanation bars (relief, slope, roughness, shape, image embedding);
- a terrain table for both patches;
- NASA POWER climate and ESA WorldCover land cover;
- a novelty flag: "Near a known analog" (within 50 km of one of 24 sourced analog and astronaut-training sites,
  or inside a well-studied analog region) or "Outside our analog catalogue";
- strong-match, breaks-down and tests-suited lines;
- a downloadable Markdown dossier.

**How it works.**

1. Fetch real terrain models (LOLA 5 m site DEMs, the CTX DTM, Copernicus GLO-30 for 30 Earth regions).
2. Resample everything to a common 60 m metric grid, warping Mars from equirectangular to an azimuthal equidistant
   projection centred on Jezero, and cut 3.84 km patches: 65,555 on Earth and 473 on the six targets.
3. Compute 20 rotation-invariant terrain features and a ResNet-18 image embedding per patch.
4. Remove vegetated (trees, shrubs, grass, moss, wetland), cropland, built-up, wet, icy and flat Earth patches
   with ESA WorldCover. Score every remaining Earth patch against every target patch: 60% terrain fingerprint,
   40% image embedding.
5. Explain each match and add climate, land cover and novelty.

**Why scale matters.** Screening Earth at about 50 km cells can say "the Atacama". At 60 m and 3.84 km patches, the
answer is a specific slope or ridge that a team can drive, walk and image. Example: the top match for Malapert
massif is a slope near Yungay in the Atacama, a well-studied analog area, with a 90th-percentile slope of 16.4°
against 16.5° on the Moon. It scores 89.1 of 100.

**Validation results.**

- **Crater retrieval benchmark.** Seven confirmed impact craters 0.8–3.5 km across, from the PASSC Earth Impact
  Database. Each crater's patch searches 65,407 grid patches from other regions.
  - The image embedding reaches a mean ROC AUC of 0.976 and puts another crater in the top 10 for 86% of queries.
    Against hard negatives (non-crater patches from the other crater tiles) it also reaches 0.976, so it
    recognises craters, not just dry terrain.
  - The 20 readable terrain features alone reach 0.632, about the same as relief alone (0.629).
  - The combined score at the Moon targets' σ, the closer match to the app's ranker, reaches 0.885, but another
    crater rarely reaches its top 10. We keep 60% terrain features because they carry the slope and roughness
    values operations planning needs; the split was set before the benchmark, and changing it now would tune
    the method on its own test set.
  - Random scores 0.546.
  - Our first version had a leak, which we found and fixed; the Validation page explains it.
- **Robustness.** A 90 m rerun keeps the top-20 region ranking (Spearman ρ 0.80–0.95 across the six targets).
  With ±20% feature-group weight changes, 86–99% of top-10 sites stay in the top 10. Changing the
  terrain/embedding split to 0.4/0.6 or 0.8/0.2 keeps 60–100%.
- **Sanity checks.** All four pass.
- **Rediscovery of known analogs.** Saturated, so it is reported as context only.

**What is new compared with regional screening.**

- Site-scale matching: a 60 m grid and 3.84 km patches.
- Side-by-side terrain evidence for every match.
- A per-target terrain coverage figure: Earth has a close match for 56% of Malapert's patches, 69% of Shackleton
  rim's, 90% of de Gerlache rim's, 94% of Leibnitz beta's, 98% of Connecting ridge's and 100% of Jezero's.
- A benchmark with clean ground truth, plus an honest ablation.
- Sites outside our analog catalogue, flagged by distance to a sourced catalogue. Examples: Puna de Atacama for
  Shackleton rim (#4, 112 km from Licancabur, the nearest catalogued analog); Harrat Khaybar for Jezero (#2,
  768 km from Makhtesh Ramon, where the D-MARS and AMADEE-20 analog missions ran).

**Limits.**

- Earth cannot reproduce lunar or martian gravity, vacuum or thin CO₂ air, radiation, regolith or polar light.
- A 60 m grid misses boulders and small craters.
- The steepest lunar massif faces have no close Earth match.
- Copernicus DEM is a surface model.
- The crater benchmark has only seven craters.
- The novelty catalogue is a set of 24 points, not a census; "outside our analog catalogue" does not mean
  unstudied.
- Antarctica has no WorldCover land-cover data, so McMurdo sites are not masked; their dossiers warn that the
  patch may be glacier ice.

**Tools used.** Python, rasterio/GDAL, NumPy, SciPy, pandas, scikit-learn, PyTorch and torchvision (ResNet-18), FAISS,
Pydantic, React, TypeScript, Vite, Leaflet, GitHub Pages.

**What comes next.**

- More targets: Gale crater, other Artemis candidate regions, and a lunar pit for the caves consideration.
- Finer Earth DEMs inside the best regions.
- LRO Diviner temperatures beside the Earth climate values.
- Process tags (impact, volcanic, aeolian, glacial).
- Client-side weight sliders.

## Space agency data

- **NASA LRO LOLA 5 m south-pole site DEMs (GSFC PGDA):** Moon target terrain (Malapert massif, Shackleton rim,
  Connecting ridge, de Gerlache rim, Leibnitz beta plateau).
- **USGS Astrogeology Mars 2020 TRN CTX DTM:** Mars target terrain (Jezero landing area).
- **ESA Copernicus DEM GLO-30:** Earth terrain for all 30 regions.
- **ESA WorldCover 2021:** vegetation, cropland, built-up and water masks, and the bare and snow-ice shares around
  each site.
- **NASA POWER climatology:** temperature, range, precipitation, humidity and sunlight for every candidate site.
- **NASA GIBS:** Blue Marble and Landsat WELD map tiles in the app.

## References

- Barker, M.K. et al. (2021). Improved LOLA Elevation Maps for South Pole Landing Sites: Error Estimates and Their
  Impact on Illumination Conditions. Planetary and Space Science 203, 105119. doi:10.1016/j.pss.2020.105119
- NASA GSFC PGDA, South Pole Landing Site LOLA DEMs: https://pgda.gsfc.nasa.gov/products/78
- Fergason, R.L. et al. (2020). Mars 2020 Terrain Relative Navigation CTX DTM Mosaic. USGS Astrogeology Science
  Center. doi:10.5066/P906QQT8
- Copernicus DEM GLO-30, ESA / European Union: https://registry.opendata.aws/copernicus-dem/
- Zanaga, D. et al. (2022). ESA WorldCover 10 m 2021 v200. doi:10.5281/zenodo.7254221
- NASA POWER Project, NASA Langley Research Center: https://power.larc.nasa.gov/
- NASA Global Imagery Browse Services (GIBS): https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api
- Earth Impact Database, Planetary and Space Science Centre, University of New Brunswick (read via Internet Archive
  snapshots; URLs in `config/craters.yaml`)
- Pfeiffer, M., Amundson, R., Jordan, T.E. (2021). Soil temperature and relative humidity at the Yungay hyperarid
  site. PANGAEA. doi:10.1594/PANGAEA.929560
- NASA (28 October 2024). NASA Provides Update on Artemis III Moon Landing Regions:
  https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/
- He, K. et al. (2016). Deep Residual Learning for Image Recognition. CVPR. (torchvision ResNet-18 weights)
- Wikipedia articles cited per region and per catalogued analog in `config/regions.yaml` and
  `config/known_analogs.yaml`
- Official challenge page: Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars, 2026 NASA
  Space Apps Challenge

## 30-second video storyboard

| Time | Shot | Voice-over |
| --- | --- | --- |
| 0–4 s | Title card with team image | "I'm Manoj, team Rehearsal Grounds, Identify Earth Analogs challenge." |
| 4–9 s | Malapert massif hillshade | "Before we drive on the lunar south pole, we rehearse on Earth. But where, exactly?" |
| 9–19 s | Screen recording: pick Malapert, map fills, open the top match, side-by-side view | "We match NASA lunar terrain against Earth's, patch by patch at 60 metres, and explain every match." |
| 19–25 s | Validation page | "Its image embedding finds impact craters across continents, with an AUC of 0.98." |
| 25–30 s | Data credits and URL | "Built on NASA, USGS and ESA open data. Try it at iammanoj807.github.io/rehearsal-grounds." |

## Backup slide deck (7 slides including title)

1. Title: Rehearsal Grounds, team name, Manoj Kumar Thapa, challenge name.
2. The problem: analog sites are chosen by tradition, and regional screening works at about 50 km.
3. The idea: match terrain at 60 m, so the answer is a rim or a ridge, not a region.
4. How it works: the five-stage pipeline.
5. Example: Malapert massif vs its top Earth match (Atacama near Yungay, 89.1), side by side with the scorecard.
6. Validation: crater benchmark (AUC 0.976 embedding, also 0.976 against hard negatives, vs 0.632 features, 0.885
   combined at the Moon σ and 0.546 random), robustness, limits.
7. Impact and next steps, with data credits.

## Still to do before submitting

- [ ] Record the 30-second video and add its public link above, or submit the 7-slide PDF deck
      (`docs/rehearsal-grounds-slides.pdf`, built by `scripts/make_slides.py` from the exported data) as the demo.
- [ ] Confirm the live URL loads on a phone after the GitHub Pages deploy.
- [ ] Recheck the 2026 submission guide for any changed limits.
