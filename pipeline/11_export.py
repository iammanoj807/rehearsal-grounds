"""Step 11: write the web app's static data contract and hillshade images.

Writes into ``web/public/data`` (or the profile's export folder):

* ``targets.json``, ``regions.json``, ``results/<target_id>.json``,
  ``sources.json`` and, when present, ``validation.json``;
* ``img/targets/<target_id>.png``: overview hillshade of each target;
* ``img/patches/<patch>.png``: 256 x 256 hillshades of every matched Earth
  patch and best-matching target patch, all at the same scale (3.84 km across,
  1 km scale bar, azimuth 315, altitude 45, contrast-stretched for display).

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
from render import hillshade_image
from schemas import Dataset, Environment, Images, Match, Novelty, Region, Results, Sources, SubScores, Target, Terrain

log = get_logger("11_export")

GROUP_TEXT: dict[str, tuple[str, list[tuple[str, str, str, int]]]] = {
    "relief": ("Relief", [("height range (5th-95th pct)", "relief_m", "m", 0)]),
    "slope": ("Slope", [("median", "slope_p50", "°", 1), ("90th percentile", "slope_p90", "°", 1)]),
    "roughness": ("Roughness", [("plane-fit spread", "rough_std_m", "m", 1), ("ruggedness index", "tri_m", "m", 1)]),
    "shape": ("Shape", [("bowl index (+ bowl, - dome)", "bowl_index", "", 2)]),
}
WEAK_BAR = 75.0
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


def explain(row: pd.Series, body: str, env: Environment | None, rules: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str]]:
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
        if env.vegetation_fraction is not None and env.vegetation_fraction > 0.005:
            breaks.append(f"Vegetation, cropland or buildings cover {100 * env.vegetation_fraction:.0f}% of the "
                          f"2 km surroundings (none on the {body_label})")
        if env.precip_mm_per_day is not None and env.precip_mm_per_day > 0:
            breaks.append(f"Rain and snow: {env.precip_mm_per_day:.2f} mm per day on average (NASA POWER)")
        if env.water_fraction is not None and env.water_fraction > 0.005:
            breaks.append(f"Open water covers {100 * env.water_fraction:.0f}% of the 2 km surroundings")
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
    cache: dict[str, np.ndarray] = {}
    res = float(cfg["resolution_m"])

    targets_out = []
    for target in selected_targets(load_yaml("targets.yaml")["targets"]):
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
                    save_png(hillshade_image(load_patch(pid, meta, cache), res), out / rel)
                images[kind] = rel
            env = env_for(row["site_id"], env_table)
            novelty = None
            if nov_table is not None and row["site_id"] in nov_table.index:
                n = nov_table.loc[row["site_id"]]
                novelty = Novelty(status=n["status"], nearest_known_analog=n["nearest_known_analog"],
                                  distance_km=float(n["distance_km"]), source_url=n["source_url"])
            strong, breaks, tests = explain(row, target["body"], env, rules)
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
            data_note=target.get("data_note"),
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
        ))
    (out / "targets.json").write_text(json.dumps([t.model_dump() for t in targets_out], indent=1))
    (out / "regions.json").write_text(json.dumps([r.model_dump() for r in regions_out], indent=1))
    (out / "sources.json").write_text(build_sources().model_dump_json(indent=1))
    validation = run_dir() / "validation.json"
    if validation.exists():
        shutil.copyfile(validation, out / "validation.json")
    meta_out = {"generated_at": now_iso(), "config_hash": config_hash(), "n_earth_patches": int((meta["body"] == "earth").sum()),
                "n_searchable": int(((meta["body"] == "earth") & meta["search_ok"]).sum()),
                "resolution_m": res, "patch_px": int(cfg["patch_px"]), "weights": cfg["weights"]}
    (out / "meta.json").write_text(json.dumps(meta_out, indent=1))
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    log.info("export complete: %d targets, %d regions, %.1f MB in %s", len(targets_out), len(regions_out), size / 1e6, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
