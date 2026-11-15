"""Step 11: write the web app's static data contract and hillshade images.

Writes into ``web/public/data`` (or the profile's export folder):

* ``targets.json``, ``regions.json``, ``results/<target_id>.json``,
  ``sources.json`` and, when present, ``validation.json``;
* ``img/targets/<target_id>.png``: overview hillshade of each target;
* ``img/patches/<patch>.png``: 256 x 256 hillshades of every matched Earth
  patch and best-matching target patch, all at the same scale (3.84 km across,
  1 km scale bar, azimuth 315, altitude 45). All patch images share one
  contrast stretch: the 1st-99th percentile of the hillshade over every
  exported patch, so brightness compares directly between the Moon or Mars
  patch and its Earth match. Target overview images keep a per-image stretch.

Every JSON file is validated against the Pydantic models in ``schemas.py``.
Environment and novelty fields are filled when step 09 has run.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from PIL import Image

from common import (SOURCES_MD, config_hash, export_dir, get_logger, grids_dir, load_config, load_yaml, now_iso,
                    patches_dir, results_dir, run_dir, selected_regions, selected_targets)
from display import DisplayWindows
from render import hillshade_image, shade_array, shared_stretch
from schemas import (ArtemisCoverage, Dataset, Environment, Images, Lighting, LightingInfo, Match, MonthCal, Novelty,
                     Region, Results, Sources, SubScores, SunBand, Target, Terrain, UsualSites)

log = get_logger("11_export")

GROUP_TEXT: dict[str, tuple[str, list[tuple[str, str, str, int]]]] = {
    "relief": ("Relief", [("height range (5th-95th pct)", "relief_m", "m", 0)]),
    "slope": ("Slope", [("median", "slope_p50", "°", 1), ("90th percentile", "slope_p90", "°", 1)]),
    "roughness": ("Roughness", [("plane-fit spread", "rough_std_m", "m", 1), ("ruggedness index", "tri_m", "m", 1)]),
    "shape": ("Shape", [("bowl index (+ bowl, - dome)", "bowl_index", "", 2)]),
}
WEAK_BAR = 75.0
NO_LANDCOVER_LINE = "No land-cover data south of 60°S: this patch may be glacier ice; check the imagery."
EARTH_LIMITS = {
    "moon": [
        "Gravity: Earth's is about six times the Moon's, so rovers, suits and loose soil behave differently.",
        "Vacuum: the Moon has no atmosphere; Earth's air carries heat, sound and dust in ways the Moon cannot.",
        "Radiation and light: Earth's atmosphere and magnetic field block most space radiation, and polar "
        "lighting with permanent shadows cannot be reproduced.",
    ],
    "mars": [
        "Gravity: Earth's is about 2.6 times that of Mars.",
        "Thin air: Mars' surface pressure is under 1% of Earth's and the air is mostly carbon dioxide.",
        "Radiation: Earth's atmosphere and magnetic field block most of the radiation that reaches Mars' surface.",
    ],
}


def safe_name(patch_id: str) -> str:
    """Filesystem-safe image name for a patch id."""
    return patch_id.replace(":", "_")


def load_patch(patch_id: str, meta: pd.DataFrame, cache: dict[str, np.ndarray]) -> np.ndarray:
    """Elevation array of one patch."""
    row = meta.loc[meta["patch_id"] == patch_id].iloc[0]
    sid = row["source_id"]
    if sid not in cache:
        cache[sid] = np.load(patches_dir() / f"{sid}.npy")
    local = meta.index[meta["source_id"] == sid].get_loc(row.name)
    return cache[sid][local]


def save_png(img: Image.Image, path: Path) -> None:
    """Save a greyscale optimised PNG."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("L").save(path, optimize=True)


def terrain_of(row: pd.Series, prefix: str) -> Terrain:  # noqa: D103
    """Terrain values of the Earth or target patch of a result row."""
    return Terrain(
        relief_m=row[f"{prefix}_relief_m"], slope_p50_deg=row[f"{prefix}_slope_p50"],
        slope_p90_deg=row[f"{prefix}_slope_p90"], rough_std_m=row[f"{prefix}_rough_std_m"],
        bowl_index=row[f"{prefix}_bowl_index"], tri_m=row[f"{prefix}_tri_m"],
        hypsometric_integral=row[f"{prefix}_hypsometric_integral"],
    )


