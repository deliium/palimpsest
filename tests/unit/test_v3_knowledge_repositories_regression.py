"""Knowledge-repositories regression pins: SEMANTIC 53, commands 34, metrics 65."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from experiments import OFF_GATE_MATRIX_EXPERIMENT_IDS, experiment_ao_knowledge_repositories
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.runner_models import RUNNER_SCHEMA_VERSION_V34
from world.actions import (
    AgentCommand,
    DepositRecord,
    EstablishRepository,
    IndexRepository,
    MaintainRepository,
    RetrieveRecord,
)

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def test_semantic_event_count_is_54() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 54
    assert "REPOSITORY_ESTABLISHED" in SEMANTIC_EVENT_TYPES
    assert "REPOSITORY_MEMBER_DEPOSITED" in SEMANTIC_EVENT_TYPES
    assert "REPOSITORY_MEMBER_RETRIEVED" in SEMANTIC_EVENT_TYPES
    assert "REPOSITORY_MAINTAINED" in SEMANTIC_EVENT_TYPES
    assert "REPOSITORY_INDEXED" in SEMANTIC_EVENT_TYPES
    assert "REPOSITORY_NEGLECTED" in SEMANTIC_EVENT_TYPES


def test_agent_command_count_is_34() -> None:
    commands = get_args(AgentCommand)
    assert len(commands) == 34
    assert EstablishRepository in commands
    assert DepositRecord in commands
    assert RetrieveRecord in commands
    assert MaintainRepository in commands
    assert IndexRepository in commands


def test_metric_family_count_is_62() -> None:
    assert METRIC_FAMILY_COUNT == 65
    assert MetricFamilyId.KNOWLEDGE_REPOSITORY_SURVIVAL.value == (
        "knowledge_repository_survival"
    )
    assert MetricFamilyId.KNOWLEDGE_REPOSITORY_ACCESS.value == (
        "knowledge_repository_access"
    )
    assert MetricFamilyId.KNOWLEDGE_REPOSITORY_ORGANIZATION.value == (
        "knowledge_repository_organization"
    )


def test_alembic_head_stays_0017() -> None:
    versions = _ROOT / "alembic" / "versions"
    assert (versions / "0017_memory_embedding_hnsw.py").is_file()
    assert not any(versions.glob("*0018*"))


def test_experiment_ao_off_gate_and_schema_pin() -> None:
    assert "experiment-ao-knowledge-repositories" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert RUNNER_SCHEMA_VERSION_V34 == "runner-config-v34"
    assert experiment_ao_knowledge_repositories is not None


def test_no_library_institution_module() -> None:
    world = _ROOT / "src" / "world"
    assert not (world / "library_institution.py").exists()
    assert not any(world.rglob("*LibraryInstitution*"))
