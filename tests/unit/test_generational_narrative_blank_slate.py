"""New agents start blank-slate with no V2 narrative provenance."""

from __future__ import annotations

from agents.cognition.defaults import default_cognitive_loop
from simulation.new_agent_initialization import (
    BLANK_SLATE_SUBJECTIVE_STORES,
    SUBJECTIVE_COPY_DENY_LIST,
    default_new_agent_initialization_spec,
)
from tests.unit.test_cultural_narratives_runtime import _runtime


def test_blank_slate_denies_cultural_narratives_and_v2_provenance() -> None:
    assert "cultural_narratives" in BLANK_SLATE_SUBJECTIVE_STORES
    assert "cultural_narratives" in SUBJECTIVE_COPY_DENY_LIST
    for forbidden in (
        "source_witnesses",
        "record_refs",
        "transitions",
        "source_loss",
        "narrative_provenance",
    ):
        assert forbidden not in BLANK_SLATE_SUBJECTIVE_STORES


def test_new_runtime_has_no_narrative_ledger() -> None:
    spec = default_new_agent_initialization_spec()
    assert spec is not None
    runtime = _runtime(default_cognitive_loop())
    assert runtime.export_cultural_narratives() is None