def fmt(value: float, unit: str, digits: int) -> str:
    """Number with unit, e.g. '16.4°' or '330 m'."""
    space = " " if unit and unit not in ("°",) else ""
    return f"{value:.{digits}f}{space}{unit}"


def group_line(group: str, row: pd.Series, body_label: str) -> str:
    """'Slope (bar 89/100): median 9.1° here vs 12.0° on the Moon target; 90th percentile ...'."""
    label, parts = GROUP_TEXT[group]
    values = "; ".join(
        f"{name} {fmt(row[f'earth_{key}'], unit, digits)} here vs {fmt(row[f'target_{key}'], unit, digits)}"
        for name, key, unit, digits in parts
    )
    return f"{label} (bar {row[f'sub_{group}']:.0f}/100): {values} on the {body_label} target"


def vegetation_lines(env: Environment, body_label: str, humid_mm: float) -> list[str]:
    """Breaks-down lines for land cover, separating dense cover from dryland shrub and grass."""
    if env.dense_veg_fraction is None or env.sparse_veg_fraction is None:
        if env.vegetation_fraction is not None and env.vegetation_fraction > 0.005:
            return [f"Vegetation, cropland or buildings cover {100 * env.vegetation_fraction:.0f}% of the "
                    f"2 km surroundings (none on the {body_label})"]
        return []
    lines = []
    if env.dense_veg_fraction > 0.005:
        lines.append(f"Trees, crops, buildings or wetland cover {100 * env.dense_veg_fraction:.0f}% of the 2 km "
                     f"surroundings (none on the {body_label})")
    if env.sparse_veg_fraction > 0.005:
        annual = env.precip_mm_per_day * 365.25 if env.precip_mm_per_day is not None else None
        if annual is not None and annual <= humid_mm:
            lines.append(f"WorldCover labels {100 * env.sparse_veg_fraction:.0f}% of the 2 km surroundings as shrub, "
                         f"grass or moss; with about {annual:.0f} mm of rain a year this is sparse dryland cover "
                         f"(none on the {body_label})")
        else:
            lines.append(f"Shrub, grass or moss cover {100 * env.sparse_veg_fraction:.0f}% of the 2 km surroundings "
                         f"(none on the {body_label})")
    return lines


def explain(row: pd.Series, body: str, env: Environment | None, rules: list[dict[str, Any]],
            humid_mm: float = 500.0) -> tuple[list[str], list[str], list[str]]:
    """Strong-match, breaks-down and tests-suited lines for one site."""
    body_label = "Moon" if body == "moon" else "Mars"
    groups = sorted(GROUP_TEXT, key=lambda g: row[f"sub_{g}"], reverse=True)
    strong = [group_line(g, row, body_label) for g in groups[:2]]
    if row["sub_embedding"] >= 90:
        strong.append(f"Image embedding: the shaded-relief texture is closer than {row['sub_embedding']:.0f}% "
                      "of random Earth patch pairs")
    weakest = groups[-1]
    if row[f"sub_{weakest}"] < WEAK_BAR:
        breaks = ["Weakest terrain match. " + group_line(weakest, row, body_label)]
    else:
        breaks = [f"All four terrain groups score at least {WEAK_BAR:.0f}/100; the weakest is "
                  f"{GROUP_TEXT[weakest][0].lower()} ({row[f'sub_{weakest}']:.0f}/100)"]
    if row["sub_embedding"] < WEAK_BAR:
        breaks.append(f"Image embedding bar {row['sub_embedding']:.0f}/100: the shaded relief looks less alike "
                      "than the terrain numbers suggest")
    if env is not None:
        breaks.extend(vegetation_lines(env, body_label, humid_mm))
        if env.precip_mm_per_day is not None and env.precip_mm_per_day > 0:
            breaks.append(f"Rain and snow: {env.precip_mm_per_day:.2f} mm per day on average (NASA POWER)")
        if env.water_fraction is not None and env.water_fraction > 0.005:
            breaks.append(f"Open water covers {100 * env.water_fraction:.0f}% of the 2 km surroundings")
    if not bool(row.get("earth_wc_available", True)):
        breaks.append(NO_LANDCOVER_LINE)
    breaks.extend(EARTH_LIMITS[body])

    tests = []
    terrain = {"slope_p90_deg": row["earth_slope_p90"], "relief_m": row["earth_relief_m"]}
    env_vals = env.model_dump() if env is not None else {}
    for rule in rules:
        ok = all(row[f"sub_{k}"] >= v for k, v in (rule.get("min_sub_scores") or {}).items())
        ok &= all(terrain.get(k, -np.inf) >= v for k, v in (rule.get("min_terrain") or {}).items())
        for k, v in (rule.get("max_environment") or {}).items():
            ok &= env_vals.get(k) is not None and env_vals[k] <= v
        for k, v in (rule.get("min_environment") or {}).items():
            ok &= env_vals.get(k) is not None and env_vals[k] >= v
        if ok:
            tests.append(rule["text"])
    return strong, breaks, tests


