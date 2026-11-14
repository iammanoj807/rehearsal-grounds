# Rehearsal Grounds

**Where on Earth should a team rehearse for a specific Moon or Mars site?** Rehearsal Grounds matches terrain at the
scale of a crater rim, ridge or lava field (a 60 m grid, 3.84 km patches), not at the scale of a whole region. For
each named target, such as the Malapert massif near the lunar south pole or the Jezero crater landing area on Mars, it
ranks thousands of Earth patches. Each candidate analog then gets a dossier: the two terrains side by side, what
matches, where the analogy breaks down, its climate, whether it is near a known analog, and which tests it suits.

**Live app:** https://iammanoj807.github.io/rehearsal-grounds/ · 2026 NASA Space Apps Challenge, *Identify Earth
Locations that Analog the Permanent Moon Base Locations and Mars*.

![Explore screen: the selected Moon target's terrain in a lens beside the headline question and key numbers](docs/screenshot-hero.jpg)
![Ranked candidate analogs, a swipe comparison of the Moon patch and its Earth match, and the world map](docs/screenshot-explore.jpg)
![Site dossier: similarity score and a swipe comparison of the Moon target patch and the matched Earth patch](docs/screenshot-site.jpg)

## How it works

1. **Real terrain models.** NASA LRO LOLA 5 m/pix site DEMs for five lunar south-pole sites (Malapert massif,
   Shackleton rim, Connecting ridge, de Gerlache rim, Leibnitz beta plateau), the USGS Mars 2020 CTX DTM of the Jezero landing area, and ESA Copernicus DEM
   GLO-30 for 30 Earth regions: 12 well-studied analogs, 12 discovery candidates and 6 crater benchmark tiles.
2. **One common grid.** Everything is resampled to 60 m: Earth to local UTM, the Moon in its polar stereographic
   metres, and Mars warped from equirectangular to an azimuthal equidistant projection centred on Jezero (otherwise
   east-west slopes at 18° N are stretched by 5%). The grids are cut into 64 × 64 px (3.84 km) patches with 50%
   overlap: 65,555 on Earth, 473 on the six targets.
3. **Terrain fingerprint.** 20 rotation-invariant features a geologist can read: relief, hypsometric integral,
   slope statistics and histogram at 60 m and 120 m, roughness, ruggedness, curvature and a bowl-versus-dome
   index. A pretrained ResNet-18 adds a 64-d image embedding of each patch (hillshade, slope and detrended height
   channels). No model is trained.
4. **Search.** Earth patches with more than 20% vegetation (trees, shrubs, grass, moss, wetland), cropland or
   buildings (ESA WorldCover), more than 5% water, more than 50% snow and ice, or under 5 m of relief are
   excluded, which leaves 35,417 candidates. Every candidate is scored against every target
   patch:
   `S = 100 × (0.6 · exp(−d² / 2σ²) + 0.4 · (1 + cos) / 2)`, where d is the fingerprint distance with equal weight
   per feature group, and σ is the median distance from the target's patches to their nearest Earth patch. Sites are
   kept at least 10 km apart.
5. **Explain.** Explanation bars give each feature group's closeness as a percentile against random Earth patch
   pairs. The dossier adds NASA POWER climate, WorldCover land cover within 2 km, a novelty flag and rule-based
   "tests suited" lines. The flag reads "Near a known analog" when the site is within 50 km of a catalogue entry
   (24 analog and astronaut-training sites, each with a source) or inside a well-studied analog region, and
   "Outside our analog catalogue" otherwise. Antarctica has no WorldCover tiles, so McMurdo sites stay in the
   search and their dossiers warn that the patch may be glacier ice.

## Validation

All numbers are read from [`web/public/data/validation.json`](web/public/data/validation.json), written by
`pipeline/10_validate.py`. Nothing is edited by hand.

**V1, crater retrieval (headline).** Seven PASSC impact craters 0.8–3.5 km across, exposed and younger than 10 Ma.
Each crater-centred patch is used as a query against 65,407 regular grid patches from the other regions. A hit is a
patch whose window fully contains another crater. Hard negatives are only the non-crater patches of the other
crater tiles (about 6,500 per query): non-crater terrain from the same landscapes as the other benchmark craters.

| Ranker | Mean ROC AUC | AUC, hard negatives | Mean reciprocal rank | Hit rate @10 |
| --- | --- | --- | --- | --- |
| Random | 0.546 | 0.546 | 0.000 | 0% |
| Relief only | 0.629 | 0.524 | 0.004 | 0% |
| Terrain features only | 0.632 | 0.542 | 0.000 | 0% |
| **Image embedding only** | **0.976** | **0.976** | **0.656** | **86%** |
| Combined, Earth-to-Earth σ (0.16) | 0.976 | 0.974 | 0.387 | 71% |
| Combined, Moon-target σ (0.71) | 0.885 | 0.842 | 0.019 | 0% |

The finding: at 60 m the readable terrain features alone recognise 1–3 km craters only weakly, while the image
embedding does much better, also against hard negatives, so it recognises the craters themselves, not just the
landscapes around them. The
Earth-to-Earth combined row tracks the embedding because its σ drives the terrain term to near zero. At the Moon
targets' σ (median 0.71, the closer match to how the app ranks Moon targets) the combined score still separates
craters from other terrain (AUC 0.885), but another crater rarely reaches the top 10: patches with similar slope and
relief compete with them. The app keeps 60% terrain features because they carry the slope, relief and roughness
values operations planning needs, and the 0.6/0.4 split was set before this benchmark existed; changing it now
would tune the method on its own test set. An earlier version of the test leaked: crater-centred patches were also
the answers. The Validation page documents that fix.

**V2, rediscovery.** The median well-studied region's best patch ranks in the top 1.1% for every target, and the
median discovery region's in the top 1.8%, so this measure does not separate the two sets. It is reported as
context only.

**V3, robustness.** The 90 m rerun gives Spearman ρ between 0.80 (Jezero) and 0.95 (Connecting ridge) for the
top-20 regions of the six targets. With ±20% feature-group weight perturbations, 86–99% of top-10 sites stay in
the top 10. The terrain/embedding split matters more: at 0.4/0.6, 60–80% of each target's top 10 stays, and at
0.8/0.2, 60–100%.

**V4, sanity checks.** All four pass: self-match = 100, 90° rotation keeps its own top match, flat plane = slope 0,
gradient 0.1 = 5.71°.

## Quick start

```bash
make setup                # Python 3.11 venv (uv) + web dependencies
make pipeline-small       # 1 target, 2 regions, under a minute; writes data/small/export
make pipeline             # full run: downloads ~0.9 GB, about 10 minutes on a laptop
make test                 # 31 unit tests
cd web && npm run dev     # app on http://localhost:5173/rehearsal-grounds/
```

The web app only reads the static files in `web/public/data/`. There is no server.

## Pipeline

| Step | Script | Output |
| --- | --- | --- |
| 01 | `01_fetch_targets.py` | LOLA and CTX GeoTIFFs in `data/raw/targets/` |
| 02 | `02_fetch_earth.py` | Copernicus DEM + WorldCover windows per region (COGs over HTTPS) |
| 03 | `03_reproject.py` | 60 m metric grids (UTM, polar stereographic, Mars azimuthal equidistant) |
| 04 | `04_patches.py` | 3.84 km patches, land-cover shares, overlap de-duplication |
| 05 | `05_features.py` | `features.parquet` (20 features per patch) |
| 06 | `06_embed.py` | ResNet-18 embeddings → PCA 64-d (target rotations included) |
| 07 | `07_index.py` | robust scaling, FAISS index, σ and percentile calibration |
| 08 | `08_query.py` | top-50 sites per target after 10 km non-maximum suppression |
| 09 | `09_environment.py` | NASA POWER climate, WorldCover 2 km shares, novelty |
| 10 | `10_validate.py` | `validation.json` (V1–V4) |
| 11 | `11_export.py` | JSON + hillshade PNGs validated against `pipeline/schemas.py` |

Configuration lives in `config/`: `pipeline.yaml`, plus regions, targets, craters, known analogs and the tests-suited
rules, each entry with its source URL.

## Data sources and licences

LOLA site DEMs (NASA GSFC PGDA; Barker et al. 2021), Mars 2020 TRN CTX DTM (USGS, CC0; Fergason et al. 2020),
Copernicus DEM GLO-30 (ESA/EU), ESA WorldCover 2021 (CC-BY 4.0), NASA POWER, NASA GIBS (Blue Marble and Landsat
WELD tiles), the PASSC Earth Impact Database (read from Internet Archive snapshots, because passc.net is offline),
Wikipedia and PANGAEA coordinates. See [`DATA_LICENSES.md`](DATA_LICENSES.md) for the attribution text and
[`data/SOURCES.md`](data/SOURCES.md) for every downloaded file with URL and date.

## Limits

- Earth cannot reproduce lunar or martian gravity, vacuum or thin CO₂ air, radiation, regolith or polar lighting.
- A 60 m grid cannot see boulders or small craters. The LOLA site maps are largely interpolated between laser tracks.
- Copernicus DEM is a surface model, so vegetation and lakes distort it. Land-cover masks remove the worst cases.
- The steepest target slopes have no close Earth match. Earth has a close terrain match for 56% of Malapert's
  patches and 69% of Shackleton rim's (90–100% for the other four targets). The unmatched patches are the steep,
  high-relief ones: for Malapert, their median 90th-percentile slope is 26.9° and relief 1,493 m, against 21.1° and
  877 m for the matched patches. For Shackleton rim the figures are 32.4° and 2,139 m against 25.9° and 859 m.
- The vegetation mask counts sparse grassland too, so arid grassland regions are excluded from the search: the
  Pilbara and Ries keep no searchable patches, and Meteor Crater keeps 545 of 2,390.
- Antarctica has no land-cover data, so McMurdo patches are not masked. McMurdo now holds 11 of the 60 top-10
  places across the six targets; each of those dossiers warns that the patch may be glacier ice.
- The novelty catalogue is a set of 24 points, not a complete census of analog research. "Outside our analog
  catalogue" means only that: the site may still have been studied.
- Crater benchmark: seven craters, so the metrics carry wide uncertainty.

## Licence

Code: MIT (see `LICENSE`). Data: see `DATA_LICENSES.md`.
