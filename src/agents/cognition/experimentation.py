"""Owner-scoped experiment hypotheses. Not laws and not practical knowledge."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Final, cast

from agents.cognition.production import observed_experiment_operand_ids
from agents.models import AgentId
from world.actions import Experiment
from world.experimentation import (
    DiscoveryMode,
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.experimentation")

_OUTCOMES: Final[frozenset[str]] = frozenset(
    item.value for item in ExperimentOutcomeClass
)


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def experiment_hypothesis_id(
    owner_id: AgentId,
    operator: ExperimentOperator,
    operand_a_id: str,
    operand_b_id: str | None,
    process_token: ExperimentProcessToken,
) -> str:
    """Stable id from owner, operator, operand order, and process. No RNG."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(operator) is not ExperimentOperator:
        raise _fail("operator", "invalid_type")
    if type(process_token) is not ExperimentProcessToken:
        raise _fail("process_token", "invalid_type")
    if type(operand_a_id) is not str or not operand_a_id:
        raise _fail("operand_a_id", "invalid_type")
    if operand_b_id is not None and type(operand_b_id) is not str:
        raise _fail("operand_b_id", "invalid_type")
    second = "" if operand_b_id is None else operand_b_id
    material = "|".join(
        (
            owner_id.value,
            operator.value,
            operand_a_id,
            second,
            process_token.value,
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"hyp:{digest}"


@dataclass(frozen=True, slots=True)
class ExperimentCognitionBinding:
    """Caps the loop may see. Law rows are not copied."""

    max_hypotheses: int
    max_trials_per_tick: int
    repeat_threshold: int
    learn_into_genealogy: bool
    allow_provider: bool


def cognition_binding_from_spec(spec: object) -> ExperimentCognitionBinding:
    """Copy closed caps off a runner spec. Ignore law rows."""
    if type(spec) is ExperimentCognitionBinding:
        return spec
    row = cast(Any, spec)
    try:
        binding = ExperimentCognitionBinding(
            max_hypotheses=int(row.max_hypotheses),
            max_trials_per_tick=int(row.max_trials_per_tick),
            repeat_threshold=int(row.repeat_threshold),
            learn_into_genealogy=bool(row.learn_into_genealogy),
            allow_provider=bool(row.allow_provider),
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise TypeError("bounded_experimentation spec caps are invalid") from exc
    if type(row.learn_into_genealogy) is not bool:
        raise TypeError("learn_into_genealogy must be bool")
    if type(row.allow_provider) is not bool:
        raise TypeError("allow_provider must be bool")
    return binding


@dataclass(frozen=True, slots=True)
class ExperimentHypothesis:
    """Subjective proposal. Predicted outcome is not an engine input."""

    owner_id: AgentId
    hypothesis_id: str
    operator: ExperimentOperator
    operand_a_id: str
    process_token: ExperimentProcessToken
    predicted_outcome: str | None
    operand_b_id: str | None = None
    support: int = 0
    counter: int = 0
    evidence_event_ids: tuple[str, ...] = ()
    active: bool = True
    created_tick: int = 0

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.hypothesis_id) is not str or not self.hypothesis_id:
            raise _fail("hypothesis_id", "invalid_type")
        if type(self.operator) is not ExperimentOperator:
            raise _fail("operator", "invalid_type")
        if type(self.process_token) is not ExperimentProcessToken:
            raise _fail("process_token", "invalid_type")
        if type(self.operand_a_id) is not str or not self.operand_a_id:
            raise _fail("operand_a_id", "invalid_type")
        if self.operand_b_id is not None and type(self.operand_b_id) is not str:
            raise _fail("operand_b_id", "invalid_type")
        if self.predicted_outcome is not None and (
            self.predicted_outcome not in _OUTCOMES
        ):
            raise _fail("predicted_outcome", "invalid_outcome")
        if type(self.support) is not int or self.support < 0:
            raise _fail("support", "invalid_count")
        if type(self.counter) is not int or self.counter < 0:
            raise _fail("counter", "invalid_count")
        if type(self.active) is not bool:
            raise _fail("active", "invalid_type")
        if type(self.created_tick) is not int or self.created_tick < 0:
            raise _fail("created_tick", "invalid_tick")
        if not isinstance(self.evidence_event_ids, tuple):
            raise _fail("evidence_event_ids", "invalid_type")


@dataclass(frozen=True, slots=True)
class ExperimentTrial:
    """One objective result copied from an experiment_resolved event."""

    tick: int
    event_id: str
    outcome_class: str
    discovery_mode: str
    hypothesis_id: str = ""

    def __post_init__(self) -> None:
        if type(self.tick) is not int or self.tick < 0:
            raise _fail("tick", "invalid_tick")
        if type(self.event_id) is not str or not self.event_id:
            raise _fail("event_id", "invalid_type")
        if self.outcome_class not in _OUTCOMES:
            raise _fail("outcome_class", "invalid_outcome")
        if self.discovery_mode not in {item.value for item in DiscoveryMode}:
            raise _fail("discovery_mode", "invalid_mode")
        if type(self.hypothesis_id) is not str:
            raise _fail("hypothesis_id", "invalid_type")


@dataclass(frozen=True, slots=True)
class ExperimentLedger:
    """Owner hypotheses and trials. Outside the objective fold."""

    owner_id: AgentId
    max_hypotheses: int
    max_trials_per_tick: int
    repeat_threshold: int
    learn_into_genealogy: bool
    hypotheses: tuple[ExperimentHypothesis, ...] = ()
    trials: tuple[ExperimentTrial, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.max_hypotheses) is not int or not 1 <= self.max_hypotheses <= 32:
            raise _fail("max_hypotheses", "invalid_cap")
        if (
            type(self.max_trials_per_tick) is not int
            or not 1 <= self.max_trials_per_tick <= 4
        ):
            raise _fail("max_trials_per_tick", "invalid_cap")
        if (
            type(self.repeat_threshold) is not int
            or not 1 <= self.repeat_threshold <= 8
        ):
            raise _fail("repeat_threshold", "invalid_cap")
        if type(self.learn_into_genealogy) is not bool:
            raise _fail("learn_into_genealogy", "invalid_type")
        if not isinstance(self.hypotheses, tuple):
            raise _fail("hypotheses", "invalid_type")
        if not isinstance(self.trials, tuple):
            raise _fail("trials", "invalid_type")
        for row in self.hypotheses:
            if type(row) is not ExperimentHypothesis or row.owner_id != self.owner_id:
                raise _fail("hypotheses", "owner_mismatch")
        for trial in self.trials:
            if type(trial) is not ExperimentTrial:
                raise _fail("trials", "invalid_type")


def empty_experiment_ledger(
    owner_id: AgentId,
    binding: ExperimentCognitionBinding,
) -> ExperimentLedger:
    """Empty owner ledger. Construction does not copy another owner."""
    ledger = ExperimentLedger(
        owner_id=owner_id,
        max_hypotheses=binding.max_hypotheses,
        max_trials_per_tick=binding.max_trials_per_tick,
        repeat_threshold=binding.repeat_threshold,
        learn_into_genealogy=binding.learn_into_genealogy,
    )
    _LOG.debug(
        "experiment_ledger_constructed owner_id=%s hypothesis_count=%s",
        owner_id.value,
        0,
    )
    return ledger


def admit_hypothesis(
    ledger: ExperimentLedger, hypothesis: ExperimentHypothesis
) -> ExperimentLedger:
    """Insert a hypothesis, evicting lowest support then oldest past the cap."""
    if type(hypothesis) is not ExperimentHypothesis:
        raise _fail("hypothesis", "invalid_type")
    if hypothesis.owner_id != ledger.owner_id:
        raise _fail("hypothesis", "owner_mismatch")
    if any(row.hypothesis_id == hypothesis.hypothesis_id for row in ledger.hypotheses):
        return ledger
    rows = [*ledger.hypotheses, hypothesis]
    while len(rows) > ledger.max_hypotheses:
        rows.sort(key=lambda row: (row.support, row.created_tick, row.hypothesis_id))
        rows.pop(0)
    return replace(ledger, hypotheses=tuple(rows))


def record_trial(ledger: ExperimentLedger, trial: ExperimentTrial) -> ExperimentLedger:
    """Append one trial unless this tick is already at the cap."""
    if type(trial) is not ExperimentTrial:
        raise _fail("trial", "invalid_type")
    used = sum(1 for row in ledger.trials if row.tick == trial.tick)
    if used >= ledger.max_trials_per_tick:
        raise ValueError("experiment_trial_cap")
    return replace(ledger, trials=(*ledger.trials, trial))


def _match_hypothesis(
    ledger: ExperimentLedger,
    operator: str | None,
    operand_a_id: str | None,
) -> ExperimentHypothesis | None:
    if operator is None:
        return None
    rows = [
        row
        for row in ledger.hypotheses
        if row.active
        and row.operator.value == operator
        and (operand_a_id is None or row.operand_a_id == operand_a_id)
    ]
    if not rows:
        return None
    rows.sort(key=lambda row: (row.created_tick, row.hypothesis_id))
    return rows[-1]


def score_remembered_experiment(
    ledger: ExperimentLedger,
    occurrence: object,
    *,
    tick: int,
) -> ExperimentLedger:
    """Update support from the objective class. Does not mint knowledge."""
    if type(ledger) is not ExperimentLedger:
        raise _fail("ledger", "invalid_type")
    if type(tick) is not int or tick < 0:
        raise _fail("tick", "invalid_tick")
    if getattr(occurrence, "kind", None) != "experiment_resolved":
        return ledger
    facts = getattr(occurrence, "public_facts", None)
    if not isinstance(facts, Mapping) or "operator" not in facts:
        return ledger
    outcome = facts.get("outcome_class")
    if type(outcome) is not str or outcome not in _OUTCOMES:
        return ledger
    mode = facts.get("discovery_mode")
    if mode not in {item.value for item in DiscoveryMode}:
        mode = DiscoveryMode.DELIBERATE.value
    provenance = getattr(occurrence, "provenance", None)
    event = getattr(provenance, "source_event_id", None)
    event_id = getattr(event, "value", None)
    if type(event_id) is not str or not event_id:
        return ledger
    if any(row.event_id == event_id for row in ledger.trials):
        return ledger
    used = sum(1 for row in ledger.trials if row.tick == tick)
    if used >= ledger.max_trials_per_tick:
        return ledger
    operator = facts.get("operator")
    other = getattr(occurrence, "other_entity_id", None)
    operand = getattr(other, "value", None)
    match = _match_hypothesis(
        ledger,
        operator if type(operator) is str else None,
        operand if type(operand) is str else None,
    )
    hypothesis_id = ""
    if match is not None:
        matched = outcome == match.predicted_outcome
        updated_row = replace(
            match,
            support=match.support + (1 if matched else 0),
            counter=match.counter + (0 if matched else 1),
            evidence_event_ids=(*match.evidence_event_ids, event_id),
        )
        ledger = replace(
            ledger,
            hypotheses=tuple(
                updated_row if row.hypothesis_id == match.hypothesis_id else row
                for row in ledger.hypotheses
            ),
        )
        hypothesis_id = match.hypothesis_id
        _LOG.debug(
            "experiment_hypothesis_scored support=%s counter=%s",
            updated_row.support,
            updated_row.counter,
        )
    return record_trial(
        ledger,
        ExperimentTrial(
            tick=tick,
            event_id=event_id,
            outcome_class=outcome,
            discovery_mode=str(mode),
            hypothesis_id=hypothesis_id,
        ),
    )


_DRAFT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "operator",
        "operand_a_id",
        "operand_b_id",
        "process_token",
        "predicted_outcome",
    }
)
_PHYSICS_KEYS: Final[frozenset[str]] = frozenset(
    {
        "damage",
        "delta",
        "harm",
        "harm_band",
        "invented_product",
        "item_kind",
        "law",
        "laws",
        "outcome_class",
        "probability",
        "product_id",
        "success_probability",
    }
)
_PROMPT_NAME: Final[str] = "experiment_hypothesis"
_PROMPT_VERSION: Final[str] = "v1"


