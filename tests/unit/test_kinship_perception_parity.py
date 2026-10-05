"""Kinship perception modes: channel gating and live/restored parity."""

from __future__ import annotations

import json
import logging

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.models import SimulationRunConfig
from simulation.runner_models import KinshipSpec, example_kinship_spec
from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.observations import Observation

_LOG = logging.getLogger("tests.kinship_perception_parity")


def _engine(*, perception_mode: str | None) -> WorldEngine:
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-kinship-obs"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body_a, body_b),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-a"), body_a.entity_id),
            AgentRegistration(AgentId("agent-b"), body_b.entity_id),
        ),
    )
    if perception_mode is None:
        return WorldEngine(
            config=SimulationRunConfig(
                seed=9, physical_rules=non_lethal_physical_rules()
            ),
            bootstrap=bootstrap,
        )
    kinship = example_kinship_spec(
        parent_agent_id="agent-a",
        child_agent_id="agent-b",
    )
    kinship = KinshipSpec(
        bootstrap_edges=kinship.bootstrap_edges,
        max_query_depth=kinship.max_query_depth,
        max_parents_per_child=kinship.max_parents_per_child,
        perception_mode=perception_mode,
        admit_link_policy=kinship.admit_link_policy,
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=9, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        kinship_spec=kinship,
    )


def test_perception_none_omits_kinship_visible() -> None:
    _LOG.debug("case_id=obs_perception_none")
    engine = _engine(perception_mode="none")
    batch = engine.observe()
    for observation in batch.observations:
        assert observation.self_body is not None
        assert observation.self_body.kinship_visible is None
        encoded = json.loads(encode_domain(observation))
        assert "kinship_visible" not in encoded["data"].get("self_body", {})


def test_channel_off_omits_kinship_visible() -> None:
    _LOG.debug("case_id=obs_channel_off")
    engine = _engine(perception_mode=None)
    batch = engine.observe()
    observation = batch.observations[0]
    assert observation.self_body is not None
    assert observation.self_body.kinship_visible is None


def test_self_incident_public_exposes_self_kinship() -> None:
    _LOG.debug("case_id=obs_self_incident_public")
    engine = _engine(perception_mode="self_incident_public")
    by_body = {
        obs.observer_id.value: obs for obs in engine.observe().observations
    }
    parent_obs = by_body["body-a"]
    child_obs = by_body["body-b"]
    assert parent_obs.self_body is not None
    assert parent_obs.self_body.kinship_visible is not None
    assert parent_obs.self_body.kinship_visible.parents == ()
    assert parent_obs.self_body.kinship_visible.children == ("agent-b",)
    assert child_obs.self_body is not None
    assert child_obs.self_body.kinship_visible is not None
    assert child_obs.self_body.kinship_visible.parents == ("agent-a",)
    assert child_obs.self_body.kinship_visible.children == ()
    # Child sees parent body with self-incident fact only.
    visible = {body.entity_id.value: body for body in child_obs.visible_bodies}
    assert "body-a" in visible
    assert visible["body-a"].kinship_visible is not None
    assert visible["body-a"].kinship_visible.parents == ("agent-a",)
    assert visible["body-a"].kinship_visible.children == ()


def test_kinship_observation_round_trip_parity() -> None:
    _LOG.debug("case_id=obs_encode_decode_parity")
    engine = _engine(perception_mode="self_incident_public")
    live = next(
        obs
        for obs in engine.observe().observations
        if obs.observer_id.value == "body-b"
    )
    restored = decode_domain(encode_domain(live))
    assert type(restored) is Observation
    assert restored.self_body is not None
    assert live.self_body is not None
    assert restored.self_body.kinship_visible == live.self_body.kinship_visible
    payload = json.loads(encode_domain(live))["data"]["self_body"]
    assert set(payload["kinship_visible"]) == {"parents", "children"}
