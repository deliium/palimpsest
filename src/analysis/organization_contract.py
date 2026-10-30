"""Closed vocabulary for detached organization analysis.

This module is read-only and declares the analytical vocabulary only. Values
mirror the owner-scoped cognition contract; the strings are duplicated on
purpose so analysis never imports ``agents.cognition``. An organizational
candidate is a research label with an opaque ``org-`` identifier; it is never an
entity, a roster, or a world fact.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.numerical import quantize_float
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "ABSORPTION_CONTAINMENT",
    "CONTINUATION_JACCARD",
    "EMERGENCE_TICK_RULE",
    "LINEAGE_TRANSFORM_JACCARD",
    "MAX_CANDIDATE_MEMBERS",
    "MAX_EVIDENCE_WINDOWS",
    "MAX_WINDOW_CANDIDATES",
    "ORGANIZATION_ANALYSIS_POLICY_VERSION",
    "ORGANIZATION_ANALYTICAL_ID_HEX_CHARS",
    "ORGANIZATION_ANALYTICAL_ID_NAMESPACE",
    "ORGANIZATION_ANALYTICAL_ID_PREFIX",
    "ORGANIZATION_IDENTITY_POLICY_VERSION",
    "SPLIT_CONTAINMENT",
    "OrganizationAnalysisError",
    "OrganizationCandidateStatus",
    "OrganizationCoverage",
    "OrganizationLayer",
    "OrganizationLineageKind",
    "OrganizationMembershipStatus",
    "OrganizationTemporalScope",
    "derive_organization_id",
    "require_organization_id",
]

ORGANIZATION_ANALYSIS_POLICY_VERSION: Final[str] = "organization-analysis.v1"
ORGANIZATION_IDENTITY_POLICY_VERSION: Final[str] = "organization-identity.v1"
ORGANIZATION_ANALYTICAL_ID_NAMESPACE: Final[str] = "organization-identity.v1"
ORGANIZATION_ANALYTICAL_ID_PREFIX: Final[str] = "org-"
ORGANIZATION_ANALYTICAL_ID_HEX_CHARS: Final[int] = 16

CONTINUATION_JACCARD: Final[float] = 0.5
LINEAGE_TRANSFORM_JACCARD: Final[float] = 0.75
SPLIT_CONTAINMENT: Final[float] = 0.4
ABSORPTION_CONTAINMENT: Final[float] = 0.5
EMERGENCE_TICK_RULE: Final[str] = "first_observed_window"
MAX_EVIDENCE_WINDOWS: Final[int] = 512
MAX_WINDOW_CANDIDATES: Final[int] = 2048
MAX_CANDIDATE_MEMBERS: Final[int] = 512

_ANALYTICAL_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{ORGANIZATION_ANALYTICAL_ID_PREFIX}"
    rf"[0-9a-f]{{{ORGANIZATION_ANALYTICAL_ID_HEX_CHARS}}}$"
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organization_contract")


class OrganizationCandidateStatus(StrEnum):
    """Analytical status of one candidate in one window."""

    RECOGNIZED = "recognized"
    PARTIAL = "partial"
    DISPUTED = "disputed"
    FRAGMENTED = "fragmented"
    TEMPORARY = "temporary"
    DISSOLVED = "dissolved"


class OrganizationMembershipStatus(StrEnum):
    """Per-member status; mirrors the owner-scoped vocabulary."""

    EXPLICIT = "explicit"
    PERCEIVED = "perceived"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"
    FORMER = "former"


class OrganizationTemporalScope(StrEnum):
    """Closed temporal scope for one member or candidate."""

    ONGOING = "ongoing"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


class OrganizationLayer(StrEnum):
    """The three representations kept strictly separate."""

    OBJECTIVE_STRUCTURE = "objective_structure"
    SUBJECTIVE_CLAIMS = "subjective_claims"
    ANALYTICAL_CANDIDATES = "analytical_candidates"


class OrganizationLineageKind(StrEnum):
    """Allowed forward-only lineage transitions between adjacent windows."""

    CONTINUED = "continued"
    TRANSFORMED = "transformed"
    SPLIT = "split"
    MERGE = "merge"
    DISSOLVED = "dissolved"
    EMERGED = "emerged"


class OrganizationAnalysisError(ValueError):
    """Fail-closed analysis error with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code: str = require_stable_id("reason_code", reason_code)
        _LOG.debug("organization_analysis_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class OrganizationCoverage:
    """Observed-versus-expected coverage; ``ratio`` is absent when unknown."""

    observed: int
    expected: int
    ratio: float | None

    def __post_init__(self) -> None:
        observed = require_exact_nonneg_int("observed", self.observed)
        expected = require_exact_nonneg_int("expected", self.expected)
        if observed > expected:
            raise OrganizationAnalysisError("organization_invalid_coverage")
        ratio = None if expected == 0 else quantize_float(observed / expected)
        object.__setattr__(self, "observed", observed)
        object.__setattr__(self, "expected", expected)
        object.__setattr__(self, "ratio", ratio)

    @classmethod
    def of(cls, observed: int, expected: int) -> OrganizationCoverage:
        """Build coverage from counts, deriving the quantized ratio."""
        return cls(observed=observed, expected=expected, ratio=None)


def validate_member_ids(name: str, raw: object) -> tuple[str, ...]:
    """Validate a member id collection: no payload, no duplicates, sorted."""
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise OrganizationAnalysisError("organization_content_payload_rejected")
    members: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise OrganizationAnalysisError("organization_content_payload_rejected")
        try:
            member = require_stable_id(f"{name}.member_id", item)
        except ValueError as exc:
            raise OrganizationAnalysisError("organization_invalid_member") from exc
        if member in seen:
            raise OrganizationAnalysisError("organization_duplicate_member")
        seen.add(member)
        members.append(member)
    if len(members) > MAX_CANDIDATE_MEMBERS:
        raise OrganizationAnalysisError("organization_too_many_members")
    return tuple(sorted(members))


def derive_organization_id(
    *,
    creation_tick: int,
    founding_member_ids: Iterable[str],
    structural_anchors: Iterable[str],
) -> str:
    """Derive the opaque ``org-`` id from creation evidence only."""
    tick = require_exact_nonneg_int("creation_tick", creation_tick)
    members = validate_member_ids("founding_member_ids", tuple(founding_member_ids))
    anchors: list[str] = []
    for item in structural_anchors:
        if not isinstance(item, str) or not item:
            raise OrganizationAnalysisError("organization_invalid_anchor")
        anchors.append(item)
    if len(set(anchors)) != len(anchors):
        raise OrganizationAnalysisError("organization_duplicate_anchor")
    payload = {
        "namespace": ORGANIZATION_ANALYTICAL_ID_NAMESPACE,
        "creation_tick": tick,
        "founding_member_ids": list(members),
        "structural_anchors": sorted(anchors),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    short = digest[:ORGANIZATION_ANALYTICAL_ID_HEX_CHARS]
    return f"{ORGANIZATION_ANALYTICAL_ID_PREFIX}{short}"


def require_organization_id(value: str) -> str:
    """Validate an exact ``org-`` plus 16 lowercase hex characters id."""
    if not isinstance(value, str) or not _ANALYTICAL_ID_PATTERN.match(value):
        raise OrganizationAnalysisError("organization_invalid_id")
    return value
