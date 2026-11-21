"""Context joins for scientific-knowledge diffusion.

Only exact, run-qualified references create a context edge. V3 knowledge entry
links point back to the existing genealogy node; they never rewrite that graph.
Organization, migration, society, and translation joins annotate one carrier
occurrence and remain analytical.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

from analysis.knowledge_genealogy import build_qualified_knowledge_lineage
from analysis.science_diffusion_contract import (
    DiffusionContextFlag,
    DiffusionError,
    DiffusionLane,
    DiffusionOccurrence,
    DiffusionReason,
    DiffusionResolution,
    DiffusionStage,
    ScienceVersion,
    ScienceVersionKey,
)
from simulation import ObjectiveFacts
from simulation.fork_checkpoint import FinalizedResearchBoundary
from simulation.models import RunId

__all__ = [
    "GenealogyContext",
    "MigrationQualification",
    "OrganizationContextWindow",
    "OrganizationalService",
    "ScienceDiffusionContextJoin",
    "SocietyAssignment",
    "SocietyContextWindow",
    "TranslationApplication",
    "join_science_diffusion_context",
    "organization_context_present",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.science_diffusion_genealogy"
)

@dataclass(frozen=True, slots=True)
class _EntryAudit:
    owner_id: Any
    entry_id: str
    kind: str
    content_key: str
    origin: str
    parent_entry_ids: tuple[str, ...]
    lineage_root_id: str
    hop_index: int
    mutated: bool
    acquired_tick: int
    tick: int
    active: bool
    reason_code: str
    capability_anchor: str | None
    source_agent_id: str | None
    teacher_agent_id: str | None


_CONTEXT_WINDOW_TICKS: Final[int] = 32


@dataclass(frozen=True, slots=True)
class OrganizationalService:
    """One exact organization contributor and optional carrier service."""

    owner_id: str
    contributor: bool
    candidate_id: str
    service_carrier_id: str = ""
    service_content_revision: int | None = None
    expires_tick: int | None = None


@dataclass(frozen=True, slots=True)
class OrganizationContextWindow:
    """Absolute complete organization window with exact contributors."""

    start_tick: int
    end_tick_exclusive: int
    candidates: tuple[tuple[str, tuple[OrganizationalService, ...]], ...]

    def __post_init__(self) -> None:
        if self.end_tick_exclusive <= self.start_tick:
            raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
        if self.end_tick_exclusive - self.start_tick != _CONTEXT_WINDOW_TICKS:
            raise DiffusionError(DiffusionReason.COVERAGE_GAP.value)


@dataclass(frozen=True, slots=True)
class SocietyAssignment:
    """One owner's unique assignment in an absolute society window."""

    owner_id: str
    candidate_id: str


@dataclass(frozen=True, slots=True)
class SocietyContextWindow:
    """Absolute complete macro-society window with reserved owner assignments."""

    start_tick: int
    end_tick_exclusive: int
    assignments: tuple[SocietyAssignment, ...]

    def __post_init__(self) -> None:
        if self.end_tick_exclusive <= self.start_tick:
            raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
        if self.end_tick_exclusive - self.start_tick != _CONTEXT_WINDOW_TICKS:
            raise DiffusionError(DiffusionReason.COVERAGE_GAP.value)


@dataclass(frozen=True, slots=True)
class MigrationQualification:
    """Same-owner carriage witnessed from departure to a qualified arrival."""

    owner_id: str
    version_key: ScienceVersionKey
    departure_tick: int
    arrival_tick: int
    qualified_boundary: int
    journey_id: str
    completed: bool = True
    alive_on_arrival: bool = True


@dataclass(frozen=True, slots=True)
class TranslationApplication:
    """One addressed translation application bound to a real message."""

    message_id: str
    mapping_id: str
    source_digest: str
    owner_id: str
    applied: bool
    ambiguous: bool = False
    target_binding_witnessed: bool = False


