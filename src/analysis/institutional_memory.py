"""Detached institutional-memory continuity and provenance metrics.

Rows are harvested from exported owner ledgers and completed objective events
after the run. Owner-local channels, declared frame lineage, native carrier
receipts, and analytical alignment remain distinct evidence. Nothing here feeds
live cognition.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Final, cast

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "InstitutionalCarrierRow",
    "InstitutionalChannelRow",
    "InstitutionalIdentityRow",
    "InstitutionalMemoryEntryRow",
    "InstitutionalMemorySnapshot",
    "InstitutionalMemoryTransferEdge",
    "InstitutionalMemoryUseRow",
    "InstitutionalOccupantClaimRow",
    "compute_institutional_memory_continuity",
    "compute_institutional_memory_provenance",
    "harvest_institutional_memory_rows",
    "institutional_memory_carrier_rows_from_events",
    "institutional_memory_identity_rows_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.institutional_memory")

_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_DIGEST_LEN: Final[int] = 16


class InstitutionalMemoryAnalysisError(ValueError):
    """Fail-closed analysis error with code-only messages."""


def _digest16(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:_DIGEST_LEN]


def _stable(value: object) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) and raw else None


def _as_str(value: object, field_name: str) -> str:
    text = _stable(value)
    if text is None:
        raise InstitutionalMemoryAnalysisError(f"invalid:{field_name}")
    return text


def _as_optional_str(value: object) -> str | None:
    return _stable(value)


def _as_optional_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise InstitutionalMemoryAnalysisError(f"invalid:{field_name}")
    return value


def _as_int(value: object, field_name: str) -> int:
    parsed = _as_optional_int(value, field_name)
    if parsed is None:
        raise InstitutionalMemoryAnalysisError(f"invalid:{field_name}")
    return parsed


def _sequence(value: object, field_name: str) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise InstitutionalMemoryAnalysisError(f"invalid:{field_name}")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class InstitutionalIdentityRow:
    """One objective agent/entity identity binding."""

    agent_id: str
    entity_id: str
    first_tick: int
    last_tick: int | None = None


@dataclass(frozen=True, slots=True)
class InstitutionalCarrierRow:
    """One completed native delivery or artifact revision occurrence."""

    run_id: str
    event_id: str
    tick: int
    sequence: int
    kind: str
    actor_entity_id: str
    recipient_entity_id: str | None = None
    artifact_id: str | None = None
    content_revision: int | None = None
    parent_artifact_id: str | None = None
    source_artifact_id: str | None = None


@dataclass(frozen=True, slots=True)
class InstitutionalOccupantClaimRow:
    """One owner-local attributed occupant claim."""

    owner_id: str
    channel_id: str
    occupant_id: str | None
    attributed_actor_id: str | None
    status: str
    start_tick: int | None
    end_tick: int | None
    source_evidence_ref: str | None


@dataclass(frozen=True, slots=True)
class InstitutionalChannelRow:
    """One detached channel binding and its retained occupant claims."""

    owner_id: str
    channel_id: str
    binding_kind: str
    function_token: str
    context_digest: str
    first_tick: int
    last_tick: int
    revision_count: int
    current_local_reference: str
    occupants: tuple[InstitutionalOccupantClaimRow, ...]
    pruned: bool


@dataclass(frozen=True, slots=True)
class InstitutionalMemoryEntryRow:
    """One owner-local entry reduced to detached analytical fields."""

    owner_id: str
    entry_id: str
    channel_id: str | None
    acquisition_tick: int
    acquisition_channel: str
    facts: tuple[tuple[str, str, str], ...]
    declared_root: str | None
    declared_parent: str | None
    source_event_id: str | None
    artifact_id: str | None
    artifact_revision: int | None
    partial: bool
    ignored: bool
    source_state: str
    revision: int = 0
    artifact_root_id: str | None = None
    observed_entity_id: str | None = None
    resolved_source_agent_id: str | None = None
    binding_kind: str | None = None
    function_token: str | None = None
    context_digest: str | None = None
    active: bool = True


@dataclass(frozen=True, slots=True)
class InstitutionalMemoryUseRow:
    """One completion receipt from an owner's exported ledger."""

    owner_id: str
    entry_id: str
    channel_id: str | None
    invocation_id: str
    tick: int
    disposition: str


