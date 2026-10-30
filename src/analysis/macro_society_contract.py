"""Closed vocabulary for macro-society analytical identity.

This module is read-only and declares the only allowed vocabulary for the
V4-02 analysis layer. It never imports persistence, API, experiments, observer,
or world authority. A macro-society is an analysis-output label with an opaque
``msoc-`` identifier; it is never an entity, a command target, or a world fact.
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
    "CONTESTED_MIN_MEMBERS",
    "EDGE_LANES",
    "FRAGMENT_COVERAGE_MIN",
    "LANE_AGREEMENT_JACCARD",
    "LINEAGE_JACCARD",
    "MACRO_SOCIETY_ID_HEX_CHARS",
    "MACRO_SOCIETY_ID_NAMESPACE",
    "MACRO_SOCIETY_ID_PREFIX",
    "MACRO_SOCIETY_POLICY_VERSION",
    "MAX_CANDIDATE_MEMBERS",
    "MAX_EVIDENCE_WINDOWS",
    "MAX_LINEAGE_EDGES",
    "MAX_WINDOW_CANDIDATES",
    "MAX_WINDOW_EDGES",
    "MAX_WINDOW_PERSONS",
    "MIN_CANDIDATE_MEMBERS",
    "MIN_LANE_CLUSTER_MEMBERS",
    "TOKEN_LANES",
    "TRANSFORM_JACCARD",
    "MacroSocietyCoverage",
    "MacroSocietyError",
    "MacroSocietyLane",
    "MacroSocietyLaneKind",
    "MacroSocietyLayer",
    "MacroSocietyLineageKind",
    "MacroSocietyMembershipStatus",
    "MacroSocietyStatus",
    "derive_macro_society_id",
    "require_macro_society_id",
    "validate_member_ids",
]

MACRO_SOCIETY_POLICY_VERSION: Final[str] = "macro-society-identity.v1"
MACRO_SOCIETY_ID_NAMESPACE: Final[str] = "macro-society-identity-v1"
MACRO_SOCIETY_ID_PREFIX: Final[str] = "msoc-"
MACRO_SOCIETY_ID_HEX_CHARS: Final[int] = 16

MIN_CANDIDATE_MEMBERS: Final[int] = 4
MIN_LANE_CLUSTER_MEMBERS: Final[int] = 4
LANE_AGREEMENT_JACCARD: Final[float] = 0.5
LINEAGE_JACCARD: Final[float] = 0.5
TRANSFORM_JACCARD: Final[float] = 0.75
ABSORPTION_CONTAINMENT: Final[float] = 0.5
FRAGMENT_COVERAGE_MIN: Final[float] = 0.4
CONTESTED_MIN_MEMBERS: Final[int] = 2

MAX_EVIDENCE_WINDOWS: Final[int] = 512
MAX_WINDOW_PERSONS: Final[int] = 20000
MAX_WINDOW_EDGES: Final[int] = 50000
MAX_CANDIDATE_MEMBERS: Final[int] = 512
MAX_WINDOW_CANDIDATES: Final[int] = 2048
MAX_LINEAGE_EDGES: Final[int] = 16384

_MACRO_SOCIETY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{MACRO_SOCIETY_ID_PREFIX}[0-9a-f]{{{MACRO_SOCIETY_ID_HEX_CHARS}}}$"
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.macro_society_contract")


class MacroSocietyLane(StrEnum):
    """The nine detached evidence lanes a candidate may draw on."""

    INTERACTION = "interaction"
    COMMUNICATION = "communication"
    MIGRATION = "migration"
    EXCHANGE = "exchange"
    INSTITUTION = "institution"
    CULTURE = "culture"
    TERRITORY = "territory"
    SELF_IDENTIFICATION = "self_identification"
    COLLECTIVE_DECISION = "collective_decision"


class MacroSocietyLaneKind(StrEnum):
    """Whether a lane contributes pairwise edges or shared-token membership."""

    EDGE = "edge"
    TOKEN = "token"


EDGE_LANES: Final[frozenset[MacroSocietyLane]] = frozenset(
    {
        MacroSocietyLane.INTERACTION,
        MacroSocietyLane.COMMUNICATION,
        MacroSocietyLane.MIGRATION,
        MacroSocietyLane.EXCHANGE,
    }
)
TOKEN_LANES: Final[frozenset[MacroSocietyLane]] = frozenset(
    {
        MacroSocietyLane.INSTITUTION,
        MacroSocietyLane.CULTURE,
        MacroSocietyLane.TERRITORY,
        MacroSocietyLane.SELF_IDENTIFICATION,
        MacroSocietyLane.COLLECTIVE_DECISION,
    }
)


class MacroSocietyStatus(StrEnum):
    """Analytical status of one candidate in one window."""

    SUPPORTED = "supported"
    FRAGMENTED = "fragmented"
    CONTESTED = "contested"


class MacroSocietyMembershipStatus(StrEnum):
    """Per-member support inside one candidate."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    CONTESTED = "contested"


