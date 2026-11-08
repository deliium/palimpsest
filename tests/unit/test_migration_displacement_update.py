# mypy: ignore-errors
"""Ordered owner-scoped migration-displacement update pipeline."""

from __future__ import annotations

import dataclasses
import inspect
import logging
import re
from types import SimpleNamespace

import pytest

from agents.cognition import migration_displacement as module
from agents.cognition.migration_displacement import (
    MIGRATION_DISPLACEMENT_UPDATE_ORDER,
    CauseEvidenceStatus,
    ClusterBasis,
    IntegrationDomain,
    IntegrationStatus,
    MigrationCauseKind,
    MigrationCauseSource,
    MigrationDisplacementLedger,
    MigrationIntentStatus,
    RouteBeliefBasis,
    RouteBeliefStatus,
    WaveObservationStatus,
    apply_migration_displacement_update,
    default_migration_displacement_policy,
    empty_migration_displacement_ledger,
    migration_displacement_update_summary,
    require_migration_displacement_digest,
)
from agents.cognition.migration_displacement_communication import (
    MigrationFrame,
    MigrationFrameAct,
    migration_displacement_claim_relation,
)
from agents.models import AgentId
from tests.unit.migration_displacement_helpers import (
    IDENTITY,
    OWNER,
    OWNER_ENTITY,
    PEER,
    PEER3,
    PEER3_ENTITY,
    PEER_ENTITY,
    A,
    B,
    C,
    cause,
    intent,
    ledger,
    observation,
)
from world.communications import origin_utterance
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

POLICY = default_migration_displacement_policy()
EMPTY = empty_migration_displacement_ledger(OWNER)


def _update(obs, prior=EMPTY, *, tick: int = 3, identity=IDENTITY, **kwargs):
    return apply_migration_displacement_update(
        owner_id=OWNER,
        tick=tick,
        observation=obs,
        prior=prior,
        identity=identity,
        policy=POLICY,
        **kwargs,
    )


def _frame(
    act: MigrationFrameAct = MigrationFrameAct.REPORT_CAUSE,
    *,
    speaker: EntityId = PEER_ENTITY,
    speaker_ref: str | None = None,
    subject: str | None = None,
    route_refs: tuple[str, ...] = (),
    cause_kind: MigrationCauseKind = MigrationCauseKind.CONFLICT,
    provenance: str | None = "mdv-declared",
    confidence: int = 80,
) -> MigrationFrame:
    return MigrationFrame(
        act=act,
        speaker_ref=speaker.value if speaker_ref is None else speaker_ref,
        subject_ref=speaker.value if subject is None else subject,
        origin_ref=route_refs[0] if route_refs else "",
        route_refs=route_refs,
        destination_ref=route_refs[-1] if route_refs else "",
        cause_kind=cause_kind,
        source_kind=MigrationCauseSource.TESTIMONY,
        cluster_ref=None,
        confidence_q=confidence,
        as_of_tick=2,
        evidence_ref=None,
        declared_provenance_ref=provenance,
    )


def _communication(frame: MigrationFrame, *, speaker: EntityId = PEER_ENTITY):
    return SimpleNamespace(
        speaker_id=speaker,
        listener_id=OWNER_ENTITY,
        utterance=origin_utterance(
            text="mdp_v1",
            speaker_id=speaker,
            relations=migration_displacement_claim_relation(frame),
        ),
        provenance=SimpleNamespace(source_tick=2),
    )


def _concepts(*rows):
    return SimpleNamespace(owner_id=OWNER, concepts=tuple(rows))


def _concept(concept_id: str, status: str):
    return SimpleNamespace(concept_id=concept_id, status=status, member_ids=())


def _move(actor: EntityId, destination: EntityId):
    return SimpleNamespace(kind="move", actor_id=actor, destination_id=destination)