def target_overview(target: dict[str, Any], out: Path) -> tuple[str, dict[str, float]]:
    """Render the full target hillshade; return its path and extent info."""
    with rasterio.open(grids_dir() / f"{target['id']}_dem.tif") as src:
        z = src.read(1).astype(np.float32)
        res = src.res[0]
    img = hillshade_image(z, res, scale_bar_m=5000.0)
    rel = f"img/targets/{target['id']}.png"
    save_png(img, out / rel)
    return rel, {"extent_km": round(max(z.shape) * res / 1000.0, 2)}


def dataset_dates() -> dict[str, str]:
    """Earliest download timestamp per URL fragment, from data/SOURCES.md."""
    dates: dict[str, str] = {}
    for line in SOURCES_MD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[1].startswith("http"):
            dates.setdefault(cells[1], cells[2])
    return dates


def build_sources() -> Sources:
    """sources.json from config/datasets.yaml plus download dates."""
    dates = dataset_dates()
    datasets = []
    for d in load_yaml("datasets.yaml")["datasets"]:
        hits = sorted(v for k, v in dates.items() if d.get("sources_match", "@@") in k)
        fields = {k: v for k, v in d.items() if k != "sources_match"}
        datasets.append(Dataset(**fields, downloaded=hits[0] if hits else None))
    return Sources(generated_at=now_iso(), datasets=datasets)


