"""Off-gate Experiment AR catalog for technique lifecycle."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from agents.models import AgentId
from analysis.models import AppliedActionRow
from analysis.technique_lifecycle import (
    TechniqueLifecycleState,
    classify_technique_lifecycle,
)
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_aq_bounded_experimentation,
    experiment_ar_technique_lifecycle,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V36,
    RUNNER_SCHEMA_VERSION_V37,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import AgentCommand
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    return base_runner_config_from_scenario(
        seed=37,
        stochastic_identity="cmp-ar-lifecycle",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ar"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_a,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_a),
            ),
            AgentRunnerSpec(
                agent_id=agent_b,
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_b),
            ),
        ),
        max_ticks=4,
    )


def _definition():
    return experiment_ar_technique_lifecycle(_base())


def _arm(arm_id: str):
    definition = _definition()
    return next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == arm_id
    )


def _audit(**overrides: object) -> SimpleNamespace:
    payload: dict[str, object] = {
        "owner_id": "agent-a",
        "entry_id": "entry-1",
        "kind": "practical",
        "content_key": "tech:hafting",
        "origin": "independent_discovery",
        "lineage_root_id": "root-1",
        "hop_index": 0,
        "acquired_tick": 1,
        "tick": 1,
        "active": True,
        "parent_entry_ids": (),
        "mutated": False,
        "evidence_refs": (),
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _state(config, audits, **kwargs):
    rows = classify_technique_lifecycle(
        audits,
        spec=config.technique_lifecycle,
        applied_actions=kwargs.pop(
            "applied_actions",
            (
                AppliedActionRow(
                    tick=1,
                    ordinal=0,
                    agent_id="agent-a",
                    action_kind="move",
                    location_id="loc-1",
                ),
            ),
        ),
        **kwargs,
    )
    return next(row for row in rows if row.scope == "global")


def test_ar_is_off_gate() -> None:
    assert "experiment-ar-technique-lifecycle" in OFF_GATE_MATRIX_EXPERIMENT_IDS


def test_ar_channel_off_matches_v36_without_lifecycle(caplog) -> None:
    caplog.set_level(logging.INFO)
    config = _arm("ar-channel-off")
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V36
    assert config.technique_lifecycle is None
    encoded = encode_runner_config(config)
    assert b"technique_lifecycle" not in encoded
    assert runner_config_fingerprint(config) == runner_config_fingerprint(
        decode_runner_config(encoded)
    )
    aq = experiment_aq_bounded_experimentation(_base())
    aq_arm = next(
        item.runner_config
        for item in aq.conditions
        if item.condition_id == "aq-harm"
    )
    assert b"technique_lifecycle" not in encode_runner_config(aq_arm)
    assert "experiment_arm_start arm_id=ar-channel-off" in caplog.text


def test_ar_discovered_then_diffusing_then_known() -> None:
    config = _arm("ar-discovered-known")
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V37
    one = _state(config, (_audit(),), as_of_tick=2)
    assert one.state is TechniqueLifecycleState.DISCOVERED
    assert one.known_by_n == 1
    audits = (
        _audit(),
        _audit(
            owner_id="agent-b",
            entry_id="entry-2",
            origin="teaching",
            hop_index=1,
            acquired_tick=3,
        ),
    )
    actions = (
        AppliedActionRow(
            tick=1,
            ordinal=0,
            agent_id="agent-a",
            action_kind="move",
            location_id="loc-1",
        ),
        AppliedActionRow(
            tick=3,
            ordinal=0,
            agent_id="agent-b",
            action_kind="move",
            location_id="loc-2",
        ),
    )
    diffusing = _state(config, audits, as_of_tick=4, applied_actions=actions)
    assert diffusing.state is TechniqueLifecycleState.DIFFUSING
    assert diffusing.known_by_n == 2
    later = classify_technique_lifecycle(
        audits,
        as_of_tick=20,
        spec=example_window(config.technique_lifecycle),
        applied_actions=actions,
    )
    known = next(row for row in later if row.scope == "global")
    assert known.state is TechniqueLifecycleState.KNOWN
    assert known.known_by_n == 2


def example_window(spec):
    from dataclasses import replace

    return replace(spec, diffusion_window_ticks=2)


def test_ar_flags_off_stays_v4() -> None:
    config = _arm("ar-flags-off")
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert config.technique_lifecycle is None
    assert len(AgentCommand.__args__) == 36  # type: ignore[attr-defined]


def test_ar_not_a_tree_rejects_requires_technique() -> None:
    config = _arm("ar-not-a-tree")
    document = json.loads(encode_runner_config(config))
    document["technique_lifecycle"]["technology_tree"] = []
    from simulation.runner_serialization import RunnerSerializationError

    with pytest.raises(
        RunnerSerializationError, match="technique_lifecycle_forbidden_alias"
    ):
        decode_runner_config(json.dumps(document).encode())
