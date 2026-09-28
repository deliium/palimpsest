"""Experiment M identity and the in-memory epistemic audit."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.epistemic import EpistemicAuditSnapshot
from agents.cognition.theory_of_mind import TheoryOfMind, build_mind_audit
from agents.models import AgentId
from experiments.catalog import experiment_m_epistemic_asymmetry
from tests.unit.test_epistemic_model import _row
from tests.unit.test_simulation_runner_e2e import _config
from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS

_CATALOG = "experiments.catalog"
_EPISTEMIC = "agents.cognition.epistemic"


def test_experiment_m_shares_identity_and_stays_off_the_v1_gate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_CATALOG)
    definition = experiment_m_epistemic_asymmetry(_config())
    ids = {experiment_id for experiment_id, _builder in _CATALOG_BUILDERS}
    assert definition.experiment_id == "experiment-m-epistemic-asymmetry"
    assert definition.experiment_id not in ids
    disabled, enabled = definition.conditions
    assert disabled.condition_id == "m-disabled"
    assert enabled.condition_id == "m-enabled"
    assert disabled.runner_config.schema_version == "runner-config-v4"
    assert enabled.runner_config.schema_version == "runner-config-v4"
    assert enabled.runner_config.capability_flags.advanced_social_inference is True
    assert disabled.runner_config.capability_flags.advanced_social_inference is False
    assert disabled.runner_config.seed == enabled.runner_config.seed
    assert (
        disabled.runner_config.stochastic_identity
        == enabled.runner_config.stochastic_identity
    )
    assert disabled.runner_config.scenario == enabled.runner_config.scenario
    text = caplog.text
    assert "experiment_m_built" in text
    assert "experiment_id=experiment-m-epistemic-asymmetry" in text
    assert "condition_id=m-enabled" in text


def test_mind_audit_projects_epistemic_rows(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_EPISTEMIC)
    owner = AgentId("agent-alice")
    row = _row()
    model = TheoryOfMind(owner_id=owner, attributions=(row,), last_tick=4)
    audit = build_mind_audit(model)
    assert audit.epistemic == (
        EpistemicAuditSnapshot(
            attribution_id=row.attribution_id,
            nesting_level=1,
            attitude=row.attitude.value,
            source=row.source.value,
            confidence=row.confidence,
            proposition_ref=row.proposition_ref,
        ),
    )
    assert "epistemic_audit" in caplog.text
    assert "snapshot_count=1" in caplog.text
    assert "owner_id=agent-alice" in caplog.text
    assert "belief:belief-1" not in caplog.text
    with pytest.raises(ValueError, match="invalid_type"):
        type(audit)(
            owner_id=owner,
            tick=4,
            mode="enabled",
            hypothesis_count=0,
            update_count=0,
            max_confidence=0.0,
            fallback_used=False,
            epistemic=("not-a-snapshot",),
        )
