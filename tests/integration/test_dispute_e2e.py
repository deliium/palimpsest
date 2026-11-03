"""V4-07 end-to-end contested-debt/ownership dispute through real surfaces.

No PostgreSQL, Docker, provider, or network is required: the runner, engine,
admission, cognition update, publication store, and API all run in-process.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_weather,
    weather_for_locations,
)
from tests.unit.formal_rule_helpers import make_ledger as make_formal_rule_ledger

from agents.cognition import (
    DisputeAct,
    DisputeClaimKind,
    DisputeClaimPolarity,
    DisputeClaimRole,
    DisputeFrame,
    DisputeKind,
    DisputeLedger,
    DisputeMediationLinkStatus,
    DisputeResolution,
    DisputeResolutionResponseKind,
    DisputeResolutionSource,
    DisputeResolutionStatus,
    DisputeResolutionTerm,
    DisputeResolutionTermKind,
    DisputeRuleReferenceStatus,
    DisputeSubjectKind,
    FormalRuleConstraintKind,
    apply_dispute_update,
    compile_dispute_undertaking,
    dispute_case_ref,
    dispute_claim_ref,
    dispute_frame_relation,
    dispute_resolution_ref,
    dispute_subject_digest,
    dispute_terms_digest,
    link_mediation_references,
    propose_dispute_resolution,
    record_dispute_resolution_response,
)
from agents.cognition.legal_dispute_communication import dispute_communicate_utterance
from agents.cognition.mediation import (
    MediationCase,
    MediationCaseStatus,
    MediationLedger,
    MediationRecommendation,
    MediationRecommendationStatus,
    mediation_case_id,
    mediation_recommendation_id,
)
from agents.cognition.models import (
    ActionPlan,
    CounterpartBinding,
    OwnerSafeSocialIdentity,
)
from agents.models import AgentId
from analysis.dispute_contract import DISPUTE_FORBIDDEN_RESULT_FIELDS
from analysis.dispute_evidence import (
    build_dispute_windows,
    dispute_objective_anchor_rows_from_events,
)
from analysis.dispute_layers import project_dispute_layers
from analysis.dispute_lineage import derive_dispute_lineage, summarize_disputes
from analysis.disputes import harvest_dispute_rows
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from api.dependencies import get_dispute_reader, get_settings
from api.dispute_cursor import DisputeCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.dispute import router as dispute_router
from experiments.catalog import base_runner_config_from_scenario
from experiments.dispute_harvest import build_completed_run_dispute_harvest
from infrastructure.settings import Settings
from persistence.dispute_filesystem import create_dispute_reader
from research_runner.dispute_composition import (
    DisputeProducerOptions,
    publish_dispute_harvest,
)
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from world.actions import Give, Take, Talk, Wait
from world.communications import CommunicationSourceBasis, origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
)

AGENTS = ("agent-a", "agent-b", "agent-c", "agent-d")
BODIES = ("body-a", "body-b", "body-c", "body-d")
SUBJECT = "item-1"
CASE_REF = dispute_case_ref(SUBJECT, ("agent-a", "agent-b"))
SUBJECT_DIGEST = dispute_subject_digest(DisputeSubjectKind.ITEM, SUBJECT)
A_CLAIM_REF = dispute_claim_ref(
    CASE_REF,
    "agent-a",
    DisputeClaimRole.CLAIM,
    DisputeClaimKind.DEBT_OWED,
    DisputeClaimPolarity.AFFIRM,
    SUBJECT_DIGEST,
)
B_COUNTER_REF = dispute_claim_ref(
    CASE_REF,
    "agent-b",
    DisputeClaimRole.COUNTERCLAIM,
    DisputeClaimKind.ITEM_OWNED,
    DisputeClaimPolarity.DENY,
    SUBJECT_DIGEST,
)
TERMS = (
    DisputeResolutionTerm(
        term_kind=DisputeResolutionTermKind.TRANSFER_ITEM,
        party_id="agent-a",
        counterparty_id="agent-b",
        item_token=SUBJECT,
        quantity=1,
    ),
)
TERMS_DIGEST = dispute_terms_digest(TERMS)
RESOLUTION_REF = dispute_resolution_ref(CASE_REF, "agent-a", TERMS_DIGEST)


class _ScriptedPlanner:
    """Choose one deterministic command; the rest of cognition is production."""

    def __init__(self, choose: Any, *, actor: str) -> None:
        self._choose = choose
        self._actor = actor

    async def plan(
        self, loop_input: Any, intention: Any, futures: Any, *args: Any, **kwargs: Any
    ) -> ActionPlan:
        _ = (intention, futures, args, kwargs)
        command = self._choose(loop_input.observation.tick)
        return ActionPlan(owner_id=loop_input.agent_id, command=command, confidence=1.0)


def _talk(actor: str, recipient: str, frame: DisputeFrame) -> Talk:
    body = BODIES[AGENTS.index(actor)]
    target = BODIES[AGENTS.index(recipient)]
    talk = Talk(
        recipient_id=EntityId(target),
        utterance=origin_utterance(
            text="dispute",
            speaker_id=EntityId(body),
            communication_id=f"dispute-{frame.act.value}-{actor}",
            relations=(),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    return dispute_communicate_utterance(talk, frame)  # type: ignore[return-value]


def _claim_frame(actor: str, frame_kind: DisputeKind) -> DisputeFrame:
    role = (
        DisputeClaimRole.CLAIM if actor == "agent-a" else DisputeClaimRole.COUNTERCLAIM
    )
    return DisputeFrame(
        act=DisputeAct.CLAIM if actor == "agent-a" else DisputeAct.COUNTERCLAIM,
        case_ref=CASE_REF,
        claim_ref=None if actor == "agent-a" else A_CLAIM_REF,
        role=role,
        kind=frame_kind,
        polarity=(
            DisputeClaimPolarity.AFFIRM
            if actor == "agent-a"
            else DisputeClaimPolarity.DENY
        ),
        party_ref=BODIES[AGENTS.index(actor)],
        subject_kind=DisputeSubjectKind.ITEM,
        subject_token=SUBJECT,
    )


def _script(actor: str, rule_ref: str, other_rule_ref: str) -> Any:
    def talk(recipient: str, frame: DisputeFrame) -> Talk:
        return _talk(actor, recipient, frame)

    def choose(tick: int) -> Any:
        if actor == "agent-a":
            if tick == 0:
                return talk(
                    "agent-b", _claim_frame("agent-a", DisputeKind.CONTESTED_DEBT)
                )
            if tick == 1:
                return talk(
                    "agent-b",
                    DisputeFrame(
                        act=DisputeAct.CITE_RULE,
                        case_ref=CASE_REF,
                        claim_ref=A_CLAIM_REF,
                        rule_ref=f"{rule_ref}@1",
                    ),
                )
            if tick == 3:
                return talk(
                    "agent-b",
                    DisputeFrame(
                        act=DisputeAct.PROPOSE_RESOLUTION,
                        case_ref=CASE_REF,
                        resolution_ref=RESOLUTION_REF,
                        terms_digest=TERMS_DIGEST,
                        terms=TERMS,
                    ),
                )
            if tick == 5:
                return talk(
                    "agent-b",
                    DisputeFrame(
                        act=DisputeAct.ACCEPT_RESOLUTION,
                        case_ref=CASE_REF,
                        resolution_ref=RESOLUTION_REF,
                        party_ref="body-a",
                        terms_digest=TERMS_DIGEST,
                    ),
                )
            return Wait()
        if actor == "agent-b":
            if tick == 1:
                return talk(
                    "agent-a",
                    _claim_frame("agent-b", DisputeKind.OWNERSHIP_CLAIM),
                )
            if tick == 2:
                return talk(
                    "agent-a",
                    DisputeFrame(
                        act=DisputeAct.CITE_RULE,
                        case_ref=CASE_REF,
                        claim_ref=B_COUNTER_REF,
                        rule_ref=f"{other_rule_ref}@1",
                    ),
                )
            if tick == 5:
                return talk(
                    "agent-a",
                    DisputeFrame(
                        act=DisputeAct.ACCEPT_RESOLUTION,
                        case_ref=CASE_REF,
                        resolution_ref=RESOLUTION_REF,
                        party_ref="body-b",
                        terms_digest=TERMS_DIGEST,
                    ),
                )
            return Wait()
        if actor == "agent-c":
            if tick == 1:
                return talk(
                    "agent-a",
                    DisputeFrame(
                        act=DisputeAct.TESTIFY,
                        case_ref=CASE_REF,
                        claim_ref=A_CLAIM_REF,
                        party_ref="body-c",
                        direct=True,
                        root_ref="root-c",
                    ),
                )
            return Wait()
        if actor == "agent-d":
            if tick == 2:
                return talk(
                    "agent-a",
                    DisputeFrame(
                        act=DisputeAct.TESTIFY,
                        case_ref=CASE_REF,
                        claim_ref=A_CLAIM_REF,
                        party_ref="body-d",
                        direct=False,
                        root_ref="root-c",
                    ),
                )
            return Wait()
        return Wait()

    return choose


def _config(*, max_ticks: int = 7) -> SimulationRunnerConfig:
    bodies = tuple(
        alive_body(body, inventory=(EntityId(f"item-{index + 1}"),))
        if index in (0, 1)
        else alive_body(body)
        for index, body in enumerate(BODIES)
    )
    base = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-dispute-e2e",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-dispute-e2e"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=bodies,
            items=(
                make_item("item-1", holder_id="body-a", location_id=None),
                make_item("item-2", holder_id="body-b", location_id=None),
            ),
            weather=(make_weather(),),
        ),
        agents=tuple(
            AgentRunnerSpec(
                agent_id=AgentId(agent),
                entity_id=EntityId(body),
                cognition=AgentCognitionSpec(agent_id=AgentId(agent)),
            )
            for agent, body in zip(AGENTS, BODIES, strict=True)
        ),
        max_ticks=max_ticks,
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(
            legal_disputes=True,
            formal_rules=True,
        ),
    )


@dataclass(frozen=True)
class _Scenario:
    result: Any
    run_id: str
    config: SimulationRunnerConfig
    ledgers: dict[str, DisputeLedger]


def _run(max_ticks: int = 7) -> _Scenario:
    config = _config(max_ticks=max_ticks)
    a_rules = make_formal_rule_ledger(
        owner="agent-a",
        action="give",
        constraint=FormalRuleConstraintKind.OBLIGATION,
        ticks=(0,),
    )
    b_rules = make_formal_rule_ledger(
        owner="agent-b",
        action="give",
        constraint=FormalRuleConstraintKind.PERMISSION,
        ticks=(0,),
    )
    a_rule_ref = a_rules.rules[0].rule_id
    b_rule_ref = b_rules.rules[0].rule_id

    async def run() -> _Scenario:
        run_id = f"run-dispute-e2e-{max_ticks}"
        async with await SimulationRunner.from_config(
            config, run_id=RunId(run_id)
        ) as runner:
            for runtime in runner._runtimes:
                actor = runtime._agent.agent_id.value
                if actor == "agent-a":
                    runtime._formal_rules = a_rules
                elif actor == "agent-b":
                    runtime._formal_rules = b_rules
                runtime._loop._planner = _ScriptedPlanner(
                    _script(actor, a_rule_ref, b_rule_ref), actor=actor
                )
            result = await runner.run()
        ledgers = {
            ledger.owner_id: ledger
            for ledger in result.dispute_ledgers
            if isinstance(ledger, DisputeLedger)
        }
        return _Scenario(result=result, run_id=run_id, config=config, ledgers=ledgers)

    return asyncio.run(run())


@pytest.fixture(scope="module")
def scenario() -> _Scenario:
    return _run()


def _metric_documents(result: Any) -> dict[str, Any]:
    rows = harvest_dispute_rows(tuple(result.dispute_ledgers or ()))
    windows = build_dispute_windows(rows, window_ticks=100)
    analysis = derive_dispute_lineage(rows, windows)
    summary = summarize_disputes(rows, analysis)
    layers = project_dispute_layers(rows, analysis, summary, windows=windows)
    inputs = MetricComputationInputs(
        run_id=str(result.run_id),
        input_revision="revision-e2e",
        window_end=int(result.ticks_committed),
        dispute_rows=rows,
        dispute_objective_rows=dispute_objective_anchor_rows_from_events(
            (), entity_to_agent={"body-a": "agent-a", "body-b": "agent-b"}
        ),
    )
    assembled = assemble_metric_documents(inputs)
    documents = {document.metric_family: document for document in assembled.documents}
    assert layers.digest
    assert summary.determinism_digest
    return documents


def _api_client(root: Path) -> httpx.AsyncClient:
    token = "dispute-e2e-token-0123456789abcdef"
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(dispute_router)
    settings = Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(token),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_dispute_reader(root)
    assert reader is not None
    app.dependency_overrides[get_dispute_reader] = lambda: reader
    app.state.dispute_cursor_codec = DisputeCursorCodec(b"k" * 32, now=lambda: 1000.0)
    app.state.dispute_reader = reader
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"x-palimpsest-token": token},
    )


def _claim_ledger() -> tuple[DisputeLedger, Observation]:
    relation = dispute_frame_relation(
        DisputeFrame(
            act=DisputeAct.CLAIM,
            case_ref=CASE_REF,
            role=DisputeClaimRole.CLAIM,
            kind=DisputeKind.CONTESTED_DEBT,
            polarity=DisputeClaimPolarity.AFFIRM,
            party_ref="body-b",
            subject_kind=DisputeSubjectKind.ITEM,
            subject_token=SUBJECT,
        )
    )
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=1,
            source_event_id=EventId("event-claim"),
        ),
        speaker_id=EntityId("body-b"),
        listener_id=EntityId("body-a"),
        utterance=origin_utterance(
            text="statement",
            speaker_id=EntityId("body-b"),
            communication_id="comm-claim",
            relations=(relation,),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
        action_kind="tell",
    )
    observation = Observation(
        world_id=WorldId("world-e2e"),
        observer_id=EntityId("body-a"),
        revision=WorldRevision(2),
        tick=2,
        communications=(communication,),
    )
    identity = OwnerSafeSocialIdentity(
        owner_id=AgentId("agent-a"),
        owner_entity_id=EntityId("body-a"),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId("agent-b"), entity_id=EntityId("body-b")
            ),
        ),
    )
    ledger = apply_dispute_update("agent-a", 2, observation, None, identity=identity)
    assert ledger.cases
    return ledger, observation


def _physical_bootstrap() -> WorldBootstrap:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldBootstrap(
        world_id=WorldId("world-physical"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("body-a", inventory=(EntityId(SUBJECT),)),
            alive_body("body-b"),
        ),
        items=(make_item(SUBJECT, holder_id="body-a", location_id=None),),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-a"), EntityId("body-a")),
            AgentRegistration(AgentId("agent-b"), EntityId("body-b")),
        ),
    )


def test_contested_debt_and_ownership_dispute_e2e(
    scenario: _Scenario, tmp_path: Path
) -> None:
    a = scenario.ledgers["agent-a"]
    b = scenario.ledgers["agent-b"]

    assert a.cases and b.cases
    assert a.cases[0].status.value == "apparently_resolved"
    assert b.cases[0].status.value == "apparently_resolved"
    assert {claim.claimant_id for claim in a.claims} == {"agent-a", "agent-b"}
    assert {claim.claimant_id for claim in b.claims} == {"agent-a", "agent-b"}
    assert {claim.role.value for claim in a.claims} == {"claim", "counterclaim"}
    assert a.cases[0].party_ids == ("agent-a", "agent-b")

    assert any(
        testimony.speaker_id == "agent-c"
        and testimony.channel.value == "direct"
        and testimony.independently_evidenced
        for testimony in a.testimony
    )
    retold = next(
        testimony for testimony in a.testimony if testimony.speaker_id == "agent-d"
    )
    assert retold.channel.value == "communicated"
    assert retold.independently_evidenced is False
    assert retold.root_ref == "root-c"

    a_statuses = {ref.status for ref in a.rule_references}
    b_statuses = {ref.status for ref in b.rule_references}
    assert DisputeRuleReferenceStatus.RESOLVED in a_statuses
    assert DisputeRuleReferenceStatus.ORPHANED in a_statuses
    assert DisputeRuleReferenceStatus.RESOLVED in b_statuses
    assert DisputeRuleReferenceStatus.ORPHANED in b_statuses
    resolved_a = next(
        ref
        for ref in a.rule_references
        if ref.status is DisputeRuleReferenceStatus.RESOLVED
    )
    resolved_b = next(
        ref
        for ref in b.rule_references
        if ref.status is DisputeRuleReferenceStatus.RESOLVED
    )
    assert resolved_a.constraint_kind == "obligation"
    assert resolved_b.constraint_kind == "permission"

    resolution = next(
        row for row in a.resolutions if row.resolution_ref == RESOLUTION_REF
    )
    assert resolution.status is DisputeResolutionStatus.APPARENTLY_ACCEPTED
    active_accepts = {
        response.party_id
        for response in a.resolution_responses
        if response.resolution_ref == resolution.resolution_ref
        and response.active
        and response.kind is DisputeResolutionResponseKind.ACCEPT
    }
    assert active_accepts == {"agent-a", "agent-b"}
    assert "binding" not in DisputeResolution.__dataclass_fields__
    assert "enforced_by_world" not in DisputeResolution.__dataclass_fields__

    for ledger in (a, b):
        names = {field.name for field in fields(type(ledger))}
        assert not names & DISPUTE_FORBIDDEN_RESULT_FIELDS
        assert "objective_supported_claim_ratio" not in repr(ledger)

    receipt = publish_dispute_harvest(
        scenario.result, DisputeProducerOptions(root=tmp_path)
    )
    assert receipt["status"] == "published"
    assert receipt["publication_id"]

    documents = _metric_documents(scenario.result)
    for family in (
        "dispute_claim_structure",
        "dispute_testimony_independence",
        "dispute_resolution_alignment",
    ):
        assert family in documents
        assert documents[family].availability is MetricAvailability.PRESENT
        assert documents[family].values
    alignment = documents["dispute_resolution_alignment"].values
    assert "objective_supported_claim_ratio" in alignment
    assert "objective_inconsistent_claim_ratio" in alignment
    assert all("verdict" not in key for key in alignment)


def test_conflicting_memories_produce_separate_claims(scenario: _Scenario) -> None:
    a = scenario.ledgers["agent-a"]
    b = scenario.ledgers["agent-b"]
    assert a is not b
    assert a.owner_id == "agent-a"
    assert b.owner_id == "agent-b"

    a_own = next(claim for claim in a.claims if claim.claimant_id == "agent-a")
    b_own = next(claim for claim in b.claims if claim.claimant_id == "agent-b")
    assert a_own.owner_id == "agent-a"
    assert b_own.owner_id == "agent-b"
    assert a_own.polarity is DisputeClaimPolarity.AFFIRM
    assert b_own.polarity is DisputeClaimPolarity.DENY
    assert a_own.claim_kind is DisputeClaimKind.DEBT_OWED
    assert b_own.claim_kind is DisputeClaimKind.ITEM_OWNED
    assert a_own.claim_ref != b_own.claim_ref
    assert a_own.subject_token == b_own.subject_token == SUBJECT
    assert a.cases[0].case_ref == b.cases[0].case_ref == CASE_REF


def test_real_checkpoint_round_trip_preserves_dispute_ledgers(
    tmp_path: Path,
) -> None:
    config = _config(max_ticks=2)

    async def round_trip() -> tuple[Any, Any]:
        run_id = RunId("run-dispute-e2e-checkpoint")
        async with await SimulationRunner.from_config(config, run_id=run_id) as runner:
            for runtime in runner._runtimes:
                actor = runtime._agent.agent_id.value
                runtime._loop._planner = _ScriptedPlanner(
                    _script(actor, "unused", "unused"), actor=actor
                )
            await runner.run()
            checkpoint = runner.export_runtime_checkpoint()
            exported = {
                ledger.owner_id: ledger
                for ledger in runner.export_dispute_ledgers()
                if isinstance(ledger, DisputeLedger)
            }
        async with await SimulationRunner.from_config(
            config, run_id=run_id
        ) as restored:
            restored.apply_runtime_checkpoint(checkpoint)
            return exported, {
                ledger.owner_id: ledger
                for ledger in restored.export_dispute_ledgers()
                if isinstance(ledger, DisputeLedger)
            }

    before, restored = asyncio.run(round_trip())
    assert before["agent-a"].claims
    assert before["agent-b"].claims
    assert restored == before
    assert restored["agent-a"].owner_id == "agent-a"
    assert "binding" not in DisputeResolution.__dataclass_fields__


def test_mediation_recommendation_is_not_binding(tmp_path: Path) -> None:
    ledger, _ = _claim_ledger()
    case = ledger.cases[0]
    mediation_case_ref = "d" * 64
    mediation_context = "e" * 16
    mediation = MediationLedger(
        owner_id=AgentId("agent-a"),
        cases=(
            MediationCase(
                case_id=mediation_case_id(AgentId("agent-a"), mediation_case_ref),
                owner_id=AgentId("agent-a"),
                case_ref=mediation_case_ref,
                subject_token=SUBJECT,
                context_key=mediation_context,
                status=MediationCaseStatus.UNRESOLVED,
                first_tick=2,
                last_tick=2,
                window_first_tick=2,
                window_last_tick=66,
                origin_id=AgentId("agent-b"),
                party_ids=(AgentId("agent-a"), AgentId("agent-b")),
            ),
        ),
        recommendations=(
            MediationRecommendation(
                recommendation_id=mediation_recommendation_id(
                    AgentId("agent-a"), mediation_case_ref, 0
                ),
                owner_id=AgentId("agent-a"),
                case_ref=mediation_case_ref,
                revision=0,
                proposed_actor_id=AgentId("agent-a"),
                action_token="give",
                first_tick=2,
                last_tick=2,
                window_first_tick=2,
                window_last_tick=66,
                status=MediationRecommendationStatus.ACTIVE,
                originator_id=AgentId("agent-b"),
                target_ids=(AgentId("agent-b"),),
                item_token=SUBJECT,
                quantity=1,
            ),
        ),
    )
    linked = link_mediation_references(
        ledger, mediation=mediation, owner_id="agent-a", tick=3
    )
    link = linked.mediation_references[0]
    assert link.link_status is DisputeMediationLinkStatus.LINKED
    assert link.recommendation_ref is not None
    mediator = next(
        resolution
        for resolution in linked.resolutions
        if resolution.source is DisputeResolutionSource.MEDIATOR
    )
    assert mediator.status is DisputeResolutionStatus.PROPOSED
    assert "binding" not in DisputeResolution.__dataclass_fields__
    assert "enforced_by_world" not in DisputeResolution.__dataclass_fields__

    accepted = record_dispute_resolution_response(
        linked,
        owner_id="agent-a",
        resolution_ref=mediator.resolution_ref,
        party_id="agent-a",
        kind=DisputeResolutionResponseKind.ACCEPT,
        tick=3,
        terms_digest=mediator.terms_digest,
        verified_speaker="agent-a",
    )
    assert (
        next(
            row
            for row in accepted.resolutions
            if row.resolution_id == mediator.resolution_id
        ).status
        is DisputeResolutionStatus.PARTIALLY_ACCEPTED
    )
    assert (
        compile_dispute_undertaking(
            accepted,
            owner_id="agent-a",
            tick=3,
            identity=OwnerSafeSocialIdentity(
                owner_id=AgentId("agent-a"),
                owner_entity_id=EntityId("body-a"),
                counterparts=(),
            ),
            inventory=(),
            mediation=mediation,
        )
        is None
    )
    assert case.case_ref == CASE_REF


def test_same_tick_acceptance_is_refused_then_next_tick_succeeds(
    tmp_path: Path,
) -> None:
    ledger, _ = _claim_ledger()
    case = ledger.cases[0]
    proposed = propose_dispute_resolution(
        ledger,
        owner_id="agent-a",
        case_ref=case.case_ref,
        proposer_id="agent-a",
        source="unilateral",
        terms=TERMS,
        tick=2,
    )
    resolution = proposed.resolutions[0]
    same_tick = record_dispute_resolution_response(
        proposed,
        owner_id="agent-a",
        resolution_ref=resolution.resolution_ref,
        party_id="agent-b",
        kind=DisputeResolutionResponseKind.ACCEPT,
        tick=2,
        terms_digest=resolution.terms_digest,
        verified_speaker="agent-b",
    )
    assert "dispute_resolution_requires_prior_tick" in same_tick.notices
    assert same_tick.resolution_responses == ()

    next_tick = record_dispute_resolution_response(
        proposed,
        owner_id="agent-a",
        resolution_ref=resolution.resolution_ref,
        party_id="agent-b",
        kind=DisputeResolutionResponseKind.ACCEPT,
        tick=3,
        terms_digest=resolution.terms_digest,
        verified_speaker="agent-b",
    )
    assert next_tick.resolution_responses
    current = next_tick.resolutions[0]
    assert current.status is DisputeResolutionStatus.PARTIALLY_ACCEPTED
    assert current.first_tick == 2


def test_publication_failure_preserves_scientific_result(
    scenario: _Scenario, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before_ledgers = tuple(scenario.result.dispute_ledgers or ())
    before_documents = _metric_documents(scenario.result)

    class _FailingPublisher:
        def publish(self, publication: object) -> None:
            _ = publication
            raise OSError("injected publication failure")

    import research_runner.dispute_composition as composition

    monkeypatch.setattr(
        composition, "create_dispute_publisher", lambda *a, **k: _FailingPublisher()
    )
    receipt = publish_dispute_harvest(
        scenario.result, DisputeProducerOptions(root=tmp_path)
    )
    assert receipt["status"] == "failed"
    assert receipt["published"] is False
    assert tuple(scenario.result.dispute_ledgers or ()) == before_ledgers
    after_documents = _metric_documents(scenario.result)
    assert set(before_documents) == set(after_documents)
    for family, document in before_documents.items():
        assert dict(document.values) == dict(after_documents[family].values)


def test_physical_admission_is_independent_of_dispute_belief(
    scenario: _Scenario,
) -> None:
    assert scenario.ledgers["agent-a"].cases
    engine = WorldEngine(
        config=SimulationRunConfig(seed=21), bootstrap=_physical_bootstrap()
    )
    batch = engine.observe()
    accepted = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-a"),
                command=Give(
                    recipient_id=EntityId("body-b"), item_id=EntityId(SUBJECT)
                ),
            ),
        )
    )
    assert accepted.resolutions[0].status is not ActionResolutionStatus.REJECTED
    batch = engine.observe()
    observed = engine.observation_for(AgentId("agent-b"))
    assert observed.self_body is not None
    assert observed.self_body.inventory == (EntityId(SUBJECT),)

    rejected = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-a"),
                command=Take(item_id=EntityId("item-missing")),
            ),
        )
    )
    resolution = rejected.resolutions[0]
    assert resolution.status is ActionResolutionStatus.REJECTED
    assert resolution.reason is not None
    assert resolution.reason.value == "invalid_target"


def test_api_reads_are_committed_artifacts_only(
    scenario: _Scenario, tmp_path: Path
) -> None:
    receipt = publish_dispute_harvest(
        scenario.result, DisputeProducerOptions(root=tmp_path)
    )
    assert receipt["status"] == "published"

    async def read() -> dict[str, Any]:
        async with _api_client(tmp_path) as client:
            summary = await client.get(f"/v1/simulations/{scenario.run_id}/disputes")
            candidates = await client.get(
                f"/v1/simulations/{scenario.run_id}/disputes/candidates"
            )
            assert summary.status_code == 200
            assert candidates.status_code == 200
            candidate_id = candidates.json()["items"][0]["candidate_id"]
            detail = await client.get(
                f"/v1/simulations/{scenario.run_id}/disputes/candidates/{candidate_id}"
            )
            claims = await client.get(
                f"/v1/simulations/{scenario.run_id}/disputes/candidates/{candidate_id}/claims"
            )
            resolutions = await client.get(
                f"/v1/simulations/{scenario.run_id}/disputes/candidates/{candidate_id}/resolutions"
            )
            lineage = await client.get(
                f"/v1/simulations/{scenario.run_id}/disputes/lineage"
            )
            return {
                "summary": summary.json(),
                "candidate_id": candidate_id,
                "detail": detail.json(),
                "claims": claims.json(),
                "resolutions": resolutions.json(),
                "lineage": lineage.json(),
            }

    payload = asyncio.run(read())
    assert payload["summary"]["candidate_count"] >= 1
    assert payload["detail"]["candidate"]["candidate_id"] == payload["candidate_id"]
    assert payload["claims"]["items"]
    assert payload["resolutions"]["items"]
    assert "items" in payload["lineage"]
    assert payload["summary"]["snapshot_digest"]
    assert receipt["publication_id"] == payload["summary"]["publication_id"]


def test_harvest_matches_published_candidate_and_claims(
    scenario: _Scenario, tmp_path: Path
) -> None:
    harvest = build_completed_run_dispute_harvest(
        scenario.result,
        run_id=scenario.run_id,
        input_revision="revision-e2e",
        generated_tick=int(scenario.result.ticks_committed),
    )
    assert harvest.analysis.candidates
    assert harvest.rows.claims
    assert harvest.coverage.observed <= harvest.coverage.expected
    receipt = publish_dispute_harvest(
        scenario.result, DisputeProducerOptions(root=tmp_path)
    )
    assert receipt["status"] == "published"
    assert receipt["candidate_count"] == len(harvest.analysis.candidates)
