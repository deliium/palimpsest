# mypy: ignore-errors
"""Wave, displacement-like, cluster, and integration-outcome detection."""

from __future__ import annotations

import dataclasses
import random
from pathlib import Path

import pytest

from analysis.migration_displacement_detection import (
    DISPLACEMENT_BASES,
    DISPLACEMENT_CLASSIFICATIONS,
    INTEGRATION_CLASSIFICATIONS,
    classify_displacement,
    classify_integration_outcomes,
    detect_migration_clusters,
    detect_migration_waves,
)
from tests.unit.migration_displacement_analysis_helpers import (
    POLICY,
    cause,
    evidence,
    loc,
    movement,
    p,
)

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src" / "analysis"


def waves(movements, causes=(), clusters=()):
    return detect_migration_waves(movements, causes, clusters, POLICY)


def pair(name_a, name_b):
    return tuple(sorted((p(name_a), p(name_b))))


def two_mover_wave(**kwargs):
    return waves(
        (
            movement("agent-1", "loc-a", "loc-b", 1, **kwargs),
            movement("agent-2", "loc-a", "loc-b", 2, **kwargs),
        )
    )


def test_one_participant_is_not_a_wave() -> None:
    assert waves((movement("agent-1", "loc-a", "loc-b", 1),)) == ()
    assert (
        waves(
            (
                movement("agent-1", "loc-a", "loc-b", 1),
                movement("agent-1", "loc-a", "loc-b", 2, end=2),
            )
        )
        == ()
    )
    # A single cause never makes a wave either.
    assert waves((), (cause("agent-1", "environmental_hazard"),)) == ()


def test_two_independent_participants_form_a_wave() -> None:
    (wave,) = two_mover_wave()
    assert wave.wave_token.startswith("mig-")
    assert wave.participant_tokens == pair("agent-1", "agent-2")
    assert wave.destination_token == loc("loc-b")
    assert wave.origin_token == loc("loc-a")
    assert (wave.start_tick, wave.end_tick) == (1, 2)
    assert wave.displacement_classification == "unknown"
    assert wave.coverage == "complete"
    (partial,) = two_mover_wave(coverage="partial")
    assert partial.coverage == "partial"


def test_same_destination_and_shared_origin_is_required() -> None:
    different_origins = waves(
        (
            movement("agent-1", "loc-a", "loc-b", 1),
            movement("agent-2", "loc-c", "loc-b", 2),
        )
    )
    assert different_origins == ()
    different_destinations = waves(
        (
            movement("agent-1", "loc-a", "loc-b", 1),
            movement("agent-2", "loc-a", "loc-c", 2),
        )
    )
    assert different_destinations == ()
    pending = waves(
        (
            movement("agent-1", "loc-a", "loc-b", 1),
            movement("agent-2", "loc-a", "loc-b", 2, status="pending"),
        )
    )
    assert pending == ()
    shared_hop = waves(
        (
            movement(
                "agent-1",
                "loc-a",
                "loc-d",
                1,
                route=(loc("loc-a"), loc("loc-x"), loc("loc-d")),
            ),
            movement(
                "agent-2",
                "loc-c",
                "loc-d",
                2,
                route=(loc("loc-c"), loc("loc-x"), loc("loc-d")),
            ),
        )
    )
    assert len(shared_hop) == 1  # a shared non-destination route token suffices


def test_window_gap_splits_waves() -> None:
    movements = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-a", "loc-b", 2),
        movement("agent-3", "loc-a", "loc-b", 30),
        movement("agent-4", "loc-a", "loc-b", 31),
        movement("agent-5", "loc-a", "loc-b", 100),
    )
    out = waves(movements)
    assert len(out) == 2
    assert [
        (w.start_tick, w.end_tick) for w in sorted(out, key=lambda w: w.start_tick)
    ] == [
        (1, 2),
        (30, 31),
    ]
    # A chain of small gaps is still split once the window is exceeded.
    chain = tuple(movement(f"agent-{i}", "loc-a", "loc-b", 1 + 4 * i) for i in range(6))
    assert len(waves(chain)) == 2


