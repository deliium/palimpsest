"""Per-utterance communication strategy.

The choice is computed for one claim from this tick's inputs. It is not a
trait, and the rendered command does not carry the choice.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.epistemic import EpistemicJudgment
from agents.cognition.models import (
    _EFFECT_QUANTUM,
    EmotionalStateEvaluation,
    EmotionDriverCode,
    EmotionKind,
    GoalBoard,
    SelfModel,
    SubjectiveRisk,
    SubjectiveRiskKind,
)
from agents.cognition.theory_of_mind import (
    MindAspect,
    MindSlot,
    TheoryOfMind,
    TheoryOfMindPolicy,
    default_theory_of_mind_policy,
)
from agents.models import AgentId, GoalOutcomeKind
from social.relationships import DirectedRelationshipProfile, RelationshipDimension
from world.actions import Ask, Talk, Tell
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    confidence_band,
    origin_utterance,
)
from world.identifiers import (
    EntityId,
    require_bounded_text,
    require_exact_nonneg_int,
    require_stable_id,
)
from world.observations import Observation

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.communication_strategy"
)

COMMUNICATION_STRATEGY_POLICY_VERSION: Final[str] = "communication-strategy.v1"
_RELATIONSHIP_HIGH: Final[float] = 0.4
_LOW_SOURCE_CONFIDENCE: Final[float] = 0.55
_EMOTION_INTENSITY: Final[float] = 0.4
_TRUST_LOW: Final[float] = 0.5
_MAX_SOURCE_ATOMS: Final[int] = 8
_MAX_FACTORS: Final[int] = 8
_ID_PREFIX: Final[str] = "cs-"
_ALLOWLISTED_CONCEPTS: Final[tuple[str, ...]] = ("food", "water", "rest", "danger")
_FORBIDDEN_VIEW_TYPES: Final[frozenset[str]] = frozenset(
    {"WorldState", "PhysicalRules", "AgentBody"}
)
_SAFE_HELLO: Final[str] = "hello"
_SAFE_ASK: Final[str] = "status?"


class CommunicationStrategy(StrEnum):
    """Closed render choice for one utterance."""

    TRUTHFUL = "truthful"
    UNCERTAIN = "uncertain"
    REFUSAL = "refusal"
    OMISSION = "omission"
    SELECTIVE_DISCLOSURE = "selective_disclosure"
    EXAGGERATION = "exaggeration"
    DELIBERATE_FALSE_STATEMENT = "deliberate_false_statement"


class SpeakerStance(StrEnum):
    """What the speaker did to their own record."""

    ASSERT_MATCH = "assert_match"
    HEDGE = "hedge"
    WITHHOLD = "withhold"
    REFUSE = "refuse"
    DIVERGE = "diverge"


class CommunicationDivergence(StrEnum):
    """How the render differs from the selected source."""

    NONE = "none"
    CONFIDENCE_INFLATED = "confidence_inflated"
    ATOM_SUBSTITUTED = "atom_substituted"
    ATOMS_DROPPED = "atoms_dropped"
    WITHHELD = "withheld"
    REFUSED = "refused"


class CommunicationFactor(StrEnum):
    """Closed reason codes for one choice. None of these is a trait."""

    GOAL_PRESERVE_LIFE = "goal_preserve_life"
    GOAL_OTHER = "goal_other"
    RELATIONSHIP_MISSING = "relationship_missing"
    FEAR_HIGH = "fear_high"
    RESENTMENT_HIGH = "resentment_high"
    TRUST_LOW = "trust_low"
    TOM_ABSENT = "tom_absent"
    TOM_ATTACK = "tom_attack"
    TOM_ANGER = "tom_anger"
    RISK_PHYSICAL_HARM = "risk_physical_harm"
    RISK_SOCIAL_COST = "risk_social_cost"
    RISK_ABSENT = "risk_absent"
    SELF_MODEL_GOAL = "self_model_goal"
    SELF_MODEL_ABSENT = "self_model_absent"
    EMOTION_ABSENT = "emotion_absent"
    EMOTION_ANGER = "emotion_anger"
    EPISTEMIC_SECRET = "epistemic_secret"
    EPISTEMIC_UNCERTAIN = "epistemic_uncertain"
    LOW_CONFIDENCE = "low_confidence"
    ALTERNATE_TOKEN = "alternate_token"
    NO_ALTERNATE_TOKEN = "no_alternate_token"
    NORMS_UNAVAILABLE = "norms_unavailable"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "communication_strategy_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _quantize(value: float) -> float:
    steps = round(value / _EFFECT_QUANTUM)
    if steps == 0:
        return 0.0
    return float(Decimal(steps) * Decimal(str(_EFFECT_QUANTUM)))


def canonical_source_atom_key(tokens: Sequence[str]) -> str:
    """Stable atom key. Order is the caller's order after the cap."""
    return "|".join(tokens)


