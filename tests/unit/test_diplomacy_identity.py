"""V4-10 candidate identity, read-only joins, and lineage."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis.diplomacy_contract import diplomacy_agent_token
from analysis.diplomacy_detection import DiplomaticRelationCandidate
from analysis.diplomacy_identity import (
    assign_diplomacy_identities,
    derive_diplomacy_lineage,
    join_diplomacy_parties,
    party_member_tokens,
)

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"


def _candidate(left: str = "a", right: str = "b") -> DiplomaticRelationCandidate:
    return DiplomaticRelationCandidate(
        candidate_key=f"{left}:{right}",
        owner_token=diplomacy_agent_token(left),
        party_tokens=tuple(
            sorted((diplomacy_agent_token(left), diplomacy_agent_token(right)))
        ),
        lanes=("trade",),
        status="observed",
    )


def test_ids_are_stable_across_windows() -> None:
    candidate = _candidate()
    first = assign_diplomacy_identities(
        (candidate,), creation_ticks={candidate.candidate_key: 1}
    )
    second = assign_diplomacy_identities(
        (candidate,), creation_ticks={candidate.candidate_key: 1}
    )
    assert first == second
    assert first[0].candidate_id.startswith("dip-")
    assert len({row.candidate_id for row in first}) == 1


def test_new_pair_gets_a_distinct_id() -> None:
    first = assign_diplomacy_identities((_candidate(),))
    second = assign_diplomacy_identities((_candidate("a", "c"),))
    assert first[0].candidate_id != second[0].candidate_id


def test_lineage_is_forward_only_and_deterministic() -> None:
    previous = assign_diplomacy_identities((_candidate(),))
    current = assign_diplomacy_identities((_candidate(), _candidate("a", "c")))
    edges = derive_diplomacy_lineage(previous, current, tick=2)
    assert edges
    assert all(edge.edge_id.startswith("dip-edge-") for edge in edges)
    assert {edge.kind for edge in edges} <= {
        "continued",
        "transformed",
        "split",
        "merge",
        "dormant",
        "ended",
    }
    assert edges == derive_diplomacy_lineage(previous, current, tick=2)


def test_join_matches_existing_org_and_msoc_ids_without_minting() -> None:
    candidate = _candidate()
    org_member = SimpleNamespace(token=candidate.party_tokens[1])
    organization = SimpleNamespace(
        candidate_id="org-existing",
        member_tokens=(candidate.party_tokens[0], org_member.token),
    )
    macro = SimpleNamespace(
        candidate_id="msoc-existing",
        member_tokens=(candidate.party_tokens[0],),
    )
    rows = join_diplomacy_parties(
        assign_diplomacy_identities((candidate,)),
        organization_rows=(organization,),
        macro_society_analysis=SimpleNamespace(candidates=(macro,)),
    )
    assert any("org-existing" in row.organization_candidate_ids for row in rows)
    assert any("msoc-existing" in row.macro_society_candidate_ids for row in rows)


def test_unmatched_join_stays_empty() -> None:
    rows = join_diplomacy_parties(assign_diplomacy_identities((_candidate(),)))
    assert all(not row.organization_candidate_ids for row in rows)
    assert all(not row.macro_society_candidate_ids for row in rows)
    assert party_member_tokens(diplomacy_agent_token("a")) == ()


def test_no_identity_minting_imports_in_diplomacy_analysis() -> None:
    offenders = []
    for path in sorted((_SRC / "analysis").glob("diplomacy_*.py")):
        source = path.read_text(encoding="utf-8")
        if "derive_organization_id" in source or "derive_macro_society_id" in source:
            offenders.append(path.name)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in {
                "analysis.organization_contract",
                "analysis.macro_society_contract",
            }:
                offenders.append(path.name)
    assert offenders == []


def test_overlapping_candidates_are_legal() -> None:
    first = _candidate("a", "b")
    second = _candidate("a", "c")
    rows = assign_diplomacy_identities((first, second))
    assert len(rows) == 2
    assert len({row.candidate_id for row in rows}) == 2
