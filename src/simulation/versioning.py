"""Reserved V4 write pairs: metadata only, never runtime selection.

V4-01 publishes which future objective contexts may need a new event/codec pair.
A reservation is a number, not semantics: a later plan must still land
effect-complete details, replay, and persistence proof before writing it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, NoReturn

from simulation.compatibility import V4_CAPABILITY_FLAG_NAMES
from simulation.v4_architecture import (
    V4_ANALYSIS_ONLY_CONTEXTS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
)
from world.events import EVENT_SCHEMA_REPLAY_V22

V4_VERSION_RESERVATION_SCHEMA: Final[str] = "v4-write-pair-reservations-v1"


@dataclass(frozen=True, slots=True)
class WritePairReservation:
    """One future objective write pair; no encoding or runtime path reads it."""

    context_id: V4ContextId
    event_schema: int
    codec_version: str
    prerequisite_flags: tuple[str, ...]
    owner_package: str
    reason: str


V4_WRITE_PAIR_RESERVATIONS: Final[tuple[WritePairReservation, ...]] = (
    WritePairReservation(
        context_id=V4ContextId.INFRASTRUCTURE_NETWORKS,
        event_schema=23,
        codec_version="v21",
        prerequisite_flags=("infrastructure_networks", "supply_chains"),
        owner_package="world",
        reason=(
            "physical network topology, capacity, and condition need "
            "effect-complete replay"
        ),
    ),
    WritePairReservation(
        context_id=V4ContextId.EPIDEMICS,
        event_schema=24,
        codec_version="v22",
        prerequisite_flags=("epidemics",),
        owner_package="world",
        reason="host/transmission state changes must replay",
    ),
    WritePairReservation(
        context_id=V4ContextId.ECOLOGICAL_FEEDBACK,
        event_schema=25,
        codec_version="v23",
        prerequisite_flags=("ecological_feedback",),
        owner_package="world",
        reason="regeneration and depletion coupling must replay",
    ),
    WritePairReservation(
        context_id=V4ContextId.DISASTERS,
        event_schema=26,
        codec_version="v24",
        prerequisite_flags=("disasters",),
        owner_package="world",
        reason="multi-location hazard onset/effect must replay",
    ),
)

V4_EVENT_REUSING_CONTEXTS: Final[frozenset[V4ContextId]] = frozenset(
    {
        V4ContextId.ORGANIZATIONS,
        V4ContextId.FORMAL_RULES,
        V4ContextId.LEGAL_DISPUTES,
        V4ContextId.DIPLOMACY,
        V4ContextId.ORGANIZED_CONFLICT,
        V4ContextId.SUPPLY_CHAINS,
        V4ContextId.MARKETS_CREDIT,
        V4ContextId.SCIENCE,
        V4ContextId.SOCIETAL_RESILIENCE,
        V4ContextId.MACRO_SOCIETY_IDENTITY,
    }
)

_RESERVED_OWNER_PACKAGES: Final[frozenset[str]] = frozenset({"world", "simulation"})
_KNOWN_FLAGS: Final[frozenset[str]] = frozenset(V4_CAPABILITY_FLAG_NAMES)


def _fail(code: str) -> NoReturn:
    raise ValueError(code)


def _codec_number(version: str) -> int:
    return int(version.removeprefix("v"))


def validate_write_pair_reservations(
    reservations: Sequence[WritePairReservation] = V4_WRITE_PAIR_RESERVATIONS,
    *,
    reusing_contexts: frozenset[V4ContextId] = V4_EVENT_REUSING_CONTEXTS,
) -> None:
    """Validate reservations and context coverage with stable error codes."""
    events = [reservation.event_schema for reservation in reservations]
    if len(set(events)) != len(events):
        _fail("v4_pair_duplicate_event")
    codecs = [reservation.codec_version for reservation in reservations]
    if len(set(codecs)) != len(codecs):
        _fail("v4_pair_duplicate_codec")

    expected_events = list(
        range(
            EVENT_SCHEMA_REPLAY_V22 + 1, EVENT_SCHEMA_REPLAY_V22 + 1 + len(reservations)
        )
    )
    if events != expected_events:
        _fail("v4_pair_noncontiguous_event")

    expected_codecs = [f"v{index}" for index in range(21, 21 + len(reservations))]
    if codecs != expected_codecs:
        _fail("v4_pair_noncontiguous_codec")

    reservation_contexts: set[V4ContextId] = set()
    for reservation in reservations:
        if reservation.context_id not in V4_CONTEXT_BY_ID:
            _fail("v4_pair_unknown_context")
        spec = V4_CONTEXT_BY_ID[reservation.context_id]
        if (
            reservation.context_id in V4_ANALYSIS_ONLY_CONTEXTS
            or spec.authority is V4Authority.DETACHED_ANALYSIS
            or spec.capability_flag is None
        ):
            _fail("v4_pair_analysis_context")
        if reservation.owner_package not in _RESERVED_OWNER_PACKAGES:
            _fail("v4_pair_unknown_context")
        if not set(reservation.prerequisite_flags) <= _KNOWN_FLAGS:
            _fail("v4_pair_unknown_flag")
        reservation_contexts.add(reservation.context_id)

    known_contexts = {spec.context_id for spec in V4_CONTEXTS}
    if not (reservation_contexts | reusing_contexts) == known_contexts:
        _fail("v4_pair_uncovered_context")
    if reservation_contexts & reusing_contexts:
        _fail("v4_pair_overlap")


def reservation_for_context(context_id: V4ContextId) -> WritePairReservation:
    """Return the reservation for ``context_id``; reusing contexts have none."""
    for reservation in V4_WRITE_PAIR_RESERVATIONS:
        if reservation.context_id == context_id:
            return reservation
    raise ValueError("v4_pair_unknown_context")


__all__ = [
    "V4_EVENT_REUSING_CONTEXTS",
    "V4_VERSION_RESERVATION_SCHEMA",
    "V4_WRITE_PAIR_RESERVATIONS",
    "WritePairReservation",
    "reservation_for_context",
    "validate_write_pair_reservations",
]
