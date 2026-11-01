"""Closed V4-04 organization operation contract: enums, policy, ids, refs."""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields, replace
from enum import StrEnum
from pathlib import Path

import pytest

from agents.cognition import (
    ORGANIZATION_ACTION_ID_PREFIX,
    ORGANIZATION_DECISION_ID_PREFIX,
    ORGANIZATION_ID_HEX_LEN,
    ORGANIZATION_LEGITIMACY_DOCTRINES,
    ORGANIZATION_OPERATION_ANALYSIS_POLICY_VERSION,
    ORGANIZATION_OPERATION_ERROR_CODES,
    ORGANIZATION_OPERATION_EVIDENCE_ID_PREFIX,
    ORGANIZATION_OPERATION_POLICY_VERSION,
    ORGANIZATION_OPERATION_REF_NAMESPACES,
    ORGANIZATION_PUBLICATION_OPERATION_ID_PREFIX,
    OrganizationAdmissionStance,
    OrganizationAssignmentStance,
    OrganizationAuthorityBasis,
    OrganizationCommitmentStance,
    OrganizationControlStance,
    OrganizationDepartureStance,
    OrganizationOperationAct,
    OrganizationOperationDomain,
    OrganizationOperationError,
    OrganizationOperationOutcome,
    OrganizationOperationPolicy,
    OrganizationOperationProvenance,
    default_organization_operation_policy,
    organization_action_id,
    organization_decision_id,
    organization_operation_evidence_id,
    organization_operation_ref,
    organization_publication_operation_id,
    require_organization_action_id,
    require_organization_decision_id,
    require_organization_operation_evidence_id,
    require_organization_operation_ref,
    require_organization_publication_operation_id,
)

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src"
MODULE = SRC / "agents" / "cognition" / "organization_operations.py"

OWNER = "agent-1"
ORGANIZATION = f"orgc-{'a' * 16}"
DECISION = f"{ORGANIZATION_DECISION_ID_PREFIX}{'b' * 16}"
TICK = 12


def test_policy_versions_and_id_prefixes_are_frozen() -> None:
    assert ORGANIZATION_OPERATION_POLICY_VERSION == "organization-operations.v1"
    assert (
        ORGANIZATION_OPERATION_ANALYSIS_POLICY_VERSION
        == "organization-operations-analysis.v1"
    )
    assert ORGANIZATION_DECISION_ID_PREFIX == "orgd-"
    assert ORGANIZATION_ACTION_ID_PREFIX == "orga-"
    assert ORGANIZATION_PUBLICATION_OPERATION_ID_PREFIX == "orgop-"
    assert ORGANIZATION_OPERATION_EVIDENCE_ID_PREFIX == "orgev-"
    assert ORGANIZATION_ID_HEX_LEN == 16
    assert ORGANIZATION_OPERATION_REF_NAMESPACES == frozenset(
        {"target", "anchor", "role_signature", "decision_content"}
    )


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    (
        (
            OrganizationOperationDomain,
            (
                "resource_control",
                "storage",
                "record_keeping",
                "membership_admission",
                "membership_departure",
                "role_assignment",
                "procedure_action",
                "internal_commitment",
            ),
        ),
        (
            OrganizationOperationAct,
            (
                "admit",
                "depart",
                "assign",
                "remove",
                "authorize_control",
                "revoke_control",
                "invoke_procedure",
                "declare_commitment",
                "fulfill_commitment",
                "record_decision",
            ),
        ),
        (
            OrganizationControlStance,
            (
                "claimed",
                "recognized",
                "shared",
                "disputed",
                "former",
                "unknown",
            ),
        ),
        (
            OrganizationAdmissionStance,
            (
                "admitted",
                "claimed",
                "self_joined",
                "denied",
                "disputed",
                "former",
                "unknown",
            ),
        ),
        (
            OrganizationDepartureStance,
            ("resigned", "expelled", "departed", "disputed", "unknown"),
        ),
        (
            OrganizationAssignmentStance,
            ("assigned", "claimed", "disputed", "removed", "vacant", "unknown"),
        ),
        (
            OrganizationCommitmentStance,
            (
                "declared",
                "accepted",
                "fulfilled",
                "violated",
                "disputed",
                "forgotten",
                "unknown",
            ),
        ),
        (
            OrganizationAuthorityBasis,
            (
                "self_authored",
                "role_belief",
                "decision_belief",
                "procedure_belief",
                "record_reference",
                "observation",
                "unknown",
            ),
        ),
        (
            OrganizationOperationOutcome,
            ("observed", "attempted", "completed", "blocked", "unknown"),
        ),
        (
            OrganizationOperationProvenance,
            (
                "self_authored",
                "role_authorized",
                "decision_supported",
                "procedure_recognized",
                "observed_effect",
                "unknown_authority",
                "contested",
                "expired",
                "orphaned",
            ),
        ),
    ),
)
def test_enum_membership_is_closed_and_ordered(
    enum_type: type[StrEnum], expected: tuple[str, ...]
) -> None:
    assert tuple(member.value for member in enum_type) == expected
    for value in expected:
        assert enum_type(value).value == value