@dataclass(frozen=True, slots=True)
class GenealogyContext:
    """One exact link to an existing V3 knowledge-genealogy node."""

    transmission_key: str
    v3_node_key: str
    origin: str
    relation: str
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class ScienceDiffusionContextJoin:
    """Annotated occurrences, genealogy links, and per-lane availability."""

    occurrences: tuple[DiffusionOccurrence, ...]
    genealogy: tuple[GenealogyContext, ...]
    organization_state: str
    migration_state: str
    society_state: str
    translation_state: str
    diagnostics: tuple[str, ...] = ()


def organization_context_present(
    boundary: FinalizedResearchBoundary,
) -> bool:
    """Return whether any owner retained organization concepts at this boundary."""

    for owner in boundary.owners:
        checkpoint = owner.runtime_checkpoint
        if checkpoint is None:
            continue
        if getattr(checkpoint, "organization_concepts", None) is not None:
            return True
    return False


def _occurrence_key(occurrence: DiffusionOccurrence) -> str:
    return occurrence.evidence.qualified_key().__repr__()


def _latest_window(
    windows: Sequence[OrganizationContextWindow | SocietyContextWindow],
    *,
    tick: int,
    kind: str,
) -> OrganizationContextWindow | SocietyContextWindow | None:
    eligible = [
        row
        for row in windows
        if getattr(row, "end_tick_exclusive", 0) <= tick
        and tick - getattr(row, "end_tick_exclusive", 0) <= _CONTEXT_WINDOW_TICKS
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda row: row.end_tick_exclusive)


def _practical_audits(
    boundary: FinalizedResearchBoundary,
) -> tuple[tuple[object, ...], dict[tuple[str, str], tuple[str, ...]]]:
    audits: list[object] = []
    refs_by_entry: dict[tuple[str, str], tuple[str, ...]] = {}
    for owner in boundary.owners:
        checkpoint = owner.runtime_checkpoint
        if checkpoint is None:
            continue
        ledger = getattr(checkpoint, "practical_knowledge", None)
        entries = getattr(ledger, "entries", ())
        for entry in entries:
            audits.append(
                _EntryAudit(
                    owner_id=entry.owner_id,
                    entry_id=entry.entry_id,
                    kind=getattr(entry.kind, "value", entry.kind),
                    content_key=entry.content_key,
                    origin=getattr(entry.origin, "value", entry.origin),
                    parent_entry_ids=tuple(entry.parent_entry_ids),
                    lineage_root_id=entry.lineage_root_id,
                    hop_index=entry.hop_index,
                    mutated=entry.mutated,
                    acquired_tick=entry.acquired_tick,
                    tick=entry.acquired_tick,
                    active=entry.active,
                    reason_code="diffusion_context",
                    capability_anchor=getattr(entry, "capability_anchor", None),
                    source_agent_id=(
                        None
                        if entry.source_agent_id is None
                        else entry.source_agent_id.value
                    ),
                    teacher_agent_id=(
                        None
                        if entry.teacher_agent_id is None
                        else entry.teacher_agent_id.value
                    ),
                )
            )
            refs_by_entry[(entry.owner_id.value, entry.entry_id)] = tuple(
                entry.evidence_refs
            )
    return tuple(audits), refs_by_entry


