"""Owner-scoped beliefs about who should hold a decedent's items.

The ledger is not an inheritance law and is not on Observation. Support
counts, claims, and sanctions never move items.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from agents.models import AgentId
from world.actions import AssertPossessionClaim, Take
from world.identifiers import EntityId, require_exact_nonneg_int
from world.models import LifeStatus
from world.observations import Observation, ObservedItemPlacement
from world.possession_succession import POSSESSION_DOCTRINES

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.possession_legitimacy"
)

POSSESSION_SUPPORT_CAP: Final[int] = 32
POSSESSION_SANCTION_TOKENS: Final[frozenset[str]] = frozenset(
    {"none", "criticism", "shun", "retaliation_considered"}
)


@dataclass(frozen=True, slots=True)
class PossessionClaimNote:
    """A claim this owner made or witnessed. Not an engine resolution."""

    tick: int
    decedent_id: EntityId
    claimant_id: EntityId
    doctrine: str
    item_id: EntityId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("PossessionClaimNote.tick", self.tick),
        )
        for name in ("decedent_id", "claimant_id"):
            if type(getattr(self, name)) is not EntityId:
                raise TypeError(f"PossessionClaimNote.{name} must be EntityId")
        if self.doctrine not in POSSESSION_DOCTRINES:
            raise ValueError("PossessionClaimNote.doctrine")
        if self.item_id is not None and type(self.item_id) is not EntityId:
            raise TypeError("PossessionClaimNote.item_id must be EntityId or None")


@dataclass(frozen=True, slots=True)
class PossessionSanctionNote:
    """Subjective reaction. Writing a token does not enqueue Attack."""

    tick: int
    decedent_id: EntityId
    target_id: EntityId
    token: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("PossessionSanctionNote.tick", self.tick),
        )
        for name in ("decedent_id", "target_id"):
            if type(getattr(self, name)) is not EntityId:
                raise TypeError(f"PossessionSanctionNote.{name} must be EntityId")
        if self.token not in POSSESSION_SANCTION_TOKENS:
            raise ValueError("PossessionSanctionNote.token")


@dataclass(frozen=True, slots=True)
class PossessionLegitimacyLedger:
    """One owner's doctrines, claims, and sanctions."""

    owner_id: AgentId
    supports: tuple[tuple[str, int], ...] = ()
    claims: tuple[PossessionClaimNote, ...] = ()
    sanctions: tuple[PossessionSanctionNote, ...] = ()
    witnessed_take_decedents: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("PossessionLegitimacyLedger.owner_id must be AgentId")
        if isinstance(self.supports, (str, bytes)) or not isinstance(
            self.supports, tuple
        ):
            raise TypeError("supports must be a tuple")
        seen: set[str] = set()
        for pair in self.supports:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise TypeError("supports entries must be (doctrine, count)")
            doctrine, count = pair
            if doctrine not in POSSESSION_DOCTRINES or doctrine in seen:
                raise ValueError("PossessionLegitimacyLedger.supports")
            if type(count) is not int or not 1 <= count <= POSSESSION_SUPPORT_CAP:
                raise ValueError("PossessionLegitimacyLedger.supports")
            seen.add(doctrine)
        ordered = tuple(sorted(self.supports))
        if ordered != self.supports:
            object.__setattr__(self, "supports", ordered)
        if isinstance(self.claims, (str, bytes)) or not isinstance(self.claims, tuple):
            raise TypeError("claims must be a tuple")
        for note in self.claims:
            if type(note) is not PossessionClaimNote:
                raise TypeError("claims entries must be PossessionClaimNote")
        if isinstance(self.sanctions, (str, bytes)) or not isinstance(
            self.sanctions, tuple
        ):
            raise TypeError("sanctions must be a tuple")
        for note in self.sanctions:
            if type(note) is not PossessionSanctionNote:
                raise TypeError("sanctions entries must be PossessionSanctionNote")
        if isinstance(self.witnessed_take_decedents, (str, bytes)) or not isinstance(
            self.witnessed_take_decedents, tuple
        ):
            raise TypeError("witnessed_take_decedents must be a tuple")
        taken = tuple(sorted(self.witnessed_take_decedents))
        if len(set(taken)) != len(taken):
            raise ValueError("witnessed_take_decedents must be unique")
        for item in taken:
            if type(item) is not str or item == "":
                raise TypeError("witnessed_take_decedents entries must be str")
        if taken != self.witnessed_take_decedents:
            object.__setattr__(self, "witnessed_take_decedents", taken)

    def support_count(self, doctrine: str) -> int:
        for token, count in self.supports:
            if token == doctrine:
                return count
        return 0


