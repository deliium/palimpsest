"""Closed detached dispute-analysis vocabulary and identity grammar.

This module is read-only analysis policy. It never imports cognition, simulation
runtime, persistence, API, or a world event store, and it never creates a shared
case file, court, verdict, or binding resolution.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn

from analysis.numerical import quantize_float

DISPUTE_ANALYSIS_POLICY_VERSION: Final[str] = "dispute-analysis.v1"
DISPUTE_IDENTITY_POLICY_VERSION: Final[str] = "dispute-identity.v1"
DISPUTE_CANDIDATE_ID_PREFIX: Final[str] = "disp-"
DISPUTE_PUBLISHED_CLAIM_PREFIX: Final[str] = "dispcl-"
DISPUTE_PUBLISHED_RESOLUTION_PREFIX: Final[str] = "dispres-"
DISPUTE_EDGE_ID_PREFIX: Final[str] = "disp-edge-"
DISPUTE_PUBLICATION_ID_PREFIX: Final[str] = "disp-pub-"
DISPUTE_ID_HEX_LEN: Final[int] = 16
DISPUTE_MAX_WINDOWS: Final[int] = 1024
DISPUTE_DEFAULT_WINDOW_TICKS: Final[int] = 100

# Owner-local dispute record prefixes. They never appear in objective or
# analytical rows and never become an analytical identity.
DISPUTE_OWNER_LOCAL_PREFIXES: Final[tuple[str, ...]] = (
    "dsc-",
    "dcl-",
    "dts-",
    "dev-",
    "drf-",
    "dmr-",
    "dar-",
    "drs-",
    "drp-",
)

# Analytical identities owned by other detached contexts. Dispute analysis never
# creates, splits, merges, dissolves, or re-identifies one of these.
DISPUTE_FOREIGN_CANDIDATE_PREFIXES: Final[tuple[str, ...]] = (
    "frule-",
    "org-",
    "orgop-",
    "orgc-",
    "msoc-",
    "off-",
    "inst-",
    "med-",
)

DISPUTE_FORBIDDEN_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    {"verdict", "guilty", "liable", "true_owner", "winner"}
)

DISPUTE_COVERAGE_TOKENS: Final[frozenset[str]] = frozenset({"complete", "partial"})

DISPUTE_ANALYSIS_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "dispute_duplicate_owner",
        "dispute_invalid_row",
        "dispute_invalid_candidate",
        "dispute_duplicate_id",
        "dispute_lineage_invalid",
        "dispute_lineage_cycle",
        "dispute_layer_leak",
        "dispute_owner_token",
        "dispute_metric_invalid",
        "dispute_policy_mismatch",
        "dispute_coverage_invalid",
    }
)

_EDGE_NAMESPACE: Final[str] = "dispute-edge"
_CANDIDATE_NAMESPACE: Final[str] = "dispute-candidate"
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_HEX16_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")
_CANDIDATE_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{DISPUTE_CANDIDATE_ID_PREFIX}[0-9a-f]{{{DISPUTE_ID_HEX_LEN}}}$"
)
_EDGE_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{DISPUTE_EDGE_ID_PREFIX}[0-9a-f]{{{DISPUTE_ID_HEX_LEN}}}$"
)


class DisputeCandidateStatus(StrEnum):
    """Closed detached candidate status; owner disagreement is legal."""

    EMERGING = "emerging"
    ACTIVE = "active"
    CONTESTED = "contested"
    FRAGMENTED = "fragmented"
    APPARENTLY_RESOLVED = "apparently_resolved"
    DISSOLVED = "dissolved"
    UNKNOWN = "unknown"


class DisputeLayer(StrEnum):
    """Closed layer vocabulary for the three separated evidence layers."""

    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"
    ANALYTICAL = "analytical"


class DisputeLineageKind(StrEnum):
    """Closed forward-only lineage relation kind."""

    CONTINUED = "continued"
    TRANSFORMED = "transformed"
    SPLIT = "split"
    MERGE = "merge"
    DISSOLVED = "dissolved"
    EMERGED = "emerged"


class DisputeAnalysisError(ValueError):
    """Stable-code detached analysis violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in DISPUTE_ANALYSIS_ERROR_CODES:
            raise ValueError("dispute_analysis_invalid_error_code")
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise DisputeAnalysisError(code)


