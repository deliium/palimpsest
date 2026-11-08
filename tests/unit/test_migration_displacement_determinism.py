# mypy: ignore-errors
"""Deterministic migration-displacement ids, digests, ordering, and no-telepathy."""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from agents.cognition import migration_displacement as module
from agents.cognition.migration_displacement import (
    CauseEvidenceStatus,
    IntegrationStatus,
    MigrationCauseKind,
    MigrationCauseSource,
    MigrationDisplacementLedger,
    WaveObservationStatus,
    canonical_migration_displacement_json,
    canonical_migration_displacement_payload,
    empty_migration_displacement_ledger,
    finalize_migration_displacement_ledger,
    migration_cause_id,
    migration_cluster_id,
    migration_displacement_action_biases,
    migration_intent_id,
    migration_route_id,
    migration_wave_observation_id,
)
from agents.cognition.migration_displacement_communication import (
    MigrationFrame,
    MigrationFrameAct,
    encode_migration_displacement_claim,
    migration_frame_root_key,
    parse_migration_displacement_claim,
)
from analysis.migration_displacement_detection import detect_migration_waves
from analysis.migration_displacement_identity import migration_candidate_row
from simulation.migration_displacement_codec import (
    encode_migration_displacement_snapshot,
    finalize_migration_displacement_snapshot,
)
from simulation.migration_displacement_models import (
    empty_migration_displacement_snapshot,
)
from tests.unit.migration_displacement_analysis_helpers import POLICY, movement
from tests.unit.migration_displacement_helpers import (
    OWNER,
    PEER,
    PEER3,
    A,
    B,
    C,
    cause,
    cluster,
    integration,
    intent,
    ledger,
    observation,
    route,
    wave,
)

pytestmark = __import__("pytest").mark.unit

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_SRC = tuple(
    sorted(
        path
        for pattern in (
            "src/agents/cognition/migration_displacement*.py",
            "src/analysis/migration_displacement_*.py",
            "src/simulation/migration_displacement_*.py",
        )
        for path in ROOT.glob(pattern)
    )
)


def test_ordered_route_ids_are_stable_and_order_sensitive() -> None:
    route_a = (A, B, C)
    assert migration_route_id(OWNER, route_a, 1) == migration_route_id(
        OWNER, route_a, 1
    )
    assert migration_route_id(OWNER, route_a, 1) != migration_route_id(
        OWNER, (A, C, B), 1
    )

    @given(st.sampled_from([(A, B), (A, B, C), (A, C)]))
    @settings(max_examples=6)
    def check(locations):
        assert migration_route_id(OWNER, locations, 1) == migration_route_id(
            OWNER, locations, 1
        )

    check()


def test_cluster_member_sorting_produces_the_same_cluster_id() -> None:
    from agents.cognition.migration_displacement import ClusterBasis

    members = tuple(sorted((OWNER, PEER, PEER3), key=lambda item: item.value))
    first = migration_cluster_id(OWNER, members, ClusterBasis.KINSHIP, 1)
    second = migration_cluster_id(OWNER, members, ClusterBasis.KINSHIP, 1)
    assert first == second
    reshuffled = tuple(
        sorted((PEER3, OWNER, PEER), key=lambda item: item.value)
    )
    assert migration_cluster_id(
        OWNER, reshuffled, ClusterBasis.KINSHIP, 1
    ) == first


def test_identical_inputs_produce_identical_ids_and_digests() -> None:
    first = ledger(
        causes=(cause(),),
        routes=(route(),),
        intents=(intent(),),
        clusters=(cluster(),),
        integrations=(integration(),),
        waves=(wave(),),
    )
    second = ledger(
        causes=(cause(),),
        routes=(route(),),
        intents=(intent(),),
        clusters=(cluster(),),
        integrations=(integration(),),
        waves=(wave(),),
    )
    assert first == second
    assert first.digest == second.digest
    assert migration_cause_id(
        OWNER,
        MigrationCauseKind.RESOURCE_SCARCITY,
        MigrationCauseSource.OWN_NEED,
        None,
        1,
    ) == migration_cause_id(
        OWNER,
        MigrationCauseKind.RESOURCE_SCARCITY,
        MigrationCauseSource.OWN_NEED,
        None,
        1,
    )
    assert migration_intent_id(OWNER, (A, B, C), 1) == migration_intent_id(
        OWNER, (A, B, C), 1
    )
    participants = tuple(sorted((OWNER, PEER), key=lambda item: item.value))
    assert migration_wave_observation_id(
        OWNER, A, B, participants, 1
    ) == migration_wave_observation_id(OWNER, A, B, participants, 1)


