# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Atomic filesystem store for ``migration-displacement-store-v1``."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from simulation.migration_displacement_codec import (
    decode_migration_displacement_snapshot,
    encode_migration_displacement_snapshot,
)
from simulation.migration_displacement_models import MigrationDisplacementSnapshot
from simulation.migration_displacement_ports import MigrationDisplacementSummary

__all__ = [
    "MIGRATION_DISPLACEMENT_STORE_VERSION",
    "MigrationDisplacementPublisherOptions",
    "create_migration_displacement_publisher",
    "create_migration_displacement_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.migration_displacement_filesystem"
)

MIGRATION_DISPLACEMENT_STORE_VERSION: Final[str] = "migration-displacement-store-v1"
_STATE_FILE: Final[str] = "state.json"
_LOCK_FILE: Final[str] = "store.lock"
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True, slots=True)
class MigrationDisplacementPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8_388_608

    def __post_init__(self) -> None:
        if type(self.max_publications) is not int or self.max_publications <= 0:
            raise ValueError("migration_displacement_publications_range")
        if type(self.max_bytes) is not int or self.max_bytes <= 0:
            raise ValueError("migration_displacement_bytes_range")


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"migration_displacement_store_invalid_{field}")
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(f"migration_displacement_store_invalid_{field}")
    return value


def _empty_state() -> dict[str, object]:
    return {
        "store_version": MIGRATION_DISPLACEMENT_STORE_VERSION,
        "publications": {},
    }


def _run_root(root: Path, run_id: str) -> Path:
    return root / _token(run_id, field="run_id")


def _load_state(run_dir: Path) -> dict[str, object]:
    path = run_dir / _STATE_FILE
    if not path.exists():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("migration_displacement_store_corrupt") from exc
    if type(data) is not dict:
        raise ValueError("migration_displacement_store_corrupt")
    if data.get("store_version") != MIGRATION_DISPLACEMENT_STORE_VERSION:
        raise ValueError("migration_displacement_store_corrupt")
    publications = data.get("publications")
    if type(publications) is not dict:
        raise ValueError("migration_displacement_store_corrupt")
    return data


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _locked(run_dir: Path) -> Iterator[None]:
    run_dir.mkdir(parents=True, exist_ok=True)
    import fcntl

    lock_path = run_dir / _LOCK_FILE
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _summary_from_snapshot(
    snapshot: MigrationDisplacementSnapshot,
) -> MigrationDisplacementSummary:
    summary = snapshot.summary
    return MigrationDisplacementSummary(
        run_id=summary.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        schema_version=snapshot.schema_version,
        candidate_count=summary.candidate_count,
        wave_count=summary.wave_count,
        cluster_count=summary.cluster_count,
        outcome_count=summary.outcome_count,
        movement_count=summary.movement_count,
        cause_count=summary.cause_count,
        coverage=summary.coverage,
    )


class _Publisher:
    def __init__(
        self, root: Path, options: MigrationDisplacementPublisherOptions
    ) -> None:
        self._root = root
        self._options = options

    def publish(self, snapshot: MigrationDisplacementSnapshot) -> None:
        if type(snapshot) is not MigrationDisplacementSnapshot:
            raise TypeError("snapshot must be MigrationDisplacementSnapshot")
        run_id = _token(snapshot.summary.run_id, field="run_id")
        publication_id = _token(snapshot.publication_id, field="publication_id")
        payload = encode_migration_displacement_snapshot(snapshot)
        run_dir = _run_root(self._root, run_id)
        with _locked(run_dir):
            state = _load_state(run_dir)
            publications = cast(dict[str, object], state["publications"])
            existing = publications.get(publication_id)
            payload_path = run_dir / f"{publication_id}.json"
            if isinstance(existing, dict):
                if payload_path.is_file() and payload_path.read_bytes() == payload:
                    return
                raise ValueError("migration_displacement_publication_exists")
            if len(publications) >= self._options.max_publications:
                raise ValueError("migration_displacement_quota_exceeded")
            existing_bytes = sum(
                int(cast(dict[str, object], entry).get("bytes", 0))
                for entry in publications.values()
                if isinstance(entry, dict)
            )
            if existing_bytes + len(payload) > self._options.max_bytes:
                raise ValueError("migration_displacement_quota_exceeded")
            _atomic_write(payload_path, payload)
            publications[publication_id] = {
                "bytes": len(payload),
                "digest": snapshot.digest,
            }
            content = json.dumps(
                state, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            _atomic_write(run_dir / _STATE_FILE, content)
        row_total = (
            len(snapshot.candidates)
            + len(snapshot.movements)
            + len(snapshot.causes)
            + len(snapshot.routes)
            + len(snapshot.clusters)
            + len(snapshot.waves)
            + len(snapshot.outcomes)
            + len(snapshot.lineage)
            + len(snapshot.alignment)
            + len(snapshot.metric_provenance)
        )
        _LOG.info(
            "migration_displacement_store_published rows=%s bytes=%s",
            row_total,
            len(payload),
        )

    def read_summary(self, run_id: str) -> MigrationDisplacementSummary | None:
        snapshot = self.read_snapshot(run_id)
        if snapshot is None:
            return None
        return _summary_from_snapshot(snapshot)

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> MigrationDisplacementSnapshot | None:
        return _Reader(self._root).read_snapshot(run_id, publication_id)

    def list_publications(self, run_id: str) -> tuple[str, ...]:
        return _Reader(self._root).list_publications(run_id)


class _Reader:
    def __init__(self, root: Path) -> None:
        self._root = root

    def list_publications(self, run_id: str) -> tuple[str, ...]:
        run_dir = _run_root(self._root, run_id)
        if not (run_dir / _STATE_FILE).exists():
            return ()
        state = _load_state(run_dir)
        publications = cast(dict[str, object], state["publications"])
        return tuple(sorted(str(key) for key in publications))

    def read_summary(self, run_id: str) -> MigrationDisplacementSummary | None:
        snapshot = self.read_snapshot(run_id)
        if snapshot is None:
            return None
        return _summary_from_snapshot(snapshot)

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> MigrationDisplacementSnapshot | None:
        run_dir = _run_root(self._root, run_id)
        if not (run_dir / _STATE_FILE).exists():
            return None
        state = _load_state(run_dir)
        publications = cast(dict[str, object], state["publications"])
        if not publications:
            return None
        if publication_id is None:
            publication_id = sorted(str(key) for key in publications)[-1]
        else:
            publication_id = _token(publication_id, field="publication_id")
        entry = publications.get(publication_id)
        if entry is None:
            return None
        if type(entry) is not dict:
            raise ValueError("migration_displacement_store_corrupt")
        path = run_dir / f"{publication_id}.json"
        try:
            payload = path.read_bytes()
            snapshot = decode_migration_displacement_snapshot(payload)
        except Exception as exc:
            raise ValueError("migration_displacement_store_corrupt") from exc
        if snapshot.publication_id != publication_id:
            raise ValueError("migration_displacement_store_corrupt")
        if snapshot.digest != entry.get("digest"):
            raise ValueError("migration_displacement_store_corrupt")
        return snapshot

    def summary(self, run_id: str) -> MigrationDisplacementSummary | None:
        return self.read_summary(run_id)


def create_migration_displacement_reader(root: Path) -> _Reader:
    return _Reader(Path(root))


def create_migration_displacement_publisher(
    root: Path, options: MigrationDisplacementPublisherOptions | None = None
) -> _Publisher:
    return _Publisher(Path(root), options or MigrationDisplacementPublisherOptions())
