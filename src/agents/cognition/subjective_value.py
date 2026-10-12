"""Owner-scoped reservations. These numbers are not a world price."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace

from agents.cognition.scarcity_beliefs import (
    ScarcityBelief,
    ScarcityBeliefLedger,
    empty_scarcity_beliefs,
    scarcity_row,
    store_scarcity_belief,
)
from agents.models import AgentId
from world.identifiers import EntityId
from world.values import ItemKind

_LOG = logging.getLogger("agents.cognition.subjective_value")

VALUATION_COMPONENTS: frozenset[str] = frozenset(
    {
        "need",
        "inventory",
        "scarcity",
        "plan",
        "risk",
        "expected_future",
        "observed_acceptance",
    }
)
_RESERVATION_MAX = 16


@dataclass(frozen=True, slots=True)
class ValuationComponent:
    """One closed contribution to a reservation."""

    token: str
    amount: int

    def __post_init__(self) -> None:
        if self.token not in VALUATION_COMPONENTS:
            raise ValueError("ValuationComponent.token")
        if type(self.amount) is not int or isinstance(self.amount, bool):
            raise TypeError("ValuationComponent.amount must be int")


@dataclass(frozen=True, slots=True)
class ValuationRow:
    """One kind appraisal or one judgment of a named proposal."""

    item_kind: ItemKind
    reference_kind: ItemKind
    reservation: int
    components: tuple[ValuationComponent, ...]
    tick: int
    counterparty_id: EntityId | None = None

    def __post_init__(self) -> None:
        if type(self.item_kind) is not ItemKind:
            raise TypeError("ValuationRow.item_kind must be ItemKind")
        if type(self.reference_kind) is not ItemKind:
            raise TypeError("ValuationRow.reference_kind must be ItemKind")
        if (
            type(self.reservation) is not int
            or isinstance(self.reservation, bool)
            or not 0 <= self.reservation <= _RESERVATION_MAX
        ):
            raise ValueError("reservation must be in [0, 16]")
        if self.item_kind is self.reference_kind and self.reservation != 1:
            raise ValueError("reference kind reservation must be 1")
        if isinstance(self.components, (str, bytes)) or not isinstance(
            self.components, tuple
        ):
            raise TypeError("components must be a tuple")
        seen: set[str] = set()
        for component in self.components:
            if type(component) is not ValuationComponent:
                raise TypeError("components entries must be ValuationComponent")
            if component.token in seen:
                raise ValueError("duplicate valuation component")
            seen.add(component.token)
        if (
            self.counterparty_id is not None
            and type(self.counterparty_id) is not EntityId
        ):
            raise TypeError("counterparty_id must be EntityId or None")
        if type(self.tick) is not int or isinstance(self.tick, bool) or self.tick < 0:
            raise ValueError("ValuationRow.tick must be a non-negative int")


@dataclass(frozen=True, slots=True)
class SubjectiveValuationLedger:
    """Latest kind row per item kind, plus judgments this owner answered."""

    owner_id: AgentId
    kind_rows: tuple[ValuationRow, ...] = ()
    judgment_rows: tuple[ValuationRow, ...] = ()
    max_judgments: int = 32

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("SubjectiveValuationLedger.owner_id must be AgentId")
        if (
            type(self.max_judgments) is not int
            or isinstance(self.max_judgments, bool)
            or not 1 <= self.max_judgments <= 32
        ):
            raise ValueError("max_judgments must be in [1, 32]")
        kind_rows = _row_tuple("kind_rows", self.kind_rows)
        judgment_rows = _row_tuple("judgment_rows", self.judgment_rows)
        seen: set[ItemKind] = set()
        for row in kind_rows:
            if row.counterparty_id is not None:
                raise ValueError("kind rows have no counterparty")
            if row.item_kind in seen:
                raise ValueError("duplicate kind row")
            seen.add(row.item_kind)
        for row in judgment_rows:
            if row.counterparty_id is None:
                raise ValueError("judgment rows require a counterparty")
        if len(judgment_rows) > self.max_judgments:
            raise ValueError("judgment cap exceeded")
        object.__setattr__(self, "kind_rows", kind_rows)
        object.__setattr__(self, "judgment_rows", judgment_rows)


def _row_tuple(name: str, value: object) -> tuple[ValuationRow, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    copied: list[ValuationRow] = []
    for row in value:
        if type(row) is not ValuationRow:
            raise TypeError(f"{name} entries must be ValuationRow")
        copied.append(row)
    return tuple(copied)


def empty_subjective_valuations(owner_id: AgentId) -> SubjectiveValuationLedger:
    """Blank owner ledger. Does not copy another owner's reservations."""
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    return SubjectiveValuationLedger(owner_id)


