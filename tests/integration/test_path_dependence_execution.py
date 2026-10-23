"""Opt-in PostgreSQL durability for historical-contingency ensembles."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from experiments.path_dependence_scenario import historical_contingency_scenario
from experiments.path_dependence_serialization import encode_path_dependence_spec
from infrastructure.settings import Settings
from research_runner.path_dependence_cli import _execute
from research_runner.path_dependence_composition import (
    build_path_dependence_postgres_composition,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_path_dependence_database_durability(
    migrated_test_database: Settings, tmp_path: Path
) -> None:
    composition = build_path_dependence_postgres_composition(migrated_test_database)
    try:
        spec = replace(
            historical_contingency_scenario(seed=901, profile="smoke"),
            seeds=(901,),
            replicates_per_seed=1,
        )
        spec_path = tmp_path / "spec.json"
        spec_path.write_bytes(encode_path_dependence_spec(spec))
        ensemble, summary = await _execute(
            spec_path=spec_path,
            root=tmp_path / "artifacts",
            code_revision="integration-revision",
            source_artifact_digest="a" * 64,
            factories=composition.factories,
        )
        assert summary.completed_count == 2
        for prefix in summary.prefixes:
            assert await composition.presence.exists(prefix.parent_run_id)
            for child in prefix.child_results:
                assert await composition.presence.exists(child.child_run_id)
                terminal = await composition.presence.terminal(child.child_run_id)
                assert terminal is not None
                assert terminal["terminal_tick"] == child.ticks_committed
        assert ensemble["schema_version"] == "path-dependence-ensemble-v1"
        assert list((tmp_path / "artifacts").rglob("completion.json"))
    finally:
        await composition.close()


@pytest.mark.scale
@pytest.mark.asyncio
async def test_tick_100_multigeneration_ensemble(
    migrated_test_database: Settings, tmp_path: Path
) -> None:
    composition = build_path_dependence_postgres_composition(migrated_test_database)
    try:
        spec = replace(
            historical_contingency_scenario(seed=902, profile="long"),
            seeds=(902,),
            replicates_per_seed=1,
        )
        spec_path = tmp_path / "spec.json"
        spec_path.write_bytes(encode_path_dependence_spec(spec))
        _ensemble, summary = await _execute(
            spec_path=spec_path,
            root=tmp_path / "artifacts",
            code_revision="integration-scale-revision",
            source_artifact_digest="b" * 64,
            factories=composition.factories,
        )
        assert summary.prefixes
        assert summary.prefixes[0].fork_tick == 100
        assert summary.completed_count == 2
        assert (
            max(child.ticks_committed for child in summary.prefixes[0].child_results)
            >= 1100
        )
    finally:
        await composition.close()
