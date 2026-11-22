"""Detached, opt-in evidence capture for subjective medical beliefs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, cast

from agents.models import AgentId
from simulation import SimulationRunnerConfig, SimulationRunnerResult
from simulation.lifecycle import ActionResolutionStatus
from simulation.medical_beliefs_checkpoint import MedicalBeliefLedgerExport
from simulation.runner import SimulationRunner
from simulation.runner_models import ActionResolutionEvidence, is_failure_stop_reason

__all__ = [
    "MEDICAL_BELIEFS_EVIDENCE_VERSION",
    "MedicalAttemptEvidence",
    "MedicalBeliefEvidence",
    "MedicalBeliefsCaptureResult",
    "MedicalBeliefsCaptureStatus",
    "MedicalBeliefsEvidence",
    "MedicalInterpretationEvidence",
    "MedicalOutcomeEvidence",
    "MedicalTransmissionEvidence",
    "run_with_medical_beliefs_capture",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.medical_beliefs_capture"
)

MEDICAL_BELIEFS_EVIDENCE_VERSION: Final[str] = "medical-beliefs-evidence-v1"


class MedicalBeliefsCaptureStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    CAPTURE_FAILED = "capture_failed"


@dataclass(frozen=True, slots=True)
class MedicalBeliefEvidence:
    owner_id: AgentId
    tick: int
    cause: object
    score: int


@dataclass(frozen=True, slots=True)
class MedicalAttemptEvidence:
    owner_id: AgentId
    tick: int
    attempt_id: str
    cause: object
    practice: object
    command_kind: str
    application_status: ActionResolutionStatus | None
    request_id: str | None


@dataclass(frozen=True, slots=True)
class MedicalOutcomeEvidence:
    owner_id: AgentId
    tick: int
    attempt_id: str
    outcome: object


@dataclass(frozen=True, slots=True)
class MedicalInterpretationEvidence:
    owner_id: AgentId
    tick: int
    attempt_id: str
    outlook: object | None


@dataclass(frozen=True, slots=True)
class MedicalTransmissionEvidence:
    owner_id: AgentId
    tick: int
    cause: object
    practice: object
    outlook: object
    root: str
    hop: int
    speaker_id: object
    occurrence_ref: str
    status: object


@dataclass(frozen=True, slots=True)
class MedicalBeliefsEvidence:
    beliefs: tuple[MedicalBeliefEvidence, ...] = ()
    attempts: tuple[MedicalAttemptEvidence, ...] = ()
    outcomes: tuple[MedicalOutcomeEvidence, ...] = ()
    interpretations: tuple[MedicalInterpretationEvidence, ...] = ()
    transmissions: tuple[MedicalTransmissionEvidence, ...] = ()
    schema_version: str = MEDICAL_BELIEFS_EVIDENCE_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != MEDICAL_BELIEFS_EVIDENCE_VERSION:
            raise ValueError("medical_beliefs_evidence_schema_invalid")


@dataclass(frozen=True, slots=True)
class MedicalBeliefsCaptureResult:
    result: SimulationRunnerResult
    status: MedicalBeliefsCaptureStatus
    evidence: MedicalBeliefsEvidence | None
    reason_codes: tuple[str, ...] = ()


_MAX_SEEN_ROOTS: Final[int] = 128
_COMMAND_KIND: Final[dict[str, str]] = {
    "leave": "move",
    "rest": "sleep",
    "ritual_pause": "wait",
}


def _attempt_key(row: object) -> tuple[str, int, str]:
    typed = cast(Any, row)
    practice = getattr(typed.practice, "value", None)
    return (
        typed.owner_id.value,
        typed.tick,
        _COMMAND_KIND[str(practice)],
    )


def _project(
    export: MedicalBeliefLedgerExport,
    result: SimulationRunnerResult,
) -> tuple[MedicalBeliefsEvidence, tuple[str, ...]]:
    beliefs: list[MedicalBeliefEvidence] = []
    attempts: list[MedicalAttemptEvidence] = []
    outcomes: list[MedicalOutcomeEvidence] = []
    interpretations: list[MedicalInterpretationEvidence] = []
    transmissions: list[MedicalTransmissionEvidence] = []
    keys = {
        _attempt_key(row)
        for ledger in export.ledgers
        for row in ledger.rows
        if getattr(row, "kind", None) == "attempt"
    }
    matches: dict[tuple[str, int, str], list[ActionResolutionEvidence]] = {}
    for receipt in result.finalized_tick_receipts:
        for receipt_resolution in receipt.resolutions:
            key = (
                receipt_resolution.agent_id.value,
                receipt_resolution.tick,
                receipt_resolution.command_kind,
            )
            if key in keys:
                matches.setdefault(key, []).append(receipt_resolution)
    reasons: list[str] = []
    for ledger in export.ledgers:
        for raw_row in ledger.rows:
            row = cast(Any, raw_row)
            kind = getattr(row, "kind", None)
            if kind == "belief":
                beliefs.append(
                    MedicalBeliefEvidence(
                        owner_id=row.owner_id,
                        tick=row.tick,
                        cause=row.cause,
                        score=row.score,
                    )
                )
            elif kind == "attempt":
                found = matches.get(_attempt_key(row), [])
                if len(found) > 1:
                    raise ValueError("medical_beliefs_duplicate_receipt")
                resolution: ActionResolutionEvidence | None = (
                    None if not found else found[0]
                )
                if resolution is None:
                    reasons.append("attempt_receipt_missing")
                attempts.append(
                    MedicalAttemptEvidence(
                        owner_id=row.owner_id,
                        tick=row.tick,
                        attempt_id=row.attempt_id,
                        cause=row.cause,
                        practice=row.practice,
                        command_kind=_COMMAND_KIND[str(row.practice.value)],
                        application_status=(
                            None
                            if resolution is None
                            else getattr(resolution, "status", None)
                        ),
                        request_id=(
                            None
                            if resolution is None
                            else getattr(resolution, "request_id", None)
                        ),
                    )
                )
            elif kind == "outcome":
                outcomes.append(
                    MedicalOutcomeEvidence(
                        owner_id=row.owner_id,
                        tick=row.tick,
                        attempt_id=row.attempt_id,
                        outcome=row.outcome,
                    )
                )
            elif kind == "interpretation":
                interpretations.append(
                    MedicalInterpretationEvidence(
                        owner_id=row.owner_id,
                        tick=row.tick,
                        attempt_id=row.attempt_id,
                        outlook=row.outlook,
                    )
                )
            elif kind == "transmission":
                transmissions.append(
                    MedicalTransmissionEvidence(
                        owner_id=row.owner_id,
                        tick=row.tick,
                        cause=row.cause,
                        practice=row.practice,
                        outlook=row.outlook,
                        root=row.root,
                        hop=row.hop,
                        speaker_id=row.speaker_id,
                        occurrence_ref=row.occurrence_ref,
                        status=row.status,
                    )
                )
        if ledger.history_truncated:
            reasons.append("history_truncated")
        if len(ledger.seen_roots) >= _MAX_SEEN_ROOTS:
            reasons.append("root_cap_reached")
    if export.unavailable_owner_ids:
        reasons.append("owner_unavailable")
    if export.expected_count > len(export.ledgers):
        reasons.append("owner_omitted")
    return (
        MedicalBeliefsEvidence(
            beliefs=tuple(beliefs),
            attempts=tuple(attempts),
            outcomes=tuple(outcomes),
            interpretations=tuple(interpretations),
            transmissions=tuple(transmissions),
        ),
        tuple(sorted(set(reasons))),
    )


async def run_with_medical_beliefs_capture(
    runner: SimulationRunner, *, capture: bool = False
) -> MedicalBeliefsCaptureResult:
    """Run once and optionally return detached five-lane medical evidence."""
    if type(runner) is not SimulationRunner:
        raise TypeError("runner must be SimulationRunner")
    if type(capture) is not bool:
        raise TypeError("capture must be bool")
    starting_tick = runner.ticks_committed
    starting_cursor = runner.engine.tick.value
    result = await runner.run()
    if not capture:
        return MedicalBeliefsCaptureResult(
            result=result,
            status=MedicalBeliefsCaptureStatus.UNAVAILABLE,
            evidence=None,
            reason_codes=("capture_disabled",),
        )
    config: SimulationRunnerConfig = runner.config
    if config.medical_beliefs is None:
        return MedicalBeliefsCaptureResult(
            result=result,
            status=MedicalBeliefsCaptureStatus.UNAVAILABLE,
            evidence=None,
            reason_codes=("medical_beliefs_disabled",),
        )
    if is_failure_stop_reason(result.stop_reason):
        return MedicalBeliefsCaptureResult(
            result=result,
            status=MedicalBeliefsCaptureStatus.UNAVAILABLE,
            evidence=None,
            reason_codes=("terminal_abort",),
        )
    if runner.engine.tick.value != result.ticks_committed:
        return MedicalBeliefsCaptureResult(
            result=result,
            status=MedicalBeliefsCaptureStatus.UNAVAILABLE,
            evidence=None,
            reason_codes=("boundary_mismatch",),
        )
    try:
        export = runner.export_medical_belief_ledgers()
        if type(export) is not MedicalBeliefLedgerExport:
            raise TypeError("invalid export")
        evidence, reasons = _project(export, result)
    except Exception:
        _LOG.warning(
            "medical_beliefs_capture_failed run_id=%s",
            result.run_id.value,
        )
        return MedicalBeliefsCaptureResult(
            result=result,
            status=MedicalBeliefsCaptureStatus.CAPTURE_FAILED,
            evidence=None,
            reason_codes=("capture_failed",),
        )
    partial = bool(reasons) or starting_tick != 0 or starting_cursor != 0
    if len(result.finalized_tick_receipts) < result.ticks_committed:
        partial = True
        reasons = tuple(sorted({*reasons, "finalized_receipt_gap"}))
    _LOG.info(
        "medical_beliefs_capture run_id=%s status=%s beliefs=%s attempts=%s "
        "outcomes=%s interpretations=%s transmissions=%s",
        result.run_id.value,
        "partial" if partial else "complete",
        len(evidence.beliefs),
        len(evidence.attempts),
        len(evidence.outcomes),
        len(evidence.interpretations),
        len(evidence.transmissions),
    )
    return MedicalBeliefsCaptureResult(
        result=result,
        status=(
            MedicalBeliefsCaptureStatus.PARTIAL
            if partial
            else MedicalBeliefsCaptureStatus.COMPLETE
        ),
        evidence=evidence,
        reason_codes=reasons,
    )
