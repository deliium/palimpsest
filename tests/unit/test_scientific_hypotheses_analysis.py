# mypy: ignore-errors
"""Bounded scientific-hypothesis analysis composition."""

from __future__ import annotations

import dataclasses

import pytest

from analysis.scientific_hypotheses_analysis import (
    empty_scientific_hypotheses_analysis,
    harvest_scientific_hypotheses_analysis,
    scientific_hypotheses_analysis_digest,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesesError,
    ScientificHypothesisAvailability,
    ScientificHypothesisConditionSlot,
    ScientificHypothesisCoverage,
    ScientificHypothesisLayer,
    ScientificHypothesisRevisionReason,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
    mint_owner_token,
)
from analysis.scientific_hypotheses_policy import policy_with
from analysis.scientific_hypotheses_rows import (
    HypothesisConditionFact,
    HypothesisFact,
    HypothesisRevisionFact,
    HypothesisTrialFact,
)
from world.effects import ActionCause
from world.events import ExperimentResolved, OccurrenceContext, WorldEvent
from world.experimentation import (
    DiscoveryMode,
    ExperimentOutcomeClass,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)

pytestmark = pytest.mark.unit

WORLD = WorldId("world-scientific-hypotheses-analysis")
OWNER = mint_owner_token("agent-1")


