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


def test_cli_run_and_status(tmp_path) -> None:
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
