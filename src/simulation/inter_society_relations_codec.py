# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Canonical codec for ``inter-society-relations-snapshot-v1``."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict
from typing import Final

from simulation.inter_society_relations_models import (
    INTER_SOCIETY_RELATIONS_PUBLICATION_PREFIX,
    INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY,
    INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION,
    ISR_MAX_BYTES,
    InterSocietyRelationsArtifactError,
    InterSocietyRelationsComparisonRecord,
    InterSocietyRelationsDomainPanelRecord,
    InterSocietyRelationsPairRecord,
    InterSocietyRelationsSeriesPointRecord,
    InterSocietyRelationsSnapshot,
    InterSocietyRelationsSummaryRecord,
)

__all__ = [
    "canonical_inter_society_relations_json",
    "canonical_inter_society_relations_payload",
    "decode_inter_society_relations_snapshot",
    "encode_inter_society_relations_snapshot",
    "finalize_inter_society_relations_snapshot",
    "inter_society_relations_publication_id",
    "inter_society_relations_snapshot_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.inter_society_relations.codec"
)
_PUBLICATION_HEX_CHARS: Final[int] = 32


def canonical_inter_society_relations_payload(
    snapshot: InterSocietyRelationsSnapshot,
) -> dict[str, object]:
    if type(snapshot) is not InterSocietyRelationsSnapshot:
        raise TypeError("snapshot must be InterSocietyRelationsSnapshot")
    return asdict(snapshot)


