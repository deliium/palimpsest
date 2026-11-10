"""Atomic filesystem store for ``supply-chains-store-v1``."""

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

from simulation.supply_chain_codec import (
    decode_supply_chain_snapshot,
    encode_supply_chain_snapshot,
)
from simulation.supply_chain_models import SupplyChainSnapshot
from simulation.supply_chain_ports import SupplyChainSummary

__all__ = [
    "SUPPLY_CHAIN_STORE_VERSION",
    "SupplyChainPublisherOptions",
    "create_supply_chain_publisher",
    "create_supply_chain_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger("persistence.supply_chain_filesystem")

SUPPLY_CHAIN_STORE_VERSION: Final[str] = "supply-chains-store-v1"
_STATE_FILE: Final[str] = "state.json"
_LOCK_FILE: Final[str] = "store.lock"
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class SupplyChainStoreCorrupt(ValueError):
    def __init__(self) -> None:
        super().__init__("supply_chain_store_corrupt")


@dataclass(frozen=True, slots=True)
class SupplyChainPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8_388_608

    def __post_init__(self) -> None:
        if type(self.max_publications) is not int or self.max_publications <= 0:
            raise ValueError("supply_chain_publications_range")
        if type(self.max_bytes) is not int or self.max_bytes <= 0:
            raise ValueError("supply_chain_bytes_range")


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"supply_chain_store_invalid_{field}")
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(f"supply_chain_store_invalid_{field}")
    return value


def _empty_state() -> dict[str, object]:
    return {"store_version": SUPPLY_CHAIN_STORE_VERSION, "publications": {}}


def _run_root(root: Path, run_id: str) -> Path:
    return root / _token(run_id, field="run_id")


def _load_state(run_dir: Path) -> dict[str, object]:
    path = run_dir / _STATE_FILE
    if not path.exists():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SupplyChainStoreCorrupt() from exc
    if (
        type(data) is not dict
        or data.get("store_version") != SUPPLY_CHAIN_STORE_VERSION
        or type(data.get("publications")) is not dict
    ):
        raise SupplyChainStoreCorrupt()
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

    with (run_dir / _LOCK_FILE).open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _summary(snapshot: SupplyChainSnapshot) -> SupplyChainSummary:
    row = snapshot.summary
    return SupplyChainSummary(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        schema_version=snapshot.schema_version,
        stage_count=row.stage_count,
        edge_count=row.edge_count,
        chain_count=row.chain_count,
        bottleneck_count=row.bottleneck_count,
        location_count=row.location_count,
        organization_count=row.organization_count,
        coverage=row.coverage,
    )


class _Publisher:
    def __init__(self, root: Path, options: SupplyChainPublisherOptions) -> None:
        self._root = root
        self._options = options

    def publish(self, snapshot: SupplyChainSnapshot) -> None:
        if type(snapshot) is not SupplyChainSnapshot:
            raise TypeError("snapshot must be SupplyChainSnapshot")
        run_id = _token(snapshot.run_id, field="run_id")
        publication_id = _token(snapshot.publication_id, field="publication_id")
        payload = encode_supply_chain_snapshot(snapshot)
        run_dir = _run_root(self._root, run_id)
        with _locked(run_dir):
            state = _load_state(run_dir)
            publications = cast(dict[str, object], state["publications"])
            payload_path = run_dir / f"{publication_id}.json"
            existing = publications.get(publication_id)
            if isinstance(existing, dict):
                if payload_path.is_file() and payload_path.read_bytes() == payload:
                    return
                raise ValueError("supply_chain_publication_exists")
            if len(publications) >= self._options.max_publications:
                _LOG.error("supply_chain_store_quota_exceeded")
                raise ValueError("supply_chain_store_quota_exceeded")
            existing_bytes = 0
            for entry in publications.values():
                if isinstance(entry, dict):
                    raw = entry.get("bytes", 0)
                    if isinstance(raw, int):
                        existing_bytes += raw
            if existing_bytes + len(payload) > self._options.max_bytes:
                _LOG.error("supply_chain_store_quota_exceeded")
                raise ValueError("supply_chain_store_quota_exceeded")
            _atomic_write(payload_path, payload)
            publications[publication_id] = {
                "bytes": len(payload),
                "digest": snapshot.digest,
            }
            _atomic_write(
                run_dir / _STATE_FILE,
                json.dumps(state, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                ),
            )
        _LOG.info(
            "supply_chain_snapshot_published publications=%s bytes=%s",
            len(publications),
            len(payload),
        )

    def read_summary(self, run_id: str) -> SupplyChainSummary | None:
        snapshot = self.read_snapshot(run_id)
        return None if snapshot is None else _summary(snapshot)

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> SupplyChainSnapshot | None:
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
        return tuple(
            sorted(str(key) for key in cast(dict[str, object], state["publications"]))
        )

    def read_summary(self, run_id: str) -> SupplyChainSummary | None:
        snapshot = self.read_snapshot(run_id)
        return None if snapshot is None else _summary(snapshot)

    def summary(self, run_id: str) -> SupplyChainSummary | None:
        return self.read_summary(run_id)

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> SupplyChainSnapshot | None:
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
            raise SupplyChainStoreCorrupt()
        path = run_dir / f"{publication_id}.json"
        try:
            snapshot = decode_supply_chain_snapshot(path.read_bytes(), run_id=run_id)
        except Exception as exc:
            _LOG.warning("supply_chain_store_corrupt publication_id=%s", publication_id)
            raise SupplyChainStoreCorrupt() from exc
        if snapshot.publication_id != publication_id:
            raise SupplyChainStoreCorrupt()
        if snapshot.digest != entry.get("digest"):
            raise SupplyChainStoreCorrupt()
        return snapshot


def create_supply_chain_reader(root: Path) -> _Reader:
    return _Reader(Path(root))


def create_supply_chain_publisher(
    root: Path, options: SupplyChainPublisherOptions | None = None
) -> _Publisher:
    return _Publisher(Path(root), options or SupplyChainPublisherOptions())
