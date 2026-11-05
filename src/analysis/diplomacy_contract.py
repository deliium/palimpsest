"""Closed detached-analysis vocabulary for inter-society diplomacy.

Analysis rows and candidates are read-only projections. They never feed
cognition, prompts, memory, world state, stop selectors, or observer semantics.
No lane, candidate, or metric is a bilateral score.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Final, NoReturn

from analysis.delegation_representation_contract import representation_owner_token

__all__ = [
    "DIPLOMACY_ANALYSIS_POLICY_VERSION",
    "DIPLOMACY_CANDIDATE_PREFIX",
    "DIPLOMACY_EDGE_PREFIX",
    "DIPLOMACY_FORBIDDEN_RESULT_FIELDS",
    "DIPLOMACY_IDENTITY_VERSION",
    "DIPLOMACY_PARTY_KINDS",
    "DIPLOMACY_PUBLICATION_PREFIX",
    "DIPLOMACY_STATUSES",
    "DiplomacyAnalysisError",
    "DiplomacyCoverage",
    "DiplomacyLayer",
    "DiplomacyLineageKind",
    "DiplomaticRelationStatus",
    "InterSocietyLane",
    "derive_diplomacy_candidate_id",
    "diplomacy_agent_token",
    "diplomacy_candidate_key",
    "diplomacy_edge_id",
    "diplomacy_party_token",
    "diplomacy_subject_token",
    "require_diplomacy_candidate_id",
    "require_diplomacy_token",
]

DIPLOMACY_ANALYSIS_POLICY_VERSION: Final[str] = "diplomacy-analysis.v1"
DIPLOMACY_IDENTITY_VERSION: Final[str] = "diplomacy-identity.v1"
DIPLOMACY_CANDIDATE_PREFIX: Final[str] = "dip-"
DIPLOMACY_EDGE_PREFIX: Final[str] = "dip-edge-"
DIPLOMACY_PUBLICATION_PREFIX: Final[str] = "dip-pub-"

DIPLOMACY_PARTY_KINDS: Final[frozenset[str]] = frozenset(
    {"agent", "organization", "settlement", "coalition", "unknown"}
)
DIPLOMACY_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "observed",
        "fragmented",
        "contested",
        "dormant",
        "unknown",
        "claimed",
        "recognized",
        "rejected",
        "revoked",
        "expired",
        "superseded",
        "proposed",
        "open",
        "apparently_accepted",
        "withdrawn",
        "unresolved",
        "active",
        "completed_claimed",
    }
)
DIPLOMACY_FORBIDDEN_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "score",
        "relation_score",
        "trust",
        "rank",
        "valence",
        "index",
        "composite",
        "overall_relation",
        "bilateral_score",
        "mean_score",
        "truth",
        "verified",
        "legitimate",
        "binding",
        "enforced",
        "enforcement",
        "winner",
        "misremembered",
        "false_belief",
        "truth_value",
    }
)

_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")
_SUBJECT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_.:-]{1,32}$")
_SEPARATOR: Final[str] = "\x1f"

DIPLOMACY_ANALYSIS_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "diplomacy_harvest_invalid",
        "diplomacy_invalid_row",
        "diplomacy_layer_leak",
        "diplomacy_lineage_invalid",
        "diplomacy_identity_conflict",
        "diplomacy_analysis_invalid_input",
        "diplomacy_candidate_capacity_reached",
        "diplomacy_foreign_identity_mutation",
        "diplomacy_unmatched_join",
        "diplomacy_forbidden_result_field",
        "diplomacy_duplicate_row",
        "diplomacy_metric_input_missing",
        "diplomacy_metric_forbidden_value_key",
    }
)


class InterSocietyLane(StrEnum):
    """Six independent inter-society evidence lanes."""

    AGENT_RELATIONSHIPS = "agent_relationships"
    TRADE = "trade"
    CONFLICT = "conflict"
    AGREEMENTS = "agreements"
    NARRATIVES = "narratives"
    INSTITUTIONAL_INTERACTION = "institutional_interaction"


class DiplomaticRelationStatus(StrEnum):
    """Closed analytical relation-candidate status."""

    OBSERVED = "observed"
    FRAGMENTED = "fragmented"
    CONTESTED = "contested"
    DORMANT = "dormant"
    UNKNOWN = "unknown"


class DiplomacyLayer(StrEnum):
    """Closed detached layer. The three layers are never collapsed."""

    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"
    ANALYTICAL = "analytical"


class DiplomacyLineageKind(StrEnum):
    """Closed forward-only candidate lineage transition."""

    CONTINUED = "continued"
    TRANSFORMED = "transformed"
    SPLIT = "split"
    MERGE = "merge"
    DORMANT = "dormant"
    ENDED = "ended"


class DiplomacyCoverage(StrEnum):
    """Closed coverage state for detached diplomacy analysis."""

    COMPLETE = "complete"
    PARTIAL = "partial"


class DiplomacyAnalysisError(ValueError):
    """Stable-code detached-analysis violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in DIPLOMACY_ANALYSIS_ERROR_CODES:
            raise ValueError("diplomacy_analysis_invalid_error_code")
        self.code = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise DiplomacyAnalysisError(code)


