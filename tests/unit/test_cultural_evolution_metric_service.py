"""Six-family cultural evolution metric service integration."""

from __future__ import annotations

import json

from analysis.cultural_evolution_evidence import (
    CULTURAL_DIMENSIONS,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    InventoryBoundary,
    TraitPresence,
)
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    metric_specification,
    validate_metric_catalog,
)

_DIGEST = "d" * 64
_TRAIT = "1" * 64


def _coverage(owners: tuple[str, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (owner, dimension, "complete")
        for owner in owners
        for dimension in CULTURAL_DIMENSIONS
    )


def _boundary(tick: int, entries: tuple[TraitPresence, ...]) -> InventoryBoundary:
    owners = tuple(sorted({entry.owner_id for entry in entries})) or ("owner",)
    return InventoryBoundary(
        boundary_tick=tick,
        living_owner_ids=owners,
        generation_by_owner={owner: 0 for owner in owners},
        owner_dimension_coverage=_coverage(owners),
        entries=entries,
    )


def _inputs(*, boundaries: tuple[InventoryBoundary, ...] | None = None):
    return CulturalEvolutionInputs(
        run_id="run-metrics",
        source_revision="rev-metrics",
        window=CulturalAnalysisWindow(end_boundary=1),
        boundaries=boundaries if boundaries is not None else (),
    )


def _entry(tick: int) -> TraitPresence:
    return TraitPresence(
        owner_id="owner",
        local_entry_id="entry-1",
        dimension="feature:practice",
        content_digest=_TRAIT,
        acquisition_tick=tick,
    )


def _computation(cultural=None):
    return MetricComputationInputs(
        run_id="run-metrics",
        input_revision="rev-metrics",
        window_end=1,
        cultural_evolution=cultural,
        cultural_evolution_evidence_digest=_DIGEST if cultural is not None else None,
    )


def test_six_cultural_families_are_in_the_catalog() -> None:
    specs = validate_metric_catalog()
    assert METRIC_FAMILY_COUNT == 136
    assert len(specs) == 136
    for family in (
        MetricFamilyId.CULTURAL_TRAIT_DYNAMICS,
        MetricFamilyId.CULTURAL_EVOLUTION_TRANSMISSION,
        MetricFamilyId.CULTURAL_POPULATION_STRUCTURE,
        MetricFamilyId.CULTURAL_NARRATIVE_SURVIVAL,
        MetricFamilyId.CULTURAL_VOCABULARY_DIFFERENTIATION,
        MetricFamilyId.CULTURAL_TECHNOLOGY_CONTINUITY,
    ):
        assert metric_specification(family).algorithm_version == "1"


def test_no_capture_omits_cultural_families() -> None:
    bundle = assemble_metric_documents(_computation())
    assert not [
        doc
        for doc in bundle.documents
        if doc.metric_family.startswith("cultural_")
        and doc.metric_family
        in {
            "cultural_trait_dynamics",
            "cultural_evolution_transmission",
            "cultural_population_structure",
            "cultural_narrative_survival",
            "cultural_vocabulary_differentiation",
            "cultural_technology_continuity",
        }
    ]


def test_complete_capture_produces_six_separate_documents() -> None:
    cultural = _inputs(
        boundaries=(
            _boundary(0, (_entry(0),)),
            _boundary(1, (_entry(0),)),
        )
    )
    bundle = assemble_metric_documents(_computation(cultural))
    documents = {
        doc.metric_family: doc
        for doc in bundle.documents
        if doc.metric_family
        in {
            "cultural_trait_dynamics",
            "cultural_evolution_transmission",
            "cultural_population_structure",
            "cultural_narrative_survival",
            "cultural_vocabulary_differentiation",
            "cultural_technology_continuity",
        }
    }
    assert len(documents) == 6
    for document in documents.values():
        assert document.values["policy_version"] == "cultural-evolution.v1"
        assert document.values["evidence_manifest_digest"] == _DIGEST
        assert isinstance(document.values["rows_json"], str)
    dynamics = documents["cultural_trait_dynamics"]
    assert dynamics.values["measurement_count"] > 0
    rows = json.loads(dynamics.values["rows_json"])
    assert rows
    assert all(set(row) == set(_measurement_keys()) for row in rows)
    assert all(row["row_id"] for row in rows)
    assert dynamics.availability is MetricAvailability.PRESENT


def test_attempted_empty_capture_gives_unknown_not_fabricated_panel() -> None:
    bundle = assemble_metric_documents(_computation(_inputs(boundaries=())))
    documents = {
        doc.metric_family: doc
        for doc in bundle.documents
        if doc.metric_family
        in {
            "cultural_trait_dynamics",
            "cultural_evolution_transmission",
            "cultural_population_structure",
            "cultural_narrative_survival",
            "cultural_vocabulary_differentiation",
            "cultural_technology_continuity",
        }
    }
    assert len(documents) == 6
    assert all(
        doc.availability is MetricAvailability.UNKNOWN for doc in documents.values()
    )
    assert all(doc.values["measurement_count"] == 0 for doc in documents.values())


def test_rows_json_is_canonical_and_digest_bound_before_any_write() -> None:
    cultural = _inputs(
        boundaries=(
            _boundary(0, (_entry(0),)),
            _boundary(1, (_entry(0),)),
        )
    )
    first = assemble_metric_documents(_computation(cultural))
    second = assemble_metric_documents(_computation(cultural))
    first_cultural = [
        doc
        for doc in first.documents
        if doc.metric_family
        in {
            "cultural_trait_dynamics",
            "cultural_evolution_transmission",
            "cultural_population_structure",
            "cultural_narrative_survival",
            "cultural_vocabulary_differentiation",
            "cultural_technology_continuity",
        }
    ]
    second_cultural = [
        doc
        for doc in second.documents
        if doc.metric_family
        in {
            "cultural_trait_dynamics",
            "cultural_evolution_transmission",
            "cultural_population_structure",
            "cultural_narrative_survival",
            "cultural_vocabulary_differentiation",
            "cultural_technology_continuity",
        }
    ]
    assert [doc.values["rows_json"] for doc in first_cultural] == [
        doc.values["rows_json"] for doc in second_cultural
    ]
    rows_json = next(
        doc.values["rows_json"]
        for doc in first.documents
        if doc.metric_family == "cultural_trait_dynamics"
    )
    assert rows_json == json.dumps(
        json.loads(rows_json),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def test_legacy_metric_documents_unchanged_without_cultural_field() -> None:
    with_field = assemble_metric_documents(_computation())
    without_field = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-metrics",
            input_revision="rev-metrics",
            window_end=1,
        )
    )
    assert with_field.documents == without_field.documents
    assert with_field.fingerprints == without_field.fingerprints


def _measurement_keys() -> tuple[str, ...]:
    return (
        "row_id",
        "measurement_id",
        "dimension",
        "representation",
        "scope",
        "partition_id",
        "group_ids",
        "population_basis",
        "denominator_code",
        "baseline_tick",
        "end_tick",
        "trait_id",
        "lineage_id",
        "subject_id",
        "units",
        "value",
        "numerator",
        "denominator",
        "availability",
        "reason_code",
        "coverage_observed",
        "coverage_expected",
        "left_censored",
        "right_censored",
        "evidence_ids",
    )
