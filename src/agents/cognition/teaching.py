"""Owner-scoped declarative advice. This is not a belief or a skill level.

Advice records heard public acts. It does not import ``world._skills``,
``world._teaching``, or ``world._state``.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from unicodedata import category

from agents.models import AgentId

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.teaching")

_CURSOR_CAP: Final[int] = 32
_ACT_COUNT: Final[int] = 4
_CONTRACT_VERSION: Final[str] = "teaching-interaction-v1"


class AdviceAct(StrEnum):
    """Closed acts. String values match the objective teaching predicates."""

    REQUEST_INSTRUCTION = "request_instruction"
    EXPLAIN = "explain"
    DEMONSTRATE = "demonstrate"
    PRACTICE_TOGETHER = "practice_together"


class AdviceDomain(StrEnum):
    """Closed domain tokens. String values match the objective skill domains."""

    FORAGING = "foraging"
    NAVIGATION = "navigation"
    RESOURCE_DETECTION = "resource_detection"
    CRAFTING = "crafting"
    BUILDING = "building"
    HEALING = "healing"
    COMMUNICATION = "communication"
    TEACHING = "teaching"


class AdviceBand(StrEnum):
    """Public band stored with the advice. ``unspecified`` has no claim."""

    LOW = "low"
    UNCERTAIN = "uncertain"
    HIGH = "high"
    UNSPECIFIED = "unspecified"


_EXPLAIN_BANDS: Final[frozenset[AdviceBand]] = frozenset(
    {AdviceBand.LOW, AdviceBand.UNCERTAIN, AdviceBand.HIGH}
)


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "teaching_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _require_act(value: object) -> AdviceAct:
    if type(value) is not AdviceAct:
        raise _fail("act", "unknown_act")
    return value


def _require_domain(value: object) -> AdviceDomain:
    if type(value) is not AdviceDomain:
        raise _fail("domain", "unknown_domain")
    return value


def _require_band(value: object) -> AdviceBand:
    if type(value) is not AdviceBand:
        raise _fail("band", "bad_claim")
    return value


def _occurrence_id(value: object) -> str:
    if not isinstance(value, str):
        raise _fail("occurrence_id", "invalid_type")
    length = len(value)
    if length < 1 or length > 128 or value != value.strip():
        raise _fail("occurrence_id", "invalid_type")
    if any(category(char) == "Cc" for char in value):
        raise _fail("occurrence_id", "invalid_type")
    return value


def _delivery_tick(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail("delivery_tick", "invalid_type")
    return value


@dataclass(frozen=True, slots=True)
class DeclarativeAdvice:
    """One heard act. The band is ``unspecified`` when the act has no claim."""

    occurrence_id: str
    source_agent_id: AgentId
    act: AdviceAct
    domain: AdviceDomain
    band: AdviceBand
    delivery_tick: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurrence_id", _occurrence_id(self.occurrence_id))
        if type(self.source_agent_id) is not AgentId:
            raise _fail("source_agent_id", "invalid_type")
        act = _require_act(self.act)
        band = _require_band(self.band)
        if act is AdviceAct.EXPLAIN:
            if band not in _EXPLAIN_BANDS:
                raise _fail("band", "bad_claim")
        elif band is not AdviceBand.UNSPECIFIED:
            raise _fail("band", "bad_claim")
        object.__setattr__(self, "act", act)
        object.__setattr__(self, "domain", _require_domain(self.domain))
        object.__setattr__(self, "band", band)
        object.__setattr__(self, "delivery_tick", _delivery_tick(self.delivery_tick))


@dataclass(frozen=True, slots=True)
class AdviceStore:
    """Owner-scoped advice. Occurrence ids cap at 32 per domain."""

    owner_id: AgentId
    rows: tuple[DeclarativeAdvice, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if isinstance(self.rows, (str, bytes, set, frozenset)) or not isinstance(
            self.rows, tuple
        ):
            raise _fail("rows", "invalid_type")
        seen: set[str] = set()
        counts: dict[AdviceDomain, int] = {}
        normalized: list[DeclarativeAdvice] = []
        for row in self.rows:
            if type(row) is not DeclarativeAdvice:
                raise _fail("rows", "invalid_type")
            if row.occurrence_id in seen:
                raise _fail("occurrence_id", "duplicate_occurrence")
            seen.add(row.occurrence_id)
            counts[row.domain] = counts.get(row.domain, 0) + 1
            if counts[row.domain] > _CURSOR_CAP:
                raise _fail("occurrence_id", "cursor_overflow")
            normalized.append(row)
        object.__setattr__(self, "rows", tuple(normalized))
        _LOG.debug(
            "advice_store_built policy_version=%s act_count=%s",
            _CONTRACT_VERSION,
            _ACT_COUNT,
        )

    def record(self, advice: DeclarativeAdvice) -> AdviceStore:
        """Append one row. A stored occurrence id is skipped.

        The cursor keeps the newest 32 rows of that domain and drops the oldest.
        """
        if type(advice) is not DeclarativeAdvice:
            raise _fail("rows", "invalid_type")
        if any(row.occurrence_id == advice.occurrence_id for row in self.rows):
            return self
        retained: list[DeclarativeAdvice] = []
        domain_seen = 0
        for row in self.rows:
            if row.domain is advice.domain:
                domain_seen += 1
        overflow = domain_seen + 1 - _CURSOR_CAP
        dropped = 0
        for row in self.rows:
            if row.domain is advice.domain and dropped < overflow:
                dropped += 1
                continue
            retained.append(row)
        retained.append(advice)
        return AdviceStore(owner_id=self.owner_id, rows=tuple(retained))


def empty_advice_store(owner_id: AgentId) -> AdviceStore:
    """An owner starts with no heard acts."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    return AdviceStore(owner_id=owner_id)


