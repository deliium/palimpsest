# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Atomic filesystem store for ``infrastructure-networks-store-v1``."""

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

from simulation.infrastructure_codec import (
    decode_infrastructure_networks_snapshot,
    encode_infrastructure_networks_snapshot,
)
from simulation.infrastructure_models import InfrastructureNetworksSnapshot
from simulation.infrastructure_paging import (
    TravelRouteRowSelection,
    page_travel_routes,
)
from simulation.infrastructure_ports import (
    InfrastructureNetworksSummary,
)

__all__ = [
    "INFRASTRUCTURE_NETWORKS_STORE_VERSION",
    "InfrastructureNetworksPublisherOptions",
    "create_infrastructure_networks_publisher",
    "create_infrastructure_networks_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.infrastructure_networks_filesystem"
)

INFRASTRUCTURE_NETWORKS_STORE_VERSION: Final[str] = "infrastructure-networks-store-v1"
_STATE_FILE: Final[str] = "state.json"
_LOCK_FILE: Final[str] = "store.lock"
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8_388_608

    def __post_init__(self) -> None:
        if type(self.max_publications) is not int or self.max_publications <= 0:
            raise ValueError("infrastructure_networks_publications_range")
        if type(self.max_bytes) is not int or self.max_bytes <= 0:
            raise ValueError("infrastructure_networks_bytes_range")


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"infrastructure_networks_store_invalid_{field}")
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(f"infrastructure_networks_store_invalid_{field}")
    return value


def _empty_state() -> dict[str, object]:
    return {
        "store_version": INFRASTRUCTURE_NETWORKS_STORE_VERSION,
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
        raise ValueError("infrastructure_networks_store_corrupt") from exc
    if type(data) is not dict:
        raise ValueError("infrastructure_networks_store_corrupt")
    if data.get("store_version") != INFRASTRUCTURE_NETWORKS_STORE_VERSION:
        raise ValueError("infrastructure_networks_store_corrupt")
    publications = data.get("publications")
    if type(publications) is not dict:
        raise ValueError("infrastructure_networks_store_corrupt")
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
    snapshot: InfrastructureNetworksSnapshot,
) -> InfrastructureNetworksSummary:
    summary = snapshot.summary
    return InfrastructureNetworksSummary(
        run_id=summary.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        schema_version=snapshot.schema_version,
        asset_count=summary.asset_count,
        node_count=summary.node_count,
        edge_count=summary.edge_count,
        operational_count=summary.operational_count,
        damaged_count=summary.damaged_count,
        destroyed_count=summary.destroyed_count,
        effects_active_count=summary.effects_active_count,
        coverage=summary.coverage,
    )


class _Publisher:
    def __init__(
        self, root: Path, options: InfrastructureNetworksPublisherOptions
    ) -> None:
        self._root = root
        self._options = options

    def publish(self, snapshot: InfrastructureNetworksSnapshot) -> None:
        if type(snapshot) is not InfrastructureNetworksSnapshot:
            raise TypeError("snapshot must be InfrastructureNetworksSnapshot")
        run_id = _token(snapshot.summary.run_id, field="run_id")
        publication_id = _token(snapshot.publication_id, field="publication_id")
        payload = encode_infrastructure_networks_snapshot(snapshot)
        run_dir = _run_root(self._root, run_id)
        with _locked(run_dir):
            state = _load_state(run_dir)
            publications = cast(dict[str, object], state["publications"])
            existing = publications.get(publication_id)
            payload_path = run_dir / f"{publication_id}.json"
            if isinstance(existing, dict):
                if payload_path.is_file() and payload_path.read_bytes() == payload:
                    return
                raise ValueError("infrastructure_networks_publication_exists")
            if len(publications) >= self._options.max_publications:
                raise ValueError("infrastructure_networks_quota_exceeded")
            existing_bytes = sum(
                int(cast(dict[str, object], entry).get("bytes", 0))
                for entry in publications.values()
                if isinstance(entry, dict)
            )
            if existing_bytes + len(payload) > self._options.max_bytes:
                raise ValueError("infrastructure_networks_quota_exceeded")
            _atomic_write(payload_path, payload)
            publications[publication_id] = {
                "bytes": len(payload),
                "digest": snapshot.digest,
            }
            content = json.dumps(state, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
            _atomic_write(run_dir / _STATE_FILE, content)
        row_total = len(snapshot.assets)
        _LOG.info(
            "infrastructure_networks_store_published rows=%s bytes=%s",
            row_total,
            len(payload),
        )

    def read_summary(self, run_id: str) -> InfrastructureNetworksSummary | None:
        snapshot = self.read_snapshot(run_id)
        if snapshot is None:
            return None
        return _summary_from_snapshot(snapshot)

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> InfrastructureNetworksSnapshot | None:
        return _Reader(self._root).read_snapshot(run_id, publication_id)

    def routes(
        self,
        run_id: str,
        *,
        after_key: str | None = None,
        limit: int | None = None,
    ) -> TravelRouteRowSelection | None:
        return _Reader(self._root).routes(run_id, after_key=after_key, limit=limit)

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

    def read_summary(self, run_id: str) -> InfrastructureNetworksSummary | None:
        snapshot = self.read_snapshot(run_id)
        if snapshot is None:
            return None
        return _summary_from_snapshot(snapshot)

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> InfrastructureNetworksSnapshot | None:
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
            raise ValueError("infrastructure_networks_store_corrupt")
        path = run_dir / f"{publication_id}.json"
        try:
            payload = path.read_bytes()
            snapshot = decode_infrastructure_networks_snapshot(payload)
        except Exception as exc:
            raise ValueError("infrastructure_networks_store_corrupt") from exc
        if snapshot.publication_id != publication_id:
            raise ValueError("infrastructure_networks_store_corrupt")
        if snapshot.digest != entry.get("digest"):
            raise ValueError("infrastructure_networks_store_corrupt")
        return snapshot

    def routes(
        self,
        run_id: str,
        *,
        after_key: str | None = None,
        limit: int | None = None,
    ) -> TravelRouteRowSelection | None:
        snapshot = self.read_snapshot(run_id)
        if snapshot is None:
            return None
        return page_travel_routes(snapshot, after_key=after_key, limit=limit)

    def summary(self, run_id: str) -> InfrastructureNetworksSummary | None:
        return self.read_summary(run_id)


def create_infrastructure_networks_reader(root: Path) -> _Reader:
    return _Reader(Path(root))


def create_infrastructure_networks_publisher(
    root: Path, options: InfrastructureNetworksPublisherOptions | None = None
) -> _Publisher:
    return _Publisher(Path(root), options or InfrastructureNetworksPublisherOptions())
