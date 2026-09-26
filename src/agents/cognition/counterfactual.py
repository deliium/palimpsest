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

from agents.cognition.models import (
    _EFFECT_QUANTUM,
    ActionDirection,
    CognitiveLoopInput,
)
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


_REMEMBERED_VALUE: Final[dict[DecisionOutcomeCode, float]] = {
    DecisionOutcomeCode.NO_PROGRESS: -0.2,
    DecisionOutcomeCode.UNKNOWN: 0.0,
    DecisionOutcomeCode.PERCEIVED_CHANGE: 0.2,
}
_ALTERNATIVE_VALUE: Final[dict[ActionDirection, float]] = {
    ActionDirection.WAIT: 0.0,
    ActionDirection.MOVE: 0.3,
    ActionDirection.COMMUNICATE: 0.25,
}
_AFFECT_EDGE: Final[float] = 0.05
_HELP_CONFIDENCE: Final[float] = 0.75
_SEARCH_CONFIDENCE: Final[float] = 0.6


def _confidence_band(confidence: float) -> str:
    if confidence >= 0.66:
        return "high"
    if confidence >= 0.33:
        return "medium"
    return "low"


def _ordered(
    field_name: str, value: object
) -> tuple[object, ...]:
    _reject_objective(value, field_name)
    if isinstance(value, (str, bytes, set, frozenset)) or not isinstance(
        value, Sequence
    ):
        raise _fail(field_name, "not_ordered")
    return tuple(value)


def alternative_for(
    decision: RememberedDecision, observation: object
) -> tuple[ActionDirection, str | None] | None:
    """One alternative from the remembered kind and the current observation."""
    _reject_objective(decision, "decision")
    _reject_objective(observation, "observation")
    if type(decision) is not RememberedDecision:
        raise _fail("decision", "invalid_type")
    kind = decision.command_kind
    if kind == "help":
        return (ActionDirection.WAIT, decision.counterpart_id)
    if kind == "search":
        destination = _move_destination(observation, decision.place_id)
        if destination is None:
            return None
        return (ActionDirection.MOVE, destination)
    if kind == "wait" and decision.counterpart_id is not None:
        return (ActionDirection.COMMUNICATE, decision.counterpart_id)
    return None


def _move_destination(observation: object, place_id: str | None) -> str | None:
    exits = getattr(observation, "exits", ())
    if isinstance(exits, (str, bytes)) or not isinstance(exits, Sequence):
        return None
    ordered = sorted(
        exits,
        key=lambda item: _id_value(getattr(item, "destination_id", None)) or "",
    )
    for item in ordered:
        destination = _id_value(getattr(item, "destination_id", None))
        if destination is None:
            continue
        if place_id is None or destination != place_id:
            return destination
    return None


def _trust_toward(
    relationships: object, owner_id: AgentId, counterpart: str | None
) -> float:
    if counterpart is None:
        return 0.0
    for profile in _ordered("relationships", relationships):
        _reject_objective(profile, "relationships")
        if getattr(profile, "source_id", None) != owner_id:
            continue
        if _id_value(getattr(profile, "target_id", None)) != counterpart:
            continue
        dimensions = getattr(profile, "dimensions", ())
        if not isinstance(dimensions, Sequence):
            continue
        for item in dimensions:
            dimension = getattr(item, "dimension", None)
            if getattr(dimension, "value", None) != "trust":
                continue
            value = getattr(item, "value", 0.0)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return 0.0
            return max(0.0, float(value))
    return 0.0


def _alternative_confidence(
    decision: RememberedDecision,
    direction: ActionDirection,
    relationships: object,
) -> float:
    if decision.command_kind == "help" and direction is ActionDirection.WAIT:
        return _quantize(_HELP_CONFIDENCE)
    if decision.command_kind == "search" and direction is ActionDirection.MOVE:
        return _quantize(_SEARCH_CONFIDENCE)
    trust = _trust_toward(relationships, decision.owner_id, decision.counterpart_id)
    return _quantize(min(1.0, 0.5 + 0.5 * max(trust, 0.0)))


def _affect(alternative_value: float, remembered_value: float) -> CounterfactualAffect:
    difference = alternative_value - remembered_value
    if difference > _AFFECT_EDGE:
        code = CounterfactualAffectCode.REGRET
    elif difference < -_AFFECT_EDGE:
        code = CounterfactualAffectCode.RELIEF
    else:
        code = CounterfactualAffectCode.NEUTRAL
    magnitude = _quantize(min(1.0, abs(difference)))
    return CounterfactualAffect(code=code, magnitude=magnitude)


