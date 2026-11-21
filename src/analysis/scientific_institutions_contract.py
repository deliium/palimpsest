"""Closed detached vocabulary for scientific-institution practice analysis.

The module declares value types only. Objective receipts, owner-attributed
organization context, and analytical associations are separate types on
purpose: composing them into one "scientific institution" object would collapse
the three authorities this project keeps apart. No cognition, world, API,
persistence, or client import belongs here.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MAX_BOUNDARY_OWNERS",
    "MAX_CUMULATIVE_EVENTS",
    "MAX_ORGANIZATION_CONTRIBUTIONS",
    "MAX_PRACTICE_TICKS",
    "MAX_PRACTICE_WINDOWS",
    "MAX_PUBLISHED_ROWS",
    "MAX_WINDOW_ROWS",
    "OPTIONAL_PRACTICE_LANES",
    "PRACTICE_WINDOW_TICKS",
    "SCIENTIFIC_INSTITUTIONS_POLICY_VERSION",
    "SCIENTIFIC_INSTITUTIONS_TOKEN_HEX_LEN",
    "SCIENTIFIC_INSTITUTIONS_TOKEN_NAMESPACE",
    "SCIENTIFIC_INSTITUTIONS_TOKEN_PREFIX",
    "PracticeCarrierAction",
    "PracticeCarrierFact",
    "PracticeCarrierKind",
    "PracticeCarrierSurvivalFact",
    "PracticeCoverage",
    "PracticeCoverageStatus",
    "PracticeExecutionFact",
    "PracticeLane",
    "PracticeLayer",
    "PracticeOrganizationFact",
    "PracticeOrganizationLink",
    "PracticeSignalKind",
    "PracticeStatus",
    "PracticeSupplementFact",
    "PracticeWindow",
    "ScientificInstitutionContextEvidence",
    "ScientificInstitutionContextWindow",
    "ScientificInstitutionsError",
    "canonical_activity_keys",
    "derive_practice_token",
    "practice_activity_key",
    "require_boundary_owner_cap",
    "require_cumulative_event_cap",
    "require_organization_contribution_cap",
    "require_practice_token",
    "require_practice_window_index",
    "require_published_row_cap",
    "require_window_row_cap",
]

SCIENTIFIC_INSTITUTIONS_POLICY_VERSION: Final[str] = "scientific-institutions.v1"
SCIENTIFIC_INSTITUTIONS_TOKEN_NAMESPACE: Final[str] = "scientific-institutions.v1"
SCIENTIFIC_INSTITUTIONS_TOKEN_PREFIX: Final[str] = "t:"
SCIENTIFIC_INSTITUTIONS_TOKEN_HEX_LEN: Final[int] = 32

PRACTICE_WINDOW_TICKS: Final[int] = 32
MAX_PRACTICE_WINDOWS: Final[int] = 16
MAX_PRACTICE_TICKS: Final[int] = MAX_PRACTICE_WINDOWS * PRACTICE_WINDOW_TICKS
MAX_BOUNDARY_OWNERS: Final[int] = 64
MAX_ORGANIZATION_CONTRIBUTIONS: Final[int] = 128
MAX_CUMULATIVE_EVENTS: Final[int] = 32_768
MAX_WINDOW_ROWS: Final[int] = 4_096
MAX_PUBLISHED_ROWS: Final[int] = 8_192

_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(SCIENTIFIC_INSTITUTIONS_TOKEN_PREFIX)}"
    rf"[0-9a-f]{{{SCIENTIFIC_INSTITUTIONS_TOKEN_HEX_LEN}}}$"
)
_ORGANIZATION_PATTERN: Final[re.Pattern[str]] = re.compile(r"^org-[0-9a-f]{16}$")

_TOKEN_DOMAINS: Final[frozenset[str]] = frozenset(
    {"actor", "occurrence", "carrier", "source_root", "owner_local", "organization"}
)

OPTIONAL_PRACTICE_LANES: Final[tuple[str, ...]] = (
    "archive",
    "institutional_memory",
    "instrument",
    "procedure",
    "record",
    "replication",
    "teaching",
)


class ScientificInstitutionsError(ValueError):
    """Fail-closed analysis error carrying only a stable reason code."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code: str = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


