"""Trusted analytical lineage composition and strict institution JSON decoding.

This outer layer converts detached analysis results into simulation-owned
neutral publication DTOs. HTTP and persistence never call these functions and
never import analysis.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from analysis.institution_lineage import (
    INSTITUTION_LINEAGE_POLICY_VERSION,
    InstitutionLineageConfidence,
    InstitutionLineageEdgeKind,
)
from analysis.institutional_decay_metrics import INSTITUTION_LINEAGE_GRAPH_SCHEMA
from analysis.knowledge_genealogy import build_qualified_knowledge_lineage
from analysis.mentorship_lineage import build_mentorship_lineage
from simulation.lineage_capture import LineageCaptureReceipt
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
    lineage_edge_key,
)
from simulation.lineage_models import (
    LINEAGE_SNAPSHOT_SCHEMA_VERSION,
    LineageCoverage,
    LineageCoverageState,
    LineageEdge,
    LineageError,
    LineageNode,
    LineageNodeState,
    LineageScope,
    LineageSnapshotRef,
    MentorshipLineageRecord,
)
from simulation.lineage_ports import (
    LineageBoundaryFrame,
    LineagePublication,
    LineagePublicationPort,
    LineageReadBudget,
    LineageReadPort,
    LineageSourceProjection,
    NarrativeVariantSource,
)
from simulation.models import RunId
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("experiments.lineage_publication")

__all__ = [
    "LINEAGE_CAPTURE_STATUS_SCHEMA_VERSION",
    "MAX_INSTITUTION_LINEAGE_JSON_BYTES",
    "AnalyticalLineageInputs",
    "CompletedLineageHarvest",
    "LineageCaptureStatusDocument",
    "decode_institution_lineage_payload",
    "project_analytical_narrative_lineage",
    "publish_analytical_lineage",
    "publish_completed_lineage",
]

LINEAGE_CAPTURE_STATUS_SCHEMA_VERSION: Final[str] = "lineage-capture-status-v1"

MAX_INSTITUTION_LINEAGE_JSON_BYTES: Final[int] = 16 * 1024 * 1024
_MAX_JSON_DEPTH: Final[int] = 32
_MAX_INSTITUTION_EPISODES: Final[int] = 20_000
_MAX_INSTITUTION_EDGES: Final[int] = 40_000


@dataclass(frozen=True, slots=True)
class AnalyticalLineageInputs:
    """Detached analytical projection plus provenance before publication."""

    projection: LineageSourceProjection
    source_revision: str
    policy_version: str

    def __post_init__(self) -> None:
        if type(self.projection) is not LineageSourceProjection:
            raise ValueError("projection must be LineageSourceProjection")
        object.__setattr__(
            self,
            "source_revision",
            require_stable_id("source_revision", self.source_revision),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_stable_id("policy_version", self.policy_version),
        )


class _DuplicateKey(ValueError):
    pass


def _reject_constant(value: str) -> object:
    raise ValueError(f"nonfinite_json:{value}")


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey("duplicate_json_key")
        result[key] = value
    return result


def _depth_ok(value: object, *, depth: int = 0) -> bool:
    if depth > _MAX_JSON_DEPTH:
        return False
    if isinstance(value, Mapping):
        return all(
            _depth_ok(key, depth=depth + 1) and _depth_ok(item, depth=depth + 1)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return all(_depth_ok(item, depth=depth + 1) for item in value)
    return True


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("nonfinite_json")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite_json")
    return number


def _nonneg(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("invalid_institution_lineage")
    return value


def _text(value: object) -> str:
    return require_stable_id("institution_lineage_value", value)


def _exact_keys(
    value: object, expected: frozenset[str], *, name: str
) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"invalid_institution_lineage:{name}")
    if set(value) != expected:
        raise ValueError(f"invalid_institution_lineage:{name}")
    return value


@dataclass(frozen=True, slots=True)
class _InstitutionEpisodeRow:
    episode_id: str
    owner: str
    pattern: str
    first_tick: int
    last_tick: int
    components: tuple[str, ...]
    state: str
    pruned: bool


def _decode_institution_payload(
    payload: str | bytes, *, boundary_tick: int
) -> tuple[
    str,
    int,
    tuple[_InstitutionEpisodeRow, ...],
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str, str, int, int, str, int, float], ...],
    tuple[tuple[str, str], ...],
]:
    if isinstance(payload, str):
        encoded = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        encoded = payload
    else:
        raise ValueError("invalid_institution_lineage")
    if len(encoded) > MAX_INSTITUTION_LINEAGE_JSON_BYTES:
        raise LineageError("lineage_record_oversize")
    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid_institution_lineage") from exc
    try:
        document = json.loads(
            text,
            object_pairs_hook=_pairs_hook,
            parse_constant=_reject_constant,
        )
    except _DuplicateKey as exc:
        raise ValueError("lineage_identity_conflict") from exc
    if not isinstance(document, dict):
        raise ValueError("invalid_institution_lineage")
    if not _depth_ok(document):
        raise ValueError("invalid_institution_lineage")
    top = _exact_keys(
        document,
        frozenset(
            {
                "schema_version",
                "as_of_tick",
                "policy_version",
                "episodes",
                "stubs",
                "edges",
                "ambiguous",
            }
        ),
        name="top",
    )
    if top["schema_version"] != INSTITUTION_LINEAGE_GRAPH_SCHEMA:
        raise LineageError("unsupported_lineage_schema")
    as_of_tick = _nonneg(top["as_of_tick"])
    if as_of_tick > boundary_tick:
        raise LineageError("snapshot_corrupt")
    policy_version = _text(top["policy_version"])
    if policy_version != INSTITUTION_LINEAGE_POLICY_VERSION:
        raise LineageError("unsupported_lineage_schema")

    raw_episodes = top["episodes"]
    if (
        not isinstance(raw_episodes, list)
        or len(raw_episodes) > _MAX_INSTITUTION_EPISODES
    ):
        raise LineageError("lineage_record_oversize")
    episodes: list[_InstitutionEpisodeRow] = []
    seen_episode_ids: set[str] = set()
    for raw in raw_episodes:
        row = _exact_keys(
            raw,
            frozenset(
                {
                    "episode_id",
                    "owner",
                    "pattern",
                    "first_tick",
                    "last_tick",
                    "components",
                    "state",
                    "pruned",
                }
            ),
            name="episode",
        )
        episode_id_value = _text(row["episode_id"])
        if episode_id_value in seen_episode_ids:
            raise ValueError("lineage_identity_conflict")
        seen_episode_ids.add(episode_id_value)
        owner = _text(row["owner"])
        pattern = _text(row["pattern"])
        first_tick = _nonneg(row["first_tick"])
        last_tick = _nonneg(row["last_tick"])
        if first_tick > last_tick or last_tick > boundary_tick:
            raise LineageError("snapshot_corrupt")
        components = row["components"]
        if not isinstance(components, list):
            raise ValueError("invalid_institution_lineage")
        if row["state"] not in {
            "emerging",
            "stable",
            "weakening",
            "collapsed",
            "right_censored",
            "unknown",
        }:
            raise ValueError("invalid_institution_lineage")
        if type(row["pruned"]) is not bool:
            raise ValueError("invalid_institution_lineage")
        episodes.append(
            _InstitutionEpisodeRow(
                episode_id=episode_id_value,
                owner=owner,
                pattern=pattern,
                first_tick=first_tick,
                last_tick=last_tick,
                components=tuple(_text(item) for item in components),
                state=str(row["state"]),
                pruned=row["pruned"],
            )
        )

    raw_stubs = top["stubs"]
    if not isinstance(raw_stubs, list):
        raise ValueError("invalid_institution_lineage")
    stubs: list[tuple[str, str]] = []
    for raw in raw_stubs:
        row = _exact_keys(raw, frozenset({"episode_id", "reason"}), name="stub")
        stubs.append((_text(row["episode_id"]), _text(row["reason"])))

    raw_edges = top["edges"]
    if not isinstance(raw_edges, list) or len(raw_edges) > _MAX_INSTITUTION_EDGES:
        raise LineageError("lineage_record_oversize")
    edges: list[tuple[str, str, str, int, int, str, int, float]] = []
    for raw in raw_edges:
        row = _exact_keys(
            raw,
            frozenset(
                {
                    "kind",
                    "parent_id",
                    "child_id",
                    "parent_tick",
                    "child_tick",
                    "confidence",
                    "shared_components",
                    "jaccard",
                }
            ),
            name="edge",
        )
        kind = _text(row["kind"])
        confidence = _text(row["confidence"])
        try:
            InstitutionLineageEdgeKind(kind)
            InstitutionLineageConfidence(confidence)
        except ValueError as exc:
            raise ValueError("invalid_institution_lineage") from exc
        parent_tick = _nonneg(row["parent_tick"])
        child_tick = _nonneg(row["child_tick"])
        if child_tick < parent_tick or child_tick > boundary_tick:
            raise LineageError("snapshot_corrupt")
        edges.append(
            (
                kind,
                _text(row["parent_id"]),
                _text(row["child_id"]),
                parent_tick,
                child_tick,
                confidence,
                _nonneg(row["shared_components"]),
                _finite(row["jaccard"]),
            )
        )

    raw_ambiguous = top["ambiguous"]
    if not isinstance(raw_ambiguous, list):
        raise ValueError("invalid_institution_lineage")
    ambiguous: list[tuple[str, str]] = []
    for raw in raw_ambiguous:
        row = _exact_keys(
            raw, frozenset({"child", "candidate_parent"}), name="ambiguous"
        )
        ambiguous.append((_text(row["child"]), _text(row["candidate_parent"])))

    return (
        policy_version,
        as_of_tick,
        tuple(episodes),
        tuple(stubs),
        tuple(edges),
        tuple(ambiguous),
    )


def decode_institution_lineage_payload(
    payload: str | bytes,
    *,
    run_id: RunId,
    boundary_tick: int,
    coverage: LineageCoverage | None = None,
) -> LineageSourceProjection:
    """Strictly decode one verified analytical institution lineage payload."""
    if type(run_id) is not RunId:
        raise ValueError("run_id must be RunId")
    boundary = require_exact_nonneg_int("boundary_tick", boundary_tick)
    (
        policy_version,
        as_of_tick,
        episodes,
        stubs,
        edges,
        ambiguous,
    ) = _decode_institution_payload(payload, boundary_tick=boundary)
    coverage_value = coverage or LineageCoverage(
        state=LineageCoverageState.COMPLETE,
        capture_start_tick=0,
        capture_end_tick=boundary,
        policy_version=policy_version,
    )

    nodes: dict[str, LineageNode] = {}
    owner_by_episode: dict[str, str] = {}
    for episode in episodes:
        ref = LineageNodeRef(
            run_id=run_id,
            family=LineageFamily.INSTITUTION,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.INSTITUTION_EPISODE,
            native_id=episode.episode_id,
            identity_owner=episode.owner,
        )
        owner_by_episode[episode.episode_id] = episode.owner
        nodes[ref.key] = LineageNode(
            ref=ref,
            state=(
                LineageNodeState.ARCHIVED
                if episode.pruned
                else LineageNodeState.OBSERVED
            ),
            observed_tick=episode.last_tick,
            status_code=episode.state,
            counts=(
                ("first_tick", episode.first_tick),
                ("component_count", len(episode.components)),
            ),
            source_observed_boundary=as_of_tick,
        )

    for stub_id, reason in stubs:
        owner = owner_by_episode.get(stub_id)
        if owner is None:
            for _kind, parent, child, *_ in edges:
                if parent == stub_id:
                    owner = owner_by_episode.get(child)
                    break
                if child == stub_id:
                    owner = owner_by_episode.get(parent)
                    break
        if owner is None:
            raise LineageError("lineage_scope_mismatch")
        ref = LineageNodeRef(
            run_id=run_id,
            family=LineageFamily.INSTITUTION,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.INSTITUTION_EPISODE,
            native_id=stub_id,
            identity_owner=owner,
        )
        owner_by_episode[stub_id] = owner
        nodes[ref.key] = LineageNode(
            ref=ref,
            state=LineageNodeState.UNRESOLVED,
            unresolved_reason=reason,
            source_observed_boundary=as_of_tick,
        )

    edge_map: dict[str, LineageEdge] = {}
    for (
        kind,
        parent_id,
        child_id,
        _parent_tick,
        child_tick,
        confidence,
        shared_components,
        jaccard,
    ) in edges:
        parent_owner = owner_by_episode.get(parent_id)
        child_owner = owner_by_episode.get(child_id)
        if parent_owner is None or child_owner is None:
            raise LineageError("lineage_scope_mismatch")
        parent_ref = LineageNodeRef(
            run_id=run_id,
            family=LineageFamily.INSTITUTION,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.INSTITUTION_EPISODE,
            native_id=parent_id,
            identity_owner=parent_owner,
        )
        child_ref = LineageNodeRef(
            run_id=run_id,
            family=LineageFamily.INSTITUTION,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.INSTITUTION_EPISODE,
            native_id=child_id,
            identity_owner=child_owner,
        )
        evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.INSTITUTION_EPISODE,
            native_id=child_id,
            owner_id=child_owner,
            observed_tick=child_tick,
        )
        key = lineage_edge_key(
            relation=kind,
            source_key=parent_ref.key,
            target_key=child_ref.key,
            native_kind=LineageNativeKind.INSTITUTION_EPISODE,
            native_id=child_id,
            evidence_keys=(evidence.key,),
        )
        edge_map.setdefault(
            key,
            LineageEdge(
                edge_key=key,
                source_key=parent_ref.key,
                target_key=child_ref.key,
                relation=kind,
                native_kind=LineageNativeKind.INSTITUTION_EPISODE,
                native_id=child_id,
                evidence_refs=(evidence,),
                observed_tick=child_tick,
                status_code=confidence,
                confidence_value=jaccard,
                counts=(("shared_components", shared_components),),
            ),
        )

    ambiguous_by_child: dict[str, int] = {}
    for child, _parent in ambiguous:
        ambiguous_by_child[child] = ambiguous_by_child.get(child, 0) + 1
    for episode_id, count in ambiguous_by_child.items():
        owner = owner_by_episode.get(episode_id)
        if owner is None:
            continue
        ref = LineageNodeRef(
            run_id=run_id,
            family=LineageFamily.INSTITUTION,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.INSTITUTION_EPISODE,
            native_id=episode_id,
            identity_owner=owner,
        )
        existing = nodes[ref.key]
        counts = (
            *(
                (key, value)
                for key, value in existing.counts
                if key != "ambiguous_parent_count"
            ),
            ("ambiguous_parent_count", count),
        )
        nodes[ref.key] = replace(existing, counts=counts)

    _LOG.debug(
        "institution_lineage_decoded run_id=%s as_of=%s episode_count=%s "
        "edge_count=%s stub_count=%s ambiguous_count=%s",
        run_id.value,
        as_of_tick,
        len(episodes),
        len(edge_map),
        len(stubs),
        len(ambiguous),
    )
    return LineageSourceProjection(
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edge_map[key] for key in sorted(edge_map)),
        coverage=coverage_value,
    )


def project_analytical_narrative_lineage(
    variants: Sequence[tuple[str, NarrativeVariantSource]],
    *,
    run_id: RunId,
    as_of_tick: int,
    coverage: LineageCoverage | None = None,
) -> LineageSourceProjection:
    """Link owner-qualified variants only through explicit evidence."""
    if type(run_id) is not RunId:
        raise ValueError("run_id must be RunId")
    boundary = require_exact_nonneg_int("as_of_tick", as_of_tick)
    coverage_value = coverage or LineageCoverage(
        state=LineageCoverageState.COMPLETE,
        capture_start_tick=0,
        capture_end_tick=boundary,
        policy_version="narrative-analytical-lineage.v1",
    )
    nodes: dict[str, LineageNode] = {}
    edges: dict[str, LineageEdge] = {}
    event_keys: dict[str, str] = {}
    for owner_id, variant in variants:
        owner = require_stable_id("owner_id", owner_id)
        if type(variant) is not NarrativeVariantSource:
            raise ValueError("variants must carry NarrativeVariantSource")
        observed_tick = variant.last_tick if variant.last_tick is not None else 0
        if observed_tick > boundary:
            raise LineageError("snapshot_corrupt")
        ref = LineageNodeRef(
            run_id=run_id,
            family=LineageFamily.NARRATIVE,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.NARRATIVE_VARIANT,
            native_id=variant.variant_id,
            identity_owner=owner,
        )
        nodes[ref.key] = LineageNode(
            ref=ref,
            state=(
                LineageNodeState.ARCHIVED
                if variant.status in {"retired", "merged"}
                else LineageNodeState.OBSERVED
            ),
            observed_tick=observed_tick,
            status_code=variant.status,
            confidence_code=variant.origin,
            confidence_value=variant.strength,
            counts=(
                ("known_witness_count", variant.known_witness_count),
                ("dead_witness_count", variant.dead_witness_count),
            ),
            source_observed_boundary=boundary,
        )
        if variant.source_event_id is not None:
            event_ref = LineageNodeRef(
                run_id=run_id,
                family=LineageFamily.NARRATIVE,
                evidence_class=LineageEvidenceClass.ANALYTICAL,
                native_kind=LineageNativeKind.EVENT,
                native_id=variant.source_event_id,
            )
            nodes.setdefault(
                event_ref.key,
                LineageNode(
                    ref=event_ref,
                    state=LineageNodeState.OBSERVED,
                    observed_tick=observed_tick,
                    status_code="analytical_event_reference",
                ),
            )
            evidence = LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.ANALYTICAL,
                native_kind=LineageNativeKind.NARRATIVE_VARIANT,
                native_id=variant.variant_id,
                owner_id=owner,
                observed_tick=observed_tick,
            )
            key = lineage_edge_key(
                relation="claimed_event_origin",
                source_key=event_ref.key,
                target_key=ref.key,
                native_kind=LineageNativeKind.NARRATIVE_VARIANT,
                native_id=variant.variant_id,
                claim_owner_id=owner,
                evidence_keys=(evidence.key,),
            )
            edges.setdefault(
                key,
                LineageEdge(
                    edge_key=key,
                    source_key=event_ref.key,
                    target_key=ref.key,
                    relation="claimed_event_origin",
                    native_kind=LineageNativeKind.NARRATIVE_VARIANT,
                    native_id=variant.variant_id,
                    claim_owner_id=owner,
                    evidence_refs=(evidence,),
                    observed_tick=observed_tick,
                    status_code="testimony",
                ),
            )
            event_keys.setdefault(variant.source_event_id, event_ref.key)
    _LOG.debug(
        "analytical_narrative_projected run_id=%s as_of=%s variant_count=%s "
        "shared_event_count=%s",
        run_id.value,
        boundary,
        len(variants),
        sum(1 for key in event_keys),
    )
    return LineageSourceProjection(
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
        coverage=coverage_value,
    )


def _canonical_projection_payload(
    projection: LineageSourceProjection,
) -> dict[str, object]:
    return {
        "nodes": [
            {
                "key": node.key,
                "family": node.ref.family.value,
                "evidence_class": node.ref.evidence_class.value,
                "native_kind": node.ref.native_kind.value,
                "native_id": node.ref.native_id,
                "identity_owner": node.ref.identity_owner,
                "state": node.state.value,
                "observed_tick": node.observed_tick,
                "status_code": node.status_code,
                "counts": [list(item) for item in node.counts],
            }
            for node in projection.nodes
        ],
        "edges": [
            {
                "edge_key": edge.edge_key,
                "source_key": edge.source_key,
                "target_key": edge.target_key,
                "relation": edge.relation,
                "claim_owner_id": edge.claim_owner_id,
                "observed_tick": edge.observed_tick,
                "status_code": edge.status_code,
                "source_presence": edge.source_presence,
            }
            for edge in projection.edges
        ],
        "coverage": {
            "state": projection.coverage.state.value,
            "reason_codes": list(projection.coverage.reason_codes),
            "capture_start_tick": projection.coverage.capture_start_tick,
            "capture_end_tick": projection.coverage.capture_end_tick,
            "missing_prefix_tick": projection.coverage.missing_prefix_tick,
            "pruned_count": projection.coverage.pruned_count,
            "unresolved_count": projection.coverage.unresolved_count,
            "policy_version": projection.coverage.policy_version,
        },
    }


async def publish_analytical_lineage(
    inputs: AnalyticalLineageInputs,
    *,
    publisher: LineagePublicationPort,
    scope: LineageScope,
    boundary_tick: int,
) -> LineageSnapshotRef:
    """Publish an analytical projection through the writer-only capability."""
    if type(inputs) is not AnalyticalLineageInputs:
        raise ValueError("inputs must be AnalyticalLineageInputs")
    if type(scope) is not LineageScope:
        raise ValueError("scope must be LineageScope")
    if scope.evidence_class is not LineageEvidenceClass.ANALYTICAL:
        raise LineageError("invalid_lineage_scope")
    boundary = require_exact_nonneg_int("boundary_tick", boundary_tick)
    payload = _canonical_projection_payload(inputs.projection)
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    snapshot = LineageSnapshotRef(
        publication_id=f"lineage-{digest[:16]}",
        digest=digest,
        boundary_tick=boundary,
        schema_version=LINEAGE_SNAPSHOT_SCHEMA_VERSION,
    )
    frame = LineageBoundaryFrame(
        run_id=scope.run_id,
        scope=scope,
        boundary_tick=boundary,
        observed_boundary=boundary,
        nodes=inputs.projection.nodes,
        edges=inputs.projection.edges,
        coverage=inputs.projection.coverage,
        source_revision=inputs.source_revision,
    )
    publication = LineagePublication(snapshot=snapshot, frame=frame)
    return await publisher.publish(publication)


@dataclass(frozen=True, slots=True)
class CompletedLineageHarvest:
    """Detached completed-run evidence available to the analytical stage."""

    run_id: RunId
    boundary_tick: int
    source_revision: str
    practical_knowledge_audits: tuple[object, ...] = ()
    narrative_variants: tuple[tuple[str, NarrativeVariantSource], ...] = ()
    institution_payload: str | None = None
    mentorship_records: tuple[MentorshipLineageRecord, ...] = ()

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise ValueError("run_id must be RunId")
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int("boundary_tick", self.boundary_tick),
        )
        object.__setattr__(
            self,
            "source_revision",
            require_stable_id("source_revision", self.source_revision),
        )
        for name in ("practical_knowledge_audits", "narrative_variants"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        records = tuple(self.mentorship_records)
        for record in records:
            if type(record) is not MentorshipLineageRecord:
                raise ValueError(
                    "mentorship_records must be MentorshipLineageRecord"
                )
        object.__setattr__(self, "mentorship_records", records)
        if self.institution_payload is not None and not isinstance(
            self.institution_payload, str
        ):
            raise ValueError("institution_payload must be str or None")


@dataclass(frozen=True, slots=True)
class LineageCaptureStatusDocument:
    """Adjacent capture-health document; never runner-result serialization."""

    run_id: RunId
    boundary_tick: int
    published: tuple[tuple[str, str], ...]
    unavailable: tuple[tuple[str, str], ...]
    receipt_count: int
    failure_code: str | None = None

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": LINEAGE_CAPTURE_STATUS_SCHEMA_VERSION,
            "run_id": self.run_id.value,
            "boundary_tick": self.boundary_tick,
            "published": [
                {"family": family, "publication_id": publication_id}
                for family, publication_id in self.published
            ],
            "unavailable": [
                {"family": family, "reason_code": reason}
                for family, reason in self.unavailable
            ],
            "receipt_count": self.receipt_count,
            "failure_code": self.failure_code,
        }


async def _read_mentorship_records(
    reader: LineageReadPort,
    receipts: Sequence[LineageCaptureReceipt],
    boundary_tick: int,
) -> tuple[MentorshipLineageRecord, ...]:
    records: list[MentorshipLineageRecord] = []
    seen: set[tuple[str, str]] = set()
    read_scopes: set[LineageScope] = set()
    for receipt in receipts:
        scope = receipt.scope
        receipt_boundary = receipt.boundary_tick
        if (
            type(scope) is not LineageScope
            or receipt_boundary != boundary_tick
            or scope.family is not LineageFamily.MENTORSHIP
            or scope.evidence_class is not LineageEvidenceClass.SUBJECTIVE
            or scope in read_scopes
        ):
            continue
        read_scopes.add(scope)
        budget = LineageReadBudget.for_capture()
        try:
            async with reader.open_read(run_id=scope.run_id, budget=budget) as session:
                snapshot = await session.resolve_snapshot(scope, boundary_tick)
                after: str | None = None
                while True:
                    page = await session.node_page(snapshot, after, 200)
                    for node in page.rows:
                        record = node.mentorship_record
                        if record is None:
                            continue
                        key = (record.owner_id, record.lineage_id)
                        if key in seen:
                            continue
                        seen.add(key)
                        records.append(record)
                    if page.continuation is None:
                        break
                    after = page.continuation
        except LineageError:
            continue
    return tuple(records)


async def publish_completed_lineage(
    harvest: CompletedLineageHarvest,
    *,
    receipts: Sequence[LineageCaptureReceipt],
    reader: LineageReadPort,
    options: object,
    publisher: LineagePublicationPort,
) -> LineageCaptureStatusDocument:
    """Publish detached analytical families after a successful finalized run."""
    if type(harvest) is not CompletedLineageHarvest:
        raise ValueError("harvest must be CompletedLineageHarvest")
    del options  # caps are enforced by the injected publisher capability
    boundaries = [item.boundary_tick for item in receipts]
    boundary = max(boundaries, default=harvest.boundary_tick)
    records = harvest.mentorship_records + await _read_mentorship_records(
        reader, receipts, boundary
    )
    projections: dict[LineageFamily, LineageSourceProjection] = {}
    if records:
        projections[LineageFamily.MENTORSHIP] = build_mentorship_lineage(
            records, run_id=harvest.run_id, as_of_tick=boundary
        )
    if harvest.practical_knowledge_audits:
        projections[LineageFamily.KNOWLEDGE] = build_qualified_knowledge_lineage(
            harvest.practical_knowledge_audits,
            run_id=harvest.run_id,
            as_of_tick=boundary,
        )
        projections[LineageFamily.TECHNOLOGY] = build_qualified_knowledge_lineage(
            harvest.practical_knowledge_audits,
            run_id=harvest.run_id,
            as_of_tick=boundary,
            family=LineageFamily.TECHNOLOGY,
            policy_version="technology-analytical-lineage.v1",
        )
    if harvest.narrative_variants:
        projections[LineageFamily.NARRATIVE] = project_analytical_narrative_lineage(
            harvest.narrative_variants,
            run_id=harvest.run_id,
            as_of_tick=boundary,
        )
    if harvest.institution_payload is not None:
        projections[LineageFamily.INSTITUTION] = decode_institution_lineage_payload(
            harvest.institution_payload,
            run_id=harvest.run_id,
            boundary_tick=boundary,
        )
    published: list[tuple[str, str]] = []
    unavailable: list[tuple[str, str]] = []
    for family in (
        LineageFamily.MENTORSHIP,
        LineageFamily.KNOWLEDGE,
        LineageFamily.TECHNOLOGY,
        LineageFamily.NARRATIVE,
        LineageFamily.INSTITUTION,
    ):
        projection = projections.get(family)
        if projection is None:
            unavailable.append((family.value, "detailed_source_unavailable"))
            continue
        if not projection.nodes:
            unavailable.append((family.value, "no_detached_source_rows"))
            continue
        try:
            snapshot = await publish_analytical_lineage(
                AnalyticalLineageInputs(
                    projection=projection,
                    source_revision=harvest.source_revision,
                    policy_version=(
                        projection.coverage.policy_version
                        or f"{family.value}-analytical-lineage.v1"
                    ),
                ),
                publisher=publisher,
                scope=LineageScope(
                    run_id=harvest.run_id,
                    family=family,
                    evidence_class=LineageEvidenceClass.ANALYTICAL,
                ),
                boundary_tick=boundary,
            )
        except LineageError as exc:
            unavailable.append(
                (family.value, f"publication_failed:{exc.code or 'unknown'}")
            )
            continue
        published.append((family.value, snapshot.publication_id))
    _LOG.info(
        "lineage_analytical_publication_finished run_id=%s boundary_tick=%s "
        "published_count=%s unavailable_count=%s",
        harvest.run_id.value,
        boundary,
        len(published),
        len(unavailable),
    )
    return LineageCaptureStatusDocument(
        run_id=harvest.run_id,
        boundary_tick=boundary,
        published=tuple(published),
        unavailable=tuple(unavailable),
        receipt_count=len(receipts),
    )