def test_update_order_is_own_then_frames_then_integration_then_waves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert MIGRATION_DISPLACEMENT_UPDATE_ORDER == (
        "intents",
        "routes",
        "causes",
        "clusters",
        "frames",
        "anchors",
        "integrations",
        "waves",
        "expire",
        "caps",
        "digest",
    )
    calls: list[str] = []
    for name in (
        "_update_own_intents",
        "_update_route_beliefs",
        "_update_cause_evidence",
        "_update_cluster_beliefs",
        "_apply_frames",
        "_resolve_anchors",
        "_update_integration_beliefs",
        "_update_wave_observations",
        "_expire_rows",
        "_enforce_caps",
        "_finalize_digest",
    ):
        original = getattr(module, name)

        def spy(*args, _name=name, _original=original, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, spy)
    _update(observation(hunger=90))
    assert calls == [
        "_update_own_intents",
        "_update_route_beliefs",
        "_update_cause_evidence",
        "_update_cluster_beliefs",
        "_apply_frames",
        "_resolve_anchors",
        "_update_integration_beliefs",
        "_update_wave_observations",
        "_expire_rows",
        "_enforce_caps",
        "_finalize_digest",
    ]


def test_hunger_creates_a_cause_backed_planned_intent_and_open_route() -> None:
    result = _update(observation(hunger=90))
    assert len(result.intents) == 1
    row = result.intents[0]
    assert row.status is MigrationIntentStatus.PLANNED
    assert row.route_locations == (A, B)
    causes = {item.cause_id: item for item in result.causes}
    assert set(row.cause_ids) <= set(causes)
    only = causes[row.cause_ids[0]]
    assert only.cause_kind is MigrationCauseKind.RESOURCE_SCARCITY
    assert only.source_kind is MigrationCauseSource.OWN_NEED
    assert len(result.routes) == 1
    assert result.routes[0].basis is RouteBeliefBasis.DIRECT_OBSERVATION
    assert result.routes[0].status is RouteBeliefStatus.OPEN
    require_migration_displacement_digest(result)
    summary = migration_displacement_update_summary(result)
    assert summary["intents"] == 1
    assert summary["causes"] == 1


def test_silence_creates_no_intent_route_cause_or_wave() -> None:
    silent = _update(observation(hunger=0, thirst=0))
    assert migration_displacement_update_summary(silent) == {
        "intents": 0,
        "routes": 0,
        "causes": 0,
        "clusters": 0,
        "integrations": 0,
        "waves": 0,
        "notices": 0,
    }
    # A visible exit alone is not a cause; communications without frames neither.
    plain = SimpleNamespace(
        speaker_id=PEER_ENTITY,
        listener_id=OWNER_ENTITY,
        utterance=origin_utterance(text="hello", speaker_id=PEER_ENTITY),
    )
    chatty = _update(observation(communications=(plain,)))
    assert chatty.digest == silent.digest
    assert chatty.intents == ()
    # Co-movement alone creates neither a cause nor an intent.
    moved = _update(
        observation(
            occurrences=(_move(PEER_ENTITY, B), _move(PEER3_ENTITY, B)),
        )
    )
    assert moved.intents == ()
    assert moved.routes == ()
    assert all(item.cause_kind is MigrationCauseKind.UNKNOWN for item in moved.causes)
    assert all(item.status is WaveObservationStatus.OBSERVED for item in moved.waves)


def test_unobserved_route_stays_unresolved() -> None:
    prior_cause = cause(tick=1)
    prior = ledger(
        intents=(intent((A, B, C), causes=(prior_cause,), tick=1),),
        causes=(prior_cause,),
    )
    result = _update(observation(hunger=90, exits=(B,)), prior)
    long_route = next(
        item for item in result.routes if item.route_locations == (A, B, C)
    )
    assert long_route.basis is RouteBeliefBasis.UNRESOLVED
    assert long_route.status is RouteBeliefStatus.UNRESOLVED
    assert long_route.evidence == ()
    assert "route_unobserved" in result.notices
    # The exit that is visible stays supported on its own.
    seen = _update(observation(hunger=90, exits=(B,)))
    assert seen.routes[0].basis is RouteBeliefBasis.DIRECT_OBSERVATION
    assert "route_unobserved" not in seen.notices


