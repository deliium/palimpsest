# mypy: ignore-errors
"""Closed migration-displacement vocabulary, route contract, and rows."""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from agents.cognition import migration_displacement as module
from agents.cognition.migration_displacement import (
    MAX_ROUTE_EDGES,
    MAX_ROUTE_LOCATIONS,
    MIGRATION_DISPLACEMENT_FRAME_FIELD_COUNT,
    MIGRATION_DISPLACEMENT_FRAME_MAX_CHARS,
    MIGRATION_DISPLACEMENT_FRAME_MAX_RELATIONS,
    MIGRATION_DISPLACEMENT_FRAME_VERSION,
    MIGRATION_DISPLACEMENT_LEDGER_VERSION,
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
    MigrationNoticeCode,
    RouteBeliefBasis,
    RouteBeliefRow,
    RouteBeliefStatus,
    SocialClusterBeliefRow,
    WaveObservationRow,
    WaveObservationStatus,
    migration_candidate_id,
    migration_location_token,
    migration_publication_id,
    migration_route_tokens,
    require_route_edges,
    require_route_locations,
    route_edge_pairs,
)
from agents.models import AgentId
from analysis import migration_displacement_contract as analysis_contract
from analysis.migration_displacement_contract import analysis_migration_candidate_id
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
A = EntityId("loc-a")
B = EntityId("loc-b")
C = EntityId("loc-c")
D = EntityId("loc-d")
E = EntityId("loc-e")

FORBIDDEN_NAMES = frozenset(
    {
        "refugee",
        "asylum",
        "forced",
        "displaced",
        "threat",
        "hardship",
        "wellbeing",
        "assimilation",
        "integration_score",
        "score",
        "composite",
    }
)
FORBIDDEN_CLASS_NAMES = (
    "Refugee",
    "RefugeeStatus",
    "AsylumSeeker",
    "DisplacedPerson",
    "RefugeeCamp",
    "ResettlementAuthority",
    "MigrationRegistry",
    "WaveRegistry",
    "MigrationWave",
    "CauseOracle",
    "IntegrationOracle",
    "AssimilationScore",
    "WellbeingScore",
    "ForcedMigrationClassifier",
    "MigrationAuthority",
    "MigrationExecutor",
)


def _id(prefix: str, seed: str = "a") -> str:
    return prefix + seed * 32


def _intent(**overrides) -> MigrationIntentRow:
    values = {
        "intent_id": _id("mdi-"),
        "owner_id": OWNER,
        "origin_location_id": A,
        "destination_location_id": C,
        "route_locations": (A, B, C),
        "cause_ids": (_id("mdc-", "1"), _id("mdc-", "2")),
        "cluster_ids": (_id("mdg-"),),
        "status": MigrationIntentStatus.CONSIDERED,
        "confidence": 0.5,
        "first_tick": 1,
        "last_tick": 3,
    }
    values.update(overrides)
    return MigrationIntentRow(**values)


def _evidence(tick: int = 1, ref: str = "ref-1") -> MigrationEvidence:
    return MigrationEvidence(
        kind=MigrationCauseSource.DIRECT_OBSERVATION,
        source_owner_id=None,
        source_tick=tick,
        lineage_ref=ref,
        policy_version=MIGRATION_DISPLACEMENT_POLICY_VERSION,
    )


