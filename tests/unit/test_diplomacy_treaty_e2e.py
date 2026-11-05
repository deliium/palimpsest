"""V4-11 in-process treaty lifecycle with real ticks, speech, and recognition."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agents.cognition import (
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
    TreatyAcceptanceBasis,
    TreatyAct,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatyRecollectionBasis,
    TreatyRecollectionStance,
    TreatyStatus,
    TreatySubjectKind,
    apply_diplomacy_update,
    apply_representation_update,
    default_diplomacy_policy,
    default_representation_policy,
    diplomacy_treaty_version_status,
    record_diplomacy_utterance,
)
from agents.cognition.delegation_representation import RepresentationLedger
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
)
from agents.cognition.diplomacy import DiplomacyLedger
from agents.cognition.diplomacy_communication import (
    TreatyFrame,
    treaty_communicate_utterance,
)
from agents.cognition.institutional_memory import (
    InstitutionalFact,
    InstitutionalMemoryChannel,
    InstitutionalMemoryEntry,
    InstitutionalMemoryLedger,
    InstitutionalProvenance,
    append_institutional_memory_entry,
    empty_institutional_memory_ledger,
    institutional_entry_id,
)
from agents.models import AgentId
from analysis.diplomacy_alignment import classify_treaty_recollection_alignment
from experiments.diplomacy_harvest import build_completed_run_diplomacy_harvest
from experiments.diplomacy_publication import (
    build_diplomacy_harvest_result,
    publish_diplomacy_snapshot,
)
from persistence.diplomacy_filesystem import FilesystemDiplomacyPublisher
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from simulation.runner_models import DurableRecordsSpec
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    weather_for_locations,
)
from tests.unit.test_diplomacy_api import HEADERS, RUN, _client
from world.actions import Give, Inscribe, Take, Talk
from world.artifacts import ArtifactContent, ArtifactKind, DurableRecordGenre
from world.communications import (
    CommunicationContent,
    CommunicationId,
    CommunicationSourceBasis,
    DeclaredTransmission,
    StructuredUtterance,
)
from world.identifiers import EntityId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

OWNER = "agent-a"
PEER = "agent-b"
THIRD = "agent-c"
ENVOY = "envoy-e"
AGENTS = (OWNER, PEER, THIRD, ENVOY)


def _bootstrap() -> WorldBootstrap:
    location = make_location("loc-e2e")
    return WorldBootstrap(
        world_id=WorldId("world-treaty-e2e"),
        revision=WorldRevision(0),
        locations=(location,),
        bodies=tuple(
            alive_body(
                name,
                location_id="loc-e2e",
                inventory=(EntityId("item-e2e"),) if name == OWNER else (),
            )
            for name in AGENTS
        ),
        items=(
            make_item("item-e2e", holder_id=OWNER, location_id=None),
        ),
        weather=weather_for_locations((location,)),
        registrations=tuple(
            AgentRegistration(AgentId(name), EntityId(name)) for name in AGENTS
        ),
    )


def _engine() -> WorldEngine:
    return WorldEngine(
        config=SimulationRunConfig(seed=51),
        bootstrap=_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=DurableRecordsSpec(enabled_genres=("agreement",)),
    )


def _talk(
    frame: TreatyFrame, *, speaker: str, recipient: str, communication_id: str
) -> Any:
    base = Talk(
        recipient_id=EntityId(recipient),
        utterance=StructuredUtterance(
            content=CommunicationContent(text="treaty", concepts=(), relations=()),
            declared=DeclaredTransmission(
                communication_id=CommunicationId(communication_id),
                immediate_source_id=EntityId(speaker),
                parent_communication_id=None,
                root_communication_id=CommunicationId(communication_id),
                source_agent_chain=(EntityId(speaker),),
                hop_count=0,
                sender_confidence=0.8,
                source_basis=CommunicationSourceBasis.GOAL,
            ),
        ),
    )
    return treaty_communicate_utterance(base, frame)


def _resolve(engine: WorldEngine, speaker: str, command: Any) -> Any:
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId(speaker),
                command=command,
            ),
        )
    )
    assert result.resolutions[0].status in {
        ActionResolutionStatus.APPLIED,
        ActionResolutionStatus.REJECTED,
    }
    return result


def _owner_observation(engine: WorldEngine) -> object:
    batch = engine.observe()
    return next(
        item for item in batch.observations if item.observer_id == EntityId(OWNER)
    )


def _principal_frame(
    act: TreatyAct,
    *,
    party: str,
    tick: int,
    treaty_ref: str | None = None,
    version_ref: str | None = None,
    subject: TreatySubjectKind = TreatySubjectKind.CEASEFIRE,
    provisions: tuple[TreatyProvisionKind, ...] = (
        TreatyProvisionKind.NON_HOSTILITY,
    ),
    terms_digest: str = "a" * 64,
    record_refs: tuple[str, ...] = (),
    institutional_memory_refs: tuple[str, ...] = (),
) -> TreatyFrame:
    return TreatyFrame(
        act=act,
        treaty_ref=treaty_ref,
        version_ref=version_ref,
        participant_refs=tuple(f"agent:{name}" for name in (OWNER, PEER, THIRD)),
        party_ref=party,
        envoy_ref=party,
        subject_kind=subject,
        change_kind=(
            TreatyChangeKind.ORIGINAL if act is TreatyAct.TREATY_PROPOSE else None
        ),
        provision_kinds=provisions,
        terms_digest=terms_digest,
        record_refs=record_refs,
        institutional_memory_refs=institutional_memory_refs,
        effective_tick=tick,
    )


def _envoy_frame(
    act: TreatyAct,
    *,
    party: str,
    envoy: str,
    treaty_ref: str,
    version_ref: str,
    tick: int,
) -> TreatyFrame:
    return TreatyFrame(
        act=act,
        treaty_ref=treaty_ref,
        version_ref=version_ref,
        participant_refs=tuple(f"agent:{name}" for name in (OWNER, PEER, THIRD)),
        party_ref=party,
        envoy_ref=envoy,
        subject_kind=TreatySubjectKind.CEASEFIRE,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=tick,
    )


def _recognized_representation(
    duration_kind: RepresentationDurationKind = (
        RepresentationDurationKind.UNTIL_REVOKED
    ),
) -> RepresentationLedger:
    policy = default_representation_policy()

    def frame(
        act: RepresentationAct,
        *,
        actor: str,
        mandate_ref: str | None = None,
    ) -> RepresentationFrame:
        return RepresentationFrame(
            act=act,
            mandate_ref=mandate_ref,
            principal_kind=RepresentationPrincipalKind.AGENT,
            principal_ref=PEER,
            representative_ref=ENVOY,
            scope_kind=RepresentationScopeKind.NEGOTIATE,
            scope_subject="ceasefire",
            duration_kind=duration_kind,
            end_tick=(
                1 if duration_kind is RepresentationDurationKind.SINGLE_ACT else None
            ),
            provenance=RepresentationProvenance.SELF_DECLARED,
            actor_ref=actor,
        )

    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=1,
        observation=None,
        prior=None,
        frames=(frame(RepresentationAct.CLAIM, actor=ENVOY),),
        policy=policy,
    )
    mandate_id = ledger.mandates[-1].mandate_id
    return apply_representation_update(
        owner_id=OWNER,
        tick=2,
        observation=None,
        prior=ledger,
        frames=(frame(RepresentationAct.ACCEPT, actor=PEER, mandate_ref=mandate_id),),
        policy=policy,
    )


def _record_and_memory(
    engine: WorldEngine,
) -> tuple[str, str, InstitutionalMemoryLedger]:
    result = _resolve(
        engine,
        OWNER,
        Inscribe(
            kind=ArtifactKind.RECORD,
            content=ArtifactContent(marks=("terms",)),
            record_genre=DurableRecordGenre.AGREEMENT,
        ),
    )
    record_id = None
    for receipt in result.events:
        details = getattr(receipt.event, "details", None)
        artifact_id = getattr(details, "artifact_id", None)
        if artifact_id is not None:
            record_id = str(artifact_id.value)
            break
    assert record_id is not None
    owner = AgentId(OWNER)
    entry = InstitutionalMemoryEntry(
        owner_id=owner,
        entry_id=institutional_entry_id(owner, None, 1),
        channel_id=None,
        ordinal=1,
        revision=0,
        facts=(InstitutionalFact("treaty", "records", "terms"),),
        declared_fact_count=1,
        acquisition_tick=1,
        confidence=0.75,
        distorted=False,
        partial=False,
        active=True,
        ignored=False,
        provenance=(
            InstitutionalProvenance(
                immediate_channel=InstitutionalMemoryChannel.OBSERVATION
            ),
        ),
    )
    memory_ledger = append_institutional_memory_entry(
        empty_institutional_memory_ledger(owner), entry
    )
    memory_id = memory_ledger.entries[0].entry_id
    return record_id, memory_id, memory_ledger


def _propose(
    engine: WorldEngine,
    *,
    tick: int,
    record_id: str,
    memory_id: str,
) -> DiplomacyLedger:
    frame = _principal_frame(
        TreatyAct.TREATY_PROPOSE,
        party=OWNER,
        tick=tick,
        record_refs=(record_id,),
        institutional_memory_refs=(memory_id,),
    )
    ledger = record_diplomacy_utterance(
        apply_diplomacy_update(
            owner_id=OWNER,
            tick=0,
            observation=None,
            prior=None,
            frames=(),
        ),
        _talk(frame, speaker=OWNER, recipient=PEER, communication_id="comm-propose"),
        owner_id=OWNER,
        tick=tick,
    )
    assert ledger.treaties
    return ledger


def _deliver_accept(
    engine: WorldEngine,
    ledger: DiplomacyLedger,
    *,
    speaker: str,
    party: str,
    version_ref: str,
    tick: int,
    envoy: str | None = None,
    communication_id: str,
) -> DiplomacyLedger:
    frame = (
        _principal_frame(
            TreatyAct.TREATY_ACCEPT,
            party=party,
            tick=tick,
            treaty_ref=ledger.treaties[0].treaty_id,
            version_ref=version_ref,
        )
        if envoy is None
        else _envoy_frame(
            TreatyAct.TREATY_ACCEPT,
            party=party,
            envoy=envoy,
            treaty_ref=ledger.treaties[0].treaty_id,
            version_ref=version_ref,
            tick=tick,
        )
    )
    if speaker == OWNER:
        return record_diplomacy_utterance(
            ledger,
            _talk(
                frame,
                speaker=OWNER,
                recipient=PEER,
                communication_id=f"{communication_id}-self",
            ),
            owner_id=OWNER,
            tick=tick,
        )
    _resolve(
        engine,
        speaker,
        _talk(
            frame,
            speaker=speaker,
            recipient=OWNER,
            communication_id=communication_id,
        ),
    )
    return apply_diplomacy_update(
        owner_id=OWNER,
        tick=tick,
        observation=_owner_observation(engine),
        prior=ledger,
    )


def test_three_party_ceasefire_is_believed_but_not_enforced() -> None:
    engine = _engine()
    record_id, memory_id, _memory_ledger = _record_and_memory(engine)
    ledger = _propose(engine, tick=2, record_id=record_id, memory_id=memory_id)
    version = ledger.treaty_versions[0]
    ledger = _deliver_accept(
        engine,
        ledger,
        speaker=OWNER,
        party=OWNER,
        version_ref=version.version_id,
        tick=3,
        communication_id="comm-accept-owner",
    )
    ledger = _deliver_accept(
        engine,
        ledger,
        speaker=PEER,
        party=PEER,
        version_ref=version.version_id,
        tick=4,
        communication_id="comm-accept-peer",
    )
    ledger = _deliver_accept(
        engine,
        ledger,
        speaker=THIRD,
        party=THIRD,
        version_ref=version.version_id,
        tick=5,
        communication_id="comm-accept-third",
    )
    assert ledger.treaty_versions[0].record_refs == (record_id,)
    assert ledger.treaty_versions[0].institutional_memory_refs == (memory_id,)
    assert (
        diplomacy_treaty_version_status(
            ledger.treaty_versions[0],
            ledger.treaty_declarations,
            tick=5,
            policy=default_diplomacy_policy(),
            envoys=ledger.envoys,
            relation_id=ledger.treaties[0].relation_id,
            subject_kind=TreatySubjectKind.CEASEFIRE,
        )[0].value
        == "apparently_accepted"
    )

    possible = _resolve(
        engine,
        OWNER,
        Give(recipient_id=EntityId(PEER), item_id=EntityId("item-e2e")),
    )
    assert possible.resolutions[0].status is not ActionResolutionStatus.REJECTED
    impossible = _resolve(engine, OWNER, Take(item_id=EntityId("missing-item")))
    assert impossible.resolutions[0].status is ActionResolutionStatus.REJECTED


def test_renewal_creates_version_two_and_linear_lineage() -> None:
    engine = _engine()
    record_id, memory_id, _memory_ledger = _record_and_memory(engine)
    ledger = _propose(engine, tick=2, record_id=record_id, memory_id=memory_id)
    first = ledger.treaty_versions[0]
    for tick, party in enumerate((OWNER, PEER, THIRD), start=3):
        ledger = _deliver_accept(
            engine,
            ledger,
            speaker=party,
            party=party,
            version_ref=first.version_id,
            tick=tick,
            communication_id=f"comm-first-{party}",
        )
    renewal = _principal_frame(
        TreatyAct.TREATY_RENEW,
        party=OWNER,
        tick=6,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=first.version_id,
        terms_digest="b" * 64,
    )
    ledger = record_diplomacy_utterance(
        ledger,
        _talk(renewal, speaker=OWNER, recipient=PEER, communication_id="comm-renew"),
        owner_id=OWNER,
        tick=6,
    )
    second = max(ledger.treaty_versions, key=lambda row: row.version_index)
    assert second.version_index == 2
    assert second.parent_version_ids == (first.version_id,)
    for tick, party in enumerate((OWNER, PEER, THIRD), start=7):
        ledger = _deliver_accept(
            engine,
            ledger,
            speaker=party,
            party=party,
            version_ref=second.version_id,
            tick=tick,
            communication_id=f"comm-second-{party}",
        )
    assert len(ledger.treaty_versions) == 2


def test_later_generation_recalls_without_creating_a_local_treaty() -> None:
    engine = _engine()
    record_id, memory_id, _memory_ledger = _record_and_memory(engine)
    ledger = _propose(engine, tick=2, record_id=record_id, memory_id=memory_id)
    recollection = TreatyFrame(
        act=TreatyAct.TREATY_RECOLLECT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[0].version_id,
        subject_kind=TreatySubjectKind.CEASEFIRE,
        basis=TreatyRecollectionBasis.DURABLE_RECORD,
        stance=TreatyRecollectionStance.REMEMBER,
        confidence=0.5,
        terms_digest="a" * 64,
        envoy_ref="agent-d",
    )
    observer = apply_diplomacy_update(
        owner_id="agent-d",
        tick=3,
        observation=None,
        prior=None,
        frames=(recollection,),
    )
    assert observer.treaties == ()
    assert observer.treaty_versions == ()
    assert len(observer.treaty_recollections) == 1


def test_alignment_distinguishes_consistent_and_inconsistent_recall() -> None:
    engine = _engine()
    record_id, memory_id, _memory_ledger = _record_and_memory(engine)
    ledger = _propose(engine, tick=2, record_id=record_id, memory_id=memory_id)
    version = ledger.treaty_versions[0]

    def recollection(digest: str, *, tick: int = 3) -> object:
        return apply_diplomacy_update(
            owner_id=OWNER,
            tick=tick,
            observation=None,
            prior=ledger,
            frames=(
                TreatyFrame(
                    act=TreatyAct.TREATY_RECOLLECT,
                    treaty_ref=ledger.treaties[0].treaty_id,
                    version_ref=version.version_id,
                    subject_kind=TreatySubjectKind.CEASEFIRE,
                    basis=TreatyRecollectionBasis.DURABLE_RECORD,
                    stance=TreatyRecollectionStance.REMEMBER,
                    confidence=0.5,
                    terms_digest=digest,
                    envoy_ref=OWNER,
                ),
            ),
        )

    matching = recollection(version.terms_digest, tick=3)
    differing = recollection("b" * 64, tick=4)
    harvest = build_completed_run_diplomacy_harvest(
        SimpleNamespace(
            run_id=SimpleNamespace(value=RUN),
            ticks_committed=3,
            diplomacy_ledgers=(matching, differing),
        )
    )
    statuses = {
        row.claimed_terms_digest: row.status
        for row in classify_treaty_recollection_alignment(harvest.rows)
    }
    assert statuses[version.terms_digest] == "consistent"
    assert statuses["b" * 64] == "inconsistent"


def test_non_participant_cannot_create_a_treaty() -> None:
    frame = _principal_frame(TreatyAct.TREATY_PROPOSE, party="agent-d", tick=1)
    ledger = apply_diplomacy_update(
        owner_id="agent-d", tick=1, observation=None, prior=None, frames=(frame,)
    )
    assert ledger.treaties == ()
    assert len(ledger.treaty_recollections) == 1


def test_single_act_envoy_never_completes_a_party() -> None:
    def two_party() -> DiplomacyLedger:
        frame = TreatyFrame(
            act=TreatyAct.TREATY_PROPOSE,
            participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
            subject_kind=TreatySubjectKind.CEASEFIRE,
            change_kind=TreatyChangeKind.ORIGINAL,
            provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
            terms_digest="a" * 64,
            effective_tick=1,
            envoy_ref=OWNER,
        )
        return apply_diplomacy_update(
            owner_id=OWNER, tick=1, observation=None, prior=None, frames=(frame,)
        )

    def accept_all(
        ledger: DiplomacyLedger, representation: RepresentationLedger
    ) -> tuple[TreatyStatus, TreatyAcceptanceBasis]:
        version = ledger.treaty_versions[0]
        owner_accept = TreatyFrame(
            act=TreatyAct.TREATY_ACCEPT,
            treaty_ref=ledger.treaties[0].treaty_id,
            version_ref=version.version_id,
            party_ref=OWNER,
            envoy_ref=OWNER,
            participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        )
        envoy_accept = TreatyFrame(
            act=TreatyAct.TREATY_ACCEPT,
            treaty_ref=ledger.treaties[0].treaty_id,
            version_ref=version.version_id,
            party_ref=PEER,
            envoy_ref=ENVOY,
            actor_ref=ENVOY,
            mandate_ref=representation.mandates[-1].mandate_id,
            participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        )
        ledger = apply_diplomacy_update(
            owner_id=OWNER,
            tick=2,
            observation=None,
            prior=ledger,
            frames=(owner_accept,),
            representation=representation,
        )
        ledger = apply_diplomacy_update(
            owner_id=OWNER,
            tick=3,
            observation=None,
            prior=ledger,
            frames=(envoy_accept,),
            representation=representation,
        )
        return diplomacy_treaty_version_status(
            version,
            ledger.treaty_declarations,
            tick=3,
            policy=default_diplomacy_policy(),
            representation=representation,
            envoys=ledger.envoys,
            relation_id=ledger.treaties[0].relation_id,
            subject_kind=TreatySubjectKind.CEASEFIRE,
        )

    recognized = accept_all(
        two_party(),
        _recognized_representation(RepresentationDurationKind.UNTIL_REVOKED),
    )
    assert recognized[0].value == "apparently_accepted"
    single_act = accept_all(
        two_party(), _recognized_representation(RepresentationDurationKind.SINGLE_ACT)
    )
    assert single_act[0].value == "proposed"


def test_real_durable_record_and_institutional_memory_anchors_round_trip() -> None:
    engine = _engine()
    record_id, memory_id, memory_ledger = _record_and_memory(engine)
    ledger = _propose(engine, tick=2, record_id=record_id, memory_id=memory_id)
    version = ledger.treaty_versions[0]
    assert version.record_refs == (record_id,)
    assert version.institutional_memory_refs == (memory_id,)
    assert len(version.record_refs[0]) > 0
    assert len(version.institutional_memory_refs[0]) == 64
    assert memory_ledger.entries[0].entry_id == memory_id
    assert memory_ledger.entries[0].facts[0].subject == "treaty"


def test_publication_and_all_eight_routes_expose_v2_without_changing_science(
    tmp_path: Path,
) -> None:
    engine = _engine()
    record_id, memory_id, _memory_ledger = _record_and_memory(engine)
    ledger = _propose(engine, tick=2, record_id=record_id, memory_id=memory_id)
    version = ledger.treaty_versions[0]
    representation = _recognized_representation()
    for tick, party in enumerate((OWNER, PEER, THIRD), start=3):
        ledger = _deliver_accept(
            engine,
            ledger,
            speaker=party,
            party=party,
            version_ref=version.version_id,
            tick=tick,
            communication_id=f"comm-publish-{party}",
        )
    ticks = 6
    result = SimpleNamespace(
        run_id=RunId(RUN),
        ticks_committed=ticks,
        stop_reason=SimpleNamespace(value="max_ticks"),
        diplomacy_ledgers=(ledger,),
        representation_ledgers=(representation,),
    )
    harvest = build_completed_run_diplomacy_harvest(
        result, entity_to_agent={EntityId(name): name for name in AGENTS}
    )
    built = build_diplomacy_harvest_result(
        harvest, run_id=RUN, revision="rev-e2e", window_end=ticks
    )
    assert built.snapshot is not None
    assert built.snapshot.schema_version == "diplomacy-snapshot-v2"
    assert built.snapshot.treaty_versions[0].status == "apparently_accepted"
    assert built.receipt["treaty_accepted"] == 1
    publish_diplomacy_snapshot(built, FilesystemDiplomacyPublisher(tmp_path / "store"))

    async def exercise() -> None:
        async with _client(tmp_path, clock=[100.0]) as client:
            summary = await client.get(
                f"/v1/simulations/{RUN}/diplomacy", headers=HEADERS
            )
            assert summary.status_code == 200
            relations = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/relations", headers=HEADERS
            )
            assert relations.status_code == 200
            relation_id = relations.json()["items"][0]["relation_id"]
            assert (
                await client.get(
                    f"/v1/simulations/{RUN}/diplomacy/relations/{relation_id}",
                    headers=HEADERS,
                )
            ).status_code == 200
            instruments = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/instruments", headers=HEADERS
            )
            assert instruments.status_code == 200
            items = instruments.json()["items"]
            instrument_id = (
                items[0]["instrument_id"] if items else "dpi-0000000000000000"
            )
            instrument_detail = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/instruments/{instrument_id}",
                headers=HEADERS,
            )
            assert instrument_detail.status_code in {200, 404}
            assert (
                await client.get(
                    f"/v1/simulations/{RUN}/diplomacy/lineage", headers=HEADERS
                )
            ).status_code == 200
            treaties = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/treaties", headers=HEADERS
            )
            assert treaties.status_code == 200
            treaty_id = treaties.json()["items"][0]["treaty_id"]
            detail = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/treaties/{treaty_id}",
                headers=HEADERS,
            )
            assert detail.status_code == 200
            assert detail.json()["versions"]

    asyncio.run(exercise())
