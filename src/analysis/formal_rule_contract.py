"""Closed detached formal-rule analysis vocabulary and identity grammar.

This module is read-only analysis policy. It never imports cognition, simulation
runtime, persistence, API, or a world event store, and it never creates an
objective rule, jurisdiction, or enforcement mechanism.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn

FORMAL_RULE_ANALYSIS_POLICY_VERSION: Final[str] = "formal-rule-analysis.v1"
FORMAL_RULE_IDENTITY_POLICY_VERSION: Final[str] = "formal-rule-identity.v1"
FORMAL_RULE_CANDIDATE_ID_PREFIX: Final[str] = "frule-"
FORMAL_RULE_EDGE_ID_PREFIX: Final[str] = "frule-edge-"
FORMAL_RULE_ID_HEX_LEN: Final[int] = 16
FORMAL_RULE_MAX_HARVEST_RULES: Final[int] = 4096

_EDGE_NAMESPACE: Final[str] = "formal-rule-edge"
_CANDIDATE_NAMESPACE: Final[str] = "formal-rule-candidate"
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{FORMAL_RULE_CANDIDATE_ID_PREFIX}[0-9a-f]{{{FORMAL_RULE_ID_HEX_LEN}}}$"
)
_EDGE_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{FORMAL_RULE_EDGE_ID_PREFIX}[0-9a-f]{{{FORMAL_RULE_ID_HEX_LEN}}}$"
)

FORMAL_RULE_ANALYSIS_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "formal_rule_harvest_invalid",
        "formal_rule_metric_invalid",
        "formal_rule_layer_leakage",
        "formal_rule_lineage_invalid",
        "formal_rule_candidate_invalid",
        "formal_rule_policy_mismatch",
        "formal_rule_coverage_invalid",
        "formal_rule_artifact_invalid",
    }
)


class FormalRuleCandidateStatus(StrEnum):
    """Closed detached candidate status; overlap is legal."""

    RECOGNIZED = "recognized"
    PARTIAL = "partial"
    CONTESTED = "contested"
    FRAGMENTED = "fragmented"
    TEMPORARY = "temporary"
    DISSOLVED = "dissolved"


class FormalRuleLayer(StrEnum):
    """Closed layer vocabulary for the three separated evidence layers."""

    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"
    ANALYTICAL = "analytical"


class FormalRuleLineageKind(StrEnum):
    """Closed forward-only lineage relation kind."""

    CONTINUED = "continued"
    TRANSFORMED = "transformed"
    SPLIT = "split"
    MERGE = "merge"
    DISSOLVED = "dissolved"
    EMERGED = "emerged"


class FormalRuleAnalysisError(ValueError):
    """Stable-code detached analysis violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in FORMAL_RULE_ANALYSIS_ERROR_CODES:
            raise ValueError("formal_rule_analysis_invalid_error_code")
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise FormalRuleAnalysisError(code)


@dataclass(frozen=True, slots=True)
class FormalRuleCoverage:
    """One explicit observed/expected/partial coverage triple."""

    observed: int
    expected: int
    partial: bool = False

    def __post_init__(self) -> None:
        if type(self.observed) is not int or self.observed < 0:
            _fail("formal_rule_coverage_invalid")
        if type(self.expected) is not int or self.expected < 0:
            _fail("formal_rule_coverage_invalid")
        if self.observed > self.expected:
            _fail("formal_rule_coverage_invalid")
        if type(self.partial) is not bool:
            _fail("formal_rule_coverage_invalid")
        if self.partial and self.observed >= self.expected:
            _fail("formal_rule_coverage_invalid")

    @property
    def coverage_fraction(self) -> float | None:
        """Return the coverage ratio, or ``None`` when nothing is expected."""
        if self.expected == 0:
            return None
        return self.observed / self.expected


def _require_text(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return value


def _require_tick(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("formal_rule_artifact_invalid")
    return value


def _short_digest(namespace: str, parts: tuple[str, ...]) -> str:
    payload = "\x1f".join((namespace, *parts))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[
        :FORMAL_RULE_ID_HEX_LEN
    ]


def derive_formal_rule_id(creation_digest: str) -> str:
    """Mint one stable ``frule-`` identity from a creation digest."""
    if (
        type(creation_digest) is not str
        or _HEX64_PATTERN.match(creation_digest) is None
    ):
        _fail("formal_rule_candidate_invalid")
    body = creation_digest[:FORMAL_RULE_ID_HEX_LEN]
    return f"{FORMAL_RULE_CANDIDATE_ID_PREFIX}{body}"


def formal_rule_edge_id(source: str, target: str, kind: str, tick: int) -> str:
    """Mint one stable forward-only ``frule-edge-`` identity."""
    source_id = require_formal_rule_candidate_id(source)
    target_id = require_formal_rule_candidate_id(target)
    if kind not in {member.value for member in FormalRuleLineageKind}:
        _fail("formal_rule_lineage_invalid")
    absolute_tick = _require_tick(tick)
    body = _short_digest(
        _EDGE_NAMESPACE,
        (source_id, target_id, kind, str(absolute_tick)),
    )
    return f"{FORMAL_RULE_EDGE_ID_PREFIX}{body}"


def require_formal_rule_candidate_id(value: object) -> str:
    """Require one deterministic ``frule-`` candidate identity."""
    if type(value) is not str or _CANDIDATE_PATTERN.match(value) is None:
        _fail("formal_rule_candidate_invalid")
    return value


def require_formal_rule_edge_id(value: object) -> str:
    """Require one deterministic ``frule-edge-`` identity."""
    if type(value) is not str or _EDGE_PATTERN.match(value) is None:
        _fail("formal_rule_lineage_invalid")
    return value


def candidate_key(material: tuple[str, ...]) -> str:
    """Return the internal content-addressed candidate key."""
    return f"cand-{_short_digest(_CANDIDATE_NAMESPACE, material)}"


__all__ = [
    "FORMAL_RULE_ANALYSIS_ERROR_CODES",
    "FORMAL_RULE_ANALYSIS_POLICY_VERSION",
    "FORMAL_RULE_CANDIDATE_ID_PREFIX",
    "FORMAL_RULE_EDGE_ID_PREFIX",
    "FORMAL_RULE_IDENTITY_POLICY_VERSION",
    "FORMAL_RULE_ID_HEX_LEN",
    "FORMAL_RULE_MAX_HARVEST_RULES",
    "FormalRuleAnalysisError",
    "FormalRuleCandidateStatus",
    "FormalRuleCoverage",
    "FormalRuleLayer",
    "FormalRuleLineageKind",
    "candidate_key",
    "derive_formal_rule_id",
    "formal_rule_edge_id",
    "require_formal_rule_candidate_id",
    "require_formal_rule_edge_id",
]
