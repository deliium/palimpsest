"""Determinism and forbid-list hardening for inter-society relations."""

from __future__ import annotations

import random
from dataclasses import asdict
from typing import Any, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.inter_society_relations_contract import (
    CULTURAL_SIMILARITY_ALLOWED_VALUE_KEYS,
    INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS,
    InterSocietyRelationsError,
    assert_no_forbidden_fields,
    derive_inter_society_pair_id,
    validate_cultural_similarity_keys,
)
from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
    harvest_inter_society_relations,
)
from analysis.inter_society_relations_evidence import InterSocietyEvidenceInputs
from analysis.inter_society_relations_timeseries import (
    build_pair_window_series,
    compare_inter_society_pairs,
)
from analysis.macro_society_contract import MacroSocietyLane, derive_macro_society_id
from analysis.specifications import all_metric_specifications
from experiments.inter_society_relations_completed_run import (
    compose_inter_society_relations_snapshot,
)
from simulation.inter_society_relations_codec import (
    inter_society_relations_snapshot_digest,
)

pytestmark = pytest.mark.unit

LANES = (MacroSocietyLane.INTERACTION.value,)


def _msoc(label: str, *, tick: int = 0) -> str:
    return derive_macro_society_id(
        creation_tick=tick,
        founding_member_ids=tuple(f"{label}-p{index}" for index in range(1, 5)),
        lane_signature=LANES,
    )


def _harvest(
    *,
    left_label: str = "alpha",
    right_label: str = "beta",
    window_tick: int = 32,
    exchange: int = 2,
    left_tick: int = 0,
    right_tick: int = 1,
) -> Any:
    left = _msoc(left_label, tick=left_tick)
    right = _msoc(right_label, tick=right_tick)
    ordered = cast(tuple[str, str], tuple(sorted((left, right))))
    candidates = [
        InterSocietyMacroCandidate(
            society_id=left,
            member_ids=tuple(f"{left_label}-p{index}" for index in range(1, 5)),
            window_tick=window_tick,
        ),
        InterSocietyMacroCandidate(
            society_id=right,
            member_ids=tuple(f"{right_label}-p{index}" for index in range(1, 5)),
            window_tick=window_tick,
        ),
    ]
    evidence = {ordered: InterSocietyEvidenceInputs(exchange_event_count=exchange)}
    return harvest_inter_society_relations(candidates, evidence_by_pair=evidence)


def _fingerprint(analysis: Any) -> tuple[object, ...]:
    return (
        analysis.pair_count,
        tuple(
            (
                pair.pair_id,
                pair.society_a,
                pair.society_b,
                pair.window_tick,
                tuple(
                    (
                        panel.domain.value,
                        panel.event_count,
                        panel.availability.value,
                        tuple(sorted(panel.values.items())),
                    )
                    for panel in pair.panels
                ),
            )
            for pair in analysis.pairs
        ),
    )


@given(seed=st.integers(min_value=0, max_value=10_000))
@settings(max_examples=25, deadline=None)
def test_candidate_order_permutation_never_changes_pair_ids(seed: int) -> None:
    left = _msoc("alpha")
    right = _msoc("beta", tick=1)
    ordered = cast(tuple[str, str], tuple(sorted((left, right))))
    candidates = [
        InterSocietyMacroCandidate(
            society_id=left,
            member_ids=("alpha-p1", "alpha-p2", "alpha-p3", "alpha-p4"),
            window_tick=32,
        ),
        InterSocietyMacroCandidate(
            society_id=right,
            member_ids=("beta-p1", "beta-p2", "beta-p3", "beta-p4"),
            window_tick=32,
        ),
    ]
    evidence = {ordered: InterSocietyEvidenceInputs(exchange_event_count=3)}
    baseline = harvest_inter_society_relations(candidates, evidence_by_pair=evidence)
    rng = random.Random(seed)
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    permuted = harvest_inter_society_relations(shuffled, evidence_by_pair=evidence)
    assert _fingerprint(permuted) == _fingerprint(baseline)


def test_repeated_harvest_and_series_are_byte_identical() -> None:
    first = _harvest()
    second = _harvest()
    assert _fingerprint(first) == _fingerprint(second)
    windows = [
        _harvest(window_tick=0, exchange=1).pairs[0],
        _harvest(window_tick=32, exchange=2).pairs[0],
        _harvest(window_tick=64, exchange=3).pairs[0],
    ]
    series_a = build_pair_window_series(windows)
    series_b = build_pair_window_series(windows)
    assert series_a == series_b
    assert [point.window_index for point in series_a[0].points] == [0, 1, 2]


def test_isr_id_stable_under_society_argument_swap() -> None:
    left = _msoc("alpha")
    right = _msoc("beta", tick=1)
    first = derive_inter_society_pair_id(
        window_tick=32,
        society_a=left,
        society_b=right,
        domain_signature=("exchange", "cooperation"),
    )
    second = derive_inter_society_pair_id(
        window_tick=32,
        society_a=right,
        society_b=left,
        domain_signature=("cooperation", "exchange"),
    )
    assert first == second
    assert first.startswith("isr-")


def test_forbidden_field_names_fail_closed_on_rows_and_metrics() -> None:
    for name in sorted(INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS):
        with pytest.raises(InterSocietyRelationsError) as excinfo:
            assert_no_forbidden_fields({name: 1}, path="row")
        assert (
            excinfo.value.reason_code
            == "inter_society_relations_forbidden_result_field"
        )
    for family in all_metric_specifications()[-4:]:
        assert INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS.isdisjoint(
            family.value_keys
        )
        for key in family.value_keys:
            assert "score" not in key
            assert key != "composite"


def test_cultural_similarity_keys_reject_score_aliases() -> None:
    validate_cultural_similarity_keys(
        {
            "overlap_count": 1,
            "union_count": 2,
            "jaccard": 0.5,
            "availability": "present",
        }
    )
    assert "score" not in CULTURAL_SIMILARITY_ALLOWED_VALUE_KEYS
    for bad in ("score", "similarity_score", "trust_score", "composite"):
        with pytest.raises(InterSocietyRelationsError) as excinfo:
            validate_cultural_similarity_keys({bad: 0})
        assert excinfo.value.reason_code in {
            "inter_society_relations_cultural_key_rejected",
            "inter_society_relations_forbidden_result_field",
        }


def test_comparison_and_snapshot_digest_forbid_composites() -> None:
    left = _harvest(window_tick=32, exchange=1).pairs[0]
    right = _harvest(
        left_label="gamma",
        right_label="delta",
        left_tick=2,
        right_tick=3,
        window_tick=32,
        exchange=4,
    ).pairs[0]
    view = compare_inter_society_pairs(left, right)
    payload = asdict(view)
    assert_no_forbidden_fields(payload, path="comparison")
    assert "score" not in str(payload)
    assert "composite" not in str(payload)

    analysis = _harvest()
    first = compose_inter_society_relations_snapshot(
        analysis, run_id="run-isr-det", comparisons=(view,)
    )
    second = compose_inter_society_relations_snapshot(
        analysis, run_id="run-isr-det", comparisons=(view,)
    )
    assert first.digest == second.digest
    assert first.digest == inter_society_relations_snapshot_digest(first)
    assert len(first.digest) == 64
    assert "score" not in first.digest
