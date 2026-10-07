"""Practical knowledge ledger construction, hop resolution, and eviction."""

from __future__ import annotations

import pytest

from agents.cognition.practical_knowledge import (
    KnowledgeTransmissionOrigin,
    PracticalKnowledgeKind,
    SubjectivePracticalKnowledge,
    empty_practical_knowledge_ledger,
    entry_to_audit,
    practical_knowledge_content_key,
    require_owner_practical_knowledge,
    resolve_practical_knowledge_hop_index,
    upsert_practical_knowledge,
)
from agents.models import AgentId


def _entry(
    *,
    entry_id: str = "pk-1",
    owner: str = "agent-a",
    kind: PracticalKnowledgeKind = PracticalKnowledgeKind.FORAGING_METHOD,
    token: str = "berry-pick",
    origin: KnowledgeTransmissionOrigin = (
        KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY
    ),
    parents: tuple[str, ...] = (),
    hop: int = 0,
    active: bool = True,
    tick: int = 0,
    fingerprint: tuple[str, ...] = ("cue-a", "cue-b"),
    source: AgentId | None = None,
    refs: tuple[str, ...] = (),
) -> SubjectivePracticalKnowledge:
    teacher = (
        source if origin is KnowledgeTransmissionOrigin.TEACHING else None
    )
    return SubjectivePracticalKnowledge(
        entry_id=entry_id,
        owner_id=AgentId(owner),
        kind=kind,
        content_key=practical_knowledge_content_key(token),
        content_fingerprint=fingerprint,
        origin=origin,
        parent_entry_ids=parents,
        lineage_root_id=(
            f"root:{owner}:{kind.value}:"
            f"{practical_knowledge_content_key(token)}"
        ),
        hop_index=hop,
        mutated=False,
        source_agent_id=source,
        teacher_agent_id=teacher,
        evidence_refs=refs,
        acquired_tick=tick,
        active=active,
    )


def test_content_key_uses_tech_prefix() -> None:
    assert practical_knowledge_content_key("berry-pick") == "tech:berry-pick"


def test_independent_discovery_legal() -> None:
    entry = _entry()
    assert entry.hop_index == 0
    assert entry.parent_entry_ids == ()
    ledger = upsert_practical_knowledge(
        empty_practical_knowledge_ledger(AgentId("agent-a")), entry
    )
    assert len(ledger.entries) == 1


def test_independent_discovery_rejects_parents() -> None:
    with pytest.raises(ValueError, match="independent_discovery_no_parents"):
        _entry(parents=("pk-other",), hop=0)


def test_combination_requires_two_parents() -> None:
    with pytest.raises(
        ValueError, match="knowledge_genealogy_combination_requires_parents"
    ):
        _entry(
            origin=KnowledgeTransmissionOrigin.COMBINATION,
            parents=("pk-a",),
            hop=1,
        )


def test_combination_multi_parent_legal() -> None:
    entry = _entry(
        origin=KnowledgeTransmissionOrigin.COMBINATION,
        parents=("pk-a", "pk-b"),
        hop=2,
        fingerprint=("cue-a", "cue-b", "cue-c"),
    )
    assert len(entry.parent_entry_ids) == 2


def test_hop_resolution_independent() -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("agent-a"))
    assert (
        resolve_practical_knowledge_hop_index(
            ledger,
            origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
            parent_entry_ids=(),
        )
        == 0
    )


def test_hop_resolution_peer_taught_empty_parents() -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("agent-a"))
    assert (
        resolve_practical_knowledge_hop_index(
            ledger,
            origin=KnowledgeTransmissionOrigin.TEACHING,
            parent_entry_ids=(),
        )
        == 1
    )


def test_hop_resolution_parent_hop_fallback_is_one() -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("agent-a"))
    assert (
        resolve_practical_knowledge_hop_index(
            ledger,
            origin=KnowledgeTransmissionOrigin.TEACHING,
            parent_entry_ids=("missing-parent",),
        )
        == 2
    )  # missing ⇒ hop 1, then +1


