"""Read and publication ports for ``formal-rule-snapshot-v1``.

Simulation owns the cursor payload and matching only. The API layer signs and
expires cursors; no HTTP, analysis, or persistence type is imported here.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Final, Protocol

from simulation.formal_rule_models import (
    FormalRuleArtifactError,
    FormalRuleCandidateRecord,
    FormalRuleCoverage,
)
from simulation.formal_rule_paging import FormalRuleRowSelection

__all__ = [
    "FORMAL_RULE_CURSOR_PURPOSES",
    "FormalRuleCursor",
    "FormalRulePublication",
    "FormalRulePublicationPort",
    "FormalRuleReadPort",
    "FormalRuleReadSession",
    "FormalRuleSummary",
    "formal_rule_cursor_matches",
    "formal_rule_query_fingerprint",
    "require_known_formal_rule",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.formal_rule_ports")

FORMAL_RULE_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "candidates",
    "candidate",
    "rules",
    "versions",
    "lineage",
)


@dataclass(frozen=True, slots=True)
class FormalRulePublication:
    run_id: str
    publication_id: str
    snapshot_digest: str
    payload: bytes
    generated_tick: int


@dataclass(frozen=True, slots=True)
class FormalRuleSummary:
    run_id: str
    publication_id: str
    snapshot_digest: str
    generated_tick: int
    candidate_count: int
    rule_count: int
    version_count: int
    edge_count: int
    coverage: FormalRuleCoverage
    schema_version: str = "formal-rule-snapshot-v1"
    window_count: int = 0
    provenance_code: str = "ok"

    def __post_init__(self) -> None:
        for name in (
            "candidate_count",
            "rule_count",
            "version_count",
            "edge_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise FormalRuleArtifactError("formal_rule_invalid_value")


@dataclass(frozen=True, slots=True)
class FormalRuleCursor:
    purpose: str
    run_id: str
    publication_id: str
    snapshot_digest: str
    offset: int
    query_fingerprint: str

    def __post_init__(self) -> None:
        if self.purpose not in FORMAL_RULE_CURSOR_PURPOSES:
            raise FormalRuleArtifactError("formal_rule_cursor_invalid")
        if type(self.offset) is not int or self.offset < 0:
            raise FormalRuleArtifactError("formal_rule_cursor_invalid")
        digest = self.query_fingerprint
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise FormalRuleArtifactError("formal_rule_cursor_invalid")


@dataclass(frozen=True, slots=True)
class FormalRuleReadSession:
    publication: FormalRulePublication
    response_byte_budget: int = 2 * 1024 * 1024

    def __post_init__(self) -> None:
        if type(self.response_byte_budget) is not int or self.response_byte_budget < 1:
            raise FormalRuleArtifactError("formal_rule_size_limit")


class FormalRuleReadPort(Protocol):
    def summary(self, run_id: str) -> FormalRuleSummary: ...

    def candidates(
        self,
        run_id: str,
        *,
        status: str | None,
        offset: int,
        limit: int,
    ) -> FormalRuleRowSelection: ...

    def candidate(
        self, run_id: str, candidate_id: str
    ) -> FormalRuleCandidateRecord: ...

    def rules(
        self,
        run_id: str,
        *,
        candidate_id: str,
        stage: str | None,
        offset: int,
        limit: int,
    ) -> FormalRuleRowSelection: ...

    def versions(
        self,
        run_id: str,
        *,
        candidate_id: str,
        rule_id: str | None,
        offset: int,
        limit: int,
    ) -> FormalRuleRowSelection: ...

    def lineage(
        self,
        run_id: str,
        *,
        kind: str | None,
        offset: int,
        limit: int,
    ) -> FormalRuleRowSelection: ...


class FormalRulePublicationPort(Protocol):
    def publish(self, publication: FormalRulePublication) -> str: ...


def formal_rule_query_fingerprint(
    purpose: str,
    *,
    run_id: str,
    publication_id: str,
    candidate_id: str | None = None,
    filters: tuple[tuple[str, str], ...] = (),
) -> str:
    """Return a sorted canonical fingerprint for one query shape."""
    if purpose not in FORMAL_RULE_CURSOR_PURPOSES:
        raise FormalRuleArtifactError("formal_rule_cursor_invalid")
    payload = {
        "purpose": purpose,
        "run_id": run_id,
        "publication_id": publication_id,
        "candidate_id": candidate_id,
        "filters": sorted(filters),
    }
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def formal_rule_cursor_matches(
    cursor: FormalRuleCursor,
    *,
    purpose: str,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    fingerprint: str,
) -> bool:
    """Return whether a cursor still binds to the same publication and query."""
    if type(cursor) is not FormalRuleCursor:
        return False
    return (
        cursor.purpose == purpose
        and cursor.run_id == run_id
        and cursor.publication_id == publication_id
        and cursor.snapshot_digest == snapshot_digest
        and cursor.query_fingerprint == fingerprint
    )


def require_known_formal_rule(value: object | None, *, field_name: str) -> object:
    """Require one known record; unknown values fail closed."""
    if value is None:
        _LOG.warning(
            "formal_rule_unknown field=%s reason_code=formal_rule_unknown",
            field_name,
        )
        raise FormalRuleArtifactError("formal_rule_unknown")
    return value
