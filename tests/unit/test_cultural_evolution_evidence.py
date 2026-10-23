"""Detached cultural evolution evidence contracts and validation."""

from __future__ import annotations

import math
from typing import Any

import pytest

from agents.cognition import (
    NarrativeLedger,
    TerminologyLedger,
    empty_cultural_feature_ledger,
    empty_practical_knowledge_ledger,
)
from agents.models import AgentId
from analysis.cultural_evolution_evidence import (
    CULTURAL_DIMENSIONS,
    CULTURAL_EVOLUTION_POLICY_VERSION,
    CULTURAL_FEATURE_DIMENSIONS,
    ArchiveKnowledgeState,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    CulturalMeasurement,
    EvidencePointer,
    GroupMembership,
    InventoryBoundary,
    TraitPresence,
    TransmissionEdge,
    build_evidence_registry,
)
from analysis.models import MetricAvailability
from simulation.cultural_evidence import (
    CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER,
    CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF,
    CULTURAL_EVIDENCE_BASIS_FRESH_EMPTY,
    CULTURAL_EVIDENCE_BASIS_RESTORED_LEDGER,
    CULTURAL_EVIDENCE_BASIS_UNAVAILABLE,
    CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
    CULTURAL_EVIDENCE_CHANNEL_NARRATIVES,
    CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE,
    CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY,
    CULTURAL_EVIDENCE_CHANNELS,
    CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
    CULTURAL_EVIDENCE_COVERAGE_DISABLED,
    CULTURAL_EVIDENCE_COVERAGE_MISSING,
    CulturalBoundaryExport,
    CulturalChannelExport,
    CulturalOwnerExport,
)

_OWNER = AgentId("owner-a")
_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64


def _digest(character: str) -> str:
    return character * 64


def _disabled_channel(channel: str) -> CulturalChannelExport:
    return CulturalChannelExport(
        channel=channel,
        enabled=False,
        coverage=CULTURAL_EVIDENCE_COVERAGE_DISABLED,
        basis=CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF,
    )


def _owner_export(
    owner: AgentId = _OWNER,
    *,
    living: bool = True,
    generation: int = 0,
    channels: tuple[CulturalChannelExport, ...] | None = None,
) -> CulturalOwnerExport:
    if channels is None:
        channels = tuple(_disabled_channel(name) for name in CULTURAL_EVIDENCE_CHANNELS)
    return CulturalOwnerExport(
        owner_id=owner,
        generation_index=generation,
        living=living,
        channels=channels,
    )