def _event(
    *,
    tick: int,
    sequence: int,
    event_id: str,
    outcome: str = "success",
    delta: str = "none",
    product_id: str = "",
) -> WorldEvent:
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-scientific",
        world_id=WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{event_id}"),
        resulting_revision=WorldRevision(tick),
        schema_version=27,
        details=ExperimentResolved(
            operator="combine",
            operand_a_id=EntityId("item-material"),
            operand_b_id=EntityId("resource-material"),
            process_token="none",
            outcome_class=outcome,
            delta=delta,
            discovery_mode="deliberate",
            product_id=product_id,
            health_delta=0.0,
        ),
        actor_id=EntityId("body-1"),
        target_id=EntityId("item-material"),
        cause=ActionCause(RequestId(f"req-{event_id}"), EntityId("body-1")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _fact(
    *,
    created_tick: int = 0,
    hypothesis_token: str = "schyp-1",
    predicted: str | None = "success",
    support_events: tuple[str, ...] = (),
    counter_events: tuple[str, ...] = (),
    trials: tuple[HypothesisTrialFact, ...] = (),
    conditions: tuple[HypothesisConditionFact, ...] = (),
    revisions: tuple[HypothesisRevisionFact, ...] = (),
    source_kind: ScientificHypothesisSourceKind = (
        ScientificHypothesisSourceKind.SELF_FORMULATED
    ),
) -> HypothesisFact:
    status = ScientificHypothesisStatus.PROVISIONAL
    if len(support_events) >= 2 and len(counter_events) == 0:
        status = ScientificHypothesisStatus.SUPPORTED
    elif len(counter_events) >= 2 and len(counter_events) > len(support_events):
        status = ScientificHypothesisStatus.CONTRADICTED
    return HypothesisFact(
        owner_token=OWNER,
        hypothesis_token=hypothesis_token,
        claim_token=f"claim-{hypothesis_token}",
        causal_hypothesis_token=NONE_TOKEN,
        status=status,
        predicted_outcome=predicted if predicted is not None else NONE_TOKEN,
        confidence_milli=500,
        created_tick=created_tick,
        active=True,
        source_kind=source_kind,
        source_token="self",
        conditions=conditions,
        revisions=revisions,
        trials=trials,
    )


def _revision(
    *,
    index: int = 0,
    tick: int = 0,
    reason: ScientificHypothesisRevisionReason = (
        ScientificHypothesisRevisionReason.FORMULATED
    ),
) -> HypothesisRevisionFact:
    return HypothesisRevisionFact(
        revision_index=index,
        tick=tick,
        reason=reason,
        claim_token="claim-schyp-1",
        predicted_outcome="success",
        condition_pairs=(),
        confidence_milli=500,
        evidence_ref="",
    )


def _trial(
    *,
    tick: int = 1,
    event_token: str = "evt:e1",
    matched: bool = True,
    predicted: str = "success",
    outcome: ExperimentOutcomeClass = ExperimentOutcomeClass.SUCCESS,
) -> HypothesisTrialFact:
    return HypothesisTrialFact(
        tick=tick,
        event_token=event_token,
        outcome_class=outcome,
        discovery_mode=DiscoveryMode.DELIBERATE,
        predicted_outcome=predicted,
        matched=matched,
    )


def test_empty_analysis_is_explicitly_missing() -> None:
    analysis = empty_scientific_hypotheses_analysis()
    assert analysis.hypothesis_rows == ()
    assert analysis.coverage_rows[0].coverage is ScientificHypothesisCoverage.MISSING
    assert analysis.coverage_rows[0].availability is (
        ScientificHypothesisAvailability.UNAVAILABLE
    )
    assert analysis.source_layers == (
        ScientificHypothesisLayer.ANALYTICAL_SUMMARY,
    )


def test_no_facts_and_no_events_is_missing() -> None:
    analysis = harvest_scientific_hypotheses_analysis(events=(), facts=())
    assert analysis.coverage_rows[0].coverage is ScientificHypothesisCoverage.MISSING
    assert analysis.row_count == 1


def test_one_hypothesis_emits_owner_revision_source_and_coverage_rows() -> None:
    analysis = harvest_scientific_hypotheses_analysis(
        events=(),
        facts=(_fact(conditions=(
            HypothesisConditionFact(
                slot=ScientificHypothesisConditionSlot.LOCATION,
                value_token="loc-1",
            ),
        ), revisions=(_revision(),)),),
    )
    assert len(analysis.hypothesis_rows) == 1
    assert len(analysis.revision_rows) == 1
    assert len(analysis.source_rows) == 1
    assert analysis.hypothesis_rows[0].condition_count == 1
    assert analysis.hypothesis_rows[0].owner_token == OWNER
    assert analysis.coverage_rows[0].hypothesis_count == 1


def test_two_windows_are_separate() -> None:
    analysis = harvest_scientific_hypotheses_analysis(
        events=(_event(tick=0, sequence=0, event_id="e1"),),
        facts=(_fact(created_tick=0), _fact(created_tick=40, hypothesis_token="schyp-2")),  # noqa: E501
    )
    windows = {row.window_index for row in analysis.hypothesis_rows}
    assert windows == {0, 1}
    assert {row.window_tick for row in analysis.hypothesis_rows} == {0, 32}


def test_objective_rule_payload_never_copies_delta_product_or_health() -> None:
    analysis = harvest_scientific_hypotheses_analysis(
        events=(
            _event(
                tick=0,
                sequence=0,
                event_id="e1",
                delta="emit_catalog_product",
                product_id="secret-product",
            ),
        ),
        facts=(_fact(),),
    )
    dumped = str(dataclasses.asdict(analysis))
    assert "secret-product" not in dumped
    assert "emit_catalog_product" not in dumped
    assert "health_delta" not in dumped
    assert "harm_band" not in dumped
    row = analysis.objective_rows[0]
    assert not hasattr(row, "product_id")
    assert not hasattr(row, "delta")


def test_trial_linking_and_unlinked_notice() -> None:
    analysis = harvest_scientific_hypotheses_analysis(
        events=(_event(tick=1, sequence=0, event_id="e1"),),
        facts=(
            _fact(
                trials=(
                    _trial(event_token="evt:e1", matched=True),
                    _trial(event_token="evt:missing", matched=False),
                )
            ),
        ),
    )
    assert analysis.trial_rows[0].trial_count == 2
    assert analysis.trial_rows[0].matched_count == 1
    assert analysis.trial_rows[0].mismatched_count == 1
    assert "unlinked_trials" in analysis.notices


def test_analytical_rows_do_not_expose_owner_tokens() -> None:
    analysis = harvest_scientific_hypotheses_analysis(
        events=(_event(tick=1, sequence=0, event_id="e1"),),
        facts=(_fact(trials=(_trial(),)),),
    )
    for row in (
        *analysis.trial_rows,
        *analysis.source_rows,
        *analysis.outcome_rows,
        *analysis.coverage_rows,
    ):
        assert not hasattr(row, "owner_token")


def test_cap_truncation_is_partial_with_one_notice() -> None:
    analysis = harvest_scientific_hypotheses_analysis(
        events=(),
        facts=(
            _fact(hypothesis_token="schyp-1"),
            _fact(hypothesis_token="schyp-2"),
        ),
        policy=policy_with(max_hypotheses=1),
    )
    assert len(analysis.hypothesis_rows) == 1
    assert "hypotheses" in analysis.notices
    assert analysis.hypothesis_rows[0].coverage is (
        ScientificHypothesisCoverage.PARTIAL
    )


def test_fewer_than_min_samples_is_insufficient() -> None:
    analysis = harvest_scientific_hypotheses_analysis(
        events=(_event(tick=1, sequence=0, event_id="e1"),),
        facts=(_fact(trials=(_trial(),)),),
    )
    assert analysis.coverage_rows[0].availability is (
        ScientificHypothesisAvailability.INSUFFICIENT_SAMPLES
    )
    assert analysis.outcome_rows[0].availability is (
        ScientificHypothesisAvailability.INSUFFICIENT_SAMPLES
    )


def test_unexpected_is_counted_as_mismatch() -> None:
    trial = _trial(
        matched=False,
        predicted="unexpected",
        outcome=ExperimentOutcomeClass.UNEXPECTED,
    )
    analysis = harvest_scientific_hypotheses_analysis(
        events=(_event(tick=1, sequence=0, event_id="e1", outcome="unexpected"),),
        facts=(_fact(predicted="unexpected", trials=(trial,)),),
    )
    row = analysis.outcome_rows[0]
    assert row.outcome_class is ExperimentOutcomeClass.UNEXPECTED
    assert row.mismatched_count == 1
    assert row.matched_count == 0


def test_communicated_source_counts_as_adopted() -> None:
    analysis = harvest_scientific_hypotheses_analysis(
        events=(),
        facts=(
            _fact(source_kind=ScientificHypothesisSourceKind.COMMUNICATED),
        ),
    )
    row = analysis.source_rows[0]
    assert row.source_kind is ScientificHypothesisSourceKind.COMMUNICATED
    assert row.adopted_count == 1


def test_digest_is_stable_across_input_order() -> None:
    facts = (_fact(hypothesis_token="schyp-1"), _fact(hypothesis_token="schyp-2"))
    first = harvest_scientific_hypotheses_analysis(events=(), facts=facts)
    second = harvest_scientific_hypotheses_analysis(
        events=(), facts=tuple(reversed(facts))
    )
    assert scientific_hypotheses_analysis_digest(first) == (
        scientific_hypotheses_analysis_digest(second)
    )


def test_rejects_invalid_input_types() -> None:
    with pytest.raises(ScientificHypothesesError):
        harvest_scientific_hypotheses_analysis(events="bad", facts=())  # type: ignore[arg-type]
    with pytest.raises(ScientificHypothesesError):
        harvest_scientific_hypotheses_analysis(events=(), facts="bad")  # type: ignore[arg-type]
