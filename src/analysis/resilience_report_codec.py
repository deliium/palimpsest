"""Strict canonical codec for societal-resilience-report-v1."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from analysis.resilience_report import (
    IMMEDIATE_STATE_DIMENSIONS,
    RESILIENCE_REPORT_SCHEMA_VERSION,
    ResilienceReport,
)
from analysis.resilience_series import RESILIENCE_DIMENSION_ORDER
from analysis.resilience_windows import RESILIENCE_POLICY_ID
from simulation.resilience_evidence import MAX_RESILIENCE_APPLIED_SHOCK_TICKS

__all__ = [
    "ResilienceReportCodecError",
    "decode_resilience_report",
    "encode_resilience_report",
]

_MAX_BYTES: Final[int] = 8 * 1024 * 1024
_FORBIDDEN_SCORE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "resilience_score",
        "composite_score",
        "universal_score",
        "score",
        "ranking",
        "recommendation",
    }
)

_ROOT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "policy_id",
        "run_id",
        "config_fingerprint",
        "finalized_through",
        "capture_through",
        "capture_status",
        "shock_status",
        "non_applied_counts",
        "schedule",
        "episodes",
    }
)
_SCHEDULE_KEYS: Final[frozenset[str]] = frozenset(
    {"tick", "rule_id", "status", "outcome", "receipt_event_id"}
)
_EPISODE_KEYS: Final[frozenset[str]] = frozenset(
    {"shock_tick", "receipts", "immediate_state", "windows", "panels"}
)
_RECEIPT_KEYS: Final[frozenset[str]] = frozenset(
    {"tick", "sequence", "event_id", "kind", "origin", "outcome"}
)
_WINDOW_AXIS_KEYS: Final[frozenset[str]] = frozenset(
    {"window_index", "status", "reason", "expected_ticks", "observed_ticks"}
)
_PANEL_KEYS: Final[frozenset[str]] = frozenset({"dimension", "windows"})
_CELL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "window_index",
        "status",
        "reason",
        "expected_ticks",
        "observed_ticks",
        "owner_coverage",
        "measures",
    }
)
_IMMEDIATE_ROOT_KEYS: Final[frozenset[str]] = frozenset(
    {"boundary_tick", "pre_boundary_tick", "panels"}
)
_IMMEDIATE_PANEL_KEYS: Final[frozenset[str]] = frozenset(
    {"dimension", "status", "reason", "owner_coverage", "measures"}
)
_MEASURE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "metric",
        "scope",
        "unit",
        "value",
        "numerator",
        "denominator",
        "delta_from_baseline",
        "reason",
        "delta_reason",
    }
)
_OWNER_KEYS: Final[frozenset[str]] = frozenset({"eligible_owners", "observed_owners"})
_SCOPE_KEYS: Final[frozenset[str]] = frozenset({"kind", "key"})
_SHOCK_STATUS: Final[frozenset[str]] = frozenset({"observed", "no_shock", "unknown"})
_CAPTURE_STATUS: Final[frozenset[str]] = frozenset({"captured", "sealed"})
_COVERAGE: Final[frozenset[str]] = frozenset(
    {"complete", "partial", "unavailable", "censored"}
)
_SCHEDULE_STATUS: Final[frozenset[str]] = frozenset(
    {"applied", "not_applied", "not_reached", "unverified", "receipt_missing"}
)


class ResilienceReportCodecError(ValueError):
    """Closed codec failure."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def encode_resilience_report(report: ResilienceReport) -> bytes:
    """Emit UTF-8 canonical JSON without a trailing newline."""

    if type(report) is not ResilienceReport:
        raise ResilienceReportCodecError("resilience_report_invalid")
    if report.schema_version != RESILIENCE_REPORT_SCHEMA_VERSION:
        raise ResilienceReportCodecError("resilience_report_schema")
    if report.policy_id != RESILIENCE_POLICY_ID:
        raise ResilienceReportCodecError("resilience_report_policy")
    document = _report_to_document(report)
    _validate_document(document)
    try:
        payload = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ResilienceReportCodecError("resilience_report_encode") from exc
    if len(payload) > _MAX_BYTES:
        raise ResilienceReportCodecError("resilience_report_too_large")
    return payload