def consider_counterfactuals(
    loop_input: CognitiveLoopInput,
    remembered_decisions: Sequence[RememberedDecision] = (),
    *,
    policy: CounterfactualPolicy | None = None,
    memory: object | None = None,
    goal_board: object | None = None,
    self_model: object | None = None,
    relationships: Sequence[object] = (),
    causal_world_model: object | None = None,
    skipped_out: list[int] | None = None,
) -> tuple[CounterfactualScenario, ...]:
    """Freeze one scenario per salient remembered decision. Off stays quiet."""
    _reject_objective(causal_world_model, "causal_world_model")
    _reject_objective(memory, "memory")
    _reject_objective(goal_board, "goal_board")
    _reject_objective(self_model, "self_model")
    if type(loop_input) is not CognitiveLoopInput:
        raise _fail("loop_input", "invalid_type")
    if policy is None:
        return ()
    if type(policy) is not CounterfactualPolicy:
        raise _fail("policy", "invalid_type")
    decisions = _ordered("remembered_decisions", remembered_decisions)
    if not decisions:
        _LOG.warning("counterfactual_skipped reason_code=no_remembered_decision")
        _LOG.info("counterfactual_considered kept_count=0 skipped_count=1")
        if skipped_out is not None:
            skipped_out.append(1)
        return ()
    owner = loop_input.agent_id
    tick = loop_input.observation.tick
    window = decisions[-policy.max_decisions :]
    kept: list[CounterfactualScenario] = []
    skipped = 0
    for item in window:
        _reject_objective(item, "remembered_decisions")
        if type(item) is not RememberedDecision:
            raise _fail("remembered_decisions", "invalid_type")
        if item.owner_id != owner:
            _LOG.error(
                "counterfactual_owner_mismatch owner_id=%s reason_code=owner_mismatch",
                owner.value,
            )
            raise _fail("remembered_decisions", "owner_mismatch")
        if item.outcome_code is not DecisionOutcomeCode.NO_PROGRESS:
            skipped += 1
            _LOG.warning("counterfactual_skipped reason_code=not_salient")
            continue
        alternative = alternative_for(item, loop_input.observation)
        if alternative is None:
            skipped += 1
            _LOG.warning("counterfactual_skipped reason_code=no_alternative")
            continue
        direction, target_id = alternative
        remembered_value = _REMEMBERED_VALUE[item.outcome_code]
        alternative_value = _quantize(_ALTERNATIVE_VALUE[direction])
        affect = _affect(alternative_value, remembered_value)
        confidence = _alternative_confidence(item, direction, relationships)
        scenario = CounterfactualScenario(
            owner_id=owner,
            scenario_id=scenario_id_for(
                owner_id=owner,
                decision_id=item.decision_id,
                direction=direction,
                target_id=target_id,
            ),
            decision=item,
            alternative_direction=direction,
            target_id=target_id,
            predicted_outcome=PredictedAlternativeOutcome(
                direction=direction,
                value=alternative_value,
                magnitude=affect.magnitude,
            ),
            confidence=confidence,
            goal_ids=item.goal_ids,
            emotional_impact=affect,
            provenance=CounterfactualProvenanceKind.IMAGINED_ALTERNATIVE,
        )
        _LOG.debug(
            "counterfactual_scenario owner_id=%s tick=%s scenario_id=%s "
            "direction_code=%s confidence_band=%s affect_code=%s provenance_code=%s",
            owner.value,
            tick,
            scenario.scenario_id,
            direction.value,
            _confidence_band(confidence),
            affect.code.value,
            scenario.provenance.value,
        )
        kept.append(scenario)
    assembled = assemble_counterfactual_scenarios(kept)
    _LOG.info(
        "counterfactual_considered kept_count=%s skipped_count=%s",
        len(assembled),
        skipped,
    )
    if skipped_out is not None:
        skipped_out.append(skipped)
    return assembled


def log_counterfactual_affect(owner_id: AgentId, tick: int, reason_code: str) -> None:
    """Metadata-only affect effect. No claim text."""
    _LOG.debug(
        "counterfactual_effect owner_id=%s tick=%s effect_code=affect reason_code=%s",
        owner_id.value,
        tick,
        reason_code,
    )


def counterfactual_state_for(
    scenarios: Sequence[CounterfactualScenario],
) -> CounterfactualState:
    """Latest affect carried beside the scenarios. Empty stays neutral."""
    if not scenarios:
        return CounterfactualState()
    latest = scenarios[-1]
    return CounterfactualState(
        code=latest.emotional_impact.code,
        magnitude=latest.emotional_impact.magnitude,
    )


