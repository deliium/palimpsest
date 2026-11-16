"""Owner-scoped experiment hypotheses. Not laws and not practical knowledge."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
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

MAX_HYPOTHESIS_CONDITIONS: Final[int] = 8
MAX_HYPOTHESIS_REVISIONS: Final[int] = 32
MAX_HYPOTHESIS_EVIDENCE: Final[int] = 64
HYPOTHESIS_CONFIDENCE_PRIOR: Final[int] = 1


class HypothesisConditionSlot(StrEnum):
    """Ten closed observation slots a hypothesis may condition on."""

    LOCATION = "location"
    DAY_PHASE = "day_phase"
    WEATHER = "weather"
    HELD_ITEM_KIND = "held_item_kind"
    COUNTERPART = "counterpart"
    SEASON = "season"
    TEMPERATURE_BAND = "temperature_band"
    HAZARD = "hazard"
    ACTION = "action"
    CONCEPT = "concept"


class HypothesisSourceKind(StrEnum):
    """Descriptive provenance; a communicated claim is not evidence."""

    SELF_FORMULATED = "self_formulated"
    OBSERVED = "observed"
    REMEMBERED = "remembered"
    COMMUNICATED = "communicated"
    RECORDED = "recorded"
    UNKNOWN = "unknown"


class HypothesisStatus(StrEnum):
    """Owner-relative status; never an objective truth value."""

    PROVISIONAL = "provisional"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class HypothesisRevisionReason(StrEnum):
    """Closed reasons for one append-only hypothesis revision."""

    FORMULATED = "formulated"
    PREDICTION_REVISED = "prediction_revised"
    CONDITION_REVISED = "condition_revised"
    SUPPORT_ADDED = "support_added"
    CONTRADICTION_ADDED = "contradiction_added"
    CONFIDENCE_REVISED = "confidence_revised"
    SOURCE_ADOPTED = "source_adopted"
    TEST_FORMULATED = "test_formulated"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


def _require_condition_token(value: object) -> str:
    if type(value) is not str or not value:
        raise _fail("condition", "invalid_value")
    if len(value) > 128 or value != value.strip():
        raise _fail("condition", "invalid_value")
    if any(ord(char) < 32 for char in value):
        raise _fail("condition", "invalid_value")
    if "|" in value or "=" in value:
        raise _fail("condition", "invalid_separator")
    return value


def _require_evidence(field_name: str, values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise _fail(field_name, "invalid_type")
    if len(values) > MAX_HYPOTHESIS_EVIDENCE:
        raise _fail(field_name, "invalid_cap")
    for value in values:
        if type(value) is not str or not value:
            raise _fail(field_name, "invalid_type")
    return values


def confidence_milli_from_masses(
    support: int,
    counter: int,
    *,
    prior: int = HYPOTHESIS_CONFIDENCE_PRIOR,
) -> int:
    """Integer support ratio in milli; not a probability or calibration."""

    for name, value in (("support", support), ("counter", counter), ("prior", prior)):
        if isinstance(value, bool) or type(value) is not int or value < 0:
            raise _fail(name, "invalid_count")
    if prior < 1:
        raise _fail("prior", "invalid_count")
    value = ((support + prior) * 1000) // (support + counter + 2 * prior)
    return max(0, min(1000, value))


def derive_hypothesis_status(
    support: int,
    counter: int,
    *,
    min_evidence: int = 2,
) -> HypothesisStatus:
    """Derive the owner-relative status from retained evidence mass."""

    for name, value in (
        ("support", support),
        ("counter", counter),
        ("min_evidence", min_evidence),
    ):
        if isinstance(value, bool) or type(value) is not int or value < 0:
            raise _fail(name, "invalid_count")
    if min_evidence < 1:
        raise _fail("min_evidence", "invalid_count")
    if support + counter < min_evidence:
        return HypothesisStatus.PROVISIONAL
    if counter >= min_evidence and counter > support:
        return HypothesisStatus.CONTRADICTED
    if support >= min_evidence and support > counter:
        return HypothesisStatus.SUPPORTED
    return HypothesisStatus.INCONCLUSIVE


@dataclass(frozen=True, slots=True)
class HypothesisCondition:
    """One closed observation slot and its stable value token."""

    slot: HypothesisConditionSlot
    value_token: str

    def __post_init__(self) -> None:
        if type(self.slot) is not HypothesisConditionSlot:
            raise _fail("slot", "invalid_type")
        object.__setattr__(
            self, "value_token", _require_condition_token(self.value_token)
        )


@dataclass(frozen=True, slots=True)
class HypothesisClaim:
    """Claim components plus an optional predicted outcome class."""

    operator: ExperimentOperator
    operand_a_id: str
    operand_b_id: str | None
    process_token: ExperimentProcessToken
    predicted_outcome: ExperimentOutcomeClass | None = None

    def __post_init__(self) -> None:
        if type(self.operator) is not ExperimentOperator:
            raise _fail("operator", "invalid_type")
        if type(self.process_token) is not ExperimentProcessToken:
            raise _fail("process_token", "invalid_type")
        if type(self.operand_a_id) is not str or not self.operand_a_id:
            raise _fail("operand_a_id", "invalid_type")
        if self.operand_b_id is not None and type(self.operand_b_id) is not str:
            raise _fail("operand_b_id", "invalid_type")
        if self.predicted_outcome is not None and (
            type(self.predicted_outcome) is not ExperimentOutcomeClass
        ):
            raise _fail("predicted_outcome", "invalid_outcome")


@dataclass(frozen=True, slots=True)
class HypothesisRevision:
    """One append-only revision of an owner hypothesis."""

    revision_index: int
    tick: int
    reason: HypothesisRevisionReason
    claim: HypothesisClaim
    conditions: tuple[HypothesisCondition, ...] = ()
    confidence_milli: int = 0
    evidence_ref: str = ""

    def __post_init__(self) -> None:
        if type(self.revision_index) is not int or self.revision_index < 0:
            raise _fail("revision_index", "invalid_index")
        if type(self.tick) is not int or self.tick < 0:
            raise _fail("tick", "invalid_tick")
        if type(self.reason) is not HypothesisRevisionReason:
            raise _fail("reason", "invalid_type")
        if type(self.claim) is not HypothesisClaim:
            raise _fail("claim", "invalid_type")
        if not isinstance(self.conditions, tuple):
            raise _fail("conditions", "invalid_type")
        if len(self.conditions) > MAX_HYPOTHESIS_CONDITIONS:
            raise _fail("conditions", "invalid_cap")
        seen: set[HypothesisConditionSlot] = set()
        for condition in self.conditions:
            if type(condition) is not HypothesisCondition:
                raise _fail("conditions", "invalid_type")
            if condition.slot in seen:
                raise _fail("conditions", "duplicate")
            seen.add(condition.slot)
        if (
            isinstance(self.confidence_milli, bool)
            or type(self.confidence_milli) is not int
            or not 0 <= self.confidence_milli <= 1000
        ):
            raise _fail("confidence_milli", "invalid_range")
        if self.evidence_ref:
            if type(self.evidence_ref) is not str or not self.evidence_ref:
                raise _fail("evidence_ref", "invalid_type")


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
    causal_hypothesis_id: str = ""
    conditions: tuple[HypothesisCondition, ...] = ()
    confidence_milli: int | None = None
    counter_evidence_event_ids: tuple[str, ...] = ()
    source_kind: HypothesisSourceKind = HypothesisSourceKind.SELF_FORMULATED
    source_token: str = "self"
    status: HypothesisStatus | None = None
    revisions: tuple[HypothesisRevision, ...] = ()

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
        object.__setattr__(
            self,
            "evidence_event_ids",
            _require_evidence("evidence_event_ids", self.evidence_event_ids),
        )
        object.__setattr__(
            self,
            "counter_evidence_event_ids",
            _require_evidence(
                "counter_evidence_event_ids", self.counter_evidence_event_ids
            ),
        )
        if type(self.causal_hypothesis_id) is not str:
            raise _fail("causal_hypothesis_id", "invalid_type")
        object.__setattr__(
            self, "conditions", _validated_conditions(self.conditions)
        )
        if type(self.source_kind) is not HypothesisSourceKind:
            raise _fail("source_kind", "invalid_type")
        if type(self.source_token) is not str or not self.source_token:
            raise _fail("source_token", "invalid_type")
        if self.source_token != self.source_token.strip() or any(
            ord(char) < 32 for char in self.source_token
        ):
            raise _fail("source_token", "invalid_type")
        if (
            self.source_kind is not HypothesisSourceKind.SELF_FORMULATED
            and self.source_token == "self"
        ):
            raise _fail("source_token", "invalid_source_token")
        object.__setattr__(self, "revisions", _validated_revisions(self.revisions))
        expected_confidence = confidence_milli_from_masses(
            self.support, self.counter
        )
        if self.confidence_milli is None:
            object.__setattr__(self, "confidence_milli", expected_confidence)
        elif (
            isinstance(self.confidence_milli, bool)
            or type(self.confidence_milli) is not int
            or not 0 <= self.confidence_milli <= 1000
        ):
            raise _fail("confidence_milli", "invalid_range")
        expected_status = derive_hypothesis_status(self.support, self.counter)
        if self.status is None:
            object.__setattr__(self, "status", expected_status)
        elif type(self.status) is not HypothesisStatus:
            raise _fail("status", "invalid_type")

    @property
    def claim(self) -> HypothesisClaim:
        """Project the legacy claim fields into a closed claim value."""

        return HypothesisClaim(
            operator=self.operator,
            operand_a_id=self.operand_a_id,
            operand_b_id=self.operand_b_id,
            process_token=self.process_token,
            predicted_outcome=(
                None
                if self.predicted_outcome is None
                else ExperimentOutcomeClass(self.predicted_outcome)
            ),
        )


def _validated_conditions(
    conditions: object,
) -> tuple[HypothesisCondition, ...]:
    if not isinstance(conditions, tuple):
        raise _fail("conditions", "invalid_type")
    if len(conditions) > MAX_HYPOTHESIS_CONDITIONS:
        raise _fail("conditions", "invalid_cap")
    seen: set[HypothesisConditionSlot] = set()
    for condition in conditions:
        if type(condition) is not HypothesisCondition:
            raise _fail("conditions", "invalid_type")
        if condition.slot in seen:
            raise _fail("conditions", "duplicate")
        seen.add(condition.slot)
    return conditions


def _validated_revisions(
    revisions: object,
) -> tuple[HypothesisRevision, ...]:
    if not isinstance(revisions, tuple):
        raise _fail("revisions", "invalid_type")
    if len(revisions) > MAX_HYPOTHESIS_REVISIONS:
        raise _fail("revisions", "invalid_cap")
    previous = -1
    for revision in revisions:
        if type(revision) is not HypothesisRevision:
            raise _fail("revisions", "invalid_type")
        if revision.revision_index <= previous:
            raise _fail("revisions", "out_of_order")
        previous = revision.revision_index
    return revisions


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


def require_owner_experiment_ledger(
    ledger: object,
    owner_id: object,
    *,
    field_name: str,
) -> ExperimentLedger:
    """Return the ledger only when it belongs to the exact owner."""

    if type(ledger) is not ExperimentLedger:
        raise ValueError(f"{field_name}: invalid_type")
    if type(owner_id) is not AgentId or ledger.owner_id != owner_id:
        raise ValueError(f"{field_name}: owner_mismatch")
    return ledger


def admit_hypothesis(
    ledger: ExperimentLedger, hypothesis: ExperimentHypothesis
) -> ExperimentLedger:
    """Insert a hypothesis, evicting lowest confidence then oldest past the cap."""
    if type(hypothesis) is not ExperimentHypothesis:
        raise _fail("hypothesis", "invalid_type")
    if hypothesis.owner_id != ledger.owner_id:
        raise _fail("hypothesis", "owner_mismatch")
    if any(row.hypothesis_id == hypothesis.hypothesis_id for row in ledger.hypotheses):
        return ledger
    rows = [*ledger.hypotheses, hypothesis]
    evicted: ExperimentHypothesis | None = None
    while len(rows) > ledger.max_hypotheses:
        rows.sort(
            key=lambda row: (
                row.confidence_milli if row.confidence_milli is not None else 0,
                row.created_tick,
                row.hypothesis_id,
            )
        )
        evicted = rows.pop(0)
    _LOG.debug(
        "scientific_hypothesis_admitted hypothesis_prefix=%s",
        hypothesis.hypothesis_id[:12],
    )
    if evicted is not None:
        _LOG.debug(
            "scientific_hypothesis_evicted hypothesis_prefix=%s",
            evicted.hypothesis_id[:12],
        )
    return replace(ledger, hypotheses=tuple(rows))


def record_trial(ledger: ExperimentLedger, trial: ExperimentTrial) -> ExperimentLedger:
    """Append one trial unless this tick is already at the cap."""
    if type(trial) is not ExperimentTrial:
        raise _fail("trial", "invalid_type")
    used = sum(1 for row in ledger.trials if row.tick == trial.tick)
    if used >= ledger.max_trials_per_tick:
        raise ValueError("experiment_trial_cap")
    return replace(ledger, trials=(*ledger.trials, trial))


def _outcome_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, ExperimentOutcomeClass):
        return value.value
    if type(value) is str and value in _OUTCOMES:
        return value
    raise _fail("predicted_outcome", "invalid_outcome")


def _require_reason(value: object) -> HypothesisRevisionReason:
    if type(value) is not HypothesisRevisionReason:
        raise _fail("reason", "invalid_type")
    return value


def _trim_evidence(
    values: tuple[str, ...], event_id: str
) -> tuple[tuple[str, ...], bool]:
    appended = (*values, event_id)
    if len(appended) > MAX_HYPOTHESIS_EVIDENCE:
        return appended[-MAX_HYPOTHESIS_EVIDENCE:], True
    return appended, False


def append_revision(
    hypothesis: ExperimentHypothesis,
    *,
    reason: HypothesisRevisionReason,
    tick: int,
    claim: HypothesisClaim | None = None,
    conditions: tuple[HypothesisCondition, ...] | None = None,
    confidence_milli: int | None = None,
    evidence_ref: str = "",
) -> ExperimentHypothesis:
    """Append one monotonic revision and trim only the oldest past the cap."""
    if type(hypothesis) is not ExperimentHypothesis:
        raise _fail("hypothesis", "invalid_type")
    reason = _require_reason(reason)
    if type(tick) is not int or tick < 0:
        raise _fail("tick", "invalid_tick")
    active_claim = hypothesis.claim if claim is None else claim
    if type(active_claim) is not HypothesisClaim:
        raise _fail("claim", "invalid_type")
    active_conditions = (
        hypothesis.conditions if conditions is None else tuple(conditions)
    )
    confidence = (
        hypothesis.confidence_milli
        if confidence_milli is None
        else confidence_milli
    )
    previous = hypothesis.revisions[-1].revision_index if hypothesis.revisions else -1
    revision = HypothesisRevision(
        revision_index=previous + 1,
        tick=tick,
        reason=reason,
        claim=active_claim,
        conditions=active_conditions,
        confidence_milli=confidence if confidence is not None else 0,
        evidence_ref=evidence_ref,
    )
    revisions = (*hypothesis.revisions, revision)
    if len(revisions) > MAX_HYPOTHESIS_REVISIONS:
        _LOG.warning("scientific_hypothesis_evidence_capped")
        revisions = revisions[-MAX_HYPOTHESIS_REVISIONS:]
    _LOG.debug(
        "scientific_hypothesis_revised reason=%s revisions=%s",
        reason.value,
        len(revisions),
    )
    return replace(
        hypothesis,
        predicted_outcome=(
            None
            if active_claim.predicted_outcome is None
            else active_claim.predicted_outcome.value
        ),
        conditions=active_conditions,
        confidence_milli=revision.confidence_milli,
        revisions=revisions,
    )


def formulate_hypothesis(
    *,
    owner_id: AgentId,
    hypothesis_id: str,
    operator: ExperimentOperator,
    operand_a_id: str,
    process_token: ExperimentProcessToken,
    predicted_outcome: ExperimentOutcomeClass | str | None,
    operand_b_id: str | None = None,
    conditions: Sequence[HypothesisCondition] = (),
    source_kind: HypothesisSourceKind = HypothesisSourceKind.SELF_FORMULATED,
    source_token: str = "self",
    causal_hypothesis_id: str = "",
    created_tick: int = 0,
) -> ExperimentHypothesis:
    """Build a provisional hypothesis with one ``formulated`` revision."""

    predicted = _outcome_value(predicted_outcome)
    claim = HypothesisClaim(
        operator=operator,
        operand_a_id=operand_a_id,
        operand_b_id=operand_b_id,
        process_token=process_token,
        predicted_outcome=(
            None if predicted is None else ExperimentOutcomeClass(predicted)
        ),
    )
    condition_tuple = tuple(conditions)
    confidence = confidence_milli_from_masses(0, 0)
    revision = HypothesisRevision(
        revision_index=0,
        tick=created_tick,
        reason=HypothesisRevisionReason.FORMULATED,
        claim=claim,
        conditions=condition_tuple,
        confidence_milli=confidence,
    )
    return ExperimentHypothesis(
        owner_id=owner_id,
        hypothesis_id=hypothesis_id,
        operator=operator,
        operand_a_id=operand_a_id,
        operand_b_id=operand_b_id,
        process_token=process_token,
        predicted_outcome=_outcome_value(claim.predicted_outcome),
        conditions=condition_tuple,
        source_kind=source_kind,
        source_token=source_token,
        causal_hypothesis_id=causal_hypothesis_id,
        confidence_milli=confidence,
        status=HypothesisStatus.PROVISIONAL,
        created_tick=created_tick,
        revisions=(revision,),
    )


def _find_hypothesis(
    ledger: ExperimentLedger, hypothesis_id: str
) -> ExperimentHypothesis:
    for row in ledger.hypotheses:
        if row.hypothesis_id == hypothesis_id:
            return row
    raise ValueError("hypothesis_not_found")


def _replace_hypothesis(
    ledger: ExperimentLedger, updated: ExperimentHypothesis
) -> ExperimentLedger:
    return replace(
        ledger,
        hypotheses=tuple(
            updated if row.hypothesis_id == updated.hypothesis_id else row
            for row in ledger.hypotheses
        ),
    )


def revise_hypothesis(
    ledger: ExperimentLedger,
    hypothesis_id: str,
    *,
    reason: HypothesisRevisionReason,
    tick: int,
    predicted_outcome: ExperimentOutcomeClass | str | None = None,
    conditions: Sequence[HypothesisCondition] | None = None,
) -> ExperimentLedger:
    """Revise prediction or conditions without rewriting old revisions."""

    if type(ledger) is not ExperimentLedger:
        raise _fail("ledger", "invalid_type")
    row = _find_hypothesis(ledger, hypothesis_id)
    reason = _require_reason(reason)
    if row.status is HypothesisStatus.SUPERSEDED:
        raise ValueError("hypothesis_superseded")
    prediction = (
        row.predicted_outcome
        if predicted_outcome is None
        else _outcome_value(predicted_outcome)
    )
    claim = HypothesisClaim(
        operator=row.operator,
        operand_a_id=row.operand_a_id,
        operand_b_id=row.operand_b_id,
        process_token=row.process_token,
        predicted_outcome=(
            None if prediction is None else ExperimentOutcomeClass(prediction)
        ),
    )
    condition_tuple = row.conditions if conditions is None else tuple(conditions)
    updated = append_revision(
        row,
        reason=reason,
        tick=tick,
        claim=claim,
        conditions=condition_tuple,
        confidence_milli=row.confidence_milli,
    )
    updated = replace(
        updated,
        status=HypothesisStatus.PROVISIONAL,
        active=True,
    )
    return _replace_hypothesis(ledger, updated)


def _prediction_for_tick(
    hypothesis: ExperimentHypothesis, tick: int
) -> ExperimentOutcomeClass | None:
    for revision in reversed(hypothesis.revisions):
        if (
            revision.reason is HypothesisRevisionReason.TEST_FORMULATED
            and revision.tick <= tick
        ):
            return revision.claim.predicted_outcome
    if hypothesis.predicted_outcome is None:
        return None
    return ExperimentOutcomeClass(hypothesis.predicted_outcome)


def apply_test_outcome(
    ledger: ExperimentLedger,
    hypothesis_id: str,
    *,
    outcome_class: ExperimentOutcomeClass | str,
    event_id: str,
    tick: int,
    discovery_mode: DiscoveryMode | str,
) -> ExperimentLedger:
    """Append one trial result's evidence, confidence, status, and revision."""

    if type(ledger) is not ExperimentLedger:
        raise _fail("ledger", "invalid_type")
    if type(event_id) is not str or not event_id:
        raise _fail("event_id", "invalid_type")
    if type(tick) is not int or tick < 0:
        raise _fail("tick", "invalid_tick")
    try:
        observed = ExperimentOutcomeClass(outcome_class)
    except ValueError as error:
        raise _fail("outcome_class", "invalid_outcome") from error
    if isinstance(discovery_mode, DiscoveryMode):
        mode = discovery_mode
    elif type(discovery_mode) is str:
        try:
            mode = DiscoveryMode(discovery_mode)
        except ValueError as error:
            raise _fail("discovery_mode", "invalid_mode") from error
    else:
        raise _fail("discovery_mode", "invalid_mode")
    if any(trial.event_id == event_id for trial in ledger.trials):
        return ledger
    row = _find_hypothesis(ledger, hypothesis_id)
    if (
        event_id in row.evidence_event_ids
        or event_id in row.counter_evidence_event_ids
    ):
        return ledger
    prediction = _prediction_for_tick(row, tick)
    evidence = row.evidence_event_ids
    counter_evidence = row.counter_evidence_event_ids
    if prediction is None:
        support = row.support
        counter = row.counter
        reason = HypothesisRevisionReason.CONFIDENCE_REVISED
    elif observed is ExperimentOutcomeClass.UNEXPECTED:
        support = row.support
        counter = row.counter + 1
        counter_evidence, trimmed = _trim_evidence(counter_evidence, event_id)
        if trimmed:
            _LOG.warning("scientific_hypothesis_evidence_capped")
        reason = HypothesisRevisionReason.CONTRADICTION_ADDED
    elif observed is prediction:
        support = row.support + 1
        counter = row.counter
        evidence, trimmed = _trim_evidence(evidence, event_id)
        if trimmed:
            _LOG.warning("scientific_hypothesis_evidence_capped")
        reason = HypothesisRevisionReason.SUPPORT_ADDED
    else:
        support = row.support
        counter = row.counter + 1
        counter_evidence, trimmed = _trim_evidence(counter_evidence, event_id)
        if trimmed:
            _LOG.warning("scientific_hypothesis_evidence_capped")
        reason = HypothesisRevisionReason.CONTRADICTION_ADDED
    confidence = confidence_milli_from_masses(support, counter)
    status = derive_hypothesis_status(support, counter)
    updated = replace(
        row,
        support=support,
        counter=counter,
        evidence_event_ids=evidence,
        counter_evidence_event_ids=counter_evidence,
        confidence_milli=confidence,
        status=status,
    )
    updated = append_revision(
        updated,
        reason=reason,
        tick=tick,
        confidence_milli=confidence,
        evidence_ref=event_id,
    )
    _LOG.debug(
        "scientific_hypothesis_scored support=%s counter=%s status=%s",
        support,
        counter,
        status.value,
    )
    _LOG.debug(
        "scientific_hypothesis_trial_outcome discovery_mode=%s",
        mode.value,
    )
    return _replace_hypothesis(ledger, updated)