def require_owner_subjective_valuations(
    value: object | None, owner_id: AgentId, *, field_name: str
) -> None:
    if value is None:
        return
    if type(value) is not SubjectiveValuationLedger:
        raise TypeError(f"{field_name} must be SubjectiveValuationLedger or None")
    if value.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


def reference_kind_for(hunger: int, thirst: int) -> ItemKind:
    """This owner's unit for one appraisal. Not a shared numeraire."""
    if hunger > thirst and hunger > 0:
        return ItemKind.FOOD
    if thirst > hunger and thirst > 0:
        return ItemKind.WATER
    return ItemKind.FOOD


def appraise_reservation(
    *,
    item_kind: ItemKind,
    hunger: int = 0,
    thirst: int = 0,
    health: int = 100,
    body_present: bool = True,
    held_count: int = 0,
    others_visible_count: int | None = None,
    plan_names_kind: bool = False,
    risk_active: bool = False,
    expected_future_scarcity: bool = False,
    observed_acceptance: int | None = None,
    tick: int = 0,
) -> ValuationRow:
    """Integer reservation for one kind. The world never reads this number."""
    if type(item_kind) is not ItemKind:
        raise TypeError("item_kind must be ItemKind")
    acceptance = _acceptance_component(observed_acceptance, item_kind)
    reference = reference_kind_for(hunger, thirst)
    if item_kind is reference:
        return ValuationRow(item_kind, reference, 1, (), tick)
    need = 0
    if body_present:
        if item_kind is ItemKind.FOOD:
            need = hunger // 8
        elif item_kind is ItemKind.WATER:
            need = thirst // 8
        elif item_kind is ItemKind.MEDICAL:
            need = (100 - health) // 8
    inventory = -min(4, max(0, held_count - 1))
    if others_visible_count is None:
        scarcity = 0
    elif others_visible_count <= 0:
        scarcity = 4
    elif others_visible_count == 1:
        scarcity = 3
    else:
        scarcity = 0
    plan = 4 if plan_names_kind else 0
    risk = (
        2
        if risk_active
        and item_kind in {ItemKind.FOOD, ItemKind.WATER, ItemKind.MEDICAL}
        else 0
    )
    future = 2 if expected_future_scarcity else 0
    parts = (
        ("need", need),
        ("inventory", inventory),
        ("scarcity", scarcity),
        ("plan", plan),
        ("risk", risk),
        ("expected_future", future),
        ("observed_acceptance", acceptance),
    )
    reservation = max(0, min(16, sum(amount for _token, amount in parts)))
    components = tuple(
        ValuationComponent(token, amount) for token, amount in parts if amount
    )
    row = ValuationRow(item_kind, reference, reservation, components, tick)
    _LOG.debug(
        "valuation_appraised item_kind=%s reservation=%s components=%s",
        item_kind.value,
        reservation,
        ",".join(component.token for component in components),
    )
    return row


def _acceptance_component(value: int | None, item_kind: ItemKind) -> int:
    if value is None:
        _LOG.debug(
            "valuation_acceptance_omitted item_kind=%s",
            item_kind.value,
        )
        return 0
    if type(value) is not int or isinstance(value, bool) or not 0 <= value <= 64:
        _LOG.error(
            "valuation_acceptance_invalid item_kind=%s received_count=%s",
            item_kind.value,
            value,
        )
        raise ValueError("observed_acceptance must be an int in [0, 64] or None")
    if value >= 8:
        return 3
    if value >= 3:
        return 2
    if value >= 1:
        return 1
    return 0


