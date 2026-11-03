"""V4-06 end-to-end: real commands, publication, read, and metrics."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition import (
    FormalRuleAct,
    FormalRuleAuthorityKind,
    FormalRuleClaim,
    FormalRuleConstraintKind,
    FormalRuleRecognition,
    FormalRuleResponse,
    FormalRuleScope,
    FormalRuleScopeKind,
    FormalRuleStage,
    apply_formal_rule_update,
    default_formal_rule_policy,
    formal_rule_claim_relation,
    formal_rule_id,
    formal_rule_system_id,
    select_formal_rule_response,
)
from agents.cognition.social_norms import (
    NormBelief,
    NormContext,
    NormExpectation,
    NormLedger,
    NormPattern,
    NormStatus,
    norm_belief_id,
)
from agents.models import AgentId
from api.dependencies import get_formal_rule_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.formal_rule_cursor import FormalRuleCursorCodec
from api.routes.formal_rule import router as formal_rule_router
from experiments.catalog import base_runner_config_from_scenario
from experiments.collectors import assemble_arm_metric_bundle
from experiments.formal_rule_harvest import build_completed_run_formal_rule_harvest
from experiments.formal_rule_publication import (
    build_formal_rule_harvest_result,
    publish_formal_rule_snapshot,
)
from infrastructure.settings import Settings
from persistence.formal_rule_filesystem import (
    create_formal_rule_publisher,
    create_formal_rule_reader,
)
from simulation import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunner,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.engine import WorldEngine
from simulation.formal_rule_models import FormalRuleArtifactError
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import RunId
from simulation.runner_models import example_durable_records_spec
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import alive_body, make_location, make_weather
from tests.unit.formal_rule_helpers import make_ledger
from world.actions import Give, Inscribe, Take
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.communications import CommunicationRelation
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.observations import Observation, ObservedArtifact, ObservedItemPlacement

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
RUN = "run-formal-rule-e2e"
TOKEN = "test-debug-token-0123456789abcdef"
SCOPE = FormalRuleScope(FormalRuleScopeKind.UNSPECIFIED, ())
ACTION = "maintain"


def _system_id(authority: FormalRuleAuthorityKind) -> str:
    return formal_rule_system_id(OWNER.value, SCOPE.digest, authority)


def _rule_id(
    authority: FormalRuleAuthorityKind,
    constraint: FormalRuleConstraintKind,
) -> str:
    return formal_rule_id(
        OWNER.value,
        _system_id(authority),
        constraint,
        ACTION,
        SCOPE.digest,
    )


def _support_claim(authority: FormalRuleAuthorityKind) -> FormalRuleClaim:
    return FormalRuleClaim(
        act=FormalRuleAct.SUPPORT,
        system_ref=_system_id(authority),
        rule_ref=_rule_id(authority, FormalRuleConstraintKind.OBLIGATION),
    )


def _claim_observation(
    *claims: FormalRuleClaim,
    tick: int = 1,
    artifacts: tuple[ObservedArtifact, ...] = (),
) -> SimpleNamespace:
    relations = tuple(
        CommunicationRelation(
            subject=subject, predicate=predicate, object=body
        )
        for claim in claims
        for subject, predicate, body in (formal_rule_claim_relation(claim),)
    )
    return SimpleNamespace(
        tick=tick,
        artifacts=artifacts,
        communications=(
            SimpleNamespace(
                speaker_id=EntityId("body-2"),
                utterance=SimpleNamespace(
                    content=SimpleNamespace(relations=relations)
                ),
            ),
        ),
    )


def _office() -> SimpleNamespace:
    return SimpleNamespace(
        concepts=(
            SimpleNamespace(
                status="recognized",
                duties=(SimpleNamespace(duty_kind=ACTION),),
                supporters=(),
            ),
        )
    )


def _norm() -> NormLedger:
    pattern = NormPattern.SHARED_UPKEEP
    return NormLedger(
        owner_id=OWNER,
        beliefs=(
            NormBelief(
                belief_id=norm_belief_id(OWNER, pattern),
                owner_id=OWNER,
                pattern=pattern,
                expectation=NormExpectation.MAINTAIN_STRUCTURE,
                context=NormContext(pattern=pattern),
                status=NormStatus.ACTIVE,
                confidence=0.7,
            ),
        ),
    )


def _observation() -> Observation:
    artifact = ObservedArtifact(
        entity_id=EntityId("artifact-1"),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-1"),
        created_tick=0,
        content=ArtifactContent(),
        content_revision=1,
        placement=ObservedItemPlacement.GROUND_HERE,
        record_genre=DurableRecordGenre.AGREEMENT,
        integrity=RecordIntegrity.INTACT,
    )
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=0,
        artifacts=(artifact,),
    )


def _interpretations() -> SimpleNamespace:
    return SimpleNamespace(
        interpretations=(
            SimpleNamespace(
                artifact_id=EntityId("artifact-1"),
                reading_marks=("maintain",),
                reading_relations=(),
            ),
        )
    )


def _runner_result() -> Any:
    ledgers = (
        make_ledger(
            owner="agent-1",
            action="maintain",
            constraint=FormalRuleConstraintKind.OBLIGATION,
            ticks=(0, 100),
        ),
        make_ledger(
            owner="agent-2",
            action="maintain",
            constraint=FormalRuleConstraintKind.PROHIBITION,
            ticks=(0, 100),
        ),
    )
    return SimpleNamespace(
        formal_rule_ledgers=ledgers,
        stop_reason="max_ticks",
        ticks_committed=100,
    )


def _built() -> Any:
    harvest = build_completed_run_formal_rule_harvest(
        _runner_result(),
        run_id=RUN,
        input_revision="revision-1",
        generated_tick=100,
    )
    return build_formal_rule_harvest_result(harvest)


def _client(root: Path) -> Any:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(formal_rule_router)
    app.dependency_overrides[get_settings] = lambda: Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
    )
    reader = create_formal_rule_reader(root)
    app.dependency_overrides[get_formal_rule_reader] = lambda: reader
    app.state.formal_rule_reader = reader
    app.state.formal_rule_cursor_codec = (
        FormalRuleCursorCodec(b"k" * 32, now=lambda: 1000.0)
        if reader is not None
        else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _engine() -> WorldEngine:
    return WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
    )


def _take(engine: WorldEngine) -> None:
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED


def test_formal_rule_progression_reaches_documented() -> None:
    ledger = apply_formal_rule_update(
        OWNER,
        0,
        _observation(),
        None,
        social_norms=_norm(),
        artifact_interpretations=_interpretations(),
    )
    assert ledger.rules
    assert ledger.rules[0].stage.value == "documented"
    assert ledger.rules[0].versions[-1].written is not None


def test_real_inscribed_record_promotes_documented_rule() -> None:
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
    )
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Inscribe(
                    kind=ArtifactKind.RECORD,
                    content=ArtifactContent(marks=(ACTION,)),
                    record_genre=DurableRecordGenre.AGREEMENT,
                ),
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED

    observation = engine.observe().for_observer(EntityId("body-1"))
    assert observation.artifacts
    artifact = observation.artifacts[0]
    interpretations = SimpleNamespace(
        interpretations=(
            SimpleNamespace(
                artifact_id=artifact.entity_id,
                reading_marks=(ACTION,),
                reading_relations=(),
            ),
        )
    )
    ledger = apply_formal_rule_update(
        OWNER,
        observation.tick,
        observation,
        None,
        social_norms=_norm(),
        artifact_interpretations=interpretations,
    )
    rule = ledger.rules[0]
    assert rule.stage is FormalRuleStage.DOCUMENTED
    assert rule.versions[-1].written is not None
    assert rule.versions[-1].written.artifact_id == artifact.entity_id.value


def test_formal_rule_progression_reaches_recognized_enforcement() -> None:
    ledger = apply_formal_rule_update(
        OWNER,
        1,
        _claim_observation(
            _support_claim(FormalRuleAuthorityKind.OFFICE),
            artifacts=tuple(_observation().artifacts),
        ),
        None,
        social_norms=_norm(),
        office_concepts=_office(),
        artifact_interpretations=_interpretations(),
    )
    rule = ledger.rules[0]
    assert rule.stage is FormalRuleStage.RECOGNIZED_ENFORCEMENT
    assert rule.recognition is FormalRuleRecognition.RECOGNIZED
    assert rule.versions[-1].stage is FormalRuleStage.RECOGNIZED_ENFORCEMENT


def test_formal_rules_and_organizations_flags_coexist_on_v56() -> None:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    config = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-formal-rule-e2e",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-formal-rule-e2e"),
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
    )
    configured = replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(
            formal_rules=True, organizations=True
        ),
    )

    async def execute() -> Any:
        async with await SimulationRunner.from_config(
            configured, run_id=RunId("run-formal-rule-e2e")
        ) as runner:
            assert runner.config.v4_capability_flags.owned_enabled_names() == (
                "organizations",
                "formal_rules",
            )
            return await runner.run()

    result = asyncio.run(execute())
    assert len(result.formal_rule_ledgers) == 1
    assert result.formal_rule_ledgers[0].owner_id == agent_id


def test_competing_systems_survive_publication_and_read(tmp_path: Path) -> None:
    built = _built()
    assert built.candidate_count == 2
    publisher = create_formal_rule_publisher(tmp_path)
    assert publisher is not None
    publish_formal_rule_snapshot(built, publisher)
    reader = create_formal_rule_reader(tmp_path)
    assert reader is not None
    page = reader.candidates(RUN, status=None, offset=0, limit=10)
    assert len(page.rows) == 2
    assert len({cast(Any, row).candidate_id for row in page.rows}) == 2


@pytest.mark.asyncio
async def test_snapshot_publication_and_six_route_read(tmp_path: Path) -> None:
    built = _built()
    publisher = create_formal_rule_publisher(tmp_path)
    assert publisher is not None
    publish_formal_rule_snapshot(built, publisher)

    headers = {"x-palimpsest-token": TOKEN}
    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/formal-rules", headers=headers
        )
        assert summary.status_code == 200
        assert summary.json()["publication_id"] == built.publication_id

        candidates = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/candidates", headers=headers
        )
        assert candidates.status_code == 200
        candidate_id = candidates.json()["items"][0]["candidate_id"]

        detail = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/candidates/{candidate_id}",
            headers=headers,
        )
        assert detail.status_code == 200

        rules = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/candidates/{candidate_id}/rules",
            headers=headers,
        )
        assert rules.status_code == 200
        rule_id = rules.json()["items"][0]["rule_id"]

        versions = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/candidates/"
            f"{candidate_id}/versions",
            headers=headers,
            params={"rule_id": rule_id},
        )
        assert versions.status_code == 200

        lineage = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/lineage", headers=headers
        )
        assert lineage.status_code == 200


def test_declared_responses_do_not_create_commands() -> None:
    ledger = make_ledger(action="give")
    _, response = select_formal_rule_response(
        ledger,
        tick=1,
        action_token="give",
        policy=default_formal_rule_policy(),
    )
    assert type(response) is FormalRuleResponse
    assert not hasattr(response, "to_agent_command")


def test_prohibited_but_possible_command_is_admitted() -> None:
    engine = _engine()
    _take(engine)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Give(EntityId("body-2"), EntityId("item-1")),
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED


def test_physically_impossible_command_is_rejected_independently() -> None:
    engine = _engine()
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Give(EntityId("body-2"), EntityId("item-1")),
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert "formal_rule" not in repr(result.resolutions[0])


def test_metric_assembly_emits_all_three_documents() -> None:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    config = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="metric-v4-formal-rule-e2e",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-formal-rule-metrics"),
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
    )
    arm = SimpleNamespace(
        assignment=SimpleNamespace(
            run_id=RunId(RUN),
            runner_config=config,
        ),
        runner_result=_runner_result(),
        config_fingerprint="a" * 64,
    )
    documents = assemble_arm_metric_bundle(arm)
    families = {document.metric_family for document in documents.documents}
    assert {
        "formal_rule_development",
        "formal_rule_authority",
        "formal_rule_response",
    } <= families


def test_publication_failure_changes_only_the_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import research_runner.formal_rule_composition as composition

    def _fail(*args: object, **kwargs: object) -> None:
        raise FormalRuleArtifactError("formal_rule_digest_mismatch")

    monkeypatch.setattr(composition, "publish_formal_rule_snapshot", _fail)
    result = _runner_result()
    before_ledgers = tuple(result.formal_rule_ledgers)
    before_repr = repr(result)
    receipt = composition.publish_formal_rule_harvest(
        result,
        run_id=RUN,
        input_revision="revision-1",
        generated_tick=100,
        options=composition.FormalRuleProducerOptions(root=tmp_path),
    )
    assert receipt == {
        "status": "failed",
        "reason_code": "formal_rule_digest_mismatch",
    }
    assert tuple(result.formal_rule_ledgers) == before_ledgers
    assert repr(result) == before_repr


def test_repeated_scenario_is_byte_identical() -> None:
    first = _built()
    second = _built()
    assert first.snapshot_digest == second.snapshot_digest
    assert first.publication_id == second.publication_id
