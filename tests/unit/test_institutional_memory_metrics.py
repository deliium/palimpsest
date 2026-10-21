"""Detached institutional-memory metric known answers and availability."""

from __future__ import annotations

from agents.cognition.institutional_memory import (
    InstitutionalBindingKind,
    InstitutionalChannel,
    InstitutionalFact,
    InstitutionalMemoryChannel,
    InstitutionalMemoryEntry,
    InstitutionalMemoryLedger,
    InstitutionalMemoryUse,
    InstitutionalMemoryUseDisposition,
    InstitutionalProvenance,
    institutional_channel_id,
    institutional_entry_id,
)
from agents.models import AgentId
from analysis.institutional_memory import (
    InstitutionalCarrierRow,
    InstitutionalIdentityRow,
    compute_institutional_memory_continuity,
    compute_institutional_memory_provenance,
    harvest_institutional_memory_rows,
)
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    metric_specification,
)
from world.identifiers import EntityId

_OWNER = AgentId("alice")
_INCEPTION = "a" * 64
_CONTEXT = "c" * 16


def _ledger() -> InstitutionalMemoryLedger:
    channel_id = institutional_channel_id(
        _OWNER, InstitutionalBindingKind.ROLE, _INCEPTION
    )
    channel = InstitutionalChannel(
        owner_id=_OWNER,
        channel_id=channel_id,
        binding_kind=InstitutionalBindingKind.ROLE,
        inception_reference=_INCEPTION,
        current_local_reference="b" * 64,
        public_function_token="exchange_aaaaaaaa",
        context_digest=_CONTEXT,
        first_tick=1,
        last_tick=2,
        revision_count=0,
    )
    record = InstitutionalMemoryEntry(
        owner_id=_OWNER,
        entry_id=institutional_entry_id(_OWNER, channel_id, 0),
        channel_id=channel_id,
        ordinal=0,
        revision=0,
        facts=(InstitutionalFact("trade", "owes", "grain"),),
        declared_fact_count=1,
        acquisition_tick=1,
        confidence=0.8,
        distorted=False,
        partial=False,
        active=True,
        ignored=False,
        provenance=(
            InstitutionalProvenance(
                immediate_channel=InstitutionalMemoryChannel.RECORD,
                artifact_id=EntityId("record-1"),
                artifact_revision=0,
                artifact_root_id=EntityId("record-1"),
                occurrence_ref="event-1",
            ),
        ),
    )
    transmitted = InstitutionalMemoryEntry(
        owner_id=_OWNER,
        entry_id=institutional_entry_id(_OWNER, channel_id, 1),
        channel_id=channel_id,
        ordinal=1,
        revision=0,
        facts=(InstitutionalFact("trade", "owes", "salt"),),
        declared_fact_count=2,
        acquisition_tick=2,
        confidence=0.3,
        distorted=False,
        partial=True,
        active=True,
        ignored=True,
        provenance=(
            InstitutionalProvenance(
                immediate_channel=InstitutionalMemoryChannel.TRANSMISSION,
                declared_frame_root="r_" + "d" * 24,
                declared_frame_parent="p_none",
            ),
        ),
    )
    use = InstitutionalMemoryUse(
        owner_id=_OWNER,
        invocation_id="inv:consulted",
        entry_id=record.entry_id,
        channel_id=channel_id,
        tick=2,
        disposition=InstitutionalMemoryUseDisposition.CONSULTED,
    )
    return InstitutionalMemoryLedger(
        owner_id=_OWNER,
        channels=(channel,),
        entries=(record, transmitted),
        uses=(use,),
    )


def test_harvest_preserves_entry_and_use_fields() -> None:
    snapshots = harvest_institutional_memory_rows((_ledger(),))
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.owner_id == "alice"
    assert snapshot.channel_count == 1
    assert snapshot.consulted_entry_count == 1
    assert snapshot.entries[0].acquisition_channel == "record"
    assert snapshot.entries[0].artifact_revision == 0
    assert snapshot.entries[1].declared_root == "r_" + "d" * 24
    assert snapshot.entries[1].partial is True


def test_continuity_known_answer() -> None:
    snapshots = harvest_institutional_memory_rows((_ledger(),))
    document = compute_institutional_memory_continuity(
        snapshots, run_id="run", input_revision="rev", tick=3
    )
    assert document.metric_family == "institutional_memory_continuity"
    assert document.values["enabled_owner_count"] == 1
    assert document.values["bound_channel_count"] == 1
    assert document.values["entry_count"] == 2
    assert document.values["record_acquisition_count"] == 1
    assert document.values["transmission_acquisition_count"] == 1
    assert document.values["teaching_acquisition_count"] == 0
    assert document.values["partial_entry_count"] == 1
    assert document.values["ignored_entry_count"] == 1
    assert document.values["consulted_entry_count"] == 1
    assert document.values["partial_coverage"] is True


def test_provenance_separates_observed_and_declared_edges() -> None:
    snapshots = harvest_institutional_memory_rows((_ledger(),))
    document = compute_institutional_memory_provenance(
        snapshots,
        run_id="run",
        input_revision="rev",
        tick=3,
        carrier_rows=(
            InstitutionalCarrierRow(
                run_id="run",
                event_id="event-1",
                tick=1,
                sequence=1,
                kind="artifact_created",
                actor_entity_id="record-author-body",
                artifact_id="record-1",
                content_revision=0,
            ),
        ),
        identity_rows=(
            InstitutionalIdentityRow("alice", "record-author-body", 0),
        ),
    )
    assert document.values["entry_count"] == 2
    assert document.values["observed_carrier_edge_count"] == 1
    assert document.values["declared_only_edge_count"] == 1
    assert document.values["independent_root_count"] == 1
    assert document.values["conflicting_claim_count"] == 1


def test_none_and_empty_inputs_are_absent() -> None:
    continuity = compute_institutional_memory_continuity(
        None, run_id="run", input_revision="rev"
    )
    provenance = compute_institutional_memory_provenance(
        (), run_id="run", input_revision="rev"
    )
    assert continuity.availability.value == "absent"
    assert provenance.availability.value == "absent"


def test_specifications_are_registered_exactly() -> None:
    assert METRIC_FAMILY_COUNT == 126
    continuity = metric_specification(MetricFamilyId.INSTITUTIONAL_MEMORY_CONTINUITY)
    provenance = metric_specification(MetricFamilyId.INSTITUTIONAL_MEMORY_PROVENANCE)
    assert len(continuity.value_keys) == 15
    assert len(provenance.value_keys) == 10
