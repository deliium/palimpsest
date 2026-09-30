"""Owner-scoped belief about skill. This is not the objective ledger.

Support and counter mass live on the owner. Believed level is
``support / (support + counter + prior)``. Skill channels write counter
mass ``0``. A teaching update may store a positive counter.
This module does not import ``world._skills``.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.competence")

COMPETENCE_BELIEF_POLICY_VERSION: Final[str] = "competence-belief-v1"
_SKILL_QUANTUM: Final[float] = 1e-6
_CURSOR_CAP: Final[int] = 32


class CompetenceDomain(StrEnum):
    """Closed tokens. The string values match the objective skill domains."""

    FORAGING = "foraging"
    NAVIGATION = "navigation"
    RESOURCE_DETECTION = "resource_detection"
    CRAFTING = "crafting"
    BUILDING = "building"
    HEALING = "healing"
    COMMUNICATION = "communication"
    TEACHING = "teaching"


class CompetenceUpdateChannel(StrEnum):
    """Subjective channel. Failure does not add counter mass in this plan."""

    PRACTICE = "practice"
    SUCCESS = "success"
    FAILURE = "failure"
    INSTRUCTION = "instruction"
    OBSERVATION = "observation"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "competence_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _quantize(value: float) -> float:
    return round(value / _SKILL_QUANTUM) * _SKILL_QUANTUM


def _finite_number(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _nonnegative_rate(field_name: str, value: object) -> float:
    number = _finite_number(field_name, value)
    if number < 0.0:
        raise _fail(field_name, "negative_rate")
    return number


def _unit_weight(field_name: str, value: object) -> float:
    number = _finite_number(field_name, value)
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _require_domain(value: object) -> CompetenceDomain:
    if type(value) is not CompetenceDomain:
        raise _fail("domain", "unknown_domain")
    return value


def believed_level(support: float, counter: float, prior: float) -> float:
    """Quantize ``support / (support + counter + prior)`` into ``[0, 1]``."""
    denominator = support + counter + prior
    raw = 0.0 if denominator == 0.0 else support / denominator
    quantized = _quantize(raw)
    if quantized < 0.0:
        return 0.0
    if quantized > 1.0:
        return 1.0
    return float(quantized)


@dataclass(frozen=True, slots=True)
class CompetenceBeliefPolicy:
    """Locked belief rates. Version ``competence-belief-v1``.

    ``allow_provider`` defaults to false. A true value may rank domain tokens
    already on the owner's model. It does not emit a skill level.
    """

    belief_practice_rate: float = 0.00
    belief_success_rate: float = 0.10
    belief_failure_rate: float = 0.00
    belief_instruction_rate: float = 0.08
    belief_observation_rate: float = 0.02
    belief_prior: float = 1.0
    belief_action_weight: float = 0.25
    allow_provider: bool = False
    version: str = COMPETENCE_BELIEF_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.version != COMPETENCE_BELIEF_POLICY_VERSION:
            raise _fail("version", "unsupported_version")
        if type(self.allow_provider) is not bool:
            raise _fail("allow_provider", "invalid_type")
        object.__setattr__(
            self,
            "belief_practice_rate",
            _nonnegative_rate("belief_practice_rate", self.belief_practice_rate),
        )
        object.__setattr__(
            self,
            "belief_success_rate",
            _nonnegative_rate("belief_success_rate", self.belief_success_rate),
        )
        object.__setattr__(
            self,
            "belief_failure_rate",
            _nonnegative_rate("belief_failure_rate", self.belief_failure_rate),
        )
        object.__setattr__(
            self,
            "belief_instruction_rate",
            _nonnegative_rate("belief_instruction_rate", self.belief_instruction_rate),
        )
        object.__setattr__(
            self,
            "belief_observation_rate",
            _nonnegative_rate(
                "belief_observation_rate", self.belief_observation_rate
            ),
        )
        object.__setattr__(
            self, "belief_prior", _nonnegative_rate("belief_prior", self.belief_prior)
        )
        object.__setattr__(
            self,
            "belief_action_weight",
            _unit_weight("belief_action_weight", self.belief_action_weight),
        )
        _LOG.debug(
            "competence_belief_policy_built policy_version=%s domain_count=%s",
            self.version,
            len(CompetenceDomain),
        )


def default_competence_belief_policy(
    *,
    allow_provider: bool = False,
) -> CompetenceBeliefPolicy:
    """Locked belief defaults. Provider ranking stays off unless requested."""
    if type(allow_provider) is not bool:
        raise _fail("allow_provider", "invalid_type")
    return CompetenceBeliefPolicy(allow_provider=allow_provider)


@dataclass(frozen=True, slots=True)
class CompetenceBelief:
    """One domain's believed level, support mass, and counter mass."""

    domain: CompetenceDomain
    believed_level: float
    support_mass: float
    counter_mass: float

    def __post_init__(self) -> None:
        domain = _require_domain(self.domain)
        object.__setattr__(self, "domain", domain)
        support = _nonnegative_rate("support_mass", self.support_mass)
        counter = _nonnegative_rate("counter_mass", self.counter_mass)
        believed = _finite_number("believed_level", self.believed_level)
        if believed < 0.0 or believed > 1.0:
            raise _fail("believed_level", "out_of_range")
        object.__setattr__(self, "support_mass", support)
        object.__setattr__(self, "counter_mass", counter)
        object.__setattr__(self, "believed_level", believed)


