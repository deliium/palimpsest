# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Objective movement and integration-evidence rows from committed events.

This is the only objective layer of migration-displacement analysis. Rows are
token-only facts: who moved, from where to where, when, and how it ended. They
never carry a cause, an owner belief, a classification, or a wave identity.

The module reads committed ``WorldEvent`` values by duck typing on the public
``details.kind`` vocabulary. It never reads an observation, a ledger, a frame,
or a command, and it imports no cognition, runtime, API, persistence, or
observer module.

Tokens hash the same material as the owner export (``mdo-`` for a participant
and ``mdl-`` for a location) so objective rows join owner rows by equality. No
raw ``AgentId``, ``EntityId``, or location label appears in a row.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

__all__ = [
    "MIGRATION_INTEGRATION_DOMAINS",
    "MIGRATION_MOVEMENT_PREFIX",
    "MigrationArrivalStatus",
    "MigrationIntegrationEvidenceRow",
    "MigrationMovementKind",
    "MigrationMovementRow",
    "migration_agent_token",
    "migration_communication_pairs_from_events",
    "migration_integration_rows_from_events",
    "migration_kinship_pairs_from_events",
    "migration_location_token",
    "migration_movement_rows_from_events",
    "migration_movement_rows_with_coverage",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.migration_displacement.events"
)

MIGRATION_MOVEMENT_PREFIX: Final[str] = "mig-move-"
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_HEX_CHARS: Final[int] = 16
_MAX_GROUP: Final[int] = 8
_COVERAGES: Final[frozenset[str]] = frozenset({"complete", "partial", "missing"})

MIGRATION_INTEGRATION_DOMAINS: Final[tuple[str, ...]] = (
    "residence",
    "needs",
    "resource_access",
    "organization_participation",
    "institution_participation",
    "relationships",
    "conflict_status",
)


class MigrationMovementKind(StrEnum):
    """Closed relocation kind of one objective movement."""

    MOVE = "move"
    TRANSPORT = "transport"
    FLEE = "flee"
    JOURNEY = "journey"


class MigrationArrivalStatus(StrEnum):
    """Closed objective end state of one movement."""

    ARRIVED = "arrived"
    TIMEOUT = "timeout"
    DEAD = "dead"
    PENDING = "pending"
    UNKNOWN = "unknown"


def _check_token(field_name: str, value: object) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"migration_events: {field_name}")
    return value


def _check_tick(field_name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"migration_events: {field_name}")
    return value


@dataclass(frozen=True, slots=True)
class MigrationMovementRow:
    """One objective participant movement. No cause, owner, or classification."""

    participant_token: str
    origin_token: str
    destination_token: str
    route_tokens: tuple[str, ...]
    start_tick: int
    end_tick: int
    relocation_kind: str
    group_size: int
    arrival_status: str
    coverage: str

    def __post_init__(self) -> None:
        _check_token("participant_token", self.participant_token)
        _check_token("origin_token", self.origin_token)
        _check_token("destination_token", self.destination_token)
        if type(self.route_tokens) is not tuple:
            raise ValueError("migration_events: route_tokens")
        for token in self.route_tokens:
            _check_token("route_tokens", token)
        start = _check_tick("start_tick", self.start_tick)
        end = _check_tick("end_tick", self.end_tick)
        if end < start:
            raise ValueError("migration_events: end_tick")
        if self.relocation_kind not in {item.value for item in MigrationMovementKind}:
            raise ValueError("migration_events: relocation_kind")
        if (
            type(self.group_size) is not int
            or self.group_size < 1
            or self.group_size > _MAX_GROUP
        ):
            raise ValueError("migration_events: group_size")
        if self.arrival_status not in {item.value for item in MigrationArrivalStatus}:
            raise ValueError("migration_events: arrival_status")
        if self.coverage not in _COVERAGES:
            raise ValueError("migration_events: coverage")


@dataclass(frozen=True, slots=True)
class MigrationIntegrationEvidenceRow:
    """Counted committed evidence for one participant at one destination."""

    participant_token: str
    destination_token: str
    domain: str
    evidence_count: int
    first_tick: int
    last_tick: int
    coverage: str

    def __post_init__(self) -> None:
        _check_token("participant_token", self.participant_token)
        _check_token("destination_token", self.destination_token)
        if self.domain not in MIGRATION_INTEGRATION_DOMAINS:
            raise ValueError("migration_events: domain")
        if type(self.evidence_count) is not int or self.evidence_count < 1:
            raise ValueError("migration_events: evidence_count")
        first = _check_tick("first_tick", self.first_tick)
        last = _check_tick("last_tick", self.last_tick)
        if last < first:
            raise ValueError("migration_events: last_tick")
        if self.coverage not in _COVERAGES:
            raise ValueError("migration_events: coverage")


