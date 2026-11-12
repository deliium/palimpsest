"""Byte-level determinism across hash seeds and shuffled event order."""

# mypy: ignore-errors


from __future__ import annotations

import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from analysis.credit_relationships_analysis import (
    credit_relationships_analysis_digest,
    harvest_credit_relationships_analysis,
)
from experiments.credit_relationships_publication import (
    compose_credit_relationships_snapshot,
)
from simulation import encode_credit_relationships_snapshot
from tests.unit.credit_relationships_analysis_helpers import (
    completed,
    frame,
    given,
    talked,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _events():
    events = [
        completed("evt-0", give_ids=("item-1",), give_kinds=("food",), tick=0)
    ]
    for index in range(1, 7):
        events.append(talked(f"evt-{index}", frame(), tick=index, sequence=1))
        events.append(given(f"evt-g-{index}", item_id="item-1", tick=index))
    return events


def test_shuffled_order_is_byte_identical() -> None:
    first = harvest_credit_relationships_analysis(committed_events=_events())
    shuffled = list(_events())
    random.Random(11).shuffle(shuffled)
    second = harvest_credit_relationships_analysis(committed_events=shuffled)
    assert credit_relationships_analysis_digest(first) == (
        credit_relationships_analysis_digest(second)
    )
    first_bytes = encode_credit_relationships_snapshot(
        compose_credit_relationships_snapshot(first, run_id="run-1")
    )
    second_bytes = encode_credit_relationships_snapshot(
        compose_credit_relationships_snapshot(second, run_id="run-1")
    )
    assert first_bytes == second_bytes


@pytest.mark.parametrize("seed", ("0", "12345"))
def test_subprocess_hash_seed_is_byte_identical(seed: str) -> None:
    code = (
        "from analysis.credit_relationships_analysis import "
        "credit_relationships_analysis_digest, "
        "harvest_credit_relationships_analysis;"
        "from tests.unit.credit_relationships_analysis_helpers import "
        "completed, frame, given, talked;"
        "events=[completed('evt-0', give_ids=('item-1',),"
        " give_kinds=('food',), tick=0)];"
        "[events.extend((talked(f'evt-{index}', frame(), tick=index, sequence=1), "
        "given(f'evt-g-{index}', item_id='item-1', tick=index))) "
        "for index in range(1, 7)];"
        "print(credit_relationships_analysis_digest("
        "harvest_credit_relationships_analysis(committed_events=events)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONHASHSEED": seed},
    )
    expected = credit_relationships_analysis_digest(
        harvest_credit_relationships_analysis(committed_events=_events())
    )
    assert result.stdout.strip() == expected