def test_opposite_ordered_routes_do_not_share_wave_identity() -> None:
    forward = (loc("loc-x"), loc("loc-y"), loc("loc-d"))
    backward = (loc("loc-y"), loc("loc-x"), loc("loc-d"))

    def build(route):
        return waves(
            (
                movement("agent-1", "loc-a", "loc-d", 1, route=route),
                movement("agent-2", "loc-a", "loc-d", 2, route=route),
            )
        )

    (first,) = build(forward)
    (second,) = build(backward)
    assert first.participant_tokens == second.participant_tokens
    assert first.wave_token != second.wave_token
    assert first.route_tokens == forward


def test_displacement_like_requires_independent_displacement_evidence() -> None:
    movements = (
        movement("agent-1", "loc-a", "loc-b", 5),
        movement("agent-2", "loc-a", "loc-b", 6),
    )

    def label(*causes):
        (wave,) = waves(movements, causes)
        return wave.displacement_classification, wave

    assert (
        label(cause("agent-1", "environmental_hazard", tick=4))[0]
        == "displacement_like"
    )
    assert (
        label(cause("agent-1", "conflict", anchor="attack-1", tick=4))[0]
        == "displacement_like"
    )
    assert (
        label(cause("agent-1", "resource_scarcity", anchor="need", tick=4))[0]
        == "displacement_like"
    )
    # Not a participant, outside the window, or not active: no displacement evidence.
    assert label(cause("agent-9", "environmental_hazard", tick=4))[0] == "unknown"
    assert label(cause("agent-1", "environmental_hazard", tick=90))[0] == "unknown"
    assert (
        label(cause("agent-1", "environmental_hazard", status="contradicted"))[0]
        == "unknown"
    )
    # Scarcity or conflict without a qualifying anchor is not displacement evidence.
    assert label(cause("agent-1", "resource_scarcity", tick=4))[0] == "unknown"
    assert label(cause("agent-1", "conflict", tick=4))[0] == "unknown"
    state, wave = label(cause("agent-1", "conflict", anchor="denied-route", tick=4))
    assert state == "displacement_like" and wave.displacement_bases == ("route_denial",)
    state, wave = label(cause("agent-1", "conflict", anchor="coercion", tick=4))
    assert wave.displacement_bases == ("coercion",)


def test_institution_exclusion_and_opportunity_are_mutually_exclusive_per_row() -> None:
    wave_row = two_mover_wave()[0]
    excluded = classify_displacement(
        wave_row,
        (cause("agent-1", "institution", anchor="rule-denial", tick=1),),
        POLICY,
    )
    assert excluded.displacement_bases == ("institutional_exclusion",)
    assert excluded.opportunity_bases == ()
    assert excluded.classification == "displacement_like"
    offered = classify_displacement(
        wave_row,
        (cause("agent-1", "institution", anchor="rule-offer", tick=1),),
        POLICY,
    )
    assert offered.displacement_bases == ()
    assert offered.opportunity_bases == ("institution",)
    assert offered.classification == "not_displacement_like"
    no_anchor = classify_displacement(
        wave_row, (cause("agent-1", "institution"),), POLICY
    )
    assert no_anchor.opportunity_bases == ("institution",)


def test_mixed_and_not_displacement_like_are_distinct() -> None:
    wave_row = two_mover_wave()[0]
    mixed = classify_displacement(
        wave_row,
        (
            cause("agent-1", "environmental_hazard"),
            cause("agent-2", "opportunity"),
        ),
        POLICY,
    )
    assert mixed.classification == "mixed"
    assert mixed.displacement_bases == ("environmental_hazard",)
    assert mixed.opportunity_bases == ("opportunity",)
    opportunity_only = classify_displacement(
        wave_row,
        (cause("agent-1", "opportunity"), cause("agent-2", "social_network")),
        POLICY,
    )
    assert opportunity_only.classification == "not_displacement_like"
    assert opportunity_only.displacement_bases == ()
    assert opportunity_only.independent_cause_count == 2
    assert opportunity_only.cause_support_counts == (
        ("opportunity", 1),
        ("social_network", 1),
    )