class PracticeCoverageStatus(StrEnum):
    """Per-window per-lane evidence coverage; absence is never zero."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class PracticeLane(StrEnum):
    """Closed evidence lanes, each with its own denominator."""

    EXECUTION = "execution"
    CARRIER = "carrier"
    ORGANIZATION = "organization"
    RECORD = "record"
    ARCHIVE = "archive"
    TEACHING = "teaching"
    REPLICATION = "replication"
    INSTRUMENT = "instrument"
    PROCEDURE = "procedure"
    INSTITUTIONAL_MEMORY = "institutional_memory"
    OFFICE = "office"


class PracticeLayer(StrEnum):
    """The three representations that must never be collapsed."""

    OBJECTIVE_RECEIPT = "objective_receipt"
    OWNER_CLAIM = "owner_claim"
    ANALYTICAL_ASSOCIATION = "analytical_association"


class PracticeStatus(StrEnum):
    """Closed window-local practice status; no quality or truth rank exists."""

    SUPPORTED = "supported"
    STABLE = "stable"
    OBSERVED_ONLY = "observed_only"
    NOT_OBSERVED = "not_observed"
    UNAVAILABLE = "unavailable"


class PracticeCarrierKind(StrEnum):
    """Closed durable carrier families referenced by committed receipts."""

    ARTIFACT = "artifact"
    RECORD = "record"
    REPOSITORY = "repository"
    REPOSITORY_MEMBER = "repository_member"


class PracticeCarrierAction(StrEnum):
    """Closed carrier service actions; copy is provenance, not a fresh root."""

    CREATE = "create"
    ANNOTATE = "annotate"
    DEPOSIT = "deposit"
    RETRIEVE = "retrieve"
    COPY = "copy"


class PracticeSignalKind(StrEnum):
    """Optional practice descriptions; never preset actor classes or votes."""

    EXPERIMENTER = "experimenter"
    RECORD_KEEPER = "record_keeper"
    TEACHER = "teacher"
    REPLICATION_EXPECTATION = "replication_expectation"
    ARCHIVE = "archive"
    SHARED_INSTRUMENT = "shared_instrument"
    PROCEDURE = "procedure"
    INSTITUTIONAL_MEMORY = "institutional_memory"
    OFFICE = "office"


def derive_practice_token(domain: str, *parts: str) -> str:
    """Derive one run-scoped opaque token in an explicit digest domain."""

    if domain not in _TOKEN_DOMAINS:
        raise ScientificInstitutionsError("scientific_institutions_invalid_domain")
    if not parts:
        raise ScientificInstitutionsError("scientific_institutions_invalid_token")
    material: list[str] = []
    for part in parts:
        if type(part) is not str or not part:
            raise ScientificInstitutionsError("scientific_institutions_invalid_token")
        material.append(part)
    payload = "\x1f".join(
        (SCIENTIFIC_INSTITUTIONS_TOKEN_NAMESPACE, domain, *material)
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return (
        f"{SCIENTIFIC_INSTITUTIONS_TOKEN_PREFIX}"
        f"{digest[:SCIENTIFIC_INSTITUTIONS_TOKEN_HEX_LEN]}"
    )


def require_practice_token(value: str) -> str:
    """Validate one exact opaque practice token."""

    if type(value) is not str or _TOKEN_PATTERN.match(value) is None:
        raise ScientificInstitutionsError("scientific_institutions_invalid_token")
    return value


def practice_activity_key(operator: str, process_token: str) -> tuple[str, str]:
    """Return the closed coarse activity family key `(operator, process)`."""

    try:
        left = require_stable_id("operator", operator)
        right = require_stable_id("process_token", process_token)
    except ValueError as exc:
        raise ScientificInstitutionsError(
            "scientific_institutions_invalid_activity"
        ) from exc
    return (left, right)


def _require_tick(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except (TypeError, ValueError) as exc:
        raise ScientificInstitutionsError(
            "scientific_institutions_invalid_range"
        ) from exc


def _require_text(name: str, value: object) -> str:
    try:
        return require_stable_id(name, value)
    except (TypeError, ValueError) as exc:
        raise ScientificInstitutionsError(
            "scientific_institutions_invalid_identity"
        ) from exc


def _require_organization(value: object) -> str:
    if type(value) is not str or _ORGANIZATION_PATTERN.match(value) is None:
        raise ScientificInstitutionsError(
            "scientific_institutions_invalid_identity"
        )
    return value


def _sorted_tokens(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ScientificInstitutionsError("scientific_institutions_invalid_order")
    out: list[str] = []
    for value in values:
        out.append(require_practice_token(value))
    if len(set(out)) != len(out):
        raise ScientificInstitutionsError("scientific_institutions_duplicate_token")
    if tuple(out) != tuple(sorted(out)):
        raise ScientificInstitutionsError("scientific_institutions_invalid_order")
    return tuple(out)


def _sorted_typed_tokens(
    name: str, values: object
) -> tuple[tuple[str, str], ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ScientificInstitutionsError("scientific_institutions_invalid_order")
    out: list[tuple[str, str]] = []
    for entry in values:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ScientificInstitutionsError("scientific_institutions_invalid_order")
        kind, token = entry
        if type(kind) is not str or not kind:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_identity"
            )
        out.append(
            (
                require_stable_id(f"{name}.kind", kind),
                require_practice_token(token),
            )
        )
    if len(set(out)) != len(out):
        raise ScientificInstitutionsError("scientific_institutions_duplicate_token")
    if tuple(out) != tuple(sorted(out)):
        raise ScientificInstitutionsError("scientific_institutions_invalid_order")
    return tuple(out)


def require_practice_window_index(value: object) -> int:
    """Validate one window index and enforce the first-release cap."""

    index = _require_tick("window_index", value)
    if index >= MAX_PRACTICE_WINDOWS:
        raise ScientificInstitutionsError("scientific_institutions_window_cap")
    return index


def require_boundary_owner_cap(value: object) -> int:
    """Reject a boundary with more than the supported owner count."""

    count = _require_tick("owner_count", value)
    if count > MAX_BOUNDARY_OWNERS:
        raise ScientificInstitutionsError("scientific_institutions_owner_cap")
    return count


def require_organization_contribution_cap(value: object) -> int:
    """Reject a detector window with too many organization contributions."""

    count = _require_tick("organization_contribution_count", value)
    if count > MAX_ORGANIZATION_CONTRIBUTIONS:
        raise ScientificInstitutionsError(
            "scientific_institutions_contribution_cap"
        )
    return count


def require_cumulative_event_cap(value: object) -> int:
    """Reject a supplied boundary beyond the cumulative event cap."""

    count = _require_tick("cumulative_event_count", value)
    if count > MAX_CUMULATIVE_EVENTS:
        raise ScientificInstitutionsError("scientific_institutions_event_cap")
    return count


def require_window_row_cap(value: object) -> int:
    """Reject a projected window beyond the row cap."""

    count = _require_tick("window_row_count", value)
    if count > MAX_WINDOW_ROWS:
        raise ScientificInstitutionsError("scientific_institutions_row_cap")
    return count


def require_published_row_cap(value: object) -> int:
    """Reject a publication beyond the total row cap."""

    count = _require_tick("published_row_count", value)
    if count > MAX_PUBLISHED_ROWS:
        raise ScientificInstitutionsError(
            "scientific_institutions_publication_cap"
        )
    return count


@dataclass(frozen=True, slots=True)
class PracticeCoverage:
    """One lane's coverage state inside one absolute-tick window."""

    run_id: str
    window_index: int
    lane: PracticeLane
    status: PracticeCoverageStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        object.__setattr__(
            self,
            "window_index",
            require_practice_window_index(self.window_index),
        )
        if type(self.lane) is not PracticeLane:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_lane"
            )
        if type(self.status) is not PracticeCoverageStatus:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_coverage"
            )

    @property
    def complete(self) -> bool:
        return self.status is PracticeCoverageStatus.COMPLETE


