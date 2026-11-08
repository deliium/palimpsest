# mypy: ignore-errors
"""Shared builders for migration-displacement unit tests."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.migration_displacement import (
    MIGRATION_DISPLACEMENT_POLICY_VERSION,
    CauseEvidenceRow,
    CauseEvidenceStatus,
    ClusterBasis,
    ClusterStatus,
    IntegrationBeliefRow,
    IntegrationDomain,
    IntegrationStatus,
    MigrationCauseKind,
    MigrationCauseSource,
    MigrationDisplacementLedger,
    MigrationEvidence,
    MigrationIntentRow,
    MigrationIntentStatus,
    RouteBeliefBasis,
    RouteBeliefRow,
    RouteBeliefStatus,
    SocialClusterBeliefRow,
    WaveObservationRow,
    WaveObservationStatus,
    finalize_migration_displacement_ledger,
    migration_cause_id,
    migration_cluster_id,
    migration_integration_id,
    migration_intent_id,
    migration_route_id,
    migration_wave_observation_id,
)
from agents.models import AgentId
from world.identifiers import EntityId

OWNER = AgentId("agent-1")
PEER = AgentId("agent-2")
PEER3 = AgentId("agent-3")
OWNER_ENTITY = EntityId("body-1")
PEER_ENTITY = EntityId("body-2")
PEER3_ENTITY = EntityId("body-3")
A = EntityId("loc-a")
B = EntityId("loc-b")
C = EntityId("loc-c")
D = EntityId("loc-d")
E = EntityId("loc-e")

IDENTITY = SimpleNamespace(
    owner_id=OWNER,
    owner_entity_id=OWNER_ENTITY,
    counterparts=(
        SimpleNamespace(entity_id=PEER_ENTITY, agent_id=PEER),
        SimpleNamespace(entity_id=PEER3_ENTITY, agent_id=PEER3),
    ),
)


def evidence(
    tick: int = 1,
    ref: str = "ref-1",
    kind: MigrationCauseSource = MigrationCauseSource.DIRECT_OBSERVATION,
    owner: AgentId | None = None,
) -> MigrationEvidence:
    return MigrationEvidence(
        kind=kind,
        source_owner_id=owner,
        source_tick=tick,
        lineage_ref=ref,
        policy_version=MIGRATION_DISPLACEMENT_POLICY_VERSION,
    )


def cause(
    kind: MigrationCauseKind = MigrationCauseKind.RESOURCE_SCARCITY,
    source: MigrationCauseSource = MigrationCauseSource.OWN_NEED,
    *,
    anchor: str | None = None,
    tick: int = 1,
    last_tick: int | None = None,
    status: CauseEvidenceStatus = CauseEvidenceStatus.ACTIVE,
    confidence: float = 0.6,
    owner: AgentId = OWNER,
    with_evidence: bool = True,
) -> CauseEvidenceRow:
    if kind is MigrationCauseKind.UNKNOWN:
        source = MigrationCauseSource.UNKNOWN
        anchor = None
    return CauseEvidenceRow(
        cause_id=migration_cause_id(owner, kind, source, anchor, tick),
        owner_id=owner,
        cause_kind=kind,
        source_kind=source,
        anchor_ref=anchor,
        confidence=confidence,
        first_tick=tick,
        last_tick=tick if last_tick is None else last_tick,
        status=status,
        evidence=(evidence(tick, f"cause-{tick}"),) if with_evidence else (),
    )


def route(
    locations: tuple[EntityId, ...] = (A, B, C),
    *,
    basis: RouteBeliefBasis = RouteBeliefBasis.DIRECT_OBSERVATION,
    status: RouteBeliefStatus = RouteBeliefStatus.OPEN,
    tick: int = 1,
    last_tick: int | None = None,
    owner: AgentId = OWNER,
) -> RouteBeliefRow:
    return RouteBeliefRow(
        route_id=migration_route_id(owner, locations, tick),
        owner_id=owner,
        origin_location_id=locations[0],
        destination_location_id=locations[-1],
        route_locations=locations,
        observed_duration_ticks=None,
        fatigue_cost=None,
        basis=basis,
        status=status,
        first_tick=tick,
        last_tick=tick if last_tick is None else last_tick,
        evidence=() if basis is RouteBeliefBasis.UNRESOLVED else (evidence(tick),),
    )


def intent(
    locations: tuple[EntityId, ...] = (A, B, C),
    *,
    causes: tuple[CauseEvidenceRow, ...] | None = None,
    status: MigrationIntentStatus = MigrationIntentStatus.PLANNED,
    confidence: float = 0.6,
    tick: int = 1,
    last_tick: int | None = None,
    cluster_ids: tuple[str, ...] = (),
    owner: AgentId = OWNER,
) -> MigrationIntentRow:
    causes = (cause(tick=tick, owner=owner),) if causes is None else causes
    return MigrationIntentRow(
        intent_id=migration_intent_id(owner, locations, tick),
        owner_id=owner,
        origin_location_id=locations[0],
        destination_location_id=locations[-1],
        route_locations=locations,
        cause_ids=tuple(sorted(item.cause_id for item in causes)),
        cluster_ids=cluster_ids,
        status=status,
        confidence=confidence,
        first_tick=tick,
        last_tick=tick if last_tick is None else last_tick,
        evidence=(evidence(tick, f"intent-{tick}"),),
    )


def cluster(
    members: tuple[AgentId, ...] = (OWNER, PEER),
    *,
    basis: ClusterBasis = ClusterBasis.KINSHIP,
    status: ClusterStatus = ClusterStatus.BELIEVED,
    tick: int = 1,
    owner: AgentId = OWNER,
) -> SocialClusterBeliefRow:
    ordered = tuple(sorted(members, key=lambda item: item.value))
    return SocialClusterBeliefRow(
        cluster_id=migration_cluster_id(owner, ordered, basis, tick),
        owner_id=owner,
        member_ids=ordered,
        basis=basis,
        confidence=0.5,
        status=status,
        first_tick=tick,
        last_tick=tick,
        evidence=(evidence(tick, f"cluster-{tick}"),),
    )


def integration(
    destination: EntityId = C,
    *,
    domain: IntegrationDomain = IntegrationDomain.RESIDENCE,
    status: IntegrationStatus = IntegrationStatus.SETTLED,
    tick: int = 1,
    owner: AgentId = OWNER,
) -> IntegrationBeliefRow:
    return IntegrationBeliefRow(
        outcome_id=migration_integration_id(owner, destination, domain, tick),
        owner_id=owner,
        destination_location_id=destination,
        domain=domain,
        status=status,
        confidence=0.5,
        first_tick=tick,
        last_tick=tick,
        evidence=(evidence(tick, f"integration-{tick}"),),
    )


def wave(
    participants: tuple[AgentId, ...] = (OWNER, PEER),
    *,
    origin: EntityId = A,
    destination: EntityId = B,
    causes: tuple[CauseEvidenceRow, ...] | None = None,
    status: WaveObservationStatus = WaveObservationStatus.OBSERVED,
    tick: int = 1,
    owner: AgentId = OWNER,
) -> WaveObservationRow:
    ordered = tuple(sorted(participants, key=lambda item: item.value))
    causes = (cause(tick=tick, owner=owner),) if causes is None else causes
    return WaveObservationRow(
        observation_id=migration_wave_observation_id(
            owner, origin, destination, ordered, tick
        ),
        owner_id=owner,
        origin_location_id=origin,
        destination_location_id=destination,
        participant_ids=ordered,
        cause_ids=tuple(sorted(item.cause_id for item in causes)),
        cluster_ids=(),
        status=status,
        first_tick=tick,
        last_tick=tick,
        evidence=(evidence(tick, f"wave-{tick}"),),
    )


def ledger(
    *,
    owner: AgentId = OWNER,
    intents=(),
    routes=(),
    causes=(),
    clusters=(),
    integrations=(),
    waves=(),
    notices=(),
) -> MigrationDisplacementLedger:
    return finalize_migration_displacement_ledger(
        MigrationDisplacementLedger(
            owner_id=owner,
            intents=tuple(intents),
            routes=tuple(routes),
            causes=tuple(causes),
            clusters=tuple(clusters),
            integrations=tuple(integrations),
            waves=tuple(waves),
            notices=tuple(notices),
        )
    )


def need(value: int) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def visible_exit(
    destination: EntityId, *, duration: int = 2, fatigue: float = 1.0
) -> SimpleNamespace:
    return SimpleNamespace(
        destination_id=destination,
        travel_duration_ticks=duration,
        fatigue_cost=fatigue,
    )


def observation(
    *,
    tick: int = 3,
    location: EntityId = A,
    hunger: int = 0,
    thirst: int = 0,
    exits: tuple[EntityId, ...] = (B,),
    journey=None,
    communications=(),
    visible_bodies=(),
    occurrences=(),
    resources=(),
    kin=None,
    hazards=None,
) -> SimpleNamespace:
    return SimpleNamespace(
        tick=tick,
        observer_id=OWNER_ENTITY,
        self_body=SimpleNamespace(
            location_id=location,
            hunger=need(hunger),
            thirst=need(thirst),
            fatigue=need(0),
            journey=journey,
            kinship_visible=kin,
        ),
        exits=tuple(visible_exit(item) for item in exits),
        communications=tuple(communications),
        visible_bodies=tuple(visible_bodies),
        occurrences=tuple(occurrences),
        resources=tuple(resources),
        hazard_kinds=hazards,
    )
