"""Off-gate experiment ``measurement_instruments@1`` (four declared arms)."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.measurement_config import MeasurementInstrumentsSpec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    RUNNER_SCHEMA_VERSION_V57,
    BoundedExperimentationSpec,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V3CapabilityFlags,
    V4CapabilityFlags,
    example_cultural_feature_provenance_spec,
    example_experiment_law,
)
from world.identifiers import EntityId
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReference,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.models import Item
from world.values import ItemKind, ItemLoad

__all__ = [
    "MEASUREMENT_INSTRUMENTS_EXPERIMENT_ID",
    "measurement_instruments_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.measurement_scenario")

MEASUREMENT_INSTRUMENTS_EXPERIMENT_ID: Final[str] = "measurement_instruments@1"
_MEASUREMENT_POLICY: Final[str] = "measurement-instruments.v1"
_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)


def _tool_item(item_id: str, name: str, holder_id: EntityId) -> Item:
    return Item(
        entity_id=EntityId(item_id),
        name=name,
        kind=ItemKind.TOOL,
        load=ItemLoad(1),
        holder_id=holder_id,
    )


def _instrument(
    item_id: EntityId, *, bias: int = 0, damage: int = 0
) -> InstrumentState:
    return InstrumentState(
        item_id=item_id,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        nominal_step_milli=1000,
        intrinsic_bias_milli=bias,
        base_error_bound_milli=0,
        damage_milli=damage,
        correction_milli=0,
        calibration_state=CalibrationState.NEVER_ADJUSTED,
        calibration_revision=0,
    )


def _with_instruments(
    config: SimulationRunnerConfig,
) -> tuple[
    SimulationRunnerConfig,
    tuple[InstrumentState, ...],
    tuple[MeasurementReference, ...],
]:
    if len(config.agents) < 2:
        raise ValueError("measurement_scenario_requires_two_founders")
    bodies = {body.entity_id: body for body in config.scenario.bodies}
    items = list(config.scenario.items)
    instruments: list[InstrumentState] = []
    references: list[MeasurementReference] = []
    body_updates = {}
    used_ids = {item.entity_id.value for item in config.scenario.items}
    for agent in config.agents[:2]:
        body = bodies.get(agent.entity_id)
        if body is None:
            raise ValueError("measurement_scenario_body_missing")
        available = body.carry_capacity.value - sum(
            next(
                item.load.value
                for item in config.scenario.items
                if item.entity_id == item_id
            )
            for item_id in body.inventory
        )
        if available < 2:
            raise ValueError("measurement_scenario_carry_capacity")
        instrument_id = f"item:measure-instrument-{agent.entity_id.value}"
        reference_id = f"item:measure-reference-{agent.entity_id.value}"
        if instrument_id in used_ids or reference_id in used_ids:
            raise ValueError("measurement_scenario_id_collision")
        items.append(
            _tool_item(instrument_id, "measurement instrument", agent.entity_id)
        )
        items.append(_tool_item(reference_id, "measurement reference", agent.entity_id))
        body_updates[body.entity_id] = replace(
            body,
            inventory=(
                *body.inventory,
                EntityId(instrument_id),
                EntityId(reference_id),
            ),
        )
        instruments.append(_instrument(EntityId(instrument_id)))
        references.append(
            MeasurementReference(
                item_id=EntityId(reference_id),
                unit=_CELSIUS,
                nominal_value_milli=20000,
                physical_value_milli=21000,
            )
        )
    bodies_tuple = tuple(
        body_updates.get(body.entity_id, body) for body in config.scenario.bodies
    )
    return (
        replace(
            config,
            scenario=replace(config.scenario, items=tuple(items), bodies=bodies_tuple),
        ),
        tuple(sorted(instruments, key=lambda row: row.item_id.value)),
        tuple(sorted(references, key=lambda row: row.item_id.value)),
    )


def measurement_instruments_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 64,
) -> ExperimentDefinition:
    """Four arms over the accepted v56 science seam and explicit v57 instruments."""
    if isinstance(max_ticks, bool) or type(max_ticks) is not int or max_ticks < 64:
        _LOG.warning("measurement_scenario_invalid reason_code=min_ticks")
        raise ValueError("measurement_scenario_min_ticks")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    law = example_experiment_law(
        operator="vary_process",
        operand_a_kind="item:tool",
        operand_b_kind="none",
        process_token="harvest",
        outcome_class="failure",
        delta="none",
    )
    shared, instruments, references = _with_instruments(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V56,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            capability_flags=V2CapabilityFlags(predictive_world_model=True),
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=(example_cultural_feature_provenance_spec()),
            bounded_experimentation=BoundedExperimentationSpec(
                laws=(law,),
                max_hypotheses=8,
                max_trials_per_tick=1,
                repeat_threshold=2,
                learn_into_genealogy=False,
                allow_provider=False,
            ),
            v4_capability_flags=V4CapabilityFlags(science=True),
        )
    )
    from world.production import example_production_catalog

    catalog = example_production_catalog()
    shared = replace(
        shared,
        agents=tuple(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            )
            for agent in shared.agents
        ),
    )
    baseline = replace(
        shared,
        v4_capability_flags=V4CapabilityFlags(science=True),
    )
    unspeced = replace(
        baseline,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        measurement_instruments=None,
    )

    def _enabled(bias: int = 0, damage: int = 0) -> SimulationRunnerConfig:
        tuned = tuple(
            _instrument(row.item_id, bias=bias, damage=damage) for row in instruments
        )
        return replace(
            shared,
            schema_version=RUNNER_SCHEMA_VERSION_V57,
            measurement_instruments=MeasurementInstrumentsSpec(
                policy_version=_MEASUREMENT_POLICY,
                instruments=tuned,
                references=references,
            ),
        )

    conditions = (
        ExperimentCondition(
            condition_id="measurement-absent",
            label_code="measurement_absent",
            runner_config=unspeced,
        ),
        ExperimentCondition(
            condition_id="measurement-unbiased",
            label_code="measurement_unbiased",
            runner_config=_enabled(),
        ),
        ExperimentCondition(
            condition_id="measurement-biased",
            label_code="measurement_biased",
            runner_config=_enabled(bias=5000),
        ),
        ExperimentCondition(
            condition_id="measurement-damaged",
            label_code="measurement_damaged",
            runner_config=_enabled(damage=750),
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s",
        MEASUREMENT_INSTRUMENTS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=MEASUREMENT_INSTRUMENTS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{MEASUREMENT_INSTRUMENTS_EXPERIMENT_ID}-world",
    )