@dataclass(frozen=True, slots=True)
class InstitutionalMemorySnapshot:
    """All detached rows for one enabled owner."""

    owner_id: str
    entries: tuple[InstitutionalMemoryEntryRow, ...]
    channel_count: int
    bound_channel_count: int
    use_count: int
    consulted_entry_count: int
    coverage: str
    channels: tuple[InstitutionalChannelRow, ...] = ()
    uses: tuple[InstitutionalMemoryUseRow, ...] = ()
    observation_count: int = 0
    pruned: bool = False


@dataclass(frozen=True, slots=True)
class InstitutionalMemoryTransferEdge:
    """One candidate content-transfer edge with explicit evidence status."""

    source_owner_id: str | None
    target_owner_id: str
    entry_id: str
    kind: str
    status: str
    source_event_id: str | None = None
    artifact_id: str | None = None
    artifact_revision: int | None = None
    declared_root: str | None = None


def _source_state(provenance: object) -> str:
    predecessor = getattr(provenance, "predecessor", None)
    state = getattr(predecessor, "state", None)
    return _stable(state) or "retained"


def _channel_value(provenance: object) -> str:
    channel = getattr(provenance, "immediate_channel", None)
    return _stable(channel) or "unknown"


def _occupant_rows(
    owner: str, channel: object, channel_id: str
) -> tuple[InstitutionalOccupantClaimRow, ...]:
    rows: list[InstitutionalOccupantClaimRow] = []
    for claim in _sequence(getattr(channel, "occupants", ()), "occupants"):
        rows.append(
            InstitutionalOccupantClaimRow(
                owner_id=owner,
                channel_id=channel_id,
                occupant_id=_as_optional_str(getattr(claim, "occupant_id", None)),
                attributed_actor_id=_as_optional_str(
                    getattr(claim, "attributed_actor_id", None)
                ),
                status=_stable(getattr(claim, "status", None)) or "unknown",
                start_tick=_as_optional_int(
                    getattr(claim, "start_tick", None), "claim.start_tick"
                ),
                end_tick=_as_optional_int(
                    getattr(claim, "end_tick", None), "claim.end_tick"
                ),
                source_evidence_ref=_as_optional_str(
                    getattr(claim, "source_evidence_ref", None)
                ),
            )
        )
    return tuple(rows)


def _channel_rows(owner: str, ledger: object) -> tuple[InstitutionalChannelRow, ...]:
    rows: list[InstitutionalChannelRow] = []
    for channel in _sequence(getattr(ledger, "channels", ()), "channels"):
        channel_id = _as_str(getattr(channel, "channel_id", None), "channel_id")
        rows.append(
            InstitutionalChannelRow(
                owner_id=owner,
                channel_id=channel_id,
                binding_kind=_stable(getattr(channel, "binding_kind", None)) or "role",
                function_token=(
                    _as_optional_str(getattr(channel, "public_function_token", None))
                    or "unknown"
                ),
                context_digest=(
                    _as_optional_str(getattr(channel, "context_digest", None)) or ""
                ),
                first_tick=_as_int(getattr(channel, "first_tick", 0), "first_tick"),
                last_tick=_as_int(getattr(channel, "last_tick", 0), "last_tick"),
                revision_count=_as_int(
                    getattr(channel, "revision_count", 0), "revision_count"
                ),
                current_local_reference=(
                    _as_optional_str(getattr(channel, "current_local_reference", None))
                    or ""
                ),
                occupants=_occupant_rows(owner, channel, channel_id),
                pruned=bool(
                    getattr(channel, "pruned_evidence_count", 0)
                    or getattr(channel, "pruned_occupant_count", 0)
                ),
            )
        )
    return tuple(rows)


