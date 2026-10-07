"""Cultural narrative lineage metric family."""

from __future__ import annotations

from analysis.cultural_narrative_metrics import (
    CULTURAL_NARRATIVE_LINEAGE_METRIC_VERSION,
    compute_cultural_narrative_lineage,
)
from analysis.models import MetricAvailability
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    metric_specification,
)


def test_family_registered_and_version_locked() -> None:
    assert CULTURAL_NARRATIVE_LINEAGE_METRIC_VERSION == "cultural_narrative_lineage@1"
    assert METRIC_FAMILY_COUNT == 62
    spec = metric_specification(MetricFamilyId.CULTURAL_NARRATIVE_LINEAGE)
    assert spec.family_id is MetricFamilyId.CULTURAL_NARRATIVE_LINEAGE
    assert "persistence_rate" in spec.value_keys
    assert "inaccuracy_vs_objective" in spec.value_keys


def test_empty_rows_are_absent() -> None:
    document = compute_cultural_narrative_lineage(
        (),
        run_id="run-ab",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.ABSENT


def test_persistence_and_inaccuracy_blocks() -> None:
    rows = (
        {
            "tick": 1,
            "owner_id": "ada",
            "variant_id": "v1",
            "fingerprint": "fp-founding",
            "status": "active",
            "strength": 0.6,
            "origin": "observed_event",
            "founding_origin": "observed_event",
            "repetition_count": 3,
            "mutation_generation": 0,
            "has_source_event": True,
            "founding_had_source_event": True,
            "location_count": 1,
            "carrier_count": 1,
            "first_tick": 1,
            "last_tick": 1,
            "parent_count": 0,
            "competing_count": 0,
        },
        {
            "tick": 5,
            "owner_id": "ada",
            "variant_id": "v2",
            "fingerprint": "fp-child",
            "status": "active",
            "strength": 0.7,
            "origin": "retold_story",
            "founding_origin": "observed_event",
            "repetition_count": 4,
            "mutation_generation": 1,
            "has_source_event": False,
            "founding_had_source_event": True,
            "has_source_memory": False,
            "location_count": 2,
            "carrier_count": 3,
            "first_tick": 2,
            "last_tick": 5,
            "parent_count": 1,
            "competing_count": 1,
            "token_add_rate": 0.5,
            "token_loss_rate": 0.25,
            "covers_source": False,
            "transmission_root_id": "root-1",
        },
        {
            "tick": 5,
            "owner_id": "ada",
            "variant_id": "v1",
            "fingerprint": "fp-founding",
            "status": "active",
            "strength": 0.55,
            "origin": "observed_event",
            "founding_origin": "observed_event",
            "repetition_count": 5,
            "mutation_generation": 0,
            "has_source_event": True,
            "founding_had_source_event": True,
            "location_count": 1,
            "carrier_count": 2,
            "first_tick": 1,
            "last_tick": 5,
            "parent_count": 0,
            "competing_count": 1,
            "transmission_root_id": "root-1",
        },
    )
    document = compute_cultural_narrative_lineage(
        rows,
        run_id="run-ab",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["active_variant_count"] == 2
    assert document.values["inaccuracy_vs_objective"] == 1.0
    assert document.values["multi_location_rate"] == 0.5
    assert document.values["social_reach_rate"] == 0.5
    assert document.values["source_event_drop_rate"] == 0.5
    assert "branch_rate" in document.values
    assert "merge_rate" in document.values
    assert "mean_location_span" in document.values
    assert "mean_carrier_span" in document.values
