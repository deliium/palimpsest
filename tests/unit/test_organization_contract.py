"""Closed V4-03 organization contract: enums, identity grammar, policy, errors."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from agents.cognition import (
    FORBIDDEN_ORGANIZATION_LABEL_TOKENS,
    ORGANIZATION_ANALYTICAL_ID_PREFIX,
    ORGANIZATION_CONCEPT_ERROR_CODES,
    ORGANIZATION_CONCEPT_ID_PREFIX,
    ORGANIZATION_CONCEPT_POLICY_VERSION,
    ORGANIZATION_ID_HEX_LEN,
    ORGANIZATION_PUBLICATION_ID_PREFIX,
    OrganizationCommitmentRole,
    OrganizationConceptError,
    OrganizationConceptPolicy,
    OrganizationConceptualization,
    OrganizationEvidenceChannel,
    OrganizationGoalKind,
    OrganizationIdentityStance,
    OrganizationLineageKind,
    OrganizationMembershipBasis,
    OrganizationMembershipStatus,
    OrganizationProcedureKind,
    OrganizationRecordKind,
    OrganizationResourceKind,
    OrganizationRevisionKind,
    OrganizationStatus,
    OrganizationTemporalScope,
    default_organization_concept_policy,
    organization_concept_id,
    organization_label_is_forbidden,
    organization_lineage_id,
    require_organization_analytical_id,
    require_organization_concept_id,
    require_organization_label,
    require_organization_publication_id,
    require_organization_tick,
)

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src"
MODULE = SRC / "agents" / "cognition" / "organization_concepts.py"

OWNER = "agent-1"
TICK = 12
MEMBERS = ("agent-3", "agent-1", "agent-2")
ANCHORS = ("project-alpha", "repository-beta")


def test_policy_version_and_id_prefixes_are_frozen() -> None:
    assert ORGANIZATION_CONCEPT_POLICY_VERSION == "organization-concepts.v1"
    assert ORGANIZATION_CONCEPT_ID_PREFIX == "orgc-"
    assert ORGANIZATION_ANALYTICAL_ID_PREFIX == "org-"
    assert ORGANIZATION_PUBLICATION_ID_PREFIX == "org-edge-"
    assert ORGANIZATION_ID_HEX_LEN == 16


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    (
        (
            OrganizationStatus,
            {"candidate", "recognized", "disputed", "dissolved", "retired"},
        ),
        (
            OrganizationMembershipStatus,
            {"explicit", "perceived", "disputed", "unknown", "former"},
        ),
        (OrganizationTemporalScope, {"ongoing", "temporary", "unknown"}),
        (
            OrganizationEvidenceChannel,
            {"observed", "communicated", "remembered", "recorded"},
        ),
        (
            OrganizationMembershipBasis,
            {
                "self_identification",
                "participation",
                "role_occupancy",
                "collective_participation",
                "communicated_claim",
                "record_reference",
                "inference",
            },
        ),
        (
            OrganizationIdentityStance,
            {"member", "affiliated", "outside", "unknown"},
        ),
        (
            OrganizationConceptualization,
            {"none", "named_usual", "named_custom"},
        ),
        (
            OrganizationGoalKind,
            {
                "collective_project",
                "public_good",
                "resource_allocation",
                "migration",
                "shared_defense",
                "storage",
                "norm_enforcement",
                "unknown",
            },
        ),
        (
            OrganizationResourceKind,
            {
                "repository",
                "artifact",
                "stored_resource",
                "shelter",
                "territory",
                "unknown",
            },
        ),
        (
            OrganizationProcedureKind,
            {"institution_concept", "social_convention", "unknown"},
        ),
        (OrganizationRecordKind, {"artifact", "repository", "unknown"}),
        (OrganizationCommitmentRole, {"debtor", "creditor"}),
        (
            OrganizationRevisionKind,
            {
                "membership_revised",
                "role_revised",
                "goal_revised",
                "resource_revised",
                "procedure_revised",
                "record_revised",
                "commitment_revised",
                "identity_revised",
                "continued",
                "split",
                "merged",
                "dissolved",
                "revived",
            },
        ),
        (
            OrganizationLineageKind,
            {
                "continued",
                "transformed",
                "split",
                "merge",
                "dissolved",
                "emerged",
            },
        ),
    ),
)
def test_enum_membership_is_closed(enum_type: type[object], expected: set[str]) -> None:
    assert {member.value for member in enum_type} == expected  # type: ignore[attr-defined]
    for value in expected:
        assert enum_type(value).value == value  # type: ignore[call-arg]


def test_concept_id_is_stable_under_permutation_and_tick_sensitive() -> None:
    base = organization_concept_id(OWNER, TICK, MEMBERS, ANCHORS)
    assert base.startswith(ORGANIZATION_CONCEPT_ID_PREFIX)
    assert len(base) == len(ORGANIZATION_CONCEPT_ID_PREFIX) + ORGANIZATION_ID_HEX_LEN
    assert base == organization_concept_id(
        OWNER, TICK, tuple(reversed(MEMBERS)), tuple(reversed(ANCHORS))
    )
    assert base == organization_concept_id(OWNER, TICK, MEMBERS, ANCHORS)
    assert base != organization_concept_id(OWNER, TICK + 1, MEMBERS, ANCHORS)
    assert base != organization_concept_id(OWNER, TICK, MEMBERS, ("anchor-other",))
    assert base != organization_concept_id("agent-2", TICK, MEMBERS, ANCHORS)
    assert require_organization_concept_id(base) == base


def test_concept_id_rejects_invalid_creation_evidence() -> None:
    with pytest.raises(OrganizationConceptError) as excinfo:
        organization_concept_id("", TICK, MEMBERS, ANCHORS)
    assert excinfo.value.code == "organization_invalid_owner"

    with pytest.raises(OrganizationConceptError) as excinfo:
        organization_concept_id(OWNER, -1, MEMBERS, ANCHORS)
    assert excinfo.value.code == "organization_tick_regression"

    with pytest.raises(OrganizationConceptError) as excinfo:
        organization_concept_id(OWNER, True, MEMBERS, ANCHORS)  # type: ignore[arg-type]
    assert excinfo.value.code == "organization_tick_regression"

    with pytest.raises(OrganizationConceptError) as excinfo:
        organization_concept_id(OWNER, TICK, (), ANCHORS)
    assert excinfo.value.code == "organization_invalid_member"

    with pytest.raises(OrganizationConceptError) as excinfo:
        organization_concept_id(OWNER, TICK, ("agent-1", "agent-1"), ANCHORS)
    assert excinfo.value.code == "organization_duplicate_member"

    with pytest.raises(OrganizationConceptError) as excinfo:
        organization_concept_id(OWNER, TICK, MEMBERS, ())
    assert excinfo.value.code == "organization_unknown_anchor"


def test_lineage_id_is_stable_and_direction_sensitive() -> None:
    first = organization_concept_id(OWNER, TICK, MEMBERS, ANCHORS)
    second = organization_concept_id(OWNER, TICK, ("agent-4",), ("anchor-2",))
    edge = organization_lineage_id(OWNER, "split", TICK + 1, (first,), (second,))
    assert edge == organization_lineage_id(
        OWNER, "split", TICK + 1, (first,), (second,)
    )
    assert edge != organization_lineage_id(
        OWNER, "split", TICK + 1, (second,), (first,)
    )
    assert edge != organization_lineage_id(
        OWNER, "merge", TICK + 1, (first,), (second,)
    )

    with pytest.raises(OrganizationConceptError) as excinfo:
        organization_lineage_id(OWNER, "split", TICK, (), (second,))
    assert excinfo.value.code == "organization_invalid_lineage"


def test_identity_grammars_are_distinct() -> None:
    concept = organization_concept_id(OWNER, TICK, MEMBERS, ANCHORS)
    assert require_organization_concept_id(concept) == concept

    analytical = f"{ORGANIZATION_ANALYTICAL_ID_PREFIX}{'a' * 16}"
    assert require_organization_analytical_id(analytical) == analytical

    publication = f"{ORGANIZATION_PUBLICATION_ID_PREFIX}{'b' * 16}"
    assert require_organization_publication_id(publication) == publication

    for value, checker in (
        (analytical, require_organization_concept_id),
        (publication, require_organization_concept_id),
        (concept, require_organization_analytical_id),
        (concept, require_organization_publication_id),
        ("orgc-XYZ", require_organization_concept_id),
    ):
        with pytest.raises(OrganizationConceptError) as excinfo:
            checker(value)
        assert excinfo.value.code == "organization_invalid_id"


def test_policy_is_locked_and_rejects_mutation() -> None:
    policy = OrganizationConceptPolicy()
    assert policy == default_organization_concept_policy()
    assert policy.max_concepts == 16
    assert policy.max_members == 32
    assert policy.window_ticks == 100
    assert policy.recognition_floor == 0.45
    assert policy.retire_floor == 0.12
    assert policy.temporary_default_ticks == 16
    assert policy.merge_jaccard == 0.5
    assert policy.split_containment == 0.4

    with pytest.raises(OrganizationConceptError) as excinfo:
        replace(policy, window_ticks=101)
    assert excinfo.value.code == "organization_policy_mismatch"

    with pytest.raises(OrganizationConceptError) as excinfo:
        replace(policy, max_members=True)
    assert excinfo.value.code == "organization_policy_mismatch"


def test_forbidden_labels_are_rejected() -> None:
    for token in (
        "government",
        "church",
        "corporation",
        "army",
        "university",
        "guild",
        "state",
        "nation",
        "polity",
        "empire",
        "tribe",
        "treasury",
        "bank",
        "court",
        "police",
        "party",
        "religion",
        "ministry",
        "department",
        "firm",
        "company",
    ):
        assert token in FORBIDDEN_ORGANIZATION_LABEL_TOKENS
        assert organization_label_is_forbidden(token) is True
        with pytest.raises(OrganizationConceptError) as excinfo:
            require_organization_label(f"The {token.title()}")
        assert excinfo.value.code == "organization_forbidden_label"

    assert organization_label_is_forbidden("the water carriers") is False
    assert organization_label_is_forbidden("statemakers") is False
    assert require_organization_label("  the water carriers  ") == (
        "the water carriers"
    )

    with pytest.raises(OrganizationConceptError) as excinfo:
        require_organization_label("   ")
    assert excinfo.value.code == "organization_forbidden_label"


def test_error_codes_are_stable_and_payload_free() -> None:
    assert ORGANIZATION_CONCEPT_ERROR_CODES == frozenset(
        {
            "organization_invalid_owner",
            "organization_invalid_id",
            "organization_invalid_status",
            "organization_invalid_member",
            "organization_duplicate_member",
            "organization_unknown_anchor",
            "organization_tick_regression",
            "organization_cap_exceeded",
            "organization_foreign_ledger",
            "organization_forbidden_label",
            "organization_invalid_temporal_scope",
            "organization_invalid_lineage",
            "organization_lineage_cycle",
            "organization_policy_mismatch",
            "organization_invalid_claim",
        }
    )
    error = OrganizationConceptError("organization_invalid_member")
    assert error.code == "organization_invalid_member"
    assert str(error) == "organization_invalid_member"
    assert error.args == ("organization_invalid_member",)

    with pytest.raises(ValueError):
        OrganizationConceptError("organization_custom_payload_agent-1")

    assert require_organization_tick(0) == 0


def test_contract_module_imports_only_stdlib_and_cognition_contracts() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)

    import sys

    stdlib = set(sys.stdlib_module_names)
    assert roots <= stdlib | {"agents"}, roots
    assert roots & {"world", "simulation", "analysis", "experiments"} == set()
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "class Government",
        "class Church",
        "class Corporation",
        "class Army",
        "class University",
        "class Guild",
    ):
        assert forbidden not in source