def supersede_hypothesis(
    ledger: ExperimentLedger,
    hypothesis_id: str,
    *,
    tick: int,
    evidence_ref: str = "",
) -> ExperimentLedger:
    """Terminally supersede a hypothesis while retaining its evidence."""

    row = _find_hypothesis(ledger, hypothesis_id)
    if row.status is HypothesisStatus.SUPERSEDED:
        return ledger
    updated = append_revision(
        row,
        reason=HypothesisRevisionReason.SUPERSEDED,
        tick=tick,
        evidence_ref=evidence_ref,
    )
    return _replace_hypothesis(
        ledger,
        replace(updated, status=HypothesisStatus.SUPERSEDED, active=False),
    )


def retire_hypothesis(
    ledger: ExperimentLedger,
    hypothesis_id: str,
    *,
    tick: int,
    evidence_ref: str = "",
) -> ExperimentLedger:
    """Retire a hypothesis; a later revision may reopen it."""

    row = _find_hypothesis(ledger, hypothesis_id)
    if row.status is HypothesisStatus.RETIRED:
        return ledger
    updated = append_revision(
        row,
        reason=HypothesisRevisionReason.RETIRED,
        tick=tick,
        evidence_ref=evidence_ref,
    )
    return _replace_hypothesis(
        ledger,
        replace(updated, status=HypothesisStatus.RETIRED, active=False),
    )


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
        ledger = apply_test_outcome(
            ledger,
            match.hypothesis_id,
            outcome_class=outcome,
            event_id=event_id,
            tick=tick,
            discovery_mode=str(mode),
        )
        updated_row = next(
            row
            for row in ledger.hypotheses
            if row.hypothesis_id == match.hypothesis_id
        )
        hypothesis_id = match.hypothesis_id
        _LOG.debug(
            "experiment_hypothesis_scored support=%s counter=%s",
            updated_row.support,
            updated_row.counter,
        )
        predicted = match.predicted_outcome
        if outcome == ExperimentOutcomeClass.UNEXPECTED.value and (
            predicted is None or predicted != outcome
        ):
            mode = DiscoveryMode.ACCIDENTAL.value
    _LOG.info(
        "experiment_discovery_mode discovery_mode=%s outcome_class=%s",
        mode,
        outcome,
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
    conditions: tuple[HypothesisCondition, ...] = (),
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
        _LOG.warning("experiment_draft_rejected reason_code=%s", "experiment_trial_cap")
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
        conditions=conditions,
    )
    updated = admit_hypothesis(ledger, hypothesis)
    matches = [row for row in updated.hypotheses if row.hypothesis_id == hypothesis_id]
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
    return ExperimentCompile(updated, command=command, hypothesis=stored)