def communication_intent_id(
    *,
    owner_id: AgentId,
    recipient_id: AgentId,
    tick: int,
    strategy: CommunicationStrategy,
    source_atom_tokens: Sequence[str],
) -> str:
    """sha256 of owner, recipient, tick, strategy, and the source atom key."""
    key = canonical_source_atom_key(source_atom_tokens)
    material = (
        f"{owner_id.value}|{recipient_id.value}|{tick}|{strategy.value}|{key}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{_ID_PREFIX}{digest[:48]}"


def _confidence(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "non_finite_confidence")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "non_finite_confidence")
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "not_confidence")
    return _quantize(number)


def _token_tuple(field_name: str, value: object, *, limit: int) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise _fail(field_name, "invalid_type")
    if len(value) > limit:
        raise _fail(field_name, "cap_exceeded")
    tokens: list[str] = []
    for item in value:
        if type(item) is not str:
            raise _fail(field_name, "invalid_type")
        try:
            tokens.append(require_bounded_text(field_name, item))
        except ValueError as exc:
            raise _fail(field_name, "invalid_value") from exc
    return tuple(tokens)


def _factor_tuple(value: object) -> tuple[CommunicationFactor, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise _fail("factor_codes", "invalid_type")
    if len(value) > _MAX_FACTORS:
        raise _fail("factor_codes", "cap_exceeded")
    factors: list[CommunicationFactor] = []
    for item in value:
        if type(item) is not CommunicationFactor:
            raise _fail("factor_codes", "unknown_enum")
        factors.append(item)
    return tuple(factors)


@dataclass(frozen=True, slots=True)
class CommunicationStrategyPolicy:
    """Thresholds for one choice. Not runner JSON keys."""

    version: str = COMMUNICATION_STRATEGY_POLICY_VERSION
    relationship_high: float = _RELATIONSHIP_HIGH
    low_confidence: float = _LOW_SOURCE_CONFIDENCE
    emotion_intensity: float = _EMOTION_INTENSITY

    def __post_init__(self) -> None:
        if self.version != COMMUNICATION_STRATEGY_POLICY_VERSION:
            raise _fail("version", "unsupported_version")
        object.__setattr__(
            self,
            "relationship_high",
            _confidence("relationship_high", self.relationship_high),
        )
        object.__setattr__(
            self,
            "low_confidence",
            _confidence("low_confidence", self.low_confidence),
        )
        object.__setattr__(
            self,
            "emotion_intensity",
            _confidence("emotion_intensity", self.emotion_intensity),
        )


def default_communication_strategy_policy() -> CommunicationStrategyPolicy:
    """Return the v1 thresholds."""
    return CommunicationStrategyPolicy()


@dataclass(frozen=True, slots=True)
class CommunicationIntent:
    """Hidden structured choice. The utterance does not carry these fields."""

    intent_id: str
    owner_id: AgentId
    recipient_id: AgentId
    tick: int
    strategy: CommunicationStrategy
    stance: SpeakerStance
    divergence: CommunicationDivergence
    source_basis: CommunicationSourceBasis
    source_confidence: float
    source_atom_tokens: tuple[str, ...]
    cited_event_id: str | None
    factor_codes: tuple[CommunicationFactor, ...]
    delivered: bool

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.recipient_id) is not AgentId:
            raise _fail("recipient_id", "invalid_type")
        try:
            tick = require_exact_nonneg_int("tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "not_nonnegative") from exc
        object.__setattr__(self, "tick", tick)
        if type(self.strategy) is not CommunicationStrategy:
            raise _fail("strategy", "unknown_enum")
        if type(self.stance) is not SpeakerStance:
            raise _fail("stance", "unknown_enum")
        if type(self.divergence) is not CommunicationDivergence:
            raise _fail("divergence", "unknown_enum")
        if type(self.source_basis) is not CommunicationSourceBasis:
            raise _fail("source_basis", "unknown_enum")
        if type(self.delivered) is not bool:
            raise _fail("delivered", "invalid_type")
        tokens = _token_tuple(
            "source_atom_tokens", self.source_atom_tokens, limit=_MAX_SOURCE_ATOMS
        )
        object.__setattr__(self, "source_atom_tokens", tokens)
        object.__setattr__(
            self,
            "source_confidence",
            _confidence("source_confidence", self.source_confidence),
        )
        factors = _factor_tuple(self.factor_codes)
        object.__setattr__(self, "factor_codes", factors)
        if self.cited_event_id is not None:
            if type(self.cited_event_id) is not str:
                raise _fail("cited_event_id", "invalid_type")
            try:
                cited = require_stable_id("cited_event_id", self.cited_event_id)
            except ValueError as exc:
                raise _fail("cited_event_id", "invalid_value") from exc
            object.__setattr__(self, "cited_event_id", cited)
        expected = communication_intent_id(
            owner_id=self.owner_id,
            recipient_id=self.recipient_id,
            tick=tick,
            strategy=self.strategy,
            source_atom_tokens=tokens,
        )
        if self.intent_id != expected:
            raise _fail("intent_id", "intent_id_mismatch")
        _LOG.debug(
            "communication_intent_built owner_id=%s policy_version=%s strategy=%s",
            self.owner_id.value,
            COMMUNICATION_STRATEGY_POLICY_VERSION,
            self.strategy.value,
        )


@dataclass(frozen=True, slots=True)
class CommunicationIntentAudit:
    """In-run research record. Omitted from runner-result serialization."""

    intent_id: str
    owner_id: AgentId
    recipient_id: AgentId
    tick: int
    strategy: CommunicationStrategy
    stance: SpeakerStance
    divergence: CommunicationDivergence
    source_basis: CommunicationSourceBasis
    source_confidence: float
    source_atom_tokens: tuple[str, ...]
    cited_event_id: str | None
    factor_codes: tuple[CommunicationFactor, ...]
    delivered: bool
    fallback_used: bool

    def __post_init__(self) -> None:
        if type(self.fallback_used) is not bool:
            raise _fail("fallback_used", "invalid_type")
        intent = CommunicationIntent(
            intent_id=self.intent_id,
            owner_id=self.owner_id,
            recipient_id=self.recipient_id,
            tick=self.tick,
            strategy=self.strategy,
            stance=self.stance,
            divergence=self.divergence,
            source_basis=self.source_basis,
            source_confidence=self.source_confidence,
            source_atom_tokens=self.source_atom_tokens,
            cited_event_id=self.cited_event_id,
            factor_codes=self.factor_codes,
            delivered=self.delivered,
        )
        object.__setattr__(self, "source_confidence", intent.source_confidence)
        object.__setattr__(self, "source_atom_tokens", intent.source_atom_tokens)
        object.__setattr__(self, "factor_codes", intent.factor_codes)
        object.__setattr__(self, "tick", intent.tick)
        object.__setattr__(self, "cited_event_id", intent.cited_event_id)


def reject_empty_refusal_render(
    strategy: CommunicationStrategy,
    *,
    rendered_predicates: Sequence[str] | None,
    rendered_object_tokens: Sequence[str] | None,
) -> None:
    """Reject a refusal render that is empty and still carries a source token."""
    if type(strategy) is not CommunicationStrategy:
        raise _fail("strategy", "unknown_enum")
    if strategy is not CommunicationStrategy.REFUSAL:
        return
    if rendered_predicates is None and rendered_object_tokens is None:
        return
    predicates = () if rendered_predicates is None else tuple(rendered_predicates)
    objects = () if rendered_object_tokens is None else tuple(rendered_object_tokens)
    if objects and not predicates:
        raise _fail("rendered_predicates", "empty_refusal_render")


def communication_intent(
    *,
    owner_id: AgentId,
    recipient_id: AgentId,
    tick: int,
    strategy: CommunicationStrategy,
    stance: SpeakerStance,
    divergence: CommunicationDivergence,
    source_basis: CommunicationSourceBasis,
    source_confidence: float,
    source_atom_tokens: Sequence[str],
    cited_event_id: str | None,
    factor_codes: Sequence[CommunicationFactor],
    delivered: bool,
    rendered_predicates: Sequence[str] | None = None,
    rendered_object_tokens: Sequence[str] | None = None,
) -> CommunicationIntent:
    """Build an intent whose id is the canonical digest of the source."""
    if isinstance(source_atom_tokens, (str, bytes)) or not isinstance(
        source_atom_tokens, Sequence
    ):
        raise _fail("source_atom_tokens", "invalid_type")
    if isinstance(factor_codes, (str, bytes)) or not isinstance(
        factor_codes, Sequence
    ):
        raise _fail("factor_codes", "invalid_type")
    tokens = tuple(source_atom_tokens)
    factors = tuple(factor_codes)
    if type(strategy) is not CommunicationStrategy:
        raise _fail("strategy", "unknown_enum")
    reject_empty_refusal_render(
        strategy,
        rendered_predicates=rendered_predicates,
        rendered_object_tokens=rendered_object_tokens,
    )
    intent_id = communication_intent_id(
        owner_id=owner_id,
        recipient_id=recipient_id,
        tick=tick,
        strategy=strategy,
        source_atom_tokens=tokens,
    )
    return CommunicationIntent(
        intent_id=intent_id,
        owner_id=owner_id,
        recipient_id=recipient_id,
        tick=tick,
        strategy=strategy,
        stance=stance,
        divergence=divergence,
        source_basis=source_basis,
        source_confidence=source_confidence,
        source_atom_tokens=tokens,
        cited_event_id=cited_event_id,
        factor_codes=factors,
        delivered=delivered,
    )


def _dimension(
    profile: DirectedRelationshipProfile,
    kind: RelationshipDimension,
) -> float | None:
    for item in profile.dimensions:
        if item.dimension is kind:
            return item.value
    return None


def _require_observation(value: object) -> Observation | None:
    if value is None:
        return None
    if type(value).__name__ in _FORBIDDEN_VIEW_TYPES:
        raise TypeError("observation must not be world authority")
    if type(value) is not Observation:
        raise TypeError("observation must be Observation or None")
    return value


def _held_tokens(observation: Observation | None) -> tuple[str, ...]:
    if observation is None:
        return ()
    found: list[str] = []
    body = observation.self_body
    if body is not None:
        found.append(body.location_id.value)
    for location in observation.locations:
        found.append(location.entity_id.value)
    for exit_ in observation.exits:
        found.append(exit_.destination_id.value)
    for occurrence in observation.occurrences:
        if occurrence.destination_id is not None:
            found.append(occurrence.destination_id.value)
    allow = set(_ALLOWLISTED_CONCEPTS)
    for item in observation.items:
        if item.name in allow:
            found.append(item.name)
    for resource in observation.resources:
        if resource.name in allow:
            found.append(resource.name)
    for message in observation.communications:
        for concept in message.utterance.content.concepts:
            if concept in allow:
                found.append(concept)
    return tuple(found)


def _alternate_for(
    tokens: Sequence[str],
    held: Sequence[str],
) -> tuple[int, str] | None:
    if not tokens:
        return None
    for index in range(len(tokens) - 1, -1, -1):
        target = tokens[index]
        pool = [item for item in tokens if item != target]
        pool.extend(item for item in held if item != target and item not in pool)
        if pool:
            return index, pool[0]
    return None


def _cap_tokens(tokens: Sequence[str]) -> tuple[str, ...]:
    if len(tokens) > _MAX_SOURCE_ATOMS:
        _LOG.warning(
            "communication_strategy_cap reason_code=cap_exceeded "
            "field=source_atom_tokens"
        )
        return tuple(tokens[:_MAX_SOURCE_ATOMS])
    return tuple(tokens)


def _store_factors(
    factors: Sequence[CommunicationFactor],
) -> tuple[CommunicationFactor, ...]:
    ordered = tuple(factor for factor in CommunicationFactor if factor in factors)
    if len(ordered) > _MAX_FACTORS:
        _LOG.warning(
            "communication_strategy_cap reason_code=cap_exceeded field=factor_codes"
        )
        return ordered[:_MAX_FACTORS]
    return ordered


def _anger_intensity(evaluation: EmotionalStateEvaluation) -> float:
    for entry in evaluation.state.intensities:
        if entry.kind is EmotionKind.ANGER:
            return entry.value
    return 0.0


def _owner_mismatch(field_name: str, owner_id: AgentId, other: AgentId) -> None:
    if other != owner_id:
        raise _fail(field_name, "owner_mismatch")


def _collect_factors(
    *,
    owner_id: AgentId,
    recipient_id: AgentId,
    recipient_entity_id: EntityId,
    owner_entity_id: EntityId | None,
    policy: CommunicationStrategyPolicy,
    goal_board: GoalBoard | None,
    relationships: Sequence[DirectedRelationshipProfile] | None,
    mind: TheoryOfMind | None,
    mind_policy: TheoryOfMindPolicy | None,
    risks: Sequence[SubjectiveRisk] | None,
    self_model: SelfModel | None,
    emotional_state: EmotionalStateEvaluation | None,
    observation: Observation | None,
    source_confidence: float,
    source_atom_tokens: Sequence[str],
    epistemic_judgment: EpistemicJudgment | None,
    norms: object | None,
) -> tuple[set[CommunicationFactor], tuple[int, str] | None]:
    factors: set[CommunicationFactor] = set()
    if goal_board is not None:
        if type(goal_board) is not GoalBoard:
            raise TypeError("goal_board must be GoalBoard or None")
        _owner_mismatch("goal_board", owner_id, goal_board.owner_id)
        by_id = {item.goal_id: item for item in goal_board.goals}
        for focus_id in goal_board.foci_ids:
            outcome = by_id[focus_id].outcome.kind
            if outcome is GoalOutcomeKind.PRESERVE_LIFE:
                factors.add(CommunicationFactor.GOAL_PRESERVE_LIFE)
            else:
                factors.add(CommunicationFactor.GOAL_OTHER)
    profile = _profile_for(owner_id, recipient_id, relationships)
    if profile is None:
        factors.add(CommunicationFactor.RELATIONSHIP_MISSING)
    else:
        high = policy.relationship_high
        fear = _dimension(profile, RelationshipDimension.FEAR)
        resentment = _dimension(profile, RelationshipDimension.RESENTMENT)
        trust = _dimension(profile, RelationshipDimension.TRUST)
        if fear is not None and _quantize(fear) >= high:
            factors.add(CommunicationFactor.FEAR_HIGH)
        if resentment is not None and _quantize(resentment) >= high:
            factors.add(CommunicationFactor.RESENTMENT_HIGH)
        if trust is not None and _quantize(trust) < _quantize(_TRUST_LOW):
            factors.add(CommunicationFactor.TRUST_LOW)
    if mind is None:
        factors.add(CommunicationFactor.TOM_ABSENT)
    else:
        if type(mind) is not TheoryOfMind:
            raise TypeError("mind must be TheoryOfMind or None")
        _owner_mismatch("mind", owner_id, mind.owner_id)
        active = (
            default_theory_of_mind_policy()
            if mind_policy is None
            else mind_policy
        )
        if type(active) is not TheoryOfMindPolicy:
            raise TypeError("mind_policy must be TheoryOfMindPolicy or None")
        _read_mind(
            factors,
            mind=mind,
            recipient_entity_id=recipient_entity_id,
            owner_entity_id=owner_entity_id,
            threshold=active.action_threshold,
        )
    if risks is None:
        factors.add(CommunicationFactor.RISK_ABSENT)
    else:
        if isinstance(risks, (str, bytes)) or not isinstance(risks, Sequence):
            raise TypeError("risks must be a sequence or None")
        for risk in risks:
            if type(risk) is not SubjectiveRisk:
                raise TypeError("risks entries must be SubjectiveRisk")
            if risk.kind is SubjectiveRiskKind.PHYSICAL_HARM:
                factors.add(CommunicationFactor.RISK_PHYSICAL_HARM)
            elif risk.kind is SubjectiveRiskKind.SOCIAL_COST:
                factors.add(CommunicationFactor.RISK_SOCIAL_COST)
    focused = set()
    if goal_board is not None:
        focused = set(goal_board.foci_ids)
    if (
        self_model is not None
        and type(self_model) is SelfModel
        and focused
        and any(item in self_model.goal_ids for item in focused)
    ):
        _owner_mismatch("self_model", owner_id, self_model.owner_id)
        factors.add(CommunicationFactor.SELF_MODEL_GOAL)
    else:
        if self_model is not None:
            if type(self_model) is not SelfModel:
                raise TypeError("self_model must be SelfModel or None")
            _owner_mismatch("self_model", owner_id, self_model.owner_id)
        factors.add(CommunicationFactor.SELF_MODEL_ABSENT)
    if emotional_state is not None and type(emotional_state) is not (
        EmotionalStateEvaluation
    ):
        raise TypeError("emotional_state must be EmotionalStateEvaluation or None")
    passthrough = (
        emotional_state is not None
        and EmotionDriverCode.PASSTHROUGH in emotional_state.driver_codes
    )
    if emotional_state is None or passthrough:
        if emotional_state is not None:
            _owner_mismatch("emotional_state", owner_id, emotional_state.owner_id)
        factors.add(CommunicationFactor.EMOTION_ABSENT)
    else:
        _owner_mismatch("emotional_state", owner_id, emotional_state.owner_id)
        if _quantize(_anger_intensity(emotional_state)) >= policy.emotion_intensity:
            factors.add(CommunicationFactor.EMOTION_ANGER)
    if epistemic_judgment is EpistemicJudgment.SECRET:
        factors.add(CommunicationFactor.EPISTEMIC_SECRET)
    elif epistemic_judgment is EpistemicJudgment.UNCERTAIN:
        factors.add(CommunicationFactor.EPISTEMIC_UNCERTAIN)
    elif (
        epistemic_judgment is not None
        and type(epistemic_judgment) is not EpistemicJudgment
    ):
        raise _fail("epistemic_judgment", "unknown_enum")
    if source_confidence < policy.low_confidence:
        factors.add(CommunicationFactor.LOW_CONFIDENCE)
    alternate = _alternate_for(source_atom_tokens, _held_tokens(observation))
    if alternate is None:
        factors.add(CommunicationFactor.NO_ALTERNATE_TOKEN)
    else:
        factors.add(CommunicationFactor.ALTERNATE_TOKEN)
    if norms is None:
        factors.add(CommunicationFactor.NORMS_UNAVAILABLE)
    return factors, alternate


def _profile_for(
    owner_id: AgentId,
    recipient_id: AgentId,
    relationships: Sequence[DirectedRelationshipProfile] | None,
) -> DirectedRelationshipProfile | None:
    if relationships is None:
        return None
    if isinstance(relationships, (str, bytes)) or not isinstance(
        relationships, Sequence
    ):
        raise TypeError("relationships must be a sequence or None")
    for item in relationships:
        if type(item) is not DirectedRelationshipProfile:
            raise TypeError("relationships entries must be DirectedRelationshipProfile")
        if item.source_id == owner_id and item.target_id == recipient_id:
            return item
    return None


def _read_mind(
    factors: set[CommunicationFactor],
    *,
    mind: TheoryOfMind,
    recipient_entity_id: EntityId,
    owner_entity_id: EntityId | None,
    threshold: float,
) -> None:
    owner_token = None if owner_entity_id is None else owner_entity_id.value
    for item in mind.hypotheses:
        if item.subject_id != recipient_entity_id:
            continue
        if item.confidence < threshold:
            continue
        if item.aspect is MindAspect.FUTURE_ACTION:
            action = _atom_value(item.atoms, MindSlot.ACTION)
            target = _atom_value(item.atoms, MindSlot.TARGET)
            toward_owner = target is None or target == owner_token
            if action == "attack" and toward_owner:
                factors.add(CommunicationFactor.TOM_ATTACK)
        elif item.aspect is MindAspect.EMOTION:
            if _atom_value(item.atoms, MindSlot.EMOTION_KIND) == "anger":
                factors.add(CommunicationFactor.TOM_ANGER)


def _atom_value(atoms: Sequence[object], slot: MindSlot) -> str | None:
    for atom in atoms:
        if getattr(atom, "slot", None) is slot:
            value = getattr(atom, "value", None)
            if type(value) is str:
                return value
    return None


def _select_rule(
    factors: set[CommunicationFactor],
    *,
    tokens: Sequence[str],
    source_confidence: float,
) -> tuple[CommunicationStrategy, SpeakerStance, CommunicationDivergence]:
    secret = CommunicationFactor.EPISTEMIC_SECRET in factors
    fear = CommunicationFactor.FEAR_HIGH in factors
    attack = CommunicationFactor.TOM_ATTACK in factors
    life = CommunicationFactor.GOAL_PRESERVE_LIFE in factors
    harm = CommunicationFactor.RISK_PHYSICAL_HARM in factors
    if secret and (fear or attack or life or harm):
        return (
            CommunicationStrategy.REFUSAL,
            SpeakerStance.REFUSE,
            CommunicationDivergence.REFUSED,
        )
    if secret:
        return (
            CommunicationStrategy.OMISSION,
            SpeakerStance.WITHHOLD,
            CommunicationDivergence.WITHHELD,
        )
    low = CommunicationFactor.LOW_CONFIDENCE in factors
    uncertain = CommunicationFactor.EPISTEMIC_UNCERTAIN in factors
    if low or uncertain:
        return (
            CommunicationStrategy.UNCERTAIN,
            SpeakerStance.HEDGE,
            CommunicationDivergence.NONE,
        )
    if not tokens:
        return (
            CommunicationStrategy.TRUTHFUL,
            SpeakerStance.ASSERT_MATCH,
            CommunicationDivergence.NONE,
        )
    missing = CommunicationFactor.RELATIONSHIP_MISSING in factors
    resentment = CommunicationFactor.RESENTMENT_HIGH in factors
    anger = CommunicationFactor.EMOTION_ANGER in factors
    alternate = CommunicationFactor.ALTERNATE_TOKEN in factors
    risk_or_tom = harm or attack
    pressure = harm or fear or attack or (resentment and anger)
    if pressure and alternate and (not missing or risk_or_tom):
        return (
            CommunicationStrategy.DELIBERATE_FALSE_STATEMENT,
            SpeakerStance.DIVERGE,
            CommunicationDivergence.ATOM_SUBSTITUTED,
        )
    no_alternate = CommunicationFactor.NO_ALTERNATE_TOKEN in factors
    if (resentment or anger) and no_alternate and source_confidence < 1.0:
        return (
            CommunicationStrategy.EXAGGERATION,
            SpeakerStance.DIVERGE,
            CommunicationDivergence.CONFIDENCE_INFLATED,
        )
    trust_low = CommunicationFactor.TRUST_LOW in factors
    if trust_low and len(tokens) > 1 and not missing:
        return (
            CommunicationStrategy.SELECTIVE_DISCLOSURE,
            SpeakerStance.DIVERGE,
            CommunicationDivergence.ATOMS_DROPPED,
        )
    return (
        CommunicationStrategy.TRUTHFUL,
        SpeakerStance.ASSERT_MATCH,
        CommunicationDivergence.NONE,
    )


def choose_communication_strategy(
    *,
    owner_id: AgentId,
    recipient_id: AgentId,
    recipient_entity_id: EntityId,
    tick: int,
    source_basis: CommunicationSourceBasis,
    source_confidence: float,
    source_atom_tokens: Sequence[str],
    cited_event_id: str | None = None,
    policy: CommunicationStrategyPolicy | None = None,
    goal_board: GoalBoard | None = None,
    relationships: Sequence[DirectedRelationshipProfile] | None = None,
    mind: TheoryOfMind | None = None,
    mind_policy: TheoryOfMindPolicy | None = None,
    risks: Sequence[SubjectiveRisk] | None = None,
    self_model: SelfModel | None = None,
    emotional_state: EmotionalStateEvaluation | None = None,
    observation: object | None = None,
    owner_entity_id: EntityId | None = None,
    epistemic_judgment: EpistemicJudgment | None = None,
    norms: object | None = None,
) -> tuple[CommunicationIntent, CommunicationIntentAudit]:
    """Pick one strategy. Missing inputs are reason codes, not a lie default."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(recipient_id) is not AgentId:
        raise _fail("recipient_id", "invalid_type")
    if type(recipient_entity_id) is not EntityId:
        raise _fail("recipient_entity_id", "invalid_type")
    active_policy = (
        default_communication_strategy_policy() if policy is None else policy
    )
    if type(active_policy) is not CommunicationStrategyPolicy:
        raise _fail("policy", "invalid_type")
    if type(source_basis) is not CommunicationSourceBasis:
        raise _fail("source_basis", "unknown_enum")
    view = _require_observation(observation)
    if isinstance(source_atom_tokens, (str, bytes)) or not isinstance(
        source_atom_tokens, Sequence
    ):
        raise _fail("source_atom_tokens", "invalid_type")
    confidence = _confidence("source_confidence", source_confidence)
    tokens = _cap_tokens(tuple(source_atom_tokens))
    for token in tokens:
        if type(token) is not str:
            raise _fail("source_atom_tokens", "invalid_type")
    factors, alternate = _collect_factors(
        owner_id=owner_id,
        recipient_id=recipient_id,
        recipient_entity_id=recipient_entity_id,
        owner_entity_id=owner_entity_id,
        policy=active_policy,
        goal_board=goal_board,
        relationships=relationships,
        mind=mind,
        mind_policy=mind_policy,
        risks=risks,
        self_model=self_model,
        emotional_state=emotional_state,
        observation=view,
        source_confidence=confidence,
        source_atom_tokens=tokens,
        epistemic_judgment=epistemic_judgment,
        norms=norms,
    )
    fallback_used = False
    if norms is not None:
        _LOG.warning(
            "communication_strategy_fallback reason_code=norms_unimplemented"
        )
        strategy = CommunicationStrategy.TRUTHFUL
        stance = SpeakerStance.ASSERT_MATCH
        divergence = CommunicationDivergence.NONE
        fallback_used = True
    else:
        _LOG.debug("communication_strategy_norms reason_code=norms_unavailable")
        strategy, stance, divergence = _select_rule(
            factors, tokens=tokens, source_confidence=confidence
        )
    stored = _store_factors(factors)
    intent = communication_intent(
        owner_id=owner_id,
        recipient_id=recipient_id,
        tick=tick,
        strategy=strategy,
        stance=stance,
        divergence=divergence,
        source_basis=source_basis,
        source_confidence=confidence,
        source_atom_tokens=tokens,
        cited_event_id=cited_event_id,
        factor_codes=stored,
        delivered=strategy is not CommunicationStrategy.OMISSION,
    )
    audit = CommunicationIntentAudit(
        intent_id=intent.intent_id,
        owner_id=intent.owner_id,
        recipient_id=intent.recipient_id,
        tick=intent.tick,
        strategy=intent.strategy,
        stance=intent.stance,
        divergence=intent.divergence,
        source_basis=intent.source_basis,
        source_confidence=intent.source_confidence,
        source_atom_tokens=intent.source_atom_tokens,
        cited_event_id=intent.cited_event_id,
        factor_codes=intent.factor_codes,
        delivered=intent.delivered,
        fallback_used=fallback_used,
    )
    _LOG.debug(
        "communication_strategy_chosen owner_id=%s tick=%s recipient_id=%s "
        "strategy=%s stance=%s divergence=%s factor_codes=%s confidence_band=%s",
        owner_id.value,
        intent.tick,
        recipient_id.value,
        strategy.value,
        stance.value,
        divergence.value,
        ",".join(item.value for item in stored),
        confidence_band(intent.source_confidence),
    )
    if strategy is not CommunicationStrategy.TRUTHFUL:
        _LOG.info(
            "communication_strategy_choice strategy=%s stance=%s",
            strategy.value,
            stance.value,
        )
    del alternate
    return intent, audit


def _disclosed_atom(tokens: Sequence[str]) -> str:
    for token in tokens:
        if token in _ALLOWLISTED_CONCEPTS:
            return token
    return tokens[0]


def _render_tokens(
    intent: CommunicationIntent,
    observation: Observation | None,
) -> tuple[str, ...]:
    tokens = intent.source_atom_tokens
    strategy = intent.strategy
    if strategy is CommunicationStrategy.SELECTIVE_DISCLOSURE:
        if len(tokens) <= 1:
            return tokens
        return (_disclosed_atom(tokens),)
    if strategy is CommunicationStrategy.DELIBERATE_FALSE_STATEMENT:
        found = _alternate_for(tokens, _held_tokens(observation))
        if found is None:
            return tokens
        index, alternate = found
        rendered = tuple(
            alternate if offset == index else token
            for offset, token in enumerate(tokens)
        )
        return rendered
    return tokens


def _utterance_text(tokens: Sequence[str], *, ask: bool) -> str:
    if not tokens:
        return _SAFE_ASK if ask else _SAFE_HELLO
    first = tokens[0]
    if first == "uncertain":
        return _SAFE_ASK if ask else _SAFE_HELLO
    return first


def render_communication_intent(
    intent: CommunicationIntent,
    *,
    speaker_id: EntityId,
    recipient_entity_id: EntityId,
    action_kind: str,
    observation: object | None = None,
) -> Talk | Ask | Tell | None:
    """Render one command. Omission returns None. The command has no strategy."""
    if type(intent) is not CommunicationIntent:
        raise _fail("intent", "invalid_type")
    if type(speaker_id) is not EntityId:
        raise _fail("speaker_id", "invalid_type")
    if type(recipient_entity_id) is not EntityId:
        raise _fail("recipient_entity_id", "invalid_type")
    if intent.strategy is CommunicationStrategy.OMISSION or not intent.delivered:
        return None
    view = _require_observation(observation)
    source = intent.source_basis
    confidence = intent.source_confidence
    if intent.strategy is CommunicationStrategy.EXAGGERATION:
        confidence = 1.0
    tokens = _render_tokens(intent, view)
    kind = action_kind
    relations: tuple[CommunicationRelation, ...] = ()
    if intent.strategy is CommunicationStrategy.UNCERTAIN:
        kind = "ask"
        if action_kind == "tell" and tokens:
            relations = (
                CommunicationRelation(
                    subject=speaker_id.value,
                    predicate="uncertain",
                    object=tokens[0],
                ),
            )
    elif intent.strategy is CommunicationStrategy.REFUSAL:
        kind = "talk"
        tokens = ()
        decline_object = recipient_entity_id.value
        if decline_object in intent.source_atom_tokens:
            decline_object = speaker_id.value
        if decline_object in intent.source_atom_tokens:
            decline_object = "none"
        relations = (
            CommunicationRelation(
                subject=speaker_id.value,
                predicate="decline",
                object=decline_object,
            ),
        )
        reject_empty_refusal_render(
            intent.strategy,
            rendered_predicates=("decline",),
            rendered_object_tokens=(),
        )
        if any(token in intent.source_atom_tokens for token in (decline_object,)):
            if decline_object in intent.source_atom_tokens:
                raise _fail("rendered_object_tokens", "empty_refusal_render")
    ask = kind == "ask"
    utterance = origin_utterance(
        text=_utterance_text(tokens, ask=ask) if tokens else (
            "decline" if intent.strategy is CommunicationStrategy.REFUSAL else (
                _SAFE_ASK if ask else _SAFE_HELLO
            )
        ),
        speaker_id=speaker_id,
        communication_id=intent.intent_id,
        sender_confidence=confidence,
        source_basis=source,
        concepts=tokens,
        relations=relations,
    )
    if intent.strategy is CommunicationStrategy.REFUSAL and utterance.content.concepts:
        raise _fail("rendered_predicates", "empty_refusal_render")
    if kind == "ask":
        return Ask(recipient_id=recipient_entity_id, utterance=utterance)
    if kind == "tell":
        return Tell(recipient_id=recipient_entity_id, utterance=utterance)
    if kind == "talk":
        return Talk(recipient_id=recipient_entity_id, utterance=utterance)
    raise _fail("action_kind", "unknown_enum")


def apply_communication_strategy(
    *,
    owner_id: AgentId,
    recipient_id: AgentId,
    recipient_entity_id: EntityId,
    speaker_id: EntityId,
    tick: int,
    source_basis: CommunicationSourceBasis,
    source_confidence: float,
    source_atom_tokens: Sequence[str],
    action_kind: str,
    cited_event_id: str | None = None,
    policy: CommunicationStrategyPolicy | None = None,
    goal_board: GoalBoard | None = None,
    relationships: Sequence[DirectedRelationshipProfile] | None = None,
    mind: TheoryOfMind | None = None,
    mind_policy: TheoryOfMindPolicy | None = None,
    risks: Sequence[SubjectiveRisk] | None = None,
    self_model: SelfModel | None = None,
    emotional_state: EmotionalStateEvaluation | None = None,
    observation: object | None = None,
    owner_entity_id: EntityId | None = None,
    epistemic_judgment: EpistemicJudgment | None = None,
    norms: object | None = None,
) -> tuple[Talk | Ask | Tell | None, CommunicationIntent, CommunicationIntentAudit]:
    """Choose and render. The world receives only the command."""
    intent, audit = choose_communication_strategy(
        owner_id=owner_id,
        recipient_id=recipient_id,
        recipient_entity_id=recipient_entity_id,
        tick=tick,
        source_basis=source_basis,
        source_confidence=source_confidence,
        source_atom_tokens=source_atom_tokens,
        cited_event_id=cited_event_id,
        policy=policy,
        goal_board=goal_board,
        relationships=relationships,
        mind=mind,
        mind_policy=mind_policy,
        risks=risks,
        self_model=self_model,
        emotional_state=emotional_state,
        observation=observation,
        owner_entity_id=owner_entity_id,
        epistemic_judgment=epistemic_judgment,
        norms=norms,
    )
    command = render_communication_intent(
        intent,
        speaker_id=speaker_id,
        recipient_entity_id=recipient_entity_id,
        action_kind=action_kind,
        observation=observation,
    )
    return command, intent, audit
