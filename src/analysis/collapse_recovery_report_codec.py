"""Strict canonical codec for collapse-recovery-report-v1."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Final

from analysis.collapse_recovery_indicators import (
    COLLAPSE_AXIS_ORDER,
    COLLAPSE_POLICY_ID,
    COLLAPSE_WINDOW_TICKS,
)
from analysis.collapse_recovery_report import (
    COLLAPSE_RECOVERY_REPORT_SCHEMA,
    CollapseRecoveryReport,
)

__all__ = [
    "CollapseRecoveryReportCodecError",
    "decode_collapse_recovery_report",
    "encode_collapse_recovery_report",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.collapse_recovery_report_codec"
)

_MAX_BYTES: Final[int] = 8 * 1024 * 1024
_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "civilization_collapsed",
        "CivilizationCollapsed",
        "collapse_score",
        "composite_score",
        "universal_score",
        "score",
        "ranking",
        "recommendation",
        "authority",
    }
)

_ROOT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "policy_version",
        "run_id",
        "config_fingerprint",
        "window_ticks",
        "committed_through",
        "captured_through",
        "capture_reason",
        "windows",
        "episodes",
        "lineage",
    }
)
_WINDOW_KEYS: Final[frozenset[str]] = frozenset(
    {"scope", "start_tick", "end_tick", "complete", "axes", "technique"}
)
_AXIS_KEYS: Final[frozenset[str]] = frozenset(
    {
        "axis",
        "group",
        "coverage",
        "coverage_reason",
        "value",
        "denominator",
        "rate_milli",
        "comparison",
        "baseline_window_end",
        "supporting",
    }
)
_EPISODE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "scope",
        "onset_end",
        "confirmed_end",
        "baseline_end",
        "disposition",
        "last_assessed_end",
        "contributing_axes",
        "censor_reason",
    }
)
_LINEAGE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "windows",
        "nodes",
        "edges",
        "boundaries",
        "institutions",
        "techniques",
        "split_aggregates",
        "branch_losses",
        "episode_links",
    }
)
_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {"ongoing_at_end", "recovered", "censored"}
)
_COMPARISONS: Final[frozenset[str]] = frozenset(
    {"stressed", "not_stressed", "not_comparable"}
)
_COVERAGES: Final[frozenset[str]] = frozenset(
    {"complete", "unavailable", "partial", "censored"}
)
_EDGE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "continuation",
        "split_successor",
        "merge_successor",
        "ambiguous_transition",
    }
)


class CollapseRecoveryReportCodecError(ValueError):
    """Closed codec failure with a stable reason code."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def _reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise CollapseRecoveryReportCodecError("collapse_report_duplicate_key")
        if key in _FORBIDDEN_KEYS:
            raise CollapseRecoveryReportCodecError("collapse_report_forbidden_field")
        out[key] = value
    return out


def _require_keys(document: Mapping[str, Any], keys: frozenset[str], code: str) -> None:
    actual = frozenset(document)
    if actual != keys:
        raise CollapseRecoveryReportCodecError(code)


def _exact_int(value: object, code: str) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise CollapseRecoveryReportCodecError(code)
    return value


def _exact_bool(value: object, code: str) -> bool:
    if type(value) is not bool:
        raise CollapseRecoveryReportCodecError(code)
    return value


def _optional_int(value: object, code: str) -> int | None:
    if value is None:
        return None
    return _exact_int(value, code)


