"""Tests for configuration loading and run profiles."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import common  # noqa: E402


def test_config_has_spec_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RG_PROFILE", raising=False)
    cfg = common.load_config()
    assert cfg["resolution_m"] == 60
    assert cfg["patch_px"] == 64
    assert cfg["stride_px"] == 32
    assert cfg["weights"] == {"morph": 0.6, "embed": 0.4}
    assert cfg["seed"] == 42


def test_res90_profile_keeps_window_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RG_PROFILE", "res90")
    cfg = common.load_config()
    assert cfg["resolution_m"] == 90
    window_m = cfg["patch_px"] * cfg["resolution_m"]
    assert abs(window_m - 3840) <= 90


def test_bad_profile_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RG_PROFILE", "nope")
    with pytest.raises(ValueError):
        common.profile()


def test_config_hash_is_stable() -> None:
    assert common.config_hash() == common.config_hash()
    assert len(common.config_hash()) == 64
