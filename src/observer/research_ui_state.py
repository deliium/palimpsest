"""Credential-free Research UI deep-link and epistemic chrome contracts.

Closed UI classes extend the three wire EvidenceClass values for
researcher presentation only — they do not rename ``observer-protocol-v1``.

Canonical query params: ``run_id``, ``tick``, ``event_id`` / ``sequence``,
``agent_id``, ``view``. Never accept credential-like keys in the query string
(same policy as ``api.security`` / ``debugger_state``).
"""

from __future__ import annotations

import logging
import re
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
        "societies",
        "institutions",
        "contact",
        "traces",
        "compare",
        "matrix",
        "population",
        "cohorts",
        "lineage",
        "teaching",
        "technology",
        "culture",
        "language",
        "narratives",
        "migration",
        "economy",
        "projects",
    }
)
_RUN_SCOPED_VIEWS: Final[frozenset[str]] = frozenset(
    {
        "overview",
        "graphs",
        "agent",
        "analytics",
        "societies",
        "institutions",
        "contact",
        "traces",
        "compare",
        "population",
        "cohorts",
        "lineage",
        "teaching",
        "technology",
        "culture",
        "language",
        "narratives",
        "migration",
        "economy",
        "projects",
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

# Observer wire EvidenceClass values.
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
        "society_emergence",
        "society_divergence",
        "society_isolation",
        "institution_emergence",
        "institutional_persistence",
        "society_contact",
        "contact_cultural_change",
        "contact_hybrid_practice",
        "contact_knowledge_transfer",
        "contact_lexical_borrowing",
        "contact_reputation_transfer",
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
    "CohortSelection",
    "ResearchEntityFocus",
    "ResearchSelection",
    "ResearchUiDeepLinkState",
    "ResearchUiStateError",
    "build_research_selection_query",
    "build_research_ui_query",
    "epistemic_from_debugger_artifact",
    "epistemic_from_evidence_class",
    "epistemic_from_overlay_kind",
    "parse_research_selection",
    "parse_research_ui_query",
    "resolve_cohort_candidate",
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


# ---------------------------------------------------------------------------
# Canonical research selection (additive mirror of the TypeScript contract)
# ---------------------------------------------------------------------------

_KNOWN_SELECTION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "run_id",
        "view",
        "tick",
        "event_id",
        "event",
        "sequence",
        "generation_index",
        "cohort_generation_index",
        "cohort_entry_tick",
        "cohort_id",
        "agent_id",
        "agent",
        "location_id",
        "institution_id",
        "narrative_id",
        "technology_id",
        "owner_id",
        "identity_owner",
        "evidence_class",
        "entity_source",
        "native_kind",
        "lineage_family",
        "lineage_node_key",
        "lineage_publication_id",
        "civilization_row_id",
        "civilization_publication_id",
    }
)

_EVIDENCE_CLASSES: Final[frozenset[str]] = frozenset(
    {"objective", "subjective", "analytical"}
)
_ENTITY_SOURCES: Final[frozenset[str]] = frozenset({"lineage", "civilization"})
_OBJECTIVE_FAMILIES: Final[frozenset[str]] = frozenset({"genealogy", "record"})
_SUBJECTIVE_FAMILIES: Final[frozenset[str]] = frozenset(
    {"mentorship", "technology", "knowledge", "narrative", "office_succession"}
)
_ANALYTICAL_FAMILIES: Final[frozenset[str]] = frozenset(
    {"mentorship", "technology", "knowledge", "narrative", "institution"}
)
_ANALYTICAL_SHARED_KINDS: Final[frozenset[str]] = frozenset({"agent", "event"})
_FOCUS_ID_KEYS: Final[tuple[str, ...]] = (
    "agent_id",
    "location_id",
    "institution_id",
    "narrative_id",
    "technology_id",
)
_LINEAGE_QUALIFIER_KEYS: Final[tuple[str, ...]] = (
    "lineage_family",
    "lineage_node_key",
    "lineage_publication_id",
)
_CIVILIZATION_QUALIFIER_KEYS: Final[tuple[str, ...]] = (
    "civilization_row_id",
    "civilization_publication_id",
)
_INSTITUTION_LINEAGE_KINDS: Final[frozenset[str]] = frozenset({"institution_episode"})
_OFFICE_LINEAGE_KINDS: Final[frozenset[str]] = frozenset(
    {"office", "office_claim", "office_transition"}
)
_CIVILIZATION_INSTITUTION_KINDS: Final[frozenset[str]] = frozenset(
    {"concept", "office", "episode"}
)
_NODE_KEY_HEX: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_SELECTION_ORDER: Final[tuple[str, ...]] = (
    "run_id",
    "view",
    "tick",
    "event_id",
    "sequence",
    "generation_index",
    "cohort_generation_index",
    "cohort_entry_tick",
    "cohort_id",
    "agent_id",
    "location_id",
    "institution_id",
    "narrative_id",
    "technology_id",
    "entity_source",
    "native_kind",
    "lineage_family",
    "lineage_node_key",
    "lineage_publication_id",
    "civilization_publication_id",
    "civilization_row_id",
    "owner_id",
    "identity_owner",
    "evidence_class",
)


