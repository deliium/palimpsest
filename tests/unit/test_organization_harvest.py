"""Detached organization harvest: rows, ordering, and owner isolation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition import (
    OrganizationConceptLedger,
    apply_organization_concept_update,
    default_organization_concept_policy,
    empty_organization_concept_ledger,
)
from agents.models import AgentId
from analysis import (
    OrganizationAnalysisError,
    harvest_organization_rows,
    harvest_organization_snapshot,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservedCollectiveProject,
    ObservedProjectContribution,
)

pytestmark = pytest.mark.unit

MODULE = Path(__file__).resolve().parents[2] / "src" / "analysis" / "organizations.py"


def _ledger(tick: int = 3, owner: str = "ada") -> OrganizationConceptLedger:
    project = ObservedCollectiveProject(
        project_id=EntityId("project-1"),
        location_id=EntityId("clearing"),
        kind="store",
        status="active",
        labor_done=2,
        materials_done=0,
        contributions=(
            ObservedProjectContribution(
                actor_id=EntityId("body-ada"),
                tick=tick - 1,
                accepted=True,
                labor_delta=1,
            ),
            ObservedProjectContribution(
                actor_id=EntityId("body-ben"),
                tick=tick - 1,
                accepted=True,
                labor_delta=1,
            ),
        ),
    )
    observation = Observation(
        world_id=WorldId("world-harvest"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(tick),
        tick=tick,
        collective_projects=(project,),
    )
    return apply_organization_concept_update(
        owner_id=owner,
        tick=tick,
        observation=observation,
        prior=None,
        institution_concepts=None,
        offices=None,
        group_formation=None,
        collective_decisions=None,
        structured_commitments=None,
        social_conventions=None,
        policy=default_organization_concept_policy(),
    )


def test_harvest_preserves_rows_and_order() -> None:
    rows = harvest_organization_rows((_ledger(),))
    assert len(rows) == 1
    harvest = rows[0]
    assert harvest.owner.owner_id == "ada"
    assert harvest.owner.policy_version == "organization-concepts.v1"
    assert harvest.owner.concept_count == len(harvest.concepts) == 1
    assert harvest.concepts[0].organization_id.startswith("orgc-")
    assert [member.member_id for member in harvest.members] == [
        "body-ada",
        "body-ben",
    ]
    assert harvest.goals[0].anchor_id == "project-1"
    assert harvest.windows
    assert harvest.concepts[0].structural_signature


def test_harvest_orders_multiple_owners() -> None:
    rows = harvest_organization_rows((_ledger(owner="ben"), _ledger()))
    assert len(rows) == 2
    assert [row.owner.owner_id for row in rows] == ["ada", "ben"]


def test_harvest_accepts_already_harvested_rows() -> None:
    first = harvest_organization_rows((_ledger(),))
    assert harvest_organization_rows(first) == first


def test_empty_or_missing_ledgers_yield_empty_rows() -> None:
    assert harvest_organization_rows(None) == ()
    assert harvest_organization_rows(()) == ()
    assert harvest_organization_snapshot(object()) == ()
    empty = empty_organization_concept_ledger(AgentId("ada"))
    rows = harvest_organization_rows((empty,))
    assert rows[0].concepts == ()
    assert rows[0].members == ()


def test_foreign_owner_concept_is_rejected() -> None:
    ledger = _ledger()
    concept = ledger.concepts[0]
    object.__setattr__(concept, "owner_id", AgentId("ben"))
    with pytest.raises(OrganizationAnalysisError) as excinfo:
        harvest_organization_rows((ledger,))
    assert excinfo.value.reason_code == "organization_row_owner_mismatch"


def test_duplicate_owner_ledger_is_rejected() -> None:
    with pytest.raises(OrganizationAnalysisError) as excinfo:
        harvest_organization_rows((_ledger(), _ledger(tick=4)))
    assert excinfo.value.reason_code == "organization_row_duplicate"


def test_harvest_module_does_not_import_cognition() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not node.module.startswith("agents.cognition")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("agents.cognition")
