"""Step 02: fetch Earth elevation (Copernicus GLO-30) and land cover (WorldCover).

For every region in ``config/regions.yaml`` the script builds a square box,
``half_km`` either side of the cited centre, works out which 1 x 1 degree
Copernicus DEM tiles and 3 x 3 degree WorldCover tiles it touches, reads only
the needed window of each Cloud-Optimised GeoTIFF over HTTPS and mosaics them.

* Copernicus GLO-30 missing for a land tile -> retry with GLO-90 and log it.
* A tile absent from both tile lists is open ocean and is skipped.
* WorldCover has no tiles for Antarctica; such regions are written without a
  land-cover file and flagged ``worldcover: unavailable``.

Outputs: ``data/raw/earth/<region>_dem.tif``, ``<region>_wc.tif`` and
``data/raw/earth/fetch_log.json``.
"""

from __future__ import annotations

import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import requests
from rasterio.merge import merge
from rasterio.windows import from_bounds

from common import RAW_DIR, get_logger, load_config, load_yaml, now_iso, record_source, selected_regions

log = get_logger("02_fetch_earth")
EARTH_DIR = RAW_DIR / "earth"
DEM_BUCKETS = {
    "GLO-30": ("https://copernicus-dem-30m.s3.amazonaws.com", "10"),
    "GLO-90": ("https://copernicus-dem-90m.s3.amazonaws.com", "30"),
}
WC_BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "4",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "GDAL_HTTP_MULTIRANGE": "YES",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "VSI_CACHE": "TRUE",
}
COPERNICUS_LICENCE = (
    "Copernicus DEM licence: free with attribution "
    "('produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH "
    "2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved')"
)
WORLDCOVER_LICENCE = (
    "CC-BY 4.0; (c) ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) "
    "processed by ESA WorldCover consortium"
)


def box_bounds(lat: float, lon: float, half_km: float) -> tuple[float, float, float, float]:
    """Return (west, south, east, north) of a ``2*half_km`` square box in degrees."""
    dlat = half_km / 111.32
    dlon = half_km / (111.32 * max(math.cos(math.radians(lat)), 0.05))
    south, north = max(lat - dlat, -89.999), min(lat + dlat, 89.999)
    return lon - dlon, south, lon + dlon, north


def _ns(value: int) -> str:
    return f"{'N' if value >= 0 else 'S'}{abs(value):02d}"


def _ew(value: int) -> str:
    return f"{'E' if value >= 0 else 'W'}{abs(value):03d}"


def dem_tile_names(bounds: tuple[float, float, float, float], code: str) -> list[str]:
    """Copernicus tile names (SW-corner naming) intersecting ``bounds``."""
    west, south, east, north = bounds
    names = []
    for lat in range(math.floor(south), math.ceil(north)):
        for lon in range(math.floor(west), math.ceil(east)):
            names.append(f"Copernicus_DSM_COG_{code}_{_ns(lat)}_00_{_ew(lon)}_00_DEM")
    return names


def worldcover_tile_names(bounds: tuple[float, float, float, float]) -> list[str]:
    """WorldCover 3 x 3 degree tile names intersecting ``bounds``."""
    west, south, east, north = bounds
    names = []
    for lat in range(math.floor(south / 3) * 3, math.ceil(north / 3) * 3, 3):
        for lon in range(math.floor(west / 3) * 3, math.ceil(east / 3) * 3, 3):
            names.append(f"ESA_WorldCover_10m_2021_v200_{_ns(lat)}{_ew(lon)}_Map")
    return names


@lru_cache(maxsize=None)
def tile_list(product: str) -> frozenset[str]:
    """Set of tile names published in a Copernicus DEM bucket."""
    base, _ = DEM_BUCKETS[product]
    resp = requests.get(f"{base}/tileList.txt", timeout=60)
    resp.raise_for_status()
    return frozenset(line.strip() for line in resp.text.splitlines() if line.strip())


def url_exists(url: str) -> bool:
    """True when an HTTP HEAD on ``url`` returns 200."""
    return requests.head(url, timeout=60).status_code == 200


def mosaic_window(urls: list[str], bounds: tuple[float, float, float, float], dest: Path,
                  resampling_nodata: float | None,
                  min_res: tuple[float, float] | None = None) -> dict[str, Any]:
    """Read ``bounds`` from each COG URL, mosaic, and write a compressed GeoTIFF.

    ``min_res`` (degrees x, y) caps the read resolution: WorldCover is read at
    about 20 m instead of 10 m, which keeps high-latitude boxes in memory and
    is still three times finer than the 60 m analysis grid.
    """
    with rasterio.Env(**GDAL_ENV):
        sources = [rasterio.open(f"/vsicurl/{u}") for u in urls]
        try:
            res = min(abs(s.res[0]) for s in sources), min(abs(s.res[1]) for s in sources)
            if min_res is not None:
                res = max(res[0], min_res[0]), max(res[1], min_res[1])
            nodata = sources[0].nodata if sources[0].nodata is not None else resampling_nodata
            array, transform = merge(sources, bounds=bounds, res=res, nodata=nodata)
            profile = sources[0].profile.copy()
        finally:
            for s in sources:
                s.close()
    profile.update(
        driver="GTiff", height=array.shape[1], width=array.shape[2], transform=transform,
        count=1, nodata=nodata, compress="deflate", tiled=True, blockxsize=512, blockysize=512,
        predictor=2 if array.dtype.kind in "iu" else 3,
    )
    profile.pop("photometric", None)
    tmp = dest.with_suffix(".part.tif")
    with rasterio.open(tmp, "w", **profile) as out:
        out.write(array[0], 1)
    tmp.replace(dest)
    valid = np.isfinite(array[0]) & (array[0] != nodata) if nodata is not None else np.isfinite(array[0])
    return {"shape": list(array.shape[1:]), "res_deg": list(res), "valid_fraction": float(valid.mean())}


