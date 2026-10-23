"""Transmission fidelity, mutation, and generation classifications."""

from __future__ import annotations

import pytest

from analysis.cultural_evolution_evidence import (
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    TransmissionEdge,
)
from analysis.cultural_evolution_transmission import (
    compute_cultural_evolution_transmission,
)
from analysis.models import MetricAvailability

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64


def _edge(
    edge_id: str,
    *,
    status: str = "resolved",
    generation: str = "intergenerational",
    kin: bool = False,
    source_digest: str | None = _DIGEST_A,
    target_digest: str | None = _DIGEST_A,
    modality: str = "teaching",
    mutated: bool = False,
    recombined: bool = False,
    evidence: tuple[str, ...] = (),
) -> TransmissionEdge:
    resolved = status == "resolved"
    return TransmissionEdge(
        edge_id=edge_id,
        source_owner_id="teacher" if resolved else None,
        receiver_owner_id="learner",
        source_local_id=f"pk-{edge_id}" if resolved else None,
        receiver_local_id=f"pk-learn-{edge_id}",
        acquisition_boundary=1,
        modality=modality,
        attribution_status=status,
        generation_class=generation,
        kin_vertical=kin,
        source_digest=source_digest,
        target_digest=target_digest,
        mutated=mutated,
        recombined=recombined,
        evidence_ids=evidence,
    )


def _inputs(edges: tuple[TransmissionEdge, ...]) -> CulturalEvolutionInputs:
    return CulturalEvolutionInputs(
        run_id="run-transmission",
        source_revision="rev-transmission",
        window=CulturalAnalysisWindow(end_boundary=1),
        transmission_edges=edges,
    )


def _row(rows, measurement_id: str):
    matches = [row for row in rows if row.measurement_id == measurement_id]
    assert len(matches) == 1
    return matches[0]


def test_exact_copy_has_fidelity_one_and_zero_mutation() -> None:
    rows = compute_cultural_evolution_transmission(_inputs((_edge("e1"),)))
    assert _row(rows, "exact_fidelity").value == 1.0
    assert _row(rows, "mutation_rate").value == 0.0
    assert _row(rows, "horizontal_share").value == 0.0
    assert _row(rows, "forward_intergenerational_share").value == 1.0
    assert _row(rows, "unknown_generation_share").value == 0.0


def test_changed_copy_has_partial_fidelity_and_mutation() -> None:
    rows = compute_cultural_evolution_transmission(
        _inputs(
            (
                _edge("e1"),
                _edge("e2", target_digest=_DIGEST_B),
            )
        )
    )
    assert _row(rows, "exact_fidelity").value == 0.5
    assert _row(rows, "mutation_rate").value == 0.5


def test_recombination_is_excluded_from_single_source_denominator() -> None:
    rows = compute_cultural_evolution_transmission(
        _inputs(
            (
                _edge("e1"),
                _edge(
                    "e2",
                    target_digest=_DIGEST_B,
                    recombined=True,
                ),
            )
        )
    )
    assert _row(rows, "comparable_edge_count").value == 1.0
    assert _row(rows, "exact_fidelity").value == 1.0
    assert _row(rows, "mutation_rate").value == 0.0
    assert _row(rows, "recombination_count").value == 1.0
    assert _row(rows, "recombination_share").value == 0.5


def test_ambiguous_and_unknown_sources_are_excluded_with_counts() -> None:
    rows = compute_cultural_evolution_transmission(
        _inputs(
            (
                _edge("e1"),
                _edge("e2", status="ambiguous_source", generation="unknown"),
                _edge("e3", status="unknown_source", generation="unknown"),
            )
        )
    )
    assert _row(rows, "ambiguous_source_count").value == 1.0
    assert _row(rows, "unknown_source_count").value == 1.0
    assert _row(rows, "attributable_edge_count").value == 1.0
    assert _row(rows, "exact_fidelity").denominator == 1.0


def test_reverse_generation_and_vertical_kin_are_distinct() -> None:
    rows = compute_cultural_evolution_transmission(
        _inputs(
            (
                _edge("e1", generation="reverse_intergenerational"),
                _edge("e2", generation="intergenerational", kin=True),
            )
        )
    )
    assert _row(rows, "reverse_intergenerational_share").value == 0.5
    assert _row(rows, "forward_intergenerational_share").value == 0.5
    assert _row(rows, "vertical_kin_share").value == 0.5
    assert _row(rows, "vertical_kin_count").value == 1.0


def test_missing_generation_is_reported_separately() -> None:
    rows = compute_cultural_evolution_transmission(
        _inputs((_edge("e1", generation="unknown"),))
    )
    assert _row(rows, "unknown_generation_share").value == 1.0
    assert _row(rows, "horizontal_share").availability is MetricAvailability.UNKNOWN
    assert _row(rows, "horizontal_share").value is None


def test_declared_mutation_can_disagree_with_exact_evidence() -> None:
    rows = compute_cultural_evolution_transmission(
        _inputs((_edge("e1", mutated=True),))
    )
    assert _row(rows, "mutation_rate").value == 0.0
    assert _row(rows, "declared_mutation_share").value == 1.0


def test_representation_mismatch_is_not_comparable() -> None:
    rows = compute_cultural_evolution_transmission(
        _inputs((_edge("e1", source_digest=None, target_digest=None),))
    )
    assert _row(rows, "comparable_edge_count").value == 0.0
    assert _row(rows, "exact_fidelity").value is None
    assert _row(rows, "exact_fidelity").reason_code == "no_comparable_edges"
    assert _row(rows, "mutation_rate").value is None


def test_zero_opportunities_yield_nulls_not_perfect_fidelity() -> None:
    rows = compute_cultural_evolution_transmission(_inputs(()))
    assert _row(rows, "exact_fidelity").value is None
    assert _row(rows, "mutation_rate").value is None
    assert _row(rows, "attributable_edge_count").value == 0.0


def test_input_order_does_not_change_values() -> None:
    edges = (
        _edge("e1"),
        _edge("e2", target_digest=_DIGEST_B),
        _edge("e3", status="unknown_source", generation="unknown"),
    )
    forward = compute_cultural_evolution_transmission(_inputs(edges))
    reverse = compute_cultural_evolution_transmission(_inputs(tuple(reversed(edges))))
    assert forward == reverse


def test_numerators_never_exceed_denominators() -> None:
    rows = compute_cultural_evolution_transmission(
        _inputs(
            (
                _edge("e1"),
                _edge("e2", target_digest=_DIGEST_B),
                _edge("e3", status="unknown_source", generation="unknown"),
            )
        )
    )
    for row in rows:
        if row.numerator is not None and row.denominator is not None:
            assert row.numerator <= row.denominator


def test_artifact_and_independent_rediscovery_are_counted_separately() -> None:
    rows = compute_cultural_evolution_transmission(
        _inputs(
            (
                _edge("e1", modality="artifact"),
                _edge(
                    "e2",
                    status="independent_rediscovery",
                    generation="unknown",
                    modality="independent_rediscovery",
                ),
            )
        )
    )
    assert _row(rows, "artifact_acquisition_count").value == 1.0
    assert _row(rows, "independent_rediscovery_count").value == 1.0


def test_invalid_input_type_fails_closed() -> None:
    with pytest.raises(TypeError):
        compute_cultural_evolution_transmission(object())  # type: ignore[arg-type]