def bundle_concession(
    *,
    debt: float = 0.0,
    affection: float = 0.0,
    obligation: bool = False,
) -> int:
    """Relationship and debt concessions. They do not change the stored reservation."""
    total = 0
    if debt >= 0.4:
        total += 1
    if affection >= 0.6:
        total += 1
    if obligation:
        total += 1
    return min(3, total)


def bundle_acceptable(
    *, received: int, given: int, concession: int = 0
) -> bool:
    """Local test only. The engine does not call this."""
    return received + concession >= given


def remember_judgment(
    ledger: SubjectiveValuationLedger, row: ValuationRow
) -> SubjectiveValuationLedger:
    """Keep one judgment per answered proposal. Drop the oldest past the cap."""
    if type(ledger) is not SubjectiveValuationLedger:
        raise TypeError("ledger must be SubjectiveValuationLedger")
    if type(row) is not ValuationRow or row.counterparty_id is None:
        raise ValueError("judgment rows require a counterparty")
    rows = (*ledger.judgment_rows, row)
    while len(rows) > ledger.max_judgments:
        _LOG.debug(
            "valuation_judgment_dropped owner_id=%s item_kind=%s",
            ledger.owner_id.value,
            rows[0].item_kind.value,
        )
        rows = rows[1:]
    return replace(ledger, judgment_rows=rows)


def refresh_owner_ledgers(
    *,
    owner_id: AgentId,
    valuations: SubjectiveValuationLedger | None,
    scarcity: ScarcityBeliefLedger | None,
    tick: int,
    hunger: int,
    thirst: int,
    health: int,
    body_present: bool,
    held_counts: dict[ItemKind, int],
    ground_kinds: tuple[ItemKind, ...],
    other_held_kinds: tuple[ItemKind, ...],
    location_id: EntityId | None,
    plan_kinds: frozenset[ItemKind],
    risk_active: bool,
    future_kinds: frozenset[ItemKind],
    acceptance_counts: dict[ItemKind, int | None] | None = None,
    judgment_kind: ItemKind | None = None,
    counterparty_id: EntityId | None = None,
    max_judgments: int = 32,
) -> tuple[SubjectiveValuationLedger, ScarcityBeliefLedger]:
    """Appraise this owner only. Another owner's rows are never copied in."""
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if valuations is None or valuations.owner_id != owner_id:
        valuations = SubjectiveValuationLedger(owner_id, max_judgments=max_judgments)
    if scarcity is None or scarcity.owner_id != owner_id:
        scarcity = empty_scarcity_beliefs(owner_id)
    visible: dict[ItemKind, int] = {}
    for kind in (*ground_kinds, *other_held_kinds):
        visible[kind] = min(64, visible.get(kind, 0) + 1)
    if location_id is not None:
        for kind in ItemKind:
            scarcity = store_scarcity_belief(
                scarcity,
                ScarcityBelief(kind, visible.get(kind, 0), location_id, tick),
            )
    for kind in ItemKind:
        if location_id is not None:
            others = visible.get(kind, 0)
        else:
            stored = scarcity_row(scarcity, kind)
            others = None if stored is None else stored.believed_local_count
        row = appraise_reservation(
            item_kind=kind,
            hunger=hunger,
            thirst=thirst,
            health=health,
            body_present=body_present,
            held_count=held_counts.get(kind, 0),
            others_visible_count=others,
            plan_names_kind=kind in plan_kinds,
            risk_active=risk_active,
            expected_future_scarcity=kind in future_kinds,
            observed_acceptance=(
                None
                if acceptance_counts is None
                else acceptance_counts.get(kind)
            ),
            tick=tick,
        )
        valuations = store_kind_valuation(valuations, row)
    if judgment_kind is not None and counterparty_id is not None:
        judged = next(
            row for row in valuations.kind_rows if row.item_kind is judgment_kind
        )
        valuations = remember_judgment(
            valuations,
            replace(judged, counterparty_id=counterparty_id),
        )
    _LOG.debug(
        "valuation_bound owner_id=%s kind_row_count=%s",
        owner_id.value,
        len(valuations.kind_rows),
    )
    return valuations, scarcity