@dataclass(frozen=True, slots=True)
class CohortSelection:
    """Full cohort identity: generation, entry tick and cohort ID."""

    generation_index: int
    entry_tick: int
    cohort_id: str

    def __post_init__(self) -> None:
        _require_nonneg_int("cohort_generation_index", self.generation_index)
        _require_nonneg_int("cohort_entry_tick", self.entry_tick)
        require_stable_id("CohortSelection.cohort_id", self.cohort_id)


@dataclass(frozen=True, slots=True)
class ResearchEntityFocus:
    """Qualified entity focus for lineage or civilization evidence."""

    kind: str
    source: str
    native_id: str
    evidence_class: str | None = None
    family: str | None = None
    native_kind: str | None = None
    identity_owner: str | None = None
    node_key: str | None = None
    row_id: str | None = None
    publication_id: str | None = None


@dataclass(frozen=True, slots=True)
class ResearchSelection:
    """Canonical credential-free Research UI selection."""

    run_id: str | None = None
    view: str = DEFAULT_RESEARCH_UI_VIEW
    tick: int | None = None
    event_id: str | None = None
    sequence: int | None = None
    generation_index: int | None = None
    cohort: CohortSelection | None = None
    scope_owner_id: str | None = None
    evidence_class: str | None = None
    focus: ResearchEntityFocus | None = None

    def __post_init__(self) -> None:
        if self.run_id is not None:
            require_stable_id("ResearchSelection.run_id", self.run_id)
        if self.view not in RESEARCH_UI_VIEWS:
            raise ResearchUiStateError("invalid_view")
        for name, value in (
            ("tick", self.tick),
            ("sequence", self.sequence),
            ("generation_index", self.generation_index),
        ):
            if value is not None:
                _require_nonneg_int(name, value)
        if self.tick is None and self.sequence is not None:
            raise ResearchUiStateError("incomplete_event_cursor")
        if self.event_id is not None:
            require_stable_id("ResearchSelection.event_id", self.event_id)
        if self.scope_owner_id is not None:
            require_stable_id("ResearchSelection.scope_owner_id", self.scope_owner_id)
        if (
            self.evidence_class is not None
            and self.evidence_class not in _EVIDENCE_CLASSES
        ):
            raise ResearchUiStateError("invalid_evidence_class")