def empty_possession_legitimacy(owner_id: AgentId) -> PossessionLegitimacyLedger:
    """Blank owner ledger. Does not copy another owner's doctrines."""
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    return PossessionLegitimacyLedger(owner_id)


def note_doctrine_support(
    ledger: PossessionLegitimacyLedger, doctrine: str
) -> PossessionLegitimacyLedger:
    """Increment one adopted doctrine, capped at 32."""
    if type(ledger) is not PossessionLegitimacyLedger:
        raise TypeError("ledger must be PossessionLegitimacyLedger")
    if doctrine not in POSSESSION_DOCTRINES:
        raise ValueError("doctrine")
    counts = dict(ledger.supports)
    updated = min(counts.get(doctrine, 0) + 1, POSSESSION_SUPPORT_CAP)
    counts[doctrine] = updated
    _LOG.debug(
        "possession_ledger_updated owner_id=%s doctrine=%s count=%s",
        ledger.owner_id.value,
        doctrine,
        updated,
    )
    return _copy_ledger(ledger, supports=tuple(counts.items()))


def append_possession_claim(
    ledger: PossessionLegitimacyLedger, note: PossessionClaimNote
) -> PossessionLegitimacyLedger:
    if type(ledger) is not PossessionLegitimacyLedger:
        raise TypeError("ledger must be PossessionLegitimacyLedger")
    if type(note) is not PossessionClaimNote:
        raise TypeError("note must be PossessionClaimNote")
    return _copy_ledger(ledger, claims=(*ledger.claims, note))


def append_possession_sanction(
    ledger: PossessionLegitimacyLedger, note: PossessionSanctionNote
) -> PossessionLegitimacyLedger:
    """Store a sanction token. Does not submit Attack."""
    if type(ledger) is not PossessionLegitimacyLedger:
        raise TypeError("ledger must be PossessionLegitimacyLedger")
    if type(note) is not PossessionSanctionNote:
        raise TypeError("note must be PossessionSanctionNote")
    return _copy_ledger(ledger, sanctions=(*ledger.sanctions, note))


def _copy_ledger(
    ledger: PossessionLegitimacyLedger, **changes: object
) -> PossessionLegitimacyLedger:
    return PossessionLegitimacyLedger(
        ledger.owner_id,
        supports=changes.get("supports", ledger.supports),  # type: ignore[arg-type]
        claims=changes.get("claims", ledger.claims),  # type: ignore[arg-type]
        sanctions=changes.get("sanctions", ledger.sanctions),  # type: ignore[arg-type]
        witnessed_take_decedents=changes.get(  # type: ignore[arg-type]
            "witnessed_take_decedents", ledger.witnessed_take_decedents
        ),
    )


def require_owner_possession_legitimacy(
    value: object | None,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    if value is None:
        return
    if type(value) is not PossessionLegitimacyLedger:
        raise TypeError(f"{field_name} must be PossessionLegitimacyLedger or None")
    if value.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


def ledgers_by_owner(
    ledgers: Mapping[AgentId, PossessionLegitimacyLedger],
) -> dict[str, PossessionLegitimacyLedger]:
    """Detach ledgers keyed by owner id string. Rejects a foreign owner id."""
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Mapping):
        raise TypeError("ledgers must be a mapping")
    copied: dict[str, PossessionLegitimacyLedger] = {}
    for owner_id, ledger in ledgers.items():
        if (
            type(owner_id) is not AgentId
            or type(ledger) is not PossessionLegitimacyLedger
        ):
            raise TypeError("ledgers must map AgentId to PossessionLegitimacyLedger")
        if ledger.owner_id != owner_id:
            raise ValueError("possession_legitimacy owner_id mismatch")
        copied[owner_id.value] = ledger
    return copied


@dataclass(frozen=True, slots=True)
class PossessionAlignmentContext:
    """Optional graphs the owner may already have. Absent channels are skipped."""

    kinship_on: bool = False
    children_of: Mapping[str, tuple[str, ...]] | None = None
    care_on: bool = False
    caregivers_of: Mapping[str, tuple[str, ...]] | None = None
    groups_on: bool = False
    co_members_of: Mapping[str, tuple[str, ...]] | None = None

    def __post_init__(self) -> None:
        for name in ("kinship_on", "care_on", "groups_on"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"PossessionAlignmentContext.{name} must be bool")


