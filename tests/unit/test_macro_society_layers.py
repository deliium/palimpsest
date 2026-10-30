"""Layer projection: objective counts, owner claims, analytical candidates."""

from __future__ import annotations

import pytest

from analysis.macro_society_contract import MacroSocietyError, MacroSocietyLane
from analysis.macro_society_detection import detect_macro_society_candidates
from analysis.macro_society_evidence import (
    MacroSocietyEdge,
    MacroSocietyWindowEvidence,
)
from analysis.macro_society_layers import (
    MacroSocietyLayerView,
    MacroSocietyObjectiveRow,
    MacroSocietySubjectiveRow,
    assert_layer_separation,
    project_macro_society_layers,
)

PERSONS = ("person-1", "person-2", "person-3", "person-4", "person-5")


def _window_result():
    edges = tuple(
        MacroSocietyEdge(MacroSocietyLane.INTERACTION, source, target, 0)
        for index, source in enumerate(PERSONS[:4])
        for target in PERSONS[:4][index + 1 :]
    )
    window = MacroSocietyWindowEvidence(
        window_index=2,
        tick_start=20,
        tick_end=29,
        person_ids=PERSONS,
        edges=edges,
    )
    return detect_macro_society_candidates(window)


def test_projection_keeps_objective_counts_without_identity() -> None:
    view = project_macro_society_layers(
        window_result=_window_result(),
        objective_rows=[
            {"region_id": "region-a", "tick": 20, "population_count": 4},
        ],
        subjective_rows=[
            {"owner_id": "person-1", "lane": "culture", "local_token_id": "trait-1"},
            {"owner_id": "person-9", "lane": "culture", "local_token_id": "trait-2"},
        ],
    )
    assert len(view.objective_rows) == 1
    assert view.objective_rows[0].population_count == 4
    assert len(view.subjective_rows) == 1
    assert view.subjective_rows[0].owner_id == "person-1"
    assert view.windows == (2,)
    assert len(view.candidate_ids) == 1


def test_objective_row_carrying_a_candidate_id_is_rejected() -> None:
    with pytest.raises(
        MacroSocietyError, match="macro_society_objective_identity_leak"
    ):
        project_macro_society_layers(
            window_result=_window_result(),
            objective_rows=[
                {
                    "region_id": "region-a",
                    "tick": 20,
                    "population_count": 4,
                    "macro_society_id": "msoc-0123456789abcdef",
                }
            ],
        )


def test_subjective_row_carrying_a_candidate_id_is_rejected() -> None:
    with pytest.raises(
        MacroSocietyError, match="macro_society_subjective_identity_leak"
    ):
        MacroSocietySubjectiveRow(
            owner_id="person-1",
            lane=MacroSocietyLane.CULTURE,
            local_token_id="msoc-0123456789abcdef",
        )


def test_malformed_rows_fail_closed() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_invalid_objective_row"):
        project_macro_society_layers(
            window_result=_window_result(),
            objective_rows=[{"region_id": "region-a"}],
        )
    with pytest.raises(MacroSocietyError, match="macro_society_invalid_subjective_row"):
        project_macro_society_layers(
            window_result=_window_result(),
            subjective_rows=[{"owner_id": "person-1"}],
        )
    with pytest.raises(MacroSocietyError, match="macro_society_unknown_lane"):
        project_macro_society_layers(
            window_result=_window_result(),
            subjective_rows=[
                {"owner_id": "person-1", "lane": "not_a_lane", "local_token_id": "t"}
            ],
        )


def test_layer_separation_passes_for_valid_views() -> None:
    view = MacroSocietyLayerView(
        objective_rows=(MacroSocietyObjectiveRow("region-a", 1, 3),),
        subjective_rows=(
            MacroSocietySubjectiveRow(
                "person-1", MacroSocietyLane.CULTURE, "trait-1"
            ),
        ),
        candidate_ids=("msoc-candidate-0123456789abcdef",),
        windows=(0,),
    )
    assert_layer_separation(view)


def test_layer_separation_rejects_objective_identity_leak() -> None:
    view = MacroSocietyLayerView(
        objective_rows=(
            MacroSocietyObjectiveRow("msoc-candidate-0123456789abcdef", 1, 3),
        ),
        subjective_rows=(),
        candidate_ids=(),
        windows=(0,),
    )
    with pytest.raises(
        MacroSocietyError, match="macro_society_objective_identity_leak"
    ):
        assert_layer_separation(view)


def test_layer_separation_rejects_subjective_candidate_identity() -> None:
    view = MacroSocietyLayerView(
        objective_rows=(),
        subjective_rows=(
            MacroSocietySubjectiveRow(
                "person-1", MacroSocietyLane.CULTURE, "trait-1"
            ),
        ),
        candidate_ids=("msoc-candidate-0123456789abcdef",),
        windows=(0,),
    )
    object.__setattr__(
        view.subjective_rows[0], "local_token_id", "msoc-candidate-0123456789abcdef"
    )
    with pytest.raises(
        MacroSocietyError, match="macro_society_subjective_identity_leak"
    ):
        assert_layer_separation(view)


def test_candidate_ids_must_be_unique() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_duplicate_candidate"):
        MacroSocietyLayerView(
            objective_rows=(),
            subjective_rows=(),
            candidate_ids=("msoc-candidate-0123456789abcdef",) * 2,
            windows=(0,),
        )