_CONDITION_ATOM_ATTRS: Final[Mapping[HypothesisConditionSlot, tuple[str, ...]]] = {
    HypothesisConditionSlot.LOCATION: ("location_id",),
    HypothesisConditionSlot.DAY_PHASE: ("day_phase",),
    HypothesisConditionSlot.WEATHER: ("weather_condition", "weather"),
    HypothesisConditionSlot.HELD_ITEM_KIND: ("held_item_kind",),
    HypothesisConditionSlot.COUNTERPART: ("counterpart",),
    HypothesisConditionSlot.SEASON: ("season",),
    HypothesisConditionSlot.TEMPERATURE_BAND: ("temperature_band",),
    HypothesisConditionSlot.HAZARD: ("hazard_kinds", "hazard"),
    HypothesisConditionSlot.ACTION: ("action",),
    HypothesisConditionSlot.CONCEPT: ("concept", "concepts"),
}


def _token_values(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, StrEnum):
        return (value.value,)
    if type(value) is str:
        return (value,) if value else ()
    raw = getattr(value, "value", None)
    if type(raw) is str and raw:
        return (raw,)
    if isinstance(value, (str, bytes)):
        return ()
    if isinstance(value, Sequence):
        tokens: list[str] = []
        for item in value:
            tokens.extend(_token_values(item))
        return tuple(tokens)
    return ()