def test_changed_confidence_route_cause_or_tick_changes_id() -> None:
    base = migration_cause_id(
        OWNER,
        MigrationCauseKind.CONFLICT,
        MigrationCauseSource.TESTIMONY,
        "conflict:c-1",
        1,
    )
    different_tick = migration_cause_id(
        OWNER,
        MigrationCauseKind.CONFLICT,
        MigrationCauseSource.TESTIMONY,
        "conflict:c-1",
        2,
    )
    different_cause = migration_cause_id(
        OWNER,
        MigrationCauseKind.OPPORTUNITY,
        MigrationCauseSource.TESTIMONY,
        "conflict:c-1",
        1,
    )
    assert base != different_tick
    assert base != different_cause
    assert migration_route_id(OWNER, (A, B), 1) != migration_route_id(
        OWNER, (A, C), 1
    )
    low = cause(confidence=0.4)
    high = cause(confidence=0.9)
    assert finalize_migration_displacement_ledger(
        MigrationDisplacementLedger(owner_id=OWNER, causes=(low,))
    ).digest != finalize_migration_displacement_ledger(
        MigrationDisplacementLedger(owner_id=OWNER, causes=(high,))
    ).digest


def test_canonical_json_has_sorted_keys_and_no_raw_identities() -> None:
    row = ledger(
        causes=(cause(),),
        routes=(route(),),
        waves=(wave(),),
    )
    text = canonical_migration_displacement_json(row)
    payload = json.loads(text)
    assert list(payload) == sorted(payload)
    assert "agent-1" not in text
    assert "body-1" not in text
    assert "EntityId" not in text
    assert "AgentId" not in text
    assert "digest" not in canonical_migration_displacement_payload(row)


def test_wave_cluster_and_outcome_ordering_is_total() -> None:
    causes = (
        cause(tick=2),
        cause(
            MigrationCauseKind.CONFLICT,
            MigrationCauseSource.CONFLICT_BELIEF,
            anchor="conflict:c-1",
            tick=1,
        ),
    )
    clusters = (
        cluster(members=(OWNER, PEER3), tick=2),
        cluster(members=(OWNER, PEER), tick=1),
    )
    integrations = (
        integration(status=IntegrationStatus.RETURNED, tick=2),
        integration(status=IntegrationStatus.SETTLED, tick=1),
    )
    waves = (
        wave(participants=(OWNER, PEER3), tick=2),
        wave(participants=(OWNER, PEER), tick=1),
    )
    rich = ledger(
        causes=causes,
        clusters=clusters,
        integrations=integrations,
        waves=waves,
    )
    permuted = ledger(
        causes=tuple(reversed(causes)),
        clusters=tuple(reversed(clusters)),
        integrations=tuple(reversed(integrations)),
        waves=tuple(reversed(waves)),
    )
    assert rich.digest == permuted.digest
    movements = (
        movement("agent-2", "loc-a", "loc-b", 2),
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-3", "loc-a", "loc-b", 3),
    )
    detected = detect_migration_waves(movements, (), (), POLICY)
    again = detect_migration_waves(tuple(reversed(movements)), (), (), POLICY)
    assert [row.wave_token for row in detected] == [
        row.wave_token for row in again
    ]
    assert detected
    assert detected[0].wave_token.startswith("mig-")
    candidate = migration_candidate_row(
        "wave",
        detected[0].wave_token,
        first_tick=detected[0].start_tick,
        last_tick=detected[0].end_tick,
        member_count=len(detected[0].participant_tokens),
        destination_token=detected[0].destination_token,
        classification=detected[0].displacement_classification,
        member_tokens=detected[0].participant_tokens,
    )
    assert candidate.candidate_token == detected[0].wave_token


