"""Owner-local institutional-decay contracts and locked policy."""

from __future__ import annotations

import dataclasses
import math

import pytest

from agents.cognition.institution_concepts import (
    InstitutionConceptLedger,
    InstitutionPatternChannel,
)
from agents.cognition.institutional_decay import (
    FORBIDDEN_INSTITUTION_DECAY_FIELD_NAMES,
    INSTITUTIONAL_DECAY_POLICY_VERSION,
    InstitutionDecayAvailability,
    InstitutionDecayBinding,
    InstitutionDecayDimension,
    InstitutionDecayLedger,
    InstitutionDecayPolicy,
    InstitutionDecayReceipt,
    InstitutionDecayRecord,
    InstitutionDecaySample,
    InstitutionDecayUpdate,
    InstitutionDimensionEvidence,
    append_institution_decay_receipt,
    default_institutional_decay_policy,
    empty_institution_decay_ledger,
    institution_decay_local_pattern_id,
    require_owner_institution_decay,
    retain_institution_decay_sample,
)
from agents.models import AgentId


def _agent(value: str = "alice") -> AgentId:
    return AgentId(value)


def _binding(
    owner: AgentId,
    *,
    group_key: str = "b" * 64,
    concept_id: str = "c" * 64,
    inception_tick: int = 1,
) -> InstitutionDecayBinding:
    return InstitutionDecayBinding(
        local_pattern_id=institution_decay_local_pattern_id(
            owner, group_key, inception_tick
        ),
        owner_id=owner,
        group_key=group_key,
        concept_id=concept_id,
        inception_tick=inception_tick,
        anchor_digests=("a" * 16,),
    )


def _record(
    owner: AgentId,
    binding: InstitutionDecayBinding,
) -> InstitutionDecayRecord:
    return InstitutionDecayRecord(
        owner_id=owner,
        local_pattern_id=binding.local_pattern_id,
        group_key=binding.group_key,
        concept_id=binding.concept_id,
        anchor_digests=("a" * 16,),
        structural_signature_key="d" * 16,
        inception_tick=binding.inception_tick,
        last_activity_tick=1,
        current_span_start_tick=1,
    )


def _sample(
    owner: AgentId,
    binding: InstitutionDecayBinding,
    *,
    observation_tick: int,
    role: float = 0.5,
) -> InstitutionDecaySample:
    return InstitutionDecaySample(
        owner_id=owner,
        local_pattern_id=binding.local_pattern_id,
        observation_tick=observation_tick,
        source_first_tick=observation_tick,
        source_last_tick=observation_tick,
        role_recognition=role,
        procedure_recurrence=0.5,
        social_expectation=0.5,
        legitimacy_belief=0.5,
        succession_observed=0.0,
        generational_continuity=0.0,
        recognized=True,
        evidence=InstitutionDimensionEvidence(),
        anchor_digests=("a" * 16,),
    )


def _ledger(
    owner: AgentId, *bindings: InstitutionDecayBinding
) -> InstitutionDecayLedger:
    records = tuple(_record(owner, binding) for binding in bindings)
    return InstitutionDecayLedger(
        owner_id=owner,
        bindings=tuple(bindings),
        records=records,
    )


def test_empty_ledger_and_disabled_are_distinct() -> None:
    owner = _agent()
    empty = empty_institution_decay_ledger(owner)

    assert empty.owner_id == owner
    assert empty.bindings == ()
    assert empty.samples == ()
    assert empty.policy_version == INSTITUTIONAL_DECAY_POLICY_VERSION
    assert empty is not None
    require_owner_institution_decay(None, owner)


def test_exact_enums() -> None:
    assert {item.value for item in InstitutionDecayAvailability} == {
        "observed",
        "unknown",
        "disabled",
        "partial",
        "not_applicable",
    }
    assert {item.value for item in InstitutionDecayDimension} == {
        "support",
        "participation",
        "procedure_repetition",
        "succession_continuity",
        "knowledge_continuity",
    }


