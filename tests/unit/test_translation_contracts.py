"""Owner-scoped translation contracts and validation."""

from __future__ import annotations

import hashlib

import pytest

from agents.cognition.configuration import (
    CognitionSemanticNamingMode,
    CognitionTranslationMode,
)
from agents.cognition.semantic_naming import (
    LabelBinding,
    NamingCandidate,
    NamingReferentKind,
    NamingStatus,
    TerminologyLedger,
    label_binding_id,
)
from agents.cognition.translation import (
    TRANSLATION_POLICY_VERSION,
    TranslationApplication,
    TranslationApplicationKind,
    TranslationApplicationOutcome,
    TranslationEvidenceChannel,
    TranslationEvidenceItem,
    TranslationFit,
    TranslationLedger,
    TranslationMapping,
    TranslationMappingStatus,
    TranslationMode,
    TranslationPolicy,
    TranslationSourceKind,
    TranslationStrengthBand,
    TranslationTarget,
    default_translation_policy,
    empty_translation_ledger,
    require_owner_translation,
    translation_mapping_id,
    translation_source_digest,
    translation_strength_band,
)
from agents.models import AgentId
from simulation.runner_models import TranslationMode as RunnerTranslationMode


def _agent(value: str = "alice") -> AgentId:
    return AgentId(value)


def _binding(
    owner: AgentId,
    token: str,
    *,
    kind: NamingReferentKind = NamingReferentKind.LOCATION,
    entity_id: str = "loc-1",
    status: NamingStatus = NamingStatus.ACTIVE,
    strength: float = 0.6,
) -> LabelBinding:
    return LabelBinding(
        binding_id=label_binding_id(owner, kind, token),
        owner_id=owner,
        label_token=token,
        referent_kind=kind,
        status=status,
        strength=strength,
        candidates=(
            NamingCandidate(kind=kind, entity_id=entity_id, confidence=0.7),
        ),
        evidence_count=2,
    )


def _terminology(
    owner: AgentId, *bindings: LabelBinding
) -> TerminologyLedger:
    return TerminologyLedger(owner_id=owner, bindings=tuple(bindings))


def _target(binding: LabelBinding, weight: float = 0.5) -> TranslationTarget:
    return TranslationTarget(
        binding_id=binding.binding_id,
        label_token=binding.label_token,
        referent_kind=binding.referent_kind,
        weight=weight,
    )


def _mapping(
    owner: AgentId,
    *targets: TranslationTarget,
    source: str = "foreign_a",
    status: TranslationMappingStatus = TranslationMappingStatus.CANDIDATE,
    fit: TranslationFit = TranslationFit.RESOLVED,
    strength: float = 0.5,
) -> TranslationMapping:
    digest = translation_source_digest(source)
    return TranslationMapping(
        mapping_id=translation_mapping_id(owner, digest),
        owner_id=owner,
        source_token=source,
        source_digest=digest,
        source_kind=TranslationSourceKind.LABEL,
        targets=tuple(targets),
        status=status,
        fit=fit,
        strength=strength,
        evidence_count=0,
        first_tick=1,
        last_tick=1,
    )


def test_policy_locks_constants_and_modes_match() -> None:
    policy = default_translation_policy()
    assert policy.version == TRANSLATION_POLICY_VERSION == "translation.v1"
    assert policy.active_strength == 0.45
    assert policy.retire_strength == 0.15
    assert policy.decay == 0.04
    assert policy.promotion_count == 3
    assert policy.max_mappings == 16
    assert policy.max_targets == 3
    assert policy.max_evidence == 32
    assert policy.max_applications == 32
    assert policy.ambiguity_margin == 0.10
    assert policy.outbound_interval == 4
    assert policy.teaching_window == 8
    assert policy.shared_observation_delta == 0.18
    assert policy.demonstration_delta == 0.14
    assert policy.repeated_interaction_delta == 0.10
    assert policy.teaching_delta == 0.20
    assert policy.artifact_delta == 0.12
    assert policy.context_delta == 0.06
    with pytest.raises(ValueError, match="unsupported_policy"):
        TranslationPolicy(active_strength=0.5)
    assert [mode.value for mode in CognitionTranslationMode] == [
        mode.value for mode in TranslationMode
    ]
    assert [mode.value for mode in RunnerTranslationMode] == [
        mode.value for mode in TranslationMode
    ]
    assert CognitionSemanticNamingMode.DETERMINISTIC.value == "deterministic"


