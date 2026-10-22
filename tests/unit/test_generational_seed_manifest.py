"""Truthful seed lineage for generational runs."""

from __future__ import annotations

from dataclasses import replace

from simulation.generational_seeds import build_generational_seed_manifest
from simulation.models import RunId
from tests.unit.test_generational_population_runner import _v55_config


def test_same_complete_identity_produces_same_manifest() -> None:
    config = _v55_config()
    first = build_generational_seed_manifest(config, RunId("run-seed-1"))
    second = build_generational_seed_manifest(config, RunId("run-seed-1"))
    assert first == second
    assert first.manifest_hash == second.manifest_hash


def test_different_run_id_is_recorded_and_changes_hash() -> None:
    config = _v55_config()
    first = build_generational_seed_manifest(config, RunId("run-seed-1"))
    second = build_generational_seed_manifest(config, RunId("run-seed-2"))
    assert first.run_id != second.run_id
    assert first.manifest_hash != second.manifest_hash
    assert {channel.name for channel in first.channels} == {
        "world",
        "demography",
        "agent_initialization",
        "lifespan",
        "innovation",
        "environment",
        "llm",
    }


def test_demographic_reserved_draw_is_not_reported_as_zero() -> None:
    manifest = build_generational_seed_manifest(
        _v55_config(), RunId("run-seed-3")
    )
    by_name = {channel.name: channel for channel in manifest.channels}
    assert by_name["demography"].draw_usage == "reserved_ignored"
    assert by_name["innovation"].draw_usage == "deterministic_hash"
    assert by_name["environment"].draw_usage == "deterministic_hash"


def test_schedule_and_rules_identity_are_covered() -> None:
    config = _v55_config()
    manifest = build_generational_seed_manifest(config, RunId("run-seed-4"))
    assert manifest.physical_rules_fingerprint
    assert manifest.schedule_fingerprint
    changed = replace(
        config,
        seed=config.seed + 1,
    )
    other = build_generational_seed_manifest(changed, RunId("run-seed-4"))
    assert other.schedule_fingerprint == manifest.schedule_fingerprint
    assert other.manifest_hash != manifest.manifest_hash
