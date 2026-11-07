"""Researcher-only border interpretation alignment and summary."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.borders_contract import (
    BorderAgreementRow,
    BorderAlignmentRow,
    BorderAnalysisSummary,
    BorderClaimRow,
    BorderDisputeRow,
    BorderPatternRow,
)
from analysis.borders_identity import border_candidate_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.borders.alignment")

_AGREEMENT_FINAL: Final[frozenset[str]] = frozenset(
    {"apparent_acceptance", "recognized"}
)


def _classify(
    *,
    has_claim: bool,
    has_agreement: bool,
    has_pattern: bool,
    has_dispute: bool,
    overlapping_other_owner: bool,
) -> str:
    if not has_claim:
        return "not_applicable"
    if has_dispute:
        return "inconsistent"
    if overlapping_other_owner and not has_agreement:
        return "inconsistent"
    if has_agreement and has_pattern and not has_dispute:
        return "consistent"
    return "unresolved"


def align_border_interpretations(
    claims: Sequence[BorderClaimRow],
    agreements: Sequence[BorderAgreementRow],
    patterns: Sequence[BorderPatternRow],
    *,
    disputes: Sequence[BorderDisputeRow] = (),
) -> tuple[BorderAlignmentRow, ...]:
    """Classify claim/agreement/pattern agreement for researchers only."""
    groups: dict[tuple[str, ...], list[BorderClaimRow]] = {}
    for claim in claims:
        groups.setdefault(tuple(sorted(claim.location_tokens)), []).append(claim)
    agreement_domains = {
        item.domain_token for item in agreements if item.status in _AGREEMENT_FINAL
    }
    disputed_domains = {item.domain_token for item in disputes}
    pattern_domains = {item.domain_token for item in patterns}
    rows: list[BorderAlignmentRow] = []
    for locations, group in sorted(groups.items()):
        domain_tokens = {claim.domain_token for claim in group}
        owners = {claim.owner_token for claim in group}
        other_sets = [
            set(other.location_tokens)
            for other in claims
            if other.owner_token not in owners
        ]
        overlapping = any(set(locations) & other for other in other_sets)
        has_claim = True
        has_agreement = bool(domain_tokens & agreement_domains)
        has_dispute = bool(domain_tokens & disputed_domains)
        has_pattern = bool(domain_tokens & pattern_domains)
        alignment = _classify(
            has_claim=has_claim,
            has_agreement=has_agreement,
            has_pattern=has_pattern,
            has_dispute=has_dispute,
            overlapping_other_owner=overlapping,
        )
        rows.append(
            BorderAlignmentRow(
                candidate_id=border_candidate_id(locations),
                alignment=alignment,
                claim_alignment="consistent" if has_claim else "unresolved",
                agreement_alignment=("consistent" if has_agreement else "unresolved"),
                pattern_alignment="consistent" if has_pattern else "unresolved",
                basis_counts=(
                    ("claims", len(group)),
                    ("agreements", int(has_agreement)),
                    ("patterns", int(has_pattern)),
                    ("disputes", int(has_dispute)),
                ),
            )
        )
    claimed_domains = {claim.domain_token for claim in claims}
    for domain_token in sorted(
        (agreement_domains | pattern_domains | disputed_domains) - claimed_domains
    ):
        rows.append(
            BorderAlignmentRow(
                candidate_id=domain_token,
                alignment="not_applicable",
                claim_alignment="not_applicable",
                agreement_alignment=(
                    "consistent"
                    if domain_token in agreement_domains
                    else "not_applicable"
                ),
                pattern_alignment=(
                    "consistent"
                    if domain_token in pattern_domains
                    else "not_applicable"
                ),
                basis_counts=(
                    ("claims", 0),
                    ("agreements", int(domain_token in agreement_domains)),
                    ("patterns", int(domain_token in pattern_domains)),
                    ("disputes", int(domain_token in disputed_domains)),
                ),
            )
        )
    rows.sort(key=lambda item: item.candidate_id)
    return tuple(rows)


def summarize_borders(
    *,
    claims: Sequence[BorderClaimRow],
    agreements: Sequence[BorderAgreementRow],
    disputes: Sequence[BorderDisputeRow],
    physical_row_count: int,
    patterns: Sequence[BorderPatternRow],
    alignment: Sequence[BorderAlignmentRow],
    catalog_version: str,
    coverage: str = "partial",
) -> BorderAnalysisSummary:
    counts: dict[str, int] = {}
    for row in alignment:
        counts[row.alignment] = counts.get(row.alignment, 0) + 1
    _LOG.debug(
        "borders_summary claims=%s agreements=%s disputes=%s patterns=%s",
        len(claims),
        len(agreements),
        len(disputes),
        len(patterns),
    )
    return BorderAnalysisSummary(
        candidate_count=len({row.candidate_id for row in alignment}),
        claim_count=len(claims),
        agreement_count=len(agreements),
        dispute_count=len(disputes),
        physical_row_count=physical_row_count,
        pattern_count=len(patterns),
        alignment_counts=tuple(sorted(counts.items())),
        coverage=coverage,
        catalog_version=catalog_version,
    )


__all__ = ["align_border_interpretations", "summarize_borders"]
