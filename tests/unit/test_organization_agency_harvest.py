"""Detached harvest of owner collective-agency ledgers."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition import (
    OrganizationAgencyConcept,
    OrganizationAgencyError,
    OrganizationAgencyLedger,
    OrganizationStatus,
)
from agents.models import AgentId
from analysis.organization_agency import (
    harvest_organization_agency_rows,
    harvest_organization_agency_snapshot,
    organization_agency_concept_counts,
    organization_agency_decision_ticks,
)
from analysis.organization_contract import OrganizationAnalysisError
from tests.unit.organization_agency_helpers import (
    OTHER,
    OWNER,
    concept_id,
    concept_ledger,
    decision,
    implementation,
    position,
    proposal,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src" / "analysis" / "organization_agency.py"


def _ledger(owner: AgentId = OWNER) -> OrganizationAgencyLedger:
    concepts = concept_ledger()
    first = proposal(organization_id=concept_id(concepts))
    decided = decision(first)
    done = implementation(decided)
    stance = position(first.proposal_id, actor=OWNER)
    return OrganizationAgencyLedger(
        owner_id=owner,
        concepts=(
            OrganizationAgencyConcept(
                organization_id=concept_id(concepts),
                owner_id=owner,
                status=OrganizationStatus.RECOGNIZED,
                first_tick=1,
                last_tick=10,
                proposals=(first,),
                positions=(stance,),
                decisions=(decided,),
                implementations=(done,),
            ),
        ),
    )


def test_harvest_counts_rows() -> None:
    rows = harvest_organization_agency_rows((_ledger(),))
    assert len(rows) == 1
    row = rows[0]
    assert row.owner.owner_id == "agent-1"
    assert row.owner.concept_count == 1
    assert len(row.proposals) == 1
    assert len(row.positions) == 1
    assert len(row.decisions) == 1
    assert len(row.implementations) == 1


def test_harvest_none_and_empty_are_empty() -> None:
    assert harvest_organization_agency_rows(None) == ()
    assert harvest_organization_agency_rows(()) == ()
    assert harvest_organization_agency_snapshot(object()) == ()


def test_harvest_is_idempotent() -> None:
    rows = harvest_organization_agency_rows((_ledger(),))
    assert harvest_organization_agency_rows(rows) == rows


def test_duplicate_owner_fails_closed() -> None:
    with pytest.raises(OrganizationAnalysisError):
        harvest_organization_agency_rows((_ledger(), _ledger()))


def test_foreign_concept_owner_fails_closed() -> None:
    ledger = _ledger()
    concept = ledger.concepts[0]
    with pytest.raises(OrganizationAgencyError):
        OrganizationAgencyLedger(
            owner_id=OTHER,
            concepts=(
                OrganizationAgencyConcept(
                    organization_id=concept.organization_id,
                    owner_id=OWNER,
                    status=OrganizationStatus.RECOGNIZED,
                    first_tick=1,
                    last_tick=10,
                ),
            ),
        )


def test_counts_and_ticks_helpers() -> None:
    rows = harvest_organization_agency_rows((_ledger(),))
    counts = organization_agency_concept_counts(rows)
    assert counts[0][0] == "agent-1"
    assert counts[0][2] == 1
    assert organization_agency_decision_ticks(rows) == (6,)


def test_analysis_module_does_not_import_cognition() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.startswith("agents") for name in imported)


def test_completed_run_harvest_reads_agency_ledgers() -> None:
    from types import SimpleNamespace

    from experiments.organization_harvest import (
        build_completed_run_organization_harvest,
    )

    concept = concept_ledger()
    result = SimpleNamespace(
        organization_concept_ledgers=(concept,),
        organization_operation_ledgers=(),
        organization_agency_ledgers=(_ledger(),),
    )
    harvest = build_completed_run_organization_harvest(
        result,
        run_id="run-agency-harvest",
        input_revision="revision-1",
        generated_tick=10,
    )
    assert len(harvest.agency_rows) == 1
