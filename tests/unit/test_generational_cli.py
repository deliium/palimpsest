"""Generational CLI composition and preflight."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.generational_runner_scenario import generational_runner_scenario
from research_runner.cli import build_parser
from simulation.runner_serialization import encode_runner_config


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


def test_help_exposes_generational_command() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "generational" in help_text


def test_generational_cli_runs_and_writes_archive(tmp_path: Path) -> None:
    config_path, recipe_path = _write_inputs(tmp_path)
    parser = build_parser()
    args = parser.parse_args(
        [
            "generational",
            "--config",
            str(config_path),
            "--execution-recipe",
            str(recipe_path),
            "--artifact-root",
            str(tmp_path / "archive"),
            "--run-id",
            "run-cli-1",
            "--code-revision",
            "abc123",
            "--source-clean",
        ]
    )
    assert args.func(args) == 0
    completion = (
        tmp_path / "archive" / "run-cli-1" / "single" / "completion.json"
    )
    assert completion.exists()


def test_generational_cli_requires_source_assertion(tmp_path: Path) -> None:
    config_path, recipe_path = _write_inputs(tmp_path)
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
            "run-cli-2",
            "--code-revision",
            "abc123",
        ]
    )
    assert args.func(args) == 2