def decode_resilience_report(payload: bytes) -> ResilienceReport:
    """Decode and re-encode for canonical byte equality."""

    if type(payload) is not bytes:
        raise ResilienceReportCodecError("resilience_report_invalid_payload")
    if len(payload) > _MAX_BYTES:
        raise ResilienceReportCodecError("resilience_report_too_large")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResilienceReportCodecError("resilience_report_encoding") from exc
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicates)
        raw = decoder.decode(text)
    except ResilienceReportCodecError:
        raise
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise ResilienceReportCodecError("resilience_report_invalid_json") from exc
    if type(raw) is not dict:
        raise ResilienceReportCodecError("resilience_report_invalid_object")
    _validate_document(raw)
    report = _document_to_report(raw)
    encoded = encode_resilience_report(report)
    if encoded != payload:
        raise ResilienceReportCodecError("resilience_report_noncanonical")
    return report


def _reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ResilienceReportCodecError("resilience_report_duplicate_key")
        if key in _FORBIDDEN_SCORE_KEYS:
            raise ResilienceReportCodecError("resilience_report_forbidden_field")
        out[key] = value
    return out


def _report_to_document(report: ResilienceReport) -> dict[str, Any]:
    return {
        "schema_version": report.schema_version,
        "policy_id": report.policy_id,
        "run_id": report.run_id,
        "config_fingerprint": report.config_fingerprint,
        "finalized_through": report.finalized_through,
        "capture_through": report.capture_through,
        "capture_status": report.capture_status,
        "shock_status": report.shock_status,
        "non_applied_counts": {
            key: report.non_applied_counts[key]
            for key in sorted(report.non_applied_counts)
        },
        "schedule": _jsonable(report.schedule),
        "episodes": _jsonable(report.episodes),
    }


def _jsonable(value: object) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _document_to_report(document: Mapping[str, Any]) -> ResilienceReport:
    return ResilienceReport(
        schema_version=document["schema_version"],
        policy_id=document["policy_id"],
        run_id=document["run_id"],
        config_fingerprint=document["config_fingerprint"],
        finalized_through=document["finalized_through"],
        capture_through=document["capture_through"],
        capture_status=document["capture_status"],
        shock_status=document["shock_status"],
        non_applied_counts=dict(document["non_applied_counts"]),
        schedule=tuple(_jsonable(row) for row in document["schedule"]),
        episodes=tuple(_jsonable(ep) for ep in document["episodes"]),
    )


def _validate_document(document: Mapping[str, Any]) -> None:
    _exact_keys(document, _ROOT_KEYS, "root")
    if document["schema_version"] != RESILIENCE_REPORT_SCHEMA_VERSION:
        raise ResilienceReportCodecError("resilience_report_schema")
    if document["policy_id"] != RESILIENCE_POLICY_ID:
        raise ResilienceReportCodecError("resilience_report_policy")
    _require_str(document["run_id"])
    _require_str(document["config_fingerprint"])
    _require_nonneg_int(document["finalized_through"])
    _require_nonneg_int(document["capture_through"])
    if document["capture_through"] > document["finalized_through"]:
        raise ResilienceReportCodecError("resilience_report_horizon")
    if document["capture_status"] not in _CAPTURE_STATUS:
        raise ResilienceReportCodecError("resilience_report_capture_status")
    if document["shock_status"] not in _SHOCK_STATUS:
        raise ResilienceReportCodecError("resilience_report_shock_status")
    counts = document["non_applied_counts"]
    if type(counts) is not dict:
        raise ResilienceReportCodecError("resilience_report_counts")
    for key, value in counts.items():
        _require_str(key)
        _require_nonneg_int(value)
    schedule = document["schedule"]
    if type(schedule) is not list:
        raise ResilienceReportCodecError("resilience_report_schedule")
    if len(schedule) > MAX_RESILIENCE_APPLIED_SHOCK_TICKS:
        raise ResilienceReportCodecError("resilience_report_schedule_overflow")
    prev_key: tuple[int, str] | None = None
    for row in schedule:
        _validate_schedule_row(row)
        key = (row["tick"], row["rule_id"])
        if prev_key is not None and key < prev_key:
            raise ResilienceReportCodecError("resilience_report_schedule_order")
        prev_key = key
    episodes = document["episodes"]
    if type(episodes) is not list:
        raise ResilienceReportCodecError("resilience_report_episodes")
    if len(episodes) > MAX_RESILIENCE_APPLIED_SHOCK_TICKS:
        raise ResilienceReportCodecError("resilience_report_episode_overflow")
    if document["shock_status"] == "observed" and not episodes:
        raise ResilienceReportCodecError("resilience_report_shock_status")
    if document["shock_status"] == "no_shock" and episodes:
        raise ResilienceReportCodecError("resilience_report_shock_status")
    prev_tick = -1
    for episode in episodes:
        _validate_episode(episode)
        tick = episode["shock_tick"]
        if tick <= prev_tick:
            raise ResilienceReportCodecError("resilience_report_episode_order")
        prev_tick = tick


