"""Bounded canonical ``inter-society-relations-snapshot-v1`` document.

Independent of ``analysis``: experiments maps harvest outputs into these DTOs.
No civilization relationship score field exists anywhere on the snapshot.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "INTER_SOCIETY_RELATIONS_FORBIDDEN_FIELD_NAMES",
    "INTER_SOCIETY_RELATIONS_PUBLICATION_PREFIX",
    "INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY",
    "INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION",
    "INTER_SOCIETY_RELATIONS_STORE_VERSION",
    "ISR_MAX_BYTES",
    "ISR_MAX_COMPARISONS",
    "ISR_MAX_PAIRS",
    "ISR_MAX_SERIES_POINTS",
    "ISR_MAX_WINDOWS",
    "InterSocietyRelationsArtifactError",
    "InterSocietyRelationsComparisonRecord",
    "InterSocietyRelationsDomainPanelRecord",
    "InterSocietyRelationsPairRecord",
    "InterSocietyRelationsSeriesPointRecord",
    "InterSocietyRelationsSnapshot",
    "InterSocietyRelationsSummaryRecord",
    "empty_inter_society_relations_snapshot",
    "require_inter_society_pair_id",
    "require_macro_society_id",
]

INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION: Final[str] = (
    "inter-society-relations-snapshot-v1"
)
INTER_SOCIETY_RELATIONS_STORE_VERSION: Final[str] = "inter-society-relations-store-v1"
INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY: Final[str] = (
    "inter-society-relations-analysis.v1"
)
INTER_SOCIETY_RELATIONS_PUBLICATION_PREFIX: Final[str] = "isr-pub-"

ISR_MAX_BYTES: Final[int] = 4 * 1024 * 1024
ISR_MAX_PAIRS: Final[int] = 4096
ISR_MAX_WINDOWS: Final[int] = 512
ISR_MAX_SERIES_POINTS: Final[int] = 8192
ISR_MAX_COMPARISONS: Final[int] = 2048

INTER_SOCIETY_RELATIONS_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "score",
        "composite",
        "rank",
        "trust",
        "valence",
        "bilateral_score",
        "civilization_relationship_score",
        "alliance_score",
        "enmity_score",
        "relationship_score",
        "trust_score",
        "raw_owner_id",
        "raw_agent_id",
        "frame_body",
        "evidence_body",
    }
)

_PAIR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^isr-[0-9a-f]{16}$")
_MSOC_PATTERN: Final[re.Pattern[str]] = re.compile(r"^msoc-[0-9a-f]{16}$")
_PUBLICATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{INTER_SOCIETY_RELATIONS_PUBLICATION_PREFIX}[0-9a-f]{{32}}$"
)
_HEX64: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_DOMAIN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "cooperation",
        "hostility",
        "exchange",
        "migration",
        "trust_proxy",
        "agreement",
        "conflict",
        "cultural_similarity",
    }
)
_AVAILABILITIES: Final[frozenset[str]] = frozenset({"present", "partial", "absent"})
_STATUSES: Final[frozenset[str]] = frozenset({"observed", "partial", "empty"})

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.inter_society_relations.models"
)


class InterSocietyRelationsArtifactError(ValueError):
    """Fail-closed snapshot error with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        _LOG.debug(
            "inter_society_relations_artifact_invalid reason_code=%s", reason_code
        )
        super().__init__(reason_code)


def require_inter_society_pair_id(value: object) -> str:
    if not isinstance(value, str) or not _PAIR_PATTERN.match(value):
        raise InterSocietyRelationsArtifactError("inter_society_relations_invalid_id")
    return value


def require_macro_society_id(value: object) -> str:
    if not isinstance(value, str) or not _MSOC_PATTERN.match(value):
        raise InterSocietyRelationsArtifactError(
            "inter_society_relations_invalid_society_id"
        )
    return value


def require_publication_id(value: object) -> str:
    if not isinstance(value, str) or not _PUBLICATION_PATTERN.match(value):
        raise InterSocietyRelationsArtifactError(
            "inter_society_relations_invalid_publication_id"
        )
    return value