def test_policy_ledger_and_frame_versions_are_frozen() -> None:
    assert MIGRATION_DISPLACEMENT_POLICY_VERSION == "migration-displacement.v1"
    assert MIGRATION_DISPLACEMENT_LEDGER_VERSION == "migration-displacement-ledger.v1"
    assert MIGRATION_DISPLACEMENT_FRAME_VERSION == "mdp_v1"
    assert MIGRATION_DISPLACEMENT_FRAME_MAX_CHARS == 256
    assert MIGRATION_DISPLACEMENT_FRAME_MAX_RELATIONS == 4
    assert MIGRATION_DISPLACEMENT_FRAME_FIELD_COUNT == 14
    assert MAX_ROUTE_LOCATIONS == 4
    assert MAX_ROUTE_EDGES == 3
    assert [item.value for item in MigrationCauseKind] == [
        "resource_scarcity",
        "environmental_hazard",
        "conflict",
        "opportunity",
        "social_network",
        "institution",
        "unknown",
    ]
    assert len(MigrationCauseSource) == 16
    assert [item.value for item in MigrationIntentStatus] == [
        "considered",
        "planned",
        "departed",
        "arrived",
        "abandoned",
        "expired",
        "unknown",
    ]
    assert [item.value for item in RouteBeliefBasis] == [
        "direct_observation",
        "own_journey",
        "testimony",
        "inference",
        "unresolved",
    ]
    assert [item.value for item in RouteBeliefStatus] == [
        "open",
        "blocked_belief",
        "unresolved",
        "expired",
        "unknown",
    ]
    assert len(ClusterBasis) == 6
    assert len(ClusterStatus) == 5
    assert len(IntegrationDomain) == 8
    assert len(IntegrationStatus) == 5
    assert len(WaveObservationStatus) == 5
    assert len(CauseEvidenceStatus) == 5
    assert len(MigrationNoticeCode) == 16
    assert analysis_contract.MIGRATION_ANALYSIS_POLICY_VERSION == (
        "migration-displacement-analysis.v1"
    )
    assert analysis_contract.MIGRATION_CANDIDATE_PREFIX == "mig-"


def test_route_locations_preserve_order_and_reject_duplicates() -> None:
    route = require_route_locations([C, A, B])
    assert route == (C, A, B)
    assert require_route_locations((B, A)) == (B, A)
    with pytest.raises(ValueError, match="duplicate_location"):
        require_route_locations((A, B, A))
    for bad in ("loc-a", b"ab", {A, B}, {A: 1, B: 2}, frozenset({A, B})):
        with pytest.raises(ValueError, match="invalid_type"):
            require_route_locations(bad)
    with pytest.raises(ValueError, match="unresolved_entity"):
        require_route_locations((A, "loc-b"))
    with pytest.raises(ValueError, match="unresolved_entity"):
        require_route_locations((A, AgentId("loc-b")))


def test_route_requires_two_to_four_locations_and_distinct_consecutive_pairs() -> None:
    with pytest.raises(ValueError, match="location_count"):
        require_route_locations((A,))
    with pytest.raises(ValueError, match="location_count"):
        require_route_locations(())
    with pytest.raises(ValueError, match="location_count"):
        require_route_locations((A, B, C, D, E))
    assert len(require_route_locations((A, B, C, D))) == 4
    with pytest.raises(ValueError, match="route_self_edge"):
        require_route_locations((A, A, B))
    with pytest.raises(ValueError, match="route_self_edge"):
        route_edge_pairs((A, A))


def test_route_edges_are_ordered_directed_and_bounded() -> None:
    assert route_edge_pairs((C, A, B)) == (("loc-c", "loc-a"), ("loc-a", "loc-b"))
    assert route_edge_pairs((A, B, C, D)) == (
        ("loc-a", "loc-b"),
        ("loc-b", "loc-c"),
        ("loc-c", "loc-d"),
    )
    edges = (("loc-z", "loc-a"), ("loc-b", "loc-a"))
    assert require_route_edges(edges) == edges
    assert require_route_edges(()) == ()
    with pytest.raises(ValueError, match="edge_count"):
        require_route_edges(
            (("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")),
        )
    with pytest.raises(ValueError, match="route_self_edge"):
        require_route_edges((("a", "a"),))
    with pytest.raises(ValueError, match="duplicate_edge"):
        require_route_edges((("a", "b"), ("a", "b")))
    with pytest.raises(ValueError, match="invalid_edge"):
        require_route_edges((("a", "b", "c"),))
    with pytest.raises(ValueError, match="invalid_edge"):
        require_route_edges((["a", "b"],))
    with pytest.raises(ValueError, match="invalid_type"):
        require_route_edges("ab")


