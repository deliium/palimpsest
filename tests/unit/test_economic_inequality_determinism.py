# mypy: ignore-errors
"""Determinism tests for the economic-inequality analysis pipeline."""

from __future__ import annotations

import os
import subprocess
import sys

from analysis.economic_inequality_analysis import (
    economic_inequality_analysis_digest,
    harvest_economic_inequality_analysis,
)
from analysis.economic_inequality_rows import (
    EconomicCohortMembership,
    EconomicPossessionRow,
    EconomicSocietyMembership,
)


def _rows(count: int = 8) -> tuple[EconomicPossessionRow, ...]:
    return tuple(
        EconomicPossessionRow(
            owner_token=f"eio-{owner:016x}",
            tick=owner % 3,
            window_index=0,
            observed_item_count=owner * 3,
            observed_tool_count=owner,
        )
        for owner in range(count)
    )


def _analysis():
    memberships = tuple(
        EconomicCohortMembership(
            owner_token=f"eio-{owner:016x}",
            generation_index=owner // 4,
            first_tick=0,
        )
        for owner in range(8)
    )
    societies = tuple(
        EconomicSocietyMembership(
            owner_token=f"eio-{owner:016x}",
            society_token=f"eis-{owner // 4:016x}",
            window_indexes=(0,),
        )
        for owner in range(8)
    )
    return harvest_economic_inequality_analysis(
        possession_rows=_rows(),
        cohort_memberships=memberships,
        society_memberships=societies,
    )


def test_repeated_analysis_has_identical_digest() -> None:
    first = _analysis()
    second = _analysis()
    assert first == second
    assert economic_inequality_analysis_digest(first) == (
        economic_inequality_analysis_digest(second)
    )
    assert first.dimension_rows == second.dimension_rows
    assert first.cohort_rows == second.cohort_rows
    assert first.society_rows == second.society_rows


_SCRIPT = """
from analysis.economic_inequality_analysis import (
    economic_inequality_analysis_digest,
    harvest_economic_inequality_analysis,
)
from analysis.economic_inequality_rows import (
    EconomicCohortMembership,
    EconomicPossessionRow,
)
rows = tuple(
    EconomicPossessionRow(
        owner_token=f"eio-{owner:016x}",
        tick=owner % 3,
        window_index=0,
        observed_item_count=owner * 3,
        observed_tool_count=owner,
    )
    for owner in range(8)
)
memberships = tuple(
    EconomicCohortMembership(
        owner_token=f"eio-{owner:016x}",
        generation_index=owner // 4,
        first_tick=0,
    )
    for owner in range(8)
)
analysis = harvest_economic_inequality_analysis(
    possession_rows=rows, cohort_memberships=memberships
)
print(economic_inequality_analysis_digest(analysis))
"""


def test_digest_is_stable_across_hash_seeds() -> None:
    digests = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", _SCRIPT],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        digests.append(completed.stdout.strip())
    assert len(set(digests)) == 1