@dataclass(frozen=True, slots=True)
class CompetenceDomainCursor:
    """Occurrence ids already applied for one domain. Cap is 32, oldest first."""

    domain: CompetenceDomain
    occurrence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        domain = _require_domain(self.domain)
        object.__setattr__(self, "domain", domain)
        if isinstance(self.occurrence_ids, (str, bytes)) or not isinstance(
            self.occurrence_ids, tuple
        ):
            raise _fail("occurrence_ids", "invalid_type")
        if len(self.occurrence_ids) > _CURSOR_CAP:
            raise _fail("occurrence_ids", "cursor_overflow")
        for occurrence_id in self.occurrence_ids:
            if not isinstance(occurrence_id, str) or not occurrence_id:
                raise _fail("occurrence_ids", "invalid_type")


def _zero_belief(domain: CompetenceDomain) -> CompetenceBelief:
    return CompetenceBelief(
        domain=domain,
        believed_level=0.0,
        support_mass=0.0,
        counter_mass=0.0,
    )


@dataclass(frozen=True, slots=True)
class CompetenceSelfModel:
    """Private competence model for one owner. Not the objective ledger."""

    owner_id: AgentId
    beliefs: tuple[CompetenceBelief, ...]
    cursors: tuple[CompetenceDomainCursor, ...]
    preferred_domains: tuple[str, ...] = ()
    selection_fallback_used: bool = False

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if len(self.beliefs) != len(CompetenceDomain) or len(self.cursors) != len(
            CompetenceDomain
        ):
            raise _fail("domain", "unknown_domain")
        domains = list(CompetenceDomain)
        for index, domain in enumerate(domains):
            belief = self.beliefs[index]
            cursor = self.cursors[index]
            if type(belief) is not CompetenceBelief or belief.domain is not domain:
                raise _fail("domain", "unknown_domain")
            if (
                type(cursor) is not CompetenceDomainCursor
                or cursor.domain is not domain
            ):
                raise _fail("domain", "unknown_domain")
        if isinstance(self.preferred_domains, (str, bytes)) or not isinstance(
            self.preferred_domains, tuple
        ):
            raise _fail("preferred_domains", "invalid_type")
        for token in self.preferred_domains:
            try:
                CompetenceDomain(token)
            except ValueError:
                _LOG.error(
                    "competence_bias owner_id=%s domain=%s reason_code=unknown_domain",
                    self.owner_id.value,
                    token,
                )
                raise _fail("preferred_domains", "unknown_domain") from None
        if type(self.selection_fallback_used) is not bool:
            raise _fail("selection_fallback_used", "invalid_type")

    def belief_for(self, domain: CompetenceDomain) -> CompetenceBelief:
        checked = _require_domain(domain)
        return self.beliefs[list(CompetenceDomain).index(checked)]