@dataclass(frozen=True, slots=True)
class PracticeWindow:
    """One half-open `[start, end)` window; an incomplete tail never qualifies."""

    run_id: str
    window_index: int
    start_tick: int
    end_tick_exclusive: int
    complete: bool
    coverage: tuple[PracticeCoverage, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        index = require_practice_window_index(self.window_index)
        start = _require_tick("start_tick", self.start_tick)
        end = _require_tick("end_tick_exclusive", self.end_tick_exclusive)
        if start != index * PRACTICE_WINDOW_TICKS:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_range"
            )
        if end <= start or end - start > PRACTICE_WINDOW_TICKS:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_range"
            )
        if type(self.complete) is not bool:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_range"
            )
        if self.complete and end - start != PRACTICE_WINDOW_TICKS:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_range"
            )
        if not self.complete and end - start == PRACTICE_WINDOW_TICKS:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_range"
            )
        if isinstance(self.coverage, (str, bytes)) or not isinstance(
            self.coverage, Sequence
        ):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_coverage"
            )
        coverage: list[PracticeCoverage] = []
        seen: set[str] = set()
        for entry in self.coverage:
            if type(entry) is not PracticeCoverage:
                raise ScientificInstitutionsError(
                    "scientific_institutions_invalid_coverage"
                )
            if entry.run_id != self.run_id or entry.window_index != index:
                raise ScientificInstitutionsError(
                    "scientific_institutions_invalid_coverage"
                )
            if entry.lane.value in seen:
                raise ScientificInstitutionsError(
                    "scientific_institutions_duplicate_lane"
                )
            seen.add(entry.lane.value)
            coverage.append(entry)
        coverage.sort(key=lambda item: item.lane.value)
        object.__setattr__(self, "coverage", tuple(coverage))

    @property
    def start(self) -> int:
        return self.start_tick

    @property
    def end_exclusive(self) -> int:
        return self.end_tick_exclusive

    def covers(self, tick: int) -> bool:
        return self.start_tick <= tick < self.end_tick_exclusive

    def lane_status(self, lane: PracticeLane) -> PracticeCoverageStatus | None:
        for entry in self.coverage:
            if entry.lane is lane:
                return entry.status
        return None