def _validate_schedule_row(row: object) -> None:
    if type(row) is not dict:
        raise ResilienceReportCodecError("resilience_report_schedule")
    _exact_keys(row, _SCHEDULE_KEYS, "schedule")
    _require_nonneg_int(row["tick"])
    _require_str(row["rule_id"])
    if row["status"] not in _SCHEDULE_STATUS:
        raise ResilienceReportCodecError("resilience_report_schedule_status")
    if row["status"] in {"applied", "not_applied"}:
        _require_str(row["outcome"])
        _require_str(row["receipt_event_id"])
    else:
        if row["outcome"] is not None or row["receipt_event_id"] is not None:
            raise ResilienceReportCodecError("resilience_report_schedule_ref")


def _validate_episode(episode: object) -> None:
    if type(episode) is not dict:
        raise ResilienceReportCodecError("resilience_report_episode")
    _exact_keys(episode, _EPISODE_KEYS, "episode")
    _require_nonneg_int(episode["shock_tick"])
    receipts = episode["receipts"]
    if type(receipts) is not list or not receipts:
        raise ResilienceReportCodecError("resilience_report_receipts")
    for receipt in receipts:
        _validate_receipt(receipt)
        if receipt["tick"] != episode["shock_tick"]:
            raise ResilienceReportCodecError("resilience_report_receipt_tick")
        if receipt["outcome"] != "applied":
            raise ResilienceReportCodecError("resilience_report_receipt_outcome")
    immediate = episode["immediate_state"]
    _validate_immediate(immediate, shock_tick=episode["shock_tick"])
    windows = episode["windows"]
    if type(windows) is not list or len(windows) != 9:
        raise ResilienceReportCodecError("resilience_report_windows")
    expected_indexes = [-1, *range(8)]
    for expected, window in zip(expected_indexes, windows, strict=True):
        _validate_window_axis(window, expected_index=expected)
    panels = episode["panels"]
    if type(panels) is not list or len(panels) != 10:
        raise ResilienceReportCodecError("resilience_report_panels")
    for name, panel in zip(RESILIENCE_DIMENSION_ORDER, panels, strict=True):
        _validate_panel(panel, expected_dimension=name)


def _validate_receipt(receipt: object) -> None:
    if type(receipt) is not dict:
        raise ResilienceReportCodecError("resilience_report_receipt")
    _exact_keys(receipt, _RECEIPT_KEYS, "receipt")
    _require_nonneg_int(receipt["tick"])
    _require_nonneg_int(receipt["sequence"])
    for key in ("event_id", "kind", "origin", "outcome"):
        _require_str(receipt[key])


def _validate_window_axis(window: object, *, expected_index: int) -> None:
    if type(window) is not dict:
        raise ResilienceReportCodecError("resilience_report_window")
    _exact_keys(window, _WINDOW_AXIS_KEYS, "window")
    if window["window_index"] != expected_index:
        raise ResilienceReportCodecError("resilience_report_window_index")
    if window["status"] not in _COVERAGE:
        raise ResilienceReportCodecError("resilience_report_coverage")
    if window["reason"] is not None:
        _require_str(window["reason"])
    _require_nonneg_int(window["expected_ticks"])
    _require_nonneg_int(window["observed_ticks"])


def _validate_panel(panel: object, *, expected_dimension: str) -> None:
    if type(panel) is not dict:
        raise ResilienceReportCodecError("resilience_report_panel")
    _exact_keys(panel, _PANEL_KEYS, "panel")
    if panel["dimension"] != expected_dimension:
        raise ResilienceReportCodecError("resilience_report_dimension")
    windows = panel["windows"]
    if type(windows) is not list or len(windows) != 9:
        raise ResilienceReportCodecError("resilience_report_panel_windows")
    expected_indexes = [-1, *range(8)]
    for expected, cell in zip(expected_indexes, windows, strict=True):
        _validate_cell(cell, expected_index=expected)


