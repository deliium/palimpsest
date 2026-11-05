# mypy: ignore-errors
"""V4-11 detached treaty layers keep three authorities separate."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from analysis.diplomacy_contract import DiplomacyAnalysisError, DiplomacyCoverage
from analysis.diplomacy_layers import (
    DiplomacyLayerView,
    assert_diplomacy_layer_separation,
    project_diplomacy_layers,
)
from analysis.diplomacy_rows import DiplomacyHarvestRows

pytestmark = pytest.mark.unit

OWNER = "a" * 16


def _rows() -> DiplomacyHarvestRows:
    from analysis.diplomacy_rows import (
        DiplomacyTreatyDeclarationRow,
        DiplomacyTreatyRow,
        DiplomacyTreatyVersionRow,
    )

    return DiplomacyHarvestRows(
        treaties=(
            DiplomacyTreatyRow(
                owner_token=OWNER,
                treaty_id="dpg-" + "0" * 16,
                relation_id="dpl-" + "0" * 16,
                party_tokens=("b" * 16, "c" * 16),
                subject_token="ceasefire",
                current_version_id="dpv-" + "0" * 16,
                opened_tick=1,
                last_tick=2,
                provenance="communicated",
            ),
        ),
        treaty_versions=(
            DiplomacyTreatyVersionRow(
                owner_token=OWNER,
                version_id="dpv-" + "0" * 16,
                treaty_id="dpg-" + "0" * 16,
                version_index=1,
                parent_version_ids=(),
                change_kind="original",
                party_tokens=("b" * 16, "c" * 16),
                provision_kinds=("non_hostility",),
                terms_digest="a" * 64,
                record_refs=(),
                institutional_memory_refs=(),
                effective_tick=1,
                end_tick=None,
                proposer_party_token="b" * 16,
                proposer_envoy_token=None,
                provenance="communicated",
            ),
        ),
        treaty_declarations=(
            DiplomacyTreatyDeclarationRow(
                owner_token=OWNER,
                treaty_id="dpg-" + "0" * 16,
                version_id="dpv-" + "0" * 16,
                party_token="b" * 16,
                envoy_token=None,
                act="accept",
                declared_tick=2,
                provenance="communicated",
            ),
            DiplomacyTreatyDeclarationRow(
                owner_token=OWNER,
                treaty_id="dpg-" + "0" * 16,
                version_id="dpv-" + "0" * 16,
                party_token="c" * 16,
                envoy_token=None,
                act="accept",
                declared_tick=2,
                provenance="communicated",
            ),
        ),
        coverage=DiplomacyCoverage.COMPLETE,
    )


def test_treaty_subject_counts_appear_only_in_subjective_rows() -> None:
    layers = project_diplomacy_layers(_rows(), (), ())
    assert layers.subjective[0].treaty_subject_counts == (("ceasefire", 1),)
    assert layers.subjective[0].treaty_status_counts == (("apparently_accepted", 1),)
    assert all(not hasattr(row, "treaty_subject_counts") for row in layers.objective)


@dataclass(frozen=True)
class _Leak:
    owner_token: str


@dataclass(frozen=True)
class _Forbidden:
    candidate_id: str
    party_tokens: tuple[str, ...]
    score: int


def test_cross_layer_leaks_are_rejected() -> None:
    leak = _Leak(owner_token=OWNER)
    with pytest.raises(DiplomacyAnalysisError, match="diplomacy_layer_leak"):
        assert_diplomacy_layer_separation(
            DiplomacyLayerView(
                objective=(leak,), subjective=(), analytical=(), coverage="partial"
            )
        )
    forbid = _Forbidden(candidate_id="dip-" + "0" * 16, party_tokens=(), score=1)
    with pytest.raises(DiplomacyAnalysisError, match="diplomacy_layer_leak"):
        assert_diplomacy_layer_separation(
            DiplomacyLayerView(
                objective=(), subjective=(), analytical=(forbid,), coverage="partial"
            )
        )