@dataclass(frozen=True, slots=True)
class PracticeExecutionFact:
    """One admitted deliberate experiment receipt; outcome fields stay out."""

    run_id: str
    occurrence_token: str
    actor_token: str
    tick: int
    operator: str
    process_token: str
    layer: PracticeLayer = PracticeLayer.OBJECTIVE_RECEIPT

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        object.__setattr__(
            self, "occurrence_token", require_practice_token(self.occurrence_token)
        )
        object.__setattr__(
            self, "actor_token", require_practice_token(self.actor_token)
        )
        object.__setattr__(self, "tick", _require_tick("tick", self.tick))
        key = practice_activity_key(self.operator, self.process_token)
        object.__setattr__(self, "operator", key[0])
        object.__setattr__(self, "process_token", key[1])
        if self.layer is not PracticeLayer.OBJECTIVE_RECEIPT:
            raise ScientificInstitutionsError(
                "scientific_institutions_layer_mismatch"
            )

    @property
    def activity_key(self) -> tuple[str, str]:
        return (self.operator, self.process_token)


@dataclass(frozen=True, slots=True)
class PracticeCarrierFact:
    """One committed carrier service receipt on a live durable carrier."""

    run_id: str
    occurrence_token: str
    actor_token: str
    tick: int
    carrier_kind: PracticeCarrierKind
    carrier_token: str
    source_root_token: str
    action: PracticeCarrierAction
    member_token: str | None = None
    parent_token: str | None = None
    layer: PracticeLayer = PracticeLayer.OBJECTIVE_RECEIPT

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        object.__setattr__(
            self, "occurrence_token", require_practice_token(self.occurrence_token)
        )
        object.__setattr__(
            self, "actor_token", require_practice_token(self.actor_token)
        )
        object.__setattr__(self, "tick", _require_tick("tick", self.tick))
        if type(self.carrier_kind) is not PracticeCarrierKind:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_carrier"
            )
        if type(self.action) is not PracticeCarrierAction:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_action"
            )
        object.__setattr__(
            self, "carrier_token", require_practice_token(self.carrier_token)
        )
        object.__setattr__(
            self,
            "source_root_token",
            require_practice_token(self.source_root_token),
        )
        if self.member_token is not None:
            object.__setattr__(
                self, "member_token", require_practice_token(self.member_token)
            )
        if self.parent_token is not None:
            object.__setattr__(
                self, "parent_token", require_practice_token(self.parent_token)
            )
        if (
            self.carrier_kind is PracticeCarrierKind.REPOSITORY_MEMBER
            and self.member_token is None
        ):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_carrier"
            )
        if (
            self.carrier_kind is not PracticeCarrierKind.REPOSITORY_MEMBER
            and self.member_token is not None
        ):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_carrier"
            )
        if (
            self.action is PracticeCarrierAction.COPY
            and self.parent_token is None
        ):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_carrier"
            )
        if (
            self.action is not PracticeCarrierAction.COPY
            and self.parent_token is not None
        ):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_carrier"
            )
        if self.layer is not PracticeLayer.OBJECTIVE_RECEIPT:
            raise ScientificInstitutionsError(
                "scientific_institutions_layer_mismatch"
            )


