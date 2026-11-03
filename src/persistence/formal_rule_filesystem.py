"""Atomic append-only filesystem store for ``formal-rule-snapshot-v1``."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Final, cast

from simulation.formal_rule_codec import (
    decode_formal_rule_snapshot,
    encode_formal_rule_snapshot,
    formal_rule_digest,
)
from simulation.formal_rule_models import (
    FormalRuleArtifactError,
    FormalRuleCandidateRecord,
    FormalRuleSnapshot,
)
from simulation.formal_rule_paging import (
    FormalRuleRowSelection,
    select_formal_rule_candidate_rows,
    select_formal_rule_lineage_rows,
    select_formal_rule_rows,
    select_formal_rule_version_rows,
)
from simulation.formal_rule_ports import (
    FormalRulePublication,
    FormalRuleSummary,
)

__all__ = [
    "FilesystemFormalRulePublisher",
    "FilesystemFormalRuleReader",
    "create_formal_rule_publisher",
    "create_formal_rule_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger("persistence.formal_rule_filesystem")

_STORE_SCHEMA: Final[str] = "formal-rule-store-v1"
_STATE_FILE: Final[str] = "state.json"
_PUBLICATION_DIR: Final[str] = "publications"
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _fail(code: str = "formal_rule_invalid_value") -> None:
    raise FormalRuleArtifactError(code)


def _token(value: object) -> str:
    if type(value) is not str or not value or ".." in value:
        _fail()
    token = cast(str, value)
    if _TOKEN_PATTERN.match(token) is None:
        _fail()
    return token


def _fsync_dir(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class FilesystemFormalRulePublisher:
    """Append-only publisher with one atomic state commit point."""

    def __init__(
        self,
        root: Path,
        *,
        max_publications: int = 16,
        max_artifact_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self._root = Path(root)
        self._publications = self._root / _PUBLICATION_DIR
        self._max_publications = max_publications
        self._max_artifact_bytes = max_artifact_bytes

    def _state(self) -> dict[str, object]:
        path = self._root / _STATE_FILE
        if not path.is_file():
            return {"schema_version": _STORE_SCHEMA, "publications": {}}
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != _STORE_SCHEMA:
            _fail()
        return cast(dict[str, object], data)

    def publish(self, publication: FormalRulePublication) -> str:
        if type(publication) is not FormalRulePublication:
            raise TypeError("publication must be FormalRulePublication")
        run_id = _token(publication.run_id)
        publication_id = _token(publication.publication_id)
        payload = bytes(publication.payload)
        if len(payload) > self._max_artifact_bytes:
            _fail("formal_rule_size_limit")
        self._root.mkdir(parents=True, exist_ok=True)
        self._publications.mkdir(parents=True, exist_ok=True)
        state = self._state()
        entries = cast(dict[str, object], state["publications"])
        existing = entries.get(publication_id)
        if isinstance(existing, dict):
            existing_path = self._publications / f"{publication_id}.json"
            if existing_path.is_file() and existing_path.read_bytes() == payload:
                return publication_id
            _LOG.warning(
                "formal_rule_publication_exists run_id=%s reason=%s",
                run_id,
                "formal_rule_publication_exists",
            )
            _fail("formal_rule_publication_exists")
        if len(entries) >= self._max_publications:
            _fail("formal_rule_size_limit")
        cumulative = sum(
            int(cast(Any, cast(dict[str, object], entry).get("bytes", 0)))
            for entry in entries.values()
        )
        byte_ceiling = self._max_artifact_bytes * self._max_publications
        if cumulative + len(payload) > byte_ceiling:
            _fail("formal_rule_size_limit")
        target = self._publications / f"{publication_id}.json"
        temporary = self._publications / f".{publication_id}.tmp"
        temporary.write_bytes(payload)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        _fsync_dir(self._publications)
        entries[publication_id] = {
            "run_id": run_id,
            "generated_tick": int(publication.generated_tick),
            "snapshot_digest": publication.snapshot_digest,
            "bytes": len(payload),
        }
        state_tmp = self._root / f".{_STATE_FILE}.tmp"
        state_tmp.write_text(
            json.dumps(state, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        with state_tmp.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(state_tmp, self._root / _STATE_FILE)
        _fsync_dir(self._root)
        _LOG.info(
            "formal_rule_publication_published run_id=%s publication_id=%s bytes=%s",
            run_id,
            publication_id,
            len(payload),
        )
        return publication_id


class FilesystemFormalRuleReader:
    """Read-only reader over one committed store state."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._publications = self._root / _PUBLICATION_DIR

    def _state(self) -> dict[str, object]:
        path = self._root / _STATE_FILE
        if not path.is_file():
            _fail("formal_rule_unknown")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != _STORE_SCHEMA:
            _fail("formal_rule_digest_mismatch")
        return cast(dict[str, object], data)

    def _snapshot(self, run_id: str) -> tuple[FormalRuleSnapshot, dict[str, object]]:
        state = self._state()
        entries = cast(dict[str, object], state["publications"])
        matches = [
            (publication_id, cast(dict[str, object], entry))
            for publication_id, entry in entries.items()
            if cast(dict[str, object], entry).get("run_id") == run_id
        ]
        if not matches:
            _fail("formal_rule_unknown")
        publication_id, entry = max(
            matches,
            key=lambda item: (
                int(cast(Any, item[1].get("generated_tick", 0))),
                item[0],
            ),
        )
        payload = (self._publications / f"{publication_id}.json").read_bytes()
        if formal_rule_digest(payload) != entry.get("snapshot_digest"):
            _fail("formal_rule_digest_mismatch")
        return decode_formal_rule_snapshot(payload), entry

    def summary(self, run_id: str) -> FormalRuleSummary:
        snapshot, _ = self._snapshot(run_id)
        return FormalRuleSummary(
            run_id=snapshot.ref.run_id,
            publication_id=snapshot.ref.publication_id,
            snapshot_digest=formal_rule_digest(
                encode_formal_rule_snapshot(snapshot)
            ),
            generated_tick=snapshot.ref.generated_tick,
            candidate_count=len(snapshot.candidates),
            rule_count=len(snapshot.rules),
            version_count=len(snapshot.versions),
            edge_count=len(snapshot.lineage),
            coverage=snapshot.coverage,
            schema_version=snapshot.schema_version,
            window_count=len(snapshot.windows),
            provenance_code=snapshot.provenance_code,
        )

    def candidates(
        self,
        run_id: str,
        *,
        status: str | None,
        offset: int,
        limit: int,
    ) -> FormalRuleRowSelection:
        snapshot, _ = self._snapshot(run_id)
        rows = [
            item
            for item in snapshot.candidates
            if status is None or item.status == status
        ]
        return select_formal_rule_candidate_rows(
            rows, offset=offset, limit=limit, byte_budget=2 * 1024 * 1024
        )

    def candidate(self, run_id: str, candidate_id: str) -> FormalRuleCandidateRecord:
        snapshot, _ = self._snapshot(run_id)
        for item in snapshot.candidates:
            if item.candidate_id == candidate_id:
                return item
        _fail("formal_rule_unknown")
        raise AssertionError("unreachable")

    def rules(
        self,
        run_id: str,
        *,
        candidate_id: str,
        stage: str | None,
        offset: int,
        limit: int,
    ) -> FormalRuleRowSelection:
        snapshot, _ = self._snapshot(run_id)
        rows = [
            item
            for item in snapshot.rules
            if item.candidate_id == candidate_id
            and (stage is None or item.stage == stage)
        ]
        return select_formal_rule_rows(
            rows,
            candidate_id=candidate_id,
            offset=offset,
            limit=limit,
            byte_budget=2 * 1024 * 1024,
        )

    def versions(
        self,
        run_id: str,
        *,
        candidate_id: str,
        rule_id: str | None,
        offset: int,
        limit: int,
    ) -> FormalRuleRowSelection:
        snapshot, _ = self._snapshot(run_id)
        rows = [
            item
            for item in snapshot.versions
            if (rule_id is None or item.rule_id == rule_id)
        ]
        return select_formal_rule_version_rows(
            rows,
            candidate_id=candidate_id,
            rule_id=rule_id,
            offset=offset,
            limit=limit,
            byte_budget=2 * 1024 * 1024,
        )

    def lineage(
        self,
        run_id: str,
        *,
        kind: str | None,
        offset: int,
        limit: int,
    ) -> FormalRuleRowSelection:
        snapshot, _ = self._snapshot(run_id)
        rows = [
            item
            for item in snapshot.lineage
            if kind is None or item.kind == kind
        ]
        return select_formal_rule_lineage_rows(
            rows, offset=offset, limit=limit, byte_budget=2 * 1024 * 1024
        )


def create_formal_rule_publisher(
    root: Path | None,
    *,
    max_publications: int = 16,
    max_artifact_bytes: int = 8 * 1024 * 1024,
) -> FilesystemFormalRulePublisher | None:
    if root is None:
        return None
    return FilesystemFormalRulePublisher(
        root,
        max_publications=max_publications,
        max_artifact_bytes=max_artifact_bytes,
    )


def create_formal_rule_reader(root: Path | None) -> FilesystemFormalRuleReader | None:
    if root is None:
        return None
    return FilesystemFormalRuleReader(root)
