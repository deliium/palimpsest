"""Owner-scoped causal hypotheses updated from subjective episodes.

Confidence is a support ratio. It is not an engine probability. This module
reads observations and already-retrieved memories. It does not read world
authority, physical rules, or analysis metrics.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Final

from agents.cognition.models import (
    _EFFECT_QUANTUM,
    AgentEmotionalState,
    RetrievedMemoryContext,
)
from agents.models import AgentId
from memory.models import MemoryId, ReconstructedMemory
from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id
from world.observations import (
    Observation,
    ObservedCommunication,
    ObservedItemPlacement,
    ObservedOccurrence,
)
from world.values import DayPhase, ItemKind, WeatherCondition

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.world_model")

WORLD_MODEL_POLICY_VERSION: Final[str] = "world-model-v1"
_ID_PREFIX: Final[str] = "ch-"
_PRIOR: Final[float] = 1.0
_BASE_WEIGHT: Final[float] = 1.0
_SALIENCE_HARM: Final[float] = 4.0
_EMOTION_MULTIPLIER: Final[float] = 2.0
_GENERALIZE_RATE: Final[float] = 0.5
_ACTION_THRESHOLD: Final[float] = 0.55
_EMOTION_THRESHOLD: Final[float] = 0.5
_MILD_COUNTER_WEIGHT: Final[float] = 1.0
_MAX_HYPOTHESES: Final[int] = 64
_MAX_HISTORY: Final[int] = 32
_MAX_ATOMS: Final[int] = 16

_HELP_KINDS: Final[frozenset[str]] = frozenset({"help", "give"})
_SEARCH_KIND: Final[str] = "search"
_ASK_KIND: Final[str] = "ask"
_ATTACK_KIND: Final[str] = "attack"
_FLEE_KIND: Final[str] = "flee"

_DAY_PHASE_VALUES: Final[frozenset[str]] = frozenset(item.value for item in DayPhase)
_WEATHER_VALUES: Final[frozenset[str]] = frozenset(
    item.value for item in WeatherCondition
)
_ITEM_KIND_VALUES: Final[frozenset[str]] = frozenset(item.value for item in ItemKind)
_HELD_TAG: Final[str] = "held_by_self"


class CausalSlot(StrEnum):
    """Closed condition slots copied from subjective records."""

    LOCATION = "location"
    DAY_PHASE = "day_phase"
    WEATHER = "weather"
    COUNTERPART = "counterpart"
    HELD_ITEM_KIND = "held_item_kind"
    ACTION = "action"
    CONCEPT = "concept"
    SEASON = "season"
    TEMPERATURE_BAND = "temperature_band"
    HAZARD = "hazard"


class CausalOutcome(StrEnum):
    """Closed predicted outcomes derived from owner-visible facts."""

    DANGER = "danger"
    HELP = "help"
    SEARCH_SUCCESS = "search_success"
    SEARCH_FAILURE = "search_failure"


class CausalUpdateReason(StrEnum):
    """Closed reason for one arithmetic hypothesis update."""

    SUPPORT = "support"
    COUNTER = "counter"
    GENERALIZE = "generalize"


class CausalProvenanceKind(StrEnum):
    """Where the creating evidence id was copied from."""

    OBSERVATION = "observation"
    MEMORY = "memory"


class CausalEpisodeRole(StrEnum):
    """Whether an episode adds support or only mild counter-mass."""

    SUPPORT = "support"
    COUNTER = "counter"


_SLOT_ORDER: Final[dict[CausalSlot, int]] = {
    slot: index for index, slot in enumerate(CausalSlot)
}
_SEARCH_OUTCOMES: Final[frozenset[CausalOutcome]] = frozenset(
    {CausalOutcome.SEARCH_SUCCESS, CausalOutcome.SEARCH_FAILURE}
)


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "world_model_validation_failed field=%s reason_code=%s",
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


def _quantize_confidence(value: float) -> float:
    quantized = _quantize_mass(value)
    if quantized < 0.0:
        return 0.0
    if quantized > 1.0:
        return 1.0
    return quantized


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


def _bounded_int(field_name: str, value: object, *, upper: int) -> int:
    try:
        number = require_exact_nonneg_int(field_name, value)
    except ValueError as exc:
        raise _fail(field_name, "not_positive") from exc
    if number < 1 or number > upper:
        raise _fail(field_name, "out_of_bounds")
    return number


def canonical_atom_key(atoms: Sequence[CausalAtom]) -> str:
    """Stable slot=value key. Slot order follows ``CausalSlot`` declaration."""
    ordered = tuple(sorted(atoms, key=lambda item: _SLOT_ORDER[item.slot]))
    return "|".join(f"{item.slot.value}={item.value}" for item in ordered)


def hypothesis_id_for(
    *,
    owner_id: AgentId,
    atoms: Sequence[CausalAtom],
    outcome: CausalOutcome,
) -> str:
    """sha256 of owner, canonical atom key, and outcome. No RNG or builtin hash."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(outcome) is not CausalOutcome:
        raise _fail("outcome", "unknown_outcome")
    if not atoms:
        raise _fail("atoms", "empty_atoms")
    material = (
        f"{WORLD_MODEL_POLICY_VERSION}|{owner_id.value}|"
        f"{canonical_atom_key(atoms)}|{outcome.value}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{_ID_PREFIX}{digest[:48]}"


def confidence_from_masses(
    support: float,
    counter: float,
    *,
    prior: float = _PRIOR,
) -> float:
    """``support / (support + counter + prior)`` quantized at ``_EFFECT_QUANTUM``."""
    support_mass = _finite_nonnegative("support", support)
    counter_mass = _finite_nonnegative("counter", counter)
    prior_mass = _positive_quantum("prior", prior)
    total = support_mass + counter_mass + prior_mass
    return _quantize_confidence(support_mass / total)


@dataclass(frozen=True, slots=True)
class CausalAtom:
    """One perceived slot value. The value is a copied token, not prose."""

    slot: CausalSlot
    value: str

    def __post_init__(self) -> None:
        if type(self.slot) is not CausalSlot:
            raise _fail("slot", "unknown_slot")
        try:
            text = require_stable_id("CausalAtom.value", self.value)
        except ValueError as exc:
            raise _fail("value", "invalid_value") from exc
        if "|" in text or "=" in text:
            raise _fail("value", "invalid_value")
        object.__setattr__(self, "value", text)


@dataclass(frozen=True, slots=True)
class CausalUpdateRecord:
    """One arithmetic change. No episode payload."""

    tick: int
    hypothesis_id: str
    support_delta: float
    counter_delta: float
    reason: CausalUpdateReason

    def __post_init__(self) -> None:
        try:
            tick = require_exact_nonneg_int("CausalUpdateRecord.tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "not_positive") from exc
        object.__setattr__(self, "tick", tick)
        try:
            hypothesis_id = require_stable_id(
                "CausalUpdateRecord.hypothesis_id", self.hypothesis_id
            )
        except ValueError as exc:
            raise _fail("hypothesis_id", "invalid_value") from exc
        object.__setattr__(self, "hypothesis_id", hypothesis_id)
        if type(self.reason) is not CausalUpdateReason:
            raise _fail("reason", "unknown_reason")
        support_delta = _finite_nonnegative("support_delta", self.support_delta)
        counter_delta = _finite_nonnegative("counter_delta", self.counter_delta)
        if support_delta == 0.0 and counter_delta == 0.0:
            raise _fail("support_delta", "empty_delta")
        object.__setattr__(self, "support_delta", support_delta)
        object.__setattr__(self, "counter_delta", counter_delta)


@dataclass(frozen=True, slots=True)
class CausalHypothesis:
    """Conditional expectation owned by one agent. Not a semantic belief."""

    owner_id: AgentId
    atoms: tuple[CausalAtom, ...]
    outcome: CausalOutcome
    support: float
    counter: float
    evidence_ids: tuple[str, ...]
    counter_evidence_ids: tuple[str, ...]
    provenance_kind: CausalProvenanceKind
    update_history: tuple[CausalUpdateRecord, ...] = ()
    prior: float = field(default=_PRIOR, repr=False)
    hypothesis_id: str = field(init=False)
    confidence: float = field(init=False)

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.outcome) is not CausalOutcome:
            raise _fail("outcome", "unknown_outcome")
        if type(self.provenance_kind) is not CausalProvenanceKind:
            raise _fail("provenance_kind", "unknown_provenance")
        atoms = _atoms_tuple("atoms", self.atoms)
        object.__setattr__(self, "atoms", atoms)
        support = _finite_nonnegative("support", self.support)
        counter = _finite_nonnegative("counter", self.counter)
        prior = _positive_quantum("prior", self.prior)
        object.__setattr__(self, "support", support)
        object.__setattr__(self, "counter", counter)
        object.__setattr__(self, "prior", prior)
        object.__setattr__(
            self,
            "confidence",
            confidence_from_masses(support, counter, prior=prior),
        )
        object.__setattr__(
            self,
            "hypothesis_id",
            hypothesis_id_for(
                owner_id=self.owner_id, atoms=atoms, outcome=self.outcome
            ),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _id_tuple("evidence_ids", self.evidence_ids),
        )
        object.__setattr__(
            self,
            "counter_evidence_ids",
            _id_tuple("counter_evidence_ids", self.counter_evidence_ids),
        )
        history = _history_tuple(self.update_history, self.hypothesis_id)
        object.__setattr__(self, "update_history", history)

    def last_update_tick(self) -> int:
        if not self.update_history:
            return 0
        return self.update_history[-1].tick

    def latest_reason(self) -> CausalUpdateReason | None:
        if not self.update_history:
            return None
        return self.update_history[-1].reason


@dataclass(frozen=True, slots=True)
class SeasonSuccessorTable:
    """Owner-scoped counts of observed season changes. Not the calendar."""

    previous_season: str | None = None
    transitions: tuple[tuple[str, str, int], ...] = ()

    def observe(self, owner_id: AgentId, season: str) -> SeasonSuccessorTable:
        token = require_stable_id("season", season)
        if self.previous_season is None:
            return SeasonSuccessorTable(
                previous_season=token, transitions=self.transitions
            )
        if self.previous_season == token:
            return self
        transitions = _increment_transition(
            self.transitions, self.previous_season, token
        )
        count = next(
            item[2]
            for item in transitions
            if item[0] == self.previous_season and item[1] == token
        )
        _LOG.debug(
            "season_successor_updated owner_id=%s season=%s successor_count=%s",
            owner_id.value,
            token,
            count,
        )
        return SeasonSuccessorTable(previous_season=token, transitions=transitions)

    def unique_successor(self, season: str) -> str | None:
        recorded = [
            item for item in self.transitions if item[0] == season and item[2] >= 1
        ]
        if not recorded:
            _LOG.info(
                "season_successor_unused reason_code=%s",
                "successor_count_zero",
            )
            return None
        names = {item[1] for item in recorded}
        if len(names) != 1:
            _LOG.info(
                "season_successor_unused reason_code=%s",
                "successor_ambiguous",
            )
            return None
        return next(iter(names))


def _increment_transition(
    transitions: tuple[tuple[str, str, int], ...],
    previous: str,
    successor: str,
) -> tuple[tuple[str, str, int], ...]:
    updated: list[tuple[str, str, int]] = []
    found = False
    for item in transitions:
        if item[0] == previous and item[1] == successor:
            updated.append((previous, successor, item[2] + 1))
            found = True
        else:
            updated.append(item)
    if not found:
        updated.append((previous, successor, 1))
    updated.sort(key=lambda item: (item[0], item[1]))
    return tuple(updated)


@dataclass(frozen=True, slots=True)
class CausalWorldModel:
    """Private hypothesis store for one owner. Flag-off leaves this ``None``."""

    owner_id: AgentId
    hypotheses: tuple[CausalHypothesis, ...] = ()
    last_observed_health: float | None = None
    last_tick: int | None = None
    preferred_ids: tuple[str, ...] = ()
    selection_fallback_used: bool = False
    season_successors: SeasonSuccessorTable = field(
        default_factory=SeasonSuccessorTable
    )

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        hypotheses = _hypotheses_tuple(self.owner_id, self.hypotheses)
        object.__setattr__(self, "hypotheses", hypotheses)
        if self.last_observed_health is not None:
            object.__setattr__(
                self,
                "last_observed_health",
                _health_value("last_observed_health", self.last_observed_health),
            )
        if self.last_tick is not None:
            try:
                tick = require_exact_nonneg_int("last_tick", self.last_tick)
            except ValueError as exc:
                raise _fail("last_tick", "not_positive") from exc
            object.__setattr__(self, "last_tick", tick)
        known = {item.hypothesis_id for item in hypotheses}
        preferred = _id_tuple("preferred_ids", self.preferred_ids)
        if len(set(preferred)) != len(preferred):
            raise _fail("preferred_ids", "schema_invalid")
        if any(item not in known for item in preferred):
            raise _fail("preferred_ids", "foreign_id")
        object.__setattr__(self, "preferred_ids", preferred)
        if type(self.selection_fallback_used) is not bool:
            raise _fail("selection_fallback_used", "invalid_type")
        if type(self.season_successors) is not SeasonSuccessorTable:
            raise _fail("season_successors", "invalid_type")
        _LOG.debug(
            "causal_world_model_constructed owner_id=%s policy_version=%s "
            "hypothesis_count=%s",
            self.owner_id.value,
            WORLD_MODEL_POLICY_VERSION,
            len(self.hypotheses),
        )


@dataclass(frozen=True, slots=True)
class WorldModelPolicy:
    """``world-model-v1`` thresholds. Not a runner JSON key."""

    version: str = WORLD_MODEL_POLICY_VERSION
    prior: float = _PRIOR
    salience_harm: float = _SALIENCE_HARM
    emotion_multiplier: float = _EMOTION_MULTIPLIER
    generalize_rate: float = _GENERALIZE_RATE
    action_threshold: float = _ACTION_THRESHOLD
    emotion_threshold: float = _EMOTION_THRESHOLD
    base_weight: float = _BASE_WEIGHT
    max_hypotheses: int = _MAX_HYPOTHESES
    max_history: int = _MAX_HISTORY
    allow_provider: bool = False

    def __post_init__(self) -> None:
        if self.version != WORLD_MODEL_POLICY_VERSION:
            raise _fail("version", "unsupported")
        object.__setattr__(self, "prior", _positive_quantum("prior", self.prior))
        object.__setattr__(
            self,
            "salience_harm",
            _positive_quantum("salience_harm", self.salience_harm),
        )
        object.__setattr__(
            self,
            "emotion_multiplier",
            _positive_quantum("emotion_multiplier", self.emotion_multiplier),
        )
        object.__setattr__(
            self,
            "generalize_rate",
            _unit_quantum("generalize_rate", self.generalize_rate),
        )
        object.__setattr__(
            self,
            "action_threshold",
            _unit_quantum("action_threshold", self.action_threshold),
        )
        object.__setattr__(
            self,
            "emotion_threshold",
            _unit_quantum("emotion_threshold", self.emotion_threshold),
        )
        object.__setattr__(
            self, "base_weight", _positive_quantum("base_weight", self.base_weight)
        )
        object.__setattr__(
            self,
            "max_hypotheses",
            _bounded_int(
                "max_hypotheses", self.max_hypotheses, upper=_MAX_HYPOTHESES
            ),
        )
        object.__setattr__(
            self,
            "max_history",
            _bounded_int("max_history", self.max_history, upper=_MAX_HISTORY),
        )
        if type(self.allow_provider) is not bool:
            raise _fail("allow_provider", "invalid_type")
        _LOG.debug(
            "world_model_policy_constructed policy_version=%s",
            self.version,
        )


def default_world_model_policy(*, allow_provider: bool = False) -> WorldModelPolicy:
    """Return ``world-model-v1``. Provider calls stay off unless a test opts in."""
    if type(allow_provider) is not bool:
        raise _fail("allow_provider", "invalid_type")
    return WorldModelPolicy(allow_provider=allow_provider)


def empty_world_model(owner_id: AgentId) -> CausalWorldModel:
    """An owner store with no hypotheses and no health cursor."""
    return CausalWorldModel(owner_id=owner_id)


@dataclass(frozen=True, slots=True)
class CausalEpisode:
    """One outcome episode. One value per slot. Not stored on the hypothesis."""

    owner_id: AgentId
    tick: int
    outcome: CausalOutcome
    atoms: tuple[CausalAtom, ...]
    evidence_id: str
    provenance_kind: CausalProvenanceKind
    role: CausalEpisodeRole = CausalEpisodeRole.SUPPORT

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.outcome) is not CausalOutcome:
            raise _fail("outcome", "unknown_outcome")
        if type(self.provenance_kind) is not CausalProvenanceKind:
            raise _fail("provenance_kind", "unknown_provenance")
        if type(self.role) is not CausalEpisodeRole:
            raise _fail("role", "unknown_role")
        try:
            tick = require_exact_nonneg_int("CausalEpisode.tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "not_positive") from exc
        object.__setattr__(self, "tick", tick)
        atoms = _atoms_tuple("atoms", self.atoms)
        object.__setattr__(self, "atoms", atoms)
        try:
            evidence_id = require_stable_id("evidence_id", self.evidence_id)
        except ValueError as exc:
            raise _fail("evidence_id", "invalid_value") from exc
        object.__setattr__(self, "evidence_id", evidence_id)


@dataclass
class _Acc:
    owner_id: AgentId
    atoms: tuple[CausalAtom, ...]
    outcome: CausalOutcome
    support: float
    counter: float
    evidence_ids: list[str]
    counter_evidence_ids: list[str]
    provenance_kind: CausalProvenanceKind
    history: list[CausalUpdateRecord]
    prior: float
    hypothesis_id: str
    existed: bool


def update_world_model(
    model: CausalWorldModel,
    episodes: Sequence[CausalEpisode],
    policy: WorldModelPolicy,
    *,
    tick: int,
    observed_health: float | None = None,
    emotional_state: AgentEmotionalState | None = None,
) -> CausalWorldModel:
    """Apply support, mild counters, and one-step overgeneralization."""
    _LOG.debug(
        "update_world_model_enter owner_id=%s tick=%s episode_count=%s",
        model.owner_id.value if type(model) is CausalWorldModel else None,
        tick,
        len(episodes) if isinstance(episodes, Sequence) else None,
    )
    if type(model) is not CausalWorldModel:
        raise _fail("model", "invalid_type")
    if type(policy) is not WorldModelPolicy:
        raise _fail("policy", "invalid_type")
    try:
        resolved_tick = require_exact_nonneg_int("tick", tick)
    except ValueError as exc:
        raise _fail("tick", "not_positive") from exc
    if emotional_state is not None:
        if type(emotional_state) is not AgentEmotionalState:
            raise _fail("emotional_state", "invalid_type")
        if emotional_state.owner_id != model.owner_id:
            _LOG.error(
                "world_model_owner_mismatch owner_id=%s reason_code=owner_mismatch",
                model.owner_id.value,
            )
            raise _fail("emotional_state", "owner_mismatch")
    store: dict[str, _Acc] = {
        item.hypothesis_id: _acc_from_hypothesis(item) for item in model.hypotheses
    }
    created = 0
    updated = 0
    dropped = 0
    seen_ids: set[str] = set()
    episode_list = _episode_tuple(episodes)
    for episode in episode_list:
        if episode.owner_id != model.owner_id:
            _LOG.error(
                "world_model_owner_mismatch owner_id=%s reason_code=owner_mismatch",
                model.owner_id.value,
            )
            raise _fail("episode.owner_id", "owner_mismatch")
        if episode.tick != resolved_tick:
            raise _fail("tick", "tick_mismatch")
        if episode.role is CausalEpisodeRole.COUNTER:
            touched = _apply_counter(
                store,
                model.owner_id,
                episode,
                policy,
                weight=_MILD_COUNTER_WEIGHT,
            )
            updated += touched
            continue
        weight = _support_weight(episode.outcome, policy, emotional_state)
        created_now, updated_now = _apply_support(
            store,
            episode,
            policy,
            weight=weight,
            reason=CausalUpdateReason.SUPPORT,
        )
        created += created_now
        updated += updated_now
        if len(episode.atoms) >= 2:
            for parent in _parents(episode.atoms):
                parent_episode = CausalEpisode(
                    owner_id=episode.owner_id,
                    tick=episode.tick,
                    outcome=episode.outcome,
                    atoms=parent,
                    evidence_id=episode.evidence_id,
                    provenance_kind=episode.provenance_kind,
                    role=CausalEpisodeRole.SUPPORT,
                )
                parent_weight = _quantize_mass(policy.generalize_rate * weight)
                if parent_weight == 0.0:
                    continue
                created_parent, updated_parent = _apply_support(
                    store,
                    parent_episode,
                    policy,
                    weight=parent_weight,
                    reason=CausalUpdateReason.GENERALIZE,
                )
                created += created_parent
                updated += updated_parent
        if episode.outcome in _SEARCH_OUTCOMES:
            opposite = (
                CausalOutcome.SEARCH_FAILURE
                if episode.outcome is CausalOutcome.SEARCH_SUCCESS
                else CausalOutcome.SEARCH_SUCCESS
            )
            updated += _counter_existing(
                store,
                model.owner_id,
                outcome=opposite,
                atoms=episode.atoms,
                evidence_id=episode.evidence_id,
                tick=episode.tick,
                policy=policy,
            )
        seen_ids.add(episode.evidence_id)
    evicted = _evict(store, policy.max_hypotheses)
    health = model.last_observed_health
    if observed_health is not None:
        health = _health_value("observed_health", observed_health)
    hypotheses = _trim_and_freeze(store, policy)
    successors = _advance_season_successors(model, episode_list)
    _LOG.info(
        "world_model_updated episode_count=%s created_count=%s "
        "updated_count=%s dropped_count=%s",
        len(episode_list),
        created,
        updated,
        dropped + evicted,
    )
    return CausalWorldModel(
        owner_id=model.owner_id,
        hypotheses=hypotheses,
        last_observed_health=health,
        last_tick=resolved_tick,
        season_successors=successors,
    )


def episodes_from_observation(
    observation: object,
    owner_id: AgentId,
    model: CausalWorldModel | None = None,
) -> tuple[CausalEpisode, ...]:
    """Build episodes from one owner-visible observation.

    The observation parameter must be an ``Observation``. Other objects,
    including engine state, raise ``TypeError``.
    """
    if type(observation) is not Observation:
        raise TypeError("episodes_from_observation: invalid_observation")
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if model is not None:
        if type(model) is not CausalWorldModel:
            raise _fail("model", "invalid_type")
        if model.owner_id != owner_id:
            _LOG.error(
                "world_model_owner_mismatch owner_id=%s reason_code=owner_mismatch",
                owner_id.value,
            )
            raise _fail("model.owner_id", "owner_mismatch")
    ambient = _ambient_atoms(observation)
    held = _held_item_atom(observation)
    episodes: list[CausalEpisode] = []
    dropped = 0

    danger = _danger_atoms(
        observation,
        ambient=ambient,
        prior_health=None if model is None else model.last_observed_health,
    )
    if danger is not None:
        built = _support_episode(
            owner_id=owner_id,
            tick=observation.tick,
            outcome=CausalOutcome.DANGER,
            atoms=danger,
            evidence_id=_danger_evidence_id(observation),
        )
        if built is None:
            dropped += 1
        else:
            episodes.append(built)
    elif ambient:
        episodes.append(
            CausalEpisode(
                owner_id=owner_id,
                tick=observation.tick,
                outcome=CausalOutcome.DANGER,
                atoms=ambient,
                evidence_id=_ambient_evidence_id(observation),
                provenance_kind=CausalProvenanceKind.OBSERVATION,
                role=CausalEpisodeRole.COUNTER,
            )
        )

    help_episodes = _help_episodes(
        observation,
        owner_id=owner_id,
        ambient=ambient,
    )
    episodes.extend(help_episodes)
    helped = _counterparts(help_episodes)

    search = _search_episode(
        observation,
        owner_id=owner_id,
        ambient=ambient,
        held=held,
    )
    if search is not None:
        episodes.append(search)

    for ask in _ask_situations(observation, ambient=ambient):
        counterpart = _value_for(ask, CausalSlot.COUNTERPART)
        if counterpart is not None and counterpart in helped:
            continue
        if not ask:
            dropped += 1
            _LOG.warning("world_model_episode_dropped reason_code=empty_atoms")
            continue
        evidence = _ask_evidence_id(observation, counterpart)
        episodes.append(
            CausalEpisode(
                owner_id=owner_id,
                tick=observation.tick,
                outcome=CausalOutcome.HELP,
                atoms=ask,
                evidence_id=evidence,
                provenance_kind=CausalProvenanceKind.OBSERVATION,
                role=CausalEpisodeRole.COUNTER,
            )
        )
    _LOG.debug(
        "episodes_from_observation owner_id=%s tick=%s episode_count=%s "
        "dropped_count=%s",
        owner_id.value,
        observation.tick,
        len(episodes),
        dropped,
    )
    return tuple(episodes)


def episodes_from_reconstructions(
    context: object,
    *,
    owner_id: AgentId,
    observer_id: object,
    used_provenance_ids: Sequence[str],
) -> tuple[CausalEpisode, ...]:
    """Fill missing episodes. Skip provenance already present on the observation."""
    if type(context) is not RetrievedMemoryContext:
        raise TypeError("episodes_from_reconstructions: invalid_context")
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if context.owner_id != owner_id:
        _LOG.error(
            "world_model_owner_mismatch owner_id=%s reason_code=owner_mismatch",
            owner_id.value,
        )
        raise _fail("context.owner_id", "owner_mismatch")
    if type(observer_id) is not EntityId:
        raise _fail("observer_id", "invalid_type")
    used = _provenance_set(used_provenance_ids)
    known = {item.value for item in context.memory_ids}
    episodes: list[CausalEpisode] = []
    skipped = 0
    for item in context.reconstructions:
        if type(item) is not ReconstructedMemory:
            raise _fail("reconstructions", "invalid_type")
        if item.owner_id != owner_id:
            _LOG.error(
                "world_model_owner_mismatch owner_id=%s reason_code=owner_mismatch",
                owner_id.value,
            )
            raise _fail("reconstruction.owner_id", "owner_mismatch")
        source_ids = tuple(source.value for source in item.source_memory_ids)
        if any(source not in known for source in source_ids):
            raise _fail("source_memory_ids", "foreign_memory")
        if any(_provenance_overlap(source, used) for source in source_ids):
            skipped += len(source_ids)
            continue
        built = _episode_from_reconstruction(
            item,
            owner_id=owner_id,
            observer_id=observer_id,
        )
        if built is None:
            _LOG.warning("world_model_episode_dropped reason_code=outcome_unknown")
            continue
        episodes.append(built)
    _LOG.debug(
        "world_model_memory_episodes owner_id=%s tick=%s memory_episode_count=%s "
        "skipped_duplicate_count=%s",
        owner_id.value,
        context.retrieval_tick,
        len(episodes),
        skipped,
    )
    return tuple(episodes)


def match_hypothesis(
    model: CausalWorldModel | None,
    *,
    outcome: CausalOutcome,
    atoms: Sequence[CausalAtom],
    minimum_confidence: float | None = None,
) -> CausalHypothesis | None:
    """Highest-confidence hypothesis whose atoms are all present.

    Ties prefer more atoms, then the smaller hypothesis id.
    """
    if model is None:
        return None
    if type(model) is not CausalWorldModel:
        raise _fail("model", "invalid_type")
    if type(outcome) is not CausalOutcome:
        raise _fail("outcome", "unknown_outcome")
    situation = _atoms_tuple("atoms", atoms)
    present = {(item.slot, item.value) for item in situation}
    floor = None
    if minimum_confidence is not None:
        floor = _unit_quantum("minimum_confidence", minimum_confidence)
    matches = [
        item
        for item in model.hypotheses
        if item.outcome is outcome
        and all((atom.slot, atom.value) in present for atom in item.atoms)
        and (floor is None or item.confidence >= floor)
    ]
    if not matches:
        return None
    preferred = set(model.preferred_ids)
    if preferred:
        chosen = [item for item in matches if item.hypothesis_id in preferred]
        if chosen:
            matches = chosen
    matches.sort(key=lambda item: item.hypothesis_id)
    matches.sort(key=lambda item: len(item.atoms), reverse=True)
    matches.sort(key=lambda item: item.confidence, reverse=True)
    return matches[0]


def contemplated_situation_atoms(
    observation: Observation,
    *,
    direction: object,
    target_entity_id: str | None,
) -> tuple[CausalAtom, ...]:
    """Atoms a contemplated action can be matched against.

    Move uses the destination as ``LOCATION``. Other directions use the
    observer's current place. Communication is the ask action, because that
    is the command a help hypothesis records.
    """
    from agents.cognition.models import ActionDirection

    if type(observation) is not Observation:
        raise _fail("observation", "invalid_type")
    if type(direction) is not ActionDirection:
        raise _fail("direction", "invalid_type")
    if target_entity_id is not None and type(target_entity_id) is not str:
        raise _fail("target_entity_id", "invalid_type")
    atoms: list[CausalAtom] = []
    if direction is ActionDirection.MOVE and target_entity_id is not None:
        atoms.append(_atom(CausalSlot.LOCATION, target_entity_id))
    elif observation.self_body is not None:
        atoms.append(
            _atom(CausalSlot.LOCATION, observation.self_body.location_id.value)
        )
    if observation.day_phase is not None:
        atoms.append(_atom(CausalSlot.DAY_PHASE, observation.day_phase.value))
    if observation.weather_condition is not None:
        atoms.append(_atom(CausalSlot.WEATHER, observation.weather_condition.value))
    _append_present_environment(atoms, observation)
    if direction is ActionDirection.COMMUNICATE and target_entity_id is not None:
        atoms.append(_atom(CausalSlot.COUNTERPART, target_entity_id))
        atoms.append(_atom(CausalSlot.ACTION, "ask"))
    elif direction is ActionDirection.SEARCH:
        atoms.append(_atom(CausalSlot.ACTION, "search"))
        held = _held_item_atom(observation)
        if held is not None:
            atoms.append(held)
    else:
        atoms.append(_atom(CausalSlot.ACTION, direction.value))
    return tuple(atoms)


def _atoms_tuple(name: str, values: object) -> tuple[CausalAtom, ...]:
    if isinstance(values, (set, frozenset, Mapping, str, bytes, bytearray)):
        raise _fail(name, "not_ordered")
    if not isinstance(values, Sequence):
        raise _fail(name, "not_ordered")
    items = tuple(values)
    if not items:
        raise _fail(name, "empty_atoms")
    if len(items) > _MAX_ATOMS:
        raise _fail(name, "exceeds_max_length")
    seen: set[CausalSlot] = set()
    parsed: list[CausalAtom] = []
    for item in items:
        if type(item) is not CausalAtom:
            raise _fail(name, "unknown_slot")
        if item.slot in seen:
            raise _fail(name, "duplicate_slot")
        seen.add(item.slot)
        parsed.append(item)
    parsed.sort(key=lambda item: _SLOT_ORDER[item.slot])
    return tuple(parsed)


def _id_tuple(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (set, frozenset, Mapping, str, bytes, bytearray)):
        raise _fail(name, "not_ordered")
    if not isinstance(values, Sequence):
        raise _fail(name, "not_ordered")
    parsed: list[str] = []
    for item in values:
        try:
            parsed.append(require_stable_id(name, item))
        except ValueError as exc:
            raise _fail(name, "invalid_value") from exc
    if len(parsed) > _MAX_HISTORY:
        raise _fail(name, "exceeds_max_length")
    return tuple(parsed)


def _history_tuple(
    values: object, hypothesis_id: str
) -> tuple[CausalUpdateRecord, ...]:
    if isinstance(values, (set, frozenset, Mapping, str, bytes, bytearray)):
        raise _fail("update_history", "not_ordered")
    if not isinstance(values, Sequence):
        raise _fail("update_history", "not_ordered")
    items = tuple(values)
    if len(items) > _MAX_HISTORY:
        raise _fail("update_history", "exceeds_max_length")
    for item in items:
        if type(item) is not CausalUpdateRecord:
            raise _fail("update_history", "invalid_type")
        if item.hypothesis_id != hypothesis_id:
            raise _fail("update_history", "owner_mismatch")
    return items


def _hypotheses_tuple(
    owner_id: AgentId, values: object
) -> tuple[CausalHypothesis, ...]:
    if isinstance(values, (set, frozenset, Mapping, str, bytes, bytearray)):
        raise _fail("hypotheses", "not_ordered")
    if not isinstance(values, Sequence):
        raise _fail("hypotheses", "not_ordered")
    items = tuple(values)
    if len(items) > _MAX_HYPOTHESES:
        raise _fail("hypotheses", "exceeds_max_length")
    seen: set[str] = set()
    for item in items:
        if type(item) is not CausalHypothesis:
            raise _fail("hypotheses", "invalid_type")
        if item.owner_id != owner_id:
            _LOG.error(
                "world_model_owner_mismatch owner_id=%s reason_code=owner_mismatch",
                owner_id.value,
            )
            raise _fail("hypotheses", "owner_mismatch")
        if item.hypothesis_id in seen:
            raise _fail("hypotheses", "duplicate_hypothesis")
        seen.add(item.hypothesis_id)
    return items


def _episode_tuple(values: object) -> tuple[CausalEpisode, ...]:
    if isinstance(values, (set, frozenset, Mapping, str, bytes, bytearray)):
        raise _fail("episodes", "not_ordered")
    if not isinstance(values, Sequence):
        raise _fail("episodes", "not_ordered")
    items = tuple(values)
    for item in items:
        if type(item) is not CausalEpisode:
            raise _fail("episodes", "invalid_type")
    return items


def _provenance_set(values: Sequence[str]) -> frozenset[str]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise _fail("used_provenance_ids", "not_ordered")
    parsed: list[str] = []
    for item in values:
        try:
            parsed.append(require_stable_id("used_provenance_ids", item))
        except ValueError as exc:
            raise _fail("used_provenance_ids", "invalid_value") from exc
    return frozenset(parsed)


def _provenance_overlap(memory_id: str, used: frozenset[str]) -> bool:
    if memory_id in used:
        return True
    padded = f"-{memory_id}-"
    return any(f"-{item}-" in padded for item in used)


def _acc_from_hypothesis(item: CausalHypothesis) -> _Acc:
    return _Acc(
        owner_id=item.owner_id,
        atoms=item.atoms,
        outcome=item.outcome,
        support=item.support,
        counter=item.counter,
        evidence_ids=list(item.evidence_ids),
        counter_evidence_ids=list(item.counter_evidence_ids),
        provenance_kind=item.provenance_kind,
        history=list(item.update_history),
        prior=item.prior,
        hypothesis_id=item.hypothesis_id,
        existed=True,
    )


def _support_weight(
    outcome: CausalOutcome,
    policy: WorldModelPolicy,
    emotional_state: AgentEmotionalState | None,
) -> float:
    if outcome is CausalOutcome.DANGER:
        weight = policy.salience_harm
    else:
        weight = policy.base_weight
    if emotional_state is None:
        return weight
    if emotional_state.max_intensity() >= policy.emotion_threshold:
        return _quantize_mass(weight * policy.emotion_multiplier)
    return weight


def _apply_support(
    store: dict[str, _Acc],
    episode: CausalEpisode,
    policy: WorldModelPolicy,
    *,
    weight: float,
    reason: CausalUpdateReason,
) -> tuple[int, int]:
    hypothesis_id = hypothesis_id_for(
        owner_id=episode.owner_id,
        atoms=episode.atoms,
        outcome=episode.outcome,
    )
    created = 0
    updated = 0
    current = store.get(hypothesis_id)
    if current is None:
        current = _Acc(
            owner_id=episode.owner_id,
            atoms=episode.atoms,
            outcome=episode.outcome,
            support=0.0,
            counter=0.0,
            evidence_ids=[],
            counter_evidence_ids=[],
            provenance_kind=episode.provenance_kind,
            history=[],
            prior=policy.prior,
            hypothesis_id=hypothesis_id,
            existed=False,
        )
        store[hypothesis_id] = current
        created = 1
    else:
        updated = 1
    current.support = _quantize_mass(current.support + weight)
    _append_id(current.evidence_ids, episode.evidence_id, policy.max_history)
    record = CausalUpdateRecord(
        tick=episode.tick,
        hypothesis_id=hypothesis_id,
        support_delta=weight,
        counter_delta=0.0,
        reason=reason,
    )
    _append_history(current, record, policy.max_history)
    confidence = confidence_from_masses(
        current.support, current.counter, prior=current.prior
    )
    _LOG.debug(
        "world_model_update owner_id=%s tick=%s hypothesis_id=%s outcome=%s "
        "reason_code=%s atom_count=%s confidence=%s",
        episode.owner_id.value,
        episode.tick,
        hypothesis_id,
        episode.outcome.value,
        reason.value,
        len(episode.atoms),
        confidence,
    )
    return created, updated


def _apply_counter(
    store: dict[str, _Acc],
    owner_id: AgentId,
    episode: CausalEpisode,
    policy: WorldModelPolicy,
    *,
    weight: float,
) -> int:
    return _counter_existing(
        store,
        owner_id,
        outcome=episode.outcome,
        atoms=episode.atoms,
        evidence_id=episode.evidence_id,
        tick=episode.tick,
        policy=policy,
        weight=weight,
    )


def _counter_existing(
    store: dict[str, _Acc],
    owner_id: AgentId,
    *,
    outcome: CausalOutcome,
    atoms: tuple[CausalAtom, ...],
    evidence_id: str,
    tick: int,
    policy: WorldModelPolicy,
    weight: float = _MILD_COUNTER_WEIGHT,
) -> int:
    covered = {(item.slot, item.value) for item in atoms}
    touched = 0
    for current in tuple(store.values()):
        if current.outcome is not outcome:
            continue
        if not all((atom.slot, atom.value) in covered for atom in current.atoms):
            continue
        current.counter = _quantize_mass(current.counter + weight)
        _append_id(current.counter_evidence_ids, evidence_id, policy.max_history)
        record = CausalUpdateRecord(
            tick=tick,
            hypothesis_id=current.hypothesis_id,
            support_delta=0.0,
            counter_delta=weight,
            reason=CausalUpdateReason.COUNTER,
        )
        _append_history(current, record, policy.max_history)
        confidence = confidence_from_masses(
            current.support, current.counter, prior=current.prior
        )
        _LOG.debug(
            "world_model_update owner_id=%s tick=%s hypothesis_id=%s outcome=%s "
            "reason_code=%s atom_count=%s confidence=%s",
            owner_id.value,
            tick,
            current.hypothesis_id,
            outcome.value,
            CausalUpdateReason.COUNTER.value,
            len(current.atoms),
            confidence,
        )
        touched += 1
    return touched


def _parents(atoms: tuple[CausalAtom, ...]) -> tuple[tuple[CausalAtom, ...], ...]:
    parents: list[tuple[CausalAtom, ...]] = []
    for index in range(len(atoms)):
        parent = atoms[:index] + atoms[index + 1 :]
        if parent:
            parents.append(parent)
    return tuple(parents)


def _append_id(bucket: list[str], evidence_id: str, limit: int) -> None:
    bucket.append(evidence_id)
    overflow = len(bucket) - limit
    if overflow > 0:
        del bucket[:overflow]


def _append_history(current: _Acc, record: CausalUpdateRecord, limit: int) -> None:
    current.history.append(record)
    overflow = len(current.history) - limit
    if overflow > 0:
        del current.history[:overflow]


def _evict(store: dict[str, _Acc], limit: int) -> int:
    if len(store) <= limit:
        return 0
    ranked = sorted(store.values(), key=lambda item: item.hypothesis_id, reverse=True)
    ranked = sorted(ranked, key=lambda item: _last_tick(item))
    ranked = sorted(ranked, key=lambda item: _confidence_of(item))
    evicted = 0
    while len(ranked) > limit:
        victim = ranked.pop(0)
        del store[victim.hypothesis_id]
        evicted += 1
    return evicted


def _last_tick(item: _Acc) -> int:
    if not item.history:
        return 0
    return item.history[-1].tick


def _confidence_of(item: _Acc) -> float:
    return confidence_from_masses(item.support, item.counter, prior=item.prior)


def _trim_and_freeze(
    store: dict[str, _Acc], policy: WorldModelPolicy
) -> tuple[CausalHypothesis, ...]:
    frozen: list[CausalHypothesis] = []
    for hypothesis_id in sorted(store):
        current = store[hypothesis_id]
        evidence = tuple(current.evidence_ids[-policy.max_history :])
        counters = tuple(current.counter_evidence_ids[-policy.max_history :])
        history = tuple(current.history[-policy.max_history :])
        frozen.append(
            CausalHypothesis(
                owner_id=current.owner_id,
                atoms=current.atoms,
                outcome=current.outcome,
                support=current.support,
                counter=current.counter,
                evidence_ids=evidence,
                counter_evidence_ids=counters,
                provenance_kind=current.provenance_kind,
                update_history=history,
                prior=current.prior,
            )
        )
    return tuple(frozen)


def _atom(slot: CausalSlot, value: str) -> CausalAtom:
    return CausalAtom(slot=slot, value=value)


def _append_present_environment(
    atoms: list[CausalAtom], observation: Observation
) -> None:
    season = observation.season
    if season is None:
        return
    atoms.append(_atom(CausalSlot.SEASON, season.value))
    if observation.temperature_band is not None:
        atoms.append(
            _atom(CausalSlot.TEMPERATURE_BAND, observation.temperature_band.value)
        )
    if observation.hazard_kinds is None:
        return
    token = ",".join(kind.value for kind in observation.hazard_kinds) or "none"
    atoms.append(_atom(CausalSlot.HAZARD, token))


def _advance_season_successors(
    model: CausalWorldModel, episodes: tuple[CausalEpisode, ...]
) -> SeasonSuccessorTable:
    seasons = {
        atom.value
        for episode in episodes
        for atom in episode.atoms
        if atom.slot is CausalSlot.SEASON
    }
    if len(seasons) != 1:
        if len(seasons) > 1:
            _LOG.info(
                "season_successor_unused reason_code=%s",
                "successor_ambiguous",
            )
        return model.season_successors
    return model.season_successors.observe(model.owner_id, next(iter(seasons)))


def apply_recorded_season_successor(
    atoms: Sequence[CausalAtom],
    table: SeasonSuccessorTable,
    *,
    owner_id: AgentId,
) -> tuple[CausalAtom, ...]:
    """Replace a current season token with its unique recorded successor."""
    del owner_id
    current = [atom for atom in atoms if atom.slot is CausalSlot.SEASON]
    if len(current) != 1:
        return tuple(atoms)
    successor = table.unique_successor(current[0].value)
    if successor is None:
        return tuple(atoms)
    return tuple(
        _atom(CausalSlot.SEASON, successor) if atom.slot is CausalSlot.SEASON else atom
        for atom in atoms
    )


def _ambient_atoms(observation: Observation) -> tuple[CausalAtom, ...]:
    atoms: list[CausalAtom] = []
    if observation.self_body is not None:
        atoms.append(
            _atom(CausalSlot.LOCATION, observation.self_body.location_id.value)
        )
    if observation.day_phase is not None:
        atoms.append(_atom(CausalSlot.DAY_PHASE, observation.day_phase.value))
    if observation.weather_condition is not None:
        atoms.append(_atom(CausalSlot.WEATHER, observation.weather_condition.value))
    _append_present_environment(atoms, observation)
    return tuple(atoms)


def _held_item_atom(observation: Observation) -> CausalAtom | None:
    held = [
        item
        for item in observation.items
        if item.placement is ObservedItemPlacement.HELD_BY_SELF
    ]
    if len(held) != 1:
        return None
    return _atom(CausalSlot.HELD_ITEM_KIND, held[0].kind.value)


def _danger_atoms(
    observation: Observation,
    *,
    ambient: tuple[CausalAtom, ...],
    prior_health: float | None,
) -> tuple[CausalAtom, ...] | None:
    harms: list[ObservedOccurrence] = []
    for occurrence in observation.occurrences:
        if _is_owner_harm(occurrence, observation.observer_id):
            harms.append(occurrence)
    health_drop = False
    body = observation.self_body
    health_now = None if body is None else body.health.value
    if (
        health_now is not None
        and prior_health is not None
        and health_now < prior_health
    ):
        health_drop = True
    if not harms and not health_drop:
        return None
    atoms = list(ambient)
    counterparts = _unique_token(
        [
            occurrence.actor_id.value
            for occurrence in harms
            if occurrence.kind == _ATTACK_KIND and occurrence.actor_id is not None
        ]
    )
    if counterparts is not None:
        atoms.append(_atom(CausalSlot.COUNTERPART, counterparts))
    action = _single_observer_action(harms, observation.observer_id)
    if action is not None:
        atoms.append(_atom(CausalSlot.ACTION, action))
    return tuple(atoms)


def _is_owner_harm(occurrence: ObservedOccurrence, observer_id: object) -> bool:
    if occurrence.kind == _ATTACK_KIND and occurrence.other_entity_id == observer_id:
        return occurrence.actor_id != observer_id
    if occurrence.kind == _FLEE_KIND and occurrence.success is False:
        return occurrence.actor_id == observer_id
    return False


def _unique_token(values: Sequence[str]) -> str | None:
    unique: list[str] = []
    for item in values:
        if item not in unique:
            unique.append(item)
    if len(unique) != 1:
        return None
    return unique[0]


def _single_observer_action(
    occurrences: Sequence[ObservedOccurrence], observer_id: object
) -> str | None:
    kinds = [
        occurrence.kind
        for occurrence in occurrences
        if occurrence.actor_id == observer_id and occurrence.kind
    ]
    return _unique_token(kinds)


def _danger_evidence_id(observation: Observation) -> str:
    for occurrence in observation.occurrences:
        if not _is_owner_harm(occurrence, observation.observer_id):
            continue
        event_id = occurrence.provenance.source_event_id
        if event_id is not None:
            return event_id.value
    return f"health-{observation.observer_id.value}-t{observation.tick}"


def _ambient_evidence_id(observation: Observation) -> str:
    return f"ambient-{observation.observer_id.value}-t{observation.tick}"


def _support_episode(
    *,
    owner_id: AgentId,
    tick: int,
    outcome: CausalOutcome,
    atoms: tuple[CausalAtom, ...],
    evidence_id: str,
) -> CausalEpisode | None:
    if not atoms:
        _LOG.warning("world_model_episode_dropped reason_code=empty_atoms")
        return None
    try:
        return CausalEpisode(
            owner_id=owner_id,
            tick=tick,
            outcome=outcome,
            atoms=atoms,
            evidence_id=evidence_id,
            provenance_kind=CausalProvenanceKind.OBSERVATION,
            role=CausalEpisodeRole.SUPPORT,
        )
    except ValueError:
        _LOG.warning("world_model_episode_dropped reason_code=invalid_episode")
        return None


def _help_episodes(
    observation: Observation,
    *,
    owner_id: AgentId,
    ambient: tuple[CausalAtom, ...],
) -> tuple[CausalEpisode, ...]:
    built: list[CausalEpisode] = []
    for occurrence in observation.occurrences:
        if occurrence.kind not in _HELP_KINDS:
            continue
        if occurrence.other_entity_id != observation.observer_id:
            continue
        actor_is_observer = occurrence.actor_id == observation.observer_id
        if occurrence.actor_id is None or actor_is_observer:
            continue
        atoms = list(ambient)
        atoms.append(_atom(CausalSlot.COUNTERPART, occurrence.actor_id.value))
        ask = _ask_for_counterpart(observation, occurrence.actor_id.value)
        if ask is not None:
            atoms.append(_atom(CausalSlot.ACTION, _ASK_KIND))
            if ask[0] is not None:
                atoms.append(_atom(CausalSlot.CONCEPT, ask[0]))
        event_id = occurrence.provenance.source_event_id
        evidence = (
            event_id.value
            if event_id is not None
            else f"help-{observation.observer_id.value}-t{observation.tick}"
        )
        episode = _support_episode(
            owner_id=owner_id,
            tick=observation.tick,
            outcome=CausalOutcome.HELP,
            atoms=tuple(atoms),
            evidence_id=evidence,
        )
        if episode is not None:
            built.append(episode)
    return tuple(built)


def _ask_for_counterpart(
    observation: Observation, counterpart: str
) -> tuple[str | None] | None:
    matches = [
        item
        for item in observation.communications
        if item.action_kind == _ASK_KIND
        and item.speaker_id == observation.observer_id
        and item.listener_id.value == counterpart
    ]
    if len(matches) != 1:
        return None
    concepts = tuple(matches[0].utterance.content.concepts)
    if len(concepts) == 1:
        return (concepts[0],)
    return (None,)


def _search_episode(
    observation: Observation,
    *,
    owner_id: AgentId,
    ambient: tuple[CausalAtom, ...],
    held: CausalAtom | None,
) -> CausalEpisode | None:
    searches = [
        occurrence
        for occurrence in observation.occurrences
        if occurrence.kind == _SEARCH_KIND
        and occurrence.actor_id == observation.observer_id
        and type(occurrence.success) is bool
    ]
    if not searches:
        return None
    successes = {occurrence.success for occurrence in searches}
    if len(successes) != 1:
        _LOG.warning("world_model_episode_dropped reason_code=ambiguous_outcome")
        return None
    outcome = (
        CausalOutcome.SEARCH_SUCCESS
        if searches[0].success is True
        else CausalOutcome.SEARCH_FAILURE
    )
    atoms = list(ambient)
    atoms.append(_atom(CausalSlot.ACTION, _SEARCH_KIND))
    if held is not None:
        atoms.append(held)
    event_id = searches[0].provenance.source_event_id
    evidence = (
        event_id.value
        if event_id is not None
        else f"search-{observation.observer_id.value}-t{observation.tick}"
    )
    return _support_episode(
        owner_id=owner_id,
        tick=observation.tick,
        outcome=outcome,
        atoms=tuple(atoms),
        evidence_id=evidence,
    )


def _ask_situations(
    observation: Observation,
    *,
    ambient: tuple[CausalAtom, ...],
) -> tuple[tuple[CausalAtom, ...], ...]:
    situations: list[tuple[CausalAtom, ...]] = []
    seen: set[str] = set()
    for item in observation.communications:
        if item.action_kind != _ASK_KIND:
            continue
        if item.speaker_id != observation.observer_id:
            continue
        counterpart = item.listener_id.value
        if counterpart in seen:
            continue
        seen.add(counterpart)
        atoms = list(ambient)
        atoms.append(_atom(CausalSlot.COUNTERPART, counterpart))
        atoms.append(_atom(CausalSlot.ACTION, _ASK_KIND))
        concepts = tuple(item.utterance.content.concepts)
        if len(concepts) == 1:
            atoms.append(_atom(CausalSlot.CONCEPT, concepts[0]))
        situations.append(tuple(atoms))
    for occurrence in observation.occurrences:
        if occurrence.kind != _ASK_KIND:
            continue
        if occurrence.actor_id != observation.observer_id:
            continue
        if occurrence.other_entity_id is None:
            continue
        counterpart = occurrence.other_entity_id.value
        if counterpart in seen:
            continue
        seen.add(counterpart)
        atoms = list(ambient)
        atoms.append(_atom(CausalSlot.COUNTERPART, counterpart))
        atoms.append(_atom(CausalSlot.ACTION, _ASK_KIND))
        concept = _concept_for_ask(observation, occurrence)
        if concept is not None:
            atoms.append(_atom(CausalSlot.CONCEPT, concept))
        situations.append(tuple(atoms))
    return tuple(situations)


def _health_value(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise _fail(field_name, "not_finite")
    if number > 100.0:
        raise _fail(field_name, "out_of_bounds")
    return 0.0 if number == 0.0 else number


def _concept_for_ask(
    observation: Observation, occurrence: ObservedOccurrence
) -> str | None:
    event_id = occurrence.provenance.source_event_id
    matches: list[ObservedCommunication] = []
    for item in observation.communications:
        if item.action_kind != _ASK_KIND:
            continue
        if event_id is not None and item.provenance.source_event_id == event_id:
            matches.append(item)
    if len(matches) != 1:
        return None
    concepts = tuple(matches[0].utterance.content.concepts)
    if len(concepts) != 1:
        return None
    return concepts[0]


def _ask_evidence_id(observation: Observation, counterpart: str | None) -> str:
    for item in observation.communications:
        if item.action_kind != _ASK_KIND:
            continue
        if counterpart is not None and item.listener_id.value != counterpart:
            continue
        event_id = item.provenance.source_event_id
        if event_id is not None:
            return event_id.value
    suffix = "ask" if counterpart is None else counterpart
    return f"ask-{observation.observer_id.value}-{suffix}-t{observation.tick}"


def _counterparts(episodes: Sequence[CausalEpisode]) -> frozenset[str]:
    found: set[str] = set()
    for episode in episodes:
        value = _value_for(episode.atoms, CausalSlot.COUNTERPART)
        if value is not None:
            found.add(value)
    return frozenset(found)


def _value_for(atoms: Sequence[CausalAtom], slot: CausalSlot) -> str | None:
    for atom in atoms:
        if atom.slot is slot:
            return atom.value
    return None


def _episode_from_reconstruction(
    item: ReconstructedMemory,
    *,
    owner_id: AgentId,
    observer_id: object,
) -> CausalEpisode | None:
    outcome = _outcome_from_memory(item)
    if outcome is None:
        return None
    atoms = _atoms_from_memory(item, observer_id)
    if not atoms:
        _LOG.warning("world_model_episode_dropped reason_code=empty_atoms")
        return None
    evidence_id = item.source_memory_ids[0].value
    if type(item.source_memory_ids[0]) is not MemoryId:
        raise _fail("source_memory_ids", "foreign_memory")
    return CausalEpisode(
        owner_id=owner_id,
        tick=item.reconstructed_at_tick,
        outcome=outcome,
        atoms=atoms,
        evidence_id=evidence_id,
        provenance_kind=CausalProvenanceKind.MEMORY,
        role=CausalEpisodeRole.SUPPORT,
    )


def _outcome_from_memory(item: ReconstructedMemory) -> CausalOutcome | None:
    tokens = list(item.context.tags) + [concept.concept for concept in item.concepts]
    found: list[CausalOutcome] = []
    for token in tokens:
        try:
            outcome = CausalOutcome(token)
        except ValueError:
            continue
        if outcome not in found:
            found.append(outcome)
    if len(found) != 1:
        return None
    return found[0]


def _atoms_from_memory(
    item: ReconstructedMemory, observer_id: object
) -> tuple[CausalAtom, ...]:
    atoms: list[CausalAtom] = []
    if item.context.location_id is not None:
        atoms.append(_atom(CausalSlot.LOCATION, item.context.location_id.value))
    phase = _single_token(item.context.tags, _DAY_PHASE_VALUES)
    if phase is not None:
        atoms.append(_atom(CausalSlot.DAY_PHASE, phase))
    weather = _single_token(item.context.tags, _WEATHER_VALUES)
    if weather is not None:
        atoms.append(_atom(CausalSlot.WEATHER, weather))
    action = _single_token(item.context.tags, _action_values())
    if action is not None:
        atoms.append(_atom(CausalSlot.ACTION, action))
    concepts = [
        concept.concept
        for concept in item.concepts
        if concept.concept not in {item.value for item in CausalOutcome}
        and concept.concept not in _action_values()
    ]
    if len(concepts) == 1:
        atoms.append(_atom(CausalSlot.CONCEPT, concepts[0]))
    counterparts = [
        entity.entity_id.value
        for entity in item.entities
        if entity.entity_id is not None and entity.entity_id != observer_id
    ]
    unique_counterparts = list(dict.fromkeys(counterparts))
    if len(unique_counterparts) == 1:
        atoms.append(_atom(CausalSlot.COUNTERPART, unique_counterparts[0]))
    if _HELD_TAG in item.context.tags:
        kinds = [token for token in concepts if token in _ITEM_KIND_VALUES]
        if len(kinds) == 1:
            atoms.append(_atom(CausalSlot.HELD_ITEM_KIND, kinds[0]))
    return tuple(atoms)


def _action_values() -> frozenset[str]:
    return frozenset(
        {
            "wait",
            "move",
            "search",
            "drink",
            "eat",
            "sleep",
            "flee",
            "help",
            "attack",
            "ask",
            "talk",
            "tell",
            "give",
            "rest",
        }
    )


def confidence_band(confidence: float, *, threshold: float) -> str:
    """Discrete band. The LLM payload never carries a probability."""
    if confidence >= 0.8:
        return "high"
    if confidence >= threshold:
        return "mid"
    return "low"


def canonical_atom_tokens(atoms: Sequence[CausalAtom]) -> tuple[str, ...]:
    """Ordered ``slot=value`` tokens. No evidence payload."""
    ordered = tuple(sorted(atoms, key=lambda item: _SLOT_ORDER[item.slot]))
    return tuple(f"{item.slot.value}={item.value}" for item in ordered)


@dataclass(frozen=True, slots=True)
class WorldModelHypothesisSnapshot:
    """One audit row. Ids and quantized confidence only."""

    hypothesis_id: str
    atom_tokens: tuple[str, ...]
    outcome: str
    confidence: float

    def __post_init__(self) -> None:
        try:
            hypothesis_id = require_stable_id("hypothesis_id", self.hypothesis_id)
        except ValueError as exc:
            raise _fail("hypothesis_id", "invalid_value") from exc
        object.__setattr__(self, "hypothesis_id", hypothesis_id)
        tokens = _id_tuple("atom_tokens", self.atom_tokens)
        object.__setattr__(self, "atom_tokens", tokens)
        if self.outcome not in {item.value for item in CausalOutcome}:
            raise _fail("outcome", "unknown_outcome")
        object.__setattr__(
            self, "confidence", _unit_quantum("confidence", self.confidence)
        )


@dataclass(frozen=True, slots=True)
class WorldModelAudit:
    """In-run audit. Not written by runner-result serialization."""

    owner_id: AgentId
    tick: int
    mode: str
    hypothesis_count: int
    update_count: int
    max_confidence: float
    fallback_used: bool
    snapshots: tuple[WorldModelHypothesisSnapshot, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        try:
            tick = require_exact_nonneg_int("tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "not_positive") from exc
        object.__setattr__(self, "tick", tick)
        if self.mode != "enabled":
            raise _fail("mode", "invalid_mode")
        for name, value, upper in (
            ("hypothesis_count", self.hypothesis_count, _MAX_HYPOTHESES),
            (
                "update_count",
                self.update_count,
                _MAX_HYPOTHESES * _MAX_HISTORY,
            ),
        ):
            try:
                number = require_exact_nonneg_int(name, value)
            except ValueError as exc:
                raise _fail(name, "not_positive") from exc
            if number > upper:
                raise _fail(name, "out_of_bounds")
            object.__setattr__(self, name, number)
        object.__setattr__(
            self, "max_confidence", _unit_quantum("max_confidence", self.max_confidence)
        )
        if type(self.fallback_used) is not bool:
            raise _fail("fallback_used", "invalid_type")
        if isinstance(self.snapshots, (set, frozenset, Mapping, str)):
            raise _fail("snapshots", "not_ordered")
        snapshots = tuple(self.snapshots)
        if len(snapshots) > _MAX_HYPOTHESES:
            raise _fail("snapshots", "exceeds_max_length")
        for item in snapshots:
            if type(item) is not WorldModelHypothesisSnapshot:
                raise _fail("snapshots", "invalid_type")
        object.__setattr__(self, "snapshots", snapshots)


def build_world_model_audit(model: CausalWorldModel) -> WorldModelAudit:
    """Snapshot the committed model. Omits evidence ids and episode payloads."""
    if type(model) is not CausalWorldModel:
        raise _fail("model", "invalid_type")
    snapshots = tuple(
        WorldModelHypothesisSnapshot(
            hypothesis_id=item.hypothesis_id,
            atom_tokens=canonical_atom_tokens(item.atoms),
            outcome=item.outcome.value,
            confidence=item.confidence,
        )
        for item in model.hypotheses
    )
    tick = 0 if model.last_tick is None else model.last_tick
    update_count = sum(
        1
        for item in model.hypotheses
        for record in item.update_history
        if record.tick == tick
    )
    maximum = max((item.confidence for item in model.hypotheses), default=0.0)
    return WorldModelAudit(
        owner_id=model.owner_id,
        tick=tick,
        mode="enabled",
        hypothesis_count=len(model.hypotheses),
        update_count=update_count,
        max_confidence=maximum,
        fallback_used=model.selection_fallback_used,
        snapshots=snapshots,
    )


def _single_token(tags: Sequence[str], allowed: frozenset[str]) -> str | None:
    found = [tag for tag in tags if tag in allowed]
    if len(found) != 1:
        return None
    return found[0]
