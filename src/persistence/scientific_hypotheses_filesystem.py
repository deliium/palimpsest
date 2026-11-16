"""Atomic filesystem store for ``scientific-hypotheses-store-v1``."""

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

from simulation.scientific_hypotheses_codec import (
    decode_scientific_hypotheses_snapshot,
    encode_scientific_hypotheses_snapshot,
)
from simulation.scientific_hypotheses_models import ScientificHypothesesSnapshot
from simulation.scientific_hypotheses_ports import (
    ScientificHypothesesPublisher,
    ScientificHypothesesReader,
)

__all__ = [
    "SCIENTIFIC_HYPOTHESES_STORE_VERSION",
    "ScientificHypothesesPublisherOptions",
    "ScientificHypothesesStoreReceipt",
    "scientific_hypotheses_store_publisher",
    "scientific_hypotheses_store_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.scientific_hypotheses_filesystem"
)

SCIENTIFIC_HYPOTHESES_STORE_VERSION: Final[str] = "scientific-hypotheses-store-v1"
_STATE_FILE: Final[str] = "state.json"
_LOCK_FILE: Final[str] = "store.lock"
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)


@dataclass(frozen=True, slots=True)
class ScientificHypothesesPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8_388_608

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_publications, bool)
            or type(self.max_publications) is not int
            or self.max_publications <= 0
        ):
            raise ValueError("scientific_hypotheses_publications_range")
        if (
            isinstance(self.max_bytes, bool)
            or type(self.max_bytes) is not int
            or self.max_bytes <= 0
        ):
            raise ValueError("scientific_hypotheses_bytes_range")


@dataclass(frozen=True, slots=True)
class ScientificHypothesesStoreReceipt:
    run_id: str
    publication_id: str
    digest: str
    stored: bool
    reason_code: str
    coverage: str


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"scientific_hypotheses_store_invalid_{field}")
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(f"scientific_hypotheses_store_invalid_{field}")
    return value


def _empty_state() -> dict[str, object]:
    return {
        "store_version": SCIENTIFIC_HYPOTHESES_STORE_VERSION,
        "latest": "",
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
        raise ValueError("scientific_hypotheses_store_corrupt") from exc
    if type(data) is not dict:
        raise ValueError("scientific_hypotheses_store_corrupt")
    if data.get("store_version") != SCIENTIFIC_HYPOTHESES_STORE_VERSION:
        raise ValueError("scientific_hypotheses_store_corrupt")
    if type(data.get("publications")) is not dict:
        raise ValueError("scientific_hypotheses_store_corrupt")
    if type(data.get("latest")) is not str:
        raise ValueError("scientific_hypotheses_store_corrupt")
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


class _Publisher(ScientificHypothesesPublisher):
    def __init__(
        self, root: Path, options: ScientificHypothesesPublisherOptions
    ) -> None:
        self._root = root
        self._options = options

    def publish(self, snapshot: object) -> ScientificHypothesesStoreReceipt:
        if type(snapshot) is not ScientificHypothesesSnapshot:
            raise TypeError("snapshot must be ScientificHypothesesSnapshot")
        payload = encode_scientific_hypotheses_snapshot(snapshot)
        if len(payload) > self._options.max_bytes:
            raise ValueError("scientific_hypotheses_store_quota_exceeded")
        run_dir = _run_root(self._root, snapshot.run_id)
        with _locked(run_dir):
            state = _load_state(run_dir)
            publications = state["publications"]
            assert isinstance(publications, dict)
            existing = publications.get(snapshot.publication_id)
            if existing is not None:
                if (
                    type(existing) is not dict
                    or existing.get("digest") != snapshot.internal_digest
                ):
                    _LOG.warning("scientific_hypotheses_publication_exists")
                    raise ValueError("scientific_hypotheses_publication_exists")
                return ScientificHypothesesStoreReceipt(
                    run_id=snapshot.run_id,
                    publication_id=snapshot.publication_id,
                    digest=snapshot.internal_digest,
                    stored=False,
                    reason_code="published",
                    coverage=snapshot.summary.coverage,
                )
            if len(publications) >= self._options.max_publications:
                _LOG.warning("scientific_hypotheses_store_quota_exceeded")
                raise ValueError("scientific_hypotheses_store_quota_exceeded")
            existing_bytes = 0
            for entry in publications.values():
                if isinstance(entry, dict):
                    raw_bytes = entry.get("bytes", 0)
                    if isinstance(raw_bytes, int):
                        existing_bytes += raw_bytes
            if existing_bytes + len(payload) > self._options.max_bytes:
                _LOG.warning("scientific_hypotheses_store_quota_exceeded")
                raise ValueError("scientific_hypotheses_store_quota_exceeded")
            _atomic_write(run_dir / f"{snapshot.publication_id}.json", payload)
            publications[snapshot.publication_id] = {
                "digest": snapshot.internal_digest,
                "bytes": len(payload),
            }
            state["latest"] = snapshot.publication_id
            _atomic_write(
                run_dir / _STATE_FILE,
                json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
                + b"\n",
            )
        _LOG.info(
            "scientific_hypotheses_store_published publications=%s bytes=%s",
            len(publications),
            len(payload),
        )
        return ScientificHypothesesStoreReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.internal_digest,
            stored=True,
            reason_code="published",
            coverage=snapshot.summary.coverage,
        )


class _Reader(ScientificHypothesesReader):
    def __init__(self, root: Path) -> None:
        self._root = root

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> ScientificHypothesesSnapshot:
        run_dir = _run_root(self._root, run_id)
        state = _load_state(run_dir)
        publications = state["publications"]
        assert isinstance(publications, dict)
        selected = publication_id
        if selected is None:
            latest = state.get("latest")
            selected = (
                latest
                if isinstance(latest, str) and latest
                else (sorted(publications)[-1] if publications else None)
            )
        if selected is None or selected not in publications:
            raise ValueError("scientific_hypotheses_publication_missing")
        path = run_dir / f"{_token(selected, field='publication_id')}.json"
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ValueError("scientific_hypotheses_store_corrupt") from exc
        snapshot = decode_scientific_hypotheses_snapshot(payload, run_id=run_id)
        if snapshot.publication_id != selected:
            raise ValueError("scientific_hypotheses_store_corrupt")
        return snapshot


def scientific_hypotheses_store_publisher(
    root: Path,
    *,
    options: ScientificHypothesesPublisherOptions | None = None,
) -> ScientificHypothesesPublisher:
    """Create one atomic hypothesis snapshot publisher."""

    active = options or ScientificHypothesesPublisherOptions()
    if type(active) is not ScientificHypothesesPublisherOptions:
        raise TypeError("options must be ScientificHypothesesPublisherOptions")
    _LOG.info("scientific_hypotheses_store_ready")
    return _Publisher(root, active)


def scientific_hypotheses_store_reader(
    root: Path,
) -> ScientificHypothesesReader:
    """Create one hypothesis snapshot reader."""

    _LOG.info("scientific_hypotheses_store_ready")
    return _Reader(root)