def _opaque(prefix: str, material: str) -> str:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:_HEX_CHARS]}"


def migration_agent_token(raw: str) -> str:
    """Opaque participant token; equals the owner-export owner token."""
    if type(raw) is not str or not raw:
        raise ValueError("migration_events: invalid_identifier")
    return _opaque("mdo-", f"agent|{raw}")


def migration_location_token(raw: str) -> str:
    """Opaque location token; equals the owner-export location token."""
    if type(raw) is not str or not raw:
        raise ValueError("migration_events: invalid_identifier")
    return _opaque("mdl-", f"location|{raw}")


def _text(value: object) -> str | None:
    if value is None:
        return None
    inner = getattr(value, "value", value)
    if type(inner) is not str or not inner:
        return None
    return inner


def _participants(value: object) -> tuple[str, ...] | None:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Sequence):
        return None
    out: list[str] = []
    for item in value:
        text = _text(item)
        if text is None:
            return None
        out.append(text)
    return tuple(out) if out else None


def _require_events(events: object) -> Sequence[object]:
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("events must be an ordered sequence")
    return events


def _require_ids(run_id: object, input_revision: object) -> None:
    _check_stable("run_id", run_id)
    _check_stable("input_revision", input_revision)


def _check_stable(field_name: str, value: object) -> None:
    if type(value) is not str or not value or len(value) > 128:
        raise ValueError(f"migration_events: {field_name}")


def _participant_token(raw: str, entity_to_agent: Mapping[str, str] | None) -> str:
    if entity_to_agent is not None and raw in entity_to_agent:
        return migration_agent_token(entity_to_agent[raw])
    return migration_agent_token(raw)


@dataclass(slots=True)
class _Pending:
    start_tick: int
    origin: str
    destination: str
    participants: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Draft:
    participant: str
    origin: str
    destination: str
    start_tick: int
    end_tick: int
    kind: str
    group: int
    status: str


def _event_fields(event: object) -> tuple[int, str, object] | None:
    tick = getattr(event, "tick", None)
    details = getattr(event, "details", None)
    kind = getattr(details, "kind", None)
    if type(tick) is not int or tick < 0 or type(kind) is not str:
        return None
    return tick, kind, details


