"""Contract tests for the frozen organization collective-agency vocabulary."""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any

import pytest

import agents.cognition as cognition
from agents.cognition import organization_agency
from agents.cognition.organization_agency import (
    FORBIDDEN_AGENCY_FIELD_NAMES,
    ORGANIZATION_AGENCY_CONTRARY_EFFECTS,
    ORGANIZATION_AGENCY_DOMAIN_EFFECTS,
    ORGANIZATION_AGENCY_EFFECTS,
    ORGANIZATION_AGENCY_NOTICE_CODES,
    ORGANIZATION_AGENCY_REF_NAMESPACES,
    ORGANIZATION_AGENCY_TARGET_KINDS,
    OrganizationAgencyEffect,
    OrganizationAgencyError,
    OrganizationAgencyImplementationMode,
    OrganizationAgencyImplementationStatus,
    OrganizationAgencyPolicy,
    OrganizationAgencyPositionStance,
    OrganizationAgencyProposalStatus,
    OrganizationAgencyProvenance,
    OrganizationAgencyRecognition,
    OrganizationAgencyReportKind,
    OrganizationAgencyTopic,
    default_organization_agency_policy,
    organization_agency_evidence_id,
    organization_agency_ref,
    organization_amendment_id,
    organization_collective_decision_id,
    organization_implementation_id,
    organization_proposal_id,
    organization_publication_decision_id,
    organization_publication_implementation_id,
    require_organization_agency_evidence_id,
    require_organization_agency_ref,
    require_organization_amendment_id,
    require_organization_collective_decision_id,
    require_organization_implementation_id,
    require_organization_proposal_id,
    require_organization_publication_decision_id,
    require_organization_publication_implementation_id,
)

_REF = organization_agency_ref("proposal-material", namespace="proposal")


def _validators() -> list[tuple[Any, Any]]:
    return [
        (
            organization_proposal_id("owner-1", "orgc-0123456789abcdef", _REF),
            require_organization_proposal_id,
        ),
        (
            organization_amendment_id(
                "owner-1",
                "orgc-0123456789abcdef",
                organization_proposal_id("owner-1", "orgc-0123456789abcdef", _REF),
                1,
                _REF,
            ),
            require_organization_amendment_id,
        ),
        (
            organization_collective_decision_id(
                "owner-1",
                "orgc-0123456789abcdef",
                organization_proposal_id("owner-1", "orgc-0123456789abcdef", _REF),
                1,
                OrganizationAgencyRecognition.RECOGNIZED,
                3,
            ),
            require_organization_collective_decision_id,
        ),
        (
            organization_implementation_id(
                "owner-1",
                "orgc-0123456789abcdef",
                organization_collective_decision_id(
                    "owner-1",
                    "orgc-0123456789abcdef",
                    organization_proposal_id("owner-1", "orgc-0123456789abcdef", _REF),
                    1,
                    OrganizationAgencyRecognition.RECOGNIZED,
                    3,
                ),
                "agent-2",
                OrganizationAgencyImplementationMode.PHYSICAL,
                4,
            ),
            require_organization_implementation_id,
        ),
        (
            organization_agency_evidence_id(
                "owner-1", "orgc-0123456789abcdef", "observation", 5, 0, _REF
            ),
            require_organization_agency_evidence_id,
        ),
        (
            organization_publication_decision_id(
                "org-0123456789abcdef", _REF, 6, 0, "a" * 64
            ),
            require_organization_publication_decision_id,
        ),
        (
            organization_publication_implementation_id(
                "org-0123456789abcdef",
                organization_publication_decision_id(
                    "org-0123456789abcdef", _REF, 6, 0, "a" * 64
                ),
                _REF,
                7,
                0,
                "b" * 64,
            ),
            require_organization_publication_implementation_id,
        ),
    ]


def test_id_grammar_accepts_exactly_sixteen_lowercase_hex() -> None:
    for value, validator in _validators():
        assert validator(value) == value


@pytest.mark.parametrize(
    "bad",
    [
        "orgp-0123456789ABCDEF",
        "orgp-0123456789abcde",
        "orgp-0123456789abcdef0",
        "orgc-0123456789abcdef",
        "orgd-0123456789abcdef",
        "orga-0123456789abcdef",
        "orgp-x",
        "orgp-0123456789abcdeg",
        "",
    ],
)
def test_proposal_grammar_rejects_foreign_or_malformed_ids(bad: str) -> None:
    with pytest.raises(OrganizationAgencyError) as excinfo:
        require_organization_proposal_id(bad)
    assert excinfo.value.code == "organization_agency_invalid"


def test_each_minter_is_deterministic_and_material_sensitive() -> None:
    first = organization_proposal_id("owner-1", "orgc-0123456789abcdef", _REF)
    assert first == organization_proposal_id("owner-1", "orgc-0123456789abcdef", _REF)
    assert first != organization_proposal_id("owner-2", "orgc-0123456789abcdef", _REF)
    assert first != organization_proposal_id(
        "owner-1",
        "orgc-0123456789abcdef",
        organization_agency_ref("other", namespace="proposal"),
    )

    decision = organization_collective_decision_id(
        "owner-1",
        "orgc-0123456789abcdef",
        first,
        1,
        OrganizationAgencyRecognition.RECOGNIZED,
        3,
    )
    assert decision == organization_collective_decision_id(
        "owner-1",
        "orgc-0123456789abcdef",
        first,
        1,
        OrganizationAgencyRecognition.RECOGNIZED,
        3,
    )
    assert decision != organization_collective_decision_id(
        "owner-1",
        "orgc-0123456789abcdef",
        first,
        1,
        OrganizationAgencyRecognition.CONTESTED,
        3,
    )


