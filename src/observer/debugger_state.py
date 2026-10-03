"""Credential-free debugger deep-link / state parameter contracts.

Canonical query/in-client params: ``run_id``, ``tick``, ``event_id`` /
``sequence``, ``agent_id``, ``debugger``. UI ``event N`` means ``sequence``.
Never accept credential-like keys in the query string.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, Mapping
from urllib.parse import parse_qsl

from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("observer.debugger_state")

_SECRET_KEYS: Final[frozenset[str]] = frozenset(
    {
        "token",
        "credential",
        "credentials",
        "secret",
        "api_key",
        "apikey",
        "authorization",
        "password",
        "access_token",
    }
)

__all__ = [
    "DebuggerDeepLinkState",
    "DebuggerStateError",
    "parse_debugger_query",
]


class DebuggerStateError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message if message is not None else code)


@dataclass(frozen=True, slots=True)
class DebuggerDeepLinkState:
    """Stable credential-free debugger / observer focus state."""

    run_id: str
    tick: int | None = None
    event_id: str | None = None
    sequence: int | None = None
    agent_id: str | None = None
    open_debugger: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("DebuggerDeepLinkState.run_id", self.run_id),
        )
        if self.tick is not None and (
            isinstance(self.tick, bool) or not isinstance(self.tick, int) or self.tick < 0
        ):
            raise DebuggerStateError("invalid_tick")
        if self.sequence is not None and (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise DebuggerStateError("invalid_sequence")
        if self.event_id is not None:
            object.__setattr__(
                self,
                "event_id",
                require_stable_id("DebuggerDeepLinkState.event_id", self.event_id),
            )
        if self.agent_id is not None:
            object.__setattr__(
                self,
                "agent_id",
                require_stable_id("DebuggerDeepLinkState.agent_id", self.agent_id),
            )
        if type(self.open_debugger) is not bool:
            raise TypeError("open_debugger must be bool")


def parse_debugger_query(query: str | Mapping[str, str]) -> DebuggerDeepLinkState:
    """Parse URL query or mapping into debugger state.

    Rejects credential-like keys. Requires ``run_id``. Event focus needs
    ``event_id`` and/or ``(tick, sequence)``.
    """
    if isinstance(query, str):
        text = query.strip()
        if text.startswith("?"):
            text = text[1:]
        pairs = parse_qsl(text, keep_blank_values=True)
        raw: dict[str, str] = {}
        for key, value in pairs:
            raw[key] = value
    else:
        raw = {str(key): str(value) for key, value in query.items()}

    keys = frozenset(raw)
    banned = keys & _SECRET_KEYS
    if banned:
        _LOG.warning(
            "debugger_state_rejected reason_code=%s",
            "query_string_secret",
        )
        raise DebuggerStateError("query_string_secret")

    run_id = raw.get("run_id", "").strip()
    if not run_id:
        _LOG.warning("debugger_state_rejected reason_code=%s", "run_id_missing")
        raise DebuggerStateError("run_id_missing")

    tick = _optional_nonneg_int(raw.get("tick"), field="tick")
    sequence = _optional_nonneg_int(raw.get("sequence"), field="sequence")
    event_id = raw.get("event_id") or raw.get("event")
    if event_id is not None:
        event_id = event_id.strip() or None
    agent_id = raw.get("agent_id") or raw.get("agent")
    if agent_id is not None:
        agent_id = agent_id.strip() or None

    debugger_raw = (raw.get("debugger") or "").strip().lower()
    open_debugger = debugger_raw in {"1", "true", "causal", "yes"}

    if tick is None and sequence is not None:
        _LOG.warning(
            "debugger_state_rejected reason_code=%s",
            "incomplete_event_cursor",
        )
        raise DebuggerStateError("incomplete_event_cursor")

    state = DebuggerDeepLinkState(
        run_id=run_id,
        tick=tick,
        event_id=event_id,
        sequence=sequence,
        agent_id=agent_id,
        open_debugger=open_debugger,
    )
    _LOG.debug(
        "debugger_state_parsed run_id=%s tick=%s sequence=%s event_id=%s "
        "agent_id=%s open_debugger=%s",
        state.run_id,
        state.tick,
        state.sequence,
        state.event_id,
        state.agent_id,
        state.open_debugger,
    )
    return state


def _optional_nonneg_int(raw: str | None, *, field: str) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise DebuggerStateError(f"invalid_{field}") from exc
    if value < 0:
        raise DebuggerStateError(f"invalid_{field}")
    return value