def apply_possession_legitimacy_update(
    observation: object,
    previous: PossessionLegitimacyLedger | None,
    *,
    owner_id: AgentId,
    alignment: PossessionAlignmentContext | None = None,
) -> PossessionLegitimacyLedger:
    """Update one owner's ledger from that owner's observation only.

    Does not read another ledger and does not emit ``Attack``.
    """
    from world.observations import Observation

    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if previous is not None and type(previous) is not PossessionLegitimacyLedger:
        raise TypeError("previous must be PossessionLegitimacyLedger or None")
    if previous is not None and previous.owner_id != owner_id:
        raise ValueError("previous owner_id mismatch")
    if alignment is not None and type(alignment) is not PossessionAlignmentContext:
        raise TypeError("alignment must be PossessionAlignmentContext or None")
    ledger = (
        empty_possession_legitimacy(owner_id) if previous is None else previous
    )
    seen_items: set[str] = set()
    for occurrence in observation.occurrences:
        kind = occurrence.kind
        facts = occurrence.public_facts
        if kind == "possession_claim_asserted":
            ledger = _apply_claim(ledger, observation, occurrence, facts)
        elif kind == "taken_from_corpse":
            ledger = _apply_take(ledger, observation, occurrence, facts, alignment)
            for item_id in _fact_ids(facts, "item_ids"):
                seen_items.add(item_id)
        elif kind == "given":
            _note_given(facts, occurrence, seen_items)
    return ledger


def _apply_claim(ledger, observation, occurrence, facts):
    doctrine = facts.get("doctrine")
    if type(doctrine) is not str or doctrine not in POSSESSION_DOCTRINES:
        return ledger
    decedent = _one_id(facts.get("decedent_id"))
    claimant = occurrence.actor_id
    if decedent is None or claimant is None:
        return ledger
    item_ids = _fact_ids(facts, "item_ids")
    item_id = None if not item_ids else EntityId(item_ids[0])
    ledger = append_possession_claim(
        ledger,
        PossessionClaimNote(
            observation.tick, decedent, claimant, doctrine, item_id
        ),
    )
    ledger = note_doctrine_support(ledger, doctrine)
    _LOG.debug("possession_support doctrine=%s", doctrine)
    return ledger


def _apply_take(ledger, observation, occurrence, facts, alignment):
    decedent = _one_id(facts.get("decedent_id"))
    taker = occurrence.actor_id
    if decedent is None or taker is None:
        return ledger
    decedent_key = decedent.value
    if decedent_key not in ledger.witnessed_take_decedents:
        ledger = note_doctrine_support(ledger, "first_claimant_owns")
        _LOG.debug("possession_support doctrine=%s", "first_claimant_owns")
        ledger = _copy_ledger(
            ledger,
            witnessed_take_decedents=(
                *ledger.witnessed_take_decedents,
                decedent_key,
            ),
        )
    doctrine = _highest_doctrine(ledger)
    if doctrine is None or doctrine == "nobody_owns":
        return ledger
    aligned = _take_aligned(doctrine, taker.value, decedent_key, ledger, alignment)
    if aligned is None or aligned:
        return ledger
    ledger = append_possession_sanction(
        ledger,
        PossessionSanctionNote(
            observation.tick, decedent, taker, "criticism"
        ),
    )
    _LOG.debug("possession_sanction token=%s", "criticism")
    _LOG.info("possession_sanction token=%s", "criticism")
    return ledger


def _note_given(facts, occurrence, seen_items: set[str]) -> None:
    item_id = facts.get("target_id")
    if type(item_id) is not str and occurrence.other_entity_id is not None:
        item_id = occurrence.other_entity_id.value
    if type(item_id) is str and item_id in seen_items:
        _LOG.debug("possession_given item_known=%s", "yes")


