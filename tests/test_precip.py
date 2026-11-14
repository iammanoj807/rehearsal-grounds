"""Tests for the NASA POWER regional precipitation helper."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import precip  # noqa: E402


def _feature(lon: float, lat: float, ann: float) -> dict:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat, 0.0]},
            "properties": {"parameter": {"PRECTOTCORR": {"ANN": ann}}}}


def test_request_box_is_at_least_two_degrees_and_centred() -> None:
    w, s, e, n = precip.request_box([118.52, -21.45, 119.48, -20.55])
    assert 2.0 < e - w < 2.1 and 2.0 < n - s < 2.1
    assert (w + e) / 2 == pytest.approx(119.0, abs=1e-3) and (s + n) / 2 == pytest.approx(-21.0, abs=1e-3)
    big = precip.request_box([0.0, 0.0, 3.0, 3.0])
    assert big == (0.0, 0.0, 3.0, 3.0)


def test_grid_cells_convert_to_mm_per_year_and_drop_fill() -> None:
    data = {"features": [_feature(10.0, 20.0, 1.0), _feature(10.625, 20.0, -999.0)]}
    cells = precip.grid_cells(data)
    assert cells.shape == (1, 3)
    assert cells[0, 2] == pytest.approx(365.25)


def test_nearest_cell_is_chosen() -> None:
    cells = np.array([[10.0, 20.0, 100.0], [10.625, 20.0, 900.0], [10.0, 20.5, 400.0]])
    got = precip.nearest_annual_mm(np.array([20.05, 20.45, 20.0]), np.array([10.1, 10.0, 10.5]), cells)
    assert list(got) == [100.0, 400.0, 900.0]


def test_regional_response_is_cached(tmp_path: Path) -> None:
    calls = []

    class Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"features": [_feature(1.0, 1.0, 2.0)]}

    def fake_get(url: str, params: dict, timeout: float) -> Resp:
        calls.append(params)
        return Resp()

    first = precip.fetch_regional("r1", [0.5, 0.5, 1.5, 1.5], tmp_path, get=fake_get)
    second = precip.fetch_regional("r1", [0.5, 0.5, 1.5, 1.5], tmp_path, get=fake_get)
    assert first == second and len(calls) == 1
    assert float(calls[0]["latitude-max"]) - float(calls[0]["latitude-min"]) >= 2.0
    assert json.loads((tmp_path / "r1.json").read_text()) == first