def canonical_inter_society_relations_json(
    snapshot: InterSocietyRelationsSnapshot,
) -> str:
    return json.dumps(
        canonical_inter_society_relations_payload(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def inter_society_relations_snapshot_digest(
    snapshot: InterSocietyRelationsSnapshot,
) -> str:
    payload = canonical_inter_society_relations_payload(snapshot)
    payload["digest"] = ""
    payload["publication_id"] = ""
    summary = dict(payload["summary"])  # type: ignore[arg-type]
    summary["digest"] = ""
    summary["publication_id"] = ""
    payload["summary"] = summary
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def inter_society_relations_publication_id(*, run_id: str, digest: str) -> str:
    material = f"isr-pub|{run_id}|{digest}"
    hex_digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return (
        f"{INTER_SOCIETY_RELATIONS_PUBLICATION_PREFIX}"
        f"{hex_digest[:_PUBLICATION_HEX_CHARS]}"
    )


def finalize_inter_society_relations_snapshot(
    snapshot: InterSocietyRelationsSnapshot,
) -> InterSocietyRelationsSnapshot:
    digest = inter_society_relations_snapshot_digest(snapshot)
    publication_id = inter_society_relations_publication_id(
        run_id=snapshot.summary.run_id, digest=digest
    )
    summary = InterSocietyRelationsSummaryRecord(
        run_id=snapshot.summary.run_id,
        publication_id=publication_id,
        digest=digest,
        schema_version=INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION,
        policy_version=INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY,
        pair_count=len(snapshot.pairs),
        window_count=len({point.window_index for point in snapshot.series_points}),
        series_point_count=len(snapshot.series_points),
        comparison_count=len(snapshot.comparisons),
        coverage=snapshot.summary.coverage,
    )
    finalized = InterSocietyRelationsSnapshot(
        summary=summary,
        pairs=snapshot.pairs,
        series_points=snapshot.series_points,
        comparisons=snapshot.comparisons,
        digest=digest,
        publication_id=publication_id,
    )
    encoded = encode_inter_society_relations_snapshot(finalized)
    _LOG.debug(
        "inter_society_relations_finalize bytes=%s pair_count=%s",
        len(encoded),
        finalized.summary.pair_count,
    )
    return finalized


def encode_inter_society_relations_snapshot(
    snapshot: InterSocietyRelationsSnapshot,
) -> bytes:
    text = canonical_inter_society_relations_json(snapshot) + "\n"
    payload = text.encode("utf-8")
    if len(payload) > ISR_MAX_BYTES:
        _LOG.error(
            "inter_society_relations_encode_failed "
            "reason_code=inter_society_relations_size_limit bytes=%s",
            len(payload),
        )
        raise InterSocietyRelationsArtifactError("inter_society_relations_size_limit")
    return payload


def _panel(raw: object) -> InterSocietyRelationsDomainPanelRecord:
    if not isinstance(raw, dict):
        raise InterSocietyRelationsArtifactError(
            "inter_society_relations_store_corrupt"
        )
    return InterSocietyRelationsDomainPanelRecord(
        domain=raw["domain"],  # type: ignore[arg-type]
        event_count=raw["event_count"],  # type: ignore[arg-type]
        availability=raw["availability"],  # type: ignore[arg-type]
        coverage_observed=raw["coverage_observed"],  # type: ignore[arg-type]
        coverage_expected=raw["coverage_expected"],  # type: ignore[arg-type]
        values=dict(raw.get("values") or {}),  # type: ignore[arg-type]
    )


def decode_inter_society_relations_snapshot(
    payload: bytes | str | dict[str, object],
) -> InterSocietyRelationsSnapshot:
    try:
        if isinstance(payload, dict):
            data = payload
        else:
            text = (
                payload.decode("utf-8")
                if isinstance(payload, (bytes, bytearray))
                else str(payload)
            )
            data = json.loads(text)
        if not isinstance(data, dict):
            raise TypeError("payload")
        summary_raw = data["summary"]
        pairs = tuple(
            InterSocietyRelationsPairRecord(
                pair_id=item["pair_id"],
                society_a=item["society_a"],
                society_b=item["society_b"],
                window_tick=item["window_tick"],
                status=item["status"],
                overlap_member_count=item["overlap_member_count"],
                panels=tuple(_panel(panel) for panel in item["panels"]),
            )
            for item in data.get("pairs") or ()
        )
        series_points = tuple(
            InterSocietyRelationsSeriesPointRecord(
                pair_id=item["pair_id"],
                window_index=item["window_index"],
                window_start_tick=item["window_start_tick"],
                window_end_tick=item["window_end_tick"],
                panels=tuple(_panel(panel) for panel in item["panels"]),
            )
            for item in data.get("series_points") or ()
        )
        comparisons = tuple(
            InterSocietyRelationsComparisonRecord(
                left_pair_id=item["left_pair_id"],
                right_pair_id=item["right_pair_id"],
                left_window_tick=item["left_window_tick"],
                right_window_tick=item["right_window_tick"],
                domain_deltas=tuple(
                    (row[0], int(row[1]), row[2], row[3])
                    for row in item.get("domain_deltas") or ()
                ),
            )
            for item in data.get("comparisons") or ()
        )
        summary = InterSocietyRelationsSummaryRecord(
            run_id=summary_raw["run_id"],
            publication_id=summary_raw.get("publication_id") or "",
            digest=summary_raw.get("digest") or "",
            schema_version=summary_raw["schema_version"],
            policy_version=summary_raw["policy_version"],
            pair_count=summary_raw["pair_count"],
            window_count=summary_raw["window_count"],
            series_point_count=summary_raw["series_point_count"],
            comparison_count=summary_raw["comparison_count"],
            coverage=summary_raw.get("coverage") or "not_applicable",
        )
        snapshot = InterSocietyRelationsSnapshot(
            summary=summary,
            pairs=pairs,
            series_points=series_points,
            comparisons=comparisons,
            digest=data.get("digest") or "",
            publication_id=data.get("publication_id") or "",
            schema_version=data.get("schema_version")
            or INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION,
            policy_version=data.get("policy_version")
            or INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY,
        )
    except InterSocietyRelationsArtifactError:
        raise
    except Exception as exc:
        _LOG.error(
            "inter_society_relations_decode_failed "
            "reason_code=inter_society_relations_store_corrupt"
        )
        raise InterSocietyRelationsArtifactError(
            "inter_society_relations_store_corrupt"
        ) from exc
    _LOG.debug(
        "inter_society_relations_decode pair_count=%s", snapshot.summary.pair_count
    )
    return snapshot
