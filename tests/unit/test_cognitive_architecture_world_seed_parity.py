"""Shared world + seed invariance across architecture arms."""

from __future__ import annotations

from pathlib import Path

from experiments import experiment_ac_cognitive_architectures
from simulation.runner_serialization import scenario_fingerprint
from tests.unit.test_runner_models import _config

_V1_GATE = (
    Path(__file__).resolve().parents[1] / "unit" / "test_v1_regression_gate.py"
)


def test_architecture_arms_share_scenario_and_seed_identity() -> None:
    base = _config(seed=99, stochastic="arch-parity")
    definition = experiment_ac_cognitive_architectures(base)

    assert definition.experiment_id == "experiment-ac-cognitive-architectures"
    assert definition.paired_world_group == (
        "experiment-ac-cognitive-architectures-world"
    )
    assert len(definition.conditions) == 7

    scenario_fps = {
        scenario_fingerprint(condition.runner_config)
        for condition in definition.conditions
    }
    assert len(scenario_fps) == 1

    seeds = {condition.runner_config.seed for condition in definition.conditions}
    identities = {
        condition.runner_config.stochastic_identity
        for condition in definition.conditions
    }
    assert seeds == {base.seed}
    assert identities == {base.stochastic_identity}

    reactive = next(
        c for c in definition.conditions if c.condition_id == "ac-reactive_baseline"
    )
    full = next(
        c for c in definition.conditions if c.condition_id == "ac-full_v2_agent"
    )
    assert scenario_fingerprint(reactive.runner_config) == scenario_fingerprint(
        full.runner_config
    )
    assert reactive.runner_config.seed == full.runner_config.seed
    assert (
        reactive.runner_config.stochastic_identity
        == full.runner_config.stochastic_identity
    )
    # Cognition/capability/schema may differ by design.
    assert reactive.runner_config.schema_version != full.runner_config.schema_version
    assert (
        reactive.runner_config.capability_flags.enabled_names()
        != full.runner_config.capability_flags.enabled_names()
    )


def test_v1_regression_gate_does_not_import_experiment_ac() -> None:
    text = _V1_GATE.read_text(encoding="utf-8")
    assert "experiment_ac" not in text
    assert "experiment-ac-cognitive-architectures" not in text
    assert "cognitive_architectures" not in text
