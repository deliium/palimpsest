"""Normalization and canonical evidence codec for cultural evolution."""

from __future__ import annotations

import json

import pytest

from agents.cognition import (
    CulturalFeatureKindId,
    CulturalTransmissionChannelId,
    NarrativeLedger,
    SubjectiveCulturalBelief,
    TerminologyLedger,
    empty_cultural_feature_ledger,
    empty_practical_knowledge_ledger,
)
from agents.models import AgentId
from analysis.cultural_evolution_evidence import (
    CULTURAL_EVOLUTION_POLICY_VERSION,
    CULTURAL_FEATURE_DIMENSIONS,
    CulturalAnalysisWindow,
    TraitPresence,
)
from analysis.models import MetricAvailability
from experiments.cultural_evidence import (
    cultural_evolution_inputs_from_capture,
)
from experiments.cultural_evidence_serialization import (
    CULTURAL_EVOLUTION_EVIDENCE_SCHEMA_VERSION,
    CulturalEvidenceSerializationError,
    decode_cultural_evolution_evidence,
    encode_cultural_evolution_evidence,
    evidence_digest,
)
from simulation.cultural_evidence import (
    CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER,
    CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF,
    CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
    CULTURAL_EVIDENCE_CHANNEL_NARRATIVES,
    CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE,
    CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY,
    CULTURAL_EVIDENCE_CHANNELS,
    CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
    CULTURAL_EVIDENCE_COVERAGE_DISABLED,
    CulturalBoundaryExport,
    CulturalCaptureStatus,
    CulturalChannelExport,
    CulturalOwnerExport,
)
from tests.unit.test_cultural_evolution_evidence import _coverage_for

_TEACHER = AgentId("teacher")
_LEARNER = AgentId("learner")


def _empty_ledgers(owner: AgentId) -> dict[str, object | None]:
    return {
        CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES: (
            empty_cultural_feature_ledger(owner)
        ),
        CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY: TerminologyLedger(owner_id=owner),
        CULTURAL_EVIDENCE_CHANNEL_NARRATIVES: NarrativeLedger(owner_id=owner),
        CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE: (
            empty_practical_knowledge_ledger(owner)
        ),
    }


def _channel(
    name: str, ledger: object | None, *, enabled: bool = True
) -> CulturalChannelExport:
    if not enabled:
        return CulturalChannelExport(
            channel=name,
            enabled=False,
            coverage=CULTURAL_EVIDENCE_COVERAGE_DISABLED,
            basis=CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF,
        )
    return CulturalChannelExport(
        channel=name,
        enabled=True,
        coverage=CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
        basis=CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER,
        ledger=ledger,
    )


def _owner(
    owner: AgentId,
    generation: int,
    ledgers: dict[str, object | None],
) -> CulturalOwnerExport:
    return CulturalOwnerExport(
        owner_id=owner,
        generation_index=generation,
        living=True,
        channels=tuple(
            _channel(name, ledgers.get(name)) for name in CULTURAL_EVIDENCE_CHANNELS
        ),
    )


def _practical_entry(
    *,
    owner: AgentId,
    entry_id: str,
    content_key: str,
    fingerprint: tuple[str, ...],
    acquired_tick: int,
    source: AgentId | None = None,
) -> object:
    from agents.cognition.practical_knowledge import (
        KnowledgeTransmissionOrigin,
        PracticalKnowledgeKind,
        SubjectivePracticalKnowledge,
    )

    return SubjectivePracticalKnowledge(
        entry_id=entry_id,
        owner_id=owner,
        kind=PracticalKnowledgeKind.CRAFTING_PROCESS,
        content_key=content_key,
        content_fingerprint=fingerprint,
        origin=(
            KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY
            if source is None
            else KnowledgeTransmissionOrigin.TEACHING
        ),
        parent_entry_ids=(),
        lineage_root_id=f"root:{content_key}",
        hop_index=0 if source is None else 1,
        mutated=False,
        evidence_refs=() if source is None else ("evidence:teaching",),
        acquired_tick=acquired_tick,
        active=True,
        capability_anchor="crafting",
        source_agent_id=source,
        teacher_agent_id=source,
    )


def _practical_ledger(owner: AgentId, entries: tuple[object, ...]) -> object:
    from agents.cognition.practical_knowledge import PracticalKnowledgeLedger

    return PracticalKnowledgeLedger(owner_id=owner, entries=entries)