def test_source_digest_and_owner_scoped_mapping_id() -> None:
    owner = _agent()
    digest = translation_source_digest("foreign_a")
    expected = hashlib.sha256(b"translation|foreign_a").hexdigest()[:16]
    assert digest == expected
    assert len(digest) == 16
    assert translation_source_digest("foreign_a") == digest
    alice = translation_mapping_id(owner, digest)
    bob = translation_mapping_id(_agent("bob"), digest)
    assert alice != bob
    assert alice == (
        hashlib.sha256(f"{owner.value}|translation|{digest}".encode()).hexdigest()
    )


def test_mapping_round_trip_and_ambiguous_mapping_is_legal() -> None:
    owner = _agent()
    first = _binding(owner, "own_a", entity_id="loc-1")
    second = _binding(owner, "own_b", entity_id="loc-2")
    mapping = _mapping(
        owner,
        _target(first, 0.5),
        _target(second, 0.4),
        fit=TranslationFit.AMBIGUOUS,
    )
    assert mapping.targets[0].label_token == "own_a"
    assert mapping.fit is TranslationFit.AMBIGUOUS
    ledger = TranslationLedger(owner_id=owner, mappings=(mapping,))
    ledger.validate_against(_terminology(owner, first, second))
    assert ledger.mappings[0].mapping_id == mapping.mapping_id


def test_mapping_with_no_target_must_be_unresolved() -> None:
    owner = _agent()
    with pytest.raises(ValueError, match="empty_targets_require_unresolved"):
        _mapping(owner)
    unresolved = _mapping(owner, fit=TranslationFit.UNRESOLVED)
    assert unresolved.targets == ()
    with pytest.raises(ValueError, match="unresolved_requires_no_targets"):
        _mapping(
            owner,
            _target(_binding(owner, "own_a")),
            fit=TranslationFit.UNRESOLVED,
        )


def test_incorrect_target_is_representable_without_correct_flag() -> None:
    owner = _agent()
    wrong = _binding(owner, "own_a", entity_id="loc-2")
    mapping = _mapping(owner, _target(wrong))
    assert not hasattr(mapping, "correct")
    assert mapping.fit is TranslationFit.RESOLVED


def test_target_validation_rejects_retired_foreign_and_mismatched() -> None:
    owner = _agent()
    retired = _binding(owner, "own_a", status=NamingStatus.RETIRED)
    mapping = _mapping(owner, _target(retired))
    with pytest.raises(ValueError, match="inactive_target"):
        mapping.validate_against(_terminology(owner, retired))
    active = _binding(owner, "own_b")
    mapping = _mapping(owner, _target(active))
    foreign = _binding(_agent("bob"), "own_b")
    with pytest.raises(ValueError, match="owner_mismatch"):
        mapping.validate_against(_terminology(_agent("bob"), foreign))



def test_source_token_cannot_be_a_target() -> None:
    owner = _agent()
    binding = _binding(owner, "foreign_a")
    with pytest.raises(ValueError, match="source_self_target"):
        _mapping(owner, _target(binding))


