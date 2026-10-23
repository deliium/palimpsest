"""Path-dependence recipe validation and strict codec contracts."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import cast

import pytest

from agents.models import AgentId
from experiments.institutionalization_scenario import institutionalization_scenario
from experiments.path_dependence_models import (
    MAX_COMMON_SETUP_COMMANDS,
    ArmRole,
    CommonSetupCommand,
    ForkTickSchedule,
    GiveInterventionAction,
    OutcomeDomain,
    OutcomeSelector,
    OutcomeWindow,
    PathDependenceArm,
    PathDependenceSpec,
    PathDependenceValidationError,
    ProtocolContrast,
    ScheduledCommandIntervention,
    WaitInterventionAction,
)
from experiments.path_dependence_serialization import (
    PathDependenceSerializationError,
    action_schedule_digest,
    decode_path_dependence_spec,
    encode_path_dependence_spec,
    encode_path_dependence_spec_document,
    path_dependence_spec_fingerprint,
)
from simulation.clock import Tick
from simulation.generational_models import GenerationalRunSpec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    ExactReproducibilityMode,
    RecordingPolicy,
    RunnerStopPolicy,
    SimulationRunnerConfig,
)
from world.actions import Search, Wait
from world.identifiers import EntityId


def _base(*, schema_version: str = RUNNER_SCHEMA_VERSION_V55) -> SimulationRunnerConfig:
    config = next(
        condition.runner_config
        for condition in institutionalization_scenario(
            seed=23, max_ticks=8
        ).conditions
        if condition.condition_id == "bf-institution-on"
    )
    return replace(
        config,
        schema_version=schema_version,
        stop_policy=RunnerStopPolicy(
            max_ticks=8, stop_on_all_agents_terminal=False
        ),
        generational_run=(
            GenerationalRunSpec(max_generation_index=2)
            if schema_version == RUNNER_SCHEMA_VERSION_V55
            else None
        ),
        mentorship=None,
        developmental_learning=None,
        dependency_care=None,
        kinship=None,
        cultural_feature_provenance=None,
        collective_projects=None,
        public_goods=None,
        structured_commitments=None,
        subjective_valuation=None,
        resource_exchange_profile=None,
        generational_narratives=None,
        v3_capability_flags=replace(
            config.v3_capability_flags,
            kinship_inheritance=False,
            cultural_historical_memory=False,
        ),
    )


def _arm(
    arm_id: str,
    role: ArmRole,
    schedules: tuple[ForkTickSchedule, ...],
) -> PathDependenceArm:
    return PathDependenceArm(
        arm_id=arm_id,
        label_code=arm_id.upper(),
        role=role,
        schedule_by_fork_tick=schedules,
    )


def _windows(
    fork_tick: Tick | None = None, horizon: Tick | None = None
) -> tuple[OutcomeWindow, ...]:
    fork_tick = Tick(2) if fork_tick is None else fork_tick
    horizon = Tick(8) if horizon is None else horizon
    return (OutcomeWindow("win", fork_tick, fork_tick, horizon),)


def _selectors() -> tuple[OutcomeSelector, ...]:
    return (
        OutcomeSelector("norms.active_beliefs", OutcomeDomain.NORMS, "win"),
        OutcomeSelector(
            "cooperation.applied_rate", OutcomeDomain.COOPERATION, "win"
        ),
    )


def _spec(**overrides: object) -> PathDependenceSpec:
    fork = Tick(2)
    values: dict[str, object] = {
        "base": _base(),
        "seeds": (7,),
        "replicates_per_seed": 1,
        "fork_ticks": (fork,),
        "horizon_tick": Tick(8),
        "arms": (
            _arm("control", ArmRole.CONTROL, (ForkTickSchedule(fork, ()),)),
            _arm(
                "share",
                ArmRole.TREATMENT,
                (
                    ForkTickSchedule(
                        fork,
                        (
                            ScheduledCommandIntervention(
                                "share-1",
                                AgentId("agent-1"),
                                Tick(3),
                                GiveInterventionAction(
                                    EntityId("item-food"),
                                    EntityId("body-2"),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        "contrasts": (ProtocolContrast("share-vs-control", "control", "share"),),
        "windows": _windows(),
        "selectors": _selectors(),
        "assignment_seed": 11,
        "common_setup": (),
        "max_interventions_per_arm": 4,
    }
    values.update(overrides)
    return PathDependenceSpec(**values)  # type: ignore[arg-type]


def test_codec_round_trip_and_fingerprint_are_canonical() -> None:
    spec = _spec()
    payload = encode_path_dependence_spec(spec)
    assert decode_path_dependence_spec(payload) == spec
    assert encode_path_dependence_spec(decode_path_dependence_spec(payload)) == payload
    assert path_dependence_spec_fingerprint(spec) == path_dependence_spec_fingerprint(
        decode_path_dependence_spec(payload)
    )
    assert action_schedule_digest(()) == action_schedule_digest(())


def test_documented_scenario_spec_round_trips_with_exact_top_level_keys() -> None:
    from experiments.path_dependence_scenario import historical_contingency_scenario

    spec = historical_contingency_scenario(seed=23, profile="smoke")
    document = encode_path_dependence_spec_document(spec)
    assert set(document) == {
        "schema_version",
        "experiment_id",
        "base",
        "seeds",
        "replicates_per_seed",
        "fork_ticks",
        "horizon_tick",
        "arms",
        "contrasts",
        "windows",
        "selectors",
        "assignment_seed",
        "max_interventions_per_arm",
        "common_setup",
        "capture_policy",
    }
    payload = json.dumps(
        document, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode()
    assert path_dependence_spec_fingerprint(
        decode_path_dependence_spec(payload)
    ) == path_dependence_spec_fingerprint(spec)


def test_codec_rejects_unknown_and_missing_keys() -> None:
    document = encode_path_dependence_spec_document(_spec())
    document["retry_policy"] = {"max_attempts": 2}
    with pytest.raises(PathDependenceSerializationError, match="invalid_fields"):
        decode_path_dependence_spec(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        )

    document = encode_path_dependence_spec_document(_spec())
    del document["assignment_seed"]
    with pytest.raises(PathDependenceSerializationError, match="missing_field"):
        decode_path_dependence_spec(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        )


def test_codec_rejects_nested_unknown_keys_and_duplicate_keys() -> None:
    document = encode_path_dependence_spec_document(_spec())
    arms = cast(list[dict[str, object]], document["arms"])
    arms[0]["retry_on_failure"] = True
    with pytest.raises(PathDependenceSerializationError, match="invalid_fields"):
        decode_path_dependence_spec(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        )

    payload = json.dumps(
        encode_path_dependence_spec_document(_spec()),
        sort_keys=True,
        separators=(",", ":"),
    ).replace('"assignment_seed":11', '"assignment_seed":11,"assignment_seed":12')
    with pytest.raises(PathDependenceSerializationError, match="duplicate_key"):
        decode_path_dependence_spec(payload.encode())


def test_codec_rejects_boolean_ticks_and_seeds() -> None:
    document = encode_path_dependence_spec_document(_spec())
    document["fork_ticks"] = [True]
    with pytest.raises(PathDependenceSerializationError, match="invalid_int"):
        decode_path_dependence_spec(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        )

    document = encode_path_dependence_spec_document(_spec())
    document["seeds"] = [True]
    with pytest.raises(PathDependenceSerializationError, match="invalid_int"):
        decode_path_dependence_spec(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        )


def test_duplicate_arm_and_action_ids_are_rejected() -> None:
    fork = Tick(2)
    with pytest.raises(PathDependenceValidationError, match="duplicate_intervention"):
        ForkTickSchedule(
            fork,
            (
                ScheduledCommandIntervention(
                    "same", AgentId("agent-1"), Tick(3), WaitInterventionAction()
                ),
                ScheduledCommandIntervention(
                    "same", AgentId("agent-2"), Tick(3), WaitInterventionAction()
                ),
            ),
        )

    with pytest.raises(PathDependenceValidationError, match="duplicate_intervention"):
        ForkTickSchedule(
            fork,
            (
                ScheduledCommandIntervention(
                    "a", AgentId("agent-1"), Tick(3), WaitInterventionAction()
                ),
                ScheduledCommandIntervention(
                    "b", AgentId("agent-1"), Tick(3), WaitInterventionAction()
                ),
            ),
        )

    with pytest.raises(PathDependenceValidationError, match="unknown_arm"):
        _spec(
            arms=(
                _arm("control", ArmRole.CONTROL, (ForkTickSchedule(fork, ()),)),
                _arm("control", ArmRole.TREATMENT, (ForkTickSchedule(fork, ()),)),
            )
        )


def test_missing_contrast_arm_is_rejected() -> None:
    with pytest.raises(PathDependenceValidationError, match="unknown_arm"):
        _spec(
            contrasts=(ProtocolContrast("bad", "control", "missing"),),
        )


def test_actions_outside_fork_window_are_rejected() -> None:
    fork = Tick(2)
    early = ForkTickSchedule(
        fork,
        (
            ScheduledCommandIntervention(
                "early", AgentId("agent-1"), Tick(1), WaitInterventionAction()
            ),
        ),
    )
    with pytest.raises(PathDependenceValidationError, match="invalid_fork_window"):
        _spec(
            arms=(
                _arm("control", ArmRole.CONTROL, (ForkTickSchedule(fork, ()),)),
                _arm("share", ArmRole.TREATMENT, (early,)),
            )
        )

    late = ForkTickSchedule(
        fork,
        (
            ScheduledCommandIntervention(
                "late", AgentId("agent-1"), Tick(8), WaitInterventionAction()
            ),
        ),
    )
    with pytest.raises(PathDependenceValidationError, match="invalid_fork_window"):
        _spec(
            arms=(
                _arm("control", ArmRole.CONTROL, (ForkTickSchedule(fork, ()),)),
                _arm("share", ArmRole.TREATMENT, (late,)),
            )
        )


def test_intervention_budget_is_bounded() -> None:
    fork = Tick(2)
    actions = tuple(
        ScheduledCommandIntervention(
            f"a-{index}", AgentId(f"agent-{index}"), Tick(3), WaitInterventionAction()
        )
        for index in range(5)
    )
    with pytest.raises(
        PathDependenceValidationError, match="intervention_budget_exceeded"
    ):
        _spec(
            arms=(
                _arm("control", ArmRole.CONTROL, (ForkTickSchedule(fork, ()),)),
                _arm("share", ArmRole.TREATMENT, (ForkTickSchedule(fork, actions),)),
            )
        )

    with pytest.raises(
        PathDependenceValidationError, match="intervention_budget_exceeded"
    ):
        _spec(max_interventions_per_arm=17)


def test_common_setup_tags_and_duplicate_slots() -> None:
    with pytest.raises(PathDependenceValidationError, match="unsupported_intervention"):
        CommonSetupCommand(AgentId("agent-1"), Tick(0), Search())

    with pytest.raises(PathDependenceValidationError, match="duplicate_intervention"):
        _spec(
            common_setup=(
                CommonSetupCommand(AgentId("agent-1"), Tick(0), Wait()),
                CommonSetupCommand(AgentId("agent-1"), Tick(0), Wait()),
            )
        )


def test_common_setup_must_end_before_earliest_fork() -> None:
    with pytest.raises(PathDependenceValidationError, match="invalid_fork_window"):
        _spec(
            common_setup=(
                CommonSetupCommand(AgentId("agent-1"), Tick(2), Wait()),
            )
        )


def test_f_zero_requires_empty_common_setup() -> None:
    with pytest.raises(PathDependenceValidationError, match="invalid_fork_window"):
        _spec(
            fork_ticks=(Tick(0),),
            windows=_windows(Tick(0)),
            common_setup=(
                CommonSetupCommand(AgentId("agent-1"), Tick(0), Wait()),
            ),
            arms=(
                _arm("control", ArmRole.CONTROL, (ForkTickSchedule(Tick(0), ()),)),
                _arm("share", ArmRole.TREATMENT, (ForkTickSchedule(Tick(0), ()),)),
            ),
        )


def test_common_setup_cap_is_enforced() -> None:
    fork = Tick(MAX_COMMON_SETUP_COMMANDS + 10)
    commands = tuple(
        CommonSetupCommand(AgentId("agent-1"), Tick(index), Wait())
        for index in range(MAX_COMMON_SETUP_COMMANDS + 1)
    )
    with pytest.raises(
        PathDependenceValidationError, match="intervention_budget_exceeded"
    ):
        _spec(
            fork_ticks=(fork,),
            horizon_tick=Tick(fork.value + 10),
            windows=(OutcomeWindow("win", fork, fork, Tick(fork.value + 10)),),
            common_setup=commands,
            arms=(
                _arm("control", ArmRole.CONTROL, (ForkTickSchedule(fork, ()),)),
                _arm("share", ArmRole.TREATMENT, (ForkTickSchedule(fork, ()),)),
            ),
        )


def test_single_and_duplicate_numeric_seeds_are_accepted() -> None:
    assert _spec(seeds=(7,)).planned_child_count() == 2
    duplicate = _spec(seeds=(7, 7))
    assert duplicate.seeds == (7, 7)
    assert duplicate.planned_child_count() == 4


def test_unsupported_base_configuration_fails_closed() -> None:
    with pytest.raises(PathDependenceValidationError, match="unsupported_base"):
        _spec(
            base=replace(
                _base(),
                provider=replace(
                    _base().provider,
                    recording_policy=RecordingPolicy.LIVE,
                    exact_reproducibility=ExactReproducibilityMode.NOT_REQUIRED,
                ),
            )
        )
    document = encode_path_dependence_spec_document(_spec())
    base = cast(dict[str, object], document["base"])
    base["schema_version"] = "runner-config-v54"
    with pytest.raises(PathDependenceSerializationError, match="unsupported_base"):
        decode_path_dependence_spec(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        )


def test_two_fork_ticks_stay_one_seed_block_and_cover_exactly() -> None:
    first, second = Tick(2), Tick(4)
    spec = _spec(
        fork_ticks=(first, second),
        windows=(
            OutcomeWindow("win-2", first, first, Tick(8)),
            OutcomeWindow("win-4", second, second, Tick(8)),
        ),
        selectors=(
            OutcomeSelector("norms.active_beliefs", OutcomeDomain.NORMS, "win-2"),
            OutcomeSelector("norms.active_beliefs", OutcomeDomain.NORMS, "win-4"),
        ),
        arms=(
            _arm(
                "control",
                ArmRole.CONTROL,
                (ForkTickSchedule(first, ()), ForkTickSchedule(second, ())),
            ),
            _arm(
                "share",
                ArmRole.TREATMENT,
                (
                    ForkTickSchedule(first, ()),
                    ForkTickSchedule(
                        second,
                        (
                            ScheduledCommandIntervention(
                                "wait-4",
                                AgentId("agent-1"),
                                Tick(5),
                                WaitInterventionAction(),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    assert spec.fork_ticks == (first, second)
    assert spec.planned_child_count() == 4
    assert spec.planned_child_count() == (
        len(spec.seeds)
        * spec.replicates_per_seed
        * len(spec.fork_ticks)
        * len(spec.arms)
    )


def test_arm_schedules_must_cover_every_fork_tick_exactly() -> None:
    fork = Tick(2)
    with pytest.raises(PathDependenceValidationError, match="invalid_fork_window"):
        _spec(
            arms=(
                _arm("control", ArmRole.CONTROL, (ForkTickSchedule(fork, ()),)),
                _arm("share", ArmRole.TREATMENT, (ForkTickSchedule(fork, ()),)),
            ),
            fork_ticks=(fork, Tick(4)),
            windows=(
                OutcomeWindow("win-2", fork, fork, Tick(8)),
                OutcomeWindow("win-4", Tick(4), Tick(4), Tick(8)),
            ),
            selectors=(
                OutcomeSelector(
                    "norms.active_beliefs", OutcomeDomain.NORMS, "win-2"
                ),
                OutcomeSelector(
                    "norms.active_beliefs", OutcomeDomain.NORMS, "win-4"
                ),
            ),
        )
