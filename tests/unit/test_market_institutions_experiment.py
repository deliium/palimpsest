"""V4-20 off-gate experiment registration and scenario shape."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.catalog import (
    EXPERIMENT_A_V1_CONDITION_IDS,
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_market_institutions,
)
from experiments.market_institution_scenario import (
    MARKET_INSTITUTIONS_EXPERIMENT_ID,
    market_institution_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    V3CapabilityFlags,
)
from tests.unit.test_trade_networks_experiment import _base

pytestmark = pytest.mark.unit


def test_experiment_is_off_gate() -> None:
    assert MARKET_INSTITUTIONS_EXPERIMENT_ID == "market_institutions@1"
    assert MARKET_INSTITUTIONS_EXPERIMENT_ID in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert MARKET_INSTITUTIONS_EXPERIMENT_ID not in EXPERIMENT_A_V1_CONDITION_IDS


def test_two_arms_differ_only_by_the_owned_flag() -> None:
    definition = experiment_market_institutions(_base())
    assert len(definition.conditions) == 2
    control, treatment = definition.conditions
    assert control.condition_id == "market-institutions-control"
    assert treatment.condition_id == "market-institutions-treatment"
    assert control.runner_config.v4_capability_flags.markets_credit is False
    assert treatment.runner_config.v4_capability_flags.markets_credit is True
    assert control.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V56
    assert treatment.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V56
    assert control.runner_config.resource_exchange_profile is not None
    assert treatment.runner_config.subjective_valuation is not None
    assert (
        replace(
            control.runner_config,
            v4_capability_flags=replace(
                control.runner_config.v4_capability_flags, markets_credit=True
            ),
        )
        == treatment.runner_config
    )


def test_missing_regions_fails_closed() -> None:
    with pytest.raises(ValueError, match="market_institutions_requires_regions"):
        market_institution_scenario(
            replace(
                _base(),
                regions_migration=None,
                v3_capability_flags=V3CapabilityFlags(),
            )
        )


def test_less_than_three_windows_is_rejected() -> None:
    with pytest.raises(ValueError, match="three_windows"):
        market_institution_scenario(_base(), max_ticks=64)


def test_no_runner_config_v57_is_emitted() -> None:
    definition = experiment_market_institutions(_base())
    assert all(
        condition.runner_config.schema_version != "runner-config-v57"
        for condition in definition.conditions
    )
