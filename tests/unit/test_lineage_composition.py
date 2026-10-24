"""CLI options and trusted lineage composition wiring."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.generational_comparison_scenario import (
    generational_comparison_scenario,
)
from experiments.generational_runner_scenario import generational_runner_scenario
from research_runner.cli import _lineage_installer, build_parser
from research_runner.lineage_composition import (
    LineageProducerOptions,
    create_lineage_capture,
    finalize_lineage_capture,
    install_lineage_capture,
)
from simulation.lineage_capture import LineageCaptureOptions
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageNode,
    LineageNodeState,
    LineageScope,
)
from simulation.lineage_ports import LineageBoundaryFrame
from simulation.models import RunId
from simulation.runner_serialization import encode_runner_config

_RUN = RunId("run-cli-lineage")


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    definition = generational_runner_scenario(seed=23, max_ticks=4)
    config = next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == "bl-generational-unassisted"
    )
    config_path = tmp_path / "config.json"
    config_path.write_bytes(encode_runner_config(config))
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(
        json.dumps(
            {
                "recipe_id": "plain-generational",
                "version": "1",
                "params": {},
                "intervention_id": None,
                "intervention_version": None,
                "intervention_params": {},
            }
        ),
        encoding="utf-8",
    )
    return config_path, recipe_path


def _audit(owner: str, entry_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=owner,
        entry_id=entry_id,
        kind="foraging_method",
        content_key="tech:forage",
        origin="independent_discovery",
        parent_entry_ids=(),
        lineage_root_id=f"root:{owner}",
        hop_index=0,
        mutated=False,
        acquired_tick=1,
        tick=1,
        active=True,
        source_agent_id=None,
        teacher_agent_id=None,
        capability_anchor="foraging",
    )


def test_generational_parser_exposes_lineage_options(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "generational",
            "--config",
            "config.json",
            "--execution-recipe",
            "recipe.json",
            "--artifact-root",
            str(tmp_path),
            "--run-id",
            "run-1",
            "--code-revision",
            "abc123",
            "--source-clean",
            "--lineage-root",
            str(tmp_path / "lineage"),
            "--lineage-cadence",
            "2",
            "--lineage-max-publications",
            "10",
            "--lineage-max-bytes",
            "1024",
        ]
    )
    assert args.lineage_root == str(tmp_path / "lineage")
    assert args.lineage_cadence == 2
    assert args.lineage_max_publications == 10
    assert args.lineage_max_bytes == 1024


def test_installer_creates_session_then_binds_sink_last(tmp_path: Path) -> None:
    calls: list[object] = []

    class _Runner:
        def set_lineage_boundary_sink(self, sink: object) -> None:
            calls.append(sink)

    options = LineageProducerOptions(
        root=tmp_path,
        capture=LineageCaptureOptions(cadence=1),
    )
    session = install_lineage_capture(_Runner(), options)
    assert calls == [session]
    assert session.status.active is True


def test_create_capture_uses_separate_root(tmp_path: Path) -> None:
    session = create_lineage_capture(
        LineageProducerOptions(
            root=tmp_path / "lineage",
            capture=LineageCaptureOptions(),
        )
    )
    assert session.status.active is True
    assert (tmp_path / "lineage").is_dir()


def test_cli_installer_builder_returns_callable(tmp_path: Path) -> None:
    installer = _lineage_installer(tmp_path, 1)
    assert callable(installer)
    with pytest.raises(AttributeError):
        installer(object())


def test_cli_generational_installs_capture_and_writes_status(
    tmp_path: Path,
) -> None:
    definition = generational_comparison_scenario(seed=23, max_ticks=12)
    config = next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == "bm-oral-vs-records-treatment"
    )
    config_path = tmp_path / "config.json"
    config_path.write_bytes(encode_runner_config(config))
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(
        json.dumps(
            {
                "recipe_id": "plain-generational",
                "version": "1",
                "params": {},
                "intervention_id": None,
                "intervention_version": None,
                "intervention_params": {},
            }
        ),
        encoding="utf-8",
    )
    args = build_parser().parse_args(
        [
            "generational",
            "--config",
            str(config_path),
            "--execution-recipe",
            str(recipe_path),
            "--artifact-root",
            str(tmp_path / "archive"),
            "--run-id",
            _RUN.value,
            "--code-revision",
            "abc123",
            "--source-clean",
            "--lineage-root",
            str(tmp_path / "lineage"),
        ]
    )
    assert args.func(args) == 0
    status_files = sorted(
        (tmp_path / "archive").glob("lineage-capture-status-*.json")
    )
    assert len(status_files) == 1
    payload = json.loads(status_files[0].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "lineage-capture-status-v1"
    assert payload["run_id"] == _RUN.value
    assert payload["receipt_count"] >= 0
    assert {item["family"] for item in payload["unavailable"]} >= {
        "mentorship",
        "narrative",
        "institution",
    }
    assert (tmp_path / "lineage").is_dir()


@pytest.mark.asyncio
async def test_finalize_publishes_detached_knowledge_and_status(
    tmp_path: Path,
) -> None:
    options = LineageProducerOptions(
        root=tmp_path / "lineage",
        capture=LineageCaptureOptions(),
        artifact_root=tmp_path,
    )
    session = create_lineage_capture(options)
    scope = LineageScope(
        run_id=_RUN,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
    )
    agent = LineageNode(
        ref=LineageNodeRef(
            run_id=_RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id="alice",
        ),
        state=LineageNodeState.OBSERVED,
        living=True,
        observed_tick=1,
    )
    await session.capture(
        LineageBoundaryFrame(
            run_id=_RUN,
            scope=scope,
            boundary_tick=1,
            observed_boundary=1,
            nodes=(agent,),
            edges=(),
            coverage=LineageCoverage(
                state=LineageCoverageState.COMPLETE,
                capture_start_tick=0,
                capture_end_tick=1,
            ),
            source_revision="objective-v1",
        )
    )
    variant = SimpleNamespace(
        variant_id="a" * 64,
        origin=SimpleNamespace(value="observed_event"),
        status=SimpleNamespace(value="active"),
        strength=0.5,
        first_tick=0,
        last_tick=1,
        repetition_count=1,
        mutation_generation=0,
        parent_variant_ids=(),
        merged_into_id=None,
        competing_variant_ids=(),
        source_event_id="event-1",
        source_memory_id=None,
        reconstruction_id=None,
        transmission_root_id=None,
        source_loss=None,
    )
    arm = SimpleNamespace(
        runner_result=SimpleNamespace(
            run_id=_RUN,
            ticks_committed=1,
            practical_knowledge_audits=(_audit("alice", "e-alice"),),
            cultural_narrative_ledgers=(
                SimpleNamespace(
                    owner_id=SimpleNamespace(value="alice"), variants=(variant,)
                ),
            ),
            institutional_decay_ledgers=(),
        )
    )
    status = await finalize_lineage_capture(arm, session, options)
    assert any(family == "knowledge" for family, _ in status.published)
    assert any(family == "technology" for family, _ in status.published)
    assert any(family == "narrative" for family, _ in status.published)
    assert (tmp_path / f"lineage-capture-status-{_RUN.value}.json").is_file()
