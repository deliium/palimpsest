"""Closed detached-analysis vocabulary for delegation and representation.

Analysis rows and candidates are read-only projections. They never feed
cognition, prompts, memory, world state, stop selectors, or observer semantics,
and they never assert legitimacy, authority, or a winning representative.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Final, NoReturn

__all__ = [
    "REPRESENTATION_ANALYSIS_POLICY_VERSION",
    "REPRESENTATION_CANDIDATE_PREFIX",
    "REPRESENTATION_EDGE_PREFIX",
    "REPRESENTATION_FORBIDDEN_RESULT_FIELDS",
    "REPRESENTATION_IDENTITY_VERSION",
    "REPRESENTATION_PROVENANCE_CHANNELS",
    "REPRESENTATION_SCOPE_KINDS",
    "REPRESENTATION_STATUSES",
    "RepresentationAnalysisError",
    "RepresentationCandidateStatus",
    "RepresentationCoverage",
    "RepresentationLayer",
    "RepresentationLineageKind",
    "derive_representation_candidate_id",
    "representation_candidate_key",
    "representation_edge_id",
    "representation_owner_token",
    "representation_principal_token",
    "representation_scope_subject_token",
]

REPRESENTATION_ANALYSIS_POLICY_VERSION: Final[str] = (
    "delegation-representation-analysis.v1"
)
REPRESENTATION_IDENTITY_VERSION: Final[str] = "delegation-representation-identity.v1"
REPRESENTATION_CANDIDATE_PREFIX: Final[str] = "rep-"
REPRESENTATION_EDGE_PREFIX: Final[str] = "rep-edge-"

REPRESENTATION_SCOPE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "speak_for",
        "negotiate",
        "carry_message",
        "coordinate_project",
        "transact",
        "decide",
        "unknown",
    }
)
REPRESENTATION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "claimed",
        "recognized",
        "contested",
        "rejected",
        "revoked",
        "expired",
        "superseded",
        "unknown",
    }
)
REPRESENTATION_PROVENANCE_CHANNELS: Final[frozenset[str]] = frozenset(
    {
        "self_declared",
        "principal_declared",
        "communicated",
        "witnessed_act",
        "written_record",
        "office_belief",
        "collective_decision",
        "procedure_belief",
        "unknown",
    }
)
REPRESENTATION_FORBIDDEN_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "truth",
        "verified",
        "legitimate",
        "permission",
        "authorized",
        "winner",
        "mandate_valid",
        "authority",
    }
)

_OWNER_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")
_SCOPE_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_.:-]{1,32}$")
_SEPARATOR: Final[str] = "\x1f"

REPRESENTATION_ANALYSIS_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "representation_harvest_invalid",
        "representation_invalid_row",
        "representation_layer_leak",
        "representation_lineage_invalid",
        "representation_identity_conflict",
        "representation_analysis_invalid_input",
    }
)


class RepresentationCandidateStatus(StrEnum):
    """Closed analytical status for one representation candidate."""

    CLAIMED = "claimed"
    RECOGNIZED = "recognized"
    CONTESTED = "contested"
    FRAGMENTED = "fragmented"
    DISSOLVED = "dissolved"
    UNKNOWN = "unknown"


class RepresentationLayer(StrEnum):
    """Closed detached layer. The three layers are never collapsed."""

    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"
    ANALYTICAL = "analytical"


class RepresentationLineageKind(StrEnum):
    """Closed forward-only candidate lineage transition."""

    CONTINUED = "continued"
    TRANSFORMED = "transformed"
    SPLIT = "split"
    MERGE = "merge"
    DISSOLVED = "dissolved"
    EMERGED = "emerged"


class RepresentationCoverage(StrEnum):
    """Closed coverage state for detached representation analysis."""

    COMPLETE = "complete"
    PARTIAL = "partial"


class RepresentationAnalysisError(ValueError):
    """Stable-code detached-analysis violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in REPRESENTATION_ANALYSIS_ERROR_CODES:
            raise ValueError("representation_analysis_invalid_error_code")
        self.code = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise RepresentationAnalysisError(code)


def _digest(*parts: str) -> str:
    return hashlib.sha256(_SEPARATOR.join(parts).encode("utf-8")).hexdigest()


def representation_owner_token(owner_id: object) -> str:
    """Return a safe 16-hex owner token. The raw owner id never leaves analysis."""

    value = getattr(owner_id, "value", owner_id)
    if type(value) is not str or not value:
        _fail("representation_analysis_invalid_input")
    return _digest("representation-owner", value)[:16]


def representation_principal_token(kind: str, ref: object) -> str | None:
    """Hash an agent principal; keep owner-safe collective and region anchors."""

    if ref is None:
        return None
    value = getattr(ref, "value", ref)
    if type(value) is not str or not value:
        _fail("representation_analysis_invalid_input")
    if kind == "agent":
        return _digest("representation-principal", value)[:16]
    if kind in {"organization", "coalition"}:
        if not value.startswith("orgc-"):
            _fail("representation_analysis_invalid_input")
        return value
    if kind == "settlement":
        return value
    return None


def representation_scope_subject_token(value: object) -> str | None:
    if value is None:
        return None
    text = getattr(value, "value", value)
    if type(text) is not str or _SCOPE_TOKEN_PATTERN.match(text) is None:
        _fail("representation_analysis_invalid_input")
    return text


def representation_candidate_key(
    principal_kind: str,
    principal_token: str | None,
    scope_kind: str,
    scope_subject_token: str | None,
) -> str:
    if scope_kind not in REPRESENTATION_SCOPE_KINDS:
        _fail("representation_analysis_invalid_input")
    return _digest(
        "representation-candidate-key",
        principal_kind,
        principal_token or "none",
        scope_kind,
        scope_subject_token or "none",
    )


def derive_representation_candidate_id(
    principal_kind: str,
    principal_token: str | None,
    scope_kind: str,
    scope_subject_token: str | None,
    creation_tick: int,
    creation_owner_token: str,
) -> str:
    key = representation_candidate_key(
        principal_kind, principal_token, scope_kind, scope_subject_token
    )
    if type(creation_tick) is not int or creation_tick < 0:
        _fail("representation_analysis_invalid_input")
    if _OWNER_TOKEN_PATTERN.match(creation_owner_token) is None:
        _fail("representation_analysis_invalid_input")
    body = _digest(
        "representation-candidate",
        key,
        str(creation_tick),
        creation_owner_token,
    )[:16]
    return f"{REPRESENTATION_CANDIDATE_PREFIX}{body}"


def representation_edge_id(
    from_candidate_id: str, to_candidate_id: str, kind: str, tick: int
) -> str:
    if type(tick) is not int or tick < 0:
        _fail("representation_analysis_invalid_input")
    body = _digest(
        "representation-edge",
        from_candidate_id,
        to_candidate_id,
        kind,
        str(tick),
    )[:16]
    return f"{REPRESENTATION_EDGE_PREFIX}{body}"


def require_owner_token(value: object) -> str:
    if type(value) is not str or _OWNER_TOKEN_PATTERN.match(value) is None:
        _fail("representation_invalid_row")
    return value


def require_candidate_id(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith(REPRESENTATION_CANDIDATE_PREFIX)
        or value.startswith(REPRESENTATION_EDGE_PREFIX)
    ):
        _fail("representation_invalid_row")
    return value
