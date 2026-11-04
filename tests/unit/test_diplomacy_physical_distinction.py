"""V4-10 diplomacy never becomes world authority."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.cognition import (
    DiplomacyFrame,
    DiplomacyPolicy,
    DiplomaticAct,
    DiplomaticEnvoyStatus,
    DiplomaticPartyKind,
    DiplomaticTermKind,
    apply_diplomacy_update,
    default_diplomacy_policy,
    diplomacy_envoy_status,
    empty_diplomacy_ledger,
)
from agents.cognition.diplomacy import DiplomacyLedger
from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import SimulationRunConfig
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    weather_for_locations,
)
from world.actions import Give, Take
from world.identifiers import EntityId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"
_OWNER = "agent-e2e-a"
_ENVOY = "agent-envoy"


def _bootstrap() -> WorldBootstrap:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldBootstrap(
        world_id=WorldId("world-diplomacy-admission"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("body-e2e-a", inventory=(EntityId("item-e2e"),)),
            alive_body("body-e2e-b"),
        ),
        items=(make_item("item-e2e", holder_id="body-e2e-a", location_id=None),),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-e2e-a"), EntityId("body-e2e-a")),
            AgentRegistration(AgentId("agent-e2e-b"), EntityId("body-e2e-b")),
        ),
    )


def _rejected_envoy_ledger() -> DiplomacyLedger:
    policy: DiplomacyPolicy = default_diplomacy_policy()
    ledger = empty_diplomacy_ledger(_OWNER, tick=0)
    ledger = apply_diplomacy_update(
        owner_id=_OWNER,
        tick=1,
        observation=None,
        prior=ledger,
        frames=(
            DiplomacyFrame(
                act=DiplomaticAct.PROPOSE,
                envoy_ref=_OWNER,
                actor_ref=_OWNER,
                party_kind=DiplomaticPartyKind.AGENT,
                party_ref="agent-e2e-b",
                topic_subject="trade",
                term_kind=DiplomaticTermKind.MATERIAL_EXCHANGE,
            ),
        ),
        policy=policy,
    )
    ledger = apply_diplomacy_update(
        owner_id=_OWNER,
        tick=2,
        observation=None,
        prior=ledger,
        frames=(
            DiplomacyFrame(
                act=DiplomaticAct.ACCREDIT,
                envoy_ref=_ENVOY,
                actor_ref=_ENVOY,
                party_kind=DiplomaticPartyKind.AGENT,
                party_ref="agent-e2e-b",
                mandate_ref="rmd-" + "0" * 16,
            ),
        ),
        policy=policy,
    )
    envoy = ledger.envoys[-1]
    status = diplomacy_envoy_status(envoy, None, tick=2, policy=policy)
    assert status is not DiplomaticEnvoyStatus.RECOGNIZED
    assert status in {
        DiplomaticEnvoyStatus.CLAIMED,
        DiplomaticEnvoyStatus.UNKNOWN,
    }
    return ledger


def test_physically_possible_command_is_admitted_despite_rejected_envoy() -> None:
    ledger = _rejected_envoy_ledger()
    assert ledger.envoys

    engine = WorldEngine(
        config=SimulationRunConfig(seed=41), bootstrap=_bootstrap()
    )
    batch = engine.observe()
    possible = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-e2e-a"),
                command=Give(
                    recipient_id=EntityId("body-e2e-b"),
                    item_id=EntityId("item-e2e"),
                ),
            ),
        )
    )
    assert possible.resolutions[0].status is not ActionResolutionStatus.REJECTED


def test_physically_impossible_command_is_still_rejected() -> None:
    engine = WorldEngine(
        config=SimulationRunConfig(seed=42), bootstrap=_bootstrap()
    )
    batch = engine.observe()
    impossible = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-e2e-a"),
                command=Take(item_id=EntityId("item-missing")),
            ),
        )
    )
    assert impossible.resolutions[0].status is ActionResolutionStatus.REJECTED


def test_contested_agreement_grants_no_objective_access() -> None:
    engine = WorldEngine(
        config=SimulationRunConfig(seed=43), bootstrap=_bootstrap()
    )
    batch = engine.observe()
    unauthorised = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-e2e-b"),
                command=Take(item_id=EntityId("item-e2e")),
            ),
        )
    )
    assert unauthorised.resolutions[0].status is ActionResolutionStatus.REJECTED

    source = (_SRC / "agents" / "cognition" / "diplomacy.py").read_text(
        encoding="utf-8"
    )
    assert "move_item(" not in source
    assert "holder_id =" not in source
    assert "admit(" not in source


def test_world_and_engine_never_read_the_diplomacy_ledger() -> None:
    for path in sorted((_SRC / "world").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "agents.cognition.diplomacy" not in source
        assert "DiplomacyLedger" not in source
    engine = (_SRC / "simulation" / "engine.py").read_text(encoding="utf-8")
    assert "agents.cognition.diplomacy" not in engine
    assert "DiplomacyLedger" not in engine


def test_diplomacy_helpers_never_construct_a_command() -> None:
    for path in sorted((_SRC / "agents" / "cognition").glob("diplomacy*.py")):
        source = path.read_text(encoding="utf-8")
        assert "AgentCommand(" not in source
        assert "ActionSubmission(" not in source