def test_reverse_directed_hops_are_not_collapsed() -> None:
    forward = route_edge_pairs((A, B))
    reverse = route_edge_pairs((B, A))
    assert forward == (("loc-a", "loc-b"),)
    assert reverse == (("loc-b", "loc-a"),)
    assert forward != reverse
    both = (("loc-a", "loc-b"), ("loc-b", "loc-a"))
    assert require_route_edges(both) == both
    assert require_route_edges(tuple(reversed(both))) == tuple(reversed(both))


def test_intent_validates_owner_route_cause_cluster_status_and_ticks() -> None:
    row = _intent(evidence=(_evidence(3, "ref-b"), _evidence(1, "ref-a")))
    assert row.route_locations == (A, B, C)
    assert [item.lineage_ref for item in row.evidence] == ["ref-a", "ref-b"]
    assert row.confidence == 0.5
    with pytest.raises(ValueError, match="owner_id: invalid_type"):
        _intent(owner_id="agent-1")
    with pytest.raises(ValueError, match="intent_id: invalid_identifier"):
        _intent(intent_id="mdi-short")
    with pytest.raises(ValueError, match="intent_id: invalid_identifier"):
        _intent(intent_id=_id("mdr-"))
    with pytest.raises(ValueError, match="route_origin_mismatch"):
        _intent(origin_location_id=B)
    with pytest.raises(ValueError, match="route_destination_mismatch"):
        _intent(destination_location_id=B)
    with pytest.raises(ValueError, match="unresolved_entity"):
        _intent(origin_location_id="loc-a")
    with pytest.raises(ValueError, match="duplicate_id"):
        _intent(cause_ids=(_id("mdc-"), _id("mdc-")))
    with pytest.raises(ValueError, match="unsorted_ids"):
        _intent(cause_ids=(_id("mdc-", "2"), _id("mdc-", "1")))
    with pytest.raises(ValueError, match="invalid_identifier"):
        _intent(cause_ids=(_id("mdg-"),))
    with pytest.raises(ValueError, match="cap_exceeded"):
        _intent(
            cluster_ids=(_id("mdg-", "1"), _id("mdg-", "2"), _id("mdg-", "3")),
        )
    with pytest.raises(ValueError, match="invalid_type"):
        _intent(cause_ids="mdc-")
    with pytest.raises(ValueError, match="unknown_intent_status"):
        _intent(status="considered")
    with pytest.raises(ValueError, match="out_of_range"):
        _intent(confidence=1.5)
    with pytest.raises(ValueError, match="not_finite"):
        _intent(confidence=float("nan"))
    with pytest.raises(ValueError, match="not_finite"):
        _intent(confidence=True)
    with pytest.raises(ValueError, match="invalid_tick"):
        _intent(first_tick=-1)
    with pytest.raises(ValueError, match="invalid_tick"):
        _intent(last_tick=True)
    with pytest.raises(ValueError, match="tick_order"):
        _intent(first_tick=5, last_tick=4)
    with pytest.raises(ValueError, match="cap_exceeded"):
        _intent(evidence=tuple(_evidence(tick, f"ref-{tick}") for tick in range(17)))
    with pytest.raises(ValueError, match="duplicate_evidence"):
        _intent(evidence=(_evidence(), _evidence()))
    quantized = _intent(confidence=0.1234567)
    assert quantized.confidence == 0.123457
    # every status is accepted; unknown enums fail closed
    for status in MigrationIntentStatus:
        assert _intent(status=status).status is status


