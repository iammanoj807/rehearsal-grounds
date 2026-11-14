"""Step 04: cut every 60 m grid into overlapping square patches.

Windows of ``patch_px`` pixels slide by ``stride_px``. A patch is kept when at
least ``min_valid_fraction`` of its pixels have elevation. For Earth patches
the WorldCover class shares are stored, plus two flags:

* ``wc_ok``: vegetation + cropland + built-up share (``WORLDCOVER_VEG_BUILT``:
  trees, shrubs, grass, crops, built-up, wetland, mangrove, moss) <=
  ``mask_max_veg_built_crop``, water share <= ``mask_max_water`` and snow/ice
  share <= ``mask_max_snow_ice`` (always True where WorldCover has no coverage,
  i.e. Antarctica, which is flagged by ``wc_available``).
* ``dedupe_ok``: False when the patch also lies inside another region's box
  and is closer to that region's centre (the boxes of nearby regions overlap).

Benchmark craters get one extra patch centred exactly on the crater, because
the 1.92 km patch grid would otherwise often miss the 0.5 km labelling radius.

Outputs ``patches/<source>.npy`` (float32, n x P x P) and
``patches/<source>.parquet`` with
``patch_id, body, source_id, row, col, x_m, y_m, lat, lon`` and the flags.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from numpy.lib.stride_tricks import sliding_window_view
from rasterio.crs import CRS
from rasterio.warp import transform as warp_transform

from common import RAW_DIR, WORLDCOVER_VEG_BUILT, get_logger, grids_dir, load_config, load_yaml, patches_dir, selected_regions, selected_targets
from grids import haversine_km, mars_geographic_crs, moon_geographic_crs

log = get_logger("04_patches")

WORLDCOVER_CLASSES = {
    10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built", 60: "bare",
    70: "snow_ice", 80: "water", 90: "wetland", 95: "mangrove", 100: "moss_lichen",
}


def geographic_crs(body: str) -> CRS:
    """Lon/lat CRS for a body."""
    if body == "earth":
        return CRS.from_epsg(4326)
    return moon_geographic_crs() if body == "moon" else mars_geographic_crs()


def window_origins(n: int, patch: int, stride: int) -> np.ndarray:
    """Top-left offsets of sliding windows along one axis."""
    if n < patch:
        return np.array([], dtype=int)
    return np.arange(0, n - patch + 1, stride)


def class_shares(wc: np.ndarray, rows: np.ndarray, cols: np.ndarray, patch: int) -> dict[str, np.ndarray]:
    """Share of each WorldCover class (over classified pixels) in each window."""
    valid = wc > 0
    count_valid = np.array([valid[r:r + patch, c:c + patch].sum() for r, c in zip(rows, cols)], dtype=float)
    denom = np.maximum(count_valid, 1.0)
    out = {"wc_valid_fraction": count_valid / (patch * patch)}
    for code, name in WORLDCOVER_CLASSES.items():
        hit = wc == code
        out[f"frac_{name}"] = np.array([hit[r:r + patch, c:c + patch].sum() for r, c in zip(rows, cols)]) / denom
    return out


def landcover_ok(table: pd.DataFrame, cfg: dict[str, Any]) -> pd.Series:
    """True where a patch passes the vegetation/built-up, water and snow/ice masks."""
    veg = sum(table[f"frac_{WORLDCOVER_CLASSES[c]}"] for c in WORLDCOVER_VEG_BUILT)
    return ((veg <= cfg["mask_max_veg_built_crop"]) & (table["frac_water"] <= cfg["mask_max_water"])
            & (table["frac_snow_ice"] <= cfg["mask_max_snow_ice"]))


def region_boxes() -> dict[str, dict[str, Any]]:
    """Lat/lon bounds and centres of every fetched region (from the fetch log)."""
    log_path = RAW_DIR / "earth" / "fetch_log.json"
    fetched = json.loads(log_path.read_text())
    regions = {r["id"]: r for r in load_yaml("regions.yaml")["regions"]}
    return {rid: {"bounds": rec["bounds"], "lat": regions[rid]["lat"], "lon": regions[rid]["lon"]}
            for rid, rec in fetched.items() if rid in regions}


def dedupe_flags(region_id: str, lats: np.ndarray, lons: np.ndarray, boxes: dict[str, dict[str, Any]],
                 active: set[str]) -> np.ndarray:
    """True where no other active region's box contains the patch with a nearer centre."""
    own = boxes[region_id]
    keep = np.ones(len(lats), dtype=bool)
    d_own = np.array([haversine_km(a, b, own["lat"], own["lon"]) for a, b in zip(lats, lons)])
    for rid, box in boxes.items():
        if rid == region_id or rid not in active:
            continue
        w, s, e, n = box["bounds"]
        inside = (lons >= w) & (lons <= e) & (lats >= s) & (lats <= n)
        if not inside.any():
            continue
        d_other = np.array([haversine_km(a, b, box["lat"], box["lon"]) for a, b in zip(lats, lons)])
        keep &= ~(inside & (d_other < d_own))
    return keep