def _optional_str(value: object, code: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise CollapseRecoveryReportCodecError(code)
    return value


def _jsonable(value: object) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _report_to_document(report: CollapseRecoveryReport) -> dict[str, Any]:
    return {
        "schema_version": report.schema_version,
        "policy_version": report.policy_version,
        "run_id": report.run_id,
        "config_fingerprint": report.config_fingerprint,
        "window_ticks": report.window_ticks,
        "committed_through": report.committed_through,
        "captured_through": report.captured_through,
        "capture_reason": report.capture_reason,
        "windows": _jsonable(report.windows),
        "episodes": _jsonable(report.episodes),
        "lineage": _jsonable(report.lineage),
    }


def _validate_axis(axis: Mapping[str, Any]) -> None:
    _require_keys(axis, _AXIS_KEYS, "collapse_report_axis_keys")
    if axis["axis"] not in COLLAPSE_AXIS_ORDER:
        raise CollapseRecoveryReportCodecError("collapse_report_axis_id")
    if axis["comparison"] not in _COMPARISONS:
        raise CollapseRecoveryReportCodecError("collapse_report_comparison")
    if axis["coverage"] not in _COVERAGES:
        raise CollapseRecoveryReportCodecError("collapse_report_coverage")
    _optional_int(axis["value"], "collapse_report_int")
    _optional_int(axis["denominator"], "collapse_report_int")
    _optional_int(axis["rate_milli"], "collapse_report_int")
    _optional_int(axis["baseline_window_end"], "collapse_report_int")
    if type(axis["supporting"]) is not dict:
        raise CollapseRecoveryReportCodecError("collapse_report_supporting")


def _validate_window(window: Mapping[str, Any]) -> None:
    _require_keys(window, _WINDOW_KEYS, "collapse_report_window_keys")
    if type(window["scope"]) is not str or not window["scope"]:
        raise CollapseRecoveryReportCodecError("collapse_report_scope")
    start = _exact_int(window["start_tick"], "collapse_report_int")
    end = _exact_int(window["end_tick"], "collapse_report_int")
    if end <= start:
        raise CollapseRecoveryReportCodecError("collapse_report_window_bounds")
    _exact_bool(window["complete"], "collapse_report_bool")
    axes = window["axes"]
    if type(axes) is not list or len(axes) != 8:
        raise CollapseRecoveryReportCodecError("collapse_report_axes")
    order = [axis["axis"] for axis in axes]
    if order != list(COLLAPSE_AXIS_ORDER):
        raise CollapseRecoveryReportCodecError("collapse_report_axis_order")
    for axis in axes:
        if type(axis) is not dict:
            raise CollapseRecoveryReportCodecError("collapse_report_axis")
        _validate_axis(axis)
        if (
            axis["comparison"] in {"stressed", "not_stressed"}
            and axis["coverage"] != "complete"
        ):
            raise CollapseRecoveryReportCodecError("collapse_report_vote_coverage")
    technique = window["technique"]
    if type(technique) is not dict:
        raise CollapseRecoveryReportCodecError("collapse_report_technique")
    expected = {
        "retained",
        "observed_loss",
        "reobserved",
        "not_observed",
        "unassessable",
    }
    if frozenset(technique) != expected:
        raise CollapseRecoveryReportCodecError("collapse_report_technique_keys")
    for value in technique.values():
        _exact_int(value, "collapse_report_int")


def _validate_episode(episode: Mapping[str, Any]) -> None:
    _require_keys(episode, _EPISODE_KEYS, "collapse_report_episode_keys")
    if type(episode["scope"]) is not str:
        raise CollapseRecoveryReportCodecError("collapse_report_scope")
    onset = _exact_int(episode["onset_end"], "collapse_report_int")
    confirmed = _exact_int(episode["confirmed_end"], "collapse_report_int")
    last = _exact_int(episode["last_assessed_end"], "collapse_report_int")
    _exact_int(episode["baseline_end"], "collapse_report_int")
    if onset > confirmed or confirmed > last:
        raise CollapseRecoveryReportCodecError("collapse_report_episode_bounds")
    if episode["disposition"] not in _DISPOSITIONS:
        raise CollapseRecoveryReportCodecError("collapse_report_disposition")
    axes = episode["contributing_axes"]
    if type(axes) is not list or not all(type(item) is str for item in axes):
        raise CollapseRecoveryReportCodecError("collapse_report_contributing")
    _optional_str(episode["censor_reason"], "collapse_report_censor")


def _validate_lineage(lineage: Mapping[str, Any]) -> None:
    _require_keys(lineage, _LINEAGE_KEYS, "collapse_report_lineage_keys")
    for name in _LINEAGE_KEYS:
        if type(lineage[name]) is not list:
            raise CollapseRecoveryReportCodecError("collapse_report_lineage_list")
    node_ids = set()
    for node in lineage["nodes"]:
        if type(node) is not dict:
            raise CollapseRecoveryReportCodecError("collapse_report_node")
        node_id = node.get("node_id")
        if type(node_id) is not str or not node_id.startswith("cr-node-"):
            raise CollapseRecoveryReportCodecError("collapse_report_node_id")
        if node_id in node_ids:
            raise CollapseRecoveryReportCodecError("collapse_report_duplicate_node")
        node_ids.add(node_id)
        _exact_int(node.get("window_start"), "collapse_report_int")
        _exact_int(node.get("window_end"), "collapse_report_int")
    split_children: dict[str, int] = {}
    for edge in lineage["edges"]:
        if type(edge) is not dict:
            raise CollapseRecoveryReportCodecError("collapse_report_edge")
        kind = edge.get("kind")
        if kind not in _EDGE_KINDS or kind == "ambiguous_transition":
            raise CollapseRecoveryReportCodecError("collapse_report_edge_kind")
        from_id = edge.get("from_id")
        to_id = edge.get("to_id")
        if from_id not in node_ids or to_id not in node_ids:
            raise CollapseRecoveryReportCodecError("collapse_report_dangling_edge")
        from_end = _exact_int(edge.get("from_window_end"), "collapse_report_int")
        to_start = _exact_int(edge.get("to_window_start"), "collapse_report_int")
        if to_start < from_end:
            raise CollapseRecoveryReportCodecError("collapse_report_edge_order")
        if kind == "split_successor":
            split_children[from_id] = split_children.get(from_id, 0) + 1
    for count in split_children.values():
        if count < 2:
            raise CollapseRecoveryReportCodecError("collapse_report_split_arity")
    for loss in lineage["branch_losses"]:
        if type(loss) is not dict:
            raise CollapseRecoveryReportCodecError("collapse_report_branch_loss")
        if loss.get("split_successor_id") not in node_ids:
            raise CollapseRecoveryReportCodecError("collapse_report_branch_loss_ref")
        if loss.get("confirmation_node_id") not in node_ids:
            raise CollapseRecoveryReportCodecError("collapse_report_branch_loss_ref")


def _validate_document(document: Mapping[str, Any]) -> None:
    _require_keys(document, _ROOT_KEYS, "collapse_report_root_keys")
    if document["schema_version"] != COLLAPSE_RECOVERY_REPORT_SCHEMA:
        raise CollapseRecoveryReportCodecError("collapse_report_schema")
    if document["policy_version"] != COLLAPSE_POLICY_ID:
        raise CollapseRecoveryReportCodecError("collapse_report_policy")
    if (
        _exact_int(document["window_ticks"], "collapse_report_int")
        != COLLAPSE_WINDOW_TICKS
    ):
        raise CollapseRecoveryReportCodecError("collapse_report_window_ticks")
    committed = _exact_int(document["committed_through"], "collapse_report_int")
    captured = _exact_int(document["captured_through"], "collapse_report_int")
    if captured > committed:
        raise CollapseRecoveryReportCodecError("collapse_report_capture_horizon")
    _optional_str(document["capture_reason"], "collapse_report_reason")
    if (
        type(document["run_id"]) is not str
        or type(document["config_fingerprint"]) is not str
    ):
        raise CollapseRecoveryReportCodecError("collapse_report_ids")
    windows = document["windows"]
    episodes = document["episodes"]
    lineage = document["lineage"]
    if (
        type(windows) is not list
        or type(episodes) is not list
        or type(lineage) is not dict
    ):
        raise CollapseRecoveryReportCodecError("collapse_report_sections")
    for window in windows:
        if type(window) is not dict:
            raise CollapseRecoveryReportCodecError("collapse_report_window")
        _validate_window(window)
    for episode in episodes:
        if type(episode) is not dict:
            raise CollapseRecoveryReportCodecError("collapse_report_episode")
        _validate_episode(episode)
    _validate_lineage(lineage)


def _document_to_report(document: Mapping[str, Any]) -> CollapseRecoveryReport:
    return CollapseRecoveryReport(
        schema_version=document["schema_version"],
        policy_version=document["policy_version"],
        run_id=document["run_id"],
        config_fingerprint=document["config_fingerprint"],
        window_ticks=document["window_ticks"],
        committed_through=document["committed_through"],
        captured_through=document["captured_through"],
        capture_reason=document["capture_reason"],
        windows=tuple(document["windows"]),
        episodes=tuple(document["episodes"]),
        lineage=document["lineage"],
    )


def encode_collapse_recovery_report(report: CollapseRecoveryReport) -> bytes:
    """Emit UTF-8 canonical JSON without a trailing newline."""

    if type(report) is not CollapseRecoveryReport:
        raise CollapseRecoveryReportCodecError("collapse_report_invalid")
    if report.schema_version != COLLAPSE_RECOVERY_REPORT_SCHEMA:
        raise CollapseRecoveryReportCodecError("collapse_report_schema")
    if report.policy_version != COLLAPSE_POLICY_ID:
        raise CollapseRecoveryReportCodecError("collapse_report_policy")
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
        raise CollapseRecoveryReportCodecError("collapse_report_encode") from exc
    if len(payload) > _MAX_BYTES:
        raise CollapseRecoveryReportCodecError("collapse_report_too_large")
    _LOG.debug("collapse_report_encoded bytes=%s", len(payload))
    return payload


def decode_collapse_recovery_report(payload: bytes) -> CollapseRecoveryReport:
    """Decode and re-encode for canonical byte equality."""

    if type(payload) is not bytes:
        raise CollapseRecoveryReportCodecError("collapse_report_invalid_payload")
    if len(payload) > _MAX_BYTES:
        raise CollapseRecoveryReportCodecError("collapse_report_too_large")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CollapseRecoveryReportCodecError("collapse_report_encoding") from exc
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicates)
        raw = decoder.decode(text)
    except CollapseRecoveryReportCodecError:
        raise
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise CollapseRecoveryReportCodecError("collapse_report_invalid_json") from exc
    if type(raw) is not dict:
        raise CollapseRecoveryReportCodecError("collapse_report_invalid_object")
    _validate_document(raw)
    report = _document_to_report(raw)
    encoded = encode_collapse_recovery_report(report)
    if encoded != payload:
        raise CollapseRecoveryReportCodecError("collapse_report_noncanonical")
    return report
