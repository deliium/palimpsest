"""Documentation parity for the V4-07 dispute-resolution feature.

Task 23 creates ``docs/disputes.md`` and updates the documentation index. The
former ``docs/dispute-resolution.md`` path remains a compatibility landing page
that points at the canonical contract. Until the canonical page exists this test
fails clearly instead of silently skipping the required artifact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from api.routes.dispute import router as dispute_router
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.dispute_models import DISPUTE_SNAPSHOT_SCHEMA
from simulation.v4_architecture import V4_CAPABILITY_FLAGS, V4_CONTEXTS
from world._rules import COMMAND_RULE_MATRIX

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "disputes.md"

DISPUTE_ROUTES = (
    "/v1/simulations/{run_id}/disputes",
    "/v1/simulations/{run_id}/disputes/candidates",
    "/v1/simulations/{run_id}/disputes/candidates/{candidate_id}",
    "/v1/simulations/{run_id}/disputes/candidates/{candidate_id}/claims",
    "/v1/simulations/{run_id}/disputes/candidates/{candidate_id}/resolutions",
    "/v1/simulations/{run_id}/disputes/lineage",
)

REQUIRED_HEADINGS = (
    "## What a dispute can and cannot do",
    "## Claims and counterclaims",
    "## Testimony and evidence",
    "## Rule references",
    "## Mediation and institutional roles",
    "## Proposed resolutions and declarations",
    "## Objective alignment (researcher only)",
    "## Snapshot, publication, and routes",
    "## Metrics",
    "## Configuration",
    "## Limits and non-goals",
    "## Non-claims",
)


def _doc_text() -> str:
    assert DOC.is_file(), (
        "Task 23 must create docs/disputes.md; V4-07 documentation parity "
        "cannot pass without the mandatory artifact"
    )
    return DOC.read_text(encoding="utf-8")


def test_dispute_doc_covers_every_required_section() -> None:
    text = _doc_text()
    for heading in REQUIRED_HEADINGS:
        assert heading in text, heading


def test_dispute_doc_states_belief_and_physical_semantics() -> None:
    text = _doc_text()
    assert "one owner's belief" in text
    assert "never reads a dispute" in text
    assert "physically possible command is still admitted" in text
    assert "physically impossible command is still rejected" in text
    assert "no objective justice oracle" in text.lower()
    assert "no court" in text.lower()
    assert "global" in text.lower() and "registry" in text.lower()


def test_dispute_doc_covers_claims_testimony_rules_and_mediation() -> None:
    text = _doc_text()
    for phrase in (
        "contested debt",
        "ownership claim",
        "contract interpretation",
        "injury",
        "broken promise",
        "resource appropriation",
        "claimant",
        "counterclaim",
        "shared root",
        "independently_evidenced",
        "orphaned",
        "version_mismatch",
        "conflict_mediation",
        "not binding",
    ):
        assert phrase in text.lower(), phrase


def test_dispute_doc_covers_resolution_and_alignment_semantics() -> None:
    text = _doc_text()
    for status in (
        "proposed",
        "partially_accepted",
        "apparently_accepted",
        "contested",
        "withdrawn",
        "expired",
        "superseded",
    ):
        assert status in text
    for alignment in ("supported", "unresolved", "inconsistent", "not_applicable"):
        assert alignment in text
    assert "researcher" in text.lower()
    assert "prior committed tick" in text.lower()


def test_dispute_doc_metric_and_wire_counts_match_the_code() -> None:
    text = _doc_text()
    assert str(METRIC_FAMILY_COUNT) == "164"
    assert "164" in text
    assert "43 commands" in text or str(len(COMMAND_RULE_MATRIX)) in text
    assert "73" in text or str(len(SEMANTIC_EVENT_TYPES)) in text
    assert "0017" in text
    assert "no `0018`" in text or "no 0018" in text
    assert str(len(V4_CONTEXTS)) in text
    assert str(len(V4_CAPABILITY_FLAGS)) in text
    assert DISPUTE_SNAPSHOT_SCHEMA in text
    assert "dispute-resolution-store-v1" in text
    assert "runner-config-v57" in text or "v57" in text
    assert "observer-protocol-v1" in text


def test_readme_and_research_api_link_the_feature() -> None:
    assert "docs/disputes.md" in (ROOT / "README.md").read_text(encoding="utf-8")
    compatibility = (ROOT / "docs" / "dispute-resolution.md").read_text(
        encoding="utf-8"
    )
    assert "disputes.md" in compatibility
    research_api = (ROOT / "docs" / "research-api.md").read_text(encoding="utf-8")
    for route in DISPUTE_ROUTES:
        assert route in research_api, route
    assert "SUBJECTIVE_DEBUG" in research_api
    assert "503 dispute_disabled" in research_api
    assert "dispute_cursor_invalid" in research_api


def test_configuration_documents_three_owned_flags() -> None:
    text = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    assert "`organizations`" in text
    assert "`formal_rules`" in text
    assert "`legal_disputes`" in text
    assert "PALIMPSEST_DISPUTE_ROOT" in text
    assert "dispute_cursor_key" in text


def test_docs_do_not_claim_objective_justice_or_binding_settlement() -> None:
    text = _doc_text().lower()
    for forbidden in (
        "verdict",
        "guilty",
        "liable",
        "true owner",
        "binding settlement",
    ):
        assert forbidden in text, forbidden
    assert "does not" in text or "never" in text
    assert "not a court" in text or "no court" in text


def test_dispute_route_contract_matches_the_documented_six() -> None:
    paths = {
        getattr(route, "path", "")
        for route in dispute_router.routes
        if getattr(route, "methods", None) is not None
    }
    assert paths == set(DISPUTE_ROUTES)
