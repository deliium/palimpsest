"""Neutral finalized-boundary lineage capture session over reader/writer ports.

No analytical inference, runner import or concrete storage dependency exists
here. Capture merges previously observed metadata, publishes immutable
snapshots and exposes bounded receipts for the scopes actually committed.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from typing import Final

from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageDirection,
    LineageError,
    LineageNode,
    LineageScope,
    LineageSnapshotRef,
)
from simulation.lineage_ports import (
    CAPTURE_MAX_ARTIFACT_BYTES,
    CAPTURE_MAX_EDGES,
    CAPTURE_MAX_NODES,
    CAPTURE_MAX_NORMALIZED_BYTES,
    CAPTURE_MAX_PUBLICATION_RESERVATIONS,
    LineageBoundaryFrame,
    LineageBoundarySink,
    LineagePublication,
    LineagePublicationPort,
    LineageReadBudget,
    LineageReadPort,
    LineageSourceProjection,
)
from simulation.lineage_subjective import merge_lineage_observations

_LOG: Final[logging.Logger] = logging.getLogger("simulation.lineage_capture")

__all__ = [
    "LineageCaptureOptions",
    "LineageCaptureReceipt",
    "LineageCaptureSession",
    "LineageCaptureStatus",
]


@dataclass(frozen=True, slots=True)
class LineageCaptureOptions:
    """Composition-only capture cadence and bounds."""

    enabled: bool = True
    cadence: int = 1
    capture_start_boundary: int = 0
    max_nodes: int = CAPTURE_MAX_NODES
    max_edges: int = CAPTURE_MAX_EDGES
    max_publications: int = CAPTURE_MAX_PUBLICATION_RESERVATIONS
    max_artifact_bytes: int = CAPTURE_MAX_ARTIFACT_BYTES

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be bool")
        for name, maximum in (
            ("cadence", 1_000),
            ("capture_start_boundary", 1_000_000_000),
            ("max_nodes", CAPTURE_MAX_NODES),
            ("max_edges", CAPTURE_MAX_EDGES),
            ("max_publications", CAPTURE_MAX_PUBLICATION_RESERVATIONS),
            ("max_artifact_bytes", CAPTURE_MAX_ARTIFACT_BYTES),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
            if name in {"cadence", "max_nodes", "max_edges"} and value < 1:
                raise ValueError(f"{name} must be positive")
            if value > maximum:
                raise ValueError(f"{name} exceeds the supported maximum")


@dataclass(frozen=True, slots=True)
class LineageCaptureReceipt:
    scope: LineageScope
    boundary_tick: int
    snapshot: LineageSnapshotRef


@dataclass(frozen=True, slots=True)
class LineageCaptureStatus:
    active: bool
    failed: bool
    last_boundary: int | None
    failure_code: str | None
    receipt_count: int


class LineageCaptureSession(LineageBoundarySink):
    """Sink that merges and publishes finalized owner/objective frames."""

    __slots__ = (
        "_failed",
        "_failure_code",
        "_fingerprints",
        "_last_boundary",
        "_options",
        "_publisher",
        "_reader",
        "_receipts",
    )

    def __init__(
        self,
        *,
        reader: LineageReadPort,
        publisher: LineagePublicationPort,
        options: LineageCaptureOptions | None = None,
    ) -> None:
        self._reader = reader
        self._publisher = publisher
        self._options = options or LineageCaptureOptions()
        self._receipts: list[LineageCaptureReceipt] = []
        self._last_boundary: dict[tuple[str, str, str | None], int] = {}
        self._fingerprints: dict[tuple[tuple[str, str, str | None], int], str] = {}
        self._failed = False
        self._failure_code: str | None = None

    @property
    def status(self) -> LineageCaptureStatus:
        last = max(self._last_boundary.values(), default=None)
        return LineageCaptureStatus(
            active=self._options.enabled and not self._failed,
            failed=self._failed,
            last_boundary=last,
            failure_code=self._failure_code,
            receipt_count=len(self._receipts),
        )

    @property
    def receipts(self) -> tuple[LineageCaptureReceipt, ...]:
        return tuple(self._receipts)

    def receipt_for(
        self, scope: LineageScope, boundary_tick: int
    ) -> LineageSnapshotRef | None:
        for receipt in self._receipts:
            if receipt.scope == scope and receipt.boundary_tick == boundary_tick:
                return receipt.snapshot
        return None

    def _mark_failed(self, code: str) -> None:
        if self._failed:
            return
        self._failed = True
        self._failure_code = code
        _LOG.warning("lineage_capture_stopped reason_code=%s", code)

    async def capture(self, frame: LineageBoundaryFrame) -> LineageSnapshotRef | None:
        if not self._options.enabled or self._failed:
            return None
        if type(frame) is not LineageBoundaryFrame:
            raise ValueError("frame must be LineageBoundaryFrame")
        boundary = frame.boundary_tick
        if boundary < self._options.capture_start_boundary:
            return None
        if self._options.cadence > 1 and boundary % self._options.cadence != 0:
            return None
        key = (
            frame.scope.family.value,
            frame.scope.evidence_class.value,
            frame.scope.owner_id,
        )
        fingerprint = _frame_fingerprint(frame)
        previous_boundary = self._last_boundary.get(key)
        if previous_boundary is not None and boundary <= previous_boundary:
            stored = self._fingerprints.get((key, boundary))
            if stored is not None and stored != fingerprint:
                self._mark_failed("lineage_publication_conflict")
                return None
            return self.receipt_for(frame.scope, boundary)
        if len(frame.nodes) > self._options.max_nodes:
            self._mark_failed("lineage_capture_node_cap")
            return None
        if len(frame.edges) > self._options.max_edges:
            self._mark_failed("lineage_capture_edge_cap")
            return None
        try:
            previous = await self._read_previous(frame.scope)
            current = LineageSourceProjection(
                nodes=frame.nodes,
                edges=frame.edges,
                coverage=frame.coverage,
            )
            if frame.coverage.state is LineageCoverageState.DISABLED:
                merged = current
            else:
                merged = merge_lineage_observations(previous, current, boundary)
            if _projection_size(merged) > CAPTURE_MAX_NORMALIZED_BYTES:
                self._mark_failed("lineage_capture_byte_cap")
                return None
            digest = _projection_digest(merged, boundary)
            publication = LineagePublication(
                snapshot=LineageSnapshotRef(
                    publication_id="placeholder",
                    digest=digest,
                    boundary_tick=boundary,
                ),
                frame=LineageBoundaryFrame(
                    run_id=frame.run_id,
                    scope=frame.scope,
                    boundary_tick=boundary,
                    observed_boundary=frame.observed_boundary,
                    nodes=merged.nodes,
                    edges=merged.edges,
                    coverage=merged.coverage,
                    source_revision=frame.source_revision,
                ),
            )
            snapshot = await self._publisher.publish(publication)
        except LineageError as exc:
            self._mark_failed(exc.code or "lineage_capture_failed")
            return None
        except Exception:
            self._mark_failed("lineage_capture_failed")
            return None
        self._last_boundary[key] = boundary
        self._fingerprints[(key, boundary)] = fingerprint
        self._receipts.append(
            LineageCaptureReceipt(
                scope=frame.scope,
                boundary_tick=boundary,
                snapshot=snapshot,
            )
        )
        _LOG.debug(
            "lineage_boundary_captured run_id=%s family=%s class=%s boundary=%s "
            "node_count=%s edge_count=%s",
            frame.run_id.value,
            frame.scope.family.value,
            frame.scope.evidence_class.value,
            boundary,
            len(merged.nodes),
            len(merged.edges),
        )
        return snapshot

    async def _read_previous(self, scope: LineageScope) -> LineageSourceProjection:
        empty = LineageSourceProjection(
            nodes=(),
            edges=(),
            coverage=LineageCoverage(state=LineageCoverageState.COMPLETE),
        )
        budget = LineageReadBudget.for_capture()
        try:
            async with self._reader.open_read(
                run_id=scope.run_id, budget=budget
            ) as session:
                snapshot = await session.resolve_snapshot(scope)
                nodes: list[LineageNode] = []
                after: str | None = None
                while True:
                    page = await session.node_page(snapshot, after, 200)
                    nodes.extend(page.rows)
                    if page.continuation is None:
                        break
                    after = page.continuation
                edges = []
                seen: set[str] = set()
                for node in nodes:
                    neighbor_after: str | None = None
                    while True:
                        neighbor_page = await session.neighbors(
                            snapshot,
                            node.key,
                            LineageDirection.BOTH,
                            neighbor_after,
                            200,
                        )
                        for row in neighbor_page.rows:
                            if row.edge.edge_key not in seen:
                                seen.add(row.edge.edge_key)
                                edges.append(row.edge)
                        if neighbor_page.continuation is None:
                            break
                        if (
                            neighbor_after is not None
                            and neighbor_page.continuation <= neighbor_after
                        ):
                            raise LineageError("lineage_cursor_not_advancing")
                        neighbor_after = neighbor_page.continuation
                return LineageSourceProjection(
                    nodes=tuple(nodes),
                    edges=tuple(edges),
                    coverage=snapshot_coverage(snapshot),
                )
        except LineageError as exc:
            if exc.code == "snapshot_unavailable":
                return empty
            raise


def snapshot_coverage(snapshot: LineageSnapshotRef) -> LineageCoverage:
    return LineageCoverage(
        state=LineageCoverageState.PARTIAL,
        reason_codes=("prior_publication_metadata_only",),
        capture_end_tick=snapshot.boundary_tick,
    )


def _frame_fingerprint(frame: LineageBoundaryFrame) -> str:
    payload = {
        "boundary_tick": frame.boundary_tick,
        "coverage": asdict(frame.coverage),
        "edges": [
            asdict(edge) for edge in sorted(frame.edges, key=lambda item: item.edge_key)
        ],
        "nodes": [
            asdict(node) for node in sorted(frame.nodes, key=lambda item: item.key)
        ],
        "source_revision": frame.source_revision,
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _projection_size(projection: LineageSourceProjection) -> int:
    encoded = json.dumps(
        {
            "edges": [asdict(edge) for edge in projection.edges],
            "nodes": [asdict(node) for node in projection.nodes],
        },
        allow_nan=False,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return len(encoded)


def _projection_digest(projection: LineageSourceProjection, boundary_tick: int) -> str:
    payload = {
        "boundary_tick": boundary_tick,
        "nodes": [
            [node.key, node.state.value, node.observed_tick, node.status_code]
            for node in sorted(projection.nodes, key=lambda item: item.key)
        ],
        "edges": [
            [edge.edge_key, edge.observed_tick, edge.status_code]
            for edge in sorted(projection.edges, key=lambda item: item.edge_key)
        ],
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
