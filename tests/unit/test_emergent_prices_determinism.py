"""Byte-level determinism across hash seeds and shuffled event order."""

# mypy: ignore-errors


from __future__ import annotations

import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from analysis.emergent_prices_analysis import (
    emergent_prices_analysis_digest,
    harvest_emergent_prices_analysis,
)
from experiments.emergent_prices_publication import (
    compose_emergent_prices_snapshot,
)
from simulation import encode_emergent_prices_snapshot
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _events():
    return [completed(f"event-{index}", tick=index) for index in range(6)]


def test_shuffled_order_is_byte_identical() -> None:
    first = harvest_emergent_prices_analysis(committed_events=_events())
    shuffled = list(_events())
    random.Random(11).shuffle(shuffled)
    second = harvest_emergent_prices_analysis(committed_events=shuffled)
    assert emergent_prices_analysis_digest(first) == (
        emergent_prices_analysis_digest(second)
    )
    first_bytes = encode_emergent_prices_snapshot(
        compose_emergent_prices_snapshot(first, run_id="run-1")
    )
    second_bytes = encode_emergent_prices_snapshot(
        compose_emergent_prices_snapshot(second, run_id="run-1")
    )
    assert first_bytes == second_bytes


@pytest.mark.parametrize("seed", ("0", "12345"))
def test_subprocess_hash_seed_is_byte_identical(seed: str) -> None:
    code = (
        "from analysis.emergent_prices_analysis import "
        "emergent_prices_analysis_digest, harvest_emergent_prices_analysis;"
        "from tests.unit.emergent_prices_analysis_helpers import completed;"
        "analysis = harvest_emergent_prices_analysis(committed_events="
        "[completed(f'event-{index}', tick=index) for index in range(6)]);"
        "print(emergent_prices_analysis_digest(analysis))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONHASHSEED": seed},
    )
    expected = emergent_prices_analysis_digest(
        harvest_emergent_prices_analysis(committed_events=_events())
    )
    assert result.stdout.strip() == expected
