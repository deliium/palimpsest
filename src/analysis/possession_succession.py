"""Analysis-only labels for corpse custody. Not an inheritance law.

Physical holders and legitimacy claims stay separate. This module never
moves items and is not imported by ``WorldEngine``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from world.events import (
    CorpseCustodyOpened,
    Given,
    PossessionClaimAsserted,
    TakenFromCorpse,
    WorldEvent,
)
from world.identifiers import require_exact_nonneg_int
from world.possession_succession import POSSESSION_DOCTRINES

_LOG: Final[logging.Logger] = logging.getLogger("analysis.possession_succession")
_CORPSE: Final[str] = "corpse"
_DOCTRINES: Final[tuple[str, ...]] = tuple(sorted(POSSESSION_DOCTRINES))


@dataclass(frozen=True, slots=True)
class PossessionLedgerSnapshot:
    """Detached support counts for one owner at one place. Not a world rule."""

    owner_id: str
    alive: bool
    location_id: str
    supports: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not str or self.owner_id == "":
            raise ValueError("PossessionLedgerSnapshot.owner_id")
        if type(self.alive) is not bool:
            raise TypeError("PossessionLedgerSnapshot.alive must be bool")
        if type(self.location_id) is not str or self.location_id == "":
            raise ValueError("PossessionLedgerSnapshot.location_id")
        if not isinstance(self.supports, tuple):
            raise TypeError("supports must be a tuple")
        for doctrine, count in self.supports:
            if doctrine not in POSSESSION_DOCTRINES:
                raise ValueError("PossessionLedgerSnapshot.supports")
            if type(count) is not int or count < 1:
                raise ValueError("PossessionLedgerSnapshot.supports")


@dataclass(frozen=True, slots=True)
class PossessionEpisode:
    """One decedent custody episode. Holders are not legitimacy winners."""

    decedent_id: str
    location_id: str
    opened_tick: int
    physical_possession: tuple[tuple[str, str], ...]
    legitimacy_claims: tuple[tuple[str, str, str | None], ...]
    conflict: bool
    appropriation: bool
    voluntary_transfer: bool
    convention_token: str
    alignment: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "opened_tick",
            require_exact_nonneg_int("opened_tick", self.opened_tick),
        )
        if type(self.conflict) is not bool:
            raise TypeError("conflict must be bool")
        if type(self.appropriation) is not bool:
            raise TypeError("appropriation must be bool")
        if type(self.voluntary_transfer) is not bool:
            raise TypeError("voluntary_transfer must be bool")


def classify_possession_episodes(
    events: Sequence[WorldEvent],
    *,
    as_of_tick: int,
    ledgers: Sequence[PossessionLedgerSnapshot] = (),
    children_of: Mapping[str, frozenset[str]] | None = None,
    caregivers_of: Mapping[str, frozenset[str]] | None = None,
    co_members_of: Mapping[str, frozenset[str]] | None = None,
) -> tuple[PossessionEpisode, ...]:
    """Label each custody opening. Missing graphs are ``not_applicable``."""
    typed_tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("events must be a sequence of WorldEvent")
    ordered = tuple(
        event
        for event in events
        if type(event) is WorldEvent and event.tick <= typed_tick
    )
    episodes: list[PossessionEpisode] = []
    for index, event in enumerate(ordered):
        details = event.details
        if type(details) is not CorpseCustodyOpened:
            continue
        episode = _episode(
            ordered[index:],
            details,
            opened_tick=event.tick,
            ledgers=ledgers,
            children_of=children_of,
            caregivers_of=caregivers_of,
            co_members_of=co_members_of,
        )
        _LOG.debug(
            "possession_episode convention_token=%s conflict=%s appropriation=%s",
            episode.convention_token,
            episode.conflict,
            episode.appropriation,
        )
        episodes.append(episode)
    return tuple(episodes)


def _episode(
    events: tuple[WorldEvent, ...],
    opened: CorpseCustodyOpened,
    *,
    opened_tick: int,
    ledgers: Sequence[PossessionLedgerSnapshot],
    children_of: Mapping[str, frozenset[str]] | None,
    caregivers_of: Mapping[str, frozenset[str]] | None,
    co_members_of: Mapping[str, frozenset[str]] | None,
) -> PossessionEpisode:
    decedent = opened.body_id.value
    item_ids = tuple(item.value for item in opened.item_ids)
    holders = {item_id: _CORPSE for item_id in item_ids}
    claims: list[_Claim] = []
    takes: list[_Take] = []
    voluntary = False
    for event in events:
        details = event.details
        if (
            type(details) is PossessionClaimAsserted
            and details.decedent_id.value == decedent
        ):
            actor = "" if event.actor_id is None else event.actor_id.value
            claims.append(
                _Claim(
                    event.tick,
                    event.sequence,
                    actor,
                    details.doctrine,
                    None if details.item_id is None else details.item_id.value,
                )
            )
        elif (
            type(details) is TakenFromCorpse
            and details.source_body_id.value == decedent
            and details.item_id.value in holders
        ):
            holder = details.resulting_holder_id.value
            holders[details.item_id.value] = holder
            actor = "" if event.actor_id is None else event.actor_id.value
            takes.append(
                _Take(event.tick, event.sequence, actor, details.item_id.value)
            )
        elif type(details) is Given and details.item_id.value in holders:
            recipient = (
                details.resulting_holder_id.value
                if details.resulting_holder_id is not None
                else details.recipient_id.value
            )
            holders[details.item_id.value] = recipient
            voluntary = True
    first_take = None
    if takes:
        first_take = min(takes, key=lambda take: (take.tick, take.sequence))
    earliest = _earliest_claimant(claims)
    taker = None if first_take is None else first_take.actor
    alignment = tuple(
        (
            doctrine,
            _alignment(
                doctrine,
                taker,
                decedent,
                earliest,
                children_of,
                caregivers_of,
                co_members_of,
            ),
        )
        for doctrine in _DOCTRINES
    )
    status = dict(alignment)
    appropriated = False
    for take in takes:
        latest = _latest_doctrine(claims, take.actor, take.tick, take.sequence)
        if latest is None or status.get(latest) != "aligned":
            appropriated = True
    return PossessionEpisode(
        decedent_id=decedent,
        location_id=opened.location_id.value,
        opened_tick=opened_tick,
        physical_possession=tuple(sorted(holders.items())),
        legitimacy_claims=tuple(
            (claim.actor, claim.doctrine, claim.item_id) for claim in claims
        ),
        conflict=_conflict(claims, first_take, item_ids),
        appropriation=appropriated,
        voluntary_transfer=voluntary,
        convention_token=_convention(ledgers, opened.location_id.value),
        alignment=alignment,
    )


@dataclass(frozen=True, slots=True)
class _Claim:
    tick: int
    sequence: int
    actor: str
    doctrine: str
    item_id: str | None


@dataclass(frozen=True, slots=True)
class _Take:
    tick: int
    sequence: int
    actor: str
    item_id: str


def _conflict(
    claims: Sequence[_Claim],
    first_take: _Take | None,
    item_ids: tuple[str, ...],
) -> bool:
    if first_take is None:
        return _diverse(claims)
    pre = [
        claim
        for claim in claims
        if (claim.tick, claim.sequence) < (first_take.tick, first_take.sequence)
    ]
    if _diverse(pre):
        return True
    post = [
        claim
        for claim in claims
        if (claim.tick, claim.sequence) >= (first_take.tick, first_take.sequence)
    ]
    groups: dict[str, list[_Claim]] = {item_id: [] for item_id in item_ids}
    for claim in post:
        if claim.item_id is None:
            for bucket in groups.values():
                bucket.append(claim)
        elif claim.item_id in groups:
            groups[claim.item_id].append(claim)
    return any(_diverse(bucket) for bucket in groups.values())


def _diverse(claims: Sequence[_Claim]) -> bool:
    claimants = {claim.actor for claim in claims}
    doctrines = {claim.doctrine for claim in claims}
    return len(claimants) > 1 or len(doctrines) > 1


def _earliest_claimant(claims: Sequence[_Claim]) -> str | None:
    if not claims:
        return None
    first = min(claims, key=lambda claim: (claim.tick, claim.sequence))
    return first.actor


def _latest_doctrine(
    claims: Sequence[_Claim], actor: str, tick: int, sequence: int
) -> str | None:
    prior = [
        claim
        for claim in claims
        if claim.actor == actor and (claim.tick, claim.sequence) <= (tick, sequence)
    ]
    if not prior:
        return None
    return max(prior, key=lambda claim: (claim.tick, claim.sequence)).doctrine


def _alignment(
    doctrine: str,
    taker: str | None,
    decedent: str,
    earliest: str | None,
    children_of: Mapping[str, frozenset[str]] | None,
    caregivers_of: Mapping[str, frozenset[str]] | None,
    co_members_of: Mapping[str, frozenset[str]] | None,
) -> str:
    if taker is None:
        return "not_applicable"
    if doctrine == "nobody_owns":
        return "aligned"
    if doctrine == "first_claimant_owns":
        if earliest is None:
            return "unaligned"
        return "aligned" if taker == earliest else "unaligned"
    if doctrine == "children_should_inherit":
        return _member_status(children_of, decedent, taker)
    if doctrine == "caregiver_inherits":
        return _member_status(caregivers_of, decedent, taker)
    if doctrine == "group_owns":
        if co_members_of is None:
            return "not_applicable"
        members = co_members_of.get(decedent)
        if members is None:
            return "not_applicable"
        return "aligned" if taker in members and decedent in members else "unaligned"
    return "not_applicable"


def _member_status(
    graph: Mapping[str, frozenset[str]] | None, decedent: str, taker: str
) -> str:
    if graph is None:
        return "not_applicable"
    members = graph.get(decedent)
    if members is None:
        return "not_applicable"
    return "aligned" if taker in members else "unaligned"


def _convention(
    ledgers: Sequence[PossessionLedgerSnapshot], location_id: str
) -> str:
    totals: dict[str, int] = {}
    for ledger in ledgers:
        if type(ledger) is not PossessionLedgerSnapshot:
            raise TypeError("ledgers entries must be PossessionLedgerSnapshot")
        if not ledger.alive or ledger.location_id != location_id:
            continue
        for doctrine, count in ledger.supports:
            totals[doctrine] = totals.get(doctrine, 0) + count
    if not totals:
        return "unformed"
    top = max(totals.values())
    winners = sorted(doctrine for doctrine, count in totals.items() if count == top)
    if len(winners) != 1:
        return "contested"
    return winners[0]
