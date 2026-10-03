"""Causal debugger lineage enrichment ports and closed summary DTOs.

Read-only drill-down navigators over previously stored subjective provenance.
No SQL here — persistence adapters implement these ports in Task 5.

Forbidden on all lineage DTOs: CoT, prompts, raw responses, proposition /
narrative / utterance text bodies, credentials.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from agents.models import AgentId
from simulation.causal_debugger import (
    CausalDebuggerError,
    CausalTraceAvailability,
    CounterfactualNodeMaterial,
    CounterfactualSourceKind,
    DebuggerFocusHandle,
    DebuggerLineageKind,
    reject_forbidden_debugger_attributes,
    select_counterfactual_material,
)
from simulation.clock import require_exact_nonneg_int
from simulation.cognition_trace import CognitionTraceInvocation
from simulation.models import RunId
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("simulation.debugger_lineage")

__all__ = [
    "BeliefEvidenceLineage",
    "BeliefEvidenceLineagePort",
    "CommunicationLineage",
    "CommunicationLineagePort",
    "DebuggerLineageEntry",
    "DebuggerLineageResponse",
    "GoalAncestryLineage",
    "GoalAncestryLineagePort",
    "InMemoryBeliefEvidenceLineage",
    "InMemoryCommunicationLineage",
    "InMemoryGoalAncestryLineage",
    "InMemoryMemoryDerivationLineage",
    "InMemoryNarrativeLineage",
    "InMemoryPredictionProvenance",
    "MemoryDerivationLineage",
    "MemoryDerivationLineagePort",
    "NarrativeLineage",
    "NarrativeLineagePort",
    "PredictionProvenance",
    "PredictionProvenancePort",
    "assemble_prediction_provenance",
    "project_goal_ancestry_from_checkpoint",
    "project_narrative_lineage_from_checkpoint",
    "require_lineage_kind",
]


@dataclass(frozen=True, slots=True)
class DebuggerLineageEntry:
    """One closed lineage summary row (ids / codes / optional focus only)."""

    entry_id: str
    kind: DebuggerLineageKind
    related_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    counts: Mapping[str, int] | None = None
    focus_handles: tuple[DebuggerFocusHandle, ...] = ()
    parent_ids: tuple[str, ...] = ()
    status_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "entry_id",
            require_stable_id("DebuggerLineageEntry.entry_id", self.entry_id),
        )
        if type(self.kind) is not DebuggerLineageKind:
            raise TypeError("DebuggerLineageEntry.kind must be DebuggerLineageKind")
        object.__setattr__(
            self,
            "related_ids",
            tuple(
                require_stable_id("DebuggerLineageEntry.related_id", item)
                for item in self.related_ids
            ),
        )
        object.__setattr__(
            self,
            "reason_codes",
            tuple(
                require_stable_id("DebuggerLineageEntry.reason_code", item)
                for item in self.reason_codes
            ),
        )
        object.__setattr__(
            self,
            "parent_ids",
            tuple(
                require_stable_id("DebuggerLineageEntry.parent_id", item)
                for item in self.parent_ids
            ),
        )
        if self.status_code is not None:
            object.__setattr__(
                self,
                "status_code",
                require_stable_id(
                    "DebuggerLineageEntry.status_code", self.status_code
                ),
            )
        if self.counts is not None:
            normalized: dict[str, int] = {}
            for key, raw in self.counts.items():
                normalized[
                    require_stable_id("DebuggerLineageEntry.counts.key", key)
                ] = require_exact_nonneg_int("DebuggerLineageEntry.counts.value", raw)
            object.__setattr__(self, "counts", normalized)
        for handle in self.focus_handles:
            if type(handle) is not DebuggerFocusHandle:
                raise TypeError(
                    "DebuggerLineageEntry.focus_handles must be DebuggerFocusHandle"
                )
        reject_forbidden_debugger_attributes(self, type_name="DebuggerLineageEntry")


@dataclass(frozen=True, slots=True)
class DebuggerLineageResponse:
    """Owner-scoped lineage navigator payload."""

    run_id: RunId
    owner_id: AgentId
    kind: DebuggerLineageKind
    subject_id: str
    availability: CausalTraceAvailability
    entries: tuple[DebuggerLineageEntry, ...] = ()
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("DebuggerLineageResponse.run_id must be RunId")
        if type(self.owner_id) is not AgentId:
            raise TypeError("DebuggerLineageResponse.owner_id must be AgentId")
        if type(self.kind) is not DebuggerLineageKind:
            raise TypeError("DebuggerLineageResponse.kind must be DebuggerLineageKind")
        if type(self.availability) is not CausalTraceAvailability:
            raise TypeError(
                "DebuggerLineageResponse.availability must be CausalTraceAvailability"
            )
        object.__setattr__(
            self,
            "subject_id",
            require_stable_id("DebuggerLineageResponse.subject_id", self.subject_id),
        )
        if self.reason_code is not None:
            object.__setattr__(
                self,
                "reason_code",
                require_stable_id(
                    "DebuggerLineageResponse.reason_code", self.reason_code
                ),
            )
        for entry in self.entries:
            if type(entry) is not DebuggerLineageEntry:
                raise TypeError(
                    "DebuggerLineageResponse.entries must be DebuggerLineageEntry"
                )
        reject_forbidden_debugger_attributes(
            self, type_name="DebuggerLineageResponse"
        )
        _LOG.debug(
            "debugger_lineage_response kind=%s run_id=%s owner_id=%s "
            "subject_id=%s entry_count=%s availability=%s",
            self.kind.value,
            self.run_id.value,
            self.owner_id.value,
            self.subject_id,
            len(self.entries),
            self.availability.value,
        )


# Type aliases documenting navigator-specific response shapes (same DTO).
BeliefEvidenceLineage = DebuggerLineageResponse
MemoryDerivationLineage = DebuggerLineageResponse
CommunicationLineage = DebuggerLineageResponse
NarrativeLineage = DebuggerLineageResponse
GoalAncestryLineage = DebuggerLineageResponse
PredictionProvenance = DebuggerLineageResponse


class BeliefEvidenceLineagePort(Protocol):
    async def belief_evidence(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> BeliefEvidenceLineage:
        """Return evidence memory ids for one owner-scoped belief."""


class MemoryDerivationLineagePort(Protocol):
    async def memory_derivation(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> MemoryDerivationLineage:
        """Return MemoryLineage-derived ids for one memory / reconstruction."""


class CommunicationLineagePort(Protocol):
    async def communication_lineage(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> CommunicationLineage:
        """Return CommunicatedTransmissionMeta closed fields + delivery focus."""


class NarrativeLineagePort(Protocol):
    async def narrative_lineage(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> NarrativeLineage:
        """Return NarrativeLedger variant parents / competing variants."""


class GoalAncestryLineagePort(Protocol):
    async def goal_ancestry(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> GoalAncestryLineage:
        """Return parent_goal_id chain for one goal (no new goal store)."""


class PredictionProvenancePort(Protocol):
    async def prediction_provenance(
        self,
        *,
        run_id: RunId,
        owner_id: AgentId,
        subject_id: str,
        invocation: CognitionTraceInvocation | None = None,
        harvest: CounterfactualNodeMaterial | None = None,
    ) -> PredictionProvenance:
        """Trace refs first → harvest → unavailable (Task 1c)."""


def assemble_prediction_provenance(
    *,
    run_id: RunId,
    owner_id: AgentId,
    subject_id: str,
    invocation: CognitionTraceInvocation | None,
    harvest: CounterfactualNodeMaterial | None = None,
) -> PredictionProvenance:
    """Pure Task 1c projection for prediction / counterfactual provenance."""
    _LOG.debug(
        "prediction_provenance_entry run_id=%s owner_id=%s subject_id=%s "
        "has_invocation=%s has_harvest=%s",
        run_id.value,
        owner_id.value,
        subject_id,
        invocation is not None,
        harvest is not None,
    )
    if invocation is None:
        response = DebuggerLineageResponse(
            run_id=run_id,
            owner_id=owner_id,
            kind=DebuggerLineageKind.PREDICTION,
            subject_id=subject_id,
            availability=CausalTraceAvailability.UNAVAILABLE,
            reason_code="cognition_trace_missing",
        )
        _LOG.debug(
            "prediction_provenance_exit reason_code=%s entry_count=%s",
            response.reason_code,
            0,
        )
        return response
    material = select_counterfactual_material(invocation, harvest=harvest)
    if material.source is CounterfactualSourceKind.NONE:
        response = DebuggerLineageResponse(
            run_id=run_id,
            owner_id=owner_id,
            kind=DebuggerLineageKind.PREDICTION,
            subject_id=subject_id,
            availability=CausalTraceAvailability.UNAVAILABLE,
            reason_code=material.reason_code or "counterfactual_unavailable",
        )
        _LOG.debug(
            "prediction_provenance_exit reason_code=%s entry_count=%s",
            response.reason_code,
            0,
        )
        return response
    counts: dict[str, int] = {}
    if material.scenario_count is not None:
        counts["scenario_count"] = material.scenario_count
    if material.regret_count is not None:
        counts["regret_count"] = material.regret_count
    if material.relief_count is not None:
        counts["relief_count"] = material.relief_count
    if material.neutral_count is not None:
        counts["neutral_count"] = material.neutral_count
    entry = DebuggerLineageEntry(
        entry_id=subject_id,
        kind=DebuggerLineageKind.PREDICTION,
        related_ids=tuple(value for _, value in material.id_refs),
        reason_codes=material.selection_codes,
        counts=counts or None,
        status_code=material.source.value,
    )
    response = DebuggerLineageResponse(
        run_id=run_id,
        owner_id=owner_id,
        kind=DebuggerLineageKind.PREDICTION,
        subject_id=subject_id,
        availability=CausalTraceAvailability.AVAILABLE,
        entries=(entry,),
    )
    _LOG.debug(
        "prediction_provenance_exit reason_code=%s entry_count=%s source=%s",
        None,
        1,
        material.source.value,
    )
    return response


def _unavailable(
    *,
    run_id: RunId,
    owner_id: AgentId,
    kind: DebuggerLineageKind,
    subject_id: str,
    reason_code: str,
) -> DebuggerLineageResponse:
    return DebuggerLineageResponse(
        run_id=run_id,
        owner_id=owner_id,
        kind=kind,
        subject_id=subject_id,
        availability=CausalTraceAvailability.UNAVAILABLE,
        reason_code=reason_code,
    )


def _stable_id(value: object) -> str | None:
    if value is None:
        return None
    text = str(getattr(value, "value", value)).strip()
    return text or None


def _enum_code(value: object) -> str | None:
    if value is None:
        return None
    code = getattr(value, "value", value)
    text = str(code).strip()
    return text or None


def _focus_from_variant(
    *, run_id: RunId, variant: object
) -> tuple[DebuggerFocusHandle, ...]:
    event_id = _stable_id(getattr(variant, "source_event_id", None))
    if event_id is None:
        return ()
    tick_raw = getattr(variant, "last_tick", None)
    if tick_raw is None:
        tick_raw = getattr(variant, "first_tick", None)
    if tick_raw is None or isinstance(tick_raw, bool) or not isinstance(tick_raw, int):
        return ()
    if tick_raw < 0:
        return ()
    return (
        DebuggerFocusHandle(
            run_id=run_id,
            tick=tick_raw,
            sequence=None,
            event_id=event_id,
        ),
    )


def project_narrative_lineage_from_checkpoint(
    *,
    run_id: RunId,
    owner_id: AgentId,
    subject_id: str,
    checkpoint: object | None,
) -> NarrativeLineage:
    """Project NarrativeLedger parents / competitors from a runtime checkpoint.

    Metadata-only: no content tokens, fingerprints, or narrative text.
    ``subject_id`` is the variant id.
    """
    _LOG.debug(
        "narrative_lineage_entry run_id=%s owner_id=%s subject_id=%s has_checkpoint=%s",
        run_id.value,
        owner_id.value,
        subject_id,
        checkpoint is not None,
    )
    if checkpoint is None:
        return _unavailable(
            run_id=run_id,
            owner_id=owner_id,
            kind=DebuggerLineageKind.NARRATIVE,
            subject_id=subject_id,
            reason_code="checkpoint_unavailable",
        )
    ledger = getattr(checkpoint, "cultural_narratives", None)
    if ledger is None:
        return _unavailable(
            run_id=run_id,
            owner_id=owner_id,
            kind=DebuggerLineageKind.NARRATIVE,
            subject_id=subject_id,
            reason_code="narrative_ledger_missing",
        )
    variants = tuple(getattr(ledger, "variants", ()) or ())
    by_id: dict[str, object] = {}
    for item in variants:
        variant_id = _stable_id(getattr(item, "variant_id", None))
        if variant_id is not None:
            by_id[variant_id] = item
    target = by_id.get(subject_id)
    if target is None:
        _LOG.warning(
            "debugger_lineage_incomplete kind=%s reason_code=%s subject_id=%s",
            "narrative",
            "lineage_not_found",
            subject_id,
        )
        return _unavailable(
            run_id=run_id,
            owner_id=owner_id,
            kind=DebuggerLineageKind.NARRATIVE,
            subject_id=subject_id,
            reason_code="lineage_not_found",
        )

    parent_ids = tuple(
        pid
        for pid in (
            _stable_id(item)
            for item in (getattr(target, "parent_variant_ids", ()) or ())
        )
        if pid is not None
    )
    competing = tuple(
        cid
        for cid in (
            _stable_id(item)
            for item in (getattr(target, "competing_variant_ids", ()) or ())
        )
        if cid is not None
    )
    related = tuple(dict.fromkeys((*parent_ids, *competing)))
    status_code = _enum_code(getattr(target, "status", None))
    origin_code = _enum_code(getattr(target, "origin", None))
    reason_codes: tuple[str, ...] = ()
    if origin_code is not None:
        reason_codes = (f"origin:{origin_code}",)
    entries: list[DebuggerLineageEntry] = [
        DebuggerLineageEntry(
            entry_id=subject_id,
            kind=DebuggerLineageKind.NARRATIVE,
            related_ids=related,
            parent_ids=parent_ids,
            reason_codes=reason_codes,
            counts={
                "parent_count": len(parent_ids),
                "competing_count": len(competing),
            },
            focus_handles=_focus_from_variant(run_id=run_id, variant=target),
            status_code=status_code,
        )
    ]
    for parent_id in parent_ids:
        parent = by_id.get(parent_id)
        if parent is None:
            continue
        entries.append(
            DebuggerLineageEntry(
                entry_id=parent_id,
                kind=DebuggerLineageKind.NARRATIVE,
                related_ids=(subject_id,),
                parent_ids=tuple(
                    pid
                    for pid in (
                        _stable_id(item)
                        for item in (getattr(parent, "parent_variant_ids", ()) or ())
                    )
                    if pid is not None
                ),
                focus_handles=_focus_from_variant(run_id=run_id, variant=parent),
                status_code=_enum_code(getattr(parent, "status", None)),
            )
        )
    response = DebuggerLineageResponse(
        run_id=run_id,
        owner_id=owner_id,
        kind=DebuggerLineageKind.NARRATIVE,
        subject_id=subject_id,
        availability=CausalTraceAvailability.AVAILABLE,
        entries=tuple(entries),
    )
    _LOG.debug(
        "narrative_lineage_exit entry_count=%s parent_count=%s competing_count=%s",
        len(entries),
        len(parent_ids),
        len(competing),
    )
    return response


def project_goal_ancestry_from_checkpoint(
    *,
    run_id: RunId,
    owner_id: AgentId,
    subject_id: str,
    checkpoint: object | None,
) -> GoalAncestryLineage:
    """Project ``parent_goal_id`` ancestry from checkpoint ``goals``.

    Metadata-only: ids, status/horizon codes, counts — never goal descriptions.
    """
    _LOG.debug(
        "goal_ancestry_entry run_id=%s owner_id=%s subject_id=%s has_checkpoint=%s",
        run_id.value,
        owner_id.value,
        subject_id,
        checkpoint is not None,
    )
    if checkpoint is None:
        return _unavailable(
            run_id=run_id,
            owner_id=owner_id,
            kind=DebuggerLineageKind.GOAL_ANCESTRY,
            subject_id=subject_id,
            reason_code="checkpoint_unavailable",
        )
    goals = tuple(getattr(checkpoint, "goals", ()) or ())
    by_id: dict[str, object] = {}
    for goal in goals:
        goal_id = _stable_id(getattr(goal, "goal_id", None))
        if goal_id is not None:
            by_id[goal_id] = goal
    target = by_id.get(subject_id)
    if target is None:
        _LOG.warning(
            "debugger_lineage_incomplete kind=%s reason_code=%s subject_id=%s",
            "goal_ancestry",
            "lineage_not_found",
            subject_id,
        )
        return _unavailable(
            run_id=run_id,
            owner_id=owner_id,
            kind=DebuggerLineageKind.GOAL_ANCESTRY,
            subject_id=subject_id,
            reason_code="lineage_not_found",
        )

    ancestors: list[str] = []
    cursor = _stable_id(getattr(target, "parent_goal_id", None))
    seen: set[str] = {subject_id}
    while cursor is not None and cursor not in seen:
        ancestors.append(cursor)
        seen.add(cursor)
        parent = by_id.get(cursor)
        if parent is None:
            break
        cursor = _stable_id(getattr(parent, "parent_goal_id", None))
    children = tuple(
        sorted(
            gid
            for gid, goal in by_id.items()
            if _stable_id(getattr(goal, "parent_goal_id", None)) == subject_id
        )
    )
    parent_ids = tuple(ancestors)
    related = tuple(dict.fromkeys((*parent_ids, *children)))
    entries: list[DebuggerLineageEntry] = [
        DebuggerLineageEntry(
            entry_id=subject_id,
            kind=DebuggerLineageKind.GOAL_ANCESTRY,
            related_ids=related,
            parent_ids=parent_ids[:1],
            reason_codes=(),
            counts={
                "ancestor_count": len(parent_ids),
                "child_count": len(children),
            },
            status_code=_enum_code(getattr(target, "status", None)),
        )
    ]
    for ancestor_id in parent_ids:
        ancestor = by_id.get(ancestor_id)
        if ancestor is None:
            continue
        entries.append(
            DebuggerLineageEntry(
                entry_id=ancestor_id,
                kind=DebuggerLineageKind.GOAL_ANCESTRY,
                related_ids=(subject_id,),
                parent_ids=tuple(
                    pid
                    for pid in [
                        _stable_id(getattr(ancestor, "parent_goal_id", None))
                    ]
                    if pid is not None
                ),
                status_code=_enum_code(getattr(ancestor, "status", None)),
            )
        )
    response = DebuggerLineageResponse(
        run_id=run_id,
        owner_id=owner_id,
        kind=DebuggerLineageKind.GOAL_ANCESTRY,
        subject_id=subject_id,
        availability=CausalTraceAvailability.AVAILABLE,
        entries=tuple(entries),
    )
    _LOG.debug(
        "goal_ancestry_exit entry_count=%s ancestor_count=%s child_count=%s",
        len(entries),
        len(parent_ids),
        len(children),
    )
    return response


class _InMemoryLineageStore:
    """Shared seed table for lineage fakes keyed by (run, owner, subject)."""

    __slots__ = ("_items", "_kind")

    def __init__(self, kind: DebuggerLineageKind) -> None:
        self._kind = kind
        self._items: dict[
            tuple[str, str, str], DebuggerLineageResponse
        ] = {}

    def seed(self, response: DebuggerLineageResponse) -> None:
        if type(response) is not DebuggerLineageResponse:
            raise TypeError("response must be DebuggerLineageResponse")
        if response.kind is not self._kind:
            raise CausalDebuggerError(
                "invalid_kind",
                f"expected {self._kind.value}, got {response.kind.value}",
            )
        key = (
            response.run_id.value,
            response.owner_id.value,
            response.subject_id,
        )
        self._items[key] = response

    def get(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> DebuggerLineageResponse:
        _LOG.debug(
            "debugger_lineage_port_entry kind=%s run_id=%s owner_id=%s subject_id=%s",
            self._kind.value,
            run_id.value,
            owner_id.value,
            subject_id,
        )
        found = self._items.get((run_id.value, owner_id.value, subject_id))
        if found is None:
            _LOG.warning(
                "debugger_lineage_incomplete kind=%s reason_code=%s subject_id=%s",
                self._kind.value,
                "lineage_not_found",
                subject_id,
            )
            return _unavailable(
                run_id=run_id,
                owner_id=owner_id,
                kind=self._kind,
                subject_id=subject_id,
                reason_code="lineage_not_found",
            )
        _LOG.debug(
            "debugger_lineage_port_exit kind=%s entry_count=%s",
            self._kind.value,
            len(found.entries),
        )
        return found


class InMemoryBeliefEvidenceLineage:
    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store = _InMemoryLineageStore(DebuggerLineageKind.BELIEF_EVIDENCE)

    def seed(self, response: DebuggerLineageResponse) -> None:
        self._store.seed(response)

    async def belief_evidence(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> BeliefEvidenceLineage:
        return self._store.get(
            run_id=run_id, owner_id=owner_id, subject_id=subject_id
        )


class InMemoryMemoryDerivationLineage:
    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store = _InMemoryLineageStore(DebuggerLineageKind.MEMORY_DERIVATION)

    def seed(self, response: DebuggerLineageResponse) -> None:
        self._store.seed(response)

    async def memory_derivation(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> MemoryDerivationLineage:
        return self._store.get(
            run_id=run_id, owner_id=owner_id, subject_id=subject_id
        )


class InMemoryCommunicationLineage:
    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store = _InMemoryLineageStore(DebuggerLineageKind.COMMUNICATION)

    def seed(self, response: DebuggerLineageResponse) -> None:
        self._store.seed(response)

    async def communication_lineage(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> CommunicationLineage:
        return self._store.get(
            run_id=run_id, owner_id=owner_id, subject_id=subject_id
        )


class InMemoryNarrativeLineage:
    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store = _InMemoryLineageStore(DebuggerLineageKind.NARRATIVE)

    def seed(self, response: DebuggerLineageResponse) -> None:
        self._store.seed(response)

    async def narrative_lineage(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> NarrativeLineage:
        return self._store.get(
            run_id=run_id, owner_id=owner_id, subject_id=subject_id
        )


class InMemoryGoalAncestryLineage:
    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store = _InMemoryLineageStore(DebuggerLineageKind.GOAL_ANCESTRY)

    def seed(self, response: DebuggerLineageResponse) -> None:
        self._store.seed(response)

    async def goal_ancestry(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> GoalAncestryLineage:
        return self._store.get(
            run_id=run_id, owner_id=owner_id, subject_id=subject_id
        )


class InMemoryPredictionProvenance:
    """Prediction port that honors Task 1c via assemble_prediction_provenance."""

    __slots__ = ("_harvests", "_invocations")

    def __init__(self) -> None:
        self._invocations: dict[
            tuple[str, str, str], CognitionTraceInvocation
        ] = {}
        self._harvests: dict[
            tuple[str, str, str], CounterfactualNodeMaterial
        ] = {}

    def seed_invocation(
        self,
        *,
        subject_id: str,
        invocation: CognitionTraceInvocation,
    ) -> None:
        key = (
            invocation.run_id.value,
            invocation.agent_id.value,
            subject_id,
        )
        self._invocations[key] = invocation

    def seed_harvest(
        self,
        *,
        run_id: RunId,
        owner_id: AgentId,
        subject_id: str,
        harvest: CounterfactualNodeMaterial,
    ) -> None:
        self._harvests[(run_id.value, owner_id.value, subject_id)] = harvest

    async def prediction_provenance(
        self,
        *,
        run_id: RunId,
        owner_id: AgentId,
        subject_id: str,
        invocation: CognitionTraceInvocation | None = None,
        harvest: CounterfactualNodeMaterial | None = None,
    ) -> PredictionProvenance:
        key = (run_id.value, owner_id.value, subject_id)
        resolved_invocation = invocation or self._invocations.get(key)
        resolved_harvest = harvest or self._harvests.get(key)
        return assemble_prediction_provenance(
            run_id=run_id,
            owner_id=owner_id,
            subject_id=subject_id,
            invocation=resolved_invocation,
            harvest=resolved_harvest,
        )


def require_lineage_kind(value: str) -> DebuggerLineageKind:
    """Parse closed lineage kind or raise ``invalid_kind``."""
    try:
        return DebuggerLineageKind(value)
    except ValueError as exc:
        _LOG.error(
            "debugger_lineage_invalid_kind reason_code=%s kind=%s",
            "invalid_kind",
            value,
        )
        raise CausalDebuggerError(
            "invalid_kind", f"unknown lineage kind {value!r}"
        ) from exc
