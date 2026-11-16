"""Step 11c: "Earth with lunar craters (simulated)" pictures for every Moon match.

Runs after step 11 (it reads the exported shortlist and its shared hillshade stretch). It changes no score and no
existing export; it only adds ``simulated_craters.json`` and ``img/simulated/`` to the web data.

1. Fetch the Robbins (2019) lunar crater database (USGS Astrogeology; recorded in data/SOURCES.md).
2. For each Moon target, count Robbins craters of D >= 1 km centred on a valid pixel of the target's 60 m grid, and
   extrapolate to D >= 240 m with the cumulative slope of ``craters.B_SLOPE`` (the equilibrium slope of small lunar
   craters). The Robbins catalogue is complete only to about 1-2 km, so these densities are lower bounds.
3. For every exported match, read the Earth patch at the display resolution, add craters at the target's density with
   a fixed seed (``craters.crater_field``), and draw it exactly like the other patch images (same hillshade function,
   same shared stretch), marked SIMULATED.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio
import requests
from PIL import ImageDraw
from rasterio.warp import transform as warp_transform
from scipy.stats import chi2

import craters
from common import RAW_DIR, export_dir, get_logger, grids_dir, load_config, now_iso, record_source, run_dir, selected_targets, load_yaml
from display import DisplayWindows
from grids import moon_geographic_crs
from render import hillshade_image

log = get_logger("11c_simulated_craters")
ROBBINS_URL = ("https://astrogeology.usgs.gov/ckan/dataset/f89f5478-b69a-486c-b9b5-30d7b0c5ad2b/resource/"
               "c4f25cc2-4f8a-4207-a845-5e176da3ac5a/download/lunar_crater_database_robbins_2018")
ROBBINS_PAGE = "https://astrogeology.usgs.gov/search/map/moon_crater_database_v1_robbins"
ROBBINS_SHA256 = "694137e141138892555d0f976446875331d3317ea506ddf055d91b917ca307ab"
CSV_NAME = "lunar_crater_database_robbins_2018_bundle/data/lunar_crater_database_robbins_2018.csv"


def robbins_csv() -> Path:
    """Download (once) and unpack the Robbins database; return the CSV path."""
    folder = RAW_DIR / "craters"; folder.mkdir(parents=True, exist_ok=True)
    csv = folder / Path(CSV_NAME).name
    if csv.exists():
        return csv
    zpath = folder / "lunar_crater_database_robbins_2018.zip"
    if not zpath.exists():
        resp = requests.get(ROBBINS_URL, timeout=600); resp.raise_for_status()
        zpath.write_bytes(resp.content)
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    if digest != ROBBINS_SHA256:
        raise RuntimeError(f"Robbins zip checksum {digest} does not match {ROBBINS_SHA256}")
    with zipfile.ZipFile(zpath) as z, z.open(CSV_NAME) as src:
        csv.write_bytes(src.read())
    record_source(url=ROBBINS_URL, dataset="Robbins (2019) lunar crater database v1 (USGS Astrogeology)",
                  licence="No licence or use terms stated on the USGS page, README or PDS4 label; research use, cited, "
                          "not redistributed. Robbins, S. J. (2019), JGR Planets 124, doi:10.1029/2018JE005592",
                  local_path=str(zpath.relative_to(RAW_DIR.parent.parent)), size_bytes=zpath.stat().st_size,
                  note=f"page {ROBBINS_PAGE}; sha256 {digest}")
    return csv


def garwood(n: int) -> tuple[float, float]:
    """Exact Poisson 95% interval for a count."""
    return (0.0 if n == 0 else float(chi2.ppf(0.025, 2 * n) / 2)), float(chi2.ppf(0.975, 2 * n + 2) / 2)


def densities(moon_ids: list[str]) -> dict[str, dict[str, Any]]:
    cat = pd.read_csv(robbins_csv(), usecols=["LAT_CIRC_IMG", "LON_CIRC_IMG", "DIAM_CIRC_IMG"])
    cat = cat[(cat["LAT_CIRC_IMG"] < -80.0) & (cat["DIAM_CIRC_IMG"] >= 1.0)]
    out = {}
    factor = (1000.0 / craters.D_MIN) ** craters.B_SLOPE
    for tid in moon_ids:
        with rasterio.open(grids_dir() / f"{tid}_dem.tif") as g:
            arr = g.read(1, masked=True).filled(np.nan); tf = g.transform; crs = g.crs
        lon = ((cat["LON_CIRC_IMG"].to_numpy() + 180) % 360) - 180
        x, y = warp_transform(moon_geographic_crs(), crs, lon.tolist(), cat["LAT_CIRC_IMG"].to_numpy().tolist())
        cols, rows = ~tf * (np.asarray(x), np.asarray(y))
        rows, cols = np.floor(rows).astype(int), np.floor(cols).astype(int)
        inside = (rows >= 0) & (cols >= 0) & (rows < arr.shape[0]) & (cols < arr.shape[1])
        valid = np.isfinite(arr)
        n1 = int(valid[rows[inside], cols[inside]].sum())
        area = float(valid.sum() * abs(tf.a * tf.e) / 1e6)
        lo, hi = garwood(n1)
        out[tid] = {"craters_ge_1km": n1, "area_km2": round(area, 1),
                    "density_ge_240m_per_km2": round(n1 / area * factor, 3),
                    "density_95_interval": [round(lo / area * factor, 3), round(hi / area * factor, 3)]}
    return out


def main() -> int:
    cfg = load_config()
    out = export_dir()
    meta_web = json.loads((out / "meta.json").read_text())
    stretch = tuple(meta_web["hillshade_stretch"])
    feats = pd.read_parquet(run_dir() / "features.parquet").set_index("patch_id")
    moon = [t["id"] for t in selected_targets(load_yaml("targets.yaml")["targets"]) if t["body"] == "moon"]
    dens = densities(moon)
    dw = DisplayWindows(cfg)
    img_dir = out / "img" / "simulated"
    doc: dict[str, Any] = {
        "generated_at": now_iso(),
        "method": {
            "profile": "parabolic bowl: depth 0.196 D^1.01 (km) and rim height 0.036 D (Pike 1977); ejecta (r/R)^-3 "
                       "outside the rim (McGetchin, Settle and Head 1973), cut at 5 R",
            "degradation": f"linear diffusion, kappa {craters.KAPPA} m2/Myr (Fassett and Thomson 2014), "
                           f"random age 0-{craters.T_MAX_MYR:.0f} Myr per crater",
            "sizes": f"{craters.D_MIN:.0f} m-{craters.D_MAX / 1000:.0f} km, cumulative slope {craters.B_SLOPE} "
                     "(equilibrium of small lunar craters, Minton et al. 2019)",
            "density": "Robbins (2019) craters >= 1 km in each target map, extrapolated to >= 240 m; a lower bound",
            "note": "Illustration only: the Earth patch with the target's crater density added. No score uses it.",
        },
        "targets": {},
    }
    n_img = 0
    for tid in moon:
        res = json.loads((out / "results" / f"{tid}.json").read_text())
        rho = dens[tid]["density_ge_240m_per_km2"]
        sites = {}
        for m in res["matches"]:
            sid = m["site_id"]; r = feats.loc[sid]
            z = dw.window({"patch_id": sid, "source_id": r["source_id"], "row": int(r["row"]), "col": int(r["col"])})
            z = np.where(np.isfinite(z), z, np.nanmedian(z))
            seed = int(hashlib.sha256(f"{tid}:{sid}".encode()).hexdigest()[:8], 16)
            field, n = craters.crater_field(z.shape, dw.res, rho, np.random.default_rng(seed))
            img = hillshade_image(z + field, dw.res, stretch_range=stretch)
            d = ImageDraw.Draw(img)                     # bottom-right: the scale bar is bottom-left, labels sit on top
            d.rectangle([img.width - 96, img.height - 26, img.width - 6, img.height - 8], fill=(255, 255, 255))
            d.text((img.width - 90, img.height - 24), "SIMULATED", fill=(170, 20, 20))
            rel = f"img/simulated/{tid}/{sid.replace(':', '_')}.png"
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            buf = io.BytesIO(); img.save(buf, "PNG", optimize=True); (out / rel).write_bytes(buf.getvalue())
            sites[sid] = {"image": rel, "craters_in_view": n}
            n_img += 1
        doc["targets"][tid] = dens[tid] | {"sites": sites}
    (out / "simulated_craters.json").write_text(json.dumps(doc, indent=1))
    log.info("wrote %d simulated pictures for %d Moon targets", n_img, len(moon))
    return 0


if __name__ == "__main__":
    sys.exit(main())
