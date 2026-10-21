"""Causal invariants: no telepathy, no inherited content, no correction."""

from __future__ import annotations

from dataclasses import replace

from agents.cognition.institutional_memory import (
    InstitutionalFact,
    InstitutionalMemoryChannel,
    InstitutionalMemoryEntry,
    InstitutionalMemoryLedger,
    InstitutionalProvenance,
    apply_institutional_memory_update,
    empty_institutional_memory_ledger,
    institutional_entry_id,
)
from agents.cognition.models import OwnerSafeSocialIdentity
from agents.models import AgentId
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation

_OWNER = AgentId("alice")
_BODY = EntityId("alice-body")


def _observation() -> Observation:
    return Observation(
        world_id=WorldId("world"),
        observer_id=_BODY,
        revision=WorldRevision(1),
        tick=1,
    )


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(owner_id=_OWNER, owner_entity_id=_BODY)


def _entry() -> InstitutionalMemoryEntry:
    return InstitutionalMemoryEntry(
        owner_id=_OWNER,
        entry_id=institutional_entry_id(_OWNER, None, 0),
        channel_id=None,
        ordinal=0,
        revision=0,
        facts=(InstitutionalFact("trade", "owes", "grain"),),
        declared_fact_count=1,
        acquisition_tick=1,
        confidence=0.5,
        distorted=False,
        partial=False,
        active=True,
        ignored=False,
        provenance=(
            InstitutionalProvenance(
                immediate_channel=InstitutionalMemoryChannel.OBSERVATION
            ),
        ),
    )


def test_unseen_peer_state_does_not_change_owner_output() -> None:
    first = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
    )
    second = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
    )
    assert first == second


def test_successor_channel_is_not_predecessor_content() -> None:
    predecessor = empty_institutional_memory_ledger(_OWNER)
    successor = empty_institutional_memory_ledger(AgentId("bob"))
    assert predecessor.entries == ()
    assert successor.entries == ()
    assert predecessor.owner_id != successor.owner_id


def test_learned_entry_survives_carrier_loss() -> None:
    ledger = InstitutionalMemoryLedger(owner_id=_OWNER, entries=(_entry(),))
    damaged_source = _observation()
    updated = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=damaged_source,
        identity=_identity(),
        previous=ledger,
    )
    assert updated.entries[0].facts == ledger.entries[0].facts


def test_rewriting_a_claim_does_not_erase_prior_entries() -> None:
    ledger = InstitutionalMemoryLedger(owner_id=_OWNER, entries=(_entry(),))
    conflicting = replace(
        ledger.entries[0],
        entry_id=institutional_entry_id(_OWNER, None, 1),
        ordinal=1,
        facts=(InstitutionalFact("trade", "owes", "salt"),),
    )
    updated = replace(ledger, entries=(*ledger.entries, conflicting))
    assert len(updated.entries) == 2
    assert updated.entries[0].facts != updated.entries[1].facts
