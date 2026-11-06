# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Compose and publish ``organized-conflict-snapshot-v1``."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final, cast

from analysis.organized_conflict_contract import ConflictAlignment
from analysis.organized_conflict_events import conflict_agent_token
from experiments.organized_conflict_harvest import (
    OrganizedConflictHarvest,
    build_completed_run_organized_conflict_harvest,
)
from simulation.organized_conflict_codec import (
    finalize_organized_conflict_snapshot,
)
from simulation.organized_conflict_models import (
    ORGANIZED_CONFLICT_SNAPSHOT_POLICY,
    ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
    OrganizedConflictContradictionRow,
    OrganizedConflictEpisodeRow,
    OrganizedConflictInterpretationRow,
    OrganizedConflictLineageRow,
    OrganizedConflictMetricProvenanceRow,
    OrganizedConflictOutcomeRow,
    OrganizedConflictParticipantRow,
    OrganizedConflictPlanRow,
    OrganizedConflictSnapshot,
    OrganizedConflictSummaryRow,
    OrganizedConflictTerminationRow,
)
from simulation.organized_conflict_ports import OrganizedConflictPublisherPort

__all__ = [
    "INCOMPLETE_CONFLICT_STOP_CODES",
    "OrganizedConflictHarvestResult",
    "build_organized_conflict_harvest_result",
    "organized_conflict_publication_document",
    "publish_organized_conflict_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.organized_conflict.publication"
)

INCOMPLETE_CONFLICT_STOP_CODES: Final[frozenset[str]] = frozenset(
    {
        "cancelled",
        "cognition_failure",
        "authority_failure",
        "finalization_recovery_required",
        "experiment_criterion_failure",
        "historical_artifact_failure",
    }
)
_FAMILIES: Final[tuple[str, ...]] = (
    "organized_conflict_participation",
    "organized_conflict_persistence",
    "organized_conflict_outcomes",
    "organized_conflict_interpretation",
)


@dataclass(frozen=True, slots=True)
class OrganizedConflictReceipt:
    status: str
    reason: str
    publication_id: str = ""
    digest: str = ""
    episodes: int = 0
    plans: int = 0
    interpretations: int = 0
    coverage: str = "not_applicable"


@dataclass(frozen=True, slots=True)
class OrganizedConflictHarvestResult:
    receipt: OrganizedConflictReceipt
    snapshot: OrganizedConflictSnapshot | None = None


def _stop_reason(runner_result: object) -> str:
    value = getattr(runner_result, "stop_reason", None)
    return getattr(value, "value", str(value or ""))


def _owner_token(row: object) -> str:
    owner = getattr(row, "owner_id", None)
    return conflict_agent_token(owner)


def _candidate_rows(
    harvest: OrganizedConflictHarvest,
) -> tuple[
    tuple[OrganizedConflictEpisodeRow, ...], tuple[OrganizedConflictParticipantRow, ...]
]:
    episodes: list[OrganizedConflictEpisodeRow] = []
    participants: list[OrganizedConflictParticipantRow] = []
    for candidate in harvest.candidates:
        episodes.append(
            OrganizedConflictEpisodeRow(
                episode_id=candidate.candidate_id,
                classification=candidate.classification,
                start_tick=candidate.start_tick,
                end_tick=candidate.end_tick,
                participant_tokens=tuple(sorted(candidate.participant_tokens)),
                opponent_tokens=tuple(sorted(candidate.opponent_tokens)),
                side_count=candidate.side_count,
                hostile_event_count=candidate.hostile_event_count,
                active_window_count=candidate.active_window_count,
                sustained=candidate.sustained,
                org_ids=tuple(candidate.org_ids),
                macro_society_ids=tuple(candidate.macro_society_ids),
            )
        )
        for token in sorted(candidate.participant_tokens):
            participants.append(
                OrganizedConflictParticipantRow(
                    episode_id=candidate.candidate_id,
                    participant_token=token,
                    role="participant",
                    tick=candidate.start_tick,
                )
            )
    return (
        tuple(sorted(episodes, key=lambda row: row.episode_id)),
        tuple(
            sorted(
                participants, key=lambda row: (row.episode_id, row.participant_token)
            )
        ),
    )


