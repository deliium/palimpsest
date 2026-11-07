# mypy: ignore-errors
"""Overlap, dispute, recognition, and control-pattern detection."""

from __future__ import annotations

import dataclasses

from analysis.borders_contract import (
    BorderAgreementRow,
    BorderClaimRow,
    BorderDisputeRow,
    BorderPatternRow,
    BorderRecognitionRow,
)
from analysis.borders_detection import (
    control_summary,
    detect_border_disputes,
    detect_border_overlaps,
    detect_boundary_recognitions,
    detect_control_patterns,
)
from analysis.borders_events import BorderPhysicalRow
from analysis.borders_policy import default_borders_analysis_policy

POLICY = default_borders_analysis_policy()


def _claim(owner: str, domain: str, locations: tuple[str, ...]) -> BorderClaimRow:
    return BorderClaimRow(owner, domain, locations, (), "claimed", 0.8)


def _agreement(domain: str, provisions: tuple[str, ...]) -> BorderAgreementRow:
    return BorderAgreementRow(
        "bda-1", domain, "bcp-1", provisions, "apparent_acceptance", "recognized"
    )


def test_overlap_requires_different_owners() -> None:
    claims = (
        _claim("owner-1", "domain-1", ("a", "b")),
        _claim("owner-1", "domain-2", ("a", "b")),
        _claim("owner-2", "domain-3", ("b", "c")),
    )
    overlaps = detect_border_overlaps(claims, policy=POLICY)
    assert [(item.left_domain_token, item.right_domain_token) for item in overlaps] == [
        ("domain-1", "domain-3"),
        ("domain-2", "domain-3"),
    ]


def test_overlap_retains_all_shared_locations() -> None:
    overlaps = detect_border_overlaps(
        (
            _claim("owner-1", "domain-1", ("a", "b", "c")),
            _claim("owner-2", "domain-2", ("b", "c", "d")),
        ),
        policy=POLICY,
    )
    assert overlaps[0].overlap_location_tokens == ("b", "c")
    assert overlaps[0].overlap_count == 2


def test_dispute_is_retained_without_winner() -> None:
    overlaps = detect_border_overlaps(
        (
            _claim("owner-1", "domain-1", ("a",)),
            _claim("owner-2", "domain-2", ("a",)),
        ),
        policy=POLICY,
    )
    resolved = detect_border_disputes(overlaps, (), policy=POLICY)
    assert resolved[0].dispute_status == "disputed"
    names = {item.name for item in dataclasses.fields(resolved[0])}
    assert names.isdisjoint({"winner", "loser", "score", "composite"})


def test_agreement_overlap_is_acknowledged_but_not_reconciled() -> None:
    overlaps = detect_border_overlaps(
        (
            _claim("owner-1", "domain-1", ("a",)),
            _claim("owner-2", "domain-2", ("a",)),
        ),
        policy=POLICY,
    )
    resolved = detect_border_disputes(
        overlaps,
        (_agreement("domain-1", ("territorial_acknowledgement",)),),
        policy=POLICY,
    )
    assert resolved[0].dispute_status == "acknowledged"
    assert resolved[0].overlap_location_tokens == ("a",)


def test_recognition_precedence() -> None:
    edge = ("a", "b")
    states = detect_boundary_recognitions(
        (
            BorderRecognitionRow(
                "bdr-1", "domain-1", (edge,), "own_claim", "recognized"
            ),
        ),
        (),
    )
    assert states[0].status == "recognized"
    states = detect_boundary_recognitions(
        (
            BorderRecognitionRow(
                "bdr-1", "domain-1", (edge,), "own_claim", "recognized"
            ),
        ),
        (BorderDisputeRow("bdd-1", "domain-1", "bcp-1", ("a",), "active"),),
    )
    assert states[0].status == "disputed"
    assert detect_boundary_recognitions((), ()) == ()


def test_control_pattern_precedence_and_unknown() -> None:
    physical = (BorderPhysicalRow("a", 0, 5, 2, 3, 0, 0, 2, "shared_use"),)
    claims = (_claim("owner-1", "domain-1", ("a",)),)
    patterns = detect_control_patterns(physical, claims, (), (), policy=POLICY)
    assert patterns[0].pattern == "claim_aligned"

    disputed = detect_control_patterns(
        physical,
        claims,
        (_agreement("domain-1", ("territorial_acknowledgement",)),),
        (BorderDisputeRow("bdd-1", "domain-1", "bcp-1", ("a",), "active"),),
        policy=POLICY,
    )
    assert disputed[0].pattern == "contested"

    hostile = detect_control_patterns(
        (BorderPhysicalRow("a", 0, 5, 2, 3, 1, 0, 2, "contested_use"),),
        claims,
        (),
        (),
        policy=POLICY,
    )
    assert hostile[0].pattern == "contested"

    unclaimed = detect_control_patterns(physical, (), (), (), policy=POLICY)
    assert unclaimed[0].pattern == "physical_unclaimed"

    assert detect_control_patterns((), (), (), (), policy=POLICY) == ()


def test_no_composite_or_winner_field() -> None:
    for type_ in (BorderPatternRow, BorderClaimRow, BorderRecognitionRow):
        names = {item.name for item in dataclasses.fields(type_)}
        assert names.isdisjoint(
            {"winner", "loser", "score", "composite", "sovereignty"}
        )


def test_detection_is_deterministic_and_sorted() -> None:
    claims = (
        _claim("owner-2", "domain-b", ("a",)),
        _claim("owner-1", "domain-a", ("a",)),
    )
    first = detect_border_overlaps(claims, policy=POLICY)
    second = detect_border_overlaps(tuple(reversed(claims)), policy=POLICY)
    assert first == second
    assert first == tuple(
        sorted(
            first, key=lambda item: (item.left_domain_token, item.right_domain_token)
        )
    )
    patterns = detect_control_patterns(
        (BorderPhysicalRow("a", 0, 5, 1, 1, 0, 0, 1, "transient"),),
        claims,
        (),
        (),
        policy=POLICY,
    )
    assert control_summary(patterns).pattern_counts


def test_policy_comes_from_analysis_not_runner() -> None:
    assert POLICY.physical_window_ticks == 6
    assert POLICY.max_pairs_per_run == 4096
