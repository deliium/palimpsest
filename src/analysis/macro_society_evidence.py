"""Normalized detached evidence for macro-society detection.

Every adapter is a read-only projection over rows that already exist elsewhere
in the analysis layer. Adapters emit identifiers, weights, and opaque tokens
only: never utterances, labels, narratives, memories, or embeddings.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.macro_society_contract import (
    EDGE_LANES,
    MAX_EVIDENCE_WINDOWS,
    MAX_WINDOW_EDGES,
    MAX_WINDOW_PERSONS,
    TOKEN_LANES,
    MacroSocietyError,
    MacroSocietyLane,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MacroSocietyEdge",
    "MacroSocietyToken",
    "MacroSocietyWindowEvidence",
    "edges_from_communication",
    "edges_from_exchanges",
    "edges_from_interaction",
    "edges_from_journeys",
    "tokens_from_collective_decisions",
    "tokens_from_culture",
    "tokens_from_institutions",
    "tokens_from_residence",
    "tokens_from_self_identification",
    "tokens_from_territory",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.macro_society_evidence")

_SPEECH_KINDS: Final[frozenset[str]] = frozenset({"talk", "ask", "tell"})
_TERRITORY_KINDS: Final[frozenset[str]] = frozenset({"location", "region"})


def _stable(name: str, value: object, code: str) -> str:
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise MacroSocietyError(code) from exc


def _tick(row: object, *, default: int = 0) -> int:
    raw = getattr(row, "tick", getattr(row, "observation_tick", default))
    try:
        return require_exact_nonneg_int("tick", raw)
    except ValueError as exc:
        raise MacroSocietyError("macro_society_invalid_evidence_row") from exc


def _field(row: object, *names: str) -> str | None:
    for name in names:
        if isinstance(row, Mapping):
            value = row.get(name)
        else:
            value = getattr(row, name, None)
        if isinstance(value, str) and value:
            return value
    return None


def _required(row: object, *names: str) -> str:
    value = _field(row, *names)
    if value is None:
        raise MacroSocietyError("macro_society_invalid_evidence_row")
    return _stable(names[0], value, "macro_society_invalid_evidence_row")


def _sort_edges(edges: Iterable[MacroSocietyEdge]) -> tuple[MacroSocietyEdge, ...]:
    unique: dict[tuple[str, str, str, int, float], MacroSocietyEdge] = {}
    for edge in edges:
        key = (
            edge.lane.value,
            edge.source_person_id,
            edge.target_person_id,
            edge.tick,
            edge.weight,
        )
        unique.setdefault(key, edge)
    return tuple(unique[key] for key in sorted(unique))


def _sort_tokens(tokens: Iterable[MacroSocietyToken]) -> tuple[MacroSocietyToken, ...]:
    unique: dict[tuple[str, str, str], MacroSocietyToken] = {}
    for token in tokens:
        key = (token.lane.value, token.person_id, token.token_id)
        unique.setdefault(key, token)
    return tuple(unique[key] for key in sorted(unique))


@dataclass(frozen=True, slots=True)
class MacroSocietyEdge:
    """One undirected analytical edge in one evidence lane."""

    lane: MacroSocietyLane
    source_person_id: str
    target_person_id: str
    tick: int
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.lane, MacroSocietyLane) or self.lane not in EDGE_LANES:
            raise MacroSocietyError("macro_society_unknown_lane")
        source = _stable(
            "source_person_id",
            self.source_person_id,
            "macro_society_invalid_evidence_row",
        )
        target = _stable(
            "target_person_id",
            self.target_person_id,
            "macro_society_invalid_evidence_row",
        )
        if source == target:
            raise MacroSocietyError("macro_society_self_edge_rejected")
        tick = _tick(self)
        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)):
            raise MacroSocietyError("macro_society_invalid_weight")
        weight = float(self.weight)
        if not math.isfinite(weight) or weight <= 0.0:
            raise MacroSocietyError("macro_society_invalid_weight")
        object.__setattr__(self, "source_person_id", source)
        object.__setattr__(self, "target_person_id", target)
        object.__setattr__(self, "tick", tick)
        object.__setattr__(self, "weight", weight)


@dataclass(frozen=True, slots=True)
class MacroSocietyToken:
    """One opaque shared-token membership held by one person in one lane."""

    lane: MacroSocietyLane
    person_id: str
    token_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.lane, MacroSocietyLane) or self.lane not in TOKEN_LANES:
            raise MacroSocietyError("macro_society_unknown_lane")
        object.__setattr__(
            self,
            "person_id",
            _stable("person_id", self.person_id, "macro_society_invalid_evidence_row"),
        )
        object.__setattr__(
            self,
            "token_id",
            _stable("token_id", self.token_id, "macro_society_invalid_evidence_row"),
        )


@dataclass(frozen=True, slots=True)
class MacroSocietyWindowEvidence:
    """One normalized observation window over detached evidence."""

    window_index: int
    tick_start: int
    tick_end: int
    person_ids: tuple[str, ...]
    edges: tuple[MacroSocietyEdge, ...] = ()
    tokens: tuple[MacroSocietyToken, ...] = ()

    def __post_init__(self) -> None:
        index = require_exact_nonneg_int("window_index", self.window_index)
        if index >= MAX_EVIDENCE_WINDOWS:
            raise MacroSocietyError("macro_society_window_too_large")
        first = require_exact_nonneg_int("tick_start", self.tick_start)
        last = require_exact_nonneg_int("tick_end", self.tick_end)
        if last < first:
            raise MacroSocietyError("macro_society_invalid_window")

        persons: list[str] = []
        seen: set[str] = set()
        for raw in self.person_ids:
            person = _stable(
                "person_id", raw, "macro_society_invalid_evidence_row"
            )
            if person in seen:
                raise MacroSocietyError("macro_society_duplicate_member")
            seen.add(person)
            persons.append(person)
        if not persons:
            raise MacroSocietyError("macro_society_empty_window")
        if len(persons) > MAX_WINDOW_PERSONS:
            raise MacroSocietyError("macro_society_window_too_large")
        known = frozenset(persons)

        edges = tuple(self.edges)
        if len(edges) > MAX_WINDOW_EDGES:
            raise MacroSocietyError("macro_society_window_too_large")
        for edge in edges:
            if type(edge) is not MacroSocietyEdge:
                raise MacroSocietyError("macro_society_invalid_evidence_row")
            if (
                edge.source_person_id not in known
                or edge.target_person_id not in known
            ):
                raise MacroSocietyError("macro_society_unknown_person")

        tokens = tuple(self.tokens)
        for token in tokens:
            if type(token) is not MacroSocietyToken:
                raise MacroSocietyError("macro_society_invalid_evidence_row")
            if token.person_id not in known:
                raise MacroSocietyError("macro_society_unknown_person")

        object.__setattr__(self, "window_index", index)
        object.__setattr__(self, "tick_start", first)
        object.__setattr__(self, "tick_end", last)
        object.__setattr__(self, "person_ids", tuple(sorted(persons)))
        object.__setattr__(self, "edges", _sort_edges(edges))
        object.__setattr__(self, "tokens", _sort_tokens(tokens))

    @property
    def lane_presence(self) -> tuple[tuple[str, bool], ...]:
        """Which of the nine lanes contributed evidence in this window."""
        present = {edge.lane for edge in self.edges}
        present.update(token.lane for token in self.tokens)
        return tuple(
            sorted((lane.value, lane in present) for lane in MacroSocietyLane)
        )


def _edge(
    lane: MacroSocietyLane, source: str, target: str, tick: int, weight: float = 1.0
) -> MacroSocietyEdge | None:
    if source == target:
        return None
    return MacroSocietyEdge(
        lane=lane,
        source_person_id=source,
        target_person_id=target,
        tick=tick,
        weight=weight,
    )


def edges_from_communication(
    rows: Sequence[object] | None,
) -> tuple[MacroSocietyEdge, ...]:
    """Verified speech delivery edges (``talk``/``ask``/``tell``)."""
    edges: list[MacroSocietyEdge] = []
    for row in rows or ():
        kind = getattr(row, "action_kind", getattr(row, "kind", None))
        if isinstance(kind, str) and kind not in _SPEECH_KINDS:
            continue
        speaker = _required(row, "speaker_id", "source_person_id", "sender_id")
        listener = _required(row, "listener_id", "target_person_id", "recipient_id")
        edge = _edge(MacroSocietyLane.COMMUNICATION, speaker, listener, _tick(row))
        if edge is not None:
            edges.append(edge)
    result = _sort_edges(edges)
    _LOG.debug("macro_society_evidence lane=communication edges=%s", len(result))
    return result


def edges_from_interaction(
    rows: Sequence[object] | None,
) -> tuple[MacroSocietyEdge, ...]:
    """Applied-action edges between an actor and a target person."""
    edges: list[MacroSocietyEdge] = []
    for row in rows or ():
        actor = _required(row, "actor_id", "source_person_id", "agent_id")
        target = _required(row, "target_id", "target_person_id")
        edge = _edge(MacroSocietyLane.INTERACTION, actor, target, _tick(row))
        if edge is not None:
            edges.append(edge)
    result = _sort_edges(edges)
    _LOG.debug("macro_society_evidence lane=interaction edges=%s", len(result))
    return result


def edges_from_journeys(rows: Sequence[object] | None) -> tuple[MacroSocietyEdge, ...]:
    """Co-travel edges for persons sharing one origin/destination/tick."""
    grouped: dict[tuple[str, str, int], list[str]] = {}
    for row in rows or ():
        person = _required(row, "person_id", "owner_id")
        origin = _required(row, "origin_region_id", "origin_location_id")
        destination = _required(row, "destination_region_id", "destination_location_id")
        grouped.setdefault((origin, destination, _tick(row)), []).append(person)
    edges: list[MacroSocietyEdge] = []
    for (_, _, tick), persons in grouped.items():
        ordered = sorted(set(persons))
        for index, source in enumerate(ordered):
            for target in ordered[index + 1 :]:
                edge = _edge(MacroSocietyLane.MIGRATION, source, target, tick)
                if edge is not None:
                    edges.append(edge)
    result = _sort_edges(edges)
    _LOG.debug("macro_society_evidence lane=migration edges=%s", len(result))
    return result


def edges_from_exchanges(rows: Sequence[object] | None) -> tuple[MacroSocietyEdge, ...]:
    """Completed exchange edges between the two moving parties."""
    edges: list[MacroSocietyEdge] = []
    for row in rows or ():
        source = _field(row, "from_owner_id", "source_owner_id", "giver_id")
        target = _field(row, "to_owner_id", "target_owner_id", "receiver_id")
        if source is None or target is None:
            continue
        edge = _edge(
            MacroSocietyLane.EXCHANGE,
            _stable("from_owner_id", source, "macro_society_invalid_evidence_row"),
            _stable("to_owner_id", target, "macro_society_invalid_evidence_row"),
            _tick(row),
        )
        if edge is not None:
            edges.append(edge)
    result = _sort_edges(edges)
    _LOG.debug("macro_society_evidence lane=exchange edges=%s", len(result))
    return result


def _tokens(
    lane: MacroSocietyLane, pairs: Iterable[tuple[str, str]]
) -> tuple[MacroSocietyToken, ...]:
    tokens = [
        MacroSocietyToken(lane=lane, person_id=person, token_id=token)
        for person, token in pairs
    ]
    result = _sort_tokens(tokens)
    _LOG.debug("macro_society_evidence lane=%s tokens=%s", lane.value, len(result))
    return result


def tokens_from_institutions(
    rows: Sequence[object] | None,
) -> tuple[MacroSocietyToken, ...]:
    """Owner-local institution pattern tokens."""
    pairs: list[tuple[str, str]] = []
    for row in rows or ():
        owner = _required(row, "owner_id", "person_id")
        pattern = _required(row, "local_pattern_id", "concept_id", "pattern_id")
        pairs.append((owner, pattern))
    return _tokens(MacroSocietyLane.INSTITUTION, pairs)


def tokens_from_culture(
    rows: Sequence[object] | None,
) -> tuple[MacroSocietyToken, ...]:
    """Shared cultural-trait carriers, from carrier maps or flat rows."""
    pairs: list[tuple[str, str]] = []
    for row in rows or ():
        carriers = row.get("carriers") if isinstance(row, Mapping) else getattr(
            row, "carriers", None
        )
        if isinstance(carriers, Mapping):
            for trait_id, owners in carriers.items():
                trait = _stable(
                    "trait_id", trait_id, "macro_society_invalid_evidence_row"
                )
                for owner in owners:
                    pairs.append(
                        (
                            _stable(
                                "owner_id", owner, "macro_society_invalid_evidence_row"
                            ),
                            trait,
                        )
                    )
            continue
        owner = _required(row, "owner_id", "carrier_id", "person_id")
        trait = _required(row, "trait_id", "cluster_fingerprint", "local_entry_id")
        pairs.append((owner, trait))
    return _tokens(MacroSocietyLane.CULTURE, pairs)


def tokens_from_territory(
    rows: Sequence[object] | None,
) -> tuple[MacroSocietyToken, ...]:
    """Shared territory tokens from claims or residence rows."""
    pairs: list[tuple[str, str]] = []
    for row in rows or ():
        owner = _required(row, "owner_id", "person_id")
        kind = _field(row, "target_kind")
        if kind is not None and kind not in _TERRITORY_KINDS:
            continue
        target = _required(row, "target_entity_id", "region_id", "location_id")
        pairs.append((owner, target))
    return _tokens(MacroSocietyLane.TERRITORY, pairs)


def tokens_from_self_identification(
    rows: Sequence[object] | None,
) -> tuple[MacroSocietyToken, ...]:
    """Owner-scoped self-identified group tokens."""
    pairs: list[tuple[str, str]] = []
    for row in rows or ():
        owner = _required(row, "owner_id", "person_id")
        group = _required(row, "group_id", "basis_id")
        pairs.append((owner, group))
    return _tokens(MacroSocietyLane.SELF_IDENTIFICATION, pairs)


def tokens_from_collective_decisions(
    rows: Sequence[object] | None,
) -> tuple[MacroSocietyToken, ...]:
    """Co-participation tokens over an owner-scoped proposal reference."""
    pairs: list[tuple[str, str]] = []
    for row in rows or ():
        owner = _required(row, "owner_id", "person_id")
        proposal = _required(row, "proposal_ref", "case_ref")
        pairs.append((owner, proposal))
    return _tokens(MacroSocietyLane.COLLECTIVE_DECISION, pairs)


def tokens_from_residence(
    rows: Sequence[object] | None,
) -> tuple[MacroSocietyToken, ...]:
    """Residence tokens; the region identifier is namespaced explicitly."""
    pairs: list[tuple[str, str]] = []
    for row in rows or ():
        person = _required(row, "person_id", "owner_id")
        region = _required(row, "region_id", "residence_region_id")
        pairs.append((person, f"region:{region}"))
    return _tokens(MacroSocietyLane.TERRITORY, pairs)
