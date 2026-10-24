"""Filesystem lineage read model with one atomic run discovery commit point.

Reader and writer capabilities are separate. The writer serializes publications
under an exclusive per-run lock, reserves quota before staging, and publishes a
new commit only by atomically replacing ``state.json`` after all referenced
files are durable. Readers ignore pending and unreachable artifacts.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from simulation.lineage_codec import (
    LINEAGE_MANIFEST_MAX_BYTES,
    LINEAGE_NODE_PAGE_MAX_NODES,
    LINEAGE_RECORD_MAX_BYTES,
    LineageAdjacencyPage,
    LineageNodePage,
    LineageSnapshotManifest,
    compute_publication_id,
    decode_lineage_adjacency_page,
    decode_lineage_manifest,
    decode_lineage_node_descriptor,
    decode_lineage_node_page,
    encode_lineage_adjacency_page,
    encode_lineage_manifest,
    encode_lineage_node_descriptor,
    encode_lineage_node_page,
)
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageFamily,
    LineageNativeKind,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageDirection,
    LineageEdge,
    LineageError,
    LineageNode,
    LineageScope,
    LineageSnapshotRef,
)
from simulation.lineage_ports import (
    CAPTURE_MAX_ARTIFACT_BYTES,
    CAPTURE_MAX_PUBLICATION_RESERVATIONS,
    LineageNeighborPage,
    LineageNeighborRow,
    LineageNodeCataloguePage,
    LineagePublication,
    LineagePublicationPort,
    LineageReadBudget,
    LineageReadPort,
    LineageReadSession,
    LineageSnapshotCataloguePage,
)
from simulation.models import RunId

_LOG: Final[logging.Logger] = logging.getLogger("persistence.lineage_filesystem")

__all__ = [
    "LINEAGE_STATE_MAX_BYTES",
    "FilesystemLineagePublisher",
    "FilesystemLineageReader",
    "create_lineage_publisher",
    "create_lineage_reader",
]

LINEAGE_STATE_MAX_BYTES: Final[int] = 4 * 1024
_LINEAGE_COMMIT_MAX_BYTES: Final[int] = 64 * 1024
_RESERVATION_ALLOWANCE: Final[int] = 256 * 1024
_STATE_SCHEMA: Final[str] = "lineage-state-v1"
_COMMIT_SCHEMA: Final[str] = "lineage-commit-v1"
_LOOKUP_SCHEMA: Final[str] = "lineage-lookup-v1"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _reject_constant(value: str) -> object:
    raise ValueError("nonfinite")


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _decode(payload: bytes, *, max_bytes: int) -> object:
    if len(payload) > max_bytes:
        raise LineageError("lineage_record_oversize")
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_pairs_hook,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise LineageError("lineage_snapshot_corrupt") from exc


def _scope_key(scope: LineageScope) -> str:
    material = "|".join(
        (
            scope.family.value,
            scope.evidence_class.value,
            scope.owner_id or "",
        )
    )
    return _digest(material.encode("utf-8"))


def _identity_hash(native_kind: LineageNativeKind, native_id: str) -> str:
    return _digest(
        _canonical({"native_id": native_id, "native_kind": native_kind.value})
    )


def _boundary_hex(boundary_tick: int) -> str:
    return f"{boundary_tick:016x}"


@dataclass(frozen=True, slots=True)
class _ScopeHead:
    family: LineageFamily
    evidence_class: LineageEvidenceClass
    owner_id: str | None
    boundary_tick: int
    publication_id: str
    snapshot_digest: str
    snapshot_path: str


@dataclass(frozen=True, slots=True)
class _CommitManifest:
    run_id: RunId
    commit_ref: str
    catalogue_generation: str
    scope_heads: tuple[_ScopeHead, ...]

    def payload(self, *, include_ref: bool) -> dict[str, object]:
        document: dict[str, object] = {
            "catalogue_generation": self.catalogue_generation,
            "run_id": self.run_id.value,
            "schema_version": _COMMIT_SCHEMA,
            "scope_heads": [
                {
                    "boundary_tick": head.boundary_tick,
                    "evidence_class": head.evidence_class.value,
                    "family": head.family.value,
                    "owner_id": head.owner_id,
                    "publication_id": head.publication_id,
                    "snapshot_digest": head.snapshot_digest,
                    "snapshot_path": head.snapshot_path,
                }
                for head in self.scope_heads
            ],
        }
        if include_ref:
            document["commit_ref"] = self.commit_ref
        return document


def _commit_ref(manifest: _CommitManifest) -> str:
    return _digest(_canonical(manifest.payload(include_ref=False)))


@dataclass(frozen=True, slots=True)
class _PendingReservation:
    publication_id: str
    snapshot_digest: str
    family: LineageFamily
    evidence_class: LineageEvidenceClass
    owner_id: str | None
    boundary_tick: int
    planned_bytes: int
    prior_commit_ref: str | None
    expected_commit_ref: str | None = None


@dataclass(frozen=True, slots=True)
class _RunState:
    run_id: RunId
    catalogue_generation: str
    committed_ref: str | None
    quota_reservations: int
    quota_artifact_bytes: int
    pending: _PendingReservation | None

    def payload(self) -> dict[str, object]:
        return {
            "catalogue_generation": self.catalogue_generation,
            "committed_ref": self.committed_ref,
            "pending": (
                None
                if self.pending is None
                else {
                    "boundary_tick": self.pending.boundary_tick,
                    "evidence_class": self.pending.evidence_class.value,
                    "expected_commit_ref": self.pending.expected_commit_ref,
                    "family": self.pending.family.value,
                    "owner_id": self.pending.owner_id,
                    "planned_bytes": self.pending.planned_bytes,
                    "prior_commit_ref": self.pending.prior_commit_ref,
                    "publication_id": self.pending.publication_id,
                    "snapshot_digest": self.pending.snapshot_digest,
                }
            ),
            "quota_artifact_bytes": self.quota_artifact_bytes,
            "quota_reservations": self.quota_reservations,
            "run_id": self.run_id.value,
            "schema_version": _STATE_SCHEMA,
        }


def _state_from_payload(payload: object) -> _RunState:
    if not isinstance(payload, dict):
        raise LineageError("lineage_snapshot_corrupt")
    expected = {
        "catalogue_generation",
        "committed_ref",
        "pending",
        "quota_artifact_bytes",
        "quota_reservations",
        "run_id",
        "schema_version",
    }
    if set(payload) != expected or payload["schema_version"] != _STATE_SCHEMA:
        raise LineageError("lineage_snapshot_corrupt")
    pending_payload = payload["pending"]
    pending: _PendingReservation | None = None
    if pending_payload is not None:
        if not isinstance(pending_payload, dict):
            raise LineageError("lineage_snapshot_corrupt")
        pending = _PendingReservation(
            publication_id=str(pending_payload["publication_id"]),
            snapshot_digest=str(pending_payload["snapshot_digest"]),
            family=LineageFamily(str(pending_payload["family"])),
            evidence_class=LineageEvidenceClass(str(pending_payload["evidence_class"])),
            owner_id=pending_payload["owner_id"],
            boundary_tick=int(pending_payload["boundary_tick"]),
            planned_bytes=int(pending_payload["planned_bytes"]),
            prior_commit_ref=pending_payload["prior_commit_ref"],
            expected_commit_ref=pending_payload["expected_commit_ref"],
        )
    return _RunState(
        run_id=RunId(str(payload["run_id"])),
        catalogue_generation=str(payload["catalogue_generation"]),
        committed_ref=payload["committed_ref"],
        quota_reservations=int(payload["quota_reservations"]),
        quota_artifact_bytes=int(payload["quota_artifact_bytes"]),
        pending=pending,
    )


class _RunLock:
    __slots__ = ("_fd", "_path")

    def __init__(self, run_root: Path) -> None:
        self._path = run_root / "writer.lock"
        self._fd: int | None = None

    def __enter__(self) -> _RunLock:
        try:
            self._fd = os.open(
                self._path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except FileExistsError as exc:
            raise LineageError("lineage_writer_busy") from exc
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    fd = os.open(
        temp,
        os.O_CREAT | os.O_TRUNC | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temp, path)
    _fsync_dir(path.parent)


def _safe_root(root: Path, *, create: bool) -> Path:
    if root.exists() and root.is_symlink():
        raise LineageError("lineage_storage_unavailable")
    if create:
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve()
    return root.absolute()


def _safe_path(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise LineageError("lineage_storage_unavailable")
    current = root
    for part in parts:
        if not part or part in {".", ".."} or "/" in part or "\\" in part:
            raise LineageError("lineage_storage_unavailable")
        current = current / part
        if current.is_symlink():
            raise LineageError("lineage_storage_unavailable")
    return resolved


def _encode_snapshot_files(
    publication: LineagePublication,
) -> tuple[dict[str, bytes], LineageSnapshotManifest]:
    frame = publication.frame
    scope = frame.scope
    files: dict[str, bytes] = {}
    for node in frame.nodes:
        files[f"nodes/{node.key}.json"] = encode_lineage_node_descriptor(node)
    outgoing: dict[str, list[LineageEdge]] = {}
    incoming: dict[str, list[LineageEdge]] = {}
    for edge in frame.edges:
        outgoing.setdefault(edge.source_key, []).append(edge)
        incoming.setdefault(edge.target_key, []).append(edge)
    for node_key in sorted(set(outgoing) | set(incoming)):
        for direction, grouped in (
            (LineageDirection.DESCENDANTS, outgoing),
            (LineageDirection.ANCESTORS, incoming),
        ):
            edges = sorted(
                grouped.get(node_key, ()),
                key=lambda edge: (edge.observed_tick or 0, edge.edge_key),
            )
            if not edges:
                continue
            adjacency_page = LineageAdjacencyPage(
                direction=direction,
                node_key=node_key,
                edges=tuple(edges),
            )
            files[f"adjacency/{node_key}-{direction.value}-0000.json"] = (
                encode_lineage_adjacency_page(adjacency_page)
            )
    for index in range(0, len(frame.nodes), LINEAGE_NODE_PAGE_MAX_NODES):
        node_page = LineageNodePage(
            nodes=frame.nodes[index : index + LINEAGE_NODE_PAGE_MAX_NODES]
        )
        files[f"catalog/nodes-{index // LINEAGE_NODE_PAGE_MAX_NODES:04d}.json"] = (
            encode_lineage_node_page(node_page)
        )
    # Rebuild lookup shards deterministically with all keys per identity hash.
    identity_groups: dict[str, dict[str, list[str]]] = {}
    for node in frame.nodes:
        identity = _identity_hash(node.ref.native_kind, node.ref.native_id)
        shard = identity[:2]
        identity_groups.setdefault(shard, {}).setdefault(identity, []).append(node.key)
    for shard, groups in identity_groups.items():
        files[f"lookup/{shard}.json"] = _canonical(
            {
                "entries": [
                    [identity, sorted(keys)]
                    for identity, keys in sorted(groups.items())
                ],
                "schema_version": _LOOKUP_SCHEMA,
            }
        )
    integrity: dict[str, list[list[str]]] = {}
    for path, content in files.items():
        shard = _digest(path.encode("utf-8"))[:2]
        integrity.setdefault(shard, []).append([path, _digest(content)])
    for shard, entries in integrity.items():
        files[f"integrity/{shard}.json"] = _canonical(
            {
                "entries": sorted(entries),
                "schema_version": "lineage-integrity-v1",
            }
        )
    page_digests = tuple(
        (path, _digest(content)) for path, content in sorted(files.items())
    )
    manifest = LineageSnapshotManifest(
        run_id=frame.run_id,
        family=scope.family,
        evidence_class=scope.evidence_class,
        owner_id=scope.owner_id,
        boundary_tick=frame.boundary_tick,
        publication_id="0" * 64,
        content_digest=publication.snapshot.digest,
        source_revision=frame.source_revision,
        policy_version=frame.coverage.policy_version or "lineage-snapshot-v1",
        coverage=frame.coverage,
        node_count=len(frame.nodes),
        edge_count=len(frame.edges),
        page_count=len(files),
        page_digests=page_digests,
    )
    manifest = replace(manifest, publication_id=compute_publication_id(manifest))
    files["manifest.json"] = encode_lineage_manifest(manifest)
    return files, manifest


def _snapshot_relative_path(
    scope: LineageScope, boundary: int, publication_id: str
) -> str:
    return (
        f"scopes/{_scope_key(scope)}/snapshots/"
        f"{_boundary_hex(boundary)}/{publication_id}"
    )


def _read_budgeted(
    path: Path, budget: LineageReadBudget | None, *, max_bytes: int
) -> bytes:
    """Read one control/data file, charging a probe or its size first."""
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        if budget is not None:
            budget.reserve(0)
        raise
    if budget is None:
        return path.read_bytes()
    reservation = budget.reserve(size)
    content = path.read_bytes()
    reservation.require_actual_bytes(len(content))
    if len(content) > max_bytes:
        raise LineageError("lineage_record_oversize")
    return content


def _snapshot_keyset(head: _ScopeHead) -> tuple[int, str]:
    return (head.boundary_tick, head.publication_id)


def _snapshot_after_key(after: str) -> tuple[int, str]:
    tick_text, _, publication = after.partition(":")
    try:
        tick = int(tick_text)
    except ValueError as exc:
        raise LineageError("invalid_lineage_cursor") from exc
    if tick < 0:
        raise LineageError("invalid_lineage_cursor")
    return (tick, publication)


def _declared(manifest: LineageSnapshotManifest, relative: str) -> bool:
    return any(path == relative for path, _digest_value in manifest.page_digests)


def _default_state(run_id: RunId) -> _RunState:
    return _RunState(
        run_id=run_id,
        catalogue_generation="0",
        committed_ref=None,
        quota_reservations=0,
        quota_artifact_bytes=0,
        pending=None,
    )


def _load_run_state(
    run_root: Path, run_id: RunId, budget: LineageReadBudget | None = None
) -> _RunState:
    path = run_root / "state.json"
    try:
        payload = _read_budgeted(path, budget, max_bytes=LINEAGE_STATE_MAX_BYTES)
    except FileNotFoundError:
        return _default_state(run_id)
    state = _state_from_payload(_decode(payload, max_bytes=LINEAGE_STATE_MAX_BYTES))
    if state.run_id != run_id:
        raise LineageError("lineage_scope_mismatch")
    return state


def _load_commit_manifest(
    run_root: Path,
    run_id: RunId,
    commit_ref: str,
    budget: LineageReadBudget | None = None,
) -> _CommitManifest:
    path = _safe_path(run_root, "commits", commit_ref, "manifest.json")
    payload = _decode(
        _read_budgeted(path, budget, max_bytes=_LINEAGE_COMMIT_MAX_BYTES),
        max_bytes=_LINEAGE_COMMIT_MAX_BYTES,
    )
    if not isinstance(payload, dict):
        raise LineageError("lineage_snapshot_corrupt")
    expected = {
        "catalogue_generation",
        "commit_ref",
        "run_id",
        "schema_version",
        "scope_heads",
    }
    if set(payload) != expected or payload["schema_version"] != _COMMIT_SCHEMA:
        raise LineageError("lineage_snapshot_corrupt")
    heads = tuple(
        _ScopeHead(
            family=LineageFamily(str(item["family"])),
            evidence_class=LineageEvidenceClass(str(item["evidence_class"])),
            owner_id=item["owner_id"],
            boundary_tick=int(item["boundary_tick"]),
            publication_id=str(item["publication_id"]),
            snapshot_digest=str(item["snapshot_digest"]),
            snapshot_path=str(item["snapshot_path"]),
        )
        for item in payload["scope_heads"]
    )
    manifest = _CommitManifest(
        run_id=RunId(str(payload["run_id"])),
        commit_ref=str(payload["commit_ref"]),
        catalogue_generation=str(payload["catalogue_generation"]),
        scope_heads=heads,
    )
    if _commit_ref(manifest) != commit_ref:
        raise LineageError("lineage_digest_mismatch")
    return manifest


class FilesystemLineagePublisher(LineagePublicationPort):
    """Writer-only immutable publication capability."""

    __slots__ = ("_max_artifact_bytes", "_max_publications", "_root")

    def __init__(
        self,
        root: Path | str,
        *,
        max_publications: int = CAPTURE_MAX_PUBLICATION_RESERVATIONS,
        max_artifact_bytes: int = CAPTURE_MAX_ARTIFACT_BYTES,
    ) -> None:
        if (
            isinstance(max_publications, bool)
            or not isinstance(max_publications, int)
            or not 1 <= max_publications <= CAPTURE_MAX_PUBLICATION_RESERVATIONS
        ):
            raise ValueError("max_publications is outside the supported range")
        if (
            isinstance(max_artifact_bytes, bool)
            or not isinstance(max_artifact_bytes, int)
            or not 1 <= max_artifact_bytes <= CAPTURE_MAX_ARTIFACT_BYTES
        ):
            raise ValueError("max_artifact_bytes is outside the supported range")
        self._max_publications = max_publications
        self._max_artifact_bytes = max_artifact_bytes
        self._root = _safe_root(Path(root), create=True)

    def _run_root(self, run_id: RunId) -> Path:
        return _safe_path(self._root, "runs", _digest(run_id.value.encode("utf-8")))

    def _load_state(self, run_id: RunId) -> _RunState:
        return _load_run_state(self._run_root(run_id), run_id)

    def _write_state(self, state: _RunState) -> None:
        payload = _canonical(state.payload())
        if len(payload) > LINEAGE_STATE_MAX_BYTES:
            raise LineageError("lineage_record_oversize")
        run_root = self._run_root(state.run_id)
        _atomic_write(run_root / "state.json", payload)

    def _load_commit(self, run_id: RunId, commit_ref: str) -> _CommitManifest:
        return _load_commit_manifest(self._run_root(run_id), run_id, commit_ref)

    def _write_commit(self, manifest: _CommitManifest) -> None:
        run_root = self._run_root(manifest.run_id)
        path = _safe_path(run_root, "commits", manifest.commit_ref, "manifest.json")
        payload = _canonical(manifest.payload(include_ref=True))
        if len(payload) > _LINEAGE_COMMIT_MAX_BYTES:
            raise LineageError("lineage_record_oversize")
        _atomic_write(path, payload)

    def _snapshot_manifest(
        self, run_id: RunId, snapshot_path: str
    ) -> LineageSnapshotManifest:
        path = _safe_path(self._run_root(run_id), *snapshot_path.split("/"))
        payload = (path / "manifest.json").read_bytes()
        if len(payload) > LINEAGE_MANIFEST_MAX_BYTES:
            raise LineageError("lineage_record_oversize")
        return decode_lineage_manifest(payload)

    async def publish(self, publication: LineagePublication) -> LineageSnapshotRef:
        if type(publication) is not LineagePublication:
            raise ValueError("publication must be LineagePublication")
        run_id = publication.frame.run_id
        run_root = self._run_root(run_id)
        run_root.mkdir(parents=True, exist_ok=True)
        with _RunLock(run_root):
            state = self._load_state(run_id)
            if state.pending is not None:
                state = self._recover_locked(state)
            files, manifest = _encode_snapshot_files(publication)
            total_bytes = sum(len(item) for item in files.values())
            reserved_bytes = total_bytes + _RESERVATION_ALLOWANCE
            snapshot = LineageSnapshotRef(
                publication_id=manifest.publication_id,
                digest=manifest.content_digest,
                boundary_tick=manifest.boundary_tick,
            )
            scope = publication.frame.scope
            commit = (
                self._load_commit(run_id, state.committed_ref)
                if state.committed_ref is not None
                else _CommitManifest(
                    run_id=run_id,
                    commit_ref="",
                    catalogue_generation="0",
                    scope_heads=(),
                )
            )
            existing = next(
                (
                    head
                    for head in commit.scope_heads
                    if head.family is scope.family
                    and head.evidence_class is scope.evidence_class
                    and head.owner_id == scope.owner_id
                    and head.boundary_tick == manifest.boundary_tick
                ),
                None,
            )
            if existing is not None:
                if existing.snapshot_digest == manifest.content_digest:
                    return LineageSnapshotRef(
                        publication_id=existing.publication_id,
                        digest=existing.snapshot_digest,
                        boundary_tick=existing.boundary_tick,
                    )
                raise LineageError("lineage_publication_conflict")
            if (
                state.quota_reservations + 1 > self._max_publications
                or state.quota_artifact_bytes + reserved_bytes
                > self._max_artifact_bytes
            ):
                raise LineageError("lineage_source_budget")
            pending = _PendingReservation(
                publication_id=manifest.publication_id,
                snapshot_digest=manifest.content_digest,
                family=scope.family,
                evidence_class=scope.evidence_class,
                owner_id=scope.owner_id,
                boundary_tick=manifest.boundary_tick,
                planned_bytes=total_bytes,
                prior_commit_ref=state.committed_ref,
            )
            reserved = replace(
                state,
                quota_reservations=state.quota_reservations + 1,
                quota_artifact_bytes=state.quota_artifact_bytes + reserved_bytes,
                pending=pending,
            )
            self._write_state(reserved)
            snapshot_path = _snapshot_relative_path(
                scope, manifest.boundary_tick, manifest.publication_id
            )
            try:
                staging = _safe_path(run_root, "staging", manifest.publication_id)
                if staging.exists():
                    shutil.rmtree(staging)
                for path, content in files.items():
                    _atomic_write(staging.joinpath(*path.split("/")), content)
                final_dir = _safe_path(run_root, *snapshot_path.split("/"))
                if final_dir.exists():
                    raise LineageError("lineage_publication_conflict")
                final_dir.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging, final_dir)
                _fsync_dir(final_dir.parent)
                heads = (
                    *commit.scope_heads,
                    _ScopeHead(
                        family=scope.family,
                        evidence_class=scope.evidence_class,
                        owner_id=scope.owner_id,
                        boundary_tick=manifest.boundary_tick,
                        publication_id=manifest.publication_id,
                        snapshot_digest=manifest.content_digest,
                        snapshot_path=snapshot_path,
                    ),
                )
                new_commit = _CommitManifest(
                    run_id=run_id,
                    commit_ref="",
                    catalogue_generation=str(
                        int(commit.catalogue_generation or "0") + 1
                    ),
                    scope_heads=heads,
                )
                new_commit = replace(new_commit, commit_ref=_commit_ref(new_commit))
                self._write_commit(new_commit)
                reserved = replace(
                    reserved,
                    catalogue_generation=new_commit.catalogue_generation,
                    pending=replace(pending, expected_commit_ref=new_commit.commit_ref),
                )
                self._write_state(reserved)
                final_state = replace(
                    reserved,
                    committed_ref=new_commit.commit_ref,
                    pending=None,
                )
                self._write_state(final_state)
            except BaseException:
                raise
            return snapshot

    def _recover_locked(self, state: _RunState) -> _RunState:
        pending = state.pending
        if pending is None:
            return state
        if pending.expected_commit_ref is not None:
            try:
                commit = self._load_commit(state.run_id, pending.expected_commit_ref)
            except (FileNotFoundError, LineageError):
                commit = None
            if commit is not None:
                head = next(
                    (
                        item
                        for item in commit.scope_heads
                        if item.publication_id == pending.publication_id
                    ),
                    None,
                )
                if head is not None:
                    try:
                        self._verify_snapshot_files(state.run_id, head.snapshot_path)
                    except (FileNotFoundError, LineageError):
                        head = None
                if head is not None:
                    recovered = replace(
                        state,
                        committed_ref=commit.commit_ref,
                        catalogue_generation=commit.catalogue_generation,
                        pending=None,
                    )
                    self._write_state(recovered)
                    return recovered
            abandoned = replace(state, pending=None)
            self._write_state(abandoned)
            return abandoned

        snapshot_path = _snapshot_relative_path(
            LineageScope(
                run_id=state.run_id,
                family=pending.family,
                evidence_class=pending.evidence_class,
                owner_id=pending.owner_id,
            ),
            pending.boundary_tick,
            pending.publication_id,
        )
        try:
            self._verify_snapshot_files(state.run_id, snapshot_path)
        except (FileNotFoundError, LineageError):
            abandoned = replace(state, pending=None)
            self._write_state(abandoned)
            return abandoned
        prior = (
            self._load_commit(state.run_id, state.committed_ref)
            if state.committed_ref is not None
            else _CommitManifest(
                run_id=state.run_id,
                commit_ref="",
                catalogue_generation="0",
                scope_heads=(),
            )
        )
        heads = (
            *prior.scope_heads,
            _ScopeHead(
                family=pending.family,
                evidence_class=pending.evidence_class,
                owner_id=pending.owner_id,
                boundary_tick=pending.boundary_tick,
                publication_id=pending.publication_id,
                snapshot_digest=pending.snapshot_digest,
                snapshot_path=snapshot_path,
            ),
        )
        content = _CommitManifest(
            run_id=state.run_id,
            commit_ref="",
            catalogue_generation=str(int(prior.catalogue_generation or "0") + 1),
            scope_heads=heads,
        )
        content = replace(content, commit_ref=_commit_ref(content))
        self._write_commit(content)
        recovered = replace(
            state,
            committed_ref=content.commit_ref,
            catalogue_generation=content.catalogue_generation,
            pending=None,
        )
        self._write_state(recovered)
        return recovered

    def _verify_snapshot_files(self, run_id: RunId, snapshot_path: str) -> None:
        manifest = self._snapshot_manifest(run_id, snapshot_path)
        root = _safe_path(self._run_root(run_id), *snapshot_path.split("/"))
        for path, digest in manifest.page_digests:
            content = root.joinpath(*path.split("/")).read_bytes()
            if _digest(content) != digest:
                raise LineageError("lineage_snapshot_corrupt")

    def recover_pending_publication(self, run_id: RunId) -> LineageSnapshotRef | None:
        run_root = self._run_root(run_id)
        run_root.mkdir(parents=True, exist_ok=True)
        with _RunLock(run_root):
            state = self._load_state(run_id)
            recovered = self._recover_locked(state)
            if recovered.committed_ref is None:
                return None
            commit = self._load_commit(run_id, recovered.committed_ref)
            head = commit.scope_heads[-1] if commit.scope_heads else None
            if head is None:
                return None
            return LineageSnapshotRef(
                publication_id=head.publication_id,
                digest=head.snapshot_digest,
                boundary_tick=head.boundary_tick,
            )


class _FilesystemReadSession(LineageReadSession):
    __slots__ = ("_budget", "_cache", "_commit", "_reader", "_run_id")

    def __init__(
        self,
        *,
        reader: FilesystemLineageReader,
        run_id: RunId,
        budget: LineageReadBudget,
        commit: _CommitManifest,
    ) -> None:
        self._reader = reader
        self._run_id = run_id
        self._budget = budget
        self._commit = commit
        self._cache: dict[str, bytes] = {}

    @property
    def run_commit_ref(self) -> str:
        return self._commit.commit_ref

    @property
    def budget(self) -> LineageReadBudget:
        return self._budget

    async def coverage(self, snapshot: LineageSnapshotRef) -> LineageCoverage:
        _head, manifest = self._snapshot(snapshot)
        return manifest.coverage

    def _read(self, *parts: str) -> bytes:
        path = _safe_path(self._reader._run_root(self._run_id), *parts)
        key = str(path)
        cached = self._cache.get(key)
        if cached is not None:
            self._budget.record_cache_hit()
            return cached
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            self._budget.reserve(0)
            raise
        reservation = self._budget.reserve(size)
        content = path.read_bytes()
        reservation.require_actual_bytes(len(content))
        self._cache[key] = content
        return content

    def _read_verified(
        self,
        head: _ScopeHead,
        manifest: LineageSnapshotManifest,
        relative: str,
    ) -> bytes:
        try:
            content = self._read(
                *head.snapshot_path.split("/"), *relative.split("/")
            )
        except FileNotFoundError:
            if _declared(manifest, relative):
                raise LineageError("lineage_snapshot_corrupt") from None
            raise
        expected = dict(manifest.page_digests).get(relative)
        if expected is not None and _digest(content) != expected:
            raise LineageError("lineage_snapshot_corrupt")
        return content

    def _snapshot(
        self, snapshot: LineageSnapshotRef
    ) -> tuple[_ScopeHead, LineageSnapshotManifest]:
        scope_heads = self._commit.scope_heads
        for head in scope_heads:
            if head.publication_id == snapshot.publication_id:
                try:
                    payload = self._read(
                        *head.snapshot_path.split("/"), "manifest.json"
                    )
                except FileNotFoundError:
                    raise LineageError("lineage_snapshot_corrupt") from None
                manifest = decode_lineage_manifest(payload)
                if manifest.content_digest != snapshot.digest:
                    raise LineageError("lineage_digest_mismatch")
                return head, manifest
        raise LineageError("snapshot_unavailable")

    async def resolve_snapshot(
        self, scope: LineageScope, boundary_tick: int | None = None
    ) -> LineageSnapshotRef:
        heads = [
            head
            for head in self._commit.scope_heads
            if head.family is scope.family
            and head.evidence_class is scope.evidence_class
            and head.owner_id == scope.owner_id
        ]
        if not heads:
            raise LineageError("snapshot_unavailable")
        resolved_head: _ScopeHead | None
        if boundary_tick is None:
            resolved_head = max(heads, key=lambda item: item.boundary_tick)
        else:
            resolved_head = next(
                (item for item in heads if item.boundary_tick == boundary_tick),
                None,
            )
            if resolved_head is None:
                raise LineageError("snapshot_unavailable")
        return LineageSnapshotRef(
            publication_id=resolved_head.publication_id,
            digest=resolved_head.snapshot_digest,
            boundary_tick=resolved_head.boundary_tick,
        )

    async def get_node(
        self, snapshot: LineageSnapshotRef, key: str
    ) -> LineageNode | None:
        head, manifest = self._snapshot(snapshot)
        relative = f"nodes/{key}.json"
        try:
            return decode_lineage_node_descriptor(
                self._read_verified(head, manifest, relative)
            )
        except FileNotFoundError:
            if _declared(manifest, relative):
                raise LineageError("lineage_snapshot_corrupt") from None
            return None

    async def neighbors(
        self,
        snapshot: LineageSnapshotRef,
        key: str,
        direction: LineageDirection,
        after: str | None,
        limit: int,
    ) -> LineageNeighborPage:
        head, manifest = self._snapshot(snapshot)
        directions = (
            (LineageDirection.ANCESTORS, LineageDirection.DESCENDANTS)
            if direction is LineageDirection.BOTH
            else (direction,)
        )
        rows: list[LineageNeighborRow] = []
        declared = 0
        for item in directions:
            direction_rows: list[LineageNeighborRow] = []
            try:
                page = decode_lineage_adjacency_page(
                    self._read_verified(
                        head,
                        manifest,
                        f"adjacency/{key}-{item.value}-0000.json",
                    )
                )
            except FileNotFoundError:
                continue
            declared += len(page.edges)
            for edge in page.edges:
                endpoint = (
                    edge.target_key
                    if item is LineageDirection.DESCENDANTS
                    else edge.source_key
                )
                node = await self.get_node(snapshot, endpoint)
                if node is None:
                    raise LineageError("lineage_snapshot_corrupt")
                if after is not None and edge.edge_key <= after:
                    continue
                direction_rows.append(LineageNeighborRow(edge=edge, node=node))
            direction_rows.sort(key=lambda row: row.edge.edge_key)
            rows.extend(direction_rows)
        selected = rows[:limit]
        continuation = selected[-1].edge.edge_key if len(rows) > limit else None
        return LineageNeighborPage(
            rows=tuple(selected),
            declared_count=declared,
            continuation=continuation,
        )

    async def node_page(
        self, snapshot: LineageSnapshotRef, after: str | None, limit: int
    ) -> LineageNodeCataloguePage:
        head, manifest = self._snapshot(snapshot)
        pages = [
            path
            for path, _digest_value in manifest.page_digests
            if path.startswith("catalog/nodes-")
        ]
        nodes: list[LineageNode] = []
        for path in sorted(pages):
            page = decode_lineage_node_page(self._read_verified(head, manifest, path))
            nodes.extend(page.nodes)
            if len(nodes) >= (limit + (1 if after else 0)):
                break
        filtered = sorted(
            (node for node in nodes if after is None or node.key > after),
            key=lambda node: node.key,
        )
        selected = filtered[:limit]
        return LineageNodeCataloguePage(
            rows=tuple(selected),
            declared_count=len(filtered),
            continuation=selected[-1].key if len(filtered) > limit else None,
            coverage=manifest.coverage,
        )

    async def lookup_nodes(
        self,
        snapshot: LineageSnapshotRef,
        native_kind: LineageNativeKind,
        native_id: str,
        after: str | None,
        limit: int,
    ) -> LineageNodeCataloguePage:
        head, manifest = self._snapshot(snapshot)
        identity = _identity_hash(native_kind, native_id)
        try:
            payload = _decode(
                self._read_verified(head, manifest, f"lookup/{identity[:2]}.json"),
                max_bytes=LINEAGE_RECORD_MAX_BYTES,
            )
        except FileNotFoundError:
            return LineageNodeCataloguePage(
                rows=(), declared_count=0, coverage=manifest.coverage
            )
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _LOOKUP_SCHEMA
        ):
            raise LineageError("lineage_snapshot_corrupt")
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise LineageError("lineage_snapshot_corrupt")
        keys: list[str] = []
        for entry in entries:
            if (
                isinstance(entry, list)
                and len(entry) == 2
                and entry[0] == identity
                and isinstance(entry[1], list)
            ):
                keys.extend(str(key) for key in entry[1])
        keys = sorted(key for key in keys if after is None or key > after)
        selected: list[LineageNode] = []
        for key in keys[:limit]:
            node = await self.get_node(snapshot, key)
            if node is None:
                raise LineageError("lineage_snapshot_corrupt")
            selected.append(node)
        return LineageNodeCataloguePage(
            rows=tuple(selected),
            declared_count=len(keys),
            continuation=selected[-1].key if len(keys) > limit else None,
            coverage=manifest.coverage,
        )

    async def snapshot_page(
        self, scope: LineageScope, after: str | None, limit: int
    ) -> LineageSnapshotCataloguePage:
        heads = sorted(
            (
                head
                for head in self._commit.scope_heads
                if head.family is scope.family
                and head.evidence_class is scope.evidence_class
                and head.owner_id == scope.owner_id
            ),
            key=lambda head: head.boundary_tick,
        )
        rows = [
            LineageSnapshotRef(
                publication_id=head.publication_id,
                digest=head.snapshot_digest,
                boundary_tick=head.boundary_tick,
            )
            for head in heads
            if after is None or _snapshot_keyset(head) > _snapshot_after_key(after)
        ]
        selected = rows[:limit]
        if len(rows) > limit and selected:
            last = selected[-1]
            continuation = f"{last.boundary_tick}:{last.publication_id}"
        else:
            continuation = None
        return LineageSnapshotCataloguePage(
            rows=tuple(selected),
            declared_count=len(rows),
            continuation=continuation,
        )


class _ReadSessionContext(AbstractAsyncContextManager[_FilesystemReadSession]):
    __slots__ = ("_session",)

    def __init__(self, session: _FilesystemReadSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FilesystemReadSession:
        return self._session

    async def __aexit__(self, *_exc: object) -> None:
        return None


class FilesystemLineageReader(LineageReadPort):
    """Reader-only capability pinned to committed discovery state."""

    __slots__ = ("_root",)

    def __init__(self, root: Path | str) -> None:
        self._root = _safe_root(Path(root), create=False)

    def _run_root(self, run_id: RunId) -> Path:
        return _safe_path(self._root, "runs", _digest(run_id.value.encode("utf-8")))

    def has_run(self, run_id: RunId) -> bool:
        return (self._run_root(run_id) / "state.json").is_file()

    def open_read(
        self,
        *,
        run_id: RunId,
        budget: LineageReadBudget,
        commit_ref: str | None = None,
    ) -> AbstractAsyncContextManager[LineageReadSession]:
        run_root = self._run_root(run_id)
        state = _load_run_state(run_root, run_id, budget)
        pinned = commit_ref or state.committed_ref
        if pinned is None:
            raise LineageError("snapshot_unavailable")
        commit = _load_commit_manifest(run_root, run_id, pinned, budget)
        return _ReadSessionContext(
            _FilesystemReadSession(
                reader=self,
                run_id=run_id,
                budget=budget,
                commit=commit,
            )
        )


def create_lineage_reader(root: Path | str) -> FilesystemLineageReader:
    return FilesystemLineageReader(root)


def create_lineage_publisher(
    root: Path | str,
    *,
    max_publications: int = CAPTURE_MAX_PUBLICATION_RESERVATIONS,
    max_artifact_bytes: int = CAPTURE_MAX_ARTIFACT_BYTES,
) -> FilesystemLineagePublisher:
    return FilesystemLineagePublisher(
        root,
        max_publications=max_publications,
        max_artifact_bytes=max_artifact_bytes,
    )