_SKILL_QUANTUM: Final[float] = 1e-6
_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {"ObjectiveSkillLedger", "ObjectiveSkillPolicy", "WorldState"}
)
_ACT_BY_PREDICATE: Final[dict[str, AdviceAct]] = {
    "request_instruction": AdviceAct.REQUEST_INSTRUCTION,
    "explain": AdviceAct.EXPLAIN,
    "demonstrate": AdviceAct.DEMONSTRATE,
    "practice_together": AdviceAct.PRACTICE_TOGETHER,
}
_DOMAIN_BY_TOKEN: Final[dict[str, AdviceDomain]] = {
    domain.value: domain for domain in AdviceDomain
}
_BAND_BY_TOKEN: Final[dict[str, AdviceBand]] = {
    "low": AdviceBand.LOW,
    "uncertain": AdviceBand.UNCERTAIN,
    "high": AdviceBand.HIGH,
}


@dataclass(frozen=True, slots=True)
class TeachingClaimPolicy:
    """Cognition-side teaching weights. Version ``teaching-interaction-v1``."""

    belief_explain_rate: float = 0.08
    explain_low_below: float = 0.34
    explain_high_at: float = 0.67
    teaching_response_weight: float = 0.25
    belief_prior: float = 1.0
    allow_provider: bool = False
    version: str = _CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.version != _CONTRACT_VERSION:
            raise _fail("version", "unsupported_version")
        if type(self.allow_provider) is not bool:
            raise _fail("allow_provider", "invalid_type")
        rate = _unit_rate("belief_explain_rate", self.belief_explain_rate)
        low = _unit_rate("explain_low_below", self.explain_low_below)
        high = _unit_rate("explain_high_at", self.explain_high_at)
        if low >= high:
            raise _fail("explain_low_below", "threshold_order")
        weight = _unit_rate("teaching_response_weight", self.teaching_response_weight)
        prior = _nonnegative("belief_prior", self.belief_prior)
        object.__setattr__(self, "belief_explain_rate", rate)
        object.__setattr__(self, "explain_low_below", low)
        object.__setattr__(self, "explain_high_at", high)
        object.__setattr__(self, "teaching_response_weight", weight)
        object.__setattr__(self, "belief_prior", prior)
        _LOG.debug(
            "teaching_claim_policy_built policy_version=%s act_count=%s",
            self.version,
            _ACT_COUNT,
        )


