"""V4-10 layer separation, envoy alignment, and analysis summary."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from analysis.diplomacy_alignment import (
    DiplomacyAlignmentStatus,
    classify_diplomacy_envoy_alignment,
    diplomacy_analysis_digest,
    summarize_diplomacy,
)
from analysis.diplomacy_contract import (
    DIPLOMACY_FORBIDDEN_RESULT_FIELDS,
    DiplomacyAnalysisError,
    diplomacy_agent_token,
)
from analysis.diplomacy_detection import DiplomaticRelationCandidate
from analysis.diplomacy_identity import assign_diplomacy_identities
from analysis.diplomacy_layers import (
    DiplomacyAnalyticalRow,
    DiplomacyLayerView,
    assert_diplomacy_layer_separation,
    project_diplomacy_layers,
)
from analysis.diplomacy_rows import (
    DiplomacyDeclarationRow,
    DiplomacyHarvestRows,
    DiplomacyInstrumentRow,
)

pytestmark = pytest.mark.unit

OWNER = diplomacy_agent_token("agent-a")
ENVOY = diplomacy_agent_token("envoy-e")
PARTY = diplomacy_agent_token("agent-b")


def _rows(act: str = "accept") -> DiplomacyHarvestRows:
    return DiplomacyHarvestRows(
        instruments=(
            DiplomacyInstrumentRow(
                owner_token=OWNER,
                relation_id="dpl-1",
                instrument_id="dpi-1",
                party_tokens=(OWNER, PARTY),
                instrument_kind="agreement",
                term_kind="material_exchange",
                subject_token=None,
                opened_tick=1,
                end_tick=None,
                anchor_refs=(),
            ),
        ),
        declarations=(
            DiplomacyDeclarationRow(
                owner_token=OWNER,
                instrument_id="dpi-1",
                party_token=PARTY,
                envoy_token=ENVOY,
                act=act,
                declared_tick=2,
            ),
        ),
    )


def _mandate(status: str = "recognized", **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "owner_token": OWNER,
        "representative_token": ENVOY,
        "status": status,
        "scope_kind": "negotiate",
        "duration_kind": "until_revoked",
        "scope_subject_token": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_valid_projection_is_sorted_and_guarded() -> None:
    candidate = DiplomaticRelationCandidate(
        candidate_key="k",
        owner_token=OWNER,
        party_tokens=tuple(sorted((OWNER, PARTY))),
        lanes=("trade",),
        status="observed",
    )
    analysis = assign_diplomacy_identities((candidate,))
    rows = _rows()
    view = project_diplomacy_layers(rows, (candidate,), analysis)
    assert view.analytical[0].candidate_id == analysis[0].candidate_id
    assert_diplomacy_layer_separation(view)
    assert diplomacy_analysis_digest(
        summarize_diplomacy(rows, (candidate,), view)
    ) == diplomacy_analysis_digest(summarize_diplomacy(rows, (candidate,), view))


@dataclass(frozen=True, slots=True)
class _LeakyObjective:
    owner_token: str


def test_layer_leak_is_rejected() -> None:
    with pytest.raises(DiplomacyAnalysisError) as excinfo:
        assert_diplomacy_layer_separation(
            DiplomacyLayerView(
                objective=(_LeakyObjective(OWNER),),  # type: ignore[arg-type]
                subjective=(),
                analytical=(),
                coverage="partial",
            )
        )
    assert excinfo.value.code == "diplomacy_layer_leak"


def test_analytical_row_carries_no_forbidden_field() -> None:
    row = DiplomacyAnalyticalRow(
        candidate_id="dip-0000000000000000",
        party_tokens=(OWNER, PARTY),
        organization_candidate_ids=(),
        macro_society_candidate_ids=(),
        lanes=("trade",),
        status="observed",
    )
    for name in DIPLOMACY_FORBIDDEN_RESULT_FIELDS:
        assert not hasattr(row, name)


@pytest.mark.parametrize(
    ("acts", "mandate", "expected"),
    (
        ("accept", _mandate(), DiplomacyAlignmentStatus.CONSISTENT),
        ("accept", None, DiplomacyAlignmentStatus.UNRESOLVED),
        (
            "accept",
            _mandate(status="superseded"),
            DiplomacyAlignmentStatus.INCONSISTENT,
        ),
        (
            "accept",
            _mandate(duration_kind="single_act"),
            DiplomacyAlignmentStatus.INCONSISTENT,
        ),
        ("report", _mandate(), DiplomacyAlignmentStatus.NOT_APPLICABLE),
    ),
)
def test_alignment_statuses(
    acts: str, mandate: object, expected: DiplomacyAlignmentStatus
) -> None:
    alignment = classify_diplomacy_envoy_alignment(
        _rows(acts), () if mandate is None else (mandate,)
    )
    assert alignment[0].status == expected.value


def test_summary_has_no_score_and_digest_is_stable() -> None:
    rows = _rows()
    summary = summarize_diplomacy(rows, (), project_diplomacy_layers(rows, (), ()))
    for name in DIPLOMACY_FORBIDDEN_RESULT_FIELDS:
        assert not hasattr(summary, name)
    assert diplomacy_analysis_digest(summary) == diplomacy_analysis_digest(summary)