@dataclass(frozen=True, slots=True)
class ExperimentAction:
    """Closed hypothesis draft. It is not a world command."""

    operator: ExperimentOperator
    operand_a_id: str
    process_token: ExperimentProcessToken
    predicted_outcome: str | None = None
    operand_b_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExperimentCompile:
    """One command, or a stable reject. The ledger is unchanged on reject."""

    ledger: ExperimentLedger
    command: Experiment | None = None
    reason: str | None = None
    hypothesis: ExperimentHypothesis | None = None


def _reject_draft(reason: str) -> tuple[None, str]:
    _LOG.warning("experiment_draft_rejected reason_code=%s", reason)
    return None, reason


def parse_experiment_draft(
    payload: object,
) -> tuple[ExperimentAction | None, str | None]:
    """Accept a closed draft. Physics keys reject the whole payload."""
    if not isinstance(payload, Mapping):
        return _reject_draft("experiment_draft_not_object")
    keys = set(payload)
    if keys & _PHYSICS_KEYS:
        return _reject_draft("experiment_draft_physics")
    if keys - _DRAFT_KEYS:
        return _reject_draft("experiment_draft_unknown_key")
    if "operator" not in payload or "operand_a_id" not in payload:
        return _reject_draft("experiment_draft_incomplete")
    if "process_token" not in payload:
        return _reject_draft("experiment_draft_incomplete")
    try:
        operator = ExperimentOperator(str(payload["operator"]))
        process_token = ExperimentProcessToken(str(payload["process_token"]))
    except ValueError:
        return _reject_draft("experiment_draft_closed_value")
    operand_a = payload["operand_a_id"]
    if type(operand_a) is not str or not operand_a:
        return _reject_draft("experiment_operand_not_observed")
    raw_b = payload.get("operand_b_id")
    if raw_b is not None and type(raw_b) is not str:
        return _reject_draft("experiment_draft_closed_value")
    operand_b = raw_b if raw_b else None
    if operator is ExperimentOperator.VARY_PROCESS:
        if process_token is ExperimentProcessToken.NONE or operand_b is not None:
            return _reject_draft("experiment_draft_closed_value")
    elif process_token is not ExperimentProcessToken.NONE or operand_b is None:
        return _reject_draft("experiment_draft_closed_value")
    predicted = payload.get("predicted_outcome")
    if predicted is not None and (
        type(predicted) is not str or predicted not in _OUTCOMES
    ):
        return _reject_draft("experiment_draft_closed_value")
    return (
        ExperimentAction(
            operator=operator,
            operand_a_id=operand_a,
            operand_b_id=operand_b,
            process_token=process_token,
            predicted_outcome=predicted if type(predicted) is str else None,
        ),
        None,
    )