def _entry_rows(
    owner: str, ledger: object
) -> tuple[InstitutionalMemoryEntryRow, ...]:
    rows: list[InstitutionalMemoryEntryRow] = []
    for entry in _sequence(getattr(ledger, "entries", ()), "entries"):
        provenance = _sequence(getattr(entry, "provenance", ()), "provenance")
        first = provenance[0] if provenance else None
        facts: list[tuple[str, str, str]] = []
        for fact in _sequence(getattr(entry, "facts", ()), "facts"):
            subject = _as_optional_str(getattr(fact, "subject", None))
            predicate = _as_optional_str(getattr(fact, "predicate", None))
            obj = _as_optional_str(getattr(fact, "object", None))
            if subject is not None and predicate is not None and obj is not None:
                facts.append((subject, predicate, obj))
        rows.append(
            InstitutionalMemoryEntryRow(
                owner_id=owner,
                entry_id=_as_str(getattr(entry, "entry_id", None), "entry_id"),
                channel_id=_as_optional_str(getattr(entry, "channel_id", None)),
                acquisition_tick=_as_int(
                    getattr(entry, "acquisition_tick", 0), "acquisition_tick"
                ),
                acquisition_channel=_channel_value(first),
                facts=tuple(facts),
                declared_root=(
                    None
                    if first is None
                    else _as_optional_str(getattr(first, "declared_frame_root", None))
                ),
                declared_parent=(
                    None
                    if first is None
                    else _as_optional_str(getattr(first, "declared_frame_parent", None))
                ),
                source_event_id=(
                    None
                    if first is None
                    else _as_optional_str(getattr(first, "occurrence_ref", None))
                ),
                artifact_id=(
                    None
                    if first is None
                    else _as_optional_str(getattr(first, "artifact_id", None))
                ),
                artifact_revision=(
                    None
                    if first is None
                    else _as_optional_int(
                        getattr(first, "artifact_revision", None),
                        "artifact_revision",
                    )
                ),
                partial=bool(getattr(entry, "partial", False)),
                ignored=bool(getattr(entry, "ignored", False)),
                source_state=_source_state(first) if first is not None else "retained",
                revision=_as_int(getattr(entry, "revision", 0), "revision"),
                artifact_root_id=(
                    None
                    if first is None
                    else _as_optional_str(getattr(first, "artifact_root_id", None))
                ),
                observed_entity_id=(
                    None
                    if first is None
                    else _as_optional_str(getattr(first, "observed_entity_id", None))
                ),
                resolved_source_agent_id=(
                    None
                    if first is None
                    else _as_optional_str(
                        getattr(first, "resolved_source_agent_id", None)
                    )
                ),
                binding_kind=_stable(getattr(entry, "binding_kind", None)),
                function_token=_as_optional_str(
                    getattr(entry, "binding_function_token", None)
                ),
                context_digest=_as_optional_str(
                    getattr(entry, "binding_context_digest", None)
                ),
                active=bool(getattr(entry, "active", True)),
            )
        )
    return tuple(rows)


def _use_rows(owner: str, ledger: object) -> tuple[InstitutionalMemoryUseRow, ...]:
    rows: list[InstitutionalMemoryUseRow] = []
    for use in _sequence(getattr(ledger, "uses", ()), "uses"):
        rows.append(
            InstitutionalMemoryUseRow(
                owner_id=owner,
                entry_id=_as_str(getattr(use, "entry_id", None), "use.entry_id"),
                channel_id=_as_optional_str(getattr(use, "channel_id", None)),
                invocation_id=_as_str(
                    getattr(use, "invocation_id", None), "use.invocation_id"
                ),
                tick=_as_int(getattr(use, "tick", 0), "use.tick"),
                disposition=_stable(getattr(use, "disposition", None)) or "unknown",
            )
        )
    return tuple(rows)


def harvest_institutional_memory_rows(
    ledgers: object,
) -> tuple[InstitutionalMemorySnapshot, ...]:
    """Freeze completed exported ledgers without reading live cognition."""
    if ledgers is None:
        return ()
    snapshots: list[InstitutionalMemorySnapshot] = []
    for ledger in _sequence(ledgers, "ledgers"):
        owner = _as_str(getattr(ledger, "owner_id", None), "owner")
        channels = _channel_rows(owner, ledger)
        entries = _entry_rows(owner, ledger)
        uses = _use_rows(owner, ledger)
        coverage = _stable(getattr(ledger, "coverage", None)) or (
            "partial" if any(entry.partial for entry in entries) else "complete"
        )
        pruned = (
            coverage == "partial"
            or any(
                _as_int(getattr(ledger, name, 0), name) > 0
                for name in (
                    "pruned_channel_count",
                    "pruned_entry_count",
                    "pruned_use_count",
                    "pruned_provenance_count",
                    "pruned_receipt_count",
                )
            )
        )
        snapshots.append(
            InstitutionalMemorySnapshot(
                owner_id=owner,
                entries=entries,
                channel_count=len(channels),
                bound_channel_count=sum(
                    1 for channel in channels if channel.channel_id
                ),
                use_count=len(uses),
                consulted_entry_count=sum(
                    1 for use in uses if use.disposition == "consulted"
                ),
                coverage=coverage,
                channels=channels,
                uses=uses,
                observation_count=_as_int(
                    getattr(ledger, "observation_count", 0), "observation_count"
                ),
                pruned=pruned,
            )
        )
    _LOG.debug(
        "institutional_memory_rows_harvested ledger_count=%s owner_count=%s",
        len(snapshots),
        len(snapshots),
    )
    return tuple(sorted(snapshots, key=lambda item: item.owner_id))


