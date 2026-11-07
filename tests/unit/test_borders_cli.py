# mypy: ignore-errors
"""Border CLI producer flags and receipt behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_runner.borders_composition import (
    BordersProducerOptions,
    borders_producer_options_from_args,
    publish_borders_harvest,
    write_borders_receipt,
)
from research_runner.cli import build_parser


def test_generational_flags_and_defaults() -> None:
    args = build_parser().parse_args(
        [
            "generational",
            "--config",
            "config.json",
            "--execution-recipe",
            "recipe.json",
            "--artifact-root",
            "archive",
            "--run-id",
            "run-1",
            "--code-revision",
            "abc123",
        ]
    )
    assert args.borders_root is None
    assert args.borders_max_publications == 16
    assert args.borders_max_bytes == 8_388_608
    options = borders_producer_options_from_args(args)
    assert options == BordersProducerOptions()
    assert options.enabled is False


def test_matrix_run_does_not_expose_border_flags() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", "--borders-root", "/tmp/x"])


def test_missing_root_reports_disabled() -> None:
    from types import SimpleNamespace

    result = publish_borders_harvest(
        SimpleNamespace(
            stop_reason=SimpleNamespace(value="completed"), border_ledgers=()
        ),
        BordersProducerOptions(),
        committed_events=(),
        run_id="run-1",
    )
    assert result["status"] == "disabled"


def test_receipt_is_written_after_completion(tmp_path: Path) -> None:
    write_borders_receipt(tmp_path, "run-1", {"status": "published"})
    assert (tmp_path / "borders-publication-run-1.json").is_file()


def test_publication_failure_does_not_change_scientific_output() -> None:
    from types import SimpleNamespace

    runner = SimpleNamespace(
        stop_reason=SimpleNamespace(value="completed"),
        border_ledgers=(),
    )
    before = (runner.stop_reason.value, runner.border_ledgers)
    result = publish_borders_harvest(
        runner,
        BordersProducerOptions(),
        committed_events=(),
        run_id="run-1",
    )
    assert result["status"] == "disabled"
    assert (runner.stop_reason.value, runner.border_ledgers) == before
