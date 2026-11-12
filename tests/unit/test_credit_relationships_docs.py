"""Documentation parity and negative claims for V4-22."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


REQUIRED_HEADINGS = (
    "# Credit relationships",
    "## Overview",
    "## Non-goals",
    "## Activation",
    "## Owner ledger",
    "## crd_v1 frames",
    "## Acts",
    "## Analysis",
    "## Metrics",
    "## Snapshot, store, and routes",
    "## Experiment",
    "## What this feature does not do",
    "## See also",
)

TOKENS = (
    "credit-relationships.v1",
    "crd_v1",
    "credit-relationships-snapshot-v1",
    "credit-relationships-store-v1",
    "credit_relationships@1",
)


def test_page_exists_with_every_required_heading() -> None:
    page = _read("docs/credit-relationships.md")
    for heading in REQUIRED_HEADINGS:
        assert heading in page


def test_every_document_mentions_the_seam() -> None:
    for path in (
        "README.md",
        ".ai-factory/ARCHITECTURE.md",
        ".ai-factory/DESCRIPTION.md",
        "docs/architecture.md",
        "docs/configuration.md",
        "docs/analysis-metrics.md",
        "docs/research-api.md",
        "docs/emergent-prices.md",
        "docs/market-like-institutions.md",
    ):
        text = _read(path)
        assert (
            "credit_relationships" in text
            or "credit-relationships" in text
            or "Credit relationships" in text
        ), path


def test_tokens_match_code_and_docs() -> None:
    page = _read("docs/credit-relationships.md")
    from agents.cognition.credit_relationships import (
        CREDIT_RELATIONSHIPS_POLICY_VERSION,
    )
    from experiments.credit_relationship_scenario import (
        CREDIT_RELATIONSHIPS_EXPERIMENT_ID,
    )
    from persistence.credit_relationships_filesystem import (
        CREDIT_RELATIONSHIPS_STORE_VERSION,
    )
    from simulation.credit_relationships_models import (
        CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
    )
    from world.credit_relationships import CREDIT_FRAME_SUBJECT

    for token in (
        CREDIT_RELATIONSHIPS_POLICY_VERSION,
        CREDIT_FRAME_SUBJECT,
        CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
        CREDIT_RELATIONSHIPS_STORE_VERSION,
        CREDIT_RELATIONSHIPS_EXPERIMENT_ID,
    ):
        assert token in page, token
        assert token in TOKENS


def test_active_catalog_is_216() -> None:
    from analysis.specifications import METRIC_FAMILY_COUNT

    assert METRIC_FAMILY_COUNT == 216
    for path in (
        "docs/credit-relationships.md",
        "docs/analysis-metrics.md",
        "docs/architecture.md",
        ".ai-factory/ARCHITECTURE.md",
        ".ai-factory/DESCRIPTION.md",
    ):
        text = _read(path)
        assert "216" in text, path
        assert "Current catalog: 212" not in text, path


def test_seven_route_suffixes_are_documented() -> None:
    api = _read("docs/research-api.md")
    for suffix in (
        "/credit-relationships",
        "/credit-relationships/relationships",
        "/credit-relationships/claims",
        "/credit-relationships/performances",
        "/credit-relationships/distributions",
        "/credit-relationships/counterparties",
        "/credit-relationships/alignment",
    ):
        assert suffix in api, suffix


def test_both_settings_are_documented() -> None:
    configuration = _read("docs/configuration.md")
    assert "PALIMPSEST_CREDIT_RELATIONSHIPS_ROOT" in configuration
    assert "PALIMPSEST_CREDIT_RELATIONSHIPS_CURSOR_KEY" in configuration


def test_no_affirmative_forbidden_feature_claim() -> None:
    for path in (
        "docs/credit-relationships.md",
        "README.md",
        "docs/analysis-metrics.md",
        "docs/research-api.md",
    ):
        text = _read(path).lower()
        for claim in (
            "is a credit score",
            "credit score is",
            "money is created",
            "enforceable debt exists",
            "canonical credit is",
            "acts as a bank",
        ):
            start = 0
            while True:
                index = text.find(claim, start)
                if index < 0:
                    break
                window = text[max(0, index - 12) : index]
                assert "no " in window or "not " in window, (path, claim)
                start = index + len(claim)


def test_no_schema_protocol_or_migration_bump() -> None:
    text = _read("docs/credit-relationships.md")
    assert "runner-config-v57" not in text
    assert "observer-protocol-v2" not in text
    assert "alembic/versions/0018" not in text
    assert "/v2/simulations" not in text


def test_experiment_is_off_gate() -> None:
    from experiments.catalog import (
        EXPERIMENT_A_V1_CONDITION_IDS,
        OFF_GATE_MATRIX_EXPERIMENT_IDS,
    )

    assert "credit_relationships@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "credit_relationships@1" not in EXPERIMENT_A_V1_CONDITION_IDS
    page = _read("docs/credit-relationships.md")
    assert "credit_relationships@1" in page
    assert "off" in page.lower() and "gate" in page.lower()


def test_historical_counts_are_not_active_pins() -> None:
    metrics = _read("docs/analysis-metrics.md")
    assert "208 -> 212" in metrics or "208 -> **212**" in metrics
    assert "Closed catalog cardinality: **216**" in metrics
