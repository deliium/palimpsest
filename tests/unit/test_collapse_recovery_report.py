"""Canonical collapse-recovery report build and codec tests."""

from __future__ import annotations

import json

import pytest

from analysis.collapse_recovery_evidence import (
    CollapseBatch,
    CollapseBodyRow,
    CollapseEvidence,
    CollapseFrame,
    CollapseReceiptKind,
    CollapseReceiptRow,
    CollapseSourceCoverage,
    OwnerLaneState,
)
from analysis.collapse_recovery_report import (
    COLLAPSE_RECOVERY_REPORT_SCHEMA,
    build_collapse_recovery_report,
)
from analysis.collapse_recovery_report_codec import (
    CollapseRecoveryReportCodecError,
    decode_collapse_recovery_report,
    encode_collapse_recovery_report,
)
from simulation.resilience_evidence import ResilienceOwnerKeys

pytestmark = pytest.mark.unit


def _body(index: int, *, living: bool = True) -> CollapseBodyRow:
    return CollapseBodyRow(
        body_id=f"body-{index}",
        agent_id=f"agent-{index}",
        living=living,
        region_id="region-a",
    )


def _owner(
    index: int, *, keys: tuple[str, ...] = (), concepts: tuple[str, ...] = ()
) -> ResilienceOwnerKeys:
    return ResilienceOwnerKeys(
        agent_id=f"agent-{index}",
        body_id=f"body-{index}",
        living=True,
        institution_state=OwnerLaneState.COMPLETE,
        knowledge_state=OwnerLaneState.COMPLETE,
        recognized_concept_ids=concepts,
        active_content_keys=keys,
    )


def _frame(
    tick: int,
    bodies: tuple[CollapseBodyRow, ...],
    owners: tuple[ResilienceOwnerKeys, ...] = (),
) -> CollapseFrame:
    return CollapseFrame(
        run_id="run-report",
        config_fingerprint="cfg",
        tick=tick,
        revision=tick,
        body_projection_hash="hash",
        history_length=tick,
        infrastructure_channel=OwnerLaneState.OFF,
        bodies=bodies,
        infrastructure=(),
        owners=owners,
    )


def _contact(
    *,
    event_id: str,
    tick: int,
    sequence: int,
    kind: CollapseReceiptKind,
    left: str,
    right: str,
) -> CollapseReceiptRow:
    return CollapseReceiptRow(
        event_id=event_id,
        tick=tick,
        sequence=sequence,
        kind=kind,
        participant_body_id=left,
        counterpart_body_id=right,
        origin_location_id=None,
        destination_location_id=None,
        origin_region_id=None,
        destination_region_id=None,
        site_location_id=None,
        site_region_id=None,
        attribution_gap=False,
    )


def _clique(
    tick: int, members: tuple[int, ...], *, seq_base: int = 0
) -> list[CollapseReceiptRow]:
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    rows: list[CollapseReceiptRow] = []
    sequence = seq_base
    for kind in kinds:
        for i, left in enumerate(members):
            for right in members[i + 1 :]:
                rows.append(
                    _contact(
                        event_id=f"{kind.value}-{tick}-{left}-{right}",
                        tick=tick,
                        sequence=sequence,
                        kind=kind,
                        left=f"body-{left}",
                        right=f"body-{right}",
                    )
                )
                sequence += 1
    rows.sort(
        key=lambda row: (
            row.sequence,
            row.event_id,
            row.kind.value,
            row.participant_body_id or "",
        )
    )
    return rows


def _quiet_evidence(ticks: int = 64, bodies: int = 4) -> CollapseEvidence:
    frames = tuple(
        _frame(tick, tuple(_body(index) for index in range(bodies)))
        for tick in range(ticks + 1)
    )
    batches = tuple(
        CollapseBatch(
            tick=tick,
            resulting_revision=tick + 1,
            raw_event_count=0,
            receipts=(),
        )
        for tick in range(ticks)
    )
    return CollapseEvidence(
        run_id="run-report",
        config_fingerprint="cfg",
        captured_through=ticks,
        committed_through=ticks,
        seal_reason=None,
        region_ids=("region-a",),
        location_regions={},
        source_coverage=CollapseSourceCoverage(
            regions_migration=False,
            resource_exchange=False,
            production=False,
            infrastructure=OwnerLaneState.OFF,
        ),
        frames=frames,
        batches=batches,
    )