def test_domains_match_the_eight_requested_primitives() -> None:
    assert {domain.value for domain in OrganizationOperationDomain} == {
        "resource_control",
        "storage",
        "record_keeping",
        "membership_admission",
        "membership_departure",
        "role_assignment",
        "procedure_action",
        "internal_commitment",
    }


def test_legitimacy_doctrines_are_closed() -> None:
    assert ORGANIZATION_LEGITIMACY_DOCTRINES == frozenset(
        {
            "none",
            "group_owns",
            "role_trusteeship",
            "decision_grant",
            "first_claimant_owns",
            "shared_use",
            "unknown",
        }
    )


def test_error_codes_are_closed() -> None:
    assert {
        "organization_operation_invalid",
        "organization_operation_policy_mismatch",
        "organization_operation_foreign_ledger",
        "organization_operation_cap_exceeded",
        "organization_operation_unknown_concept",
        "organization_operation_unknown_decision",
        "organization_operation_tick_regression",
        "organization_operation_invalid_ref",
        "organization_duplicate_operation",
    } <= ORGANIZATION_OPERATION_ERROR_CODES


def test_policy_is_locked_and_has_no_version_field() -> None:
    policy = OrganizationOperationPolicy()
    assert policy == default_organization_operation_policy()
    assert default_organization_operation_policy() is (
        default_organization_operation_policy()
    )
    assert policy.max_concepts == 16
    assert policy.max_controls == 32
    assert policy.max_admissions == 32
    assert policy.max_departures == 32
    assert policy.max_assignments == 16
    assert policy.max_procedures == 16
    assert policy.max_commitments == 16
    assert policy.max_decisions == 32
    assert policy.max_actions == 64
    assert policy.max_evidence_per_record == 8
    assert policy.max_total_evidence == 256
    assert policy.max_total_records == 256
    assert policy.max_owner_support == 32
    assert policy.max_contest == 32
    assert "version" not in {item.name for item in fields(policy)}

    with pytest.raises(OrganizationOperationError) as excinfo:
        replace(policy, max_controls=33)
    assert excinfo.value.code == "organization_operation_policy_mismatch"

    with pytest.raises(OrganizationOperationError) as excinfo:
        replace(policy, max_actions=True)
    assert excinfo.value.code == "organization_operation_policy_mismatch"


def test_decision_id_is_stable_and_material_sensitive() -> None:
    base = organization_decision_id(
        OWNER,
        ORGANIZATION,
        "resource_control",
        "authorize_control",
        TICK,
        "agent-2",
        "agent-3",
        "repository",
        "repository-beta",
        "recognized",
    )
    assert base.startswith(ORGANIZATION_DECISION_ID_PREFIX)
    assert len(base) == len(ORGANIZATION_DECISION_ID_PREFIX) + ORGANIZATION_ID_HEX_LEN
    assert base == organization_decision_id(
        OWNER,
        ORGANIZATION,
        OrganizationOperationDomain.RESOURCE_CONTROL,
        OrganizationOperationAct.AUTHORIZE_CONTROL,
        TICK,
        "agent-2",
        "agent-3",
        "repository",
        "repository-beta",
        OrganizationControlStance.RECOGNIZED,
    )
    assert base != organization_decision_id(
        OWNER,
        ORGANIZATION,
        "resource_control",
        "authorize_control",
        TICK + 1,
        "agent-2",
        "agent-3",
        "repository",
        "repository-beta",
        "recognized",
    )
    for changed in (
        organization_decision_id(
            "agent-9",
            ORGANIZATION,
            "resource_control",
            "authorize_control",
            TICK,
            "agent-2",
            "agent-3",
            "repository",
            "repository-beta",
            "recognized",
        ),
        organization_decision_id(
            OWNER,
            ORGANIZATION,
            "storage",
            "authorize_control",
            TICK,
            "agent-2",
            "agent-3",
            "repository",
            "repository-beta",
            "recognized",
        ),
        organization_decision_id(
            OWNER,
            ORGANIZATION,
            "resource_control",
            "revoke_control",
            TICK,
            "agent-2",
            "agent-3",
            "repository",
            "repository-beta",
            "recognized",
        ),
        organization_decision_id(
            OWNER,
            ORGANIZATION,
            "resource_control",
            "authorize_control",
            TICK,
            "agent-4",
            "agent-3",
            "repository",
            "repository-beta",
            "recognized",
        ),
        organization_decision_id(
            OWNER,
            ORGANIZATION,
            "resource_control",
            "authorize_control",
            TICK,
            "agent-2",
            "agent-5",
            "repository",
            "repository-beta",
            "recognized",
        ),
        organization_decision_id(
            OWNER,
            ORGANIZATION,
            "resource_control",
            "authorize_control",
            TICK,
            "agent-2",
            "agent-3",
            "artifact",
            "repository-beta",
            "recognized",
        ),
        organization_decision_id(
            OWNER,
            ORGANIZATION,
            "resource_control",
            "authorize_control",
            TICK,
            "agent-2",
            "agent-3",
            "repository",
            "repository-gamma",
            "recognized",
        ),
        organization_decision_id(
            OWNER,
            ORGANIZATION,
            "resource_control",
            "authorize_control",
            TICK,
            "agent-2",
            "agent-3",
            "repository",
            "repository-beta",
            "disputed",
        ),
    ):
        assert changed != base
    assert require_organization_decision_id(base) == base


