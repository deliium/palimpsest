"""Practical knowledge form / mutate / combine / supersede lineage APIs."""

from __future__ import annotations

import pytest

from agents.cognition.practical_knowledge import (
    KnowledgeTransmissionOrigin,
    PracticalKnowledgeKind,
    combine_practical_knowledge,
    empty_practical_knowledge_ledger,
    form_or_reinforce_practical_knowledge,
    mutate_practical_knowledge,
    practical_knowledge_content_key,
    supersede_practical_knowledge,
)
from agents.models import AgentId

_KINDS = ("foraging_method",)


def _form_root(ledger, *, token: str = "berry-pick", tick: int = 0):
    return form_or_reinforce_practical_knowledge(
        ledger,
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=practical_knowledge_content_key(token),
        content_fingerprint=("cue-a", "cue-b", "cue-c"),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=tick,
        enabled_kinds=_KINDS,
    )


def test_form_independent_root_hop_zero() -> None:
    owner = AgentId("agent-a")
    ledger = _form_root(empty_practical_knowledge_ledger(owner))
    entry = ledger.entries[0]
    assert entry.hop_index == 0
    assert entry.origin is KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY
    assert entry.active is True


def test_reinforce_updates_active_row() -> None:
    owner = AgentId("agent-a")
    key = practical_knowledge_content_key("berry-pick")
    ledger = _form_root(empty_practical_knowledge_ledger(owner))
    ledger = form_or_reinforce_practical_knowledge(
        ledger,
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=key,
        content_fingerprint=("cue-a", "cue-b", "cue-d"),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=2,
        enabled_kinds=_KINDS,
        evidence_refs=("practice:1",),
    )
    active = [row for row in ledger.entries if row.active]
    assert len(active) == 1
    assert active[0].content_fingerprint == ("cue-a", "cue-b", "cue-d")
    assert "practice:1" in active[0].evidence_refs


def test_channel_inactive_rejected() -> None:
    owner = AgentId("agent-a")
    with pytest.raises(ValueError, match="knowledge_genealogy_inactive"):
        form_or_reinforce_practical_knowledge(
            empty_practical_knowledge_ledger(owner),
            kind=PracticalKnowledgeKind.FORAGING_METHOD,
            content_key=practical_knowledge_content_key("berry-pick"),
            content_fingerprint=("cue-a",),
            origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
            tick=0,
            enabled_kinds=_KINDS,
            channel_active=False,
        )


def test_mutate_creates_child_hop_plus_one() -> None:
    owner = AgentId("agent-a")
    ledger = _form_root(empty_practical_knowledge_ledger(owner))
    prior_id = ledger.entries[0].entry_id
    ledger = mutate_practical_knowledge(
        ledger,
        entry_id=prior_id,
        tick=3,
        allow_mutation=True,
        mutation_requires_evidence=False,
        owner_evidence_present=False,
        max_token_edits=2,
        mutation_distance_threshold=0.01,
        rng_namespace="knowledge_genealogy",
        seed_material="seed-1",
    )
    children = [row for row in ledger.entries if prior_id in row.parent_entry_ids]
    assert len(children) == 1
    child = children[0]
    assert child.hop_index == 1
    assert child.parent_entry_ids == (prior_id,)
    assert child.mutated is True
    assert child.active is True
    # Prior active row for same content_key soft-superseded.
    prior = next(row for row in ledger.entries if row.entry_id == prior_id)
    assert prior.active is False


def test_mutation_disabled_rejected() -> None:
    owner = AgentId("agent-a")
    ledger = _form_root(empty_practical_knowledge_ledger(owner))
    with pytest.raises(ValueError, match="knowledge_genealogy_mutation_disabled"):
        mutate_practical_knowledge(
            ledger,
            entry_id=ledger.entries[0].entry_id,
            tick=1,
            allow_mutation=False,
            mutation_requires_evidence=False,
            owner_evidence_present=True,
            max_token_edits=1,
            mutation_distance_threshold=0.15,
            rng_namespace="knowledge_genealogy",
        )


def test_combine_requires_two_parents() -> None:
    owner = AgentId("agent-a")
    ledger = _form_root(empty_practical_knowledge_ledger(owner), token="a")
    with pytest.raises(
        ValueError, match="knowledge_genealogy_combination_requires_parents"
    ):
        combine_practical_knowledge(
            ledger,
            parent_entry_ids=(ledger.entries[0].entry_id,),
            tick=2,
            allow_combination=True,
            allow_multi_parent=True,
            min_token_overlap=0.0,
        )


def test_combine_multi_parent_share() -> None:
    owner = AgentId("agent-a")
    ledger = empty_practical_knowledge_ledger(owner)
    ledger = _form_root(ledger, token="left", tick=0)
    ledger = _form_root(ledger, token="right", tick=1)
    parents = tuple(row.entry_id for row in ledger.entries if row.active)
    assert len(parents) == 2
    ledger = combine_practical_knowledge(
        ledger,
        parent_entry_ids=parents,
        tick=4,
        allow_combination=True,
        allow_multi_parent=True,
        min_token_overlap=0.0,
        enabled_kinds=_KINDS,
    )
    combined = [
        row
        for row in ledger.entries
        if row.origin is KnowledgeTransmissionOrigin.COMBINATION
    ]
    assert len(combined) == 1
    assert len(combined[0].parent_entry_ids) == 2
    assert combined[0].hop_index == 1


def test_combination_disabled_rejected() -> None:
    owner = AgentId("agent-a")
    ledger = empty_practical_knowledge_ledger(owner)
    ledger = _form_root(ledger, token="left", tick=0)
    ledger = _form_root(ledger, token="right", tick=1)
    parents = tuple(row.entry_id for row in ledger.entries if row.active)
    with pytest.raises(
        ValueError, match="knowledge_genealogy_combination_disabled"
    ):
        combine_practical_knowledge(
            ledger,
            parent_entry_ids=parents,
            tick=2,
            allow_combination=False,
            allow_multi_parent=True,
            min_token_overlap=0.0,
        )


def test_supersede_sets_inactive_without_delete() -> None:
    owner = AgentId("agent-a")
    ledger = _form_root(empty_practical_knowledge_ledger(owner))
    entry_id = ledger.entries[0].entry_id
    ledger = supersede_practical_knowledge(ledger, entry_id=entry_id, tick=5)
    assert len(ledger.entries) == 1
    assert ledger.entries[0].entry_id == entry_id
    assert ledger.entries[0].active is False


def test_mutate_hop_cap() -> None:
    owner = AgentId("agent-a")
    ledger = empty_practical_knowledge_ledger(owner, max_hop_depth=1)
    ledger = _form_root(ledger)
    with pytest.raises(ValueError, match="knowledge_genealogy_hop_cap"):
        mutate_practical_knowledge(
            ledger,
            entry_id=ledger.entries[0].entry_id,
            tick=1,
            allow_mutation=True,
            mutation_requires_evidence=False,
            owner_evidence_present=True,
            max_token_edits=1,
            mutation_distance_threshold=0.15,
            rng_namespace="knowledge_genealogy",
        )
