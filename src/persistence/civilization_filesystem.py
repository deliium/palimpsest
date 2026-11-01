"""Immutable filesystem publication and bounded read model for civilization.

Rows and manifests are encoded with the independent civilization codec. Hashes
are child-first; the only commit point is the atomic ``state.json`` reference.
Readers never glob uncommitted files or repair orphan writes.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, cast

from simulation.civilization_codec import (
    civilization_digest,
    decode_civilization_value,
    encode_civilization_value,
)
from simulation.civilization_models import (
    CivilizationArtifactRef,
    CivilizationCoverage,
    CivilizationCursor,
    CivilizationError,
    CivilizationEvidenceClass,
    CivilizationHashManifest,
    CivilizationLayer,
    CivilizationMarker,
    CivilizationPublicationRef,
    CivilizationScope,
    CivilizationWindow,
)
from simulation.civilization_ports import (
    CIVILIZATION_MAX_BOUNDARIES,
    CIVILIZATION_MAX_BOUNDARY_BYTES,
    CIVILIZATION_MAX_CAPTURE_BYTES,
    CIVILIZATION_MAX_METADATA_BYTES,
    CIVILIZATION_MAX_SHARD_BYTES,
    CIVILIZATION_MAX_SHARD_ROWS,
    CivilizationBoundaryPublication,
    CivilizationBoundaryRef,
    CivilizationCataloguePage,
    CivilizationMarkerSelection,
    CivilizationPage,
    CivilizationReadBudget,
)
from simulation.civilization_rows import (
    CivilizationCapturedRow,
    CivilizationCultureRow,
    CivilizationGroupRow,
    CivilizationInstitutionRow,
    CivilizationLocationRow,
    CivilizationMapRow,
    CivilizationMigrationRow,
    CivilizationProjectRow,
    CivilizationRecordRow,
    CivilizationRegionRow,
    CivilizationRepositoryRow,
    CivilizationRouteRow,
    CivilizationSettlementRow,
    CivilizationTechnologyRow,
    CivilizationTradeRow,
)
from simulation.civilization_store_index import (
    CIVILIZATION_INDEX_PAGE_SCHEMA,
    CIVILIZATION_STORE_ROOT_PATH,
    CivilizationStoreRootV2,
    compute_store_digest,
    decode_civilization_store_root,
    encode_civilization_store_root,
)
from simulation.lineage_store_index import (
    LineageIndexEntry,
    LineageIndexPage,
    build_index_root,
    decode_lineage_index_page,
    lineage_object_path,
)

_ROW_TYPES = (
    CivilizationRegionRow,
    CivilizationRouteRow,
    CivilizationLocationRow,
    CivilizationProjectRow,
    CivilizationRepositoryRow,
    CivilizationRecordRow,
    CivilizationSettlementRow,
    CivilizationMigrationRow,
    CivilizationTradeRow,
    CivilizationCultureRow,
    CivilizationTechnologyRow,
    CivilizationGroupRow,
    CivilizationInstitutionRow,
)

__all__ = [
    "FilesystemCivilizationPublisher",
    "FilesystemCivilizationReader",
    "create_civilization_publisher",
    "create_civilization_reader",
]

_LOG = logging.getLogger(__name__)
_POLICY = "civilization-overlays.v1"
_SAFE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_STATE = "state.json"
# Index keys must stay inside the 128-code-point stable-id bound. The full
# scope digest plus a tick plus a row id can exceed it, and truncation both
# collapses shard ranges and breaks row-key pagination. Keys therefore carry a
# fixed-width scope tag and a per-(scope, boundary) shard ordinal instead.
_INDEX_SCOPE_TAG_LENGTH = 16
_INDEX_SHARD_ORDINAL_WIDTH = 8


class CivilizationFilesystemError(CivilizationError):
    """Closed storage/publication codes only."""


def _safe_component(value: object) -> str:
    if type(value) is not str or not _SAFE.fullmatch(value) or value in {".", ".."}:
        raise CivilizationError("civilization_storage_corrupt")
    return value


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_root(root: Path, run_id: str) -> Path:
    if type(run_id) is not str or not run_id:
        raise CivilizationError("civilization_storage_corrupt")
    return root / _digest_text(run_id)


def _safe_path(root: Path, *parts: str) -> Path:
    for part in parts:
        if (
            type(part) is not str
            or not part
            or part in {".", ".."}
            or "/" in part
            or "\\" in part
        ):
            raise CivilizationError("civilization_storage_corrupt")
    path = root.joinpath(*parts)
    if not path.resolve(strict=False).is_relative_to(root.resolve(strict=False)):
        raise CivilizationError("civilization_storage_corrupt")
    return path


def _scope_key(scope: CivilizationScope) -> str:
    return _digest_text(
        "|".join(
            (
                scope.layer.value,
                scope.evidence_class.value,
                scope.owner_id or "",
            )
        )
    )


def _row_key(row: object) -> str:
    context = getattr(row, "context", None)
    key = getattr(context, "row_id", None)
    if not isinstance(key, str):
        raise CivilizationError()
    return key


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _read_budgeted(
    path: Path,
    budget: CivilizationReadBudget,
    *,
    metadata: bool = False,
) -> bytes:
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        raise CivilizationError("civilization_storage_corrupt") from None
    reservation = budget.reserve_file(size, metadata=metadata)
    try:
        content = path.read_bytes()
    except OSError:
        raise CivilizationError("civilization_storage_corrupt") from None
    reservation.require_actual_bytes(len(content))
    return content


def _encode_rows(rows: tuple[object, ...]) -> bytes:
    return b"".join(encode_civilization_value(row) for row in rows)


def _decode_lines(
    content: bytes,
    *,
    expected_type: type,
    budget: CivilizationReadBudget,
) -> tuple[object, ...]:
    values: list[object] = []
    for line in content.splitlines(keepends=True):
        if not line.endswith(b"\n"):
            raise CivilizationError("civilization_storage_corrupt")
        budget.reserve_scan(1)
        value = decode_civilization_value(line)
        if type(value) is not expected_type:
            raise CivilizationError("civilization_storage_corrupt")
        values.append(value)
    return tuple(values)


def _encode_state(payload: dict[str, object]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _decode_state(content: bytes) -> dict[str, object]:
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise CivilizationError("civilization_storage_corrupt") from None
    if type(value) is not dict:
        raise CivilizationError("civilization_storage_corrupt")
    return value


@contextmanager
def _locked(run_root: Path) -> Iterator[None]:
    run_root.mkdir(parents=True, exist_ok=True)
    lock_path = run_root / ".lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _directory_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise CivilizationError("civilization_storage_corrupt")
        if path.is_file():
            total += path.stat().st_size
    return total


class FilesystemCivilizationPublisher:
    """Single-writer, atomic, quota-aware publication of finalized boundaries."""

    def __init__(self, root: Path | str) -> None:
        resolved = Path(root)
        if resolved.is_symlink():
            raise CivilizationError("civilization_storage_corrupt")
        resolved.mkdir(parents=True, exist_ok=True)
        self._root = resolved.resolve()

    def _publication_root(self, run_id: str, publication_id: str) -> Path:
        _safe_component(publication_id)
        return _safe_path(
            self._root,
            _digest_text(run_id),
            "publications",
            publication_id,
        )

    async def publish_boundary(
        self, publication_id: str, boundary: CivilizationBoundaryPublication
    ) -> None:
        if type(boundary) is not CivilizationBoundaryPublication:
            raise CivilizationError()
        run_id = boundary.cursor.run_id
        run_root = _run_root(self._root, run_id)
        publication_root = self._publication_root(run_id, publication_id)
        boundary_tick = boundary.cursor.boundary_tick
        if boundary_tick is None:
            raise CivilizationError()
        rows_by_scope: dict[str, list[CivilizationCapturedRow]] = {}
        for row in boundary.rows:
            rows_by_scope.setdefault(_scope_key(row.history.scope), []).append(row)
        files: dict[str, bytes] = {}
        shard_keys: dict[str, tuple[str, str]] = {}
        marker_chunk: list[CivilizationMarker] = []
        marker_part = 0
        for marker in boundary.markers:
            candidate_markers = (*marker_chunk, marker)
            encoded_markers = _encode_rows(candidate_markers)
            if marker_chunk and (
                len(candidate_markers) > CIVILIZATION_MAX_SHARD_ROWS
                or len(encoded_markers) > CIVILIZATION_MAX_SHARD_BYTES
            ):
                files[f"markers/part-{marker_part:04d}.jsonl"] = _encode_rows(
                    tuple(marker_chunk)
                )
                marker_part += 1
                marker_chunk = [marker]
            else:
                marker_chunk = list(candidate_markers)
        if marker_chunk:
            files[f"markers/part-{marker_part:04d}.jsonl"] = _encode_rows(
                tuple(marker_chunk)
            )
        for scope_key, rows in sorted(rows_by_scope.items()):
            ordered: tuple[CivilizationCapturedRow, ...] = tuple(
                sorted(rows, key=_row_key)
            )
            chunk: list[CivilizationCapturedRow] = []
            part = 0
            for row in ordered:
                candidate = (*chunk, row)
                encoded = _encode_rows(candidate)
                if (
                    len(candidate) > CIVILIZATION_MAX_SHARD_ROWS
                    or len(encoded) > CIVILIZATION_MAX_SHARD_BYTES
                ):
                    shard_name = f"rows/{scope_key}/part-{part:04d}.jsonl"
                    files[shard_name] = _encode_rows(tuple(chunk))
                    shard_keys[shard_name] = (
                        _row_key(chunk[0]),
                        _row_key(chunk[-1]),
                    )
                    part += 1
                    chunk = [row]
                else:
                    chunk = list(candidate)
            if chunk:
                shard_name = f"rows/{scope_key}/part-{part:04d}.jsonl"
                files[shard_name] = _encode_rows(tuple(chunk))
                shard_keys[shard_name] = (_row_key(chunk[0]), _row_key(chunk[-1]))
        total_bytes = sum(len(value) for value in files.values())
        if (
            total_bytes > CIVILIZATION_MAX_BOUNDARY_BYTES
            or len(files) > CIVILIZATION_MAX_BOUNDARIES
        ):
            raise CivilizationError("civilization_row_too_large")
        with _locked(run_root):
            if (
                _directory_bytes(run_root) + total_bytes
                > CIVILIZATION_MAX_CAPTURE_BYTES
            ):
                raise CivilizationError("civilization_read_budget")
            boundary_root = _safe_path(
                publication_root, "boundaries", f"{boundary_tick:08d}"
            )
            manifest_children = []
            for relative, encoded in sorted(files.items()):
                key = f"boundaries/{boundary_tick:08d}/{relative}"
                target = _safe_path(publication_root, *key.split("/"))
                if target.exists():
                    if target.read_bytes() != encoded:
                        raise CivilizationError("civilization_storage_corrupt")
                else:
                    _write_atomic(target, encoded)
                row_count = encoded.count(b"\n")
                first_key = last_key = relative
                manifest_children.append(
                    _artifact_ref(
                        kind="row_shard",
                        key=key,
                        digest=civilization_digest(encoded),
                        byte_count=len(encoded),
                        row_count=row_count,
                        first_key=first_key,
                        last_key=last_key,
                    )
                )
            from simulation.civilization_models import (
                CivilizationArtifactRef,
                CivilizationHashManifest,
            )

            bounds_payload: dict[str, object] = {
                "bounds": {
                    relative: [first, last]
                    for relative, (first, last) in sorted(shard_keys.items())
                },
                "schema_version": "civilization-row-bounds-v1",
            }
            _write_atomic(
                _safe_path(boundary_root, "row-bounds.json"),
                _encode_state(bounds_payload),
            )

            manifest = CivilizationHashManifest(
                "boundary_manifest",
                run_id,
                boundary.cursor.world_id,
                publication_id,
                "civilization-capture-v1",
                publication_id,
                _POLICY,
                boundary_tick,
                tuple(manifest_children),
            )
            try:
                manifest_bytes = encode_civilization_value(manifest)
            except CivilizationError:
                raise
            if len(manifest_bytes) > CIVILIZATION_MAX_METADATA_BYTES:
                raise CivilizationError("civilization_row_too_large")
            manifest_path = _safe_path(
                publication_root, *boundary_root.parts[-2:], "manifest.json"
            )
            _write_atomic(manifest_path, manifest_bytes)
            ref = CivilizationBoundaryRef(
                boundary.cursor,
                civilization_digest(manifest_bytes),
                boundary.scopes,
                _overall_coverage(boundary),
            )
            ref_path = _safe_path(
                publication_root, *boundary_root.parts[-2:], "ref.json"
            )
            _write_atomic(ref_path, encode_civilization_value(ref))
            del CivilizationArtifactRef

    async def seal_catalogue(
        self, run_id: str, publication_id: str
    ) -> CivilizationPublicationRef:
        from simulation.civilization_models import (
            CivilizationHashManifest,
        )

        publication_root = self._publication_root(run_id, publication_id)
        run_root = _run_root(self._root, run_id)
        with _locked(run_root):
            refs: list[CivilizationBoundaryRef] = []
            for path in sorted(publication_root.glob("boundaries/*/ref.json")):
                content = path.read_bytes()
                value = decode_civilization_value(content)
                if type(value) is not CivilizationBoundaryRef:
                    raise CivilizationError("civilization_storage_corrupt")
                refs.append(value)
            if len(refs) > CIVILIZATION_MAX_BOUNDARIES or not refs:
                raise CivilizationError("civilization_read_budget")
            page_children: list[CivilizationArtifactRef] = []
            page_chunk: list[CivilizationBoundaryRef] = []
            page_bytes = b""
            for ref in refs:
                encoded = encode_civilization_value(ref)
                if page_chunk and (
                    len(page_chunk) >= CIVILIZATION_MAX_SHARD_ROWS
                    or len(page_bytes) + len(encoded) > CIVILIZATION_MAX_SHARD_BYTES
                ):
                    relative = f"catalogue/page-{len(page_children):04d}.jsonl"
                    target = _safe_path(publication_root, *relative.split("/"))
                    _write_atomic(target, page_bytes)
                    page_children.append(
                        _artifact_ref(
                            kind="catalogue_page",
                            key=relative,
                            digest=civilization_digest(page_bytes),
                            byte_count=len(page_bytes),
                            row_count=len(page_chunk),
                            first_key=f"{page_chunk[0].cursor.boundary_tick:08d}",
                            last_key=f"{page_chunk[-1].cursor.boundary_tick:08d}",
                        )
                    )
                    page_chunk = []
                    page_bytes = b""
                page_chunk.append(ref)
                page_bytes += encoded
            if page_chunk:
                relative = f"catalogue/page-{len(page_children):04d}.jsonl"
                target = _safe_path(publication_root, *relative.split("/"))
                _write_atomic(target, page_bytes)
                page_children.append(
                    _artifact_ref(
                        kind="catalogue_page",
                        key=relative,
                        digest=civilization_digest(page_bytes),
                        byte_count=len(page_bytes),
                        row_count=len(page_chunk),
                        first_key=f"{page_chunk[0].cursor.boundary_tick:08d}",
                        last_key=f"{page_chunk[-1].cursor.boundary_tick:08d}",
                    )
                )
            index = CivilizationHashManifest(
                "catalogue_index",
                run_id,
                refs[0].cursor.world_id if refs else "",
                publication_id,
                "civilization-capture-v1",
                publication_id,
                _POLICY,
                None,
                tuple(page_children),
            )
            index_bytes = encode_civilization_value(index)
            if len(index_bytes) > CIVILIZATION_MAX_METADATA_BYTES:
                raise CivilizationError("civilization_row_too_large")
            _write_atomic(
                _safe_path(publication_root, "catalogue", "index.json"),
                index_bytes,
            )
            digest = civilization_digest(index_bytes)

            catalogue_entries = [
                LineageIndexEntry(
                    first_key=child.first_key,
                    last_key=child.last_key,
                    digest=child.digest,
                    path=child.key,
                    row_count=child.row_count,
                    byte_count=child.byte_count,
                    is_index=False,
                )
                for child in page_children
            ]
            catalogue_root, catalogue_objects = build_index_root(
                "civilization-catalogue",
                catalogue_entries,
                page_schema=CIVILIZATION_INDEX_PAGE_SCHEMA,
                max_bytes=CIVILIZATION_MAX_METADATA_BYTES,
            )
            row_entries: list[LineageIndexEntry] = []
            shard_ordinals: dict[tuple[str, int], int] = {}
            for ref in refs:
                boundary_tick = ref.cursor.boundary_tick
                if boundary_tick is None:
                    raise CivilizationError("civilization_storage_corrupt")
                boundary_root = _safe_path(
                    publication_root, "boundaries", f"{boundary_tick:08d}"
                )
                manifest_path = _safe_path(boundary_root, "manifest.json")
                manifest_content = manifest_path.read_bytes()
                if civilization_digest(manifest_content) != ref.manifest_digest:
                    raise CivilizationError("civilization_storage_corrupt")
                manifest_value = decode_civilization_value(manifest_content)
                if type(manifest_value) is not CivilizationHashManifest:
                    raise CivilizationError("civilization_storage_corrupt")
                bounds_path = _safe_path(boundary_root, "row-bounds.json")
                try:
                    bounds_value = _decode_state(bounds_path.read_bytes())
                except FileNotFoundError:
                    bounds_value = {}
                raw_bounds = bounds_value.get("bounds", {})
                if type(raw_bounds) is not dict:
                    raise CivilizationError("civilization_storage_corrupt")
                for child in manifest_value.children:
                    if "/rows/" not in child.key:
                        continue
                    relative = child.key.split(
                        f"boundaries/{boundary_tick:08d}/", 1
                    )[-1]
                    scope_key = child.key.split("/")[-2]
                    bounds = raw_bounds.get(relative)
                    if (
                        not isinstance(bounds, list)
                        or len(bounds) != 2
                        or not all(type(item) is str for item in bounds)
                    ):
                        raise CivilizationError("civilization_storage_corrupt")
                    ordinal_key = (scope_key, boundary_tick)
                    ordinal = shard_ordinals.get(ordinal_key, 0)
                    shard_ordinals[ordinal_key] = ordinal + 1
                    index_key = (
                        f"{scope_key[:_INDEX_SCOPE_TAG_LENGTH]}"
                        f"|{boundary_tick:08d}"
                        f"|{ordinal:0{_INDEX_SHARD_ORDINAL_WIDTH}d}"
                    )
                    row_entries.append(
                        LineageIndexEntry(
                            first_key=index_key,
                            last_key=index_key,
                            digest=child.digest,
                            path=child.key,
                            row_count=child.row_count,
                            byte_count=child.byte_count,
                            is_index=False,
                        )
                    )
            row_entries.sort(key=lambda entry: entry.first_key)
            rows_root, rows_objects = build_index_root(
                "civilization-rows",
                row_entries,
                page_schema=CIVILIZATION_INDEX_PAGE_SCHEMA,
                max_bytes=CIVILIZATION_MAX_METADATA_BYTES,
            )
            objects = {**catalogue_objects, **rows_objects}
            for object_digest, content in sorted(objects.items()):
                target = _safe_path(
                    publication_root,
                    *lineage_object_path(object_digest).split("/"),
                )
                if target.exists():
                    if civilization_digest(target.read_bytes()) != object_digest:
                        raise CivilizationError("civilization_storage_corrupt")
                else:
                    _write_atomic(target, content)
            store = CivilizationStoreRootV2(
                run_id=run_id,
                world_id=refs[0].cursor.world_id,
                publication_id=publication_id,
                policy_version=_POLICY,
                catalogue=catalogue_root,
                rows=rows_root,
                store_digest="0" * 64,
            )
            store = CivilizationStoreRootV2(
                run_id=store.run_id,
                world_id=store.world_id,
                publication_id=store.publication_id,
                policy_version=store.policy_version,
                catalogue=store.catalogue,
                rows=store.rows,
                store_digest=compute_store_digest(store),
            )
            _write_atomic(
                _safe_path(
                    publication_root,
                    *CIVILIZATION_STORE_ROOT_PATH.split("/"),
                ),
                encode_civilization_store_root(store),
            )

            state: dict[str, object] = {
                "run_id": run_id,
                "publication_id": publication_id,
                "catalogue_ref": "catalogue/index.json",
                "catalogue_digest": digest,
                "policy_version": _POLICY,
            }
            _write_atomic(
                _safe_path(run_root, _STATE),
                _encode_state(state),
            )
            return CivilizationPublicationRef(publication_id, digest, _POLICY)


def _artifact_ref(
    *,
    kind: Literal[
        "row_shard", "boundary_manifest", "catalogue_page", "catalogue_index"
    ],
    key: str,
    digest: str,
    byte_count: int,
    row_count: int,
    first_key: str,
    last_key: str,
) -> CivilizationArtifactRef:
    return CivilizationArtifactRef(
        kind,
        key,
        digest,
        byte_count,
        row_count,
        first_key,
        last_key,
    )


def _overall_coverage(
    boundary: CivilizationBoundaryPublication,
) -> CivilizationCoverage:
    from simulation.civilization_models import CivilizationCoverageState

    states = {row.history.coverage.state for row in boundary.rows}
    if states and states == {CivilizationCoverageState.COMPLETE}:
        return CivilizationCoverage(CivilizationCoverageState.COMPLETE)
    if not states:
        return CivilizationCoverage(CivilizationCoverageState.COMPLETE)
    return CivilizationCoverage(CivilizationCoverageState.PARTIAL, "capture_gap")


class FilesystemCivilizationReader:
    """Read-only committed state; never writes, repairs or globs uncommitted data."""

    def __init__(self, root: Path | str) -> None:
        resolved = Path(root)
        if resolved.is_symlink():
            raise CivilizationError("civilization_storage_corrupt")
        self._root = resolved.resolve()

    def has_run(self, run_id: str) -> bool:
        try:
            state = _decode_state(
                _read_budgeted(
                    _safe_path(_run_root(self._root, run_id), _STATE),
                    CivilizationReadBudget(),
                    metadata=True,
                )
            )
            publication_root = _safe_path(
                _run_root(self._root, run_id),
                "publications",
                str(state["publication_id"]),
            )
            index_content = _read_budgeted(
                _safe_path(publication_root, "catalogue", "index.json"),
                CivilizationReadBudget(),
                metadata=True,
            )
            return (
                state.get("run_id") == run_id
                and civilization_digest(index_content) == state["catalogue_digest"]
            )
        except (CivilizationError, KeyError, TypeError):
            return False

    def _state(self, run_id: str, budget: CivilizationReadBudget) -> dict[str, object]:
        content = _read_budgeted(
            _safe_path(_run_root(self._root, run_id), _STATE),
            budget,
            metadata=True,
        )
        state = _decode_state(content)
        if (
            state.get("run_id") != run_id
            or type(state.get("publication_id")) is not str
            or type(state.get("catalogue_digest")) is not str
            or state.get("catalogue_ref") != "catalogue/index.json"
        ):
            raise CivilizationError("civilization_storage_corrupt")
        return state

    async def publication(
        self, run_id: str, *, budget: CivilizationReadBudget
    ) -> CivilizationPublicationRef | None:
        """Return the current commit, or None only when no commit exists.

        An existing but invalid state file is corruption, never "not published".
        """
        state_path = _safe_path(_run_root(self._root, run_id), _STATE)
        if not state_path.is_file():
            return None
        state = self._state(run_id, budget)
        return CivilizationPublicationRef(
            str(state["publication_id"]),
            str(state["catalogue_digest"]),
            _POLICY,
        )

    def _store_root(
        self, publication_root: Path, budget: CivilizationReadBudget
    ) -> CivilizationStoreRootV2 | None:
        path = _safe_path(publication_root, *CIVILIZATION_STORE_ROOT_PATH.split("/"))
        if not path.is_file():
            return None
        content = _read_budgeted(path, budget, metadata=True)
        return decode_civilization_store_root(content)

    def _row_bounds(
        self,
        publication_root: Path,
        boundary: int,
        budget: CivilizationReadBudget,
    ) -> dict[str, tuple[str, str]]:
        """Load published shard row-key bounds for bounded page skipping.

        Bounds are advisory publisher metadata: they let one page skip shards
        whose last row key is at or before the requested cursor instead of
        re-reading every earlier shard. Row values are still digest-verified
        when a shard is read.
        """
        path = _safe_path(
            publication_root, "boundaries", f"{boundary:08d}", "row-bounds.json"
        )
        if not path.is_file():
            return {}
        if path.stat().st_size > CIVILIZATION_MAX_SHARD_BYTES:
            _LOG.warning(
                "civilization_row_bounds_skipped reason=too_large byte_count=%s",
                path.stat().st_size,
            )
            return {}
        content = _read_budgeted(path, budget)
        value = _decode_state(content)
        raw = value.get("bounds", {})
        if type(raw) is not dict:
            return {}
        prefix = f"boundaries/{boundary:08d}/"
        bounds: dict[str, tuple[str, str]] = {}
        for relative, pair in raw.items():
            if (
                type(relative) is not str
                or not isinstance(pair, list)
                or len(pair) != 2
                or not all(type(item) is str for item in pair)
            ):
                continue
            first, last = cast(list[str], pair)
            bounds[f"{prefix}{relative}"] = (first, last)
        return bounds

    def _index_page(
        self,
        publication_root: Path,
        digest: str,
        path: str,
        budget: CivilizationReadBudget,
    ) -> LineageIndexPage:
        content = _read_budgeted(
            _safe_path(publication_root, *path.split("/")), budget
        )
        if civilization_digest(content) != digest:
            raise CivilizationError("civilization_storage_corrupt")
        page = decode_lineage_index_page(
            content, schema=CIVILIZATION_INDEX_PAGE_SCHEMA
        )
        previous: str | None = None
        for entry in page.entries:
            if entry.last_key < entry.first_key:
                raise CivilizationError("civilization_storage_corrupt")
            if previous is not None and entry.first_key <= previous:
                raise CivilizationError("civilization_storage_corrupt")
            previous = entry.last_key
        return page

    def _iter_index_entries(
        self,
        publication_root: Path,
        root: object,
        budget: CivilizationReadBudget,
        *,
        lower: str | None,
        upper: str | None,
    ) -> Iterator[LineageIndexEntry]:
        from simulation.lineage_store_index import LineageRootRef

        if type(root) is not LineageRootRef or root.digest is None:
            return
        if root.path is None:
            return
        yield from self._walk_index(
            publication_root,
            root.digest,
            root.path,
            budget,
            lower=lower,
            upper=upper,
        )

    def _walk_index(
        self,
        publication_root: Path,
        digest: str,
        path: str,
        budget: CivilizationReadBudget,
        *,
        lower: str | None,
        upper: str | None,
    ) -> Iterator[LineageIndexEntry]:
        page = self._index_page(publication_root, digest, path, budget)
        for entry in page.entries:
            if upper is not None and entry.first_key > upper:
                continue
            if lower is not None and entry.last_key < lower:
                continue
            if entry.is_index:
                yield from self._walk_index(
                    publication_root,
                    entry.digest,
                    entry.path,
                    budget,
                    lower=lower,
                    upper=upper,
                )
            else:
                yield entry

    def _loaded_refs_v2(
        self,
        publication_root: Path,
        store_root: CivilizationStoreRootV2,
        budget: CivilizationReadBudget,
        *,
        after_boundary: int | None,
        limit: int | None,
    ) -> tuple[dict[str, object], tuple[CivilizationBoundaryRef, ...], bool]:
        wanted = None if limit is None else limit + 1
        lower = None if after_boundary is None else f"{after_boundary + 1:08d}"
        refs: list[CivilizationBoundaryRef] = []
        more = False
        for entry in self._iter_index_entries(
            publication_root,
            store_root.catalogue,
            budget,
            lower=lower,
            upper=None,
        ):
            content = _read_budgeted(
                _safe_path(publication_root, *entry.path.split("/")), budget
            )
            if civilization_digest(content) != entry.digest:
                raise CivilizationError("civilization_storage_corrupt")
            for line in content.splitlines(keepends=True):
                if not line.endswith(b"\n"):
                    raise CivilizationError("civilization_storage_corrupt")
                budget.reserve_scan(1)
                value = decode_civilization_value(line)
                if type(value) is not CivilizationBoundaryRef:
                    raise CivilizationError("civilization_storage_corrupt")
                tick = value.cursor.boundary_tick
                if tick is None:
                    raise CivilizationError("civilization_storage_corrupt")
                if after_boundary is not None and tick <= after_boundary:
                    continue
                refs.append(value)
                if wanted is not None and len(refs) >= wanted:
                    more = True
                    break
            if more:
                break
        selected = refs if limit is None else refs[:limit]
        return {}, tuple(selected), more

    def _loaded_refs(
        self,
        run_id: str,
        publication: CivilizationPublicationRef | None,
        budget: CivilizationReadBudget,
        *,
        after_boundary: int | None = None,
        limit: int | None = None,
    ) -> tuple[dict[str, object], tuple[CivilizationBoundaryRef, ...], bool]:
        """Stream verified catalogue pages; never decode an unneeded shard."""
        state = self._state(run_id, budget)
        if publication is not None and (
            publication.publication_id != state["publication_id"]
            or publication.digest != state["catalogue_digest"]
        ):
            raise CivilizationError("civilization_publication_gone")
        publication_root = _safe_path(
            _run_root(self._root, run_id),
            "publications",
            str(state["publication_id"]),
        )
        store_root = self._store_root(publication_root, budget)
        if store_root is not None:
            if (
                store_root.publication_id != state["publication_id"]
                or store_root.policy_version != _POLICY
            ):
                raise CivilizationError("civilization_storage_corrupt")
            _, selected_v2, more_v2 = self._loaded_refs_v2(
                publication_root,
                store_root,
                budget,
                after_boundary=after_boundary,
                limit=limit,
            )
            return state, selected_v2, more_v2
        index_content = _read_budgeted(
            _safe_path(publication_root, "catalogue", "index.json"),
            budget,
            metadata=True,
        )
        expected_digest = state["catalogue_digest"]
        if civilization_digest(index_content) != expected_digest:
            raise CivilizationError("civilization_storage_corrupt")
        index = decode_civilization_value(index_content)
        from simulation.civilization_models import CivilizationHashManifest

        if type(index) is not CivilizationHashManifest:
            raise CivilizationError("civilization_storage_corrupt")
        refs: list[CivilizationBoundaryRef] = []
        more = False
        wanted = None if limit is None else limit + 1
        for child in index.children:
            if after_boundary is not None and int(child.last_key) <= after_boundary:
                continue
            if wanted is not None and len(refs) >= wanted:
                more = True
                break
            try:
                content = _read_budgeted(
                    _safe_path(publication_root, *child.key.split("/")),
                    budget,
                )
            except CivilizationError as exc:
                if (
                    exc.code == "civilization_read_budget"
                    and refs
                    and (after_boundary is None or refs[-1].cursor.boundary_tick)
                ):
                    more = True
                    break
                raise
            if civilization_digest(content) != child.digest:
                raise CivilizationError("civilization_storage_corrupt")
            for line in content.splitlines(keepends=True):
                if not line.endswith(b"\n"):
                    raise CivilizationError("civilization_storage_corrupt")
                try:
                    budget.reserve_scan(1)
                except CivilizationError:
                    if not refs:
                        raise
                    more = True
                    break
                value = decode_civilization_value(line)
                if type(value) is not CivilizationBoundaryRef:
                    raise CivilizationError("civilization_storage_corrupt")
                ref = value
                tick = ref.cursor.boundary_tick
                if tick is None:
                    raise CivilizationError("civilization_storage_corrupt")
                if after_boundary is not None and tick <= after_boundary:
                    continue
                refs.append(ref)
                if wanted is not None and len(refs) >= wanted:
                    more = True
                    break
            if more:
                break
        if wanted is not None and limit is not None and len(refs) > limit:
            more = True
        selected = refs if limit is None else refs[:limit]
        return state, tuple(selected), more

    async def catalogue(
        self,
        run_id: str,
        *,
        after_boundary: int | None,
        publication: CivilizationPublicationRef | None,
        budget: CivilizationReadBudget,
    ) -> CivilizationCataloguePage:
        state, selected, more = self._loaded_refs(
            run_id,
            publication,
            budget,
            after_boundary=after_boundary,
            limit=budget.limit,
        )
        truncated = more and bool(selected)
        next_cursor = (
            None
            if not truncated or not selected
            else str(selected[-1].cursor.boundary_tick)
        )
        if more and not selected:
            raise CivilizationError("civilization_read_budget")
        first_world = selected[0].cursor.world_id if selected else ""
        publication_ref = CivilizationPublicationRef(
            str(state["publication_id"]),
            str(state["catalogue_digest"]),
            _POLICY,
        )
        return CivilizationCataloguePage(
            run_id,
            first_world,
            publication_ref,
            selected,
            next_cursor,
            truncated,
        )

    async def exact_snapshot(
        self,
        cursor: CivilizationCursor,
        *,
        publication: CivilizationPublicationRef,
        budget: CivilizationReadBudget,
    ) -> CivilizationBoundaryRef:
        boundary_tick = cursor.boundary_tick
        if boundary_tick is None:
            raise CivilizationError("civilization_boundary_missing")
        _, refs, _ = self._loaded_refs(
            cursor.run_id,
            publication,
            budget,
            after_boundary=None if boundary_tick == 0 else boundary_tick - 1,
            limit=1,
        )
        if not refs or refs[0].cursor.boundary_tick != boundary_tick:
            raise CivilizationError("civilization_boundary_missing")
        if refs[0].cursor.world_id != cursor.world_id:
            raise CivilizationError("civilization_identity_conflict")
        return refs[0]

    async def rows(
        self,
        cursor: CivilizationCursor,
        scope: CivilizationScope,
        *,
        publication: CivilizationPublicationRef,
        after_key: str | None,
        entity_id: str | None,
        location_id: str | None = None,
        region_id: str | None = None,
        budget: CivilizationReadBudget,
    ) -> CivilizationPage:
        boundary = cursor.boundary_tick
        if boundary is None:
            raise CivilizationError("civilization_boundary_missing")
        _, refs, _ = self._loaded_refs(
            cursor.run_id,
            publication,
            budget,
            after_boundary=None if boundary == 0 else boundary - 1,
            limit=1,
        )
        if not refs or refs[0].cursor.boundary_tick != boundary:
            raise CivilizationError("civilization_boundary_missing")
        if refs[0].cursor.world_id != cursor.world_id:
            raise CivilizationError("civilization_identity_conflict")
        ref = refs[0]
        state = self._state(cursor.run_id, budget)
        publication_root = _safe_path(
            _run_root(self._root, cursor.run_id),
            "publications",
            str(state["publication_id"]),
        )
        store_root = self._store_root(publication_root, budget)
        scope_key = _scope_key(scope)
        scope_tag = scope_key[:_INDEX_SCOPE_TAG_LENGTH]
        candidates: list[tuple[str, str]] = []
        if store_root is not None:
            if store_root.publication_id != state["publication_id"]:
                raise CivilizationError("civilization_storage_corrupt")
            entries = list(
                self._iter_index_entries(
                    publication_root,
                    store_root.rows,
                    budget,
                    lower=f"{scope_tag}|{boundary:08d}|",
                    upper=f"{scope_tag}|{boundary:08d}|\uffff",
                )
            )
            if not entries:
                # Legacy range-key layouts embedded the full scope digest and a
                # truncated row key. Read them only when the bounded tag range
                # found nothing, so new publications never use the old form.
                entries = list(
                    self._iter_index_entries(
                        publication_root,
                        store_root.rows,
                        budget,
                        lower=f"{scope_key}|{boundary:08d}|",
                        upper=f"{scope_key}|{boundary:08d}|\uffff",
                    )
                )
            for entry in entries:
                candidates.append((entry.path, entry.digest))
        else:
            boundary_root = _safe_path(
                publication_root, "boundaries", f"{boundary:08d}"
            )
            manifest_content = _read_budgeted(
                _safe_path(boundary_root, "manifest.json"),
                budget,
                metadata=True,
            )
            if civilization_digest(manifest_content) != ref.manifest_digest:
                raise CivilizationError("civilization_storage_corrupt")
            manifest = decode_civilization_value(manifest_content)
            if type(manifest) is not CivilizationHashManifest:
                raise CivilizationError("civilization_storage_corrupt")
            for child in sorted(
                (
                    child
                    for child in manifest.children
                    if child.key.startswith(
                        f"boundaries/{boundary:08d}/rows/{scope_key}/"
                    )
                ),
                key=lambda child: child.key,
            ):
                candidates.append((child.key, child.digest))
        rows: list[CivilizationMapRow | CivilizationCapturedRow] = []
        next_key: str | None = None
        truncated = False
        last_scanned = after_key
        bounds = (
            self._row_bounds(publication_root, boundary, budget)
            if after_key is not None
            else {}
        )
        for candidate_path, candidate_digest in candidates:
            if after_key is not None:
                bound = bounds.get(candidate_path)
                if bound is not None and bound[1] <= after_key:
                    continue
            try:
                content = _read_budgeted(
                    _safe_path(publication_root, *candidate_path.split("/")),
                    budget,
                )
            except CivilizationError as exc:
                if exc.code == "civilization_read_budget" and last_scanned != after_key:
                    truncated = True
                    next_key = last_scanned
                    break
                raise
            if civilization_digest(content) != candidate_digest:
                raise CivilizationError("civilization_storage_corrupt")
            lines = content.splitlines(keepends=True)
            if not lines:
                continue
            if after_key is not None:
                budget.reserve_scan(1)
                first_row = decode_civilization_value(lines[0])
                budget.reserve_scan(1)
                last_row = decode_civilization_value(lines[-1])
                if (
                    type(first_row) not in _ROW_TYPES
                    or type(last_row) not in _ROW_TYPES
                ):
                    raise CivilizationError("civilization_storage_corrupt")
                typed_last = cast(
                    CivilizationMapRow | CivilizationCapturedRow, last_row
                )
                if typed_last.context.row_id <= after_key:
                    continue
            for line in lines:
                if not line.endswith(b"\n"):
                    raise CivilizationError("civilization_storage_corrupt")
                try:
                    budget.reserve_scan(1)
                except CivilizationError:
                    if last_scanned == after_key:
                        raise
                    truncated = True
                    next_key = last_scanned
                    break
                decoded = decode_civilization_value(line)
                if type(decoded) not in _ROW_TYPES:
                    raise CivilizationError("civilization_storage_corrupt")
                value = cast(CivilizationMapRow | CivilizationCapturedRow, decoded)
                key = value.context.row_id
                if after_key is not None and key <= after_key:
                    continue
                if (
                    (entity_id is not None and not _matches_entity(value, entity_id))
                    or (
                        location_id is not None
                        and not _matches_location(value, location_id)
                    )
                    or (region_id is not None and not _matches_region(value, region_id))
                ):
                    last_scanned = key
                    continue
                if len(rows) >= budget.limit:
                    truncated = True
                    next_key = rows[-1].context.row_id if rows else last_scanned
                    break
                try:
                    budget.reserve_response(
                        len(encode_civilization_value(value)), rows=1
                    )
                except CivilizationError:
                    if not rows and last_scanned == after_key:
                        raise
                    truncated = True
                    next_key = rows[-1].context.row_id if rows else last_scanned
                    break
                rows.append(value)
                last_scanned = key
            if truncated:
                break
        if not truncated:
            next_key = None
        window = (
            cast(CivilizationCapturedRow, rows[0]).history.window
            if rows
            else CivilizationWindow(boundary, boundary)
        )
        return CivilizationPage(
            cursor,
            cursor,
            scope,
            ref.coverage,
            tuple(rows),
            next_key,
            truncated,
            cursor.revision,
            publication,
            window,
        )

    async def markers(
        self,
        cursor: CivilizationCursor,
        *,
        publication: CivilizationPublicationRef,
        budget: CivilizationReadBudget,
    ) -> tuple[CivilizationMarker, ...]:
        ref = await self.exact_snapshot(cursor, publication=publication, budget=budget)
        selection = await self.markers_at(
            ref,
            publication=publication,
            after_key=None,
            evidence_class=None,
            owner_id=None,
            layer=None,
            limit=200,
            budget=budget,
        )
        return selection.markers

    async def markers_at(
        self,
        ref: CivilizationBoundaryRef,
        *,
        publication: CivilizationPublicationRef,
        after_key: str | None,
        evidence_class: CivilizationEvidenceClass | None,
        owner_id: str | None,
        layer: CivilizationLayer | None,
        limit: int,
        budget: CivilizationReadBudget,
    ) -> CivilizationMarkerSelection:
        boundary = ref.cursor.boundary_tick
        if boundary is None:
            raise CivilizationError("civilization_boundary_missing")
        publication_root = _safe_path(
            _run_root(self._root, ref.cursor.run_id),
            "publications",
            publication.publication_id,
        )
        boundary_root = _safe_path(publication_root, "boundaries", f"{boundary:08d}")
        manifest_content = _read_budgeted(
            _safe_path(boundary_root, "manifest.json"),
            budget,
            metadata=True,
        )
        if civilization_digest(manifest_content) != ref.manifest_digest:
            raise CivilizationError("civilization_storage_corrupt")
        manifest = decode_civilization_value(manifest_content)
        if type(manifest) is not CivilizationHashManifest:
            raise CivilizationError("civilization_storage_corrupt")
        children = sorted(
            (
                item
                for item in manifest.children
                if item.key.startswith(f"boundaries/{boundary:08d}/markers/")
            ),
            key=lambda item: item.key,
        )
        markers: list[CivilizationMarker] = []
        next_key: str | None = None
        truncated = False
        last_scanned = after_key
        for item in children:
            try:
                content = _read_budgeted(
                    _safe_path(publication_root, *item.key.split("/")),
                    budget,
                )
            except CivilizationError as exc:
                if exc.code == "civilization_read_budget" and last_scanned != after_key:
                    truncated = True
                    next_key = last_scanned
                    break
                raise
            if civilization_digest(content) != item.digest:
                raise CivilizationError("civilization_storage_corrupt")
            for line in content.splitlines(keepends=True):
                if not line.endswith(b"\n"):
                    raise CivilizationError("civilization_storage_corrupt")
                try:
                    budget.reserve_scan(1)
                except CivilizationError:
                    if last_scanned == after_key:
                        raise
                    truncated = True
                    next_key = last_scanned
                    break
                decoded = decode_civilization_value(line)
                if type(decoded) is not CivilizationMarker:
                    raise CivilizationError("civilization_storage_corrupt")
                marker = decoded
                key = marker.marker_id
                if after_key is not None and key <= after_key:
                    continue
                if (
                    (
                        evidence_class is not None
                        and marker.evidence_class is not evidence_class
                    )
                    or (owner_id is not None and marker.owner_id != owner_id)
                    or (owner_id is None and marker.owner_id is not None)
                    or (layer is not None and marker.layer is not layer)
                ):
                    last_scanned = key
                    continue
                if len(markers) >= limit:
                    truncated = True
                    next_key = markers[-1].marker_id if markers else last_scanned
                    break
                try:
                    budget.reserve_response(
                        len(encode_civilization_value(marker)), rows=1
                    )
                except CivilizationError:
                    if not markers and last_scanned == after_key:
                        raise
                    truncated = True
                    next_key = markers[-1].marker_id if markers else last_scanned
                    break
                markers.append(marker)
                last_scanned = key
            if truncated:
                break
        if not truncated:
            next_key = None
        return CivilizationMarkerSelection(tuple(markers), next_key, truncated)


def _matches_entity(row: object, entity_id: str) -> bool:
    for name in (
        "location_id",
        "project_id",
        "repository_id",
        "record_id",
        "region_id",
        "route_id",
        "candidate_id",
        "journey_id",
        "holder_id",
        "group_id",
        "institution_id",
    ):
        if getattr(row, name, None) == entity_id:
            return True
    return False


def _matches_location(row: object, location_id: str) -> bool:
    context = getattr(row, "context", None)
    for anchor in getattr(context, "anchors", ()) or ():
        if getattr(anchor, "location_id", None) == location_id:
            return True
    for name in (
        "location_id",
        "origin_location_id",
        "destination_location_id",
        "occurrence_location_id",
    ):
        if getattr(row, name, None) == location_id:
            return True
    return False


def _matches_region(row: object, region_id: str) -> bool:
    for name in ("region_id", "region_a", "region_b"):
        if getattr(row, name, None) == region_id:
            return True
    return False


def create_civilization_publisher(root: Path | str) -> FilesystemCivilizationPublisher:
    return FilesystemCivilizationPublisher(root)


def create_civilization_reader(root: Path | str) -> FilesystemCivilizationReader:
    return FilesystemCivilizationReader(root)
