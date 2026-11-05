# mypy: ignore-errors
"""V4-11 treaty version lineage and read-only identity joins."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.diplomacy_detection import DiplomaticRelationCandidate
from analysis.diplomacy_identity import (
    assign_diplomacy_identities,
    derive_treaty_version_lineage,
    join_diplomacy_parties,
)
from analysis.diplomacy_rows import (
    DiplomacyTreatyDeclarationRow,
    DiplomacyTreatyRow,
    DiplomacyTreatyVersionRow,
)

pytestmark = pytest.mark.unit


def _version(
    index: int, *, parents: tuple[str, ...] = (), change: str = "original"
) -> DiplomacyTreatyVersionRow:
    return DiplomacyTreatyVersionRow(
        owner_token="a" * 16,
        version_id=f"dpv-{index:016x}",
        treaty_id="dpg-" + "0" * 16,
        version_index=index,
        parent_version_ids=parents,
        change_kind=change,
        party_tokens=("b" * 16, "c" * 16),
        provision_kinds=("non_hostility",),
        terms_digest="a" * 64,
        record_refs=(),
        institutional_memory_refs=(),
        effective_tick=index,
        end_tick=None,
        proposer_party_token="b" * 16,
        proposer_envoy_token=None,
        provenance="communicated",
    )


def test_lineage_edges_are_content_addressed_and_sorted() -> None:
    first = _version(1)
    second = _version(2, parents=(first.version_id,), change="renewal")
    third = _version(3, parents=(second.version_id,), change="amendment")
    edges = derive_treaty_version_lineage((first, second, third))
    assert [edge.from_version_id for edge in edges] == [
        first.version_id,
        second.version_id,
    ]
    assert [edge.to_version_id for edge in edges] == [
        second.version_id,
        third.version_id,
    ]
    assert all(edge.edge_id.startswith("dip-edge-") for edge in edges)
    assert edges == derive_treaty_version_lineage((first, second, third))


def test_join_is_read_only_and_never_invents_identity() -> None:
    rows = join_diplomacy_parties(
        (),
        organization_rows=(),
        macro_society_analysis=None,
    )
    assert rows == ()


def test_analysis_modules_never_call_identity_mutation_helpers() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "analysis"
    forbidden = {"mint", "rename", "split", "merge", "dissolve"}
    for path in root.glob("diplomacy_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in forbidden
        }
        assert not called, (path.name, called)


def test_analysis_carries_treaty_counts_and_accepted_versions() -> None:
    owner = "a" * 16
    party = "b" * 16
    candidate = DiplomaticRelationCandidate(
        candidate_key="candidate-key",
        owner_token=owner,
        party_tokens=(owner, party),
        lanes=(),
        status="observed",
    )
    treaty = DiplomacyTreatyRow(
        owner_token=owner,
        treaty_id="dpg-" + "0" * 16,
        relation_id="dpl-" + "0" * 16,
        party_tokens=(owner, party),
        subject_token="ceasefire",
        current_version_id="dpv-" + "0" * 16,
        opened_tick=1,
        last_tick=2,
        provenance="communicated",
    )
    version = DiplomacyTreatyVersionRow(
        owner_token=owner,
        version_id="dpv-" + "0" * 16,
        treaty_id=treaty.treaty_id,
        version_index=1,
        parent_version_ids=(),
        change_kind="original",
        party_tokens=(owner, party),
        provision_kinds=("non_hostility",),
        terms_digest="a" * 64,
        record_refs=(),
        institutional_memory_refs=(),
        effective_tick=1,
        end_tick=None,
        proposer_party_token=owner,
        proposer_envoy_token=None,
        provenance="communicated",
    )
    declarations = (
        DiplomacyTreatyDeclarationRow(
            owner_token=owner,
            treaty_id=treaty.treaty_id,
            version_id=version.version_id,
            party_token=owner,
            envoy_token=None,
            act="accept",
            declared_tick=2,
            provenance="self_declared",
        ),
        DiplomacyTreatyDeclarationRow(
            owner_token=owner,
            treaty_id=treaty.treaty_id,
            version_id=version.version_id,
            party_token=party,
            envoy_token=None,
            act="accept",
            declared_tick=2,
            provenance="communicated",
        ),
    )
    analysis = assign_diplomacy_identities(
        (candidate,),
        treaty_rows=(treaty,),
        treaty_versions=(version,),
        treaty_declarations=declarations,
        treaty_lineage=derive_treaty_version_lineage((version,)),
    )
    assert analysis[0].treaty_count == 1
    assert analysis[0].version_count == 1
    assert analysis[0].accepted_version_count == 1
