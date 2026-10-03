"""Cognitive budget contracts, presets, and tick ledger accounting."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.cognition.budget import (
    COGNITIVE_BUDGET_POLICY_VERSION,
    BudgetDimension,
    BudgetExhaustedReason,
    CognitiveBudgetAudit,
    CognitiveBudgetPolicy,
    TickBudgetLedger,
    high_cost_budget_limits,
    low_cost_budget_limits,
    policy_from_limits,
)
from agents.cognition.configuration import CognitionBudgetMode, CognitionLoopConfig
from agents.models import AgentId

_CATALOG_A_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runner_configs"
    / "catalog_a_condition_v2.json"
)


def _owner() -> AgentId:
    return AgentId("alice")


def test_budget_mode_values() -> None:
    assert CognitionBudgetMode.DISABLED.value == "disabled"
    assert CognitionBudgetMode.ENFORCED.value == "enforced"


def test_policy_version_and_presets() -> None:
    low = low_cost_budget_limits()
    high = high_cost_budget_limits()
    assert low.version == COGNITIVE_BUDGET_POLICY_VERSION
    assert high.version == COGNITIVE_BUDGET_POLICY_VERSION
    assert low.max_llm_calls_per_tick == 0
    assert low.max_tokens_per_tick == 0
    assert low.max_imagination_branches == 2
    assert low.max_planning_depth == 1
    assert low.max_recalled_memories == 2
    assert low.max_tom_targets == 1
    assert low.reflection_interval_ticks == 16
    assert low.timeout_seconds == 0.0
    assert high.max_llm_calls_per_tick == 4
    assert high.max_tokens_per_tick == 2048
    assert high.max_imagination_branches == 16
    assert high.max_planning_depth == 3
    assert high.max_recalled_memories == 12
    assert high.max_tom_targets == 6
    assert high.reflection_interval_ticks == 8
    assert high.timeout_seconds == 0.0


def test_zero_llm_and_token_caps_are_legal() -> None:
    policy = CognitiveBudgetPolicy(
        max_llm_calls_per_tick=0,
        max_tokens_per_tick=0,
        max_imagination_branches=1,
        max_planning_depth=1,
        max_recalled_memories=1,
        max_tom_targets=0,
        reflection_interval_ticks=1,
        timeout_seconds=0.0,
    )
    assert policy.max_llm_calls_per_tick == 0
    assert policy.max_tom_targets == 0


def test_policy_rejects_non_finite_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        CognitiveBudgetPolicy(timeout_seconds=float("nan"))
    with pytest.raises(ValueError, match="timeout_seconds"):
        CognitiveBudgetPolicy(timeout_seconds=-1.0)
    with pytest.raises(ValueError, match="clock"):
        CognitiveBudgetPolicy(clock=object())  # type: ignore[arg-type]


def test_policy_rejects_non_positive_branch_depth_memory_reflection() -> None:
    with pytest.raises(ValueError, match="max_imagination_branches"):
        CognitiveBudgetPolicy(max_imagination_branches=0)
    with pytest.raises(ValueError, match="max_planning_depth"):
        CognitiveBudgetPolicy(max_planning_depth=0)
    with pytest.raises(ValueError, match="max_recalled_memories"):
        CognitiveBudgetPolicy(max_recalled_memories=0)
    with pytest.raises(ValueError, match="reflection_interval_ticks"):
        CognitiveBudgetPolicy(reflection_interval_ticks=0)


def test_config_disabled_clears_policy() -> None:
    config = CognitionLoopConfig(
        cognitive_budget_mode=CognitionBudgetMode.DISABLED,
        cognitive_budget_policy=low_cost_budget_limits(),
    )
    assert config.cognitive_budget_mode is CognitionBudgetMode.DISABLED
    assert config.cognitive_budget_policy is None


def test_config_enforced_requires_or_defaults_policy() -> None:
    config = CognitionLoopConfig(
        cognitive_budget_mode=CognitionBudgetMode.ENFORCED,
    )
    assert config.cognitive_budget_policy is not None
    assert config.cognitive_budget_policy.version == COGNITIVE_BUDGET_POLICY_VERSION
    explicit = CognitionLoopConfig(
        cognitive_budget_mode=CognitionBudgetMode.ENFORCED,
        cognitive_budget_policy=high_cost_budget_limits(),
    )
    assert explicit.cognitive_budget_policy.max_llm_calls_per_tick == 4


def test_ledger_charges_and_warns_once_per_dimension(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = CognitiveBudgetPolicy(
        max_llm_calls_per_tick=1,
        max_tokens_per_tick=10,
        max_imagination_branches=1,
        max_planning_depth=1,
        max_recalled_memories=1,
        max_tom_targets=1,
        reflection_interval_ticks=8,
        timeout_seconds=0.0,
    )
    ledger = TickBudgetLedger(owner_id=_owner(), tick=3, policy=policy)
    assert ledger.try_consume(BudgetDimension.LLM, 1) is True
    assert ledger.try_consume(BudgetDimension.LLM, 1) is False
    assert BudgetExhaustedReason.BUDGET_LLM in ledger.exhausted_reasons()
    warnings = [
        record
        for record in caplog.records
        if record.name == "agents.cognition.budget"
        and "tick_budget_exhausted" in record.getMessage()
    ]
    assert len(warnings) == 1
    assert ledger.try_consume(BudgetDimension.LLM, 1) is False
    warnings_after = [
        record
        for record in caplog.records
        if record.name == "agents.cognition.budget"
        and "tick_budget_exhausted" in record.getMessage()
    ]
    assert len(warnings_after) == 1


def test_ledger_timeout_via_injected_clock() -> None:
    ticks = iter([0.0, 0.05, 0.11])

    def clock() -> float:
        return next(ticks)

    policy = CognitiveBudgetPolicy(
        max_llm_calls_per_tick=4,
        max_tokens_per_tick=100,
        max_imagination_branches=4,
        max_planning_depth=2,
        max_recalled_memories=4,
        max_tom_targets=2,
        reflection_interval_ticks=4,
        timeout_seconds=0.1,
        clock=clock,
    )
    ledger = TickBudgetLedger(owner_id=_owner(), tick=1, policy=policy)
    assert ledger.check_timeout() is False
    assert ledger.allow_llm() is False or ledger.check_timeout() is True
    assert BudgetExhaustedReason.BUDGET_TIMEOUT in ledger.exhausted_reasons()


def test_ledger_snapshot_audit() -> None:
    policy = low_cost_budget_limits()
    ledger = TickBudgetLedger(owner_id=_owner(), tick=2, policy=policy)
    assert ledger.try_consume(BudgetDimension.BRANCHES, 1) is True
    audit = ledger.snapshot()
    assert type(audit) is CognitiveBudgetAudit
    assert audit.owner_id == _owner()
    assert audit.mode == "enforced"
    assert audit.imagination_branches_used == 1
    assert audit.degraded is False


def test_memory_truncate_marks_exhausted() -> None:
    policy = CognitiveBudgetPolicy(
        max_llm_calls_per_tick=0,
        max_tokens_per_tick=0,
        max_imagination_branches=1,
        max_planning_depth=1,
        max_recalled_memories=2,
        max_tom_targets=0,
        reflection_interval_ticks=8,
    )
    ledger = TickBudgetLedger(owner_id=_owner(), tick=0, policy=policy)
    assert ledger.truncate_memories(5) == 2
    assert BudgetExhaustedReason.BUDGET_MEMORIES in ledger.exhausted_reasons()
    assert ledger.used(BudgetDimension.MEMORIES) == 2


def test_policy_from_limits_maps_flat_keys() -> None:
    policy = policy_from_limits(
        max_llm_calls_per_tick=1,
        max_tokens_per_tick=8,
        max_imagination_branches=3,
        max_planning_depth=2,
        max_recalled_memories=4,
        max_tom_targets=2,
        reflection_interval_ticks=5,
        timeout_seconds=0.0,
    )
    assert policy.max_imagination_branches == 3
    assert policy.clock is None


def test_exhausted_reason_enum_type_distinct_from_prospective() -> None:
    from agents.cognition.prospective import ProspectivePruneReason

    assert BudgetExhaustedReason is not ProspectivePruneReason
    assert BudgetExhaustedReason.BUDGET_LLM is not ProspectivePruneReason.BUDGET_LLM
    assert BudgetExhaustedReason.BUDGET_LLM.value == "budget_llm"


def test_mode_lockstep_with_simulation() -> None:
    from simulation.runner_models import CognitiveBudgetMode as SimMode

    assert [mode.value for mode in CognitionBudgetMode] == [
        mode.value for mode in SimMode
    ]


def test_runner_v22_budget_schema_gates_and_round_trip() -> None:
    import json
    from dataclasses import replace

    from agents.cognition.configuration import CognitionBudgetMode as LoopMode
    from simulation.runner import _cognition_config_for
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        CognitiveBudgetLimits,
        CognitiveBudgetMode,
        CulturalNarrativeMode,
        MortalityMode,
        ProspectiveImaginationMode,
        ReflectionMode,
        V2CapabilityFlags,
    )
    from simulation.runner_serialization import (
        decode_runner_config,
        encode_runner_config,
    )
    from tests.unit.test_runner_serialization import _configured

    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    quiet = json.loads(encode_runner_config(base).decode("utf-8"))
    assert quiet["schema_version"] == "runner-config-v4"
    assert "cognitive_budget_mode" not in quiet["agents"][0]["cognition"]
    agent = base.agents[0]
    limits = CognitiveBudgetLimits(
        max_llm_calls_per_tick=0,
        max_tokens_per_tick=0,
        max_imagination_branches=2,
        max_planning_depth=1,
        max_recalled_memories=2,
        max_tom_targets=1,
        reflection_interval_ticks=16,
        timeout_seconds=0.0,
    )
    early = replace(
        agent,
        cognition=replace(
            agent.cognition,
            cognitive_budget_mode=CognitiveBudgetMode.ENFORCED,
            cognitive_budget_limits=limits,
        ),
    )
    with pytest.raises(ValueError, match="cognitive_budget_mode_requires_v22"):
        replace(base, agents=(early,))
    with pytest.raises(ValueError, match="cognitive_budget_mode_requires_v22"):
        replace(base, agents=(early,), schema_version=RUNNER_SCHEMA_VERSION_V21)
    narratives = replace(
        agent,
        cognition=replace(
            agent.cognition,
            cultural_narrative_mode=CulturalNarrativeMode.DETERMINISTIC,
        ),
    )
    narratives_only = replace(
        base, agents=(narratives,), schema_version=RUNNER_SCHEMA_VERSION_V21
    )
    narratives_doc = json.loads(encode_runner_config(narratives_only).decode("utf-8"))
    assert narratives_doc["schema_version"] == "runner-config-v21"
    assert "cognitive_budget_mode" not in narratives_doc["agents"][0]["cognition"]
    with pytest.raises(ValueError, match="v22_requires_cognitive_budget"):
        replace(narratives_only, schema_version=RUNNER_SCHEMA_VERSION_V22)
    enabled = replace(
        early,
        cognition=replace(
            early.cognition,
            reflection_mode=ReflectionMode.DETERMINISTIC,
            prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
        ),
    )
    enforced = replace(
        base, agents=(enabled,), schema_version=RUNNER_SCHEMA_VERSION_V22
    )
    encoded = encode_runner_config(enforced)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v22"
    cognition = document["agents"][0]["cognition"]
    assert cognition["cognitive_budget_mode"] == "enforced"
    assert cognition["max_llm_calls_per_tick"] == 0
    assert cognition["max_imagination_branches"] == 2
    assert cognition["reflection_mode"] == "deterministic"
    assert cognition["prospective_mode"] == "deterministic"
    assert cognition["cultural_narrative_mode"] == "disabled"
    assert decode_runner_config(encoded) == enforced
    both = replace(
        enabled,
        cognition=replace(
            enabled.cognition,
            cultural_narrative_mode=CulturalNarrativeMode.DETERMINISTIC,
        ),
    )
    both_config = replace(
        base, agents=(both,), schema_version=RUNNER_SCHEMA_VERSION_V22
    )
    both_doc = json.loads(encode_runner_config(both_config).decode("utf-8"))
    both_cognition = both_doc["agents"][0]["cognition"]
    assert both_cognition["cultural_narrative_mode"] == "deterministic"
    assert both_cognition["cognitive_budget_mode"] == "enforced"
    assert both_cognition["max_tokens_per_tick"] == 0
    assert decode_runner_config(encode_runner_config(both_config)) == both_config
    flags = V2CapabilityFlags(multi_hop_testimony_tracking=True)
    assert flags.unimplemented_enabled_names() == ("multi_hop_testimony_tracking",)
    built = _cognition_config_for(
        early.cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.cognitive_budget_mode is LoopMode.ENFORCED
    assert built.cognitive_budget_policy is not None
    assert built.cognitive_budget_policy.max_imagination_branches == 2
    disabled_built = _cognition_config_for(
        agent.cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert disabled_built.cognitive_budget_mode is LoopMode.DISABLED
    assert disabled_built.cognitive_budget_policy is None


@pytest.mark.asyncio
async def test_guarded_provider_refuses_when_llm_budget_zero() -> None:
    from agents.cognition.budget import BudgetExhaustedError, BudgetGuardedProvider

    class _CountingProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, request: object) -> object:
            self.calls += 1
            return object()

    policy = CognitiveBudgetPolicy(
        max_llm_calls_per_tick=0,
        max_tokens_per_tick=64,
        max_imagination_branches=1,
        max_planning_depth=1,
        max_recalled_memories=1,
        max_tom_targets=0,
        reflection_interval_ticks=1,
        timeout_seconds=0.0,
    )
    ledger = TickBudgetLedger(owner_id=_owner(), tick=1, policy=policy)
    inner = _CountingProvider()
    guarded = BudgetGuardedProvider(inner=inner, ledger=ledger)
    with pytest.raises(BudgetExhaustedError, match="budget_llm"):
        await guarded.generate(object())
    assert inner.calls == 0
    assert BudgetExhaustedReason.BUDGET_LLM in ledger.exhausted_reasons()


def test_reflection_interval_floor_and_skip_mark() -> None:
    from agents.cognition.reflection import ReflectionPolicy

    budget = CognitiveBudgetPolicy(
        max_llm_calls_per_tick=0,
        max_tokens_per_tick=0,
        max_imagination_branches=1,
        max_planning_depth=1,
        max_recalled_memories=1,
        max_tom_targets=0,
        reflection_interval_ticks=16,
        timeout_seconds=0.0,
    )
    local = ReflectionPolicy(interval_ticks=4, min_gap_ticks=2)
    effective_interval = max(
        local.interval_ticks,
        local.min_gap_ticks or local.interval_ticks,
        budget.reflection_interval_ticks,
    )
    assert effective_interval == 16
    ledger = TickBudgetLedger(owner_id=_owner(), tick=3, policy=budget)
    ledger.mark_reflection_skipped()
    assert BudgetExhaustedReason.BUDGET_REFLECTION in ledger.exhausted_reasons()
    audit = ledger.snapshot()
    assert audit.reflection_ran is False
    assert audit.degraded is True


def test_v1_regression_gate_does_not_list_experiment_ad() -> None:
    from pathlib import Path

    gate = Path("tests/unit/test_v1_regression_gate.py").read_text(encoding="utf-8")
    assert "experiment-ad-cognitive-budgets" not in gate
    assert "cognitive_budget" not in gate
    assert "experiment_ad" not in gate


def test_identical_charge_sequence_low_strictly_below_high() -> None:
    """Shared seed charge attempts: low-cost exhausts earlier than high-cost."""

    def _drive(policy: CognitiveBudgetPolicy) -> CognitiveBudgetAudit:
        ledger = TickBudgetLedger(owner_id=_owner(), tick=1, policy=policy)
        for _ in range(4):
            ledger.try_consume(BudgetDimension.LLM, 1)
        for _ in range(8):
            ledger.try_consume(BudgetDimension.BRANCHES, 1)
        for _ in range(3):
            ledger.try_tom_target()
        return ledger.snapshot()

    low = _drive(low_cost_budget_limits())
    high = _drive(high_cost_budget_limits())
    assert low.llm_calls_used < high.llm_calls_used
    assert low.imagination_branches_used < high.imagination_branches_used
    assert low.tom_targets_used < high.tom_targets_used
    assert low.degraded is True


@pytest.mark.asyncio