def _v3_links(
    boundary: FinalizedResearchBoundary,
    occurrences: Sequence[DiffusionOccurrence],
) -> tuple[tuple[GenealogyContext, ...], tuple[str, ...]]:
    run_id = boundary.run_id.value
    audits, refs_by_entry = _practical_audits(boundary)
    if not audits:
        anchored = any(
            _entry_refs(row)
            for row in occurrences
            if row.lane in {DiffusionLane.TEACHING, DiffusionLane.RECORDS}
        )
        if anchored:
            return (), (DiffusionReason.GENEALOGY_ANCHOR_MISSING.value,)
        return (), ()
    projection = build_qualified_knowledge_lineage(
        audits,
        run_id=RunId(run_id),
        as_of_tick=boundary.boundary_tick.value,
    )
    node_keys: dict[tuple[str, str], str] = {}
    for node in projection.nodes:
        owner = node.ref.identity_owner
        native = node.ref.native_id
        if owner is None:
            continue
        node_keys[(owner, native)] = f"knowledge:{owner}:{native}"
    entry_audits = tuple(audits)
    links: list[GenealogyContext] = []
    diagnostics: list[str] = []
    for occurrence in occurrences:
        if occurrence.lane not in {DiffusionLane.TEACHING, DiffusionLane.RECORDS}:
            continue
        if occurrence.resolution is not DiffusionResolution.CONFIRMED:
            continue
        owner = (
            occurrence.counterparty_id
            if occurrence.lane is DiffusionLane.TEACHING
            else occurrence.actor_id
        )
        if owner is None:
            continue
        refs = _entry_refs(occurrence)
        if not refs:
            continue
        matches = [
            row
            for row in entry_audits
            if getattr(getattr(row, "owner_id", None), "value", None) == owner
            and getattr(row, "active", False)
            and getattr(row, "acquired_tick", 0) >= occurrence.tick
            and bool(
                set(
                    refs_by_entry.get(
                        (owner, getattr(row, "entry_id", "")), ()
                    )
                ).intersection(refs)
            )
        ]
        if not matches:
            diagnostics.append(DiffusionReason.GENEALOGY_ANCHOR_MISSING.value)
            continue
        roots = {
            (getattr(row, "lineage_root_id", ""), getattr(row, "entry_id", ""))
            for row in matches
        }
        ambiguous = len({root for root, _ in roots}) > 1
        chosen = sorted(matches, key=lambda row: (getattr(row, "entry_id", ""),))[0]
        entry_id = getattr(chosen, "entry_id", "")
        node_key = node_keys.get((owner, entry_id))
        if node_key is None:
            diagnostics.append(DiffusionReason.GENEALOGY_ANCHOR_MISSING.value)
            continue
        links.append(
            GenealogyContext(
                transmission_key=_occurrence_key(occurrence),
                v3_node_key=node_key,
                origin=getattr(chosen, "origin", "unknown"),
                relation=(
                    "teaching_uptake"
                    if occurrence.lane is DiffusionLane.TEACHING
                    else "written_record_uptake"
                ),
                ambiguous=ambiguous,
            )
        )
    return tuple(sorted(links, key=lambda row: row.transmission_key)), tuple(
        sorted(set(diagnostics))
    )


def _entry_refs(occurrence: DiffusionOccurrence) -> tuple[str, ...]:
    if occurrence.lane is DiffusionLane.TEACHING:
        return (f"teach:{occurrence.evidence.event_id}",)
    if occurrence.lane is DiffusionLane.RECORDS and occurrence.carrier_id:
        return (
            f"artifact:{occurrence.carrier_id}",
            f"durable:{occurrence.carrier_id}",
        )
    return ()


def _organization_flags(
    windows: Sequence[OrganizationContextWindow],
    occurrences: Sequence[DiffusionOccurrence],
) -> tuple[dict[int, tuple[DiffusionContextFlag, ...]], tuple[str, ...]]:
    flags: dict[int, tuple[DiffusionContextFlag, ...]] = {}
    diagnostics: list[str] = []
    for index, occurrence in enumerate(occurrences):
        window = _latest_window(windows, tick=occurrence.tick, kind="organization")
        if window is None:
            continue
        assert isinstance(window, OrganizationContextWindow)
        participants = [
            (candidate_id, service)
            for candidate_id, services in window.candidates
            for service in services
            if service.owner_id in {occurrence.actor_id, occurrence.counterparty_id}
            and service.contributor
            and (
                service.expires_tick is None
                or occurrence.tick < service.expires_tick
            )
        ]
        candidate_ids = {candidate_id for candidate_id, _ in participants}
        if len(candidate_ids) > 1:
            diagnostics.append(DiffusionReason.OVERLAPPING_MEMBERSHIP.value)
            continue
        if not candidate_ids:
            diagnostics.append(DiffusionReason.MEMBERSHIP_UNKNOWN.value)
            continue
        candidate_id = next(iter(candidate_ids))
        services = [
            service
            for _, service in participants
            if service.service_carrier_id == occurrence.carrier_id
            and service.service_content_revision == occurrence.content_revision
        ]
        if (
            occurrence.carrier_id
            and occurrence.content_revision is not None
            and services
        ):
            flags[index] = (DiffusionContextFlag.ORGANIZATION_MEDIATED,)
        else:
            flags[index] = (DiffusionContextFlag.SHARED_ORG_CONTEXT,)
        _ = candidate_id
    return flags, tuple(sorted(set(diagnostics)))