def test_other_row_families_validate_closed_fields() -> None:
    route = RouteBeliefRow(
        route_id=_id("mdr-"),
        owner_id=OWNER,
        origin_location_id=A,
        destination_location_id=B,
        route_locations=(A, B),
        observed_duration_ticks=3,
        fatigue_cost=0.25,
        basis=RouteBeliefBasis.OWN_JOURNEY,
        status=RouteBeliefStatus.OPEN,
        first_tick=1,
        last_tick=2,
    )
    assert route.fatigue_cost == 0.25
    with pytest.raises(ValueError, match="invalid_duration"):
        dataclasses.replace(route, observed_duration_ticks=0)
    with pytest.raises(ValueError, match="out_of_range"):
        dataclasses.replace(route, fatigue_cost=-0.1)
    with pytest.raises(ValueError, match="unknown_route_basis"):
        dataclasses.replace(route, basis="own_journey")
    unobserved = dataclasses.replace(
        route,
        observed_duration_ticks=None,
        fatigue_cost=None,
        basis=RouteBeliefBasis.UNRESOLVED,
        status=RouteBeliefStatus.UNRESOLVED,
    )
    assert unobserved.observed_duration_ticks is None

    cause = CauseEvidenceRow(
        cause_id=_id("mdc-"),
        owner_id=OWNER,
        cause_kind=MigrationCauseKind.RESOURCE_SCARCITY,
        source_kind=MigrationCauseSource.OWN_NEED,
        anchor_ref="anchor-1",
        confidence=0.6,
        first_tick=1,
        last_tick=1,
        status=CauseEvidenceStatus.ACTIVE,
    )
    assert cause.anchor_ref == "anchor-1"
    with pytest.raises(ValueError, match="unknown_cause_kind"):
        dataclasses.replace(cause, cause_kind="conflict")
    with pytest.raises(ValueError, match="invalid_identifier"):
        dataclasses.replace(cause, anchor_ref="x" * 129)
    with pytest.raises(ValueError, match="invalid_identifier"):
        dataclasses.replace(cause, anchor_ref=" padded ")

    cluster = SocialClusterBeliefRow(
        cluster_id=_id("mdg-"),
        owner_id=OWNER,
        member_ids=(OWNER, OTHER),
        basis=ClusterBasis.KINSHIP,
        confidence=0.5,
        status=ClusterStatus.BELIEVED,
        first_tick=1,
        last_tick=2,
    )
    assert cluster.member_ids == (OWNER, OTHER)
    with pytest.raises(ValueError, match="member_count"):
        dataclasses.replace(cluster, member_ids=(OWNER,))
    with pytest.raises(ValueError, match="unsorted_ids"):
        dataclasses.replace(cluster, member_ids=(OTHER, OWNER))
    with pytest.raises(ValueError, match="duplicate_member"):
        dataclasses.replace(cluster, member_ids=(OWNER, OWNER))

    outcome = IntegrationBeliefRow(
        outcome_id=_id("mdn-"),
        owner_id=OWNER,
        destination_location_id=C,
        domain=IntegrationDomain.RESIDENCE,
        status=IntegrationStatus.SETTLED,
        confidence=0.7,
        first_tick=2,
        last_tick=9,
    )
    with pytest.raises(ValueError, match="unknown_integration_domain"):
        dataclasses.replace(outcome, domain="residence")

    wave = WaveObservationRow(
        observation_id=_id("mdw-"),
        owner_id=OWNER,
        origin_location_id=A,
        destination_location_id=C,
        participant_ids=(OWNER, OTHER),
        cause_ids=(_id("mdc-"),),
        cluster_ids=(),
        status=WaveObservationStatus.OBSERVED,
        first_tick=1,
        last_tick=4,
    )
    with pytest.raises(ValueError, match="route_self_edge"):
        dataclasses.replace(wave, destination_location_id=A)
    with pytest.raises(ValueError, match="member_count"):
        dataclasses.replace(wave, participant_ids=(OWNER,))
    with pytest.raises(ValueError, match="unknown_wave_status"):
        dataclasses.replace(wave, status="observed")

    ledger = MigrationDisplacementLedger(
        owner_id=OWNER,
        intents=(_intent(),),
        routes=(route,),
        causes=(cause,),
        clusters=(cluster,),
        integrations=(outcome,),
        waves=(wave,),
        notices=("truncated", "route_unobserved", "truncated"),
    )
    assert ledger.notices == ("route_unobserved", "truncated")
    assert ledger.policy_version == MIGRATION_DISPLACEMENT_POLICY_VERSION
    with pytest.raises(ValueError, match="owner_mismatch"):
        MigrationDisplacementLedger(owner_id=OTHER, intents=(_intent(),))
    with pytest.raises(ValueError, match="duplicate_row"):
        MigrationDisplacementLedger(owner_id=OWNER, intents=(_intent(), _intent()))
    with pytest.raises(ValueError, match="invalid_type"):
        MigrationDisplacementLedger(owner_id=OWNER, intents=(route,))
    with pytest.raises(ValueError, match="unknown_notice"):
        MigrationDisplacementLedger(owner_id=OWNER, notices=("refugee_wave",))
    with pytest.raises(ValueError, match="invalid_digest"):
        MigrationDisplacementLedger(owner_id=OWNER, digest="abc")
    with pytest.raises(ValueError, match="unsupported_policy"):
        MigrationDisplacementLedger(owner_id=OWNER, policy_version="other.v1")


