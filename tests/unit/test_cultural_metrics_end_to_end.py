"""Hand-calculated and real-matrix cultural metric end-to-end gates."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from analysis.cultural_evolution_evidence import CulturalAnalysisWindow
from analysis.cultural_evolution_metrics import assemble_cultural_evolution_documents
from analysis.models import MetricAvailability
from experiments.cultural_evidence_serialization import (
    decode_cultural_evolution_evidence,
)
from research_runner.cli import main

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "cultural_metrics"
    / "known-lineage-v1.json"
)
_MATRIX = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "matrices"
    / "v3-cultural-metrics.json"
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _documents(inputs: object) -> dict[str, list[dict[str, object]]]:
    encoded = decode_cultural_evolution_evidence(_FIXTURE.read_bytes())
    docs = assemble_cultural_evolution_documents(
        inputs,  # type: ignore[arg-type]
        evidence_manifest_digest=encoded.digest,
    )
    result: dict[str, list[dict[str, object]]] = {}
    for document in docs:
        raw = document.values["rows_json"]
        assert isinstance(raw, str)
        result[document.metric_family] = json.loads(raw)
    return result


def _group_ids(row: dict[str, object]) -> list[object]:
    raw = row["group_ids"]
    assert isinstance(raw, list)
    return raw


def _row(
    rows: list[dict[str, object]],
    measurement_id: str,
    *,
    dimension: str | None = None,
    baseline: int | None = None,
    end: int | None = None,
    group_ids: tuple[str, ...] | None = None,
    **extra: object,
) -> dict[str, object]:
    matches = [
        row
        for row in rows
        if row["measurement_id"] == measurement_id
        and (dimension is None or row["dimension"] == dimension)
        and (baseline is None or row["baseline_tick"] == baseline)
        and (end is None or row["end_tick"] == end)
        and (group_ids is None or tuple(_group_ids(row)) == group_ids)
        and all(row[key] == value for key, value in extra.items())
    ]
    assert len(matches) == 1, (measurement_id, len(matches))
    return matches[0]


def test_known_lineage_fixture_covers_all_requested_areas() -> None:
    encoded = decode_cultural_evolution_evidence(_FIXTURE.read_bytes())
    rows = _documents(encoded.inputs)

    dynamics = rows["cultural_trait_dynamics"]
    for label in ("p", "q", "m2"):
        assert _row(
            dynamics,
            "trait_frequency",
            dimension="feature:practice",
            baseline=4,
            end=4,
            trait_id=_digest(label),
        )["value"] == pytest.approx(1 / 3)
    persistence = _row(dynamics, "endpoint_persistence", dimension="feature:practice")
    assert persistence["value"] == pytest.approx(1.0)
    assert persistence["denominator"] == pytest.approx(2.0)
    continuous = _row(dynamics, "continuous_persistence", dimension="feature:practice")
    assert continuous["value"] == pytest.approx(0.5)
    extinction = _row(dynamics, "extinction_transition", dimension="feature:practice")
    assert extinction["value"] == pytest.approx(1.0)
    assert extinction["trait_id"] == _digest("q")
    assert (
        _row(
            dynamics,
            "richness",
            dimension="feature:practice",
            baseline=4,
            end=4,
        )["value"]
        == 3.0
    )
    assert _row(
        dynamics,
        "shannon_entropy",
        dimension="feature:practice",
        baseline=4,
        end=4,
    )["value"] == pytest.approx(math.log(3))

    transmission = rows["cultural_evolution_transmission"]
    assert _row(transmission, "exact_fidelity")["value"] == pytest.approx(2 / 3)
    assert _row(transmission, "mutation_rate")["value"] == pytest.approx(1 / 3)
    assert _row(transmission, "horizontal_share")["value"] == pytest.approx(1 / 3)
    assert _row(transmission, "forward_intergenerational_share")[
        "value"
    ] == pytest.approx(2 / 3)
    assert _row(transmission, "vertical_kin_share")["value"] == pytest.approx(1 / 3)
    assert _row(transmission, "declared_mutation_share")["value"] == pytest.approx(
        1 / 3
    )

    structure = rows["cultural_population_structure"]
    divergence = _row(
        structure,
        "between_group_js_divergence",
        dimension="vocabulary",
        baseline=4,
        end=4,
        group_ids=("group-north", "group-south"),
    )
    assert divergence["value"] == pytest.approx(math.log(2))
    convergence = _row(
        structure,
        "within_group_convergence",
        dimension="vocabulary",
        baseline=1,
        end=4,
        group_ids=("group-north",),
    )
    assert convergence["value"] == pytest.approx(2 / 3)

    narrative = rows["cultural_narrative_survival"]
    assert _row(narrative, "baseline_variant_count")["value"] == 2.0
    assert _row(narrative, "surviving_baseline_count")["value"] == 2.0
    assert _row(narrative, "endpoint_persistence")["value"] == pytest.approx(1.0)
    assert _row(narrative, "continuous_persistence")["value"] == pytest.approx(1.0)

    vocabulary = rows["cultural_vocabulary_differentiation"]
    assert _row(
        vocabulary,
        "between_group_vocabulary_jaccard",
        baseline=4,
        end=4,
        group_ids=("group-north", "group-south"),
    )["value"] == pytest.approx(1.0)
    assert _row(
        vocabulary,
        "between_group_vocabulary_js",
        baseline=4,
        end=4,
        group_ids=("group-north", "group-south"),
    )["value"] == pytest.approx(math.log(2))

    technology = rows["cultural_technology_continuity"]
    assert _row(technology, "living_retention")["value"] == pytest.approx(0.5)
    assert _row(technology, "living_loss_share")["value"] == pytest.approx(0.5)
    assert _row(technology, "global_loss_share")["value"] == pytest.approx(0.0)
    assert _row(technology, "exact_variant_retention")["value"] == pytest.approx(0.5)
    assert _row(technology, "technology_preserved_count")["value"] == 2.0


def test_empty_baseline_is_not_rebased() -> None:
    encoded = decode_cultural_evolution_evidence(_FIXTURE.read_bytes())
    inputs = replace(
        encoded.inputs,
        window=CulturalAnalysisWindow(baseline_boundary=0, end_boundary=4),
    )
    rows = _documents(inputs)
    persistence = _row(
        rows["cultural_trait_dynamics"],
        "endpoint_persistence",
        dimension="feature:practice",
    )
    assert persistence["value"] is None
    assert persistence["reason_code"] == "empty_baseline"
    assert persistence["baseline_tick"] == 0
    technology = _row(rows["cultural_technology_continuity"], "living_retention")
    assert technology["value"] is None
    assert technology["reason_code"] == "empty_baseline"


def test_real_generational_matrix_capture_and_comparison(tmp_path: Path) -> None:
    recipe = tmp_path / "recipe.json"
    recipe.write_text(
        json.dumps(
            {
                "recipe_id": "plain-generational",
                "version": "1",
                "params": {},
                "intervention_id": None,
                "intervention_version": None,
                "intervention_params": None,
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest"
    archive = tmp_path / "archive"
    run_code = main(
        [
            "--code-revision",
            "fixture-rev",
            "run",
            "--matrix",
            str(_MATRIX),
            "--manifest-root",
            str(manifest),
            "--generational-artifact-root",
            str(archive),
            "--execution-recipe",
            str(recipe),
            "--source-clean",
            "--cultural-metrics",
        ]
    )
    assert run_code == 0
    sidecars = sorted((manifest / "cells").glob("*.cultural-metrics.json"))
    assert len(sidecars) == 6
    aggregate_code = main(
        [
            "--code-revision",
            "fixture-rev",
            "aggregate",
            "--matrix",
            str(_MATRIX),
            "--manifest-root",
            str(manifest),
            "--cultural-summary",
            "--cultural-contrast",
            "record_availability-absent:record_availability-present",
        ]
    )
    assert aggregate_code == 0
    comparison = json.loads(
        (manifest / "cultural-metric-comparison.json").read_text(encoding="utf-8")
    )
    assert comparison["schema_version"] == "cultural-metric-comparison-v1"
    assert comparison["method"] == "student_t_seed_block_mean"
    assert len(comparison["conditions"]) == 2
    contrast = comparison["contrasts"][0]
    assert contrast["pairing_basis"] == "seed_ordinal_replicate"
    assert contrast["n"] == 3
    assert contrast["mean_difference"] is not None
    assert contrast["ci_low"] is not None
    assert contrast["shared_stream_status"] in {"shared", "mixed", "unknown"}


def test_default_runner_versions_unchanged_without_capture() -> None:
    from experiments.matrix_factors import matrix_reference_fixture_base

    config = matrix_reference_fixture_base(max_ticks=1)
    assert config.schema_version == "runner-config-v4"
    assert MetricAvailability.PRESENT.value == "present"


def test_legacy_benchmark_matrix_still_decodes_and_expands() -> None:
    from experiments.matrix_expand import expand_matrix
    from experiments.matrix_serialization import decode_matrix_spec

    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "matrices"
        / "v2-benchmark-suite.json"
    )
    spec = decode_matrix_spec(fixture.read_bytes())
    definition, cells = expand_matrix(spec)
    assert definition.conditions
    assert cells


def test_current_catalog_and_default_versions_are_pinned() -> None:
    from analysis.specifications import METRIC_FAMILY_COUNT, validate_metric_catalog
    from simulation.compatibility import ALEMBIC_HEAD_REVISION

    validate_metric_catalog()
    assert METRIC_FAMILY_COUNT == 136
    assert ALEMBIC_HEAD_REVISION == "0017"
