"""Canonical codec for ``trade-networks-snapshot-v1``."""

# ruff: noqa: E501
# mypy: disable-error-code="type-arg,no-untyped-def,return-value,misc,assignment,arg-type,call-overload,attr-defined"

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict
from typing import Final

from simulation.trade_networks_models import (
    TRADE_NETWORKS_SNAPSHOT_VERSION,
    CrossSocietyTradeRecord,
    TradeCorridorRecord,
    TradeDependenceRecord,
    TradeFlowCountRecord,
    TradeFlowRecord,
    TradeLocationRecord,
    TradeNetworkRecord,
    TradeNetworksArtifactError,
    TradeNetworksSnapshot,
    TradeNetworksSummaryRecord,
)

__all__ = [
    "canonical_trade_networks_json",
    "canonical_trade_networks_payload",
    "compute_trade_networks_publication_id",
    "decode_trade_networks_snapshot",
    "encode_trade_networks_snapshot",
    "finalize_trade_networks_snapshot",
    "trade_networks_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.trade_networks.codec")
_PUBLICATION_PREFIX: Final[str] = "trd-pub-"
_PUBLICATION_HEX_CHARS: Final[int] = 32
_MAX_BYTES: Final[int] = 8_388_608

_SNAPSHOT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "run_id",
        "schema_version",
        "policy_version",
        "summary",
        "corridors",
        "flows",
        "locations",
        "dependence",
        "cross_society",
        "networks",
        "digest",
        "publication_id",
    }
)


def canonical_trade_networks_payload(
    snapshot: TradeNetworksSnapshot,
) -> dict[str, object]:
    if type(snapshot) is not TradeNetworksSnapshot:
        raise TypeError("snapshot must be TradeNetworksSnapshot")
    return asdict(snapshot)