def store_kind_valuation(
    ledger: SubjectiveValuationLedger, row: ValuationRow
) -> SubjectiveValuationLedger:
    """Keep the latest kind row. Kind rows are never dropped for age."""
    if type(ledger) is not SubjectiveValuationLedger:
        raise TypeError("ledger must be SubjectiveValuationLedger")
    if type(row) is not ValuationRow or row.counterparty_id is not None:
        raise ValueError("kind valuation has no counterparty")
    kept = tuple(
        item for item in ledger.kind_rows if item.item_kind is not row.item_kind
    )
    updated = replace(ledger, kind_rows=(*kept, row))
    _LOG.debug(
        "valuation_stored owner_id=%s item_kind=%s reservation=%s",
        ledger.owner_id.value,
        row.item_kind.value,
        row.reservation,
    )
    return updated


def propose_exchange_command(
    command: object,
    observation: object,
    *,
    channel_on: bool,
    max_bundle: int,
    valuations: object | None,
    owner_entity_id: EntityId,
    relationships: object | None = None,
    commitments: object | None = None,
    resource_exchange_profile_active: bool = False,
) -> object:
    """Answer a perceived proposal. Channel off returns the ranked command."""
    from world.actions import Attack, Give, NegotiateExchange

    if not channel_on:
        return command
    if type(owner_entity_id) is not EntityId:
        raise TypeError("owner_entity_id must be EntityId")
    if type(max_bundle) is not int or not 1 <= max_bundle <= 8:
        raise ValueError("max_bundle")
    proposal = _perceived_proposal(observation, owner_entity_id)
    if proposal is None or type(valuations) is not SubjectiveValuationLedger:
        return command
    actor, give_ids, give_kinds, take_ids, take_kinds = proposal
    concession = _concession_for(
        relationships,
        commitments,
        owner_entity_id=owner_entity_id,
        kinds=(*give_kinds, *take_kinds),
    )
    received = _bundle_value(valuations, give_kinds)
    given = _bundle_value(valuations, take_kinds)
    if bundle_acceptable(received=received, given=given, concession=concession):
        chosen: object = NegotiateExchange(
            actor, "accept", tuple(take_ids), tuple(give_ids)
        )
    else:
        chosen = _counter_or_withdraw(
            observation,
            valuations,
            actor=actor,
            give_ids=give_ids,
            give_kinds=give_kinds,
            take_ids=take_ids,
            take_kinds=take_kinds,
            max_bundle=max_bundle,
            prefer_inert=resource_exchange_profile_active,
        )
    if type(chosen) in {Give, Attack}:
        return command
    act = getattr(chosen, "act", "")
    _LOG.debug("exchange_proposal command=%s act=%s", getattr(chosen, "kind", ""), act)
    if type(chosen) is NegotiateExchange:
        _LOG.info(
            "exchange_proposal_selected act=%s give_len=%s take_len=%s",
            chosen.act,
            len(chosen.give_item_ids),
            len(chosen.take_item_ids),
        )
    return chosen


def _bundle_value(
    ledger: SubjectiveValuationLedger, kinds: tuple[ItemKind, ...]
) -> int:
    reservations = {row.item_kind: row.reservation for row in ledger.kind_rows}
    return sum(reservations.get(kind, 0) for kind in kinds)


def _perceived_proposal(
    observation: object, owner_entity_id: EntityId
) -> tuple[object, ...] | None:
    from world.observations import ObservationAudienceRole

    found = None
    for occurrence in getattr(observation, "occurrences", ()) or ():
        facts = getattr(occurrence, "public_facts", {})
        if not isinstance(facts, dict) and not hasattr(facts, "get"):
            continue
        if facts.get("kind") != "exchange_proposed":
            continue
        role = getattr(occurrence, "audience_role", None)
        if role is not ObservationAudienceRole.TARGET:
            continue
        actor = getattr(occurrence, "actor_id", None)
        if type(actor) is not EntityId or actor == owner_entity_id:
            continue
        give_ids, give_kinds = _fact_items(facts, "give")
        take_ids, take_kinds = _fact_items(facts, "take")
        if give_ids and take_ids:
            found = (actor, give_ids, give_kinds, take_ids, take_kinds)
    return found


