"""V4-09 end-to-end: real run -> beliefs -> snapshot -> store -> API."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

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

from agents.cognition import (
    RepresentationConflictKind,
    RepresentationDurationKind,
    RepresentationMandate,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationRecognitionBasis,
    RepresentationScopeKind,
    RepresentationStatus,
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
from analysis import MetricAvailability
from api.delegation_representation_cursor import (
    DelegationRepresentationCursorCodec,
)
from api.dependencies import get_delegation_representation_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.routes.delegation_representation import router
from experiments.catalog import base_runner_config_from_scenario
from experiments.collectors import assemble_arm_metric_bundle, collect_catalog_metrics
from experiments.delegation_representation_harvest import (
    build_completed_run_representation_harvest,
)
from experiments.delegation_representation_publication import (
    build_representation_harvest_result,
    publish_representation_snapshot,
)
from infrastructure.settings import Settings
from persistence.delegation_representation_filesystem import (
    FilesystemDelegationRepresentationPublisher,
    create_delegation_representation_reader,
)
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.delegation_representation_ports import (
    delegation_representation_query_fingerprint,
)
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
from world.actions import Give, Take
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.integration

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-representation-e2e"
OWNER = "agent-1"
PRINCIPAL = "agent-principal"
REP = "agent-representative"


def _config() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId(OWNER)
    return replace(
        base_runner_config_from_scenario(
            seed=11,
            stochastic_identity="cmp-v4-representation-e2e",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-v4-representation-e2e"),
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
        v4_capability_flags=V4CapabilityFlags(organizations=True),
    )


def _frame(
    act: RepresentationAct,
    *,
    mandate_ref: str | None = None,
    actor: str = REP,
    principal_kind: RepresentationPrincipalKind = RepresentationPrincipalKind.AGENT,
    principal: str | None = PRINCIPAL,
    representative: str = REP,
    scope_kind: RepresentationScopeKind = RepresentationScopeKind.SPEAK_FOR,
    scope_subject: str | None = "border",
    duration_kind: RepresentationDurationKind = (
        RepresentationDurationKind.UNTIL_REVOKED
    ),
    end_tick: int | None = None,
    provenance: RepresentationProvenance = RepresentationProvenance.SELF_DECLARED,
) -> RepresentationFrame:
    return RepresentationFrame(
        act=act,
        mandate_ref=mandate_ref,
        principal_kind=principal_kind,
        principal_ref=principal,
        representative_ref=representative,
        scope_kind=scope_kind,
        scope_subject=scope_subject,
        duration_kind=duration_kind,
        end_tick=end_tick,
        provenance=provenance,
        actor_ref=actor,
    )


def _mandate(
    ledger: RepresentationLedger,
    *,
    principal_kind: RepresentationPrincipalKind,
    principal_ref: str | None,
    representative: str,
) -> RepresentationMandate:
    return next(
        mandate
        for mandate in ledger.mandates
        if mandate.principal_kind is principal_kind
        and mandate.principal_ref == principal_ref
        and mandate.representative_id == representative
    )


def _scenario(ledger: RepresentationLedger) -> RepresentationLedger:
    policy = default_representation_policy()
    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=3,
        observation=None,
        prior=ledger,
        frames=(_frame(RepresentationAct.CLAIM),),
        policy=policy,
    )
    claimed = _mandate(
        ledger,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=PRINCIPAL,
        representative=REP,
    )
    mandate_id = claimed.mandate_id
    assert claimed.status is RepresentationStatus.CLAIMED

    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=4,
        observation=None,
        prior=ledger,
        frames=(
            _frame(RepresentationAct.SUPPORT, mandate_ref=mandate_id, actor="agent-c"),
            _frame(RepresentationAct.OPPOSE, mandate_ref=mandate_id, actor="agent-d"),
        ),
        policy=policy,
    )
    contested = _mandate(
        ledger,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=PRINCIPAL,
        representative=REP,
    )
    assert contested.status is RepresentationStatus.CONTESTED
    assert len(ledger.positions) == 2

    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=5,
        observation=None,
        prior=ledger,
        frames=(
            _frame(
                RepresentationAct.ACCEPT,
                mandate_ref=mandate_id,
                actor=PRINCIPAL,
            ),
        ),
        policy=policy,
    )
    accepted = _mandate(
        ledger,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=PRINCIPAL,
        representative=REP,
    )
    assert accepted.status is RepresentationStatus.RECOGNIZED
    assert (
        accepted.recognition_basis
        is RepresentationRecognitionBasis.PRINCIPAL_DECLARATION
    )

    # The principal delegates the same standing to a second agent. Both
    # recognized mandates coexist and are flagged, never reconciled.
    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=6,
        observation=None,
        prior=ledger,
        frames=(
            _frame(
                RepresentationAct.DELEGATE,
                actor=PRINCIPAL,
                representative="agent-c",
            ),
        ),
        policy=policy,
    )
    delegated = _mandate(
        ledger,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=PRINCIPAL,
        representative="agent-c",
    )
    assert delegated.status is RepresentationStatus.RECOGNIZED
    assert any(
        conflict.kind is RepresentationConflictKind.DUPLICATE_MANDATE
        for conflict in ledger.conflicts
    )

    # An unauthorized third party cannot revoke the delegated mandate.
    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=7,
        observation=None,
        prior=ledger,
        frames=(
            _frame(
                RepresentationAct.REVOKE,
                mandate_ref=delegated.mandate_id,
                actor="agent-d",
            ),
        ),
        policy=policy,
    )
    still_recognized = _mandate(
        ledger,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=PRINCIPAL,
        representative="agent-c",
    )
    assert still_recognized.status is RepresentationStatus.RECOGNIZED
    assert any(
        conflict.kind is RepresentationConflictKind.REVOCATION_DISPUTE
        for conflict in ledger.conflicts
    )

    # The verified principal revokes the first representative; positions and
    # the revocation row are retained.
    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=8,
        observation=None,
        prior=ledger,
        frames=(
            _frame(
                RepresentationAct.REVOKE,
                mandate_ref=mandate_id,
                actor=PRINCIPAL,
            ),
        ),
        policy=policy,
    )
    revoked = _mandate(
        ledger,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=PRINCIPAL,
        representative=REP,
    )
    assert revoked.status is RepresentationStatus.REVOKED
    assert ledger.positions
    assert ledger.revocations

    # Settlements resolve only through the owner's own visible region anchors.
    visible_observation = SimpleNamespace(
        regional_context=SimpleNamespace(region_id="region-visible")
    )
    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=9,
        observation=visible_observation,
        prior=ledger,
        frames=(
            _frame(
                RepresentationAct.CLAIM,
                principal_kind=RepresentationPrincipalKind.SETTLEMENT,
                principal="region-visible",
            ),
        ),
        policy=policy,
    )
    visible = _mandate(
        ledger,
        principal_kind=RepresentationPrincipalKind.SETTLEMENT,
        principal_ref="region-visible",
        representative=REP,
    )
    assert visible.principal_resolved is True

    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=10,
        observation=visible_observation,
        prior=ledger,
        frames=(
            _frame(
                RepresentationAct.CLAIM,
                principal_kind=RepresentationPrincipalKind.SETTLEMENT,
                principal="region-hidden",
            ),
        ),
        policy=policy,
    )
    hidden = _mandate(
        ledger,
        principal_kind=RepresentationPrincipalKind.SETTLEMENT,
        principal_ref="region-hidden",
        representative=REP,
    )
    assert hidden.principal_resolved is False
    assert hidden.status is RepresentationStatus.CLAIMED
    assert "representation_region_unavailable" in ledger.notices
    return ledger


def _client(root: Path) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_delegation_representation_reader(root / "store")
    app.dependency_overrides[get_delegation_representation_reader] = lambda: reader
    app.state.representation_reader = reader
    app.state.representation_cursor_codec = DelegationRepresentationCursorCodec(
        b"k" * 32
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _arm(result: object, config: SimulationRunnerConfig) -> SimpleNamespace:
    return SimpleNamespace(
        runner_result=result,
        assignment=SimpleNamespace(
            run_id=RunId(RUN),
            condition_id="condition-representation-e2e",
            runner_config=config,
        ),
        config_fingerprint="f" * 64,
    )


def _admission_bootstrap() -> WorldBootstrap:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldBootstrap(
        world_id=WorldId("world-representation-e2e-admission"),
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


def _assert_admission_independent() -> None:
    engine = WorldEngine(
        config=SimulationRunConfig(seed=41), bootstrap=_admission_bootstrap()
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

    engine = WorldEngine(
        config=SimulationRunConfig(seed=42), bootstrap=_admission_bootstrap()
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


@pytest.mark.asyncio
async def test_representation_end_to_end(tmp_path: Path) -> None:
    config = _config()
    async with await SimulationRunner.from_config(config, run_id=RunId(RUN)) as runner:
        result = await runner.run()

    assert len(result.representation_ledgers) == 1
    ledger = _scenario(cast(RepresentationLedger, result.representation_ledgers[0]))
    result = replace(result, representation_ledgers=(ledger,))

    arm = _arm(result, config)
    bundle = assemble_arm_metric_bundle(arm)
    present = {
        document.metric_family
        for document in bundle.documents
        if document.availability is MetricAvailability.PRESENT
    }
    assert {
        "representation_mandate_structure",
        "representation_recognition_support",
        "representation_scope_alignment",
    } <= present
    collector = collect_catalog_metrics(arm)
    assert {"catalog_present_count", "catalog_document_count"} <= {
        name for name, _ in collector.fields
    }

    harvest = build_completed_run_representation_harvest(result)
    built = build_representation_harvest_result(
        harvest=harvest, stop_reason=result.stop_reason
    )
    assert built.snapshot is not None
    publisher = FilesystemDelegationRepresentationPublisher(tmp_path / "store")
    published = publish_representation_snapshot(built, publisher)
    assert published.receipt["status"] == "published"

    _assert_admission_independent()

    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/representation", headers=HEADERS
        )
        assert summary.status_code == 200
        summary_payload = summary.json()
        assert summary_payload["mandate_count"] == 4
        assert summary_payload["conflict_count"] >= 2
        assert summary_payload["revocation_count"] >= 1

        mandates = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates", headers=HEADERS
        )
        payload = mandates.json()
        revoked_item = next(
            item for item in payload["items"] if item["status"] == "revoked"
        )
        mandate_id = revoked_item["mandate_id"]

        detail = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates/{mandate_id}",
            headers=HEADERS,
        )
        assert detail.status_code == 200
        assert detail.json()["status"] == "revoked"

        positions = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates/{mandate_id}/positions",
            headers=HEADERS,
        )
        assert positions.status_code == 200
        assert positions.json()["items"]
        revocations = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates/{mandate_id}/revocations",
            headers=HEADERS,
        )
        assert revocations.status_code == 200
        assert revocations.json()["items"]
        lineage = await client.get(
            f"/v1/simulations/{RUN}/representation/lineage", headers=HEADERS
        )
        assert lineage.status_code == 200

        codec = DelegationRepresentationCursorCodec(b"k" * 32)
        fingerprint = delegation_representation_query_fingerprint(
            purpose="mandates",
            run_id=RUN,
            publication_id=str(summary_payload["publication_id"]),
            snapshot_digest=str(summary_payload["snapshot_digest"]),
        )
        stale = codec.encode(
            purpose="mandates",
            run_id=RUN,
            publication_id=str(summary_payload["publication_id"]),
            snapshot_digest="0" * 64,
            offset=1,
            query_fingerprint=fingerprint,
        )
        rejected = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates",
            params={"cursor": stale},
            headers=HEADERS,
        )
        assert rejected.status_code == 400
        assert rejected.json()["detail"] == "representation_cursor_invalid"
