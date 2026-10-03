"""Semantic belief uplift stays gated and never writes through MemoryService."""

from __future__ import annotations

import pytest

from agents.cognition.configuration import CognitionCulturalNarrativeMode
from agents.cognition.cultural_narratives import (
    NarrativeContent,
    NarrativeLedger,
    NarrativeOrigin,
    NarrativeStatus,
    NarrativeVariant,
    narrative_content_fingerprint,
    narrative_semantic_evidence,
    narrative_variant_id,
)
from agents.models import AgentId
from memory.beliefs import BeliefRevisionRequest
from memory.models import MemoryId


def _active_variant(
    *,
    strength: float = 0.55,
    repetition_count: int = 5,
    status: NarrativeStatus = NarrativeStatus.ACTIVE,
    source_memory_id: str | None = "mem-anchor-1",
) -> NarrativeVariant:
    owner = AgentId("alice")
    content = NarrativeContent(concepts=("water", "gone"), text="tell_story")
    fingerprint = narrative_content_fingerprint(content)
    return NarrativeVariant(
        variant_id=narrative_variant_id(owner, fingerprint, 0, ""),
        owner_id=owner,
        content=content,
        content_fingerprint=fingerprint,
        origin=NarrativeOrigin.OBSERVED_EVENT,
        status=status,
        strength=strength,
        repetition_count=repetition_count,
        source_memory_id=source_memory_id,
    )


def test_uplift_returns_belief_revision_request_at_gates() -> None:
    owner = AgentId("alice")
    ledger = NarrativeLedger(owner_id=owner, variants=(_active_variant(),))
    requests = narrative_semantic_evidence(
        ledger,
        owner_id=owner,
        tick=12,
        mode=CognitionCulturalNarrativeMode.DETERMINISTIC,
    )
    assert len(requests) == 1
    assert type(requests[0]) is BeliefRevisionRequest
    assert requests[0].evidence.supporting
    assert type(requests[0].evidence.supporting[0].memory_id) is MemoryId


@pytest.mark.parametrize(
    ("status", "strength", "repetition"),
    [
        (NarrativeStatus.CANDIDATE, 0.55, 5),
        (NarrativeStatus.RETIRED, 0.55, 5),
        (NarrativeStatus.MERGED, 0.55, 5),
        (NarrativeStatus.ACTIVE, 0.50, 5),
        (NarrativeStatus.ACTIVE, 0.55, 4),
    ],
)
def test_uplift_withheld_below_gates(
    status: NarrativeStatus, strength: float, repetition: int
) -> None:
    owner = AgentId("alice")
    content = NarrativeContent(concepts=("water", "gone"), text="tell_story")
    fingerprint = narrative_content_fingerprint(content)
    parent_a = "a" * 64
    parent_b = "b" * 64
    merge_target = "c" * 64
    variant = NarrativeVariant(
        variant_id=narrative_variant_id(owner, fingerprint, 0, ""),
        owner_id=owner,
        content=content,
        content_fingerprint=fingerprint,
        origin=NarrativeOrigin.OBSERVED_EVENT,
        status=status,
        strength=strength,
        repetition_count=repetition,
        source_memory_id="mem-anchor-1",
        merged_into_id=merge_target if status is NarrativeStatus.MERGED else None,
        parent_variant_ids=(
            (parent_a, parent_b) if status is NarrativeStatus.MERGED else ()
        ),
    )
    requests = narrative_semantic_evidence(
        NarrativeLedger(owner_id=owner, variants=(variant,)),
        owner_id=owner,
        tick=12,
        mode=CognitionCulturalNarrativeMode.DETERMINISTIC,
    )
    assert requests == ()


def test_uplift_does_not_import_or_call_memory_service() -> None:
    from pathlib import Path

    import agents.cognition.cultural_narratives as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "from memory.service" not in source
    assert "import memory.service" not in source
    assert "revise_semantic_belief" not in source
    assert "MemoryService(" not in source


def test_uplift_uses_synthetic_memory_anchor_when_source_missing() -> None:
    owner = AgentId("alice")
    ledger = NarrativeLedger(
        owner_id=owner,
        variants=(_active_variant(source_memory_id=None),),
    )
    requests = narrative_semantic_evidence(
        ledger,
        owner_id=owner,
        tick=12,
        mode=CognitionCulturalNarrativeMode.DETERMINISTIC,
    )
    assert len(requests) == 1
    memory_id = requests[0].evidence.supporting[0].memory_id
    assert type(memory_id) is MemoryId
    assert memory_id.value.startswith("narrative-lineage-")
