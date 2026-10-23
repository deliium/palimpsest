"""Treatment-blind slot identities and truthful channel alignment."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from experiments.path_dependence_models import (
    BranchSlot,
    PathDependenceSpec,
    PathDependenceValidationError,
    ScheduledCommandIntervention,
)
from experiments.path_dependence_serialization import (
    action_schedule_digest,
)
from simulation.clock import Tick
from simulation.generational_seeds import GenerationalSeedManifest
from simulation.models import (
    RunId,
    SimulationRunConfig,
)
from simulation.randomness import StreamScope, create_named_stream
from simulation.runner_serialization import runner_config_fingerprint
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.path_dependence_identity"
)

SLOT_DESIGN_VERSION: Final[str] = "path-dependence-slot-design-v1"


class ChannelAlignment(StrEnum):
    """How one seed channel aligns across a branch pair."""

    SHARED = "shared"
    DISTINCT = "distinct"
    ABSENT = "absent"
    RESERVED_IGNORED = "reserved_ignored"
    UNKNOWN = "unknown"


class AlignmentSummary(StrEnum):
    """Conservative collapsed alignment over every included pair."""

    SHARED = "shared"
    MIXED = "mixed"
    DISTINCT = "distinct"
    UNKNOWN = "unknown"


class ChannelPairRef(StrEnum):
    """Coarse reference for a compared branch pair."""

    CONTROL = "control"
    TREATMENT = "treatment"


@dataclass(frozen=True, slots=True)
class SlotAssignment:
    """One predeclared treatment assignment for an opaque slot."""

    slot_ordinal: int
    arm_id: str

    def __post_init__(self) -> None:
        if isinstance(self.slot_ordinal, bool) or type(self.slot_ordinal) is not int:
            raise PathDependenceValidationError(
                "assignment_identity_mismatch", "invalid slot ordinal"
            )
        if self.slot_ordinal < 0:
            raise PathDependenceValidationError(
                "assignment_identity_mismatch", "invalid slot ordinal"
            )
        object.__setattr__(
            self, "arm_id", require_stable_id("arm_id", self.arm_id)
        )


@dataclass(frozen=True, slots=True)
class BranchChannelAlignment:
    """Per-channel status for one branch pair."""

    channels: tuple[tuple[str, ChannelAlignment], ...]

    def __post_init__(self) -> None:
        if isinstance(self.channels, (set, frozenset, Mapping)):
            raise PathDependenceValidationError(
                "assignment_identity_mismatch", "channels must be ordered"
            )
        channels = tuple(self.channels)
        seen: set[str] = set()
        for name, alignment in channels:
            if type(name) is not str or type(alignment) is not ChannelAlignment:
                raise PathDependenceValidationError(
                    "assignment_identity_mismatch", "invalid channel entry"
                )
            if name in seen:
                raise PathDependenceValidationError(
                    "assignment_identity_mismatch", "duplicate channel"
                )
            seen.add(name)
        object.__setattr__(self, "channels", channels)

    def channel(self, name: str) -> ChannelAlignment:
        for channel_name, alignment in self.channels:
            if channel_name == name:
                return alignment
        return ChannelAlignment.UNKNOWN

    @property
    def summary(self) -> AlignmentSummary:
        values = {alignment for _, alignment in self.channels}
        if ChannelAlignment.UNKNOWN in values:
            return AlignmentSummary.UNKNOWN
        if values <= {
            ChannelAlignment.SHARED,
            ChannelAlignment.ABSENT,
            ChannelAlignment.RESERVED_IGNORED,
        }:
            return AlignmentSummary.SHARED
        if ChannelAlignment.DISTINCT in values and (
            values
            & {
                ChannelAlignment.SHARED,
                ChannelAlignment.ABSENT,
                ChannelAlignment.RESERVED_IGNORED,
            }
        ):
            return AlignmentSummary.MIXED
        if values == {ChannelAlignment.DISTINCT}:
            return AlignmentSummary.DISTINCT
        return AlignmentSummary.UNKNOWN


def _canonical(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def slot_design_payload(spec: PathDependenceSpec) -> dict[str, object]:
    """Label-blind design payload shared by identities and assignment streams."""
    if type(spec) is not PathDependenceSpec:
        raise TypeError("slot_design_payload requires PathDependenceSpec")
    schedule = []
    for arm in spec.arms:
        entries = []
        for fork_schedule in arm.schedule_by_fork_tick:
            entries.append(
                {
                    "fork_tick": fork_schedule.fork_tick.value,
                    "schedule_digest": _actions_digest(fork_schedule.actions),
                }
            )
        schedule.append(entries)
    return {
        "version": SLOT_DESIGN_VERSION,
        "base_config_fingerprint": runner_config_fingerprint(spec.base),
        "seeds": list(spec.seeds),
        "replicates_per_seed": spec.replicates_per_seed,
        "fork_ticks": [tick.value for tick in spec.fork_ticks],
        "horizon_tick": spec.horizon_tick.value,
        "arm_schedules": schedule,
        "assignment_seed": spec.assignment_seed,
        "common_setup": [
            {
                "actor_id": command.actor_id.value,
                "tick": command.tick.value,
                "command_kind": command.command.kind,
            }
            for command in spec.common_setup
        ],
    }


def slot_design_fingerprint(spec: PathDependenceSpec) -> str:
    """Canonical label-blind design identity."""
    return _canonical(slot_design_payload(spec))


def _actions_digest(
    actions: tuple[ScheduledCommandIntervention, ...]
) -> str:
    return action_schedule_digest(actions)


def _assignment_config(spec: PathDependenceSpec) -> SimulationRunConfig:
    return SimulationRunConfig(
        seed=spec.assignment_seed,
        physical_rules=spec.base.resolve_physical_rules(),
        derivation_version=spec.base.derivation_version,
        stochastic_identity=spec.base.stochastic_identity,
    )


def _slot_run_id(
    *,
    design_fingerprint: str,
    parent_identity: str,
    numeric_seed: int,
    seed_ordinal: int,
    replicate: int,
    fork_tick: int,
    slot_ordinal: int,
) -> RunId:
    material = _canonical(
        {
            "version": SLOT_DESIGN_VERSION,
            "design": design_fingerprint,
            "parent": parent_identity,
            "numeric_seed": numeric_seed,
            "seed_ordinal": seed_ordinal,
            "replicate": replicate,
            "fork_tick": fork_tick,
            "slot_ordinal": slot_ordinal,
        }
    )
    return RunId(f"pd-slot-{material[:48]}")


def build_branch_slots(
    spec: PathDependenceSpec,
    parent_identity: str,
    fork_tick: Tick,
) -> tuple[BranchSlot, ...]:
    """Build treatment-blind slots for one parent boundary."""
    if type(spec) is not PathDependenceSpec:
        raise TypeError("build_branch_slots requires PathDependenceSpec")
    parent_identity = require_stable_id("parent_identity", parent_identity)
    if type(fork_tick) is not Tick or fork_tick not in spec.fork_ticks:
        raise PathDependenceValidationError(
            "invalid_fork_window", "fork_tick is not configured"
        )
    design = slot_design_fingerprint(spec)
    fork_index = spec.fork_ticks.index(fork_tick)
    arms_per_block = len(spec.arms)
    block_size = spec.replicates_per_seed * arms_per_block
    slots: list[BranchSlot] = []
    for seed_ordinal, numeric_seed in enumerate(spec.seeds):
        for replicate in range(spec.replicates_per_seed):
            for arm_position in range(arms_per_block):
                slot_ordinal = (
                    (seed_ordinal * block_size + replicate * arms_per_block)
                    + arm_position
                    + fork_index * len(spec.seeds) * block_size
                )
                slots.append(
                    BranchSlot(
                        slot_ordinal=slot_ordinal,
                        numeric_seed=numeric_seed,
                        seed_ordinal=seed_ordinal,
                        replicate=replicate,
                        fork_tick=fork_tick,
                        child_run_id=_slot_run_id(
                            design_fingerprint=design,
                            parent_identity=parent_identity,
                            numeric_seed=numeric_seed,
                            seed_ordinal=seed_ordinal,
                            replicate=replicate,
                            fork_tick=fork_tick.value,
                            slot_ordinal=slot_ordinal,
                        ).value,
                    )
                )
    return tuple(slots)


def assign_branch_arms(
    spec: PathDependenceSpec,
    slots: tuple[BranchSlot, ...],
    *,
    parent_identity: str,
) -> tuple[SlotAssignment, ...]:
    """Permute arm IDs over treatment-blind slots before outcomes exist."""
    if type(spec) is not PathDependenceSpec:
        raise TypeError("assign_branch_arms requires PathDependenceSpec")
    parent_identity = require_stable_id("parent_identity", parent_identity)
    design = slot_design_fingerprint(spec)
    assignment_config = _assignment_config(spec)
    by_block: dict[tuple[int, int, int], list[BranchSlot]] = {}
    for slot in slots:
        key = (slot.fork_tick.value, slot.seed_ordinal, slot.replicate)
        by_block.setdefault(key, []).append(slot)
    assigned: list[SlotAssignment] = []
    arm_ids = tuple(arm.arm_id for arm in spec.arms)
    for (fork_tick, seed_ordinal, replicate), block in sorted(by_block.items()):
        if len(block) != len(arm_ids):
            raise PathDependenceValidationError(
                "assignment_identity_mismatch", "block does not cover every arm"
            )
        scope = StreamScope(
            namespace="path_dependence_assignment",
            names=(
                design,
                parent_identity,
                str(spec.assignment_seed),
                str(fork_tick),
                str(seed_ordinal),
                str(replicate),
            ),
        )
        rng = create_named_stream(assignment_config, scope)
        shuffled = list(arm_ids)
        rng.shuffle(shuffled)
        ordered = sorted(block, key=lambda item: item.slot_ordinal)
        for slot, arm_id in zip(ordered, shuffled, strict=True):
            assigned.append(
                SlotAssignment(slot_ordinal=slot.slot_ordinal, arm_id=arm_id)
            )
    return tuple(sorted(assigned, key=lambda item: item.slot_ordinal))


def _classify_channel(left: object, right: object) -> ChannelAlignment:
    from simulation.generational_seeds import SeedChannelLineage

    if type(left) is not SeedChannelLineage or type(right) is not SeedChannelLineage:
        return ChannelAlignment.UNKNOWN
    if left.algorithm_version != right.algorithm_version:
        return ChannelAlignment.UNKNOWN
    if left.namespace != right.namespace:
        return ChannelAlignment.UNKNOWN
    if left.scope_fields != right.scope_fields:
        return ChannelAlignment.UNKNOWN
    if (
        left.draw_usage == "reserved_ignored"
        and right.draw_usage == "reserved_ignored"
    ):
        return ChannelAlignment.RESERVED_IGNORED
    if left.draw_usage == "absent" and right.draw_usage == "absent":
        return ChannelAlignment.ABSENT
    if left.identity_selector == "stochastic_identity" and (
        right.identity_selector == "stochastic_identity"
    ):
        return ChannelAlignment.SHARED
    if left.identity_selector != right.identity_selector:
        return ChannelAlignment.UNKNOWN
    if left.identity_selector == "durable_run_id":
        return ChannelAlignment.DISTINCT
    return ChannelAlignment.SHARED


def compare_branch_channel_manifests(
    left: GenerationalSeedManifest, right: GenerationalSeedManifest
) -> BranchChannelAlignment:
    """Compare every channel in two manifests."""
    if type(left) is not GenerationalSeedManifest or type(
        right
    ) is not GenerationalSeedManifest:
        raise TypeError("compare_branch_channel_manifests requires manifests")
    left_channels = {channel.name: channel for channel in left.channels}
    right_channels = {channel.name: channel for channel in right.channels}
    names = sorted(set(left_channels) | set(right_channels))
    return BranchChannelAlignment(
        channels=tuple(
            (
                name,
                _classify_channel(
                    left_channels.get(name), right_channels.get(name)
                ),
            )
            for name in names
        )
    )


def summarize_branch_channel_alignment(
    pairs: Sequence[tuple[GenerationalSeedManifest, GenerationalSeedManifest]],
) -> AlignmentSummary:
    """Collapse every included pair conservatively, never only the first."""
    if isinstance(pairs, (str, bytes)) or not isinstance(pairs, Sequence):
        raise TypeError("pairs must be an ordered sequence")
    if not pairs:
        return AlignmentSummary.UNKNOWN
    summaries: list[AlignmentSummary] = []
    for left, right in pairs:
        summaries.append(
            compare_branch_channel_manifests(left, right).summary
        )
    if AlignmentSummary.UNKNOWN in summaries:
        return AlignmentSummary.UNKNOWN
    if all(item is AlignmentSummary.SHARED for item in summaries):
        return AlignmentSummary.SHARED
    if all(item is AlignmentSummary.DISTINCT for item in summaries):
        return AlignmentSummary.DISTINCT
    if AlignmentSummary.DISTINCT in summaries or AlignmentSummary.MIXED in summaries:
        return AlignmentSummary.MIXED
    return AlignmentSummary.UNKNOWN


__all__ = [
    "SLOT_DESIGN_VERSION",
    "AlignmentSummary",
    "BranchChannelAlignment",
    "ChannelAlignment",
    "ChannelPairRef",
    "SlotAssignment",
    "assign_branch_arms",
    "build_branch_slots",
    "compare_branch_channel_manifests",
    "slot_design_fingerprint",
    "slot_design_payload",
    "summarize_branch_channel_alignment",
]