def _deterministic_action(observation: object) -> ExperimentAction | None:
    operands = observed_experiment_operand_ids(observation)
    if len(operands) >= 2:
        return ExperimentAction(
            operator=ExperimentOperator.COMBINE,
            operand_a_id=operands[0],
            operand_b_id=operands[1],
            process_token=ExperimentProcessToken.NONE,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        )
    if len(operands) == 1:
        return ExperimentAction(
            operator=ExperimentOperator.VARY_PROCESS,
            operand_a_id=operands[0],
            process_token=ExperimentProcessToken.HARVEST,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        )
    return None


def _reusable(
    ledger: ExperimentLedger, observed: frozenset[str]
) -> ExperimentHypothesis | None:
    rows = [
        row
        for row in ledger.hypotheses
        if row.active
        and row.operand_a_id in observed
        and (row.operand_b_id is None or row.operand_b_id in observed)
    ]
    if not rows:
        return None
    rows.sort(key=lambda row: (row.created_tick, row.hypothesis_id))
    return rows[0]


def compile_experiment_command(
    owner_id: AgentId,
    ledger: ExperimentLedger,
    observation: object,
    *,
    draft: object | None = None,
    allow_provider: bool = False,
    proposals_this_tick: int = 0,
) -> ExperimentCompile:
    """Emit one Experiment command, or a stable reject. No physics fields."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not ExperimentLedger or ledger.owner_id != owner_id:
        raise _fail("ledger", "owner_mismatch")
    if type(allow_provider) is not bool:
        raise TypeError("allow_provider must be bool")
    if type(proposals_this_tick) is not int or proposals_this_tick < 0:
        raise _fail("proposals_this_tick", "invalid_count")
    tick = getattr(observation, "tick", 0)
    tick_value = tick if type(tick) is int and tick >= 0 else 0
    used = sum(1 for row in ledger.trials if row.tick == tick_value)
    if used + proposals_this_tick >= ledger.max_trials_per_tick:
        _LOG.warning(
            "experiment_draft_rejected reason_code=%s", "experiment_trial_cap"
        )
        return ExperimentCompile(ledger, reason="experiment_trial_cap")
    observed = frozenset(observed_experiment_operand_ids(observation))
    action: ExperimentAction | None
    if draft is None:
        existing = _reusable(ledger, observed)
        if existing is not None:
            command = Experiment(
                operator=existing.operator,
                operand_a_id=EntityId(existing.operand_a_id),
                operand_b_id=(
                    None
                    if existing.operand_b_id is None
                    else EntityId(existing.operand_b_id)
                ),
                process_token=existing.process_token,
                hypothesis_id=existing.hypothesis_id,
            )
            _LOG.info(
                "experiment_hypothesis_proposed operator=%s id_prefix=%s",
                existing.operator.value,
                existing.hypothesis_id[:12],
            )
            return ExperimentCompile(ledger, command=command, hypothesis=existing)
        action = _deterministic_action(observation)
        if action is None:
            return ExperimentCompile(ledger, reason="experiment_operands_insufficient")
    else:
        _LOG.debug(
            "experiment_hypothesis_prompt name=%s version=%s",
            _PROMPT_NAME,
            _PROMPT_VERSION,
        )
        if not allow_provider:
            _LOG.warning(
                "experiment_draft_rejected reason_code=%s",
                "experiment_provider_disabled",
            )
            return ExperimentCompile(ledger, reason="experiment_provider_disabled")
        if type(draft) is ExperimentAction:
            action = draft
        else:
            action, reason = parse_experiment_draft(draft)
            if action is None:
                return ExperimentCompile(ledger, reason=reason)
    assert action is not None
    if action.operand_a_id not in observed or (
        action.operand_b_id is not None and action.operand_b_id not in observed
    ):
        _LOG.warning(
            "experiment_draft_rejected reason_code=%s",
            "experiment_operand_not_observed",
        )
        return ExperimentCompile(ledger, reason="experiment_operand_not_observed")
    hypothesis_id = experiment_hypothesis_id(
        owner_id,
        action.operator,
        action.operand_a_id,
        action.operand_b_id,
        action.process_token,
    )
    tick = getattr(observation, "tick", 0)
    created_tick = tick if type(tick) is int and tick >= 0 else 0
    hypothesis = ExperimentHypothesis(
        owner_id=owner_id,
        hypothesis_id=hypothesis_id,
        operator=action.operator,
        operand_a_id=action.operand_a_id,
        operand_b_id=action.operand_b_id,
        process_token=action.process_token,
        predicted_outcome=action.predicted_outcome,
        created_tick=created_tick,
    )
    updated = admit_hypothesis(ledger, hypothesis)
    matches = [
        row for row in updated.hypotheses if row.hypothesis_id == hypothesis_id
    ]
    if not matches:
        return ExperimentCompile(updated, reason="experiment_hypothesis_evicted")
    stored = matches[0]
    command = Experiment(
        operator=stored.operator,
        operand_a_id=EntityId(stored.operand_a_id),
        operand_b_id=(
            None if stored.operand_b_id is None else EntityId(stored.operand_b_id)
        ),
        process_token=stored.process_token,
        hypothesis_id=stored.hypothesis_id,
    )
    _LOG.info(
        "experiment_hypothesis_proposed operator=%s id_prefix=%s",
        stored.operator.value,
        stored.hypothesis_id[:12],
    )
    return ExperimentCompile(
        updated, command=command, hypothesis=stored
    )