def _split_evidence() -> CollapseEvidence:
    members = tuple(range(8))
    left = tuple(range(4))
    right = tuple(range(4, 8))
    receipts: dict[int, tuple[CollapseReceiptRow, ...]] = {
        0: tuple(_clique(0, members)),
    }
    child = _clique(32, left) + _clique(32, right, seq_base=10_000)
    child.sort(
        key=lambda row: (
            row.sequence,
            row.event_id,
            row.kind.value,
            row.participant_body_id or "",
        )
    )
    receipts[32] = tuple(child)
    for start in (64, 96):
        cont = _clique(start, left) + _clique(start, right, seq_base=10_000)
        cont.sort(
            key=lambda row: (
                row.sequence,
                row.event_id,
                row.kind.value,
                row.participant_body_id or "",
            )
        )
        receipts[start] = tuple(cont)
    ticks = 128
    owners: dict[int, tuple[ResilienceOwnerKeys, ...]] = {}
    for tick in range(33):
        owners[tick] = tuple(
            _owner(index, keys=("tech-a", "tech-b"), concepts=("concept-a",))
            for index in range(8)
        )
    for tick in range(33, ticks + 1):
        owners[tick] = tuple(
            _owner(
                index,
                keys=("tech-b",) if index < 4 else ("tech-a", "tech-b"),
                concepts=("concept-a",),
            )
            for index in range(8)
        )
    frames = tuple(
        _frame(
            tick,
            tuple(_body(index) for index in range(8)),
            owners.get(tick, ()),
        )
        for tick in range(ticks + 1)
    )
    batches = tuple(
        CollapseBatch(
            tick=tick,
            resulting_revision=tick + 1,
            raw_event_count=len(receipts.get(tick, ())),
            receipts=receipts.get(tick, ()),
        )
        for tick in range(ticks)
    )
    return CollapseEvidence(
        run_id="run-report",
        config_fingerprint="cfg",
        captured_through=ticks,
        committed_through=ticks,
        seal_reason=None,
        region_ids=("region-a",),
        location_regions={},
        source_coverage=CollapseSourceCoverage(
            regions_migration=False,
            resource_exchange=True,
            production=False,
            infrastructure=OwnerLaneState.OFF,
        ),
        frames=frames,
        batches=batches,
    )


def test_quiet_report_round_trip_and_eight_axes() -> None:
    report = build_collapse_recovery_report(_quiet_evidence())
    assert report.schema_version == COLLAPSE_RECOVERY_REPORT_SCHEMA
    assert report.windows
    assert all(len(window["axes"]) == 8 for window in report.windows)
    payload = encode_collapse_recovery_report(report)
    again = decode_collapse_recovery_report(payload)
    assert encode_collapse_recovery_report(again) == payload
    assert b"body-" not in payload
    assert b"tech-a" not in payload
    assert b"CivilizationCollapsed" not in payload


def test_split_continuity_branch_loss_in_report() -> None:
    report = build_collapse_recovery_report(_split_evidence())
    lineage = report.lineage
    assert lineage["edges"]
    assert any(edge["kind"] == "split_successor" for edge in lineage["edges"])
    assert lineage["institutions"]
    assert lineage["techniques"]
    assert lineage["branch_losses"]
    payload = encode_collapse_recovery_report(report)
    assert decode_collapse_recovery_report(payload)
    text = payload.decode("utf-8")
    assert "concept-a" not in text
    assert "tech-a" not in text
    assert "body-0" not in text


def test_forbidden_score_field_rejected() -> None:
    report = build_collapse_recovery_report(_quiet_evidence())
    payload = encode_collapse_recovery_report(report)
    document = json.loads(payload)
    document["collapse_score"] = 1
    bad = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(CollapseRecoveryReportCodecError) as exc:
        decode_collapse_recovery_report(bad)
    assert exc.value.reason_code == "collapse_report_forbidden_field"


def test_boolean_as_int_rejected() -> None:
    report = build_collapse_recovery_report(_quiet_evidence())
    payload = encode_collapse_recovery_report(report)
    document = json.loads(payload)
    document["windows"][0]["complete"] = 1
    bad = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(CollapseRecoveryReportCodecError):
        decode_collapse_recovery_report(bad)


def test_one_child_split_rejected() -> None:
    report = build_collapse_recovery_report(_split_evidence())
    payload = encode_collapse_recovery_report(report)
    document = json.loads(payload)
    splits = [
        edge
        for edge in document["lineage"]["edges"]
        if edge["kind"] == "split_successor"
    ]
    assert len(splits) >= 2
    document["lineage"]["edges"] = [
        edge
        for edge in document["lineage"]["edges"]
        if edge is splits[0] or edge["kind"] != "split_successor"
    ]
    # Keep only first split edge.
    document["lineage"]["edges"] = [
        edge
        for edge in json.loads(payload)["lineage"]["edges"]
        if edge["kind"] != "split_successor"
    ] + [splits[0]]
    bad = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(CollapseRecoveryReportCodecError) as exc:
        decode_collapse_recovery_report(bad)
    assert exc.value.reason_code == "collapse_report_split_arity"


def test_dangling_edge_rejected() -> None:
    report = build_collapse_recovery_report(_split_evidence())
    payload = encode_collapse_recovery_report(report)
    document = json.loads(payload)
    document["lineage"]["edges"][0]["to_id"] = "cr-node-" + ("0" * 64)
    bad = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(CollapseRecoveryReportCodecError) as exc:
        decode_collapse_recovery_report(bad)
    assert exc.value.reason_code == "collapse_report_dangling_edge"


def test_oversize_payload_rejected() -> None:
    with pytest.raises(CollapseRecoveryReportCodecError) as exc:
        decode_collapse_recovery_report(b"{" + (b"x" * (8 * 1024 * 1024 + 1)))
    assert exc.value.reason_code == "collapse_report_too_large"
