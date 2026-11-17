"""Publication and read ports for scientific-replication snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from simulation.replication_models import ScientificReplicationSnapshot


class ReplicationPublicationError(ValueError):
    """Safe publication/read failure."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or not code:
            raise ValueError("replication_publication_invalid_code")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReplicationPublicationRef:
    run_id: str
    publication_id: str
    internal_digest: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class ReplicationPublicationReceipt:
    publication_id: str
    stored: bool
    reason: str
    byte_size: int = 0


@dataclass(frozen=True, slots=True)
class ReplicationPublicationOptions:
    enabled: bool = False
    max_publications: int = 16
    max_bytes: int = 8_388_608


class ScientificReplicationReader(Protocol):
    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> ScientificReplicationSnapshot: ...


class ScientificReplicationPublisher(Protocol):
    def publish(
        self, snapshot: ScientificReplicationSnapshot
    ) -> ReplicationPublicationReceipt: ...


def replication_query_fingerprint(
    *,
    run_id: str,
    publication_id: str | None,
    record_kinds: tuple[str, ...] = (),
) -> str:
    material = json.dumps(
        {
            "run_id": run_id,
            "publication_id": publication_id or "",
            "record_kinds": list(record_kinds),
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(material).hexdigest()[:32]


__all__ = [
    "ReplicationPublicationError",
    "ReplicationPublicationOptions",
    "ReplicationPublicationReceipt",
    "ReplicationPublicationRef",
    "ScientificReplicationPublisher",
    "ScientificReplicationReader",
    "replication_query_fingerprint",
]
