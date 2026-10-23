"""Grouped shared-prefix execution for historical-contingency experiments."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final

from experiments.interventions import MilestoneInterventionArbiter, MilestoneOverride
from experiments.path_dependence_identity import assign_branch_arms, build_branch_slots
from experiments.path_dependence_interventions import (
    PathDependenceArbiter,
    TreatmentLedgerEntry,
)
from experiments.path_dependence_models import (
    CommonSetupCommand,
    PathDependenceSpec,
    ScheduledCommandIntervention,
)
from experiments.path_dependence_scenario import (
    PrefixEligibility,
    resolve_food_opportunity_eligibility,
)
from simulation.engine import WorldEngine
from simulation.fork_checkpoint import RunnerForkCheckpoint
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import runner_stop_is_failure
from world.actions import AgentCommand

_LOG: Final[logging.Logger] = logging.getLogger("experiments.path_dependence_runner")


class PathDependenceExecutionError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PathDependenceExecutionContext:
    factories: RunnerDependencyFactories
    materialize_engine: Callable[[RunnerForkCheckpoint, RunId], Awaitable[WorldEngine]]
    eligibility: Callable[[RunnerForkCheckpoint], PrefixEligibility] | None = None
    cultural_sink_factory: Callable[[RunId], object | None] | None = None
    source_identity: str = "unspecified"


@dataclass(frozen=True, slots=True)
class BranchExecutionResult:
    slot_ordinal: int
    child_run_id: str
    arm_id: str
    status: str
    ticks_committed: int = 0
    stop_reason: str | None = None
    error_code: str | None = None
    treatment_ledger: tuple[TreatmentLedgerEntry, ...] = ()
    complete_state_digest: str | None = None
    objective_head_hash: str | None = None
    terminal_revision: int | None = None


@dataclass(frozen=True, slots=True)
class PrefixExecutionResult:
    parent_run_id: str
    fork_tick: int
    eligible: bool
    reason_code: str
    child_results: tuple[BranchExecutionResult, ...] = ()
    boundary_revision: int = 0
    config_fingerprint: str = ""
    complete_state_digest: str = ""
    bootstrap_hash: str = ""
    snapshot_hash: str = ""
    objective_head_hash: str = ""
    eligibility_witness: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class PathDependenceExecutionSummary:
    spec_fingerprint: str
    prefixes: tuple[PrefixExecutionResult, ...]

    @property
    def completed_count(self) -> int:
        return sum(
            1
            for prefix in self.prefixes
            for child in prefix.child_results
            if child.status == "completed"
        )

    @property
    def failed_count(self) -> int:
        return sum(
            1
            for prefix in self.prefixes
            for child in prefix.child_results
            if child.status == "failed"
        )

    @property
    def ineligible_count(self) -> int:
        return sum(1 for prefix in self.prefixes if not prefix.eligible)


def _setup_arbiter(setup: Sequence[CommonSetupCommand]) -> MilestoneInterventionArbiter:
    def _build(value: AgentCommand) -> Callable[[], AgentCommand]:
        def build() -> AgentCommand:
            return value

        return build

    milestones = [
        MilestoneOverride(
            f"setup-{index}",
            command.tick.value,
            command.actor_id,
            build_command=_build(command.command),
        )
        for index, command in enumerate(setup)
    ]
    return MilestoneInterventionArbiter(milestones, override_budget=len(milestones))


def _arm_actions(
    spec: PathDependenceSpec, arm_id: str, fork_tick: int
) -> tuple[ScheduledCommandIntervention, ...]:
    from simulation.clock import Tick

    arm = next((item for item in spec.arms if item.arm_id == arm_id), None)
    if arm is None:
        raise PathDependenceExecutionError("unknown_arm")
    return arm.actions_for(Tick(fork_tick))


class PathDependenceBatchRunner:
    async def run(
        self,
        spec: PathDependenceSpec,
        context: PathDependenceExecutionContext,
    ) -> PathDependenceExecutionSummary:
        from experiments.path_dependence_serialization import (
            path_dependence_spec_fingerprint,
        )

        if type(spec) is not PathDependenceSpec:
            raise TypeError("spec must be PathDependenceSpec")
        if type(context) is not PathDependenceExecutionContext:
            raise TypeError("context must be PathDependenceExecutionContext")
        fingerprint = path_dependence_spec_fingerprint(spec)
        parent_run_id = RunId(f"pd-parent-{fingerprint[:24]}")
        parent = await SimulationRunner.from_config(
            spec.base, run_id=parent_run_id, factories=context.factories
        )
        try:
            parent.set_intervention_arbiter(_setup_arbiter(spec.common_setup))
            await parent.initialize_finalized_boundary()
            prefixes: list[PrefixExecutionResult] = []
            for fork_tick in spec.fork_ticks:
                while (
                    parent.export_runtime_checkpoint().ticks_committed
                    < fork_tick.value
                ):
                    receipt = await parent.run_tick()
                    if receipt.status.value != "finalized":
                        raise PathDependenceExecutionError(
                            "prefix_execution_aborted"
                        )
                checkpoint = await parent.capture_fork_checkpoint()
                from simulation.fork_checkpoint import fork_state_digest

                prefix_state_digest = fork_state_digest(checkpoint)
                eligibility = (
                    resolve_food_opportunity_eligibility(checkpoint)
                    if context.eligibility is None
                    else context.eligibility(checkpoint)
                )
                slots = build_branch_slots(spec, parent_run_id.value, fork_tick)
                assignments = {
                    item.slot_ordinal: item.arm_id
                    for item in assign_branch_arms(
                        spec, slots, parent_identity=parent_run_id.value
                    )
                }
                children: list[BranchExecutionResult] = []
                if not eligibility.eligible:
                    for slot in slots:
                        children.append(
                            BranchExecutionResult(
                                slot_ordinal=slot.slot_ordinal,
                                child_run_id=slot.child_run_id,
                                arm_id=assignments[slot.slot_ordinal],
                                status="ineligible",
                                error_code=eligibility.reason_code,
                            )
                        )
                else:
                    for slot in slots:
                        arm_id = assignments[slot.slot_ordinal]
                        child_run = RunId(slot.child_run_id)
                        try:
                            engine = await context.materialize_engine(
                                checkpoint, child_run
                            )
                            sink = (
                                None
                                if context.cultural_sink_factory is None
                                else context.cultural_sink_factory(child_run)
                            )
                            child = await SimulationRunner.from_fork_checkpoint(
                                spec.base,
                                run_id=child_run,
                                checkpoint=checkpoint,
                                restored_engine=engine,
                                factories=context.factories,
                                cultural_sink=sink,
                            )
                            try:
                                arbiter = PathDependenceArbiter(
                                    _arm_actions(spec, arm_id, fork_tick.value),
                                    override_budget=(
                                        spec.max_interventions_per_arm
                                    ),
                                )
                                child.set_intervention_arbiter(arbiter)
                                result = await child.run()
                                arbiter.finalize_unreached()
                                failed = runner_stop_is_failure(
                                    result.stop_reason
                                )
                                child_digest = None
                                child_head = None
                                child_rev = None
                                if not failed:
                                    try:
                                        child_checkpoint = (
                                            await child.capture_fork_checkpoint()
                                        )
                                        child_digest = fork_state_digest(
                                            child_checkpoint
                                        )
                                        child_head = (
                                            child_checkpoint.snapshot.integrity_hash.value
                                        )
                                        child_rev = (
                                            child_checkpoint.boundary_revision.value
                                        )
                                    except Exception:
                                        child_digest = None
                                children.append(
                                    BranchExecutionResult(
                                        slot_ordinal=slot.slot_ordinal,
                                        child_run_id=slot.child_run_id,
                                        arm_id=arm_id,
                                        status=(
                                            "failed" if failed else "completed"
                                        ),
                                        ticks_committed=result.ticks_committed,
                                        stop_reason=result.stop_reason.value,
                                        error_code=(
                                            result.stop_reason.value
                                            if failed
                                            else None
                                        ),
                                        treatment_ledger=(
                                            arbiter.treatment_ledger
                                        ),
                                        complete_state_digest=child_digest,
                                        objective_head_hash=child_head,
                                        terminal_revision=child_rev,
                                    )
                                )
                            finally:
                                await child.aclose()
                        except Exception:
                            _LOG.error(
                                "path_dependence_child_failed child_run_id=%s "
                                "arm_id=%s reason_code=child_execution_failed",
                                slot.child_run_id,
                                arm_id,
                            )
                            children.append(
                                BranchExecutionResult(
                                    slot_ordinal=slot.slot_ordinal,
                                    child_run_id=slot.child_run_id,
                                    arm_id=arm_id,
                                    status="failed",
                                    error_code="child_execution_failed",
                                )
                            )
                prefixes.append(
                    PrefixExecutionResult(
                        parent_run_id=parent_run_id.value,
                        fork_tick=fork_tick.value,
                        eligible=eligibility.eligible,
                        reason_code=eligibility.reason_code,
                        child_results=tuple(children),
                        boundary_revision=checkpoint.boundary_revision.value,
                        config_fingerprint=checkpoint.config_fingerprint,
                        complete_state_digest=prefix_state_digest,
                        bootstrap_hash=(
                            checkpoint.bootstrap_snapshot.integrity_hash.value
                        ),
                        snapshot_hash=checkpoint.snapshot.integrity_hash.value,
                        objective_head_hash=(
                            checkpoint.snapshot.integrity_hash.value
                        ),
                        eligibility_witness=(
                            ()
                            if eligibility.witness is None
                            else (
                                {
                                    "founder_agent_id": (
                                        eligibility.witness.founder_agent_id.value
                                    ),
                                    "founder_body_id": (
                                        eligibility.witness.founder_body_id.value
                                    ),
                                    "recipient_body_id": (
                                        eligibility.witness.recipient_body_id.value
                                    ),
                                    "item_id": eligibility.witness.item_id.value,
                                    "item_name": eligibility.witness.item_name,
                                    "location_id": (
                                        eligibility.witness.location_id.value
                                    ),
                                },
                            )
                        ),
                    )
                )
            return PathDependenceExecutionSummary(
                spec_fingerprint=fingerprint, prefixes=tuple(prefixes)
            )
        finally:
            await parent.aclose()


__all__ = [
    "BranchExecutionResult",
    "PathDependenceBatchRunner",
    "PathDependenceExecutionContext",
    "PathDependenceExecutionError",
    "PathDependenceExecutionSummary",
    "PrefixExecutionResult",
]
