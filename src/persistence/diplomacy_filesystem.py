"""Atomic quota-bounded filesystem store for diplomacy snapshots."""

from __future__ import annotations

import fcntl
import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final, cast

from simulation.diplomacy_codec import decode_diplomacy_snapshot
from simulation.diplomacy_models import (
    DiplomacyArtifactError,
    DiplomacySnapshot,
)
from simulation.diplomacy_paging import (
    select_diplomacy_instrument,
    select_diplomacy_instruments,
    select_diplomacy_lineage,
    select_diplomacy_relation,
    select_diplomacy_relations,
)
from simulation.diplomacy_ports import (
    DiplomacyInstrumentDetail,
    DiplomacyPortError,
    DiplomacyPublication,
    DiplomacyRelationDetail,
    DiplomacySummary,
)

__all__ = [
    "DIPLOMACY_STORE_SCHEMA",
    "FilesystemDiplomacyPublisher",
    "FilesystemDiplomacyReader",
    "create_diplomacy_publisher",
    "create_diplomacy_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger("persistence.diplomacy_filesystem")

DIPLOMACY_STORE_SCHEMA: Final[str] = "diplomacy-store-v1"


def _atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


@contextmanager
def _publish_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_state(root: Path) -> dict[str, object]:
    path = root / "state.json"
    if not path.exists():
        return {"schema": DIPLOMACY_STORE_SCHEMA, "publications": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DiplomacyArtifactError("diplomacy_snapshot_invalid") from exc
    if type(payload) is not dict or payload.get("schema") != DIPLOMACY_STORE_SCHEMA:
        raise DiplomacyArtifactError("diplomacy_snapshot_invalid")
    if type(payload.get("publications")) is not list:
        raise DiplomacyArtifactError("diplomacy_snapshot_invalid")
    return payload


class FilesystemDiplomacyPublisher:
    """Publisher port with per-run publication and cumulative byte quotas."""

    def __init__(
        self,
        root: Path | str,
        *,
        max_publications: int = 16,
        max_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self._root = Path(root)
        if type(max_publications) is not int or not 1 <= max_publications <= 1024:
            raise ValueError("diplomacy publication cap is outside range")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 268_435_456:
            raise ValueError("diplomacy byte cap is outside range")
        self._max_publications = max_publications
        self._max_bytes = max_bytes

    def publish(self, publication: DiplomacyPublication) -> None:
        snapshot = publication.snapshot
        payload = _encode(snapshot)
        if snapshot.digest != publication.snapshot_digest:
            raise DiplomacyArtifactError("diplomacy_snapshot_digest_mismatch")
        with _publish_lock(self._root / ".publish.lock"):
            state = _read_state(self._root)
            entries = cast(list[dict[str, Any]], state["publications"])
            same_run = [
                entry for entry in entries if entry.get("run_id") == publication.run_id
            ]
            for entry in entries:
                if entry.get("publication_id") == publication.publication_id:
                    existing = self._root / str(entry.get("path"))
                    if existing.exists() and existing.read_bytes() == payload:
                        return
                    raise DiplomacyArtifactError("diplomacy_publication_exists")
            if len(same_run) >= self._max_publications:
                raise DiplomacyArtifactError("diplomacy_quota_exceeded")
            total_bytes = sum(int(entry.get("bytes", 0)) for entry in entries)
            if total_bytes + len(payload) > self._max_bytes:
                raise DiplomacyArtifactError("diplomacy_quota_exceeded")
            relative = f"publications/{publication.publication_id}.json"
            path = self._root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.tmp")
            temporary.write_bytes(payload)
            os.replace(temporary, path)
            entries.append(
                {
                    "run_id": publication.run_id,
                    "publication_id": publication.publication_id,
                    "snapshot_digest": publication.snapshot_digest,
                    "window_end": snapshot.window_end,
                    "path": relative,
                    "bytes": len(payload),
                }
            )
            state["publications"] = entries
            _atomic_json(self._root / "state.json", state)
        _LOG.info("diplomacy_store_published status=published")


def _encode(snapshot: DiplomacySnapshot) -> bytes:
    from simulation.diplomacy_codec import encode_diplomacy_snapshot

    return encode_diplomacy_snapshot(snapshot)


class FilesystemDiplomacyReader:
    """Reader port over committed diplomacy publications."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def _snapshot(self, run_id: str) -> DiplomacySnapshot:
        state = _read_state(self._root)
        entries = [
            entry
            for entry in cast(list[dict[str, Any]], state["publications"])
            if entry.get("run_id") == run_id
        ]
        if not entries:
            raise DiplomacyPortError("diplomacy_not_found")
        entry = entries[-1]
        path = self._root / str(entry.get("path"))
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise DiplomacyPortError("diplomacy_not_found") from exc
        try:
            snapshot = decode_diplomacy_snapshot(payload)
        except DiplomacyArtifactError as exc:
            raise DiplomacyPortError(exc.code) from exc
        if snapshot.digest != entry.get("snapshot_digest"):
            raise DiplomacyPortError("diplomacy_publication_digest_mismatch")
        return snapshot


    def relations_page(
        self, run_id: str, *, after_key: str | None = None, limit: int = 500
    ) -> DiplomacyRowSelection:
        return select_diplomacy_relations(
            self._snapshot(run_id), after_key=after_key, limit=limit
        )

    def instruments_page(
        self, run_id: str, *, after_key: str | None = None, limit: int = 500
    ) -> DiplomacyRowSelection:
        return select_diplomacy_instruments(
            self._snapshot(run_id), after_key=after_key, limit=limit
        )

    def lineage_page(
        self, run_id: str, *, after_key: str | None = None, limit: int = 500
    ) -> DiplomacyRowSelection:
        return select_diplomacy_lineage(
            self._snapshot(run_id), after_key=after_key, limit=limit
        )

    def read_summary(self, run_id: str) -> DiplomacySummary:
        snapshot = self._snapshot(run_id)
        return DiplomacySummary(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=snapshot.digest,
            summary=snapshot.summary,
            metric_families=snapshot.metric_families,
            coverage=snapshot.coverage,
        )

    def read_relations(
        self, run_id: str, *, cursor: object | None = None
    ) -> tuple[object, ...]:
        snapshot = self._snapshot(run_id)
        after = None if cursor is None else getattr(cursor, "after_key", None)
        return select_diplomacy_relations(snapshot, after_key=after).rows

    def read_relation(self, run_id: str, relation_id: str) -> DiplomacyRelationDetail:
        snapshot = self._snapshot(run_id)
        try:
            selection = select_diplomacy_relation(snapshot, relation_id)
        except DiplomacyArtifactError as exc:
            raise DiplomacyPortError("diplomacy_unknown_relation") from exc
        relation = selection.rows[0]
        return DiplomacyRelationDetail(
            relation=relation, rows=selection.rows, truncated=selection.truncated
        )

    def read_instruments(
        self, run_id: str, *, cursor: object | None = None
    ) -> tuple[object, ...]:
        snapshot = self._snapshot(run_id)
        after = None if cursor is None else getattr(cursor, "after_key", None)
        return select_diplomacy_instruments(snapshot, after_key=after).rows

    def read_instrument(
        self, run_id: str, instrument_id: str
    ) -> DiplomacyInstrumentDetail:
        snapshot = self._snapshot(run_id)
        try:
            selection = select_diplomacy_instrument(snapshot, instrument_id)
        except DiplomacyArtifactError as exc:
            raise DiplomacyPortError("diplomacy_unknown_instrument") from exc
        instrument = selection.rows[0]
        return DiplomacyInstrumentDetail(
            instrument=instrument, rows=selection.rows, truncated=selection.truncated
        )

    def read_lineage(
        self, run_id: str, *, cursor: object | None = None
    ) -> tuple[object, ...]:
        snapshot = self._snapshot(run_id)
        after = None if cursor is None else getattr(cursor, "after_key", None)
        return select_diplomacy_lineage(snapshot, after_key=after).rows

    def read_publication(self, publication_id: str) -> DiplomacyPublication | None:
        state = _read_state(self._root)
        for entry in cast(list[dict[str, Any]], state["publications"]):
            if entry.get("publication_id") == publication_id:
                snapshot = self._snapshot(str(entry.get("run_id")))
                return DiplomacyPublication(
                    run_id=snapshot.run_id,
                    publication_id=snapshot.publication_id,
                    snapshot_digest=snapshot.digest,
                    snapshot=snapshot,
                )
        return None


def create_diplomacy_publisher(
    root: Path | str, *, max_publications: int = 16, max_bytes: int = 8_388_608
) -> FilesystemDiplomacyPublisher:
    return FilesystemDiplomacyPublisher(
        root, max_publications=max_publications, max_bytes=max_bytes
    )


def create_diplomacy_reader(root: Path | str) -> FilesystemDiplomacyReader:
    return FilesystemDiplomacyReader(root)
