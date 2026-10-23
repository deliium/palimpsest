"""Label-blind slot identity, assignment, and channel alignment proofs."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.generational_comparison_base import generational_comparison_base
from experiments.path_dependence_identity import (
    AlignmentSummary,
    ChannelAlignment,
    assign_branch_arms,
    build_branch_slots,
    compare_branch_channel_manifests,
    slot_design_fingerprint,
    summarize_branch_channel_alignment,
)
from experiments.path_dependence_models import (
    ArmRole,
    ForkTickSchedule,
    PathDependenceArm,
    PathDependenceSpec,
    ScheduledCommandIntervention,
    WaitInterventionAction,
)
from simulation.clock import Tick
from simulation.generational_seeds import (
    GenerationalSeedManifest,
    build_generational_seed_manifest,
)
from simulation.models import RunId
from tests.unit.test_path_dependence_models import _spec

pytestmark = pytest.mark.unit


def _renamed(spec: PathDependenceSpec) -> PathDependenceSpec:
    mapping = {
        arm.arm_id: f"renamed-{index}" for index, arm in enumerate(spec.arms)
    }
    arms = tuple(
        replace(arm, arm_id=mapping[arm.arm_id], label_code=f"LABEL-{index}")
        for index, arm in enumerate(spec.arms)
    )
    contrasts = tuple(
        replace(
            contrast,
            control_arm_id=mapping[contrast.control_arm_id],
            treatment_arm_id=mapping[contrast.treatment_arm_id],
        )
        for contrast in spec.contrasts
    )
    return replace(spec, arms=arms, contrasts=contrasts)


def test_slot_ids_are_label_blind_and_unique() -> None:
    spec = _spec()
    renamed = _renamed(spec)
    assert slot_design_fingerprint(spec) == slot_design_fingerprint(renamed)
    parent = "parent-run"
    slots = build_branch_slots(spec, parent, Tick(2))
    renamed_slots = build_branch_slots(renamed, parent, Tick(2))
    assert [slot.child_run_id for slot in slots] == [
        slot.child_run_id for slot in renamed_slots
    ]
    assert len(slots) == len(spec.seeds) * spec.replicates_per_seed * len(spec.arms)
    assert len({slot.child_run_id for slot in slots}) == len(slots)
    assert [slot.slot_ordinal for slot in slots] == sorted(
        slot.slot_ordinal for slot in slots
    )


def test_assignment_is_reproducible_and_order_independent() -> None:
    spec = _spec(seeds=(7, 8), replicates_per_seed=2)
    slots = build_branch_slots(spec, "parent-run", Tick(2))
    first = assign_branch_arms(spec, slots, parent_identity="parent-run")
    second = assign_branch_arms(
        spec, tuple(reversed(slots)), parent_identity="parent-run"
    )
    assert first == second
    assert len(first) == len(slots)
    assert {entry.arm_id for entry in first} == {arm.arm_id for arm in spec.arms}
    for seed_ordinal in range(len(spec.seeds)):
        for replicate in range(spec.replicates_per_seed):
            block = [
                entry
                for entry in first
                if any(
                    slot.slot_ordinal == entry.slot_ordinal
                    and slot.seed_ordinal == seed_ordinal
                    and slot.replicate == replicate
                    for slot in slots
                )
            ]
            assert {entry.arm_id for entry in block} == {
                arm.arm_id for arm in spec.arms
            }


def test_distinct_fork_ticks_get_independent_slots() -> None:
    first, second = Tick(2), Tick(4)
    spec = _spec(
        fork_ticks=(first, second),
        windows=(
            __import__(
                "experiments.path_dependence_models",
                fromlist=["OutcomeWindow"],
            ).OutcomeWindow("win-2", first, first, Tick(8)),
            __import__(
                "experiments.path_dependence_models",
                fromlist=["OutcomeWindow"],
            ).OutcomeWindow("win-4", second, second, Tick(8)),
        ),
        selectors=(
            __import__(
                "experiments.path_dependence_models",
                fromlist=["OutcomeDomain", "OutcomeSelector"],
            ).OutcomeSelector(
                "norms.active_beliefs",
                __import__(
                    "experiments.path_dependence_models",
                    fromlist=["OutcomeDomain"],
                ).OutcomeDomain.NORMS,
                "win-2",
            ),
            __import__(
                "experiments.path_dependence_models",
                fromlist=["OutcomeDomain", "OutcomeSelector"],
            ).OutcomeSelector(
                "norms.active_beliefs",
                __import__(
                    "experiments.path_dependence_models",
                    fromlist=["OutcomeDomain"],
                ).OutcomeDomain.NORMS,
                "win-4",
            ),
        ),
        arms=(
            PathDependenceArm(
                "control",
                "CONTROL",
                ArmRole.CONTROL,
                (ForkTickSchedule(first, ()), ForkTickSchedule(second, ())),
            ),
            PathDependenceArm(
                "share",
                "SHARE",
                ArmRole.TREATMENT,
                (
                    ForkTickSchedule(first, ()),
                    ForkTickSchedule(
                        second,
                        (
                            ScheduledCommandIntervention(
                                "wait-4",
                                __import__(
                                    "agents.models", fromlist=["AgentId"]
                                ).AgentId("agent-1"),
                                Tick(5),
                                WaitInterventionAction(),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    first_slots = build_branch_slots(spec, "parent-run", first)
    second_slots = build_branch_slots(spec, "parent-run", second)
    assert {slot.child_run_id for slot in first_slots}.isdisjoint(
        slot.child_run_id for slot in second_slots
    )


def test_channel_alignment_uses_every_pair_and_conservative_summary() -> None:
    config = generational_comparison_base(seed=23, max_ticks=8)
    left = build_generational_seed_manifest(config, RunId("left-run"))
    right = build_generational_seed_manifest(config, RunId("right-run"))
    alignment = compare_branch_channel_manifests(left, right)
    assert alignment.channel("demography") is ChannelAlignment.RESERVED_IGNORED
    assert alignment.channel("world") is ChannelAlignment.SHARED
    assert summarize_branch_channel_alignment([(left, right)]) in {
        AlignmentSummary.SHARED,
        AlignmentSummary.MIXED,
    }

    # Make only the second pair run-ID scoped; it must not be hidden by the
    # first pair's shared summary.
    def _run_scoped(
        manifest: GenerationalSeedManifest,
    ) -> GenerationalSeedManifest:
        return replace(
            manifest,
            channels=tuple(
                replace(channel, identity_selector="durable_run_id")
                if channel.name == "world"
                else channel
                for channel in manifest.channels
            ),
        )

    assert summarize_branch_channel_alignment(
        [(left, right), (_run_scoped(left), _run_scoped(right))]
    ) is AlignmentSummary.MIXED
