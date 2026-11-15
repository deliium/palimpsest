# mypy: ignore-errors
"""Byte-identical cascade output across hash seeds and sorted input."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from analysis.economic_cascades_analysis import (
    economic_cascades_analysis_digest,
    harvest_economic_cascades_analysis,
)
from tests.unit.test_economic_cascades_analysis import (
    _harvest_events,
    _recipes,
    _stage,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _analysis():
    return harvest_economic_cascades_analysis(
        events=_harvest_events(),
        recipe_specs=_recipes(),
        stages=[_stage(completions=1), _stage(completions=0, sequence=1)],
    )


def test_digest_is_order_independent() -> None:
    first = _analysis()
    second = harvest_economic_cascades_analysis(
        events=tuple(reversed(_harvest_events())),
        recipe_specs=_recipes(),
        stages=[_stage(completions=1), _stage(completions=0, sequence=1)],
    )
    assert economic_cascades_analysis_digest(first) == (
        economic_cascades_analysis_digest(second)
    )


def test_snapshot_bytes_match_across_hash_seeds() -> None:
    script = """
import json
from analysis.economic_cascades_analysis import harvest_economic_cascades_analysis
from experiments.economic_cascades_publication import compose_economic_cascades_snapshot
from simulation.economic_cascades_codec import encode_economic_cascades_snapshot
from unit.test_economic_cascades_analysis import _harvest_events, _recipes, _stage

analysis = harvest_economic_cascades_analysis(
    events=_harvest_events(),
    recipe_specs=_recipes(),
    stages=[_stage(completions=1), _stage(completions=0, sequence=1)],
)
snapshot = compose_economic_cascades_snapshot(analysis, run_id="run-1")
print(json.dumps({
    "digest": snapshot.internal_digest,
    "bytes": encode_economic_cascades_snapshot(snapshot).decode(),
}))
"""
    outputs = []
    for seed in ("0", "1"):
        env = dict(
            os.environ,
            PYTHONHASHSEED=seed,
            PYTHONPATH="src:tests",
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        outputs.append(json.loads(completed.stdout))
    assert outputs[0] == outputs[1]