def _snapshot(
    harvest: OrganizedConflictHarvest, run_id: str
) -> OrganizedConflictSnapshot:
    episodes, participants = _candidate_rows(harvest)
    plans = tuple(
        sorted(
            (
                OrganizedConflictPlanRow(
                    plan_id=row.plan_id,
                    owner_token=str(
                        getattr(row, "coordinator_ref", None)
                        or getattr(row, "side_ref", None)
                        or "0" * 16
                    ),
                    operation=str(getattr(row, "operation", "")),
                    target_kind=str(getattr(row, "target_kind", "")),
                    status=str(getattr(row, "status", "")),
                    participant_count=len(getattr(row, "participant_refs", ())),
                    tick=int(getattr(row, "start_tick", 0)),
                )
                for row in cast("tuple[Any, ...]", harvest.rows.owner_plans)
            ),
            key=lambda row: row.plan_id,
        )
    )
    alignment_by_interpretation = {
        row.interpretation_id: row.alignment.value for row in harvest.alignment
    }
    episode_refs = {row.episode_id for row in episodes}
    interpretations = tuple(
        sorted(
            (
                OrganizedConflictInterpretationRow(
                    interpretation_id=row.interpretation_id,
                    owner_token=_owner_token(row),
                    episode_id=(
                        row.episode_ref if row.episode_ref in episode_refs else ""
                    ),
                    kind=str(row.kind),
                    alignment=alignment_by_interpretation.get(
                        row.interpretation_id,
                        ConflictAlignment.UNRESOLVED.value,
                    ),
                    tick=int(row.tick),
                )
                for row in cast("tuple[Any, ...]", harvest.rows.owner_interpretations)
            ),
            key=lambda row: row.interpretation_id,
        )
    )
    outcomes = tuple(
        sorted(
            (
                OrganizedConflictOutcomeRow(
                    outcome_id=row.outcome_id,
                    plan_id=row.plan_id,
                    kind=str(row.kind),
                    target_token=row.target_ref,
                    tick=int(row.tick),
                )
                for row in cast("tuple[Any, ...]", harvest.rows.owner_outcomes)
            ),
            key=lambda row: row.outcome_id,
        )
    )
    contradictions = tuple(
        sorted(
            (
                OrganizedConflictContradictionRow(
                    contradiction_id=row.contradiction_id,
                    kind=str(row.kind),
                    member_count=len(row.member_ids),
                    tick=int(row.tick),
                )
                for row in cast("tuple[Any, ...]", harvest.rows.owner_contradictions)
            ),
            key=lambda row: row.contradiction_id,
        )
    )
    terminations = tuple(
        sorted(
            (
                OrganizedConflictTerminationRow(
                    termination_id=row.termination_id,
                    plan_id=row.plan_id,
                    kind=str(row.kind),
                    tick=int(row.tick),
                )
                for row in cast("tuple[Any, ...]", harvest.rows.owner_terminations)
            ),
            key=lambda row: row.termination_id,
        )
    )
    lineage = tuple(
        sorted(
            (
                OrganizedConflictLineageRow(
                    edge_id=row.edge_id,
                    from_id=row.from_id,
                    to_id=row.to_id,
                    kind=row.kind,
                    tick=row.tick,
                )
                for row in harvest.lineage
            ),
            key=lambda row: row.edge_id,
        )
    )
    provenance = tuple(
        sorted(
            (
                OrganizedConflictMetricProvenanceRow(
                    family=family,
                    algorithm_version="1",
                    policy_version=ORGANIZED_CONFLICT_SNAPSHOT_POLICY,
                )
                for family in _FAMILIES
            ),
            key=lambda row: row.family,
        )
    )
    summary = OrganizedConflictSummaryRow(
        episode_count=len(episodes),
        individual_episode_count=sum(
            1 for row in episodes if row.classification == "individual_violence"
        ),
        coordinated_episode_count=sum(
            1 for row in episodes if row.classification == "coordinated_conflict"
        ),
        persistent_inter_group_episode_count=sum(
            1
            for row in episodes
            if row.classification == "persistent_inter_group_conflict"
        ),
        participant_count=len(participants),
        plan_count=len(plans),
        interpretation_count=len(interpretations),
        outcome_count=len(outcomes),
        contradiction_count=len(contradictions),
        termination_count=len(terminations),
        sustained_episode_count=sum(1 for row in episodes if row.sustained),
        coverage=harvest.layers.coverage.value,
    )
    return finalize_organized_conflict_snapshot(
        OrganizedConflictSnapshot(
            schema_version=ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
            policy_version=ORGANIZED_CONFLICT_SNAPSHOT_POLICY,
            run_id=run_id,
            publication_id="oc-pub-" + "0" * 16,
            digest="0" * 64,
            summary=summary,
            episodes=episodes,
            participants=participants,
            plans=plans,
            interpretations=interpretations,
            outcomes=outcomes,
            contradictions=contradictions,
            terminations=terminations,
            lineage=lineage,
            metric_provenance=provenance,
            coverage=harvest.layers.coverage.value,
            notices=harvest.notices,
        )
    )