def _stable(name: str, value: object) -> str:
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise InterSocietyRelationsArtifactError(
            "inter_society_relations_invalid_value"
        ) from exc


def _tick(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except ValueError as exc:
        raise InterSocietyRelationsArtifactError(
            "inter_society_relations_invalid_value"
        ) from exc


def _reject_forbidden(mapping: object) -> None:
    if not isinstance(mapping, dict):
        return
    for key, value in mapping.items():
        if isinstance(key, str) and (
            key in INTER_SOCIETY_RELATIONS_FORBIDDEN_FIELD_NAMES
            or key.endswith("_score")
        ):
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_forbidden_result_field"
            )
        if isinstance(value, dict):
            _reject_forbidden(value)


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsDomainPanelRecord:
    domain: str
    event_count: int
    availability: str
    coverage_observed: int
    coverage_expected: int
    values: dict[str, object]

    def __post_init__(self) -> None:
        domain = _stable("domain", self.domain)
        if domain not in _DOMAIN_KEYS:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_invalid_domain"
            )
        availability = _stable("availability", self.availability)
        if availability not in _AVAILABILITIES:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_invalid_availability"
            )
        values = dict(self.values)
        _reject_forbidden(values)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "availability", availability)
        object.__setattr__(self, "event_count", _tick("event_count", self.event_count))
        object.__setattr__(
            self,
            "coverage_observed",
            _tick("coverage_observed", self.coverage_observed),
        )
        object.__setattr__(
            self,
            "coverage_expected",
            _tick("coverage_expected", self.coverage_expected),
        )
        object.__setattr__(self, "values", values)


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsPairRecord:
    pair_id: str
    society_a: str
    society_b: str
    window_tick: int
    status: str
    overlap_member_count: int
    panels: tuple[InterSocietyRelationsDomainPanelRecord, ...]

    def __post_init__(self) -> None:
        pair_id = require_inter_society_pair_id(self.pair_id)
        society_a = require_macro_society_id(self.society_a)
        society_b = require_macro_society_id(self.society_b)
        if society_a >= society_b:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_invalid_pair"
            )
        status = _stable("status", self.status)
        if status not in _STATUSES:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_invalid_status"
            )
        panels = tuple(sorted(self.panels, key=lambda panel: panel.domain))
        if {panel.domain for panel in panels} != _DOMAIN_KEYS:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_invalid_domain"
            )
        object.__setattr__(self, "pair_id", pair_id)
        object.__setattr__(self, "society_a", society_a)
        object.__setattr__(self, "society_b", society_b)
        object.__setattr__(self, "window_tick", _tick("window_tick", self.window_tick))
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "overlap_member_count",
            _tick("overlap_member_count", self.overlap_member_count),
        )
        object.__setattr__(self, "panels", panels)


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsSeriesPointRecord:
    pair_id: str
    window_index: int
    window_start_tick: int
    window_end_tick: int
    panels: tuple[InterSocietyRelationsDomainPanelRecord, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "pair_id", require_inter_society_pair_id(self.pair_id))
        start = _tick("window_start_tick", self.window_start_tick)
        end = _tick("window_end_tick", self.window_end_tick)
        if end < start:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_invalid_tick_range"
            )
        object.__setattr__(
            self, "window_index", _tick("window_index", self.window_index)
        )
        object.__setattr__(self, "window_start_tick", start)
        object.__setattr__(self, "window_end_tick", end)
        object.__setattr__(
            self,
            "panels",
            tuple(sorted(self.panels, key=lambda panel: panel.domain)),
        )


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsComparisonRecord:
    left_pair_id: str
    right_pair_id: str
    left_window_tick: int
    right_window_tick: int
    domain_deltas: tuple[tuple[str, int, str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "left_pair_id", require_inter_society_pair_id(self.left_pair_id)
        )
        object.__setattr__(
            self, "right_pair_id", require_inter_society_pair_id(self.right_pair_id)
        )
        object.__setattr__(
            self,
            "left_window_tick",
            _tick("left_window_tick", self.left_window_tick),
        )
        object.__setattr__(
            self,
            "right_window_tick",
            _tick("right_window_tick", self.right_window_tick),
        )
        deltas: list[tuple[str, int, str, str]] = []
        for item in self.domain_deltas:
            if not isinstance(item, tuple) or len(item) != 4:
                raise InterSocietyRelationsArtifactError(
                    "inter_society_relations_comparison_invalid"
                )
            domain, delta, left_av, right_av = item
            domain_s = _stable("domain", domain)
            if domain_s not in _DOMAIN_KEYS:
                raise InterSocietyRelationsArtifactError(
                    "inter_society_relations_invalid_domain"
                )
            if type(delta) is not int:
                raise InterSocietyRelationsArtifactError(
                    "inter_society_relations_comparison_invalid"
                )
            left_s = _stable("left_availability", left_av)
            right_s = _stable("right_availability", right_av)
            if left_s not in _AVAILABILITIES or right_s not in _AVAILABILITIES:
                raise InterSocietyRelationsArtifactError(
                    "inter_society_relations_invalid_availability"
                )
            deltas.append((domain_s, delta, left_s, right_s))
        object.__setattr__(
            self, "domain_deltas", tuple(sorted(deltas, key=lambda row: row[0]))
        )


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsSummaryRecord:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    policy_version: str
    pair_count: int
    window_count: int
    series_point_count: int
    comparison_count: int
    coverage: str = "not_applicable"

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _stable("run_id", self.run_id))
        if self.publication_id:
            object.__setattr__(
                self, "publication_id", require_publication_id(self.publication_id)
            )
        if self.digest and _HEX64.match(self.digest) is None:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_invalid_digest"
            )
        if self.schema_version != INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_unsupported_schema"
            )
        if self.policy_version != INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_unsupported_policy"
            )
        for name in (
            "pair_count",
            "window_count",
            "series_point_count",
            "comparison_count",
        ):
            object.__setattr__(self, name, _tick(name, getattr(self, name)))
        object.__setattr__(self, "coverage", _stable("coverage", self.coverage))


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsSnapshot:
    summary: InterSocietyRelationsSummaryRecord
    pairs: tuple[InterSocietyRelationsPairRecord, ...]
    series_points: tuple[InterSocietyRelationsSeriesPointRecord, ...]
    comparisons: tuple[InterSocietyRelationsComparisonRecord, ...]
    digest: str = ""
    publication_id: str = ""
    schema_version: str = INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION
    policy_version: str = INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY

    def __post_init__(self) -> None:
        if len(self.pairs) > ISR_MAX_PAIRS:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_size_limit"
            )
        if len(self.series_points) > ISR_MAX_SERIES_POINTS:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_size_limit"
            )
        if len(self.comparisons) > ISR_MAX_COMPARISONS:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_size_limit"
            )
        pair_ids = [pair.pair_id for pair in self.pairs]
        if len(set(pair_ids)) != len(pair_ids):
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_duplicate_pair"
            )
        object.__setattr__(
            self,
            "pairs",
            tuple(
                sorted(self.pairs, key=lambda pair: (pair.window_tick, pair.pair_id))
            ),
        )
        object.__setattr__(
            self,
            "series_points",
            tuple(
                sorted(
                    self.series_points,
                    key=lambda point: (point.pair_id, point.window_index),
                )
            ),
        )
        if self.schema_version != INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_unsupported_schema"
            )
        if self.policy_version != INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_unsupported_policy"
            )
        if self.publication_id:
            object.__setattr__(
                self, "publication_id", require_publication_id(self.publication_id)
            )
        if self.digest and _HEX64.match(self.digest) is None:
            raise InterSocietyRelationsArtifactError(
                "inter_society_relations_invalid_digest"
            )


def empty_inter_society_relations_snapshot(
    *, run_id: str
) -> InterSocietyRelationsSnapshot:
    """Empty snapshot used when fewer than two societies exist."""
    summary = InterSocietyRelationsSummaryRecord(
        run_id=run_id,
        publication_id="",
        digest="",
        schema_version=INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION,
        policy_version=INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY,
        pair_count=0,
        window_count=0,
        series_point_count=0,
        comparison_count=0,
        coverage="not_applicable",
    )
    return InterSocietyRelationsSnapshot(
        summary=summary,
        pairs=(),
        series_points=(),
        comparisons=(),
    )
