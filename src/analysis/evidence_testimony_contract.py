"""Closed detached-analysis vocabulary for owner-scoped evidence and testimony.

Analysis rows and candidates are read-only projections. They never feed
cognition, prompts, memory, world state, stop selectors, or observer semantics,
and they never assert truth, authenticity, guilt, liability, or a winning
account.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Final, NoReturn

__all__ = [
    "EVIDENCE_ANALYSIS_POLICY_VERSION",
    "EVIDENCE_CANDIDATE_PREFIX",
    "EVIDENCE_CONFIDENCE_BANDS",
    "EVIDENCE_CUSTODY_STATUSES",
    "EVIDENCE_EDGE_PREFIX",
    "EVIDENCE_FORBIDDEN_RESULT_FIELDS",
    "EVIDENCE_FOREIGN_CANDIDATE_PREFIXES",
    "EVIDENCE_IDENTITY_VERSION",
    "EVIDENCE_INTERPRETATIONS",
    "EVIDENCE_ITEM_PREFIX",
    "EVIDENCE_OWNER_LOCAL_PREFIXES",
    "EVIDENCE_PROVENANCE_CHANNELS",
    "EVIDENCE_PUBLICATION_PREFIX",
    "EVIDENCE_SOURCE_KINDS",
    "EVIDENCE_TRUST_BASES",
    "EvidenceAnalysisError",
    "EvidenceCandidateStatus",
    "EvidenceCoverage",
    "EvidenceLayer",
    "EvidenceLineageKind",
    "derive_evidence_candidate_id",
    "evidence_candidate_key",
    "evidence_edge_id",
    "evidence_owner_token",
]

EVIDENCE_ANALYSIS_POLICY_VERSION: Final[str] = "evidence-testimony-analysis.v1"
EVIDENCE_IDENTITY_VERSION: Final[str] = "evidence-testimony-identity.v1"

EVIDENCE_CANDIDATE_PREFIX: Final[str] = "evid-"
EVIDENCE_ITEM_PREFIX: Final[str] = "evid-item-"
EVIDENCE_EDGE_PREFIX: Final[str] = "evid-edge-"
EVIDENCE_PUBLICATION_PREFIX: Final[str] = "evid-pub-"

EVIDENCE_OWNER_LOCAL_PREFIXES: Final[tuple[str, ...]] = (
    "evs-",
    "evw-",
    "evi-",
    "evc-",
    "evx-",
    "eva-",
)
EVIDENCE_FOREIGN_CANDIDATE_PREFIXES: Final[tuple[str, ...]] = (
    "disp-",
    "dispcl-",
    "dispres-",
    "frule-",
    "org-",
    "orgop-",
    "orgc-",
    "msoc-",
    "off-",
    "inst-",
    "med-",
)

EVIDENCE_FORBIDDEN_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "truth",
        "verified",
        "authenticated",
        "authentic",
        "forged",
        "fake",
        "proof",
        "verdict",
        "guilt",
        "guilty",
        "liable",
        "liability",
        "true_owner",
        "winner",
    }
)

EVIDENCE_SOURCE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "witness_testimony",
        "written_record",
        "artifact",
        "physical_state",
        "prior_agreement",
        "reputation",
        "remembered_event",
        "unknown",
    }
)
EVIDENCE_PROVENANCE_CHANNELS: Final[frozenset[str]] = frozenset(
    {
        "direct_observation",
        "communicated",
        "remembered",
        "recorded",
        "derived",
        "inferred",
        "unknown",
    }
)
EVIDENCE_INTERPRETATIONS: Final[frozenset[str]] = frozenset(
    {"supports", "contradicts", "ambiguous", "insufficient", "irrelevant", "unknown"}
)
EVIDENCE_CUSTODY_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "not_applicable",
        "complete_belief",
        "incomplete_belief",
        "conflicting_belief",
        "unknown",
    }
)
EVIDENCE_TRUST_BASES: Final[frozenset[str]] = frozenset(
    {
        "direct_experience",
        "relationship_trust",
        "reputation",
        "role_authority",
        "rule_authority",
        "institution_membership",
        "none",
        "unknown",
    }
)
EVIDENCE_CONFIDENCE_BANDS: Final[frozenset[str]] = frozenset({"low", "mid", "high"})
_OWNER_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")
_SEPARATOR: Final[str] = "\x1f"


class EvidenceCandidateStatus(StrEnum):
    """Closed analytical status of one cross-owner evidence candidate."""

    CONVERGENT = "convergent"
    CONTESTED = "contested"
    FRAGMENTED = "fragmented"
    ISOLATED = "isolated"
    UNKNOWN = "unknown"


class EvidenceLayer(StrEnum):
    """Closed detached layer. The three layers are never collapsed."""

    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"
    ANALYTICAL = "analytical"


class EvidenceLineageKind(StrEnum):
    """Closed forward-only candidate lineage transition."""

    CONTINUED = "continued"
    TRANSFORMED = "transformed"
    SPLIT = "split"
    MERGE = "merge"
    DISSOLVED = "dissolved"
    EMERGED = "emerged"


class EvidenceCoverage(StrEnum):
    """Closed coverage state for detached evidence analysis."""

    COMPLETE = "complete"
    PARTIAL = "partial"


EVIDENCE_ANALYSIS_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "evidence_testimony_invalid_input",
        "evidence_testimony_invalid_row",
        "evidence_testimony_duplicate_owner",
        "evidence_testimony_unknown_reference",
        "evidence_testimony_layer_leak",
        "evidence_testimony_lineage_invalid",
        "evidence_testimony_identity_conflict",
    }
)


class EvidenceAnalysisError(ValueError):
    """Stable-code detached-analysis violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in EVIDENCE_ANALYSIS_ERROR_CODES:
            raise ValueError("evidence_testimony_invalid_error_code")
        self.code = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise EvidenceAnalysisError(code)


