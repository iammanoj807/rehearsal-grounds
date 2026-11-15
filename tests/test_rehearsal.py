"""Tests for the suggested-months rule (step 09b) and the usual-sites ranking (step 08b)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

lighting_step = importlib.import_module("09b_lighting")
usual = importlib.import_module("08b_usual_sites")
RULES = {"max_precip_mm_per_day": 1.0, "n_best_months": 3, "min_t2m_min_c": -25.0, "max_t2m_max_c": 35.0,
         "min_gain_min": 10.0}


def _cal(low_min: list[float], rain: list[float], tmax: list[float] | None = None,
         tmin: list[float] | None = None) -> list[dict]:
    hot = tmax or [20.0] * 12
    cold = tmin or [0.0] * 12
    return [{"month": i + 1, "low_sun_h": low_min[i] / 60.0, "daylight_h": 12.0, "precip_mm_per_day": rain[i],
             "t2m_min_avg_c": cold[i], "t2m_max_avg_c": hot[i]} for i in range(12)]


def test_suggests_only_clearly_better_eligible_months() -> None:
    low = [40, 40, 40, 40, 40, 40, 70, 75, 80, 40, 40, 40]
    months, rule = lighting_step.best_months(_cal(low, [0.1] * 12), RULES, "low_sun_h")
    assert months == [7, 8, 9]
    assert "BOTH" not in rule and "at least 10 more minutes" in rule


def test_needs_both_rain_and_temperature() -> None:
    # Dry months are all too hot; cool months are all wet: nothing passes both, and there is no fallback.
    rain = [0.1] * 6 + [3.0] * 6
    tmax = [40.0] * 6 + [20.0] * 6
    months, rule = lighting_step.best_months(_cal([60] * 12, rain, tmax), RULES, "low_sun_h")
    assert months == [] and "No month passes our rules" in rule and "too cold or too hot" in rule


def test_too_wet_and_too_cold_reasons() -> None:
    months, rule = lighting_step.best_months(_cal([60] * 12, [5.0] * 12, tmin=[-40.0] * 12), RULES, "low_sun_h")
    assert months == [] and "too wet" in rule and "too cold" in rule


def test_flat_low_sun_year_gets_no_suggestion() -> None:
    low = [50, 52, 54, 53, 51, 50, 52, 55, 56, 54, 52, 50]
    months, rule = lighting_step.best_months(_cal(low, [0.1] * 12), RULES, "low_sun_h")
    assert months == [] and rule.startswith("No suggested month: low-sun time is about 52 min a day all year")


def test_flat_message_names_the_eligible_months_when_not_all_year() -> None:
    low = [0, 300, 200, 300, 0, 0, 0, 0, 100, 120, 0, 0]
    tmin = [-10.0] + [-40.0] * 10 + [-12.0]  # only Jan and Dec are warm enough
    months, rule = lighting_step.best_months(_cal(low, [0.1] * 12, tmin=tmin), RULES, "low_sun_h")
    assert months == [] and "(Jan, Dec)" in rule and "all year" not in rule


def test_rank_of_counts_strictly_better_scores() -> None:
    scores = np.array([90.0, 80.0, 80.0, 70.0])
    assert usual.rank_of(90.0, scores) == 1
    assert usual.rank_of(80.0, scores) == 2
    assert usual.rank_of(70.0, scores) == 4
