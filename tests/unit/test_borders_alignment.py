"""Researcher-only border alignment labels."""

from __future__ import annotations

from analysis.borders_alignment import align_border_interpretations
from analysis.borders_contract import (
    BorderAgreementRow,
    BorderClaimRow,
    BorderPatternRow,
)

DOMAIN = "bdc-1111111111111111"
OWNER = "owner-1"
COUNTERPARTY = "counterparty-1"
LOCATIONS = ("loc-a", "loc-b")


def _claim() -> BorderClaimRow:
    return BorderClaimRow(
        owner_token=OWNER,
        domain_token=DOMAIN,
        location_tokens=LOCATIONS,
        boundary_edge_tokens=(),
        status="claimed",
        strength=1.0,
    )


def _agreement() -> BorderAgreementRow:
    return BorderAgreementRow(
        agreement_token="bda-1111111111111111",
        domain_token=DOMAIN,
        counterparty_token=COUNTERPARTY,
        provision_tokens=("territorial_acknowledgement",),
        status="apparent_acceptance",
        recognition="recognized",
    )


def _pattern() -> BorderPatternRow:
    return BorderPatternRow(
        pattern_token="bpt-1111111111111111",
        domain_token=DOMAIN,
        location_tokens=LOCATIONS,
        pattern="claim_aligned",
        physical_actions=2,
        claim_count=1,
        agreement_count=1,
    )


def test_claim_agreement_and_pattern_are_consistent() -> None:
    rows = align_border_interpretations((_claim(),), (_agreement(),), (_pattern(),))
    assert len(rows) == 1
    assert rows[0].alignment == "consistent"


def test_domain_without_claim_is_not_applicable() -> None:
    rows = align_border_interpretations((), (_agreement(),), ())
    assert len(rows) == 1
    assert rows[0].alignment == "not_applicable"
