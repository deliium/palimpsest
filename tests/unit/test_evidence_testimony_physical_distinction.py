"""V4-08: contested evidence never changes physical command admission."""

from __future__ import annotations

import pytest

import agents.cognition.evidence_testimony as evidence_testimony
from agents.cognition import (
    EvidenceAct,
    EvidenceContradictionKind,
    EvidenceFrame,
    EvidenceInterpretationKind,
    EvidenceLedger,
    EvidenceReferenceKind,
    EvidenceSourceKind,
    apply_evidence_update,
    empty_evidence_ledger,
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
        world_id=WorldId("world-1"),
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


def _contested_ledger() -> EvidenceLedger:
    assert_source = EvidenceFrame(
        act=EvidenceAct.ASSERT_SOURCE,
        subject_token=SUBJECT,
        source_kind=EvidenceSourceKind.ARTIFACT,
        reference_kind=EvidenceReferenceKind.ARTIFACT,
        reference_id="artifact-1",
        confidence_band="high",
    )
    supports = EvidenceFrame(
        act=EvidenceAct.INTERPRET,
        subject_token=SUBJECT,
        interpretation=EvidenceInterpretationKind.SUPPORTS,
        reference_id="artifact-1",
        confidence_band="high",
    )
    contradicts = EvidenceFrame(
        act=EvidenceAct.INTERPRET,
        subject_token=SUBJECT,
        interpretation=EvidenceInterpretationKind.CONTRADICTS,
        reference_id="artifact-1",
        confidence_band="low",
    )
    ledger = apply_evidence_update(
        empty_evidence_ledger(OWNER),
        owner_id=OWNER,
        tick=1,
        frames=(assert_source, supports, contradicts),
    )
    source = ledger.sources[0]
    first_item, second_item = ledger.items
    contradict = EvidenceFrame(
        act=EvidenceAct.CONTRADICT,
        subject_token=SUBJECT,
        contradiction_kind=EvidenceContradictionKind.INTERPRETATION_CONFLICT,
        first_ref=first_item.item_id,
        second_ref=second_item.item_id,
        confidence_band="mid",
    )
    ledger = apply_evidence_update(ledger, owner_id=OWNER, tick=2, frames=(contradict,))
    assert ledger.contradictions
    assert ledger.sources[0].source_id == source.source_id
    return ledger


def test_contested_evidence_does_not_change_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = _contested_ledger()
    assert isinstance(ledger, EvidenceLedger)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("admission consulted an evidence ledger")

    monkeypatch.setattr(evidence_testimony, "apply_evidence_update", forbidden)
    monkeypatch.setattr(evidence_testimony, "record_evidence_utterance", forbidden)

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
    engine.observe()
    observed = engine.observation_for(AgentId(OTHER))
    assert observed.self_body is not None
    assert observed.self_body.inventory == (EntityId(SUBJECT),)


def test_physically_impossible_command_is_still_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = _contested_ledger()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("admission consulted an evidence ledger")

    monkeypatch.setattr(evidence_testimony, "apply_evidence_update", forbidden)
    monkeypatch.setattr(evidence_testimony, "record_evidence_utterance", forbidden)

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
    engine.observe()
    observed = engine.observation_for(AgentId(OTHER))
    assert observed.self_body is not None
    assert observed.self_body.inventory == ()
    transferred = [
        record.event
        for record in result.events
        if getattr(record.event.details, "kind", "") == "item_given"
    ]
    assert transferred == []


def test_admission_modules_never_import_evidence_cognition() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src"
    for relative in (
        "world/_rules.py",
        "world/_operations.py",
        "world/_perception.py",
        "simulation/engine.py",
        "simulation/actions.py",
    ):
        text = (root / relative).read_text(encoding="utf-8").lower()
        assert "evidence" not in text, relative