def counterfactual_direction_bias(
    scenarios: Sequence[CounterfactualScenario],
    futures: Sequence[object],
    *,
    bonus: float,
    owner_id: AgentId,
    tick: int,
) -> dict[str, float] | None:
    """Mark futures that match the strongest non-neutral alternative."""
    salient = [
        item
        for item in scenarios
        if item.emotional_impact.code is not CounterfactualAffectCode.NEUTRAL
    ]
    if not salient:
        return None
    best = max(salient, key=lambda item: (item.confidence, item.scenario_id))
    bias: dict[str, float] = {}
    for future in futures:
        future_id = getattr(future, "future_id", None)
        if not isinstance(future_id, str):
            continue
        direction = getattr(future, "direction", None)
        bias[future_id] = (
            bonus if direction is best.alternative_direction else 0.0
        )
    _LOG.debug(
        "counterfactual_effect owner_id=%s tick=%s effect_code=plan "
        "reason_code=applied",
        owner_id.value,
        tick,
    )
    return bias


def _effect(
    owner_id: AgentId, tick: int, effect_code: str, reason_code: str
) -> None:
    _LOG.debug(
        "counterfactual_effect owner_id=%s tick=%s effect_code=%s reason_code=%s",
        owner_id.value,
        tick,
        effect_code,
        reason_code,
    )


def _eligible(scenario: CounterfactualScenario, policy: CounterfactualPolicy) -> str:
    if scenario.confidence < policy.min_confidence:
        return "below_min_confidence"
    if scenario.emotional_impact.code is CounterfactualAffectCode.NEUTRAL:
        return "neutral"
    if scenario.decision.memory_id is None:
        return "no_memory_evidence"
    return "applied"


def counterfactual_belief_requests(
    scenarios: Sequence[CounterfactualScenario],
    *,
    policy: CounterfactualPolicy,
    owner_id: AgentId,
    tick: int,
) -> tuple[object, ...]:
    """One revision per gated scenario. Does not write a memory trace."""
    from memory.belief_formation import (
        DEFAULT_BELIEF_FORMATION_POLICY,
        belief_id_for_claim,
    )
    from memory.beliefs import (
        BeliefEvidenceBundle,
        BeliefEvidenceContribution,
        BeliefRevisionRequest,
        BeliefValueKind,
        ClaimSubject,
        ClaimSubjectKind,
        ClaimValue,
        EvidenceStance,
        SemanticClaim,
    )
    from memory.models import MemoryId

    requests: list[BeliefRevisionRequest] = []
    for scenario in scenarios:
        reason = _eligible(scenario, policy)
        if reason != "applied":
            if reason == "no_memory_evidence":
                _effect(owner_id, tick, "belief", reason)
            continue
        memory_text = scenario.decision.memory_id
        assert memory_text is not None
        memory_id = MemoryId(memory_text)
        claim = SemanticClaim(
            subject=ClaimSubject(
                kind=ClaimSubjectKind.CONCEPT,
                concept=scenario.decision.decision_id,
            ),
            predicate="counterfactual_alternative",
            value=ClaimValue(
                kind=BeliefValueKind.TEXT,
                text_value=scenario.alternative_direction.value,
            ),
        )
        evidence = BeliefEvidenceBundle(
            supporting=(
                BeliefEvidenceContribution(
                    memory_id=memory_id,
                    stance=EvidenceStance.SUPPORTING,
                    contribution=0.5,
                    ordinal=0,
                    lineage_root_id=memory_id,
                ),
            ),
            contradicting=(),
        )
        belief_id = belief_id_for_claim(owner_id=owner_id, claim=claim)
        digest = hashlib.sha256(
            f"{owner_id.value}|{scenario.scenario_id}".encode()
        ).hexdigest()[:24]
        requests.append(
            BeliefRevisionRequest(
                owner_id=owner_id,
                operation_id=f"cf-belief-{digest}",
                logical_tick=tick,
                claim=claim,
                evidence=evidence,
                policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
                belief_id=belief_id,
            )
        )
        _effect(owner_id, tick, "belief", "applied")
    return tuple(requests)


_RUNTIME_LOG: Final[logging.Logger] = logging.getLogger("simulation.agent_runtime")