def test_evidence_and_application_are_monotonic_and_bounded() -> None:
    owner = _agent()
    binding = _binding(owner, "own_a")
    mapping_id = translation_mapping_id(owner, translation_source_digest("foreign_a"))
    with pytest.raises(ValueError, match="not_monotonic"):
        TranslationMapping(
            mapping_id=mapping_id,
            owner_id=owner,
            source_token="foreign_a",
            source_digest=translation_source_digest("foreign_a"),
            source_kind=TranslationSourceKind.LABEL,
            targets=(_target(binding),),
            status=TranslationMappingStatus.CANDIDATE,
            fit=TranslationFit.RESOLVED,
            strength=0.2,
            evidence_count=2,
            first_tick=1,
            last_tick=2,
            evidence=(
                TranslationEvidenceItem(
                    evidence_id="a" * 64,
                    ordinal=1,
                    channel=TranslationEvidenceChannel.CONTEXT,
                    lineage_ref="l",
                    tick=1,
                ),
                TranslationEvidenceItem(
                    evidence_id="b" * 64,
                    ordinal=0,
                    channel=TranslationEvidenceChannel.CONTEXT,
                    lineage_ref="l",
                    tick=2,
                ),
            ),
        )
    with pytest.raises(ValueError, match="duplicate_evidence"):
        TranslationMapping(
            mapping_id=mapping_id,
            owner_id=owner,
            source_token="foreign_a",
            source_digest=translation_source_digest("foreign_a"),
            source_kind=TranslationSourceKind.LABEL,
            targets=(_target(binding),),
            status=TranslationMappingStatus.CANDIDATE,
            fit=TranslationFit.RESOLVED,
            strength=0.2,
            evidence_count=2,
            first_tick=1,
            last_tick=2,
            evidence=(
                TranslationEvidenceItem(
                    evidence_id="a" * 64,
                    ordinal=0,
                    channel=TranslationEvidenceChannel.CONTEXT,
                    lineage_ref="l",
                    tick=1,
                ),
                TranslationEvidenceItem(
                    evidence_id="a" * 64,
                    ordinal=1,
                    channel=TranslationEvidenceChannel.CONTEXT,
                    lineage_ref="l",
                    tick=2,
                ),
            ),
        )
    application = TranslationApplication(
        application_id="c" * 64,
        ordinal=0,
        tick=1,
        kind=TranslationApplicationKind.OUTBOUND_TERM,
        mapping_id=mapping_id,
        outcome=TranslationApplicationOutcome.APPLIED,
    )
    assert application.mapping_id == mapping_id


def test_ledger_rejects_foreign_mapping_and_duplicate_source() -> None:
    owner = _agent()
    binding = _binding(owner, "own_a")
    mapping = _mapping(owner, _target(binding))
    with pytest.raises(ValueError, match="owner_mismatch"):
        TranslationLedger(owner_id=_agent("bob"), mappings=(mapping,))
    with pytest.raises(ValueError, match="duplicate_mapping"):
        TranslationLedger(owner_id=owner, mappings=(mapping, mapping))


def test_empty_ledger_and_owner_guard() -> None:
    owner = _agent()
    ledger = empty_translation_ledger(owner)
    assert ledger.mappings == ()
    require_owner_translation(ledger, owner, field_name="translation")
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_translation(ledger, _agent("bob"), field_name="translation")
    with pytest.raises(TypeError, match="must be TranslationLedger"):
        require_owner_translation(object(), owner, field_name="translation")


def test_strength_band_is_closed() -> None:
    assert (
        translation_strength_band(
            TranslationMappingStatus.CANDIDATE, 0.9
        )
        is TranslationStrengthBand.CANDIDATE
    )
    assert (
        translation_strength_band(TranslationMappingStatus.ACTIVE, 0.2)
        is TranslationStrengthBand.LOW
    )
    assert (
        translation_strength_band(TranslationMappingStatus.ACTIVE, 0.5)
        is TranslationStrengthBand.MID
    )
    assert (
        translation_strength_band(TranslationMappingStatus.ACTIVE, 0.9)
        is TranslationStrengthBand.HIGH
    )


def test_contracts_are_frozen_and_caller_mutation_cannot_alter_them() -> None:
    owner = _agent()
    binding = _binding(owner, "own_a")
    mapping = _mapping(owner, _target(binding))
    with pytest.raises(AttributeError):
        mapping.source_token = "changed"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        mapping.targets[0].weight = 0.9  # type: ignore[misc]