def canonical_trade_networks_json(snapshot: TradeNetworksSnapshot) -> str:
    return json.dumps(
        canonical_trade_networks_payload(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def trade_networks_digest(snapshot: TradeNetworksSnapshot) -> str:
    payload = canonical_trade_networks_payload(snapshot)
    payload["digest"] = ""
    payload["publication_id"] = ""
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def compute_trade_networks_publication_id(*, run_id: str, digest: str) -> str:
    material = f"trade-networks-pub|{run_id}|{digest}"
    hex_digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{_PUBLICATION_PREFIX}{hex_digest[:_PUBLICATION_HEX_CHARS]}"


def finalize_trade_networks_snapshot(
    snapshot: TradeNetworksSnapshot,
) -> TradeNetworksSnapshot:
    if type(snapshot) is not TradeNetworksSnapshot:
        raise TypeError("snapshot must be TradeNetworksSnapshot")
    digest = trade_networks_digest(snapshot)
    publication_id = compute_trade_networks_publication_id(
        run_id=snapshot.run_id, digest=digest
    )
    return TradeNetworksSnapshot(
        run_id=snapshot.run_id,
        schema_version=snapshot.schema_version,
        policy_version=snapshot.policy_version,
        summary=snapshot.summary,
        corridors=snapshot.corridors,
        flows=snapshot.flows,
        locations=snapshot.locations,
        dependence=snapshot.dependence,
        cross_society=snapshot.cross_society,
        networks=snapshot.networks,
        digest=digest,
        publication_id=publication_id,
    )


def encode_trade_networks_snapshot(snapshot: TradeNetworksSnapshot) -> bytes:
    payload = (canonical_trade_networks_json(snapshot) + "\n").encode("utf-8")
    if len(payload) > _MAX_BYTES:
        raise TradeNetworksArtifactError("trade_networks_artifact_size_limit")
    _LOG.debug("trade_networks_encode bytes=%s", len(payload))
    return payload


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TradeNetworksArtifactError("trade_networks_artifact_duplicate_key")
        result[key] = value
    return result


def _expect_keys(mapping: object, keys: frozenset[str], code: str) -> dict:
    if type(mapping) is not dict or frozenset(mapping) != keys:
        raise TradeNetworksArtifactError(code)
    return mapping


def _flow_counts(value: object) -> tuple[TradeFlowCountRecord, ...]:
    if type(value) is not list:
        raise TradeNetworksArtifactError("trade_networks_artifact_invalid_rows")
    records: list[TradeFlowCountRecord] = []
    for item in value:
        row = _expect_keys(
            item,
            frozenset({"flow_class", "count"}),
            "trade_networks_artifact_invalid_rows",
        )
        records.append(
            TradeFlowCountRecord(flow_class=row["flow_class"], count=row["count"])
        )
    return tuple(records)


def _record(mapping: object, keys: frozenset[str], builder) -> object:
    row = _expect_keys(mapping, keys, "trade_networks_artifact_invalid_rows")
    if "flow_counts" in keys or any(key.endswith("_ids") for key in keys):
        row = dict(row)
        if "flow_counts" in keys:
            row["flow_counts"] = _flow_counts(row["flow_counts"])
        for key in tuple(row):
            if key.endswith("_ids"):
                value = row[key]
                if type(value) is not list:
                    raise TradeNetworksArtifactError(
                        "trade_networks_artifact_invalid_rows"
                    )
                row[key] = tuple(value)
    return builder(**row)


def _summary(value: object) -> TradeNetworksSummaryRecord:
    keys = frozenset(TradeNetworksSummaryRecord.__dataclass_fields__)
    return _record(value, keys, TradeNetworksSummaryRecord)


def _build(snapshot: dict) -> TradeNetworksSnapshot:
    return TradeNetworksSnapshot(
        run_id=snapshot["run_id"],
        schema_version=snapshot["schema_version"],
        policy_version=snapshot["policy_version"],
        summary=_summary(snapshot["summary"]),
        corridors=tuple(
            _record(
                row,
                frozenset(TradeCorridorRecord.__dataclass_fields__),
                TradeCorridorRecord,
            )
            for row in snapshot["corridors"]
        ),
        flows=tuple(
            _record(
                row,
                frozenset(TradeFlowRecord.__dataclass_fields__),
                TradeFlowRecord,
            )
            for row in snapshot["flows"]
        ),
        locations=tuple(
            _record(
                row,
                frozenset(TradeLocationRecord.__dataclass_fields__),
                TradeLocationRecord,
            )
            for row in snapshot["locations"]
        ),
        dependence=tuple(
            _record(
                row,
                frozenset(TradeDependenceRecord.__dataclass_fields__),
                TradeDependenceRecord,
            )
            for row in snapshot["dependence"]
        ),
        cross_society=tuple(
            _record(
                row,
                frozenset(CrossSocietyTradeRecord.__dataclass_fields__),
                CrossSocietyTradeRecord,
            )
            for row in snapshot["cross_society"]
        ),
        networks=tuple(
            _record(
                row,
                frozenset(TradeNetworkRecord.__dataclass_fields__),
                TradeNetworkRecord,
            )
            for row in snapshot["networks"]
        ),
        digest=snapshot["digest"],
        publication_id=snapshot["publication_id"],
    )


def decode_trade_networks_snapshot(
    payload: bytes, *, run_id: str | None = None
) -> TradeNetworksSnapshot:
    if not isinstance(payload, (bytes, bytearray)):
        raise TradeNetworksArtifactError("trade_networks_artifact_invalid_payload")
    try:
        text = bytes(payload).decode("utf-8")
        parsed = json.loads(text, object_pairs_hook=_reject_duplicates)
    except TradeNetworksArtifactError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TradeNetworksArtifactError(
            "trade_networks_artifact_invalid_payload"
        ) from exc
    snapshot = _build(
        _expect_keys(parsed, _SNAPSHOT_KEYS, "trade_networks_artifact_unknown_field")
    )
    if snapshot.schema_version != TRADE_NETWORKS_SNAPSHOT_VERSION:
        raise TradeNetworksArtifactError("trade_networks_artifact_invalid_schema")
    if run_id is not None and snapshot.run_id != run_id:
        raise TradeNetworksArtifactError("trade_networks_artifact_run_mismatch")
    if snapshot.digest != trade_networks_digest(snapshot):
        raise TradeNetworksArtifactError("trade_networks_artifact_digest_mismatch")
    canonical = (canonical_trade_networks_json(snapshot) + "\n").encode("utf-8")
    if canonical != bytes(payload):
        raise TradeNetworksArtifactError("trade_networks_artifact_non_canonical")
    _LOG.debug(
        "trade_networks_decode corridors=%s networks=%s",
        len(snapshot.corridors),
        len(snapshot.networks),
    )
    return snapshot
