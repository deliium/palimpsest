"""Owner-local institutional memory contracts and deterministic retention."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.cognition.institutional_memory import (
    INSTITUTIONAL_MEMORY_POLICY_VERSION,
    InstitutionalBindingKind,
    InstitutionalChannel,
    InstitutionalFact,
    InstitutionalLocalReference,
    InstitutionalMemoryChannel,
    InstitutionalMemoryEntry,
    InstitutionalMemoryLedger,
    InstitutionalMemoryPolicy,
    InstitutionalMemorySelection,
    InstitutionalMemorySelectionKind,
    InstitutionalMemoryUse,
    InstitutionalMemoryUseDisposition,
    InstitutionalOccupantClaim,
    InstitutionalOccupantStatus,
    InstitutionalProvenance,
    InstitutionalReferenceState,
    append_institutional_memory_channel,
    append_institutional_memory_entry,
    append_institutional_memory_use,
    default_institutional_memory_policy,
    empty_institutional_memory_ledger,
    institutional_channel_id,
    institutional_entry_id,
    record_institutional_acquisition_receipt,
    require_owner_institutional_memory,
    require_owner_institutional_memory_selection,
)
from agents.models import AgentId
from world.communications import (
    CommunicationId,
    CommunicationSourceBasis,
    DeclaredTransmission,
)
from world.identifiers import EntityId

_INCEPTION = "a" * 64
_OFFICE_ID = "b" * 64
_CONTEXT = "c" * 16


def _agent(value: str = "alice") -> AgentId:
    return AgentId(value)


def _channel(
    owner: AgentId | None = None,
    *,
    kind: InstitutionalBindingKind = InstitutionalBindingKind.ROLE,
    inception: str = _INCEPTION,
    function: str = "trade",
    first_tick: int = 0,
    last_tick: int = 0,
    revision: int = 0,
    occupants: tuple[InstitutionalOccupantClaim, ...] = (),
) -> InstitutionalChannel:
    active = owner or _agent()
    current = (
        _OFFICE_ID if kind is InstitutionalBindingKind.ROLE else "procedure_anchor"
    )
    return InstitutionalChannel(
        owner_id=active,
        channel_id=institutional_channel_id(active, kind, inception),
        binding_kind=kind,
        inception_reference=inception,
        current_local_reference=current,
        public_function_token=function,
        context_digest=_CONTEXT,
        first_tick=first_tick,
        last_tick=last_tick,
        revision_count=revision,
        occupants=occupants,
    )


def _provenance(
    *,
    channel: InstitutionalMemoryChannel = InstitutionalMemoryChannel.OBSERVATION,
    predecessor: InstitutionalLocalReference | None = None,
    declared_root: str | None = None,
    declared_parent: str | None = None,
    transmission: DeclaredTransmission | None = None,
) -> InstitutionalProvenance:
    return InstitutionalProvenance(
        immediate_channel=channel,
        predecessor=predecessor,
        declared_frame_root=declared_root,
        declared_frame_parent=declared_parent,
        declared_transmission=transmission,
    )


def _entry(
    owner: AgentId | None = None,
    *,
    channel_id: str | None = None,
    ordinal: int = 0,
    tick: int = 0,
    revision: int = 0,
    facts: tuple[InstitutionalFact, ...] | None = None,
    provenance: tuple[InstitutionalProvenance, ...] | None = None,
    superseded: InstitutionalLocalReference | None = None,
    ignored: bool = False,
    partial: bool = False,
    declared_count: int | None = None,
) -> InstitutionalMemoryEntry:
    active = owner or _agent()
    checked_facts = facts or (InstitutionalFact("trade", "owes", "grain"),)
    return InstitutionalMemoryEntry(
        owner_id=active,
        entry_id=institutional_entry_id(active, channel_id, ordinal),
        channel_id=channel_id,
        ordinal=ordinal,
        revision=revision,
        facts=checked_facts,
        declared_fact_count=declared_count or len(checked_facts),
        acquisition_tick=tick,
        confidence=0.75,
        distorted=False,
        partial=partial,
        active=True,
        ignored=ignored,
        provenance=provenance or (_provenance(),),
        superseded_entry=superseded,
    )


def _transmission() -> DeclaredTransmission:
    return DeclaredTransmission(
        communication_id=CommunicationId("communication-1"),
        immediate_source_id=EntityId("speaker-entity"),
        parent_communication_id=None,
        root_communication_id=CommunicationId("communication-1"),
        source_agent_chain=(EntityId("speaker-entity"),),
        hop_count=0,
        sender_confidence=0.5,
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )


def test_policy_is_locked() -> None:
    policy = default_institutional_memory_policy()
    assert policy.version == INSTITUTIONAL_MEMORY_POLICY_VERSION
    assert policy.max_channels == 32
    assert policy.max_entries == 128
    assert policy.max_uses == 32
    assert policy.max_provenance == 16
    assert policy.max_receipts == 256
    with pytest.raises(ValueError, match="unsupported_policy"):
        InstitutionalMemoryPolicy(version="institutional-memory.v2")
    with pytest.raises(ValueError, match="unsupported_policy"):
        InstitutionalMemoryPolicy(max_entries=129)


def test_role_channel_is_stable_across_occupant_revision() -> None:
    alice = _agent()
    first = _channel(
        alice,
        occupants=(
            InstitutionalOccupantClaim(
                attributed_actor_id=EntityId("observer"),
                occupant_id=_agent("bob"),
                status=InstitutionalOccupantStatus.CLAIMED,
                start_tick=1,
            ),
        ),
    )
    second = _channel(
        alice,
        last_tick=4,
        revision=1,
        occupants=(
            InstitutionalOccupantClaim(
                attributed_actor_id=EntityId("observer"),
                occupant_id=_agent("carol"),
                status=InstitutionalOccupantStatus.OBSERVED,
                start_tick=4,
            ),
        ),
    )
    assert first.channel_id == second.channel_id
    assert first.current_local_reference == second.current_local_reference == _OFFICE_ID


def test_procedure_and_role_inceptions_are_separate() -> None:
    alice = _agent()
    role = _channel(alice)
    procedure = _channel(
        alice, kind=InstitutionalBindingKind.PROCEDURE, inception="d" * 64
    )
    assert role.channel_id != procedure.channel_id


def test_owner_mismatch_is_rejected() -> None:
    alice = _agent()
    bob = _agent("bob")
    ledger = empty_institutional_memory_ledger(alice)
    require_owner_institutional_memory(ledger, alice, field_name="institutional_memory")
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_institutional_memory(
            ledger, bob, field_name="institutional_memory"
        )
    with pytest.raises(TypeError):
        require_owner_institutional_memory(object(), alice, field_name="memory")
    with pytest.raises(ValueError, match="owner_mismatch"):
        InstitutionalMemoryLedger(owner_id=alice, channels=(_channel(bob),))


def test_values_are_frozen() -> None:
    fact = InstitutionalFact("trade", "owes", "grain")
    with pytest.raises(AttributeError):
        fact.subject = "other"  # type: ignore[misc]
    ledger = empty_institutional_memory_ledger(_agent())
    with pytest.raises(AttributeError):
        ledger.entries = ()  # type: ignore[misc]


def test_duplicate_ids_are_rejected() -> None:
    alice = _agent()
    channel = _channel(alice)
    entry = _entry(alice, channel_id=channel.channel_id)
    with pytest.raises(ValueError, match="duplicate_id"):
        InstitutionalMemoryLedger(owner_id=alice, channels=(channel, channel))
    with pytest.raises(ValueError, match="duplicate_id"):
        InstitutionalMemoryLedger(
            owner_id=alice, channels=(channel,), entries=(entry, entry)
        )


def test_retained_dangling_reference_is_rejected_but_pruned_is_allowed() -> None:
    alice = _agent()
    channel = _channel(alice)
    dangling = InstitutionalLocalReference("f" * 64)
    with pytest.raises(ValueError, match="dangling_reference"):
        InstitutionalMemoryLedger(
            owner_id=alice,
            channels=(channel,),
            entries=(
                _entry(
                    alice,
                    channel_id=channel.channel_id,
                    provenance=(_provenance(predecessor=dangling),),
                ),
            ),
        )
    pruned = InstitutionalLocalReference(
        "f" * 64, state=InstitutionalReferenceState.PRUNED
    )
    ledger = InstitutionalMemoryLedger(
        owner_id=alice,
        channels=(channel,),
        entries=(
            _entry(
                alice,
                channel_id=channel.channel_id,
                provenance=(_provenance(predecessor=pruned),),
            ),
        ),
    )
    assert ledger.entries[0].provenance[0].predecessor == pruned


def test_bool_as_int_and_nan_are_rejected() -> None:
    alice = _agent()
    with pytest.raises(ValueError, match="invalid_type"):
        InstitutionalMemoryEntry(
            owner_id=alice,
            entry_id=institutional_entry_id(alice, None, 0),
            channel_id=None,
            ordinal=0,
            revision=0,
            facts=(InstitutionalFact("trade", "owes", "grain"),),
            declared_fact_count=1,
            acquisition_tick=True,
            confidence=0.5,
            distorted=False,
            partial=False,
            active=True,
            ignored=False,
            provenance=(_provenance(),),
        )
    with pytest.raises(ValueError, match="nonfinite"):
        InstitutionalMemoryEntry(
            owner_id=alice,
            entry_id=institutional_entry_id(alice, None, 1),
            channel_id=None,
            ordinal=1,
            revision=0,
            facts=(InstitutionalFact("trade", "owes", "grain"),),
            declared_fact_count=1,
            acquisition_tick=0,
            confidence=float("nan"),
            distorted=False,
            partial=False,
            active=True,
            ignored=False,
            provenance=(_provenance(),),
        )
    with pytest.raises(ValueError, match="out_of_range"):
        InstitutionalMemoryEntry(
            owner_id=alice,
            entry_id=institutional_entry_id(alice, None, 2),
            channel_id=None,
            ordinal=2,
            revision=0,
            facts=(InstitutionalFact("trade", "owes", "grain"),),
            declared_fact_count=1,
            acquisition_tick=0,
            confidence=1.5,
            distorted=False,
            partial=False,
            active=True,
            ignored=False,
            provenance=(_provenance(),),
        )


def test_entry_cap_evicts_oldest_and_marks_coverage_partial() -> None:
    alice = _agent()
    channel = _channel(alice)
    ledger = empty_institutional_memory_ledger(alice)
    ledger = append_institutional_memory_channel(ledger, channel)
    for ordinal in range(129):
        ledger = append_institutional_memory_entry(
            ledger,
            _entry(alice, channel_id=channel.channel_id, ordinal=ordinal, tick=ordinal),
        )
    assert len(ledger.entries) == 128
    assert ledger.pruned_entry_count == 1
    assert ledger.coverage == "partial"
    assert ledger.entries[0].ordinal == 1


def test_channel_cap_protects_retained_channels() -> None:
    alice = _agent()
    channels = tuple(_channel(alice, inception=f"{index:064x}") for index in range(32))
    entries = tuple(
        _entry(alice, channel_id=channel.channel_id, ordinal=index)
        for index, channel in enumerate(channels)
    )
    ledger = InstitutionalMemoryLedger(
        owner_id=alice, channels=channels, entries=entries
    )
    with pytest.raises(ValueError, match="cap_exceeded"):
        append_institutional_memory_channel(ledger, _channel(alice, inception="f" * 64))


def test_unreferenced_channel_is_evicted_under_cap() -> None:
    alice = _agent()
    channels = tuple(
        _channel(
            alice,
            inception=f"{index:064x}",
            first_tick=index,
            last_tick=index,
        )
        for index in range(32)
    )
    ledger = InstitutionalMemoryLedger(owner_id=alice, channels=channels)
    new_channel = _channel(
        alice, inception="f" * 64, first_tick=99, last_tick=99
    )
    updated = append_institutional_memory_channel(ledger, new_channel)
    assert len(updated.channels) == 32
    assert updated.pruned_channel_count == 1
    assert new_channel.channel_id in {item.channel_id for item in updated.channels}


def test_conflicting_entries_are_preserved() -> None:
    alice = _agent()
    channel = _channel(alice)
    first = _entry(
        alice,
        channel_id=channel.channel_id,
        ordinal=0,
        facts=(InstitutionalFact("trade", "owes", "grain"),),
    )
    second = _entry(
        alice,
        channel_id=channel.channel_id,
        ordinal=1,
        facts=(InstitutionalFact("trade", "owes", "salt"),),
    )
    ledger = InstitutionalMemoryLedger(
        owner_id=alice, channels=(channel,), entries=(first, second)
    )
    assert len(ledger.entries) == 2
    assert ledger.entries[0].facts != ledger.entries[1].facts


def test_same_claim_received_by_two_owners_stays_independent() -> None:
    alice = _agent()
    bob = _agent("bob")
    facts = (InstitutionalFact("trade", "owes", "grain"),)
    alice_entry = _entry(alice, facts=facts)
    bob_entry = _entry(bob, facts=facts)
    assert alice_entry.facts == bob_entry.facts
    assert alice_entry.entry_id != bob_entry.entry_id


def test_frame_and_envelope_lineage_are_distinct() -> None:
    provenance = _provenance(
        channel=InstitutionalMemoryChannel.TRANSMISSION,
        declared_root="r_" + "a" * 24,
        declared_parent="p_" + "b" * 24,
        transmission=_transmission(),
    )
    assert provenance.declared_frame_root == "r_" + "a" * 24
    assert provenance.declared_frame_parent == "p_" + "b" * 24
    assert provenance.declared_transmission is not None
    assert (
        provenance.declared_transmission.root_communication_id.value
        != provenance.declared_frame_root
    )
    plain = _provenance(
        channel=InstitutionalMemoryChannel.TRANSMISSION,
        declared_root="r_" + "d" * 24,
        declared_parent="p_none",
    )
    assert plain.declared_transmission is None


def test_selection_validates_owner_and_kind() -> None:
    alice = _agent()
    bob = _agent("bob")
    entry_id = institutional_entry_id(alice, None, 0)
    ignore = InstitutionalMemorySelection(
        owner_id=alice,
        entry_id=entry_id,
        channel_id=None,
        tick=1,
        kind=InstitutionalMemorySelectionKind.IGNORE,
        ignored=True,
    )
    require_owner_institutional_memory_selection(ignore, alice, field_name="selection")
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_institutional_memory_selection(
            ignore, bob, field_name="selection"
        )
    with pytest.raises(TypeError):
        require_owner_institutional_memory_selection(
            object(), alice, field_name="selection"
        )
    with pytest.raises(ValueError, match="invalid_type"):
        InstitutionalMemorySelection(
            owner_id=alice,
            entry_id=entry_id,
            channel_id=None,
            tick=1,
            kind=InstitutionalMemorySelectionKind.IGNORE,
        )
    with pytest.raises(ValueError, match="unexpected_ignored"):
        InstitutionalMemorySelection(
            owner_id=alice,
            entry_id=entry_id,
            channel_id=None,
            tick=1,
            kind=InstitutionalMemorySelectionKind.CONSULT,
            ignored=False,
        )
    with pytest.raises(ValueError, match="invalid_type"):
        InstitutionalMemorySelection(
            owner_id=alice,
            entry_id=entry_id,
            channel_id=None,
            tick=True,
            kind=InstitutionalMemorySelectionKind.CONSULT,
        )


def test_use_receipts_and_cap() -> None:
    alice = _agent()
    ledger = empty_institutional_memory_ledger(alice)
    for index in range(33):
        ledger = append_institutional_memory_use(
            ledger,
            InstitutionalMemoryUse(
                owner_id=alice,
                invocation_id=f"invocation-{index}",
                entry_id=institutional_entry_id(alice, None, index),
                channel_id=None,
                tick=index,
                disposition=InstitutionalMemoryUseDisposition.CONSULTED,
            ),
        )
    assert len(ledger.uses) == 32
    assert ledger.pruned_use_count == 1
    assert ledger.uses[0].invocation_id == "invocation-1"


def test_acquisition_receipts_are_bounded_and_ordered() -> None:
    alice = _agent()
    ledger = empty_institutional_memory_ledger(alice)
    for index in range(258):
        ledger = record_institutional_acquisition_receipt(ledger, f"receipt-{index}")
    assert len(ledger.acquisition_receipt_keys) == 256
    assert ledger.acquisition_receipt_keys[0] == "receipt-2"
    assert ledger.pruned_receipt_count == 2
    unchanged = record_institutional_acquisition_receipt(
        ledger, ledger.acquisition_receipt_keys[0]
    )
    assert unchanged is ledger


def test_ignored_entry_state_is_retained() -> None:
    alice = _agent()
    entry = _entry(alice, ignored=True)
    ledger = InstitutionalMemoryLedger(owner_id=alice, entries=(entry,))
    assert ledger.entries[0].ignored is True
    assert ledger.entries[0].active is True


def test_repr_exposes_counts_and_modes_only() -> None:
    alice = _agent()
    channel = _channel(alice)
    entry = _entry(
        alice,
        channel_id=channel.channel_id,
        facts=(InstitutionalFact("secretlabel", "owes", "hiddenpayload"),),
    )
    ledger = InstitutionalMemoryLedger(
        owner_id=alice, channels=(channel,), entries=(entry,)
    )
    text = f"{entry!r} {ledger!r} {entry.facts[0]!r}"
    assert "secretlabel" not in text
    assert "hiddenpayload" not in text
    assert channel.channel_id not in text
    assert "fact_count=1" in text
    assert "entry_count=1" in text


@settings(max_examples=25, deadline=None)
@given(
    owner=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=20
    ),
    inception=st.text(alphabet="0123456789abcdef", min_size=64, max_size=64),
    ordinal=st.integers(min_value=0, max_value=10_000),
)
def test_identity_is_deterministic(owner: str, inception: str, ordinal: int) -> None:
    agent = AgentId(owner)
    first = institutional_channel_id(
        agent, InstitutionalBindingKind.PROCEDURE, inception
    )
    second = institutional_channel_id(
        agent, InstitutionalBindingKind.PROCEDURE, inception
    )
    assert first == second
    assert institutional_entry_id(agent, first, ordinal) == institutional_entry_id(
        agent, first, ordinal
    )


@settings(max_examples=10, deadline=None)
@given(count=st.integers(min_value=128, max_value=140))
def test_pruning_is_bounded(count: int) -> None:
    alice = _agent()
    channel = _channel(alice)
    ledger = append_institutional_memory_channel(
        empty_institutional_memory_ledger(alice), channel
    )
    for ordinal in range(count):
        ledger = append_institutional_memory_entry(
            ledger,
            _entry(alice, channel_id=channel.channel_id, ordinal=ordinal, tick=ordinal),
        )
    assert len(ledger.entries) == 128
    assert ledger.pruned_entry_count == max(0, count - 128)
    assert len({item.entry_id for item in ledger.entries}) == len(ledger.entries)
