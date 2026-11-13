"""Atomic filesystem store for ``economic-inequality-store-v1``."""

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
from typing import Final

from simulation.economic_inequality_codec import (
    decode_economic_inequality_snapshot,
    encode_economic_inequality_snapshot,
)
from simulation.economic_inequality_models import EconomicInequalitySnapshot
from simulation.economic_inequality_ports import (
    EconomicInequalityPublisher,
    EconomicInequalityReader,
)

__all__ = [
    "ECONOMIC_INEQUALITY_STORE_VERSION",
    "EconomicInequalityPublisherOptions",
    "create_economic_inequality_publisher",
    "create_economic_inequality_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.economic_inequality_filesystem"
)

ECONOMIC_INEQUALITY_STORE_VERSION: Final[str] = "economic-inequality-store-v1"
_STATE_FILE: Final[str] = "state.json"
_LOCK_FILE: Final[str] = "store.lock"
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)


@dataclass(frozen=True, slots=True)
class EconomicInequalityPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8_388_608

    def __post_init__(self) -> None:
        if type(self.max_publications) is not int or self.max_publications <= 0:
            raise ValueError("economic_inequality_publications_range")
        if type(self.max_bytes) is not int or self.max_bytes <= 0:
            raise ValueError("economic_inequality_bytes_range")


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"economic_inequality_store_invalid_{field}")
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(f"economic_inequality_store_invalid_{field}")
    return value


def _empty_state() -> dict[str, object]:
    return {"store_version": ECONOMIC_INEQUALITY_STORE_VERSION, "publications": {}}


def _run_root(root: Path, run_id: str) -> Path:
    return root / _token(run_id, field="run_id")


def _load_state(run_dir: Path) -> dict[str, object]:
    path = run_dir / _STATE_FILE
    if not path.exists():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("economic_inequality_store_corrupt") from exc
    if type(data) is not dict:
        raise ValueError("economic_inequality_store_corrupt")
    if data.get("store_version") != ECONOMIC_INEQUALITY_STORE_VERSION:
        raise ValueError("economic_inequality_store_corrupt")
    if type(data.get("publications")) is not dict:
        raise ValueError("economic_inequality_store_corrupt")
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


@dataclass(frozen=True, slots=True)
class _Receipt:
    run_id: str
    publication_id: str
    digest: str
    stored: bool
    reason_code: str
    coverage: str
    notices: tuple[str, ...] = ()


class _Publisher(EconomicInequalityPublisher):
    def __init__(
        self, root: Path, options: EconomicInequalityPublisherOptions
    ) -> None:
        self._root = root
        self._options = options

    def publish(self, snapshot: object) -> _Receipt:
        if type(snapshot) is not EconomicInequalitySnapshot:
            raise TypeError("snapshot must be EconomicInequalitySnapshot")
        payload = encode_economic_inequality_snapshot(snapshot)
        if len(payload) > self._options.max_bytes:
            raise ValueError("economic_inequality_store_quota_exceeded")
        run_dir = _run_root(self._root, snapshot.run_id)
        with _locked(run_dir):
            state = _load_state(run_dir)
            publications = state["publications"]
            assert isinstance(publications, dict)
            existing = publications.get(snapshot.publication_id)
            if existing is not None:
                if (
                    type(existing) is not dict
                    or existing.get("digest") != snapshot.digest
                ):
                    raise ValueError(
                        "economic_inequality_publication_exists"
                    )
                return _Receipt(
                    run_id=snapshot.run_id,
                    publication_id=snapshot.publication_id,
                    digest=snapshot.digest,
                    stored=False,
                    reason_code="published",
                    coverage=snapshot.summary.coverage,
                )
            if len(publications) >= self._options.max_publications:
                _LOG.warning("economic_inequality_store_quota_exceeded")
                raise ValueError("economic_inequality_store_quota_exceeded")
            existing_bytes = 0
            for entry in publications.values():
                if isinstance(entry, dict):
                    raw_bytes = entry.get("bytes", 0)
                    if isinstance(raw_bytes, int):
                        existing_bytes += raw_bytes
            if existing_bytes + len(payload) > self._options.max_bytes:
                _LOG.warning("economic_inequality_store_quota_exceeded")
                raise ValueError("economic_inequality_store_quota_exceeded")
            _atomic_write(run_dir / f"{snapshot.publication_id}.json", payload)
            publications[snapshot.publication_id] = {
                "digest": snapshot.digest,
                "bytes": len(payload),
            }
            _atomic_write(
                run_dir / _STATE_FILE,
                json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
                + b"\n",
            )
        _LOG.info(
            "economic_inequality_published stored=%s coverage=%s",
            True,
            snapshot.summary.coverage,
        )
        return _Receipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=True,
            reason_code="published",
            coverage=snapshot.summary.coverage,
        )


class _Reader(EconomicInequalityReader):
    def __init__(self, root: Path) -> None:
        self._root = root

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> EconomicInequalitySnapshot:
        run_dir = _run_root(self._root, run_id)
        state = _load_state(run_dir)
        publications = state["publications"]
        assert isinstance(publications, dict)
        selected = publication_id
        if selected is None:
            if not publications:
                raise ValueError("economic_inequality_store_missing")
            selected = sorted(publications)[-1]
        if selected not in publications:
            raise ValueError("economic_inequality_store_missing")
        path = run_dir / f"{_token(selected, field='publication_id')}.json"
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ValueError("economic_inequality_store_corrupt") from exc
        snapshot = decode_economic_inequality_snapshot(payload, run_id=run_id)
        if snapshot.publication_id != selected:
            raise ValueError("economic_inequality_store_corrupt")
        return snapshot


def create_economic_inequality_publisher(
    root: Path,
    *,
    options: EconomicInequalityPublisherOptions | None = None,
) -> EconomicInequalityPublisher:
    """Create one atomic inequality snapshot publisher."""

    active = options or EconomicInequalityPublisherOptions()
    if type(active) is not EconomicInequalityPublisherOptions:
        raise TypeError("options must be EconomicInequalityPublisherOptions")
    _LOG.info("economic_inequality_store_ready")
    return _Publisher(root, active)


def create_economic_inequality_reader(
    root: Path,
) -> EconomicInequalityReader:
    """Create one inequality snapshot reader."""

    _LOG.info("economic_inequality_store_ready")
    return _Reader(root)
