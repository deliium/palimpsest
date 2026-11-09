"""V4-08 documentation parity."""

from __future__ import annotations

from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "evidence-testimony.md"

REQUIRED_HEADINGS = (
    "# Evidence and testimony",
    "## What evidence can and cannot do",
    "## Sources",
    "## Provenance",
    "## Chain of custody",
    "## Confidence",
    "## Agent interpretation",
    "## Contradictions",
    "## Witness testimony and independence",
    "## Evaluation under the owner's own trust models",
    "## Objective alignment (researcher only)",
    "## Snapshot, publication, and routes",
    "## Metrics",
    "## Configuration",
    "## Limits and non-goals",
    "## Non-claims",
    "## See also",
)

EVIDENCE_ROUTES = (
    "/v1/simulations/{run_id}/evidence",
    "/v1/simulations/{run_id}/evidence/candidates",
    "/v1/simulations/{run_id}/evidence/candidates/{candidate_id}",
    "/v1/simulations/{run_id}/evidence/candidates/{candidate_id}/sources",
    "/v1/simulations/{run_id}/evidence/candidates/{candidate_id}/contradictions",
    "/v1/simulations/{run_id}/evidence/lineage",
)


def test_canonical_document_has_the_exact_contract_sections() -> None:
    lines = DOC.read_text(encoding="utf-8").splitlines()
    headings = [line for line in lines if line.startswith("#")]
    assert headings == list(REQUIRED_HEADINGS)


def test_canonical_document_states_the_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    for token in (
        "evidence-testimony-snapshot-v1",
        "evidence-testimony-store-v1",
        "runner-config-v56",
        "legal_disputes",
        "Witnesses may misremember",
        "records may be wrong",
        "artifacts may be misinterpreted",
        "direct_observation",
        "complete_belief",
        "incomplete_belief",
        "conflicting_belief",
        "not_applicable",
        "evidence_trust_basis_missing",
        "researcher-only",
        "never a verdict",
        "evidence_source_structure@1",
        "evidence_provenance_continuity@1",
        "evidence_objective_alignment@1",
        "evidence_testimony_disabled",
        "PALIMPSEST_EVIDENCE_ROOT",
        "PALIMPSEST_EVIDENCE_CURSOR_KEY",
    ):
        assert token in text, token
    assert f"{METRIC_FAMILY_COUNT}" in text
    assert "runner-config-v57" in text and "does not exist" in text
    for kind in (
        "witness testimony",
        "written record",
        "artifact",
        "physical state",
        "prior agreement",
        "reputation",
        "remembered event",
        "unknown",
    ):
        assert kind in text.lower(), kind
    for route in EVIDENCE_ROUTES:
        assert route in text, route
    for value in ("consistent", "unresolved", "inconsistent", "not_applicable"):
        assert value in text
    for basis in (
        "direct experience",
        "relationship",
        "reputation",
        "role authority",
        "rule authority",
        "institution",
    ):
        assert basis in text.lower()


def test_links_and_metric_documentation() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/evidence-testimony.md" in readme
    disputes = (ROOT / "docs" / "disputes.md").read_text(encoding="utf-8")
    assert "[Evidence and testimony](evidence-testimony.md)" in disputes
    metrics = (ROOT / "docs" / "analysis-metrics.md").read_text(encoding="utf-8")
    assert "160" in metrics
    assert "evidence_source_structure@1" in metrics


def test_research_api_documents_the_six_routes_and_cursor_contract() -> None:
    text = (ROOT / "docs" / "research-api.md").read_text(encoding="utf-8")
    for route in EVIDENCE_ROUTES:
        assert route in text, route
    for token in (
        "SUBJECTIVE_DEBUG",
        "evidence_testimony_disabled",
        "evidence_testimony_cursor_invalid",
        "evidence_testimony_cursor_expired",
        "900 seconds",
        "2 MiB",
        "PALIMPSEST_EVIDENCE_CURSOR_KEY",
    ):
        assert token in text, token


def test_configuration_documents_the_evidence_settings() -> None:
    text = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    for token in (
        "PALIMPSEST_EVIDENCE_ROOT",
        "PALIMPSEST_EVIDENCE_CURSOR_KEY",
        "--evidence-root",
        "--evidence-max-publications",
        "--evidence-max-bytes",
        "evidence_testimony_disabled",
    ):
        assert token in text, token


def test_context_artifacts_document_the_v4_08_seam() -> None:
    description = (ROOT / ".ai-factory" / "DESCRIPTION.md").read_text(encoding="utf-8")
    assert "V4-08 (evidence and testimony" in description
    assert "evidence-testimony-snapshot-v1" in description
    architecture = (ROOT / ".ai-factory" / "ARCHITECTURE.md").read_text(
        encoding="utf-8"
    )
    assert "### V4-08 evidence and testimony seam" in architecture
    docs_architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "## V4-08 evidence and testimony contract" in docs_architecture
    assert "evidence-testimony.md" in docs_architecture


def test_research_ui_documents_the_panel() -> None:
    text = (ROOT / "docs" / "research-ui.md").read_text(encoding="utf-8")
    assert "Evidence panel" in text
    assert "researcher-only" in text
    assert "/v1/simulations/{run_id}/evidence" in text


def test_counts_match_the_code() -> None:
    from simulation.evidence_testimony_models import (
        EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA,
    )

    text = DOC.read_text(encoding="utf-8")
    assert EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA in text
    assert METRIC_FAMILY_COUNT == 192
