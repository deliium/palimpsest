"""Durable-records regression pins: SEMANTIC 47; commands/metrics co-owned with v3-12."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from observer.version import SEMANTIC_EVENT_TYPES
from persistence.orm import AUTHORITATIVE_TABLES
from world.actions import (
    AgentCommand,
    AnnotateRecord,
    CopyRecord,
    DamageRecord,
)

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def test_semantic_event_count_is_47() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 53
    assert "ARTIFACT_COPIED" in SEMANTIC_EVENT_TYPES
    assert "ARTIFACT_ANNOTATED" in SEMANTIC_EVENT_TYPES
    assert "ARTIFACT_DAMAGED" in SEMANTIC_EVENT_TYPES
    assert "ARTIFACT_PARTIALLY_LOST" in SEMANTIC_EVENT_TYPES


def test_agent_command_count_includes_durable_commands() -> None:
    commands = get_args(AgentCommand)
    assert len(commands) == 34
    assert CopyRecord in commands
    assert AnnotateRecord in commands
    assert DamageRecord in commands


def test_metric_family_count_includes_durable_and_repository() -> None:
    assert METRIC_FAMILY_COUNT == 65
    assert MetricFamilyId.DURABLE_RECORD_LINEAGE.value == "durable_record_lineage"
    assert MetricFamilyId.DURABLE_RECORD_FIDELITY.value == "durable_record_fidelity"
    assert MetricFamilyId.DURABLE_RECORD_SURVIVAL.value == "durable_record_survival"
    assert (
        MetricFamilyId.KNOWLEDGE_REPOSITORY_SURVIVAL.value
        == "knowledge_repository_survival"
    )


def test_alembic_head_stays_0017() -> None:
    versions = _ROOT / "alembic" / "versions"
    assert (versions / "0017_memory_embedding_hnsw.py").is_file()
    assert not any(versions.glob("*0018*"))


def test_authoritative_tables_remain_append_only_surface() -> None:
    assert "world_events" in AUTHORITATIVE_TABLES
    assert "world_snapshots" in AUTHORITATIVE_TABLES