@dataclass(frozen=True, slots=True)
class PracticeOrganizationLink:
    """One exact actor/tick association between a window candidate and a receipt."""

    actor_token: str
    execution_token: str | None = None
    service_token: str | None = None
    contribution_token: str | None = None
    contribution_tick: int | None = None
    carrier_kind: PracticeCarrierKind | None = None
    carrier_token: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "actor_token", require_practice_token(self.actor_token)
        )
        if self.execution_token is None and self.service_token is None:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_association"
            )
        if self.execution_token is not None:
            object.__setattr__(
                self,
                "execution_token",
                require_practice_token(self.execution_token),
            )
        if self.service_token is not None:
            object.__setattr__(
                self, "service_token", require_practice_token(self.service_token)
            )
        if self.contribution_token is not None:
            object.__setattr__(
                self,
                "contribution_token",
                require_practice_token(self.contribution_token),
            )
        if self.contribution_tick is not None:
            object.__setattr__(
                self,
                "contribution_tick",
                _require_tick("contribution_tick", self.contribution_tick),
            )
        if (self.carrier_kind is None) != (self.carrier_token is None):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_association"
            )
        if self.carrier_kind is not None:
            if type(self.carrier_kind) is not PracticeCarrierKind:
                raise ScientificInstitutionsError(
                    "scientific_institutions_invalid_association"
                )
            object.__setattr__(
                self,
                "carrier_token",
                require_practice_token(self.carrier_token or ""),
            )


@dataclass(frozen=True, slots=True)
class PracticeOrganizationFact:
    """Owner-attributed organization context for one window; not a witness."""

    run_id: str
    window_index: int
    organization_id: str
    candidate_key: str
    participant_tokens: tuple[str, ...]
    anchor_tokens: tuple[tuple[str, str], ...]
    procedure_tokens: tuple[str, ...]
    record_tokens: tuple[str, ...]
    claimant_tokens: tuple[str, ...]
    coverage: PracticeCoverageStatus
    links: tuple[PracticeOrganizationLink, ...] = ()
    layer: PracticeLayer = PracticeLayer.OWNER_CLAIM

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        object.__setattr__(
            self,
            "window_index",
            require_practice_window_index(self.window_index),
        )
        object.__setattr__(
            self, "organization_id", _require_organization(self.organization_id)
        )
        object.__setattr__(
            self, "candidate_key", _require_text("candidate_key", self.candidate_key)
        )
        object.__setattr__(
            self,
            "participant_tokens",
            _sorted_tokens("participant_tokens", self.participant_tokens),
        )
        object.__setattr__(
            self,
            "anchor_tokens",
            _sorted_typed_tokens("anchor_tokens", self.anchor_tokens),
        )
        object.__setattr__(
            self,
            "procedure_tokens",
            _sorted_tokens("procedure_tokens", self.procedure_tokens),
        )
        object.__setattr__(
            self,
            "record_tokens",
            _sorted_tokens("record_tokens", self.record_tokens),
        )
        object.__setattr__(
            self,
            "claimant_tokens",
            _sorted_tokens("claimant_tokens", self.claimant_tokens),
        )
        if type(self.coverage) is not PracticeCoverageStatus:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_coverage"
            )
        if isinstance(self.links, (str, bytes)) or not isinstance(
            self.links, Sequence
        ):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_association"
            )
        links: list[PracticeOrganizationLink] = []
        seen: set[tuple[object, ...]] = set()
        for link in self.links:
            if type(link) is not PracticeOrganizationLink:
                raise ScientificInstitutionsError(
                    "scientific_institutions_invalid_association"
                )
            key = (
                link.actor_token,
                link.execution_token,
                link.service_token,
                link.contribution_token,
                link.contribution_tick,
                link.carrier_kind,
                link.carrier_token,
            )
            if key in seen:
                raise ScientificInstitutionsError(
                    "scientific_institutions_duplicate_association"
                )
            seen.add(key)
            links.append(link)
        links.sort(
            key=lambda item: (
                item.actor_token,
                item.execution_token or "",
                item.service_token or "",
                item.contribution_token or "",
                item.contribution_tick if item.contribution_tick is not None else -1,
                item.carrier_kind.value if item.carrier_kind is not None else "",
                item.carrier_token or "",
            )
        )
        object.__setattr__(self, "links", tuple(links))
        if self.layer is not PracticeLayer.OWNER_CLAIM:
            raise ScientificInstitutionsError(
                "scientific_institutions_layer_mismatch"
            )


