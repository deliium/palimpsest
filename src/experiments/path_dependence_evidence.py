"""Bounded, detached evidence collection for path-dependence experiments.

Collection composes existing exports and adapters. It never advances the
simulation, alters commands, or exposes analysis results to cognition.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.cultural_evolution_evidence import CulturalAnalysisWindow
from analysis.institution_emergence import InstitutionLaneRow
from analysis.models import (
    RelationshipEdgeRow,
    ResourceHoldingRow,
)
from analysis.objective_metrics import applied_actions_from_world_events
from analysis.path_dependence_models import PathDependenceEvidence
from experiments.composition import (
    institution_procedure_rows_from_events,
    institution_role_rows_from_events,
    institution_succession_rows_from_events,
    norm_belief_rows_from_ledgers,
)
from experiments.cultural_evidence import cultural_evolution_inputs_from_capture
from experiments.path_dependence_models import (
    MAX_BOUNDARY_OWNERS,
    MAX_BOUNDARY_ROWS,
    OutcomeWindow,
)
from simulation.cultural_evidence import CulturalBoundaryExport
from simulation.fork_checkpoint import (
    FinalizedResearchBoundary,
)
from simulation.runner import SimulationRunner
from social import RelationshipDimensionState, RelationshipRevision
from social.relationships import RelationshipDimension

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.path_dependence_evidence"
)

CAPTURE_LIMIT_CODE: Final[str] = "outcome_capture_limit"
CAPTURE_PARTIAL_CODE: Final[str] = "outcome_capture_partial"
CAPTURE_ENDPOINT_MISSING: Final[str] = "outcome_endpoint_missing"


@dataclass(frozen=True, slots=True)
class PathDependenceEvidenceCapture:
    boundaries: tuple[FinalizedResearchBoundary, ...]
    gaps: tuple[str, ...]
    truncated: bool

    @property
    def complete(self) -> bool:
        return not self.truncated and not self.gaps


class PathDependenceEvidenceRecorder:
    """Retain only requested boundaries under explicit size limits."""

    __slots__ = (
        "_boundaries",
        "_cadence",
        "_gaps",
        "_max_owners",
        "_max_rows",
        "_requested",
        "_rows",
        "_truncated",
    )

    def __init__(
        self,
        *,
        requested_boundaries: Sequence[int] = (),
        cadence: int | None = None,
        max_owners: int = MAX_BOUNDARY_OWNERS,
        max_rows: int = MAX_BOUNDARY_ROWS,
    ) -> None:
        if cadence is not None and (
            isinstance(cadence, bool)
            or type(cadence) is not int
            or cadence < 1
        ):
            raise ValueError("cadence: must_be_positive_integer")
        for name, value in (
            ("max_owners", max_owners),
            ("max_rows", max_rows),
        ):
            if isinstance(value, bool) or type(value) is not int or value < 1:
                raise ValueError(f"{name}: must_be_positive_integer")
        requested: set[int] = set()
        for tick in requested_boundaries:
            if isinstance(tick, bool) or type(tick) is not int or tick < 0:
                raise ValueError("requested_boundaries: invalid_tick")
            requested.add(tick)
        self._requested = frozenset(requested)
        self._cadence = cadence
        self._max_owners = max_owners
        self._max_rows = max_rows
        self._boundaries: list[FinalizedResearchBoundary] = []
        self._gaps: list[str] = []
        self._rows = 0
        self._truncated = False
        _LOG.debug(
            "path_dependence_recorder_created requested=%s cadence=%s",
            len(requested),
            cadence,
        )

    def accepts(self, boundary_tick: int) -> bool:
        if not self._requested and self._cadence is None:
            return True
        if boundary_tick in self._requested:
            return True
        return self._cadence is not None and boundary_tick % self._cadence == 0

    def capture(self, boundary: FinalizedResearchBoundary) -> bool:
        """Record one complete boundary or an explicit truncation gap."""
        if type(boundary) is not FinalizedResearchBoundary:
            raise TypeError("boundary must be FinalizedResearchBoundary")
        tick = boundary.boundary_tick.value
        if not self.accepts(tick):
            return False
        for existing in self._boundaries:
            if existing.boundary_tick != boundary.boundary_tick:
                continue
            if existing == boundary:
                return True
            raise ValueError("outcome_capture_conflict")
        if self._truncated:
            return False
        incoming = _boundary_row_count(boundary)
        if (
            len(boundary.owners) > self._max_owners
            or self._rows + incoming > self._max_rows
        ):
            self._truncated = True
            self._gaps.append(CAPTURE_LIMIT_CODE)
            _LOG.warning(
                "path_dependence_capture_truncated boundary_tick=%s "
                "reason_code=%s",
                tick,
                CAPTURE_LIMIT_CODE,
            )
            return False
        self._boundaries.append(boundary)
        self._rows += incoming
        _LOG.debug(
            "path_dependence_boundary_captured boundary_tick=%s owner_count=%s "
            "row_count=%s",
            tick,
            len(boundary.owners),
            self._rows,
        )
        return True

    def result(self) -> PathDependenceEvidenceCapture:
        return PathDependenceEvidenceCapture(
            boundaries=tuple(
                sorted(
                    self._boundaries,
                    key=lambda item: item.boundary_tick.value,
                )
            ),
            gaps=tuple(sorted(set(self._gaps))),
            truncated=self._truncated,
        )

    def analysis_evidence(
        self, window: OutcomeWindow
    ) -> PathDependenceEvidence:
        """Project captured boundaries into detached selector inputs."""
        capture = self.result()
        endpoint = window.end_tick.value
        baseline = window.fork_tick.value
        matching = [
            boundary
            for boundary in capture.boundaries
            if boundary.boundary_tick.value == endpoint
        ]
        if len(matching) > 1:
            raise ValueError("outcome_capture_duplicate_endpoint")
        if not matching:
            return PathDependenceEvidence(
                run_id="path-dependence-evidence",
                input_revision="missing-endpoint",
            )
        boundary = matching[0]
        history = tuple(
            item
            for item in capture.boundaries
            if baseline <= item.boundary_tick.value <= endpoint
        )
        ledgers: list[object] = []
        for owner in boundary.owners:
            ledger = owner.norm_ledger
            if ledger is not None:
                ledgers.append(ledger)
        norm_rows = (
            {"belief_rows": norm_belief_rows_from_ledgers(ledgers, tick=endpoint)}
            if ledgers
            else None
        )
        relationship_rows = _relationship_rows(boundary)
        lane_rows = _institution_lane_rows(boundary)
        living_ids = tuple(
            owner.owner_id.value for owner in boundary.owners if owner.living
        )
        entity_to_agent = {
            owner.entity_id.value: owner.owner_id.value
            for owner in boundary.owners
        }
        actions = applied_actions_from_world_events(
            boundary.events, entity_to_agent=entity_to_agent
        )
        cultural_inputs = cultural_evolution_inputs_from_capture(
            tuple(
                _cultural_frame_for(item)
                for item in history
            ),
            run_id=boundary.run_id.value,
            source_revision=boundary.config_fingerprint,
            window=CulturalAnalysisWindow(
                baseline_boundary=baseline,
                end_boundary=endpoint,
            ),
        )
        return PathDependenceEvidence(
            run_id=boundary.run_id.value,
            input_revision=str(boundary.boundary_revision.value),
            norm_rows=norm_rows,
            norm_history=_norm_history(history),
            norm_coverage_complete=bool(living_ids)
            and all(
                owner.norm_ledger is not None
                for owner in boundary.owners
                if owner.living
            ),
            relationship_rows=relationship_rows,
            institution_lane_rows=lane_rows,
            institution_known_person_ids=tuple(
                owner.owner_id.value for owner in boundary.owners
            ),
            institution_complete_search=False,
            cultural_inputs=cultural_inputs,
            resource_holdings=tuple(
                ResourceHoldingRow(
                    agent_id=row.agent_id,
                    value=row.item_count,
                )
                for row in boundary.resource_holdings
            ),
            living_agent_ids=living_ids,
            action_rows=actions,
            action_agent_ids=tuple(
                owner.owner_id.value for owner in boundary.owners
            ),
        )


def _boundary_row_count(boundary: FinalizedResearchBoundary) -> int:
    total = len(boundary.events)
    for owner in boundary.owners:
        total += len(owner.memories)
        total += len(owner.beliefs)
        total += len(owner.belief_histories)
        total += len(owner.relationship_profiles)
        total += len(owner.relationship_histories)
    return total


def _norm_history(
    boundaries: Sequence[FinalizedResearchBoundary],
) -> tuple[object, ...]:
    documents: list[object] = []
    for boundary in boundaries:
        ledgers = [
            owner.norm_ledger
            for owner in boundary.owners
            if owner.norm_ledger is not None
        ]
        if not ledgers:
            continue
        documents.append(
            {
                "rates": {},
                "beliefs": norm_belief_rows_from_ledgers(
                    ledgers, tick=boundary.boundary_tick.value
                ),
            }
        )
    return tuple(documents)


def _relationship_rows(
    boundary: FinalizedResearchBoundary,
) -> tuple[RelationshipEdgeRow, ...]:
    rows: list[RelationshipEdgeRow] = []
    for owner in boundary.owners:
        for _relationship_id, revisions in owner.relationship_histories:
            for revision in revisions:
                rows.append(_relationship_row(revision))
    rows.sort(
        key=lambda row: (
            row.logical_tick,
            row.ordinal,
            row.source_id,
            row.target_id,
        )
    )
    return tuple(rows)


def _relationship_row(revision: RelationshipRevision) -> RelationshipEdgeRow:
    dimensions = {
        state.dimension.value: state
        for state in getattr(revision, "dimensions", ())
    }
    trust = dimensions.get(RelationshipDimension.TRUST.value)
    values = {
        name: (
            float(trust.value)
            if name == "trust" and trust is not None
            else _dimension_value(dimensions, name)
        )
        for name in (
            "trust",
            "fear",
            "affection",
            "debt",
            "respect",
            "resentment",
            "familiarity",
            "dependency",
        )
    }
    return RelationshipEdgeRow(
        source_id=revision.source_id.value,
        target_id=revision.target_id.value,
        logical_tick=revision.logical_tick,
        activation_state=revision.activation_state.value,
        ordinal=revision.ordinal,
        trust_confidence=(
            float(trust.confidence.confidence) if trust is not None else None
        ),
        **values,
    )


def _dimension_value(
    dimensions: Mapping[str, RelationshipDimensionState], name: str
) -> float | None:
    state = dimensions.get(name)
    return None if state is None else float(state.value)


def _institution_lane_rows(
    boundary: FinalizedResearchBoundary,
) -> tuple[InstitutionLaneRow, ...]:
    events = boundary.events
    rows = [
        *institution_role_rows_from_events(events),
        *institution_procedure_rows_from_events(events),
        *institution_succession_rows_from_events(events),
    ]
    rows.sort(
        key=lambda row: (
            row.lane.value,
            row.tick_start,
            row.tick_end,
            row.subject_digest,
        )
    )
    return tuple(rows)


def _cultural_frame_for(boundary: FinalizedResearchBoundary) -> CulturalBoundaryExport:
    owners = tuple(
        owner.cultural_owner
        for owner in boundary.owners
        if owner.cultural_owner is not None
    )
    return CulturalBoundaryExport(
        run_id=boundary.run_id.value,
        boundary_tick=boundary.boundary_tick.value,
        owners=owners,
    )


async def collect_path_dependence_boundary(
    runner: SimulationRunner,
    boundary: int,
    recorder: PathDependenceEvidenceRecorder,
) -> FinalizedResearchBoundary:
    """Compose one public boundary export into a recorder."""
    if isinstance(boundary, bool) or type(boundary) is not int or boundary < 0:
        raise ValueError("boundary: invalid_tick")
    exported = await runner.export_finalized_research_boundary()
    if type(exported) is not FinalizedResearchBoundary:
        raise TypeError("runner did not return a research boundary")
    if exported.boundary_tick.value != boundary:
        raise ValueError(CAPTURE_ENDPOINT_MISSING)
    recorder.capture(exported)
    _LOG.info(
        "path_dependence_boundary_collected boundary_tick=%s owner_count=%s",
        boundary,
        len(exported.owners),
    )
    return exported


__all__ = [
    "CAPTURE_ENDPOINT_MISSING",
    "CAPTURE_LIMIT_CODE",
    "CAPTURE_PARTIAL_CODE",
    "PathDependenceEvidenceCapture",
    "PathDependenceEvidenceRecorder",
    "collect_path_dependence_boundary",
]
