"""Atomic filesystem store for ``credit-relationships-store-v1``."""

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

from simulation.credit_relationships_codec import (
    decode_credit_relationships_snapshot,
    encode_credit_relationships_snapshot,
)
from simulation.credit_relationships_models import CreditRelationshipsSnapshot
from simulation.credit_relationships_ports import (
    CreditRelationshipsPublication,
    CreditRelationshipsSummary,
)

__all__ = [
    "CREDIT_RELATIONSHIPS_STORE_VERSION",
    "CreditRelationshipsPublisherOptions",
    "create_credit_relationships_publisher",
    "create_credit_relationships_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.credit_relationships_filesystem"
)

CREDIT_RELATIONSHIPS_STORE_VERSION: Final[str] = "credit-relationships-store-v1"
_STATE_FILE: Final[str] = "state.json"
_LOCK_FILE: Final[str] = "store.lock"
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)


@dataclass(frozen=True, slots=True)
class CreditRelationshipsPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8_388_608

    def __post_init__(self) -> None:
        if type(self.max_publications) is not int or self.max_publications <= 0:
            raise ValueError("credit_relationships_publications_range")
        if type(self.max_bytes) is not int or self.max_bytes <= 0:
            raise ValueError("credit_relationships_bytes_range")


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"credit_relationships_store_invalid_{field}")
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(f"credit_relationships_store_invalid_{field}")
    return value


def _empty_state() -> dict[str, object]:
    return {
        "store_version": CREDIT_RELATIONSHIPS_STORE_VERSION,
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
        raise ValueError("credit_relationships_store_corrupt") from exc
    if type(data) is not dict:
        raise ValueError("credit_relationships_store_corrupt")
    if data.get("store_version") != CREDIT_RELATIONSHIPS_STORE_VERSION:
        raise ValueError("credit_relationships_store_corrupt")
    if type(data.get("publications")) is not dict:
        raise ValueError("credit_relationships_store_corrupt")
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


def _summary(snapshot: CreditRelationshipsSnapshot) -> CreditRelationshipsSummary:
    row = snapshot.summary
    return CreditRelationshipsSummary(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        coverage=row.coverage,
        relationship_count=row.relationship_count,
        claim_count=row.claim_count,
        performance_count=row.performance_count,
        distribution_count=row.distribution_count,
        counterparty_count=row.counterparty_count,
        alignment_count=row.alignment_count,
        truncated=row.truncated,
    )


class _Publisher:
    def __init__(
        self, root: Path, options: CreditRelationshipsPublisherOptions
    ) -> None:
        self._root = root
        self._options = options

    def publish(
        self, snapshot: CreditRelationshipsSnapshot
    ) -> CreditRelationshipsPublication:
        if type(snapshot) is not CreditRelationshipsSnapshot:
            raise TypeError("snapshot must be CreditRelationshipsSnapshot")
        run_id = _token(snapshot.run_id, field="run_id")
        publication_id = _token(snapshot.publication_id, field="publication_id")
        payload = encode_credit_relationships_snapshot(snapshot)
        run_dir = _run_root(self._root, run_id)
        with _locked(run_dir):
            state = _load_state(run_dir)
            publications = cast(dict[str, object], state["publications"])
            existing = publications.get(publication_id)
            payload_path = run_dir / f"{publication_id}.json"
            if isinstance(existing, dict):
                if payload_path.is_file() and payload_path.read_bytes() == payload:
                    return CreditRelationshipsPublication(
                        run_id=run_id,
                        publication_id=publication_id,
                        digest=snapshot.digest,
                        byte_size=len(payload),
                    )
                raise ValueError("credit_relationships_publication_exists")
            if len(publications) >= self._options.max_publications:
                _LOG.warning("credit_relationships_store_quota")
                raise ValueError("credit_relationships_store_quota")
            existing_bytes = 0
            for entry in publications.values():
                if isinstance(entry, dict):
                    raw_bytes = entry.get("bytes", 0)
                    if isinstance(raw_bytes, int):
                        existing_bytes += raw_bytes
            if existing_bytes + len(payload) > self._options.max_bytes:
                _LOG.warning("credit_relationships_store_quota")
                raise ValueError("credit_relationships_store_quota")
            _atomic_write(payload_path, payload)
            publications[publication_id] = {
                "bytes": len(payload),
                "digest": snapshot.digest,
            }
            content = json.dumps(
                state, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            _atomic_write(run_dir / _STATE_FILE, content)
        _LOG.info(
            "credit_relationships_publication_completed stored=true "
            "publications=%s bytes=%s",
            len(publications),
            len(payload),
        )
        return CreditRelationshipsPublication(
            run_id=run_id,
            publication_id=publication_id,
            digest=snapshot.digest,
            byte_size=len(payload),
        )

    def read_summary(self, run_id: str) -> CreditRelationshipsSummary | None:
        snapshot = self.read_snapshot(run_id)
        return None if snapshot is None else _summary(snapshot)

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> CreditRelationshipsSnapshot | None:
        return _Reader(self._root).read_snapshot(run_id, publication_id)

    def list_publications(
        self, run_id: str
    ) -> tuple[CreditRelationshipsPublication, ...]:
        return _Reader(self._root).list_publications(run_id)


class _Reader:
    def __init__(self, root: Path) -> None:
        self._root = root

    def list_publications(
        self, run_id: str
    ) -> tuple[CreditRelationshipsPublication, ...]:
        run_dir = _run_root(self._root, run_id)
        if not (run_dir / _STATE_FILE).exists():
            return ()
        state = _load_state(run_dir)
        publications = cast(dict[str, object], state["publications"])
        values: list[CreditRelationshipsPublication] = []
        for key in sorted(str(item) for item in publications):
            entry = publications[key]
            if type(entry) is not dict:
                raise ValueError("credit_relationships_store_corrupt")
            raw_bytes = entry.get("bytes", 0)
            digest = entry.get("digest", "")
            if type(raw_bytes) is not int or type(digest) is not str:
                raise ValueError("credit_relationships_store_corrupt")
            values.append(
                CreditRelationshipsPublication(
                    run_id=run_id,
                    publication_id=key,
                    digest=digest,
                    byte_size=raw_bytes,
                )
            )
        return tuple(values)

    def read_summary(self, run_id: str) -> CreditRelationshipsSummary | None:
        snapshot = self.read_snapshot(run_id)
        return None if snapshot is None else _summary(snapshot)

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> CreditRelationshipsSnapshot | None:
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
            raise ValueError("credit_relationships_store_corrupt")
        path = run_dir / f"{publication_id}.json"
        try:
            snapshot = decode_credit_relationships_snapshot(
                path.read_bytes(), run_id=run_id
            )
        except Exception as exc:
            _LOG.warning("credit_relationships_store_corrupt")
            raise ValueError("credit_relationships_store_corrupt") from exc
        if snapshot.publication_id != publication_id:
            raise ValueError("credit_relationships_store_corrupt")
        if snapshot.digest != entry.get("digest"):
            raise ValueError("credit_relationships_store_corrupt")
        return snapshot


def create_credit_relationships_reader(root: Path) -> _Reader:
    return _Reader(Path(root))


def create_credit_relationships_publisher(
    root: Path,
    options: CreditRelationshipsPublisherOptions | None = None,
) -> _Publisher:
    return _Publisher(
        Path(root),
        CreditRelationshipsPublisherOptions() if options is None else options,
    )
