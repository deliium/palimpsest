"""V4-09: contested representation never changes physical command admission."""

from __future__ import annotations

import pytest

import agents.cognition.delegation_representation as representation
from agents.cognition import (
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
    default_representation_policy,
)
from agents.cognition.delegation_representation import (
    RepresentationLedger,
    apply_representation_update,
)
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
)
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

OWNER = "agent-1"
OTHER = "agent-2"
OWNER_ENTITY = "body-1"
OTHER_ENTITY = "body-2"
SUBJECT = "item-1"


def _bootstrap() -> WorldBootstrap:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldBootstrap(
        world_id=WorldId("world-representation-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body(OWNER_ENTITY, inventory=(EntityId(SUBJECT),)),
            alive_body(OTHER_ENTITY),
        ),
        items=(make_item(SUBJECT, holder_id=OWNER_ENTITY, location_id=None),),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId(OWNER), EntityId(OWNER_ENTITY)),
            AgentRegistration(AgentId(OTHER), EntityId(OTHER_ENTITY)),
        ),
    )


def _frame(
    act: RepresentationAct, *, mandate_ref: str | None, actor: str
) -> RepresentationFrame:
    return RepresentationFrame(
        act=act,
        mandate_ref=mandate_ref,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref="agent-principal",
        representative_ref="agent-representative",
        scope_kind=RepresentationScopeKind.SPEAK_FOR,
        scope_subject="border",
        duration_kind=RepresentationDurationKind.UNTIL_REVOKED,
        provenance=RepresentationProvenance.SELF_DECLARED,
        actor_ref=actor,
    )


def _contested_ledger() -> RepresentationLedger:
    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=1,
        observation=None,
        prior=None,
        frames=(
            _frame(
                RepresentationAct.CLAIM, mandate_ref=None, actor="agent-representative"
            ),
        ),
        policy=default_representation_policy(),
    )
    mandate_id = ledger.mandates[0].mandate_id
    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=2,
        observation=None,
        prior=ledger,
        frames=(
            _frame(RepresentationAct.SUPPORT, mandate_ref=mandate_id, actor="agent-c"),
            _frame(RepresentationAct.OPPOSE, mandate_ref=mandate_id, actor="agent-d"),
        ),
        policy=default_representation_policy(),
    )
    assert ledger.mandates[0].status.value == "contested"
    return ledger


def test_contested_representation_does_not_change_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _contested_ledger()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("admission consulted a representation ledger")

    monkeypatch.setattr(representation, "apply_representation_update", forbidden)
    monkeypatch.setattr(representation, "record_representation_utterance", forbidden)

    engine = WorldEngine(config=SimulationRunConfig(seed=21), bootstrap=_bootstrap())
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId(OWNER),
                command=Give(
                    recipient_id=EntityId(OTHER_ENTITY),
                    item_id=EntityId(SUBJECT),
                ),
            ),
        )
    )
    assert result.resolutions[0].status is not ActionResolutionStatus.REJECTED


def test_physically_impossible_command_is_still_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _contested_ledger()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("admission consulted a representation ledger")

    monkeypatch.setattr(representation, "apply_representation_update", forbidden)
    monkeypatch.setattr(representation, "record_representation_utterance", forbidden)

    engine = WorldEngine(config=SimulationRunConfig(seed=22), bootstrap=_bootstrap())
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId(OWNER),
                command=Take(item_id=EntityId("item-missing")),
            ),
        )
    )
    resolution = result.resolutions[0]
    assert resolution.status is ActionResolutionStatus.REJECTED
    assert resolution.reason is not None
    assert resolution.reason.value == "invalid_target"


def test_admission_modules_never_import_representation_cognition() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src"
    for relative in (
        "world/_rules.py",
        "world/_operations.py",
        "world/_perception.py",
        "simulation/engine.py",
        "simulation/actions.py",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        assert "delegation_representation" not in text, relative
