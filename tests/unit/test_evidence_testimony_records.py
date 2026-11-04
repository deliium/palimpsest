"""V4-08 immutable evidence records, ledger invariants, and deterministic limits."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from typing import Any, cast

import pytest

from agents.cognition import (
    EVIDENCE_FORBIDDEN_FIELD_NAMES,
    EVIDENCE_TESTIMONY_POLICY_VERSION,
    EvidenceContradiction,
    EvidenceContradictionKind,
    EvidenceCustodyLink,
    EvidenceCustodyRole,
    EvidenceError,
    EvidenceEvaluation,
    EvidenceIntegrityBelief,
    EvidenceInterpretationKind,
    EvidenceItem,
    EvidenceItemStatus,
    EvidenceLedger,
    EvidenceProvenanceChannel,
    EvidenceReferenceKind,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceTestimonyChannel,
    EvidenceTrustBasis,
    EvidenceWitnessStatement,
    empty_evidence_ledger,
    enforce_evidence_limits,
    evidence_ledger_digest,
    require_owner_evidence,
)
from agents.cognition.evidence_testimony import _reject_forbidden_fields
from tests.unit.evidence_testimony_helpers import (
    OTHER_OWNER,
    OWNER,
    make_contradiction,
    make_custody,
    make_evaluation,
    make_item,
    make_parts,
    make_source,
    make_testimony,
)

pytestmark = pytest.mark.unit

RECORD_TYPES = (
    EvidenceSource,
    EvidenceWitnessStatement,
    EvidenceItem,
    EvidenceCustodyLink,
    EvidenceContradiction,
    EvidenceEvaluation,
    EvidenceLedger,
)


def _code(call: Callable[..., object]) -> str:
    with pytest.raises(EvidenceError) as error:
        call()
    return error.value.code


def test_no_record_carries_a_forbidden_truth_field() -> None:
    for model in RECORD_TYPES:
        names = {field.name for field in fields(model)}
        assert names.isdisjoint(EVIDENCE_FORBIDDEN_FIELD_NAMES), model

    @dataclass(frozen=True, slots=True)
    class TruthLike:
        truth: bool = True

        def __post_init__(self) -> None:
            _reject_forbidden_fields(type(self))

    with pytest.raises(EvidenceError) as error:
        TruthLike()
    assert error.value.code == "evidence_forbidden_field"


def test_source_recomputes_its_id_and_quantizes_confidence() -> None:
    source = make_source()
    assert source.confidence == 0.8
    assert source.independently_evidenced is False

    with pytest.raises(EvidenceError) as error:
        replace(source, source_id="evs-" + "0" * 16)
    assert error.value.code == "evidence_invalid_id"

    quantized = make_source(confidence=0.123456789)
    assert quantized.confidence == 0.123457

    with pytest.raises(EvidenceError) as error:
        make_source(confidence=1.1)
    assert error.value.code == "evidence_invalid_confidence"


def test_source_provenance_invariants() -> None:
    with pytest.raises(EvidenceError) as error:
        make_source(
            reference_kind=EvidenceReferenceKind.UNKNOWN,
            provenance=EvidenceProvenanceChannel.DIRECT_OBSERVATION,
        )
    assert error.value.code == "evidence_invalid_record"

    unknown = make_source(
        reference_kind=EvidenceReferenceKind.UNKNOWN,
        provenance=EvidenceProvenanceChannel.UNKNOWN,
        kind=EvidenceSourceKind.UNKNOWN,
    )
    assert unknown.reference_kind is EvidenceReferenceKind.UNKNOWN

    with pytest.raises(EvidenceError) as error:
        make_source(
            kind=EvidenceSourceKind.WITNESS_TESTIMONY,
            provenance=EvidenceProvenanceChannel.RECORDED,
        )
    assert error.value.code == "evidence_invalid_record"

    with pytest.raises(EvidenceError) as error:
        make_source(
            provenance=EvidenceProvenanceChannel.COMMUNICATED,
            independently_evidenced=True,
        )
    assert error.value.code == "evidence_invalid_record"


def test_communicated_testimony_requires_root_and_is_never_independent() -> None:
    direct = make_testimony()
    assert direct.channel is EvidenceTestimonyChannel.DIRECT
    assert direct.root_ref is None

    communicated = make_testimony(
        channel=EvidenceTestimonyChannel.COMMUNICATED, root_ref="root-1"
    )
    assert communicated.independently_evidenced is False

    with pytest.raises(EvidenceError) as error:
        replace(communicated, root_ref=None)
    assert error.value.code == "evidence_invalid_record"

    with pytest.raises(EvidenceError) as error:
        replace(communicated, independently_evidenced=True)
    assert error.value.code == "evidence_invalid_record"

    with pytest.raises(EvidenceError) as error:
        replace(direct, root_ref="root-1")
    assert error.value.code == "evidence_invalid_record"


def test_item_requires_exactly_one_anchor_and_a_retraction_reason() -> None:
    source = make_source()
    testimony = make_testimony(source_id=source.source_id)

    item = make_item(source_id=source.source_id)
    with pytest.raises(EvidenceError) as error:
        replace(item, testimony_id=testimony.testimony_id)
    assert error.value.code == "evidence_invalid_record"

    retracted = make_item(
        source_id=source.source_id,
        status=EvidenceItemStatus.RETRACTED,
        reason_code="owner_withdrew",
    )
    assert retracted.status is EvidenceItemStatus.RETRACTED

    with pytest.raises(EvidenceError) as error:
        replace(retracted, reason_code="")
    assert error.value.code == "evidence_invalid_record"


def test_custody_role_tokens_and_ordering_are_enforced() -> None:
    source = make_source()

    holder = make_custody(source_id=source.source_id)
    assert holder.role is EvidenceCustodyRole.HOLDER

    repo = make_custody(
        source_id=source.source_id,
        role=EvidenceCustodyRole.REPOSITORY_CUSTODIAN,
        holder_token=None,
        custodian_token="archive-1",
        link_index=1,
        tick=2,
    )
    assert repo.custodian_token == "archive-1"

    observer = make_custody(
        source_id=source.source_id,
        role=EvidenceCustodyRole.OBSERVER,
        holder_token=None,
        witnessed=True,
        link_index=2,
        tick=3,
    )
    assert observer.witnessed is True

    with pytest.raises(EvidenceError) as error:
        make_custody(
            source_id=source.source_id,
            role=EvidenceCustodyRole.HOLDER,
            holder_token=None,
        )
    assert error.value.code == "evidence_invalid_record"

    with pytest.raises(EvidenceError) as error:
        make_custody(
            source_id=source.source_id,
            role=EvidenceCustodyRole.OBSERVER,
            holder_token=None,
            witnessed=False,
        )
    assert error.value.code == "evidence_invalid_record"

    with pytest.raises(EvidenceError) as error:
        replace(holder, custody_id="evc-" + "0" * 16)
    assert error.value.code == "evidence_invalid_id"


def test_ledger_enforces_unique_ids_and_custody_chain_consistency() -> None:
    source = make_source()
    first = make_custody(source_id=source.source_id, link_index=0, tick=1)
    second = make_custody(
        source_id=source.source_id,
        link_index=2,
        tick=3,
        role=EvidenceCustodyRole.OBSERVER,
        holder_token=None,
        witnessed=True,
    )
    ledger = EvidenceLedger(
        owner_id=OWNER, sources=(source,), custody_links=(first, second)
    )
    assert len(ledger.custody_links) == 2

    with pytest.raises(EvidenceError) as error:
        EvidenceLedger(
            owner_id=OWNER, sources=(source,), custody_links=(first, replace(first))
        )
    assert error.value.code == "evidence_duplicate_id"

    with pytest.raises(EvidenceError) as error:
        EvidenceLedger(
            owner_id=OWNER,
            sources=(source,),
            custody_links=(
                first,
                make_custody(source_id=source.source_id, link_index=0, tick=2),
            ),
        )
    assert error.value.code == "evidence_chain_conflict"

    with pytest.raises(EvidenceError) as error:
        EvidenceLedger(
            owner_id=OWNER,
            sources=(source,),
            custody_links=(
                make_custody(source_id=source.source_id, link_index=0, tick=3),
                make_custody(source_id=source.source_id, link_index=1, tick=2),
            ),
        )
    assert error.value.code == "evidence_chain_conflict"


def test_contradiction_refs_are_distinct_owner_local_ids() -> None:
    source = make_source()
    item = make_item(source_id=source.source_id)

    with pytest.raises(EvidenceError) as error:
        make_contradiction(first_ref=source.source_id, second_ref=source.source_id)
    assert error.value.code == "evidence_invalid_record"

    with pytest.raises(EvidenceError) as error:
        make_contradiction(first_ref=source.source_id, second_ref="subject-1")
    assert error.value.code == "evidence_invalid_id"

    contradiction = make_contradiction(
        first_ref=source.source_id, second_ref=item.item_id
    )
    ledger = EvidenceLedger(
        owner_id=OWNER,
        sources=(source,),
        items=(item,),
        contradictions=(contradiction,),
    )
    assert ledger.contradictions == (contradiction,)

    with pytest.raises(EvidenceError) as error:
        EvidenceLedger(
            owner_id=OWNER,
            sources=(source,),
            contradictions=(contradiction,),
        )
    assert error.value.code == "evidence_unknown_reference"


def test_evaluation_basis_combinations_are_enforced() -> None:
    source = make_source()
    item = make_item(source_id=source.source_id)

    evaluation = make_evaluation(
        item_id=item.item_id,
        bases=(EvidenceTrustBasis.REPUTATION, EvidenceTrustBasis.DIRECT_EXPERIENCE),
    )
    assert evaluation.bases == (
        EvidenceTrustBasis.DIRECT_EXPERIENCE,
        EvidenceTrustBasis.REPUTATION,
    )

    with pytest.raises(EvidenceError) as error:
        replace(evaluation, bases=())
    assert error.value.code == "evidence_invalid_record"

    with pytest.raises(EvidenceError) as error:
        replace(
            evaluation,
            bases=(EvidenceTrustBasis.UNKNOWN, EvidenceTrustBasis.REPUTATION),
        )
    assert error.value.code == "evidence_invalid_record"

    with pytest.raises(EvidenceError) as error:
        replace(
            evaluation,
            bases=(EvidenceTrustBasis.NONE, EvidenceTrustBasis.REPUTATION),
        )
    assert error.value.code == "evidence_invalid_record"

    with pytest.raises(EvidenceError) as error:
        replace(
            evaluation,
            bases=(EvidenceTrustBasis.REPUTATION, EvidenceTrustBasis.REPUTATION),
        )
    assert error.value.code == "evidence_invalid_record"


def test_ledger_rejects_foreign_rows_and_foreign_carry() -> None:
    parts = make_parts()
    foreign = make_source(owner=OTHER_OWNER, ordinal=9)

    with pytest.raises(EvidenceError) as error:
        EvidenceLedger(owner_id=OWNER, sources=(foreign,))
    assert error.value.code == "evidence_owner_mismatch"

    ledger = parts.ledger()
    assert require_owner_evidence(ledger, OWNER) is ledger
    assert require_owner_evidence(None, OWNER) is None

    with pytest.raises(EvidenceError) as error:
        require_owner_evidence(ledger, OTHER_OWNER)
    assert error.value.code == "evidence_owner_mismatch"

    with pytest.raises(TypeError):
        require_owner_evidence(object(), OWNER)


def test_empty_ledger_digest_and_coverage() -> None:
    empty = empty_evidence_ledger(OWNER, tick=4)
    assert empty.enabled is True
    assert empty.has_content is False
    assert empty.coverage == "complete"
    assert empty.active_items == ()
    assert empty.observation_start_tick == 4

    parts = make_parts()
    ledger = parts.ledger()
    assert ledger.has_content is True
    assert ledger.coverage == "complete"
    assert len(ledger.active_items) == 1
    assert evidence_ledger_digest(ledger) == evidence_ledger_digest(parts.ledger())
    assert evidence_ledger_digest(ledger) != evidence_ledger_digest(empty)

    with pytest.raises(ValueError):
        EvidenceLedger(owner_id=OWNER, policy_version="evidence-testimony.v2")


def test_limits_truncate_in_documented_order_with_notice() -> None:
    sources = tuple(
        make_source(reference_id=f"artifact-{index}", ordinal=index)
        for index in range(65)
    )
    ledger = EvidenceLedger(owner_id=OWNER, sources=sources)
    limited = enforce_evidence_limits(ledger)

    assert len(limited.sources) == 64
    assert limited.pruned_source_count == 1
    assert limited.coverage == "partial"
    assert "evidence_truncated" in limited.notices
    assert limited.sources == tuple(sorted(sources, key=lambda row: row.source_id))[:64]

    again = enforce_evidence_limits(limited)
    assert again.pruned_source_count == 1
    assert again.sources == limited.sources
    assert evidence_ledger_digest(again) == evidence_ledger_digest(limited)


def test_limits_cascade_to_dependent_items_and_evaluations() -> None:
    sources = tuple(
        make_source(reference_id=f"artifact-{index}", ordinal=index)
        for index in range(65)
    )
    items = tuple(
        make_item(source_id=source.source_id, subject=f"subject-{index}")
        for index, source in enumerate(sources)
    )
    evaluations = tuple(make_evaluation(item_id=item.item_id) for item in items)
    ledger = EvidenceLedger(
        owner_id=OWNER,
        sources=sources,
        items=items,
        evaluations=evaluations,
    )

    limited = enforce_evidence_limits(ledger)

    assert len(limited.sources) == 64
    assert limited.pruned_source_count == 1
    assert limited.pruned_item_count == 1
    assert limited.pruned_evaluation_count == 1
    assert len(limited.items) == 64
    assert len(limited.evaluations) == 64
    assert limited.coverage == "partial"
    kept_sources = {row.source_id for row in limited.sources}
    assert {row.source_id for row in limited.items} <= kept_sources


def test_record_types_are_frozen_slots() -> None:
    for model in RECORD_TYPES:
        assert cast(Any, model).__dataclass_params__.frozen is True
        assert "__slots__" in model.__dict__

    parts = make_parts()
    with pytest.raises(dataclasses.FrozenInstanceError):
        parts.source.confidence = 0.1  # type: ignore[misc]

    assert EVIDENCE_TESTIMONY_POLICY_VERSION == parts.ledger().policy_version
    assert EvidenceContradictionKind.INTERPRETATION_CONFLICT.value == (
        "interpretation_conflict"
    )
    assert EvidenceIntegrityBelief.UNCERTAIN.value == "uncertain"
    assert EvidenceInterpretationKind.UNKNOWN.value == "unknown"
    assert make_source().source_kind is EvidenceSourceKind.ARTIFACT
