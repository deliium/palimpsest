# mypy: ignore-errors
"""Bounded mdp_v1 frame encoding, speaker binding, and delivery provenance."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from agents.cognition.migration_displacement import (
    CauseEvidenceStatus,
    MigrationCauseKind,
    MigrationCauseSource,
    apply_migration_displacement_update,
    default_migration_displacement_policy,
    empty_migration_displacement_ledger,
)
from agents.cognition.migration_displacement_communication import (
    MIGRATION_FRAME_FIELD_COUNT,
    MIGRATION_FRAME_MAX_CHARS,
    MIGRATION_FRAME_MAX_RELATIONS,
    MIGRATION_FRAME_SUBJECT,
    MIGRATION_FRAME_VERSION,
    MigrationFrame,
    MigrationFrameAct,
    MigrationFrameError,
    attach_migration_displacement_relation,
    encode_migration_displacement_claim,
    independent_migration_root_count,
    migration_displacement_claim_relation,
    migration_displacement_frame_deliveries,
    migration_displacement_frames_from_inbox,
    migration_displacement_frames_from_observation,
    migration_frame_root_key,
    parse_migration_displacement_claim,
    parse_migration_displacement_relation,
)
from tests.unit.migration_displacement_helpers import (
    IDENTITY,
    OWNER,
    OWNER_ENTITY,
    PEER,
    PEER3_ENTITY,
    PEER_ENTITY,
    observation,
)
from world.actions import Ask, Move, Talk, Tell, Wait
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

SPEAKER = PEER_ENTITY.value
OTHER = PEER3_ENTITY.value


def _frame(
    act: MigrationFrameAct = MigrationFrameAct.REPORT_INTENT,
    *,
    speaker: str = SPEAKER,
    subject: str = SPEAKER,
    route: tuple[str, ...] = ("loc-a", "loc-b"),
    origin: str | None = None,
    destination: str | None = None,
    cause: MigrationCauseKind = MigrationCauseKind.RESOURCE_SCARCITY,
    source: MigrationCauseSource = MigrationCauseSource.TESTIMONY,
    cluster: str | None = None,
    confidence: int = 60,
    as_of: int = 2,
    evidence: str | None = None,
    provenance: str | None = None,
) -> MigrationFrame:
    if origin is None:
        origin = route[0] if route else ""
    if destination is None:
        destination = route[-1] if route else ""
    return MigrationFrame(
        act=act,
        speaker_ref=speaker,
        subject_ref=subject,
        origin_ref=origin,
        route_refs=route,
        destination_ref=destination,
        cause_kind=cause,
        source_kind=source,
        cluster_ref=cluster,
        confidence_q=confidence,
        as_of_tick=as_of,
        evidence_ref=evidence,
        declared_provenance_ref=provenance,
    )


def _frame_for(act: MigrationFrameAct, **kwargs) -> MigrationFrame:
    if act in (MigrationFrameAct.REPORT_INTENT, MigrationFrameAct.REPORT_ROUTE):
        return _frame(act, **kwargs)
    if act is MigrationFrameAct.REPORT_OUTCOME:
        return _frame(act, route=(), destination="loc-c", **kwargs)
    return _frame(act, route=(), **kwargs)


def _communication(
    *frames: MigrationFrame,
    speaker: EntityId = PEER_ENTITY,
    tick: int | None = None,
):
    relations = tuple(
        relation
        for frame in frames
        for relation in migration_displacement_claim_relation(frame)
    )
    return SimpleNamespace(
        speaker_id=speaker,
        listener_id=OWNER_ENTITY,
        utterance=origin_utterance(
            text=MIGRATION_FRAME_SUBJECT,
            speaker_id=speaker,
            relations=relations,
        ),
        provenance=None if tick is None else SimpleNamespace(source_tick=tick),
    )


def _observation(*frames: MigrationFrame, speaker: EntityId = PEER_ENTITY):
    return SimpleNamespace(communications=(_communication(*frames, speaker=speaker),))


def _relations(lines: tuple[str, ...]) -> tuple[SimpleNamespace, ...]:
    # Plain namespaces so oversize payloads can model a hostile delivery.
    return tuple(
        SimpleNamespace(
            subject=MIGRATION_FRAME_SUBJECT, predicate="relation", object=line
        )
        for line in lines
    )


def _raw_observation(lines: tuple[str, ...], speaker: EntityId = PEER_ENTITY):
    return SimpleNamespace(
        communications=(
            SimpleNamespace(
                speaker_id=speaker,
                listener_id=OWNER_ENTITY,
                utterance=SimpleNamespace(
                    content=SimpleNamespace(relations=_relations(lines))
                ),
            ),
        )
    )


def test_frame_has_thirteen_semantic_fields_and_fourteen_parts() -> None:
    assert MIGRATION_FRAME_SUBJECT == "mdp_v1"
    assert MIGRATION_FRAME_VERSION == "migration-displacement-communication.v1"
    assert MIGRATION_FRAME_MAX_CHARS == 256
    assert MIGRATION_FRAME_MAX_RELATIONS == 4
    assert MIGRATION_FRAME_FIELD_COUNT == 14
    assert len(dataclasses.fields(MigrationFrame)) == MIGRATION_FRAME_FIELD_COUNT - 1
    text = encode_migration_displacement_claim(_frame())
    parts = text.split(":")
    assert len(parts) == 14
    assert parts[0] == "mdp_v1"
    assert parts[1] == "report_intent"
    assert parts[2] == SPEAKER
    assert parts[5] == "loc-a~loc-b"
    assert len(text) <= MIGRATION_FRAME_MAX_CHARS
    with pytest.raises(MigrationFrameError, match="frame_field_count"):
        parse_migration_displacement_claim(":".join(parts[:-1]))
    with pytest.raises(MigrationFrameError, match="frame_field_count"):
        parse_migration_displacement_claim(":".join((*parts, "extra")))
    with pytest.raises(MigrationFrameError, match="frame_subject"):
        parse_migration_displacement_claim(":".join(("mdp_v2", *parts[1:])))


def test_round_trip_for_every_act_and_cause() -> None:
    for act in MigrationFrameAct:
        frame = _frame_for(act, evidence="anchor-1", provenance="declared-1")
        assert (
            parse_migration_displacement_claim(
                encode_migration_displacement_claim(frame)
            )
            == frame
        )
    for cause in MigrationCauseKind:
        frame = _frame_for(MigrationFrameAct.REPORT_CAUSE, cause=cause)
        assert (
            parse_migration_displacement_claim(
                encode_migration_displacement_claim(frame)
            )
            == frame
        )
    for source in MigrationCauseSource:
        frame = _frame_for(MigrationFrameAct.REPORT_ROUTE, source=source)
        assert (
            parse_migration_displacement_claim(
                encode_migration_displacement_claim(frame)
            )
            == frame
        )
    # Absent optional values round-trip as absent.
    bare = _frame_for(MigrationFrameAct.UNKNOWN)
    text = encode_migration_displacement_claim(bare)
    assert text.split(":")[-1] == "-"
    parsed = parse_migration_displacement_claim(text)
    assert parsed.cluster_ref is None
    assert parsed.evidence_ref is None
    assert parsed.declared_provenance_ref is None
    assert parsed.route_refs == ()
    with_cluster = _frame_for(MigrationFrameAct.REPORT_CLUSTER, cluster="cluster-1")
    assert (
        parse_migration_displacement_claim(
            encode_migration_displacement_claim(with_cluster)
        ).cluster_ref
        == "cluster-1"
    )


def test_report_route_requires_two_to_four_ordered_locations() -> None:
    for act in (MigrationFrameAct.REPORT_ROUTE, MigrationFrameAct.REPORT_INTENT):
        for size in (2, 3, 4):
            route = tuple(f"loc-{index}" for index in range(size))
            frame = _frame(act, route=route)
            assert frame.route_refs == route
            assert (
                parse_migration_displacement_claim(
                    encode_migration_displacement_claim(frame)
                ).route_refs
                == route
            )
        with pytest.raises(MigrationFrameError, match="frame_route_count"):
            _frame(act, route=("loc-a",))
        with pytest.raises(MigrationFrameError, match="frame_route_count"):
            _frame(act, route=())
        with pytest.raises(MigrationFrameError, match="frame_route_count"):
            _frame(act, route=tuple(f"loc-{index}" for index in range(5)))
    with pytest.raises(MigrationFrameError, match="frame_route_destination"):
        _frame(
            MigrationFrameAct.REPORT_ROUTE,
            route=("loc-a", "loc-b"),
            destination="loc-c",
        )


def test_ask_route_allows_empty_or_partial_probe() -> None:
    for route in ((), ("loc-a",), ("loc-a", "loc-b"), ("loc-a", "loc-b", "loc-c")):
        frame = _frame(MigrationFrameAct.ASK_ROUTE, route=route)
        parsed = parse_migration_displacement_claim(
            encode_migration_displacement_claim(frame)
        )
        assert parsed == frame
        assert parsed.route_refs == route
    with pytest.raises(MigrationFrameError, match="frame_route_count"):
        _frame(MigrationFrameAct.ASK_ROUTE, route=tuple(f"l{i}" for i in range(5)))
    for act in (
        MigrationFrameAct.REPORT_CAUSE,
        MigrationFrameAct.REPORT_CLUSTER,
        MigrationFrameAct.REPORT_OUTCOME,
        MigrationFrameAct.UNKNOWN,
    ):
        with pytest.raises(MigrationFrameError, match="frame_route_forbidden"):
            _frame(act, route=("loc-a", "loc-b"), destination="loc-b")


def test_route_is_ordered_and_bounded() -> None:
    forward = _frame(MigrationFrameAct.REPORT_ROUTE, route=("loc-a", "loc-b", "loc-c"))
    backward = _frame(MigrationFrameAct.REPORT_ROUTE, route=("loc-c", "loc-b", "loc-a"))
    assert forward.route_refs != backward.route_refs
    assert encode_migration_displacement_claim(
        forward
    ) != encode_migration_displacement_claim(backward)
    assert migration_frame_root_key(forward) != migration_frame_root_key(backward)
    with pytest.raises(MigrationFrameError, match="frame_route_duplicate"):
        _frame(MigrationFrameAct.REPORT_ROUTE, route=("loc-a", "loc-b", "loc-a"))
    with pytest.raises(MigrationFrameError):
        _frame(MigrationFrameAct.REPORT_ROUTE, route=("loc-a", "loc:b"))
    with pytest.raises(MigrationFrameError):
        _frame(MigrationFrameAct.REPORT_ROUTE, route=("loc-a", "loc~b"))
    with pytest.raises(MigrationFrameError, match="frame_route_origin"):
        _frame(
            MigrationFrameAct.REPORT_ROUTE,
            route=("loc-a", "loc-b"),
            origin="loc-z",
            destination="loc-b",
        )


def test_oversize_and_bad_enum_are_rejected() -> None:
    long_token = "x" * 128
    oversize = _frame(
        MigrationFrameAct.REPORT_ROUTE,
        speaker=long_token,
        subject=long_token,
        route=("loc-a", "loc-b"),
    )
    with pytest.raises(MigrationFrameError, match="frame_too_large"):
        encode_migration_displacement_claim(oversize)
    with pytest.raises(MigrationFrameError, match="frame_too_large"):
        parse_migration_displacement_claim("x" * (MIGRATION_FRAME_MAX_CHARS + 1))
    with pytest.raises(MigrationFrameError):
        _frame(speaker="x" * 129)
    good = encode_migration_displacement_claim(_frame()).split(":")

    def mutate(index: int, value: str) -> str:
        parts = list(good)
        parts[index] = value
        return ":".join(parts)

    for index, code in (
        (1, "frame_enum"),
        (7, "frame_enum"),
        (8, "frame_enum"),
        (10, "frame_confidence"),
        (11, "frame_tick"),
    ):
        with pytest.raises(MigrationFrameError, match=code):
            parse_migration_displacement_claim(mutate(index, "bogus"))
    with pytest.raises(MigrationFrameError, match="frame_confidence"):
        parse_migration_displacement_claim(mutate(10, "101"))
    with pytest.raises(MigrationFrameError, match="frame_tick"):
        parse_migration_displacement_claim(mutate(11, "-1"))
    with pytest.raises(MigrationFrameError, match="frame_confidence"):
        _frame(confidence=-1)
    with pytest.raises(MigrationFrameError, match="frame_tick"):
        _frame(as_of=-1)
    # Observation-level oversize relations are dropped, not raised.
    oversize_line = "x" * (MIGRATION_FRAME_MAX_CHARS + 1)
    assert (
        migration_displacement_frames_from_observation(
            _raw_observation((oversize_line,)), IDENTITY
        )
        == ()
    )
    assert (
        migration_displacement_frames_from_observation(
            _raw_observation((":".join(good[:-1]),)), IDENTITY
        )
        == ()
    )
    assert (
        migration_displacement_frames_from_observation(
            _raw_observation((mutate(1, "bogus"),)), IDENTITY
        )
        == ()
    )


def test_speaker_mismatch_is_rejected_but_other_subject_is_allowed() -> None:
    matching = _frame(subject=SPEAKER)
    other_subject = _frame(subject=OTHER)
    mismatched = _frame(speaker=OTHER, subject=OTHER)
    assert migration_displacement_frames_from_observation(
        _observation(matching), IDENTITY
    ) == (matching,)
    assert migration_displacement_frames_from_observation(
        _observation(other_subject), IDENTITY
    ) == (other_subject,)
    assert (
        migration_displacement_frames_from_observation(
            _observation(mismatched), IDENTITY
        )
        == ()
    )
    # One mismatching frame drops the whole group.
    assert (
        migration_displacement_frames_from_observation(
            _observation(matching, mismatched), IDENTITY
        )
        == ()
    )
    # No identity means no verified sender, so nothing is trusted.
    assert (
        migration_displacement_frames_from_observation(_observation(matching), None)
        == ()
    )
    # A listener other than the owner never delivers.
    foreign = _observation(matching)
    foreign.communications[0].listener_id = EntityId("body-9")
    assert migration_displacement_frames_from_observation(foreign, IDENTITY) == ()
    # The same rule applies to the runtime inbox.
    inbox = (
        SimpleNamespace(
            speaker_id=PEER_ENTITY,
            utterance=_communication(matching).utterance,
        ),
    )
    assert migration_displacement_frames_from_inbox(inbox, IDENTITY) == (matching,)
    bad_inbox = (
        SimpleNamespace(
            speaker_id=PEER_ENTITY,
            utterance=_communication(mismatched).utterance,
        ),
    )
    assert migration_displacement_frames_from_inbox(bad_inbox, IDENTITY) == ()


def test_declared_provenance_is_replaced_from_delivery() -> None:
    declared = "declared-lineage-claim"
    frame = _frame(
        MigrationFrameAct.REPORT_CAUSE,
        route=(),
        cause=MigrationCauseKind.CONFLICT,
        provenance=declared,
        confidence=80,
    )
    communication = _communication(frame, tick=2)
    deliveries = migration_displacement_frame_deliveries(
        (communication,), IDENTITY, default_tick=3
    )
    assert len(deliveries) == 1
    assert deliveries[0].speaker_owner == PEER
    assert deliveries[0].delivery_tick == 2
    # The declared claim is only carried as untrusted text on the frame.
    assert deliveries[0].frame.declared_provenance_ref == declared

    owner_observation = observation(tick=3, location=EntityId("loc-a"), exits=())
    owner_observation.communications = (communication,)
    updated = apply_migration_displacement_update(
        owner_id=OWNER,
        tick=3,
        observation=owner_observation,
        prior=empty_migration_displacement_ledger(OWNER),
        identity=IDENTITY,
        policy=default_migration_displacement_policy(),
    )
    testimony = [
        row
        for row in updated.causes
        if row.source_kind is MigrationCauseSource.TESTIMONY
    ]
    assert len(testimony) == 1
    row = testimony[0]
    assert row.cause_kind is MigrationCauseKind.CONFLICT
    assert row.status is CauseEvidenceStatus.ACTIVE
    assert row.anchor_ref is None
    # Confidence is capped below direct evidence.
    assert row.confidence <= 0.7
    for item in row.evidence:
        assert item.kind is MigrationCauseSource.TESTIMONY
        assert item.source_owner_id == PEER
        assert item.source_tick == 2
        assert declared not in item.lineage_ref
        assert item.lineage_ref.startswith("mdt-")
    assert declared not in repr(updated.causes)


def test_same_root_is_not_independent() -> None:
    first = _frame(provenance="declared-a")
    second = dataclasses.replace(
        first, declared_provenance_ref="declared-b", speaker_ref=OTHER
    )
    assert migration_frame_root_key(first) == migration_frame_root_key(second)
    deliveries = migration_displacement_frame_deliveries(
        (
            _communication(first, tick=2),
            _communication(second, speaker=PEER3_ENTITY, tick=2),
        ),
        IDENTITY,
        default_tick=3,
    )
    assert len(deliveries) == 2
    assert {item.speaker_owner.value for item in deliveries} == {
        "agent-2",
        "agent-3",
    }
    assert independent_migration_root_count(deliveries) == 1
    different = _frame(route=("loc-a", "loc-c"))
    assert migration_frame_root_key(different) != migration_frame_root_key(first)
    mixed = migration_displacement_frame_deliveries(
        (
            _communication(first, tick=2),
            _communication(different, tick=2),
        ),
        IDENTITY,
        default_tick=3,
    )
    assert independent_migration_root_count(mixed) == 2

    owner_observation = observation(tick=3, location=EntityId("loc-a"), exits=())
    owner_observation.communications = (
        _communication(first, tick=2),
        _communication(second, speaker=PEER3_ENTITY, tick=2),
    )
    updated = apply_migration_displacement_update(
        owner_id=OWNER,
        tick=3,
        observation=owner_observation,
        prior=empty_migration_displacement_ledger(OWNER),
        identity=IDENTITY,
        policy=default_migration_displacement_policy(),
    )
    assert "same_root_suppressed" in updated.notices


def test_only_talk_ask_tell_accept_a_frame() -> None:
    frame = _frame()
    base = origin_utterance(text="hello", speaker_id=OWNER_ENTITY)
    for command_type in (Talk, Ask, Tell):
        command = command_type(recipient_id=PEER_ENTITY, utterance=base)
        attached = attach_migration_displacement_relation(command, frame)
        assert type(attached) is command_type
        assert attached.recipient_id == PEER_ENTITY
        relations = attached.utterance.content.relations
        assert [item.subject for item in relations] == [MIGRATION_FRAME_SUBJECT]
        assert parse_migration_displacement_relation(relations[0]) == (
            encode_migration_displacement_claim(frame)
        )
    for other in (Move(destination_id=EntityId("loc-b")), Wait(), object()):
        with pytest.raises(MigrationFrameError, match="malformed_frame"):
            attach_migration_displacement_relation(other, frame)
    with pytest.raises(MigrationFrameError, match="frame_subject"):
        parse_migration_displacement_relation(
            CommunicationRelation(subject="other", predicate="relation", object="x")
        )
    with pytest.raises(MigrationFrameError, match="frame_relation"):
        parse_migration_displacement_relation(
            SimpleNamespace(subject=MIGRATION_FRAME_SUBJECT, object=3)
        )
    attached = attach_migration_displacement_relation(
        Talk(recipient_id=PEER_ENTITY, utterance=base), frame
    )
    assert attached.kind == "talk"


def test_at_most_one_group_per_command() -> None:
    base = origin_utterance(text="hello", speaker_id=OWNER_ENTITY)
    command = Talk(recipient_id=PEER_ENTITY, utterance=base)
    frames = tuple(_frame(route=("loc-a", f"loc-{index}")) for index in range(4))
    attached = attach_migration_displacement_relation(command, frames)
    group = [
        item
        for item in attached.utterance.content.relations
        if item.subject == MIGRATION_FRAME_SUBJECT
    ]
    assert len(group) == MIGRATION_FRAME_MAX_RELATIONS
    with pytest.raises(MigrationFrameError, match="frame_duplicate_group"):
        attach_migration_displacement_relation(attached, _frame())
    with pytest.raises(MigrationFrameError, match="frame_count"):
        attach_migration_displacement_relation(
            command, (*frames, _frame(route=("loc-a", "loc-z")))
        )
    with pytest.raises(MigrationFrameError, match="frame_count"):
        attach_migration_displacement_relation(command, ())
    # Four relations parse; five are dropped as one group.
    lines = tuple(encode_migration_displacement_claim(item) for item in frames)
    assert (
        len(
            migration_displacement_frames_from_observation(
                _raw_observation(lines), IDENTITY
            )
        )
        == 4
    )
    five = (
        *lines,
        encode_migration_displacement_claim(_frame(route=("loc-a", "loc-z"))),
    )
    assert (
        migration_displacement_frames_from_observation(_raw_observation(five), IDENTITY)
        == ()
    )