def empty_competence_model(owner_id: AgentId) -> CompetenceSelfModel:
    """Every domain starts at support ``0``, counter ``0``, believed ``0``."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    beliefs = tuple(_zero_belief(domain) for domain in CompetenceDomain)
    cursors = tuple(
        CompetenceDomainCursor(domain=domain, occurrence_ids=())
        for domain in CompetenceDomain
    )
    return CompetenceSelfModel(owner_id=owner_id, beliefs=beliefs, cursors=cursors)


def _channel_support(
    channel: CompetenceUpdateChannel, policy: CompetenceBeliefPolicy
) -> float:
    if channel is CompetenceUpdateChannel.PRACTICE:
        return policy.belief_practice_rate
    if channel is CompetenceUpdateChannel.SUCCESS:
        return policy.belief_success_rate
    if channel is CompetenceUpdateChannel.FAILURE:
        return policy.belief_failure_rate
    if channel is CompetenceUpdateChannel.INSTRUCTION:
        return policy.belief_instruction_rate
    return policy.belief_observation_rate


def apply_belief_channel(
    model: CompetenceSelfModel,
    domain: CompetenceDomain,
    channel: CompetenceUpdateChannel,
    policy: CompetenceBeliefPolicy,
    **forbidden: object,
) -> CompetenceSelfModel:
    """Add one channel's support. This channel writes counter mass ``0``.

    Objective ledger and world state are not parameters. Extra keywords raise
    ``TypeError``.
    """
    if forbidden:
        raise TypeError("competence update rejects objective skill inputs")
    if type(model) is not CompetenceSelfModel:
        raise TypeError("model must be CompetenceSelfModel")
    if type(policy) is not CompetenceBeliefPolicy:
        raise TypeError("policy must be CompetenceBeliefPolicy")
    if type(channel) is not CompetenceUpdateChannel:
        raise _fail("channel", "unknown_channel")
    checked = _require_domain(domain)
    index = list(CompetenceDomain).index(checked)
    current = model.beliefs[index]
    support = current.support_mass + _channel_support(channel, policy)
    updated = CompetenceBelief(
        domain=checked,
        support_mass=support,
        counter_mass=0.0,
        believed_level=believed_level(support, 0.0, policy.belief_prior),
    )
    beliefs = list(model.beliefs)
    beliefs[index] = updated
    _LOG.debug(
        "competence_update owner_id=%s domain=%s channel=%s believed=%s",
        model.owner_id.value,
        checked.value,
        channel.value,
        updated.believed_level,
    )
    return CompetenceSelfModel(
        owner_id=model.owner_id,
        beliefs=tuple(beliefs),
        cursors=model.cursors,
        preferred_domains=model.preferred_domains,
        selection_fallback_used=model.selection_fallback_used,
    )


def require_owner_competence(
    model: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped model. ``None`` is passthrough."""
    if model is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(model) is not CompetenceSelfModel:
        raise TypeError(f"{field_name} must be CompetenceSelfModel")
    if model.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


def competence_direction_term(
    model: object,
    *,
    direction: object,
    targeted_search: bool,
    owner_id: AgentId,
    weight: float,
) -> float:
    """Belief weight for one existing direction. A missing model adds nothing."""
    if model is None:
        return 0.0
    if type(model) is not CompetenceSelfModel:
        raise TypeError("competence model must be CompetenceSelfModel")
    domain = _direction_domain(
        direction, targeted_search=targeted_search, owner_id=owner_id
    )
    if domain is None:
        return 0.0
    believed = model.belief_for(domain).believed_level
    _LOG.debug(
        "competence_bias owner_id=%s domain=%s believed=%s weight=%s",
        owner_id.value,
        domain.value,
        believed,
        weight,
    )
    return weight * believed


