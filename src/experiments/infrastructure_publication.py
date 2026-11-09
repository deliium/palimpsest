"""Compose and publish ``infrastructure-networks-snapshot-v1``.

Publication is opt-in and post-completion only. Incomplete stop codes isolate
scientific status via ``unavailable`` receipts; store failures never rewrite
the scientific result.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.infrastructure_networks_analysis import InfrastructureNetworksAnalysis
from experiments.infrastructure_completed_run import (
    build_completed_run_infrastructure_networks_analysis,
    compose_infrastructure_networks_snapshot,
)
from simulation.infrastructure_codec import encode_infrastructure_networks_snapshot
from simulation.infrastructure_models import (
    InfrastructureNetworksArtifactError,
    InfrastructureNetworksSnapshot,
)
from simulation.infrastructure_ports import InfrastructureNetworksPublisherPort
from world.infrastructure import InfrastructureAsset

__all__ = [
    "INCOMPLETE_INFRASTRUCTURE_NETWORKS_STOP_CODES",
    "InfrastructureNetworksHarvestResult",
    "InfrastructureNetworksReceipt",
    "build_infrastructure_networks_harvest_result",
    "infrastructure_networks_publication_document",
    "publish_infrastructure_networks_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.infrastructure.publication"
)

INCOMPLETE_INFRASTRUCTURE_NETWORKS_STOP_CODES: Final[frozenset[str]] = frozenset(
    {
        "cancelled",
        "cognition_failure",
        "authority_failure",
        "finalization_recovery_required",
        "experiment_criterion_failure",
        "historical_artifact_failure",
    }
)

_RECEIPT_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "disabled",
        "unavailable",
        "failed",
        "size_limit",
        "publication_exists",
        "quota_exceeded",
        "published",
    }
)


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksReceipt:
    status: str
    reason: str | None = None
    publication_id: str | None = None
    digest: str | None = None
    asset_count: int = 0
    byte_count: int = 0
    coverage: str = "not_applicable"
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in _RECEIPT_STATUSES:
            raise ValueError("infrastructure_networks_receipt_status")


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksHarvestResult:
    receipt: InfrastructureNetworksReceipt
    snapshot: InfrastructureNetworksSnapshot | None = None


def _stop_reason(runner_result: object) -> str:
    value = getattr(runner_result, "stop_reason", None)
    return getattr(value, "value", str(value or ""))


def _receipt_from_snapshot(
    snapshot: InfrastructureNetworksSnapshot,
    *,
    status: str,
    reason: str | None,
    notices: tuple[str, ...] = (),
) -> InfrastructureNetworksReceipt:
    payload = encode_infrastructure_networks_snapshot(snapshot)
    return InfrastructureNetworksReceipt(
        status=status,
        reason=reason,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        asset_count=snapshot.summary.asset_count,
        byte_count=len(payload),
        coverage=snapshot.summary.coverage,
        notices=notices,
    )


def _resolve_analysis(
    runner_result: object,
    *,
    analysis: InfrastructureNetworksAnalysis | None,
    assets: Sequence[InfrastructureAsset] | None,
    window_tick: int | None,
) -> InfrastructureNetworksAnalysis:
    if analysis is not None:
        return analysis
    existing = getattr(runner_result, "infrastructure_networks_analysis", None)
    if type(existing) is InfrastructureNetworksAnalysis:
        return existing
    resolved_assets = assets
    if resolved_assets is None:
        resolved_assets = (
            getattr(runner_result, "final_infrastructure_assets", None)
            or getattr(runner_result, "infrastructure_assets", ())
            or ()
        )
    routes = getattr(runner_result, "final_travel_network", ()) or ()
    tick = (
        window_tick
        if window_tick is not None
        else int(getattr(runner_result, "window_end", 0) or 0)
    )
    return build_completed_run_infrastructure_networks_analysis(
        resolved_assets, routes=routes, window_tick=tick
    )


def build_infrastructure_networks_harvest_result(
    runner_result: object,
    *,
    committed_events: Sequence[object] = (),
    run_id: str,
    analysis: InfrastructureNetworksAnalysis | None = None,
    assets: Sequence[InfrastructureAsset] | None = None,
    window_tick: int | None = None,
) -> InfrastructureNetworksHarvestResult:
    """Build a receipt + snapshot without publishing. Never raises into science."""
    del committed_events
    stop = _stop_reason(runner_result)
    if stop in INCOMPLETE_INFRASTRUCTURE_NETWORKS_STOP_CODES:
        return InfrastructureNetworksHarvestResult(
            receipt=InfrastructureNetworksReceipt(
                status="unavailable", reason=stop, coverage="not_applicable"
            )
        )
    try:
        resolved = _resolve_analysis(
            runner_result,
            analysis=analysis,
            assets=assets,
            window_tick=window_tick,
        )
        snapshot = compose_infrastructure_networks_snapshot(resolved, run_id=run_id)
    except InfrastructureNetworksArtifactError as exc:
        if exc.reason_code == "infrastructure_networks_size_limit":
            return InfrastructureNetworksHarvestResult(
                receipt=InfrastructureNetworksReceipt(
                    status="size_limit",
                    reason="infrastructure_networks_size_limit",
                )
            )
        _LOG.error("infrastructure_networks_harvest_failed")
        return InfrastructureNetworksHarvestResult(
            receipt=InfrastructureNetworksReceipt(
                status="failed",
                reason="infrastructure_networks_harvest_failed",
            )
        )
    except Exception:
        _LOG.error("infrastructure_networks_harvest_failed")
        return InfrastructureNetworksHarvestResult(
            receipt=InfrastructureNetworksReceipt(
                status="failed",
                reason="infrastructure_networks_harvest_failed",
            )
        )
    receipt = _receipt_from_snapshot(snapshot, status="published", reason="published")
    _LOG.info(
        "infrastructure_networks_publication status=%s assets=%s bytes=%s",
        receipt.status,
        receipt.asset_count,
        receipt.byte_count,
    )
    return InfrastructureNetworksHarvestResult(receipt=receipt, snapshot=snapshot)


def publish_infrastructure_networks_snapshot(
    runner_result: object,
    publisher: InfrastructureNetworksPublisherPort | None,
    *,
    committed_events: Sequence[object] = (),
    run_id: str,
    analysis: InfrastructureNetworksAnalysis | None = None,
    assets: Sequence[InfrastructureAsset] | None = None,
    window_tick: int | None = None,
) -> InfrastructureNetworksReceipt:
    """Publish when explicitly configured; never raise into the scientific path."""
    if publisher is None:
        return InfrastructureNetworksReceipt(
            status="disabled", reason="root_unset", coverage="not_applicable"
        )
    result = build_infrastructure_networks_harvest_result(
        runner_result,
        committed_events=committed_events,
        run_id=run_id,
        analysis=analysis,
        assets=assets,
        window_tick=window_tick,
    )
    if result.snapshot is None:
        return result.receipt
    if result.receipt.status in {"unavailable", "failed", "size_limit"}:
        return result.receipt
    try:
        publisher.publish(result.snapshot)
    except ValueError as exc:
        code = str(exc)
        if code == "infrastructure_networks_publication_exists":
            return InfrastructureNetworksReceipt(
                status="publication_exists",
                reason="infrastructure_networks_publication_exists",
                publication_id=result.receipt.publication_id,
                digest=result.receipt.digest,
                asset_count=result.receipt.asset_count,
                byte_count=result.receipt.byte_count,
                coverage=result.receipt.coverage,
                notices=result.receipt.notices,
            )
        if code == "infrastructure_networks_quota_exceeded":
            return InfrastructureNetworksReceipt(
                status="quota_exceeded",
                reason="infrastructure_networks_quota_exceeded",
                publication_id=result.receipt.publication_id,
                digest=result.receipt.digest,
                asset_count=result.receipt.asset_count,
                byte_count=result.receipt.byte_count,
                coverage=result.receipt.coverage,
                notices=result.receipt.notices,
            )
        if code == "infrastructure_networks_size_limit":
            return InfrastructureNetworksReceipt(
                status="size_limit",
                reason="infrastructure_networks_size_limit",
                coverage=result.receipt.coverage,
                notices=result.receipt.notices,
            )
        _LOG.error("infrastructure_networks_publish_failed")
        return InfrastructureNetworksReceipt(
            status="failed",
            reason="infrastructure_networks_publish_failed",
            publication_id=result.receipt.publication_id,
            digest=result.receipt.digest,
            asset_count=result.receipt.asset_count,
            byte_count=result.receipt.byte_count,
            coverage=result.receipt.coverage,
            notices=result.receipt.notices,
        )
    except Exception:
        _LOG.error("infrastructure_networks_publish_failed")
        return InfrastructureNetworksReceipt(
            status="failed",
            reason="infrastructure_networks_publish_failed",
            publication_id=result.receipt.publication_id,
            digest=result.receipt.digest,
            asset_count=result.receipt.asset_count,
            byte_count=result.receipt.byte_count,
            coverage=result.receipt.coverage,
            notices=result.receipt.notices,
        )
    return result.receipt


def infrastructure_networks_publication_document(
    receipt: InfrastructureNetworksReceipt,
) -> dict[str, object]:
    return {
        "status": receipt.status,
        "reason": receipt.reason,
        "publication_id": receipt.publication_id,
        "digest": receipt.digest,
        "asset_count": receipt.asset_count,
        "byte_count": receipt.byte_count,
        "coverage": receipt.coverage,
        "notices": list(receipt.notices),
    }
