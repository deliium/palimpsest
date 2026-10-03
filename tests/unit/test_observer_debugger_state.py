"""Unit tests for debugger deep-link state parsing."""

from __future__ import annotations

import pytest

from observer.debugger_state import (
    DebuggerDeepLinkState,
    DebuggerStateError,
    parse_debugger_query,
)


def test_parse_full_debugger_query() -> None:
    state = parse_debugger_query(
        "?run_id=run-1&tick=1832&sequence=17&event_id=evt-1&agent_id=alice&debugger=causal"
    )
    assert state == DebuggerDeepLinkState(
        run_id="run-1",
        tick=1832,
        sequence=17,
        event_id="evt-1",
        agent_id="alice",
        open_debugger=True,
    )


def test_reject_query_string_secrets() -> None:
    with pytest.raises(DebuggerStateError) as exc:
        parse_debugger_query("?run_id=run-1&token=secret")
    assert exc.value.code == "query_string_secret"


def test_incomplete_cursor_rejected() -> None:
    with pytest.raises(DebuggerStateError) as exc:
        parse_debugger_query("?run_id=run-1&sequence=3")
    assert exc.value.code == "incomplete_event_cursor"


def test_run_id_required() -> None:
    with pytest.raises(DebuggerStateError) as exc:
        parse_debugger_query("?tick=1")
    assert exc.value.code == "run_id_missing"
