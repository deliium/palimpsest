"""Completed-run objective evidence projected into a macro-society harvest.

The bridge is read-only and analysis-facing: it reads already-committed
``WorldEvent`` values, keeps only the four edge lanes that objective events can
support, and reports every other lane as absent. Absence is data; a missing
institution, culture, self-identification, or collective-decision lane is never
coerced into "no society".
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.macro_society_contract import (
    MAX_EVIDENCE_WINDOWS,
    MacroSocietyError,
)
from analysis.macro_society_evidence import (
    MacroSocietyEdge,
    MacroSocietyWindowEvidence,
    edges_from_communication,
    edges_from_exchanges,
    edges_from_interaction,
    edges_from_journeys,
)
from experiments.macro_society_publication import MacroSocietyHarvest

__all__ = ["DEFAULT_WINDOW_TICKS", "build_completed_run_harvest"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.macro_society_completed_run"
)

DEFAULT_WINDOW_TICKS: Final[int] = 100

_SPEECH_KINDS: Final[frozenset[str]] = frozenset({"talk", "ask", "tell"})
_INTERACTION_KINDS: Final[frozenset[str]] = frozenset(
    {"help", "feed", "transport", "attack"}
)
_EXCHANGE_KINDS: Final[frozenset[str]] = frozenset({"give"})
_JOURNEY_KINDS: Final[frozenset[str]] = frozenset({"journey_arrived"})


@dataclass(frozen=True, slots=True)
class _SpeechRow:
    speaker_id: str
    listener_id: str
    action_kind: str
    tick: int


@dataclass(frozen=True, slots=True)
class _InteractionRow:
    actor_id: str
    target_id: str
    tick: int


@dataclass(frozen=True, slots=True)
class _ExchangeRow:
    from_owner_id: str
    to_owner_id: str
    tick: int


@dataclass(frozen=True, slots=True)
class _JourneyRow:
    person_id: str
    origin_region_id: str
    destination_region_id: str
    tick: int


def _identity(value: object) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) and raw else None


def _tick(value: object) -> int | None:
    raw = getattr(value, "value", value)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return None
    return raw


def _window_size(events: Sequence[object], requested: int) -> int:
    if requested < 1:
        raise MacroSocietyError("macro_society_invalid_window")
    max_tick = 0
    for event in events:
        tick = _tick(getattr(event, "tick", None))
        if tick is not None and tick > max_tick:
            max_tick = tick
    minimum = max(1, math.ceil((max_tick + 1) / MAX_EVIDENCE_WINDOWS))
    return max(requested, minimum)


def _bucket_rows(
    events: Iterable[object], *, window_ticks: int
) -> dict[int, dict[str, list[object]]]:
    buckets: dict[int, dict[str, list[object]]] = {}
    for event in events:
        details = getattr(event, "details", None)
        kind = getattr(details, "kind", None)
        tick = _tick(getattr(event, "tick", None))
        actor = _identity(getattr(event, "actor_id", None))
        if tick is None or not isinstance(kind, str):
            continue
        bucket = tick // window_ticks
        lanes = buckets.setdefault(bucket, {})
        if kind in _SPEECH_KINDS and actor is not None:
            listener = _identity(getattr(details, "recipient_id", None))
            if listener is None:
                continue
            lanes.setdefault("communication", []).append(
                _SpeechRow(
                    speaker_id=actor,
                    listener_id=listener,
                    action_kind=kind,
                    tick=tick,
                )
            )
        elif kind in _INTERACTION_KINDS and actor is not None:
            target = _identity(getattr(details, "target_id", None))
            if target is None:
                continue
            lanes.setdefault("interaction", []).append(
                _InteractionRow(actor_id=actor, target_id=target, tick=tick)
            )
        elif kind in _EXCHANGE_KINDS and actor is not None:
            recipient = _identity(getattr(details, "recipient_id", None))
            if recipient is None:
                continue
            lanes.setdefault("exchange", []).append(
                _ExchangeRow(
                    from_owner_id=actor, to_owner_id=recipient, tick=tick
                )
            )
        elif kind in _JOURNEY_KINDS:
            origin = _identity(getattr(details, "origin_location_id", None))
            destination = _identity(
                getattr(details, "destination_location_id", None)
            )
            if origin is None or destination is None:
                continue
            participants = getattr(details, "participant_body_ids", ()) or ()
            for participant in participants:
                person = _identity(participant)
                if person is None:
                    continue
                lanes.setdefault("migration", []).append(
                    _JourneyRow(
                        person_id=person,
                        origin_region_id=origin,
                        destination_region_id=destination,
                        tick=tick,
                    )
                )
    return buckets


def _window_edges(lanes: dict[str, list[object]]) -> tuple[MacroSocietyEdge, ...]:
    edges: list[MacroSocietyEdge] = []
    edges.extend(edges_from_communication(lanes.get("communication", ())))
    edges.extend(edges_from_interaction(lanes.get("interaction", ())))
    edges.extend(edges_from_exchanges(lanes.get("exchange", ())))
    edges.extend(edges_from_journeys(lanes.get("migration", ())))
    return tuple(edges)


def build_completed_run_harvest(
    *,
    run_id: str,
    input_revision: str,
    events: Sequence[object],
    generated_tick: int,
    window_ticks: int = DEFAULT_WINDOW_TICKS,
) -> MacroSocietyHarvest:
    """Project committed objective events into a bounded harvest.

    Only communication, interaction, exchange, and migration edges are derived.
    The remaining five lanes stay absent and are reported through
    ``lane_presence`` rather than inferred.
    """
    size = _window_size(events, window_ticks)
    buckets = _bucket_rows(events, window_ticks=size)
    windows: list[MacroSocietyWindowEvidence] = []
    for index, bucket in enumerate(sorted(buckets)):
        edges = _window_edges(buckets[bucket])
        if not edges:
            continue
        persons = sorted(
            {
                person
                for edge in edges
                for person in (edge.source_person_id, edge.target_person_id)
            }
        )
        windows.append(
            MacroSocietyWindowEvidence(
                window_index=index,
                tick_start=bucket * size,
                tick_end=bucket * size + size - 1,
                person_ids=tuple(persons),
                edges=edges,
            )
        )
    if not windows:
        raise MacroSocietyError("macro_society_empty_window")
    # Window indexes must be dense after empty buckets are dropped.
    normalized = tuple(
        MacroSocietyWindowEvidence(
            window_index=position,
            tick_start=window.tick_start,
            tick_end=window.tick_end,
            person_ids=window.person_ids,
            edges=window.edges,
        )
        for position, window in enumerate(windows)
    )
    _LOG.debug(
        "macro_society_completed_run run=%s windows=%s window_ticks=%s",
        run_id,
        len(normalized),
        size,
    )
    return MacroSocietyHarvest(
        run_id=run_id,
        input_revision=input_revision,
        windows=normalized,
        generated_tick=generated_tick,
    )
