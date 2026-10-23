"""Unit tests for research_runner CLI composition (no api imports)."""

from __future__ import annotations

import ast
from pathlib import Path

from experiments.matrix_factors import matrix_reference_fixture_base
from experiments.matrix_models import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    GroupRole,
    MatrixEmbeddedBase,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
)
from experiments.matrix_serialization import encode_matrix_spec
from experiments.models import ExperimentSeedMatrix
from research_runner.cli import main
from research_runner.composition import resolve_package_version


def _write_matrix(path: Path) -> None:
    spec = ExperimentMatrixSpec(
        matrix_id="matrix-cli-demo",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(
            runner_config=matrix_reference_fixture_base(max_ticks=1)
        ),
        factors=(
            MatrixFactor(
                factor_id=MatrixFactorId.MEMORY_TYPE,
                levels=(
                    MatrixFactorLevel(
                        level_id="reference",
                        label_code="ref",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="reconstructive",
                        label_code="recon",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
            MatrixFactor(
                factor_id=MatrixFactorId.TOM,
                levels=(
                    MatrixFactorLevel(level_id="off", label_code="tom_off"),
                    MatrixFactorLevel(level_id="on", label_code="tom_on"),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(11,)),
    )
    path.write_bytes(encode_matrix_spec(spec))


def test_resolve_package_version_without_api() -> None:
    version = resolve_package_version()
    assert isinstance(version, str) and version


def test_cli_run_and_status(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    manifest_root = tmp_path / "manifest"
    _write_matrix(matrix_path)
    code = main(
        [
            "run",
            "--matrix",
            str(matrix_path),
            "--manifest-root",
            str(manifest_root),
        ]
    )
    assert code == 0
    assert (manifest_root / "manifest.json").exists()
    assert (manifest_root / "aggregate.json").exists()
    status = main(["status", "--manifest-root", str(manifest_root)])
    assert status == 0


def test_research_runner_sources_never_import_api() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "research_runner"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("api")
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith("api")


def test_cli_cultural_capture_and_summary(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    manifest_root = tmp_path / "manifest"
    _write_matrix(matrix_path)
    run_code = main(
        [
            "run",
            "--matrix",
            str(matrix_path),
            "--manifest-root",
            str(manifest_root),
            "--cultural-metrics",
            "--cultural-max-frames",
            "100",
            "--cultural-baseline-boundary",
            "0",
        ]
    )
    assert run_code == 0
    aggregate_code = main(
        [
            "aggregate",
            "--matrix",
            str(matrix_path),
            "--manifest-root",
            str(manifest_root),
            "--cultural-summary",
        ]
    )
    assert aggregate_code == 0
    comparison = manifest_root / "cultural-metric-comparison.json"
    assert comparison.exists()
    payload = comparison.read_bytes()
    assert b'"schema_version":"cultural-metric-comparison-v1"' in payload


def test_cli_cultural_options_require_capture(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    manifest_root = tmp_path / "manifest"
    _write_matrix(matrix_path)
    code = main(
        [
            "run",
            "--matrix",
            str(matrix_path),
            "--manifest-root",
            str(manifest_root),
            "--cultural-max-frames",
            "100",
        ]
    )
    assert code == 2
    assert not (manifest_root / "manifest.json").exists()


def test_cli_cultural_summary_validation(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    manifest_root = tmp_path / "manifest"
    _write_matrix(matrix_path)
    assert (
        main(
            [
                "run",
                "--matrix",
                str(matrix_path),
                "--manifest-root",
                str(manifest_root),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "aggregate",
                "--matrix",
                str(matrix_path),
                "--manifest-root",
                str(manifest_root),
                "--confidence",
                "0.9",
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "aggregate",
                "--matrix",
                str(matrix_path),
                "--manifest-root",
                str(manifest_root),
                "--cultural-summary",
                "--confidence",
                "1.5",
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "aggregate",
                "--matrix",
                str(matrix_path),
                "--manifest-root",
                str(manifest_root),
                "--cultural-summary",
                "--cultural-contrast",
                "unknown:other",
            ]
        )
        == 2
    )


def test_cli_cultural_summary_without_artifacts_is_explicit(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    manifest_root = tmp_path / "manifest"
    _write_matrix(matrix_path)
    assert (
        main(
            [
                "run",
                "--matrix",
                str(matrix_path),
                "--manifest-root",
                str(manifest_root),
            ]
        )
        == 0
    )
    code = main(
        [
            "aggregate",
            "--matrix",
            str(matrix_path),
            "--manifest-root",
            str(manifest_root),
            "--cultural-summary",
        ]
    )
    assert code == 0
    payload = (manifest_root / "cultural-metric-comparison.json").read_bytes()
    assert b'"reasons":["cultural_capture_missing"]' in payload
    assert b'"conditions":[]' in payload


def test_cli_cultural_caps_and_windows_are_validated(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    manifest_root = tmp_path / "manifest"
    _write_matrix(matrix_path)
    for extra in (
        ["--cultural-max-frames", "0"],
        ["--cultural-max-rows", "0"],
        ["--cultural-baseline-boundary", "-1"],
        ["--cultural-baseline-boundary", "2"],
        ["--cultural-end-boundary", "0"],
        ["--cultural-end-boundary", "2"],
    ):
        code = main(
            [
                "run",
                "--matrix",
                str(matrix_path),
                "--manifest-root",
                str(manifest_root),
                "--cultural-metrics",
                *extra,
            ]
        )
        assert code == 2


def test_cli_corrupt_cultural_artifact_fails_without_replacing_summary(
    tmp_path: Path,
) -> None:
    matrix_path = tmp_path / "matrix.json"
    manifest_root = tmp_path / "manifest"
    _write_matrix(matrix_path)
    assert (
        main(
            [
                "run",
                "--matrix",
                str(matrix_path),
                "--manifest-root",
                str(manifest_root),
                "--cultural-metrics",
            ]
        )
        == 0
    )
    cells = list((manifest_root / "cells").glob("*.cultural-evidence.json"))
    cells[0].write_bytes(b"{}")
    code = main(
        [
            "aggregate",
            "--matrix",
            str(matrix_path),
            "--manifest-root",
            str(manifest_root),
            "--cultural-summary",
        ]
    )
    assert code == 1
    assert not (manifest_root / "cultural-metric-comparison.json").exists()