def _first_attr(observation: object, names: Sequence[str]) -> object:
    for name in names:
        value = getattr(observation, name, None)
        if value is not None:
            return value
    return None


def observed_condition_tokens(
    observation: object,
) -> Mapping[HypothesisConditionSlot, tuple[str, ...]]:
    """Read only public observation attributes into closed condition tokens."""

    observed: dict[HypothesisConditionSlot, tuple[str, ...]] = {}
    self_body = getattr(observation, "self_body", None)
    for slot, names in _CONDITION_ATOM_ATTRS.items():
        value = _first_attr(observation, names)
        if value is None and self_body is not None:
            value = _first_attr(self_body, names)
        tokens = _token_values(value)
        if tokens:
            observed[slot] = tokens
    location = getattr(observation, "location_id", None)
    if location is None and self_body is not None:
        location = getattr(self_body, "location_id", None)
    if location is not None:
        observed[HypothesisConditionSlot.LOCATION] = _token_values(location)
    return observed


def conditions_hold(
    conditions: Sequence[HypothesisCondition], observation: object
) -> bool:
    """Every condition must appear in the owner's current observation."""

    observed = observed_condition_tokens(observation)
    for condition in conditions:
        if condition.value_token not in observed.get(condition.slot, ()):
            return False
    return True


