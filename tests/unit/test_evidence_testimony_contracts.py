"""V4-08 evidence-testimony vocabulary, identity grammar, and bounded policy."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from enum import StrEnum
from pathlib import Path

import pytest

from agents.cognition import (
    EVIDENCE_ERROR_CODES,
    EVIDENCE_FORBIDDEN_FIELD_NAMES,
    EVIDENCE_ID_HEX_LEN,
    EVIDENCE_NOTICE_REASONS,
    EVIDENCE_TESTIMONY_CONTEXT_ID,
    EVIDENCE_TESTIMONY_IS_CAPABILITY_FLAG,
    EVIDENCE_TESTIMONY_POLICY_VERSION,
    EVIDENCE_TESTIMONY_REQUIRED_RUNNER_SCHEMA,
    EvidenceContradictionKind,
    EvidenceContradictionStatus,
    EvidenceCustodyRole,
    EvidenceCustodyStatus,
    EvidenceError,
    EvidenceEvaluationKind,
    EvidenceIntegrityBelief,
    EvidenceInterpretationKind,
    EvidenceItemStatus,
    EvidencePolicy,
    EvidenceProvenanceChannel,
    EvidenceReferenceKind,
    EvidenceReportKind,
    EvidenceSourceKind,
    EvidenceTestimonyChannel,
    EvidenceTrustBasis,
    default_evidence_policy,
    evidence_contradiction_id,
    evidence_custody_id,
    evidence_evaluation_id,
    evidence_item_id,
    evidence_source_id,
    evidence_testimony_id,
    require_evidence_contradiction_id,
    require_evidence_custody_id,
    require_evidence_evaluation_id,
    require_evidence_item_id,
    require_evidence_policy,
    require_evidence_source_id,
    require_evidence_testimony_id,
)

pytestmark = pytest.mark.unit

MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "agents"
    / "cognition"
    / "evidence_testimony.py"
)
OWNER = "agent-1"
OTHER_OWNER = "agent-2"


def _code(call: Callable[..., object]) -> str:
    with pytest.raises(EvidenceError) as error:
        call()
    return error.value.code


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_type]


def test_policy_and_seam_constants_are_locked() -> None:
    assert EVIDENCE_TESTIMONY_POLICY_VERSION == "evidence-testimony.v1"
    assert EVIDENCE_TESTIMONY_CONTEXT_ID == "legal_disputes"
    assert EVIDENCE_TESTIMONY_REQUIRED_RUNNER_SCHEMA == "runner-config-v56"
    assert EVIDENCE_TESTIMONY_IS_CAPABILITY_FLAG is False

    policy = default_evidence_policy()

    assert policy.version == EVIDENCE_TESTIMONY_POLICY_VERSION
    assert policy.max_sources == 64
    assert policy.max_testimony == 64
    assert policy.max_items == 128
    assert policy.max_custody_links_per_source == 16
    assert policy.max_contradictions == 64
    assert policy.max_evaluations == 128
    assert policy.max_total_records == 640
    assert policy.max_notices == 16
    assert policy.max_frame_chars == 768
    assert policy.max_frame_relations == 32
    assert policy.max_subject_token == 128
    assert policy.trust_weight_direct_experience == 5000
    assert policy.trust_weight_relationship == 2500
    assert policy.trust_weight_reputation == 2000
    assert policy.trust_weight_role_authority == 500
    assert policy.neutral_confidence == 0.5
    assert policy.confidence_quantum == 0.000001
    assert require_evidence_policy(None) is policy
    assert require_evidence_policy(policy) is policy

    with pytest.raises(EvidenceError) as error:
        EvidencePolicy(max_sources=65)
    assert error.value.code == "evidence_policy_not_locked"

    with pytest.raises(EvidenceError) as error:
        EvidencePolicy(neutral_confidence=0.6)
    assert error.value.code == "evidence_policy_not_locked"

    with pytest.raises(FrozenInstanceError):
        policy.max_sources = 65  # type: ignore[misc]

    with pytest.raises(EvidenceError) as error:
        require_evidence_policy(object())
    assert error.value.code == "evidence_invalid_input"


def test_source_kinds_are_closed_and_complete() -> None:
    assert set(_enum_values(EvidenceSourceKind)) == {
        "witness_testimony",
        "written_record",
        "artifact",
        "physical_state",
        "prior_agreement",
        "reputation",
        "remembered_event",
        "unknown",
    }
    assert set(_enum_values(EvidenceProvenanceChannel)) == {
        "direct_observation",
        "communicated",
        "remembered",
        "recorded",
        "derived",
        "inferred",
        "unknown",
    }
    assert set(_enum_values(EvidenceReferenceKind)) == {
        "observed_occurrence",
        "observed_communication",
        "memory_trace",
        "reconstructed_memory",
        "artifact",
        "durable_record",
        "repository_entry",
        "commitment",
        "reputation_record",
        "relationship_record",
        "office_record",
        "institution_record",
        "organization_record",
        "rule_record",
        "mediation_record",
        "dispute_record",
        "unknown",
    }
    assert set(_enum_values(EvidenceTestimonyChannel)) == {"direct", "communicated"}
    assert set(_enum_values(EvidenceIntegrityBelief)) == {
        "intact",
        "damaged",
        "partially_lost",
        "destroyed_belief",
        "uncertain",
    }
    assert set(_enum_values(EvidenceInterpretationKind)) == {
        "supports",
        "contradicts",
        "ambiguous",
        "insufficient",
        "irrelevant",
        "unknown",
    }
    assert set(_enum_values(EvidenceItemStatus)) == {
        "active",
        "retracted",
        "superseded",
    }
    assert set(_enum_values(EvidenceCustodyRole)) == {
        "holder",
        "repository_custodian",
        "location",
        "observer",
    }
    assert set(_enum_values(EvidenceCustodyStatus)) == {
        "not_applicable",
        "complete_belief",
        "incomplete_belief",
        "conflicting_belief",
        "unknown",
    }
    assert set(_enum_values(EvidenceContradictionKind)) == {
        "testimony_conflict",
        "memory_conflict",
        "record_conflict",
        "artifact_conflict",
        "custody_conflict",
        "temporal_conflict",
        "interpretation_conflict",
        "provenance_conflict",
    }
    assert set(_enum_values(EvidenceContradictionStatus)) == {
        "unresolved",
        "owner_prefers_first",
        "owner_prefers_second",
        "withdrawn",
    }
    assert set(_enum_values(EvidenceTrustBasis)) == {
        "direct_experience",
        "relationship_trust",
        "reputation",
        "role_authority",
        "rule_authority",
        "institution_membership",
        "none",
        "unknown",
    }
    assert set(_enum_values(EvidenceEvaluationKind)) == {
        "corroborated",
        "contested",
        "uncorroborated",
        "excluded_by_owner",
        "unknown",
    }
    assert set(_enum_values(EvidenceReportKind)) == {
        "summary",
        "candidate",
        "item",
        "contradiction",
        "custody",
        "lineage",
    }


def test_enum_values_are_unique_and_do_not_name_forbidden_outcomes() -> None:
    enum_types = (
        EvidenceSourceKind,
        EvidenceProvenanceChannel,
        EvidenceReferenceKind,
        EvidenceTestimonyChannel,
        EvidenceIntegrityBelief,
        EvidenceInterpretationKind,
        EvidenceItemStatus,
        EvidenceCustodyRole,
        EvidenceCustodyStatus,
        EvidenceContradictionKind,
        EvidenceContradictionStatus,
        EvidenceTrustBasis,
        EvidenceEvaluationKind,
        EvidenceReportKind,
    )
    tokens: set[str] = set()
    for enum_type in enum_types:
        values = _enum_values(enum_type)
        assert len(values) == len(set(values))
        for member in enum_type:
            tokens.add(member.name.lower())
            tokens.add(member.value)

    assert tokens.isdisjoint(EVIDENCE_FORBIDDEN_FIELD_NAMES)
    assert EvidenceSourceKind("artifact") is EvidenceSourceKind.ARTIFACT
    with pytest.raises(ValueError):
        EvidenceSourceKind("objective_truth")


def test_error_codes_notices_and_forbidden_fields_are_exact() -> None:
    assert EVIDENCE_ERROR_CODES == frozenset(
        {
            "evidence_invalid_input",
            "evidence_invalid_id",
            "evidence_invalid_record",
            "evidence_owner_mismatch",
            "evidence_tick_mismatch",
            "evidence_unknown_reference",
            "evidence_duplicate_id",
            "evidence_limit_exceeded",
            "evidence_policy_not_locked",
            "evidence_forbidden_field",
            "evidence_untrusted_frame",
            "evidence_invalid_confidence",
            "evidence_chain_conflict",
        }
    )
    assert EVIDENCE_NOTICE_REASONS == frozenset(
        {
            "evidence_truncated",
            "evidence_chain_incomplete",
            "evidence_reference_unknown",
            "evidence_contradiction_retained",
            "evidence_trust_basis_missing",
            "evidence_testimony_root_shared",
            "evidence_item_retracted",
        }
    )
    assert EVIDENCE_FORBIDDEN_FIELD_NAMES == frozenset(
        {
            "truth",
            "verified",
            "authenticated",
            "authentic",
            "forged",
            "fake",
            "proof",
            "certainty",
            "verdict",
            "guilt",
            "guilty",
            "liable",
            "liability",
            "true_owner",
            "winner",
        }
    )


def test_error_exposes_only_a_safe_reason_code() -> None:
    with pytest.raises(EvidenceError) as error:
        require_evidence_source_id("evs-zzzz")
    assert error.value.code == "evidence_invalid_id"
    assert error.value.args == ("evidence_invalid_id",)
    assert error.value.__slots__ == ("code",)

    with pytest.raises(ValueError):
        EvidenceError("evidence_truth_oracle")


def test_every_id_prefix_round_trips_and_rejects_foreign_ids() -> None:
    source_id = evidence_source_id(
        OWNER,
        EvidenceSourceKind.WITNESS_TESTIMONY,
        EvidenceReferenceKind.OBSERVED_COMMUNICATION,
        "utterance-1",
        0,
    )
    testimony_id = evidence_testimony_id(
        OWNER,
        "agent-2",
        EvidenceTestimonyChannel.DIRECT,
        "root-1",
        0,
    )
    item_id = evidence_item_id(
        OWNER,
        source_id,
        EvidenceInterpretationKind.SUPPORTS,
        0,
    )
    custody_id = evidence_custody_id(
        OWNER,
        source_id,
        3,
        EvidenceCustodyRole.HOLDER,
        "item-1",
        7,
    )
    contradiction_id = evidence_contradiction_id(
        OWNER,
        source_id,
        item_id,
        EvidenceContradictionKind.TESTIMONY_CONFLICT,
        0,
    )
    evaluation_id = evidence_evaluation_id(
        OWNER,
        item_id,
        "direct_experience,relationship_trust",
        0,
    )

    pairs = (
        (source_id, require_evidence_source_id, "evs-"),
        (testimony_id, require_evidence_testimony_id, "evw-"),
        (item_id, require_evidence_item_id, "evi-"),
        (custody_id, require_evidence_custody_id, "evc-"),
        (contradiction_id, require_evidence_contradiction_id, "evx-"),
        (evaluation_id, require_evidence_evaluation_id, "eva-"),
    )
    for value, validator, prefix in pairs:
        assert validator(value) == value
        assert value.startswith(prefix)
        assert re.fullmatch(rf"{prefix}[0-9a-f]{{{EVIDENCE_ID_HEX_LEN}}}", value)
        assert _code(
            lambda validator=validator, value=value: validator(value.upper())
        ) == ("evidence_invalid_id")
        assert _code(
            lambda validator=validator, value=value: validator("evs-zzzz")
        ) == ("evidence_invalid_id")


def test_validators_reject_short_long_and_prefixed_only_ids() -> None:
    source_id = evidence_source_id(
        OWNER,
        EvidenceSourceKind.ARTIFACT,
        EvidenceReferenceKind.ARTIFACT,
        "artifact-1",
        0,
    )
    body = source_id.removeprefix("evs-")
    assert len(body) == EVIDENCE_ID_HEX_LEN

    invalid = (
        "evs-",
        "evs-xyz",
        f"evs-{body[:-1]}",
        f"evs-{body}0",
        f"evi-{body}",
        f"evs-{body.upper()}",
    )
    for value in invalid:
        assert _code(lambda value=value: require_evidence_source_id(value)) == (
            "evidence_invalid_id"
        )


def test_ids_are_stable_and_owner_scoped() -> None:
    def source(owner: str, kind: EvidenceSourceKind, reference: str) -> str:
        return evidence_source_id(
            owner,
            kind,
            EvidenceReferenceKind.DURABLE_RECORD,
            reference,
            0,
        )

    assert source(OWNER, EvidenceSourceKind.WRITTEN_RECORD, "record-1") == source(
        OWNER, EvidenceSourceKind.WRITTEN_RECORD, "record-1"
    )
    assert source(OWNER, EvidenceSourceKind.WRITTEN_RECORD, "record-1") != source(
        OTHER_OWNER, EvidenceSourceKind.WRITTEN_RECORD, "record-1"
    )
    assert source(OWNER, EvidenceSourceKind.WRITTEN_RECORD, "record-1") != source(
        OWNER, EvidenceSourceKind.ARTIFACT, "record-1"
    )
    assert source(OWNER, EvidenceSourceKind.WRITTEN_RECORD, "record-2") != source(
        OWNER, EvidenceSourceKind.WRITTEN_RECORD, "record-1"
    )

    testimony = evidence_testimony_id(
        OWNER, "agent-2", EvidenceTestimonyChannel.COMMUNICATED, "root-1", 0
    )
    assert testimony == evidence_testimony_id(
        OWNER, "agent-2", EvidenceTestimonyChannel.COMMUNICATED, "root-1", 0
    )
    assert testimony != evidence_testimony_id(
        OWNER, "agent-2", EvidenceTestimonyChannel.DIRECT, "root-1", 0
    )
    assert testimony != evidence_testimony_id(
        OWNER, "agent-3", EvidenceTestimonyChannel.COMMUNICATED, "root-1", 0
    )

    source_id = source(OWNER, EvidenceSourceKind.WRITTEN_RECORD, "record-1")
    item = evidence_item_id(OWNER, source_id, EvidenceInterpretationKind.CONTRADICTS, 1)
    assert item == evidence_item_id(
        OWNER, source_id, EvidenceInterpretationKind.CONTRADICTS, 1
    )
    assert item != evidence_item_id(
        OWNER, source_id, EvidenceInterpretationKind.CONTRADICTS, 2
    )

    custody = evidence_custody_id(
        OWNER, source_id, 4, EvidenceCustodyRole.OBSERVER, "agent-3", 9
    )
    assert custody == evidence_custody_id(
        OWNER, source_id, 4, EvidenceCustodyRole.OBSERVER, "agent-3", 9
    )
    assert custody != evidence_custody_id(
        OWNER, source_id, 4, EvidenceCustodyRole.HOLDER, "agent-3", 9
    )


def test_id_minters_reject_cross_prefixes_and_bad_inputs() -> None:
    source_id = evidence_source_id(
        OWNER,
        EvidenceSourceKind.REPUTATION,
        EvidenceReferenceKind.REPUTATION_RECORD,
        "reputation-1",
        0,
    )

    assert (
        _code(
            lambda: evidence_item_id(
                OWNER, "evc-0123456789abcdef", EvidenceInterpretationKind.UNKNOWN, 0
            )
        )
        == "evidence_invalid_id"
    )
    assert (
        _code(
            lambda: evidence_source_id(
                "",
                EvidenceSourceKind.ARTIFACT,
                EvidenceReferenceKind.ARTIFACT,
                "artifact-1",
                0,
            )
        )
        == "evidence_invalid_input"
    )
    assert (
        _code(
            lambda: evidence_source_id(
                OWNER,
                "objective_truth",  # type: ignore[arg-type]
                EvidenceReferenceKind.ARTIFACT,
                "artifact-1",
                0,
            )
        )
        == "evidence_invalid_input"
    )
    assert (
        _code(
            lambda: evidence_source_id(
                OWNER,
                EvidenceSourceKind.ARTIFACT,
                EvidenceReferenceKind.ARTIFACT,
                "artifact-1",
                -1,
            )
        )
        == "evidence_invalid_input"
    )
    assert (
        _code(
            lambda: evidence_custody_id(
                OWNER,
                source_id,
                0,
                EvidenceCustodyRole.HOLDER,
                "t" * 129,
                0,
            )
        )
        == "evidence_limit_exceeded"
    )
    assert (
        _code(
            lambda: evidence_contradiction_id(
                OWNER,
                source_id,
                source_id,
                EvidenceContradictionKind.PROVENANCE_CONFLICT,
                -1,
            )
        )
        == "evidence_invalid_input"
    )


def test_module_has_no_nondeterministic_or_outer_imports() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".")[0])

    assert imported.isdisjoint({"random", "secrets", "uuid", "time", "datetime"})
    assert imported.isdisjoint(
        {
            "analysis",
            "experiments",
            "persistence",
            "api",
            "infrastructure",
            "observer",
            "world",
            "simulation",
        }
    )