@dataclass(frozen=True, slots=True)
class DisputeCoverage:
    """One explicit observed/expected/partial coverage triple.

    ``partial`` is also true when an owner ledger reports pruned rows, so an
    enabled ledger is never silently treated as a complete zero-case channel.
    """

    observed: int
    expected: int
    ratio: float | None = None
    partial: bool = False

    def __post_init__(self) -> None:
        if type(self.observed) is not int or self.observed < 0:
            _fail("dispute_coverage_invalid")
        if type(self.expected) is not int or self.expected < 0:
            _fail("dispute_coverage_invalid")
        if self.observed > self.expected:
            _fail("dispute_coverage_invalid")
        if type(self.partial) is not bool:
            _fail("dispute_coverage_invalid")
        computed: float | None
        if self.expected == 0:
            computed = None
        else:
            computed = quantize_float(self.observed / self.expected)
        object.__setattr__(self, "ratio", computed)

    @property
    def coverage_fraction(self) -> float | None:
        """Return the coverage ratio, or ``None`` when nothing is expected."""
        return self.ratio


def _short_digest(namespace: str, parts: tuple[str, ...]) -> str:
    payload = "\x1f".join((namespace, *parts))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:DISPUTE_ID_HEX_LEN]


def derive_dispute_candidate_id(creation_digest: str) -> str:
    """Mint one stable ``disp-`` identity from creation evidence only."""
    if (
        type(creation_digest) is not str
        or _HEX64_PATTERN.match(creation_digest) is None
    ):
        _fail("dispute_invalid_candidate")
    body = creation_digest[:DISPUTE_ID_HEX_LEN]
    return f"{DISPUTE_CANDIDATE_ID_PREFIX}{body}"


def dispute_edge_id(source: str, target: str, kind: str, tick: int) -> str:
    """Mint one stable forward-only ``disp-edge-`` identity."""
    source_id = require_dispute_candidate_id(source)
    target_id = require_dispute_candidate_id(target)
    if kind not in {member.value for member in DisputeLineageKind}:
        _fail("dispute_lineage_invalid")
    if type(tick) is not int or tick < 0:
        _fail("dispute_lineage_invalid")
    body = _short_digest(_EDGE_NAMESPACE, (source_id, target_id, kind, str(tick)))
    return f"{DISPUTE_EDGE_ID_PREFIX}{body}"


def require_dispute_candidate_id(value: object) -> str:
    """Require one deterministic ``disp-`` candidate identity."""
    if type(value) is not str or _CANDIDATE_PATTERN.match(value) is None:
        _fail("dispute_invalid_candidate")
    return value


def require_dispute_edge_id(value: object) -> str:
    """Require one deterministic ``disp-edge-`` identity."""
    if type(value) is not str or _EDGE_PATTERN.match(value) is None:
        _fail("dispute_lineage_invalid")
    return value


def dispute_candidate_key(material: tuple[str, ...]) -> str:
    """Return the internal content-addressed candidate key."""
    return f"dispcand-{_short_digest(_CANDIDATE_NAMESPACE, material)}"


__all__ = [
    "DISPUTE_ANALYSIS_ERROR_CODES",
    "DISPUTE_ANALYSIS_POLICY_VERSION",
    "DISPUTE_CANDIDATE_ID_PREFIX",
    "DISPUTE_COVERAGE_TOKENS",
    "DISPUTE_DEFAULT_WINDOW_TICKS",
    "DISPUTE_EDGE_ID_PREFIX",
    "DISPUTE_FORBIDDEN_RESULT_FIELDS",
    "DISPUTE_FOREIGN_CANDIDATE_PREFIXES",
    "DISPUTE_IDENTITY_POLICY_VERSION",
    "DISPUTE_ID_HEX_LEN",
    "DISPUTE_MAX_WINDOWS",
    "DISPUTE_OWNER_LOCAL_PREFIXES",
    "DISPUTE_PUBLICATION_ID_PREFIX",
    "DISPUTE_PUBLISHED_CLAIM_PREFIX",
    "DISPUTE_PUBLISHED_RESOLUTION_PREFIX",
    "DisputeAnalysisError",
    "DisputeCandidateStatus",
    "DisputeCoverage",
    "DisputeLayer",
    "DisputeLineageKind",
    "derive_dispute_candidate_id",
    "dispute_candidate_key",
    "dispute_edge_id",
    "require_dispute_candidate_id",
    "require_dispute_edge_id",
]
