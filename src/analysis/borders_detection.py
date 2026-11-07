"""Deterministic border overlap, dispute, recognition, and control detection.

Every label is descriptive. Overlap is set intersection; a dispute is retained
without a winner; a control pattern is a closed label with counts, never a
composite score.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.borders_contract import (
    BORDER_CONTROL_PATTERNS,
    BorderAgreementRow,
    BorderClaimRow,
    BorderControlSummary,
    BorderDisputeRow,
    BorderOverlapRow,
    BorderPatternRow,
    BorderRecognitionRow,
)
from analysis.borders_events import BorderPhysicalRow
from analysis.borders_policy import BordersAnalysisPolicy

_LOG: Final[logging.Logger] = logging.getLogger("analysis.borders.detection")

_AGREEMENT_FINAL: Final[frozenset[str]] = frozenset(
    {"apparent_acceptance", "recognized"}
)


def _short(prefix: str, material: str) -> str:
    return f"{prefix}{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


@dataclass(frozen=True, slots=True)
class BorderBoundaryState:
    edge_tokens: tuple[tuple[str, str], ...]
    status: str

    def __post_init__(self) -> None:
        if self.status not in {"recognized", "unresolved", "disputed"}:
            raise ValueError("status: unknown_boundary_status")


def detect_border_overlaps(
    claims: Sequence[BorderClaimRow], *, policy: BordersAnalysisPolicy
) -> tuple[BorderOverlapRow, ...]:
    """Every shared location between two different owners is retained."""
    rows = sorted(claims, key=lambda item: (item.domain_token, item.owner_token))
    overlaps: list[BorderOverlapRow] = []
    for index, left in enumerate(rows):
        for right in rows[index + 1 :]:
            if right.owner_token == left.owner_token:
                continue
            shared = sorted(set(left.location_tokens) & set(right.location_tokens))
            if not shared:
                continue
            overlaps.append(
                BorderOverlapRow(
                    left_domain_token=min(left.domain_token, right.domain_token),
                    right_domain_token=max(left.domain_token, right.domain_token),
                    overlap_location_tokens=tuple(shared),
                    overlap_count=len(shared),
                    dispute_status="unresolved",
                )
            )
            if len(overlaps) >= policy.max_pairs_per_run:
                break
    overlaps.sort(key=lambda item: (item.left_domain_token, item.right_domain_token))
    return tuple(overlaps)


def detect_border_disputes(
    overlaps: Sequence[BorderOverlapRow],
    agreements: Sequence[BorderAgreementRow],
    *,
    policy: BordersAnalysisPolicy,
) -> tuple[BorderOverlapRow, ...]:
    """Classify an overlap as acknowledged or disputed without reconciling it."""
    del policy
    acknowledged_domains = {
        agreement.domain_token
        for agreement in agreements
        if agreement.status in _AGREEMENT_FINAL
        and "territorial_acknowledgement" in agreement.provision_tokens
    }
    rows: list[BorderOverlapRow] = []
    for overlap in overlaps:
        acknowledged = (
            overlap.left_domain_token in acknowledged_domains
            or overlap.right_domain_token in acknowledged_domains
        )
        rows.append(
            BorderOverlapRow(
                left_domain_token=overlap.left_domain_token,
                right_domain_token=overlap.right_domain_token,
                overlap_location_tokens=overlap.overlap_location_tokens,
                overlap_count=overlap.overlap_count,
                dispute_status="acknowledged" if acknowledged else "disputed",
            )
        )
    rows.sort(key=lambda item: (item.left_domain_token, item.right_domain_token))
    return tuple(rows)


def detect_boundary_recognitions(
    recognitions: Sequence[BorderRecognitionRow],
    disputes: Sequence[BorderDisputeRow],
) -> tuple[BorderBoundaryState, ...]:
    """Per-edge status: dispute wins over recognition, absence is unresolved."""
    domain_edges: dict[str, set[tuple[str, str]]] = {}
    recognized: set[tuple[str, str]] = set()
    unresolved: set[tuple[str, str]] = set()
    for row in recognitions:
        domain_edges.setdefault(row.domain_token, set()).update(row.edge_tokens)
        if row.status == "disputed":
            domain_edges[row.domain_token].update(row.edge_tokens)
        elif row.status == "recognized":
            recognized.update(row.edge_tokens)
        else:
            unresolved.update(row.edge_tokens)
    disputed_edges: set[tuple[str, str]] = set()
    for dispute in disputes:
        disputed_edges.update(domain_edges.get(dispute.domain_token, set()))
    all_edges = recognized | unresolved | disputed_edges
    states: list[BorderBoundaryState] = []
    for edge in sorted(all_edges):
        if edge in disputed_edges:
            status = "disputed"
        elif edge in recognized:
            status = "recognized"
        else:
            status = "unresolved"
        states.append(BorderBoundaryState(edge_tokens=(edge,), status=status))
    return tuple(states)


def _domain_groups(
    claims: Sequence[BorderClaimRow],
) -> dict[str, tuple[str, ...]]:
    groups: dict[str, tuple[str, ...]] = {}
    for claim in claims:
        groups.setdefault(claim.domain_token, claim.location_tokens)
    return groups


def _physical_actions(
    physical: Sequence[BorderPhysicalRow],
    locations: set[str],
    policy: BordersAnalysisPolicy,
) -> int:
    if not physical:
        return 0
    latest = max(row.window_start for row in physical)
    cutoff = latest - policy.control_pattern_window_ticks
    total = 0
    for row in physical:
        if row.window_start < cutoff:
            continue
        if locations & {row.location_token}:
            total += row.action_count
    return total


def _physical_hostile(
    physical: Sequence[BorderPhysicalRow], locations: set[str]
) -> bool:
    return any(
        row.hostile_count > 0 and row.location_token in locations for row in physical
    )


def detect_control_patterns(
    physical: Sequence[BorderPhysicalRow],
    claims: Sequence[BorderClaimRow],
    agreements: Sequence[BorderAgreementRow],
    disputes: Sequence[BorderDisputeRow],
    *,
    policy: BordersAnalysisPolicy,
) -> tuple[BorderPatternRow, ...]:
    """One closed descriptive pattern per observed domain."""
    groups = _domain_groups(claims)
    physical_locations = {row.location_token for row in physical}
    rows: list[BorderPatternRow] = []
    for domain_token, locations in sorted(groups.items()):
        location_set = set(locations)
        actions = _physical_actions(physical, location_set, policy)
        hostile = _physical_hostile(physical, location_set)
        domain_agreements = [
            item for item in agreements if item.domain_token == domain_token
        ]
        domain_disputes = [
            item for item in disputes if item.domain_token == domain_token
        ]
        overlapping_other_owner = any(
            other.domain_token != domain_token
            and other.owner_token
            != next(
                (
                    claim.owner_token
                    for claim in claims
                    if claim.domain_token == domain_token
                ),
                "",
            )
            and location_set & set(other.location_tokens)
            for other in claims
        )
        if hostile or domain_disputes:
            pattern = "contested"
        elif domain_agreements and domain_disputes:
            pattern = "agreement_contested"
        elif (
            domain_agreements and actions >= policy.control_pattern_min_physical_actions
        ):
            pattern = "agreement_aligned"
        elif overlapping_other_owner:
            pattern = "claim_overlap"
        elif actions >= policy.control_pattern_min_physical_actions:
            pattern = "claim_aligned"
        elif locations:
            pattern = "claim_only"
        elif actions:
            pattern = "physical_unclaimed"
        else:
            pattern = "unclaimed"
        if not claims and not physical:
            pattern = "unknown"
        token = _short(
            "bpat-", f"pattern|{domain_token}|{pattern}|{actions}|{len(locations)}"
        )
        rows.append(
            BorderPatternRow(
                pattern_token=token,
                domain_token=domain_token,
                location_tokens=locations,
                pattern=pattern,
                physical_actions=actions,
                claim_count=1 if locations else 0,
                agreement_count=len(domain_agreements),
                dispute_count=len(domain_disputes),
            )
        )
    # Physical-only locations with no claim are explicit descriptive rows.
    unclaimed = (
        sorted(physical_locations - set().union(*map(set, groups.values())))
        if groups
        else sorted(physical_locations)
    )
    for location in unclaimed:
        token = _short("bpat-", f"pattern|{location}|physical_unclaimed")
        rows.append(
            BorderPatternRow(
                pattern_token=token,
                domain_token=_short("bdom-", f"physical|{location}"),
                location_tokens=(location,),
                pattern="physical_unclaimed",
                physical_actions=max(
                    row.action_count
                    for row in physical
                    if row.location_token == location
                ),
                claim_count=0,
            )
        )
    rows.sort(key=lambda item: (item.domain_token, item.pattern_token))
    if any(row.pattern not in BORDER_CONTROL_PATTERNS for row in rows):
        raise ValueError("borders_detection: unknown_pattern")
    _LOG.debug(
        "borders_detection overlaps=0 disputes=%s patterns=%s",
        len(disputes),
        len(rows),
    )
    return tuple(rows)


def control_summary(
    patterns: Sequence[BorderPatternRow],
) -> BorderControlSummary:
    counts: dict[str, int] = {}
    for row in patterns:
        counts[row.pattern] = counts.get(row.pattern, 0) + 1
    return BorderControlSummary(
        pattern_counts=tuple(sorted(counts.items())),
        coverage="complete" if patterns else "not_applicable",
    )


def border_detection_notices(
    *,
    physical: Sequence[BorderPhysicalRow],
    claims: Sequence[BorderClaimRow],
    agreements: Sequence[BorderAgreementRow],
    disputes: Sequence[BorderDisputeRow],
) -> tuple[str, ...]:
    notices: set[str] = set()
    if claims and not physical:
        notices.add("insufficient_physical_evidence")
    if claims and not disputes and not agreements:
        notices.add("claim_without_observation")
    if agreements and not claims:
        notices.add("agreement_without_claim")
    if claims and disputes:
        notices.add("overlap_only")
    return tuple(sorted(notices))


__all__ = [
    "BorderBoundaryState",
    "border_detection_notices",
    "control_summary",
    "detect_border_disputes",
    "detect_border_overlaps",
    "detect_boundary_recognitions",
    "detect_control_patterns",
]