def test_two_owners_may_hold_identical_or_overlapping_routes() -> None:
    first = _intent(owner_id=OWNER)
    second = _intent(owner_id=OTHER)
    assert first.route_locations == second.route_locations
    overlapping = _intent(
        intent_id=_id("mdi-", "b"),
        owner_id=OTHER,
        destination_location_id=D,
        route_locations=(B, C, D),
        origin_location_id=B,
    )
    assert set(overlapping.route_locations) & set(first.route_locations)
    MigrationDisplacementLedger(owner_id=OWNER, intents=(first,))
    MigrationDisplacementLedger(owner_id=OTHER, intents=(second, overlapping))


def test_no_forbidden_refugee_or_registry_object_exists() -> None:
    for name in FORBIDDEN_CLASS_NAMES:
        assert not hasattr(module, name)
        assert not hasattr(analysis_contract, name)
    classes = [
        item
        for _, item in inspect.getmembers(module, inspect.isclass)
        if getattr(item, "__module__", "") == module.__name__
        and dataclasses.is_dataclass(item)
    ]
    assert classes
    for item in classes:
        for field in dataclasses.fields(item):
            assert field.name not in FORBIDDEN_NAMES, (item.__name__, field.name)
    assert FORBIDDEN_NAMES <= analysis_contract.MIGRATION_FORBIDDEN_RESULT_FIELDS
    for enum_type in (
        MigrationCauseKind,
        MigrationCauseSource,
        IntegrationDomain,
        IntegrationStatus,
        MigrationNoticeCode,
    ):
        assert not ({item.value for item in enum_type} & FORBIDDEN_NAMES)
    for name in module.__all__:
        assert hasattr(module, name)
    assert not any(name.startswith("_") for name in module.__all__)


def test_public_tokens_never_emit_entity_objects() -> None:
    assert migration_location_token(A) == "loc-a"
    tokens = migration_route_tokens((C, A, B))
    assert tokens == ("loc-c", "loc-a", "loc-b")
    assert all(type(item) is str for item in tokens)
    for pair in route_edge_pairs((A, B, C)):
        assert all(type(item) is str for item in pair)
    with pytest.raises(ValueError, match="unresolved_entity"):
        migration_location_token("loc-a")
    candidate = migration_candidate_id("wave", "material-1")
    assert candidate.startswith("mig-")
    assert len(candidate) == len("mig-") + 32
    assert candidate == migration_candidate_id("wave", "material-1")
    assert candidate != migration_candidate_id("cluster", "material-1")
    assert candidate == analysis_migration_candidate_id("wave", "material-1")
    for kind in ("wave", "cluster", "outcome"):
        assert migration_candidate_id(kind, "m") == analysis_migration_candidate_id(
            kind, "m"
        )
    with pytest.raises(ValueError, match="unknown_candidate_kind"):
        migration_candidate_id("refugee", "m")
    with pytest.raises(ValueError, match="unknown_candidate_kind"):
        analysis_migration_candidate_id("refugee", "m")
    digest = "ab" * 32
    assert migration_publication_id(digest) == "md-pub-" + digest[:32]
    with pytest.raises(ValueError, match="invalid_digest"):
        migration_publication_id("short")
    with pytest.raises(ValueError, match="invalid_digest"):
        migration_publication_id("AB" * 32)
