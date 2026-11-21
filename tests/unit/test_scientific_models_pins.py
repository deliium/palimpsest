# mypy: ignore-errors

"""Current V4-30 pins with unchanged command, observer and migration surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from agents.cognition.scientific_models import ScientificModelLedger
from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from api.routes.scientific_models import SCIENTIFIC_MODELS_ROUTE_COUNT
from observer.contracts import OBSERVER_PROTOCOL_VERSION
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import ALEMBIC_HEAD_REVISION
from simulation.run_control import (
    FINALIZATION_COMMAND_ACCEPTED_VERSIONS,
    FINALIZATION_COMMAND_CODEC_VERSION,
)
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
from simulation.scientific_models_models import (
    SCIENTIFIC_MODELS_SNAPSHOT_SCHEMA,
)
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
)
from world._rules import COMMAND_RULE_MATRIX
from world.actions import AgentCommand
from world.events import EVENT_SCHEMA_REPLAY_V27, EVENT_SCHEMA_REPLAY_V28

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_current_catalog_has_six_predictive_suffix_families() -> None:
    assert METRIC_FAMILY_COUNT == 271
    values = tuple(item.value for item in MetricFamilyId)
    assert values[255] == "scientific_replication_social_interpretation"
    assert values[256:262] == (
        "scientific_model_structure",
        "scientific_model_predictions",
        "scientific_model_observed_outcomes",
        "scientific_model_calibration",
        "scientific_model_revisions",
        "scientific_model_comparison",
    )


def test_unchanged_surfaces_and_versions() -> None:
    assert len(COMMAND_RULE_MATRIX) == 45
    assert len(get_args(AgentCommand)) == 45
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert len(V4_CONTEXTS) == 17
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"
    assert EVENT_SCHEMA_REPLAY_V27 == 27
    assert EVENT_SCHEMA_REPLAY_V28 == 28
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert SCIENTIFIC_MODELS_ROUTE_COUNT == 8
    assert SCIENTIFIC_MODELS_SNAPSHOT_SCHEMA == "scientific-models-snapshot-v1"


def test_no_new_runner_schema_or_migration() -> None:
    assert "runner-config-v58" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []


def test_pending_default_and_predictive_version_are_independent() -> None:
    assert FINALIZATION_COMMAND_CODEC_VERSION == "finalization-command-v1"
    assert "finalization-command-v4" in FINALIZATION_COMMAND_ACCEPTED_VERSIONS


def test_predictive_ledger_has_no_truth_or_progress_fields() -> None:
    for field in ScientificModelLedger.__dataclass_fields__:
        assert "truth" not in field
        assert "score" not in field
        assert "progress" not in field
