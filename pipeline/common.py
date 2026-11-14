"""Shared helpers: configuration, paths, logging and source recording.

Every pipeline script imports this module. Paths depend on the active run
profile, chosen with the ``RG_PROFILE`` environment variable:

* ``full`` (default): the real run; exports go to ``web/public/data``.
* ``small``: the quick smoke run used by ``make pipeline-small``.
* ``res90``: the 90 m robustness rerun used by the validation step.

Raw downloads (``data/raw``) and API caches (``data/cache``) are shared by all
profiles, so a profile switch never re-downloads anything.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import logging
import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
SOURCES_MD = DATA_DIR / "SOURCES.md"
WEB_DATA_DIR = ROOT / "web" / "public" / "data"

PROFILES = ("full", "small", "res90")


def profile() -> str:
    """Return the active run profile name."""
    name = os.environ.get("RG_PROFILE", "full").strip() or "full"
    if name not in PROFILES:
        raise ValueError(f"RG_PROFILE must be one of {PROFILES}, got {name!r}")
    return name


def load_yaml(name: str) -> Any:
    """Load ``config/<name>`` as YAML."""
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_config() -> dict[str, Any]:
    """Load ``pipeline.yaml`` with the active profile's overrides applied."""
    cfg = load_yaml("pipeline.yaml")
    prof = profile()
    overrides = (cfg.get("profiles") or {}).get(prof, {})
    merged = copy.deepcopy(cfg)
    merged.update(overrides)
    merged["profile"] = prof
    return merged


def config_hash() -> str:
    """SHA-256 of the raw bytes of ``config/pipeline.yaml``."""
    return hashlib.sha256((CONFIG_DIR / "pipeline.yaml").read_bytes()).hexdigest()


def run_dir() -> Path:
    """Root folder for the active profile's intermediate outputs."""
    prof = profile()
    path = DATA_DIR if prof == "full" else DATA_DIR / prof
    path.mkdir(parents=True, exist_ok=True)
    return path


def grids_dir() -> Path:
    """Folder for rasters warped to the common metric grid."""
    path = run_dir() / "work" / "grids"
    path.mkdir(parents=True, exist_ok=True)
    return path


def patches_dir() -> Path:
    """Folder for patch arrays and patch metadata."""
    path = run_dir() / "patches"
    path.mkdir(parents=True, exist_ok=True)
    return path


def index_dir() -> Path:
    """Folder for scalers, PCA and search index files."""
    path = run_dir() / "work" / "index"
    path.mkdir(parents=True, exist_ok=True)
    return path


def results_dir() -> Path:
    """Folder for raw query results before export."""
    path = run_dir() / "work" / "results"
    path.mkdir(parents=True, exist_ok=True)
    return path


def export_dir() -> Path:
    """Folder the web app reads. Only the full profile writes to the site."""
    prof = profile()
    path = WEB_DATA_DIR if prof == "full" else run_dir() / "export"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logger(name: str) -> logging.Logger:
    """Return a logger with a single, consistent console format."""
    logging.basicConfig(
        level=os.environ.get("RG_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(name)


def selected_targets(all_targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter the target list to the active profile's selection."""
    cfg = load_config()
    if profile() == "small":
        wanted = set(cfg["small"]["targets"])
        return [t for t in all_targets if t["id"] in wanted]
    return [t for t in all_targets if t.get("enabled", True)]


def selected_regions(all_regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter the region list to the active profile's selection."""
    cfg = load_config()
    if profile() == "small":
        wanted = set(cfg["small"]["regions"])
        return [r for r in all_regions if r["id"] in wanted]
    return [r for r in all_regions if r.get("enabled", True)]


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string with seconds precision."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def record_source(
    *,
    url: str,
    dataset: str,
    licence: str,
    local_path: str | None = None,
    size_bytes: int | None = None,
    note: str = "",
) -> None:
    """Append one row to ``data/SOURCES.md`` unless the URL is already listed.

    The table records what was fetched, from where, when and under which
    licence, so every number in the app can be traced back to a file.
    """
    SOURCES_MD.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "| Dataset | URL | Downloaded (UTC) | Size | Licence | Local path | Note |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
    )
    if not SOURCES_MD.exists():
        SOURCES_MD.write_text("# Data sources\n\n", encoding="utf-8")
    text = SOURCES_MD.read_text(encoding="utf-8")
    if f"| {url} |" in text:
        return
    if "| Dataset | URL |" not in text:
        text = text.rstrip("\n") + "\n\n" + header
    size = f"{size_bytes / 1e6:.1f} MB" if size_bytes else "streamed"
    row = (
        f"| {dataset} | {url} | {now_iso()} | {size} | {licence} | "
        f"{local_path or '-'} | {note or '-'} |\n"
    )
    SOURCES_MD.write_text(text.rstrip("\n") + "\n" + row, encoding="utf-8")