def test_own_ledgers_supply_local_anchors() -> None:
    organizations = _concepts(_concept("org-1", "offer"))
    rules = SimpleNamespace(
        owner_id=OWNER,
        rules=(SimpleNamespace(rule_id="rule-1", status="exclusion"),),
    )
    result = _update(
        observation(),
        organization_concepts=organizations,
        formal_rules=rules,
    )
    by_anchor = {item.anchor_ref: item for item in result.causes}
    assert by_anchor["organization:org-1"].cause_kind is MigrationCauseKind.OPPORTUNITY
    assert (
        by_anchor["organization:org-1"].source_kind
        is MigrationCauseSource.ORGANIZATION_BELIEF
    )
    assert by_anchor["rule:rule-1"].cause_kind is MigrationCauseKind.INSTITUTION
    assert "unresolved_anchor" not in result.notices
    # Weak local belief supports only a considered intent, never a plan.
    assert [item.status for item in result.intents] == [
        MigrationIntentStatus.CONSIDERED
    ]
    assert set(result.intents[0].cause_ids) <= {item.cause_id for item in result.causes}


def test_missing_anchor_is_retained_and_noticed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dangling = cause(
        MigrationCauseKind.OPPORTUNITY,
        MigrationCauseSource.ORGANIZATION_BELIEF,
        anchor="organization:org-9",
        tick=1,
    )
    prior = ledger(causes=(dangling,))
    with caplog.at_level(logging.WARNING):
        result = _update(observation(), prior)
    kept = [item for item in result.causes if item.cause_id == dangling.cause_id]
    assert len(kept) == 1
    assert kept[0].status is CauseEvidenceStatus.ACTIVE
    assert "unresolved_anchor" in result.notices
    assert "org-9" not in caplog.text
    versioned = dataclasses.replace(dangling, anchor_ref="organization:org-1@v9")
    resolved_wrong = _update(
        observation(),
        ledger(causes=(versioned,)),
        organization_concepts=SimpleNamespace(
            owner_id=OWNER,
            concepts=(
                SimpleNamespace(concept_id="org-1", status="neutral", version="v1"),
            ),
        ),
    )
    assert "unresolved_anchor" in resolved_wrong.notices
    ok = _update(
        observation(),
        ledger(causes=(versioned,)),
        organization_concepts=SimpleNamespace(
            owner_id=OWNER,
            concepts=(
                SimpleNamespace(concept_id="org-1", status="neutral", version="v9"),
            ),
        ),
    )
    assert "unresolved_anchor" not in ok.notices


def test_delivered_frame_is_testimony_not_truth() -> None:
    frame = _frame()
    result = _update(observation(communications=(_communication(frame),)))
    assert result.intents == ()
    assert result.routes == ()
    assert len(result.causes) == 1
    row = result.causes[0]
    assert row.cause_kind is MigrationCauseKind.CONFLICT
    assert row.source_kind is MigrationCauseSource.TESTIMONY
    assert row.confidence <= 0.7
    assert len(row.evidence) == 1
    stored = row.evidence[0]
    assert stored.kind is MigrationCauseSource.TESTIMONY
    assert stored.source_owner_id == PEER
    assert stored.source_tick == 2
    assert stored.lineage_ref.startswith("mdt-")
    assert "declared" not in stored.lineage_ref
    # The sender's own claim never becomes the owner's intent or a shared wave.
    assert result.waves == ()
    same = _update(observation(communications=(_communication(frame),)))
    assert same.digest == result.digest
    declared_changed = _update(
        observation(communications=(_communication(_frame(provenance="mdv-other")),))
    )
    assert declared_changed.causes[0].evidence[0].lineage_ref == stored.lineage_ref


def test_other_subject_is_allowed_when_speaker_matches() -> None:
    frame = _frame(
        MigrationFrameAct.REPORT_INTENT,
        subject=PEER3_ENTITY.value,
        route_refs=("loc-a", "loc-b"),
    )
    visible = _update(
        observation(
            communications=(_communication(frame),),
            visible_bodies=(SimpleNamespace(entity_id=PEER3_ENTITY),),
        )
    )
    assert len(visible.waves) == 1
    wave_row = visible.waves[0]
    assert wave_row.status is WaveObservationStatus.REPORTED
    assert set(wave_row.participant_ids) == {PEER, PEER3}
    assert OWNER not in wave_row.participant_ids
    assert visible.routes[0].basis is RouteBeliefBasis.TESTIMONY
    assert visible.intents == ()
    unseen = _update(observation(communications=(_communication(frame),)))
    assert unseen.waves == ()
    assert "peer_claim_untrusted" in unseen.notices