def institutional_memory_carrier_rows_from_events(
    events: object,
) -> tuple[InstitutionalCarrierRow, ...]:
    """Project only completed public event values; no cognition payloads."""
    if events is None:
        return ()
    from world.events import (
        ArtifactAnnotated,
        ArtifactCopied,
        ArtifactCreated,
        ArtifactDamaged,
        ArtifactModified,
        ArtifactPartiallyLost,
        Asked,
        Talked,
        Told,
    )

    rows: list[InstitutionalCarrierRow] = []
    for event in cast("Iterable[object]", events):
        details = getattr(event, "details", None)
        actor = _as_optional_str(getattr(event, "actor_id", None))
        if actor is None:
            actor = _as_optional_str(getattr(details, "author_id", None))
        run_id = _as_optional_str(getattr(event, "run_id", None)) or "run"
        event_id = _as_optional_str(getattr(event, "event_id", None)) or "event"
        tick = _as_int(getattr(event, "tick", 0), "event.tick")
        sequence = _as_int(getattr(event, "sequence", 0), "event.sequence")
        if isinstance(details, (Talked, Asked, Told)):
            rows.append(
                InstitutionalCarrierRow(
                    run_id=run_id,
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=details.kind,
                    actor_entity_id=actor or "unknown",
                    recipient_entity_id=_as_optional_str(details.recipient_id),
                )
            )
        elif isinstance(
            details,
            (
                ArtifactCreated,
                ArtifactModified,
                ArtifactAnnotated,
                ArtifactDamaged,
                ArtifactPartiallyLost,
            ),
        ):
            rows.append(
                InstitutionalCarrierRow(
                    run_id=run_id,
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=details.kind,
                    actor_entity_id=actor or "unknown",
                    artifact_id=_as_optional_str(details.artifact_id),
                    content_revision=_as_optional_int(
                        details.content_revision, "content_revision"
                    ),
                )
            )
        elif isinstance(details, ArtifactCopied):
            rows.append(
                InstitutionalCarrierRow(
                    run_id=run_id,
                    event_id=event_id,
                    tick=tick,
                    sequence=sequence,
                    kind=details.kind,
                    actor_entity_id=actor or "unknown",
                    artifact_id=_as_optional_str(details.child_artifact_id),
                    content_revision=_as_optional_int(
                        details.content_revision, "content_revision"
                    ),
                    parent_artifact_id=_as_optional_str(details.parent_artifact_id),
                    source_artifact_id=_as_optional_str(details.source_artifact_id),
                )
            )
        else:
            continue
    return tuple(sorted(rows, key=lambda row: (row.tick, row.sequence, row.event_id)))


def institutional_memory_identity_rows_from_events(
    events: object,
    *,
    initial_pairs: Sequence[tuple[str, str]] = (),
) -> tuple[InstitutionalIdentityRow, ...]:
    """Build objective identity rows from initial assignments and admissions."""
    rows: list[InstitutionalIdentityRow] = [
        InstitutionalIdentityRow(agent_id=agent, entity_id=entity, first_tick=0)
        for agent, entity in initial_pairs
    ]
    for event in cast("Iterable[object]", events or ()):
        details = getattr(event, "details", None)
        if getattr(details, "kind", None) != "agent_initialization_recorded":
            continue
        agent_id = _as_optional_str(getattr(details, "agent_id", None))
        entity_id = _as_optional_str(getattr(details, "body_id", None))
        tick = _as_int(getattr(event, "tick", 0), "event.tick")
        if agent_id is None or entity_id is None:
            continue
        rows.append(
            InstitutionalIdentityRow(
                agent_id=agent_id, entity_id=entity_id, first_tick=tick
            )
        )
    return tuple(
        sorted(
            {
                (row.agent_id, row.entity_id, row.first_tick, row.last_tick): row
                for row in rows
            }.values(),
            key=lambda row: (row.agent_id, row.first_tick, row.entity_id),
        )
    )


