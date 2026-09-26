"""Experiment I, optional hypothesis selection, and post-run comparison."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.cognition.world_model import (
    CausalAtom,
    CausalEpisode,
    CausalEpisodeRole,
    CausalHypothesis,
    CausalOutcome,
    CausalProvenanceKind,
    CausalSlot,
    CausalWorldModel,
    WorldModelSelectionOutput,
    build_world_model_audit,
    default_world_model_policy,
    empty_world_model,
    match_hypothesis,
    select_world_model_hypotheses,
    update_world_model,
)
from agents.models import AgentId
from analysis.causal_world_model_metrics import compute_causal_world_model_metrics
from experiments.catalog import experiment_i_causal
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_serialization import build_runner_result_document
from tests.fakes.llm import FakeLLMProvider, ScriptedSuccess
from tests.unit.test_simulation_runner_e2e import _config
from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS
from world.events import (
    EVENT_SCHEMA_REPLAY_V5,
    ActionCause,
    OccurrenceContext,
    Searched,
    WorldEvent,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import default_physical_rules

_OWNER = AgentId("agent-1")


def _atom(slot: CausalSlot, value: str) -> CausalAtom:
    return CausalAtom(slot=slot, value=value)


def _hypothesis(
    *,
    atoms: tuple[CausalAtom, ...],
    outcome: CausalOutcome,
    support: float,
) -> CausalHypothesis:
    return CausalHypothesis(
        owner_id=_OWNER,
        atoms=atoms,
        outcome=outcome,
        support=support,
        counter=0.0,
        evidence_ids=("evidence-1",),
        counter_evidence_ids=(),
        provenance_kind=CausalProvenanceKind.OBSERVATION,
    )


def _search_event(*, event_id: str, success: bool, sequence: int) -> WorldEvent:
    request = RequestId(f"r-{event_id}")
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-metric",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=sequence,
        request_id=request,
        resulting_revision=WorldRevision(1),
        schema_version=EVENT_SCHEMA_REPLAY_V5,
        details=Searched(
            success=success,
            created_item_id=EntityId(f"item-{event_id}") if success else None,
            extracted_quantity=1.0 if success else None,
            resulting_resource_quantity=1.0 if success else None,
        ),
        actor_id=EntityId("body-1"),
        cause=ActionCause(request, EntityId("body-1")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-forest")),
    )


def test_experiment_i_stays_off_the_v1_gate(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    definition = experiment_i_causal(_config())
    ids = {experiment_id for experiment_id, _builder in _CATALOG_BUILDERS}
    assert definition.experiment_id == "experiment-i-causal"
    assert "experiment-i-causal" not in ids
    disabled, enabled = definition.conditions
    assert disabled.condition_id == "i-disabled"
    assert enabled.condition_id == "i-enabled"
    assert disabled.runner_config.schema_version == enabled.runner_config.schema_version
    assert disabled.runner_config.capability_flags.predictive_world_model is False
    assert enabled.runner_config.capability_flags.predictive_world_model is True
    assert disabled.runner_config.seed == enabled.runner_config.seed
    assert (
        disabled.runner_config.stochastic_identity
        == enabled.runner_config.stochastic_identity
    )
    assert disabled.runner_config.scenario == enabled.runner_config.scenario
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "experiment_i_built" in text


@pytest.mark.asyncio
async def test_disabled_arm_matches_flags_off_objective_hash() -> None:
    disabled = next(
        item.runner_config
        for item in experiment_i_causal(_config()).conditions
        if item.condition_id == "i-disabled"
    )
    async with await SimulationRunner.from_config(
        disabled, run_id=RunId("run-i-off")
    ) as runner:
        result = await runner.run()
        assert runner.export_world_model_audits() == ()
    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-i-off")
    ) as runner:
        base = await runner.run()
    left = build_runner_result_document(result=result, config=disabled)
    right = build_runner_result_document(result=base, config=_config())
    assert left.exact_trajectory_hash == right.exact_trajectory_hash
    assert result.objective_state_hash == base.objective_state_hash
    assert result.world_model_audits == ()


def test_false_search_belief_keeps_confidence_and_reports_error() -> None:
    hypothesis = _hypothesis(
        atoms=(
            _atom(CausalSlot.LOCATION, "loc-forest"),
            _atom(CausalSlot.ACTION, "search"),
        ),
        outcome=CausalOutcome.SEARCH_FAILURE,
        support=4.0,
    )
    model = CausalWorldModel(
        owner_id=_OWNER,
        hypotheses=(hypothesis,),
        last_tick=2,
    )
    confidence = hypothesis.confidence
    audit = build_world_model_audit(model)
    assert not hasattr(audit.snapshots[0], "evidence_ids")
    events = (
        *(_search_event(event_id=f"evt-ok-{index}", success=True, sequence=index)
          for index in range(9)),
        _search_event(event_id="evt-miss", success=False, sequence=9),
    )
    report = compute_causal_world_model_metrics(
        (audit,),
        events,
        physical_rules=default_physical_rules(),
        run_id="run-metric",
        input_revision="rev-1",
    )
    compared = report.comparisons[0]
    assert compared.empirical_status == "matched"
    assert compared.empirical_rate == 0.1
    assert compared.absolute_error is not None
    assert compared.absolute_error > 0.5
    assert hypothesis.confidence == confidence
    assert "update_world_model" not in Path(
        "src/analysis/causal_world_model_metrics.py"
    ).read_text(encoding="utf-8")


def test_weather_atom_stays_unmatched() -> None:
    hypothesis = _hypothesis(
        atoms=(
            _atom(CausalSlot.WEATHER, "rain"),
            _atom(CausalSlot.ACTION, "search"),
        ),
        outcome=CausalOutcome.SEARCH_FAILURE,
        support=4.0,
    )
    audit = build_world_model_audit(
        CausalWorldModel(owner_id=_OWNER, hypotheses=(hypothesis,), last_tick=1)
    )
    report = compute_causal_world_model_metrics(
        (audit,),
        (_search_event(event_id="evt-1", success=True, sequence=0),),
        physical_rules=default_physical_rules(),
        run_id="run-metric",
        input_revision="rev-1",
    )
    assert report.comparisons[0].empirical_status == "unmatched"
    assert report.comparisons[0].empirical_rate is None


def test_location_parent_matches_a_daytime_situation() -> None:
    parent = _hypothesis(
        atoms=(_atom(CausalSlot.LOCATION, "loc-forest"),),
        outcome=CausalOutcome.DANGER,
        support=4.0,
    )
    model = CausalWorldModel(owner_id=_OWNER, hypotheses=(parent,), last_tick=1)
    match = match_hypothesis(
        model,
        outcome=CausalOutcome.DANGER,
        atoms=(
            _atom(CausalSlot.LOCATION, "loc-forest"),
            _atom(CausalSlot.DAY_PHASE, "day"),
        ),
    )
    assert match is parent


def test_help_survives_one_mild_counter() -> None:
    support = CausalEpisode(
        owner_id=_OWNER,
        tick=1,
        outcome=CausalOutcome.HELP,
        atoms=(
            _atom(CausalSlot.COUNTERPART, "agent-2"),
            _atom(CausalSlot.ACTION, "ask"),
            _atom(CausalSlot.CONCEPT, "food"),
        ),
        evidence_id="mem-1",
        provenance_kind=CausalProvenanceKind.OBSERVATION,
    )
    model = update_world_model(
        empty_world_model(_OWNER),
        (support,),
        default_world_model_policy(),
        tick=1,
    )
    before = next(
        item for item in model.hypotheses if item.outcome is CausalOutcome.HELP
    )
    counter = CausalEpisode(
        owner_id=_OWNER,
        tick=2,
        outcome=CausalOutcome.HELP,
        atoms=before.atoms,
        evidence_id="mem-2",
        provenance_kind=CausalProvenanceKind.OBSERVATION,
        role=CausalEpisodeRole.COUNTER,
    )
    updated = update_world_model(
        model, (counter,), default_world_model_policy(), tick=2
    )
    after = next(
        item for item in updated.hypotheses if item.outcome is CausalOutcome.HELP
    )
    assert after.counter == 1.0
    assert after.confidence < before.confidence


def test_update_debug_names_outcome_and_reason(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.world_model")
    episode = CausalEpisode(
        owner_id=_OWNER,
        tick=1,
        outcome=CausalOutcome.DANGER,
        atoms=(_atom(CausalSlot.LOCATION, "loc-forest"),),
        evidence_id="mem-1",
        provenance_kind=CausalProvenanceKind.OBSERVATION,
    )
    update_world_model(
        empty_world_model(_OWNER),
        (episode,),
        default_world_model_policy(),
        tick=1,
    )
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "outcome=danger" in messages
    assert "reason_code=support" in messages
    assert "search_base_probability" not in messages


@pytest.mark.asyncio
async def test_provider_false_never_calls_provider() -> None:
    model = CausalWorldModel(
        owner_id=_OWNER,
        hypotheses=(
            _hypothesis(
                atoms=(_atom(CausalSlot.LOCATION, "loc-forest"),),
                outcome=CausalOutcome.DANGER,
                support=4.0,
            ),
        ),
        last_tick=1,
    )

    class Boom:
        async def generate(self, request: object) -> object:
            raise AssertionError(request)

    selected = await select_world_model_hypotheses(
        model,
        default_world_model_policy(allow_provider=False),
        provider=Boom(),
        tick=1,
    )
    assert selected is model
    assert selected.selection_fallback_used is False


@pytest.mark.asyncio
async def test_provider_subset_is_preferred_when_it_matches() -> None:
    broad = _hypothesis(
        atoms=(_atom(CausalSlot.LOCATION, "loc-forest"),),
        outcome=CausalOutcome.DANGER,
        support=4.0,
    )
    specific = _hypothesis(
        atoms=(
            _atom(CausalSlot.LOCATION, "loc-forest"),
            _atom(CausalSlot.DAY_PHASE, "night"),
        ),
        outcome=CausalOutcome.DANGER,
        support=1.0,
    )
    model = CausalWorldModel(
        owner_id=_OWNER,
        hypotheses=(broad, specific),
        last_tick=2,
    )
    provider = FakeLLMProvider()
    provider.enqueue(
        "world-model-2-agent-1",
        ScriptedSuccess(
            output=WorldModelSelectionOutput(selected_ids=(specific.hypothesis_id,))
        ),
    )
    selected = await select_world_model_hypotheses(
        model,
        default_world_model_policy(allow_provider=True),
        provider=provider,
        tick=2,
    )
    match = match_hypothesis(
        selected,
        outcome=CausalOutcome.DANGER,
        atoms=specific.atoms,
    )
    assert match is not None
    assert match.hypothesis_id == specific.hypothesis_id
    assert selected.selection_fallback_used is False


@pytest.mark.asyncio
async def test_foreign_id_and_missing_provider_keep_confidence_order(
    caplog,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.world_model")
    hypothesis = _hypothesis(
        atoms=(_atom(CausalSlot.LOCATION, "loc-forest"),),
        outcome=CausalOutcome.DANGER,
        support=4.0,
    )
    model = CausalWorldModel(
        owner_id=_OWNER, hypotheses=(hypothesis,), last_tick=2
    )
    missing = await select_world_model_hypotheses(
        model,
        default_world_model_policy(allow_provider=True),
        provider=None,
        tick=2,
    )
    assert missing.selection_fallback_used is True
    assert missing.preferred_ids == ()
    provider = FakeLLMProvider()
    provider.enqueue(
        "world-model-2-agent-1",
        ScriptedSuccess(
            output=WorldModelSelectionOutput(selected_ids=("ch-foreign",))
        ),
    )
    foreign = await select_world_model_hypotheses(
        model,
        default_world_model_policy(allow_provider=True),
        provider=provider,
        tick=2,
    )
    assert foreign.selection_fallback_used is True
    assert foreign.preferred_ids == ()
    class SchemaFailure:
        async def generate(self, request: object) -> object:
            raise ValueError("schema_rejected")

    schema = await select_world_model_hypotheses(
        model,
        default_world_model_policy(allow_provider=True),
        provider=SchemaFailure(),
        tick=2,
    )
    assert schema.selection_fallback_used is True
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "reason_code=missing_provider" in messages
    assert "reason_code=foreign_id" in messages
    assert "reason_code=schema_rejected" in messages
