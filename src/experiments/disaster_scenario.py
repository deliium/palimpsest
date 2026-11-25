"""Off-gate experiment ``disasters@1`` (paired control / scheduled-shock).

Arms differ only by the immutable disasters schedule. The base must already be a
valid runner-config-v63 disasters document with one zero-probability rule and an
empty schedule; this factory never rewrites the horizon or enables siblings.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from agents.models import AgentId
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.disasters_config import DisastersSpec
from simulation.models import RunId
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V63,
    SimulationRunnerConfig,
)
from world.actions import (
    AgentCommand,
    ContributeCollectiveProject,
    StartCollectiveProject,
    Wait,
)
from world.disasters import (
    DisasterInfrastructureTarget,
    DisasterKind,
    DisasterScheduleEntry,
)
from world.identifiers import EntityId
from world.infrastructure import InfrastructureKind

__all__ = [
    "DISASTERS_EXPERIMENT_ID",
    "bind_disasters_experiment_runner",
    "disasters_arbiter",
    "disasters_scenario",
    "experiment_disasters",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.disaster_scenario")

DISASTERS_EXPERIMENT_ID: Final[str] = "disasters@1"
_CONTROL_ID: Final[str] = "control"
_TREATMENT_ID: Final[str] = "scheduled-shock"


class _FixedCommandArbiter:
    """Force allowlisted commands; default Wait keeps pre-treatment fixed."""

    __slots__ = ("_commands",)

    def __init__(self, commands: dict[tuple[int, str], AgentCommand]) -> None:
        self._commands = dict(commands)

    def maybe_replace(
        self,
        *,
        tick: int,
        agent_id: object,
        proposed_command: object | None = None,
    ) -> AgentCommand:
        del proposed_command
        key = (tick, getattr(agent_id, "value", str(agent_id)))
        return self._commands.get(key, Wait())


def _fail_base(reason_code: str) -> ValueError:
    _LOG.warning(
        "disasters_experiment_invalid reason_code=%s experiment_id=%s",
        reason_code,
        DISASTERS_EXPERIMENT_ID,
    )
    return ValueError("disasters_experiment_base_invalid")


def _fail_schedule(reason_code: str) -> ValueError:
    _LOG.warning(
        "disasters_experiment_invalid reason_code=%s experiment_id=%s",
        reason_code,
        DISASTERS_EXPERIMENT_ID,
    )
    return ValueError("disasters_experiment_schedule_invalid")


def _require_base(base: SimulationRunnerConfig) -> DisastersSpec:
    if type(base) is not SimulationRunnerConfig:
        raise TypeError("disasters_experiment_base_invalid")
    if base.schema_version != RUNNER_SCHEMA_VERSION_V63:
        raise _fail_base("schema_version")
    if type(base.disasters) is not DisastersSpec:
        raise _fail_base("disasters_missing")
    if not base.v4_capability_flags.disasters:
        raise _fail_base("disasters_flag")
    disasters = base.disasters
    if len(disasters.rules) != 1:
        raise _fail_base("rule_count")
    rule = disasters.rules[0]
    if rule.chance_ppm != 0:
        raise _fail_base("chance_ppm")
    if disasters.schedule != ():
        raise _fail_base("schedule_nonempty")
    return disasters


def _require_treatment_entry(
    entry: object,
    *,
    rule_id: str,
    max_ticks: int,
) -> DisasterScheduleEntry:
    if type(entry) is not DisasterScheduleEntry:
        raise _fail_schedule("entry_type")
    if entry.rule_id != rule_id:
        raise _fail_schedule("rule_mismatch")
    if (
        isinstance(max_ticks, bool)
        or type(max_ticks) is not int
        or max_ticks <= entry.tick
    ):
        raise _fail_schedule("horizon")
    return entry


def _resolve_matrix(
    seed_matrix: ExperimentSeedMatrix | None,
    *,
    seed: int,
) -> ExperimentSeedMatrix:
    if seed_matrix is None:
        return ExperimentSeedMatrix(seeds=(seed,))
    if type(seed_matrix) is not ExperimentSeedMatrix:
        raise TypeError("disasters_experiment_base_invalid")
    return seed_matrix


def disasters_scenario(
    base: SimulationRunnerConfig,
    *,
    treatment_entry: DisasterScheduleEntry,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired empty-schedule control vs one scheduled shock over a validated base."""
    disasters = _require_base(base)
    rule = disasters.rules[0]
    entry = _require_treatment_entry(
        treatment_entry,
        rule_id=rule.rule_id,
        max_ticks=base.stop_policy.max_ticks,
    )
    matrix = _resolve_matrix(seed_matrix, seed=base.seed)

    control = base
    try:
        treatment = replace(
            base,
            disasters=replace(disasters, schedule=(entry,)),
        )
    except (TypeError, ValueError) as exc:
        _LOG.warning(
            "disasters_experiment_invalid reason_code=treatment_validate "
            "experiment_id=%s",
            DISASTERS_EXPERIMENT_ID,
        )
        raise ValueError("disasters_experiment_schedule_invalid") from exc

    # Re-enter ordinary validation without mutating the caller's horizon/flags.
    if treatment.stop_policy != control.stop_policy:
        raise _fail_base("stop_policy_mutated")
    if treatment.v4_capability_flags != control.v4_capability_flags:
        raise _fail_base("flags_mutated")
    if treatment.schema_version != control.schema_version:
        raise _fail_base("schema_mutated")
    if (
        treatment.disasters is None
        or treatment.disasters.rules != control.disasters.rules  # type: ignore[union-attr]
        or treatment.disasters.schedule != (entry,)
    ):
        raise _fail_schedule("schedule_replace")

    conditions = (
        ExperimentCondition(
            condition_id=_CONTROL_ID,
            label_code="disasters_control",
            runner_config=control,
        ),
        ExperimentCondition(
            condition_id=_TREATMENT_ID,
            label_code="disasters_scheduled_shock",
            runner_config=treatment,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s",
        DISASTERS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=DISASTERS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{DISASTERS_EXPERIMENT_ID}-world",
    )


def experiment_disasters(
    base: SimulationRunnerConfig,
    *,
    treatment_entry: DisasterScheduleEntry,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Catalog-facing wrapper for ``disasters@1``."""
    return disasters_scenario(
        base, treatment_entry=treatment_entry, seed_matrix=seed_matrix
    )


def _infrastructure_prep_commands(
    config: SimulationRunnerConfig,
    *,
    run_id: RunId,
) -> dict[tuple[int, str], AgentCommand]:
    """Script a deterministic well build before a scheduled destruction."""
    from experiments.civilization_benchmark_coordination import project_id_for

    disasters = config.disasters
    if disasters is None or len(disasters.rules) != 1:
        return {}
    rule = disasters.rules[0]
    if rule.kind is not DisasterKind.INFRASTRUCTURE_DESTRUCTION:
        return {}
    if type(rule.target) is not DisasterInfrastructureTarget:
        return {}
    if rule.target.infrastructure_kind is not InfrastructureKind.WELL:
        return {}
    if not config.agents:
        return {}
    owner = config.agents[0]
    agent_id = owner.agent_id
    project_id = project_id_for(
        config, run_id=run_id, tick=0, agent_id=AgentId(agent_id.value)
    )
    body = next(
        (item for item in config.scenario.bodies if item.entity_id == owner.entity_id),
        None,
    )
    stone_ids: list[EntityId] = []
    if body is not None:
        stone_ids = list(body.inventory[:2])
    commands: dict[tuple[int, str], AgentCommand] = {
        (0, agent_id.value): StartCollectiveProject(project_kind="well"),
    }
    # Well needs two stones + three labor; bind forces certain contributes.
    for index, stone_id in enumerate(stone_ids):
        commands[(1 + index, agent_id.value)] = ContributeCollectiveProject(
            project_id=project_id, item_id=stone_id
        )
    labor_start = 1 + len(stone_ids)
    for labor_tick in range(labor_start, labor_start + 3):
        commands[(labor_tick, agent_id.value)] = ContributeCollectiveProject(
            project_id=project_id, item_id=None
        )
    _LOG.debug(
        "disasters_infra_prep agent_id=%s stone_count=%s project_id=%s "
        "labor_start=%s",
        agent_id.value,
        len(stone_ids),
        project_id.value,
        labor_start,
    )
    return commands


def disasters_arbiter(
    condition_id: str,
    config: SimulationRunnerConfig,
    *,
    run_id: RunId,
) -> _FixedCommandArbiter:
    """Fixed pre-treatment commands for ``disasters@1`` (Wait unless infra prep)."""
    del condition_id
    commands = _infrastructure_prep_commands(config, run_id=run_id)
    _LOG.debug(
        "disasters_arbiter_ready experiment_id=%s override_count=%s",
        DISASTERS_EXPERIMENT_ID,
        len(commands),
    )
    return _FixedCommandArbiter(commands)


def bind_disasters_experiment_runner(
    runner: object,
    config: SimulationRunnerConfig,
) -> None:
    """Make infrastructure prep run-id-stable by forcing certain contributes.

    Collective contributes otherwise draw at base probability 0.70, so distinct
    durable run IDs would diverge paired arms before the scheduled shock. Stock
    and surge arms leave the draw hook untouched.
    """
    disasters = config.disasters
    if disasters is None or len(disasters.rules) != 1:
        return
    if disasters.rules[0].kind is not DisasterKind.INFRASTRUCTURE_DESTRUCTION:
        return
    engine = getattr(runner, "engine", None)
    force = getattr(engine, "force_collective_contribute_success", None)
    if engine is None or not callable(force):
        _LOG.warning(
            "disasters_experiment_invalid reason_code=runner_engine_missing "
            "experiment_id=%s",
            DISASTERS_EXPERIMENT_ID,
        )
        return
    force(True)
    _LOG.info(
        "disasters_infra_contribute_certain experiment_id=%s",
        DISASTERS_EXPERIMENT_ID,
    )
