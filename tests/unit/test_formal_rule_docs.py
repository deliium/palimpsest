"""Documentation parity for the V4-06 formal-rules feature."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from simulation.v4_architecture import V4_CAPABILITY_FLAGS, V4_CONTEXTS

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "formal-rules.md"

FORMAL_RULE_ROUTES = (
    "/v1/simulations/{run_id}/formal-rules",
    "/v1/simulations/{run_id}/formal-rules/candidates",
    "/v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}",
    "/v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}/rules",
    "/v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}/versions",
    "/v1/simulations/{run_id}/formal-rules/lineage",
)


def test_formal_rules_doc_covers_every_required_section() -> None:
    text = DOC.read_text()
    for heading in (
        "## What a rule can and cannot do",
        "## Progression",
        "## Recorded dimensions",
        "## Responses and competing systems",
        "## Snapshot, publication, and routes",
        "## Metrics",
        "## Configuration",
        "## Limits and non-goals",
        "## Non-claims",
    ):
        assert heading in text


def test_formal_rules_doc_states_belief_physical_and_competing_semantics() -> None:
    text = DOC.read_text()
    assert "one owner's belief" in text
    assert "WorldEngine" in text and "never reads a formal-rule" in text
    assert "physically possible command is still admitted" in text
    assert "physically impossible command is still rejected" in text
    assert "Declared responses" in text or "declarations" in text
    assert "No precedence, majority, quorum, or consensus gate" in text
    assert "no court, police, government, jurisdiction, global registry" in text.lower()


def test_readme_and_context_artifacts_link_the_feature() -> None:
    assert "docs/formal-rules.md" in (ROOT / "README.md").read_text()
    description = (ROOT / ".ai-factory" / "DESCRIPTION.md").read_text()
    assert "V4-06" in description
    assert "metric families 198" in description

    architecture = (ROOT / ".ai-factory" / "ARCHITECTURE.md").read_text()
    assert "V4-06 formal rules seam" in architecture
    assert "V4-07 dispute resolution seam" in architecture
    assert "198 metric families" in architecture
    assert "Owned V4 flags" in architecture
    assert "`formal_rules`" in architecture

    docs_architecture = (ROOT / "docs" / "architecture.md").read_text()
    assert "## V4-06 formal social rules contract" in docs_architecture
    assert str(METRIC_FAMILY_COUNT) in docs_architecture
    assert "six GET-only" in docs_architecture


def test_configuration_documents_four_owned_and_eight_unowned_flags() -> None:
    text = (ROOT / "docs" / "configuration.md").read_text()
    assert "five owned V4 flags" in text
    assert "`organizations`" in text
    assert "`formal_rules`" in text
    assert "other seven V4 flags" in text
    assert "PALIMPSEST_FORMAL_RULE_ROOT" in text
    assert "PALIMPSEST_FORMAL_RULE_CURSOR_KEY" in text
    assert "--formal-rule-root" in text
    assert "every V4 flag is unowned" not in text
    assert "other eleven V4 flags" not in text


def test_current_v4_docs_state_the_four_owned_flags() -> None:
    research_api = (ROOT / "docs" / "research-api.md").read_text()
    assert "all V4 flags are unowned" not in research_api
    assert "other seven remain unowned" in research_api
    assert "`organizations`" in research_api
    assert "`formal_rules`" in research_api

    v4_doc = " ".join((ROOT / "docs" / "v4-architecture.md").read_text().split())
    assert "Every V4 capability flag is closed, unowned" not in v4_doc
    assert "the other seven remain unowned" in v4_doc
    assert "`organizations`" in v4_doc
    assert "`formal_rules`" in v4_doc


def test_architecture_v4_05_seam_keeps_its_own_metric_count() -> None:
    architecture = (ROOT / ".ai-factory" / "ARCHITECTURE.md").read_text()
    section = architecture.split("### V4-05 organization collective-agency seam", 1)[
        1
    ].split("\n### ", 1)[0]
    assert "metric families 148" in section
    assert "metric families 151" not in section


def test_v4_doc_keeps_fourteen_context_headings_and_owns_formal_rules() -> None:
    text = (ROOT / "docs" / "v4-architecture.md").read_text()
    assert text.count("\n### ") == len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    for context in V4_CONTEXTS:
        assert f"### {context.context_id.value}" in text

    formal_row = next(
        line for line in text.splitlines() if line.startswith("| `formal_rules` |")
    )
    assert "deferred" not in formal_row
    assert "V4-06 implementation" in formal_row
    section = text.split("### formal_rules", 1)[1].split("\n### ", 1)[0]
    assert "Owned by V4-06" in section


def test_research_api_lists_exactly_six_formal_rule_routes() -> None:
    text = (ROOT / "docs" / "research-api.md").read_text()
    for route in FORMAL_RULE_ROUTES:
        assert route in text
    assert "503 formal_rule_disabled" in text
    assert "formal_rule_cursor_invalid" in text


def test_organizations_doc_links_the_sibling_formal_rules_context() -> None:
    assert "formal-rules.md" in (ROOT / "docs" / "organizations.md").read_text()


def test_docs_do_not_claim_objective_law_or_enforcement() -> None:
    text = DOC.read_text().lower()
    assert "not objective law" in text or "never an objective law" in text
    assert "no court" in text
    assert "global registry" in text
