"""Research UI deep-link and epistemic chrome contracts."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from observer.research_ui_state import (
    EPISTEMIC_AGENT_BELIEF,
    EPISTEMIC_AGENT_MEMORY,
    EPISTEMIC_AGENT_OBSERVATION,
    EPISTEMIC_OBJECTIVE_WORLD,
    EPISTEMIC_RESEARCH_INFERENCE,
    CohortSelection,
    ResearchSelection,
    ResearchUiDeepLinkState,
    ResearchUiStateError,
    build_research_selection_query,
    build_research_ui_query,
    epistemic_from_debugger_artifact,
    epistemic_from_evidence_class,
    epistemic_from_overlay_kind,
    parse_research_selection,
    parse_research_ui_query,
    resolve_cohort_candidate,
)
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageFamily,
    LineageNativeKind,
    require_lineage_owner_for_kind,
    require_supported_scope_owner,
)

pytestmark = pytest.mark.unit


def test_rejects_token_query_keys(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ResearchUiStateError) as exc:
            parse_research_ui_query("run_id=run-1&token=secret")
    assert exc.value.code == "query_string_secret"
    assert "research_ui_state_rejected" in caplog.text
    assert "query_string_secret" in caplog.text
    assert "token=secret" not in caplog.text
    assert "run-1&token" not in caplog.text


def test_requires_run_id_for_run_scoped_views() -> None:
    with pytest.raises(ResearchUiStateError) as exc:
        parse_research_ui_query("view=graphs")
    assert exc.value.code == "run_id_missing"


def test_matrix_view_may_omit_run_id() -> None:
    state = parse_research_ui_query("view=matrix")
    assert state.view == "matrix"
    assert state.run_id is None


def test_unknown_view_defaults_to_overview(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        state = parse_research_ui_query("run_id=run-1&view=nope")
    assert state.view == "overview"
    assert "unknown_view" in caplog.text


def test_analytical_overlays_map_to_research_inference() -> None:
    assert (
        epistemic_from_overlay_kind("emergent_group_formation")
        == EPISTEMIC_RESEARCH_INFERENCE
    )
    assert (
        epistemic_from_overlay_kind("spatial_control") == EPISTEMIC_RESEARCH_INFERENCE
    )
    assert (
        epistemic_from_evidence_class("ANALYTICAL_INFERRED")
        == EPISTEMIC_RESEARCH_INFERENCE
    )


def test_debugger_artifact_mapping() -> None:
    assert (
        epistemic_from_debugger_artifact("observation") == EPISTEMIC_AGENT_OBSERVATION
    )
    assert epistemic_from_debugger_artifact("memory") == EPISTEMIC_AGENT_MEMORY
    assert epistemic_from_debugger_artifact("belief") == EPISTEMIC_AGENT_BELIEF
    assert (
        epistemic_from_debugger_artifact("objective_event") == EPISTEMIC_OBJECTIVE_WORLD
    )


def test_build_query_omits_secrets_and_default_view() -> None:
    state = ResearchUiDeepLinkState(
        run_id="run-1",
        tick=10,
        event_id="evt-1",
        agent_id="alice",
        view="overview",
    )
    query = build_research_ui_query(state)
    assert query.startswith("?")
    assert "run_id=run-1" in query
    assert "view=" not in query
    assert "token" not in query


def test_society_overlays_are_analytical_only() -> None:
    for family in ("society_emergence", "society_divergence", "society_isolation"):
        assert epistemic_from_overlay_kind(family) == EPISTEMIC_RESEARCH_INFERENCE


def test_societies_is_a_run_scoped_view() -> None:
    state = parse_research_ui_query("run_id=run-1&view=societies")
    assert state.view == "societies"


def test_institution_overlays_are_analytical_only() -> None:
    for family in ("institution_emergence", "institutional_persistence"):
        assert epistemic_from_overlay_kind(family) == EPISTEMIC_RESEARCH_INFERENCE


def test_institutions_is_a_run_scoped_view() -> None:
    state = parse_research_ui_query("run_id=run-1&view=institutions")
    assert state.view == "institutions"


_LINK_CORPUS = (
    Path(__file__).resolve().parents[2]
    / "clients"
    / "research-ui"
    / "fixtures"
    / "research-links.json"
)


def _corpus() -> dict[str, object]:
    return json.loads(_LINK_CORPUS.read_text(encoding="utf-8"))


def _selection_state(selection: ResearchSelection) -> dict[str, object]:
    focus = selection.focus
    focus_state: dict[str, object] | None = None
    if focus is not None:
        focus_state = {
            "kind": focus.kind,
            "source": focus.source,
            "native_id": focus.native_id,
            "family": focus.family,
            "native_kind": focus.native_kind,
            "identity_owner": focus.identity_owner,
            "node_key": focus.node_key,
            "row_id": focus.row_id,
            "publication_id": focus.publication_id,
        }
    return {
        "run_id": selection.run_id,
        "view": selection.view,
        "tick": selection.tick,
        "event_id": selection.event_id,
        "sequence": selection.sequence,
        "generation_index": selection.generation_index,
        "cohort": None
        if selection.cohort is None
        else {
            "cohort_generation_index": selection.cohort.generation_index,
            "cohort_entry_tick": selection.cohort.entry_tick,
            "cohort_id": selection.cohort.cohort_id,
        },
        "owner_id": selection.scope_owner_id,
        "evidence_class": selection.evidence_class,
        "focus": focus_state,
    }


def test_shared_link_corpus_round_trips() -> None:
    for entry in _corpus()["valid"]:
        selection = parse_research_selection(entry["query"])
        assert _selection_state(selection) == entry["state"], entry["name"]
        assert build_research_selection_query(selection) == entry["canonical_query"], (
            entry["name"]
        )
        again = parse_research_selection(entry["canonical_query"])
        assert _selection_state(again) == entry["state"], entry["name"]


def test_shared_link_corpus_rejects_invalid_links() -> None:
    for entry in _corpus()["invalid"]:
        with pytest.raises(ResearchUiStateError) as exc:
            parse_research_selection(entry["query"])
        assert exc.value.code == entry["reason_code"], entry["name"]


def test_lineage_fixtures_match_backend_owner_matrix() -> None:
    for entry in _corpus()["valid"]:
        state = entry["state"]
        focus = state["focus"]
        if focus is None or focus["source"] != "lineage":
            continue
        family = LineageFamily(focus["family"])
        evidence = LineageEvidenceClass(state["evidence_class"])
        require_supported_scope_owner(family, evidence, state["owner_id"])
        owner_required = require_lineage_owner_for_kind(
            evidence, LineageNativeKind(focus["native_kind"])
        )
        assert (focus["identity_owner"] is not None) is owner_required, entry["name"]


def test_legacy_cohort_resolution_never_takes_first_match() -> None:
    first = CohortSelection(generation_index=2, entry_tick=10, cohort_id="cohort-a")
    second = CohortSelection(generation_index=3, entry_tick=50, cohort_id="cohort-a")
    assert resolve_cohort_candidate("cohort-a", (first, second)) == "ambiguous"
    assert resolve_cohort_candidate("missing", (first, second)) is None
    assert resolve_cohort_candidate("cohort-a", (first,)) == first