def _office_alignment_index(
    office_rows: Sequence[object],
) -> tuple[dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]]]:
    by_office: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_context: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in office_rows:
        owner = _as_optional_str(getattr(row, "owner_id", None))
        office = _as_optional_str(getattr(row, "office_id", None))
        function = _as_optional_str(getattr(row, "function", None))
        context = _as_optional_str(getattr(row, "context_key", None))
        key = _as_optional_str(getattr(row, "alignment_key", None))
        if key is None and function is not None and context is not None:
            key = _digest16(f"office-align|{function}|{context}")
        if key is None:
            continue
        if owner is not None and office is not None:
            by_office[(owner, office)].add(key)
        if function is not None and context is not None:
            by_context[(function, context)].add(key)
    return by_office, by_context


def _align_channels(
    snapshots: Sequence[InstitutionalMemorySnapshot],
    office_rows: Sequence[object],
) -> tuple[dict[tuple[str, str], str | None], int, int]:
    by_office, by_context = _office_alignment_index(office_rows)
    alignments: dict[tuple[str, str], str | None] = {}
    ambiguous = 0
    excluded = 0
    for snapshot in snapshots:
        for channel in snapshot.channels:
            candidates: set[str] = set()
            if channel.binding_kind == "role":
                candidates = set(
                    by_office.get(
                        (snapshot.owner_id, channel.current_local_reference), set()
                    )
                )
                if not candidates:
                    candidates = set(
                        by_context.get(
                            (channel.function_token, channel.context_digest), set()
                        )
                    )
                fallback = _digest16(
                    f"institutional-role-local|{snapshot.owner_id}|{channel.channel_id}"
                )
            else:
                candidates = set(
                    by_context.get(
                        (channel.function_token, channel.context_digest), set()
                    )
                )
                fallback = _digest16(
                    f"institutional-procedure|{channel.context_digest}"
                )
            if len(candidates) == 1:
                alignments[(snapshot.owner_id, channel.channel_id)] = next(
                    iter(candidates)
                )
            elif len(candidates) > 1:
                alignments[(snapshot.owner_id, channel.channel_id)] = None
                ambiguous += 1
            else:
                alignments[(snapshot.owner_id, channel.channel_id)] = fallback
            if channel.pruned:
                excluded += 1
    return alignments, ambiguous, excluded


def _source_keys(
    entries: Sequence[InstitutionalMemoryEntryRow],
) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for entry in entries:
        if entry.declared_root is not None:
            keys.add(("declared", entry.declared_root))
        if entry.artifact_root_id is not None:
            keys.add(("artifact_root", entry.artifact_root_id))
        if entry.artifact_id is not None:
            keys.add(("artifact", entry.artifact_id))
        if entry.source_event_id is not None:
            keys.add(("event", entry.source_event_id))
    return keys


def _shares_source(
    entry: InstitutionalMemoryEntryRow,
    prior_entries: Sequence[InstitutionalMemoryEntryRow],
) -> bool:
    keys = _source_keys((entry,))
    return bool(keys & _source_keys(prior_entries))


def _cross_occupant_counts(
    snapshots: Sequence[InstitutionalMemorySnapshot],
    alignments: dict[tuple[str, str], str | None],
) -> tuple[int, int, int, int]:
    by_owner = {snapshot.owner_id: snapshot for snapshot in snapshots}
    opportunities: dict[
        tuple[str, str, str, int],
        tuple[tuple[InstitutionalMemoryEntryRow, ...], str],
    ] = {}
    ambiguous = 0
    excluded = 0
    for snapshot in snapshots:
        for channel in snapshot.channels:
            claims = [
                claim
                for claim in channel.occupants
                if claim.occupant_id is not None
                and claim.start_tick is not None
                and claim.status in {"observed", "claimed", "ended", "disputed"}
            ]
            deduped = {
                (
                    claim.occupant_id,
                    claim.start_tick,
                    claim.end_tick,
                    claim.status,
                ): claim
                for claim in claims
            }
            ordered = sorted(
                deduped.values(),
                key=lambda claim: (
                    claim.start_tick if claim.start_tick is not None else 0,
                    claim.end_tick if claim.end_tick is not None else 10**18,
                    claim.occupant_id or "",
                ),
            )
            alignment = alignments.get((snapshot.owner_id, channel.channel_id))
            if alignment is None:
                if ordered:
                    ambiguous += 1
                continue
            for prior, successor in pairwise(ordered):
                if prior.occupant_id == successor.occupant_id:
                    continue
                if (
                    prior.end_tick is None
                    or successor.start_tick is None
                    or prior.end_tick > successor.start_tick
                ):
                    excluded += 1
                    continue
                prior_entries = tuple(
                    entry
                    for entry in snapshot.entries
                    if entry.channel_id == channel.channel_id
                    and entry.acquisition_tick <= prior.end_tick
                )
                if not prior_entries:
                    excluded += 1
                    continue
                key = (
                    alignment,
                    prior.occupant_id or "",
                    successor.occupant_id or "",
                    successor.start_tick,
                )
                opportunities.setdefault(
                    key, (prior_entries, successor.occupant_id or "")
                )
    acquired = 0
    for (alignment, _prior_owner, successor_owner, transition_tick), (
        prior_entries,
        _successor_claim,
    ) in opportunities.items():
        successor_snapshot = by_owner.get(successor_owner)
        if successor_snapshot is None:
            continue
        for entry in successor_snapshot.entries:
            if entry.acquisition_tick < transition_tick:
                continue
            if (
                alignments.get(
                    (successor_snapshot.owner_id, entry.channel_id or "")
                )
                != alignment
            ):
                continue
            if _shares_source(entry, prior_entries):
                acquired += 1
                break
    return len(opportunities), acquired, ambiguous, excluded