def test_no_hash_uuid_wall_clock_or_global_rng() -> None:
    source = inspect.getsource(module)
    assert "import uuid" not in source
    assert "time.time" not in source
    assert "datetime.now" not in source
    assert "random." not in source
    assert "hash(" not in source
    for path in MIGRATION_SRC:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "hash", path
                assert node.func.id not in {"uuid4", "uuid1"}, path


def test_no_telepathy_separate_ledgers_and_analytical_wave() -> None:
    first = empty_migration_displacement_ledger(OWNER)
    second = empty_migration_displacement_ledger(PEER)
    assert first.owner_id != second.owner_id
    assert first.digest != second.digest
    moved = (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-a", "loc-b", 2),
    )
    waves = detect_migration_waves(moved, (), (), POLICY)
    assert len(waves) == 1
    assert len(waves[0].participant_tokens) == 2
    # Analytical wave exists without any shared owner cognition state.
    assert first.waves == ()
    assert second.waves == ()
    owner_wave = wave(participants=(OWNER, PEER), owner=OWNER)
    peer_wave = wave(participants=(OWNER, PEER), owner=PEER)
    owner_ledger = ledger(waves=(owner_wave,), owner=OWNER)
    peer_ledger = ledger(waves=(peer_wave,), owner=PEER)
    assert owner_ledger.digest != peer_ledger.digest
    assert {owner_ledger.owner_id, peer_ledger.owner_id} == {OWNER, PEER}
    # Ledgers stay owner-scoped: they cannot be merged across owners.
    from agents.cognition.migration_displacement import (
        merge_migration_displacement_ledger,
    )

    try:
        merge_migration_displacement_ledger(owner_ledger, peer_ledger)
    except ValueError as exc:
        assert "foreign_owner" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected foreign_owner rejection")


def test_same_root_testimony_is_counted_once() -> None:
    frame = MigrationFrame(
        act=MigrationFrameAct.REPORT_CAUSE,
        speaker_ref="body-2",
        subject_ref="body-2",
        origin_ref="",
        route_refs=(),
        destination_ref="",
        cause_kind=MigrationCauseKind.CONFLICT,
        source_kind=MigrationCauseSource.TESTIMONY,
        cluster_ref=None,
        confidence_q=80,
        as_of_tick=2,
        evidence_ref=None,
        declared_provenance_ref="mdv-declared",
    )
    again = MigrationFrame(
        act=frame.act,
        speaker_ref=frame.speaker_ref,
        subject_ref=frame.subject_ref,
        origin_ref=frame.origin_ref,
        route_refs=frame.route_refs,
        destination_ref=frame.destination_ref,
        cause_kind=frame.cause_kind,
        source_kind=frame.source_kind,
        cluster_ref=frame.cluster_ref,
        confidence_q=frame.confidence_q,
        as_of_tick=frame.as_of_tick,
        evidence_ref=frame.evidence_ref,
        declared_provenance_ref="mdv-other",
    )
    assert migration_frame_root_key(frame) == migration_frame_root_key(again)
    assert parse_migration_displacement_claim(
        encode_migration_displacement_claim(frame)
    ).cause_kind is MigrationCauseKind.CONFLICT


def test_bias_helper_is_mapping_only() -> None:
    from agents.cognition.migration_displacement import (
        default_migration_displacement_policy,
    )

    biases = migration_displacement_action_biases(
        ledger(intents=(intent(),), routes=(route(),), causes=(cause(),)),
        observation=observation(hunger=90),
        known_destinations=(B,),
        policy=default_migration_displacement_policy(),
    )
    assert isinstance(biases, dict)
    assert all(
        isinstance(key, str) and isinstance(value, float)
        for key, value in biases.items()
    )


def test_canonical_snapshot_bytes_are_stable() -> None:
    snapshot = finalize_migration_displacement_snapshot(
        empty_migration_displacement_snapshot(
            "run-1", publication_id="md-pub-pending", digest="0" * 64
        )
    )
    assert encode_migration_displacement_snapshot(
        snapshot
    ) == encode_migration_displacement_snapshot(snapshot)


def test_status_enums_remain_closed() -> None:
    assert CauseEvidenceStatus.ACTIVE.value == "active"
    assert WaveObservationStatus.OBSERVED.value == "observed"
    assert IntegrationStatus.SETTLED.value == "settled"
