"""Technique lifecycle snapshot DTO."""

from __future__ import annotations

import pytest

from analysis.technique_lifecycle import (
    TechniqueLifecycleSnapshot,
    TechniqueLifecycleState,
    TechniqueLossCause,
)


def test_snapshot_round_trip_fields() -> None:
    row = TechniqueLifecycleSnapshot(
        content_key="tech:hafting",
        scope="global",
        state=TechniqueLifecycleState.DISCOVERED,
        known_by_n=1,
        performable=None,
        causes=frozenset(),
        lineage_root_ids=("root-1",),
    )
    assert row.state is TechniqueLifecycleState.DISCOVERED
    assert row.known_by_n == 1
    assert row.performable is None


def test_unknown_state_token_rejected() -> None:
    with pytest.raises(ValueError):
        TechniqueLifecycleState("unlocked")
    with pytest.raises(ValueError, match="technique_lifecycle_state_invalid"):
        TechniqueLifecycleSnapshot(
            content_key="tech:hafting",
            scope="global",
            state="discovered",  # type: ignore[arg-type]
            known_by_n=1,
            performable=None,
            causes=frozenset({TechniqueLossCause.HOLDERS_DIED}),
            lineage_root_ids=(),
        )
