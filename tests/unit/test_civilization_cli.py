"""Opt-in civilization CLI composition and publication status."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from experiments.civilization_capture import CivilizationEvidenceRecorder
from research_runner.civilization_composition import (
    CivilizationProducerOptions,
    finalize_civilization_capture,
)
from simulation.civilization_capture import CivilizationCaptureOptions

pytestmark = pytest.mark.unit


@dataclass
class _Result:
    run_id: object


@dataclass
class _Arm:
    runner_result: _Result


def _recorder():
    from tests.unit.test_civilization_publication import (
        _frame,
        _inventory,
    )

    recorder = CivilizationEvidenceRecorder(CivilizationCaptureOptions(enabled=True))
    inventories = (_inventory("not-the-body-id"),)
    for tick in (0, 1):
        assert recorder.capture_boundary(_frame(tick, inventories=inventories))
    return recorder


def _arm(run_id: str):
    class _RunId:
        value = run_id

    return _Arm(_Result(_RunId()))


@pytest.mark.asyncio
async def test_finalizer_publishes_and_writes_separate_status(tmp_path: Path):
    from simulation.models import RunId

    recorder = _recorder()
    options = CivilizationProducerOptions(
        root=tmp_path / "civilization",
        capture=CivilizationCaptureOptions(enabled=True),
        status_root=tmp_path / "status",
    )
    arm = _arm("run-capture")
    arm.runner_result.run_id = RunId("run-capture")
    receipt = await finalize_civilization_capture(arm, recorder, options)
    assert receipt.failure_code is None
    assert receipt.published_boundaries == 2
    assert receipt.publication is not None
    payload = json.loads(
        (tmp_path / "status" / "civilization-status-run-capture.json").read_text()
    )
    assert payload["scientific_status"] == "completed"
    assert payload["publication_status"] == "ready"


@pytest.mark.asyncio
async def test_publication_failure_never_claims_scientific_failure(tmp_path: Path):
    from simulation.models import RunId

    recorder = _recorder()
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("file", encoding="utf-8")
    options = CivilizationProducerOptions(
        root=blocked,
        capture=CivilizationCaptureOptions(enabled=True),
        status_root=tmp_path / "status",
    )
    arm = _arm("run-capture")
    arm.runner_result.run_id = RunId("run-capture")
    receipt = await finalize_civilization_capture(arm, recorder, options)
    assert receipt.failure_code == "civilization_publication_failed"
    payload = json.loads(
        (tmp_path / "status" / "civilization-status-run-capture.json").read_text()
    )
    assert payload["scientific_status"] == "completed"
    assert payload["publication_status"] == "failed"


def test_cli_civilization_flags_require_root_and_respect_bounds():
    from research_runner.cli import _civilization_options_from_args, build_parser

    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--matrix",
            "matrix.json",
            "--manifest-root",
            "manifest",
            "--civilization-overlays-root",
            "/tmp/civilization",
            "--civilization-cadence",
            "2",
        ]
    )
    options = _civilization_options_from_args(args)
    assert options is not None
    assert options.capture.cadence == 2
    invalid = parser.parse_args(
        [
            "run",
            "--matrix",
            "matrix.json",
            "--manifest-root",
            "manifest",
            "--civilization-cadence",
            "2",
        ]
    )
    with pytest.raises(ValueError):
        _civilization_options_from_args(invalid)


def test_cli_civilization_spool_option_is_explicit_and_lazy(tmp_path: Path):
    from research_runner.cli import _civilization_options_from_args, build_parser

    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--matrix",
            "matrix.json",
            "--manifest-root",
            "manifest",
            "--civilization-overlays-root",
            "/tmp/civilization",
            "--civilization-spool-root",
            str(tmp_path / "spool"),
        ]
    )
    options = _civilization_options_from_args(args)
    assert options is not None
    assert options.spool is not None
    assert not (tmp_path / "spool").exists() or (tmp_path / "spool").is_dir()
    missing_root = parser.parse_args(
        [
            "run",
            "--matrix",
            "matrix.json",
            "--manifest-root",
            "manifest",
            "--civilization-spool-root",
            str(tmp_path / "spool-2"),
        ]
    )
    with pytest.raises(ValueError, match="overlays-root"):
        _civilization_options_from_args(missing_root)


def test_matrix_adoption_requires_a_committed_publication():
    from experiments.matrix_runner import (
        MatrixBatchDependencies,
        _civilization_ready,
    )

    missing = MatrixBatchDependencies(
        package_version="test",
        civilization_installer=lambda runner: object(),
        civilization_publication_exists=lambda run_id: False,
    )
    assert not _civilization_ready(missing, "run-capture")
    ready = MatrixBatchDependencies(
        package_version="test",
        civilization_installer=lambda runner: object(),
        civilization_publication_exists=lambda run_id: True,
    )
    assert _civilization_ready(ready, "run-capture")
    off = MatrixBatchDependencies(package_version="test")
    assert _civilization_ready(off, "run-capture")


@pytest.mark.asyncio
async def test_run_one_assignment_round_trip_publishes_with_hooks(tmp_path: Path):
    from experiments.coordinator import ExperimentAssignment
    from experiments.matrix_factors import matrix_reference_fixture_base
    from experiments.matrix_runner import run_one_assignment
    from persistence.civilization_filesystem import create_civilization_reader
    from research_runner.civilization_composition import (
        install_civilization_capture,
    )
    from simulation.models import RunId

    config = matrix_reference_fixture_base(max_ticks=2)
    assignment = ExperimentAssignment(
        experiment_id="reference",
        condition_id="reference",
        condition_ordinal=0,
        seed=config.seed,
        seed_ordinal=0,
        replicate_index=0,
        run_id=RunId("run-cli-round-trip"),
        runner_config=config,
    )
    options = CivilizationProducerOptions(
        root=tmp_path / "civilization",
        capture=CivilizationCaptureOptions(enabled=True),
        status_root=tmp_path / "status",
    )

    async def _finalize(arm, session):
        return await finalize_civilization_capture(arm, session, options)

    arm = await run_one_assignment(
        assignment,
        civilization_installer=lambda runner: install_civilization_capture(
            runner, options
        ),
        civilization_finalizer=_finalize,
    )
    assert arm.runner_result.ticks_committed == 2
    assert create_civilization_reader(options.root).has_run(assignment.run_id.value)
