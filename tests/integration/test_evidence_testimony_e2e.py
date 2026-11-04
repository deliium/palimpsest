"""V4-08 end-to-end: run -> harvest -> publish -> store -> API."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from tests.simulation_helpers import alive_body, make_location, make_weather

from agents.cognition import (
    EvidenceAct,
    EvidenceContradictionKind,
    EvidenceFrame,
    EvidenceInterpretationKind,
    EvidenceLedger,
    EvidenceReferenceKind,
    EvidenceSourceKind,
    EvidenceTestimonyChannel,
    apply_evidence_update,
    empty_evidence_ledger,
    evidence_communicate_utterance,
    evidence_ledger_digest,
)
from agents.cognition.models import ActionPlan
from agents.models import AgentId
from api.dependencies import get_evidence_testimony_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.evidence_testimony_cursor import EvidenceTestimonyCursorCodec
from api.routes.evidence_testimony import router
from experiments.catalog import base_runner_config_from_scenario
from experiments.evidence_testimony_harvest import (
    build_completed_run_evidence_harvest,
)
from experiments.evidence_testimony_publication import (
    build_evidence_testimony_harvest_result,
    publish_evidence_testimony_snapshot,
)
from infrastructure.settings import Settings
from persistence.evidence_testimony_filesystem import (
    FilesystemEvidenceTestimonyPublisher,
    create_evidence_testimony_reader,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from world.actions import Talk, Wait
from world.communications import CommunicationSourceBasis, origin_utterance
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.integration

TOKEN = "test-debug-token-0123456789abcdef"
RUN = "run-evidence-e2e"


@dataclass(frozen=True)
class _Entity:
    value: str


@dataclass(frozen=True)
class _Event:
    details: object
    tick: int
    event_id: _Entity


class ArtifactDestroyed:
    artifact_id = "artifact-1"
    actor_id = _Entity("body-1")


def _config() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=11,
            stochastic_identity="cmp-v4-evidence-e2e",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-v4-evidence-e2e"),
                revision=WorldRevision(0),
                physical_rules=default_physical_rules(),
                locations=(make_location(),),
                bodies=(body,),
                weather=(make_weather(),),
            ),
            agents=(
                AgentRunnerSpec(
                    agent_id=agent_id,
                    entity_id=body.entity_id,
                    cognition=AgentCognitionSpec(agent_id=agent_id),
                ),
            ),
            max_ticks=2,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(legal_disputes=True),
    )


def _contested_ledger() -> EvidenceLedger:
    ledger = empty_evidence_ledger("agent-1")
    frame = EvidenceFrame(
        act=EvidenceAct.ASSERT_SOURCE,
        subject_token="artifact-1",
        source_kind=EvidenceSourceKind.ARTIFACT,
        reference_kind=EvidenceReferenceKind.ARTIFACT,
        reference_id="artifact-1",
        confidence_band="high",
    )
    supports = EvidenceFrame(
        act=EvidenceAct.INTERPRET,
        subject_token="artifact-1",
        interpretation=EvidenceInterpretationKind.SUPPORTS,
        reference_id="artifact-1",
        confidence_band="high",
    )
    contradicts = EvidenceFrame(
        act=EvidenceAct.INTERPRET,
        subject_token="artifact-1",
        interpretation=EvidenceInterpretationKind.CONTRADICTS,
        reference_id="artifact-1",
        confidence_band="low",
    )
    ledger = apply_evidence_update(
        ledger,
        owner_id="agent-1",
        tick=2,
        frames=(frame, supports, contradicts),
    )
    contradiction = EvidenceFrame(
        act=EvidenceAct.CONTRADICT,
        subject_token="artifact-1",
        contradiction_kind=EvidenceContradictionKind.INTERPRETATION_CONFLICT,
        first_ref=ledger.items[0].item_id,
        second_ref=ledger.items[1].item_id,
        confidence_band="mid",
    )
    return apply_evidence_update(
        ledger, owner_id="agent-1", tick=2, frames=(contradiction,)
    )


class _RunnerResult:
    def __init__(self, ledgers: tuple[object, ...]) -> None:
        self.evidence_ledgers = ledgers
        self.run_id = RUN
        self.ticks_committed = 2
        self.stop_reason = type("Stop", (), {"value": "completed"})()


@pytest.mark.asyncio
async def test_full_evidence_path(tmp_path: Path) -> None:
    async with await SimulationRunner.from_config(
        _config(), run_id=RunId(RUN)
    ) as runner:
        result = await runner.run()
    assert len(result.evidence_ledgers) == 1
    exported = cast(Any, result.evidence_ledgers[0])
    assert exported.owner_id == "agent-1"

    ledger = _contested_ledger()
    before = evidence_ledger_digest(ledger)
    events = (_Event(ArtifactDestroyed(), 1, _Entity("event-1")),)
    harvest = build_completed_run_evidence_harvest(
        _RunnerResult((ledger,)),
        committed_events=events,
        entity_to_agent={"body-1": "agent-1"},
    )
    assert harvest.analysis.summary.inconsistent_count == 1
    assert evidence_ledger_digest(ledger) == before

    built = build_evidence_testimony_harvest_result(harvest)
    store = tmp_path / "store"
    publish_evidence_testimony_snapshot(
        built, FilesystemEvidenceTestimonyPublisher(store)
    )
    reader = create_evidence_testimony_reader(store)
    assert reader is not None
    summary = reader.summary(run_id=RUN)
    assert summary.contradiction_count == 1

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_evidence_testimony_reader] = lambda: reader
    app.state.evidence_testimony_cursor_codec = EvidenceTestimonyCursorCodec(b"k" * 32)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/evidence",
            headers={"x-palimpsest-token": TOKEN},
        )
        assert response.status_code == 200
        assert response.json()["contradiction_count"] == 1

        candidates = await client.get(
            f"/v1/simulations/{RUN}/evidence/candidates",
            headers={"x-palimpsest-token": TOKEN},
        )
        assert candidates.status_code == 200
        candidate_id = candidates.json()["items"][0]["candidate_id"]
        for suffix in (
            f"/candidates/{candidate_id}",
            f"/candidates/{candidate_id}/sources",
            f"/candidates/{candidate_id}/contradictions",
            "/lineage",
        ):
            page = await client.get(
                f"/v1/simulations/{RUN}/evidence{suffix}",
                headers={"x-palimpsest-token": TOKEN},
            )
            assert page.status_code == 200, suffix


@pytest.mark.asyncio
async def test_foreign_ledger_is_not_carried() -> None:
    from agents.cognition import EvidenceError, require_owner_evidence

    with pytest.raises(EvidenceError):
        require_owner_evidence(empty_evidence_ledger("agent-2"), "agent-1")


class _ScriptedPlanner:
    """Choose one deterministic command; the rest of cognition is production."""

    def __init__(self, choose: Any) -> None:
        self._choose = choose

    async def plan(self, loop_input: Any, *args: Any, **kwargs: Any) -> ActionPlan:
        _ = (args, kwargs)
        return ActionPlan(
            owner_id=loop_input.agent_id,
            command=self._choose(loop_input.observation.tick),
            confidence=1.0,
        )


def _two_owner_config() -> SimulationRunnerConfig:
    bodies = (alive_body("body-a"), alive_body("body-b"))
    agents = (
        AgentRunnerSpec(
            agent_id=AgentId("agent-a"),
            entity_id=EntityId("body-a"),
            cognition=AgentCognitionSpec(agent_id=AgentId("agent-a")),
        ),
        AgentRunnerSpec(
            agent_id=AgentId("agent-b"),
            entity_id=EntityId("body-b"),
            cognition=AgentCognitionSpec(agent_id=AgentId("agent-b")),
        ),
    )
    return replace(
        base_runner_config_from_scenario(
            seed=11,
            stochastic_identity="cmp-v4-evidence-talk-e2e",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-v4-evidence-talk-e2e"),
                revision=WorldRevision(0),
                physical_rules=default_physical_rules(),
                locations=(make_location(),),
                bodies=bodies,
                weather=(make_weather(),),
            ),
            agents=agents,
            max_ticks=2,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(legal_disputes=True),
    )


def _testimony_talk() -> Talk:
    frame = EvidenceFrame(
        act=EvidenceAct.TESTIFY,
        subject_token="artifact-1",
        testimony_channel=EvidenceTestimonyChannel.DIRECT,
        confidence_band="high",
        witness_id="body-b",
    )
    talk = Talk(
        recipient_id=EntityId("body-a"),
        utterance=origin_utterance(
            text="evidence",
            speaker_id=EntityId("body-b"),
            communication_id="evidence-testify-body-b",
            relations=(),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    command = evidence_communicate_utterance(talk, frame)
    assert isinstance(command, Talk)
    return command


@pytest.mark.asyncio
async def test_two_owner_testimony_flows_through_real_cognition() -> None:
    """B testifies through ordinary Talk; A records the attributed testimony."""

    async with await SimulationRunner.from_config(
        _two_owner_config(), run_id=RunId("run-evidence-talk-e2e")
    ) as runner:
        for runtime in runner._runtimes:
            actor = runtime._agent.agent_id.value
            if actor == "agent-b":
                runtime._loop._planner = _ScriptedPlanner(
                    lambda tick: _testimony_talk() if tick == 0 else Wait()
                )
            else:
                runtime._loop._planner = _ScriptedPlanner(lambda tick: Wait())
        result = await runner.run()

    ledgers = {
        cast(Any, ledger).owner_id: cast(Any, ledger)
        for ledger in result.evidence_ledgers
    }
    assert set(ledgers) == {"agent-a", "agent-b"}

    reached = [
        row
        for row in ledgers["agent-a"].testimony
        if row.speaker_id == "body-b"
    ]
    assert len(reached) == 1
    assert reached[0].channel is EvidenceTestimonyChannel.DIRECT
    assert reached[0].root_ref is None

    declared = ledgers["agent-b"].testimony
    assert any(row.speaker_id == "body-b" for row in declared)
