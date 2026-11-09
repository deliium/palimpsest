"""Compose and publish ``inter-society-relations-snapshot-v1``.

Publication is opt-in and post-completion only. Incomplete stop codes isolate
scientific status via ``unavailable`` receipts; store failures never rewrite
the scientific result.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
    InterSocietyRelationsAnalysis,
)
from analysis.inter_society_relations_evidence import InterSocietyEvidenceInputs
from analysis.inter_society_relations_layers import InterSocietyComparisonView
from experiments.inter_society_relations_completed_run import (
    build_completed_run_inter_society_relations_analysis,
    compose_inter_society_relations_snapshot,
)
from simulation.inter_society_relations_codec import (
    encode_inter_society_relations_snapshot,
)
from simulation.inter_society_relations_models import (
    InterSocietyRelationsArtifactError,
    InterSocietyRelationsSnapshot,
)
from simulation.inter_society_relations_ports import InterSocietyRelationsPublisherPort

__all__ = [
    "INCOMPLETE_INTER_SOCIETY_RELATIONS_STOP_CODES",
    "InterSocietyRelationsHarvestResult",
    "InterSocietyRelationsReceipt",
    "build_inter_society_relations_harvest_result",
    "inter_society_relations_publication_document",
    "publish_inter_society_relations_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.inter_society_relations.publication"
)

INCOMPLETE_INTER_SOCIETY_RELATIONS_STOP_CODES: Final[frozenset[str]] = frozenset(
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
class InterSocietyRelationsReceipt:
    status: str
    reason: str | None = None
    publication_id: str | None = None
    digest: str | None = None
    pair_count: int = 0
    series_point_count: int = 0
    comparison_count: int = 0
    byte_count: int = 0
    coverage: str = "not_applicable"
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in _RECEIPT_STATUSES:
            raise ValueError("inter_society_relations_receipt_status")


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsHarvestResult:
    receipt: InterSocietyRelationsReceipt
    snapshot: InterSocietyRelationsSnapshot | None = None


def _stop_reason(runner_result: object) -> str:
    value = getattr(runner_result, "stop_reason", None)
    return getattr(value, "value", str(value or ""))


def _receipt_from_snapshot(
    snapshot: InterSocietyRelationsSnapshot,
    *,
    status: str,
    reason: str | None,
    notices: tuple[str, ...] = (),
) -> InterSocietyRelationsReceipt:
    payload = encode_inter_society_relations_snapshot(snapshot)
    return InterSocietyRelationsReceipt(
        status=status,
        reason=reason,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        pair_count=snapshot.summary.pair_count,
        series_point_count=snapshot.summary.series_point_count,
        comparison_count=snapshot.summary.comparison_count,
        byte_count=len(payload),
        coverage=snapshot.summary.coverage,
        notices=notices,
    )


def _resolve_analysis(
    runner_result: object,
    *,
    analysis: InterSocietyRelationsAnalysis | None,
    candidates: Sequence[InterSocietyMacroCandidate] | None,
    evidence_by_pair: Mapping[tuple[str, str], InterSocietyEvidenceInputs] | None,
) -> InterSocietyRelationsAnalysis:
    if analysis is not None:
        return analysis
    existing = getattr(runner_result, "inter_society_relations_analysis", None)
    if type(existing) is InterSocietyRelationsAnalysis:
        return existing
    resolved_candidates = candidates
    if resolved_candidates is None:
        resolved_candidates = (
            getattr(runner_result, "inter_society_macro_candidates", ()) or ()
        )
    resolved_evidence = evidence_by_pair
    if resolved_evidence is None:
        resolved_evidence = getattr(
            runner_result, "inter_society_evidence_by_pair", None
        )
    return build_completed_run_inter_society_relations_analysis(
        candidates=tuple(resolved_candidates),
        evidence_by_pair=resolved_evidence,
    )


def build_inter_society_relations_harvest_result(
    runner_result: object,
    *,
    committed_events: Sequence[object] = (),
    run_id: str,
    analysis: InterSocietyRelationsAnalysis | None = None,
    candidates: Sequence[InterSocietyMacroCandidate] | None = None,
    evidence_by_pair: Mapping[tuple[str, str], InterSocietyEvidenceInputs]
    | None = None,
    comparisons: Sequence[InterSocietyComparisonView] | None = None,
) -> InterSocietyRelationsHarvestResult:
    """Build a receipt + snapshot without publishing. Never raises into science."""
    del committed_events  # reserved for future event-driven harvest adapters
    stop = _stop_reason(runner_result)
    if stop in INCOMPLETE_INTER_SOCIETY_RELATIONS_STOP_CODES:
        return InterSocietyRelationsHarvestResult(
            receipt=InterSocietyRelationsReceipt(
                status="unavailable", reason=stop, coverage="not_applicable"
            )
        )
    try:
        resolved = _resolve_analysis(
            runner_result,
            analysis=analysis,
            candidates=candidates,
            evidence_by_pair=evidence_by_pair,
        )
        snapshot = compose_inter_society_relations_snapshot(
            resolved, run_id=run_id, comparisons=comparisons
        )
    except InterSocietyRelationsArtifactError as exc:
        if exc.reason_code == "inter_society_relations_size_limit":
            return InterSocietyRelationsHarvestResult(
                receipt=InterSocietyRelationsReceipt(
                    status="size_limit",
                    reason="inter_society_relations_size_limit",
                )
            )
        _LOG.error("inter_society_relations_harvest_failed")
        return InterSocietyRelationsHarvestResult(
            receipt=InterSocietyRelationsReceipt(
                status="failed",
                reason="inter_society_relations_harvest_failed",
            )
        )
    except ValueError as exc:
        code = str(exc)
        if code == "inter_society_relations_size_limit" or "size_limit" in code:
            return InterSocietyRelationsHarvestResult(
                receipt=InterSocietyRelationsReceipt(
                    status="size_limit",
                    reason="inter_society_relations_size_limit",
                )
            )
        _LOG.error("inter_society_relations_harvest_failed")
        return InterSocietyRelationsHarvestResult(
            receipt=InterSocietyRelationsReceipt(
                status="failed",
                reason="inter_society_relations_harvest_failed",
            )
        )
    except Exception:
        _LOG.error("inter_society_relations_harvest_failed")
        return InterSocietyRelationsHarvestResult(
            receipt=InterSocietyRelationsReceipt(
                status="failed",
                reason="inter_society_relations_harvest_failed",
            )
        )
    receipt = _receipt_from_snapshot(snapshot, status="published", reason="published")
    _LOG.info(
        "inter_society_relations_publication status=%s pairs=%s bytes=%s",
        receipt.status,
        receipt.pair_count,
        receipt.byte_count,
    )
    return InterSocietyRelationsHarvestResult(receipt=receipt, snapshot=snapshot)


def publish_inter_society_relations_snapshot(
    runner_result: object,
    publisher: InterSocietyRelationsPublisherPort | None,
    *,
    committed_events: Sequence[object] = (),
    run_id: str,
    analysis: InterSocietyRelationsAnalysis | None = None,
    candidates: Sequence[InterSocietyMacroCandidate] | None = None,
    evidence_by_pair: Mapping[tuple[str, str], InterSocietyEvidenceInputs]
    | None = None,
    comparisons: Sequence[InterSocietyComparisonView] | None = None,
) -> InterSocietyRelationsReceipt:
    """Publish when explicitly configured; never raise into the scientific path."""
    if publisher is None:
        return InterSocietyRelationsReceipt(
            status="disabled", reason="root_unset", coverage="not_applicable"
        )
    result = build_inter_society_relations_harvest_result(
        runner_result,
        committed_events=committed_events,
        run_id=run_id,
        analysis=analysis,
        candidates=candidates,
        evidence_by_pair=evidence_by_pair,
        comparisons=comparisons,
    )
    if result.snapshot is None:
        return result.receipt
    if result.receipt.status in {"unavailable", "failed", "size_limit"}:
        return result.receipt
    try:
        publisher.publish(result.snapshot)
    except ValueError as exc:
        code = str(exc)
        if code == "inter_society_relations_publication_exists":
            return InterSocietyRelationsReceipt(
                status="publication_exists",
                reason="inter_society_relations_publication_exists",
                publication_id=result.receipt.publication_id,
                digest=result.receipt.digest,
                pair_count=result.receipt.pair_count,
                series_point_count=result.receipt.series_point_count,
                comparison_count=result.receipt.comparison_count,
                byte_count=result.receipt.byte_count,
                coverage=result.receipt.coverage,
                notices=result.receipt.notices,
            )
        if code == "inter_society_relations_quota_exceeded":
            return InterSocietyRelationsReceipt(
                status="quota_exceeded",
                reason="inter_society_relations_quota_exceeded",
                publication_id=result.receipt.publication_id,
                digest=result.receipt.digest,
                pair_count=result.receipt.pair_count,
                series_point_count=result.receipt.series_point_count,
                comparison_count=result.receipt.comparison_count,
                byte_count=result.receipt.byte_count,
                coverage=result.receipt.coverage,
                notices=result.receipt.notices,
            )
        if code == "inter_society_relations_size_limit":
            return InterSocietyRelationsReceipt(
                status="size_limit",
                reason="inter_society_relations_size_limit",
                coverage=result.receipt.coverage,
                notices=result.receipt.notices,
            )
        _LOG.error("inter_society_relations_publish_failed")
        return InterSocietyRelationsReceipt(
            status="failed",
            reason="inter_society_relations_publish_failed",
            publication_id=result.receipt.publication_id,
            digest=result.receipt.digest,
            pair_count=result.receipt.pair_count,
            series_point_count=result.receipt.series_point_count,
            comparison_count=result.receipt.comparison_count,
            byte_count=result.receipt.byte_count,
            coverage=result.receipt.coverage,
            notices=result.receipt.notices,
        )
    except Exception:
        _LOG.error("inter_society_relations_publish_failed")
        return InterSocietyRelationsReceipt(
            status="failed",
            reason="inter_society_relations_publish_failed",
            publication_id=result.receipt.publication_id,
            digest=result.receipt.digest,
            pair_count=result.receipt.pair_count,
            series_point_count=result.receipt.series_point_count,
            comparison_count=result.receipt.comparison_count,
            byte_count=result.receipt.byte_count,
            coverage=result.receipt.coverage,
            notices=result.receipt.notices,
        )
    return result.receipt


def inter_society_relations_publication_document(
    receipt: InterSocietyRelationsReceipt,
) -> dict[str, object]:
    return {
        "status": receipt.status,
        "reason": receipt.reason,
        "publication_id": receipt.publication_id,
        "digest": receipt.digest,
        "pair_count": receipt.pair_count,
        "series_point_count": receipt.series_point_count,
        "comparison_count": receipt.comparison_count,
        "byte_count": receipt.byte_count,
        "coverage": receipt.coverage,
        "notices": list(receipt.notices),
    }