class MacroSocietyLayer(StrEnum):
    """The three representations V4-02 keeps strictly separate."""

    OBJECTIVE_POPULATION = "objective_population"
    SUBJECTIVE_IDENTITY = "subjective_identity"
    ANALYTICAL_CANDIDATE = "analytical_candidate"


class MacroSocietyLineageKind(StrEnum):
    """Allowed forward-only lineage transitions between adjacent windows."""

    CONTINUED = "continued"
    TRANSFORMED = "transformed"
    SPLIT = "split"
    MERGE = "merge"
    DISSOLVED = "dissolved"
    EMERGED = "emerged"


class MacroSocietyError(ValueError):
    """Fail-closed macro-society error with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        _LOG.debug("macro_society_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class MacroSocietyCoverage:
    """Observed-versus-expected coverage; ``ratio`` is absent when unknown."""

    observed: int
    expected: int
    ratio: float | None

    def __post_init__(self) -> None:
        observed = require_exact_nonneg_int("observed", self.observed)
        expected = require_exact_nonneg_int("expected", self.expected)
        if observed > expected:
            raise MacroSocietyError("macro_society_invalid_coverage")
        if expected == 0:
            ratio = None
        else:
            ratio = quantize_float(observed / expected)
        if self.ratio is not None:
            if observed == 0 and expected == 0:
                raise MacroSocietyError("macro_society_invalid_coverage")
            if quantize_float(self.ratio) != ratio:
                raise MacroSocietyError("macro_society_invalid_coverage")
        object.__setattr__(self, "observed", observed)
        object.__setattr__(self, "expected", expected)
        object.__setattr__(self, "ratio", ratio)

    @classmethod
    def of(cls, observed: int, expected: int) -> MacroSocietyCoverage:
        """Build coverage from counts, deriving the quantized ratio."""
        return cls(observed=observed, expected=expected, ratio=None)


def validate_member_ids(name: str, raw: object) -> tuple[str, ...]:
    """Validate a member id collection: no payload, no duplicates, sorted."""
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise MacroSocietyError("macro_society_content_payload_rejected")
    members: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise MacroSocietyError("macro_society_content_payload_rejected")
        try:
            member = require_stable_id(f"{name}.member_id", item)
        except ValueError as exc:
            raise MacroSocietyError("macro_society_invalid_member") from exc
        if member in seen:
            raise MacroSocietyError("macro_society_duplicate_member")
        seen.add(member)
        members.append(member)
    if not members:
        raise MacroSocietyError("macro_society_empty_member_set")
    if len(members) > MAX_CANDIDATE_MEMBERS:
        raise MacroSocietyError("macro_society_too_many_members")
    return tuple(sorted(members))


def _normalize_lane_signature(raw: Iterable[str]) -> tuple[str, ...]:
    lanes: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise MacroSocietyError("macro_society_unknown_lane")
        try:
            lane = MacroSocietyLane(item)
        except ValueError as exc:
            raise MacroSocietyError("macro_society_unknown_lane") from exc
        lanes.append(lane.value)
    if not lanes:
        raise MacroSocietyError("macro_society_unknown_lane")
    unique = tuple(sorted(set(lanes)))
    return unique


def derive_macro_society_id(
    *,
    creation_tick: int,
    founding_member_ids: Iterable[str],
    lane_signature: Iterable[str],
) -> str:
    """Derive the opaque ``msoc-`` id from first-observation evidence only.

    The id is content-addressed over the creation tick, the founding member set,
    and the contributing lane signature. It never includes current membership, a
    mutable counter, a UUID, or a wall-clock value.
    """
    tick = require_exact_nonneg_int("creation_tick", creation_tick)
    members = validate_member_ids("founding_member_ids", tuple(founding_member_ids))
    lanes = _normalize_lane_signature(lane_signature)
    payload = {
        "namespace": MACRO_SOCIETY_ID_NAMESPACE,
        "creation_tick": tick,
        "founding_member_ids": list(members),
        "lane_signature": list(lanes),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"{MACRO_SOCIETY_ID_PREFIX}{digest[:MACRO_SOCIETY_ID_HEX_CHARS]}"


def require_macro_society_id(value: str) -> str:
    """Validate an exact ``msoc-`` plus 16 lowercase hex characters id."""
    if not isinstance(value, str) or not _MACRO_SOCIETY_ID_PATTERN.match(value):
        raise MacroSocietyError("macro_society_invalid_id")
    return value