def test_hop_resolution_from_owner_parent() -> None:
    owner = AgentId("agent-a")
    root = _entry(entry_id="pk-root", hop=0, tick=0)
    ledger = upsert_practical_knowledge(empty_practical_knowledge_ledger(owner), root)
    assert (
        resolve_practical_knowledge_hop_index(
            ledger,
            origin=KnowledgeTransmissionOrigin.TEACHING,
            parent_entry_ids=("pk-root",),
        )
        == 1
    )


def test_parent_cap_on_upsert() -> None:
    owner = AgentId("agent-a")
    ledger = empty_practical_knowledge_ledger(owner, max_parent_ids=2)
    entry = _entry(
        origin=KnowledgeTransmissionOrigin.COMBINATION,
        parents=("a", "b", "c"),
        hop=2,
    )
    with pytest.raises(ValueError, match="knowledge_genealogy_parent_cap"):
        upsert_practical_knowledge(ledger, entry)


def test_hop_cap_on_upsert() -> None:
    owner = AgentId("agent-a")
    ledger = empty_practical_knowledge_ledger(owner, max_hop_depth=2)
    entry = _entry(
        origin=KnowledgeTransmissionOrigin.TEACHING,
        parents=(),
        hop=2,
        source=AgentId("teacher"),
        refs=("teach:1",),
    )
    with pytest.raises(ValueError, match="knowledge_genealogy_hop_cap"):
        upsert_practical_knowledge(ledger, entry)


def test_cycle_rejected() -> None:
    owner = AgentId("agent-a")
    a = _entry(entry_id="pk-a", hop=0)
    b = _entry(
        entry_id="pk-b",
        origin=KnowledgeTransmissionOrigin.TEACHING,
        parents=("pk-a",),
        hop=1,
        source=AgentId("teacher"),
        refs=("teach:1",),
        token="berry-pick-b",
    )
    ledger = upsert_practical_knowledge(empty_practical_knowledge_ledger(owner), a)
    ledger = upsert_practical_knowledge(ledger, b)
    cyclic = _entry(
        entry_id="pk-a",
        origin=KnowledgeTransmissionOrigin.TEACHING,
        parents=("pk-b",),
        hop=2,
        source=AgentId("teacher"),
        refs=("teach:2",),
    )
    with pytest.raises(ValueError, match="knowledge_genealogy_cycle"):
        upsert_practical_knowledge(ledger, cyclic)


def test_evict_inactive_before_oldest_active() -> None:
    owner = AgentId("agent-a")
    ledger = empty_practical_knowledge_ledger(owner, max_entries=2)
    inactive = _entry(
        entry_id="pk-old-inactive",
        token="old-inactive",
        tick=0,
        active=False,
    )
    older_active = _entry(
        entry_id="pk-old-active",
        token="old-active",
        tick=1,
        active=True,
    )
    newer_active = _entry(
        entry_id="pk-new-active",
        token="new-active",
        tick=2,
        active=True,
    )
    ledger = upsert_practical_knowledge(ledger, inactive)
    ledger = upsert_practical_knowledge(ledger, older_active)
    ledger = upsert_practical_knowledge(ledger, newer_active)
    ids = {row.entry_id for row in ledger.entries}
    assert "pk-old-inactive" not in ids
    assert ids == {"pk-old-active", "pk-new-active"}


def test_entry_to_audit_metadata_only() -> None:
    entry = _entry()
    audit = entry_to_audit(entry, tick=3, reason_code="formed")
    assert audit.entry_id == entry.entry_id
    assert audit.content_key == entry.content_key
    assert audit.tick == 3
    assert audit.reason_code == "formed"
    assert not hasattr(audit, "content_fingerprint")


def test_require_owner_rejects_mismatch() -> None:
    ledger = empty_practical_knowledge_ledger(AgentId("agent-a"))
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_practical_knowledge(
            ledger, AgentId("agent-b"), field_name="practical_knowledge"
        )
