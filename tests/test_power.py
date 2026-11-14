"""NASA POWER client: cache reuse and retry behaviour (no network)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from power import PowerError, annual_values, cache_key, fetch_climatology  # noqa: E402

SAMPLE = {"properties": {"parameter": {"T2M": {"ANN": 11.36}, "T2M_MIN": {"ANN": -999.0}}}}


class _Resp:
    def __init__(self, data: dict) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._data


def test_cached_response_is_reused(tmp_path: Path) -> None:
    (tmp_path / cache_key(35.03, -111.02)).write_text(json.dumps(SAMPLE))

    def no_network(*_a, **_k):
        raise AssertionError("network should not be called")

    assert fetch_climatology(35.03, -111.02, tmp_path, get=no_network) == SAMPLE


def test_timeout_retries_three_times_then_raises(tmp_path: Path) -> None:
    calls, sleeps = [], []

    def timeout(*_a, **_k):
        calls.append(1)
        raise requests.Timeout("timed out")

    with pytest.raises(PowerError, match="after 3 attempts"):
        fetch_climatology(1.0, 2.0, tmp_path, get=timeout, sleep=sleeps.append)
    assert len(calls) == 3
    assert sleeps == [2.0, 4.0]


def test_success_after_retry_is_cached(tmp_path: Path) -> None:
    state = {"n": 0}

    def flaky(*_a, **_k):
        state["n"] += 1
        if state["n"] == 1:
            raise requests.ConnectionError("reset")
        return _Resp(SAMPLE)

    assert fetch_climatology(1.0, 2.0, tmp_path, get=flaky, sleep=lambda _s: None) == SAMPLE
    assert (tmp_path / cache_key(1.0, 2.0)).exists()


def test_fill_values_become_none() -> None:
    ann = annual_values(SAMPLE)
    assert ann["T2M"] == pytest.approx(11.36)
    assert ann["T2M_MIN"] is None