def test_forged_stable_pattern_id_rejected() -> None:
    owner = _agent()
    with pytest.raises(ValueError, match="id_mismatch"):
        InstitutionDecayBinding(
            local_pattern_id="0" * 64,
            owner_id=owner,
            group_key="b" * 64,
            concept_id="c" * 64,
            inception_tick=1,
            anchor_digests=("a" * 16,),
        )


def test_foreign_owner_rejected() -> None:
    owner = _agent()
    other = _agent("bob")
    binding = _binding(owner)
    ledger = _ledger(owner, binding)

    with pytest.raises(ValueError, match="mismatch"):
        require_owner_institution_decay(ledger, other)
    with pytest.raises(ValueError, match="owner_mismatch"):
        retain_institution_decay_sample(
            ledger, _sample(other, binding, observation_tick=1)
        )
    with pytest.raises(ValueError, match="owner_mismatch"):
        InstitutionDecayLedger(
            owner_id=owner,
            bindings=(_binding(other, group_key="e" * 64),),
        )


def test_invalid_spans_counts_and_nonfinite_values() -> None:
    owner = _agent()
    binding = _binding(owner)
    with pytest.raises(ValueError, match="not_finite"):
        _sample(owner, binding, observation_tick=1, role=math.nan)
    with pytest.raises(ValueError, match="not_finite"):
        _sample(owner, binding, observation_tick=1, role=math.inf)
    with pytest.raises(ValueError, match="out_of_range"):
        _sample(owner, binding, observation_tick=1, role=1.5)
    with pytest.raises(ValueError, match=r"non-negative|invalid_type"):
        InstitutionDecaySample(
            owner_id=owner,
            local_pattern_id=binding.local_pattern_id,
            observation_tick=True,
            source_first_tick=1,
            source_last_tick=1,
            role_recognition=0.5,
            procedure_recurrence=0.5,
            social_expectation=0.5,
            legitimacy_belief=0.5,
            succession_observed=0.0,
            generational_continuity=0.0,
            recognized=True,
            evidence=InstitutionDimensionEvidence(),
            anchor_digests=("a" * 16,),
        )


def test_defensive_detachment() -> None:
    owner = _agent()
    binding = _binding(owner)
    record = dataclasses.replace(
        _record(owner, binding),
        anchor_digests=list(("a" * 16,)),  # type: ignore[arg-type]
    )
    assert isinstance(record.anchor_digests, tuple)

    ledger = InstitutionDecayLedger(
        owner_id=owner,
        bindings=[binding],  # type: ignore[arg-type]
        records=[record],  # type: ignore[arg-type]
    )
    assert isinstance(ledger.bindings, tuple)
    assert isinstance(ledger.records, tuple)


def test_policy_override_rejection() -> None:
    with pytest.raises(ValueError, match="unsupported_policy"):
        InstitutionDecayPolicy(channel_loss=0.05)
    with pytest.raises(ValueError, match="unsupported_policy"):
        InstitutionDecayPolicy(max_samples=128)
    with pytest.raises(ValueError, match="unsupported_policy"):
        InstitutionDecayPolicy(version="institutional-decay.v2")
    policy = default_institutional_decay_policy()
    assert policy.channel_loss == 0.04
    assert policy.quantum == 0.000001
    assert policy.window_ticks == 4
    assert policy.max_patterns == 16
    assert policy.max_samples == 256
    assert policy.max_receipts == 512
    assert policy.inactive_streak_cap == 8


def test_deterministic_sample_cap_and_pruning_witnesses() -> None:
    owner = _agent()
    binding = _binding(owner)
    ledger = _ledger(owner, binding)
    for tick in range(257):
        ledger = retain_institution_decay_sample(
            ledger, _sample(owner, binding, observation_tick=tick)
        )

    assert len(ledger.samples) == 256
    assert ledger.sample_count_pruned == 1
    assert ledger.samples[0].observation_tick == 1
    record = ledger.records[0]
    assert record.sample_pruned_through_tick == 0
    assert record.inception_tick == 1
    assert record.current_span_start_tick == 1


