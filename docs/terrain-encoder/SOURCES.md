# Sources and licences

Each dataset or package is listed with its official URL, the licence as read there and the date read, before it is
downloaded.

| Item | URL | Licence (as read) | Read on | Used for |
| --- | --- | --- | --- | --- |
| App data (Copernicus GLO-30, LOLA, CTX, WorldCover, POWER) | the app's `DATA_LICENSES.md` and `data/SOURCES.md` | as recorded there | 2026-11-14 | Stage 1 (read only) |
| scikit-learn | https://github.com/scikit-learn/scikit-learn/blob/main/COPYING | BSD 3-Clause | 2026-11-15 | Stage 1 classifiers |
| Robbins (2019) lunar crater database (PDS4 bundle) | https://astrogeology.usgs.gov/search/map/moon_crater_database_v1_robbins (zip sha256 694137e1...ca307ab) | No licence or use terms on the USGS page, README or PDS4 label; purpose stated as research studies. Cite Robbins (2019), JGR Planets 124, doi:10.1029/2018JE005592 | 2026-11-15 | E1, E3, Stage 4 calibration (not redistributed) |
| LOLA 80-90 S 20 m DEM, LDEM_80S_20MPP_ADJ.TIF (PGDA product 90, cloud-optimised GeoTIFF, 2,696,082,051 bytes) | https://pgda.gsfc.nasa.gov/products/90 | No licence stated on the PGDA page; NASA material is "generally not subject to copyright in the United States" and should be acknowledged (https://www.nasa.gov/nasa-brand-center/images-and-media/). Cite Barker et al. (product 90 page) | 2026-11-15 | E5 and Stage 3 Moon patches |
| LOLA 5 m site DEMs, PGDA product 78 (8 non-target sites: Site42, Shoemaker, NPA, NPB, NPC, LM3, LM6, LM7) | https://pgda.gsfc.nasa.gov/products/78 | as above; cite Barker et al. (2021), PSS 203, 105119. LM8 returned HTTP 403 and was skipped | 2026-11-15 | Stage 3 Moon patches |
| SLDEM2015 512 ppd tiles (PGDA product 54) | https://pgda.gsfc.nasa.gov/products/54 ; http://imbrium.mit.edu/DATA/SLDEM2015/TILES/FLOAT_IMG/ | No licence stated; cite Barker et al. (2016), Icarus 273, 346-355; NASA guidelines as above | 2026-11-15 | Stage 3 Moon patches (HTTP range reads) |
| USGS Unified Geologic Map of the Moon, 64 ppd raster (sha256 d6510de0...5fba033) | https://astrogeology.usgs.gov/search/map/unified_geologic_map_of_the_moon_1_5m_2020 | "Use Constraints CC0, but please cite authors"; Fortezzo et al. (2020), LPSC 51, abstract 2760 | 2026-11-15 | highland/mare strata |
| Copernicus DEM GLO-30 (AWS Open Data) | https://registry.opendata.aws/copernicus-dem/ | "available on a free basis for the general public under the terms and conditions of the Licence"; attribution as in the app's DATA_LICENSES.md | 2026-11-15 | extra Earth tiles |
| ESA WorldCover 2021 v200 (AWS) | https://registry.opendata.aws/esa-worldcover-vito/ | CC-BY 4.0 | 2026-11-15 | Earth cell scan and main's land-cover rule |
| NASA POWER climatology (regional) | https://power.larc.nasa.gov/docs/referencing/ | cite POWER as the guide asks; no use restriction stated | 2026-11-15 | Earth rainfall rule |
| Earth Impact Database (PASSC) | http://www.passc.net/EarthImpactDatabase/ | site returns a parked-domain page; terms cannot be read | 2026-11-15 | skipped (E2 extended set) |
| Lightly 1.6.1 (VICReg loss and head) | https://github.com/lightly-ai/lightly/blob/master/LICENSE.txt | MIT | 2026-11-15 | Stages 5-6 |
| torchvision ResNet-18 ImageNet weights | https://github.com/pytorch/vision/blob/main/LICENSE | BSD 3-Clause (code); weights as distributed by torchvision | 2026-11-15 | backbone start |

## Constants (Stage 4), each checked against an open source that quotes the primary
- Pike (1977) depth of fresh simple lunar craters d = 0.196 D^1.01 (km, D < 15 km): quoted in Feoktistova and Ipatov,
  arXiv:2103.00291, Eq. 1 (read 2026-11-15). The primary (Proc. Lunar Sci. Conf. 8, 3427) is not open; not read.
- Pike rim height of simple craters h = 0.036 D: quoted in the IMPACTS paper, arXiv:2203.07476 (read 2026-11-15).
- McGetchin, Settle and Head (1973) ejecta thickness t = 0.14 R^0.74 (r/R)^-3 (R in m): quoted in arXiv:2511.14442,
  Eq. 4 (read 2026-11-15). Primary: EPSL 20, 226-236; not open.
- Fassett and Thomson (2014) average lunar topographic diffusivity about 5.5 m^2/Myr over the past 3 Ga: ADS abstract
  2014JGRE..119.2255F (read via search, 2026-11-15).
- Equilibrium cumulative size-frequency slope of small lunar craters = 2: Minton et al. (2019), arXiv:1902.07746
  (read 2026-11-15).