def test_action_id_is_stable_and_material_sensitive() -> None:
    base = organization_action_id(
        OWNER, ORGANIZATION, DECISION, TICK, "agent-2", "give", "agent", "agent-3"
    )
    assert base.startswith(ORGANIZATION_ACTION_ID_PREFIX)
    assert len(base) == len(ORGANIZATION_ACTION_ID_PREFIX) + ORGANIZATION_ID_HEX_LEN
    assert base == organization_action_id(
        OWNER, ORGANIZATION, DECISION, TICK, "agent-2", "give", "agent", "agent-3"
    )
    assert base != organization_action_id(
        OWNER, ORGANIZATION, DECISION, TICK, "agent-2", "store", "agent", "agent-3"
    )
    assert require_organization_action_id(base) == base


def test_publication_and_evidence_ids_are_stable() -> None:
    publication = organization_publication_operation_id(
        ORGANIZATION, "storage", TICK, 0, "digest-a"
    )
    assert publication.startswith(ORGANIZATION_PUBLICATION_OPERATION_ID_PREFIX)
    assert publication == organization_publication_operation_id(
        ORGANIZATION, "storage", TICK, 0, "digest-a"
    )
    assert publication != organization_publication_operation_id(
        ORGANIZATION, "storage", TICK, 1, "digest-a"
    )
    assert (
        require_organization_publication_operation_id(publication) == publication
    )

    evidence = organization_operation_evidence_id(
        OWNER, ORGANIZATION, "observed", TICK, 0, "ref-a"
    )
    assert evidence.startswith(ORGANIZATION_OPERATION_EVIDENCE_ID_PREFIX)
    assert evidence == organization_operation_evidence_id(
        OWNER, ORGANIZATION, "observed", TICK, 0, "ref-a"
    )
    assert evidence != organization_operation_evidence_id(
        OWNER, ORGANIZATION, "communicated", TICK, 0, "ref-a"
    )
    assert require_organization_operation_evidence_id(evidence) == evidence


def test_refs_are_stable_and_namespace_scoped() -> None:
    first = organization_operation_ref("repository-beta", namespace="anchor")
    assert len(first) == ORGANIZATION_ID_HEX_LEN
    assert first == organization_operation_ref("repository-beta", namespace="anchor")
    assert first != organization_operation_ref("repository-beta", namespace="target")
    assert first != organization_operation_ref("other", namespace="anchor")
    assert require_organization_operation_ref(first) == first


def test_malformed_identities_fail_closed() -> None:
    for helper in (
        require_organization_decision_id,
        require_organization_action_id,
        require_organization_publication_operation_id,
        require_organization_operation_evidence_id,
    ):
        with pytest.raises(OrganizationOperationError) as excinfo:
            helper("orgc-" + "a" * 16)
        assert excinfo.value.code == "organization_operation_invalid"

    with pytest.raises(OrganizationOperationError) as excinfo:
        require_organization_decision_id(f"orgd-{'A' * 16}")
    assert excinfo.value.code == "organization_operation_invalid"

    with pytest.raises(OrganizationOperationError) as excinfo:
        organization_operation_ref("value", namespace="peer_ledger")
    assert excinfo.value.code == "organization_operation_invalid_ref"

    with pytest.raises(OrganizationOperationError) as excinfo:
        organization_operation_ref("", namespace="target")
    assert excinfo.value.code == "organization_operation_invalid_ref"

    with pytest.raises(OrganizationOperationError) as excinfo:
        organization_decision_id(
            OWNER,
            ORGANIZATION,
            "resource_control",
            "admit",
            -1,
            "agent-2",
            "",
            "agent",
            "",
            "unknown",
        )
    assert excinfo.value.code == "organization_operation_tick_regression"

    with pytest.raises(OrganizationOperationError) as excinfo:
        organization_decision_id(
            "",
            ORGANIZATION,
            "resource_control",
            "admit",
            TICK,
            "agent-2",
            "",
            "agent",
            "",
            "unknown",
        )
    assert excinfo.value.code == "organization_operation_invalid"


def test_module_introduces_no_command_or_event_class() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert not {name for name in names if name.endswith(("Command", "Event"))}


def test_public_helpers_accept_no_peer_or_world_parameter() -> None:
    forbidden = ("peer", "other_owner", "all_ledgers", "runtimes", "world_state")
    for helper in (
        organization_decision_id,
        organization_action_id,
        organization_publication_operation_id,
        organization_operation_evidence_id,
        organization_operation_ref,
    ):
        parameters = set(inspect.signature(helper).parameters)
        assert not any(term in name for name in parameters for term in forbidden)