def fetch_region(region: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Fetch DEM and WorldCover for one region; return a log record."""
    default_half = cfg["crater_half_km"] if region["set"] == "crater_benchmark" else cfg["region_half_km"]
    half_km = float(region.get("half_km", default_half))
    bounds = box_bounds(region["lat"], region["lon"], half_km)
    record: dict[str, Any] = {"id": region["id"], "bounds": bounds, "half_km": half_km, "fetched_at": now_iso()}

    dem_dest = EARTH_DIR / f"{region['id']}_dem.tif"
    dem_urls, products, ocean = [], [], []
    for name30 in dem_tile_names(bounds, "10"):
        if name30 in tile_list("GLO-30"):
            dem_urls.append(f"{DEM_BUCKETS['GLO-30'][0]}/{name30}/{name30}.tif")
            products.append("GLO-30")
            continue
        name90 = name30.replace("_COG_10_", "_COG_30_")
        if name90 in tile_list("GLO-90"):
            log.warning("%s: %s missing in GLO-30, using GLO-90", region["id"], name30)
            dem_urls.append(f"{DEM_BUCKETS['GLO-90'][0]}/{name90}/{name90}.tif")
            products.append("GLO-90")
        else:
            ocean.append(name30)
    if not dem_urls:
        raise RuntimeError(f"{region['id']}: no Copernicus DEM tiles found")
    if not dem_dest.exists():
        record["dem"] = mosaic_window(dem_urls, bounds, dem_dest, resampling_nodata=-32767.0)
    record.update(dem_tiles=dem_urls, dem_products=sorted(set(products)), ocean_tiles=ocean)

    wc_dest = EARTH_DIR / f"{region['id']}_wc.tif"
    wc_urls = [f"{WC_BASE}/{n}.tif" for n in worldcover_tile_names(bounds)]
    wc_urls = [u for u in wc_urls if url_exists(u)]
    record["wc_tiles"] = wc_urls
    if wc_urls:
        if not wc_dest.exists():
            lat_c = math.radians(region["lat"])
            wc_res = (20.0 / (111_320.0 * max(math.cos(lat_c), 0.05)), 20.0 / 111_320.0)
            record["wc"] = mosaic_window(wc_urls, bounds, wc_dest, resampling_nodata=0, min_res=wc_res)
        record["worldcover"] = "available"
    else:
        record["worldcover"] = "unavailable"
        log.warning("%s: no WorldCover tiles (e.g. Antarctica); land-cover masks disabled", region["id"])
    return record


def main() -> int:
    """Fetch every selected region in parallel; return a process exit code."""
    EARTH_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    regions = selected_regions(load_yaml("regions.yaml")["regions"])
    log_path = EARTH_DIR / "fetch_log.json"
    previous = json.loads(log_path.read_text()) if log_path.exists() else {}
    records: dict[str, Any] = dict(previous)
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_region, r, cfg): r for r in regions}
        for fut in as_completed(futures):
            region = futures[fut]
            try:
                rec = fut.result()
                merged = {**records.get(region["id"], {}), **rec}
                records[region["id"]] = merged
                log.info("%s: DEM %s from %d tile(s) %s; WorldCover %s",
                         region["id"], merged.get("dem", {}).get("shape"), len(rec["dem_tiles"]),
                         rec["dem_products"], rec["worldcover"])
                for url in rec["dem_tiles"]:
                    record_source(url=url, dataset="Copernicus DEM (ESA)", licence=COPERNICUS_LICENCE,
                                  note=f"window for region {region['id']} read over HTTPS")
                for url in rec["wc_tiles"]:
                    record_source(url=url, dataset="ESA WorldCover 10 m 2021 v200", licence=WORLDCOVER_LICENCE,
                                  note=f"window for region {region['id']} read over HTTPS")
            except Exception as exc:  # noqa: BLE001 - collect and report all failures
                log.error("%s: FAILED: %s", region["id"], exc)
                failures.append(region["id"])
    log_path.write_text(json.dumps(records, indent=2))
    if failures:
        log.error("failed regions: %s", ", ".join(failures))
        return 1
    log.info("fetched %d regions", len(regions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
