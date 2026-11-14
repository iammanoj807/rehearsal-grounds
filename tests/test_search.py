"""Search tests: self-match, non-maximum suppression and exported schemas."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import schemas  # noqa: E402
from grids import haversine_km  # noqa: E402
from scoring import GROUPS, Index, combine, group_columns, percentile_score, score_block  # noqa: E402

query = importlib.import_module("08_query")


def _toy_index(n: int = 40, seed: int = 42) -> Index:
    rng = np.random.default_rng(seed)
    from features import FEATURE_NAMES

    feats = rng.normal(size=(n, len(FEATURE_NAMES)))
    emb = rng.normal(size=(n, 64))
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    meta = pd.DataFrame({"patch_id": [f"p{i}" for i in range(n)], "source_id": "toy"})
    quant = {g: np.linspace(0, 5, 1001) for g in (*GROUPS, "embedding", "morph")}
    return Index(meta=meta, feats=feats, emb=emb, rot={}, group_cols=group_columns(), sigma=0.5,
                 quantiles=quant, weights={"morph": 0.6, "embed": 0.4})


def test_identical_pair_scores_100() -> None:
    assert combine(np.array([0.0]), np.array([1.0]), 0.3, {"morph": 0.6, "embed": 0.4})[0] == pytest.approx(100.0)


def test_patch_scored_against_itself_is_100_and_top() -> None:
    index = _toy_index()
    rows = np.arange(len(index.feats))
    res = score_block(index, rows[:5], rows)
    for i in range(5):
        assert res["S"][i, i] == pytest.approx(100.0, abs=1e-9)
        assert int(np.argmax(res["S"][i])) == i


def test_rotated_embedding_takes_best_rotation() -> None:
    index = _toy_index()
    rows = np.arange(len(index.feats))
    other = index.emb[7]
    index.rot[0] = np.stack([index.emb[0], other, index.emb[1], index.emb[2]])
    res = score_block(index, np.array([0]), rows)
    assert res["cos"][0, 7] == pytest.approx(1.0)


def test_nms_keeps_sites_apart() -> None:
    rng = np.random.default_rng(42)
    lats = 20 + rng.uniform(0, 0.5, 300)
    lons = 30 + rng.uniform(0, 0.5, 300)
    order = np.argsort(-rng.uniform(size=300))
    kept = query.nms(lats, lons, order, 10.0, 50)
    assert kept[0] == order[0]
    for a in kept:
        for b in kept:
            if a != b:
                assert haversine_km(lats[a], lons[a], lats[b], lons[b]) >= 10.0


def test_percentile_score_bounds() -> None:
    q = np.linspace(0, 1, 101)
    assert percentile_score(np.array([0.0]), q)[0] == pytest.approx(100.0)
    assert percentile_score(np.array([2.0]), q)[0] == pytest.approx(0.0)
    assert 40 < percentile_score(np.array([0.5]), q)[0] < 60


EXPORT = ROOT / "web" / "public" / "data"


@pytest.mark.skipif(not (EXPORT / "targets.json").exists(), reason="no export yet")
def test_exported_files_match_schemas() -> None:
    targets = [schemas.Target(**t) for t in json.loads((EXPORT / "targets.json").read_text())]
    assert len(targets) >= 3
    for t in targets:
        res = schemas.Results(**json.loads((EXPORT / "results" / f"{t.id}.json").read_text()))
        assert res.matches, t.id
        assert all((EXPORT / m.images.earth_hillshade).exists() for m in res.matches)
        ranks = [m.rank for m in res.matches]
        assert ranks == sorted(ranks)
    [schemas.Region(**r) for r in json.loads((EXPORT / "regions.json").read_text())]
    schemas.Sources(**json.loads((EXPORT / "sources.json").read_text()))
