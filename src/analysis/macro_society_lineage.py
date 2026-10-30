"""Forward-only split/merge lineage for analytical macro-society identities."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, is_dataclass
from typing import Final

from analysis.macro_society_contract import (
    MACRO_SOCIETY_POLICY_VERSION,
    MAX_LINEAGE_EDGES,
    TRANSFORM_JACCARD,
    MacroSocietyCoverage,
    MacroSocietyError,
    MacroSocietyLineageKind,
    require_macro_society_id,
)
from analysis.macro_society_detection import MacroSocietyWindowResult
from analysis.macro_society_identity import (
    MacroSocietyIdentityAssignment,
    MacroSocietyRecord,
)
from analysis.macro_society_layers import MacroSocietyLayerView
from analysis.numerical import quantize_float
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MacroSocietyAnalysis",
    "MacroSocietyLineageEdge",
    "build_macro_society_analysis",
    "derive_macro_society_lineage",
    "validate_macro_society_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.macro_society_lineage")


@dataclass(frozen=True, slots=True)
class MacroSocietyLineageEdge:
    """One forward-only analytical lineage edge between identities."""

    from_id: str | None
    to_id: str | None
    kind: MacroSocietyLineageKind
    from_tick: int
    to_tick: int
    jaccard: float | None = None
    policy_note: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, MacroSocietyLineageKind):
            raise MacroSocietyError("macro_society_invalid_lineage_kind")
        if self.from_id is None and self.kind is not MacroSocietyLineageKind.EMERGED:
            raise MacroSocietyError("macro_society_invalid_lineage_endpoint")
        if self.to_id is None and self.kind is not MacroSocietyLineageKind.DISSOLVED:
            raise MacroSocietyError("macro_society_invalid_lineage_endpoint")
        if self.from_id is not None:
            object.__setattr__(
                self, "from_id", require_macro_society_id(self.from_id)
            )
        if self.to_id is not None:
            object.__setattr__(self, "to_id", require_macro_society_id(self.to_id))
        first = require_exact_nonneg_int("from_tick", self.from_tick)
        last = require_exact_nonneg_int("to_tick", self.to_tick)
        if last < first:
            raise MacroSocietyError("macro_society_lineage_nonmonotonic_tick")
        object.__setattr__(self, "from_tick", first)
        object.__setattr__(self, "to_tick", last)
        if self.jaccard is not None:
            object.__setattr__(self, "jaccard", quantize_float(self.jaccard))
        if self.policy_note is not None:
            object.__setattr__(
                self,
                "policy_note",
                require_stable_id("policy_note", self.policy_note),
            )


@dataclass(frozen=True, slots=True)
class MacroSocietyAnalysis:
    """The complete analytical result for one run."""

    policy_version: str
    windows: tuple[MacroSocietyWindowResult, ...]
    records: tuple[MacroSocietyRecord, ...]
    edges: tuple[MacroSocietyLineageEdge, ...]
    layer_view: MacroSocietyLayerView | None
    coverage: MacroSocietyCoverage
    determinism_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            require_stable_id("policy_version", self.policy_version),
        )
        object.__setattr__(
            self,
            "edges",
            tuple(
                sorted(
                    self.edges,
                    key=lambda item: (
                        item.from_tick,
                        item.from_id or "",
                        item.to_id or "",
                        item.kind.value,
                    ),
                )
            ),
        )
        digest = require_stable_id("determinism_digest", self.determinism_digest)
        if len(digest) != 64:
            raise MacroSocietyError("macro_society_invalid_digest")
        object.__setattr__(self, "determinism_digest", digest)


def derive_macro_society_lineage(
    *,
    assignment: MacroSocietyIdentityAssignment,
    windows: Sequence[MacroSocietyWindowResult],
) -> tuple[MacroSocietyLineageEdge, ...]:
    """Classify raw identity transitions into lineage edges."""
    ordered = tuple(windows)
    bounds = {
        window.window_index: (window.tick_start, window.tick_end)
        for window in ordered
    }
    positions = {window.window_index: index for index, window in enumerate(ordered)}

    out_degree: Counter[tuple[int, str]] = Counter()
    in_degree: Counter[tuple[int, str]] = Counter()
    for transition in assignment.transitions:
        if (
            transition.previous_id is not None
            and transition.current_id is not None
            and transition.previous_id != transition.current_id
        ):
            out_degree[(transition.window_index, transition.previous_id)] += 1
            in_degree[(transition.window_index, transition.current_id)] += 1

    edges: list[MacroSocietyLineageEdge] = []
    for transition in assignment.transitions:
        if transition.window_index not in bounds:
            raise MacroSocietyError("macro_society_unknown_window")
        current_start, current_end = bounds[transition.window_index]
        position = positions[transition.window_index]
        previous_end = current_start
        if position > 0:
            previous_window = ordered[position - 1]
            previous_end = previous_window.tick_end

        if transition.previous_id is None:
            edges.append(
                MacroSocietyLineageEdge(
                    from_id=None,
                    to_id=transition.current_id,
                    kind=MacroSocietyLineageKind.EMERGED,
                    from_tick=current_start,
                    to_tick=current_end,
                )
            )
            continue
        if transition.current_id is None:
            edges.append(
                MacroSocietyLineageEdge(
                    from_id=transition.previous_id,
                    to_id=None,
                    kind=MacroSocietyLineageKind.DISSOLVED,
                    from_tick=previous_end,
                    to_tick=current_start,
                )
            )
            continue

        if transition.previous_id == transition.current_id:
            kind = (
                MacroSocietyLineageKind.CONTINUED
                if transition.score is not None
                and transition.score >= TRANSFORM_JACCARD
                else MacroSocietyLineageKind.TRANSFORMED
            )
            note = None
        elif transition.note == "absorption":
            kind = MacroSocietyLineageKind.TRANSFORMED
            note = "absorption"
        elif out_degree[(transition.window_index, transition.previous_id)] > 1:
            kind = MacroSocietyLineageKind.SPLIT
            note = transition.note
        elif in_degree[(transition.window_index, transition.current_id)] > 1:
            kind = MacroSocietyLineageKind.MERGE
            note = transition.note
        elif transition.score is not None and transition.score >= TRANSFORM_JACCARD:
            kind = MacroSocietyLineageKind.CONTINUED
            note = None
        else:
            kind = MacroSocietyLineageKind.TRANSFORMED
            note = None
        edges.append(
            MacroSocietyLineageEdge(
                from_id=transition.previous_id,
                to_id=transition.current_id,
                kind=kind,
                from_tick=previous_end,
                to_tick=current_start,
                jaccard=transition.score,
                policy_note=note,
            )
        )

    if len(edges) > MAX_LINEAGE_EDGES:
        raise MacroSocietyError("macro_society_lineage_too_large")
    return tuple(edges)


def validate_macro_society_lineage(
    edges: Sequence[MacroSocietyLineageEdge],
    records: Sequence[MacroSocietyRecord],
) -> None:
    """Validate endpoints, monotonic ticks, exact fan-out, and acyclicity."""
    known = {record.macro_society_id for record in records}
    seen: set[tuple[str, str, str, int, int]] = set()
    split_children: dict[str, set[str]] = {}
    merge_parents: dict[str, set[str]] = {}

    for edge in edges:
        if type(edge) is not MacroSocietyLineageEdge:
            raise MacroSocietyError("macro_society_invalid_lineage_edge")
        key = (
            edge.from_id or "",
            edge.to_id or "",
            edge.kind.value,
            edge.from_tick,
            edge.to_tick,
        )
        if key in seen:
            raise MacroSocietyError("macro_society_lineage_duplicate_edge")
        seen.add(key)
        if edge.from_tick > edge.to_tick:
            raise MacroSocietyError("macro_society_lineage_nonmonotonic_tick")
        for endpoint in (edge.from_id, edge.to_id):
            if endpoint is not None and endpoint not in known:
                raise MacroSocietyError("macro_society_unknown_society")
        if edge.kind is MacroSocietyLineageKind.SPLIT and edge.from_id is not None:
            split_children.setdefault(edge.from_id, set()).add(edge.to_id or "")
        if edge.kind is MacroSocietyLineageKind.MERGE and edge.to_id is not None:
            merge_parents.setdefault(edge.to_id, set()).add(edge.from_id or "")

    for children in split_children.values():
        if len(children) < 2:
            raise MacroSocietyError("macro_society_lineage_ambiguous_parent")
    for parents in merge_parents.values():
        if len(parents) < 2:
            raise MacroSocietyError("macro_society_lineage_ambiguous_parent")

    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        if edge.from_id is None or edge.to_id is None:
            continue
        if edge.from_id == edge.to_id:
            # Continuation of one identity is not a graph transition.
            continue
        adjacency.setdefault(edge.from_id, set()).add(edge.to_id)

    visiting: set[str] = set()
    settled: set[str] = set()

    def visit(node: str) -> None:
        if node in settled:
            return
        if node in visiting:
            raise MacroSocietyError("macro_society_lineage_cycle")
        visiting.add(node)
        for child in sorted(adjacency.get(node, ())):
            visit(child)
        visiting.discard(node)
        settled.add(node)

    for node in sorted(adjacency):
        visit(node)


def _canonical(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical(asdict(value))
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _determinism_digest(
    *,
    windows: Sequence[MacroSocietyWindowResult],
    records: Sequence[MacroSocietyRecord],
    edges: Sequence[MacroSocietyLineageEdge],
) -> str:
    payload = {
        "policy_version": MACRO_SOCIETY_POLICY_VERSION,
        "windows": _canonical(list(windows)),
        "records": _canonical(list(records)),
        "edges": _canonical(list(edges)),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_macro_society_analysis(
    *,
    windows: Sequence[MacroSocietyWindowResult],
    assignment: MacroSocietyIdentityAssignment,
    layer_view: MacroSocietyLayerView | None = None,
) -> MacroSocietyAnalysis:
    """Derive, validate, and digest the complete analysis."""
    ordered = tuple(windows)
    edges = derive_macro_society_lineage(assignment=assignment, windows=ordered)
    validate_macro_society_lineage(edges, assignment.records)
    analysis = MacroSocietyAnalysis(
        policy_version=MACRO_SOCIETY_POLICY_VERSION,
        windows=ordered,
        records=assignment.records,
        edges=edges,
        layer_view=layer_view,
        coverage=assignment.coverage,
        determinism_digest=_determinism_digest(
            windows=ordered, records=assignment.records, edges=edges
        ),
    )
    counts = Counter(edge.kind.value for edge in analysis.edges)
    _LOG.debug(
        "macro_society_lineage records=%s edges=%s continued=%s split=%s "
        "merge=%s dissolved=%s emerged=%s",
        len(analysis.records),
        len(analysis.edges),
        counts.get("continued", 0),
        counts.get("split", 0),
        counts.get("merge", 0),
        counts.get("dissolved", 0),
        counts.get("emerged", 0),
    )
    return analysis
