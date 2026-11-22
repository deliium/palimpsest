"""Compile a supported medical belief into one ordinary intervention command."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from agents.cognition.medical_beliefs import (
    MIN_ACTIVE_CAUSE_SCORE,
    MedicalBeliefLedger,
    MedicalCause,
    MedicalPractice,
    active_cause,
    practice_support,
)
from world.actions import Move, Sleep, Wait
from world.models import LifeStatus
from world.observations import Observation

__all__ = [
    "MEDICAL_RETRY_COOLDOWN_TICKS",
    "MedicalIntervention",
    "default_practice_for",
    "select_medical_intervention",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.medical_beliefs_actions"
)

MEDICAL_RETRY_COOLDOWN_TICKS: Final[int] = 3

_DEFAULT_PRACTICE: Final[dict[MedicalCause, MedicalPractice]] = {
    MedicalCause.CONTACT: MedicalPractice.LEAVE,
    MedicalCause.LOCATION: MedicalPractice.LEAVE,
    MedicalCause.FOOD: MedicalPractice.REST,
    MedicalCause.WEATHER: MedicalPractice.REST,
    MedicalCause.CULTURAL: MedicalPractice.RITUAL_PAUSE,
}


@dataclass(frozen=True, slots=True)
class MedicalIntervention:
    cause: MedicalCause
    practice: MedicalPractice
    command: Move | Sleep | Wait


def default_practice_for(cause: MedicalCause) -> MedicalPractice:
    if type(cause) is not MedicalCause:
        raise TypeError("cause must be MedicalCause")
    return _DEFAULT_PRACTICE[cause]


def _best_practice(
    ledger: MedicalBeliefLedger, cause: MedicalCause
) -> MedicalPractice:
    ranked = sorted(
        (
            (practice_support(ledger, cause, practice), index, practice)
            for index, practice in enumerate(MedicalPractice)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    score, _index, practice = ranked[0]
    if score >= MIN_ACTIVE_CAUSE_SCORE:
        return practice
    return default_practice_for(cause)


def _cooldown_ready(
    ledger: MedicalBeliefLedger,
    tick: int,
    cause: MedicalCause,
    practice: MedicalPractice,
) -> bool:
    last = {
        (row_cause, row_practice): row_tick
        for row_cause, row_practice, row_tick in ledger.last_attempt_tick
    }.get((cause, practice))
    return last is None or tick - last >= MEDICAL_RETRY_COOLDOWN_TICKS


def _compile(
    observation: Observation, cause: MedicalCause, practice: MedicalPractice
) -> Move | Sleep | Wait | None:
    if practice is MedicalPractice.LEAVE:
        exits = sorted(observation.exits, key=lambda row: row.destination_id.value)
        if not exits:
            return None
        return Move(exits[0].destination_id)
    if practice is MedicalPractice.REST:
        return Sleep()
    return Wait()


def select_medical_intervention(
    observation: Observation,
    ledger: MedicalBeliefLedger,
    *,
    tick: int,
) -> MedicalIntervention | None:
    """Return one ordinary command when a supported pair is actionable."""
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(ledger) is not MedicalBeliefLedger:
        raise TypeError("ledger must be MedicalBeliefLedger")
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise ValueError("tick must be non-negative")
    self_body = observation.self_body
    if (
        self_body is None
        or self_body.life_status is not LifeStatus.ALIVE
        or self_body.symptom_cue != "unwell"
        or self_body.journey is not None
    ):
        return None
    cause = active_cause(ledger)
    if cause is None:
        return None
    practice = _best_practice(ledger, cause)
    if not _cooldown_ready(ledger, tick, cause, practice):
        _LOG.debug(
            "medical_intervention_skipped reason_code=cooldown cause=%s "
            "practice=%s",
            cause.value,
            practice.value,
        )
        return None
    command = _compile(observation, cause, practice)
    if command is None:
        _LOG.debug(
            "medical_intervention_skipped reason_code=no_exit cause=%s "
            "practice=%s",
            cause.value,
            practice.value,
        )
        return None
    _LOG.debug(
        "medical_intervention_selected cause=%s practice=%s command=%s",
        cause.value,
        practice.value,
        type(command).__name__.lower(),
    )
    return MedicalIntervention(cause=cause, practice=practice, command=command)
