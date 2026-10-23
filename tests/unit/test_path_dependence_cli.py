"""Researcher CLI contracts for path-dependence artifacts."""

from __future__ import annotations

from pathlib import Path

from experiments.path_dependence_artifacts import PathDependenceArtifactStore
from experiments.path_dependence_scenario import historical_contingency_scenario
from experiments.path_dependence_serialization import encode_path_dependence_spec
from research_runner.cli import main

DIGEST_A = "a" * 64


def _spec_file(tmp_path: Path) -> Path:
    path = tmp_path / "path-dependence.json"
    path.write_bytes(
        encode_path_dependence_spec(historical_contingency_scenario(profile="smoke"))
    )
    return path


def _run(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "artifacts"
    code = main(
        [
            "path-dependence",
            "run",
            "--spec",
            str(_spec_file(tmp_path)),
            "--artifact-root",
            str(root),
            "--code-revision",
            "unit-revision",
            "--source-artifact-digest",
            DIGEST_A,
        ]
    )
    assert code == 0
    ensemble_dirs = [item for item in root.iterdir() if item.is_dir()]
    assert len(ensemble_dirs) == 1
    return root, ensemble_dirs[0].name


def test_path_dependence_cli_help_is_available(capsys: object) -> None:
    try:
        main(["path-dependence", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "inspect" in output
    assert "compare" in output
    assert "resume" in output


def test_run_seals_ensemble_and_inspect_is_read_only(tmp_path: Path) -> None:
    root, ensemble_id = _run(tmp_path)
    store = PathDependenceArtifactStore(root)
    ensemble = store.read_ensemble(ensemble_id)
    assert ensemble["schema_version"] == "path-dependence-ensemble-v1"
    assert len(list((root / ensemble_id / "prefixes").rglob("prefix.json"))) == 1
    assert len(list((root / ensemble_id / "branches").rglob("completion.json"))) == 2
    before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    assert (
        main(
            [
                "path-dependence",
                "inspect",
                "--ensemble",
                str(root),
                "--ensemble-id",
                ensemble_id,
            ]
        )
        == 0
    )
    after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    assert before == after


def test_resume_reports_uncreated_slots_and_compare_writes_artifact(
    tmp_path: Path,
) -> None:
    root, ensemble_id = _run(tmp_path)
    assert (
        main(
            [
                "path-dependence",
                "resume",
                "--ensemble",
                str(root),
                "--ensemble-id",
                ensemble_id,
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "path-dependence",
                "compare",
                "--ensemble",
                str(root),
                "--ensemble-id",
                ensemble_id,
                "--comparison-id",
                "comparison-1",
            ]
        )
        == 0
    )
    store = PathDependenceArtifactStore(root)
    comparison = store.read_comparison(
        ensemble_id=ensemble_id, comparison_id="comparison-1"
    )
    assert comparison["causal_claim"] is False
    assert comparison["multiplicity_policy"] == (
        "pointwise_exploratory_no_familywise_claim"
    )