def _coverage_for(owners: tuple[str, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (owner, dimension, "complete")
        for owner in owners
        for dimension in CULTURAL_DIMENSIONS
    )


def _boundary(
    tick: int,
    owners: tuple[str, ...] = (_OWNER.value,),
    *,
    entries: tuple[TraitPresence, ...] = (),
    generations: dict[str, int] | None = None,
) -> InventoryBoundary:
    return InventoryBoundary(
        boundary_tick=tick,
        living_owner_ids=owners,
        generation_by_owner=(
            {owner: 0 for owner in owners} if generations is None else generations
        ),
        owner_dimension_coverage=_coverage_for(owners),
        entries=entries,
    )


def _measurement(**overrides: Any) -> CulturalMeasurement:
    values: dict[str, Any] = {
        "family": "cultural_trait_dynamics",
        "algorithm_version": "cultural-trait-dynamics@1",
        "policy_version": CULTURAL_EVOLUTION_POLICY_VERSION,
        "measurement_id": "trait_frequency",
        "dimension": "feature:practice",
        "representation": "ledger_carriage",
        "scope": "global",
        "partition_id": None,
        "group_ids": (),
        "population_basis": "eligible_living_owners",
        "denominator_code": "eligible_living_owners",
        "baseline_tick": 0,
        "end_tick": 3,
        "trait_id": "trait:practice:fire",
        "lineage_id": None,
        "subject_id": None,
        "units": "proportion",
        "value": 0.5,
        "numerator": 1.0,
        "denominator": 2.0,
        "availability": MetricAvailability.PRESENT,
        "reason_code": None,
        "coverage_observed": 2,
        "coverage_expected": 2,
        "left_censored": False,
        "right_censored": False,
        "evidence_ids": (_DIGEST_A,),
    }
    values.update(overrides)
    return CulturalMeasurement(**values)


def _pointer(
    *,
    owner: str | AgentId | None = "owner-a",
    boundary: int = 0,
    local_id: str | None = "entry-1",
    digest: str | None = _DIGEST_A,
) -> EvidencePointer:
    owner_token = owner.value if isinstance(owner, AgentId) else owner
    return EvidencePointer(
        run_id="run-1",
        owner_id=owner_token,
        boundary_tick=boundary,
        source_kind="trait_presence",
        local_id=local_id,
        source_revision_digest=digest,
        original_refs=("ref-2", "ref-1"),
    )


def test_enabled_channel_distinguishes_empty_missing_and_restored() -> None:
    fresh = CulturalChannelExport(
        channel=CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
        enabled=True,
        coverage=CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
        basis=CULTURAL_EVIDENCE_BASIS_FRESH_EMPTY,
    )
    assert fresh.ledger is None
    assert fresh.coverage == "complete"

    missing = CulturalChannelExport(
        channel=CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
        enabled=True,
        coverage=CULTURAL_EVIDENCE_COVERAGE_MISSING,
        basis=CULTURAL_EVIDENCE_BASIS_UNAVAILABLE,
    )
    assert missing.coverage == "missing"

    restored = CulturalChannelExport(
        channel=CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
        enabled=True,
        coverage=CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
        basis=CULTURAL_EVIDENCE_BASIS_RESTORED_LEDGER,
        ledger=empty_cultural_feature_ledger(_OWNER),
    )
    assert restored.coverage == "complete"
    assert restored.basis == "restored_ledger"

    carried = CulturalChannelExport(
        channel=CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE,
        enabled=True,
        coverage=CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
        basis=CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER,
        ledger=empty_practical_knowledge_ledger(_OWNER),
    )
    assert carried.basis == "carried_ledger"


def test_enabled_unavailable_is_not_relabelled_fresh_empty() -> None:
    with pytest.raises(ValueError, match="complete_without_ledger"):
        CulturalChannelExport(
            channel=CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
            enabled=True,
            coverage=CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
            basis=CULTURAL_EVIDENCE_BASIS_UNAVAILABLE,
        )
    with pytest.raises(ValueError, match="ledger_requires"):
        CulturalChannelExport(
            channel=CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
            enabled=True,
            coverage=CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
            basis=CULTURAL_EVIDENCE_BASIS_FRESH_EMPTY,
            ledger=empty_cultural_feature_ledger(_OWNER),
        )


def test_disabled_channel_requires_off_basis_and_no_ledger() -> None:
    with pytest.raises(ValueError, match="enabled_channel_cannot_be_disabled"):
        CulturalChannelExport(
            channel=CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
            enabled=True,
            coverage=CULTURAL_EVIDENCE_COVERAGE_DISABLED,
            basis=CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF,
        )
    with pytest.raises(ValueError, match="no_ledger"):
        CulturalChannelExport(
            channel=CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
            enabled=False,
            coverage=CULTURAL_EVIDENCE_COVERAGE_DISABLED,
            basis=CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF,
            ledger=empty_cultural_feature_ledger(_OWNER),
        )
    with pytest.raises(ValueError, match="unknown_channel"):
        _disabled_channel("culture_pack")


def test_owner_export_requires_exact_channels_and_owner_match() -> None:
    with pytest.raises(ValueError, match="channel_count"):
        CulturalOwnerExport(
            owner_id=_OWNER,
            generation_index=0,
            living=True,
            channels=(),
        )
    foreign = empty_cultural_feature_ledger(AgentId("owner-b"))
    channels = tuple(_disabled_channel(name) for name in CULTURAL_EVIDENCE_CHANNELS)
    channels = tuple(
        CulturalChannelExport(
            channel=CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
            enabled=True,
            coverage=CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
            basis=CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER,
            ledger=foreign,
        )
        if item.channel == CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES
        else item
        for item in channels
    )
    with pytest.raises(ValueError, match="owner_mismatch"):
        CulturalOwnerExport(
            owner_id=_OWNER,
            generation_index=0,
            living=True,
            channels=channels,
        )


def test_boundary_export_detaches_and_sorts_owners() -> None:
    owners = [
        _owner_export(AgentId("owner-z")),
        _owner_export(AgentId("owner-a")),
    ]
    frame = CulturalBoundaryExport(
        run_id="run-1", boundary_tick=0, owners=tuple(owners)
    )
    owners.clear()
    assert [owner.owner_id.value for owner in frame.owners] == [
        "owner-a",
        "owner-z",
    ]
    assert "ledger" not in repr(frame)
    with pytest.raises(ValueError, match="duplicate_owner"):
        CulturalBoundaryExport(
            run_id="run-1",
            boundary_tick=0,
            owners=(
                _owner_export(AgentId("owner-a")),
                _owner_export(AgentId("owner-a")),
            ),
        )


def test_ledger_types_are_channel_specific() -> None:
    with pytest.raises(ValueError, match="ledger_type_mismatch"):
        CulturalChannelExport(
            channel=CULTURAL_EVIDENCE_CHANNEL_NARRATIVES,
            enabled=True,
            coverage=CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
            basis=CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER,
            ledger=TerminologyLedger(owner_id=_OWNER),
        )


def test_terminology_and_narrative_ledgers_are_accepted() -> None:
    channels = tuple(
        CulturalChannelExport(
            channel=CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY,
            enabled=True,
            coverage=CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
            basis=CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER,
            ledger=TerminologyLedger(owner_id=_OWNER),
        )
        if item.channel == CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY
        else CulturalChannelExport(
            channel=CULTURAL_EVIDENCE_CHANNEL_NARRATIVES,
            enabled=True,
            coverage=CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
            basis=CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER,
            ledger=NarrativeLedger(owner_id=_OWNER),
        )
        if item.channel == CULTURAL_EVIDENCE_CHANNEL_NARRATIVES
        else item
        for item in tuple(
            _disabled_channel(name) for name in CULTURAL_EVIDENCE_CHANNELS
        )
    )
    export = _owner_export(channels=channels)
    assert len(export.channels) == 4


def test_dimensions_are_namespaced_and_closed() -> None:
    assert set(CULTURAL_FEATURE_DIMENSIONS) == {
        "feature:practice",
        "feature:narrative_element",
        "feature:term",
        "feature:production_technique",
        "feature:social_expectation",
        "feature:symbolic_association",
    }
    with pytest.raises(ValueError, match="unknown_value"):
        TraitPresence(
            owner_id="owner-a",
            local_entry_id="entry-1",
            dimension="term",
            content_digest=_DIGEST_A,
        )


def test_digests_must_be_full_sha256_not_audit_prefixes() -> None:
    with pytest.raises(ValueError, match="invalid_digest"):
        TraitPresence(
            owner_id="owner-a",
            local_entry_id="entry-1",
            dimension="feature:term",
            content_digest="abcd1234",
        )
    with pytest.raises(ValueError, match="invalid_digest"):
        _pointer(digest="ABCD" + "a" * 60)
    first = _pointer(digest=_DIGEST_A)
    second = _pointer(digest=_DIGEST_B)
    assert first.pointer_id != second.pointer_id
    assert first.pointer_id == _pointer(digest=_DIGEST_A).pointer_id


def test_trait_presence_detaches_and_hides_digest_in_repr() -> None:
    parents = ["parent-2", "parent-1"]
    presence = TraitPresence(
        owner_id="owner-a",
        local_entry_id="entry-1",
        dimension="narrative",
        content_digest=_DIGEST_A,
        lineage_key="lineage-1",
        acquisition_tick=2,
        parent_refs=tuple(parents),
        source_refs=["source-1"],
    )
    parents.append("parent-3")
    assert presence.parent_refs == ("parent-1", "parent-2")
    assert _DIGEST_A not in repr(presence)
    assert "owner-a" in repr(presence)


def test_inventory_boundary_rejects_future_and_foreign_entries() -> None:
    with pytest.raises(ValueError, match="future_evidence"):
        _boundary(
            2,
            entries=(
                TraitPresence(
                    owner_id="owner-a",
                    local_entry_id="entry-1",
                    dimension="feature:practice",
                    content_digest=_DIGEST_A,
                    acquisition_tick=3,
                ),
            ),
        )
    with pytest.raises(ValueError, match="owner_not_living"):
        _boundary(
            2,
            entries=(
                TraitPresence(
                    owner_id="owner-b",
                    local_entry_id="entry-1",
                    dimension="feature:practice",
                    content_digest=_DIGEST_A,
                ),
            ),
        )
    with pytest.raises(ValueError, match="roster_mismatch"):
        InventoryBoundary(
            boundary_tick=0,
            living_owner_ids=("owner-a",),
            generation_by_owner={"owner-b": 0},
            owner_dimension_coverage=_coverage_for(("owner-a",)),
            entries=(),
        )
    with pytest.raises(ValueError, match="incomplete_matrix"):
        InventoryBoundary(
            boundary_tick=0,
            living_owner_ids=("owner-a",),
            generation_by_owner={"owner-a": 0},
            owner_dimension_coverage=(),
            entries=(),
        )


def test_empty_population_is_an_explicit_boundary() -> None:
    empty = InventoryBoundary(
        boundary_tick=0,
        living_owner_ids=(),
        generation_by_owner={},
        owner_dimension_coverage=(),
        entries=(),
    )
    assert empty.living_owner_ids == ()
    assert empty.entries == ()


def test_boundary_detaches_generation_mapping() -> None:
    generations = {"owner-a": 0}
    boundary = _boundary(0, generations=generations)
    generations["owner-a"] = 9
    assert boundary.generation_by_owner["owner-a"] == 0


def test_negative_and_boolean_ticks_are_rejected() -> None:
    with pytest.raises(ValueError):
        _boundary(-1)
    with pytest.raises(ValueError):
        _boundary(True)  # type: ignore[arg-type]


def test_measurement_rejects_nonfinite_values_and_bool_counts() -> None:
    with pytest.raises(ValueError, match="not_finite"):
        _measurement(value=math.nan)
    with pytest.raises(ValueError, match="not_finite"):
        _measurement(numerator=math.inf)
    with pytest.raises(ValueError):
        _measurement(coverage_observed=True)
    with pytest.raises(ValueError, match="exceeds_expected"):
        _measurement(coverage_observed=3, coverage_expected=2)


def test_measurement_units_and_scope_codes_fail_closed() -> None:
    with pytest.raises(ValueError, match="unknown_value"):
        _measurement(units="percent")
    with pytest.raises(ValueError, match="unknown_value"):
        _measurement(dimension="term")
    with pytest.raises(ValueError, match="unknown_value"):
        _measurement(population_basis="culture_score")
    with pytest.raises(ValueError, match="scope_mismatch"):
        _measurement(scope="group", group_ids=())
    with pytest.raises(ValueError, match="scope_mismatch"):
        _measurement(scope="global", group_ids=("g1",))
    with pytest.raises(ValueError, match="too_many_groups"):
        _measurement(scope="group_pair", group_ids=("g1", "g2", "g3"))


def test_measurement_row_identity_is_selector_based() -> None:
    base = _measurement()
    same = _measurement(value=0.75, numerator=3.0, coverage_observed=1)
    assert base.row_id == same.row_id
    assert base.measurement_id == same.measurement_id
    changed_subject = _measurement(subject_id="owner-a")
    assert base.row_id != changed_subject.row_id
    assert base.measurement_id == changed_subject.measurement_id
    changed_end = _measurement(end_tick=4)
    assert base.row_id != changed_end.row_id


def test_measurement_payload_round_trip_and_exact_fields() -> None:
    measurement = _measurement(
        units="nats",
        value=0.3,
        numerator=None,
        denominator=None,
        coverage_expected=None,
        reason_code="entropy_only",
        left_censored=True,
    )
    payload = measurement.to_payload()
    assert set(payload) == {
        "row_id",
        "measurement_id",
        "dimension",
        "representation",
        "scope",
        "partition_id",
        "group_ids",
        "population_basis",
        "denominator_code",
        "baseline_tick",
        "end_tick",
        "trait_id",
        "lineage_id",
        "subject_id",
        "units",
        "value",
        "numerator",
        "denominator",
        "availability",
        "reason_code",
        "coverage_observed",
        "coverage_expected",
        "left_censored",
        "right_censored",
        "evidence_ids",
    }
    restored = CulturalMeasurement.from_payload(
        payload,
        family=measurement.family,
        algorithm_version=measurement.algorithm_version,
        policy_version=measurement.policy_version,
    )
    assert restored == measurement
    assert restored.to_payload() == payload
    with pytest.raises(ValueError, match="key_set_mismatch"):
        CulturalMeasurement.from_payload(
            {**payload, "extra": 1},
            family=measurement.family,
            algorithm_version=measurement.algorithm_version,
            policy_version=measurement.policy_version,
        )
    with pytest.raises(ValueError, match="cultural_evidence_conflict"):
        CulturalMeasurement.from_payload(
            {**payload, "row_id": _DIGEST_B},
            family=measurement.family,
            algorithm_version=measurement.algorithm_version,
            policy_version=measurement.policy_version,
        )


def test_measurement_repr_is_payload_free() -> None:
    measurement = _measurement()
    rendered = repr(measurement)
    assert _DIGEST_A not in rendered
    assert "trait_frequency" in rendered


def test_transmission_edge_resolution_rules() -> None:
    resolved = TransmissionEdge(
        edge_id="edge-1",
        source_owner_id="owner-b",
        receiver_owner_id="owner-a",
        source_local_id="entry-b",
        receiver_local_id="entry-a",
        acquisition_boundary=1,
        modality="teaching",
        attribution_status="resolved",
        generation_class="intergenerational",
        kin_vertical=True,
        source_digest=_DIGEST_A,
        target_digest=_DIGEST_A,
        evidence_ids=(_DIGEST_B,),
    )
    assert resolved.kin_vertical
    with pytest.raises(ValueError, match="resolved_requires_source"):
        TransmissionEdge(
            edge_id="edge-2",
            source_owner_id=None,
            receiver_owner_id="owner-a",
            source_local_id=None,
            receiver_local_id="entry-a",
            acquisition_boundary=1,
            modality="teaching",
            attribution_status="resolved",
            generation_class="unknown",
            kin_vertical=False,
        )
    with pytest.raises(ValueError, match="unresolved_must_not_name_source"):
        TransmissionEdge(
            edge_id="edge-3",
            source_owner_id="owner-b",
            receiver_owner_id="owner-a",
            source_local_id="entry-b",
            receiver_local_id="entry-a",
            acquisition_boundary=1,
            modality="teaching",
            attribution_status="ambiguous_source",
            generation_class="unknown",
            kin_vertical=False,
        )
    with pytest.raises(ValueError, match="requires_intergenerational"):
        TransmissionEdge(
            edge_id="edge-4",
            source_owner_id="owner-b",
            receiver_owner_id="owner-a",
            source_local_id="entry-b",
            receiver_local_id="entry-a",
            acquisition_boundary=1,
            modality="teaching",
            attribution_status="resolved",
            generation_class="horizontal",
            kin_vertical=True,
        )


def test_group_membership_and_archive_state_validate_ids() -> None:
    membership = GroupMembership(
        boundary_tick=1,
        owner_id="owner-a",
        group_id="region:north",
        basis_id="region",
        basis_version="regions-v1",
        evidence_ids=(_DIGEST_A,),
    )
    assert membership.group_id == "region:north"
    state = ArchiveKnowledgeState(
        boundary_tick=2,
        subject_id="record:1",
        content_digest=_DIGEST_A,
        record_present=False,
        holder_owner_ids=("owner-a",),
    )
    assert state.record_present is False
    assert _DIGEST_A not in repr(state)


def test_window_resolution_never_rebases() -> None:
    default = CulturalAnalysisWindow()
    assert default.baseline_boundary == 0
    assert default.resolve(7) == (0, 7)
    explicit = CulturalAnalysisWindow(baseline_boundary=2, end_boundary=5)
    assert explicit.resolve(9) == (2, 5)
    assert explicit.endpoint_reached(4) is False
    assert explicit.endpoint_reached(5) is True
    with pytest.raises(ValueError):
        CulturalAnalysisWindow(baseline_boundary=5, end_boundary=5)
    with pytest.raises(ValueError, match="after_last_finalized"):
        explicit.resolve(1)


def test_inputs_deduplicate_identical_rows_and_reject_conflicts() -> None:
    pointer = _pointer()
    inputs = CulturalEvolutionInputs(
        run_id="run-1",
        source_revision="rev-1",
        window=CulturalAnalysisWindow(end_boundary=3),
        boundaries=(_boundary(0), _boundary(1)),
        evidence_pointers=(pointer, _pointer()),
    )
    assert len(inputs.evidence_pointers) == 1
    registry = build_evidence_registry((pointer, _pointer()))
    assert list(registry) == [pointer.pointer_id]

    with pytest.raises(ValueError, match="cultural_evidence_conflict"):
        CulturalEvolutionInputs(
            run_id="run-1",
            source_revision="rev-1",
            window=CulturalAnalysisWindow(end_boundary=3),
            boundaries=(_boundary(0), _boundary(1)),
            evidence_pointers=(
                pointer,
                EvidencePointer(
                    run_id="run-1",
                    owner_id="owner-a",
                    boundary_tick=0,
                    source_kind="trait_presence",
                    local_id="entry-1",
                    source_revision_digest=_DIGEST_A,
                    original_refs=("ref-9",),
                ),
            ),
        )


def test_inputs_reject_future_evidence_and_wrong_run() -> None:
    with pytest.raises(ValueError, match="future_evidence"):
        CulturalEvolutionInputs(
            run_id="run-1",
            source_revision="rev-1",
            window=CulturalAnalysisWindow(end_boundary=1),
            boundaries=(_boundary(2),),
        )
    with pytest.raises(ValueError, match="future_evidence"):
        CulturalEvolutionInputs(
            run_id="run-1",
            source_revision="rev-1",
            window=CulturalAnalysisWindow(end_boundary=1),
            evidence_pointers=(_pointer(boundary=2),),
        )
    with pytest.raises(ValueError, match="run_mismatch"):
        CulturalEvolutionInputs(
            run_id="run-2",
            source_revision="rev-1",
            window=CulturalAnalysisWindow(),
            evidence_pointers=(_pointer(),),
        )
    with pytest.raises(ValueError, match="future_evidence"):
        CulturalEvolutionInputs(
            run_id="run-1",
            source_revision="rev-1",
            window=CulturalAnalysisWindow(end_boundary=1),
            transmission_edges=(
                TransmissionEdge(
                    edge_id="edge-1",
                    source_owner_id=None,
                    receiver_owner_id="owner-a",
                    source_local_id=None,
                    receiver_local_id="entry-a",
                    acquisition_boundary=2,
                    modality="independent_rediscovery",
                    attribution_status="independent_rediscovery",
                    generation_class="unknown",
                    kin_vertical=False,
                ),
            ),
        )


def test_inputs_policy_and_boundary_interval_fail_closed() -> None:
    with pytest.raises(ValueError, match="unsupported_policy"):
        CulturalEvolutionInputs(
            run_id="run-1",
            source_revision="rev-1",
            window=CulturalAnalysisWindow(),
            policy_version="cultural-evolution.v2",
        )
    with pytest.raises(ValueError, match="unsupported_interval"):
        CulturalEvolutionInputs(
            run_id="run-1",
            source_revision="rev-1",
            window=CulturalAnalysisWindow(),
            expected_boundary_interval=2,
        )


def test_inputs_repr_is_count_only() -> None:
    inputs = CulturalEvolutionInputs(
        run_id="run-1",
        source_revision="rev-1",
        window=CulturalAnalysisWindow(),
        boundaries=(_boundary(0),),
        evidence_pointers=(_pointer(),),
    )
    rendered = repr(inputs)
    assert "run-1" in rendered
    assert "pointer_count=1" in rendered
    assert _DIGEST_A not in rendered