def counterfactual_relationship_requests(
    scenarios: Sequence[CounterfactualScenario],
    *,
    policy: CounterfactualPolicy,
    owner_id: AgentId,
    tick: int,
    resolve_counterpart: object | None,
) -> tuple[object, ...]:
    """Revise trust for help→wait and wait→communicate. Search does not."""
    from social.relationships import (
        DEFAULT_RELATIONSHIP_POLICY,
        RelationshipInteractionSignal,
        RelationshipRevisionRequest,
        RelationshipSignalKind,
    )

    requests: list[RelationshipRevisionRequest] = []
    for scenario in scenarios:
        kind = scenario.decision.command_kind
        direction = scenario.alternative_direction
        if kind == "help" and direction is ActionDirection.WAIT:
            signal_kind = RelationshipSignalKind.COUNTERFACTUAL_TRUST_DOWN
        elif kind == "wait" and direction is ActionDirection.COMMUNICATE:
            signal_kind = RelationshipSignalKind.COUNTERFACTUAL_TRUST_UP
        else:
            continue
        reason = _eligible(scenario, policy)
        if reason != "applied":
            if reason == "no_memory_evidence":
                _RUNTIME_LOG.debug(
                    "counterfactual_effect owner_id=%s tick=%s "
                    "effect_code=relationship reason_code=%s",
                    owner_id.value,
                    tick,
                    reason,
                )
            continue
        counterpart = scenario.decision.counterpart_id
        resolved = _resolved_counterpart(
            resolve_counterpart, counterpart, owner_id
        )
        if resolved is None:
            _RUNTIME_LOG.debug(
                "counterfactual_effect owner_id=%s tick=%s effect_code=relationship "
                "reason_code=unresolved_counterpart",
                owner_id.value,
                tick,
            )
            continue
        memory_text = scenario.decision.memory_id
        assert memory_text is not None
        signal = RelationshipInteractionSignal(
            counterpart_id=resolved,
            kind=signal_kind,
            strength=scenario.confidence,
            memory_ref=memory_text,
            lineage_root_ref=memory_text,
            source_tick=scenario.decision.tick,
        )
        digest = hashlib.sha256(
            f"{owner_id.value}|{resolved.value}|{scenario.scenario_id}".encode()
        ).hexdigest()[:24]
        requests.append(
            RelationshipRevisionRequest(
                source_id=owner_id,
                target_id=resolved,
                operation_id=f"cf-rel-{digest}",
                logical_tick=tick,
                signals=(signal,),
                policy=DEFAULT_RELATIONSHIP_POLICY.as_ref(),
            )
        )
        _RUNTIME_LOG.debug(
            "counterfactual_effect owner_id=%s tick=%s effect_code=relationship "
            "reason_code=applied",
            owner_id.value,
            tick,
        )
    return tuple(requests)


def _resolved_counterpart(
    resolver: object | None, counterpart: str | None, owner_id: AgentId
) -> AgentId | None:
    from world.identifiers import EntityId

    if counterpart is None or not callable(resolver):
        return None
    try:
        entity = EntityId(counterpart)
    except (TypeError, ValueError):
        return None
    resolved = resolver(entity)
    if type(resolved) is not AgentId or resolved == owner_id:
        return None
    return resolved


@dataclass(frozen=True, slots=True)
class CounterfactualAudit:
    """In-run audit. Counts and codes only. Not runner-result JSON."""

    owner_id: AgentId
    tick: int
    mode: str
    scenario_count: int
    skipped_count: int
    regret_count: int
    relief_count: int
    neutral_count: int
    llm_call_count: int
    fallback_used: bool
    highest_direction_code: str | None
    confidence_band: str | None
    provenance_code: str

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.fallback_used) is not bool:
            raise _fail("fallback_used", "invalid_type")
        expected = CounterfactualProvenanceKind.IMAGINED_ALTERNATIVE.value
        if self.provenance_code != expected:
            raise _fail("provenance_code", "invalid_provenance")


def build_counterfactual_audit(
    *,
    owner_id: AgentId,
    tick: int,
    mode: str,
    scenarios: Sequence[CounterfactualScenario],
    skipped_count: int,
    llm_call_count: int,
    fallback_used: bool,
) -> CounterfactualAudit:
    """Count affect codes. No observation text and no prompts."""
    regret = relief = neutral = 0
    best: CounterfactualScenario | None = None
    for scenario in scenarios:
        code = scenario.emotional_impact.code
        if code is CounterfactualAffectCode.REGRET:
            regret += 1
        elif code is CounterfactualAffectCode.RELIEF:
            relief += 1
        else:
            neutral += 1
        if best is None or scenario.confidence > best.confidence:
            best = scenario
    audit = CounterfactualAudit(
        owner_id=owner_id,
        tick=tick,
        mode=mode,
        scenario_count=len(scenarios),
        skipped_count=skipped_count,
        regret_count=regret,
        relief_count=relief,
        neutral_count=neutral,
        llm_call_count=llm_call_count,
        fallback_used=fallback_used,
        highest_direction_code=None
        if best is None
        else best.alternative_direction.value,
        confidence_band=None if best is None else _confidence_band(best.confidence),
        provenance_code=CounterfactualProvenanceKind.IMAGINED_ALTERNATIVE.value,
    )
    _LOG.debug(
        "counterfactual_audit owner_id=%s tick=%s scenario_count=%s "
        "regret_count=%s fallback_used=%s",
        owner_id.value,
        tick,
        audit.scenario_count,
        audit.regret_count,
        audit.fallback_used,
    )
    return audit
