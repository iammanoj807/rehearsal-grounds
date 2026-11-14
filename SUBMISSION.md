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

In May 2024 NASA's JETT5 field test rehearsed Artemis III moonwalks in Arizona's San Francisco Volcanic Field, and ran
some EVAs at night to test a variety of lighting conditions, because the lighting at the lunar south pole is dynamic.
Rehearsal Grounds answers two questions for an analog field-test planner: where on Earth does the terrain match a
specific Artemis III or Mars site, patch by patch at 60 m; and where and when does the real Sun cast south-pole-like
shadows there? It turns NASA LRO LOLA lunar terrain, USGS Mars CTX terrain and ESA Copernicus Earth elevation into
3.84 km terrain fingerprints, searches 43,794 Earth patches, and adds a separate low-Sun shadow comparison, a
12-month rehearsal calendar and a check of how the usual analog sites, including the JETT5 area, score on the same
fingerprint. Its image embedding finds impact craters across continents with a mean ROC AUC of 0.976.

## Project details

**What it does.** A field-test planner picks one of nine targets: eight LOLA south-pole sites, four of them named
Artemis III candidate regions in NASA's October 2024 release (Haworth, Malapert Massif, Nobile Rim 1, Nobile Rim 2),
and the Jezero landing area on Mars. The app shows the 50 best-matching Earth sites on a map and in a ranked list,
each at least 10 km from the next, and how the usual analog regions rank. Every site opens a dossier with:

- a swipe comparison of the target and Earth patches at the same scale, with a "Low sun" mode showing cast shadows
  at the middle of the target's noon Sun band;
- five explanation bars (relief, slope, roughness, shape, image embedding) and a terrain table;
- a lighting similarity: the share of each patch in shadow at the target's low Sun elevations, compared;
- a 12-month calendar of low-sun hours, daylight, NASA POWER temperature and rain, with suggested months;
- NASA POWER climate and ESA WorldCover land cover;
- a novelty flag ("Near a known analog" or "Outside our analog catalogue", from 24 sourced analog sites);
- strong-match, breaks-down and tests-suited lines, and a "Before you go" box;
- downloads: Markdown dossier, a printable field-test brief, and the shortlist as CSV, GeoJSON or KML.

**How it works.**

1. Fetch real terrain models (LOLA 5 m site DEMs, the CTX DTM, Copernicus GLO-30 for 30 Earth regions).
2. Resample everything to a common 60 m metric grid and cut 3.84 km patches: 65,555 on Earth and 831 on the nine
   targets.
3. Compute 20 rotation-invariant terrain features and a ResNet-18 image embedding per patch.
4. Remove Earth patches with more than 20% trees, crops, buildings, wetland or mangrove; shrub, grass and moss count
   too where NASA POWER gives more than 500 mm of rain a year (the upper bound of semiarid land, USGS). Remove wet,
   icy and flat patches. Score every remaining patch against every target patch: 60% terrain fingerprint, 40% image
   embedding.
5. Explain each match; add climate, land cover, novelty, the usual-site comparison, the low-Sun shadow fingerprint
   (36 Sun directions, 3.84 km of surrounding terrain, curvature d²/2R) and the monthly Sun hours (NOAA equations).

**Why scale and light matter.** Screening Earth at about 50 km cells can say "the Atacama". At 60 m and 3.84 km
patches, the answer is a specific slope or ridge that a team can drive, walk and image. Example: the top match for
Malapert massif, an Artemis III candidate region, is a slope near Yungay in the Atacama with a 90th-percentile slope
of 16.4° against 16.5° on the Moon. It scores 89.1 of 100. At Malapert the noon Sun stays between 2.5° and 5.6° all
year; at 3° and 5° the two patches have a lighting similarity of 93.4, and our rule suggests May, November and
December for a rehearsal there.