def _digest(*parts: str) -> str:
    return hashlib.sha256(_SEPARATOR.join(parts).encode("utf-8")).hexdigest()


def diplomacy_agent_token(value: object) -> str:
    """Hash an agent identity in the shared V4-09 token domain."""

    try:
        return representation_owner_token(value)
    except ValueError:
        _fail("diplomacy_analysis_invalid_input")


def diplomacy_party_token(kind: str, ref: object | None) -> str | None:
    """Hash an agent party; keep owner-safe collective and region anchors."""

    if kind not in DIPLOMACY_PARTY_KINDS:
        _fail("diplomacy_analysis_invalid_input")
    if ref is None:
        return None
    value = getattr(ref, "value", ref)
    if type(value) is not str or not value:
        _fail("diplomacy_analysis_invalid_input")
    if kind == "agent":
        return diplomacy_agent_token(value)
    if kind in {"organization", "coalition"}:
        if not value.startswith("orgc-"):
            _fail("diplomacy_analysis_invalid_input")
        return value
    if kind == "settlement":
        return value
    return None


def diplomacy_subject_token(value: object | None) -> str | None:
    """Hash a free-text subject so raw labels never leave the ledger."""

    if value is None:
        return None
    text = getattr(value, "value", value)
    if type(text) is not str or _SUBJECT_PATTERN.match(text) is None:
        _fail("diplomacy_analysis_invalid_input")
    return _digest("diplomacy-subject", text)[:16]


def diplomacy_candidate_key(owner_token: str, party_tokens: tuple[str, ...]) -> str:
    require_diplomacy_token(owner_token)
    ordered = tuple(sorted(party_tokens))
    if len(ordered) < 2 or any(token is None for token in ordered):
        _fail("diplomacy_analysis_invalid_input")
    return _digest("diplomacy-candidate-key", owner_token, *ordered)


def derive_diplomacy_candidate_id(
    owner_token: str,
    party_tokens: tuple[str, ...],
    creation_tick: int,
) -> str:
    if type(creation_tick) is not int or creation_tick < 0:
        _fail("diplomacy_analysis_invalid_input")
    key = diplomacy_candidate_key(owner_token, party_tokens)
    body = _digest("diplomacy-candidate", key, str(creation_tick))[:16]
    return f"{DIPLOMACY_CANDIDATE_PREFIX}{body}"


def diplomacy_edge_id(
    from_candidate_id: str, to_candidate_id: str, kind: str, tick: int
) -> str:
    if type(tick) is not int or tick < 0:
        _fail("diplomacy_analysis_invalid_input")
    if kind not in {member.value for member in DiplomacyLineageKind}:
        _fail("diplomacy_analysis_invalid_input")
    body = _digest(
        "diplomacy-edge", from_candidate_id, to_candidate_id, kind, str(tick)
    )[:16]
    return f"{DIPLOMACY_EDGE_PREFIX}{body}"


def require_diplomacy_token(value: object) -> str:
    if type(value) is not str or _TOKEN_PATTERN.match(value) is None:
        _fail("diplomacy_invalid_row")
    return value


def require_diplomacy_candidate_id(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith(DIPLOMACY_CANDIDATE_PREFIX)
        or value.startswith(DIPLOMACY_EDGE_PREFIX)
        or len(value) != len(DIPLOMACY_CANDIDATE_PREFIX) + 16
    ):
        _fail("diplomacy_invalid_row")
    return value
