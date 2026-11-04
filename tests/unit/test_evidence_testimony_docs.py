"""V4-08 documentation parity."""

from __future__ import annotations

from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "evidence-testimony.md"


def test_canonical_document_exists_and_states_the_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    for token in (
        "evidence-testimony-snapshot-v1",
        "runner-config-v56",
        "legal_disputes",
        "Witnesses may misremember",
        "records may be wrong",
        "artifacts may be misinterpreted",
        "chain of custody",
        "Confidence",
        "Contradictions",
        "researcher-only",
        "never a verdict",
        "evidence_source_structure@1",
        "evidence_provenance_continuity@1",
        "evidence_objective_alignment@1",
        "evidence_testimony_disabled",
    ):
        assert token in text, token
    assert f"{METRIC_FAMILY_COUNT}" in text
    assert "runner-config-v57" not in text or "does not exist" in text


def test_links_and_metric_documentation() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/evidence-testimony.md" in readme
    disputes = (ROOT / "docs" / "disputes.md").read_text(encoding="utf-8")
    assert "evidence-testimony.md" in disputes
    metrics = (ROOT / "docs" / "analysis-metrics.md").read_text(encoding="utf-8")
    assert "157" in metrics
    assert "evidence_source_structure@1" in metrics


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
    assert METRIC_FAMILY_COUNT == 157
