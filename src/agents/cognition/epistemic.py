"""Owner-scoped flat epistemic ledger beside first-order mind hypotheses.

Rows are private to the store owner. Nesting is an integer plus a chain of
agent ids. This module does not read world authority, another agent's mind,
or an LLM.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.models import _EFFECT_QUANTUM
from agents.cognition.theory_of_mind import TheoryOfMind, confidence_from_masses
from agents.models import AgentId
from memory import BeliefActivationState, SemanticBelief
from world.communications import CommunicationRelation
from world.identifiers import require_exact_nonneg_int, require_stable_id
from world.observations import Observation, ObservedCommunication

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.epistemic")

EPISTEMIC_POLICY_VERSION: Final[str] = "epistemic-model-v1"
_ID_PREFIX: Final[str] = "ep-"
_PRIOR: Final[float] = 1.0
_KNOWS_THRESHOLD: Final[float] = 0.8
_BELIEVES_THRESHOLD: Final[float] = 0.55
_CONTRADICTION_THRESHOLD: Final[float] = 0.5
_ACTION_THRESHOLD: Final[float] = 0.55
_MAX_EPISTEMIC_DEPTH: Final[int] = 3
_UPDATER_DEPTH: Final[int] = 2
_MAX_ATTRIBUTIONS: Final[int] = 64
_MAX_HISTORY: Final[int] = 32
_MAX_WITNESSES: Final[int] = 16
_BEHAVIOR_WEIGHT: Final[float] = 4.0
_TESTIMONY_WEIGHT: Final[float] = 2.0
_CONCEPTS: Final[frozenset[str]] = frozenset({"food", "water", "rest", "danger"})
_TESTIMONY_ATTITUDES: Final[dict[str, str]] = {
    "knows": "knows",
    "believes": "believes",
    "uncertain": "uncertain",
    "does_not_know": "does_not_know",
}
_NESTED_OBJECTS: Final[frozenset[str]] = frozenset(
    {
        "believes",
        "thinks",
        "wants",
        "feels",
        "knows",
        "intends",
        "uncertain",
        "does_not_know",
    }
)
_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {"WorldState", "PhysicalRules", "AgentBody"}
)


class EpistemicAttitude(StrEnum):
    """Closed attitude stored on one ledger row."""

    KNOWS = "knows"
    BELIEVES = "believes"
    UNCERTAIN = "uncertain"
    DOES_NOT_KNOW = "does_not_know"


class EpistemicSource(StrEnum):
    """Closed provenance class for one ledger row."""

    SEMANTIC_BELIEF = "semantic_belief"
    OBSERVED_BEHAVIOR = "observed_behavior"
    COMMUNICATION = "communication"
    DERIVED = "derived"


class EpistemicJudgment(StrEnum):
    """Closed disclosure judgment. Secret is not a stored attitude."""

    NEW = "new"
    ALREADY_KNOWN = "already_known"
    SECRET = "secret"
    UNCERTAIN = "uncertain"
    CONTRADICTORY = "contradictory"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "epistemic_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _quantize_mass(value: float) -> float:
    steps = round(value / _EFFECT_QUANTUM)
    if steps == 0:
        return 0.0
    quantized = float(Decimal(steps) * Decimal(str(_EFFECT_QUANTUM)))
    return 0.0 if quantized == 0.0 else quantized


def _finite_nonnegative(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise _fail(field_name, "not_finite")
    return _quantize_mass(number)


def _unit_quantum(field_name: str, value: object) -> float:
    number = _finite_nonnegative(field_name, value)
    if number > 1.0:
        raise _fail(field_name, "not_unit_interval")
    return number


def _positive_quantum(field_name: str, value: object) -> float:
    number = _finite_nonnegative(field_name, value)
    if number <= 0.0:
        raise _fail(field_name, "not_positive")
    return number


def _depth_int(field_name: str, value: object, *, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(field_name, "invalid_type")
    if value < 0 or value > upper:
        raise _fail(field_name, "epistemic_depth_rejected")
    return value


def _bounded_cap(field_name: str, value: object, *, upper: int) -> int:
    try:
        number = require_exact_nonneg_int(field_name, value)
    except ValueError as exc:
        raise _fail(field_name, "not_positive") from exc
    if number < 1 or number > upper:
        raise _fail(field_name, "out_of_bounds")
    return number


def _id_tuple(name: str, values: object, *, limit: int) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _fail(name, "invalid_type")
    if isinstance(values, (set, frozenset)):
        raise _fail(name, "invalid_type")
    resolved: list[str] = []
    for item in values:
        try:
            token = require_stable_id(name, item)
        except ValueError as exc:
            raise _fail(name, "invalid_value") from exc
        if token not in resolved:
            resolved.append(token)
    overflow = len(resolved) - limit
    if overflow > 0:
        if name == "witness_ids":
            resolved = sorted(resolved)[:limit]
        else:
            del resolved[:overflow]
    return tuple(resolved)


def _validate_proposition(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail("proposition_ref", "empty_proposition")
    if value != value.strip() or "|" in value or "=" in value:
        raise _fail("proposition_ref", "proposition_rejected")
    if value in _CONCEPTS:
        return value
    if value.startswith("belief:"):
        token = value.removeprefix("belief:")
        try:
            require_stable_id("proposition_ref", token)
        except ValueError as exc:
            raise _fail("proposition_ref", "proposition_rejected") from exc
        return value
    if value.startswith("fact:"):
        rest = value.removeprefix("fact:")
        kind, separator, location = rest.partition(":")
        if not separator or not kind or not location or ":" in location:
            raise _fail("proposition_ref", "proposition_rejected")
        try:
            require_stable_id("proposition_ref", kind)
            if location != "none":
                require_stable_id("proposition_ref", location)
        except ValueError as exc:
            raise _fail("proposition_ref", "proposition_rejected") from exc
        return value
    raise _fail("proposition_ref", "proposition_rejected")


def epistemic_proposition_ref(
    *,
    belief_id: str | None = None,
    occurrence_kind: str | None = None,
    location_id: str | None = None,
) -> str:
    """Stable ``belief:`` or ``fact:`` key. Not stored prose."""
    if belief_id is not None and occurrence_kind is None:
        try:
            token = require_stable_id("belief_id", belief_id)
        except ValueError as exc:
            raise _fail("belief_id", "invalid_value") from exc
        return _validate_proposition(f"belief:{token}")
    if belief_id is None and occurrence_kind is not None:
        try:
            kind = require_stable_id("occurrence_kind", occurrence_kind)
        except ValueError as exc:
            raise _fail("occurrence_kind", "invalid_value") from exc
        location = "none" if location_id is None else location_id
        if location != "none":
            try:
                location = require_stable_id("location_id", location)
            except ValueError as exc:
                raise _fail("location_id", "invalid_value") from exc
        return _validate_proposition(f"fact:{kind}:{location}")
    raise _fail("proposition_ref", "proposition_rejected")


def epistemic_attribution_id_for(
    *,
    owner_id: AgentId,
    nesting_level: int,
    modeled_agents: Sequence[str],
    attitude: EpistemicAttitude,
    proposition_ref: str,
) -> str:
    """sha256 of owner, depth, agent chain, attitude, and proposition ref."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(attitude) is not EpistemicAttitude:
        raise _fail("attitude", "unknown_enum")
    chain = "\x1f".join(modeled_agents)
    material = (
        f"{EPISTEMIC_POLICY_VERSION}|{owner_id.value}|{nesting_level}|"
        f"{chain}|{attitude.value}|{proposition_ref}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{_ID_PREFIX}{digest[:48]}"


def _attitude_from_confidence(
    confidence: float,
    contradiction_mass: float,
    policy: EpistemicPolicy,
) -> EpistemicAttitude:
    if contradiction_mass >= policy.contradiction_threshold:
        return EpistemicAttitude.UNCERTAIN
    if confidence >= policy.knows_threshold and contradiction_mass == 0.0:
        return EpistemicAttitude.KNOWS
    if confidence >= policy.believes_threshold:
        return EpistemicAttitude.BELIEVES
    return EpistemicAttitude.UNCERTAIN


@dataclass(frozen=True, slots=True)
class EpistemicAttribution:
    """One flat ledger row. The owner is implicit and is not in the chain."""

    owner_id: AgentId
    proposition_ref: str
    attitude: EpistemicAttitude
    support: float
    counter: float
    confidence: float
    source: EpistemicSource
    nesting_level: int
    belief_id: str | None = None
    modeled_agents: tuple[str, ...] = ()
    contradiction_mass: float = 0.0
    provenance_ids: tuple[str, ...] = ()
    witness_ids: tuple[str, ...] = ()
    updated_tick: int = 0
    attribution_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        proposition = _validate_proposition(self.proposition_ref)
        object.__setattr__(self, "proposition_ref", proposition)
        if type(self.attitude) is not EpistemicAttitude:
            raise _fail("attitude", "unknown_enum")
        if type(self.source) is not EpistemicSource:
            raise _fail("source", "unknown_enum")
        if isinstance(self.nesting_level, bool) or not isinstance(
            self.nesting_level, int
        ):
            raise _fail("nesting_level", "invalid_type")
        if self.nesting_level < 1 or self.nesting_level > _MAX_EPISTEMIC_DEPTH:
            raise _fail("nesting_level", "epistemic_depth_rejected")
        agents = _id_tuple(
            "modeled_agents",
            self.modeled_agents,
            limit=_MAX_EPISTEMIC_DEPTH,
        )
        if len(agents) != self.nesting_level - 1:
            raise _fail("modeled_agents", "epistemic_depth_rejected")
        if self.owner_id.value in agents:
            raise _fail("modeled_agents", "self_subject")
        object.__setattr__(self, "modeled_agents", agents)
        if (
            self.nesting_level == 1
            and self.attitude is EpistemicAttitude.DOES_NOT_KNOW
        ):
            raise _fail("attitude", "epistemic_attitude_rejected")
        belief_id = self.belief_id
        if proposition.startswith("belief:"):
            token = proposition.removeprefix("belief:")
            if belief_id is None:
                belief_id = token
            elif belief_id != token:
                raise _fail("belief_id", "proposition_rejected")
        elif belief_id is not None:
            raise _fail("belief_id", "proposition_rejected")
        if belief_id is not None:
            try:
                belief_id = require_stable_id("belief_id", belief_id)
            except ValueError as exc:
                raise _fail("belief_id", "invalid_value") from exc
        object.__setattr__(self, "belief_id", belief_id)
        object.__setattr__(
            self, "support", _finite_nonnegative("support", self.support)
        )
        object.__setattr__(
            self, "counter", _finite_nonnegative("counter", self.counter)
        )
        object.__setattr__(
            self, "confidence", _unit_quantum("confidence", self.confidence)
        )
        object.__setattr__(
            self,
            "contradiction_mass",
            _unit_quantum("contradiction_mass", self.contradiction_mass),
        )
        object.__setattr__(
            self,
            "provenance_ids",
            _id_tuple("provenance_ids", self.provenance_ids, limit=_MAX_HISTORY),
        )
        object.__setattr__(
            self,
            "witness_ids",
            _id_tuple("witness_ids", self.witness_ids, limit=_MAX_WITNESSES),
        )
        try:
            tick = require_exact_nonneg_int("updated_tick", self.updated_tick)
        except ValueError as exc:
            raise _fail("updated_tick", "not_positive") from exc
        object.__setattr__(self, "updated_tick", tick)
        object.__setattr__(
            self,
            "attribution_id",
            epistemic_attribution_id_for(
                owner_id=self.owner_id,
                nesting_level=self.nesting_level,
                modeled_agents=agents,
                attitude=self.attitude,
                proposition_ref=proposition,
            ),
        )
        _LOG.debug(
            "epistemic_attribution_constructed owner_id=%s policy_version=%s "
            "nesting_level=%s attribution_count=%s",
            self.owner_id.value,
            EPISTEMIC_POLICY_VERSION,
            self.nesting_level,
            1,
        )


@dataclass(frozen=True, slots=True)
class EpistemicPolicy:
    """``epistemic-model-v1`` thresholds. Not a runner JSON key."""

    version: str = EPISTEMIC_POLICY_VERSION
    prior: float = _PRIOR
    knows_threshold: float = _KNOWS_THRESHOLD
    believes_threshold: float = _BELIEVES_THRESHOLD
    contradiction_threshold: float = _CONTRADICTION_THRESHOLD
    action_threshold: float = _ACTION_THRESHOLD
    max_depth: int = 2
    hard_ceiling: int = _MAX_EPISTEMIC_DEPTH
    max_attributions: int = _MAX_ATTRIBUTIONS
    max_history: int = _MAX_HISTORY

    def __post_init__(self) -> None:
        if self.version != EPISTEMIC_POLICY_VERSION:
            raise _fail("version", "unsupported")
        object.__setattr__(self, "prior", _positive_quantum("prior", self.prior))
        object.__setattr__(
            self,
            "knows_threshold",
            _unit_quantum("knows_threshold", self.knows_threshold),
        )
        object.__setattr__(
            self,
            "believes_threshold",
            _unit_quantum("believes_threshold", self.believes_threshold),
        )
        object.__setattr__(
            self,
            "contradiction_threshold",
            _unit_quantum("contradiction_threshold", self.contradiction_threshold),
        )
        object.__setattr__(
            self,
            "action_threshold",
            _unit_quantum("action_threshold", self.action_threshold),
        )
        object.__setattr__(
            self,
            "max_depth",
            _depth_int("max_depth", self.max_depth, upper=_MAX_EPISTEMIC_DEPTH),
        )
        if self.hard_ceiling != _MAX_EPISTEMIC_DEPTH:
            raise _fail("hard_ceiling", "epistemic_depth_rejected")
        object.__setattr__(
            self,
            "max_attributions",
            _bounded_cap(
                "max_attributions",
                self.max_attributions,
                upper=_MAX_ATTRIBUTIONS,
            ),
        )
        object.__setattr__(
            self,
            "max_history",
            _bounded_cap("max_history", self.max_history, upper=_MAX_HISTORY),
        )
        _LOG.debug(
            "epistemic_policy_constructed owner_id=%s policy_version=%s "
            "nesting_level=%s attribution_count=%s",
            "",
            self.version,
            self.max_depth,
            0,
        )


def default_epistemic_policy() -> EpistemicPolicy:
    """Return ``epistemic-model-v1`` with ``max_depth`` 2."""
    return EpistemicPolicy()


@dataclass(frozen=True, slots=True)
class EpistemicDisclosure:
    """One judgment for a recipient and a proposition the owner holds."""

    judgment: EpistemicJudgment
    proposition_ref: str
    recipient_id: str
    attribution_id: str | None
    confidence: float

    def __post_init__(self) -> None:
        if type(self.judgment) is not EpistemicJudgment:
            raise _fail("judgment", "unknown_enum")
        object.__setattr__(
            self, "proposition_ref", _validate_proposition(self.proposition_ref)
        )
        try:
            recipient = require_stable_id("recipient_id", self.recipient_id)
        except ValueError as exc:
            raise _fail("recipient_id", "invalid_value") from exc
        object.__setattr__(self, "recipient_id", recipient)
        if self.attribution_id is not None:
            try:
                attribution_id = require_stable_id(
                    "attribution_id", self.attribution_id
                )
            except ValueError as exc:
                raise _fail("attribution_id", "invalid_value") from exc
            object.__setattr__(self, "attribution_id", attribution_id)
        object.__setattr__(
            self, "confidence", _unit_quantum("confidence", self.confidence)
        )


def _reject_forbidden(value: object, field_name: str) -> None:
    if type(value).__name__ in _FORBIDDEN_TYPES:
        raise TypeError(f"{field_name} must not be {type(value).__name__}")


def _require_beliefs(beliefs: object) -> tuple[SemanticBelief, ...]:
    _reject_forbidden(beliefs, "beliefs")
    if isinstance(beliefs, (str, bytes)) or not isinstance(beliefs, Sequence):
        raise TypeError("beliefs must be a sequence of SemanticBelief")
    if isinstance(beliefs, (set, frozenset)):
        raise TypeError("beliefs must be a sequence of SemanticBelief")
    resolved: list[SemanticBelief] = []
    for item in beliefs:
        _reject_forbidden(item, "beliefs")
        if type(item) is not SemanticBelief:
            raise TypeError("beliefs must be a sequence of SemanticBelief")
        resolved.append(item)
    return tuple(resolved)


def _with_attributions(
    model: TheoryOfMind,
    attributions: tuple[EpistemicAttribution, ...],
) -> TheoryOfMind:
    return TheoryOfMind(
        owner_id=model.owner_id,
        hypotheses=model.hypotheses,
        cue_cursor=model.cue_cursor,
        last_tick=model.last_tick,
        preferred_ids=model.preferred_ids,
        selection_fallback_used=model.selection_fallback_used,
        attributions=attributions,
    )


def _row_key(row: EpistemicAttribution) -> tuple[int, tuple[str, ...], str, str]:
    return (
        row.nesting_level,
        row.modeled_agents,
        row.attitude.value,
        row.proposition_ref,
    )


def _level1_key(proposition_ref: str) -> tuple[int, str]:
    return (1, proposition_ref)


def _visible_ids(observation: Observation, owner: AgentId) -> tuple[str, ...]:
    excluded = {owner.value, observation.observer_id.value}
    return tuple(
        body.entity_id.value
        for body in observation.visible_bodies
        if body.entity_id.value not in excluded
    )


def _cap_witnesses(ids: Sequence[str]) -> tuple[str, ...]:
    unique = tuple(dict.fromkeys(ids))
    if len(unique) <= _MAX_WITNESSES:
        return unique
    return tuple(sorted(unique)[:_MAX_WITNESSES])


def _append_provenance(
    existing: tuple[str, ...], extra: str, limit: int
) -> tuple[str, ...]:
    values = list(existing)
    if extra not in values:
        values.append(extra)
    overflow = len(values) - limit
    if overflow > 0:
        del values[:overflow]
    return tuple(values)


def _make_row(
    *,
    owner_id: AgentId,
    proposition_ref: str,
    attitude: EpistemicAttitude,
    support: float,
    counter: float,
    confidence: float,
    source: EpistemicSource,
    nesting_level: int,
    tick: int,
    belief_id: str | None = None,
    modeled_agents: tuple[str, ...] = (),
    contradiction_mass: float = 0.0,
    provenance_ids: tuple[str, ...] = (),
    witness_ids: tuple[str, ...] = (),
) -> EpistemicAttribution:
    return EpistemicAttribution(
        owner_id=owner_id,
        proposition_ref=proposition_ref,
        attitude=attitude,
        support=support,
        counter=counter,
        confidence=confidence,
        source=source,
        nesting_level=nesting_level,
        belief_id=belief_id,
        modeled_agents=modeled_agents,
        contradiction_mass=contradiction_mass,
        provenance_ids=provenance_ids,
        witness_ids=witness_ids,
        updated_tick=tick,
    )


def _drop(reason_code: str) -> None:
    _LOG.warning("epistemic_cue_dropped reason_code=%s", reason_code)


def _find(
    rows: Sequence[EpistemicAttribution],
    *,
    nesting_level: int,
    proposition_ref: str,
    modeled_agents: tuple[str, ...] = (),
    attitudes: frozenset[EpistemicAttitude] | None = None,
) -> EpistemicAttribution | None:
    for row in rows:
        if row.nesting_level != nesting_level:
            continue
        if row.proposition_ref != proposition_ref:
            continue
        if row.modeled_agents != modeled_agents:
            continue
        if attitudes is not None and row.attitude not in attitudes:
            continue
        return row
    return None


def _replace(
    rows: list[EpistemicAttribution],
    row: EpistemicAttribution,
    *,
    level1: bool,
) -> bool:
    """Insert ``row``. Return whether it was created rather than refreshed."""
    created = True
    kept: list[EpistemicAttribution] = []
    for item in rows:
        same_level1 = level1 and _level1_key(item.proposition_ref) == _level1_key(
            row.proposition_ref
        )
        same_key = _row_key(item) == _row_key(row)
        if same_level1 and item.nesting_level == 1:
            created = False
            continue
        if same_key:
            created = False
            continue
        kept.append(item)
    kept.append(row)
    rows[:] = kept
    return created


def _evict(
    rows: list[EpistemicAttribution], limit: int
) -> int:
    dropped = 0
    while len(rows) > limit:
        lowest = min(item.confidence for item in rows)
        candidates = [item for item in rows if item.confidence == lowest]
        oldest = min(item.updated_tick for item in candidates)
        oldest_rows = [item for item in candidates if item.updated_tick == oldest]
        victim = max(oldest_rows, key=lambda item: item.attribution_id)
        rows.remove(victim)
        dropped += 1
    return dropped


def _apply_beliefs(
    rows: list[EpistemicAttribution],
    *,
    beliefs: Sequence[SemanticBelief],
    observation: Observation,
    policy: EpistemicPolicy,
    owner: AgentId,
) -> tuple[int, int]:
    created = 0
    dropped = 0
    witnesses = (
        _visible_ids(observation, owner) if observation.occurrences else ()
    )
    for belief in beliefs:
        if belief.owner_id != owner:
            _LOG.error(
                "epistemic_owner_mismatch owner_id=%s field=owner_id "
                "reason_code=owner_mismatch",
                owner.value,
            )
            raise _fail("owner_id", "owner_mismatch")
        if belief.activation_state is not BeliefActivationState.ACTIVE:
            dropped += 1
            _drop("belief_inactive")
            continue
        proposition = epistemic_proposition_ref(belief_id=belief.belief_id.value)
        prior = _find(rows, nesting_level=1, proposition_ref=proposition)
        prior_witnesses = () if prior is None else prior.witness_ids
        if observation.occurrences:
            merged = _cap_witnesses((*prior_witnesses, *witnesses))
        else:
            merged = prior_witnesses
        provenance = () if prior is None else prior.provenance_ids
        confidence = _unit_quantum("confidence", belief.confidence.confidence)
        contradiction = _unit_quantum(
            "contradiction_mass", belief.confidence.contradiction_mass
        )
        attitude = _attitude_from_confidence(confidence, contradiction, policy)
        row = _make_row(
            owner_id=owner,
            proposition_ref=proposition,
            attitude=attitude,
            support=belief.confidence.support_mass,
            counter=belief.confidence.contradiction_mass,
            confidence=confidence,
            source=EpistemicSource.SEMANTIC_BELIEF,
            nesting_level=1,
            tick=observation.tick,
            belief_id=belief.belief_id.value,
            contradiction_mass=contradiction,
            provenance_ids=_append_provenance(
                provenance, belief.belief_id.value, policy.max_history
            ),
            witness_ids=merged,
        )
        if _replace(rows, row, level1=True):
            created += 1
    return created, dropped


def _apply_occurrences(
    rows: list[EpistemicAttribution],
    *,
    observation: Observation,
    policy: EpistemicPolicy,
    owner: AgentId,
) -> int:
    created = 0
    witnesses = _visible_ids(observation, owner)
    support = _BEHAVIOR_WEIGHT
    confidence = confidence_from_masses(support, 0.0, prior=policy.prior)
    attitude = _attitude_from_confidence(confidence, 0.0, policy)
    for occurrence in observation.occurrences:
        location = (
            None
            if occurrence.destination_id is None
            else occurrence.destination_id.value
        )
        try:
            proposition = epistemic_proposition_ref(
                occurrence_kind=occurrence.kind,
                location_id=location,
            )
        except ValueError:
            _drop("proposition_rejected")
            continue
        event_id = occurrence.provenance.source_event_id
        provenance_id = "" if event_id is None else event_id.value
        prior = _find(rows, nesting_level=1, proposition_ref=proposition)
        prior_witnesses = () if prior is None else prior.witness_ids
        prior_provenance = () if prior is None else prior.provenance_ids
        row = _make_row(
            owner_id=owner,
            proposition_ref=proposition,
            attitude=attitude,
            support=support,
            counter=0.0,
            confidence=confidence,
            source=EpistemicSource.OBSERVED_BEHAVIOR,
            nesting_level=1,
            tick=observation.tick,
            provenance_ids=_append_provenance(
                prior_provenance, provenance_id, policy.max_history
            )
            if provenance_id
            else prior_provenance,
            witness_ids=_cap_witnesses((*prior_witnesses, *witnesses)),
        )
        if _replace(rows, row, level1=True):
            created += 1
    return created


def _derive_knows(
    rows: list[EpistemicAttribution],
    *,
    policy: EpistemicPolicy,
    owner: AgentId,
    tick: int,
) -> int:
    created = 0
    parents = [
        row
        for row in tuple(rows)
        if row.nesting_level == 1
        and row.attitude in {EpistemicAttitude.KNOWS, EpistemicAttitude.BELIEVES}
        and row.source
        in {EpistemicSource.OBSERVED_BEHAVIOR, EpistemicSource.SEMANTIC_BELIEF}
    ]
    for parent in parents:
        for witness in parent.witness_ids:
            if witness == owner.value:
                _drop("self_subject")
                continue
            row = _make_row(
                owner_id=owner,
                proposition_ref=parent.proposition_ref,
                attitude=EpistemicAttitude.KNOWS,
                support=parent.support,
                counter=0.0,
                confidence=parent.confidence,
                source=EpistemicSource.DERIVED,
                nesting_level=2,
                tick=tick,
                modeled_agents=(witness,),
                provenance_ids=(parent.attribution_id,),
            )
            too_deep = (
                row.nesting_level > policy.max_depth
                or row.nesting_level > _UPDATER_DEPTH
            )
            if too_deep:
                _drop("epistemic_depth_exceeded")
                continue
            if _replace(rows, row, level1=False):
                created += 1
    return created


def _derive_ignorance(
    rows: list[EpistemicAttribution],
    *,
    observation: Observation,
    policy: EpistemicPolicy,
    owner: AgentId,
) -> int:
    created = 0
    if policy.max_depth < 2:
        return 0
    visible = _visible_ids(observation, owner)
    parents = [
        row
        for row in tuple(rows)
        if row.nesting_level == 1
        and row.attitude in {EpistemicAttitude.KNOWS, EpistemicAttitude.BELIEVES}
        and row.source
        in {EpistemicSource.OBSERVED_BEHAVIOR, EpistemicSource.SEMANTIC_BELIEF}
    ]
    positive = {EpistemicAttitude.KNOWS, EpistemicAttitude.BELIEVES}
    confidence = confidence_from_masses(_BEHAVIOR_WEIGHT, 0.0, prior=policy.prior)
    for parent in parents:
        for subject in visible:
            if subject == owner.value:
                _drop("self_subject")
                continue
            if subject in parent.witness_ids:
                continue
            existing = _find(
                rows,
                nesting_level=2,
                proposition_ref=parent.proposition_ref,
                modeled_agents=(subject,),
                attitudes=positive,
            )
            if existing is not None and existing.confidence >= policy.action_threshold:
                continue
            row = _make_row(
                owner_id=owner,
                proposition_ref=parent.proposition_ref,
                attitude=EpistemicAttitude.DOES_NOT_KNOW,
                support=_BEHAVIOR_WEIGHT,
                counter=0.0,
                confidence=confidence,
                source=EpistemicSource.DERIVED,
                nesting_level=2,
                tick=observation.tick,
                modeled_agents=(subject,),
                provenance_ids=(parent.attribution_id,),
            )
            if _replace(rows, row, level1=False):
                created += 1
    return created


def _fact_keys(rows: Sequence[EpistemicAttribution]) -> frozenset[str]:
    return frozenset(
        row.proposition_ref for row in rows if row.proposition_ref.startswith("fact:")
    )


def _apply_testimony(
    rows: list[EpistemicAttribution],
    *,
    observation: Observation,
    policy: EpistemicPolicy,
    owner: AgentId,
) -> tuple[int, int]:
    created = 0
    dropped = 0
    if policy.max_depth < 2:
        return 0, 0
    visible = set(_visible_ids(observation, owner))
    known_facts = _fact_keys(rows)
    support = _TESTIMONY_WEIGHT
    confidence = confidence_from_masses(support, 0.0, prior=policy.prior)
    for item in observation.communications:
        if type(item) is not ObservedCommunication:
            raise TypeError("communications must be ObservedCommunication")
        hop = item.utterance.declared.hop_count
        if hop > 1:
            dropped += 1
            _drop("multi_hop_deferred")
            continue
        relations = tuple(item.utterance.content.relations)
        if len(relations) != 1:
            continue
        relation = relations[0]
        if type(relation) is not CommunicationRelation:
            raise TypeError("relations must be CommunicationRelation")
        predicate = relation.predicate
        if predicate not in _TESTIMONY_ATTITUDES:
            continue
        if relation.object in _NESTED_OBJECTS:
            continue
        if hop != 1:
            continue
        subject = relation.subject
        if subject == owner.value or subject == observation.observer_id.value:
            dropped += 1
            _drop("self_subject")
            continue
        if subject not in visible:
            dropped += 1
            _drop("not_visible")
            continue
        if relation.object in _CONCEPTS:
            proposition = relation.object
        elif relation.object in known_facts:
            proposition = relation.object
        else:
            dropped += 1
            _drop("proposition_rejected")
            continue
        attitude = EpistemicAttitude(_TESTIMONY_ATTITUDES[predicate])
        event_id = item.provenance.source_event_id
        provenance_id = "" if event_id is None else event_id.value
        row = _make_row(
            owner_id=owner,
            proposition_ref=proposition,
            attitude=attitude,
            support=support,
            counter=0.0,
            confidence=confidence,
            source=EpistemicSource.COMMUNICATION,
            nesting_level=2,
            tick=observation.tick,
            modeled_agents=(subject,),
            provenance_ids=(provenance_id,) if provenance_id else (),
        )
        if row.nesting_level > _UPDATER_DEPTH:
            dropped += 1
            _drop("epistemic_depth_exceeded")
            continue
        if _replace(rows, row, level1=False):
            created += 1
    return created, dropped


def _log_kept(owner: AgentId, tick: int, row: EpistemicAttribution) -> None:
    _LOG.debug(
        "epistemic_row_kept owner_id=%s tick=%s attribution_id=%s "
        "nesting_level=%s attitude=%s source=%s confidence=%s",
        owner.value,
        tick,
        row.attribution_id,
        row.nesting_level,
        row.attitude.value,
        row.source.value,
        row.confidence,
    )


def update_epistemic_state(
    model: TheoryOfMind,
    observation: Observation,
    beliefs: Sequence[SemanticBelief],
    policy: EpistemicPolicy,
) -> TheoryOfMind:
    """Refresh the owner's ledger. Hypothesis rows are copied unchanged."""
    _LOG.debug(
        "epistemic_update_start owner_id=%s policy_version=%s",
        getattr(getattr(model, "owner_id", None), "value", ""),
        getattr(policy, "version", ""),
    )
    _reject_forbidden(model, "model")
    _reject_forbidden(observation, "observation")
    _reject_forbidden(policy, "policy")
    if type(model) is not TheoryOfMind:
        raise TypeError("model must be TheoryOfMind")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(policy) is not EpistemicPolicy:
        raise TypeError("policy must be EpistemicPolicy")
    resolved_beliefs = _require_beliefs(beliefs)
    for belief in resolved_beliefs:
        if belief.owner_id != model.owner_id:
            _LOG.error(
                "epistemic_owner_mismatch owner_id=%s field=owner_id "
                "reason_code=owner_mismatch",
                model.owner_id.value,
            )
            raise _fail("owner_id", "owner_mismatch")
    if policy.max_depth == 0:
        _LOG.info(
            "epistemic_updated input_belief_count=%s created_count=%s "
            "dropped_count=%s",
            len(resolved_beliefs),
            0,
            0,
        )
        return model
    rows: list[EpistemicAttribution] = []
    dropped = 0
    for item in model.attributions:
        if type(item) is not EpistemicAttribution:
            raise TypeError("attributions must be EpistemicAttribution")
        if item.nesting_level > policy.max_depth or item.nesting_level > _UPDATER_DEPTH:
            dropped += 1
            _drop("epistemic_depth_exceeded")
            continue
        rows.append(item)
    created, inactive = _apply_beliefs(
        rows,
        beliefs=resolved_beliefs,
        observation=observation,
        policy=policy,
        owner=model.owner_id,
    )
    dropped += inactive
    created += _apply_occurrences(
        rows,
        observation=observation,
        policy=policy,
        owner=model.owner_id,
    )
    created += _derive_knows(
        rows,
        policy=policy,
        owner=model.owner_id,
        tick=observation.tick,
    )
    created_testimony, dropped_testimony = _apply_testimony(
        rows,
        observation=observation,
        policy=policy,
        owner=model.owner_id,
    )
    created += created_testimony
    dropped += dropped_testimony
    created += _derive_ignorance(
        rows,
        observation=observation,
        policy=policy,
        owner=model.owner_id,
    )
    kept = [
        row
        for row in rows
        if row.nesting_level <= policy.max_depth and row.nesting_level <= _UPDATER_DEPTH
    ]
    dropped += len(rows) - len(kept)
    if len(rows) != len(kept):
        _drop("epistemic_depth_exceeded")
    dropped += _evict(kept, policy.max_attributions)
    kept.sort(key=lambda item: item.attribution_id)
    for row in kept:
        _log_kept(model.owner_id, observation.tick, row)
    _LOG.info(
        "epistemic_updated input_belief_count=%s created_count=%s dropped_count=%s",
        len(resolved_beliefs),
        created,
        dropped,
    )
    return _with_attributions(model, tuple(kept))
