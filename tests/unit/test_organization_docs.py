"""Documentation parity for the V4-03 organization feature."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from simulation.v4_architecture import V4_CAPABILITY_FLAGS, V4_CONTEXTS

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "organizations.md"


def test_organizations_doc_covers_every_required_section() -> None:
    text = DOC.read_text()
    for heading in (
        "## What an organization is",
        "## What it is not",
        "## The nine aspects",
        "## Membership",
        "## Identity",
        "## Lineage",
        "## Configuration",
        "## Publication and inspection",
        "## Limits",
        "## Non-claims",
    ):
        assert heading in text


def test_readme_and_context_artifacts_link_the_feature() -> None:
    assert "docs/organizations.md" in (ROOT / "README.md").read_text()
    description = (ROOT / ".ai-factory" / "DESCRIPTION.md").read_text()
    assert "V4-03" in description
    assert "metric families 180" in description
    architecture = (ROOT / ".ai-factory" / "ARCHITECTURE.md").read_text()
    assert "V4-03 organizations seam" in architecture
    assert "180 metric families" in architecture

    docs_architecture = (ROOT / "docs" / "architecture.md").read_text()
    assert "Downstream V4 organization contract" in docs_architecture
    assert str(METRIC_FAMILY_COUNT) in docs_architecture
    assert "Organizations" in (ROOT / "docs" / "research-ui.md").read_text()
    assert "organizations" in (ROOT / "docs" / "configuration.md").read_text()


def test_v4_doc_keeps_fourteen_context_headings() -> None:
    text = (ROOT / "docs" / "v4-architecture.md").read_text()
    assert text.count("\n### ") == len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    for context in V4_CONTEXTS:
        assert f"### {context.context_id.value}" in text


def test_docs_do_not_claim_objective_organization_authority() -> None:
    for path in (DOC, ROOT / "docs" / "micro.md"):
        if not path.exists():
            continue
        text = path.read_text().lower()
        assert "global organization registry" not in text or "not a" in text
        assert "organization owned treasury" not in text
    text = DOC.read_text().lower()
    assert "not a global organization registry" in text
    assert "not a `worldengine` entity" in text


def test_documented_counts_match_code() -> None:
    text = DOC.read_text()
    assert "2048" in text
    assert "512" in text
    assert "16384" in text
    assert "4 MiB" in text
