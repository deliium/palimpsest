"""Detached institutional-memory continuity and provenance metrics."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
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
    "InstitutionalIdentityRow",
    "InstitutionalMemoryEntryRow",
    "InstitutionalMemorySnapshot",
    "InstitutionalMemoryTransferEdge",
    "compute_institutional_memory_continuity",
    "compute_institutional_memory_provenance",
    "harvest_institutional_memory_rows",
    "institutional_memory_carrier_rows_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.institutional_memory")


class InstitutionalMemoryAnalysisError(ValueError):
    """Fail-closed analysis error with code-only messages."""


@dataclass(frozen=True, slots=True)
class InstitutionalIdentityRow:
    agent_id: str
    entity_id: str
    first_tick: int
    last_tick: int | None = None


@dataclass(frozen=True, slots=True)
class InstitutionalCarrierRow:
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
class InstitutionalMemoryEntryRow:
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


@dataclass(frozen=True, slots=True)
class InstitutionalMemorySnapshot:
    owner_id: str
    entries: tuple[InstitutionalMemoryEntryRow, ...]
    channel_count: int
    bound_channel_count: int
    use_count: int
    consulted_entry_count: int
    coverage: str


@dataclass(frozen=True, slots=True)
class InstitutionalMemoryTransferEdge:
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
    return getattr(state, "value", "retained")


def _channel_value(provenance: object) -> str:
    channel = getattr(provenance, "immediate_channel", None)
    return getattr(channel, "value", "unknown")


def harvest_institutional_memory_rows(
    ledgers: object,
) -> tuple[InstitutionalMemorySnapshot, ...]:
    """Freeze completed exported ledgers without reading live cognition."""
    if ledgers is None:
        return ()
    if isinstance(ledgers, (str, bytes)) or not hasattr(ledgers, "__iter__"):
        raise InstitutionalMemoryAnalysisError("invalid_ledgers")
    snapshots: list[InstitutionalMemorySnapshot] = []
    for ledger in ledgers:
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        if not isinstance(owner, str):
            raise InstitutionalMemoryAnalysisError("invalid_owner")
        entries_attr = getattr(ledger, "entries", ())
        entries: list[InstitutionalMemoryEntryRow] = []
        for entry in entries_attr:
            provenance = tuple(getattr(entry, "provenance", ()))
            first = provenance[0] if provenance else None
            entries.append(
                InstitutionalMemoryEntryRow(
                    owner_id=owner,
                    entry_id=entry.entry_id,
                    channel_id=getattr(entry, "channel_id", None),
                    acquisition_tick=getattr(entry, "acquisition_tick", 0),
                    acquisition_channel=_channel_value(first),
                    facts=tuple(
                        (fact.subject, fact.predicate, fact.object)
                        for fact in getattr(entry, "facts", ())
                    ),
                    declared_root=getattr(first, "declared_frame_root", None),
                    declared_parent=getattr(first, "declared_frame_parent", None),
                    source_event_id=getattr(first, "occurrence_ref", None),
                    artifact_id=getattr(
                        getattr(first, "artifact_id", None), "value", None
                    ),
                    artifact_revision=getattr(first, "artifact_revision", None),
                    partial=bool(getattr(entry, "partial", False)),
                    ignored=bool(getattr(entry, "ignored", False)),
                    source_state=_source_state(first),
                )
            )
        channels = tuple(getattr(ledger, "channels", ()))
        uses = tuple(getattr(ledger, "uses", ()))
        snapshots.append(
            InstitutionalMemorySnapshot(
                owner_id=owner,
                entries=tuple(entries),
                channel_count=len(channels),
                bound_channel_count=sum(
                    1 for channel in channels if getattr(channel, "channel_id", None)
                ),
                use_count=len(uses),
                consulted_entry_count=sum(
                    1
                    for use in uses
                    if getattr(getattr(use, "disposition", None), "value", None)
                    == "consulted"
                ),
                coverage="partial"
                if entries and any(e.partial for e in entries)
                else "complete",
            )
        )
    return tuple(snapshots)


def institutional_memory_carrier_rows_from_events(
    events: object,
) -> tuple[InstitutionalCarrierRow, ...]:
    """Project only completed public event values; no cognition payloads."""
    if events is None:
        return ()
    rows: list[InstitutionalCarrierRow] = []
    for event in cast("Iterable[object]", events):
        kind = getattr(event, "kind", None)
        kind_value = getattr(kind, "value", kind)
        if kind_value not in {
            "talked",
            "asked",
            "told",
            "artifact_created",
            "artifact_modified",
            "artifact_annotated",
            "artifact_damaged",
            "artifact_partially_lost",
            "artifact_copied",
        }:
            continue
        details = getattr(event, "details", None)
        rows.append(
            InstitutionalCarrierRow(
                run_id=getattr(getattr(event, "run_id", None), "value", "run"),
                event_id=getattr(getattr(event, "event_id", None), "value", "event"),
                tick=getattr(event, "tick", 0),
                sequence=getattr(event, "sequence", 0),
                kind=str(kind_value),
                actor_entity_id=getattr(
                    getattr(event, "actor_id", None), "value", "unknown"
                ),
                recipient_entity_id=getattr(
                    getattr(details, "recipient_id", None), "value", None
                ),
                artifact_id=getattr(
                    getattr(details, "artifact_id", None), "value", None
                ),
                content_revision=getattr(details, "content_revision", None),
                parent_artifact_id=getattr(
                    getattr(details, "parent_artifact_id", None), "value", None
                ),
                source_artifact_id=getattr(
                    getattr(details, "source_artifact_id", None), "value", None
                ),
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.tick, row.sequence, row.event_id)))


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
) -> MetricAvailability:
    if not snapshots:
        return MetricAvailability.ABSENT
    if any(item.coverage == "partial" for item in snapshots):
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


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
    _ = carrier_rows, identity_rows, office_rows
    entries = tuple(entry for snapshot in snapshots for entry in snapshot.entries)
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
        "cross_occupant_opportunity_count": 0,
        "cross_occupant_acquired_count": 0,
        "ambiguous_alignment_count": 0,
        "excluded_alignment_count": 0,
        "partial_coverage": _availability(snapshots) is MetricAvailability.PARTIAL,
        "as_of_tick": require_exact_nonneg_int("tick", tick),
    }
    return _doc(
        family=MetricFamilyId.INSTITUTIONAL_MEMORY_CONTINUITY,
        run_id=run_id,
        input_revision=input_revision,
        snapshots=snapshots,
        values=values,
        availability=_availability(snapshots),
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
    _ = carrier_rows, identity_rows, office_rows
    entries = tuple(entry for snapshot in snapshots for entry in snapshot.entries)
    observed = 0
    declared_only = 0
    for entry in entries:
        if entry.artifact_id is not None or entry.source_event_id is not None:
            observed += 1
        elif entry.declared_root is not None:
            declared_only += 1
    values: dict[str, object] = {
        "entry_count": len(entries),
        "observed_carrier_edge_count": observed,
        "declared_only_edge_count": declared_only,
        "ambiguous_edge_count": 0,
        "unresolved_edge_count": sum(
            1 for e in entries if e.declared_root is None and e.artifact_id is None
        ),
        "pruned_edge_count": sum(1 for e in entries if e.source_state == "pruned"),
        "independent_root_count": len(
            {
                (e.artifact_id, e.source_event_id)
                for e in entries
                if e.artifact_id is not None or e.source_event_id is not None
            }
        ),
        "conflicting_claim_count": 0,
        "partial_coverage": _availability(snapshots) is MetricAvailability.PARTIAL,
        "as_of_tick": require_exact_nonneg_int("tick", tick),
    }
    return _doc(
        family=MetricFamilyId.INSTITUTIONAL_MEMORY_PROVENANCE,
        run_id=run_id,
        input_revision=input_revision,
        snapshots=snapshots,
        values=values,
        availability=_availability(snapshots),
        source_kind="institutional_memory_provenance",
    )


def _require_snapshots(rows: object) -> tuple[InstitutionalMemorySnapshot, ...]:
    if rows is None:
        return ()
    if isinstance(rows, (str, bytes)) or not hasattr(rows, "__iter__"):
        raise InstitutionalMemoryAnalysisError("invalid_rows")
    snapshots = tuple(rows)
    for item in snapshots:
        if type(item) is not InstitutionalMemorySnapshot:
            raise InstitutionalMemoryAnalysisError("invalid_row_type")
    return snapshots
