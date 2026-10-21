"""Causal invariants: no telepathy, no inherited content, no correction."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from agents.cognition.institutional_memory import (
    InstitutionalBindingKind,
    InstitutionalChannel,
    InstitutionalFact,
    InstitutionalMemoryChannel,
    InstitutionalMemoryEntry,
    InstitutionalMemoryLedger,
    InstitutionalProvenance,
    apply_institutional_memory_update,
    empty_institutional_memory_ledger,
    institutional_channel_id,
    institutional_entry_id,
    set_institutional_entry_ignored,
)
from agents.cognition.institutional_memory_actions import (
    consult_institutional_memory,
)
from agents.cognition.institutional_memory_frames import (
    InstitutionalMemoryFrame,
    decode_institutional_marks,
    encode_institutional_marks,
    institutional_frame_root,
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


def _channel(owner: AgentId = _OWNER) -> tuple[str, InstitutionalChannel]:
    inception = "a" * 64
    channel_id = institutional_channel_id(
        owner, InstitutionalBindingKind.ROLE, inception
    )
    return channel_id, InstitutionalChannel(
        owner_id=owner,
        channel_id=channel_id,
        binding_kind=InstitutionalBindingKind.ROLE,
        inception_reference=inception,
        current_local_reference="b" * 64,
        public_function_token="exchange_aaaaaaaa",
        context_digest="c" * 16,
        first_tick=0,
        last_tick=1,
        revision_count=0,
    )


def _bound_ledger() -> InstitutionalMemoryLedger:
    channel_id, channel = _channel()
    template = _entry()
    entry = InstitutionalMemoryEntry(
        owner_id=_OWNER,
        entry_id=institutional_entry_id(_OWNER, channel_id, 0),
        channel_id=channel_id,
        ordinal=0,
        revision=0,
        facts=template.facts,
        declared_fact_count=template.declared_fact_count,
        acquisition_tick=template.acquisition_tick,
        confidence=template.confidence,
        distorted=template.distorted,
        partial=template.partial,
        active=template.active,
        ignored=template.ignored,
        provenance=template.provenance,
    )
    return InstitutionalMemoryLedger(
        owner_id=_OWNER, channels=(channel,), entries=(entry,)
    )


def test_ignore_excludes_consultation_and_unignore_restores_it() -> None:
    ledger = _bound_ledger()
    entry_id = ledger.entries[0].entry_id
    ignored = set_institutional_entry_ignored(
        ledger, entry_id, ignored=True, tick=2
    )
    assert (
        consult_institutional_memory(
            ignored,
            channel_id=ledger.channels[0].channel_id,
            tick=2,
            invocation_id="inv-1",
        )
        is None
    )
    unignored = set_institutional_entry_ignored(
        ignored, entry_id, ignored=False, tick=3
    )
    selected = consult_institutional_memory(
        unignored,
        channel_id=ledger.channels[0].channel_id,
        tick=3,
        invocation_id="inv-2",
    )
    assert selected is not None
    assert len(selected.entries) == 1


@given(
    triples=st.lists(
        st.sampled_from(
            (
                ("trade", "owes", "grain"),
                ("trade", "owes", "salt"),
                ("store", "holds", "meal"),
            )
        ),
        min_size=1,
        max_size=3,
        unique=True,
    ),
    cut=st.integers(min_value=0, max_value=16),
)
def test_truncation_never_invents_facts(
    triples: list[tuple[str, str, str]], cut: int
) -> None:
    frame = InstitutionalMemoryFrame(
        binding_kind=InstitutionalBindingKind.ROLE,
        function_token="exchange_aaaaaaaa",
        context_digest="c_" + "c" * 16,
        root=institutional_frame_root("property-root"),
        parent="p_none",
        facts=tuple(InstitutionalFact(*item) for item in triples),
        declared_fact_count=len(triples),
    )
    marks = encode_institutional_marks(frame)
    decoded = decode_institutional_marks(marks[:cut])
    if decoded is not None:
        exposed = {
            (item.subject, item.predicate, item.object) for item in decoded.facts
        }
        assert exposed <= set(triples)