def _identity_maps(
    identity_rows: Sequence[InstitutionalIdentityRow],
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    agents: dict[str, str | None] = {}
    entities: dict[str, str | None] = {}
    for row in identity_rows:
        if row.agent_id in agents and agents[row.agent_id] != row.entity_id:
            agents[row.agent_id] = None
        else:
            agents.setdefault(row.agent_id, row.entity_id)
        if row.entity_id in entities and entities[row.entity_id] != row.agent_id:
            entities[row.entity_id] = None
        else:
            entities.setdefault(row.entity_id, row.agent_id)
    return agents, entities


def _carrier_index(
    carrier_rows: Sequence[InstitutionalCarrierRow],
) -> tuple[
    dict[str, InstitutionalCarrierRow],
    dict[str, tuple[InstitutionalCarrierRow, ...]],
]:
    by_event: dict[str, InstitutionalCarrierRow] = {}
    by_artifact: dict[str, list[InstitutionalCarrierRow]] = defaultdict(list)
    for row in carrier_rows:
        by_event.setdefault(row.event_id, row)
        if row.artifact_id is not None:
            by_artifact[row.artifact_id].append(row)
    return by_event, {key: tuple(value) for key, value in by_artifact.items()}


def _build_edges(
    snapshots: Sequence[InstitutionalMemorySnapshot],
    carrier_rows: Sequence[InstitutionalCarrierRow],
    identity_rows: Sequence[InstitutionalIdentityRow],
) -> tuple[tuple[InstitutionalMemoryTransferEdge, InstitutionalMemoryEntryRow], ...]:
    _agents, entities = _identity_maps(identity_rows)
    by_event, by_artifact = _carrier_index(carrier_rows)
    edges: list[
        tuple[InstitutionalMemoryTransferEdge, InstitutionalMemoryEntryRow]
    ] = []
    for snapshot in snapshots:
        for entry in snapshot.entries:
            status = "unresolved"
            source_owner: str | None = None
            chosen: InstitutionalCarrierRow | None = None
            if entry.source_state == "pruned":
                status = "pruned"
            elif entry.artifact_id is not None and entry.artifact_revision is not None:
                candidates = tuple(
                    row
                    for row in by_artifact.get(entry.artifact_id, ())
                    if row.tick <= entry.acquisition_tick
                    and (
                        row.content_revision == entry.artifact_revision
                        or row.content_revision is None
                    )
                )
                deduped = {row.event_id: row for row in candidates}
                if len(deduped) == 1:
                    chosen = next(iter(deduped.values()))
                    status = "observed_carrier_path"
                elif len(deduped) > 1:
                    status = "ambiguous"
            if chosen is None and entry.source_event_id is not None:
                candidate = by_event.get(entry.source_event_id)
                if candidate is not None and candidate.tick <= entry.acquisition_tick:
                    recipient = (
                        None
                        if candidate.recipient_entity_id is None
                        else entities.get(candidate.recipient_entity_id)
                    )
                    if candidate.recipient_entity_id is None:
                        status = "unresolved"
                    elif recipient == snapshot.owner_id:
                        chosen = candidate
                        status = "observed_carrier_path"
                    else:
                        status = "ambiguous"
                elif entry.declared_root is not None and status == "unresolved":
                    status = "declared_only"
            if chosen is not None:
                source_owner = entities.get(chosen.actor_entity_id)
            elif status == "unresolved" and entry.declared_root is not None:
                if entry.source_event_id is None and entry.artifact_id is None:
                    status = "declared_only"
            if status not in {
                "observed_carrier_path",
                "declared_only",
                "ambiguous",
                "unresolved",
                "pruned",
            }:
                status = "unresolved"
            edges.append(
                (
                    InstitutionalMemoryTransferEdge(
                        source_owner_id=source_owner,
                        target_owner_id=snapshot.owner_id,
                        entry_id=entry.entry_id,
                        kind=entry.acquisition_channel,
                        status=status,
                        source_event_id=entry.source_event_id,
                        artifact_id=entry.artifact_id,
                        artifact_revision=entry.artifact_revision,
                        declared_root=entry.declared_root,
                    ),
                    entry,
                )
            )
    return tuple(edges)


def _conflict_count(
    snapshots: Sequence[InstitutionalMemorySnapshot],
    alignments: dict[tuple[str, str], str | None],
) -> int:
    grouped: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for snapshot in snapshots:
        for entry in snapshot.entries:
            context = alignments.get(
                (snapshot.owner_id, entry.channel_id or "")
            ) or f"owner-local|{snapshot.owner_id}"
            for subject, predicate, obj in entry.facts:
                grouped[(context, subject, predicate)].add(obj)
    return sum(1 for objects in grouped.values() if len(objects) > 1)


def _independent_root_count(
    edges: Sequence[
        tuple[InstitutionalMemoryTransferEdge, InstitutionalMemoryEntryRow]
    ],
) -> int:
    roots: set[tuple[str, str]] = set()
    for edge, entry in edges:
        if edge.status != "observed_carrier_path":
            continue
        if entry.artifact_root_id is not None:
            roots.add(("artifact-root", entry.artifact_root_id))
        elif entry.artifact_id is not None:
            roots.add(("artifact", entry.artifact_id))
        elif entry.declared_root is not None:
            roots.add(("declared", entry.declared_root))
        elif entry.source_event_id is not None:
            roots.add(("event", entry.source_event_id))
    return len(roots)


def _doc(
    *,
    family: MetricFamilyId,
    run_id: str,
    input_revision: str,
    snapshots: tuple[InstitutionalMemorySnapshot, ...],
    values: dict[str, object],
    availability: MetricAvailability,
    source_kind: str,
) -> MetricDocument:
    spec = metric_specification(family)
    assert set(values) == set(spec.value_keys)
    observed = sum(1 for item in snapshots if item.coverage == "complete")
    coverage = _coverage(observed, max(observed, len(snapshots)))
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=require_stable_id("run_id", run_id),
        input_revision=require_stable_id("input_revision", input_revision),
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind=source_kind,
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )


def _coverage(observed: int, expected: int) -> MetricCoverage | None:
    if expected == 0:
        return None
    return MetricCoverage(observed=observed, expected=expected)


def _availability(
    snapshots: tuple[InstitutionalMemorySnapshot, ...],
    *,
    partial: bool,
) -> MetricAvailability:
    if not snapshots:
        return MetricAvailability.ABSENT
    if partial or any(item.coverage == "partial" for item in snapshots):
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


def _require_carrier_rows(rows: object) -> tuple[InstitutionalCarrierRow, ...]:
    if rows is None:
        return ()
    parsed = _sequence(rows, "carrier_rows")
    for item in parsed:
        if type(item) is not InstitutionalCarrierRow:
            raise InstitutionalMemoryAnalysisError("invalid_row_type")
    return cast("tuple[InstitutionalCarrierRow, ...]", parsed)


def _require_identity_rows(rows: object) -> tuple[InstitutionalIdentityRow, ...]:
    if rows is None:
        return ()
    parsed = _sequence(rows, "identity_rows")
    for item in parsed:
        if type(item) is not InstitutionalIdentityRow:
            raise InstitutionalMemoryAnalysisError("invalid_row_type")
    return cast("tuple[InstitutionalIdentityRow, ...]", parsed)


def _require_office_rows(rows: object) -> tuple[object, ...]:
    if rows is None:
        return ()
    return _sequence(rows, "office_rows")


