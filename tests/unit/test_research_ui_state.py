"""Research UI deep-link and epistemic chrome contracts."""

from __future__ import annotations

import logging

import pytest

from observer.research_ui_state import (
    EPISTEMIC_AGENT_BELIEF,
    EPISTEMIC_AGENT_MEMORY,
    EPISTEMIC_AGENT_OBSERVATION,
    EPISTEMIC_OBJECTIVE_WORLD,
    EPISTEMIC_RESEARCH_INFERENCE,
    ResearchUiDeepLinkState,
    ResearchUiStateError,
    build_research_ui_query,
    epistemic_from_debugger_artifact,
    epistemic_from_evidence_class,
    epistemic_from_overlay_kind,
    parse_research_ui_query,
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
    assert epistemic_from_overlay_kind("spatial_control") == EPISTEMIC_RESEARCH_INFERENCE
    assert (
        epistemic_from_evidence_class("ANALYTICAL_INFERRED")
        == EPISTEMIC_RESEARCH_INFERENCE
    )


def test_debugger_artifact_mapping() -> None:
    assert epistemic_from_debugger_artifact("observation") == EPISTEMIC_AGENT_OBSERVATION
    assert epistemic_from_debugger_artifact("memory") == EPISTEMIC_AGENT_MEMORY
    assert epistemic_from_debugger_artifact("belief") == EPISTEMIC_AGENT_BELIEF
    assert epistemic_from_debugger_artifact("objective_event") == EPISTEMIC_OBJECTIVE_WORLD


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
