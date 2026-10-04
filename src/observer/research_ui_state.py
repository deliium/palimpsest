"""Credential-free Research UI deep-link and epistemic chrome contracts.

Closed UI classes extend Godot's three wire EvidenceClass values for
researcher presentation only — they do not rename ``observer-protocol-v1``.

Canonical query params: ``run_id``, ``tick``, ``event_id`` / ``sequence``,
``agent_id``, ``view``. Never accept credential-like keys in the query string
(same policy as ``api.security`` / ``debugger_state``).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final
from urllib.parse import parse_qsl, urlencode

from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("observer.research_ui_state")

# Keep in sync with api.security._QUERY_SECRET_KEYS and debugger_state._SECRET_KEYS.
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

RESEARCH_UI_VIEWS: Final[frozenset[str]] = frozenset(
    {
        "overview",
        "graphs",
        "agent",
        "analytics",
        "traces",
        "compare",
        "matrix",
    }
)
_RUN_SCOPED_VIEWS: Final[frozenset[str]] = frozenset(
    {
        "overview",
        "graphs",
        "agent",
        "analytics",
        "traces",
        "compare",
    }
)
DEFAULT_RESEARCH_UI_VIEW: Final[str] = "overview"

# Closed Research UI epistemic classes (presentation-only).
EPISTEMIC_OBJECTIVE_WORLD: Final[str] = "objective_world"
EPISTEMIC_AGENT_OBSERVATION: Final[str] = "agent_observation"
EPISTEMIC_AGENT_MEMORY: Final[str] = "agent_memory"
EPISTEMIC_AGENT_BELIEF: Final[str] = "agent_belief"
EPISTEMIC_AGENT_IMAGINATION: Final[str] = "agent_imagination"
EPISTEMIC_COUNTERFACTUAL: Final[str] = "counterfactual"
EPISTEMIC_RESEARCH_INFERENCE: Final[str] = "research_inference"

EPISTEMIC_CLASSES: Final[frozenset[str]] = frozenset(
    {
        EPISTEMIC_OBJECTIVE_WORLD,
        EPISTEMIC_AGENT_OBSERVATION,
        EPISTEMIC_AGENT_MEMORY,
        EPISTEMIC_AGENT_BELIEF,
        EPISTEMIC_AGENT_IMAGINATION,
        EPISTEMIC_COUNTERFACTUAL,
        EPISTEMIC_RESEARCH_INFERENCE,
    }
)

# Godot / wire EvidenceClass values.
EVIDENCE_OBJECTIVE: Final[str] = "OBJECTIVE"
EVIDENCE_SUBJECTIVE: Final[str] = "SUBJECTIVE_TO_SELECTED_AGENT"
EVIDENCE_ANALYTICAL: Final[str] = "ANALYTICAL_INFERRED"

# Closed debugger artifact kinds (inspector chrome).
ARTIFACT_OBJECTIVE_EVENT: Final[str] = "objective_event"
ARTIFACT_OBSERVATION: Final[str] = "observation"
ARTIFACT_MEMORY: Final[str] = "memory"
ARTIFACT_BELIEF: Final[str] = "belief"
ARTIFACT_IMAGINATION: Final[str] = "imagination"
ARTIFACT_COUNTERFACTUAL: Final[str] = "counterfactual"
ARTIFACT_ANALYTICAL: Final[str] = "analytical_inference"

_ANALYTICAL_OVERLAYS: Final[frozenset[str]] = frozenset(
    {
        "spatial_control",
        "emergent_group_formation",
        "emergent_social_norms",
        "persistent_social_conventions",
        "distributed_reputation",
        "cultural_narrative_lineage",
        "communication_strategy",
        "communication_strategy_audit",
        "cultural_transmission",
        "skill_learning",
        "metric",
        "phenomenon_panel",
        "matrix_stats",
    }
)
_SUBJECTIVE_OVERLAYS: Final[frozenset[str]] = frozenset(
    {
        "subjective_labels",
        "relationships",
        "territorial_claims",
        "narrative_hops",
        "group_formation_ledger",
        "social_norms_ledger",
        "social_conventions_ledger",
        "cultural_narratives_ledger",
    }
)

__all__ = [
    "ARTIFACT_ANALYTICAL",
    "ARTIFACT_BELIEF",
    "ARTIFACT_COUNTERFACTUAL",
    "ARTIFACT_IMAGINATION",
    "ARTIFACT_MEMORY",
    "ARTIFACT_OBJECTIVE_EVENT",
    "ARTIFACT_OBSERVATION",
    "DEFAULT_RESEARCH_UI_VIEW",
    "EPISTEMIC_AGENT_BELIEF",
    "EPISTEMIC_AGENT_IMAGINATION",
    "EPISTEMIC_AGENT_MEMORY",
    "EPISTEMIC_AGENT_OBSERVATION",
    "EPISTEMIC_CLASSES",
    "EPISTEMIC_COUNTERFACTUAL",
    "EPISTEMIC_OBJECTIVE_WORLD",
    "EPISTEMIC_RESEARCH_INFERENCE",
    "EVIDENCE_ANALYTICAL",
    "EVIDENCE_OBJECTIVE",
    "EVIDENCE_SUBJECTIVE",
    "RESEARCH_UI_VIEWS",
    "ResearchUiDeepLinkState",
    "ResearchUiStateError",
    "build_research_ui_query",
    "epistemic_from_debugger_artifact",
    "epistemic_from_evidence_class",
    "epistemic_from_overlay_kind",
    "parse_research_ui_query",
]


class ResearchUiStateError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message if message is not None else code)


@dataclass(frozen=True, slots=True)
class ResearchUiDeepLinkState:
    """Stable credential-free Research UI focus / navigation state."""

    run_id: str | None = None
    tick: int | None = None
    event_id: str | None = None
    sequence: int | None = None
    agent_id: str | None = None
    view: str = DEFAULT_RESEARCH_UI_VIEW

    def __post_init__(self) -> None:
        if self.run_id is not None:
            object.__setattr__(
                self,
                "run_id",
                require_stable_id("ResearchUiDeepLinkState.run_id", self.run_id),
            )
        if self.tick is not None and (
            isinstance(self.tick, bool)
            or not isinstance(self.tick, int)
            or self.tick < 0
        ):
            raise ResearchUiStateError("invalid_tick")
        if self.sequence is not None and (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ResearchUiStateError("invalid_sequence")
        if self.event_id is not None:
            object.__setattr__(
                self,
                "event_id",
                require_stable_id("ResearchUiDeepLinkState.event_id", self.event_id),
            )
        if self.agent_id is not None:
            object.__setattr__(
                self,
                "agent_id",
                require_stable_id("ResearchUiDeepLinkState.agent_id", self.agent_id),
            )
        if self.view not in RESEARCH_UI_VIEWS:
            raise ResearchUiStateError("invalid_view")


def epistemic_from_evidence_class(value: str) -> str:
    """Map wire EvidenceClass / short labels → Research UI epistemic class."""
    key = value.strip().upper()
    if key in {"OBJECTIVE", "OBJECTIVE_WORLD"}:
        return EPISTEMIC_OBJECTIVE_WORLD
    if key in {
        "SUBJECTIVE_TO_SELECTED_AGENT",
        "SUBJECTIVE",
        "AGENT_BELIEF",
    }:
        return EPISTEMIC_AGENT_BELIEF
    if key in {"ANALYTICAL_INFERRED", "ANALYTICAL", "RESEARCH_INFERENCE"}:
        return EPISTEMIC_RESEARCH_INFERENCE
    return EPISTEMIC_RESEARCH_INFERENCE


def epistemic_from_debugger_artifact(kind: str) -> str:
    """Map closed debugger artifact kinds → Research UI epistemic class."""
    key = kind.strip().lower()
    mapping = {
        ARTIFACT_OBJECTIVE_EVENT: EPISTEMIC_OBJECTIVE_WORLD,
        "action": EPISTEMIC_OBJECTIVE_WORLD,
        ARTIFACT_OBSERVATION: EPISTEMIC_AGENT_OBSERVATION,
        ARTIFACT_MEMORY: EPISTEMIC_AGENT_MEMORY,
        ARTIFACT_BELIEF: EPISTEMIC_AGENT_BELIEF,
        ARTIFACT_IMAGINATION: EPISTEMIC_AGENT_IMAGINATION,
        ARTIFACT_COUNTERFACTUAL: EPISTEMIC_COUNTERFACTUAL,
        ARTIFACT_ANALYTICAL: EPISTEMIC_RESEARCH_INFERENCE,
    }
    return mapping.get(key, EPISTEMIC_RESEARCH_INFERENCE)


def epistemic_from_overlay_kind(kind: str) -> str:
    """Map observer overlay / metric kinds → Research UI epistemic class."""
    key = kind.strip().lower()
    if key == "communication_flows":
        return EPISTEMIC_OBJECTIVE_WORLD
    if key in _SUBJECTIVE_OVERLAYS:
        return EPISTEMIC_AGENT_BELIEF
    if key in _ANALYTICAL_OVERLAYS:
        return EPISTEMIC_RESEARCH_INFERENCE
    return EPISTEMIC_RESEARCH_INFERENCE


def parse_research_ui_query(
    query: str | Mapping[str, str],
) -> ResearchUiDeepLinkState:
    """Parse URL query or mapping into Research UI deep-link state.

    Rejects credential-like keys. Requires ``run_id`` for run-scoped views.
    Unknown ``view`` values WARN and default to ``overview``.
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
            "research_ui_state_rejected reason_code=%s",
            "query_string_secret",
        )
        raise ResearchUiStateError("query_string_secret")

    run_id_raw = raw.get("run_id", "").strip()
    run_id: str | None = run_id_raw or None

    tick = _optional_nonneg_int(raw.get("tick"), field="tick")
    sequence = _optional_nonneg_int(raw.get("sequence"), field="sequence")
    event_id = raw.get("event_id") or raw.get("event")
    if event_id is not None:
        event_id = event_id.strip() or None
    agent_id = raw.get("agent_id") or raw.get("agent")
    if agent_id is not None:
        agent_id = agent_id.strip() or None

    view_raw = (raw.get("view") or "").strip().lower()
    view = DEFAULT_RESEARCH_UI_VIEW
    if view_raw:
        if view_raw in RESEARCH_UI_VIEWS:
            view = view_raw
        else:
            _LOG.warning(
                "research_ui_state_rejected reason_code=%s",
                "unknown_view",
            )
            view = DEFAULT_RESEARCH_UI_VIEW

    if view in _RUN_SCOPED_VIEWS and run_id is None:
        _LOG.warning("research_ui_state_rejected reason_code=%s", "run_id_missing")
        raise ResearchUiStateError("run_id_missing")

    if tick is None and sequence is not None:
        _LOG.warning(
            "research_ui_state_rejected reason_code=%s",
            "incomplete_event_cursor",
        )
        raise ResearchUiStateError("incomplete_event_cursor")

    state = ResearchUiDeepLinkState(
        run_id=run_id,
        tick=tick,
        event_id=event_id,
        sequence=sequence,
        agent_id=agent_id,
        view=view,
    )
    _LOG.debug(
        "research_ui_state_parsed run_id=%s tick=%s sequence=%s event_id=%s "
        "agent_id=%s view=%s",
        state.run_id,
        state.tick,
        state.sequence,
        state.event_id,
        state.agent_id,
        state.view,
    )
    return state


def build_research_ui_query(state: ResearchUiDeepLinkState) -> str:
    """Build a credential-free query string (leading ``?`` when non-empty)."""
    pairs: list[tuple[str, str]] = []
    if state.run_id:
        pairs.append(("run_id", state.run_id))
    if state.tick is not None:
        pairs.append(("tick", str(state.tick)))
    if state.event_id:
        pairs.append(("event_id", state.event_id))
    if state.sequence is not None:
        pairs.append(("sequence", str(state.sequence)))
    if state.agent_id:
        pairs.append(("agent_id", state.agent_id))
    if state.view != DEFAULT_RESEARCH_UI_VIEW:
        pairs.append(("view", state.view))
    if not pairs:
        return ""
    return "?" + urlencode(pairs)


def _optional_nonneg_int(raw: str | None, *, field: str) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ResearchUiStateError(f"invalid_{field}") from exc
    if value < 0:
        raise ResearchUiStateError(f"invalid_{field}")
    return value