def _fact_items(
    facts: object, side: str
) -> tuple[tuple[EntityId, ...], tuple[ItemKind, ...]]:
    ids = tuple(
        EntityId(str(value)) for value in facts.get(f"{side}_item_ids", ()) or ()
    )
    by_value = {kind.value: kind for kind in ItemKind}
    kinds = tuple(
        by_value[str(value)]
        for value in facts.get(f"{side}_item_kinds", ()) or ()
        if str(value) in by_value
    )
    if len(ids) != len(kinds):
        return (), ()
    return ids, kinds


def _counter_or_withdraw(
    observation: object,
    ledger: SubjectiveValuationLedger,
    *,
    actor: EntityId,
    give_ids: tuple[EntityId, ...],
    give_kinds: tuple[ItemKind, ...],
    take_ids: tuple[EntityId, ...],
    take_kinds: tuple[ItemKind, ...],
    max_bundle: int,
    prefer_inert: bool = False,
) -> object:
    from world.actions import NegotiateExchange
    from world.observations import ObservedItemPlacement

    reference = _reference_kind(ledger, (*give_kinds, *take_kinds))
    tool = next(
        (kind for kind in (*give_kinds, *take_kinds) if kind is not reference),
        reference,
    )
    count = min(max_bundle, _bundle_value(ledger, (tool,)))
    their_reference = _holding_ids(observation, actor, reference)
    own_reference = _own_ids(observation, reference, ObservedItemPlacement)
    own_extra = _own_ids(observation, None, ObservedItemPlacement)
    if tool in take_kinds:
        _LOG.debug(
            "exchange_give_preference_skipped owner_id=%s reason=tool_side",
            ledger.owner_id.value,
        )
        give = tuple(
            item_id
            for item_id, kind in zip(take_ids, take_kinds, strict=True)
            if kind is tool
        )
        take = their_reference[:count]
        filled = len(give) <= max_bundle and len(take) == count and count > 0
        nothing_else = all(item_id in give for item_id in own_extra)
    else:
        take = tuple(
            item_id
            for item_id, kind in zip(give_ids, give_kinds, strict=True)
            if kind is tool
        )
        if prefer_inert:
            give, give_value = _fill_reference_give(
                observation,
                ledger,
                reference=reference,
                target=count,
                max_bundle=max_bundle,
                placement_type=ObservedItemPlacement,
            )
            filled = (
                len(take) > 0
                and len(give) > 0
                and give_value >= count
                and count > 0
            )
        else:
            _LOG.debug(
                "exchange_give_preference_skipped owner_id=%s reason=channel_off",
                ledger.owner_id.value,
            )
            give = own_reference[:count]
            filled = len(take) <= max_bundle and len(give) == count and count > 0
        nothing_else = all(item_id in give for item_id in own_extra)
    if not filled and nothing_else:
        _LOG.debug(
            "exchange_give_preference_skipped owner_id=%s reason=bundle_rejected",
            ledger.owner_id.value,
        )
        return NegotiateExchange(actor, "withdraw", (), ())
    if not filled:
        _LOG.debug(
            "exchange_give_preference_skipped owner_id=%s reason=bundle_rejected",
            ledger.owner_id.value,
        )
        return NegotiateExchange(actor, "withdraw", (), ())
    return NegotiateExchange(
        actor, "counteroffer", give[:max_bundle], take[:max_bundle]
    )


