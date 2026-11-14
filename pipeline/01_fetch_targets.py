"""Step 01: download the Moon and Mars target terrain models.

Each target in ``config/targets.yaml`` points at one GeoTIFF on an official
server (NASA GSFC PGDA for the Moon, USGS Astrogeology for Mars). Files are
streamed to ``data/raw/targets/`` and skipped when a complete copy exists.
Every download is recorded in ``data/SOURCES.md``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

from common import RAW_DIR, get_logger, load_yaml, record_source, selected_targets

log = get_logger("01_fetch_targets")
TARGET_DIR = RAW_DIR / "targets"
CHUNK = 1 << 20


def remote_size(url: str) -> int | None:
    """Return the Content-Length of ``url`` or None if the server omits it."""
    resp = requests.head(url, allow_redirects=True, timeout=60)
    resp.raise_for_status()
    value = resp.headers.get("Content-Length")
    return int(value) if value else None


def download(url: str, dest: Path, retries: int = 3) -> int:
    """Stream ``url`` to ``dest`` atomically, retrying with backoff."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_content(CHUNK):
                        fh.write(chunk)
            tmp.replace(dest)
            return dest.stat().st_size
        except requests.RequestException as exc:
            log.warning("download failed (%s/%s) %s: %s", attempt, retries, url, exc)
            time.sleep(2**attempt)
    raise RuntimeError(f"could not download {url} after {retries} attempts")


def licence_for(target: dict) -> str:
    """Licence text for a target's source."""
    if target["body"] == "mars":
        return "CC0 (USGS Astrogeology); cite Fergason et al. 2020, doi:10.5066/P906QQT8"
    return "NASA open data; cite Barker et al. 2021, PSS 203, 105119"


def main() -> int:
    """Fetch every selected target; return a process exit code."""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    targets = selected_targets(load_yaml("targets.yaml")["targets"])
    failures: list[str] = []
    for target in targets:
        url = target["url"]
        dest = TARGET_DIR / Path(url).name
        try:
            expected = remote_size(url)
            if dest.exists() and (expected is None or dest.stat().st_size == expected):
                log.info("%s: already present (%.1f MB)", target["id"], dest.stat().st_size / 1e6)
                size = dest.stat().st_size
            else:
                log.info("%s: downloading %s", target["id"], url)
                size = download(url, dest)
                if expected is not None and size != expected:
                    raise RuntimeError(f"size mismatch: got {size}, expected {expected}")
                log.info("%s: saved %.1f MB", target["id"], size / 1e6)
            record_source(
                url=url,
                dataset=f"{'LOLA 5 m site DEM' if target['body'] == 'moon' else 'Mars 2020 TRN CTX DTM'} ({target['name']})",
                licence=licence_for(target),
                local_path=str(dest.relative_to(RAW_DIR.parent.parent)),
                size_bytes=size,
            )
        except Exception as exc:  # noqa: BLE001 - report every failure, then stop
            log.error("%s: FAILED: %s", target["id"], exc)
            failures.append(target["id"])
    if failures:
        log.error("failed targets: %s", ", ".join(failures))
        return 1
    log.info("fetched %d targets", len(targets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