def test_speaker_mismatch_is_dropped(caplog: pytest.LogCaptureFixture) -> None:
    forged = _frame(speaker_ref=PEER3_ENTITY.value)
    with caplog.at_level(logging.WARNING):
        result = _update(observation(communications=(_communication(forged),)))
    assert result.causes == ()
    assert result.routes == ()
    assert "malformed_frame" in result.notices
    assert (
        "migration_displacement_frame_dropped reason_code=frame_speaker_mismatch"
        in (caplog.text)
    )
    assert PEER3_ENTITY.value not in caplog.text
    unknown_speaker = _update(
        observation(communications=(_communication(_frame()),)),
        identity=None,
    )
    assert unknown_speaker.causes == ()


def test_unobserved_origin_in_a_frame_is_not_stored() -> None:
    frame = _frame(
        MigrationFrameAct.REPORT_ROUTE,
        route_refs=("loc-x", "loc-y", "loc-z"),
    )
    result = _update(observation(communications=(_communication(frame),)))
    assert result.routes == ()
    assert "peer_claim_untrusted" in result.notices


def test_same_root_frames_are_not_counted_twice() -> None:
    frame = _frame()
    result = _update(
        observation(
            communications=(
                _communication(frame),
                _communication(_frame(provenance="mdv-again")),
            )
        )
    )
    assert len(result.causes) == 1
    assert len(result.causes[0].evidence) == 1
    assert "same_root_suppressed" in result.notices


def test_foreign_owner_ledger_is_rejected() -> None:
    foreign_prior = empty_migration_displacement_ledger(PEER)
    with pytest.raises(ValueError, match="migration_displacement: foreign_owner"):
        _update(observation(), foreign_prior)
    foreign_borders = SimpleNamespace(owner_id=PEER, disputes=())
    with pytest.raises(ValueError, match="migration_displacement: foreign_owner"):
        _update(observation(), borders=foreign_borders)
    with pytest.raises(ValueError, match="migration_displacement: foreign_owner"):
        _update(observation(), organization_concepts=SimpleNamespace(owner_id=PEER))
    own_borders = SimpleNamespace(owner_id=OWNER, disputes=())
    assert _update(observation(), borders=own_borders).intents == ()
    with pytest.raises(ValueError, match="invalid_type"):
        apply_migration_displacement_update(
            owner_id="agent-1",
            tick=1,
            observation=observation(),
            prior=EMPTY,
            identity=None,
            policy=POLICY,
        )
    with pytest.raises(TypeError, match="prior must be"):
        _update(observation(), object())


def test_forbidden_inputs_are_rejected() -> None:
    class WorldState:
        pass

    class AgentCommand:
        pass

    with pytest.raises(TypeError, match="forbidden_input"):
        _update(WorldState())
    with pytest.raises(TypeError, match="forbidden_input"):
        _update(observation(), inbox=AgentCommand())
    with pytest.raises(TypeError, match="forbidden_input"):
        _update(observation(), disputes=WorldState())
    source = inspect.getsource(module)
    pattern = "|".join(
        (
            "World" + "State",
            "World" + "Event",
            "Agent" + "Command",
            "Action" + "Submission",
            r"from world\._",
            r"import world\._",
        )
    )
    assert not re.search(pattern, source)


def test_pipeline_is_deterministic_under_permutation() -> None:
    kin = SimpleNamespace(parents=("agent-2",), children=("agent-3",))
    base = dict(
        hunger=90,
        exits=(B, C, A),
        kin=kin,
        visible_bodies=(
            SimpleNamespace(entity_id=PEER_ENTITY),
            SimpleNamespace(entity_id=PEER3_ENTITY),
        ),
        occurrences=(_move(PEER_ENTITY, B), _move(PEER3_ENTITY, B)),
    )
    permuted = dict(
        base,
        exits=(A, C, B),
        visible_bodies=tuple(reversed(base["visible_bodies"])),
        occurrences=tuple(reversed(base["occurrences"])),
    )
    relationships = (
        SimpleNamespace(source_id=OWNER, target_id=PEER),
        SimpleNamespace(source_id=OWNER, target_id=PEER3),
    )
    first = _update(observation(**base), relationships=relationships)
    second = _update(
        observation(**permuted), relationships=tuple(reversed(relationships))
    )
    assert first.digest == second.digest
    assert first == second
    assert first.clusters
    assert {item.basis for item in first.clusters} <= {
        ClusterBasis.KINSHIP,
        ClusterBasis.CO_MOVEMENT,
        ClusterBasis.RELATIONSHIP,
    }
    assert any(
        item.cause_kind is MigrationCauseKind.SOCIAL_NETWORK for item in first.causes
    )


