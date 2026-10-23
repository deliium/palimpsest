"""Immutable contracts for the historical-contingency research protocol.

These values describe a trusted experiment recipe. They never grant world
authority, mutate runner configuration, or install social knowledge. The only
simulation seam they reference is the already accepted ``runner-config-v55``
generational runner.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Literal

from agents.models import AgentId
from analysis.path_dependence_contracts import (
    OutcomeDomain,
    OutcomeSelector,
    OutcomeWindow,
    PathDependenceValidationError,
)
from simulation.clock import Tick
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    RecordingPolicy,
    SimulationRunnerConfig,
)
from world.actions import (
    AgentCommand,
    Drink,
    Eat,
    Give,
    Move,
    Sleep,
    Take,
    Wait,
    require_agent_command,
)
from world.identifiers import EntityId, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("experiments.path_dependence_models")

PATH_DEPENDENCE_SPEC_SCHEMA_VERSION: Final[str] = "path-dependence-spec-v1"
PATH_DEPENDENCE_EXPERIMENT_ID: Final[str] = "historical_contingency@1"
PATH_DEPENDENCE_CAPTURE_POLICY: Final[str] = "bounded-boundary-v1"

MAX_SEED_ENTRIES: Final[int] = 1024
MAX_REPLICATES_PER_SEED: Final[int] = 32
MAX_FORK_TICKS: Final[int] = 8
MAX_ARMS: Final[int] = 16
MAX_SELECTORS_OR_WINDOWS: Final[int] = 64
MAX_PLANNED_CHILDREN: Final[int] = 8192
MAX_COMMON_SETUP_COMMANDS: Final[int] = 4096
DEFAULT_MAX_ACTIONS_PER_ARM_FORK: Final[int] = 4
MAX_ACTIONS_PER_ARM_FORK: Final[int] = 16
MAX_SPEC_DOCUMENT_BYTES: Final[int] = 16 * 1024 * 1024
MAX_SPEC_DOCUMENT_DEPTH: Final[int] = 32
MAX_EVIDENCE_CHUNK_BYTES: Final[int] = 16 * 1024 * 1024
MAX_EVIDENCE_CHUNKS_PER_BRANCH: Final[int] = 1024
MAX_BOUNDARY_OWNERS: Final[int] = 2048
MAX_BOUNDARY_ROWS: Final[int] = 50000


class ArmRole(StrEnum):
    """Researcher-facing arm role. Never a world role or moral label."""

    CONTROL = "control"
    TREATMENT = "treatment"
    NEUTRAL = "neutral"


def _require_str(name: str, value: object) -> str:
    if type(value) is not str:
        raise PathDependenceValidationError("invalid_type", f"{name} must be str")
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise PathDependenceValidationError("invalid_id", str(exc)) from exc


def _require_int(name: str, value: object, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise PathDependenceValidationError(
            "invalid_int", f"{name} must be an exact int"
        )
    if value < minimum:
        raise PathDependenceValidationError(
            "invalid_int", f"{name} must be >= {minimum}"
        )
    return value


def _require_tick(name: str, value: object) -> Tick:
    if type(value) is not Tick:
        raise PathDependenceValidationError("invalid_tick", f"{name} must be Tick")
    return value


def _require_ordered[T](name: str, value: object, entry_type: type[T]) -> tuple[T, ...]:
    if isinstance(value, (set, frozenset)):
        raise PathDependenceValidationError(
            "unordered_collection", f"{name} must be ordered"
        )
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PathDependenceValidationError(
            "invalid_collection", f"{name} must be an ordered sequence"
        )
    copied = tuple(value)
    for entry in copied:
        if type(entry) is not entry_type:
            raise PathDependenceValidationError(
                "invalid_type",
                f"{name} entries must be {entry_type.__name__}",
            )
    return copied


@dataclass(frozen=True, slots=True)
class CommonSetupCommand:
    """One declared pre-treatment command on the shared parent timeline."""

    actor_id: AgentId
    tick: Tick
    command: AgentCommand

    def __post_init__(self) -> None:
        if type(self.actor_id) is not AgentId:
            raise PathDependenceValidationError(
                "invalid_type", "actor_id must be AgentId"
            )
        _require_tick("tick", self.tick)
        object.__setattr__(self, "command", require_agent_command(self.command))
        if type(self.command) not in (Move, Take, Eat, Drink, Sleep, Give, Wait):
            raise PathDependenceValidationError(
                "unsupported_intervention",
                "common setup permits only Move, Take, Eat, Drink, Sleep, Give, Wait",
            )


@dataclass(frozen=True, slots=True)
class GiveInterventionAction:
    """Give one named portable item to a pre-resolved recipient."""

    item_id: EntityId
    recipient_entity_id: EntityId
    kind: Literal["give"] = field(default="give", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise PathDependenceValidationError(
                "invalid_type", "item_id must be EntityId"
            )
        if type(self.recipient_entity_id) is not EntityId:
            raise PathDependenceValidationError(
                "invalid_type", "recipient_entity_id must be EntityId"
            )


@dataclass(frozen=True, slots=True)
class WaitInterventionAction:
    """Withhold action for exactly one actor/tick."""

    kind: Literal["wait"] = field(default="wait", init=False)


InterventionAction = GiveInterventionAction | WaitInterventionAction


@dataclass(frozen=True, slots=True)
class ScheduledCommandIntervention:
    """One bounded child-only intervention with explicit predeclared identity."""

    intervention_id: str
    actor_id: AgentId
    tick: Tick
    action: InterventionAction

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "intervention_id",
            _require_str("intervention_id", self.intervention_id),
        )
        if type(self.actor_id) is not AgentId:
            raise PathDependenceValidationError(
                "invalid_type", "actor_id must be AgentId"
            )
        _require_tick("tick", self.tick)
        if type(self.action) not in (GiveInterventionAction, WaitInterventionAction):
            raise PathDependenceValidationError(
                "unsupported_intervention",
                "action must be GiveInterventionAction or WaitInterventionAction",
            )


@dataclass(frozen=True, slots=True)
class ForkTickSchedule:
    """Ordered actions one arm declares for one fork tick."""

    fork_tick: Tick
    actions: tuple[ScheduledCommandIntervention, ...] = ()

    def __post_init__(self) -> None:
        _require_tick("fork_tick", self.fork_tick)
        object.__setattr__(
            self,
            "actions",
            _require_ordered("actions", self.actions, ScheduledCommandIntervention),
        )
        seen_interventions: set[str] = set()
        seen_slots: set[tuple[int, str]] = set()
        for action in self.actions:
            if action.intervention_id in seen_interventions:
                raise PathDependenceValidationError(
                    "duplicate_intervention",
                    f"duplicate intervention_id: {action.intervention_id}",
                )
            seen_interventions.add(action.intervention_id)
            slot = (action.tick.value, action.actor_id.value)
            if slot in seen_slots:
                raise PathDependenceValidationError(
                    "duplicate_intervention",
                    "actions must have unique (tick, actor) slots",
                )
            seen_slots.add(slot)


@dataclass(frozen=True, slots=True)
class PathDependenceArm:
    """One immutable arm with a complete per-fork-tick action schedule."""

    arm_id: str
    label_code: str
    role: ArmRole
    schedule_by_fork_tick: tuple[ForkTickSchedule, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arm_id", _require_str("arm_id", self.arm_id))
        object.__setattr__(
            self, "label_code", _require_str("label_code", self.label_code)
        )
        if type(self.role) is not ArmRole:
            raise PathDependenceValidationError("invalid_type", "role must be ArmRole")
        object.__setattr__(
            self,
            "schedule_by_fork_tick",
            _require_ordered(
                "schedule_by_fork_tick", self.schedule_by_fork_tick, ForkTickSchedule
            ),
        )
        seen_ticks: set[int] = set()
        for schedule in self.schedule_by_fork_tick:
            if schedule.fork_tick.value in seen_ticks:
                raise PathDependenceValidationError(
                    "invalid_fork_window",
                    "arm schedules must contain each fork tick exactly once",
                )
            seen_ticks.add(schedule.fork_tick.value)

    def actions_for(self, fork_tick: Tick) -> tuple[ScheduledCommandIntervention, ...]:
        for schedule in self.schedule_by_fork_tick:
            if schedule.fork_tick == fork_tick:
                return schedule.actions
        raise PathDependenceValidationError(
            "invalid_fork_window", f"arm {self.arm_id} has no schedule for {fork_tick}"
        )


@dataclass(frozen=True, slots=True)
class ProtocolContrast:
    """One declared treatment-minus-control protocol comparison."""

    contrast_id: str
    control_arm_id: str
    treatment_arm_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contrast_id", _require_str("contrast_id", self.contrast_id)
        )
        object.__setattr__(
            self,
            "control_arm_id",
            _require_str("control_arm_id", self.control_arm_id),
        )
        object.__setattr__(
            self,
            "treatment_arm_id",
            _require_str("treatment_arm_id", self.treatment_arm_id),
        )
        if self.control_arm_id == self.treatment_arm_id:
            raise PathDependenceValidationError(
                "unknown_arm", "control and treatment arms must differ"
            )


@dataclass(frozen=True, slots=True)
class BranchSlot:
    """One treatment-blind child slot in the sealed design."""

    slot_ordinal: int
    numeric_seed: int
    seed_ordinal: int
    replicate: int
    fork_tick: Tick
    child_run_id: str

    def __post_init__(self) -> None:
        _require_int("slot_ordinal", self.slot_ordinal)
        _require_int("numeric_seed", self.numeric_seed)
        _require_int("seed_ordinal", self.seed_ordinal)
        _require_int("replicate", self.replicate)
        _require_tick("fork_tick", self.fork_tick)
        object.__setattr__(
            self, "child_run_id", _require_str("child_run_id", self.child_run_id)
        )


@dataclass(frozen=True, slots=True)
class PathDependenceLineage:
    """Explicit lineage from a common parent boundary to one child branch."""

    ensemble_id: str
    spec_fingerprint: str
    parent_scientific_id: str
    parent_attempt_id: str
    parent_boundary_tick: Tick
    parent_boundary_revision: int
    parent_commit_hash: str
    parent_snapshot_hash: str
    complete_state_digest: str
    child_scientific_id: str
    child_attempt_id: str
    slot_ordinal: int
    arm_id: str
    action_schedule_digest: str
    assignment_seed: int
    assignment_policy: str
    numeric_seed: int
    seed_ordinal: int
    replicate: int
    provider_identity: str
    code_source_identity: str
    channel_lineage_digest: str
    root_parent_id: str
    ancestry: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "ensemble_id",
            "parent_scientific_id",
            "parent_attempt_id",
            "child_scientific_id",
            "child_attempt_id",
            "arm_id",
            "assignment_policy",
            "provider_identity",
            "code_source_identity",
            "root_parent_id",
        ):
            object.__setattr__(self, name, _require_str(name, getattr(self, name)))
        for name in (
            "spec_fingerprint",
            "parent_commit_hash",
            "parent_snapshot_hash",
            "complete_state_digest",
            "action_schedule_digest",
            "channel_lineage_digest",
        ):
            object.__setattr__(self, name, _require_digest(name, getattr(self, name)))
        _require_tick("parent_boundary_tick", self.parent_boundary_tick)
        for name in (
            "parent_boundary_revision",
            "slot_ordinal",
            "assignment_seed",
            "numeric_seed",
            "seed_ordinal",
            "replicate",
        ):
            object.__setattr__(self, name, _require_int(name, getattr(self, name)))
        object.__setattr__(
            self, "ancestry", _require_ordered("ancestry", self.ancestry, str)
        )
        for entry in self.ancestry:
            _require_str("ancestry", entry)


def _require_digest(name: str, value: object) -> str:
    if type(value) is not str or len(value) != 64:
        raise PathDependenceValidationError(
            "invalid_digest", f"{name} must be a 64-character hex digest"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise PathDependenceValidationError(
            "invalid_digest", f"{name} must be a 64-character hex digest"
        ) from exc
    return value.lower()


@dataclass(frozen=True, slots=True)
class PathDependenceSpec:
    """Sealed, bounded recipe for one historical-contingency ensemble."""

    base: SimulationRunnerConfig
    seeds: tuple[int, ...]
    replicates_per_seed: int
    fork_ticks: tuple[Tick, ...]
    horizon_tick: Tick
    arms: tuple[PathDependenceArm, ...]
    contrasts: tuple[ProtocolContrast, ...]
    windows: tuple[OutcomeWindow, ...]
    selectors: tuple[OutcomeSelector, ...]
    assignment_seed: int
    common_setup: tuple[CommonSetupCommand, ...] = ()
    max_interventions_per_arm: int = DEFAULT_MAX_ACTIONS_PER_ARM_FORK
    capture_policy: str = PATH_DEPENDENCE_CAPTURE_POLICY
    schema_version: str = PATH_DEPENDENCE_SPEC_SCHEMA_VERSION
    experiment_id: str = PATH_DEPENDENCE_EXPERIMENT_ID

    def __post_init__(self) -> None:
        if self.schema_version != PATH_DEPENDENCE_SPEC_SCHEMA_VERSION:
            raise PathDependenceValidationError(
                "unsupported_base", "unsupported path-dependence schema_version"
            )
        if self.experiment_id != PATH_DEPENDENCE_EXPERIMENT_ID:
            raise PathDependenceValidationError(
                "unsupported_base", "unsupported experiment_id"
            )
        if type(self.base) is not SimulationRunnerConfig:
            raise PathDependenceValidationError(
                "unsupported_base", "base must be SimulationRunnerConfig"
            )
        if self.base.schema_version != RUNNER_SCHEMA_VERSION_V55:
            raise PathDependenceValidationError(
                "unsupported_base", "base must be runner-config-v55"
            )
        if self.base.generational_run is None:
            raise PathDependenceValidationError(
                "unsupported_base", "base must declare generational_run"
            )
        if (
            self.base.provider.recording_policy
            is not RecordingPolicy.DETERMINISTIC_FAKE
        ):
            raise PathDependenceValidationError(
                "unsupported_base", "only the deterministic fake provider is supported"
            )
        if (
            type(self.capture_policy) is not str
            or self.capture_policy != PATH_DEPENDENCE_CAPTURE_POLICY
        ):
            raise PathDependenceValidationError(
                "unsupported_base", "unsupported capture_policy"
            )

        object.__setattr__(self, "seeds", _require_int_sequence("seeds", self.seeds))
        if not self.seeds:
            raise PathDependenceValidationError(
                "invalid_seed", "seeds must be non-empty"
            )
        if len(self.seeds) > MAX_SEED_ENTRIES:
            raise PathDependenceValidationError("invalid_seed", "too many seed entries")
        object.__setattr__(
            self,
            "replicates_per_seed",
            _require_int("replicates_per_seed", self.replicates_per_seed, minimum=1),
        )
        if self.replicates_per_seed > MAX_REPLICATES_PER_SEED:
            raise PathDependenceValidationError(
                "invalid_seed", "too many replicates per seed"
            )

        forks = _require_ordered("fork_ticks", self.fork_ticks, Tick)
        if not forks:
            raise PathDependenceValidationError(
                "invalid_fork_window", "fork_ticks must be non-empty"
            )
        if len(forks) > MAX_FORK_TICKS:
            raise PathDependenceValidationError(
                "invalid_fork_window", "too many fork ticks"
            )
        previous = -1
        for fork in forks:
            if fork.value <= previous:
                raise PathDependenceValidationError(
                    "invalid_fork_window", "fork_ticks must be strictly increasing"
                )
            previous = fork.value
        object.__setattr__(self, "fork_ticks", forks)

        _require_tick("horizon_tick", self.horizon_tick)
        if self.horizon_tick.value <= forks[-1].value:
            raise PathDependenceValidationError(
                "invalid_fork_window", "horizon_tick must exceed every fork tick"
            )

        arms = _require_ordered("arms", self.arms, PathDependenceArm)
        if len(arms) < 2:
            raise PathDependenceValidationError(
                "unknown_arm", "at least two arms are required"
            )
        if len(arms) > MAX_ARMS:
            raise PathDependenceValidationError("unknown_arm", "too many arms")
        arm_ids: set[str] = set()
        for arm in arms:
            if arm.arm_id in arm_ids:
                raise PathDependenceValidationError(
                    "unknown_arm", f"duplicate arm_id: {arm.arm_id}"
                )
            arm_ids.add(arm.arm_id)
        object.__setattr__(self, "arms", arms)

        contrasts = _require_ordered("contrasts", self.contrasts, ProtocolContrast)
        if not contrasts:
            raise PathDependenceValidationError(
                "unknown_arm", "at least one contrast is required"
            )
        seen_contrast_ids: set[str] = set()
        seen_pairs: set[tuple[str, str]] = set()
        for contrast in contrasts:
            if contrast.contrast_id in seen_contrast_ids:
                raise PathDependenceValidationError(
                    "duplicate_contrast",
                    f"duplicate contrast_id: {contrast.contrast_id}",
                )
            seen_contrast_ids.add(contrast.contrast_id)
            if (
                contrast.control_arm_id not in arm_ids
                or contrast.treatment_arm_id not in arm_ids
            ):
                raise PathDependenceValidationError(
                    "unknown_arm", "contrast references an unknown arm"
                )
            pair = (contrast.control_arm_id, contrast.treatment_arm_id)
            if pair in seen_pairs:
                raise PathDependenceValidationError(
                    "duplicate_contrast", "duplicate control/treatment pair"
                )
            seen_pairs.add(pair)
        object.__setattr__(self, "contrasts", contrasts)

        object.__setattr__(
            self,
            "max_interventions_per_arm",
            _require_int(
                "max_interventions_per_arm",
                self.max_interventions_per_arm,
                minimum=1,
            ),
        )
        if self.max_interventions_per_arm > MAX_ACTIONS_PER_ARM_FORK:
            raise PathDependenceValidationError(
                "intervention_budget_exceeded",
                "max_interventions_per_arm exceeds the protocol cap",
            )

        fork_values = {fork.value for fork in forks}
        for arm in arms:
            if {entry.fork_tick.value for entry in arm.schedule_by_fork_tick} != (
                fork_values
            ):
                raise PathDependenceValidationError(
                    "invalid_fork_window",
                    "arm schedules must cover exactly the configured fork ticks",
                )
            for schedule in arm.schedule_by_fork_tick:
                if len(schedule.actions) > self.max_interventions_per_arm:
                    raise PathDependenceValidationError(
                        "intervention_budget_exceeded",
                        "arm schedule exceeds max_interventions_per_arm",
                    )
                for action in schedule.actions:
                    if not (
                        schedule.fork_tick.value
                        <= action.tick.value
                        < self.horizon_tick.value
                    ):
                        raise PathDependenceValidationError(
                            "invalid_fork_window",
                            "intervention tick must lie in [F, H)",
                        )

        windows = _require_ordered("windows", self.windows, OutcomeWindow)
        if not windows:
            raise PathDependenceValidationError(
                "invalid_window", "at least one outcome window is required"
            )
        if len(windows) > MAX_SELECTORS_OR_WINDOWS:
            raise PathDependenceValidationError(
                "invalid_window", "too many outcome windows"
            )
        window_ids: set[str] = set()
        for window in windows:
            if window.window_id in window_ids:
                raise PathDependenceValidationError(
                    "invalid_window", f"duplicate window_id: {window.window_id}"
                )
            window_ids.add(window.window_id)
            if window.fork_tick.value not in fork_values:
                raise PathDependenceValidationError(
                    "invalid_window", "window fork_tick is not configured"
                )
            if (
                window.start_tick.value < window.fork_tick.value
                or window.end_tick.value > self.horizon_tick.value
            ):
                raise PathDependenceValidationError(
                    "invalid_window", "window must lie within [F, H]"
                )
        object.__setattr__(self, "windows", windows)

        selectors = _require_ordered("selectors", self.selectors, OutcomeSelector)
        if not selectors:
            raise PathDependenceValidationError(
                "unknown_outcome_selector", "at least one selector is required"
            )
        if len(selectors) > MAX_SELECTORS_OR_WINDOWS:
            raise PathDependenceValidationError(
                "unknown_outcome_selector", "too many selectors"
            )
        selector_keys: set[tuple[str, str]] = set()
        for selector in selectors:
            key = (selector.selector_id, selector.window_id)
            if key in selector_keys:
                raise PathDependenceValidationError(
                    "unknown_outcome_selector",
                    f"duplicate selector_id/window: {selector.selector_id}",
                )
            selector_keys.add(key)
            if selector.window_id not in window_ids:
                raise PathDependenceValidationError(
                    "invalid_window", "selector references an unknown window"
                )
        object.__setattr__(self, "selectors", selectors)

        object.__setattr__(
            self,
            "assignment_seed",
            _require_int("assignment_seed", self.assignment_seed),
        )

        setup = _require_ordered("common_setup", self.common_setup, CommonSetupCommand)
        if len(setup) > MAX_COMMON_SETUP_COMMANDS:
            raise PathDependenceValidationError(
                "intervention_budget_exceeded", "common setup exceeds command cap"
            )
        minimum_fork = forks[0].value
        seen_setup_slots: set[tuple[int, str]] = set()
        for command in setup:
            if command.tick.value >= minimum_fork:
                raise PathDependenceValidationError(
                    "invalid_fork_window",
                    "common setup must complete before the earliest fork tick",
                )
            slot = (command.tick.value, command.actor_id.value)
            if slot in seen_setup_slots:
                raise PathDependenceValidationError(
                    "duplicate_intervention",
                    "common setup must have unique (tick, actor) slots",
                )
            seen_setup_slots.add(slot)
        object.__setattr__(self, "common_setup", setup)

        planned_children = (
            len(self.seeds) * self.replicates_per_seed * len(forks) * len(arms)
        )
        if planned_children > MAX_PLANNED_CHILDREN:
            raise PathDependenceValidationError(
                "intervention_budget_exceeded", "planned child count exceeds cap"
            )

        _LOG.info(
            "path_dependence_spec_built experiment_id=%s seeds=%s replicates=%s "
            "forks=%s arms=%s windows=%s selectors=%s children=%s provider=fake",
            self.experiment_id,
            len(self.seeds),
            self.replicates_per_seed,
            len(forks),
            len(arms),
            len(windows),
            len(selectors),
            planned_children,
        )

    def planned_child_count(self) -> int:
        return (
            len(self.seeds)
            * self.replicates_per_seed
            * len(self.fork_ticks)
            * len(self.arms)
        )


def _require_int_sequence(name: str, value: object) -> tuple[int, ...]:
    if isinstance(value, (set, frozenset)):
        raise PathDependenceValidationError(
            "unordered_collection", f"{name} must be ordered"
        )
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PathDependenceValidationError(
            "invalid_collection", f"{name} must be an ordered sequence"
        )
    return tuple(_require_int(name, entry) for entry in value)


__all__ = [
    "DEFAULT_MAX_ACTIONS_PER_ARM_FORK",
    "MAX_ACTIONS_PER_ARM_FORK",
    "MAX_ARMS",
    "MAX_BOUNDARY_OWNERS",
    "MAX_BOUNDARY_ROWS",
    "MAX_COMMON_SETUP_COMMANDS",
    "MAX_EVIDENCE_CHUNKS_PER_BRANCH",
    "MAX_EVIDENCE_CHUNK_BYTES",
    "MAX_FORK_TICKS",
    "MAX_PLANNED_CHILDREN",
    "MAX_REPLICATES_PER_SEED",
    "MAX_SEED_ENTRIES",
    "MAX_SELECTORS_OR_WINDOWS",
    "MAX_SPEC_DOCUMENT_BYTES",
    "MAX_SPEC_DOCUMENT_DEPTH",
    "PATH_DEPENDENCE_CAPTURE_POLICY",
    "PATH_DEPENDENCE_EXPERIMENT_ID",
    "PATH_DEPENDENCE_SPEC_SCHEMA_VERSION",
    "ArmRole",
    "BranchSlot",
    "CommonSetupCommand",
    "ForkTickSchedule",
    "GiveInterventionAction",
    "InterventionAction",
    "OutcomeDomain",
    "OutcomeSelector",
    "OutcomeWindow",
    "PathDependenceArm",
    "PathDependenceLineage",
    "PathDependenceSpec",
    "PathDependenceValidationError",
    "ProtocolContrast",
    "ScheduledCommandIntervention",
    "WaitInterventionAction",
]