def _direction_domain(
    direction: object, *, targeted_search: bool, owner_id: AgentId
) -> CompetenceDomain | None:
    from agents.cognition.models import ActionDirection

    if type(direction) is not ActionDirection:
        _LOG.error(
            "competence_bias owner_id=%s domain=%s reason_code=unknown_domain",
            owner_id.value,
            getattr(direction, "value", direction),
        )
        return None
    if direction is ActionDirection.SEARCH:
        if targeted_search:
            return CompetenceDomain.RESOURCE_DETECTION
        return CompetenceDomain.FORAGING
    if direction is ActionDirection.MOVE or direction is ActionDirection.FLEE:
        return CompetenceDomain.NAVIGATION
    if direction is ActionDirection.HELP:
        return CompetenceDomain.HEALING
    if direction is ActionDirection.COMMUNICATE:
        return CompetenceDomain.COMMUNICATION
    return None


def update_competence(
    model: CompetenceSelfModel,
    observation: object,
    reconstructions: object,
    policy: CompetenceBeliefPolicy,
) -> CompetenceSelfModel:
    """Update believed skill from the owner's observation and reconstructions.

    Objective skill ledgers and world state are not inputs. Passing either
    raises ``TypeError``.
    """
    for value in (model, observation, reconstructions, policy):
        if type(value).__name__ in {
            "ObjectiveSkillLedger",
            "ObjectiveSkillPolicy",
            "WorldState",
        }:
            raise TypeError("competence update rejects objective skill inputs")
    if type(model) is not CompetenceSelfModel:
        raise TypeError("model must be CompetenceSelfModel")
    if type(policy) is not CompetenceBeliefPolicy:
        raise TypeError("policy must be CompetenceBeliefPolicy")
    from world.observations import Observation

    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if isinstance(reconstructions, (str, bytes)) or not isinstance(
        reconstructions, tuple
    ):
        raise TypeError("reconstructions must be a tuple")
    updated = model
    for item in reconstructions:
        owner = getattr(item, "owner_id", model.owner_id)
        if owner != model.owner_id:
            _LOG.error(
                "competence_update_failed owner_id=%s reason_code=owner_mismatch",
                model.owner_id.value,
            )
            continue
    for occurrence in observation.occurrences:
        updated = _apply_occurrence(
            updated, occurrence, observation.observer_id, policy
        )
    for communication in observation.communications:
        updated = _apply_communication(
            updated, communication, observation.observer_id, policy
        )
    return updated


def _apply_occurrence(
    model: CompetenceSelfModel,
    occurrence: object,
    observer_id: object,
    policy: CompetenceBeliefPolicy,
) -> CompetenceSelfModel:
    from world.identifiers import EntityId
    from world.observations import ObservedOccurrence

    if type(occurrence) is not ObservedOccurrence or type(observer_id) is not EntityId:
        return model
    kind = occurrence.kind
    domain = _occurrence_domain(kind, occurrence.other_entity_id)
    if domain is None:
        return model
    occurrence_id = _occurrence_id(occurrence)
    if occurrence_id is None or _cursor_has(model, domain, occurrence_id):
        return model
    actor = occurrence.actor_id
    success = occurrence.success
    channel: CompetenceUpdateChannel | None = None
    if actor == observer_id:
        if success is False and kind in {"search", "flee"}:
            channel = CompetenceUpdateChannel.FAILURE
        elif success is True or kind in {"move", "help", "flee"}:
            channel = CompetenceUpdateChannel.SUCCESS
    elif success is True and kind in {"search", "move", "flee", "help"}:
        channel = CompetenceUpdateChannel.OBSERVATION
    if channel is None:
        return model
    updated = apply_belief_channel(model, domain, channel, policy)
    return _remember(updated, domain, occurrence_id)