def test_unknown_when_no_cause_evidence() -> None:
    wave_row = two_mover_wave()[0]
    none = classify_displacement(wave_row, (), POLICY)
    assert none.classification == "unknown"
    assert none.independent_cause_count == 0
    only_unknown = classify_displacement(
        wave_row, (cause("agent-1", "unknown", source="unknown"),), POLICY
    )
    assert only_unknown.classification == "unknown"
    assert only_unknown.independent_cause_count == 0


def test_same_root_testimony_counts_once() -> None:
    wave_row = two_mover_wave()[0]
    result = classify_displacement(
        wave_row,
        (
            cause("agent-1", "environmental_hazard", lineage=("mdv-a", "mdv-b")),
            cause(
                "agent-2",
                "environmental_hazard",
                lineage=("mdv-b",),
                source="testimony",
            ),
        ),
        POLICY,
    )
    assert result.independent_cause_count == 1
    assert result.same_root_suppressed_count == 1
    independent = classify_displacement(
        wave_row,
        (
            cause("agent-1", "environmental_hazard", lineage=("mdv-a",)),
            cause("agent-2", "environmental_hazard", lineage=("mdv-b",)),
        ),
        POLICY,
    )
    assert independent.independent_cause_count == 2
    assert independent.same_root_suppressed_count == 0
    duplicate_owner = classify_displacement(
        wave_row,
        (
            cause("agent-1", "conflict", anchor="attack", tick=1, token="mdc-one"),
            cause("agent-1", "conflict", anchor="attack", tick=2, token="mdc-two"),
        ),
        POLICY,
    )
    assert duplicate_owner.independent_cause_count == 1


def test_cluster_requires_two_members_and_a_basis() -> None:
    solo = (movement("agent-1", "loc-a", "loc-b", 1),)
    assert detect_migration_clusters(solo, (), (), (), POLICY) == ()
    unrelated = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-c", "loc-d", 2),
    )
    assert detect_migration_clusters(unrelated, (), (), (), POLICY) == ()
    # A pair outside the movement participants is ignored.
    assert (
        detect_migration_clusters(solo, (pair("agent-1", "agent-9"),), (), (), POLICY)
        == ()
    )
    kin = detect_migration_clusters(
        unrelated, (pair("agent-1", "agent-2"),), (), (), POLICY
    )
    assert len(kin) == 1
    assert kin[0].basis_counts == (("kinship", 1),)
    assert kin[0].member_tokens == pair("agent-1", "agent-2")
    assert kin[0].cluster_token.startswith("mig-")
    assert not kin[0].cluster_token.startswith(("org-", "msoc-"))
    co = detect_migration_clusters(
        (
            movement("agent-1", "loc-a", "loc-b", 1),
            movement("agent-2", "loc-a", "loc-b", 20),
        ),
        (),
        (),
        (),
        POLICY,
    )
    assert co[0].basis_counts == (("co_movement", 1),)
    far = detect_migration_clusters(
        (
            movement("agent-1", "loc-a", "loc-b", 1),
            movement("agent-2", "loc-a", "loc-b", 90),
        ),
        (),
        (),
        (),
        POLICY,
    )
    assert far == ()
    mixed = detect_migration_clusters(
        unrelated,
        (pair("agent-1", "agent-2"),),
        (pair("agent-1", "agent-2"),),
        (pair("agent-1", "agent-2"),),
        POLICY,
    )
    assert mixed[0].basis_counts == (
        ("communication", 1),
        ("kinship", 1),
        ("organization", 1),
    )
    (wave_row,) = waves(
        (
            movement("agent-1", "loc-a", "loc-b", 1),
            movement("agent-2", "loc-a", "loc-b", 2),
        ),
        (),
        detect_migration_clusters(
            (
                movement("agent-1", "loc-a", "loc-b", 1),
                movement("agent-2", "loc-a", "loc-b", 2),
            ),
            (),
            (),
            (),
            POLICY,
        ),
    )
    assert len(wave_row.cluster_tokens) == 1


