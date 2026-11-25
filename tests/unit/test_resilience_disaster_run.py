# mypy: ignore-errors
"""Qualify societal-resilience capture against the V4-39 drought specimen."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.coordinator import materialize_assignments
from experiments.disaster_scenario import (
    bind_disasters_experiment_runner,
    disasters_arbiter,
    disasters_scenario,
)
from experiments.resilience_capture import run_with_resilience_capture
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import MortalityMode, RunnerStopPolicy
from tests.fakes.resilience_disaster_fixture import (
    DROUGHT_INJECT_TICK,
    drought_schedule_entry,
    drought_stock_base,
)
from world.disasters import DisasterKind, DisasterScheduleEntry
from world.events import DisasterOutcome
from world.values import Health, ResourceKind, Thirst

pytestmark = pytest.mark.unit


async def _capture_assignment(assignment) -> object:
    config = assignment.runner_config
    runner = await SimulationRunner.from_config(
        config,
        run_id=assignment.run_id,
        factories=RunnerDependencyFactories(),
    )
    runner.set_intervention_arbiter(
        disasters_arbiter(
            assignment.condition_id,
            config,
            run_id=assignment.run_id,
        )
    )
    bind_disasters_experiment_runner(runner, config)
    async with runner:
        return await run_with_resilience_capture(runner, capture=True)


def _water_quantity(frame) -> int | None:
    for stock in frame.stocks:
        if stock.stock_id == "res-target":
            return stock.quantity_tenths
    return None


@pytest.mark.asyncio
async def test_drought_eight_tick_immediate_water_change() -> None:
    base = drought_stock_base()
    entry = drought_schedule_entry()
    definition = disasters_scenario(base, treatment_entry=entry)
    assignments = materialize_assignments(definition)
    assert len(assignments) == 2
    control = await _capture_assignment(assignments[0])
    treatment = await _capture_assignment(assignments[1])
    assert control.status in {"captured", "sealed"}
    assert treatment.status in {"captured", "sealed"}
    assert control.report is not None
    assert treatment.report is not None
    assert control.report.shock_status in {"no_shock", "unknown"}
    assert control.report.episodes == ()
    assert treatment.report.shock_status == "observed"
    assert len(treatment.report.episodes) == 1
    episode = treatment.report.episodes[0]
    assert episode["shock_tick"] == DROUGHT_INJECT_TICK
    assert episode["receipts"][0]["outcome"] == "applied"
    assert episode["receipts"][0]["kind"] == DisasterKind.DROUGHT.value
    # Short horizon: no complete eight-tick baseline or follow-up.
    windows = episode["windows"]
    assert windows[0]["status"] != "complete"
    assert windows[1]["status"] != "complete"
    # Immediate water change from boundary 2 → 3 matches sealed frames.
    evidence = treatment.evidence
    assert evidence is not None
    by_boundary = {frame.boundary_tick: frame for frame in evidence.frames}
    pre = _water_quantity(by_boundary[2])
    post = _water_quantity(by_boundary[3])
    assert pre is not None and post is not None
    immediate = episode["immediate_state"]
    assert immediate["boundary_tick"] == 3
    assert immediate["pre_boundary_tick"] == 2
    resource_panel = next(
        panel
        for panel in immediate["panels"]
        if panel["dimension"] == "resource_recovery"
    )
    qty = next(
        measure
        for measure in resource_panel["measures"]
        if measure["metric"] == "quantity_tenths"
        and measure["scope"] is not None
        and "water" in measure["scope"]["key"]
    )
    assert qty["value"] == post
    assert qty["delta_from_baseline"] == post - pre


@pytest.mark.asyncio
async def test_drought_twenty_four_tick_windows() -> None:
    base = drought_stock_base(max_ticks=24)
    entry = drought_schedule_entry(tick=8)
    definition = disasters_scenario(base, treatment_entry=entry)
    treatment = await _capture_assignment(materialize_assignments(definition)[1])
    assert treatment.report is not None
    episode = treatment.report.episodes[0]
    assert episode["shock_tick"] == 8
    windows = episode["windows"]
    assert windows[0]["window_index"] == -1
    assert windows[0]["status"] == "complete"
    assert windows[1]["status"] == "complete"
    assert windows[2]["status"] == "complete"
    # Later posts are right-censored by run end.
    assert windows[3]["status"] in {"partial", "unavailable"}
    evidence = treatment.evidence
    assert evidence is not None
    by_boundary = {frame.boundary_tick: frame for frame in evidence.frames}
    resource = next(
        panel
        for panel in episode["panels"]
        if panel["dimension"] == "resource_recovery"
    )
    for boundary, window_index in ((8, 0), (16, 1), (24, 2)):
        expected = _water_quantity(by_boundary[boundary])
        cell = resource["windows"][window_index]
        qty = next(
            measure
            for measure in cell["measures"]
            if measure["metric"] == "quantity_tenths"
            and measure["scope"] is not None
            and "water" in measure["scope"]["key"]
        )
        assert qty["value"] == expected
    # Immediate at s+1=9.
    imm_qty = _water_quantity(by_boundary[9])
    imm_panel = next(
        panel
        for panel in episode["immediate_state"]["panels"]
        if panel["dimension"] == "resource_recovery"
    )
    published = next(
        measure
        for measure in imm_panel["measures"]
        if measure["metric"] == "quantity_tenths"
        and measure["scope"] is not None
        and "water" in measure["scope"]["key"]
    )
    assert published["value"] == imm_qty


@pytest.mark.asyncio
async def test_skipped_schedule_and_not_reached() -> None:
    # Skipped: fire under rain → weather_ineligible receipt, no episode.
    from tests.unit.test_disaster_experiments import _loss_rule, _stock_base
    from world.values import WeatherCondition

    skipped_base = _stock_base(
        rule=_loss_rule(
            "fire-a", kind=DisasterKind.FIRE, resource_id="res-target"
        ),
        target_kind=ResourceKind.MATERIAL,
        weather=WeatherCondition.RAIN,
        nontarget_kind=ResourceKind.WATER,
    )
    skipped_entry = DisasterScheduleEntry(tick=DROUGHT_INJECT_TICK, rule_id="fire-a")
    skipped = await _capture_assignment(
        materialize_assignments(
            disasters_scenario(skipped_base, treatment_entry=skipped_entry)
        )[1]
    )
    assert skipped.report is not None
    assert skipped.report.episodes == ()
    # Complete prefix with only non-applied receipts is no_shock (not unknown).
    assert skipped.report.shock_status == "no_shock"
    sched = skipped.report.schedule[0]
    assert sched["status"] == "not_applied"
    assert sched["outcome"] == DisasterOutcome.WEATHER_INELIGIBLE.value
    assert sched["receipt_event_id"] is not None
    assert skipped.report.non_applied_counts.get(
        DisasterOutcome.WEATHER_INELIGIBLE.value, 0
    ) >= 1

    # Not reached: founder dies before scheduled tick.
    early = drought_stock_base(max_ticks=8)
    terminal_body = replace(
        early.scenario.bodies[0],
        health=Health(1),
        thirst=Thirst(100),
    )
    early = replace(
        early,
        mortality_mode=MortalityMode.ENABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=8, stop_on_all_agents_terminal=True
        ),
        scenario=replace(early.scenario, bodies=(terminal_body,)),
    )
    entry = drought_schedule_entry(tick=DROUGHT_INJECT_TICK)
    definition = disasters_scenario(early, treatment_entry=entry)
    reached = await _capture_assignment(materialize_assignments(definition)[1])
    assert reached.report is not None
    assert reached.report.episodes == ()
    row = next(
        item for item in reached.report.schedule if item["rule_id"] == "drought-a"
    )
    assert row["status"] == "not_reached"
    assert row["outcome"] is None
    assert row["receipt_event_id"] is None
    assert sum(reached.report.non_applied_counts.values()) == 0


@pytest.mark.asyncio
async def test_capture_off_parity_with_ordinary_run() -> None:
    base = drought_stock_base(max_ticks=4)
    entry = drought_schedule_entry()
    definition = disasters_scenario(base, treatment_entry=entry)
    assignment = materialize_assignments(definition)[1]
    config = assignment.runner_config
    off_runner = await SimulationRunner.from_config(
        config,
        run_id=assignment.run_id,
        factories=RunnerDependencyFactories(),
    )
    off_runner.set_intervention_arbiter(
        disasters_arbiter(
            assignment.condition_id,
            config,
            run_id=assignment.run_id,
        )
    )
    bind_disasters_experiment_runner(off_runner, config)
    async with off_runner:
        off = await run_with_resilience_capture(off_runner, capture=False)
    on = await _capture_assignment(assignment)
    assert off.status == "disabled"
    assert off.report is None
    assert on.result.ticks_committed == off.result.ticks_committed
    assert on.result.stop_reason == off.result.stop_reason
    assert on.result.run_id == off.result.run_id
    assert on.result.objective_state_hash == off.result.objective_state_hash
    assert on.result.cognition_counters == off.result.cognition_counters
