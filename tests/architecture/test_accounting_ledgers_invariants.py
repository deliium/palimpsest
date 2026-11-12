"""V4-23 accounting structural, authority, and append-only invariants."""

# mypy: ignore-errors

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import get_args

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import (
    ALEMBIC_HEAD_REVISION,
    V4_OWNED_CAPABILITY_FLAGS,
)
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
)
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
)
from world._rules import COMMAND_RULE_MATRIX
from world.actions import AgentCommand

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
BASELINE_216 = "d8c72a06645fc05f1e9ec7ea5714f0032c2d4c3dea36c8a0bdac2397fdc04cc2"
ACCOUNTING_FAMILIES = (
    "accounting_record_coverage",
    "accounting_entry_alignment",
    "accounting_record_condition",
    "accounting_flow_structure",
)


def test_catalog_appends_four_accounting_families_after_220() -> None:
    assert METRIC_FAMILY_COUNT == 220
    specs = all_metric_specifications()
    assert len(specs) == 220
    assert tuple(spec.family_id.value for spec in specs[216:220]) == ACCOUNTING_FAMILIES
    assert all(spec.algorithm_version == "1" for spec in specs[216:220])


def test_first_216_catalog_entries_are_byte_identical() -> None:
    specs = all_metric_specifications()[:216]
    material = "\x1e".join(
        "\x1f".join(
            (spec.family_id.value, spec.algorithm_version, ",".join(spec.value_keys))
        )
        for spec in specs
    )
    assert hashlib.sha256(material.encode()).hexdigest() == BASELINE_216


def test_no_accounting_context_flag_or_schema_bump() -> None:
    assert "accounting_ledgers" not in {
        context.context_id.value for context in V4_CONTEXTS
    }
    assert "accounting_ledgers" not in V4_CAPABILITY_FLAGS
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 8
    unowned = set(V4_CAPABILITY_FLAGS) - set(V4_OWNED_CAPABILITY_FLAGS)
    assert unowned == {
        "science",
        "epidemics",
        "ecological_feedback",
        "disasters",
    }
    assert V4_OWNED_CAPABILITY_FLAGS == frozenset(
        {
            "organizations",
            "formal_rules",
            "legal_disputes",
            "diplomacy",
            "organized_conflict",
            "infrastructure_networks",
            "supply_chains",
            "markets_credit",
        }
    )
    token = "runner-config-" + "v57"
    assert token not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    for path in SRC.rglob("*accounting_ledgers*.py"):
        assert token not in path.read_text(encoding="utf-8", errors="ignore")


def test_organizations_context_is_unchanged() -> None:
    from simulation.v4_architecture import V4_CONTEXT_BY_ID

    spec = V4_CONTEXT_BY_ID[V4ContextId.ORGANIZATIONS]
    assert spec.authority is V4Authority.OWNER_SCOPED
    assert spec.owner_packages == ("agents.cognition", "social", "simulation")
    assert spec.uses_existing_events is True
    assert spec.prerequisite_contexts == ()


def test_version_pins_are_unchanged() -> None:
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert not list((ROOT / "alembic" / "versions").glob("0018*"))
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(get_args(AgentCommand)) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27
    assert "v25" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS


def test_accounting_is_absent_from_observer_and_api_observer() -> None:
    for path in (SRC / "observer").rglob("*.py"):
        assert "accounting_ledgers" not in path.read_text(
            encoding="utf-8", errors="ignore"
        )
    for path in (SRC / "api").glob("observer*.py"):
        assert "accounting_ledgers" not in path.read_text(
            encoding="utf-8", errors="ignore"
        )


def test_no_accounting_field_implies_truth_or_objective_value() -> None:
    from agents.cognition.accounting_ledgers import (
        ACCOUNTING_FORBIDDEN_FIELD_NAMES,
    )

    forbidden = {
        "truth",
        "verified",
        "canonical_ledger",
        "audited",
        "objective_" + "bal" + "ance",
        "book_" + "value",
        "sol" + "vent",
        "credit_score",
        "money",
        "currency",
        "price",
        "interest",
        "reconciled",
        "fraud",
    }
    assert forbidden <= ACCOUNTING_FORBIDDEN_FIELD_NAMES


def test_alignment_is_not_imported_by_cognition_or_world() -> None:
    for root in (SRC / "agents", SRC / "world", SRC / "simulation"):
        for path in root.rglob("*.py"):
            assert "accounting_ledgers_expectations" not in path.read_text(
                encoding="utf-8", errors="ignore"
            )
