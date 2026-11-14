"""Tests for the suggested-months rule (step 09b) and the usual-sites ranking (step 08b)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

lighting_step = importlib.import_module("09b_lighting")
usual = importlib.import_module("08b_usual_sites")
RULES = {"max_precip_mm_per_day": 1.0, "n_best_months": 3, "min_t2m_min_c": -25.0, "max_t2m_max_c": 35.0}


def _cal(low: list[float], rain: list[float], tmax: list[float] | None = None) -> list[dict]:
    hot = tmax or [20.0] * 12
    return [{"month": i + 1, "low_sun_h": low[i], "daylight_h": 12.0, "precip_mm_per_day": rain[i],
             "t2m_min_c": 0.0, "t2m_max_c": hot[i]} for i in range(12)]


def test_best_months_prefer_dry_months_with_most_low_sun() -> None:
    low = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    rain = [0.1] * 6 + [3.0] * 6  # only Jan-Jun are dry enough
    months, rule = lighting_step.best_months(_cal(low, rain), RULES, "low_sun_h")
    assert months == [4, 5, 6]
    assert "at most 1 mm" in rule and "low-sun hours" in rule


def test_best_months_fall_back_when_no_month_is_dry() -> None:
    months, rule = lighting_step.best_months(_cal([1.0] * 11 + [9.0], [5.0] * 12), RULES, "low_sun_h")
    assert 12 in months and len(months) == 3
    assert "no month" in rule


def test_best_months_skip_months_outside_the_temperature_band() -> None:
    low = [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    months, rule = lighting_step.best_months(_cal(low, [0.1] * 12, [45.0] * 3 + [20.0] * 9), RULES, "low_sun_h")
    assert months == [4, 5, 6]  # Jan-Mar are too hot
    assert "high at most 35" in rule


def test_rank_of_counts_strictly_better_scores() -> None:
    scores = np.array([90.0, 80.0, 80.0, 70.0])
    assert usual.rank_of(90.0, scores) == 1
    assert usual.rank_of(80.0, scores) == 2
    assert usual.rank_of(70.0, scores) == 4