@dataclass(frozen=True, slots=True)
class PracticeSupplementFact:
    """One optional contextual signal; never a qualifying vote."""

    run_id: str
    window_index: int
    organization_id: str | None
    signal: PracticeSignalKind
    actor_tokens: tuple[str, ...]
    carrier_tokens: tuple[tuple[str, str], ...]
    tick: int
    count: int
    contextual: bool = True
    layer: PracticeLayer = PracticeLayer.ANALYTICAL_ASSOCIATION

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        object.__setattr__(
            self,
            "window_index",
            require_practice_window_index(self.window_index),
        )
        if self.organization_id is not None:
            object.__setattr__(
                self,
                "organization_id",
                _require_organization(self.organization_id),
            )
        if type(self.signal) is not PracticeSignalKind:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_signal"
            )
        object.__setattr__(
            self,
            "actor_tokens",
            _sorted_tokens("actor_tokens", self.actor_tokens),
        )
        object.__setattr__(
            self,
            "carrier_tokens",
            _sorted_typed_tokens("carrier_tokens", self.carrier_tokens),
        )
        object.__setattr__(self, "tick", _require_tick("tick", self.tick))
        count = _require_tick("count", self.count)
        if count == 0:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_signal"
            )
        object.__setattr__(self, "count", count)
        if type(self.contextual) is not bool:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_signal"
            )
        if self.layer is not PracticeLayer.ANALYTICAL_ASSOCIATION:
            raise ScientificInstitutionsError(
                "scientific_institutions_layer_mismatch"
            )


@dataclass(frozen=True, slots=True)
class PracticeCarrierSurvivalFact:
    """A typed durable carrier observed alive at one window end."""

    carrier_kind: PracticeCarrierKind
    carrier_token: str
    source_root_token: str
    member_token: str | None = None

    def __post_init__(self) -> None:
        if type(self.carrier_kind) is not PracticeCarrierKind:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_carrier"
            )
        object.__setattr__(
            self, "carrier_token", require_practice_token(self.carrier_token)
        )
        object.__setattr__(
            self,
            "source_root_token",
            require_practice_token(self.source_root_token),
        )
        if self.member_token is not None:
            object.__setattr__(
                self, "member_token", require_practice_token(self.member_token)
            )


@dataclass(frozen=True, slots=True)
class ScientificInstitutionContextWindow:
    """Window-local receipts, organization facts, links, and signals."""

    window: PracticeWindow
    executions: tuple[PracticeExecutionFact, ...]
    carriers: tuple[PracticeCarrierFact, ...]
    surviving_carriers: tuple[PracticeCarrierSurvivalFact, ...]
    organizations: tuple[PracticeOrganizationFact, ...]
    supplements: tuple[PracticeSupplementFact, ...]
    unassigned: int
    ambiguous: int = 0

    def __post_init__(self) -> None:
        if type(self.window) is not PracticeWindow:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_window"
            )
        object.__setattr__(self, "executions", tuple(self.executions))
        object.__setattr__(self, "carriers", tuple(self.carriers))
        object.__setattr__(
            self, "surviving_carriers", tuple(self.surviving_carriers)
        )
        object.__setattr__(
            self,
            "organizations",
            tuple(
                sorted(
                    self.organizations,
                    key=lambda row: (row.organization_id, row.candidate_key),
                )
            ),
        )
        object.__setattr__(
            self,
            "supplements",
            tuple(
                sorted(
                    self.supplements,
                    key=lambda row: (
                        row.signal.value,
                        row.organization_id or "",
                        row.tick,
                    ),
                )
            ),
        )
        object.__setattr__(
            self, "unassigned", require_exact_nonneg_int(
                "unassigned", self.unassigned
            )
        )
        object.__setattr__(
            self, "ambiguous", require_exact_nonneg_int(
                "ambiguous", self.ambiguous
            )
        )


@dataclass(frozen=True, slots=True)
class ScientificInstitutionContextEvidence:
    """Context evidence for every window in the completed-run projection."""

    run_id: str
    windows: tuple[ScientificInstitutionContextWindow, ...]

    def __post_init__(self) -> None:
        indexes = tuple(item.window.window_index for item in self.windows)
        if indexes != tuple(range(len(indexes))):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_window"
            )

    def window(self, window_index: int) -> ScientificInstitutionContextWindow:
        for item in self.windows:
            if item.window.window_index == window_index:
                return item
        raise ScientificInstitutionsError("scientific_institutions_unknown_window")


def canonical_activity_keys(
    facts: Iterable[PracticeExecutionFact],
) -> tuple[tuple[str, str], ...]:
    """Return sorted unique activity keys without changing receipt order."""

    return tuple(sorted({fact.activity_key for fact in facts}))
