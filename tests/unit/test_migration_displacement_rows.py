# mypy: ignore-errors
"""Six owner-scoped migration-displacement row families."""

from __future__ import annotations

import dataclasses
import logging

import pytest

from agents.cognition import migration_displacement as module
from agents.cognition.migration_displacement import (
    PREFIX_BY_FAMILY,
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
    cause_kind_token,
    cluster_member_tokens,
    empty_migration_displacement_ledger,
    integration_domain_token,
    intent_location_tokens,
    migration_displacement_row_projections,
    require_owner_migration_displacement,
    require_visible_members,
    route_location_tokens,
    route_pairs_supported,
    wave_participant_tokens,
)
from agents.models import AgentId
from tests.unit.migration_displacement_helpers import (
    OWNER,
    PEER,
    PEER3,
    A,
    B,
    C,
    D,
    cause,
    cluster,
    evidence,
    integration,
    intent,
    ledger,
    route,
    wave,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

FORBIDDEN_FIELDS = frozenset(
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
ROW_TYPES = (
    MigrationIntentRow,
    RouteBeliefRow,
    CauseEvidenceRow,
    SocialClusterBeliefRow,
    IntegrationBeliefRow,
    WaveObservationRow,
)


def test_six_row_families_have_closed_prefixes() -> None:
    assert dict(PREFIX_BY_FAMILY) == {
        "intent": "mdi-",
        "route": "mdr-",
        "cause": "mdc-",
        "cluster": "mdg-",
        "integration": "mdn-",
        "wave": "mdw-",
    }
    built = {
        "intent": intent().intent_id,
        "route": route().route_id,
        "cause": cause().cause_id,
        "cluster": cluster().cluster_id,
        "integration": integration().outcome_id,
        "wave": wave().observation_id,
    }
    for family, row_id in built.items():
        assert row_id.startswith(PREFIX_BY_FAMILY[family])
        assert len(row_id) == len(PREFIX_BY_FAMILY[family]) + 32
    with pytest.raises(ValueError, match="invalid_identifier"):
        dataclasses.replace(intent(), intent_id="mdr-" + "a" * 32)
    with pytest.raises(ValueError, match="invalid_identifier"):
        dataclasses.replace(route(), route_id="mdi-" + "a" * 32)
    with pytest.raises(ValueError, match="invalid_identifier"):
        dataclasses.replace(wave(), observation_id="mdw-" + "A" * 32)


def test_every_status_transition_target_is_a_closed_value() -> None:
    for status in MigrationIntentStatus:
        assert dataclasses.replace(intent(), status=status).status is status
    for status in RouteBeliefStatus:
        if status in (RouteBeliefStatus.OPEN, RouteBeliefStatus.BLOCKED_BELIEF):
            continue
        row = dataclasses.replace(
            route(),
            basis=RouteBeliefBasis.UNRESOLVED,
            status=status,
            evidence=(),
        )
        assert row.status is status
    for status in CauseEvidenceStatus:
        assert dataclasses.replace(cause(), status=status).status is status
    for status in ClusterStatus:
        assert dataclasses.replace(cluster(), status=status).status is status
    for status in IntegrationStatus:
        assert dataclasses.replace(integration(), status=status).status is status
    for status in WaveObservationStatus:
        assert dataclasses.replace(wave(), status=status).status is status
    with pytest.raises(ValueError, match="unknown_intent_status"):
        dataclasses.replace(intent(), status="planned")
    with pytest.raises(ValueError, match="unknown_wave_status"):
        dataclasses.replace(wave(), status="observed")


def test_intent_requires_cause_or_unknown_and_bounded_clusters() -> None:
    with pytest.raises(ValueError, match="missing_cause"):
        dataclasses.replace(intent(), cause_ids=())
    unknown = cause(MigrationCauseKind.UNKNOWN)
    accepted = intent(causes=(unknown,))
    assert accepted.cause_ids == (unknown.cause_id,)
    clusters = tuple(sorted(cluster(basis=basis).cluster_id for basis in ClusterBasis))
    assert len(clusters) > 2
    assert len(dataclasses.replace(intent(), cluster_ids=clusters[:2]).cluster_ids) == 2
    with pytest.raises(ValueError, match="cap_exceeded"):
        dataclasses.replace(intent(), cluster_ids=clusters[:3])
    with pytest.raises(ValueError, match="unsorted_ids"):
        dataclasses.replace(intent(), cluster_ids=tuple(reversed(clusters[:2])))
    with pytest.raises(ValueError, match="duplicate_id"):
        dataclasses.replace(intent(), cluster_ids=(clusters[0], clusters[0]))
    with pytest.raises(ValueError, match="route_origin_mismatch"):
        dataclasses.replace(intent(), origin_location_id=B)
    with pytest.raises(ValueError, match="route_destination_mismatch"):
        dataclasses.replace(intent(), destination_location_id=B)


def test_route_belief_requires_basis_and_contiguous_pairs() -> None:
    for status in (RouteBeliefStatus.OPEN, RouteBeliefStatus.BLOCKED_BELIEF):
        with pytest.raises(ValueError, match="route_basis_unresolved"):
            route(basis=RouteBeliefBasis.UNRESOLVED, status=status)
    unresolved = route(
        basis=RouteBeliefBasis.UNRESOLVED, status=RouteBeliefStatus.UNRESOLVED
    )
    assert unresolved.evidence == ()
    assert route_pairs_supported((A, B, C), [("loc-a", "loc-b"), ("loc-b", "loc-c")])
    assert not route_pairs_supported((A, B, C), [("loc-a", "loc-b")])
    assert not route_pairs_supported(
        (A, B, C), [("loc-b", "loc-a"), ("loc-c", "loc-b")]
    )
    for bad in ((A,), (A, A), (A, B, A), (A, B, C, D, EntityId("loc-e"))):
        with pytest.raises(ValueError):
            route(bad)
    with pytest.raises(ValueError, match="invalid_duration"):
        dataclasses.replace(route(), observed_duration_ticks=0)


def test_unknown_cause_has_no_anchor() -> None:
    unknown = cause(MigrationCauseKind.UNKNOWN)
    assert unknown.source_kind is MigrationCauseSource.UNKNOWN
    assert unknown.anchor_ref is None
    with pytest.raises(ValueError, match="unknown_cause_requires_unknown_source"):
        dataclasses.replace(unknown, source_kind=MigrationCauseSource.OWN_NEED)
    with pytest.raises(ValueError, match="unknown_cause_has_anchor"):
        dataclasses.replace(unknown, anchor_ref="rule:rule-1")
    anchored = cause(
        MigrationCauseKind.INSTITUTION,
        MigrationCauseSource.INSTITUTION_BELIEF,
        anchor="institution:inst-1",
    )
    assert anchored.anchor_ref == "institution:inst-1"
    for kind in MigrationCauseKind:
        assert cause(kind).cause_kind is kind


def test_cluster_requires_two_members_and_visible_members() -> None:
    with pytest.raises(ValueError, match="member_count"):
        cluster((OWNER,))
    with pytest.raises(ValueError, match="member_count"):
        dataclasses.replace(
            cluster(), member_ids=tuple(AgentId(f"a-{i:02d}") for i in range(17))
        )
    with pytest.raises(ValueError, match="owner_not_member"):
        cluster((PEER, PEER3), basis=ClusterBasis.KINSHIP)
    communicated = cluster((PEER, PEER3), basis=ClusterBasis.COMMUNICATION)
    assert OWNER not in communicated.member_ids
    with pytest.raises(ValueError, match="unsorted_ids"):
        dataclasses.replace(cluster(), member_ids=(PEER, OWNER))
    with pytest.raises(ValueError, match="duplicate_member"):
        dataclasses.replace(cluster(), member_ids=(OWNER, OWNER))
    assert require_visible_members((OWNER, PEER), (OWNER, PEER, PEER3)) == (OWNER, PEER)
    with pytest.raises(ValueError, match="member_not_visible"):
        require_visible_members((OWNER, PEER3), (OWNER, PEER))
    for basis in ClusterBasis:
        member_basis = cluster(basis=basis)
        assert member_basis.basis is basis


def test_integration_has_no_score_or_assimilation_field() -> None:
    names = {item.name for item in dataclasses.fields(IntegrationBeliefRow)}
    assert names.isdisjoint(FORBIDDEN_FIELDS)
    assert "confidence" in names
    assert not any(
        isinstance(getattr(integration(), name), float) and name != "confidence"
        for name in names
    )
    with pytest.raises(ValueError, match="unresolved_entity"):
        dataclasses.replace(integration(), destination_location_id=None)
    with pytest.raises(ValueError, match="unknown_integration_domain"):
        dataclasses.replace(integration(), domain="residence")
    for row_type in ROW_TYPES:
        assert {item.name for item in dataclasses.fields(row_type)}.isdisjoint(
            FORBIDDEN_FIELDS
        )
    assert {
        item.name for item in dataclasses.fields(MigrationDisplacementLedger)
    }.isdisjoint(FORBIDDEN_FIELDS)
    for domain in IntegrationDomain:
        for status in IntegrationStatus:
            row = integration(domain=domain, status=status)
            assert row.domain is domain
            assert row.status is status


def test_wave_observation_requires_two_participants_and_evidence() -> None:
    with pytest.raises(ValueError, match="member_count"):
        wave((OWNER,))
    nine = tuple(AgentId(f"agent-{index}") for index in range(1, 10))
    with pytest.raises(ValueError, match="member_count"):
        wave(nine)
    eight = wave(nine[:8])
    assert len(eight.participant_ids) == 8
    with pytest.raises(ValueError, match="missing_cause"):
        dataclasses.replace(wave(), cause_ids=())
    unknown = cause(MigrationCauseKind.UNKNOWN)
    assert wave(causes=(unknown,)).cause_ids == (unknown.cause_id,)
    with pytest.raises(ValueError, match="route_self_edge"):
        wave(origin=A, destination=A)
    too_much = tuple(evidence(tick=1, ref=f"ref-{index}") for index in range(17))
    with pytest.raises(ValueError, match="cap_exceeded"):
        dataclasses.replace(wave(), evidence=too_much)
    with pytest.raises(ValueError, match="duplicate_evidence"):
        dataclasses.replace(wave(), evidence=(evidence(), evidence()))
    unsorted = (evidence(5, "b"), evidence(2, "a"))
    sorted_rows = dataclasses.replace(wave(), evidence=unsorted)
    assert [item.source_tick for item in sorted_rows.evidence] == [2, 5]


def test_foreign_owner_is_rejected(caplog: pytest.LogCaptureFixture) -> None:
    foreign = AgentId("agent-9")
    own = empty_migration_displacement_ledger(OWNER)
    require_owner_migration_displacement(None, OWNER)
    require_owner_migration_displacement(own, OWNER)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ValueError, match="migration_displacement: foreign_owner"):
            require_owner_migration_displacement(
                empty_migration_displacement_ledger(foreign), OWNER
            )
        with pytest.raises(TypeError, match="must be MigrationDisplacementLedger"):
            require_owner_migration_displacement(object(), OWNER)
        with pytest.raises(ValueError, match="owner_mismatch"):
            MigrationDisplacementLedger(
                owner_id=OWNER, intents=(intent(owner=foreign),)
            )
    assert foreign.value not in caplog.text
    for builder in (
        lambda: intent(owner=foreign),
        lambda: route(owner=foreign),
    ):
        row = builder()
        assert row.owner_id == foreign
    with pytest.raises(ValueError, match="invalid_type"):
        dataclasses.replace(intent(), owner_id="agent-1")
    with pytest.raises(ValueError, match="unresolved_entity"):
        dataclasses.replace(wave(), origin_location_id="loc-a")


def test_invalid_rows_log_metadata_only(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValueError):
            dataclasses.replace(intent(), cause_ids=())
        with pytest.raises(ValueError):
            dataclasses.replace(cause(), confidence=float("nan"))
        with pytest.raises(ValueError):
            dataclasses.replace(cause(), confidence=1.5)
    assert "migration_displacement_row_rejected family=intent" in caplog.text
    assert "family=cause" in caplog.text
    assert "agent-1" not in caplog.text
    assert "loc-a" not in caplog.text


def test_confidence_is_quantized_and_ticks_are_ordered() -> None:
    assert cause(confidence=0.12345678).confidence == 0.123457
    with pytest.raises(ValueError, match="tick_order"):
        dataclasses.replace(cause(), first_tick=5, last_tick=2)
    with pytest.raises(ValueError, match="invalid_tick"):
        dataclasses.replace(cause(), first_tick=-1)
    with pytest.raises(ValueError, match="not_finite"):
        dataclasses.replace(cause(), confidence=True)


def test_public_tokens_never_emit_entity_objects() -> None:
    sample = intent()
    for tokens in (
        intent_location_tokens(sample),
        route_location_tokens(route()),
        cluster_member_tokens(cluster()),
        wave_participant_tokens(wave()),
    ):
        assert tokens
        assert all(type(item) is str for item in tokens)
        assert all(item.startswith(("mdl-", "mdo-")) for item in tokens)
    assert cause_kind_token(cause(MigrationCauseKind.RESOURCE_SCARCITY)) == (
        "resource-scarcity"
    )
    assert (
        integration_domain_token(
            integration(domain=IntegrationDomain.ORGANIZATION_PARTICIPATION)
        )
        == "organization-participation"
    )
    full = ledger(
        intents=(sample,),
        routes=(route(),),
        causes=(cause(),),
        clusters=(cluster(),),
        integrations=(integration(),),
        waves=(wave(),),
        notices=("unresolved_anchor",),
    )
    projections = migration_displacement_row_projections(full)
    assert {item.family for item in projections} == {
        "intent",
        "route",
        "cause",
        "cluster",
        "integration",
        "wave",
        "notice",
    }
    raw = {"agent-1", "agent-2", "loc-a", "loc-b", "loc-c"}
    for item in projections:
        leaves = [
            item.family,
            item.row_token,
            item.origin_token,
            item.destination_token,
            item.status,
            item.coverage,
            *item.route_tokens,
            *item.cause_tokens,
            *item.cluster_tokens,
        ]
        assert all(type(leaf) is str for leaf in leaves)
        assert raw.isdisjoint(leaves)
    for name in (
        "intent_location_tokens",
        "route_location_tokens",
        "cause_kind_token",
        "cluster_member_tokens",
        "integration_domain_token",
        "wave_participant_tokens",
    ):
        with pytest.raises(ValueError, match="invalid_type"):
            getattr(module, name)(object())


def test_evidence_validation_rejects_bad_kinds() -> None:
    with pytest.raises(ValueError, match="unknown_cause_source"):
        MigrationEvidence(
            kind="direct_observation",
            source_owner_id=None,
            source_tick=1,
            lineage_ref="ref-1",
        )
    with pytest.raises(ValueError, match="invalid_type"):
        MigrationEvidence(
            kind=MigrationCauseSource.TESTIMONY,
            source_owner_id="agent-2",
            source_tick=1,
            lineage_ref="ref-1",
        )
