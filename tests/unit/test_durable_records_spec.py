"""DurableRecordsSpec construction and nested policy validation."""

from __future__ import annotations

import pytest

from simulation.runner_models import (
    DurableAnnotationPolicy,
    DurableCopyFidelityPolicy,
    DurableIntegrityPolicy,
    DurableLineagePolicy,
    DurableRecordsSpec,
    example_durable_records_spec,
)


def test_example_durable_records_spec_defaults() -> None:
    spec = example_durable_records_spec()
    assert spec.durable_records_mode == "deterministic"
    assert len(spec.enabled_genres) == 8
    assert "warning" in spec.enabled_genres
    assert "chronicle" in spec.enabled_genres
    assert spec.copy_fidelity_policy.default_fidelity == "perfect"
    assert spec.integrity_policy.tombstone_on_destroy is True
    assert spec.annotation_policy.max_annotations_per_record == 8
    assert spec.lineage_policy.max_copy_generation == 8
    assert spec.perception_mode == "marks_and_meta"
    assert spec.rng_namespace == "durable_records"


def test_mode_disabled_rejected() -> None:
    with pytest.raises(ValueError, match="durable_records_mode_invalid"):
        DurableRecordsSpec(
            enabled_genres=("warning",),
            durable_records_mode="disabled",
        )


def test_empty_genres_rejected() -> None:
    with pytest.raises(ValueError, match="durable_genres_empty"):
        DurableRecordsSpec(enabled_genres=())


def test_unknown_genre_rejected() -> None:
    with pytest.raises(ValueError, match="durable_genre_invalid"):
        DurableRecordsSpec(enabled_genres=("not_a_genre",))


def test_duplicate_genre_rejected() -> None:
    with pytest.raises(ValueError, match="durable_genre_duplicate"):
        DurableRecordsSpec(enabled_genres=("warning", "warning"))


def test_unknown_fidelity_rejected() -> None:
    with pytest.raises(ValueError, match="durable_copy_fidelity_invalid"):
        DurableCopyFidelityPolicy(default_fidelity="random")


def test_annotation_cap_must_be_positive() -> None:
    with pytest.raises(ValueError, match="durable_annotation_cap_invalid"):
        DurableAnnotationPolicy(max_annotations_per_record=0)


def test_copy_generation_cap_must_be_positive() -> None:
    with pytest.raises(ValueError, match="durable_copy_generation_cap_invalid"):
        DurableLineagePolicy(max_copy_generation=0)


def test_lossy_fidelity_example() -> None:
    spec = example_durable_records_spec(default_fidelity="lossy")
    assert spec.copy_fidelity_policy.default_fidelity == "lossy"


def test_canonical_payload_exact_keys() -> None:
    payload = example_durable_records_spec().canonical_payload()
    assert set(payload) == {
        "annotation_policy",
        "copy_fidelity_policy",
        "durable_records_mode",
        "enabled_genres",
        "integrity_policy",
        "lineage_policy",
        "perception_mode",
        "rng_namespace",
    }
    assert set(payload["copy_fidelity_policy"]) == {
        "copy_requires_hold_or_colocation",
        "default_fidelity",
        "max_mark_edits",
        "max_relation_edits",
        "preserve_genre",
    }
    assert set(payload["integrity_policy"]) == {
        "allow_damage",
        "allow_partial_loss",
        "partial_loss_min_marks_remaining",
        "tombstone_on_destroy",
    }
    assert isinstance(payload["integrity_policy"], dict)
    assert isinstance(DurableIntegrityPolicy(), DurableIntegrityPolicy)
