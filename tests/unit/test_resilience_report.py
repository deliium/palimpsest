# mypy: ignore-errors
"""Canonical societal-resilience report codec and assembly."""

from __future__ import annotations

import json

import pytest

from analysis.resilience_report import (
    RESILIENCE_REPORT_SCHEMA_VERSION,
    ResilienceReportInputs,
    build_resilience_report,
)
from analysis.resilience_report_codec import (
    ResilienceReportCodecError,
    decode_resilience_report,
    encode_resilience_report,
)
from analysis.resilience_series import RESILIENCE_DIMENSION_ORDER
from analysis.resilience_windows import RESILIENCE_POLICY_ID
from simulation.resilience_evidence import (
    OwnerLaneState,
    ResilienceBatchEvents,
    ResilienceBodyRow,
    ResilienceBoundaryFacts,
    ResilienceShockReceiptRow,
    ResilienceStockRow,
)

pytestmark = pytest.mark.unit


def _body(body_id: str = "a") -> ResilienceBodyRow:
    return ResilienceBodyRow(
        body_id=body_id,
        agent_id=f"agent-{body_id}",
        living=True,
        held_item_count=0,
        region_id=None,
    )


def _frame(
    boundary: int,
    *,
    stocks: tuple[ResilienceStockRow, ...] = (),
) -> ResilienceBoundaryFacts:
    return ResilienceBoundaryFacts(
        run_id="run-a",
        config_fingerprint="fp",
        boundary_tick=boundary,
        revision=boundary,
        body_projection_hash=None if boundary == 0 else "hash",
        history_length=0 if boundary == 0 else 1,
        infrastructure_channel=OwnerLaneState.OFF,
        ecology_channel=OwnerLaneState.COMPLETE,
        bodies=(_body(),),
        stocks=stocks,
        infrastructure=(),
        owners=(),
    )


def _stock(qty: int) -> ResilienceStockRow:
    return ResilienceStockRow(
        stock_id="s1",
        resource_kind="water",
        unit="units",
        quantity_tenths=qty,
        effective_capacity_tenths=40,
    )


def _inputs(
    *,
    shock_tick: int | None = 8,
    through: int = 24,
) -> ResilienceReportInputs:
    frames = tuple(_frame(b, stocks=(_stock(40),)) for b in range(0, through + 1))
    batches: list[ResilienceBatchEvents] = []
    for tick in range(through):
        shocks = ()
        if shock_tick is not None and tick == shock_tick:
            shocks = (
                ResilienceShockReceiptRow(
                    event_id="shock",
                    tick=tick,
                    sequence=0,
                    rule_id="r1",
                    kind="drought",
                    origin="spontaneous",
                    outcome="applied",
                ),
            )
        batches.append(
            ResilienceBatchEvents(
                tick=tick,
                resulting_revision=tick + 1,
                deaths=(),
                journey_arrivals=(),
                helps=(),
                feeds=(),
                contributions=(),
                exchanges=(),
                shock_receipts=shocks,
                event_count=1 if shocks else 0,
            )
        )
    # Fix history lengths to match cumulative events.
    fixed_frames = []
    history = 0
    for frame in frames:
        if frame.boundary_tick == 0:
            fixed_frames.append(frame)
            continue
        batch = batches[frame.boundary_tick - 1]
        history += batch.event_count
        fixed_frames.append(
            ResilienceBoundaryFacts(
                run_id=frame.run_id,
                config_fingerprint=frame.config_fingerprint,
                boundary_tick=frame.boundary_tick,
                revision=frame.revision,
                body_projection_hash=frame.body_projection_hash,
                history_length=history,
                infrastructure_channel=frame.infrastructure_channel,
                ecology_channel=frame.ecology_channel,
                bodies=frame.bodies,
                stocks=frame.stocks,
                infrastructure=frame.infrastructure,
                owners=frame.owners,
            )
        )
    return ResilienceReportInputs(
        run_id="run-a",
        config_fingerprint="fp",
        finalized_through=through,
        capture_through=through,
        capture_status="captured",
        frames=tuple(fixed_frames),
        batches=tuple(batches),
        schedule=(),
        regions_migration_enabled=False,
        subjective_valuation_enabled=False,
        projects_enabled=False,
        location_regions={},
    )


