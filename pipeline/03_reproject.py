"""Step 03: warp every raster to a local metric grid at the common resolution.

* Earth: UTM zone of the region centre; a square grid centred on that point.
  Elevation uses ``Resampling.average``; WorldCover uses ``Resampling.mode``.
* Moon: LOLA files are already polar stereographic metres; resample only.
* Mars: the CTX DTM is equirectangular (true scale only at the equator), so it
  is warped to an azimuthal equidistant projection centred on the DTM.

Outputs ``<grids>/<source_id>_dem.tif`` (float32, NaN = no data) and, for Earth,
``<grids>/<source_id>_wc.tif`` (uint8, 0 = no data), plus ``grids.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform as warp_transform

from common import RAW_DIR, get_logger, grids_dir, load_config, load_yaml, selected_regions, selected_targets
from grids import mars_aeqd_crs, mars_geographic_crs, utm_crs

log = get_logger("03_reproject")


def write_grid(path: Path, array: np.ndarray, crs: CRS, transform: Any, nodata: float | int) -> None:
    """Write a single-band compressed GeoTIFF."""
    profile = {
        "driver": "GTiff", "height": array.shape[0], "width": array.shape[1], "count": 1,
        "dtype": array.dtype, "crs": crs, "transform": transform, "nodata": nodata,
        "compress": "deflate", "tiled": True, "blockxsize": 256, "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1)


def warp_to(src_path: Path, dst_crs: CRS, dst_transform: Any, shape: tuple[int, int],
            resampling: Resampling, dtype: str, dst_nodata: float | int) -> np.ndarray:
    """Warp one raster into a fixed destination grid."""
    with rasterio.open(src_path) as src:
        out = np.full(shape, dst_nodata, dtype=dtype)
        src_nodata = src.nodata  # NaN for LOLA, -3.4e38 for CTX, -32767 for Copernicus mosaics
        reproject(
            source=rasterio.band(src, 1), destination=out,
            src_transform=src.transform, src_crs=src.crs, src_nodata=src_nodata,
            dst_transform=dst_transform, dst_crs=dst_crs, dst_nodata=dst_nodata,
            resampling=resampling,
        )
    return out


def earth_grid(region: dict[str, Any], half_km: float, res: float) -> tuple[CRS, Any, tuple[int, int]]:
    """UTM grid centred on the region centre covering +/- half_km."""
    crs = utm_crs(region["lat"], region["lon"])
    xs, ys = warp_transform(CRS.from_epsg(4326), crs, [region["lon"]], [region["lat"]])
    n = int(round(2 * half_km * 1000 / res))
    x0 = xs[0] - n * res / 2.0
    y0 = ys[0] + n * res / 2.0
    return crs, from_origin(x0, y0, res, res), (n, n)


def same_crs_grid(src_path: Path, res: float) -> tuple[CRS, Any, tuple[int, int]]:
    """Grid in the source CRS at ``res`` covering the source bounds."""
    with rasterio.open(src_path) as src:
        b = src.bounds
        crs = src.crs
    w = int(np.floor((b.right - b.left) / res))
    h = int(np.floor((b.top - b.bottom) / res))
    return crs, from_origin(b.left, b.top, res, res), (h, w)


def mars_grid(src_path: Path, res: float) -> tuple[CRS, Any, tuple[int, int], tuple[float, float]]:
    """Azimuthal-equidistant grid centred on the CTX DTM centre."""
    with rasterio.open(src_path) as src:
        b, src_crs = src.bounds, src.crs
    cx, cy = (b.left + b.right) / 2.0, (b.bottom + b.top) / 2.0
    lons, lats = warp_transform(src_crs, mars_geographic_crs(), [cx], [cy])
    lat0, lon0 = lats[0], lons[0]
    dst_crs = mars_aeqd_crs(lat0, lon0)
    # Project the four source corners to size the destination grid.
    xs, ys = warp_transform(src_crs, dst_crs, [b.left, b.right, b.right, b.left], [b.top, b.top, b.bottom, b.bottom])
    half_w = min(abs(min(xs)), abs(max(xs)))
    half_h = min(abs(min(ys)), abs(max(ys)))
    w, h = int(2 * half_w // res), int(2 * half_h // res)
    return dst_crs, from_origin(-w * res / 2.0, h * res / 2.0, res, res), (h, w), (lat0, lon0)


def main() -> int:
    """Warp all selected targets and regions; return a process exit code."""
    cfg = load_config()
    res = float(cfg["resolution_m"])
    out_dir = grids_dir()
    meta: dict[str, Any] = {}

    for target in selected_targets(load_yaml("targets.yaml")["targets"]):
        src = RAW_DIR / "targets" / Path(target["url"]).name
        dst = out_dir / f"{target['id']}_dem.tif"
        if target["body"] == "mars":
            crs, transform, shape, centre = mars_grid(src, res)
            extra = {"centre_lat": centre[0], "centre_lon": centre[1]}
        else:
            crs, transform, shape = same_crs_grid(src, res)
            extra = {}
        dem = warp_to(src, crs, transform, shape, Resampling.average, "float32", np.nan)
        write_grid(dst, dem, crs, transform, np.nan)
        meta[target["id"]] = {"kind": "target", "body": target["body"], "shape": list(shape),
                              "crs": crs.to_wkt(), "valid_fraction": float(np.isfinite(dem).mean()), **extra}
        log.info("%s: %s grid %s, valid %.3f", target["id"], target["body"], shape, meta[target["id"]]["valid_fraction"])

    regions = selected_regions(load_yaml("regions.yaml")["regions"])
    for region in regions:
        half = float(region.get("half_km", cfg["crater_half_km"] if region["set"] == "crater_benchmark" else cfg["region_half_km"]))
        crs, transform, shape = earth_grid(region, half, res)
        dem_src = RAW_DIR / "earth" / f"{region['id']}_dem.tif"
        dem = warp_to(dem_src, crs, transform, shape, Resampling.average, "float32", np.nan)
        write_grid(out_dir / f"{region['id']}_dem.tif", dem, crs, transform, np.nan)
        wc_src = RAW_DIR / "earth" / f"{region['id']}_wc.tif"
        has_wc = wc_src.exists()
        if has_wc:
            wc = warp_to(wc_src, crs, transform, shape, Resampling.mode, "uint8", 0)
            write_grid(out_dir / f"{region['id']}_wc.tif", wc, crs, transform, 0)
        meta[region["id"]] = {"kind": "earth", "body": "earth", "shape": list(shape), "crs": crs.to_wkt(),
                              "valid_fraction": float(np.isfinite(dem).mean()), "worldcover": has_wc}
        log.info("%s: UTM %s grid %s, valid %.3f, worldcover %s", region["id"], crs.to_epsg(), shape,
                 meta[region["id"]]["valid_fraction"], has_wc)

    (out_dir / "grids.json").write_text(json.dumps(meta, indent=2))
    log.info("warped %d rasters at %.0f m", len(meta), res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
