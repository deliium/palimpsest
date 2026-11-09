"""Canonical codec for ``infrastructure-networks-snapshot-v1``."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict
from typing import Final

from simulation.infrastructure_models import (
    INFRASTRUCTURE_MAX_BYTES,
    INFRASTRUCTURE_NETWORKS_PUBLICATION_PREFIX,
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
    InfrastructureAssetRecord,
    InfrastructureNetworksArtifactError,
    InfrastructureNetworksSnapshot,
    InfrastructureNetworksSummaryRecord,
)

__all__ = [
    "canonical_infrastructure_networks_json",
    "canonical_infrastructure_networks_payload",
    "decode_infrastructure_networks_snapshot",
    "encode_infrastructure_networks_snapshot",
    "finalize_infrastructure_networks_snapshot",
    "infrastructure_networks_publication_id",
    "infrastructure_networks_snapshot_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.infrastructure.codec")
_PUBLICATION_HEX_CHARS: Final[int] = 32


def canonical_infrastructure_networks_payload(
    snapshot: InfrastructureNetworksSnapshot,
) -> dict[str, object]:
    if type(snapshot) is not InfrastructureNetworksSnapshot:
        raise TypeError("snapshot must be InfrastructureNetworksSnapshot")
    return asdict(snapshot)


def canonical_infrastructure_networks_json(
    snapshot: InfrastructureNetworksSnapshot,
) -> str:
    return json.dumps(
        canonical_infrastructure_networks_payload(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def infrastructure_networks_snapshot_digest(
    snapshot: InfrastructureNetworksSnapshot,
) -> str:
    payload = canonical_infrastructure_networks_payload(snapshot)
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


def infrastructure_networks_publication_id(*, run_id: str, digest: str) -> str:
    material = f"infra-pub|{run_id}|{digest}"
    hex_digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return (
        f"{INFRASTRUCTURE_NETWORKS_PUBLICATION_PREFIX}"
        f"{hex_digest[:_PUBLICATION_HEX_CHARS]}"
    )


def _summary_counts(
    assets: tuple[InfrastructureAssetRecord, ...],
) -> dict[str, int]:
    return {
        "asset_count": len(assets),
        "node_count": sum(1 for asset in assets if asset.topology == "node"),
        "edge_count": sum(1 for asset in assets if asset.topology == "edge"),
        "operational_count": sum(
            1 for asset in assets if asset.status == "operational"
        ),
        "damaged_count": sum(1 for asset in assets if asset.status == "damaged"),
        "destroyed_count": sum(1 for asset in assets if asset.status == "destroyed"),
        "effects_active_count": sum(1 for asset in assets if asset.effects_active),
    }


def finalize_infrastructure_networks_snapshot(
    snapshot: InfrastructureNetworksSnapshot,
) -> InfrastructureNetworksSnapshot:
    counts = _summary_counts(snapshot.assets)
    staged = InfrastructureNetworksSnapshot(
        summary=InfrastructureNetworksSummaryRecord(
            run_id=snapshot.summary.run_id,
            publication_id="",
            digest="",
            schema_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
            policy_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
            coverage=snapshot.summary.coverage,
            **counts,
        ),
        assets=snapshot.assets,
        digest="",
        publication_id="",
    )
    digest = infrastructure_networks_snapshot_digest(staged)
    publication_id = infrastructure_networks_publication_id(
        run_id=staged.summary.run_id, digest=digest
    )
    summary = InfrastructureNetworksSummaryRecord(
        run_id=staged.summary.run_id,
        publication_id=publication_id,
        digest=digest,
        schema_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
        policy_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
        coverage=staged.summary.coverage,
        **counts,
    )
    finalized = InfrastructureNetworksSnapshot(
        summary=summary,
        assets=staged.assets,
        digest=digest,
        publication_id=publication_id,
    )
    if infrastructure_networks_snapshot_digest(finalized) != digest:
        raise InfrastructureNetworksArtifactError(
            "infrastructure_networks_invalid_digest"
        )
    encoded = encode_infrastructure_networks_snapshot(finalized)
    _LOG.debug(
        "infrastructure_networks_finalize bytes=%s asset_count=%s",
        len(encoded),
        finalized.summary.asset_count,
    )
    return finalized


def encode_infrastructure_networks_snapshot(
    snapshot: InfrastructureNetworksSnapshot,
) -> bytes:
    text = canonical_infrastructure_networks_json(snapshot) + "\n"
    payload = text.encode("utf-8")
    if len(payload) > INFRASTRUCTURE_MAX_BYTES:
        _LOG.error(
            "infrastructure_networks_encode_failed "
            "reason_code=infrastructure_networks_size_limit bytes=%s",
            len(payload),
        )
        raise InfrastructureNetworksArtifactError("infrastructure_networks_size_limit")
    return payload


def decode_infrastructure_networks_snapshot(
    payload: bytes | str | dict[str, object],
) -> InfrastructureNetworksSnapshot:
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
        assets = tuple(
            InfrastructureAssetRecord(
                asset_id=item["asset_id"],
                kind=item["kind"],
                topology=item["topology"],
                status=item["status"],
                integrity=float(item["integrity"]),
                location_id=item["location_id"],
                endpoint_location_id=item.get("endpoint_location_id"),
                effects_active=bool(item["effects_active"]),
                created_tick=item["created_tick"],
                last_maintained_tick=item["last_maintained_tick"],
                ticks_since_maintained=item["ticks_since_maintained"],
                linked_project_id=item["linked_project_id"],
                linked_structure_id=item.get("linked_structure_id"),
            )
            for item in data.get("assets") or ()
        )
        summary = InfrastructureNetworksSummaryRecord(
            run_id=summary_raw["run_id"],
            publication_id=summary_raw.get("publication_id") or "",
            digest=summary_raw.get("digest") or "",
            schema_version=summary_raw["schema_version"],
            policy_version=summary_raw["policy_version"],
            asset_count=summary_raw["asset_count"],
            node_count=summary_raw["node_count"],
            edge_count=summary_raw["edge_count"],
            operational_count=summary_raw["operational_count"],
            damaged_count=summary_raw["damaged_count"],
            destroyed_count=summary_raw["destroyed_count"],
            effects_active_count=summary_raw["effects_active_count"],
            coverage=summary_raw.get("coverage") or "not_applicable",
        )
        snapshot = InfrastructureNetworksSnapshot(
            summary=summary,
            assets=assets,
            digest=data.get("digest") or "",
            publication_id=data.get("publication_id") or "",
            schema_version=data.get("schema_version")
            or INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
            policy_version=data.get("policy_version")
            or INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
        )
    except InfrastructureNetworksArtifactError:
        raise
    except Exception as exc:
        _LOG.error(
            "infrastructure_networks_decode_failed "
            "reason_code=infrastructure_networks_store_corrupt"
        )
        raise InfrastructureNetworksArtifactError(
            "infrastructure_networks_store_corrupt"
        ) from exc
    _LOG.debug(
        "infrastructure_networks_decode asset_count=%s", snapshot.summary.asset_count
    )
    return snapshot
