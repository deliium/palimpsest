"""Owner-scoped counterfactual scenarios from records the agent already holds.

The predicted alternative comes from subjective transition rules. This module
never reads simulation history, analysis metrics, or world authority, and it
never imports a provider facade.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass, fields
from decimal import Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.models import _EFFECT_QUANTUM, ActionDirection
from agents.cognition.reflection import DecisionOutcomeCode
from agents.models import AgentId
from memory.models import MemorySourceKind
from world.identifiers import (
    require_bounded_text,
    require_exact_nonneg_int,
    require_ordered_unique,
    require_stable_id,
)

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.counterfactual")

COUNTERFACTUAL_POLICY_VERSION: Final[str] = "counterfactual-v1"
_DECISION_PREFIX: Final[str] = "rd-"
_SCENARIO_PREFIX: Final[str] = "cf-"
_DEFAULT_MAX_DECISIONS: Final[int] = 4
_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.5
_DEFAULT_DIRECTION_BONUS: Final[float] = 0.2
_DEFAULT_MAX_LLM_CALLS: Final[int] = 1
_DEFAULT_MAX_TOKENS: Final[int] = 256
_MAX_TEXT: Final[int] = 64
_COMMUNICATION_KINDS: Final[frozenset[str]] = frozenset({"talked", "asked", "told"})
_OBJECTIVE_TYPE_NAMES: Final[frozenset[str]] = frozenset(
    {"World" + "Event", "World" + "State", "Physical" + "Rules"}
)
_OBJECTIVE_PREFIXES: Final[tuple[str, ...]] = (
    "world.events",
    "world.models",
    "world._",
)


class CounterfactualProvenanceKind(StrEnum):
    """Closed provenance. An alternative is imagined, never observed."""

    IMAGINED_ALTERNATIVE = "imagined_alternative"


class CounterfactualAffectCode(StrEnum):
    """Closed regret-like affect. This is not an emotion catalog member."""

    REGRET = "regret"
    RELIEF = "relief"
    NEUTRAL = "neutral"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "counterfactual_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _type_error(field_name: str, code: str) -> TypeError:
    _LOG.error(
        "counterfactual_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return TypeError(f"{field_name}: {code}")


def _quantize(value: float) -> float:
    steps = round(value / _EFFECT_QUANTUM)
    if steps == 0:
        return 0.0
    quantized = float(Decimal(steps) * Decimal(str(_EFFECT_QUANTUM)))
    return 0.0 if quantized == 0.0 else quantized


def _positive_int(field_name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 1:
        raise _fail(field_name, "not_positive")
    return value


def _nonnegative_int(field_name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise _fail(field_name, "not_nonnegative")
    return value


def _unit(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_unit_interval")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise _fail(field_name, "not_unit_interval")
    quantized = _quantize(number)
    if quantized < 0.0 or quantized > 1.0:
        raise _fail(field_name, "not_unit_interval")
    return quantized


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return _quantize(number)


def _reject_objective(value: object, name: str) -> None:
    if value is None or isinstance(value, (str, bytes, bool, int, float)):
        return
    type_name = type(value).__name__
    module = type(value).__module__
    if type_name in _OBJECTIVE_TYPE_NAMES or module.startswith(_OBJECTIVE_PREFIXES):
        raise TypeError(f"{name} is not a subjective input")
    if isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _reject_objective(item, f"{name}[{index}]")


def _reject_fields(value: object) -> None:
    for field in fields(value):
        _reject_objective(getattr(value, field.name), field.name)


def decision_id_for(
    *,
    owner_id: AgentId,
    tick: int,
    command_kind: str,
    outcome_code: DecisionOutcomeCode,
    place_id: str | None,
    counterpart_id: str | None,
    memory_id: str | None,
    goal_ids: tuple[str, ...],
) -> str:
    """sha256 of the remembered record. No RNG, wall clock, or builtin hash."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(outcome_code) is not DecisionOutcomeCode:
        raise _fail("outcome_code", "invalid_type")
    place = "" if place_id is None else place_id
    counterpart = "" if counterpart_id is None else counterpart_id
    memory = "" if memory_id is None else memory_id
    goals = ",".join(goal_ids)
    material = (
        f"{COUNTERFACTUAL_POLICY_VERSION}|{owner_id.value}|{tick}|{command_kind}|"
        f"{outcome_code.value}|{place}|{counterpart}|{memory}|{goals}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{_DECISION_PREFIX}{digest[:48]}"


def scenario_id_for(
    *,
    owner_id: AgentId,
    decision_id: str,
    direction: ActionDirection,
    target_id: str | None,
) -> str:
    """sha256 of owner, decision, alternative direction, and target."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(direction) is not ActionDirection:
        raise _fail("direction", "invalid_type")
    target = "" if target_id is None else target_id
    material = (
        f"{COUNTERFACTUAL_POLICY_VERSION}|{owner_id.value}|{decision_id}|"
        f"{direction.value}|{target}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{_SCENARIO_PREFIX}{digest[:48]}"


@dataclass(frozen=True, slots=True)
class CounterfactualPolicy:
    """``counterfactual-v1`` knobs. Not a runner JSON key."""

    version: str = COUNTERFACTUAL_POLICY_VERSION
    max_decisions: int = _DEFAULT_MAX_DECISIONS
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE
    direction_bonus: float = _DEFAULT_DIRECTION_BONUS
    max_llm_calls: int = _DEFAULT_MAX_LLM_CALLS
    max_tokens: int = _DEFAULT_MAX_TOKENS
    allow_provider: bool = False

    def __post_init__(self) -> None:
        _reject_fields(self)
        if self.version != COUNTERFACTUAL_POLICY_VERSION:
            raise _fail("version", "unsupported")
        max_decisions = _positive_int("max_decisions", self.max_decisions)
        min_confidence = _unit("min_confidence", self.min_confidence)
        direction_bonus = _unit("direction_bonus", self.direction_bonus)
        max_llm_calls = _nonnegative_int("max_llm_calls", self.max_llm_calls)
        max_tokens = _nonnegative_int("max_tokens", self.max_tokens)
        if type(self.allow_provider) is not bool:
            raise _fail("allow_provider", "invalid_type")
        object.__setattr__(self, "max_decisions", max_decisions)
        object.__setattr__(self, "min_confidence", min_confidence)
        object.__setattr__(self, "direction_bonus", direction_bonus)
        object.__setattr__(self, "max_llm_calls", max_llm_calls)
        object.__setattr__(self, "max_tokens", max_tokens)
        _LOG.debug(
            "counterfactual_policy_constructed policy_version=%s "
            "max_decisions=%s min_confidence=%s",
            self.version,
            max_decisions,
            min_confidence,
        )


def default_counterfactual_policy(
    *, allow_provider: bool = False
) -> CounterfactualPolicy:
    """Return ``counterfactual-v1``. Provider ranking stays off unless opted in."""
    if type(allow_provider) is not bool:
        raise _fail("allow_provider", "invalid_type")
    return CounterfactualPolicy(allow_provider=allow_provider)


@dataclass(frozen=True, slots=True)
class CounterfactualAffect:
    """Regret-like affect carried on a scenario. Not an emotion kind."""

    code: CounterfactualAffectCode
    magnitude: float

    def __post_init__(self) -> None:
        _reject_fields(self)
        if type(self.code) is not CounterfactualAffectCode:
            raise _type_error("code", "invalid_affect")
        object.__setattr__(self, "magnitude", _unit("magnitude", self.magnitude))


@dataclass(frozen=True, slots=True)
class CounterfactualState:
    """Latest affect code and magnitude carried by the runtime. Not an emotion."""

    code: CounterfactualAffectCode = CounterfactualAffectCode.NEUTRAL
    magnitude: float = 0.0

    def __post_init__(self) -> None:
        _reject_fields(self)
        if type(self.code) is not CounterfactualAffectCode:
            raise _type_error("code", "invalid_affect")
        object.__setattr__(self, "magnitude", _unit("magnitude", self.magnitude))


@dataclass(frozen=True, slots=True)
class PredictedAlternativeOutcome:
    """Subjective alternative value. No free-text narrative."""

    direction: ActionDirection
    value: float
    magnitude: float

    def __post_init__(self) -> None:
        _reject_fields(self)
        if type(self.direction) is not ActionDirection:
            raise _fail("direction", "invalid_type")
        object.__setattr__(self, "value", _finite("value", self.value))
        object.__setattr__(self, "magnitude", _unit("magnitude", self.magnitude))


@dataclass(frozen=True, slots=True)
class RememberedDecision:
    """One owner command remembered from a subjective observation. Not an event."""

    decision_id: str
    owner_id: AgentId
    tick: int
    command_kind: str
    outcome_code: DecisionOutcomeCode
    place_id: str | None = None
    counterpart_id: str | None = None
    memory_id: str | None = None
    goal_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_fields(self)
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        try:
            tick = require_exact_nonneg_int("tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "not_nonnegative") from exc
        object.__setattr__(self, "tick", tick)
        try:
            command_kind = require_bounded_text(
                "command_kind", self.command_kind, max_length=_MAX_TEXT
            )
        except ValueError as exc:
            raise _fail("command_kind", "invalid_value") from exc
        object.__setattr__(self, "command_kind", command_kind)
        if type(self.outcome_code) is not DecisionOutcomeCode:
            raise _fail("outcome_code", "invalid_type")
        place_id = _optional_id("place_id", self.place_id)
        counterpart_id = _optional_id("counterpart_id", self.counterpart_id)
        memory_id = _optional_id("memory_id", self.memory_id)
        goal_ids = _goal_ids(self.goal_ids)
        object.__setattr__(self, "place_id", place_id)
        object.__setattr__(self, "counterpart_id", counterpart_id)
        object.__setattr__(self, "memory_id", memory_id)
        object.__setattr__(self, "goal_ids", goal_ids)
        expected = decision_id_for(
            owner_id=self.owner_id,
            tick=tick,
            command_kind=command_kind,
            outcome_code=self.outcome_code,
            place_id=place_id,
            counterpart_id=counterpart_id,
            memory_id=memory_id,
            goal_ids=goal_ids,
        )
        if self.decision_id != expected:
            raise _fail("decision_id", "id_mismatch")
        _LOG.debug(
            "counterfactual_constructed owner_id=%s policy_version=%s "
            "max_decisions=%s min_confidence=%s",
            self.owner_id.value,
            COUNTERFACTUAL_POLICY_VERSION,
            _DEFAULT_MAX_DECISIONS,
            _DEFAULT_MIN_CONFIDENCE,
        )


@dataclass(frozen=True, slots=True)
class CounterfactualScenario:
    """One frozen alternative. Not a memory, belief, future, or observation."""

    owner_id: AgentId
    scenario_id: str
    decision: RememberedDecision
    alternative_direction: ActionDirection
    target_id: str | None
    predicted_outcome: PredictedAlternativeOutcome
    confidence: float
    goal_ids: tuple[str, ...]
    emotional_impact: CounterfactualAffect
    provenance: CounterfactualProvenanceKind

    def __post_init__(self) -> None:
        _reject_fields(self)
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.decision) is not RememberedDecision:
            raise _fail("decision", "invalid_type")
        if self.decision.owner_id != self.owner_id:
            _LOG.error(
                "counterfactual_owner_mismatch owner_id=%s reason_code=owner_mismatch",
                self.owner_id.value,
            )
            raise _fail("decision", "owner_mismatch")
        if type(self.alternative_direction) is not ActionDirection:
            raise _fail("alternative_direction", "invalid_type")
        target_id = _optional_id("target_id", self.target_id)
        object.__setattr__(self, "target_id", target_id)
        if type(self.predicted_outcome) is not PredictedAlternativeOutcome:
            raise _fail("predicted_outcome", "invalid_type")
        if self.predicted_outcome.direction is not self.alternative_direction:
            raise _fail("predicted_outcome", "direction_mismatch")
        confidence = _unit("confidence", self.confidence)
        object.__setattr__(self, "confidence", confidence)
        goal_ids = _goal_ids(self.goal_ids)
        object.__setattr__(self, "goal_ids", goal_ids)
        if type(self.emotional_impact) is not CounterfactualAffect:
            raise _fail("emotional_impact", "invalid_type")
        if type(self.provenance) is not CounterfactualProvenanceKind:
            raise _type_error("provenance", "invalid_provenance")
        expected = scenario_id_for(
            owner_id=self.owner_id,
            decision_id=self.decision.decision_id,
            direction=self.alternative_direction,
            target_id=target_id,
        )
        if self.scenario_id != expected:
            raise _fail("scenario_id", "id_mismatch")
        _LOG.debug(
            "counterfactual_constructed owner_id=%s policy_version=%s "
            "max_decisions=%s min_confidence=%s",
            self.owner_id.value,
            COUNTERFACTUAL_POLICY_VERSION,
            _DEFAULT_MAX_DECISIONS,
            _DEFAULT_MIN_CONFIDENCE,
        )


def assemble_counterfactual_scenarios(
    scenarios: Sequence[CounterfactualScenario],
) -> tuple[CounterfactualScenario, ...]:
    """Freeze an ordered scenario tuple and reject duplicate ids."""
    _reject_objective(scenarios, "scenarios")
    if isinstance(scenarios, (set, frozenset, str, bytes)) or not isinstance(
        scenarios, Sequence
    ):
        raise _fail("scenarios", "not_ordered")
    items = tuple(scenarios)
    seen: set[str] = set()
    for item in items:
        _reject_objective(item, "scenarios")
        if type(item) is not CounterfactualScenario:
            raise _fail("scenarios", "invalid_type")
        if item.scenario_id in seen:
            raise _fail("scenarios", "duplicate_scenario_id")
        seen.add(item.scenario_id)
    return items


def _optional_id(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    try:
        return require_stable_id(field_name, value)
    except ValueError as exc:
        raise _fail(field_name, "invalid_value") from exc


def _goal_ids(values: object) -> tuple[str, ...]:
    try:
        raw = require_ordered_unique("goal_ids", values, item_type=str)
    except TypeError as exc:
        raise _fail("goal_ids", "not_ordered") from exc
    except ValueError as exc:
        raise _fail("goal_ids", "duplicate") from exc
    checked: list[str] = []
    for item in raw:
        try:
            checked.append(require_stable_id("goal_ids", item))
        except ValueError as exc:
            raise _fail("goal_ids", "invalid_value") from exc
    return tuple(checked)


def communication_counterpart(
    occurrences: Sequence[object], owner_entity_id: str | None
) -> str | None:
    """Other party on a talked, asked, or told occurrence. No event lookup."""
    _reject_objective(occurrences, "occurrences")
    if isinstance(occurrences, (str, bytes)) or not isinstance(occurrences, Sequence):
        raise _fail("occurrences", "not_ordered")
    for occurrence in occurrences:
        _reject_objective(occurrence, "occurrences")
        kind = getattr(occurrence, "kind", None)
        if kind not in _COMMUNICATION_KINDS:
            continue
        actor = _id_value(getattr(occurrence, "actor_id", None))
        other = _id_value(getattr(occurrence, "other_entity_id", None))
        if owner_entity_id is not None and actor == owner_entity_id and other:
            return other
        if owner_entity_id is not None and other == owner_entity_id and actor:
            return actor
        if actor is not None and actor != owner_entity_id:
            return actor
        if other is not None and other != owner_entity_id:
            return other
    return None


def direct_observation_memory_id(
    traces: Sequence[object], command_kind: str
) -> str | None:
    """Id of the committed direct trace whose concept equals the command kind."""
    _reject_objective(traces, "traces")
    if isinstance(traces, (str, bytes)) or not isinstance(traces, Sequence):
        raise _fail("traces", "not_ordered")
    for trace in traces:
        _reject_objective(trace, "traces")
        provenance = getattr(trace, "provenance", None)
        if provenance is None:
            continue
        if getattr(provenance, "kind", None) is not MemorySourceKind.DIRECT_OBSERVATION:
            continue
        concepts = getattr(trace, "concepts", ())
        matched = any(
            getattr(concept, "concept", None) == command_kind for concept in concepts
        )
        if matched:
            memory_id = getattr(trace, "memory_id", None)
            value = _id_value(memory_id)
            if value is not None:
                return value
    return None


def trim_remembered_decisions(
    store: tuple[RememberedDecision, ...] | None,
    decision: RememberedDecision,
    *,
    max_decisions: int,
) -> tuple[RememberedDecision, ...]:
    """Keep the newest ``max_decisions`` records. Disabled stores stay untouched."""
    _reject_objective(decision, "decision")
    if type(decision) is not RememberedDecision:
        raise _fail("decision", "invalid_type")
    cap = _positive_int("max_decisions", max_decisions)
    current = () if store is None else store
    if isinstance(current, (str, bytes)) or not isinstance(current, tuple):
        raise _fail("store", "not_ordered")
    kept = (*current, decision)
    if len(kept) > cap:
        kept = kept[-cap:]
    return kept


def _id_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    nested = getattr(value, "value", None)
    if isinstance(nested, str):
        return nested
    return None