def _apply_communication(
    model: CompetenceSelfModel,
    communication: object,
    observer_id: object,
    policy: CompetenceBeliefPolicy,
) -> CompetenceSelfModel:
    from world.identifiers import EntityId
    from world.observations import ObservedCommunication

    if type(communication) is not ObservedCommunication:
        return model
    if type(observer_id) is not EntityId:
        return model
    occurrence_id = _occurrence_id(communication)
    if occurrence_id is None:
        return model
    updated = model
    if communication.speaker_id == observer_id:
        if not _cursor_has(updated, CompetenceDomain.COMMUNICATION, occurrence_id):
            updated = apply_belief_channel(
                updated,
                CompetenceDomain.COMMUNICATION,
                CompetenceUpdateChannel.SUCCESS,
                policy,
            )
            updated = _remember(
                updated, CompetenceDomain.COMMUNICATION, occurrence_id
            )
        instructed = _instructed_domain(communication.utterance)
        if instructed is not None and not _cursor_has(
            updated, CompetenceDomain.TEACHING, occurrence_id
        ):
            updated = apply_belief_channel(
                updated,
                CompetenceDomain.TEACHING,
                CompetenceUpdateChannel.SUCCESS,
                policy,
            )
            updated = _remember(updated, CompetenceDomain.TEACHING, occurrence_id)
    if communication.listener_id != observer_id:
        return updated
    instructed = _instructed_domain(communication.utterance)
    if instructed is None or _cursor_has(updated, instructed, occurrence_id):
        return updated
    updated = apply_belief_channel(
        updated,
        instructed,
        CompetenceUpdateChannel.INSTRUCTION,
        policy,
    )
    return _remember(updated, instructed, occurrence_id)


def _instructed_domain(utterance: object) -> CompetenceDomain | None:
    from world.communications import StructuredUtterance

    if type(utterance) is not StructuredUtterance:
        return None
    relations = tuple(utterance.content.relations)
    if len(relations) != 1 or relations[0].predicate != "instruct":
        return None
    try:
        return CompetenceDomain(relations[0].object)
    except ValueError:
        return None


def _occurrence_domain(kind: str, other: object) -> CompetenceDomain | None:
    if kind == "search":
        if other is None:
            return CompetenceDomain.FORAGING
        return CompetenceDomain.RESOURCE_DETECTION
    if kind in {"move", "flee"}:
        return CompetenceDomain.NAVIGATION
    if kind == "help":
        return CompetenceDomain.HEALING
    return None


def _occurrence_id(value: object) -> str | None:
    provenance = getattr(value, "provenance", None)
    event_id = getattr(provenance, "source_event_id", None)
    if event_id is None:
        return None
    token = getattr(event_id, "value", None)
    if type(token) is not str or not token:
        return None
    return token


def _cursor_has(
    model: CompetenceSelfModel, domain: CompetenceDomain, occurrence_id: str
) -> bool:
    return occurrence_id in _cursor(model, domain).occurrence_ids


def _cursor(
    model: CompetenceSelfModel, domain: CompetenceDomain
) -> CompetenceDomainCursor:
    return model.cursors[list(CompetenceDomain).index(domain)]


def _remember(
    model: CompetenceSelfModel, domain: CompetenceDomain, occurrence_id: str
) -> CompetenceSelfModel:
    index = list(CompetenceDomain).index(domain)
    current = model.cursors[index]
    stored = (*current.occurrence_ids, occurrence_id)
    if len(stored) > _CURSOR_CAP:
        stored = stored[-_CURSOR_CAP:]
    cursors = list(model.cursors)
    cursors[index] = CompetenceDomainCursor(domain=domain, occurrence_ids=stored)
    return CompetenceSelfModel(
        owner_id=model.owner_id,
        beliefs=model.beliefs,
        cursors=tuple(cursors),
        preferred_domains=model.preferred_domains,
        selection_fallback_used=model.selection_fallback_used,
    )