def _digest(*parts: str) -> str:
    payload = _SEPARATOR.join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evidence_owner_token(owner_id: object) -> str:
    """Return a safe 16-hex owner token. The raw owner id never leaves analysis."""

    value = getattr(owner_id, "value", owner_id)
    if type(value) is not str or not value:
        _fail("evidence_testimony_invalid_input")
    return _digest("evidence-owner", value)[:16]


def require_owner_token(value: object) -> str:
    if type(value) is not str or _OWNER_TOKEN_PATTERN.match(value) is None:
        _fail("evidence_testimony_invalid_row")
    return value


def evidence_candidate_key(subject_token: str, source_kind_family: str) -> str:
    """Return the stable grouping key for one subject and source family."""

    if type(subject_token) is not str or not subject_token:
        _fail("evidence_testimony_invalid_input")
    if type(source_kind_family) is not str or not source_kind_family:
        _fail("evidence_testimony_invalid_input")
    return _digest("evidence-candidate-key", subject_token, source_kind_family)


def derive_evidence_candidate_id(
    subject_token: str, source_kind_family: str, creation_digest: str
) -> str:
    """Mint a creation-evidence ``evid-`` candidate id. Never a foreign id."""

    key = evidence_candidate_key(subject_token, source_kind_family)
    if type(creation_digest) is not str or len(creation_digest) != 64:
        _fail("evidence_testimony_invalid_input")
    body = _digest("evidence-candidate", key, creation_digest)[:16]
    return f"{EVIDENCE_CANDIDATE_PREFIX}{body}"


def evidence_edge_id(source_id: str, target_id: str, kind: str, window: int) -> str:
    """Mint a deterministic forward lineage edge id."""

    if type(window) is not int or window < 0:
        _fail("evidence_testimony_invalid_input")
    return (
        f"{EVIDENCE_EDGE_PREFIX}"
        f"{_digest('evidence-edge', source_id, target_id, kind, str(window))[:16]}"
    )


def require_local_id(value: object) -> str:
    if type(value) is not str or not value.startswith(EVIDENCE_OWNER_LOCAL_PREFIXES):
        _fail("evidence_testimony_invalid_row")
    return value


def require_candidate_id(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith(EVIDENCE_CANDIDATE_PREFIX)
        or value.startswith(EVIDENCE_ITEM_PREFIX)
        or value.startswith(EVIDENCE_EDGE_PREFIX)
        or value.startswith(EVIDENCE_PUBLICATION_PREFIX)
    ):
        _fail("evidence_testimony_invalid_row")
    return value
