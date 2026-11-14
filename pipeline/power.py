"""NASA POWER climatology client with an on-disk cache and retries."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import requests

API = "https://power.larc.nasa.gov/api/temporal/climatology/point"
PARAMETERS = ("T2M", "T2M_MAX", "T2M_MIN", "T2M_RANGE", "PRECTOTCORR", "RH2M", "ALLSKY_SFC_SW_DWN")
FILL = -999.0


class PowerError(RuntimeError):
    """Raised when the POWER API cannot be reached after all retries."""


def cache_key(lat: float, lon: float) -> str:
    """Cache file name for a point rounded to 0.01 degrees."""
    return f"{lat:+.2f}_{lon:+.2f}.json"


def fetch_climatology(lat: float, lon: float, cache_dir: Path, *, retries: int = 3, backoff_s: float = 2.0,
                      timeout_s: float = 60.0, get: Callable[..., Any] = requests.get,
                      sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Return the POWER climatology JSON for a point, using the cache when present.

    A network failure or HTTP error is retried ``retries`` times with
    exponential backoff; after that a :class:`PowerError` explains what failed.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / cache_key(lat, lon)
    if path.exists():
        return json.loads(path.read_text())
    params = {"parameters": ",".join(PARAMETERS), "community": "RE", "longitude": f"{lon:.2f}",
              "latitude": f"{lat:.2f}", "format": "JSON"}
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = get(API, params=params, timeout=timeout_s)
            resp.raise_for_status()
            data = resp.json()
            path.write_text(json.dumps(data))
            return data
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt < retries:
                sleep(backoff_s * 2 ** (attempt - 1))
    raise PowerError(f"NASA POWER request failed for ({lat:.2f}, {lon:.2f}) after {retries} attempts: {last}")


def annual_values(data: dict[str, Any]) -> dict[str, float | None]:
    """Annual ('ANN') value of every parameter, with fill values as None."""
    params = data["properties"]["parameter"]
    out: dict[str, float | None] = {}
    for name in PARAMETERS:
        value = params.get(name, {}).get("ANN")
        out[name] = None if value is None or value == FILL else float(value)
    return out