def _validate_immediate(immediate: object, *, shock_tick: int) -> None:
    if type(immediate) is not dict:
        raise ResilienceReportCodecError("resilience_report_immediate")
    _exact_keys(immediate, _IMMEDIATE_ROOT_KEYS, "immediate")
    if immediate["pre_boundary_tick"] != shock_tick:
        raise ResilienceReportCodecError("resilience_report_immediate_boundary")
    if immediate["boundary_tick"] != shock_tick + 1:
        raise ResilienceReportCodecError("resilience_report_immediate_boundary")
    panels = immediate["panels"]
    if type(panels) is not list or len(panels) != len(IMMEDIATE_STATE_DIMENSIONS):
        raise ResilienceReportCodecError("resilience_report_immediate_panels")
    for dimension, panel in zip(IMMEDIATE_STATE_DIMENSIONS, panels, strict=True):
        if type(panel) is not dict:
            raise ResilienceReportCodecError("resilience_report_immediate_panel")
        _exact_keys(panel, _IMMEDIATE_PANEL_KEYS, "immediate_panel")
        if panel["dimension"] != dimension.value:
            raise ResilienceReportCodecError("resilience_report_dimension")
        if panel["status"] not in _COVERAGE:
            raise ResilienceReportCodecError("resilience_report_coverage")
        if panel["reason"] is not None:
            _require_str(panel["reason"])
        _validate_owner_coverage(panel["owner_coverage"])
        _validate_measures(panel["measures"])


def _validate_cell(cell: object, *, expected_index: int) -> None:
    if type(cell) is not dict:
        raise ResilienceReportCodecError("resilience_report_cell")
    _exact_keys(cell, _CELL_KEYS, "cell")
    if cell["window_index"] != expected_index:
        raise ResilienceReportCodecError("resilience_report_window_index")
    if cell["status"] not in _COVERAGE:
        raise ResilienceReportCodecError("resilience_report_coverage")
    if cell["reason"] is not None:
        _require_str(cell["reason"])
    _require_nonneg_int(cell["expected_ticks"])
    _require_nonneg_int(cell["observed_ticks"])
    _validate_owner_coverage(cell["owner_coverage"])
    _validate_measures(cell["measures"])


def _validate_owner_coverage(coverage: object) -> None:
    if coverage is None:
        return
    if type(coverage) is not dict:
        raise ResilienceReportCodecError("resilience_report_owner_coverage")
    _exact_keys(coverage, _OWNER_KEYS, "owner_coverage")
    eligible = coverage["eligible_owners"]
    observed = coverage["observed_owners"]
    _require_nonneg_int(eligible)
    _require_nonneg_int(observed)
    if observed > eligible:
        raise ResilienceReportCodecError("resilience_report_owner_coverage")


def _validate_measures(measures: object) -> None:
    if type(measures) is not list:
        raise ResilienceReportCodecError("resilience_report_measures")
    seen: set[tuple[str, str | None, str | None]] = set()
    for measure in measures:
        if type(measure) is not dict:
            raise ResilienceReportCodecError("resilience_report_measure")
        _exact_keys(measure, _MEASURE_KEYS, "measure")
        _require_str(measure["metric"])
        _require_str(measure["unit"])
        scope = measure["scope"]
        scope_kind = None
        scope_key = None
        if scope is not None:
            if type(scope) is not dict:
                raise ResilienceReportCodecError("resilience_report_scope")
            _exact_keys(scope, _SCOPE_KEYS, "scope")
            _require_str(scope["kind"])
            _require_str(scope["key"])
            scope_kind = scope["kind"]
            scope_key = scope["key"]
        key = (measure["metric"], scope_kind, scope_key)
        if key in seen:
            raise ResilienceReportCodecError("resilience_report_duplicate_measure")
        seen.add(key)
        for field in (
            "value",
            "numerator",
            "denominator",
            "delta_from_baseline",
        ):
            raw = measure[field]
            if raw is None:
                continue
            if isinstance(raw, bool) or type(raw) is not int:
                raise ResilienceReportCodecError("resilience_report_measure_int")
        if measure["reason"] is not None:
            _require_str(measure["reason"])
        if measure["delta_reason"] is not None:
            _require_str(measure["delta_reason"])


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    keys = frozenset(value)
    if keys != expected:
        overlap = keys & _FORBIDDEN_SCORE_KEYS
        if overlap:
            raise ResilienceReportCodecError("resilience_report_forbidden_field")
        raise ResilienceReportCodecError(f"resilience_report_keys_{label}")


def _require_str(value: object) -> None:
    if type(value) is not str or not value:
        raise ResilienceReportCodecError("resilience_report_string")


def _require_nonneg_int(value: object) -> None:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ResilienceReportCodecError("resilience_report_integer")
