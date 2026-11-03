"""Three separated detached dispute layers with a hard leakage guard.

Objective rows are aggregate counts of committed events. Subjective rows carry a
deterministic safe owner token plus per-case counts. Analytical rows use ``disp-``
candidate identities only. Leakage between layers is a hard failure.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import astuple, dataclass, fields
from typing import Final, NoReturn, cast

from analysis.dispute_contract import (
    DISPUTE_FORBIDDEN_RESULT_FIELDS,
    DISPUTE_OWNER_LOCAL_PREFIXES,
    DisputeAnalysisError,
    DisputeCoverage,
    require_dispute_candidate_id,
)
from analysis.dispute_evidence import (
    DisputeObjectiveAnchorKind,
    DisputeObjectiveAnchorRow,
    DisputeWindowEvidence,
)
from analysis.dispute_lineage import (
    DisputeAnalysis,
    DisputeAnalysisSummary,
)
from analysis.disputes import DisputeHarvestRows

__all__ = [
    "DisputeAnalyticalRow",
    "DisputeLayerView",
    "DisputeObjectiveRow",
    "DisputeSubjectiveRow",
    "assert_dispute_layer_separation",
    "dispute_layer_digest",
    "project_dispute_layers",
    "require_dispute_owner_token",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.dispute_layers")

_OWNER_TOKEN_NAMESPACE: Final[str] = "dispute-owner-token"
_OWNER_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")


def _fail(code: str = "dispute_invalid_row") -> None:
    raise DisputeAnalysisError(code)


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail()
    return cast(int, value)


def require_dispute_owner_token(value: object) -> str:
    """Require one deterministic 16-hex safe owner token."""
    if not isinstance(value, str) or _OWNER_TOKEN_PATTERN.match(value) is None:
        raise DisputeAnalysisError("dispute_owner_token")
    return value


def dispute_owner_token(owner_id: str) -> str:
    """Return the deterministic safe token for one owner id."""
    if not isinstance(owner_id, str) or not owner_id:
        _fail()
    material = "\x1f".join((_OWNER_TOKEN_NAMESPACE, owner_id))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class DisputeObjectiveRow:
    """One tick of aggregate objective counts only; no ids of any kind."""

    tick: int
    observed_occurrence_count: int
    observed_transfer_count: int
    observed_harm_count: int
    observed_commitment_count: int
    observed_record_count: int
    observed_communication_count: int

    def __post_init__(self) -> None:
        for name in (
            "tick",
            "observed_occurrence_count",
            "observed_transfer_count",
            "observed_harm_count",
            "observed_commitment_count",
            "observed_record_count",
            "observed_communication_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class DisputeSubjectiveRow:
    """One owner's belief about one case, with counts and a safe owner token."""

    owner_token: str
    case_ref: str
    status: str
    claim_count: int
    counterclaim_count: int
    testimony_count: int
    evidence_count: int
    rule_reference_count: int
    resolution_count: int
    coverage: DisputeCoverage

    def __post_init__(self) -> None:
        require_dispute_owner_token(self.owner_token)
        if not isinstance(self.case_ref, str) or not self.case_ref:
            _fail()
        if not isinstance(self.status, str) or not self.status:
            _fail()
        for name in (
            "claim_count",
            "counterclaim_count",
            "testimony_count",
            "evidence_count",
            "rule_reference_count",
            "resolution_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if type(self.coverage) is not DisputeCoverage:
            _fail()


@dataclass(frozen=True, slots=True)
class DisputeAnalyticalRow:
    """One analytical candidate summary; uses ``disp-`` identity only."""

    candidate_id: str
    kind: str
    subject_token: str
    party_count: int
    owner_count: int
    claim_count: int
    counterclaim_count: int
    testimony_count: int
    evidence_count: int
    resolution_count: int
    disagreement_count: int
    objective_supported_count: int
    objective_unresolved_count: int
    objective_inconsistent_count: int
    status: str
    coverage: DisputeCoverage

    def __post_init__(self) -> None:
        require_dispute_candidate_id(self.candidate_id)
        if not isinstance(self.kind, str) or not self.kind:
            _fail()
        if not isinstance(self.subject_token, str) or not self.subject_token:
            _fail()
        if not isinstance(self.status, str) or not self.status:
            _fail()
        for name in (
            "party_count",
            "owner_count",
            "claim_count",
            "counterclaim_count",
            "testimony_count",
            "evidence_count",
            "resolution_count",
            "disagreement_count",
            "objective_supported_count",
            "objective_unresolved_count",
            "objective_inconsistent_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if type(self.coverage) is not DisputeCoverage:
            _fail()


@dataclass(frozen=True, slots=True)
class DisputeLayerView:
    objective: tuple[DisputeObjectiveRow, ...]
    subjective: tuple[DisputeSubjectiveRow, ...]
    analytical: tuple[DisputeAnalyticalRow, ...]
    digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "objective", tuple(sorted(self.objective, key=lambda row: row.tick))
        )
        object.__setattr__(
            self,
            "subjective",
            tuple(
                sorted(
                    self.subjective,
                    key=lambda row: (row.owner_token, row.case_ref),
                )
            ),
        )
        object.__setattr__(
            self,
            "analytical",
            tuple(sorted(self.analytical, key=lambda row: row.candidate_id)),
        )
        object.__setattr__(self, "digest", _layer_digest(self))


def _objective_rows(
    *,
    windows: Sequence[DisputeWindowEvidence],
    objective_rows: Sequence[DisputeObjectiveAnchorRow],
) -> tuple[DisputeObjectiveRow, ...]:
    if objective_rows:
        counts: dict[int, Counter[str]] = {}
        for anchor in objective_rows:
            bucket = counts.setdefault(anchor.tick, Counter())
            bucket[anchor.kind.value] += 1
        rows = []
        for tick in sorted(counts):
            counter = counts[tick]
            rows.append(
                DisputeObjectiveRow(
                    tick=tick,
                    observed_occurrence_count=sum(counter.values()),
                    observed_transfer_count=counter[
                        DisputeObjectiveAnchorKind.ITEM_TRANSFER.value
                    ]
                    + counter[DisputeObjectiveAnchorKind.EXCHANGE_COMPLETION.value],
                    observed_harm_count=counter[DisputeObjectiveAnchorKind.HARM.value],
                    observed_commitment_count=counter[
                        DisputeObjectiveAnchorKind.COMMITMENT_DECLARATION.value
                    ],
                    observed_record_count=counter[
                        DisputeObjectiveAnchorKind.RECORD_CREATION.value
                    ]
                    + counter[DisputeObjectiveAnchorKind.REPOSITORY_ENTRY.value],
                    observed_communication_count=counter[
                        DisputeObjectiveAnchorKind.OTHER.value
                    ],
                )
            )
        return tuple(rows)
    return tuple(
        DisputeObjectiveRow(
            tick=window.end_tick,
            observed_occurrence_count=window.objective_anchor_count,
            observed_transfer_count=0,
            observed_harm_count=0,
            observed_commitment_count=0,
            observed_record_count=0,
            observed_communication_count=0,
        )
        for window in windows
    )


def _subjective_rows(rows: DisputeHarvestRows) -> tuple[DisputeSubjectiveRow, ...]:
    views: list[DisputeSubjectiveRow] = []
    for case in rows.cases:
        case_claims = tuple(
            claim for claim in rows.claims if claim.case_ref == case.case_ref
        )
        partial = case.coverage == "partial"
        views.append(
            DisputeSubjectiveRow(
                owner_token=dispute_owner_token(case.owner_id),
                case_ref=case.case_ref,
                status=case.status,
                claim_count=len(case_claims),
                counterclaim_count=sum(
                    1 for claim in case_claims if claim.role == "counterclaim"
                ),
                testimony_count=sum(
                    1 for item in rows.testimony if item.case_ref == case.case_ref
                ),
                evidence_count=sum(
                    1 for item in rows.evidence if item.case_ref == case.case_ref
                ),
                rule_reference_count=sum(
                    1 for item in rows.rule_references if item.case_ref == case.case_ref
                ),
                resolution_count=sum(
                    1 for item in rows.resolutions if item.case_ref == case.case_ref
                ),
                coverage=DisputeCoverage(observed=1, expected=1, partial=partial),
            )
        )
    return tuple(views)


def _analytical_rows(
    rows: DisputeHarvestRows,
    analysis: DisputeAnalysis,
    summary: DisputeAnalysisSummary,
) -> tuple[DisputeAnalyticalRow, ...]:
    resolution_by_candidate = {item.candidate_id: item for item in analysis.resolution}
    alignment_by_candidate = {item.candidate_id: item for item in analysis.alignment}
    views: list[DisputeAnalyticalRow] = []
    for candidate in analysis.candidates:
        candidate_id = candidate.candidate_key
        members = tuple(
            claim
            for claim in rows.claims
            if claim.claim_ref in set(candidate.claim_refs)
        )
        resolution = resolution_by_candidate.get(candidate_id)
        alignment = alignment_by_candidate.get(candidate_id)
        views.append(
            DisputeAnalyticalRow(
                candidate_id=candidate_id,
                kind=candidate.kind,
                subject_token=candidate.subject_token,
                party_count=len(candidate.party_ids),
                owner_count=len(candidate.owner_ids),
                claim_count=len(members),
                counterclaim_count=sum(
                    1 for claim in members if claim.role == "counterclaim"
                ),
                testimony_count=sum(
                    1
                    for item in rows.testimony
                    if item.claim_ref in set(candidate.claim_refs)
                ),
                evidence_count=sum(
                    1
                    for item in rows.evidence
                    if item.claim_ref in set(candidate.claim_refs)
                ),
                resolution_count=(
                    candidate.resolution_count
                    if resolution is None
                    else (
                        resolution.proposed
                        + resolution.partially_accepted
                        + resolution.apparently_accepted
                        + resolution.contested
                        + resolution.withdrawn
                        + resolution.expired
                    )
                ),
                disagreement_count=candidate.disagreement_count,
                objective_supported_count=(
                    0 if alignment is None else alignment.supported_claims
                ),
                objective_unresolved_count=(
                    0 if alignment is None else alignment.unresolved_claims
                ),
                objective_inconsistent_count=(
                    0 if alignment is None else alignment.inconsistent_claims
                ),
                status=candidate.status.value,
                coverage=candidate.coverage,
            )
        )
    if summary.candidate_count != len(views):
        raise DisputeAnalysisError("dispute_invalid_candidate")
    return tuple(views)


def project_dispute_layers(
    rows: DisputeHarvestRows,
    analysis: DisputeAnalysis,
    summary: DisputeAnalysisSummary,
    *,
    windows: Sequence[DisputeWindowEvidence] = (),
    objective_rows: Sequence[DisputeObjectiveAnchorRow] = (),
) -> DisputeLayerView:
    """Project objective counts, owner claims, and candidates separately."""

    if type(rows) is not DisputeHarvestRows:
        raise TypeError("rows must be DisputeHarvestRows")
    if type(analysis) is not DisputeAnalysis:
        raise TypeError("analysis must be DisputeAnalysis")
    if type(summary) is not DisputeAnalysisSummary:
        raise TypeError("summary must be DisputeAnalysisSummary")
    view = DisputeLayerView(
        objective=_objective_rows(
            windows=tuple(windows), objective_rows=tuple(objective_rows)
        ),
        subjective=_subjective_rows(rows),
        analytical=_analytical_rows(rows, analysis, summary),
    )
    assert_dispute_layer_separation(view)
    _LOG.debug(
        "dispute_layers objective=%s subjective=%s analytical=%s",
        len(view.objective),
        len(view.subjective),
        len(view.analytical),
    )
    return view


def _leak(field_name: str) -> NoReturn:
    _LOG.error(
        "dispute_layer_leak field=%s reason_code=dispute_layer_leak",
        field_name,
    )
    raise DisputeAnalysisError("dispute_layer_leak")


def _row_field_names(model: type[object]) -> frozenset[str]:
    return frozenset(item.name for item in fields(model))  # type: ignore[arg-type]


def _contains_owner_local(value: str) -> bool:
    return value.startswith(DISPUTE_OWNER_LOCAL_PREFIXES)


def assert_dispute_layer_separation(view: DisputeLayerView) -> None:
    """Fail closed when ids, owner claims, or candidates cross layers."""

    if type(view) is not DisputeLayerView:
        raise TypeError("view must be DisputeLayerView")
    for model in (
        DisputeObjectiveRow,
        DisputeSubjectiveRow,
        DisputeAnalyticalRow,
    ):
        if _row_field_names(model) & DISPUTE_FORBIDDEN_RESULT_FIELDS:
            _leak(model.__name__)
    objective_fields = _row_field_names(DisputeObjectiveRow)
    if objective_fields & {"owner_id", "owner_token", "candidate_id"}:
        _leak("objective")
    analytical_fields = _row_field_names(DisputeAnalyticalRow)
    if analytical_fields & {"owner_id", "owner_token"}:
        _leak("analytical")
    for objective_row in view.objective:
        for value in (
            objective_row.observed_occurrence_count,
            objective_row.observed_transfer_count,
            objective_row.observed_harm_count,
            objective_row.observed_commitment_count,
            objective_row.observed_record_count,
            objective_row.observed_communication_count,
        ):
            if type(value) is not int:
                _leak("objective")
        if objective_row.tick < 0:
            _leak("objective")
    for subjective_row in view.subjective:
        require_dispute_owner_token(subjective_row.owner_token)
        if _contains_owner_local(
            subjective_row.case_ref
        ) or subjective_row.case_ref.startswith("disp-"):
            _leak("subjective")
    for analytical_row in view.analytical:
        require_dispute_candidate_id(analytical_row.candidate_id)
        if _contains_owner_local(analytical_row.subject_token):
            _leak("analytical")
        if analytical_row.subject_token.startswith("disp-"):
            _leak("analytical")


def _layer_digest(view: DisputeLayerView) -> str:
    material: list[str] = [f"o:{astuple(row)!r}" for row in view.objective]
    material.extend(f"s:{astuple(row)!r}" for row in view.subjective)
    material.extend(f"a:{astuple(row)!r}" for row in view.analytical)
    return hashlib.sha256("\x1f".join(sorted(material)).encode("utf-8")).hexdigest()


def dispute_layer_digest(view: DisputeLayerView) -> str:
    """Return an order-independent digest of the layer view."""

    if type(view) is not DisputeLayerView:
        raise TypeError("view must be DisputeLayerView")
    return _layer_digest(view)
