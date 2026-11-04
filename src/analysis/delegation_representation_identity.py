"""Stable ``rep-`` identities and forward-only lineage for representation."""

from __future__ import annotations

from dataclasses import dataclass

from analysis.delegation_representation_contract import (
    RepresentationAnalysisError,
    RepresentationLineageKind,
    representation_edge_id,
    require_candidate_id,
)
from analysis.delegation_representation_detection import (
    RepresentationCandidate,
    detect_representation_window_candidates,
)
from analysis.delegation_representation_rows import RepresentationHarvestRows

__all__ = [
    "RepresentationAnalysis",
    "RepresentationLineageEdge",
    "assign_representation_identities",
    "derive_representation_lineage",
]


@dataclass(frozen=True, slots=True)
class RepresentationLineageEdge:
    edge_id: str
    from_candidate_id: str
    to_candidate_id: str
    kind: RepresentationLineageKind
    tick: int

    def __post_init__(self) -> None:
        require_candidate_id(self.from_candidate_id)
        require_candidate_id(self.to_candidate_id)
        if not isinstance(self.kind, RepresentationLineageKind):
            raise RepresentationAnalysisError("representation_invalid_row")
        if type(self.tick) is not int or self.tick < 0:
            raise RepresentationAnalysisError("representation_invalid_row")
        expected = representation_edge_id(
            self.from_candidate_id,
            self.to_candidate_id,
            self.kind.value,
            self.tick,
        )
        if self.edge_id != expected:
            raise RepresentationAnalysisError("representation_lineage_invalid")


@dataclass(frozen=True, slots=True)
class RepresentationAnalysis:
    candidates: tuple[RepresentationCandidate, ...] = ()
    transitions: tuple[RepresentationLineageEdge, ...] = ()


def assign_representation_identities(
    rows: RepresentationHarvestRows,
    detections: tuple[RepresentationCandidate, ...],
) -> RepresentationAnalysis:
    """Assign stable creation-evidence identities to current candidates."""

    if type(rows) is not RepresentationHarvestRows:
        raise TypeError("rows must be RepresentationHarvestRows")
    if not isinstance(detections, tuple):
        raise TypeError("detections must be a tuple")
    if not detections:
        transitions: tuple[RepresentationLineageEdge, ...] = ()
    else:
        tick = max(
            (
                max((row.start_tick for row in rows.mandates), default=0),
                max((row.tick for row in rows.positions), default=0),
            ),
            default=0,
        )
        transitions = tuple(
            RepresentationLineageEdge(
                edge_id=representation_edge_id(
                    candidate.candidate_id,
                    candidate.candidate_id,
                    RepresentationLineageKind.EMERGED.value,
                    tick,
                ),
                from_candidate_id=candidate.candidate_id,
                to_candidate_id=candidate.candidate_id,
                kind=RepresentationLineageKind.EMERGED,
                tick=tick,
            )
            for candidate in detections
        )
    return RepresentationAnalysis(candidates=detections, transitions=transitions)


def derive_representation_lineage(
    rows: RepresentationHarvestRows,
    *,
    objective_rows: tuple[object, ...] = (),
    window_ticks: int = 100,
) -> RepresentationAnalysis:
    """Detect candidates and attach creation-evidence identity."""

    _ = objective_rows, window_ticks
    detections = detect_representation_window_candidates(rows)
    return assign_representation_identities(rows, detections)
