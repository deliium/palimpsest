"""V4-23 accounting seam: activation, cognition config, runner wiring."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from agents.cognition import (
    ACCOUNTING_LEDGERS_POLICY_VERSION,
    AccountingLedger,
    AccountingLedgerError,
    AccountingLedgerPolicy,
    build_cognitive_loop,
    default_accounting_ledger_policy,
    empty_accounting_ledger,
    require_owner_accounting_ledger,
)
from agents.cognition.configuration import (
    CognitionAccountingLedgerMode,
    CognitionLoopConfig,
)
from agents.models import AgentId
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    MortalityMode,
    V2CapabilityFlags,
)

pytestmark = pytest.mark.unit


def test_disabled_mode_allocates_no_policy() -> None:
    config = CognitionLoopConfig()
    assert config.accounting_ledger_mode is CognitionAccountingLedgerMode.DISABLED
    assert config.accounting_ledger_policy is None
    assert config.accounting_ledger_mode.value == "disabled"


def test_deterministic_mode_installs_the_locked_policy() -> None:
    config = CognitionLoopConfig(
        accounting_ledger_mode=CognitionAccountingLedgerMode.DETERMINISTIC
    )
    assert config.accounting_ledger_policy is default_accounting_ledger_policy()
    assert config.accounting_ledger_policy.max_entries == 32


def test_custom_policy_is_preserved_and_invalid_type_fails_closed() -> None:
    custom = AccountingLedgerPolicy()
    config = CognitionLoopConfig(
        accounting_ledger_mode=CognitionAccountingLedgerMode.DETERMINISTIC,
        accounting_ledger_policy=custom,
    )
    assert config.accounting_ledger_policy is custom
    with pytest.raises(TypeError):
        CognitionLoopConfig(
            accounting_ledger_mode=CognitionAccountingLedgerMode.DETERMINISTIC,
            accounting_ledger_policy=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        CognitionLoopConfig(accounting_ledger_mode="enabled")  # type: ignore[arg-type]


def test_disabled_mode_clears_a_supplied_policy() -> None:
    config = CognitionLoopConfig(accounting_ledger_policy=AccountingLedgerPolicy())
    assert config.accounting_ledger_mode is CognitionAccountingLedgerMode.DISABLED
    assert config.accounting_ledger_policy is None


def test_fingerprint_includes_accounting_version_only_when_enabled() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert "accounting_ledger_policy_version" not in disabled
    enabled = CognitionLoopConfig(
        accounting_ledger_mode=CognitionAccountingLedgerMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert enabled["accounting_ledger_mode"] == "deterministic"
    assert enabled["accounting_ledger_policy_version"] == (
        ACCOUNTING_LEDGERS_POLICY_VERSION
    )


def test_build_cognitive_loop_forwards_the_accounting_mode() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            accounting_ledger_mode=CognitionAccountingLedgerMode.DETERMINISTIC
        )
    )
    assert loop._accounting_ledger_mode is CognitionAccountingLedgerMode.DETERMINISTIC
    assert loop._accounting_ledger_policy is default_accounting_ledger_policy()
    disabled = build_cognitive_loop(CognitionLoopConfig())
    assert disabled._accounting_ledger_policy is None


def test_runner_activation_requires_organizations_and_durable_records() -> None:
    from simulation.runner import _cognition_config_for

    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    flag_off = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=False,
        durable_records_active=True,
    )
    assert flag_off.accounting_ledger_mode is CognitionAccountingLedgerMode.DISABLED
    assert flag_off.accounting_ledger_policy is None

    records_off = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=True,
        durable_records_active=False,
    )
    assert records_off.accounting_ledger_mode is (
        CognitionAccountingLedgerMode.DISABLED
    )
    assert records_off.accounting_ledger_policy is None

    both = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=True,
        durable_records_active=True,
    )
    assert both.accounting_ledger_mode is CognitionAccountingLedgerMode.DETERMINISTIC
    assert both.accounting_ledger_policy is default_accounting_ledger_policy()


def test_accounting_does_not_activate_for_credit_or_market_only_runs() -> None:
    from simulation.runner import _cognition_config_for

    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    credit_only = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        markets_enabled=True,
        structured_commitments_active=True,
        organizations_enabled=False,
    )
    assert credit_only.credit_relationship_mode.value == "deterministic"
    assert credit_only.accounting_ledger_mode.value == "disabled"


def test_result_tuple_rejects_foreign_and_unordered_ledgers() -> None:
    from simulation.models import RunId
    from simulation.runner_models import (
        RunnerStopReasonCode,
        SimulationRunnerResult,
    )

    owner = AgentId("agent-1")
    other = AgentId("agent-2")
    base = dict(
        run_id=RunId("run-1"),
        ticks_committed=0,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
    )
    result = SimulationRunnerResult(
        **base, accounting_ledgers=(empty_accounting_ledger(owner),)
    )
    assert type(result.accounting_ledgers[0]) is AccountingLedger
    with pytest.raises((ValueError, TypeError)):
        SimulationRunnerResult(
            **base,
            accounting_ledgers=(
                empty_accounting_ledger(other),
                empty_accounting_ledger(owner),
            ),
        )
    with pytest.raises(TypeError):
        SimulationRunnerResult(**base, accounting_ledgers=(object(),))


def test_foreign_owner_ledger_is_rejected_on_carry() -> None:
    with pytest.raises(AccountingLedgerError):
        require_owner_accounting_ledger(
            empty_accounting_ledger(AgentId("agent-2")), AgentId("agent-1")
        )