def _scan_movements(
    events: Sequence[object],
) -> tuple[list[_Draft], int, int]:
    """Return completed/pending drafts, skipped-event count, and read count."""
    drafts: list[_Draft] = []
    pending: dict[str, _Pending] = {}
    deaths: dict[str, int] = {}
    skipped = 0
    read = 0

    def skip(reason: str) -> None:
        nonlocal skipped
        skipped += 1
        _LOG.warning("migration_movement_event_skipped reason_code=%s", reason)

    def add(
        participants: tuple[str, ...],
        origin: str,
        destination: str,
        start: int,
        end: int,
        kind: str,
        status: str,
    ) -> None:
        group = min(len(participants), _MAX_GROUP)
        for raw in participants:
            drafts.append(
                _Draft(raw, origin, destination, start, end, kind, group, status)
            )

    for event in events:
        parsed = _event_fields(event)
        if parsed is None:
            skip("malformed_event")
            continue
        tick, kind, details = parsed
        occurrence = getattr(event, "occurrence", None)
        occurrence_origin = _text(getattr(occurrence, "origin_location_id", None))
        if kind == "move":
            read += 1
            actor = _text(getattr(event, "actor_id", None))
            destination = _text(
                getattr(details, "resulting_location_id", None)
            ) or _text(getattr(details, "destination_id", None))
            if actor is None or destination is None or occurrence_origin is None:
                skip("move_identity_missing")
                continue
            if occurrence_origin == destination:
                continue
            add((actor,), occurrence_origin, destination, tick, tick, "move", "arrived")
        elif kind == "transport":
            read += 1
            actor = _text(getattr(event, "actor_id", None))
            target = _text(getattr(details, "target_id", None))
            destination = _text(getattr(details, "destination_id", None))
            origin = _text(getattr(details, "origin_location_id", None)) or (
                occurrence_origin
            )
            if actor is None or target is None or destination is None or origin is None:
                skip("transport_identity_missing")
                continue
            if origin == destination:
                continue
            both = tuple(sorted({actor, target}))
            add(both, origin, destination, tick, tick, "transport", "arrived")
        elif kind == "flee":
            read += 1
            if getattr(details, "success", None) is not True:
                continue
            actor = _text(getattr(event, "actor_id", None))
            destination = _text(getattr(details, "destination_id", None))
            if actor is None or destination is None or occurrence_origin is None:
                skip("flee_identity_missing")
                continue
            if occurrence_origin == destination:
                continue
            add((actor,), occurrence_origin, destination, tick, tick, "flee", "arrived")
        elif kind == "journey_started":
            read += 1
            journey = getattr(details, "journey", None)
            journey_id = getattr(journey, "journey_id", None)
            origin = _text(getattr(journey, "origin_location_id", None))
            destination = _text(getattr(journey, "destination_location_id", None))
            members = _participants(getattr(journey, "participant_body_ids", None))
            start = getattr(journey, "start_tick", tick)
            if (
                type(journey_id) is not str
                or origin is None
                or destination is None
                or members is None
                or type(start) is not int
            ):
                skip("journey_start_incomplete")
                continue
            pending[journey_id] = _Pending(start, origin, destination, members)
        elif kind in {"journey_arrived", "journey_ended"}:
            read += 1
            journey_id = getattr(details, "journey_id", None)
            origin = _text(getattr(details, "origin_location_id", None))
            destination = _text(getattr(details, "destination_location_id", None))
            members = _participants(getattr(details, "participant_body_ids", None))
            if (
                type(journey_id) is not str
                or origin is None
                or destination is None
                or members is None
            ):
                skip("journey_end_incomplete")
                continue
            started = pending.pop(journey_id, None)
            start = tick if started is None else started.start_tick
            if kind == "journey_arrived":
                status = "arrived"
            elif getattr(details, "reason", None) == "participant_dead":
                status = "dead"
            elif getattr(details, "reason", None) == "arrival_timeout":
                status = "timeout"
            else:
                status = "unknown"
            add(
                members, origin, destination, start, max(tick, start), "journey", status
            )
        elif kind == "died":
            read += 1
            body = _text(getattr(details, "body_id", None))
            if body is None:
                skip("death_identity_missing")
                continue
            deaths.setdefault(body, tick)
        elif kind in {
            "contact_recorded",
            "lifecycle_stage_changed",
            "agent_entered_world",
        }:
            read += 1
    for item in pending.values():
        group = min(len(item.participants), _MAX_GROUP)
        for raw in item.participants:
            died = deaths.get(raw)
            if died is not None and died >= item.start_tick:
                status, end = "dead", died
            else:
                status, end = "pending", item.start_tick
            drafts.append(
                _Draft(
                    raw,
                    item.origin,
                    item.destination,
                    item.start_tick,
                    end,
                    "journey",
                    group,
                    status,
                )
            )
    return drafts, skipped, read


def _boundary_complete(
    window_end: int | None, complete_through_boundary: int | None
) -> bool:
    if window_end is None or complete_through_boundary is None:
        return True
    return complete_through_boundary >= window_end


def migration_movement_rows_with_coverage(
    events: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    region_topology: Mapping[str, str] | None = None,
    max_pairs: int = 4096,
    entity_to_agent: Mapping[str, str] | None = None,
    window_end: int | None = None,
    complete_through_boundary: int | None = None,
) -> tuple[tuple[MigrationMovementRow, ...], str]:
    """Rows plus aggregate coverage: ``complete``, ``partial``, or ``missing``."""
    _require_ids(run_id, input_revision)
    source = _require_events(events)
    if type(max_pairs) is not int or max_pairs < 1:
        raise ValueError("migration_events: max_pairs")
    drafts, skipped, _read = _scan_movements(source)
    boundary_ok = _boundary_complete(window_end, complete_through_boundary)
    base_complete = skipped == 0 and boundary_ok
    rows: dict[tuple[str, str, str, int, str], MigrationMovementRow] = {}
    for draft in drafts:
        participant = _participant_token(draft.participant, entity_to_agent)
        origin = migration_location_token(draft.origin)
        destination = migration_location_token(draft.destination)
        mapped = region_topology is None or (
            draft.origin in region_topology and draft.destination in region_topology
        )
        key = (participant, origin, destination, draft.start_tick, draft.kind)
        if key in rows:
            continue
        rows[key] = MigrationMovementRow(
            participant_token=participant,
            origin_token=origin,
            destination_token=destination,
            route_tokens=(origin, destination),
            start_tick=draft.start_tick,
            end_tick=draft.end_tick,
            relocation_kind=draft.kind,
            group_size=draft.group,
            arrival_status=draft.status,
            coverage="complete" if base_complete and mapped else "partial",
        )
    ordered = sorted(
        rows.values(),
        key=lambda row: (
            row.start_tick,
            row.participant_token,
            row.destination_token,
            row.origin_token,
            row.relocation_kind,
        ),
    )
    truncated = len(ordered) > max_pairs
    if truncated:
        _LOG.warning("migration_movement_rows_truncated cap=%s", max_pairs)
        ordered = [replace(row, coverage="partial") for row in ordered[:max_pairs]]
    if not ordered:
        if not source:
            coverage = "missing"
        else:
            coverage = "complete" if boundary_ok and skipped == 0 else "partial"
    elif any(row.coverage != "complete" for row in ordered):
        coverage = "partial"
    else:
        coverage = "complete"
    _LOG.debug(
        "migration_movement_rows events=%s rows=%s complete=%s",
        len(source),
        len(ordered),
        coverage == "complete",
    )
    return tuple(ordered), coverage