def _unit_rate(field_name: str, value: object) -> float:
    number = _nonnegative(field_name, value)
    if number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _nonnegative(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise _fail(field_name, "not_finite")
    return number


def _quantize(value: float) -> float:
    return round(value / _SKILL_QUANTUM) * _SKILL_QUANTUM


def _reject_forbidden(*values: object) -> None:
    for value in values:
        name = type(value).__name__
        if name in _FORBIDDEN_TYPES or name == "CompetenceSelfModel":
            raise TypeError("teaching update rejects objective skill inputs")


def require_owner_advice(
    store: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped store. ``None`` is passthrough."""
    if store is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(store) is not AdviceStore:
        raise TypeError(f"{field_name} must be AdviceStore")
    if store.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


def band_for_belief(level: float, policy: object) -> AdviceBand:
    """Map the speaker's own believed level onto a public claim band.

    Quantized ``level`` below ``explain_low_below`` is ``low``. Below
    ``explain_high_at`` is ``uncertain``. The boundary values belong to
    ``uncertain`` and ``high``.
    """
    _reject_forbidden(policy)
    quantized = _quantize(_nonnegative("believed_level", level))
    low = _nonnegative("explain_low_below", getattr(policy, "explain_low_below", None))
    high = _nonnegative("explain_high_at", getattr(policy, "explain_high_at", None))
    if quantized < low:
        return AdviceBand.LOW
    if quantized < high:
        return AdviceBand.UNCERTAIN
    return AdviceBand.HIGH


def record_teaching(
    advice: AdviceStore,
    observation: object,
    relationships: object,
    policy: object,
    identity: object | None = None,
) -> AdviceStore:
    """Append heard teaching acts addressed to the advice owner.

    The speaker entity is mapped through the owner's identity bindings.
    A missing binding drops the row. Relationships are accepted so a foreign
    ledger cannot hide in this call; uptake reads them separately.
    """
    _reject_forbidden(advice, observation, relationships, policy)
    if identity is not None:
        _reject_forbidden(identity)
    if type(advice) is not AdviceStore:
        raise TypeError("advice must be AdviceStore")
    if identity is not None and getattr(identity, "owner_id", None) != advice.owner_id:
        _LOG.error(
            "teaching_validation_failed field=owner_id reason_code=owner_mismatch",
        )
        raise ValueError("owner_id: owner_mismatch")
    from world.observations import Observation, ObservedCommunication

    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    bindings = _identity_bindings(identity)
    stored = advice
    for communication in observation.communications:
        if type(communication) is not ObservedCommunication:
            continue
        if communication.listener_id != observation.observer_id:
            _LOG.error(
                "teaching_validation_failed field=listener_id reason_code=not_recipient"
            )
            continue
        parsed = _parse_act(communication.utterance)
        if parsed is None:
            continue
        act, domain, band = parsed
        speaker = bindings.get(communication.speaker_id.value)
        if speaker is None:
            _LOG.error(
                "teaching_validation_failed field=speaker_id "
                "reason_code=unknown_speaker"
            )
            continue
        occurrence = _occurrence_token(communication)
        if occurrence is None:
            _LOG.error(
                "teaching_validation_failed field=occurrence_id "
                "reason_code=invalid_type"
            )
            continue
        row = DeclarativeAdvice(
            occurrence_id=occurrence,
            source_agent_id=speaker,
            act=act,
            domain=domain,
            band=band,
            delivery_tick=communication.provenance.source_tick,
        )
        previous = stored
        stored = stored.record(row)
        if stored is previous:
            continue
        _LOG.debug(
            "teaching_advice owner_id=%s act=%s domain=%s band=%s",
            advice.owner_id.value,
            act.value,
            domain.value,
            band.value,
        )
    return stored


def apply_teaching_belief(
    model: object,
    advice_delta: object,
    policy: object,
    relationships: object = (),
) -> object:
    """Move support or counter from new ``explain`` rows. Other acts do not.

    Trust is the owner's directed profile toward the speaker. A missing
    profile uses ``0.5``. Objective level is not an input.
    """
    _reject_foreign(model, advice_delta, policy, relationships)
    if type(advice_delta).__name__ == "CompetenceSelfModel":
        raise TypeError("teaching update rejects another competence model")
    if type(relationships).__name__ == "CompetenceSelfModel":
        raise TypeError("teaching update rejects another competence model")
    from agents.cognition.competence import (
        CompetenceBelief,
        CompetenceDomain,
        CompetenceSelfModel,
        believed_level,
    )

    if type(model) is not CompetenceSelfModel:
        raise TypeError("model must be CompetenceSelfModel")
    rows = _delta_rows(advice_delta, model.owner_id)
    updated = model
    rate = _nonnegative(
        "belief_explain_rate", getattr(policy, "belief_explain_rate", None)
    )
    prior = _nonnegative("belief_prior", getattr(policy, "belief_prior", 1.0))
    for row in rows:
        if row.act is not AdviceAct.EXPLAIN:
            continue
        if row.band is AdviceBand.UNCERTAIN:
            level = updated.belief_for(
                CompetenceDomain(row.domain.value)
            ).believed_level
            _LOG.debug(
                "teaching_belief owner_id=%s domain=%s band=%s believed=%s",
                model.owner_id.value,
                row.domain.value,
                row.band.value,
                level,
            )
            continue
        trust = _trust_factor(relationships, model.owner_id, row.source_agent_id)
        mass = rate * trust
        index = list(CompetenceDomain).index(CompetenceDomain(row.domain.value))
        current = updated.beliefs[index]
        support = current.support_mass
        counter = current.counter_mass
        if row.band is AdviceBand.HIGH:
            support += mass
        elif row.band is AdviceBand.LOW:
            counter += mass
        belief = CompetenceBelief(
            domain=CompetenceDomain(row.domain.value),
            support_mass=support,
            counter_mass=counter,
            believed_level=believed_level(support, counter, prior),
        )
        beliefs = list(updated.beliefs)
        beliefs[index] = belief
        updated = CompetenceSelfModel(
            owner_id=updated.owner_id,
            beliefs=tuple(beliefs),
            cursors=updated.cursors,
            preferred_domains=updated.preferred_domains,
            selection_fallback_used=updated.selection_fallback_used,
        )
        _LOG.debug(
            "teaching_belief owner_id=%s domain=%s band=%s believed=%s",
            model.owner_id.value,
            row.domain.value,
            row.band.value,
            belief.believed_level,
        )
    return updated


def _reject_foreign(*values: object) -> None:
    for value in values:
        if value is None:
            continue
        name = type(value).__name__
        if name in _FORBIDDEN_TYPES:
            raise TypeError("teaching update rejects objective skill inputs")


def _delta_rows(
    advice_delta: object, owner_id: AgentId
) -> tuple[DeclarativeAdvice, ...]:
    if type(advice_delta) is AdviceStore:
        if advice_delta.owner_id != owner_id:
            _LOG.error(
                "teaching_validation_failed field=owner_id reason_code=owner_mismatch"
            )
            raise ValueError("owner_id: owner_mismatch")
        return advice_delta.rows
    if isinstance(advice_delta, (str, bytes)) or not isinstance(advice_delta, tuple):
        raise TypeError("advice_delta must be AdviceStore or a tuple")
    rows: list[DeclarativeAdvice] = []
    for row in advice_delta:
        if type(row) is not DeclarativeAdvice:
            raise TypeError("advice_delta rows must be DeclarativeAdvice")
        rows.append(row)
    return tuple(rows)


def _identity_bindings(identity: object | None) -> dict[str, AgentId]:
    if identity is None:
        return {}
    mapping: dict[str, AgentId] = {}
    owner = getattr(identity, "owner_id", None)
    entity = getattr(identity, "owner_entity_id", None)
    from world.identifiers import EntityId

    if type(owner) is AgentId and type(entity) is EntityId:
        mapping[entity.value] = owner
    for binding in getattr(identity, "counterparts", ()):
        bound_entity = getattr(binding, "entity_id", None)
        bound_agent = getattr(binding, "agent_id", None)
        if type(bound_entity) is EntityId and type(bound_agent) is AgentId:
            mapping[bound_entity.value] = bound_agent
    return mapping


def _parse_act(utterance: object) -> tuple[AdviceAct, AdviceDomain, AdviceBand] | None:
    content = getattr(utterance, "content", None)
    relations = getattr(content, "relations", ())
    if len(tuple(relations)) != 1:
        return None
    relation = next(iter(relations))
    predicate = getattr(relation, "predicate", "")
    act = _ACT_BY_PREDICATE.get(predicate)
    if act is None:
        return None
    token = getattr(relation, "object", "")
    if act is AdviceAct.EXPLAIN:
        domain_token, separator, band_token = token.partition(":")
        if separator == "":
            _LOG.error("teaching_validation_failed field=band reason_code=bad_claim")
            return None
        domain = _DOMAIN_BY_TOKEN.get(domain_token)
        band = _BAND_BY_TOKEN.get(band_token)
        if domain is None:
            _LOG.error(
                "teaching_validation_failed field=domain reason_code=unknown_domain"
            )
            return None
        if band is None:
            _LOG.error("teaching_validation_failed field=band reason_code=bad_claim")
            return None
        return act, domain, band
    domain = _DOMAIN_BY_TOKEN.get(token)
    if domain is None:
        _LOG.error("teaching_validation_failed field=domain reason_code=unknown_domain")
        return None
    return act, domain, AdviceBand.UNSPECIFIED


def _occurrence_token(communication: object) -> str | None:
    provenance = getattr(communication, "provenance", None)
    event_id = getattr(provenance, "source_event_id", None)
    token = getattr(event_id, "value", None)
    if type(token) is not str or not token:
        return None
    return token


def _trust_factor(
    relationships: object, owner_id: AgentId, source_id: AgentId
) -> float:
    from agents.cognition.communication import project_trust_inputs

    chosen = None
    items: tuple[object, ...]
    if relationships is None:
        items = ()
    elif isinstance(relationships, (str, bytes)) or not isinstance(
        relationships, tuple
    ):
        raise TypeError("relationships must be a tuple")
    else:
        items = relationships
    for profile in items:
        if (
            getattr(profile, "source_id", None) == owner_id
            and getattr(profile, "target_id", None) == source_id
        ):
            chosen = profile
            break
    trust, _confidence = project_trust_inputs(chosen)
    return trust


def attach_teaching_act(
    command: object,
    *,
    model: object | None,
    policy: object | None,
    observation: object | None,
    mode: object | None,
    selection: tuple[AdviceAct, AdviceDomain] | None = None,
) -> object:
    """Add one teaching relation after the utterance has been rendered.

    A relation that is already present stays. A missing competence model
    adds nothing. The provider may name an act and a domain; the band is
    computed here from the owner's believed level.
    """
    from agents.cognition.configuration import CognitionTeachingInteractionMode

    if mode is not CognitionTeachingInteractionMode.DETERMINISTIC or policy is None:
        return command
    if model is None or type(model).__name__ != "CompetenceSelfModel":
        return command
    _reject_forbidden(policy)
    if type(command).__name__ not in {"Talk", "Ask", "Tell"}:
        return command
    utterance = getattr(command, "utterance", None)
    relations = tuple(getattr(getattr(utterance, "content", None), "relations", ()))
    owner = getattr(model, "owner_id", None)
    owner_token = getattr(owner, "value", "")
    if relations:
        _LOG.debug(
            "teaching_act_skipped owner_id=%s reason_code=relation_occupied",
            owner_token,
        )
        return command
    chosen = (
        selection if selection is not None else _deterministic_act(model, observation)
    )
    if chosen is None:
        return command
    act, domain = chosen
    if type(act) is not AdviceAct or type(domain) is not AdviceDomain:
        _LOG.error("teaching_validation_failed field=act reason_code=unknown_act")
        return command
    band = AdviceBand.UNSPECIFIED
    obj = domain.value
    if act is AdviceAct.EXPLAIN:
        level = _belief_level(model, domain)
        band = band_for_belief(level, policy)
        obj = f"{domain.value}:{band.value}"
    from world.actions import Ask, Talk, Tell
    from world.communications import CommunicationContent, CommunicationRelation

    kind = type(command)
    if kind not in {Talk, Ask, Tell}:
        return command
    content = utterance.content
    replaced = kind(
        command.recipient_id,
        type(utterance)(
            content=CommunicationContent(
                text=content.text,
                concepts=content.concepts,
                relations=(
                    CommunicationRelation(
                        subject="skill",
                        predicate=act.value,
                        object=obj,
                    ),
                ),
            ),
            declared=utterance.declared,
        ),
    )
    _LOG.debug(
        "teaching_act owner_id=%s act=%s domain=%s band=%s",
        owner_token,
        act.value,
        domain.value,
        band.value,
    )
    return replaced


def teaching_response_term(
    observation: object | None,
    policy: object | None,
    direction: object | None,
    owner_id: object | None,
) -> float:
    """Add the response weight when an inbound request is still unmatched."""
    if policy is None or getattr(direction, "value", None) != "communicate":
        return 0.0
    if not _inbound_request(observation):
        return 0.0
    weight = _unit_rate(
        "teaching_response_weight",
        getattr(policy, "teaching_response_weight", None),
    )
    _LOG.debug(
        "teaching_response_bias owner_id=%s weight=%s",
        getattr(owner_id, "value", ""),
        weight,
    )
    return weight


def _deterministic_act(
    model: object, observation: object | None
) -> tuple[AdviceAct, AdviceDomain] | None:
    requested = _inbound_request(observation)
    if requested is not None:
        return AdviceAct.EXPLAIN, requested
    best_domain: AdviceDomain | None = None
    best_level = -1.0
    for belief in getattr(model, "beliefs", ()):
        domain_value = getattr(getattr(belief, "domain", None), "value", "")
        domain = _DOMAIN_BY_TOKEN.get(domain_value)
        level = getattr(belief, "believed_level", None)
        if domain is None or type(level) is not float:
            continue
        if level > best_level:
            best_level = level
            best_domain = domain
    if best_domain is None:
        return None
    return AdviceAct.DEMONSTRATE, best_domain


def _belief_level(model: object, domain: AdviceDomain) -> float:
    from agents.cognition.competence import CompetenceDomain

    belief = model.belief_for(CompetenceDomain(domain.value))  # type: ignore[attr-defined]
    return float(belief.believed_level)


def _inbound_request(observation: object | None) -> AdviceDomain | None:
    if observation is None:
        return None
    observer = getattr(observation, "observer_id", None)
    for communication in getattr(observation, "communications", ()):
        if getattr(communication, "listener_id", None) != observer:
            continue
        parsed = _parse_act(getattr(communication, "utterance", None))
        if parsed is None:
            continue
        act, domain, _band = parsed
        if act is AdviceAct.REQUEST_INSTRUCTION:
            return domain
    return None