def _society_flags(
    windows: Sequence[SocietyContextWindow],
    occurrences: Sequence[DiffusionOccurrence],
) -> tuple[dict[int, tuple[DiffusionContextFlag, ...]], tuple[str, ...]]:
    flags: dict[int, tuple[DiffusionContextFlag, ...]] = {}
    diagnostics: list[str] = []
    for index, occurrence in enumerate(occurrences):
        if occurrence.actor_id is None or occurrence.counterparty_id is None:
            continue
        window = _latest_window(windows, tick=occurrence.tick, kind="society")
        if window is None:
            continue
        assert isinstance(window, SocietyContextWindow)
        assignments: dict[str, set[str]] = {}
        for row in window.assignments:
            assignments.setdefault(row.owner_id, set()).add(row.candidate_id)
        actor = assignments.get(occurrence.actor_id, set())
        recipient = assignments.get(occurrence.counterparty_id, set())
        if len(actor) != 1 or len(recipient) != 1:
            diagnostics.append(DiffusionReason.MEMBERSHIP_UNKNOWN.value)
            continue
        left = next(iter(actor))
        right = next(iter(recipient))
        if left == right:
            continue
        flags[index] = (DiffusionContextFlag.CROSS_SOCIETY,)
    return flags, tuple(sorted(set(diagnostics)))


def _migration_occurrences(
    qualifications: Sequence[MigrationQualification],
    occurrences: Sequence[DiffusionOccurrence],
    observed_boundary: int,
) -> tuple[tuple[DiffusionOccurrence, ...], tuple[str, ...]]:
    rows: list[DiffusionOccurrence] = []
    diagnostics: list[str] = []
    for row in qualifications:
        if not row.completed or not row.alive_on_arrival:
            diagnostics.append(DiffusionReason.UNQUALIFIED_ARRIVAL.value)
            continue
        if row.qualified_boundary <= 0:
            diagnostics.append(DiffusionReason.UNQUALIFIED_ARRIVAL.value)
            continue
        source = next(
            (
                item
                for item in occurrences
                if item.source_version == row.version_key
            ),
            None,
        )
        if source is None:
            continue
        rows.append(
            DiffusionOccurrence(
                run_id=source.run_id,
                lane=DiffusionLane.MIGRATION,
                occurrence_kind="qualified_carriage",
                tick=row.qualified_boundary,
                first_observed_boundary=max(observed_boundary, row.qualified_boundary),
                evidence=source.evidence,
                stage=DiffusionStage.CARRIED,
                confirmation_boundary=max(
                    observed_boundary, row.qualified_boundary
                ),
                actor_id=row.owner_id,
                source_version=row.version_key,
                context_flags=(DiffusionContextFlag.CARRIED_ACROSS_REGION,),
                detail=(
                    ("arrival_tick", str(row.arrival_tick)),
                    ("departure_tick", str(row.departure_tick)),
                    ("journey", row.journey_id),
                ),
            )
        )
    return tuple(rows), tuple(sorted(set(diagnostics)))


