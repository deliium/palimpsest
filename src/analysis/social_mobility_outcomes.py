"""Bounded observed outcome harvest for social mobility.

Each domain has exactly one measure over observed evidence. Missing evidence is
``unavailable`` downstream and is never zero-filled. Objective events are keyed
by body tokens; detached agent-id rows are translated once through the shared
identity map.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from analysis.economic_inequality_contract import (
    economic_inequality_owner_token,
)
from analysis.economic_inequality_events import (
    harvest_economic_inequality_evidence,
)
from analysis.social_mobility_contract import (
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityError,
    SocialMobilityIdentityMap,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    social_mobility_owner_token,
)
from analysis.social_mobility_policy import (
    SocialMobilityAnalysisPolicy,
    default_social_mobility_analysis_policy,
)
from analysis.social_mobility_rows import SocialMobilityOutcomeRow
from world.events import (
    AgentCreated,
    Asked,
    RepositoryMemberRetrieved,
    Talked,
    Told,
    WorldEvent,
)

__all__ = [
    "SocialMobilityOutcomeHarvest",
    "harvest_social_mobility_outcomes",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_mobility.outcomes")

_SPEECH_DETAILS: Final[tuple[type, ...]] = (Talked, Asked, Told)


@dataclass(frozen=True, slots=True)
class SocialMobilityOutcomeHarvest:
    """Observed outcome rows plus explicit coverage and per-domain counts."""

    rows: tuple[SocialMobilityOutcomeRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: SocialMobilityCoverage = SocialMobilityCoverage.MISSING
    event_count: int = 0
    owner_count: int = 0
    domain_counts: tuple[tuple[str, int], ...] = ()
    unknown_kind_count: int = 0

    def __post_init__(self) -> None:
        for name in ("rows", "notices", "domain_counts"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise SocialMobilityError("social_mobility_outcome_invalid")
        if type(self.coverage) is not SocialMobilityCoverage:
            raise SocialMobilityError("social_mobility_outcome_invalid")
        for name in ("event_count", "owner_count", "unknown_kind_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise SocialMobilityError("social_mobility_outcome_invalid")


def _ordered(events: Sequence[WorldEvent]) -> tuple[WorldEvent, ...]:
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise SocialMobilityError("social_mobility_invalid_input")
    for event in events:
        if type(event) is not WorldEvent:
            raise SocialMobilityError("social_mobility_invalid_input")
    return tuple(sorted(events, key=lambda event: (event.tick, event.sequence)))


def _entity(value: object) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", None)
    return raw if isinstance(raw, str) and raw else None


def _generation_map(
    events: Sequence[WorldEvent],
    identity_map: SocialMobilityIdentityMap,
    policy: SocialMobilityAnalysisPolicy,
) -> dict[str, int]:
    generations = {token: 0 for token in identity_map.forward.values()}
    excluded: set[str] = set()
    for event in events:
        if type(event.details) is not AgentCreated:
            continue
        details = event.details
        try:
            token = identity_map.require_token(details.agent_id)
        except SocialMobilityError:
            continue
        generation = details.generation_index
        if 0 <= generation <= policy.max_generation_index:
            if token not in excluded:
                generations[token] = generation
        else:
            excluded.add(token)
            generations.pop(token, None)
    return generations


def _entity_index(events: Sequence[WorldEvent]) -> dict[str, str]:
    """Map economic owner tokens back to social owner tokens via entity ids."""

    mapping: dict[str, str] = {}
    for event in events:
        for entity in (event.actor_id, event.target_id):
            raw = _entity(entity)
            if raw:
                mapping[economic_inequality_owner_token(raw)] = (
                    social_mobility_owner_token(raw)
                )
        details = event.details
        for name in getattr(type(details), "__dataclass_fields__", {}):
            value = getattr(details, name, None)
            values = value if isinstance(value, tuple) else (value,)
            for item in values:
                raw = _entity(item)
                if raw:
                    mapping[economic_inequality_owner_token(raw)] = (
                        social_mobility_owner_token(raw)
                    )
    return mapping


def _cumulative(
    counts: Mapping[tuple[str, int], int],
    *,
    domain: SocialMobilityDomain,
    measure: SocialMobilityMeasure,
    layer: SocialMobilityLayer,
    generations: Mapping[str, int],
    policy: SocialMobilityAnalysisPolicy,
) -> list[SocialMobilityOutcomeRow]:
    totals: dict[str, int] = {}
    rows: list[SocialMobilityOutcomeRow] = []
    for (token, window), increment in sorted(counts.items()):
        if token not in generations:
            continue
        totals[token] = totals.get(token, 0) + increment
        rows.append(
            SocialMobilityOutcomeRow(
                owner_token=token,
                generation_index=generations[token],
                tick=window * policy.window_ticks + policy.window_ticks - 1,
                window_index=window,
                domain=domain,
                measure=measure,
                quantity=totals[token],
                layer=layer,
            )
        )
    return rows


def _window_for(tick: int, policy: SocialMobilityAnalysisPolicy) -> int:
    index = tick // policy.window_ticks
    return min(index, policy.max_windows - 1)


def harvest_social_mobility_outcomes(
    events: Sequence[WorldEvent],
    *,
    identity_map: SocialMobilityIdentityMap,
    practical_knowledge_audits: Sequence[object] = (),
    teaching_audits: Sequence[object] = (),
    organization_operation_rows: Sequence[object] = (),
    recipe_output_kinds: Mapping[str, str] | None = None,
    recipe_structure_kinds: Mapping[str, str] | None = None,
    policy: SocialMobilityAnalysisPolicy | None = None,
) -> SocialMobilityOutcomeHarvest:
    """Harvest one measured quantity per owner, domain, and window."""

    active = default_social_mobility_analysis_policy() if policy is None else policy
    ordered = _ordered(events)
    notices: list[str] = []
    partial = False

    economic = harvest_economic_inequality_evidence(
        ordered,
        recipe_output_kinds=recipe_output_kinds,
        recipe_structure_kinds=recipe_structure_kinds,
    )
    entity_index = _entity_index(ordered)
    generations = _generation_map(ordered, identity_map, active)

    rows: list[SocialMobilityOutcomeRow] = []
    possession: dict[tuple[str, int], tuple[int, int, int]] = {}
    for possession_row in economic.possession_rows:
        token = entity_index.get(possession_row.owner_token)
        if token is None:
            notices.append("social_mobility_unmapped_owner")
            partial = True
            continue
        possession[(token, possession_row.window_index)] = (
            possession_row.observed_item_count,
            possession_row.observed_tool_count,
            possession_row.tick,
        )
    access: dict[tuple[str, int], tuple[int, int]] = {}
    for access_row in economic.access_rows:
        token = entity_index.get(access_row.owner_token)
        if token is None:
            continue
        access[(token, access_row.window_index)] = (
            access_row.accessible_infrastructure_count,
            access_row.accessible_storage_count,
        )

    clamp = active.max_pairs * 10_000
    for (token, window), (items, tools, tick) in sorted(possession.items()):
        if token not in generations:
            continue
        generation = generations[token]
        resources = max(0, items - tools)
        rows.append(
            SocialMobilityOutcomeRow(
                owner_token=token,
                generation_index=generation,
                tick=tick,
                window_index=window,
                domain=SocialMobilityDomain.RESOURCES,
                measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
                quantity=resources,
                layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
            )
        )
        infra, storage = access.get((token, window), (0, 0))
        assets = min(clamp, tools + infra + storage)
        rows.append(
            SocialMobilityOutcomeRow(
                owner_token=token,
                generation_index=generation,
                tick=tick,
                window_index=window,
                domain=SocialMobilityDomain.PRODUCTIVE_ASSETS,
                measure=SocialMobilityMeasure.OBSERVED_PRODUCTIVE_ASSET_COUNT,
                quantity=assets,
                layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
            )
        )
    if economic.unknown_kind_count:
        notices.append("social_mobility_unknown_item_kind")
        partial = True

    skill_keys: dict[str, dict[int, set[str]]] = {}
    for audit in practical_knowledge_audits:
        if getattr(audit, "active", False) is not True:
            continue
        try:
            owner_id = getattr(audit, "owner_id", None)
            if owner_id is None:
                raise SocialMobilityError("social_mobility_outcome_invalid")
            token = identity_map.require_token(getattr(owner_id, "value", owner_id))
        except SocialMobilityError:
            notices.append("social_mobility_unmapped_owner")
            partial = True
            continue
        if token not in generations:
            continue
        content_key = getattr(audit, "content_key", None)
        if type(content_key) is not str or not content_key:
            notices.append("social_mobility_outcome_invalid")
            partial = True
            continue
        acquired_tick = getattr(audit, "acquired_tick", None)
        if type(acquired_tick) is not int or acquired_tick < 0:
            notices.append("social_mobility_outcome_invalid")
            partial = True
            continue
        window = _window_for(acquired_tick, active)
        skill_keys.setdefault(token, {}).setdefault(window, set()).add(content_key)
    for token, by_window in sorted(skill_keys.items()):
        cumulative: set[str] = set()
        for window, keys in sorted(by_window.items()):
            cumulative.update(keys)
            rows.append(
                SocialMobilityOutcomeRow(
                    owner_token=token,
                    generation_index=generations[token],
                    tick=window * active.window_ticks + active.window_ticks - 1,
                    window_index=window,
                    domain=SocialMobilityDomain.SKILLS,
                    measure=SocialMobilityMeasure.KNOWN_TECHNIQUE_COUNT,
                    quantity=len(cumulative),
                    layer=SocialMobilityLayer.OWNER_OUTCOME,
                )
            )

    education_counts: dict[tuple[str, int], int] = {}
    for audit in teaching_audits:
        agent_id = getattr(audit, "agent_id", None)
        if agent_id is None:
            notices.append("social_mobility_outcome_invalid")
            partial = True
            continue
        try:
            token = identity_map.require_token(getattr(agent_id, "value", agent_id))
        except SocialMobilityError:
            notices.append("social_mobility_unmapped_owner")
            partial = True
            continue
        if token not in generations:
            continue
        audit_tick = getattr(audit, "tick", None)
        if type(audit_tick) is not int or audit_tick < 0:
            notices.append("social_mobility_outcome_invalid")
            partial = True
            continue
        window = _window_for(audit_tick, active)
        key = (token, window)
        education_counts[key] = education_counts.get(key, 0) + 1
    for event in ordered:
        if type(event.details) is not RepositoryMemberRetrieved:
            continue
        raw = _entity(event.details.actor_id)
        if raw is None:
            continue
        token = social_mobility_owner_token(raw)
        if token not in generations:
            continue
        window = _window_for(event.tick, active)
        key = (token, window)
        education_counts[key] = education_counts.get(key, 0) + 1
    rows.extend(
        _cumulative(
            education_counts,
            domain=SocialMobilityDomain.EDUCATIONAL_ACCESS,
            measure=SocialMobilityMeasure.EDUCATIONAL_ACCESS_RECEIPT_COUNT,
            layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
            generations=generations,
            policy=active,
        )
    )

    partner_counts: dict[tuple[str, int], set[str]] = {}
    for event in ordered:
        if type(event.details) not in _SPEECH_DETAILS:
            continue
        speech = cast(Talked | Asked | Told, event.details)
        actor = _entity(event.actor_id)
        recipient = _entity(speech.recipient_id)
        if actor is None or recipient is None:
            continue
        token = social_mobility_owner_token(recipient)
        window = _window_for(event.tick, active)
        partner_counts.setdefault((token, window), set()).add(actor)
    influence_counts = {key: len(partners) for key, partners in partner_counts.items()}
    influence_rows: list[SocialMobilityOutcomeRow] = []
    for (token, window), partners in sorted(influence_counts.items()):
        if token not in generations:
            continue
        influence_rows.append(
            SocialMobilityOutcomeRow(
                owner_token=token,
                generation_index=generations[token],
                tick=window * active.window_ticks + active.window_ticks - 1,
                window_index=window,
                domain=SocialMobilityDomain.SOCIAL_INFLUENCE,
                measure=SocialMobilityMeasure.INBOUND_COMMUNICATION_PARTNER_COUNT,
                quantity=partners,
                layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
            )
        )
    rows.extend(influence_rows)

    role_offices: dict[tuple[str, int], set[str]] = {}
    for harvest_rows in organization_operation_rows:
        for assignment in getattr(harvest_rows, "assignments", ()) or ():
            occupant = getattr(assignment, "occupant_id", None)
            office = getattr(assignment, "office_id", None)
            if occupant is None or office is None:
                continue
            if getattr(assignment, "stance", None) == "rejected":
                continue
            try:
                token = identity_map.require_token(occupant)
            except SocialMobilityError:
                notices.append("social_mobility_unmapped_owner")
                partial = True
                continue
            if token not in generations:
                continue
            assignment_tick = getattr(assignment, "last_tick", None)
            if type(assignment_tick) is not int or assignment_tick < 0:
                assignment_tick = getattr(assignment, "first_tick", 0)
            if type(assignment_tick) is not int or assignment_tick < 0:
                notices.append("social_mobility_outcome_invalid")
                partial = True
                continue
            window = _window_for(assignment_tick, active)
            role_offices.setdefault((token, window), set()).add(office)
    role_totals: dict[str, set[str]] = {}
    for (token, window), offices in sorted(role_offices.items()):
        if token not in generations:
            continue
        role_totals.setdefault(token, set()).update(offices)
        rows.append(
            SocialMobilityOutcomeRow(
                owner_token=token,
                generation_index=generations[token],
                tick=window * active.window_ticks + active.window_ticks - 1,
                window_index=window,
                domain=SocialMobilityDomain.ORGANIZATION_ROLES,
                measure=SocialMobilityMeasure.HELD_ORGANIZATION_ROLE_COUNT,
                quantity=len(role_totals[token]),
                layer=SocialMobilityLayer.OWNER_OUTCOME,
            )
        )

    rows.sort(key=lambda row: (row.window_index, row.domain.value, row.owner_token))
    if len(rows) > active.max_domain_rows:
        rows = rows[: active.max_domain_rows]
        notices.append("social_mobility_outcome_truncated")
        partial = True

    domain_counts = tuple(
        (domain.value, sum(1 for row in rows if row.domain is domain))
        for domain in SocialMobilityDomain
    )
    unavailable = [domain for domain, count in domain_counts if count == 0]
    if unavailable:
        notices.append("social_mobility_domain_unavailable")
        for domain in unavailable:
            _LOG.warning("social_mobility_domain_unavailable domain=%s", domain)

    unique_notices = tuple(dict.fromkeys(notices))[: active.max_notices]
    coverage = (
        SocialMobilityCoverage.PARTIAL
        if partial
        else (
            SocialMobilityCoverage.COMPLETE if rows else SocialMobilityCoverage.MISSING
        )
    )
    owner_count = len({row.owner_token for row in rows})
    _LOG.debug(
        "social_mobility_outcomes_harvested events=%d rows=%d owners=%d "
        "unknown_kinds=%d",
        len(ordered),
        len(rows),
        owner_count,
        economic.unknown_kind_count,
    )
    return SocialMobilityOutcomeHarvest(
        rows=tuple(rows),
        notices=unique_notices,
        coverage=coverage,
        event_count=len(ordered),
        owner_count=owner_count,
        domain_counts=domain_counts,
        unknown_kind_count=economic.unknown_kind_count,
    )