def compute_institutional_memory_continuity(
    rows: object,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
    carrier_rows: object = None,
    identity_rows: object = None,
    office_rows: object = (),
) -> MetricDocument:
    snapshots = _require_snapshots(rows)
    carriers = _require_carrier_rows(carrier_rows)
    identities = _require_identity_rows(identity_rows)
    offices = _require_office_rows(office_rows)
    entries = tuple(entry for snapshot in snapshots for entry in snapshot.entries)
    alignments, ambiguous_alignments, excluded_alignments = _align_channels(
        snapshots, offices
    )
    opportunities, acquired, occupancy_ambiguous, occupancy_excluded = (
        _cross_occupant_counts(snapshots, alignments)
    )
    ambiguous = ambiguous_alignments + occupancy_ambiguous
    excluded = excluded_alignments + occupancy_excluded
    edges = _build_edges(snapshots, carriers, identities)
    partial = (
        any(snapshot.pruned for snapshot in snapshots)
        or ambiguous > 0
        or excluded > 0
        or any(
            edge.status in {"unresolved", "ambiguous", "pruned"} for edge, _ in edges
        )
    )
    values: dict[str, object] = {
        "enabled_owner_count": len(snapshots),
        "bound_channel_count": sum(item.bound_channel_count for item in snapshots),
        "entry_count": len(entries),
        "record_acquisition_count": sum(
            1 for e in entries if e.acquisition_channel == "record"
        ),
        "transmission_acquisition_count": sum(
            1 for e in entries if e.acquisition_channel == "transmission"
        ),
        "teaching_acquisition_count": sum(
            1 for e in entries if e.acquisition_channel == "teaching"
        ),
        "partial_entry_count": sum(1 for e in entries if e.partial),
        "ignored_entry_count": sum(1 for e in entries if e.ignored),
        "consulted_entry_count": sum(item.consulted_entry_count for item in snapshots),
        "cross_occupant_opportunity_count": opportunities,
        "cross_occupant_acquired_count": acquired,
        "ambiguous_alignment_count": ambiguous,
        "excluded_alignment_count": excluded,
        "partial_coverage": partial,
        "as_of_tick": require_exact_nonneg_int("tick", tick),
    }
    return _doc(
        family=MetricFamilyId.INSTITUTIONAL_MEMORY_CONTINUITY,
        run_id=run_id,
        input_revision=input_revision,
        snapshots=snapshots,
        values=values,
        availability=_availability(snapshots, partial=partial),
        source_kind="institutional_memory_continuity",
    )


def compute_institutional_memory_provenance(
    rows: object,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
    carrier_rows: object = None,
    identity_rows: object = None,
    office_rows: object = (),
) -> MetricDocument:
    snapshots = _require_snapshots(rows)
    carriers = _require_carrier_rows(carrier_rows)
    identities = _require_identity_rows(identity_rows)
    offices = _require_office_rows(office_rows)
    entries = tuple(entry for snapshot in snapshots for entry in snapshot.entries)
    alignments, _ambiguous, _excluded = _align_channels(snapshots, offices)
    edges = _build_edges(snapshots, carriers, identities)
    statuses = [edge.status for edge, _ in edges]
    pruned = statuses.count("pruned")
    unresolved = statuses.count("unresolved")
    ambiguous = statuses.count("ambiguous")
    partial = (
        any(snapshot.pruned for snapshot in snapshots)
        or pruned > 0
        or unresolved > 0
        or ambiguous > 0
    )
    values: dict[str, object] = {
        "entry_count": len(entries),
        "observed_carrier_edge_count": statuses.count("observed_carrier_path"),
        "declared_only_edge_count": statuses.count("declared_only"),
        "ambiguous_edge_count": ambiguous,
        "unresolved_edge_count": unresolved,
        "pruned_edge_count": pruned,
        "independent_root_count": _independent_root_count(edges),
        "conflicting_claim_count": _conflict_count(snapshots, alignments),
        "partial_coverage": partial,
        "as_of_tick": require_exact_nonneg_int("tick", tick),
    }
    return _doc(
        family=MetricFamilyId.INSTITUTIONAL_MEMORY_PROVENANCE,
        run_id=run_id,
        input_revision=input_revision,
        snapshots=snapshots,
        values=values,
        availability=_availability(snapshots, partial=partial),
        source_kind="institutional_memory_provenance",
    )


def _require_snapshots(rows: object) -> tuple[InstitutionalMemorySnapshot, ...]:
    parsed = _sequence(rows, "rows")
    for item in parsed:
        if type(item) is not InstitutionalMemorySnapshot:
            raise InstitutionalMemoryAnalysisError("invalid_row_type")
    return cast("tuple[InstitutionalMemorySnapshot, ...]", parsed)
