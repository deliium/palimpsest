# mypy: ignore-errors
"""Border candidate identity, lineage, read-only joins, and alignment."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from analysis.borders_alignment import (
    align_border_interpretations,
    summarize_borders,
)
from analysis.borders_contract import (
    BorderAgreementRow,
    BorderCandidate,
    BorderClaimRow,
    BorderDisputeRow,
    BorderPatternRow,
)
from analysis.borders_identity import (
    assign_border_identities,
    border_candidate_id,
    derive_border_lineage,
    join_border_identities,
    split_merge_lineage,
)


def _claim(owner: str, domain: str, locations: tuple[str, ...], status="claimed"):
    return BorderClaimRow(owner, domain, locations, (), status, 0.8)


def _agreement(domain: str):
    return BorderAgreementRow(
        "bda-1",
        domain,
        "bcp-1",
        ("territorial_acknowledgement",),
        "apparent_acceptance",
        "recognized",
    )


def test_candidate_id_is_content_addressed_and_owner_independent() -> None:
    assert border_candidate_id(("b", "a")) == border_candidate_id(("a", "b"))
    assert border_candidate_id(("a",)) != border_candidate_id(("b",))
    assert border_candidate_id(("a",)).startswith("bord-")
    candidates = assign_border_identities(
        (
            _claim("owner-1", "domain-1", ("a", "b")),
            _claim("owner-2", "domain-2", ("b", "a")),
        ),
        (),
    )
    assert len(candidates) == 1
    assert candidates[0].evidence_count == 2


def test_lineage_is_forward_only_and_covers_all_six_labels() -> None:
    candidates = (
        BorderCandidate("bord-a", ("a",), (), "claimed", 1, 1, 1),
        BorderCandidate("bord-b", ("a", "b"), (), "claimed", 1, 2, 2),
        BorderCandidate("bord-c", ("c",), (), "claimed", 1, 3, 3),
    )
    edges = derive_border_lineage(candidates)
    kinds = {edge.kind for edge in edges}
    assert {"emerged", "transformed", "dissolved"} <= kinds
    assert edges == tuple(
        sorted(
            edges, key=lambda item: (item.parent_token, item.child_token, item.edge_id)
        )
    )
    split_merge = split_merge_lineage(
        (
            BorderCandidate("bord-p", ("a", "b"), (), "claimed", 1, 1, 1),
            BorderCandidate("bord-q", ("b", "c"), (), "claimed", 1, 1, 1),
        ),
        (
            BorderCandidate("bord-x", ("a", "b"), (), "claimed", 1, 2, 2),
            BorderCandidate("bord-y", ("b", "c"), (), "claimed", 1, 2, 2),
        ),
    )
    assert {"split", "merge"} <= {edge.kind for edge in split_merge}


def test_org_and_msoc_joins_are_read_only() -> None:
    candidates = (BorderCandidate("bord-a", ("a",), (), "claimed", 1, 1, 1),)
    org = SimpleNamespace(organization_id="org-1", border_domain_tokens=("a",))
    macro = SimpleNamespace(society_id="msoc-1", border_domain_tokens=("a",))
    joins = join_border_identities(candidates, (org,), (macro,))
    assert joins == (("bord-a", "msoc", "msoc-1"), ("bord-a", "org", "org-1"))
    assert org.organization_id == "org-1"
    assert macro.society_id == "msoc-1"


def test_alignment_matrix() -> None:
    claims = (
        _claim("owner-1", "domain-1", ("a",)),
        _claim("owner-2", "domain-2", ("a",)),
    )
    patterns = (
        BorderPatternRow("bpat-1", "domain-1", ("a",), "claim_aligned", 2, 1, 0, 0),
    )
    rows = align_border_interpretations(
        claims,
        (),
        patterns,
        disputes=(BorderDisputeRow("bdd-1", "domain-1", "bcp-1", ("a",), "active"),),
    )
    by_candidate = {row.candidate_id: row for row in rows}
    assert len(by_candidate) == 1
    row = next(iter(by_candidate.values()))
    assert row.alignment == "inconsistent"
    assert row.claim_alignment == "consistent"
    assert row.agreement_alignment == "unresolved"

    consistent = align_border_interpretations(
        (_claim("owner-1", "domain-1", ("a",)),),
        (_agreement("domain-1"),),
        patterns,
    )
    assert consistent[0].alignment == "consistent"


def test_missing_layer_is_unresolved_not_inconsistent() -> None:
    rows = align_border_interpretations(
        (_claim("owner-1", "domain-1", ("a",)),),
        (),
        (),
    )
    assert rows[0].alignment == "unresolved"
    assert align_border_interpretations((), (), ()) == ()


def test_summary_has_counts_and_no_truth_field() -> None:
    claims = (_claim("owner-1", "domain-1", ("a",)),)
    rows = align_border_interpretations(claims, (), ())
    summary = summarize_borders(
        claims=claims,
        agreements=(),
        disputes=(),
        physical_row_count=0,
        patterns=(),
        alignment=rows,
        catalog_version="metric-catalog-v1",
    )
    assert summary.candidate_count == 1
    assert summary.claim_count == 1
    names = {item.name for item in dataclasses.fields(summary)}
    assert names.isdisjoint({"truth", "winner", "legitimacy", "score"})
    assert summary.alignment_counts == (("unresolved", 1),)
