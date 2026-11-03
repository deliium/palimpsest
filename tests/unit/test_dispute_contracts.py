"""V4-07 dispute vocabulary, identity grammar, and bounded policy."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from agents.cognition import (
    DISPUTE_FORBIDDEN_FIELD_NAMES,
    DISPUTE_ID_HEX_LEN,
    DISPUTE_POLICY_VERSION,
    DisputeAuthorityKind,
    DisputeClaimKind,
    DisputeClaimPolarity,
    DisputeClaimRole,
    DisputeError,
    DisputeEvidenceChannel,
    DisputeEvidenceReferenceKind,
    DisputeKind,
    DisputeMediationLinkStatus,
    DisputePolicy,
    DisputeProvenance,
    DisputeReportKind,
    DisputeResolutionResponseKind,
    DisputeResolutionSource,
    DisputeResolutionStatus,
    DisputeResolutionTermKind,
    DisputeRuleApplicability,
    DisputeRuleInterpretation,
    DisputeRuleReferenceStatus,
    DisputeStatus,
    DisputeSubjectKind,
    DisputeTestimonyChannel,
    default_dispute_policy,
    dispute_authority_reference_id,
    dispute_case_id,
    dispute_case_ref,
    dispute_claim_id,
    dispute_claim_ref,
    dispute_evidence_id,
    dispute_mediation_reference_id,
    dispute_party_set_digest,
    dispute_resolution_id,
    dispute_resolution_ref,
    dispute_response_id,
    dispute_rule_reference_id,
    dispute_subject_digest,
    dispute_testimony_id,
    require_dispute_authority_reference_id,
    require_dispute_case_id,
    require_dispute_case_ref,
    require_dispute_claim_id,
    require_dispute_claim_ref,
    require_dispute_evidence_id,
    require_dispute_mediation_reference_id,
    require_dispute_policy,
    require_dispute_resolution_id,
    require_dispute_resolution_ref,
    require_dispute_response_id,
    require_dispute_rule_reference_id,
    require_dispute_testimony_id,
)

pytestmark = pytest.mark.unit

MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "agents"
    / "cognition"
    / "legal_disputes.py"
)
OWNER = "agent-1"
OTHER_OWNER = "agent-2"
CASE_REF = dispute_case_ref("item-1", ("agent-1", "agent-2"))
SUBJECT_DIGEST = dispute_subject_digest(DisputeSubjectKind.ITEM, "item-1")
CLAIM_REF = dispute_claim_ref(
    CASE_REF,
    "agent-1",
    DisputeClaimRole.CLAIM,
    DisputeClaimKind.ITEM_OWNED,
    DisputeClaimPolarity.AFFIRM,
    SUBJECT_DIGEST,
)
TERMS_DIGEST = dispute_subject_digest(DisputeSubjectKind.ACTION, "return-item")
RESOLUTION_REF = dispute_resolution_ref(CASE_REF, "agent-1", TERMS_DIGEST)


def _code(call: Callable[..., object]) -> str:
    with pytest.raises(DisputeError) as error:
        call()
    return error.value.code


def test_policy_version_and_limits_are_locked() -> None:
    policy = default_dispute_policy()

    assert policy.version == DISPUTE_POLICY_VERSION
    assert policy.max_cases == 16
    assert policy.max_claims_per_case == 16
    assert policy.max_total_records == 640
    assert require_dispute_policy(None) is policy

    with pytest.raises(DisputeError) as error:
        DisputePolicy(max_cases=17)
    assert error.value.code == "dispute_policy_not_locked"

    with pytest.raises(DisputeError) as error:
        require_dispute_policy(object())
    assert error.value.code == "dispute_policy_mismatch"


def test_every_id_prefix_round_trips_and_rejects_foreign_ids() -> None:
    case_id = dispute_case_id(OWNER, CASE_REF)
    claim_id = dispute_claim_id(OWNER, CLAIM_REF)
    testimony_id = dispute_testimony_id(
        OWNER,
        CASE_REF,
        CLAIM_REF,
        "agent-2",
        DisputeTestimonyChannel.DIRECT,
        "root-1",
        3,
    )
    evidence_id = dispute_evidence_id(
        OWNER,
        CASE_REF,
        CLAIM_REF,
        DisputeEvidenceChannel.REMEMBERED,
        DisputeEvidenceReferenceKind.MEMORY_TRACE,
        "mem-1",
        0,
    )
    rule_id = dispute_rule_reference_id(
        OWNER,
        CASE_REF,
        "frs-0123456789abcdef",
        "frl-0123456789abcdef",
        1,
        DisputeRuleInterpretation.LITERAL,
    )
    mediation_id = dispute_mediation_reference_id(OWNER, CASE_REF, "dmc-1", "dmr-1")
    authority_id = dispute_authority_reference_id(
        OWNER, CASE_REF, DisputeAuthorityKind.OFFICE, "ofc-1"
    )
    resolution_id = dispute_resolution_id(OWNER, RESOLUTION_REF)
    response_id = dispute_response_id(
        OWNER, RESOLUTION_REF, "agent-2", DisputeResolutionResponseKind.ACCEPT, 4
    )

    pairs = (
        (case_id, require_dispute_case_id, "dsc-"),
        (claim_id, require_dispute_claim_id, "dcl-"),
        (testimony_id, require_dispute_testimony_id, "dts-"),
        (evidence_id, require_dispute_evidence_id, "dev-"),
        (rule_id, require_dispute_rule_reference_id, "drf-"),
        (mediation_id, require_dispute_mediation_reference_id, "dmr-"),
        (authority_id, require_dispute_authority_reference_id, "dar-"),
        (resolution_id, require_dispute_resolution_id, "drs-"),
        (response_id, require_dispute_response_id, "drp-"),
    )
    for value, validator, prefix in pairs:
        assert validator(value) == value
        assert value.startswith(prefix)
        assert re.fullmatch(rf"{prefix}[0-9a-f]{{{DISPUTE_ID_HEX_LEN}}}", value)
        assert _code(
            lambda validator=validator, value=value: validator(value.upper())
        ) == ("dispute_invalid_id")
        assert _code(lambda validator=validator: validator("dsc-zzzz")) == (
            "dispute_invalid_id"
        )

    assert require_dispute_case_ref(CASE_REF) == CASE_REF
    assert require_dispute_claim_ref(CLAIM_REF) == CLAIM_REF
    assert require_dispute_resolution_ref(RESOLUTION_REF) == RESOLUTION_REF


def test_case_and_claim_ids_are_content_addressed_and_owner_scoped() -> None:
    assert dispute_case_ref("item-1", ("agent-1", "agent-2")) == CASE_REF
    assert dispute_case_ref("item-1", ("agent-2", "agent-1")) == CASE_REF
    assert dispute_case_id(OWNER, CASE_REF) == dispute_case_id(OWNER, CASE_REF)
    assert dispute_case_id(OWNER, CASE_REF) != dispute_case_id(OTHER_OWNER, CASE_REF)
    assert dispute_claim_id(OWNER, CLAIM_REF) == dispute_claim_id(OWNER, CLAIM_REF)
    assert dispute_claim_id(OWNER, CLAIM_REF) != dispute_claim_id(
        OTHER_OWNER, CLAIM_REF
    )
    assert dispute_case_ref("item-2", ("agent-1", "agent-2")) != CASE_REF

    other_ref = dispute_claim_ref(
        CASE_REF,
        "agent-2",
        DisputeClaimRole.COUNTERCLAIM,
        DisputeClaimKind.ITEM_OWNED,
        DisputeClaimPolarity.DENY,
        SUBJECT_DIGEST,
    )
    assert other_ref != CLAIM_REF


def test_party_and_subject_digests_are_sorted_deduplicated_and_bounded() -> None:
    first = dispute_party_set_digest(["agent-2", "agent-1", "agent-2"])
    second = dispute_party_set_digest(("agent-1", "agent-2"))
    assert first == second
    assert len(first) == 64

    assert _code(lambda: dispute_party_set_digest([])) == "dispute_party_limit"
    too_many = [f"agent-{index}" for index in range(9)]
    assert _code(lambda: dispute_party_set_digest(too_many)) == "dispute_party_limit"

    digest = dispute_subject_digest(DisputeSubjectKind.COMMITMENT, "commitment-1")
    assert digest == dispute_subject_digest(
        DisputeSubjectKind.COMMITMENT, "commitment-1"
    )
    assert len(digest) == 64
    assert digest != dispute_subject_digest(DisputeSubjectKind.ITEM, "commitment-1")
    assert _code(
        lambda: dispute_subject_digest(DisputeSubjectKind.ITEM, "x" * 769)
    ) == ("dispute_subject_limit")
    assert (
        _code(lambda: dispute_subject_digest("not_a_kind", "token"))
        == "dispute_invalid_mode"
    )


def test_kind_vocabulary_contains_the_six_requested_examples() -> None:
    values = {kind.value for kind in DisputeKind}
    assert {
        "contested_debt",
        "ownership_claim",
        "contract_interpretation",
        "injury",
        "broken_promise",
        "resource_appropriation",
    } <= values
    assert DisputeKind.OTHER.value == "other"
    assert {claim.value for claim in DisputeClaimKind} == {
        "debt_owed",
        "item_owned",
        "term_meaning",
        "harm_caused",
        "promise_broken",
        "resource_taken",
        "other",
    }


def test_forbidden_justice_vocabulary_is_closed() -> None:
    assert {
        "verdict",
        "judge",
        "court",
        "jury",
        "jurisdiction",
        "guilt",
        "liable",
        "liability",
        "binding",
        "enforce",
    } <= DISPUTE_FORBIDDEN_FIELD_NAMES

    enum_types = (
        DisputeKind,
        DisputeClaimRole,
        DisputeClaimPolarity,
        DisputeClaimKind,
        DisputeSubjectKind,
        DisputeStatus,
        DisputeEvidenceChannel,
        DisputeEvidenceReferenceKind,
        DisputeTestimonyChannel,
        DisputeRuleApplicability,
        DisputeRuleInterpretation,
        DisputeRuleReferenceStatus,
        DisputeAuthorityKind,
        DisputeMediationLinkStatus,
        DisputeResolutionSource,
        DisputeResolutionStatus,
        DisputeResolutionTermKind,
        DisputeResolutionResponseKind,
        DisputeProvenance,
        DisputeReportKind,
    )
    tokens: set[str] = set()
    for enum_type in enum_types:
        for member in enum_type:
            tokens.add(member.name.lower())
            tokens.add(member.value)
    assert tokens.isdisjoint(DISPUTE_FORBIDDEN_FIELD_NAMES)


def test_no_global_nondeterminism_imports() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".")[0])

    assert imported.isdisjoint({"random", "secrets", "uuid", "time", "datetime"})