**How the usual sites compare.** On the same score, the best searchable patch of the SP Crater region, in the
volcanic field where JETT5 ran, ranks #580 for Malapert, and its best patch overall is one our land-cover masks remove
(#118 with masks off). Across the eight Moon targets it ranks between #251 and #1,288; for Jezero it ranks #19. This
is a closer terrain match on our fingerprint, not a judgement of NASA's choice: JETT5 tested operations, not 60 m
terrain similarity.

**Validation results.**

- **Crater retrieval benchmark.** Seven confirmed impact craters 0.8–3.5 km across, from the PASSC Earth Impact
  Database. Each crater's patch searches 65,407 grid patches from other regions.
  - The image embedding reaches a mean ROC AUC of 0.976 and puts another crater in the top 10 for 86% of queries.
    Against hard negatives (non-crater patches from the other crater tiles) it also reaches 0.976, so it
    recognises the craters themselves, not just their surrounding landscapes.
  - The 20 readable terrain features alone reach 0.632, about the same as relief alone (0.629).
  - The combined score at the Moon targets' σ, the closer match to the app's ranker, reaches 0.889, and another
    crater reaches its top 10 for 14% of queries. We keep 60% terrain features because they carry the slope and roughness
    values operations planning needs; the split was set before the benchmark, and changing it now would tune
    the method on its own test set.
  - Random scores 0.546.
  - Our first version had a leak, which we found and fixed; the Validation page explains it.
- **Robustness.** A 90 m rerun keeps the top-20 region ranking (Spearman ρ 0.74–0.97 across the nine targets).
  With ±20% feature-group weight changes, 86–99% of top-10 sites stay in the top 10. Changing the
  terrain/embedding split to 0.4/0.6 or 0.8/0.2 keeps 50–100%.
- **Sanity checks.** All four pass.
- **Lighting checks.** All four pass: no shadow on a flat plane; a 100 m step casts a shadow of h / tan(e) within
  one pixel; the lunar curvature drop at 10 km is 28.78 m; solar elevation matches the published NREL SPA example
  (39.872° against 39.888°).
- **Rediscovery of known analogs.** Saturated, so it is reported as context only.

**What is new compared with regional screening.**

- Site-scale matching: a 60 m grid and 3.84 km patches.
- Side-by-side terrain evidence for every match.
- A per-target terrain coverage figure: Earth has a close match for 56% of Malapert's and Nobile rim 1's patches,
  69% of Shackleton rim's, 86% of Nobile rim 2's, 90% of de Gerlache rim's, 91% of Haworth's, 94% of Leibnitz
  beta's, 98% of Connecting ridge's and 100% of Jezero's.
- A low-Sun lighting analog, kept separate from the terrain score, and a rehearsal calendar per site.
- The usual analog sites, including the JETT5 area, ranked on the same fingerprint.
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
- Antarctica has no WorldCover land-cover data, so McMurdo sites are not masked (17 of the 90 top-10 places);
  their dossiers warn that the patch may be glacier ice.
- Lighting: a 60 m grid misses small shadows; no atmosphere scattering, regolith reflectance or Earthshine; at 1–2°
  most rough terrain is largely in shadow on both bodies, so lighting scores bunch near the top (medians 92–95).
- Suggested months are our rule (dry, −25 to 35 °C, most low-sun hours), not safety advice.

**Tools used.** Python, rasterio/GDAL, NumPy, SciPy, pandas, scikit-learn, PyTorch and torchvision (ResNet-18), FAISS,
Pydantic, React, TypeScript, Vite, Leaflet, GitHub Pages.

**What comes next.**

- More targets: the other five Artemis III candidate regions once site maps exist, Gale crater, and a lunar pit.
- Finer Earth DEMs inside the best regions.
- LRO Diviner temperatures beside the Earth climate values.
- Process tags (impact, volcanic, aeolian, glacial).
- Client-side weight sliders.

## Space agency data

- **NASA LRO LOLA 5 m south-pole site DEMs (GSFC PGDA):** Moon target terrain (Malapert massif, Shackleton rim,
  Connecting ridge, de Gerlache rim, Leibnitz beta plateau, Haworth, Nobile rim 1, Nobile rim 2).
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

Every spoken number comes from the exported data of this run.

| Time | Shot | Voice-over |
| --- | --- | --- |
| 0–6 s | JETT5 night-EVA image (NASA, "A Moonlit Moonwalk") or the slide 2 text | "In 2024 NASA rehearsed Artemis III moonwalks in Arizona, some at night, to test the south pole's changing light." |
| 6–12 s | Screen recording: pick Malapert massif (Artemis III region badge), the map fills | "Pick an Artemis III region. We match its terrain against 43,794 Earth patches at 60 metres." |
| 12–20 s | Open the top match (Atacama near Yungay, 89.1); swipe the divider; switch to Low sun | "The best match scores 89.1. Under Malapert's low noon Sun, 3 to 5 degrees up, the shadows agree at 93.4." |
| 20–25 s | Scroll to "When to go" (May, Nov, Dec) and back to "How the usual analog sites compare" | "It suggests the best months, and shows how the usual sites, including the JETT5 area, rank on the same fingerprint." |
| 25–30 s | Data credits and URL | "Built on NASA, USGS and ESA open data. Try it at iammanoj807.github.io/rehearsal-grounds." |

## Backup slide deck (7 slides including title)

1. Title: Rehearsal Grounds, team name, Manoj Kumar Thapa, challenge name.
2. The problem: JETT5 rehearsed Artemis III moonwalks in Arizona, some at night to test lighting conditions; the two
   questions the app answers.
3. The targets: eight LOLA south-pole sites, four of NASA's nine Artemis III candidate regions, and Jezero.
4. How it works: the five-stage pipeline, now with the low-Sun analog and monthly Sun hours.
5. Artemis III example: Malapert massif vs Atacama near Yungay (89.1), the swipe pair and the low-Sun pair, lighting
   similarity 93.4, best months.
6. Validation: crater benchmark (AUC 0.976 embedding, 0.976 against hard negatives, 0.632 features, 0.889 combined at
   the Moon σ, 0.546 random), robustness, lighting checks.
7. Impact: planner outputs, the usual sites on the same score (JETT5 area #580 for Malapert), next steps, credits.

## Still to do before submitting

- [ ] Record the 30-second video and add its public link above, or submit the 7-slide PDF deck
      (`docs/rehearsal-grounds-slides.pdf`, built by `scripts/make_slides.py` from the exported data) as the demo.
- [ ] Confirm the live URL loads on a phone after the GitHub Pages deploy.
- [ ] Recheck the 2026 submission guide for any changed limits.