def _require_nonneg_int(field: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResearchUiStateError(f"invalid_{field}")
    return value


def _optional_text(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = raw.strip()
    return text or None


def _stable_or_code(raw: str, field: str) -> str:
    try:
        return require_stable_id(field, raw)
    except ValueError as exc:
        raise ResearchUiStateError(f"invalid_{field}") from exc


def _parse_optional_nonneg(raw: str | None, field: str) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    text = raw.strip()
    if not re.fullmatch(r"0|[1-9][0-9]*", text):
        raise ResearchUiStateError(f"invalid_{field}")
    try:
        value = int(text)
    except ValueError as exc:
        raise ResearchUiStateError(f"invalid_{field}") from exc
    if value > 9007199254740991:
        raise ResearchUiStateError(f"invalid_{field}")
    return value


def _raw_pairs(query: str | Mapping[str, str]) -> list[tuple[str, str]]:
    if isinstance(query, str):
        text = query.strip()
        if text.startswith("?"):
            text = text[1:]
        return parse_qsl(text, keep_blank_values=True)
    return [(str(key), str(value)) for key, value in query.items()]


def _validate_lineage_kind(kind: str, family: str, native_kind: str) -> None:
    if kind == "institution":
        if family == "institution" and native_kind in _INSTITUTION_LINEAGE_KINDS:
            return
        if family == "office_succession" and native_kind in _OFFICE_LINEAGE_KINDS:
            return
        raise ResearchUiStateError("unsupported_family_kind")
    if kind == "narrative":
        if family == "narrative" and native_kind == "narrative_variant":
            return
        raise ResearchUiStateError("unsupported_family_kind")
    if family == "technology" and native_kind == "technique":
        return
    if family == "knowledge" and native_kind == "knowledge_entry":
        return
    raise ResearchUiStateError("unsupported_family_kind")


def _validate_civilization_kind(kind: str, native_kind: str) -> None:
    if kind == "institution":
        if native_kind in _CIVILIZATION_INSTITUTION_KINDS:
            return
        raise ResearchUiStateError("unsupported_family_kind")
    if native_kind != "technology":
        raise ResearchUiStateError("unsupported_family_kind")


def _validate_scope(
    *,
    source: str,
    evidence_class: str | None,
    family: str | None,
    native_kind: str | None,
    owner_id: str | None,
    identity_owner: str | None,
) -> None:
    if source == "civilization":
        if family is not None:
            raise ResearchUiStateError("inconsistent_focus_qualifier")
        if evidence_class is None:
            raise ResearchUiStateError("missing_evidence_class")
        if evidence_class == "objective":
            if owner_id is not None or identity_owner is not None:
                raise ResearchUiStateError("invalid_scope_owner")
            return
        if evidence_class == "subjective":
            if owner_id is None or identity_owner is None or owner_id != identity_owner:
                raise ResearchUiStateError("invalid_scope_owner")
            return
        if owner_id is not None:
            raise ResearchUiStateError("invalid_scope_owner")
        if identity_owner is None:
            raise ResearchUiStateError("missing_identity_owner")
        return

    if evidence_class is None or family is None or native_kind is None:
        raise ResearchUiStateError("missing_lineage_focus_fields")
    if evidence_class == "objective":
        if family not in _OBJECTIVE_FAMILIES:
            raise ResearchUiStateError("invalid_lineage_scope")
        if owner_id is not None or identity_owner is not None:
            raise ResearchUiStateError("invalid_scope_owner")
        return
    if evidence_class == "subjective":
        if family not in _SUBJECTIVE_FAMILIES:
            raise ResearchUiStateError("invalid_lineage_scope")
        if owner_id is None or identity_owner is None or owner_id != identity_owner:
            raise ResearchUiStateError("invalid_scope_owner")
        return
    if family not in _ANALYTICAL_FAMILIES:
        raise ResearchUiStateError("invalid_lineage_scope")
    if owner_id is not None:
        raise ResearchUiStateError("invalid_scope_owner")
    if native_kind in _ANALYTICAL_SHARED_KINDS:
        if identity_owner is not None:
            raise ResearchUiStateError("invalid_scope_owner")
        return
    if identity_owner is None:
        raise ResearchUiStateError("missing_identity_owner")


def parse_research_selection(
    query: str | Mapping[str, str],
) -> ResearchSelection:
    """Parse a URL query into the canonical immutable selection."""
    pairs = _raw_pairs(query)
    raw: dict[str, str] = {}
    counts: dict[str, int] = {}
    for key, value in pairs:
        raw[key] = value
        counts[key] = counts.get(key, 0) + 1

    if frozenset(raw) & _SECRET_KEYS:
        _LOG.warning("research_selection_rejected reason_code=query_string_secret")
        raise ResearchUiStateError("query_string_secret")
    for key in _KNOWN_SELECTION_KEYS:
        if counts.get(key, 0) > 1:
            raise ResearchUiStateError("duplicate_query_key")

    tick = _parse_optional_nonneg(raw.get("tick"), "tick")
    sequence = _parse_optional_nonneg(raw.get("sequence"), "sequence")
    generation_index = _parse_optional_nonneg(
        raw.get("generation_index"), "generation_index"
    )
    cohort_generation = _parse_optional_nonneg(
        raw.get("cohort_generation_index"), "cohort_generation_index"
    )
    cohort_entry = _parse_optional_nonneg(
        raw.get("cohort_entry_tick"), "cohort_entry_tick"
    )
    if tick is None and sequence is not None:
        raise ResearchUiStateError("incomplete_event_cursor")

    canonical_event = _optional_text(raw.get("event_id"))
    alias_event = _optional_text(raw.get("event"))
    canonical_agent = _optional_text(raw.get("agent_id"))
    alias_agent = _optional_text(raw.get("agent"))
    if (
        canonical_event is not None
        and alias_event is not None
        and canonical_event != alias_event
    ):
        raise ResearchUiStateError("conflicting_query_alias")
    if (
        canonical_agent is not None
        and alias_agent is not None
        and canonical_agent != alias_agent
    ):
        raise ResearchUiStateError("conflicting_query_alias")
    event_id = canonical_event if canonical_event is not None else alias_event
    agent_focus_id = canonical_agent if canonical_agent is not None else alias_agent

    cohort_id = _optional_text(raw.get("cohort_id"))
    cohort_present = sum(
        part is not None for part in (cohort_generation, cohort_entry, cohort_id)
    )
    if cohort_present not in (0, 3):
        raise ResearchUiStateError("incomplete_cohort_selection")
    cohort: CohortSelection | None = None
    if cohort_present == 3:
        assert cohort_generation is not None
        assert cohort_entry is not None
        assert cohort_id is not None
        cohort = CohortSelection(
            generation_index=cohort_generation,
            entry_tick=cohort_entry,
            cohort_id=_stable_or_code(cohort_id, "cohort_id"),
        )

    view_raw = (raw.get("view") or "").strip().lower()
    view = DEFAULT_RESEARCH_UI_VIEW
    if view_raw:
        if view_raw in RESEARCH_UI_VIEWS:
            view = view_raw
        else:
            _LOG.warning("research_selection_rejected reason_code=unknown_view")

    run_id_raw = _optional_text(raw.get("run_id"))
    run_id = None if run_id_raw is None else _stable_or_code(run_id_raw, "run_id")
    owner_raw = _optional_text(raw.get("owner_id"))
    owner_id = None if owner_raw is None else _stable_or_code(owner_raw, "owner_id")
    identity_raw = _optional_text(raw.get("identity_owner"))
    identity_owner = (
        None
        if identity_raw is None
        else _stable_or_code(identity_raw, "identity_owner")
    )

    if view in _RUN_SCOPED_VIEWS and run_id is None:
        raise ResearchUiStateError("run_id_missing")

    evidence_raw = (raw.get("evidence_class") or "").strip().lower()
    evidence_class: str | None = None
    if evidence_raw:
        if evidence_raw not in _EVIDENCE_CLASSES:
            raise ResearchUiStateError("invalid_evidence_class")
        evidence_class = evidence_raw

    source_raw = (raw.get("entity_source") or "").strip().lower()
    entity_source: str | None = None
    if source_raw:
        if source_raw not in _ENTITY_SOURCES:
            raise ResearchUiStateError("invalid_entity_source")
        entity_source = source_raw

    family_raw = (raw.get("lineage_family") or "").strip().lower()
    lineage_family: str | None = None
    if family_raw:
        if family_raw not in {
            "genealogy",
            "mentorship",
            "technology",
            "knowledge",
            "record",
            "narrative",
            "institution",
            "office_succession",
        }:
            raise ResearchUiStateError("invalid_lineage_family")
        lineage_family = family_raw
    native_kind = _optional_text(raw.get("native_kind"))
    node_key = _optional_text(raw.get("lineage_node_key"))
    row_id = _optional_text(raw.get("civilization_row_id"))
    lineage_publication = _optional_text(raw.get("lineage_publication_id"))
    civilization_publication = _optional_text(raw.get("civilization_publication_id"))

    if node_key is not None and not _NODE_KEY_HEX.fullmatch(node_key):
        raise ResearchUiStateError("invalid_lineage_node_key")
    if lineage_publication is not None and civilization_publication is not None:
        raise ResearchUiStateError("ambiguous_publication_source")

    focus: ResearchEntityFocus | None = None
    present_focus = [
        (key, focus_value)
        for key in _FOCUS_ID_KEYS
        if (
            focus_value := (
                agent_focus_id if key == "agent_id" else _optional_text(raw.get(key))
            )
        )
        is not None
    ]
    if len(present_focus) > 1:
        raise ResearchUiStateError("ambiguous_entity_focus")

    if not present_focus:
        for key in (
            "entity_source",
            "native_kind",
            "lineage_family",
            "lineage_node_key",
            "lineage_publication_id",
            "civilization_row_id",
            "civilization_publication_id",
            "identity_owner",
        ):
            if _optional_text(raw.get(key)) is not None:
                raise ResearchUiStateError("focus_qualifier_without_focus")
        if evidence_class == "objective" and owner_id is not None:
            raise ResearchUiStateError("invalid_scope_owner")
        if evidence_class == "subjective" and owner_id is None:
            raise ResearchUiStateError("missing_scope_owner")
        if evidence_class == "analytical" and owner_id is not None:
            raise ResearchUiStateError("invalid_scope_owner")
    else:
        focus_key, focus_id = present_focus[0]
        if focus_key == "agent_id":
            lineage_qualified = any(
                value is not None
                for value in (
                    entity_source,
                    lineage_family,
                    native_kind,
                    node_key,
                    lineage_publication,
                )
            )
            if lineage_qualified:
                if (
                    entity_source != "lineage"
                    or lineage_family != "genealogy"
                    or native_kind != "agent"
                    or evidence_class != "objective"
                    or row_id is not None
                    or civilization_publication is not None
                ):
                    raise ResearchUiStateError("inconsistent_focus_qualifier")
                _validate_scope(
                    source="lineage",
                    evidence_class=evidence_class,
                    family=lineage_family,
                    native_kind=native_kind,
                    owner_id=owner_id,
                    identity_owner=identity_owner,
                )
                _stable_or_code(focus_id, "agent_id")
                if lineage_publication is not None:
                    _stable_or_code(lineage_publication, "lineage_publication_id")
                focus = ResearchEntityFocus(
                    kind="agent",
                    source="lineage",
                    native_id=focus_id,
                    evidence_class="objective",
                    family="genealogy",
                    native_kind="agent",
                    node_key=node_key,
                    publication_id=lineage_publication,
                )
                evidence_class = "objective"
            else:
                if (
                    (evidence_class is not None and evidence_class != "objective")
                    or owner_id is not None
                    or identity_owner is not None
                    or row_id is not None
                    or civilization_publication is not None
                ):
                    raise ResearchUiStateError("inconsistent_focus_qualifier")
                focus = ResearchEntityFocus(
                    kind="agent",
                    source="objective",
                    native_id=_stable_or_code(focus_id, "agent_id"),
                    evidence_class="objective",
                )
                evidence_class = "objective"
        elif focus_key == "location_id":
            if (
                (evidence_class is not None and evidence_class != "objective")
                or owner_id is not None
                or identity_owner is not None
                or entity_source is not None
                or lineage_family is not None
                or native_kind is not None
                or node_key is not None
                or row_id is not None
                or lineage_publication is not None
                or civilization_publication is not None
            ):
                raise ResearchUiStateError("inconsistent_focus_qualifier")
            focus = ResearchEntityFocus(
                kind="location",
                source="objective",
                native_id=_stable_or_code(focus_id, "location_id"),
                evidence_class="objective",
            )
            evidence_class = "objective"
        else:
            kind = {
                "institution_id": "institution",
                "narrative_id": "narrative",
                "technology_id": "technology",
            }[focus_key]
            if entity_source == "civilization" and kind == "narrative":
                raise ResearchUiStateError("unsupported_family_kind")
            if entity_source is None:
                raise ResearchUiStateError("missing_entity_source")
            native_id = _stable_or_code(focus_id, focus_key)
            if entity_source == "lineage":
                for key in _CIVILIZATION_QUALIFIER_KEYS:
                    if _optional_text(raw.get(key)) is not None:
                        raise ResearchUiStateError("inconsistent_focus_qualifier")
                if lineage_publication is not None:
                    _stable_or_code(lineage_publication, "lineage_publication_id")
                if native_kind is None:
                    raise ResearchUiStateError("missing_lineage_focus_fields")
                if lineage_family is None or evidence_class is None:
                    raise ResearchUiStateError("missing_lineage_focus_fields")
                _validate_lineage_kind(kind, lineage_family, native_kind)
                _validate_scope(
                    source="lineage",
                    evidence_class=evidence_class,
                    family=lineage_family,
                    native_kind=native_kind,
                    owner_id=owner_id,
                    identity_owner=identity_owner,
                )
                focus = ResearchEntityFocus(
                    kind=kind,
                    source="lineage",
                    native_id=native_id,
                    evidence_class=evidence_class,
                    family=lineage_family,
                    native_kind=native_kind,
                    identity_owner=identity_owner,
                    node_key=node_key,
                    publication_id=lineage_publication,
                )
            else:
                for key in _LINEAGE_QUALIFIER_KEYS:
                    if _optional_text(raw.get(key)) is not None:
                        raise ResearchUiStateError("inconsistent_focus_qualifier")
                if row_id is None or native_kind is None:
                    raise ResearchUiStateError("missing_civilization_focus_fields")
                _validate_civilization_kind(kind, native_kind)
                _validate_scope(
                    source="civilization",
                    evidence_class=evidence_class,
                    family=None,
                    native_kind=native_kind,
                    owner_id=owner_id,
                    identity_owner=identity_owner,
                )
                if civilization_publication is not None:
                    _stable_or_code(
                        civilization_publication, "civilization_publication_id"
                    )
                stable_row = _stable_or_code(row_id, "civilization_row_id")
                focus = ResearchEntityFocus(
                    kind=kind,
                    source="civilization",
                    native_id=native_id,
                    evidence_class=evidence_class,
                    native_kind=native_kind,
                    identity_owner=identity_owner,
                    row_id=stable_row,
                    publication_id=civilization_publication,
                )

    selection = ResearchSelection(
        run_id=run_id,
        view=view,
        tick=tick,
        event_id=event_id,
        sequence=sequence,
        generation_index=generation_index,
        cohort=cohort,
        scope_owner_id=owner_id,
        evidence_class=evidence_class,
        focus=focus,
    )
    _LOG.debug(
        "research_selection_parsed run_id=%s view=%s focus_kind=%s",
        selection.run_id,
        selection.view,
        None if selection.focus is None else selection.focus.kind,
    )
    return selection


def build_research_selection_query(selection: ResearchSelection) -> str:
    """Build a deterministic credential-free query (leading ``?`` when non-empty)."""
    values: dict[str, str] = {}
    if selection.run_id:
        values["run_id"] = selection.run_id
    if selection.view != DEFAULT_RESEARCH_UI_VIEW:
        values["view"] = selection.view
    if selection.tick is not None:
        values["tick"] = str(selection.tick)
    if selection.event_id:
        values["event_id"] = selection.event_id
    if selection.sequence is not None:
        values["sequence"] = str(selection.sequence)
    if selection.generation_index is not None:
        values["generation_index"] = str(selection.generation_index)
    if selection.cohort is not None:
        values["cohort_generation_index"] = str(selection.cohort.generation_index)
        values["cohort_entry_tick"] = str(selection.cohort.entry_tick)
        values["cohort_id"] = selection.cohort.cohort_id

    focus = selection.focus
    if focus is not None:
        if focus.kind == "agent" and focus.source == "objective":
            values["agent_id"] = focus.native_id
        elif focus.kind == "location":
            values["location_id"] = focus.native_id
        else:
            id_key = {
                "agent": "agent_id",
                "institution": "institution_id",
                "narrative": "narrative_id",
                "technology": "technology_id",
            }[focus.kind]
            values[id_key] = focus.native_id
            values["entity_source"] = focus.source
            if focus.native_kind is not None:
                values["native_kind"] = focus.native_kind
            if focus.source == "lineage":
                if focus.family is not None:
                    values["lineage_family"] = focus.family
                if focus.node_key is not None:
                    values["lineage_node_key"] = focus.node_key
                if focus.publication_id is not None:
                    values["lineage_publication_id"] = focus.publication_id
            elif focus.publication_id is not None:
                values["civilization_publication_id"] = focus.publication_id
            if focus.source == "civilization" and focus.row_id is not None:
                values["civilization_row_id"] = focus.row_id

    if selection.scope_owner_id is not None:
        values["owner_id"] = selection.scope_owner_id
    if focus is not None and focus.identity_owner is not None:
        values["identity_owner"] = focus.identity_owner
    if selection.evidence_class is not None:
        values["evidence_class"] = selection.evidence_class

    pairs = [(key, values[key]) for key in _CANONICAL_SELECTION_ORDER if key in values]
    if not pairs:
        return ""
    return "?" + urlencode(pairs)


def resolve_cohort_candidate(
    cohort_id: str, rows: tuple[CohortSelection, ...] | list[CohortSelection]
) -> CohortSelection | str | None:
    """Resolve a legacy ID-only cohort reference against loaded rows."""
    matches = [row for row in rows if row.cohort_id == cohort_id]
    if not matches:
        return None
    if len(matches) > 1:
        return "ambiguous"
    return matches[0]
