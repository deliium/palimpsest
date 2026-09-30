"""Explicit teaching offers folded from public utterances.

Only ``WorldEngine`` applies the extra practice deltas. The module may use
``world._skills``. Cognition and agent packages stay outside this module.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world._skills import SkillDomain
from world.communications import CommunicationRelation
from world.identifiers import EntityId

_LOG: Final[logging.Logger] = logging.getLogger("world._teaching")

TEACHING_INTERACTION_POLICY_VERSION: Final[str] = "teaching-interaction-v1"
_OFFER_ACTS: Final[frozenset[str]] = frozenset({"demonstrate", "practice_together"})
_EXPLAIN_BANDS: Final[frozenset[str]] = frozenset({"low", "uncertain", "high"})


class TeachingAct(StrEnum):
    """Closed utterance predicates. There is no profession or teacher label."""

    REQUEST_INSTRUCTION = "request_instruction"
    EXPLAIN = "explain"
    DEMONSTRATE = "demonstrate"
    PRACTICE_TOGETHER = "practice_together"


class ClaimBand(StrEnum):
    """Public claim band. ``unspecified`` is used when the act has no band."""

    LOW = "low"
    UNCERTAIN = "uncertain"
    HIGH = "high"
    UNSPECIFIED = "unspecified"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "teaching_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


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


def _unit_interval(field_name: str, value: object) -> float:
    number = _finite_number(field_name, value)
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _require_act(value: object) -> TeachingAct:
    if type(value) is not TeachingAct:
        raise _fail("act", "unknown_act")
    return value


def _require_domain(value: object) -> SkillDomain:
    if type(value) is not SkillDomain:
        raise _fail("domain", "unknown_domain")
    return value


def _offer_window(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(field_name, "invalid_type")
    if value < 1 or value > 64:
        raise _fail(field_name, "offer_window")
    return value


def _domain_token(token: str) -> SkillDomain | None:
    try:
        domain = SkillDomain(token)
    except ValueError:
        _LOG.error(
            "teaching_validation_failed field=%s reason_code=%s",
            "domain",
            "unknown_domain",
        )
        return None
    if type(domain) is not SkillDomain:
        return None
    return domain


@dataclass(frozen=True, slots=True)
class TeachingOffer:
    """One open demonstrate or practice-together offer. Refolded from events."""

    speaker_id: EntityId
    recipient_id: EntityId
    act: TeachingAct
    domain: SkillDomain
    delivery_tick: int

    def __post_init__(self) -> None:
        if type(self.speaker_id) is not EntityId:
            raise _fail("speaker_id", "invalid_type")
        if type(self.recipient_id) is not EntityId:
            raise _fail("recipient_id", "invalid_type")
        act = _require_act(self.act)
        if act.value not in _OFFER_ACTS:
            raise _fail("act", "not_offer")
        object.__setattr__(self, "act", act)
        object.__setattr__(self, "domain", _require_domain(self.domain))
        if isinstance(self.delivery_tick, bool) or not isinstance(
            self.delivery_tick, int
        ):
            raise _fail("delivery_tick", "invalid_type")
        if self.delivery_tick < 0:
            raise _fail("delivery_tick", "invalid_type")


@dataclass(frozen=True, slots=True)
class TeachingInteractionPolicy:
    """Locked teaching weights. Version ``teaching-interaction-v1``."""

    demonstration_rate: float = 0.02
    practice_together_rate: float = 0.02
    offer_window: int = 8
    belief_explain_rate: float = 0.08
    explain_low_below: float = 0.34
    explain_high_at: float = 0.67
    teaching_response_weight: float = 0.25
    allow_provider: bool = False
    version: str = TEACHING_INTERACTION_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.version != TEACHING_INTERACTION_POLICY_VERSION:
            raise _fail("version", "unsupported_version")
        if type(self.allow_provider) is not bool:
            raise _fail("allow_provider", "invalid_type")
        object.__setattr__(
            self,
            "demonstration_rate",
            _nonnegative_rate("demonstration_rate", self.demonstration_rate),
        )
        object.__setattr__(
            self,
            "practice_together_rate",
            _nonnegative_rate("practice_together_rate", self.practice_together_rate),
        )
        object.__setattr__(
            self,
            "offer_window",
            _offer_window("offer_window", self.offer_window),
        )
        object.__setattr__(
            self,
            "belief_explain_rate",
            _nonnegative_rate("belief_explain_rate", self.belief_explain_rate),
        )
        low = _unit_interval("explain_low_below", self.explain_low_below)
        high = _unit_interval("explain_high_at", self.explain_high_at)
        if low >= high:
            raise _fail("explain_low_below", "threshold_order")
        object.__setattr__(self, "explain_low_below", low)
        object.__setattr__(self, "explain_high_at", high)
        object.__setattr__(
            self,
            "teaching_response_weight",
            _unit_interval("teaching_response_weight", self.teaching_response_weight),
        )
        _LOG.debug(
            "teaching_policy_built policy_version=%s act_count=%s",
            self.version,
            len(TeachingAct),
        )


def default_teaching_interaction_policy(
    *,
    allow_provider: bool = False,
) -> TeachingInteractionPolicy:
    """Locked teaching defaults. Provider selection stays off unless requested."""
    if type(allow_provider) is not bool:
        raise _fail("allow_provider", "invalid_type")
    return TeachingInteractionPolicy(allow_provider=allow_provider)


def parse_teaching_relation(
    relation: object,
) -> tuple[TeachingAct, SkillDomain, ClaimBand] | None:
    """Return the act, domain, and band for exactly one teaching relation.

    Any other shape is not a teaching act and returns ``None``.
    """
    if type(relation) is not CommunicationRelation:
        return None
    predicate = relation.predicate
    try:
        act = TeachingAct(predicate)
    except ValueError:
        return None
    if type(act) is not TeachingAct:
        return None
    if act is TeachingAct.EXPLAIN:
        domain_token, separator, band_token = relation.object.partition(":")
        if separator != ":" or ":" in band_token or not domain_token:
            _LOG.error(
                "teaching_validation_failed field=%s reason_code=%s",
                "object",
                "bad_claim",
            )
            return None
        if band_token not in _EXPLAIN_BANDS:
            _LOG.error(
                "teaching_validation_failed field=%s reason_code=%s",
                "band",
                "bad_claim",
            )
            return None
        domain = _domain_token(domain_token)
        if domain is None:
            return None
        return act, domain, ClaimBand(band_token)
    if ":" in relation.object:
        _LOG.error(
            "teaching_validation_failed field=%s reason_code=%s",
            "object",
            "bad_claim",
        )
        return None
    domain = _domain_token(relation.object)
    if domain is None:
        return None
    return act, domain, ClaimBand.UNSPECIFIED


def _require_world_state(value: object) -> object:
    kind = type(value)
    if kind.__module__ != "world._state" or kind.__name__ != "WorldState":
        raise TypeError("world_state must be WorldState")
    return value


def _practice_domain(details: object, *, untargeted: bool | None) -> SkillDomain | None:
    from world.events import Fled, Helped, Moved, Searched

    if type(details) is Searched:
        if untargeted is True or (untargeted is None and details.target_id is None):
            return SkillDomain.FORAGING
        return SkillDomain.RESOURCE_DETECTION
    if type(details) is Fled or type(details) is Moved:
        return SkillDomain.NAVIGATION
    if type(details) is Helped:
        return SkillDomain.HEALING
    return None


def _is_public_success(details: object) -> bool:
    from world.events import Fled, Helped, Moved, Searched

    if type(details) is Searched or type(details) is Fled:
        return details.success is True
    return type(details) is Moved or type(details) is Helped


def _is_applied_practice(details: object) -> bool:
    from world.events import Fled, Helped, Moved, Searched

    if type(details) is Searched or type(details) is Fled:
        return type(details.success) is bool
    return type(details) is Moved or type(details) is Helped


@dataclass(frozen=True, slots=True)
class _PracticeFact:
    actor_id: EntityId
    domain: SkillDomain
    success: bool
    origin_location_id: EntityId | None


def _visibility(
    rules: object,
    world_state: object,
    location_id: EntityId,
    tick: int,
) -> float | None:
    from world.models import PhysicalRules, WeatherCondition

    if type(rules) is not PhysicalRules:
        raise TypeError("rules must be PhysicalRules")
    if location_id not in world_state.locations:  # type: ignore[attr-defined]
        return None
    location = world_state.locations[location_id]  # type: ignore[attr-defined]
    weather = world_state.weather.get(location_id)  # type: ignore[attr-defined]
    condition = weather.condition if weather is not None else WeatherCondition.CLEAR
    return rules.effective_visibility(
        location_visibility=location.visibility_factor.value,
        phase=rules.day_phase_for_tick(tick),
        condition=condition,
    )


def _living_witness(
    world_state: object,
    entity_id: EntityId,
    origin: EntityId | None,
    rules: object,
    tick: int,
) -> bool:
    from world.models import LifeStatus

    if origin is None:
        return False
    body = world_state.bodies.get(entity_id)  # type: ignore[attr-defined]
    if body is None or body.life_status is not LifeStatus.ALIVE:
        return False
    if body.location_id != origin:
        return False
    visibility = _visibility(rules, world_state, origin, tick)
    return visibility is not None and visibility >= 0.5


def _offers_from_events(
    events: Sequence[object],
    participants: frozenset[EntityId],
) -> tuple[TeachingOffer, ...]:
    from world.events import Asked, Talked, Told, WorldEvent

    offers: list[TeachingOffer] = []
    for event in events:
        if type(event) is not WorldEvent or event.actor_id is None:
            continue
        details = event.details
        if (
            type(details) is not Talked
            and type(details) is not Asked
            and type(details) is not Told
        ):
            continue
        relations = tuple(details.utterance.content.relations)
        if len(relations) != 1:
            continue
        parsed = parse_teaching_relation(relations[0])
        if parsed is None:
            continue
        act, domain, _band = parsed
        if act.value not in _OFFER_ACTS:
            continue
        if (
            event.actor_id not in participants
            or details.recipient_id not in participants
        ):
            continue
        offers.append(
            TeachingOffer(
                speaker_id=event.actor_id,
                recipient_id=details.recipient_id,
                act=act,
                domain=domain,
                delivery_tick=event.tick,
            )
        )
    return tuple(offers)


def _prior_successes(
    events: Sequence[object],
    untargeted_request_ids: frozenset[str],
) -> tuple[tuple[int, EntityId, SkillDomain], ...]:
    from world.events import WorldEvent

    found: list[tuple[int, EntityId, SkillDomain]] = []
    for event in events:
        if type(event) is not WorldEvent or event.actor_id is None:
            continue
        if not _is_public_success(event.details):
            continue
        untargeted = event.request_id.value in untargeted_request_ids
        domain = _practice_domain(event.details, untargeted=untargeted)
        if domain is None:
            continue
        found.append((event.tick, event.actor_id, domain))
    return tuple(found)


def _joint_consumed(
    offer: TeachingOffer,
    events: Sequence[object],
    *,
    before_tick: int,
    offer_window: int,
    untargeted_request_ids: frozenset[str],
) -> bool:
    from world.events import WorldEvent

    by_tick: dict[int, set[EntityId]] = {}
    for event in events:
        if type(event) is not WorldEvent or event.actor_id is None:
            continue
        if event.tick <= offer.delivery_tick or event.tick >= before_tick:
            continue
        if event.tick - offer.delivery_tick > offer_window:
            continue
        untargeted = event.request_id.value in untargeted_request_ids
        domain = _practice_domain(event.details, untargeted=untargeted)
        if domain is not offer.domain or not _is_applied_practice(event.details):
            continue
        if event.actor_id not in {offer.speaker_id, offer.recipient_id}:
            continue
        by_tick.setdefault(event.tick, set()).add(event.actor_id)
    pair = {offer.speaker_id, offer.recipient_id}
    return any(pair <= actors for actors in by_tick.values())


def _consumed(
    offer: TeachingOffer,
    successes: Sequence[tuple[int, EntityId, SkillDomain]],
    *,
    before_tick: int,
    offer_window: int,
) -> bool:
    for success_tick, actor_id, domain in successes:
        if actor_id != offer.speaker_id or domain is not offer.domain:
            continue
        if success_tick <= offer.delivery_tick or success_tick >= before_tick:
            continue
        if success_tick - offer.delivery_tick <= offer_window:
            return True
    return False


def _in_window(offer: TeachingOffer, tick: int, offer_window: int) -> bool:
    elapsed = tick - offer.delivery_tick
    return 0 < elapsed <= offer_window


def _add_bonus(
    sums: dict[EntityId, dict[SkillDomain, float]],
    *,
    ledger: object,
    entity_id: EntityId,
    domain: SkillDomain,
    amount: float,
    tick: int,
    act: TeachingAct,
) -> None:
    from world._skills import ObjectiveSkillLedger

    if type(ledger) is not ObjectiveSkillLedger or entity_id not in ledger.entity_ids():
        _LOG.error(
            "teaching_validation_failed field=%s reason_code=%s",
            "entity_id",
            "missing_entity",
        )
        return
    _LOG.debug(
        "teaching_opportunity tick=%s entity_id=%s act=%s domain=%s",
        tick,
        entity_id.value,
        act.value,
        domain.value,
    )
    domains = sums.setdefault(entity_id, {})
    domains[domain] = domains.get(domain, 0.0) + amount


def fold_teaching_opportunities(
    ledger: object,
    *,
    start_ledger: object,
    applied_actions: Sequence[object],
    prior_events: Sequence[object],
    policy: TeachingInteractionPolicy,
    teaching_entity_ids: frozenset[EntityId],
    world_state: object,
    tick: int,
    rules: object,
    untargeted_request_ids: frozenset[str] = frozenset(),
) -> object:
    """Add demonstration and joint-practice bonuses onto an already folded ledger.

    Start-of-tick levels come from ``start_ledger``. The other body's level is
    not an operand. ``explain`` and ``request_instruction`` add nothing.
    """
    from world._skills import ObjectiveSkillLedger, SkillGrowthInput
    from world.models import PhysicalRules

    if type(ledger) is not ObjectiveSkillLedger:
        raise TypeError("ledger must be ObjectiveSkillLedger")
    if type(start_ledger) is not ObjectiveSkillLedger:
        raise TypeError("start_ledger must be ObjectiveSkillLedger")
    if type(policy) is not TeachingInteractionPolicy:
        raise TypeError("policy must be TeachingInteractionPolicy")
    if type(teaching_entity_ids) is not frozenset:
        raise TypeError("teaching_entity_ids must be a frozenset")
    if type(rules) is not PhysicalRules:
        raise TypeError("rules must be PhysicalRules")
    _require_world_state(world_state)
    if isinstance(tick, bool) or type(tick) is not int:
        raise _fail("tick", "invalid_type")
    if isinstance(applied_actions, (str, bytes)) or not isinstance(
        applied_actions, Sequence
    ):
        raise TypeError("applied_actions must be an ordered sequence")
    if isinstance(prior_events, (str, bytes)) or not isinstance(prior_events, Sequence):
        raise TypeError("prior_events must be an ordered sequence")
    if type(untargeted_request_ids) is not frozenset:
        raise TypeError("untargeted_request_ids must be a frozenset")

    for entity_id in teaching_entity_ids:
        if type(entity_id) is not EntityId:
            raise TypeError("teaching_entity_ids entries must be EntityId")
    enabled = set(start_ledger.entity_ids())
    for action in applied_actions:
        if type(action) is not SkillGrowthInput:
            raise TypeError("applied_actions entries must be SkillGrowthInput")
        if action.actor_id in teaching_entity_ids and action.actor_id not in enabled:
            _LOG.error(
                "teaching_validation_failed field=%s reason_code=%s",
                "entity_id",
                "missing_entity",
            )

    offers = _offers_from_events(prior_events, teaching_entity_ids)
    earlier = _prior_successes(prior_events, untargeted_request_ids)
    current: list[_PracticeFact] = []
    for action in applied_actions:
        if type(action) is not SkillGrowthInput or action.status != "applied":
            continue
        if action.actor_id not in teaching_entity_ids:
            continue
        domain = _practice_domain(action.details, untargeted=action.untargeted_search)
        if domain is None or not _is_applied_practice(action.details):
            continue
        current.append(
            _PracticeFact(
                actor_id=action.actor_id,
                domain=domain,
                success=_is_public_success(action.details),
                origin_location_id=action.origin_location_id,
            )
        )

    sums: dict[EntityId, dict[SkillDomain, float]] = {}
    paid_demonstrate: set[tuple[EntityId, EntityId, SkillDomain, int]] = set()
    for offer in offers:
        if offer.act is not TeachingAct.DEMONSTRATE:
            continue
        if not _in_window(offer, tick, policy.offer_window):
            continue
        if _consumed(
            offer, earlier, before_tick=tick, offer_window=policy.offer_window
        ):
            continue
        key = (
            offer.speaker_id,
            offer.recipient_id,
            offer.domain,
            offer.delivery_tick,
        )
        if key in paid_demonstrate:
            continue
        matched = next(
            (
                fact
                for fact in current
                if fact.success
                and fact.actor_id == offer.speaker_id
                and fact.domain is offer.domain
                and _living_witness(
                    world_state,
                    offer.recipient_id,
                    fact.origin_location_id,
                    rules,
                    tick,
                )
            ),
            None,
        )
        if matched is None:
            continue
        if offer.recipient_id not in enabled:
            _LOG.error(
                "teaching_validation_failed field=%s reason_code=%s",
                "entity_id",
                "missing_entity",
            )
            continue
        start_level = start_ledger.level(offer.recipient_id, offer.domain)
        _add_bonus(
            sums,
            ledger=ledger,
            entity_id=offer.recipient_id,
            domain=offer.domain,
            amount=policy.demonstration_rate * (1.0 - start_level),
            tick=tick,
            act=offer.act,
        )
        paid_demonstrate.add(key)

    paid_joint: set[tuple[EntityId, EntityId, SkillDomain, int]] = set()
    for offer in offers:
        if offer.act is not TeachingAct.PRACTICE_TOGETHER:
            continue
        if not _in_window(offer, tick, policy.offer_window):
            continue
        if _joint_consumed(
            offer,
            prior_events,
            before_tick=tick,
            offer_window=policy.offer_window,
            untargeted_request_ids=untargeted_request_ids,
        ):
            continue
        key = (
            offer.speaker_id,
            offer.recipient_id,
            offer.domain,
            offer.delivery_tick,
        )
        if key in paid_joint:
            continue
        speaker_facts = [
            fact
            for fact in current
            if fact.actor_id == offer.speaker_id and fact.domain is offer.domain
        ]
        recipient_facts = [
            fact
            for fact in current
            if fact.actor_id == offer.recipient_id and fact.domain is offer.domain
        ]
        if not speaker_facts or not recipient_facts:
            continue
        shared = next(
            (
                left.origin_location_id
                for left in speaker_facts
                for right in recipient_facts
                if left.origin_location_id is not None
                and left.origin_location_id == right.origin_location_id
                and _living_witness(
                    world_state,
                    offer.speaker_id,
                    left.origin_location_id,
                    rules,
                    tick,
                )
                and _living_witness(
                    world_state,
                    offer.recipient_id,
                    left.origin_location_id,
                    rules,
                    tick,
                )
            ),
            None,
        )
        if shared is None:
            continue
        for entity_id in (offer.speaker_id, offer.recipient_id):
            if entity_id not in enabled:
                _LOG.error(
                    "teaching_validation_failed field=%s reason_code=%s",
                    "entity_id",
                    "missing_entity",
                )
                continue
            start_level = start_ledger.level(entity_id, offer.domain)
            _add_bonus(
                sums,
                ledger=ledger,
                entity_id=entity_id,
                domain=offer.domain,
                amount=policy.practice_together_rate * (1.0 - start_level),
                tick=tick,
                act=offer.act,
            )
        paid_joint.add(key)
    return ledger.apply_summed_deltas(sums)


def reject_supplied_offers_without_policy(supplied: object | None) -> None:
    """Disabled resume must not carry a caller offer set."""
    if supplied in (None, ()):
        return
    _LOG.error(
        "teaching_offer_mismatch reason_code=%s",
        "teaching_offer_mismatch",
    )
    raise ValueError("teaching_offer_mismatch")


def _event_tick_groups(
    events: Sequence[object],
) -> tuple[tuple[int, tuple[object, ...]], ...]:
    grouped: dict[int, list[object]] = {}
    for event in events:
        grouped.setdefault(int(event.tick), []).append(event)
    return tuple((tick, tuple(grouped[tick])) for tick in sorted(grouped))


def _offer_signature(offer: TeachingOffer) -> tuple[object, ...]:
    return (
        offer.speaker_id,
        offer.recipient_id,
        offer.act,
        offer.domain,
        offer.delivery_tick,
    )


def refold_teaching_offers(
    events: Sequence[object],
    policy: TeachingInteractionPolicy,
    teaching_entity_ids: frozenset[EntityId],
    *,
    tick: int,
    untargeted_request_ids: frozenset[str] = frozenset(),
    project_prefix: object | None = None,
    initial_state: object | None = None,
    expected_run_id: str = "",
    expected_world_id: object | None = None,
    supplied: Sequence[object] | None = None,
) -> tuple[TeachingOffer, ...]:
    """Rebuild open offers at ``tick`` from committed events.

    Earlier tick groups are projected when a prefix projector is supplied.
    A caller-supplied set that disagrees fails with ``teaching_offer_mismatch``.
    """
    if type(policy) is not TeachingInteractionPolicy:
        raise TypeError("policy must be TeachingInteractionPolicy")
    if type(teaching_entity_ids) is not frozenset:
        raise TypeError("teaching_entity_ids must be a frozenset")
    groups = _event_tick_groups(events)
    if project_prefix is not None:
        prefix: list[object] = []
        for event_tick, group in groups:
            if event_tick >= tick:
                break
            prefix.extend(group)
            project_prefix(
                initial_state,
                tuple(prefix),
                expected_run_id,
                expected_world_id,
            )
    prior = tuple(event for event in events if int(event.tick) < tick)
    participants = teaching_entity_ids
    offers = _offers_from_events(prior, participants)
    successes = _prior_successes(prior, untargeted_request_ids)
    open_rows: list[TeachingOffer] = []
    for offer in offers:
        if not _in_window(offer, tick, policy.offer_window):
            continue
        if offer.act is TeachingAct.DEMONSTRATE and _consumed(
            offer,
            successes,
            before_tick=tick,
            offer_window=policy.offer_window,
        ):
            continue
        if offer.act is TeachingAct.PRACTICE_TOGETHER and _joint_consumed(
            offer,
            prior,
            before_tick=tick,
            offer_window=policy.offer_window,
            untargeted_request_ids=untargeted_request_ids,
        ):
            continue
        open_rows.append(offer)
    derived = tuple(open_rows)
    _LOG.debug(
        "teaching_offers_refolded tick=%s open_count=%s",
        tick,
        len(derived),
    )
    if supplied is None:
        return derived
    supplied_rows = tuple(supplied)
    for row in supplied_rows:
        if type(row) is not TeachingOffer:
            _LOG.error(
                "teaching_offer_mismatch reason_code=%s",
                "teaching_offer_mismatch",
            )
            raise ValueError("teaching_offer_mismatch")
    if tuple(sorted(_offer_signature(row) for row in supplied_rows)) != tuple(
        sorted(_offer_signature(row) for row in derived)
    ):
        _LOG.error(
            "teaching_offer_mismatch reason_code=%s",
            "teaching_offer_mismatch",
        )
        raise ValueError("teaching_offer_mismatch")
    return derived