def _conditions_from_observation(
    observation: object,
) -> tuple[HypothesisCondition, ...]:
    rows: list[HypothesisCondition] = []
    for slot, tokens in observed_condition_tokens(observation).items():
        if len(rows) >= MAX_HYPOTHESIS_CONDITIONS:
            break
        if not tokens:
            continue
        try:
            rows.append(HypothesisCondition(slot, tokens[0]))
        except ValueError:
            continue
    return tuple(rows)


def _causal_link(
    causal_model: object, owner_id: AgentId, observation: object
) -> tuple[str, HypothesisSourceKind, str] | None:
    if causal_model is None:
        return None
    if getattr(causal_model, "owner_id", None) != owner_id:
        raise _fail("causal_model", "owner_mismatch")
    observed = observed_condition_tokens(observation)
    candidates: list[object] = []
    for hypothesis in getattr(causal_model, "hypotheses", ()):
        atoms = getattr(hypothesis, "atoms", ())
        if not atoms:
            continue
        matched = True
        for atom in atoms:
            slot = getattr(getattr(atom, "slot", None), "value", None)
            value = getattr(atom, "value", None)
            if type(slot) is not str or value not in observed.get(
                HypothesisConditionSlot(slot), ()
            ):
                matched = False
                break
        if matched:
            candidates.append(hypothesis)
    if not candidates:
        return None
    candidates.sort(
        key=lambda row: (-float(getattr(row, "confidence", 0.0)), getattr(row, "hypothesis_id", ""))  # noqa: E501
    )
    chosen = candidates[0]
    provenance = getattr(getattr(chosen, "provenance_kind", None), "value", "")
    if provenance == "memory":
        source_kind = HypothesisSourceKind.REMEMBERED
        source_token = "memory"
    else:
        source_kind = HypothesisSourceKind.OBSERVED
        source_token = "observation"
    return str(getattr(chosen, "hypothesis_id", "")), source_kind, source_token