def crater_windows(source_id: str, grid_transform: Any, grid_crs: CRS, patch: int,
                   shape: tuple[int, int]) -> list[tuple[str, int, int]]:
    """(crater_id, row, col) windows centred on benchmark craters in this grid."""
    out = []
    for crater in load_yaml("craters.yaml")["craters"]:
        if crater["region_id"] != source_id:
            continue
        xs, ys = warp_transform(CRS.from_epsg(4326), grid_crs, [crater["lon"]], [crater["lat"]])
        col_f, row_f = ~grid_transform * (xs[0], ys[0])
        r0, c0 = int(round(row_f - patch / 2.0)), int(round(col_f - patch / 2.0))
        if 0 <= r0 <= shape[0] - patch and 0 <= c0 <= shape[1] - patch:
            out.append((crater["id"], r0, c0))
    return out


def cut_source(source_id: str, body: str, cfg: dict[str, Any], boxes: dict[str, dict[str, Any]] | None,
               active: set[str]) -> tuple[np.ndarray, pd.DataFrame]:
    """Cut one grid into patches and build its metadata table."""
    patch, stride, res = int(cfg["patch_px"]), int(cfg["stride_px"]), float(cfg["resolution_m"])
    gdir = grids_dir()
    with rasterio.open(gdir / f"{source_id}_dem.tif") as src:
        dem = src.read(1).astype(np.float32)
        tfm, crs = src.transform, src.crs
    rows0 = window_origins(dem.shape[0], patch, stride)
    cols0 = window_origins(dem.shape[1], patch, stride)
    rr, cc = np.meshgrid(rows0, cols0, indexing="ij")
    rows, cols = rr.ravel(), cc.ravel()
    extra = crater_windows(source_id, tfm, crs, patch, dem.shape) if body == "earth" else []
    crater_ids = [""] * len(rows) + [c[0] for c in extra]
    rows = np.concatenate([rows, np.array([c[1] for c in extra], dtype=int)])
    cols = np.concatenate([cols, np.array([c[2] for c in extra], dtype=int)])

    finite = np.isfinite(dem)
    valid = np.array([finite[r:r + patch, c:c + patch].mean() for r, c in zip(rows, cols)])
    keep = valid >= float(cfg["min_valid_fraction"])
    rows, cols, valid = rows[keep], cols[keep], valid[keep]
    crater_ids = [cid for cid, k in zip(crater_ids, keep) if k]

    arrays = np.stack([dem[r:r + patch, c:c + patch] for r, c in zip(rows, cols)]) if len(rows) else \
        np.zeros((0, patch, patch), np.float32)
    x_m = tfm.c + (cols + patch / 2.0) * res
    y_m = tfm.f - (rows + patch / 2.0) * res
    lons, lats = warp_transform(crs, geographic_crs(body), list(x_m), list(y_m)) if len(rows) else ([], [])
    lons, lats = np.asarray(lons), np.asarray(lats)

    table = pd.DataFrame({
        "patch_id": [f"{source_id}:{r}:{c}" + (f":{cid}" if cid else "") for r, c, cid in zip(rows, cols, crater_ids)],
        "body": body, "source_id": source_id, "row": rows, "col": cols,
        "x_m": x_m, "y_m": y_m, "lat": lats, "lon": lons, "valid_fraction": valid,
        "crater_centre_of": crater_ids,
    })
    if body == "earth":
        wc_path = gdir / f"{source_id}_wc.tif"
        table["wc_available"] = wc_path.exists()
        if wc_path.exists():
            with rasterio.open(wc_path) as src:
                wc = src.read(1)
            for key, values in class_shares(wc, rows, cols, patch).items():
                table[key] = values
            table["wc_ok"] = landcover_ok(table, cfg)
        else:
            table["wc_ok"] = True
        table["dedupe_ok"] = dedupe_flags(source_id, lats, lons, boxes or {}, active)
    return arrays.astype(np.float32), table


def main() -> int:
    """Cut patches for every selected target and region."""
    cfg = load_config()
    out = patches_dir()
    sources: list[tuple[str, str]] = [(t["id"], t["body"]) for t in selected_targets(load_yaml("targets.yaml")["targets"])]
    regions = selected_regions(load_yaml("regions.yaml")["regions"])
    sources += [(r["id"], "earth") for r in regions]
    boxes = region_boxes()
    active = {r["id"] for r in regions}
    summary = []
    for source_id, body in sources:
        arrays, table = cut_source(source_id, body, cfg, boxes, active)
        if body == "earth":
            drop = ~table["dedupe_ok"]
            if drop.any():
                log.info("%s: dropping %d patches that belong to an overlapping region", source_id, int(drop.sum()))
            arrays, table = arrays[~drop.values], table[~drop].reset_index(drop=True)
        np.save(out / f"{source_id}.npy", arrays)
        table.to_parquet(out / f"{source_id}.parquet", index=False)
        n_mask = int(table["wc_ok"].sum()) if "wc_ok" in table else len(table)
        n_crater = int((table["crater_centre_of"] != "").sum())
        summary.append((source_id, body, len(table), n_mask, n_crater))
        log.info("%s (%s): %d patches, %d pass land-cover masks, %d crater-centred", source_id, body,
                 len(table), n_mask, n_crater)
    total = sum(s[2] for s in summary if s[1] == "earth")
    log.info("total: %d Earth patches, %d target patches", total, sum(s[2] for s in summary if s[1] != "earth"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
