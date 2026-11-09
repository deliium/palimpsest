# mypy: ignore-errors
"""ISR snapshot mapping and codec round-trip."""

from __future__ import annotations

import pytest

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
    harvest_inter_society_relations,
)
from analysis.inter_society_relations_evidence import InterSocietyEvidenceInputs
from analysis.inter_society_relations_timeseries import compare_inter_society_pairs
from analysis.macro_society_contract import MacroSocietyLane, derive_macro_society_id
from experiments.inter_society_relations_completed_run import (
    compose_inter_society_relations_snapshot,
)
from simulation.inter_society_relations_codec import (
    decode_inter_society_relations_snapshot,
    encode_inter_society_relations_snapshot,
    finalize_inter_society_relations_snapshot,
)
from simulation.inter_society_relations_models import (
    INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION,
    empty_inter_society_relations_snapshot,
)

pytestmark = pytest.mark.unit


def _msoc(label: str, *, tick: int = 0) -> str:
    members = tuple(f"{label}-p{index}" for index in range(1, 5))
    return derive_macro_society_id(
        creation_tick=tick,
        founding_member_ids=members,
        lane_signature=(MacroSocietyLane.INTERACTION.value,),
    )


def _analysis(*, with_exchange: bool = True):
    left = _msoc("alpha")
    right = _msoc("beta", tick=1)
    ordered = tuple(sorted((left, right)))
    evidence = {
        ordered: InterSocietyEvidenceInputs(
            exchange_event_count=2 if with_exchange else None
        ),
    }
    return harvest_inter_society_relations(
        [
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
            InterSocietyMacroCandidate(
                society_id=left,
                member_ids=("alpha-p1", "alpha-p2", "alpha-p3", "alpha-p4"),
                window_tick=64,
            ),
            InterSocietyMacroCandidate(
                society_id=right,
                member_ids=("beta-p1", "beta-p2", "beta-p3", "beta-p4"),
                window_tick=64,
            ),
        ],
        evidence_by_pair=evidence,
    )


def test_empty_analysis_maps_to_empty_snapshot() -> None:
    analysis = harvest_inter_society_relations(())
    snapshot = compose_inter_society_relations_snapshot(
        analysis, run_id="run-isr-empty"
    )
    assert snapshot.summary.pair_count == 0
    assert snapshot.pairs == ()
    assert snapshot.series_points == ()
    assert snapshot.publication_id.startswith("isr-pub-")
    assert len(snapshot.digest) == 64


def test_multi_window_analysis_maps_series_and_optional_comparison() -> None:
    analysis = _analysis()
    assert analysis.pair_count >= 1
    comparison = compare_inter_society_pairs(analysis.pairs[0], analysis.pairs[-1])
    snapshot = compose_inter_society_relations_snapshot(
        analysis, run_id="run-isr-map", comparisons=(comparison,)
    )
    assert snapshot.schema_version == INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION
    assert snapshot.summary.pair_count == analysis.pair_count
    assert snapshot.summary.series_point_count >= 1
    assert snapshot.summary.comparison_count == 1
    assert snapshot.summary.window_count >= 1
    for pair in snapshot.pairs:
        assert {panel.domain for panel in pair.panels} == {
            "cooperation",
            "hostility",
            "exchange",
            "migration",
            "trust_proxy",
            "agreement",
            "conflict",
            "cultural_similarity",
        }
        assert "score" not in {panel.domain for panel in pair.panels}


def test_codec_round_trip_preserves_digest() -> None:
    snapshot = compose_inter_society_relations_snapshot(
        _analysis(), run_id="run-isr-codec"
    )
    encoded = encode_inter_society_relations_snapshot(snapshot)
    decoded = decode_inter_society_relations_snapshot(encoded)
    assert decoded.digest == snapshot.digest
    assert decoded.publication_id == snapshot.publication_id
    assert decoded.summary.pair_count == snapshot.summary.pair_count
    assert len(decoded.pairs) == len(snapshot.pairs)


def test_finalize_empty_snapshot() -> None:
    empty = empty_inter_society_relations_snapshot(run_id="run-isr-finalize")
    finalized = finalize_inter_society_relations_snapshot(empty)
    assert finalized.summary.pair_count == 0
    assert finalized.publication_id.startswith("isr-pub-")