def _command_for(hypothesis: ExperimentHypothesis) -> Experiment:
    return Experiment(
        operator=hypothesis.operator,
        operand_a_id=EntityId(hypothesis.operand_a_id),
        operand_b_id=(
            None
            if hypothesis.operand_b_id is None
            else EntityId(hypothesis.operand_b_id)
        ),
        process_token=hypothesis.process_token,
        hypothesis_id=hypothesis.hypothesis_id,
    )


def _testable(
    ledger: ExperimentLedger, tick: int, observation: object
) -> list[ExperimentHypothesis]:
    tested = {
        trial.hypothesis_id
        for trial in ledger.trials
        if trial.tick == tick and trial.hypothesis_id
    }
    return [
        row
        for row in ledger.hypotheses
        if row.active
        and row.status
        not in {HypothesisStatus.SUPERSEDED, HypothesisStatus.RETIRED}
        and row.predicted_outcome is not None
        and row.hypothesis_id not in tested
        and conditions_hold(row.conditions, observation)
    ]


def compile_scientific_test(
    owner_id: AgentId,
    ledger: ExperimentLedger,
    observation: object,
    *,
    hypothesis_id: str | None = None,
    formulate_if_missing: bool = False,
    causal_model: object | None = None,
) -> ExperimentCompile:
    """Replace a default Wait with one existing ``Experiment`` command."""

    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not ExperimentLedger or ledger.owner_id != owner_id:
        raise _fail("ledger", "owner_mismatch")
    if type(formulate_if_missing) is not bool:
        raise TypeError("formulate_if_missing must be bool")
    tick_raw = getattr(observation, "tick", 0)
    tick = tick_raw if type(tick_raw) is int and tick_raw >= 0 else 0
    used = sum(1 for row in ledger.trials if row.tick == tick)
    if used >= ledger.max_trials_per_tick:
        _LOG.warning("scientific_test_skipped reason_code=experiment_trial_cap")
        return ExperimentCompile(ledger, reason="experiment_trial_cap")

    selected: ExperimentHypothesis | None = None
    if hypothesis_id is not None:
        rows = [row for row in ledger.hypotheses if row.hypothesis_id == hypothesis_id]
        if rows and rows[0] in _testable(ledger, tick, observation):
            selected = rows[0]
    else:
        candidates = _testable(ledger, tick, observation)
        if candidates:
            candidates.sort(
                key=lambda row: (
                    0 if row.counter > row.support else 1,
                    row.created_tick,
                    row.hypothesis_id,
                )
            )
            selected = candidates[0]

    if selected is None and formulate_if_missing:
        active_with_prediction = [
            row
            for row in ledger.hypotheses
            if row.active and row.predicted_outcome is not None
        ]
        if not active_with_prediction:
            action = _deterministic_action(observation)
            if action is not None:
                new_id = experiment_hypothesis_id(
                    owner_id,
                    action.operator,
                    action.operand_a_id,
                    action.operand_b_id,
                    action.process_token,
                )
                created = formulate_hypothesis(
                    owner_id=owner_id,
                    hypothesis_id=new_id,
                    operator=action.operator,
                    operand_a_id=action.operand_a_id,
                    operand_b_id=action.operand_b_id,
                    process_token=action.process_token,
                    predicted_outcome=action.predicted_outcome,
                    conditions=_conditions_from_observation(observation),
                    source_kind=HypothesisSourceKind.OBSERVED,
                    source_token="observation",
                    created_tick=tick,
                )
                ledger = admit_hypothesis(ledger, created)
                rows = [
                    row
                    for row in ledger.hypotheses
                    if row.hypothesis_id == new_id
                ]
                if rows:
                    selected = rows[0]

    if selected is None:
        _LOG.warning(
            "scientific_test_skipped reason_code=scientific_hypothesis_untestable"
        )
        return ExperimentCompile(ledger, reason="scientific_hypothesis_untestable")

    if causal_model is not None:
        link = _causal_link(causal_model, owner_id, observation)
        if link is not None:
            causal_id, source_kind, source_token = link
            selected = replace(
                selected,
                causal_hypothesis_id=causal_id,
                source_kind=source_kind,
                source_token=source_token,
            )

    tested = append_revision(
        selected,
        reason=HypothesisRevisionReason.TEST_FORMULATED,
        tick=tick,
        claim=selected.claim,
        conditions=selected.conditions,
        confidence_milli=selected.confidence_milli,
    )
    ledger = _replace_hypothesis(ledger, tested)
    _LOG.info(
        "scientific_test_proposed hypothesis_prefix=%s",
        tested.hypothesis_id[:12],
    )
    return ExperimentCompile(
        ledger, command=_command_for(tested), hypothesis=tested
    )