def test_integration_returned_onward_settled_transient_and_censored() -> None:
    movements = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-1", "loc-b", "loc-a", 5),
        movement("agent-2", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-b", "loc-c", 5),
        movement("agent-3", "loc-a", "loc-b", 1),
        movement("agent-4", "loc-a", "loc-b", 1),
        movement("agent-5", "loc-a", "loc-b", 38),
    )
    outcomes = classify_integration_outcomes(
        movements,
        (evidence("agent-3", "loc-b", "resource_access", 2, 3, 40),),
        POLICY,
        run_end=40,
    )
    by_participant = {}
    for row in outcomes:
        by_participant.setdefault(row.participant_token, []).append(row)
    first_a = [
        r for r in by_participant[p("agent-1")] if r.destination_token == loc("loc-b")
    ]
    assert first_a[0].classification == "returned"
    first_b = [
        r for r in by_participant[p("agent-2")] if r.destination_token == loc("loc-b")
    ]
    assert first_b[0].classification == "onward"
    (settled,) = by_participant[p("agent-3")]
    assert settled.classification == "settled"
    assert settled.access_evidence_count == 2
    assert settled.residence_ticks == 39 and settled.censored is False
    (transient,) = by_participant[p("agent-4")]
    assert transient.classification == "transient"
    assert transient.access_evidence_count == 0
    (late,) = by_participant[p("agent-5")]
    assert late.censored is True and late.residence_ticks == 2
    assert all(row.classification in INTEGRATION_CLASSIFICATIONS for row in outcomes)
    tokens = [row.outcome_token for row in outcomes]
    assert tokens == sorted(tokens)
    unknown = classify_integration_outcomes(
        (movement("agent-1", "loc-a", "loc-b", 1, coverage="missing"),), (), POLICY
    )
    assert unknown[0].classification == "unknown"
    assert (
        classify_integration_outcomes(
            (movement("agent-1", "loc-a", "loc-b", 1, status="pending"),), (), POLICY
        )
        == ()
    )


def test_integration_outcomes_follow_wave_participants_only() -> None:
    movements = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-a", "loc-b", 2),
        movement("agent-3", "loc-a", "loc-c", 3),
    )
    detected = waves(movements)
    outcomes = classify_integration_outcomes(movements, (), POLICY, waves=detected)
    assert {row.participant_token for row in outcomes} == set(
        pair("agent-1", "agent-2")
    )


def test_no_refugee_or_score_label_is_emitted() -> None:
    movements = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-a", "loc-b", 2),
    )
    clusters = detect_migration_clusters(
        movements, (pair("agent-1", "agent-2"),), (), (), POLICY
    )
    causes = (
        cause("agent-1", "conflict", anchor="flee-1"),
        cause("agent-2", "opportunity"),
    )
    detected = waves(movements, causes, clusters)
    outcomes = classify_integration_outcomes(movements, (), POLICY, waves=detected)
    forbidden = (
        "refugee",
        "asylum",
        "forced",
        "displaced",
        "wellbeing",
        "assimilation",
        "score",
        "composite",
    )
    strings: list[str] = []
    for row in (*detected, *clusters, *outcomes):
        strings.extend(field.name for field in dataclasses.fields(row))
        strings.extend(
            str(getattr(row, field.name)) for field in dataclasses.fields(row)
        )
    for text in strings:
        assert not any(word in text for word in forbidden), text
    for label in (*DISPLACEMENT_CLASSIFICATIONS, *DISPLACEMENT_BASES):
        assert not any(word in label for word in forbidden)
    assert detected[0].displacement_classification in DISPLACEMENT_CLASSIFICATIONS
    source = (SRC / "migration_displacement_detection.py").read_text(encoding="utf-8")
    for word in ("refugee", "asylum", "wellbeing", "assimilation"):
        assert word not in source


def test_outputs_are_deterministic_and_validate_policy() -> None:
    movements = [movement(f"agent-{i}", "loc-a", "loc-b", 1 + i % 3) for i in range(6)]
    expected = waves(tuple(movements))
    shuffled = list(movements)
    random.Random(7).shuffle(shuffled)
    assert waves(tuple(shuffled)) == expected
    with pytest.raises(ValueError, match="migration_detection: invalid_policy"):
        detect_migration_waves(movements, (), (), object())
    with pytest.raises(ValueError, match="migration_detection: invalid_policy"):
        classify_integration_outcomes(movements, (), None)