def build_organized_conflict_harvest_result(
    runner_result: object,
    committed_events: object,
    *,
    run_id: str,
) -> OrganizedConflictHarvestResult:
    """Build status-correct conflict publication state for one completed run."""

    if _stop_reason(runner_result) in INCOMPLETE_CONFLICT_STOP_CODES:
        return OrganizedConflictHarvestResult(
            receipt=OrganizedConflictReceipt(
                status="unavailable", reason="incomplete_run"
            )
        )
    try:
        harvest = build_completed_run_organized_conflict_harvest(
            runner_result,
            committed_events,  # type: ignore[arg-type]
        )
    except Exception:
        _LOG.warning(
            "organized_conflict_publication_failed reason_code=composition_failed"
        )
        return OrganizedConflictHarvestResult(
            receipt=OrganizedConflictReceipt(
                status="failed", reason="composition_failed"
            )
        )
    if not harvest.has_ledger:
        return OrganizedConflictHarvestResult(
            receipt=OrganizedConflictReceipt(status="disabled", reason="no_rows")
        )
    try:
        snapshot = _snapshot(harvest, run_id)
    except Exception:
        _LOG.warning(
            "organized_conflict_publication_failed reason_code=composition_failed"
        )
        return OrganizedConflictHarvestResult(
            receipt=OrganizedConflictReceipt(
                status="failed", reason="composition_failed"
            )
        )
    receipt = OrganizedConflictReceipt(
        status="ready",
        reason="ready",
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        episodes=len(snapshot.episodes),
        plans=len(snapshot.plans),
        interpretations=len(snapshot.interpretations),
        coverage=snapshot.coverage,
    )
    _LOG.info(
        "organized_conflict_publication status=%s episodes=%s plans=%s",
        receipt.status,
        receipt.episodes,
        receipt.plans,
    )
    return OrganizedConflictHarvestResult(receipt=receipt, snapshot=snapshot)


def publish_organized_conflict_snapshot(
    result: OrganizedConflictHarvestResult,
    publisher: OrganizedConflictPublisherPort,
) -> OrganizedConflictHarvestResult:
    """Publish a ready snapshot; failure changes only the receipt."""

    if result.snapshot is None:
        return result
    try:
        publisher.publish(result.snapshot)
    except Exception:
        _LOG.warning(
            "organized_conflict_publication_failed reason_code=publication_failed"
        )
        return OrganizedConflictHarvestResult(
            receipt=OrganizedConflictReceipt(
                status="failed",
                reason="publication_failed",
                publication_id=result.receipt.publication_id,
                digest=result.receipt.digest,
                episodes=result.receipt.episodes,
                plans=result.receipt.plans,
                interpretations=result.receipt.interpretations,
                coverage=result.receipt.coverage,
            ),
            snapshot=result.snapshot,
        )
    return result


def organized_conflict_publication_document(
    result: OrganizedConflictHarvestResult,
) -> dict[str, object]:
    receipt = result.receipt
    return {
        "status": receipt.status,
        "reason": receipt.reason,
        "publication_id": receipt.publication_id,
        "digest": receipt.digest,
        "episodes": receipt.episodes,
        "plans": receipt.plans,
        "interpretations": receipt.interpretations,
        "coverage": receipt.coverage,
    }