def _frames() -> tuple[CulturalBoundaryExport, ...]:
    teacher_ledger = _practical_ledger(
        _TEACHER,
        (
            _practical_entry(
                owner=_TEACHER,
                entry_id="pk-teacher",
                content_key="tech:fire",
                fingerprint=("fp-fire",),
                acquired_tick=0,
            ),
        ),
    )
    learner_empty = _empty_ledgers(_LEARNER)
    teacher_ledgers = _empty_ledgers(_TEACHER)
    teacher_ledgers[CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE] = teacher_ledger
    boundary_0 = CulturalBoundaryExport(
        run_id="run-normalize",
        boundary_tick=0,
        owners=(
            _owner(_TEACHER, 0, teacher_ledgers),
            _owner(_LEARNER, 1, learner_empty),
        ),
    )
    learner_ledgers = _empty_ledgers(_LEARNER)
    learner_ledgers[CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE] = _practical_ledger(
        _LEARNER,
        (
            _practical_entry(
                owner=_LEARNER,
                entry_id="pk-learner",
                content_key="tech:fire",
                fingerprint=("fp-fire",),
                acquired_tick=0,
                source=_TEACHER,
            ),
        ),
    )
    boundary_1 = CulturalBoundaryExport(
        run_id="run-normalize",
        boundary_tick=1,
        owners=(
            _owner(_TEACHER, 0, teacher_ledgers),
            _owner(_LEARNER, 1, learner_ledgers),
        ),
    )
    return (boundary_0, boundary_1)


def _inputs():
    return cultural_evolution_inputs_from_capture(
        _frames(),
        run_id="run-normalize",
        source_revision="rev-normalize",
        window=CulturalAnalysisWindow(end_boundary=1),
        parent_child_edges=(("teacher", "learner"),),
    )


def test_normalization_preserves_dimensions_and_owner_provenance() -> None:
    inputs = _inputs()
    assert len(inputs.boundaries) == 2
    assert inputs.boundaries[1].entries[0].dimension == "technology"
    assert inputs.boundaries[1].entries[0].owner_id == "learner"
    assert inputs.evidence_pointers
    assert all(
        pointer.run_id == "run-normalize" for pointer in inputs.evidence_pointers
    )
    assert {row.dimension for row in inputs.boundaries[0].entries} == {"technology"}


def test_explicit_teacher_edge_is_intergenerational_and_resolved() -> None:
    inputs = _inputs()
    assert len(inputs.transmission_edges) == 1
    edge = inputs.transmission_edges[0]
    assert edge.source_owner_id == "teacher"
    assert edge.receiver_owner_id == "learner"
    assert edge.attribution_status == "resolved"
    assert edge.generation_class == "intergenerational"
    assert edge.kin_vertical is True
    assert edge.source_digest == edge.target_digest
    assert edge.acquisition_boundary == 1


def test_generic_culture_without_explicit_source_has_no_edge() -> None:
    belief = SubjectiveCulturalBelief(
        belief_id="belief-1",
        owner_agent_id=_LEARNER,
        feature_kind=CulturalFeatureKindId.PRACTICE,
        content_key="practice:fire",
        content_fingerprint="fp-fire",
        channel=CulturalTransmissionChannelId.INDEPENDENT_REDISCOVERY,
        confidence=0.5,
        parent_belief_ids=(),
        hop_index=0,
        mutated=False,
        recombined=False,
        evidence_refs=(),
        acquired_tick=0,
        last_updated_tick=0,
    )
    from agents.cognition import CulturalFeatureLedger

    ledgers = _empty_ledgers(_LEARNER)
    ledgers[CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES] = CulturalFeatureLedger(
        owner_id=_LEARNER, beliefs=(belief,)
    )
    frame = CulturalBoundaryExport(
        run_id="run-normalize",
        boundary_tick=0,
        owners=(_owner(_LEARNER, 0, ledgers),),
    )
    inputs = cultural_evolution_inputs_from_capture(
        (frame,),
        run_id="run-normalize",
        source_revision="rev-normalize",
        window=CulturalAnalysisWindow(end_boundary=1),
    )
    assert inputs.transmission_edges == ()
    rows = inputs.boundaries[0].entries
    assert len(rows) == 1
    assert rows[0].dimension == "feature:practice"
    assert rows[0].local_entry_id == "belief-1"


def test_vocabulary_hashes_label_token_not_referent() -> None:
    from agents.cognition import (
        LabelBinding,
        NamingReferentKind,
        NamingStatus,
        label_binding_id,
    )

    binding = LabelBinding(
        binding_id=label_binding_id(_LEARNER, NamingReferentKind.LOCATION, "river"),
        owner_id=_LEARNER,
        label_token="river",
        referent_kind=NamingReferentKind.LOCATION,
        status=NamingStatus.ACTIVE,
        strength=0.5,
    )
    ledgers = _empty_ledgers(_LEARNER)
    ledgers[CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY] = TerminologyLedger(
        owner_id=_LEARNER, bindings=(binding,)
    )
    frame = CulturalBoundaryExport(
        run_id="run-normalize",
        boundary_tick=0,
        owners=(_owner(_LEARNER, 0, ledgers),),
    )
    inputs = cultural_evolution_inputs_from_capture(
        (frame,),
        run_id="run-normalize",
        source_revision="rev-normalize",
        window=CulturalAnalysisWindow(end_boundary=1),
    )
    row = inputs.boundaries[0].entries[0]
    assert row.dimension == "vocabulary"
    assert row.local_entry_id == binding.binding_id
    assert row.content_digest != "river"


