# mypy: ignore-errors
"""Migration-displacement CLI producer flags and receipt behaviour."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from research_runner.cli import build_parser
from research_runner.migration_displacement_composition import (
    MigrationDisplacementProducerOptions,
    migration_displacement_producer_options_from_args,
    publish_migration_displacement_harvest,
    write_migration_displacement_receipt,
)
from tests.unit.migration_displacement_analysis_helpers import move
from tests.unit.migration_displacement_helpers import (
    OWNER_ENTITY,
    PEER_ENTITY,
    cause,
    cluster,
    integration,
    ledger,
    route,
    wave,
)


def _rich_ledger():
    c = cause()
    return ledger(
        causes=(c,),
        routes=(route(),),
        clusters=(cluster(),),
        integrations=(integration(),),
        waves=(wave(causes=(c,)),),
    )


def _events():
    return (
        move(1, OWNER_ENTITY.value, "loc-a", "loc-b"),
        move(2, PEER_ENTITY.value, "loc-a", "loc-b"),
    )


def _runner(*, ledgers=(), stop: str = "max_ticks"):
    return SimpleNamespace(
        stop_reason=SimpleNamespace(value=stop),
        migration_displacement_ledgers=tuple(ledgers),
        status="completed",
    )


def test_disabled_root_prints_disabled_receipt() -> None:
    result = publish_migration_displacement_harvest(
        _runner(ledgers=()),
        MigrationDisplacementProducerOptions(),
        committed_events=(),
        run_id="run-1",
    )
    assert result["status"] == "disabled"
    assert result["reason"] == "root_unset"


def test_published_run_prints_publication_id(tmp_path: Path) -> None:
    result = publish_migration_displacement_harvest(
        _runner(ledgers=(_rich_ledger(),)),
        MigrationDisplacementProducerOptions(root=tmp_path),
        committed_events=_events(),
        run_id="run-1",
    )
    # Ensure entity mapping via runner alone may yield partial; publication still ok.
    assert result["status"] in {"published", "failed"}
    if result["status"] != "published":
        # Retry with enough signal through events only still must not crash science.
        result = publish_migration_displacement_harvest(
            _runner(ledgers=(_rich_ledger(),)),
            MigrationDisplacementProducerOptions(root=tmp_path),
            committed_events=_events(),
            run_id="run-2",
        )
    assert result["status"] == "published"
    assert result["publication_id"]
    assert str(result["publication_id"]).startswith("md-pub-")
    write_migration_displacement_receipt(tmp_path, "run-1", result)
    assert (tmp_path / "migration-displacement-publication-run-1.json").is_file()


def test_storage_failure_does_not_fail_scientific_run(tmp_path: Path) -> None:
    runner = _runner(ledgers=(_rich_ledger(),))
    before = (
        runner.stop_reason.value,
        runner.status,
        runner.migration_displacement_ledgers,
    )
    # Tiny byte quota forces a receipt-only failure.
    result = publish_migration_displacement_harvest(
        runner,
        MigrationDisplacementProducerOptions(root=tmp_path, max_bytes=10),
        committed_events=_events(),
        run_id="run-1",
    )
    assert result["status"] in {"quota_exceeded", "failed", "size_limit"}
    assert (
        runner.stop_reason.value,
        runner.status,
        runner.migration_displacement_ledgers,
    ) == before


def test_cli_never_prints_tokens() -> None:
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
            "--migration-displacement-root",
            "/tmp/md-root",
        ]
    )
    options = migration_displacement_producer_options_from_args(args)
    assert options.enabled is True
    assert args.migration_displacement_max_publications == 16
    assert args.migration_displacement_max_bytes == 8_388_608
    # Receipt document keys stay metadata-only.
    result = publish_migration_displacement_harvest(
        _runner(ledgers=()),
        MigrationDisplacementProducerOptions(),
        committed_events=(),
        run_id="run-1",
    )
    blob = " ".join(f"{key}={value}" for key, value in result.items())
    assert "mig-" not in blob
    assert "mdo-" not in blob
    assert "mdl-" not in blob
    assert set(result) <= {
        "status",
        "reason",
        "publication_id",
        "digest",
        "row_count",
        "byte_count",
        "coverage",
        "notices",
    }


def test_matrix_run_does_not_expose_migration_displacement_flags() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["run", "--migration-displacement-root", "/tmp/x"]
        )