def test_arrival_creates_integration_only_after_arrival() -> None:
    planned = _update(observation(hunger=90, tick=3), tick=3)
    assert planned.integrations == ()
    arrived = _update(
        observation(hunger=0, location=B, exits=(A,), tick=5), planned, tick=5
    )
    assert arrived.intents[0].status is MigrationIntentStatus.ARRIVED
    domains = {item.domain: item for item in arrived.integrations}
    assert domains[IntegrationDomain.RESIDENCE].status is IntegrationStatus.TRANSIENT
    assert IntegrationDomain.NEEDS in domains
    assert all(item.destination_location_id == B for item in arrived.integrations)
    assert all(item.first_tick == 5 for item in arrived.integrations)
    settled = _update(
        observation(hunger=0, location=B, exits=(A,), tick=20), arrived, tick=20
    )
    residence = next(
        item
        for item in settled.integrations
        if item.domain is IntegrationDomain.RESIDENCE
    )
    assert residence.status is IntegrationStatus.SETTLED
    require_migration_displacement_digest(settled)
    leaving = _update(
        observation(hunger=0, location=C, exits=(B,), tick=21), settled, tick=21
    )
    # A settled belief is a descriptive observation, never a score.
    assert all(
        not isinstance(getattr(item, "score", None), float)
        for item in leaving.integrations
    )


def test_return_and_onward_are_terminal_observations() -> None:
    planned = _update(observation(hunger=90, tick=3), tick=3)
    arrived = _update(observation(location=B, exits=(A,), tick=5), planned, tick=5)
    returned = _update(observation(location=A, exits=(B,), tick=6), arrived, tick=6)
    residence = next(
        item
        for item in returned.integrations
        if item.domain is IntegrationDomain.RESIDENCE
    )
    assert residence.status is IntegrationStatus.RETURNED
    again = _update(observation(location=B, exits=(A,), tick=7), returned, tick=7)
    kept = next(
        item
        for item in again.integrations
        if item.domain is IntegrationDomain.RESIDENCE
    )
    assert kept.status is IntegrationStatus.RETURNED


def test_waves_come_only_from_observed_movers() -> None:
    two = _update(
        observation(occurrences=(_move(PEER_ENTITY, B), _move(PEER3_ENTITY, B)))
    )
    assert len(two.waves) == 1
    assert set(two.waves[0].participant_ids) == {PEER, PEER3}
    assert two.waves[0].status is WaveObservationStatus.OBSERVED
    assert two.intents == ()
    one = _update(observation(occurrences=(_move(PEER_ENTITY, B),)))
    assert one.waves == ()
    unbound = _update(
        observation(
            occurrences=(
                _move(EntityId("body-8"), B),
                _move(EntityId("body-9"), B),
            )
        )
    )
    assert unbound.waves == ()


def test_update_rejects_bad_scalars_and_policy() -> None:
    with pytest.raises(ValueError, match="invalid_tick"):
        _update(observation(), tick=-1)
    with pytest.raises(ValueError, match="invalid_tick"):
        _update(observation(), tick=True)
    with pytest.raises(TypeError, match="policy must be"):
        apply_migration_displacement_update(
            owner_id=OWNER,
            tick=1,
            observation=observation(),
            prior=EMPTY,
            identity=None,
            policy=object(),
        )
    with pytest.raises(TypeError, match="relationships must be"):
        _update(observation(), relationships="x")
    assert isinstance(_update(observation()), MigrationDisplacementLedger)
    assert AgentId("agent-1") == OWNER