@dataclass(frozen=True, slots=True)
class ExperimentCitation:
    """Event citation for a later Tell or Inscribe. Not a command."""

    event_ref: str
    technique_label: str


def _owner_remembers_event(
    owner_id: AgentId, traces: Sequence[object], event_id: str
) -> bool:
    for trace in traces:
        if getattr(trace, "owner_id", None) != owner_id:
            continue
        source = getattr(getattr(trace, "provenance", None), "observed_source_id", None)
        if getattr(source, "value", None) == event_id:
            return True
    return False


def cite_experiment_event(
    owner_id: AgentId,
    traces: Sequence[object],
    event_id: str,
    technique_token: str,
    *,
    channel: str,
) -> ExperimentCitation | None:
    """Cite ``evt:{id}`` only after this owner remembers the event."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if channel not in {"teach", "record"}:
        raise _fail("channel", "invalid_channel")
    if type(technique_token) is not str:
        raise _fail("technique_token", "invalid_type")
    if not _owner_remembers_event(owner_id, traces, event_id):
        return None
    label = technique_token
    if not technique_token:
        _LOG.debug("experiment_label_skipped event_id=%s", event_id)
        label = ""
    if channel == "teach":
        _LOG.debug("experiment_teach_cited event_id=%s", event_id)
    else:
        _LOG.debug("experiment_record_cited event_id=%s", event_id)
    return ExperimentCitation(event_ref=f"evt:{event_id}", technique_label=label)


_LEARN_CLASSES: Final[frozenset[str]] = frozenset(
    {"success", "partial_success", "unexpected"}
)


def _skip_learn(reason: str) -> None:
    _LOG.debug("experiment_learn_skipped reason_code=%s", reason)


def _repeated_class(
    ledger: ExperimentLedger, hypothesis_id: str
) -> tuple[str, str, str] | None:
    """Return class, event id, and discovery mode once the threshold is met."""
    counts: dict[str, int] = {}
    latest: dict[str, tuple[str, str]] = {}
    for trial in ledger.trials:
        if trial.hypothesis_id != hypothesis_id:
            continue
        counts[trial.outcome_class] = counts.get(trial.outcome_class, 0) + 1
        latest[trial.outcome_class] = (trial.event_id, trial.discovery_mode)
    for outcome, count in counts.items():
        if outcome not in _LEARN_CLASSES:
            continue
        if count >= ledger.repeat_threshold:
            event_id, mode = latest[outcome]
            return outcome, event_id, mode
    return None


def commit_experiment_learning(
    experiment_ledger: ExperimentLedger,
    knowledge_ledger: object,
    *,
    genealogy_active: bool,
    enabled_kinds: Sequence[str],
    tick: int,
) -> tuple[ExperimentLedger, object]:
    """Mint at most one practical-knowledge entry from repeated outcomes."""
    if type(experiment_ledger) is not ExperimentLedger:
        raise _fail("ledger", "invalid_type")
    if type(genealogy_active) is not bool:
        raise TypeError("genealogy_active must be bool")
    if not genealogy_active or not experiment_ledger.learn_into_genealogy:
        _skip_learn("channel_off")
        return experiment_ledger, knowledge_ledger
    eligible_waiting = False
    for hypothesis in experiment_ledger.hypotheses:
        repeated = _repeated_class(experiment_ledger, hypothesis.hypothesis_id)
        if repeated is None:
            classes = {
                trial.outcome_class
                for trial in experiment_ledger.trials
                if trial.hypothesis_id == hypothesis.hypothesis_id
            }
            if classes & _LEARN_CLASSES:
                eligible_waiting = True
            continue
        _outcome, event_id, mode = repeated
        from agents.cognition.practical_knowledge import (
            PracticalKnowledgeKind,
            mint_experiment_practical_knowledge,
        )

        if hypothesis.process_token is ExperimentProcessToken.BUILD:
            kind = PracticalKnowledgeKind.BUILDING_METHOD
        elif hypothesis.process_token in {
            ExperimentProcessToken.HARVEST,
            ExperimentProcessToken.STORE,
        }:
            kind = PracticalKnowledgeKind.FORAGING_METHOD
        else:
            kind = PracticalKnowledgeKind.CRAFTING_PROCESS
        token = f"exp-{hypothesis.operator.value}-{hypothesis.process_token.value}"
        updated, entry_id = mint_experiment_practical_knowledge(
            knowledge_ledger,  # type: ignore[arg-type]
            enabled_kinds=enabled_kinds,
            tick=tick,
            kind=kind,
            technique_token=token,
            evidence_refs=(
                f"evt:{event_id}",
                f"hypothesis:{hypothesis.hypothesis_id}",
                f"discovery_mode:{mode}",
            ),
            fingerprint=(f"cue:experiment:{_outcome}",),
        )
        if entry_id is None:
            _skip_learn("channel_off")
            return experiment_ledger, knowledge_ledger
        _LOG.info(
            "experiment_learned entry_id=%s discovery_mode=%s",
            entry_id,
            mode,
        )
        return experiment_ledger, updated
    if eligible_waiting:
        _skip_learn("threshold")
    else:
        _skip_learn("class_ineligible")
    return experiment_ledger, knowledge_ledger
