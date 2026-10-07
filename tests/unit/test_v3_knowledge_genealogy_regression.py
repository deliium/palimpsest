"""Knowledge-genealogy regression pins: SEMANTIC 53, commands 34, metrics 65."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_ap_knowledge_genealogy,
)
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.persistence import checkpoint_schema_for_production
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V34,
    RUNNER_SCHEMA_VERSION_V35,
)
from world.actions import AgentCommand
from world.events import EVENT_SCHEMA_REPLAY_V5, EVENT_SCHEMA_REPLAY_V14

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def test_semantic_event_count_is_53() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 53


def test_agent_command_count_is_34() -> None:
    assert len(get_args(AgentCommand)) == 34


def test_metric_family_count_is_65() -> None:
    assert METRIC_FAMILY_COUNT == 65
    assert MetricFamilyId.KNOWLEDGE_GENEALOGY_HOLDERS.value == (
        "knowledge_genealogy_holders"
    )
    assert MetricFamilyId.KNOWLEDGE_GENEALOGY_LINEAGE.value == (
        "knowledge_genealogy_lineage"
    )
    assert MetricFamilyId.KNOWLEDGE_GENEALOGY_MUTATION.value == (
        "knowledge_genealogy_mutation"
    )


def test_alembic_head_stays_0017() -> None:
    versions = _ROOT / "alembic" / "versions"
    assert (versions / "0017_memory_embedding_hnsw.py").is_file()
    assert not any(versions.glob("*0018*"))


def test_experiment_ap_off_gate_and_schema_pin() -> None:
    assert "experiment-ap-knowledge-genealogy" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert RUNNER_SCHEMA_VERSION_V35 == "runner-config-v35"
    assert RUNNER_SCHEMA_VERSION_V34 == "runner-config-v34"
    assert experiment_ap_knowledge_genealogy is not None


def test_genealogy_only_does_not_bump_write_pair() -> None:
    # Genealogy is subjective + analysis harvest only; the write-pair helper
    # has no genealogy knob, so channel-off baseline stays replay-v5 / v2.
    schema, codec = checkpoint_schema_for_production(production_active=False)
    assert schema == EVENT_SCHEMA_REPLAY_V5
    assert codec == "v2"
    repos_schema, repos_codec = checkpoint_schema_for_production(
        production_active=False,
        knowledge_repositories_active=True,
        durable_records_active=True,
    )
    assert repos_schema == EVENT_SCHEMA_REPLAY_V14
    assert repos_codec == "v11"


def test_no_global_technique_registry_under_world() -> None:
    world = _ROOT / "src" / "world"
    assert not any(world.rglob("*GlobalTechniqueRegistry*"))
    assert not any(world.rglob("*SocietyEncyclopedia*"))
    forbidden = (
        "class GlobalTechniqueRegistry",
        "class GlobalKnowledge",
        "class TechniqueRegistry",
        "class SocietyEncyclopedia",
    )
    hits: list[str] = []
    for path in world.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                hits.append(f"{path.relative_to(_ROOT)}:{token}")
    assert hits == []
