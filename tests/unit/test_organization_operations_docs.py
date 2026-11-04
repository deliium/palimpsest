"""Documentation parity for V4-04 organization operational state."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from simulation.v4_architecture import V4_CAPABILITY_FLAGS, V4_CONTEXTS

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "organizations.md"

DOMAINS = (
    "resource_control",
    "storage",
    "record_keeping",
    "membership_admission",
    "membership_departure",
    "role_assignment",
    "procedure_action",
    "internal_commitment",
)


def test_organizations_doc_covers_operational_state() -> None:
    text = DOC.read_text()
    assert "## Operational state" in text
    for domain in DOMAINS:
        assert domain in text, domain
    for heading in (
        "## Membership",
        "## Identity",
        "## Lineage",
        "## Configuration",
        "## Publication and inspection",
        "## Limits",
        "## Non-claims",
    ):
        assert heading in text
    assert "holder_id" in text
    assert "custodian_repository_id" in text
    assert "stored_quantity" in text
    assert "No teleport" in text
    assert "orgop-" in text


def test_counts_match_code() -> None:
    assert METRIC_FAMILY_COUNT == 164
    organizations = DOC.read_text()
    architecture = (ROOT / ".ai-factory" / "ARCHITECTURE.md").read_text()
    architecture_docs = (ROOT / "docs" / "architecture.md").read_text()
    description = (ROOT / ".ai-factory" / "DESCRIPTION.md").read_text()
    assert "160" in description
    assert "metric families 164" in description
    assert "160" in architecture
    assert "164 metric families" in architecture
    assert "160" in architecture_docs
    assert "164 metric families" in architecture_docs
    assert "organization-snapshot-v2" in organizations
    assert "organization-snapshot-v1" in organizations


def test_readme_and_context_artifacts_link_the_feature() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "docs/organizations.md" in readme
    assert "Operational state" in readme or "operational state" in readme
    description = (ROOT / ".ai-factory" / "DESCRIPTION.md").read_text()
    assert "V4-04" in description
    assert "organizations" in description
    architecture = (ROOT / ".ai-factory" / "ARCHITECTURE.md").read_text()
    assert "V4-04 organizations operations seam" in architecture
    architecture_docs = (ROOT / "docs" / "architecture.md").read_text()
    assert "Downstream V4 organization operations contract" in architecture_docs


def test_api_and_ui_docs_list_the_sixth_route() -> None:
    api = (ROOT / "docs" / "research-api.md").read_text()
    assert "/operations" in api
    assert "/collective-agency" in api
    assert "organization-snapshot-v3" in api
    ui = (ROOT / "docs" / "research-ui.md").read_text()
    assert "operations" in ui.lower()
    assert "contested" in ui.lower()


def test_v4_doc_keeps_fourteen_context_headings() -> None:
    text = (ROOT / "docs" / "v4-architecture.md").read_text()
    assert text.count("\n### ") == len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert "V4-03/V4-04 implementation" in text


def test_docs_do_not_claim_objective_or_composite_authority() -> None:
    text = DOC.read_text().lower()
    assert "not a global organization registry" in text
    assert "not a `worldengine` entity" in text
    assert "never changes them" in text
    assert "composite civilization score" in text
    assert "no consensus gate" in text
    for forbidden in (
        "organization-owned treasury",
        "organization resource pool",
        "objective ownership field is added",
    ):
        assert forbidden not in text


def test_metric_doc_names_both_families() -> None:
    metrics = (ROOT / "docs" / "analysis-metrics.md").read_text()
    assert "organization_operations@1" in metrics
    assert "organization_operation_authority@1" in metrics
    assert "operation_coverage_ratio" in metrics
    assert "authority_contest_count" in metrics


def test_development_doc_lists_operation_gates() -> None:
    development = (ROOT / "docs" / "development.md").read_text()
    assert "test_organization_operations_boundaries.py" in development
    assert "test_organization_operations_end_to_end.py" in development
    assert "test_organization_operations_api.py" in development
