"""Sharper display images: 30 m windows cut from the original maps.

Every score uses the common 60 m grid. Only the pictures in the app are drawn from
finer data: for each exported 60 m patch this module cuts a window with exactly the
same footprint (and, for the low-Sun preview, the same 3.84 km of surroundings) at
``display_resolution_m`` straight from the original files (Copernicus GLO-30 for
Earth, the LOLA 5 m site maps for the Moon, the CTX 20 m DTM for Mars), in the 60 m
grid's own projection. Averaging is used, so finer sources are smoothed to 30 m.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling

from common import RAW_DIR, grids_dir, load_yaml, selected_targets


def display_transform(grid_transform: Any, row: int, col: int, res60: float, patch60: int, res: float,
                      margin_px: int) -> tuple[Any, int]:
    """Transform and size of a display window covering a 60 m patch plus a margin (in display pixels)."""
    x_left = grid_transform.c + col * res60
    y_top = grid_transform.f - row * res60
    n = int(round(patch60 * res60 / res))
    return from_origin(x_left - margin_px * res, y_top + margin_px * res, res, res), n + 2 * margin_px


class DisplayWindows:
    """Lazy reader of display windows for patches of any source (target or Earth region)."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.res = float(cfg["display_resolution_m"])
        self.res60 = float(cfg["resolution_m"])
        self.patch60 = int(cfg["patch_px"])
        self.patch = int(round(self.patch60 * self.res60 / self.res))
        self._raw = {t["id"]: RAW_DIR / "targets" / Path(t["url"]).name
                     for t in selected_targets(load_yaml("targets.yaml")["targets"])}
        self._grid: dict[str, tuple[Any, Any]] = {}
        self._cache: dict[tuple[str, int], np.ndarray] = {}

    def raw_path(self, source_id: str) -> Path:
        """Original file behind a source's 60 m grid."""
        return self._raw.get(source_id, RAW_DIR / "earth" / f"{source_id}_dem.tif")

    def grid(self, source_id: str) -> tuple[Any, Any]:
        """CRS and transform of a source's 60 m grid."""
        if source_id not in self._grid:
            with rasterio.open(grids_dir() / f"{source_id}_dem.tif") as g:
                self._grid[source_id] = (g.crs, g.transform)
        return self._grid[source_id]

    def window(self, patch_row: dict[str, Any], margin_px: int = 0) -> np.ndarray:
        """Elevation (float, NaN outside the source) of a patch at display resolution, plus a margin."""
        key = (str(patch_row["patch_id"]), margin_px)
        if key not in self._cache:
            crs, t60 = self.grid(patch_row["source_id"])
            tf, n = display_transform(t60, int(patch_row["row"]), int(patch_row["col"]), self.res60, self.patch60,
                                      self.res, margin_px)
            with rasterio.open(self.raw_path(patch_row["source_id"])) as src, \
                    WarpedVRT(src, crs=crs, transform=tf, width=n, height=n, resampling=Resampling.average) as vrt:
                a = vrt.read(1, masked=True)
            self._cache[key] = np.ma.filled(a.astype(np.float64), np.nan)
        return self._cache[key]