def load_environment() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Environment and novelty tables written by step 09, if present."""
    env_path = results_dir() / "environment.parquet"
    nov_path = results_dir() / "novelty.parquet"
    env = pd.read_parquet(env_path).set_index("site_id") if env_path.exists() else None
    nov = pd.read_parquet(nov_path).set_index("site_id") if nov_path.exists() else None
    return env, nov


def env_for(site_id: str, env: pd.DataFrame | None) -> Environment | None:
    """Environment model for one site, or None."""
    if env is None or site_id not in env.index:
        return None
    rec = env.loc[site_id].to_dict()
    clean = {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in rec.items()
             if k in Environment.model_fields}
    return Environment(**clean)


LIGHTING_LIMITS = [
    "Shadows are computed on the 60 m grid, so boulders, small craters and short slopes cast no shadow here.",
    "The LOLA site maps are largely interpolated between laser tracks, so fine relief in the target is smoothed.",
    "No atmospheric scattering, no regolith or rock reflectance and no Earthshine: a pixel is either lit or in shadow.",
    "Cast shadows only see 3.84 km of terrain around each patch; sites marked edge-limited see less.",
    "Earth Sun hours use the true Sun position on the 15th of each month and ignore clouds and local horizons.",
]


def load_lighting() -> dict[str, Any] | None:
    """Step 09b output, if present."""
    path = results_dir() / "lighting.json"
    return json.loads(path.read_text()) if path.exists() else None


def lowsun_arrays(lighting: dict[str, Any] | None, meta: pd.DataFrame, dw: DisplayWindows | None,
                  cfg: dict[str, Any]) -> dict[str, np.ndarray]:
    """Low-Sun previews (cast shadows black) for every exported Moon-target site and its target patch.

    Drawn at the display resolution from the original maps, with 3.84 km of surroundings,
    the Sun at the middle of the target's band and the hillshade azimuth. Falls back to the
    60 m arrays written by step 09b when no display resolution is configured.
    """
    if not lighting:
        return {}
    if dw is None:
        return {f.stem.removeprefix("lowsun_"): np.load(f) for f in (run_dir() / "lighting").glob("lowsun_*.npy")}
    from lighting import R_EARTH_M, R_MOON_M, cast_shadow_mask  # noqa: PLC0415
    from features import hillshade  # noqa: PLC0415

    az = float(load_yaml("lighting.yaml")["preview_azimuth_deg"])
    rows = meta.set_index("patch_id", drop=False)
    out: dict[str, np.ndarray] = {}
    for tid, sites in lighting.get("sites", {}).items():
        band = lighting["targets"].get(tid, {})
        if not band.get("applicable"):
            continue
        elev = float(band["preview_elevation_deg"])
        res_df = pd.read_parquet(results_dir() / f"{tid}.parquet")
        for r in res_df.itertuples():
            if r.site_id not in sites or "lighting" not in sites[r.site_id]:
                continue
            for pid, radius in ((r.site_id, R_EARTH_M), (r.target_patch_id, R_MOON_M)):
                key = safe_name(pid)
                if key in out:
                    continue
                window = dw.window(rows.loc[pid].to_dict(), dw.patch)
                filled = np.where(np.isfinite(window), window, np.nanmedian(window))
                core = filled[dw.patch:2 * dw.patch, dw.patch:2 * dw.patch]
                shade = hillshade(core, dw.res, azimuth_deg=az, altitude_deg=elev)
                dark = cast_shadow_mask(window, dw.res, radius, dw.patch, dw.patch, az, elev)
                out[key] = np.where(dark, 0.0, shade).astype(np.float32)
    return out


def lowsun_stretch(arrays: dict[str, np.ndarray]) -> tuple[float, float] | None:
    """One shared 1st-99th percentile stretch over every low-sun preview array."""
    if not arrays:
        return None
    lo, hi = np.percentile(np.concatenate([a.ravel() for a in arrays.values()]), [1, 99])
    return float(lo), float(max(hi, lo + 1e-6))


def lowsun_png(pid: str, arrays: dict[str, np.ndarray], stretch: tuple[float, float], out: Path) -> str | None:
    """Render one low-sun preview with the shared stretch and a 1 km scale bar."""
    a0 = arrays.get(safe_name(pid))
    if a0 is None:
        return None
    rel = f"img/lowsun/{safe_name(pid)}.png"
    if not (out / rel).exists():
        from render import OUT_PX, ImageDraw, ImageFont  # noqa: PLC0415
        lo, hi = stretch
        a = np.clip((a0 - lo) / (hi - lo), 0.0, 1.0)
        img = Image.fromarray(np.uint8(np.round(a * 255)), mode="L").resize((OUT_PX, OUT_PX), Image.BILINEAR).convert("RGB")
        draw = ImageDraw.Draw(img)
        bar = int(round(1000.0 / (3840.0 / OUT_PX)))
        x0, y0 = 10, OUT_PX - 14
        draw.rectangle([x0 - 4, y0 - 16, x0 + bar + 6, y0 + 7], fill=(255, 255, 255))
        draw.rectangle([x0, y0, x0 + bar, y0 + 3], fill=(20, 20, 20))
        try:
            font = ImageFont.load_default(size=12)
        except TypeError:
            font = ImageFont.load_default()
        draw.text((x0, y0 - 15), "1 km", fill=(20, 20, 20), font=font)
        save_png(img, out / rel)
    return rel


def main() -> int:
    """Export the full data contract for the web app."""
    cfg = load_config()
    out = export_dir()
    for sub in ("results", "img"):
        shutil.rmtree(out / sub, ignore_errors=True)
    meta = pd.read_parquet(run_dir() / "features.parquet")
    summary = json.loads((results_dir() / "summary.json").read_text())
    regions_cfg = {r["id"]: r for r in load_yaml("regions.yaml")["regions"]}
    rules = load_yaml("tests_suited.yaml")["rules"]
    env_table, nov_table = load_environment()
    lighting = load_lighting()
    cache: dict[str, np.ndarray] = {}
    res = float(cfg["resolution_m"])
    # Pictures only: drawn from the original maps at display_resolution_m when configured.
    dw = DisplayWindows(cfg) if cfg.get("display_resolution_m") else None
    dres = dw.res if dw else res
    rows_by_id = meta.set_index("patch_id", drop=False)

    def display_patch(pid: str) -> np.ndarray:
        return dw.window(rows_by_id.loc[pid].to_dict()) if dw else load_patch(pid, meta, cache)

    larrays = lowsun_arrays(lighting, meta, dw, cfg)
    lstretch = lowsun_stretch(larrays)

    # One shared contrast stretch over every patch image that will be exported.
    all_targets = selected_targets(load_yaml("targets.yaml")["targets"])
    patch_ids: list[str] = []
    for target in all_targets:
        s = pd.read_parquet(results_dir() / f"{target['id']}.parquet")
        patch_ids += list(s["site_id"]) + list(s["target_patch_id"])
    patch_ids = list(dict.fromkeys(patch_ids))
    stretch = shared_stretch([shade_array(display_patch(pid), dres) for pid in patch_ids])
    log.info("shared hillshade stretch over %d patches: %.3f-%.3f", len(patch_ids), *stretch)

    targets_out = []
    for target in all_targets:
        tid = target["id"]
        sites = pd.read_parquet(results_dir() / f"{tid}.parquet")
        tsum = summary["targets"][tid]
        overview, extent = target_overview(target, out)
        tmeta = meta[meta["source_id"] == tid]
        matches = []
        for _, row in sites.iterrows():
            images = {}
            for kind, pid in (("earth_hillshade", row["site_id"]), ("target_hillshade", row["target_patch_id"])):
                rel = f"img/patches/{safe_name(pid)}.png"
                if not (out / rel).exists():
                    save_png(hillshade_image(display_patch(pid), dres, stretch_range=stretch), out / rel)
                images[kind] = rel
            env = env_for(row["site_id"], env_table)
            novelty = None
            if nov_table is not None and row["site_id"] in nov_table.index:
                n = nov_table.loc[row["site_id"]]
                basis = n.get("basis")
                novelty = Novelty(status=n["status"], basis=basis if isinstance(basis, str) else None,
                                  nearest_known_analog=n["nearest_known_analog"],
                                  distance_km=float(n["distance_km"]), source_url=n["source_url"])
            strong, breaks, tests = explain(row, target["body"], env, rules, float(cfg["mask_sparse_veg_humid_mm"]))
            lrec = (lighting or {}).get("sites", {}).get(tid, {}).get(row["site_id"], {})
            if lstretch and lrec.get("lighting"):
                images["lowsun_earth"] = lowsun_png(row["site_id"], larrays, lstretch, out)
                images["lowsun_target"] = lowsun_png(row["target_patch_id"], larrays, lstretch, out)
            region = regions_cfg[row["region_id"]]
            matches.append(Match(
                rank=int(row["rank"]), site_id=row["site_id"], region_id=row["region_id"],
                region_name=region["name"], region_set=region["set"], lat=row["lat"], lon=row["lon"],
                score=row["score"], best_pair_score=row["best_pair_score"], s_morph=row["s_morph"],
                s_embed=row["s_embed"],
                sub_scores=SubScores(**{k: row[f"sub_{k}"] for k in SubScores.model_fields}),
                terrain=terrain_of(row, "earth"), target_terrain=terrain_of(row, "target"),
                target_patch_id=row["target_patch_id"], environment=env, novelty=novelty,
                strong_match=strong, breaks_down=breaks, tests_suited=tests, images=Images(**images),
                lighting=Lighting(**lrec["lighting"]) if lrec.get("lighting") else None,
                calendar=[MonthCal(**c) for c in lrec["calendar"]] if lrec.get("calendar") else None,
                best_months=lrec.get("best_months"), best_months_rule=lrec.get("best_months_rule"),
            ))
        results = Results(target_id=tid, generated_at=summary["generated_at"], config_hash=summary["config_hash"],
                          sigma=tsum["sigma"], n_candidates=tsum["n_candidates"],
                          n_target_patches=tsum["n_target_patches"], target_coverage=tsum["coverage"],
                          matches=matches)
        (out / "results").mkdir(parents=True, exist_ok=True)
        (out / "results" / f"{tid}.json").write_text(results.model_dump_json(indent=1))
        targets_out.append(Target(
            id=tid, name=target["name"], body=target["body"], description=" ".join(target["description"].split()),
            description_source_url=target["description_source_url"], source_url=target["product_url"],
            data_url=target["url"], citation=target["citation"], resolution_m=res, n_patches=len(tmeta),
            centre_lat=float(tmeta["lat"].mean()), centre_lon=float(tmeta["lon"].mean()),
            extent_km=extent["extent_km"], sigma=tsum["sigma"], n_sites=len(matches), hillshade_png=overview,
            data_note=target.get("data_note"), artemis_iii_region=target.get("artemis_iii_region"),
            sun_band=SunBand(**{k: v for k, v in (lighting or {}).get("targets", {}).get(tid, {}).items()
                                if k != "applicable"}) if (lighting or {}).get("targets", {}).get(tid, {}).get("applicable") else None,
        ))
        log.info("%s: exported %d matches", tid, len(matches))

    regions_out = []
    for region in selected_regions(load_yaml("regions.yaml")["regions"]):
        rmeta = meta[meta["source_id"] == region["id"]]
        regions_out.append(Region(
            id=region["id"], name=region["name"], country=region["country"], set=region["set"],
            lat=region["lat"], lon=region["lon"], source_url=region["source_url"], note=region.get("note"),
            n_patches=len(rmeta), n_searchable=int(rmeta["search_ok"].sum()),
            worldcover_available=bool(rmeta["wc_available"].iloc[0]) if len(rmeta) else False,
            before_you_go=[{"text": " ".join(n["text"].split()), "source_url": n["source_url"]}
                           for n in region.get("before_you_go", [])] or None,
        ))
    (out / "targets.json").write_text(json.dumps([t.model_dump() for t in targets_out], indent=1))
    (out / "regions.json").write_text(json.dumps([r.model_dump() for r in regions_out], indent=1))
    (out / "sources.json").write_text(build_sources().model_dump_json(indent=1))
    art = load_yaml("targets.yaml")["artemis_iii"]
    covered = sorted({t.artemis_iii_region for t in targets_out if t.artemis_iii_region},
                     key=art["regions"].index)
    (out / "artemis.json").write_text(ArtemisCoverage(
        source_url=art["source_url"], release_date=str(art["release_date"]), regions=art["regions"], covered=covered,
        n_regions=len(art["regions"]), n_covered=len(covered)).model_dump_json(indent=1))
    if lighting:
        lcfg = load_yaml("lighting.yaml")
        (out / "lighting_info.json").write_text(LightingInfo(
            checks=lighting["checks"], settings=lighting["settings"], rules=lighting["rules"], limits=LIGHTING_LIMITS,
            refraction_note=" ".join(lcfg["refraction_note"].split()),
            refraction_source_url=lcfg["refraction_source_url"]).model_dump_json(indent=1))
    usual = results_dir() / "usual_sites.json"
    if usual.exists():
        doc = UsualSites.model_validate_json(usual.read_text())
        (out / "usual_sites.json").write_text(doc.model_dump_json(indent=1))
    validation = run_dir() / "validation.json"
    if validation.exists():
        shutil.copyfile(validation, out / "validation.json")
    meta_out = {"generated_at": now_iso(), "config_hash": config_hash(), "n_earth_patches": int((meta["body"] == "earth").sum()),
                "n_searchable": int(((meta["body"] == "earth") & meta["search_ok"]).sum()),
                "resolution_m": res, "patch_px": int(cfg["patch_px"]), "weights": cfg["weights"],
                "hillshade_stretch": [round(stretch[0], 4), round(stretch[1], 4)]}
    (out / "meta.json").write_text(json.dumps(meta_out, indent=1))
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    log.info("export complete: %d targets, %d regions, %.1f MB in %s", len(targets_out), len(regions_out), size / 1e6, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