def test_pruning_boundaries_are_per_pattern_and_receipts_separate() -> None:
    owner = _agent()
    first = _binding(owner, group_key="b" * 64)
    second = _binding(owner, group_key="e" * 64, concept_id="f" * 64)
    ledger = _ledger(owner, first, second)
    for tick in range(520):
        target = first if tick % 2 == 0 else second
        ledger = retain_institution_decay_sample(
            ledger, _sample(owner, target, observation_tick=tick)
        )

    records = {record.local_pattern_id: record for record in ledger.records}
    assert records[first.local_pattern_id].sample_pruned_through_tick is not None
    assert records[second.local_pattern_id].sample_pruned_through_tick is not None
    assert ledger.receipt_pruned_through_source_tick is None

    receipt = InstitutionDecayReceipt(
        owner_id=owner,
        local_pattern_id=first.local_pattern_id,
        channel=InstitutionPatternChannel.ROLE_RECOGNITION,
        evidence_key="event-1",
        source_tick=1,
        observation_tick=1,
    )
    ledger = append_institution_decay_receipt(ledger, receipt)
    assert len(ledger.receipts) == 1
    assert ledger.receipt_pruned_through_source_tick is None


def test_receipt_cap_prunes_by_source_tick() -> None:
    owner = _agent()
    binding = _binding(owner)
    ledger = _ledger(owner, binding)
    for tick in range(513):
        ledger = append_institution_decay_receipt(
            ledger,
            InstitutionDecayReceipt(
                owner_id=owner,
                local_pattern_id=binding.local_pattern_id,
                channel=InstitutionPatternChannel.ROLE_RECOGNITION,
                evidence_key=f"event-{tick}",
                source_tick=tick,
                observation_tick=tick,
            ),
        )

    assert len(ledger.receipts) == 512
    assert ledger.receipt_count_pruned == 1
    assert ledger.receipt_pruned_through_source_tick == 0
    with pytest.raises(ValueError, match="pruned"):
        append_institution_decay_receipt(
            ledger,
            InstitutionDecayReceipt(
                owner_id=owner,
                local_pattern_id=binding.local_pattern_id,
                channel=InstitutionPatternChannel.ROLE_RECOGNITION,
                evidence_key="old",
                source_tick=0,
                observation_tick=0,
            ),
        )


def test_raw_samples_have_no_rolling_ratio_or_lifecycle_fields() -> None:
    names = {field.name for field in dataclasses.fields(InstitutionDecaySample)}
    assert (
        not {
            "support_ratio",
            "participation_ratio",
            "health",
            "health_score",
            "collapse",
            "lifecycle",
            "window_ratio",
        }
        & names
    )
    ledger_names = {field.name for field in dataclasses.fields(InstitutionDecayLedger)}
    assert not {"lifecycle", "collapse", "health"} & ledger_names


def test_no_forbidden_authority_field_names() -> None:
    for model in (
        InstitutionDecayBinding,
        InstitutionDecayRecord,
        InstitutionDecaySample,
        InstitutionDecayLedger,
        InstitutionDecayUpdate,
        InstitutionDimensionEvidence,
    ):
        names = {field.name for field in dataclasses.fields(model)}
        assert not names & FORBIDDEN_INSTITUTION_DECAY_FIELD_NAMES


def test_update_pair_requires_matching_owners() -> None:
    owner = _agent()
    other = _agent("bob")
    concepts = InstitutionConceptLedger(owner_id=owner)
    decay = empty_institution_decay_ledger(owner)
    pair = InstitutionDecayUpdate(concepts=concepts, decay=decay)
    assert pair.concepts.owner_id == pair.decay.owner_id

    with pytest.raises(ValueError, match="owner_mismatch"):
        InstitutionDecayUpdate(
            concepts=InstitutionConceptLedger(owner_id=other),
            decay=decay,
        )


def test_ledger_rejects_unknown_sample_pattern() -> None:
    owner = _agent()
    binding = _binding(owner)
    orphan = _sample(owner, binding, observation_tick=1)
    other = _binding(owner, group_key="e" * 64, concept_id="f" * 64)
    with pytest.raises(ValueError, match="unknown_pattern"):
        InstitutionDecayLedger(
            owner_id=owner,
            bindings=(other,),
            records=(_record(owner, other),),
            samples=(orphan,),
        )
