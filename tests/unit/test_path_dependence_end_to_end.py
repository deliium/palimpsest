"""End-to-end artifact workflow over a real smoke ensemble."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from experiments.path_dependence_artifacts import (
    BRANCH_SCHEMA_VERSION,
    OUTCOMES_SCHEMA_VERSION,
    PathDependenceArtifactStore,
)
from experiments.path_dependence_scenario import historical_contingency_scenario
from experiments.path_dependence_serialization import encode_path_dependence_spec
from research_runner.cli import main

pytestmark = pytest.mark.unit

SOURCE_DIGEST = "a" * 64


def test_smoke_ensemble_seals_complete_lineage_and_honest_unknown_outcomes(
    tmp_path: Path,
) -> None:
    spec = replace(
        historical_contingency_scenario(profile="smoke"),
        seeds=(11, 12, 13),
        replicates_per_seed=2,
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_bytes(encode_path_dependence_spec(spec))
    root = tmp_path / "artifacts"
    code = main(
        [
            "path-dependence",
            "run",
            "--spec",
            str(spec_path),
            "--artifact-root",
            str(root),
            "--code-revision",
            "unit-revision",
            "--source-artifact-digest",
            SOURCE_DIGEST,
        ]
    )
    assert code == 0
    ensemble_dir = next(item for item in root.iterdir() if item.is_dir())
    store = PathDependenceArtifactStore(root)
    ensemble = store.read_ensemble(ensemble_dir.name)
    assert len(cast(list[object], ensemble["slots"])) == 12
    completions = list(ensemble_dir.rglob("completion.json"))
    failures = list(ensemble_dir.rglob("failure.json"))
    assert len(completions) == 12
    assert failures == []
    assert len(list(ensemble_dir.rglob("prefix.json"))) == 1
    outcomes = list(ensemble_dir.rglob("outcomes.json"))
    assert len(outcomes) == 12
    for path in outcomes:
        data = store.read_outcomes(
            ensemble_id=ensemble_dir.name,
            child_id=path.parent.parent.name,
            attempt_id=path.parent.name,
        )
        assert data["schema_version"] == OUTCOMES_SCHEMA_VERSION
        coverage = cast(dict[str, object], data["coverage"])
        assert coverage["complete"] is False
        rows = cast(list[dict[str, object]], data["rows"])
        assert {row["availability"] for row in rows} == {"unknown"}
        assert {row["selector_id"] for row in rows} == {
            "norms.active_beliefs",
            "norms.belief_persistence",
            "relationships.mean_abs_delta",
            "institutions.persistent_candidates",
            "technology.living_retention",
            "narratives.endpoint_persistence",
            "inequality.resource_gini",
            "inequality.resource_theil",
            "cooperation.applied_rate",
        }
    for path in completions:
        document = store.read_branch(
            ensemble_id=ensemble_dir.name,
            child_id=path.parent.parent.name,
            attempt_id=path.parent.name,
            kind="completion",
        )
        assert document["schema_version"] == BRANCH_SCHEMA_VERSION
    assert (
        main(
            [
                "path-dependence",
                "compare",
                "--ensemble",
                str(root),
                "--ensemble-id",
                ensemble_dir.name,
            ]
        )
        == 0
    )
    comparison = store.read_comparison(
        ensemble_id=ensemble_dir.name, comparison_id="comparison-1"
    )
    assert comparison["causal_claim"] is False
    assert comparison["missing_policy"] == "complete_pair_conditional_no_zero_fill"
    assert not list(root.rglob("api"))
