"""Deterministic operation identities, ordering, and disagreement retention."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.cognition import (
    OrganizationAdmissionBelief,
    OrganizationAdmissionStance,
    OrganizationAuthorityBasis,
    OrganizationControlBelief,
    OrganizationControlStance,
    OrganizationOperationalConcept,
    OrganizationOperationalStatus,
    OrganizationOperationDomain,
    OrganizationOperationLedger,
    OrganizationOperationProvenance,
    OrganizationTemporalScope,
    organization_action_id,
    organization_decision_id,
    organization_publication_operation_id,
)
from agents.models import AgentId
from analysis.organization_operations import harvest_organization_operation_rows

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src" / "agents" / "cognition" / "organization_operations.py"
ANALYSIS_MODULE = ROOT / "src" / "analysis" / "organization_operations.py"

OWNER = AgentId("owner-1")
ORG_A = f"orgc-{'a' * 16}"
ORG_B = f"orgc-{'b' * 16}"


def _decision_id(**overrides: Any) -> str:
    material: dict[str, Any] = {
        "owner_id": OWNER.value,
        "organization_id": ORG_A,
        "domain": OrganizationOperationDomain.RESOURCE_CONTROL,
        "act": "authorize_control",
        "tick": 3,
        "actor_id": OWNER.value,
        "target_id": "",
        "anchor_kind": "resource",
        "anchor_id": "anchor-1",
        "stance": "recognized",
    }
    material.update(overrides)
    return organization_decision_id(**material)


def test_decision_id_is_content_addressed() -> None:
    base = _decision_id()
    assert base.startswith("orgd-")
    assert base == _decision_id()
    for field, value in (
        ("tick", 4),
        ("domain", OrganizationOperationDomain.STORAGE),
        ("act", "revoke_control"),
        ("anchor_id", "anchor-2"),
        ("stance", "disputed"),
    ):
        assert _decision_id(**{field: value}) != base


def test_action_and_publication_ids_are_content_addressed() -> None:
    decision = _decision_id()
    action = organization_action_id(
        OWNER.value, ORG_A, decision, 3, OWNER.value, "give", "item", "item-1"
    )
    assert action.startswith("orga-")
    assert action == organization_action_id(
        OWNER.value, ORG_A, decision, 3, OWNER.value, "give", "item", "item-1"
    )
    assert action != organization_action_id(
        OWNER.value, ORG_A, decision, 4, OWNER.value, "give", "item", "item-1"
    )

    published = organization_publication_operation_id(
        f"org-{'a' * 16}", "resource_control", 3, 0, "d" * 64
    )
    assert published.startswith("orgop-")
    assert published == organization_publication_operation_id(
        f"org-{'a' * 16}", "resource_control", 3, 0, "d" * 64
    )
    assert published != organization_publication_operation_id(
        f"org-{'a' * 16}", "resource_control", 3, 1, "d" * 64
    )


def _control(support: int) -> OrganizationControlBelief:
    return OrganizationControlBelief(
        domain=OrganizationOperationDomain.RESOURCE_CONTROL,
        anchor_kind="resource",
        anchor_id=f"anchor-{support}",
        stance=OrganizationControlStance.RECOGNIZED,
        authority_basis=OrganizationAuthorityBasis.ROLE_BELIEF,
        legitimacy_doctrine="role_trusteeship",
        decision_ref=None,
        role_ref=None,
        first_tick=1,
        last_tick=9,
        owner_support_count=support,
        contest_count=0,
    )


def _admission(
    *, stance: OrganizationAdmissionStance = OrganizationAdmissionStance.ADMITTED
) -> OrganizationAdmissionBelief:
    return OrganizationAdmissionBelief(
        member_id="member-a",
        stance=stance,
        authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
        role_ref=None,
        decision_ref=None,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        expires_tick=None,
        first_tick=1,
        last_tick=9,
        owner_support_count=1,
        contest_count=0,
    )


def _concept(
    *,
    organization_id: str = ORG_A,
    controls: tuple[OrganizationControlBelief, ...] = (),
    admissions: tuple[OrganizationAdmissionBelief, ...] = (),
) -> OrganizationOperationalConcept:
    return OrganizationOperationalConcept(
        organization_id=organization_id,
        owner_id=OWNER,
        status=OrganizationOperationalStatus.ACTIVE,
        first_tick=1,
        last_tick=9,
        controls=controls,
        admissions=admissions,
    )


@settings(max_examples=25, deadline=None)
@given(st.lists(st.integers(min_value=1, max_value=20), min_size=1, max_size=4))
def test_permuted_inputs_harvest_identically(supports: list[int]) -> None:
    records = tuple(_control(support) for support in supports)
    forward = harvest_organization_operation_rows(
        (
            OrganizationOperationLedger(
                owner_id=OWNER, concepts=(_concept(controls=records),)
            ),
        )
    )
    backward = harvest_organization_operation_rows(
        (
            OrganizationOperationLedger(
                owner_id=OWNER, concepts=(_concept(controls=tuple(reversed(records))),)
            ),
        )
    )
    assert forward == backward
    assert [
        (row.anchor_id, row.owner_support_count) for row in forward[0].controls
    ] == sorted((row.anchor_id, row.owner_support_count) for row in forward[0].controls)


def test_conflicting_stances_are_both_retained() -> None:
    concept = _concept(
        admissions=(
            _admission(stance=OrganizationAdmissionStance.ADMITTED),
            _admission(stance=OrganizationAdmissionStance.DISPUTED),
        )
    )
    rows = harvest_organization_operation_rows(
        (OrganizationOperationLedger(owner_id=OWNER, concepts=(concept,)),)
    )
    assert len(rows[0].admissions) == 2
    assert {row.stance for row in rows[0].admissions} == {"admitted", "disputed"}
    assert rows[0].has_contest is True


def test_operation_modules_have_no_ambient_identity_sources() -> None:
    for path in (MODULE, ANALYSIS_MODULE):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert "uuid4" not in names
        assert "uuid1" not in names
        assert "time" not in names
        assert "datetime" not in names
        assert "hash(" not in source


def test_operation_provenance_is_closed() -> None:
    assert {code.value for code in OrganizationOperationProvenance} == {
        "self_authored",
        "role_authorized",
        "decision_supported",
        "procedure_recognized",
        "observed_effect",
        "unknown_authority",
        "contested",
        "expired",
        "orphaned",
    }