def migration_movement_rows_from_events(
    events: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    region_topology: Mapping[str, str] | None = None,
    max_pairs: int = 4096,
    entity_to_agent: Mapping[str, str] | None = None,
    window_end: int | None = None,
    complete_through_boundary: int | None = None,
) -> tuple[MigrationMovementRow, ...]:
    """Sorted, deduplicated objective movement rows from committed events."""
    rows, _coverage = migration_movement_rows_with_coverage(
        events,
        run_id=run_id,
        input_revision=input_revision,
        region_topology=region_topology,
        max_pairs=max_pairs,
        entity_to_agent=entity_to_agent,
        window_end=window_end,
        complete_through_boundary=complete_through_boundary,
    )
    return rows


def _pair(left: str, right: str) -> tuple[str, str] | None:
    if left == right:
        return None
    return (left, right) if left < right else (right, left)


def migration_kinship_pairs_from_events(
    events: Sequence[object],
) -> tuple[tuple[str, str], ...]:
    """Sorted unique participant-token pairs from ``KinshipEdgeRecorded`` only."""
    pairs: set[tuple[str, str]] = set()
    for event in _require_events(events):
        parsed = _event_fields(event)
        if parsed is None or parsed[1] != "kinship_edge_recorded":
            continue
        details = parsed[2]
        parent = getattr(details, "parent_agent_id", None)
        child = getattr(details, "child_agent_id", None)
        if getattr(details, "success", True) is not True:
            continue
        if type(parent) is not str or type(child) is not str:
            continue
        pair = _pair(migration_agent_token(parent), migration_agent_token(child))
        if pair is not None:
            pairs.add(pair)
    return tuple(sorted(pairs))


def migration_communication_pairs_from_events(
    events: Sequence[object],
    *,
    entity_to_agent: Mapping[str, str] | None = None,
) -> tuple[tuple[str, str], ...]:
    """Sorted unique token pairs from committed ``Talked``/``Asked``/``Told``."""
    pairs: set[tuple[str, str]] = set()
    for event in _require_events(events):
        parsed = _event_fields(event)
        if parsed is None or parsed[1] not in {"talk", "ask", "tell"}:
            continue
        actor = _text(getattr(event, "actor_id", None))
        recipient = _text(getattr(parsed[2], "recipient_id", None))
        if actor is None or recipient is None:
            continue
        pair = _pair(
            _participant_token(actor, entity_to_agent),
            _participant_token(recipient, entity_to_agent),
        )
        if pair is not None:
            pairs.add(pair)
    return tuple(sorted(pairs))


_BODY_DOMAIN: Final[Mapping[str, str]] = {
    "needs_applied": "needs",
    "exposure_applied": "needs",
}
_ACTOR_DOMAIN: Final[Mapping[str, str]] = {
    "exchange_completed": "resource_access",
    "public_good_benefit": "resource_access",
    "project_contributed": "resource_access",
    "give": "resource_access",
    "take": "resource_access",
    "attack": "conflict_status",
    "talk": "relationships",
    "ask": "relationships",
    "tell": "relationships",
}