def _fill_reference_give(
    observation: object,
    ledger: SubjectiveValuationLedger,
    *,
    reference: ItemKind,
    target: int,
    max_bundle: int,
    placement_type: type,
) -> tuple[tuple[EntityId, ...], int]:
    """Spend remembered inert portable items, then reference items, up to the target."""
    from world.resource_profile import physical_profile

    held = placement_type.HELD_BY_SELF
    items = sorted(
        (
            item
            for item in getattr(observation, "items", ()) or ()
            if item.placement is held
        ),
        key=lambda item: item.entity_id.value,
    )
    reservations = {row.item_kind: row.reservation for row in ledger.kind_rows}
    chosen: list[EntityId] = []
    value = 0
    for item in items:
        if len(chosen) >= max_bundle or value >= target:
            break
        tokens = physical_profile(item.kind, item.load)
        component = _component_amount(ledger, item.kind, "observed_acceptance")
        if "inert" not in tokens or "portable" not in tokens:
            _LOG.debug(
                "exchange_give_preference_skipped owner_id=%s item_id=%s "
                "reason=not_inert",
                ledger.owner_id.value,
                item.entity_id.value,
            )
            continue
        if component < 2:
            _LOG.debug(
                "exchange_give_preference_skipped owner_id=%s item_id=%s "
                "reason=below_component",
                ledger.owner_id.value,
                item.entity_id.value,
            )
            continue
        item_value = reservations.get(item.kind, 0)
        if item_value <= 0:
            continue
        chosen.append(item.entity_id)
        value += item_value
        _LOG.debug(
            "exchange_give_preference owner_id=%s item_id=%s item_kind=%s "
            "acceptance_component=%s",
            ledger.owner_id.value,
            item.entity_id.value,
            item.kind.value,
            component,
        )
    for item in items:
        if len(chosen) >= max_bundle or value >= target:
            break
        if item.kind is not reference or item.entity_id in chosen:
            continue
        chosen.append(item.entity_id)
        value += 1
    return tuple(chosen), value


def _component_amount(
    ledger: SubjectiveValuationLedger, kind: ItemKind, token: str
) -> int:
    for row in ledger.kind_rows:
        if row.item_kind is not kind:
            continue
        for component in row.components:
            if component.token == token:
                return component.amount
    return 0


def _reference_kind(
    ledger: SubjectiveValuationLedger, kinds: tuple[ItemKind, ...]
) -> ItemKind:
    for row in ledger.kind_rows:
        if row.item_kind in kinds:
            return row.reference_kind
    if ledger.kind_rows:
        return ledger.kind_rows[0].reference_kind
    return ItemKind.FOOD


def _holding_ids(
    observation: object, body_id: EntityId, kind: ItemKind
) -> tuple[EntityId, ...]:
    holdings = getattr(observation, "exchange_visible_holdings", None) or ()
    return tuple(
        holding.item_id
        for holding in holdings
        if holding.body_id == body_id and holding.kind is kind
    )


def _own_ids(
    observation: object, kind: ItemKind | None, placement_type: type
) -> tuple[EntityId, ...]:
    held = placement_type.HELD_BY_SELF
    return tuple(
        item.entity_id
        for item in getattr(observation, "items", ()) or ()
        if item.placement is held and (kind is None or item.kind is kind)
    )


def _concession_for(
    relationships: object | None,
    commitments: object | None,
    *,
    owner_entity_id: EntityId,
    kinds: tuple[ItemKind, ...],
) -> int:
    debt = 0.0
    affection = 0.0
    profiles = relationships if isinstance(relationships, tuple) else ()
    for profile in profiles:
        for dimension in getattr(profile, "dimensions", ()):
            name = getattr(getattr(dimension, "dimension", None), "value", "")
            if name == "debt":
                debt = float(getattr(dimension, "value", 0.0))
            elif name == "affection":
                affection = float(getattr(dimension, "value", 0.0))
    obligation = False
    kind_values = {kind.value for kind in kinds}
    for row in getattr(commitments, "interpretations", ()) or ():
        if row.debtor_id != owner_entity_id.value:
            continue
        if row.status not in {"proposed", "accepted", "open", "partial"}:
            continue
        if row.item_kind in kind_values or row.now_item_kind in kind_values:
            obligation = True
    return bundle_concession(debt=debt, affection=affection, obligation=obligation)
