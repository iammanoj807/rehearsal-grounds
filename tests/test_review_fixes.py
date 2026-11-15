"""Tests for the land-cover mask, the novelty rule, the Antarctica line and the shared stretch."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from common import WORLDCOVER_VEG_BUILT, load_config  # noqa: E402
from render import hillshade_image, shade_array, shared_stretch  # noqa: E402

patches = importlib.import_module("04_patches")
environment = importlib.import_module("09_environment")
export = importlib.import_module("11_export")

CATALOGUE = [{"name": "Point A", "lat": 0.0, "lon": 0.0, "source_url": "https://example.org/a"}]


def _shares(**fracs: float) -> pd.DataFrame:
    """One-row table of WorldCover class shares; unspecified classes are 0."""
    row = {f"frac_{name}": 0.0 for name in patches.WORLDCOVER_CLASSES.values()}
    row.update({f"frac_{k}": v for k, v in fracs.items()})
    return pd.DataFrame([row])


def test_mask_counts_grass_shrub_and_moss_as_vegetation() -> None:
    cfg = load_config()
    assert set(WORLDCOVER_VEG_BUILT) == set(environment.VEG_CLASSES)
    for name in ("grass", "shrub", "moss_lichen", "wetland"):
        assert not patches.landcover_ok(_shares(**{name: 0.5, "bare": 0.5}), cfg).iloc[0], name
    assert patches.landcover_ok(_shares(bare=0.9, grass=0.1), cfg).iloc[0]


def test_mask_drops_mostly_snow_and_ice() -> None:
    cfg = load_config()
    assert not patches.landcover_ok(_shares(snow_ice=0.8, bare=0.2), cfg).iloc[0]
    assert patches.landcover_ok(_shares(snow_ice=0.3, bare=0.7), cfg).iloc[0]


def test_novelty_well_studied_region_or_close_to_catalogue() -> None:
    far = 1.0  # about 111 km from Point A
    near = environment.novelty(0.0, 0.2, CATALOGUE, 50.0, "discovery")
    assert near["status"] == "well_studied" and near["basis"] == "catalogue_distance"
    in_region = environment.novelty(far, 0.0, CATALOGUE, 50.0, "well_studied")
    assert in_region["status"] == "well_studied" and in_region["basis"] == "well_studied_region"
    outside = environment.novelty(far, 0.0, CATALOGUE, 50.0, "discovery")
    assert outside["status"] == "less_studied" and outside["basis"] is None


def test_antarctic_site_gets_no_landcover_line() -> None:
    row = pd.Series({
        **{f"sub_{g}": 90.0 for g in ("relief", "slope", "roughness", "shape", "embedding")},
        **{f"{p}_{k}": 1.0 for p in ("earth", "target")
           for k in ("relief_m", "slope_p50", "slope_p90", "rough_std_m", "tri_m", "bowl_index")},
        "earth_wc_available": False,
    })
    _, breaks, tests = export.explain(row, "moon", None, export.load_yaml("tests_suited.yaml")["rules"])
    assert export.NO_LANDCOVER_LINE in breaks
    assert not any("Rover mobility" in t for t in tests)  # needs bare ground, unknown here


def test_shared_stretch_keeps_brightness_comparable() -> None:
    x = np.indices((64, 64))[1].astype(float)
    gentle, steep = x * 6.0, x * 60.0  # 0.1 and 1.0 gradient on a 60 m grid
    rng = shared_stretch([shade_array(gentle, 60.0), shade_array(steep, 60.0)])
    a = np.asarray(hillshade_image(gentle, 60.0, stretch_range=rng).convert("L"))[:200, 100:]
    b = np.asarray(hillshade_image(steep, 60.0, stretch_range=rng).convert("L"))[:200, 100:]
    assert abs(float(a.mean()) - float(b.mean())) > 20  # different slopes stay different


def test_sparse_cover_counts_only_in_humid_climates() -> None:
    cfg = load_config()
    arid = _shares(grass=0.6, shrub=0.2, bare=0.2).assign(precip_mm_yr=300.0)
    humid = _shares(grass=0.6, shrub=0.2, bare=0.2).assign(precip_mm_yr=800.0)
    unknown = _shares(grass=0.6, shrub=0.2, bare=0.2)  # no precipitation value: treated as humid
    assert patches.landcover_ok(arid, cfg).iloc[0]
    assert not patches.landcover_ok(humid, cfg).iloc[0]
    assert not patches.landcover_ok(unknown, cfg).iloc[0]
    # Dense cover counts whatever the climate.
    for name in ("tree", "crop", "built", "wetland", "mangrove"):
        dry = _shares(**{name: 0.5, "bare": 0.5}).assign(precip_mm_yr=100.0)
        assert not patches.landcover_ok(dry, cfg).iloc[0], name


def test_display_window_has_the_same_footprint_as_the_60m_patch() -> None:
    from rasterio.transform import from_origin

    from display import display_transform

    grid60 = from_origin(500_000.0, 7_300_000.0, 60.0, 60.0)
    tf, n = display_transform(grid60, row=10, col=20, res60=60.0, patch60=64, res=30.0, margin_px=0)
    assert n == 128
    assert (tf.c, tf.f) == (500_000.0 + 20 * 60.0, 7_300_000.0 - 10 * 60.0)
    assert tf.a == 30.0 and tf.e == -30.0
    tf_m, n_m = display_transform(grid60, row=10, col=20, res60=60.0, patch60=64, res=30.0, margin_px=128)
    assert n_m == 384 and tf_m.c == tf.c - 3840.0 and tf_m.f == tf.f + 3840.0