def test_canonical_evidence_round_trip_and_digest_stability() -> None:
    inputs = _inputs()
    status = CulturalCaptureStatus(active=True, failed=False)
    encoded = encode_cultural_evolution_evidence(
        inputs,
        config_fingerprint="config-1",
        capture_options={"max_frames": 10},
        capture_status=status,
    )
    envelope = decode_cultural_evolution_evidence(encoded)
    assert envelope.inputs == inputs
    assert envelope.capture_status == status
    assert envelope.digest == evidence_digest(
        inputs,
        config_fingerprint="config-1",
        capture_options={"max_frames": 10},
        capture_status=status,
    )
    assert decode_cultural_evolution_evidence(encoded).digest == envelope.digest
    payload = json.loads(encoded.decode("utf-8"))
    assert payload["schema_version"] == CULTURAL_EVOLUTION_EVIDENCE_SCHEMA_VERSION
    assert payload["digest"] == envelope.digest


def test_evidence_digest_changes_with_scientific_content() -> None:
    inputs = _inputs()
    status = CulturalCaptureStatus(active=True, failed=False)
    first = evidence_digest(
        inputs,
        config_fingerprint="config-1",
        capture_options={},
        capture_status=status,
    )
    changed_row = TraitPresence(
        owner_id="learner",
        local_entry_id="extra",
        dimension="technology",
        content_digest="c" * 64,
    )
    from dataclasses import replace

    boundary = replace(
        inputs.boundaries[1],
        entries=(*inputs.boundaries[1].entries, changed_row),
    )
    changed = replace(inputs, boundaries=(inputs.boundaries[0], boundary))
    second = evidence_digest(
        changed,
        config_fingerprint="config-1",
        capture_options={},
        capture_status=status,
    )
    assert first != second


def test_codec_rejects_duplicate_keys_and_digest_mismatch() -> None:
    inputs = _inputs()
    encoded = encode_cultural_evolution_evidence(
        inputs,
        config_fingerprint="config-1",
        capture_options={},
        capture_status=CulturalCaptureStatus(active=True, failed=False),
    )
    text = encoded.decode("utf-8")
    duplicated = text.replace(
        '"schema_version":"cultural-evolution-evidence-v1"',
        '"schema_version":"cultural-evolution-evidence-v1",'
        '"schema_version":"cultural-evolution-evidence-v1"',
        1,
    )
    with pytest.raises(CulturalEvidenceSerializationError, match="duplicate_key"):
        decode_cultural_evolution_evidence(duplicated.encode("utf-8"))
    payload = json.loads(text)
    payload["gaps"] = ["tampered"]
    with pytest.raises(CulturalEvidenceSerializationError, match="digest_mismatch"):
        decode_cultural_evolution_evidence(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )


def test_codec_rejects_unknown_and_missing_keys() -> None:
    inputs = _inputs()
    encoded = encode_cultural_evolution_evidence(
        inputs,
        config_fingerprint="config-1",
        capture_options={},
        capture_status=CulturalCaptureStatus(active=True, failed=False),
    )
    payload = json.loads(encoded)
    payload["extra"] = 1
    with pytest.raises(CulturalEvidenceSerializationError, match="key_set_mismatch"):
        decode_cultural_evolution_evidence(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )


def test_measurement_schema_is_independent_from_evidence_codec() -> None:
    from analysis.cultural_evolution_evidence import CulturalMeasurement

    measurement = CulturalMeasurement(
        family="cultural_trait_dynamics",
        algorithm_version="cultural-trait-dynamics@1",
        policy_version=CULTURAL_EVOLUTION_POLICY_VERSION,
        measurement_id="trait_frequency",
        dimension="technology",
        representation="practical_content_key",
        scope="global",
        partition_id=None,
        group_ids=(),
        population_basis="eligible_living_owners",
        denominator_code="eligible_living_owners",
        baseline_tick=0,
        end_tick=1,
        trait_id=None,
        lineage_id=None,
        subject_id=None,
        units="proportion",
        value=0.5,
        numerator=1.0,
        denominator=2.0,
        availability=MetricAvailability.PRESENT,
        reason_code=None,
        coverage_observed=2,
        coverage_expected=2,
        left_censored=False,
        right_censored=False,
        evidence_ids=(),
    )
    assert measurement.row_id
    assert len(CULTURAL_FEATURE_DIMENSIONS) == 6
    assert _coverage_for(("learner",))[0][1] in CULTURAL_FEATURE_DIMENSIONS
