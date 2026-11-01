"""End-to-end operational path: owner beliefs -> v2 artifact -> read surfaces."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition import (
    OrganizationConcept,
    OrganizationConceptLedger,
    OrganizationEvidenceChannel,
    OrganizationMemberBelief,
    OrganizationMembershipBasis,
    OrganizationMembershipStatus,
    OrganizationOperationAct,
    OrganizationOperationClaim,
    OrganizationOperationLedger,
    OrganizationStatus,
    OrganizationTemporalScope,
    apply_organization_operation_update,
    organization_operation_claim_relation,
    organization_operation_ref,
)
from agents.models import AgentId
from api.dependencies import get_organization_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.organization_cursor import OrganizationCursorCodec
from api.routes.organization import router
from experiments import (
    OrganizationHarvest,
    build_completed_run_organization_harvest,
    build_organization_harvest_result,
)
from experiments.organization_publication import OrganizationHarvestResult
from infrastructure.settings import Settings
from persistence.organization_filesystem import (
    create_organization_publisher,
    create_organization_reader,
)
from research_runner.organization_composition import (
    OrganizationProducerOptions,
    publish_organization_harvest,
)
from simulation.organization_models import (
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    OrganizationOperationRecord,
)
from simulation.runner_models import RunnerStopReasonCode
from world import Observation
from world.communications import CommunicationSourceBasis, origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
)

pytestmark = pytest.mark.unit

RUN = "run-operations-e2e"
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
OWNER_1 = AgentId("owner-1")
OWNER_2 = AgentId("owner-2")
ENTITY_1 = "body-owner-1"
ENTITY_2 = "body-owner-2"
ORG = f"orgc-{'a' * 16}"
MEMBER = "member-a"
DIGEST = "c" * 64


def _member() -> OrganizationMemberBelief:
    return OrganizationMemberBelief(
        member_id=MEMBER,
        status=OrganizationMembershipStatus.PERCEIVED,
        basis=OrganizationMembershipBasis.PARTICIPATION,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        first_tick=1,
        last_tick=9,
        strength=0.75,
        channels=(OrganizationEvidenceChannel.OBSERVED,),
        independently_evidenced=True,
        evidence_refs=("ev-1",),
    )


def _concept_ledger(owner: AgentId) -> OrganizationConceptLedger:
    concept = OrganizationConcept(
        organization_id=ORG,
        owner_id=owner,
        creation_tick=1,
        inception_digest=DIGEST,
        status=OrganizationStatus.CANDIDATE,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        strength=0.75,
        member_evidence_count=1,
        structural_channel_count=1,
        first_tick=1,
        last_tick=9,
        members=(_member(),),
        goals=(),
        resources=(),
        procedures=(),
        records=(),
        commitments=(),
        roles=(),
        identities=(),
    )
    return OrganizationConceptLedger(owner_id=owner, concepts=(concept,))


def _claim(
    act: OrganizationOperationAct, stance: str, *, event_id: str, tick: int = 4
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="claim",
        speaker_id=EntityId(ENTITY_1),
        communication_id=f"comm-{event_id}",
        relations=(
            organization_operation_claim_relation(
                OrganizationOperationClaim(
                    act=act,
                    stance=stance,
                    target_ref=organization_operation_ref(
                        MEMBER, namespace="target"
                    ),
                    anchor_kind="unknown",
                )
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=tick,
            source_event_id=EventId(event_id),
        ),
        speaker_id=EntityId(ENTITY_1),
        listener_id=EntityId(ENTITY_2),
        utterance=utterance,
        action_kind="talk",
    )


def _occurrence() -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=4,
            source_event_id=EventId("evt-give"),
        ),
        kind="given",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId(ENTITY_1),
        success=True,
        public_facts={"item_id": "item-1", "target_id": MEMBER},
    )


def _observation(
    *, observer: str = ENTITY_1, communications: tuple[Any, ...] = ()
) -> Observation:
    return Observation(
        world_id=WorldId("world-operations-e2e"),
        observer_id=EntityId(observer),
        revision=WorldRevision(5),
        tick=5,
        occurrences=(_occurrence(),),
        communications=communications,
    )


def _owner_ledger(
    owner: AgentId,
    *,
    observer: str,
    claims: tuple[tuple[OrganizationOperationAct, str, str], ...],
) -> OrganizationOperationLedger:
    communications = tuple(
        _claim(act, stance, event_id=event_id)
        for act, stance, event_id in claims
    )
    return apply_organization_operation_update(
        owner_id=owner,
        tick=5,
        observation=_observation(
            observer=observer, communications=communications
        ),
        prior=None,
        organization_concepts=_concept_ledger(owner),
        offices=None,
        collective_decisions=None,
        structured_commitments=None,
        possession_legitimacy=None,
    )


def _fixture(
    ledgers: tuple[OrganizationOperationLedger, ...],
    concept_ledgers: tuple[OrganizationConceptLedger, ...],
) -> SimpleNamespace:
    # Typed RunnerResult-compatible seam: the runner cannot naturally produce
    # organization speech inside the small tick budget, so the real exported
    # ledgers are carried on an attribute-compatible fixture.
    return SimpleNamespace(
        organization_concept_ledgers=tuple(concept_ledgers),
        organization_operation_ledgers=tuple(ledgers),
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        ticks_committed=9,
    )


def _build(
    owner_1_stance: str = "admitted", owner_2_stance: str = "denied"
) -> tuple[OrganizationHarvest, OrganizationHarvestResult]:
    ledger_1 = _owner_ledger(
        OWNER_1,
        observer=ENTITY_1,
        claims=(
            (OrganizationOperationAct.ADMIT, owner_1_stance, "evt-1"),
            (OrganizationOperationAct.AUTHORIZE_CONTROL, "recognized", "evt-2"),
        ),
    )
    ledger_2 = _owner_ledger(
        OWNER_2,
        observer=ENTITY_2,
        claims=((OrganizationOperationAct.ADMIT, owner_2_stance, "evt-3"),),
    )
    fixture = _fixture(
        (ledger_1, ledger_2),
        (_concept_ledger(OWNER_1), _concept_ledger(OWNER_2)),
    )
    harvest = build_completed_run_organization_harvest(
        fixture,
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
    )
    return harvest, build_organization_harvest_result(harvest)


def test_operational_snapshot_publishes_and_reads(tmp_path: Path) -> None:
    harvest, built = _build()
    assert built.snapshot.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
    assert built.operation_count > 0
    assert harvest.operation_rows

    payload = built.snapshot_bytes.decode()
    for token in ("orgc-", "orgd-", "orga-", "owner_id", "owner-1", "owner-2"):
        assert token not in payload
    for operation in built.snapshot.candidates[0].operations:
        assert operation.operation_id.startswith("orgop-")

    publisher = create_organization_publisher(tmp_path)
    reader = create_organization_reader(tmp_path)
    assert publisher is not None and reader is not None
    from experiments import publish_organization_snapshot

    publish_organization_snapshot(built, publisher)
    summary = reader.summary(RUN)
    assert summary is not None
    assert summary.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
    assert summary.operation_count == built.operation_count
    page = reader.operations(RUN, built.publication_id, 0, 50)
    assert len(page.rows) == built.operation_count
    owned = reader.operations(
        RUN,
        built.publication_id,
        0,
        50,
        domain="membership_admission",
    )
    assert owned.rows
    owned_rows = cast(tuple[OrganizationOperationRecord, ...], owned.rows)
    assert all(row.domain == "membership_admission" for row in owned_rows)


def test_disagreement_is_published_without_dropping_a_side() -> None:
    _, built = _build(owner_1_stance="admitted", owner_2_stance="denied")
    admissions = [
        operation
        for candidate in built.snapshot.candidates
        for operation in candidate.operations
        if operation.domain == "membership_admission"
    ]
    assert admissions
    assert {operation.stance for operation in admissions} >= {"admitted", "denied"}
    assert built.contested_operation_count >= 0


def test_deterministic_twin_produces_identical_bytes() -> None:
    _, first = _build()
    _, second = _build()
    assert first.snapshot_bytes == second.snapshot_bytes
    assert first.publication_id == second.publication_id
    assert hashlib.sha256(first.snapshot_bytes).hexdigest() == (
        hashlib.sha256(second.snapshot_bytes).hexdigest()
    )


def test_objective_artifact_contains_no_operation_ids() -> None:
    _, built = _build()
    for row in built.snapshot.objective_rows:
        for name in row.__dataclass_fields__:
            value = getattr(row, name)
            assert not isinstance(value, str)
    for window in built.snapshot.windows:
        assert not hasattr(window, "operation_ids")


def test_publication_receipt_and_read_are_id_free(tmp_path: Path) -> None:
    receipt = publish_organization_harvest(
        _fixture(
            (
                _owner_ledger(
                    OWNER_1,
                    observer=ENTITY_1,
                    claims=((OrganizationOperationAct.ADMIT, "admitted", "evt-1"),),
                ),
            ),
            (_concept_ledger(OWNER_1),),
        ),
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        options=OrganizationProducerOptions(root=tmp_path),
    )
    assert receipt["status"] == "published"
    assert receipt["operation_count"]
    serialized = repr(receipt)
    assert "orgc-" not in serialized
    assert "owner-1" not in serialized


@pytest.mark.asyncio
async def test_fifth_route_serves_published_operations(tmp_path: Path) -> None:
    publish_organization_harvest(
        _fixture(
            (
                _owner_ledger(
                    OWNER_1,
                    observer=ENTITY_1,
                    claims=((OrganizationOperationAct.ADMIT, "admitted", "evt-1"),),
                ),
            ),
            (_concept_ledger(OWNER_1),),
        ),
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        options=OrganizationProducerOptions(root=tmp_path),
    )
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_organization_reader(tmp_path)
    app.dependency_overrides[get_organization_reader] = lambda: reader
    app.state.organization_cursor_codec = OrganizationCursorCodec(
        b"k" * 32, now=lambda: 1000.0
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations", headers=HEADERS
        )
        unauthorized = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations"
        )
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert all(item["operation_id"].startswith("orgop-") for item in body["items"])
    assert unauthorized.status_code == 401


@pytest.mark.asyncio
async def test_flags_off_run_has_no_operation_state(tmp_path: Path) -> None:
    from dataclasses import replace

    from simulation.models import RunId
    from simulation.runner import SimulationRunner
    from simulation.runner_models import V4CapabilityFlags
    from tests.unit.test_organization_end_to_end import _config

    config = replace(
        _config(),
        schema_version="runner-config-v4",
        v4_capability_flags=V4CapabilityFlags(),
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-operations-flags-off")
    ) as runner:
        result = await runner.run()
    assert result.organization_operation_ledgers == ()
    harvest = build_completed_run_organization_harvest(
        result,
        run_id="run-operations-flags-off",
        input_revision="rev-1",
        generated_tick=result.ticks_committed,
    )
    assert harvest.operation_rows == ()
    built = build_organization_harvest_result(harvest)
    assert built.operation_count == 0
    assert built.snapshot.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