def _take_aligned(doctrine, taker_id, decedent_id, ledger, alignment):
    if doctrine == "first_claimant_owns":
        claimants = [
            note.claimant_id.value
            for note in ledger.claims
            if note.decedent_id.value == decedent_id
        ]
        if not claimants:
            return False
        return taker_id == claimants[0]
    if alignment is None:
        _LOG.debug("possession_alignment_skipped channel=%s", doctrine)
        return None
    if doctrine == "children_should_inherit":
        if not alignment.kinship_on:
            _LOG.debug("possession_alignment_skipped channel=%s", "kinship")
            return None
        children = (alignment.children_of or {}).get(decedent_id)
        if children is None:
            return None
        return taker_id in children
    if doctrine == "caregiver_inherits":
        if not alignment.care_on:
            _LOG.debug("possession_alignment_skipped channel=%s", "care")
            return None
        caregivers = (alignment.caregivers_of or {}).get(decedent_id)
        if caregivers is None:
            return None
        return taker_id in caregivers
    if doctrine == "group_owns":
        if not alignment.groups_on:
            _LOG.debug("possession_alignment_skipped channel=%s", "groups")
            return None
        members = (alignment.co_members_of or {}).get(decedent_id)
        if members is None:
            return None
        return taker_id in members and decedent_id in members
    return None


def _highest_doctrine(ledger: PossessionLegitimacyLedger) -> str | None:
    if not ledger.supports:
        return None
    top = max(count for _doctrine, count in ledger.supports)
    winners = sorted(
        doctrine for doctrine, count in ledger.supports if count == top
    )
    if len(winners) != 1:
        _LOG.debug("possession_support doctrine=%s", "tie")
        return None
    return winners[0]


def _fact_ids(facts, key: str) -> tuple[str, ...]:
    raw = facts.get(key)
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
        return ()
    return tuple(item for item in raw if type(item) is str)


def _one_id(value: object) -> EntityId | None:
    if type(value) is not str or value == "":
        return None
    return EntityId(value)


def propose_possession_command(
    observation: Observation,
    ledger: PossessionLegitimacyLedger | None = None,
    *,
    channel_on: bool,
    owner_id: AgentId | None = None,
) -> Take | AssertPossessionClaim | None:
    """Pick a corpse Take or a doctrine claim from this owner's ledger.

    Channel off returns None so command ranking stays unchanged. The
    choice uses only this owner's support counts and the observation.
    """
    if type(channel_on) is not bool:
        raise TypeError("channel_on must be bool")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if not channel_on:
        return None
    if ledger is not None and type(ledger) is not PossessionLegitimacyLedger:
        raise TypeError("ledger must be PossessionLegitimacyLedger or None")
    if owner_id is not None and type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId or None")
    if (
        ledger is not None
        and owner_id is not None
        and ledger.owner_id != owner_id
    ):
        ledger = None
    items = sorted(
        (
            item
            for item in observation.items
            if item.placement is ObservedItemPlacement.CORPSE_HERE
        ),
        key=lambda item: item.entity_id.value,
    )
    if not items:
        return None
    item_id = items[0].entity_id
    doctrine = None if ledger is None else _highest_doctrine(ledger)
    decedent_id = _dead_decedent(observation)
    if doctrine is not None and decedent_id is not None:
        command: Take | AssertPossessionClaim = AssertPossessionClaim(
            decedent_id, doctrine, item_id
        )
        tag = "assert_possession_claim"
        token = doctrine
    elif observation.tick % 2 == 0 or decedent_id is None:
        command = Take(item_id)
        tag = "take"
        token = "take"
    else:
        command = AssertPossessionClaim(decedent_id, "nobody_owns", item_id)
        tag = "assert_possession_claim"
        token = "nobody_owns"
    _LOG.debug("possession_proposal command=%s doctrine=%s", tag, token)
    _LOG.info("possession_proposal selected command=%s", tag)
    return command


def apply_possession_proposal(
    command: object,
    observation: Observation,
    ledger: object | None,
    *,
    channel_on: bool,
    owner_id: AgentId | None = None,
) -> object:
    """Replace a compiled command only when the channel proposes one."""
    if not channel_on:
        return command
    if ledger is not None and type(ledger) is not PossessionLegitimacyLedger:
        raise TypeError("ledger must be PossessionLegitimacyLedger or None")
    proposed = propose_possession_command(
        observation,
        ledger,
        channel_on=True,
        owner_id=owner_id,
    )
    if proposed is None:
        return command
    return proposed


def _dead_decedent(observation: Observation) -> EntityId | None:
    dead = sorted(
        (
            body.entity_id
            for body in observation.visible_bodies
            if body.life_status is LifeStatus.DEAD
        ),
        key=lambda entity_id: entity_id.value,
    )
    if not dead:
        return None
    return dead[0]
