"""Canonical codec for ``supply-chains-snapshot-v1``."""

# ruff: noqa: E501
# mypy: disable-error-code="type-arg,no-untyped-def,return-value,misc,assignment,arg-type,call-overload,attr-defined"

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict
from typing import Final

from simulation.supply_chain_models import (
    SUPPLY_CHAIN_SNAPSHOT_VERSION,
    SupplyBottleneckRecord,
    SupplyChainLineageRecord,
    SupplyChainRecord,
    SupplyChainSnapshot,
    SupplyChainSnapshotError,
    SupplyChainSummaryRecord,
    SupplyDependencyRecord,
    SupplyLocationRecord,
    SupplyOrganizationRecord,
    SupplyStageRecord,
)

__all__ = [
    "canonical_supply_chain_json",
    "canonical_supply_chain_payload",
    "compute_supply_chain_publication_id",
    "decode_supply_chain_snapshot",
    "encode_supply_chain_snapshot",
    "finalize_supply_chain_snapshot",
    "supply_chain_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.supply_chain.codec")
_PUBLICATION_PREFIX: Final[str] = "sc-pub-"
_MAX_BYTES: Final[int] = 8_388_608
_SNAPSHOT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "run_id",
        "schema_version",
        "policy_version",
        "summary",
        "stages",
        "edges",
        "chains",
        "lineage",
        "bottlenecks",
        "locations",
        "organizations",
        "digest",
        "publication_id",
    }
)


def canonical_supply_chain_payload(
    snapshot: SupplyChainSnapshot,
) -> dict[str, object]:
    if type(snapshot) is not SupplyChainSnapshot:
        raise TypeError("snapshot must be SupplyChainSnapshot")
    return asdict(snapshot)


def canonical_supply_chain_json(snapshot: SupplyChainSnapshot) -> str:
    return json.dumps(
        canonical_supply_chain_payload(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def supply_chain_digest(snapshot: SupplyChainSnapshot) -> str:
    payload = canonical_supply_chain_payload(snapshot)
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


def compute_supply_chain_publication_id(*, run_id: str, digest: str) -> str:
    material = f"supply-chains-pub|{run_id}|{digest}"
    return f"{_PUBLICATION_PREFIX}{hashlib.sha256(material.encode()).hexdigest()[:32]}"


def finalize_supply_chain_snapshot(
    snapshot: SupplyChainSnapshot,
) -> SupplyChainSnapshot:
    if type(snapshot) is not SupplyChainSnapshot:
        raise TypeError("snapshot must be SupplyChainSnapshot")
    digest = supply_chain_digest(snapshot)
    finalized = SupplyChainSnapshot(
        run_id=snapshot.run_id,
        schema_version=snapshot.schema_version,
        policy_version=snapshot.policy_version,
        summary=snapshot.summary,
        stages=snapshot.stages,
        edges=snapshot.edges,
        chains=snapshot.chains,
        lineage=snapshot.lineage,
        bottlenecks=snapshot.bottlenecks,
        locations=snapshot.locations,
        organizations=snapshot.organizations,
        digest=digest,
        publication_id=compute_supply_chain_publication_id(
            run_id=snapshot.run_id, digest=digest
        ),
    )
    _LOG.debug(
        "supply_chain_snapshot_finalized rows=%s digest=%s",
        len(snapshot.stages) + len(snapshot.edges) + len(snapshot.chains),
        digest[:8],
    )
    return finalized


def encode_supply_chain_snapshot(snapshot: SupplyChainSnapshot) -> bytes:
    payload = (canonical_supply_chain_json(snapshot) + "\n").encode("utf-8")
    if len(payload) > _MAX_BYTES:
        raise SupplyChainSnapshotError("supply_chain_snapshot_size_limit")
    return payload


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SupplyChainSnapshotError("supply_chain_snapshot_duplicate_key")
        result[key] = value
    return result


def _expect_keys(mapping: object, keys: frozenset[str]) -> dict:
    if type(mapping) is not dict or frozenset(mapping) != keys:
        raise SupplyChainSnapshotError("supply_chain_snapshot_unknown_field")
    return mapping


def _record(mapping: object, row_type: type) -> object:
    keys = frozenset(row_type.__dataclass_fields__)
    row = _expect_keys(mapping, keys)
    converted = dict(row)
    for key, value in row.items():
        if isinstance(value, list):
            converted[key] = tuple(value)
    return row_type(**converted)


def _build(parsed: dict) -> SupplyChainSnapshot:
    return SupplyChainSnapshot(
        run_id=parsed["run_id"],
        schema_version=parsed["schema_version"],
        policy_version=parsed["policy_version"],
        summary=_record(parsed["summary"], SupplyChainSummaryRecord),
        stages=tuple(_record(row, SupplyStageRecord) for row in parsed["stages"]),
        edges=tuple(_record(row, SupplyDependencyRecord) for row in parsed["edges"]),
        chains=tuple(_record(row, SupplyChainRecord) for row in parsed["chains"]),
        lineage=tuple(
            _record(row, SupplyChainLineageRecord) for row in parsed["lineage"]
        ),
        bottlenecks=tuple(
            _record(row, SupplyBottleneckRecord) for row in parsed["bottlenecks"]
        ),
        locations=tuple(
            _record(row, SupplyLocationRecord) for row in parsed["locations"]
        ),
        organizations=tuple(
            _record(row, SupplyOrganizationRecord) for row in parsed["organizations"]
        ),
        digest=parsed["digest"],
        publication_id=parsed["publication_id"],
    )


def decode_supply_chain_snapshot(
    payload: bytes, *, run_id: str | None = None
) -> SupplyChainSnapshot:
    if not isinstance(payload, (bytes, bytearray)):
        raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_payload")
    try:
        text = bytes(payload).decode("utf-8")
        parsed = json.loads(text, object_pairs_hook=_reject_duplicates)
    except SupplyChainSnapshotError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_payload") from exc
    snapshot = _build(_expect_keys(parsed, _SNAPSHOT_KEYS))
    if snapshot.schema_version != SUPPLY_CHAIN_SNAPSHOT_VERSION:
        raise SupplyChainSnapshotError("supply_chain_snapshot_version_unsupported")
    if run_id is not None and snapshot.run_id != run_id:
        raise SupplyChainSnapshotError("supply_chain_snapshot_run_mismatch")
    expected = supply_chain_digest(snapshot)
    if snapshot.digest != expected:
        _LOG.warning(
            "supply_chain_snapshot_decode_rejected "
            "code=supply_chain_snapshot_digest_mismatch"
        )
        raise SupplyChainSnapshotError("supply_chain_snapshot_digest_mismatch")
    canonical = (canonical_supply_chain_json(snapshot) + "\n").encode("utf-8")
    if canonical != bytes(payload):
        raise SupplyChainSnapshotError("supply_chain_snapshot_non_canonical")
    return snapshot