def test_agency_ref_never_carries_owner_or_local_ids() -> None:
    for namespace in sorted(ORGANIZATION_AGENCY_REF_NAMESPACES):
        ref = organization_agency_ref("material", namespace=namespace)
        assert len(ref) == 16
        assert "orgc-" not in ref
        assert "orgp-" not in ref
        assert "owner" not in ref


def test_agency_ref_rejects_unknown_namespace() -> None:
    with pytest.raises(OrganizationAgencyError) as excinfo:
        organization_agency_ref("material", namespace="owner")
    assert excinfo.value.code == "organization_agency_invalid_ref"


def test_require_ref_rejects_non_hex() -> None:
    with pytest.raises(OrganizationAgencyError):
        require_organization_agency_ref("z" * 16)


def test_default_policy_is_accepted_and_each_field_is_locked() -> None:
    policy = default_organization_agency_policy()
    assert policy == OrganizationAgencyPolicy()
    for field in fields(OrganizationAgencyPolicy):
        with pytest.raises(OrganizationAgencyError) as excinfo:
            replace(policy, **{field.name: getattr(policy, field.name) + 1})
        assert excinfo.value.code == "organization_agency_policy_mismatch"


def test_effects_are_closed_real_observation_tokens() -> None:
    for effect in OrganizationAgencyEffect:
        assert effect.value in ORGANIZATION_AGENCY_EFFECTS
    assert "none" in ORGANIZATION_AGENCY_EFFECTS
    assert all(isinstance(item, str) for item in ORGANIZATION_AGENCY_EFFECTS)


def test_every_domain_maps_to_non_empty_expected_effects() -> None:
    assert set(ORGANIZATION_AGENCY_DOMAIN_EFFECTS) == set(
        cognition.OrganizationOperationDomain
    )
    for effects in ORGANIZATION_AGENCY_DOMAIN_EFFECTS.values():
        assert effects
        assert effects <= ORGANIZATION_AGENCY_EFFECTS
        assert "none" in effects


def test_contrary_effects_are_disjoint_from_expected_effects() -> None:
    for effects in ORGANIZATION_AGENCY_DOMAIN_EFFECTS.values():
        assert not (effects & ORGANIZATION_AGENCY_CONTRARY_EFFECTS)


def test_forbidden_field_names_cover_magic_actor_vocabulary() -> None:
    for name in (
        "will",
        "consensus",
        "binding",
        "permission",
        "organization_llm",
        "command",
        "collective_prompt",
    ):
        assert name in FORBIDDEN_AGENCY_FIELD_NAMES


def test_closed_enums_and_notice_codes_are_exact() -> None:
    assert {item.value for item in OrganizationAgencyTopic} == {
        "resource_use",
        "storage",
        "record_keeping",
        "membership",
        "role",
        "procedure",
        "commitment",
        "other",
    }
    assert {item.value for item in OrganizationAgencyProposalStatus} == {
        "draft",
        "active",
        "amended",
        "withdrawn",
        "decided",
        "expired",
        "unknown",
    }
    assert {item.value for item in OrganizationAgencyPositionStance} == {
        "support",
        "oppose",
        "abstain",
        "amend",
        "withdraw",
        "unknown",
    }
    assert {item.value for item in OrganizationAgencyRecognition} == {
        "recognized",
        "contested",
        "unrecognized",
        "expired",
        "unknown",
    }
    assert {item.value for item in OrganizationAgencyImplementationStatus} == {
        "pending",
        "implemented",
        "partial",
        "unimplemented",
        "obstructed",
        "refused",
        "sabotaged",
        "contrary",
        "unknown",
        "expired",
    }
    assert {item.value for item in OrganizationAgencyImplementationMode} == {
        "physical",
        "testimonial",
    }
    assert {item.value for item in OrganizationAgencyReportKind} == {
        "implemented",
        "partial",
        "unimplemented",
        "refusal",
        "sabotage",
    }
    assert {item.value for item in OrganizationAgencyProvenance} == {
        "self_authored",
        "communicated",
        "procedure_recognized",
        "observed_effect",
        "declared_refusal",
        "contrary_effect",
        "declared_sabotage",
        "contested",
        "unrecognized",
        "expired",
        "orphaned",
        "unknown",
    }
    assert ORGANIZATION_AGENCY_TARGET_KINDS == {
        "item",
        "resource",
        "artifact",
        "structure",
        "repository",
        "collective_project",
        "commitment",
        "location",
        "agent",
        "none",
        "unknown",
    }
    assert ORGANIZATION_AGENCY_NOTICE_CODES == {
        "proposal_expired",
        "amendment_out_of_order",
        "procedure_unresolved",
        "target_unresolved",
        "agency_truncated",
        "implementation_truncated",
        "refusal_unverified",
        "sabotage_unverified",
        "orphaned_concept",
        "foreign_owner",
        "malformed_claim",
    }


def test_public_facade_exports_every_new_symbol() -> None:
    exported = set(organization_agency.__all__)
    for name in exported:
        assert hasattr(cognition, name), name
        assert name in cognition.__all__, name