def _evidence_targets(
    event: object, kind: str, details: object
) -> tuple[str, tuple[str, ...]] | None:
    """Return ``(domain, raw participant ids)`` for one evidence event."""
    if kind in _BODY_DOMAIN:
        body = _text(getattr(details, "body_id", None))
        return (_BODY_DOMAIN[kind], (body,)) if body else None
    if kind in _ACTOR_DOMAIN:
        names = [_text(getattr(event, "actor_id", None))]
        if kind in {"give", "exchange_completed", "attack"}:
            names.append(_text(getattr(event, "target_id", None)))
        if kind in {"talk", "ask", "tell"}:
            names.append(_text(getattr(details, "recipient_id", None)))
        ids = tuple(sorted({item for item in names if item}))
        return (_ACTOR_DOMAIN[kind], ids) if ids else None
    if kind == "contact_recorded":
        present = _participants(getattr(details, "participant_ids", None)) or ()
        near = _participants(getattr(details, "present_ids", None)) or ()
        ids = tuple(sorted({*present, *near}))
        return ("relationships", ids) if ids else None
    return None


def migration_integration_rows_from_events(
    events: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    max_pairs: int = 4096,
    entity_to_agent: Mapping[str, str] | None = None,
    region_topology: Mapping[str, str] | None = None,
    window_end: int | None = None,
    complete_through_boundary: int | None = None,
) -> tuple[MigrationIntegrationEvidenceRow, ...]:
    """Count committed evidence per participant, destination, and closed domain.

    Evidence is attributed to the destination where the participant resided at
    the event tick, as established by objective arrivals. Silence never creates
    a row, and organization or institution participation is never inferred from
    unrelated events.
    """
    movements, coverage = migration_movement_rows_with_coverage(
        events,
        run_id=run_id,
        input_revision=input_revision,
        region_topology=region_topology,
        max_pairs=max_pairs,
        entity_to_agent=entity_to_agent,
        window_end=window_end,
        complete_through_boundary=complete_through_boundary,
    )
    source = _require_events(events)
    timeline: dict[str, list[tuple[int, int, str, bool]]] = {}
    for row in movements:
        timeline.setdefault(row.participant_token, []).append(
            (
                row.start_tick,
                row.end_tick,
                row.destination_token,
                row.arrival_status == "arrived",
            )
        )
    for items in timeline.values():
        items.sort()
    cells: dict[tuple[str, str, str], list[int]] = {}

    def count(participant: str, destination: str, domain: str, tick: int) -> None:
        cell = cells.setdefault((participant, destination, domain), [0, tick, tick])
        cell[0] += 1
        cell[1] = min(cell[1], tick)
        cell[2] = max(cell[2], tick)

    for row in movements:
        if row.arrival_status == "arrived":
            count(
                row.participant_token, row.destination_token, "residence", row.end_tick
            )

    def residence(participant: str, tick: int) -> str | None:
        items = timeline.get(participant)
        if not items:
            return None
        for index, (_start, end, destination, arrived) in enumerate(items):
            following = items[index + 1][0] if index + 1 < len(items) else None
            if arrived and end <= tick and (following is None or tick < following):
                return destination
        return None

    for event in source:
        parsed = _event_fields(event)
        if parsed is None:
            continue
        tick, kind, details = parsed
        if kind == "kinship_edge_recorded":
            if getattr(details, "success", True) is not True:
                continue
            raw_ids = tuple(
                item
                for item in (
                    getattr(details, "parent_agent_id", None),
                    getattr(details, "child_agent_id", None),
                )
                if type(item) is str
            )
            tokens = tuple(sorted({migration_agent_token(item) for item in raw_ids}))
            domain = "relationships"
        else:
            target = _evidence_targets(event, kind, details)
            if target is None:
                continue
            domain, raw_ids = target
            tokens = tuple(
                sorted({_participant_token(item, entity_to_agent) for item in raw_ids})
            )
        for token in tokens:
            destination = residence(token, tick)
            if destination is not None:
                count(token, destination, domain, tick)
    row_coverage = "complete" if coverage == "complete" else "partial"
    rows = [
        MigrationIntegrationEvidenceRow(
            participant_token=participant,
            destination_token=destination,
            domain=domain,
            evidence_count=cell[0],
            first_tick=cell[1],
            last_tick=cell[2],
            coverage=row_coverage,
        )
        for (participant, destination, domain), cell in sorted(cells.items())
    ]
    if len(rows) > max_pairs:
        _LOG.warning("migration_integration_rows_truncated cap=%s", max_pairs)
        rows = rows[:max_pairs]
    _LOG.debug("migration_integration_rows events=%s rows=%s", len(source), len(rows))
    return tuple(rows)
