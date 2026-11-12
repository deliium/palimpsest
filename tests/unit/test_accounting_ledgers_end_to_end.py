"""In-process accounting seam over real engine admission."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition.accounting_ledgers import (
    AccountingRecordIntegrity,
    AccountingRecordObservation,
    accounting_record_token,
    apply_accounting_ledger_update,
)
from agents.models import AgentId
from api.accounting_ledgers_cursor import AccountingLedgersCursorCodec
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.accounting_ledgers import router
from experiments.accounting_ledgers_completed_run import (
    build_completed_run_accounting_ledgers_analysis,
)
from experiments.accounting_ledgers_publication import (
    build_accounting_ledgers_harvest_result,
)
from infrastructure.settings import Settings
from persistence.accounting_ledgers_filesystem import (
    create_accounting_ledgers_publisher,
    create_accounting_ledgers_reader,
)
from simulation.accounting_ledgers_export import accounting_owner_export
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from simulation.runner_models import example_durable_records_spec
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.accounting_ledgers import (
    AccountingEntryFrame,
    AccountingFrameAct,
    AccountingFrameAssessment,
    AccountingFrameDirection,
    AccountingFrameEntryKind,
    AccountingFrameIntegrity,
    accounting_entry_relation,
    accounting_record_content,
)
from world.actions import Inscribe, Tell, Wait
from world.artifacts import ArtifactKind, DurableRecordGenre
from world.communications import origin_utterance
from world.events import ArtifactCreated, Told
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules

pytestmark = pytest.mark.unit
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-accounting-e2e"


def _engine() -> WorldEngine:
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-accounting-e2e"),
        revision=WorldRevision(0),
        locations=(make_location("loc-a"),),
        items=(),
        bodies=(
            alive_body("body-1", location_id="loc-a"),
            alive_body("body-2", location_id="loc-a"),
        ),
        weather=(make_weather("loc-a"),),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=47, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId(RUN),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
    )


def _inscribe(engine: WorldEngine) -> None:
    batch = engine.observe()
    content = accounting_record_content(
        (("xch_food", "in3"), ("dbt_material", "pay2"), ("inv_tool", "hold1"))
    )
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Inscribe(
                    kind=ArtifactKind.RECORD,
                    content=content,
                    hold=False,
                    record_genre=DurableRecordGenre.AGREEMENT,
                ),
            ),
        )
    )
    assert any(
        item.status is ActionResolutionStatus.APPLIED
        for item in result.resolutions
    )


def _tell(engine: WorldEngine) -> None:
    batch = engine.observe()
    relation = accounting_entry_relation(
        AccountingEntryFrame(
            act=AccountingFrameAct.AFFIRM_ENTRY,
            entry_anchor="acct-0123456789abcdef",
            record_token=accounting_record_token("artifact-unseen"),
            entry_kind=AccountingFrameEntryKind.EXCHANGE,
            direction=AccountingFrameDirection.INFLOW,
            item_kind="food",
            quantity=2,
            organization_token=None,
            counterparty_token=None,
            assessment=AccountingFrameAssessment.CONSISTENT,
            integrity=AccountingFrameIntegrity.INTACT,
            confidence_milli=700,
            tick=0,
            revision=0,
            record_genre="agreement",
        )
    )
    utterance = origin_utterance(
        text="accounting",
        speaker_id=EntityId("body-1"),
        relations=(relation,),
    )
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Tell(recipient_id=EntityId("body-2"), utterance=utterance),
            ),
        )
    )
    assert any(
        item.status is ActionResolutionStatus.APPLIED
        for item in result.resolutions
    )


def _fold(engine: WorldEngine):
    batch = engine.observe()
    observation = batch.for_observer(EntityId("body-1"))
    records = tuple(
        AccountingRecordObservation(
            record_token=accounting_record_token(artifact.entity_id.value),
            record_genre=getattr(artifact.record_genre, "value", None),
            integrity={
                "intact": AccountingRecordIntegrity.INTACT,
                "damaged": AccountingRecordIntegrity.DAMAGED,
                "partially_lost": AccountingRecordIntegrity.PARTIALLY_LOST,
            }.get(
                getattr(getattr(artifact, "integrity", None), "value", ""),
                AccountingRecordIntegrity.UNKNOWN,
            ),
            content_revision=artifact.content_revision,
            relations=tuple(
                (relation.subject, relation.predicate, relation.object)
                for relation in artifact.content.relations
            ),
            tick=observation.tick,
        )
        for artifact in observation.artifacts
    )
    return apply_accounting_ledger_update(
        owner_id=AgentId("agent-1"), tick=observation.tick, records=records
    )


@pytest.mark.asyncio
async def test_real_engine_record_speech_analysis_store_and_api(tmp_path: Path) -> None:
    engine = _engine()
    _inscribe(engine)
    _tell(engine)
    events = engine.export_events().events
    assert any(type(event.details) is ArtifactCreated for event in events)
    assert any(type(event.details) is Told for event in events)

    ledger = _fold(engine)
    assert ledger.entries
    assert any(
        entry.terms.entry_kind.value == "exchange" for entry in ledger.entries
    )
    exported = accounting_owner_export((ledger,))
    from analysis.accounting_ledgers_contract import (
        AccountingEntryDirection,
        AccountingEntryKindToken,
        AccountingRecordAssessmentToken,
    )
    from analysis.accounting_ledgers_expectations import AccountingOwnerRowInput

    owner_rows = tuple(
        AccountingOwnerRowInput(
            owner_token=row.owner_token,
            entry_token=row.entry_token,
            record_token=row.record_token,
            entry_kind=AccountingEntryKindToken(row.entry_kind),
            direction=AccountingEntryDirection(row.direction),
            item_kind=row.item_kind,
            quantity=row.quantity,
            assessment=AccountingRecordAssessmentToken(row.assessment),
            confidence_milli=row.confidence_milli,
            first_tick=row.first_tick,
            last_tick=row.last_tick,
            window_index=row.window_index,
        )
        for row in exported
    )
    analysis = build_completed_run_accounting_ledgers_analysis(
        run_id=RUN, events=events, owner_rows=owner_rows
    )
    assert analysis.entries
    publisher = create_accounting_ledgers_publisher(tmp_path / "store")
    harvest = build_accounting_ledgers_harvest_result(analysis, publisher=publisher)
    assert harvest.receipt.stored is True
    assert harvest.snapshot.digest.startswith("sha256:")

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.accounting_ledgers_reader = create_accounting_ledgers_reader(
        tmp_path / "store"
    )
    app.state.accounting_ledgers_cursor_codec = AccountingLedgersCursorCodec(
        b"k" * 32
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/accounting-ledgers", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["digest"] == harvest.snapshot.digest
        entries = await client.get(
            f"/v1/simulations/{RUN}/accounting-ledgers/entries", headers=HEADERS
        )
        assert entries.status_code == 200
        assert entries.json()["rows"]

    before = engine.observe().for_observer(EntityId("body-1"))
    engine.resolve_tick(
        (
            ActionSubmission(
                engine.observe().token,
                AgentId("agent-1"),
                Wait(),
            ),
        )
    )
    after = engine.observe().for_observer(EntityId("body-1"))
    assert before.self_body.inventory == after.self_body.inventory