def _translation_flags(
    applications: Sequence[TranslationApplication],
    occurrences: Sequence[DiffusionOccurrence],
) -> tuple[
    dict[int, tuple[DiffusionContextFlag, ...]],
    dict[int, DiffusionReason],
    tuple[str, ...],
]:
    flags: dict[int, tuple[DiffusionContextFlag, ...]] = {}
    reasons: dict[int, DiffusionReason] = {}
    diagnostics: list[str] = []
    by_message: dict[str, list[TranslationApplication]] = {}
    for row in applications:
        by_message.setdefault(row.message_id, []).append(row)
    for index, occurrence in enumerate(occurrences):
        event_id = occurrence.evidence.event_id
        if event_id is None:
            continue
        rows = by_message.get(event_id, ())
        if not rows:
            continue
        if any(row.ambiguous for row in rows):
            reasons[index] = DiffusionReason.TRANSLATION_UNBOUND
            diagnostics.append(DiffusionReason.TRANSLATION_UNBOUND.value)
            continue
        applied = [
            row
            for row in rows
            if row.applied and row.target_binding_witnessed
        ]
        if len(applied) == 1:
            flags[index] = (DiffusionContextFlag.TRANSLATION_APPLIED,)
        elif len(applied) > 1:
            reasons[index] = DiffusionReason.TRANSLATION_UNBOUND
            diagnostics.append(DiffusionReason.TRANSLATION_UNBOUND.value)
    return flags, reasons, tuple(sorted(set(diagnostics)))


def join_science_diffusion_context(
    boundary: FinalizedResearchBoundary,
    inventory: ObjectiveFacts,
    *,
    occurrences: Sequence[DiffusionOccurrence],
    versions: Sequence[ScienceVersion],
    organization_windows: Sequence[OrganizationContextWindow] = (),
    society_windows: Sequence[SocietyContextWindow] = (),
    migration_qualifications: Sequence[MigrationQualification] = (),
    translation_applications: Sequence[TranslationApplication] = (),
    observed_boundary: int | None = None,
) -> ScienceDiffusionContextJoin:
    """Annotate carrier occurrences with exact V3/V4 context evidence."""

    _ = inventory
    observed = (
        boundary.boundary_tick.value
        if observed_boundary is None
        else observed_boundary
    )
    diagnostics: list[str] = []
    organization_flags, org_diagnostics = _organization_flags(
        organization_windows, occurrences
    )
    diagnostics.extend(org_diagnostics)
    society_flags, society_diagnostics = _society_flags(
        society_windows, occurrences
    )
    diagnostics.extend(society_diagnostics)
    translation_flags, translation_reasons, translation_diagnostics = (
        _translation_flags(translation_applications, occurrences)
    )
    diagnostics.extend(translation_diagnostics)

    annotated: list[DiffusionOccurrence] = []
    for index, occurrence in enumerate(occurrences):
        flags = set(occurrence.context_flags)
        flags.update(organization_flags.get(index, ()))
        flags.update(society_flags.get(index, ()))
        flags.update(translation_flags.get(index, ()))
        reason = occurrence.reason
        resolution = occurrence.resolution
        if index in translation_reasons:
            reason = translation_reasons[index]
            resolution = DiffusionResolution.AMBIGUOUS
        if tuple(sorted(flags)) == occurrence.context_flags and (
            reason == occurrence.reason and resolution == occurrence.resolution
        ):
            annotated.append(occurrence)
            continue
        annotated.append(
            replace(
                occurrence,
                context_flags=tuple(sorted(flags)),
                reason=reason,
                resolution=resolution,
            )
        )

    migration_rows, migration_diagnostics = _migration_occurrences(
        migration_qualifications, occurrences, observed
    )
    diagnostics.extend(migration_diagnostics)
    annotated.extend(migration_rows)

    genealogy, genealogy_diagnostics = _v3_links(boundary, annotated)
    diagnostics.extend(genealogy_diagnostics)

    organization_state = (
        "complete"
        if organization_context_present(boundary)
        else "unavailable"
    )
    migration_state = "complete" if migration_qualifications else "unavailable"
    society_state = "complete" if society_windows else "unavailable"
    translation_state = (
        "complete" if translation_applications else "unavailable"
    )
    _LOG.debug(
        "science_diffusion_context_joined run_id=%s occurrences=%s genealogy=%s "
        "diagnostics=%s",
        boundary.run_id.value,
        len(annotated),
        len(genealogy),
        len(set(diagnostics)),
    )
    return ScienceDiffusionContextJoin(
        occurrences=tuple(sorted(annotated, key=lambda row: row.sort_key())),
        genealogy=genealogy,
        organization_state=organization_state,
        migration_state=migration_state,
        society_state=society_state,
        translation_state=translation_state,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