def test_ten_lane_report_round_trip_and_no_score() -> None:
    report = build_resilience_report(_inputs())
    assert report.schema_version == RESILIENCE_REPORT_SCHEMA_VERSION
    assert report.policy_id == RESILIENCE_POLICY_ID
    assert report.shock_status == "observed"
    assert len(report.episodes) == 1
    episode = report.episodes[0]
    dims = [panel["dimension"] for panel in episode["panels"]]
    assert dims == list(RESILIENCE_DIMENSION_ORDER)
    for panel in episode["panels"]:
        assert len(panel["windows"]) == 9
    immediate_dims = [
        panel["dimension"] for panel in episode["immediate_state"]["panels"]
    ]
    assert immediate_dims == [
        "population_recovery",
        "resource_recovery",
        "institution_continuity",
        "knowledge_retention",
        "technology_loss",
        "inequality",
        "infrastructure_recovery",
    ]
    payload = encode_resilience_report(report)
    assert b"resilience_score" not in payload
    assert b"composite_score" not in payload
    twin = decode_resilience_report(payload)
    assert encode_resilience_report(twin) == payload


def test_no_shock_vs_unknown() -> None:
    no_shock = build_resilience_report(_inputs(shock_tick=None))
    assert no_shock.shock_status == "no_shock"
    assert no_shock.episodes == ()
    base = _inputs(shock_tick=None)
    # receipt_missing schedule without applied → unknown
    missing = ResilienceReportInputs(
        run_id=base.run_id,
        config_fingerprint=base.config_fingerprint,
        finalized_through=base.finalized_through,
        capture_through=base.capture_through,
        capture_status=base.capture_status,
        frames=base.frames,
        batches=base.batches,
        schedule=((4, "planned"),),
        regions_migration_enabled=False,
        subjective_valuation_enabled=False,
        projects_enabled=False,
        location_regions={},
    )
    unknown = build_resilience_report(missing)
    assert unknown.shock_status == "unknown"
    assert unknown.schedule[0]["status"] == "receipt_missing"
    assert unknown.schedule[0]["outcome"] is None


def test_forbidden_score_and_wrong_schema_rejected() -> None:
    report = build_resilience_report(_inputs())
    payload = encode_resilience_report(report)
    document = json.loads(payload.decode("utf-8"))
    document["resilience_score"] = 1
    bad = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(ResilienceReportCodecError) as raised:
        decode_resilience_report(bad)
    assert raised.value.reason_code == "resilience_report_forbidden_field"

    document = json.loads(payload.decode("utf-8"))
    document["schema_version"] = "other"
    bad_schema = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    with pytest.raises(ResilienceReportCodecError):
        decode_resilience_report(bad_schema)


def test_boolean_numeric_rejected() -> None:
    report = build_resilience_report(_inputs())
    payload = encode_resilience_report(report)
    document = json.loads(payload.decode("utf-8"))
    measure = document["episodes"][0]["panels"][0]["windows"][1]["measures"][0]
    measure["value"] = True
    bad = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    with pytest.raises(ResilienceReportCodecError):
        decode_resilience_report(bad)


def test_docs_contract_mentions_schema_and_dimensions() -> None:
    from pathlib import Path

    docs = Path("docs/societal-resilience.md")
    text = docs.read_text(encoding="utf-8")
    assert RESILIENCE_REPORT_SCHEMA_VERSION in text
    assert "run_with_resilience_capture" in text
    assert "no universal" in text.lower() or "no composite" in text.lower()
    for dim in RESILIENCE_DIMENSION_ORDER:
        assert dim in text
