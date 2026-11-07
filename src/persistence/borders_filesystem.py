# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,no-untyped-call,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Atomic filesystem store for ``borders-store-v1``."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from simulation.borders_codec import (
    decode_borders_snapshot,
    encode_borders_snapshot,
)
from simulation.borders_models import BordersSnapshot
from simulation.borders_ports import BordersSummary

__all__ = [
    "BORDERS_STORE_SCHEMA",
    "BordersPublisherOptions",
    "create_borders_publisher",
    "create_borders_reader",
]

BORDERS_STORE_SCHEMA: Final[str] = "borders-store-v1"
_STATE_FILE: Final[str] = "state.json"
_LOCK_FILE: Final[str] = "store.lock"


@dataclass(frozen=True, slots=True)
class BordersPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        if not 1 <= self.max_publications <= 1024:
            raise ValueError("borders_publications_range")
        if not 1 <= self.max_bytes <= 268_435_456:
            raise ValueError("borders_bytes_range")


def _empty_state() -> dict[str, object]:
    return {"schema": BORDERS_STORE_SCHEMA, "publications": []}


def _load_state(root: Path) -> dict[str, object]:
    path = root / _STATE_FILE
    if not path.exists():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("borders_store_corrupt") from exc
    if type(data) is not dict or data.get("schema") != BORDERS_STORE_SCHEMA:
        raise ValueError("borders_store_corrupt")
    if not isinstance(data.get("publications"), list):
        raise ValueError("borders_store_corrupt")
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


class _Publisher:
    def __init__(self, root: Path, options: BordersPublisherOptions) -> None:
        self._root = root
        self._options = options

    def publish(self, snapshot: BordersSnapshot) -> None:
        root = self._root
        root.mkdir(parents=True, exist_ok=True)
        import fcntl

        lock_path = root / _LOCK_FILE
        with lock_path.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                state = _load_state(root)
                publications = state["publications"]
                payload = encode_borders_snapshot(snapshot)
                encoded = base64.b64encode(payload).decode("ascii")
                for entry in publications:
                    if entry.get("publication_id") != snapshot.publication_id:
                        continue
                    if entry.get("payload") == encoded:
                        return
                    raise ValueError("borders_publication_exists")
                run_entries = [
                    entry
                    for entry in publications
                    if entry.get("run_id") == snapshot.run_id
                ]
                if len(run_entries) >= self._options.max_publications:
                    raise ValueError("borders_quota_exceeded")
                existing_bytes = sum(
                    len(str(entry.get("payload", ""))) for entry in run_entries
                )
                if existing_bytes + len(encoded) > self._options.max_bytes:
                    raise ValueError("borders_quota_exceeded")
                publications.append(
                    {
                        "run_id": snapshot.run_id,
                        "publication_id": snapshot.publication_id,
                        "digest": snapshot.digest,
                        "schema_version": snapshot.schema_version,
                        "payload": encoded,
                    }
                )
                content = json.dumps(
                    state, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                _atomic_write(root / _STATE_FILE, content)
                _ = self._options
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


class _Reader:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _latest_entry(self, run_id: str) -> dict[str, object] | None:
        state = _load_state(self._root)
        entries = [
            entry for entry in state["publications"] if entry.get("run_id") == run_id
        ]
        return entries[-1] if entries else None

    def snapshot(self, run_id: str) -> BordersSnapshot | None:
        entry = self._latest_entry(run_id)
        if entry is None:
            return None
        try:
            payload = base64.b64decode(str(entry["payload"]))
            snapshot = decode_borders_snapshot(payload)
        except Exception as exc:
            raise ValueError("borders_store_corrupt") from exc
        if snapshot.publication_id != entry.get("publication_id"):
            raise ValueError("borders_store_corrupt")
        return snapshot

    def read_summary(self, run_id: str) -> BordersSummary | None:
        snapshot = self.snapshot(run_id)
        if snapshot is None:
            return None
        summary = snapshot.summary
        return BordersSummary(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            schema_version=snapshot.schema_version,
            candidate_count=summary.candidate_count,
            claim_count=summary.claim_count,
            agreement_count=summary.agreement_count,
            dispute_count=summary.dispute_count,
            physical_row_count=summary.physical_row_count,
            pattern_count=summary.pattern_count,
            coverage=summary.coverage,
        )

    def read_claims(self, run_id: str, *, after: str | None, limit: int):
        snapshot = self.snapshot(run_id)
        if snapshot is None:
            return ()
        return _page(
            snapshot.claims,
            key=lambda row: (row.domain_token, row.owner_token),
            after=after,
            limit=limit,
        )

    def read_claim(self, run_id: str, claim_id: str):
        snapshot = self.snapshot(run_id)
        if snapshot is None:
            return None
        for row in snapshot.claims:
            if row.claim_token == claim_id or row.domain_token == claim_id:
                return row
        return None

    def read_agreements(self, run_id: str, *, after: str | None, limit: int):
        snapshot = self.snapshot(run_id)
        if snapshot is None:
            return ()
        return _page(
            snapshot.agreements,
            key=lambda row: (row.domain_token, row.agreement_token),
            after=after,
            limit=limit,
        )

    def read_agreement(self, run_id: str, agreement_id: str):
        snapshot = self.snapshot(run_id)
        if snapshot is None:
            return None
        for row in snapshot.agreements:
            if row.agreement_token == agreement_id:
                return row
        return None

    def read_control(self, run_id: str, *, layer: str, after: str | None, limit: int):
        snapshot = self.snapshot(run_id)
        if snapshot is None:
            return ()
        if layer == "physical":
            return _page(
                snapshot.physical,
                key=lambda row: (row.location_token, row.window_start),
                after=after,
                limit=limit,
            )
        if layer == "analytical":
            return _page(
                snapshot.patterns,
                key=lambda row: (row.domain_token, row.pattern_token),
                after=after,
                limit=limit,
            )
        if layer != "all":
            raise ValueError("borders_control_layer")
        rows = tuple(
            [("physical", row) for row in snapshot.physical]
            + [("analytical", row) for row in snapshot.patterns]
        )
        page = _page(
            rows,
            key=lambda item: (
                item[0],
                item[1].location_token
                if item[0] == "physical"
                else item[1].domain_token,
                getattr(item[1], "window_start", getattr(item[1], "pattern_token", "")),
            ),
            after=after,
            limit=limit,
        )
        return page


def _page(rows, *, key, after, limit):
    if type(limit) is not int or limit < 1 or limit > 500:
        raise ValueError("borders_page_limit")
    ordered = sorted(rows, key=key)
    if after is not None:
        ordered = [row for row in ordered if str(key(row)) > after]
    return tuple(ordered[:limit])


def create_borders_reader(root: Path) -> _Reader:
    return _Reader(Path(root))


def create_borders_publisher(
    root: Path, options: BordersPublisherOptions | None = None
) -> _Publisher:
    return _Publisher(Path(root), options or BordersPublisherOptions())
