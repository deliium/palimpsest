"""Research causal debugger: addresses, mapping, resolution, and chain assembly.

Read-only observational surface over stored cognition-trace invocations and
optional structured counterfactual summaries. Must not import ``api``,
``observer``, ``WorldEngine``, or live cognition inputs.

UI label ``event N`` means intra-tick ``sequence``. Prefer opaque ``event_id``
when known. Wire/JSON field name for focus handles is ``observer_focus``;
Python type is ``DebuggerFocusHandle``.

Counterfactual / prediction read sources (locked, no Alembic /
``cognition-trace-v2`` for audit blobs in this plan):

1. Structured id_refs / counts / decision_metadata on the selected invocation
2. Else optional experiment/runner result harvest (closed summary fields only)
3. Else ``status=unavailable`` with an explicit reason code
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from agents.cognition.trace import (
    FORBIDDEN_TRACE_ATTRIBUTES,
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
    reject_forbidden_trace_attributes,
)
from agents.models import AgentId
from simulation.clock import require_exact_nonneg_int
from simulation.cognition_trace import (
    CognitionTraceInvocation,
    CognitionTraceRepository,
)
from simulation.models import RunId
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("simulation.causal_debugger")

__all__ = [
    "FORBIDDEN_DEBUGGER_ATTRIBUTES",
    "RESEARCHER_CHAIN_SEQUENCE",
    "SECONDARY_CHAIN_STAGES",
    "STAGE_KIND_TO_RESEARCHER",
    "CausalDebuggerError",
    "CausalDebuggerService",
    "CausalNodeStatus",
    "CausalTrace",
    "CausalTraceAvailability",
    "CausalTraceNode",
    "CommandKindMapping",
    "CommandKindMappingStatus",
    "CounterfactualHarvestPort",
    "CounterfactualNodeMaterial",
    "CounterfactualSourceKind",
    "DebuggerEventAddress",
    "DebuggerEventLookupPort",
    "DebuggerEventRecord",
    "DebuggerFocusHandle",
    "DebuggerLineageKind",
    "InMemoryDebuggerEventLookup",
    "InvocationResolveResult",
    "ResearcherChainStage",
    "assemble_causal_trace",
    "map_event_to_command_kind",
    "reject_forbidden_debugger_attributes",
    "resolve_invocation_for_event",
    "select_counterfactual_material",
    "semantic_type_for_detail_kind",
]

FORBIDDEN_DEBUGGER_ATTRIBUTES: Final[frozenset[str]] = frozenset(
    {
        *FORBIDDEN_TRACE_ATTRIBUTES,
        "observation_text",
        "memory_text",
        "belief_text",
        "utterance_text",
        "proposition_text",
        "narrative_text",
        "scenario_text",
    }
)

# detail_kind (WorldEvent.details.kind) → observer semantic type (no observer import).
_DETAIL_KIND_TO_SEMANTIC_TYPE: Final[Mapping[str, str]] = {
    "move": "AGENT_MOVED",
    "search": "AGENT_SEARCHED",
    "take": "AGENT_TOOK_ITEM",
    "drop": "AGENT_DROPPED_ITEM",
    "give": "AGENT_GAVE_ITEM",
    "eat": "AGENT_ATE_ITEM",
    "drink": "AGENT_DRANK",
    "sleep": "AGENT_SLEPT",
    "talk": "AGENT_TALKED",
    "ask": "AGENT_ASKED",
    "tell": "AGENT_TOLD",
    "help": "AGENT_HELPED",
    "feed": "AGENT_FED",
    "transport": "AGENT_TRANSPORTED",
    "attack": "AGENT_ATTACKED",
    "flee": "AGENT_FLED",
    "wait": "AGENT_WAITED",
    "weather_changed": "WEATHER_CHANGED",
    "resource_regenerated": "RESOURCE_REGENERATED",
    "needs_applied": "NEEDS_APPLIED",
    "exposure_applied": "EXPOSURE_APPLIED",
    "died": "AGENT_DIED",
    "resource_harvested": "RESOURCE_HARVESTED",
    "craft_started": "CRAFT_STARTED",
    "item_crafted": "ITEM_CRAFTED",
    "structure_built": "STRUCTURE_BUILT",
    "structure_repaired": "STRUCTURE_REPAIRED",
    "item_stored": "ITEM_STORED",
    "season_changed": "SEASON_CHANGED",
    "temperature_band_changed": "TEMPERATURE_BAND_CHANGED",
    "resource_node_depleted": "RESOURCE_NODE_DEPLETED",
    "resource_node_recovered": "RESOURCE_NODE_RECOVERED",
    "environmental_hazard_started": "ENVIRONMENTAL_HAZARD_STARTED",
    "environmental_hazard_ended": "ENVIRONMENTAL_HAZARD_ENDED",
    "artifact_created": "ARTIFACT_CREATED",
    "artifact_modified": "ARTIFACT_MODIFIED",
    "artifact_moved": "ARTIFACT_MOVED",
    "artifact_destroyed": "ARTIFACT_DESTROYED",
    "artifact_copied": "ARTIFACT_COPIED",
    "artifact_annotated": "ARTIFACT_ANNOTATED",
    "artifact_damaged": "ARTIFACT_DAMAGED",
    "artifact_partially_lost": "ARTIFACT_PARTIALLY_LOST",
    "agent_created": "AGENT_CREATED",
    "agent_entered_world": "AGENT_ENTERED_WORLD",
    "agent_initialization_recorded": "AGENT_INITIALIZED",
    "lifecycle_stage_changed": "LIFECYCLE_STAGE_CHANGED",
}

# Semantic observer types / detail type names → cognition-trace command_kind.
# Inverse of observer SEMANTIC_TYPE_BY_KIND for agent-authored actions only.
# Intentionally duplicated here so simulation does not import observer.
_SEMANTIC_TO_COMMAND_KIND: Final[Mapping[str, str]] = {
    "AGENT_MOVED": "move",
    "AGENT_SEARCHED": "search",
    "AGENT_TOOK_ITEM": "take",
    "AGENT_DROPPED_ITEM": "drop",
    "AGENT_GAVE_ITEM": "give",
    "AGENT_ATE_ITEM": "eat",
    "AGENT_DRANK": "drink",
    "AGENT_SLEPT": "sleep",
    "AGENT_TALKED": "talk",
    "AGENT_ASKED": "ask",
    "AGENT_TOLD": "tell",
    "AGENT_HELPED": "help",
    "AGENT_FED": "feed",
    "AGENT_TRANSPORTED": "transport",
    "AGENT_ATTACKED": "attack",
    "AGENT_FLED": "flee",
    "AGENT_WAITED": "wait",
    "RESOURCE_HARVESTED": "harvest",
    "CRAFT_STARTED": "craft",
    "ITEM_CRAFTED": "craft",
    "STRUCTURE_BUILT": "build",
    "STRUCTURE_REPAIRED": "repair",
    "ITEM_STORED": "store",
    "ARTIFACT_CREATED": "inscribe",
    "ARTIFACT_MODIFIED": "amend",
    "ARTIFACT_MOVED": "transfer_artifact",
    "ARTIFACT_DESTROYED": "erase",
    "ARTIFACT_COPIED": "copy_record",
    "ARTIFACT_ANNOTATED": "annotate_record",
    "ARTIFACT_DAMAGED": "damage_record",
    "ARTIFACT_PARTIALLY_LOST": "damage_record",
}

_DETAIL_KIND_TO_COMMAND_KIND: Final[Mapping[str, str]] = {
    "move": "move",
    "search": "search",
    "take": "take",
    "drop": "drop",
    "give": "give",
    "eat": "eat",
    "drink": "drink",
    "sleep": "sleep",
    "talk": "talk",
    "ask": "ask",
    "tell": "tell",
    "help": "help",
    "feed": "feed",
    "transport": "transport",
    "attack": "attack",
    "flee": "flee",
    "wait": "wait",
    "resource_harvested": "harvest",
    "craft_started": "craft",
    "item_crafted": "craft",
    "structure_built": "build",
    "structure_repaired": "repair",
    "item_stored": "store",
    "artifact_created": "inscribe",
    "artifact_modified": "amend",
    "artifact_moved": "transfer_artifact",
    "artifact_destroyed": "erase",
    "artifact_copied": "copy_record",
    "artifact_annotated": "annotate_record",
    "artifact_damaged": "damage_record",
    "artifact_partially_lost": "damage_record",
}

# Detail class __name__ (Attacked, Moved, …) → command_kind when kind field absent.
_DETAIL_TYPE_NAME_TO_COMMAND_KIND: Final[Mapping[str, str]] = {
    "Moved": "move",
    "Searched": "search",
    "Taken": "take",
    "Dropped": "drop",
    "Given": "give",
    "Eaten": "eat",
    "Drunk": "drink",
    "Slept": "sleep",
    "Talked": "talk",
    "Asked": "ask",
    "Told": "tell",
    "Helped": "help",
    "Attacked": "attack",
    "Fled": "flee",
    "Waited": "wait",
    "ResourceHarvested": "harvest",
    "CraftStarted": "craft",
    "ItemCrafted": "craft",
    "StructureBuilt": "build",
    "StructureRepaired": "repair",
    "ItemStored": "store",
    "ArtifactCreated": "inscribe",
    "ArtifactModified": "amend",
    "ArtifactMoved": "transfer_artifact",
    "ArtifactDestroyed": "erase",
    "ArtifactCopied": "copy_record",
    "ArtifactAnnotated": "annotate_record",
    "ArtifactDamaged": "damage_record",
    "ArtifactPartiallyLost": "damage_record",
}

# Consequence / environment semantics: no agent command to explain.
_NOT_APPLICABLE_SEMANTICS: Final[frozenset[str]] = frozenset(
    {
        "WEATHER_CHANGED",
        "RESOURCE_REGENERATED",
        "NEEDS_APPLIED",
        "EXPOSURE_APPLIED",
        "AGENT_DIED",
        "SEASON_CHANGED",
        "TEMPERATURE_BAND_CHANGED",
        "RESOURCE_NODE_DEPLETED",
        "RESOURCE_NODE_RECOVERED",
        "ENVIRONMENTAL_HAZARD_STARTED",
        "ENVIRONMENTAL_HAZARD_ENDED",
        "AGENT_CREATED",
        "AGENT_ENTERED_WORLD",
        "AGENT_INITIALIZED",
        "LIFECYCLE_STAGE_CHANGED",
    }
)

_NOT_APPLICABLE_DETAIL_KINDS: Final[frozenset[str]] = frozenset(
    {
        "weather_changed",
        "resource_regenerated",
        "needs_applied",
        "exposure_applied",
        "died",
        "season_changed",
        "temperature_band_changed",
        "resource_node_depleted",
        "resource_node_recovered",
        "environmental_hazard_started",
        "environmental_hazard_ended",
        "agent_created",
        "agent_entered_world",
        "agent_initialization_recorded",
        "lifecycle_stage_changed",
    }
)

_NOT_APPLICABLE_DETAIL_TYPE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "WeatherChanged",
        "ResourceRegenerated",
        "NeedsApplied",
        "ExposureApplied",
        "Died",
        "SeasonChanged",
        "TemperatureBandChanged",
        "ResourceNodeDepleted",
        "ResourceNodeRecovered",
        "EnvironmentalHazardStarted",
        "EnvironmentalHazardEnded",
        "AgentCreated",
        "AgentEnteredWorld",
        "LifecycleStageChanged",
    }
)

# AGENT_DIED / Died with attacking actor_id: explain via attack invocation.
_SECONDARY_ATTACK_SEMANTICS: Final[frozenset[str]] = frozenset({"AGENT_DIED", "Died"})
_SECONDARY_ATTACK_DETAIL_KINDS: Final[frozenset[str]] = frozenset({"died"})


class CausalDebuggerError(ValueError):
    """Fail-closed validation / address errors for the causal debugger."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message if message is not None else code)


class CausalTraceAvailability(StrEnum):
    """Top-level availability of a causal-trace response."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class CausalNodeStatus(StrEnum):
    """Per-node availability on the researcher chain."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"
    FAILED = "failed"
    TRUNCATED = "truncated"


class DebuggerLineageKind(StrEnum):
    """Closed lineage navigator kinds (drill-down GET resources)."""

    BELIEF_EVIDENCE = "belief_evidence"
    MEMORY_DERIVATION = "memory_derivation"
    COMMUNICATION = "communication"
    NARRATIVE = "narrative"
    GOAL_ANCESTRY = "goal_ancestry"
    PREDICTION = "prediction"


class ResearcherChainStage(StrEnum):
    """Researcher-facing causal chain stage codes (ordered)."""

    OBSERVATION = "observation"
    RELEVANT_MEMORIES = "relevant_memories"
    RECONSTRUCTION = "reconstruction"
    BELIEFS = "beliefs"
    EMOTIONAL_STATE = "emotional_state"
    GOALS = "goals"
    THEORY_OF_MIND = "theory_of_mind"
    IMAGINED_FUTURES = "imagined_futures"
    COUNTERFACTUALS = "counterfactuals"
    SELECTED_INTENTION = "selected_intention"
    ACTION = "action"


class CommandKindMappingStatus(StrEnum):
    """Result of semantic/detail → command_kind mapping."""

    MAPPED = "mapped"
    NOT_APPLICABLE = "not_applicable"
    SECONDARY_ATTACK = "secondary_attack"
    UNMAPPED = "unmapped"


class CounterfactualSourceKind(StrEnum):
    """Locked counterfactual / prediction read-source priority labels."""

    TRACE = "trace"
    RESULT = "result"
    NONE = "none"


RESEARCHER_CHAIN_SEQUENCE: Final[tuple[ResearcherChainStage, ...]] = (
    ResearcherChainStage.OBSERVATION,
    ResearcherChainStage.RELEVANT_MEMORIES,
    ResearcherChainStage.RECONSTRUCTION,
    ResearcherChainStage.BELIEFS,
    ResearcherChainStage.EMOTIONAL_STATE,
    ResearcherChainStage.GOALS,
    ResearcherChainStage.THEORY_OF_MIND,
    ResearcherChainStage.IMAGINED_FUTURES,
    ResearcherChainStage.COUNTERFACTUALS,
    ResearcherChainStage.SELECTED_INTENTION,
    ResearcherChainStage.ACTION,
)

# Supporting nodes; must not replace RESEARCHER_CHAIN_SEQUENCE order.
SECONDARY_CHAIN_STAGES: Final[frozenset[CognitionTraceStageKind]] = frozenset(
    {
        CognitionTraceStageKind.SITUATION_MODEL,
        CognitionTraceStageKind.BUDGET_SUMMARY,
    }
)

STAGE_KIND_TO_RESEARCHER: Final[
    Mapping[CognitionTraceStageKind, ResearcherChainStage]
] = {
    CognitionTraceStageKind.OBSERVATION: ResearcherChainStage.OBSERVATION,
    CognitionTraceStageKind.RETRIEVED_MEMORIES: (
        ResearcherChainStage.RELEVANT_MEMORIES
    ),
    CognitionTraceStageKind.RECONSTRUCTED_MEMORIES: (
        ResearcherChainStage.RECONSTRUCTION
    ),
    CognitionTraceStageKind.BELIEFS: ResearcherChainStage.BELIEFS,
    CognitionTraceStageKind.EMOTIONAL_STATE: ResearcherChainStage.EMOTIONAL_STATE,
    CognitionTraceStageKind.GOALS: ResearcherChainStage.GOALS,
    CognitionTraceStageKind.THEORY_OF_MIND: ResearcherChainStage.THEORY_OF_MIND,
    CognitionTraceStageKind.IMAGINED_FUTURES: (
        ResearcherChainStage.IMAGINED_FUTURES
    ),
    CognitionTraceStageKind.SELECTED_INTENTION: (
        ResearcherChainStage.SELECTED_INTENTION
    ),
    CognitionTraceStageKind.PLANNED_ACTION: ResearcherChainStage.ACTION,
}


def reject_forbidden_debugger_attributes(value: object, *, type_name: str) -> None:
    """Raise if a debugger DTO exposes CoT / payload / credential fields."""
    for forbidden in FORBIDDEN_DEBUGGER_ATTRIBUTES:
        if hasattr(value, forbidden):
            _LOG.error(
                "causal_debugger_forbidden_attribute reason_code=%s type_name=%s "
                "attribute=%s",
                "forbidden_attribute",
                type_name,
                forbidden,
            )
            raise CausalDebuggerError(
                "forbidden_attribute",
                f"{type_name} must not expose {forbidden!r}",
            )
    reject_forbidden_trace_attributes(value, type_name=type_name)


@dataclass(frozen=True, slots=True)
class DebuggerEventAddress:
    """Stable debugger entry address.

    UI phrase ``event N`` maps to ``sequence`` (intra-tick). Prefer opaque
    ``event_id`` when known; ``(tick, sequence)`` remains when available.
    """

    run_id: RunId
    tick: int
    event_id: str | None = None
    sequence: int | None = None
    agent_id: AgentId | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("DebuggerEventAddress.run_id must be RunId")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("DebuggerEventAddress.tick", self.tick),
        )
        if self.event_id is not None:
            object.__setattr__(
                self,
                "event_id",
                require_stable_id("DebuggerEventAddress.event_id", self.event_id),
            )
        if self.sequence is not None:
            object.__setattr__(
                self,
                "sequence",
                require_exact_nonneg_int(
                    "DebuggerEventAddress.sequence", self.sequence
                ),
            )
        if self.agent_id is not None and type(self.agent_id) is not AgentId:
            raise TypeError("DebuggerEventAddress.agent_id must be AgentId or None")
        reject_forbidden_debugger_attributes(
            self, type_name="DebuggerEventAddress"
        )
        _LOG.debug(
            "debugger_address_constructed run_id=%s tick=%s event_id=%s "
            "sequence=%s agent_id=%s",
            self.run_id.value,
            self.tick,
            self.event_id,
            self.sequence,
            None if self.agent_id is None else self.agent_id.value,
        )


@dataclass(frozen=True, slots=True)
class DebuggerFocusHandle:
    """Seek/focus handle for committed occurrences.

    Serialized wire field name is ``observer_focus`` (presentation client / API).
    Python name avoids colliding with the ``observer`` package.
    """

    run_id: RunId
    tick: int
    sequence: int | None = None
    event_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("DebuggerFocusHandle.run_id must be RunId")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("DebuggerFocusHandle.tick", self.tick),
        )
        if self.sequence is not None:
            object.__setattr__(
                self,
                "sequence",
                require_exact_nonneg_int(
                    "DebuggerFocusHandle.sequence", self.sequence
                ),
            )
        if self.event_id is not None:
            object.__setattr__(
                self,
                "event_id",
                require_stable_id("DebuggerFocusHandle.event_id", self.event_id),
            )
        reject_forbidden_debugger_attributes(self, type_name="DebuggerFocusHandle")


@dataclass(frozen=True, slots=True)
class CausalTraceNode:
    """One researcher-chain or supporting node (counts/bands/ids only)."""

    stage_code: str
    status: CausalNodeStatus
    reason_code: str | None = None
    confidence: float | None = None
    uncertainty_band: str | None = None
    selection_codes: tuple[str, ...] = ()
    id_refs: tuple[tuple[str, str], ...] = ()
    counts: Mapping[str, int] | None = None
    command_kind: str | None = None
    intention_code: str | None = None
    focus_handles: tuple[DebuggerFocusHandle, ...] = ()
    secondary: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "stage_code",
            require_stable_id("CausalTraceNode.stage_code", self.stage_code),
        )
        if type(self.status) is not CausalNodeStatus:
            raise TypeError("CausalTraceNode.status must be CausalNodeStatus")
        if self.reason_code is not None:
            object.__setattr__(
                self,
                "reason_code",
                require_stable_id("CausalTraceNode.reason_code", self.reason_code),
            )
        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(
                self.confidence, (int, float)
            ):
                raise TypeError("CausalTraceNode.confidence must be float or None")
            number = float(self.confidence)
            if number < 0.0 or number > 1.0:
                raise ValueError("CausalTraceNode.confidence must be in [0.0, 1.0]")
            object.__setattr__(self, "confidence", number)
        if self.uncertainty_band is not None:
            object.__setattr__(
                self,
                "uncertainty_band",
                require_stable_id(
                    "CausalTraceNode.uncertainty_band", self.uncertainty_band
                ),
            )
        codes = tuple(
            require_stable_id("CausalTraceNode.selection_code", code)
            for code in self.selection_codes
        )
        object.__setattr__(self, "selection_codes", codes)
        refs: list[tuple[str, str]] = []
        for kind, value in self.id_refs:
            refs.append(
                (
                    require_stable_id("CausalTraceNode.id_ref.kind", kind),
                    require_stable_id("CausalTraceNode.id_ref.value", value),
                )
            )
        object.__setattr__(self, "id_refs", tuple(refs))
        if self.counts is not None:
            normalized: dict[str, int] = {}
            for key, raw in self.counts.items():
                safe_key = require_stable_id("CausalTraceNode.counts.key", key)
                normalized[safe_key] = require_exact_nonneg_int(
                    "CausalTraceNode.counts.value", raw
                )
            object.__setattr__(self, "counts", normalized)
        if self.command_kind is not None:
            object.__setattr__(
                self,
                "command_kind",
                require_stable_id("CausalTraceNode.command_kind", self.command_kind),
            )
        if self.intention_code is not None:
            object.__setattr__(
                self,
                "intention_code",
                require_stable_id(
                    "CausalTraceNode.intention_code", self.intention_code
                ),
            )
        if type(self.secondary) is not bool:
            raise TypeError("CausalTraceNode.secondary must be bool")
        for handle in self.focus_handles:
            if type(handle) is not DebuggerFocusHandle:
                raise TypeError(
                    "CausalTraceNode.focus_handles must be DebuggerFocusHandle"
                )
        reject_forbidden_debugger_attributes(self, type_name="CausalTraceNode")


@dataclass(frozen=True, slots=True)
class CausalTrace:
    """Ordered researcher causal chain for one resolved invocation or miss."""

    address: DebuggerEventAddress
    availability: CausalTraceAvailability
    nodes: tuple[CausalTraceNode, ...]
    invocation_id: str | None = None
    ambiguity: bool = False
    reason_code: str | None = None
    command_kind: str | None = None
    supporting_nodes: tuple[CausalTraceNode, ...] = ()

    def __post_init__(self) -> None:
        if type(self.address) is not DebuggerEventAddress:
            raise TypeError("CausalTrace.address must be DebuggerEventAddress")
        if type(self.availability) is not CausalTraceAvailability:
            raise TypeError(
                "CausalTrace.availability must be CausalTraceAvailability"
            )
        if type(self.ambiguity) is not bool:
            raise TypeError("CausalTrace.ambiguity must be bool")
        if self.invocation_id is not None:
            object.__setattr__(
                self,
                "invocation_id",
                require_stable_id("CausalTrace.invocation_id", self.invocation_id),
            )
        if self.reason_code is not None:
            object.__setattr__(
                self,
                "reason_code",
                require_stable_id("CausalTrace.reason_code", self.reason_code),
            )
        if self.command_kind is not None:
            object.__setattr__(
                self,
                "command_kind",
                require_stable_id("CausalTrace.command_kind", self.command_kind),
            )
        for node in self.nodes:
            if type(node) is not CausalTraceNode:
                raise TypeError("CausalTrace.nodes must be CausalTraceNode")
        for node in self.supporting_nodes:
            if type(node) is not CausalTraceNode:
                raise TypeError(
                    "CausalTrace.supporting_nodes must be CausalTraceNode"
                )
        reject_forbidden_debugger_attributes(self, type_name="CausalTrace")
        _LOG.debug(
            "causal_trace_constructed run_id=%s tick=%s event_id=%s "
            "availability=%s invocation_id=%s node_count=%s",
            self.address.run_id.value,
            self.address.tick,
            self.address.event_id,
            self.availability.value,
            self.invocation_id,
            len(self.nodes),
        )


@dataclass(frozen=True, slots=True)
class CommandKindMapping:
    """Closed mapping outcome for one semantic / detail kind."""

    status: CommandKindMappingStatus
    command_kind: str | None
    reason_code: str | None
    input_token: str

    def __post_init__(self) -> None:
        if type(self.status) is not CommandKindMappingStatus:
            raise TypeError(
                "CommandKindMapping.status must be CommandKindMappingStatus"
            )
        if self.command_kind is not None:
            object.__setattr__(
                self,
                "command_kind",
                require_stable_id(
                    "CommandKindMapping.command_kind", self.command_kind
                ),
            )
        if self.reason_code is not None:
            object.__setattr__(
                self,
                "reason_code",
                require_stable_id(
                    "CommandKindMapping.reason_code", self.reason_code
                ),
            )
        object.__setattr__(
            self,
            "input_token",
            require_stable_id("CommandKindMapping.input_token", self.input_token),
        )
        reject_forbidden_debugger_attributes(self, type_name="CommandKindMapping")


def semantic_type_for_detail_kind(detail_kind: str) -> str | None:
    """Map world ``details.kind`` to closed observer semantic type.

    Keeps simulation free of ``observer`` imports.
    """
    token = require_stable_id("detail_kind", detail_kind)
    return _DETAIL_KIND_TO_SEMANTIC_TYPE.get(token)


def map_event_to_command_kind(
    *,
    semantic_type: str | None = None,
    detail_kind: str | None = None,
    detail_type_name: str | None = None,
) -> CommandKindMapping:
    """Map observer semantic type / detail kind / class name → command_kind.

    Secondary-effect rule: ``AGENT_DIED`` / ``died`` / ``Died`` returns
    ``SECONDARY_ATTACK`` (expected ``attack``) when an attacking actor is later
    confirmed by the resolver; without actor the resolver yields
    ``not_applicable``. Environmental / non-agent semantics are
    ``NOT_APPLICABLE``. Unknown tokens warn with ``unmapped_semantic_type``.
    """
    tokens = tuple(
        token
        for token in (semantic_type, detail_kind, detail_type_name)
        if token is not None and token != ""
    )
    if not tokens:
        _LOG.warning(
            "debugger_command_map reason_code=%s",
            "unmapped_semantic_type",
        )
        return CommandKindMapping(
            status=CommandKindMappingStatus.UNMAPPED,
            command_kind=None,
            reason_code="unmapped_semantic_type",
            input_token="empty",
        )

    for token in tokens:
        if (
            token in _SECONDARY_ATTACK_SEMANTICS
            or token in _SECONDARY_ATTACK_DETAIL_KINDS
        ):
            _LOG.debug(
                "debugger_command_map semantic=%s command_kind=%s status=%s",
                token,
                "attack",
                CommandKindMappingStatus.SECONDARY_ATTACK.value,
            )
            return CommandKindMapping(
                status=CommandKindMappingStatus.SECONDARY_ATTACK,
                command_kind="attack",
                reason_code="secondary_consequence_died",
                input_token=token,
            )

    for token in tokens:
        if (
            token in _NOT_APPLICABLE_SEMANTICS
            or token in _NOT_APPLICABLE_DETAIL_KINDS
            or token in _NOT_APPLICABLE_DETAIL_TYPE_NAMES
        ):
            _LOG.debug(
                "debugger_command_map semantic=%s command_kind=%s status=%s",
                token,
                None,
                CommandKindMappingStatus.NOT_APPLICABLE.value,
            )
            return CommandKindMapping(
                status=CommandKindMappingStatus.NOT_APPLICABLE,
                command_kind=None,
                reason_code="causal_trace_not_applicable",
                input_token=token,
            )

    for token in tokens:
        mapped = (
            _SEMANTIC_TO_COMMAND_KIND.get(token)
            or _DETAIL_KIND_TO_COMMAND_KIND.get(token)
            or _DETAIL_TYPE_NAME_TO_COMMAND_KIND.get(token)
        )
        if mapped is not None:
            _LOG.debug(
                "debugger_command_map semantic=%s command_kind=%s status=%s",
                token,
                mapped,
                CommandKindMappingStatus.MAPPED.value,
            )
            return CommandKindMapping(
                status=CommandKindMappingStatus.MAPPED,
                command_kind=mapped,
                reason_code=None,
                input_token=token,
            )

    primary = tokens[0]
    _LOG.warning(
        "debugger_command_map reason_code=%s semantic=%s",
        "unmapped_semantic_type",
        primary,
    )
    return CommandKindMapping(
        status=CommandKindMappingStatus.UNMAPPED,
        command_kind=None,
        reason_code="unmapped_semantic_type",
        input_token=primary,
    )


@dataclass(frozen=True, slots=True)
class CounterfactualNodeMaterial:
    """Closed counterfactual / prediction summary for one chain node."""

    source: CounterfactualSourceKind
    reason_code: str | None
    scenario_count: int | None = None
    skipped_count: int | None = None
    regret_count: int | None = None
    relief_count: int | None = None
    neutral_count: int | None = None
    id_refs: tuple[tuple[str, str], ...] = ()
    selection_codes: tuple[str, ...] = ()
    confidence_band: str | None = None

    def __post_init__(self) -> None:
        if type(self.source) is not CounterfactualSourceKind:
            raise TypeError(
                "CounterfactualNodeMaterial.source must be CounterfactualSourceKind"
            )
        if self.reason_code is not None:
            object.__setattr__(
                self,
                "reason_code",
                require_stable_id(
                    "CounterfactualNodeMaterial.reason_code", self.reason_code
                ),
            )
        for field_name in (
            "scenario_count",
            "skipped_count",
            "regret_count",
            "relief_count",
            "neutral_count",
        ):
            raw = getattr(self, field_name)
            if raw is not None:
                object.__setattr__(
                    self,
                    field_name,
                    require_exact_nonneg_int(
                        f"CounterfactualNodeMaterial.{field_name}", raw
                    ),
                )
        if self.confidence_band is not None:
            object.__setattr__(
                self,
                "confidence_band",
                require_stable_id(
                    "CounterfactualNodeMaterial.confidence_band",
                    self.confidence_band,
                ),
            )
        reject_forbidden_debugger_attributes(
            self, type_name="CounterfactualNodeMaterial"
        )


class CounterfactualHarvestPort(Protocol):
    """Optional runner/experiment result harvest (closed counts only)."""

    async def lookup_counterfactual_summary(
        self,
        *,
        run_id: RunId,
        owner_id: AgentId,
        tick: int,
    ) -> CounterfactualNodeMaterial | None:
        """Return harvested summary for owner/tick, or None if absent."""


@dataclass(frozen=True, slots=True)
class DebuggerEventRecord:
    """Committed event identity fields needed for resolve (no payloads)."""

    event_id: str
    tick: int
    sequence: int
    actor_id: str | None
    detail_kind: str
    semantic_type: str | None = None
    detail_type_name: str | None = None
    agent_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_id",
            require_stable_id("DebuggerEventRecord.event_id", self.event_id),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("DebuggerEventRecord.tick", self.tick),
        )
        object.__setattr__(
            self,
            "sequence",
            require_exact_nonneg_int("DebuggerEventRecord.sequence", self.sequence),
        )
        object.__setattr__(
            self,
            "detail_kind",
            require_stable_id("DebuggerEventRecord.detail_kind", self.detail_kind),
        )
        if self.actor_id is not None:
            object.__setattr__(
                self,
                "actor_id",
                require_stable_id("DebuggerEventRecord.actor_id", self.actor_id),
            )
        if self.semantic_type is not None:
            object.__setattr__(
                self,
                "semantic_type",
                require_stable_id(
                    "DebuggerEventRecord.semantic_type", self.semantic_type
                ),
            )
        if self.detail_type_name is not None:
            object.__setattr__(
                self,
                "detail_type_name",
                require_stable_id(
                    "DebuggerEventRecord.detail_type_name", self.detail_type_name
                ),
            )
        if self.agent_id is not None:
            object.__setattr__(
                self,
                "agent_id",
                require_stable_id("DebuggerEventRecord.agent_id", self.agent_id),
            )
        reject_forbidden_debugger_attributes(self, type_name="DebuggerEventRecord")


class DebuggerEventLookupPort(Protocol):
    """Committed event identity lookup by opaque id or (tick, sequence)."""

    async def get_by_event_id(
        self, *, run_id: RunId, event_id: str
    ) -> DebuggerEventRecord | None:
        """Return identity fields for one opaque event id, or None."""

    async def get_by_tick_sequence(
        self, *, run_id: RunId, tick: int, sequence: int
    ) -> DebuggerEventRecord | None:
        """Return identity fields for one intra-tick cursor, or None."""


class InMemoryDebuggerEventLookup:
    """Test fake for ``DebuggerEventLookupPort`` (no SQL / presentation client)."""

    __slots__ = ("_by_cursor", "_by_id")

    def __init__(self) -> None:
        self._by_id: dict[tuple[str, str], DebuggerEventRecord] = {}
        self._by_cursor: dict[tuple[str, int, int], DebuggerEventRecord] = {}

    def seed(self, *, run_id: RunId, record: DebuggerEventRecord) -> None:
        if type(record) is not DebuggerEventRecord:
            raise TypeError("record must be DebuggerEventRecord")
        self._by_id[(run_id.value, record.event_id)] = record
        self._by_cursor[(run_id.value, record.tick, record.sequence)] = record

    async def get_by_event_id(
        self, *, run_id: RunId, event_id: str
    ) -> DebuggerEventRecord | None:
        _LOG.debug(
            "debugger_event_lookup key=event_id run_id=%s event_id=%s",
            run_id.value,
            event_id,
        )
        found = self._by_id.get((run_id.value, event_id))
        if found is None:
            _LOG.warning(
                "debugger_event_lookup reason_code=%s run_id=%s event_id=%s",
                "event_not_found",
                run_id.value,
                event_id,
            )
        return found

    async def get_by_tick_sequence(
        self, *, run_id: RunId, tick: int, sequence: int
    ) -> DebuggerEventRecord | None:
        _LOG.debug(
            "debugger_event_lookup key=tick_sequence run_id=%s tick=%s sequence=%s",
            run_id.value,
            tick,
            sequence,
        )
        found = self._by_cursor.get((run_id.value, tick, sequence))
        if found is None:
            _LOG.warning(
                "debugger_event_lookup reason_code=%s run_id=%s tick=%s sequence=%s",
                "event_not_found",
                run_id.value,
                tick,
                sequence,
            )
        return found


@dataclass(frozen=True, slots=True)
class InvocationResolveResult:
    """Typed outcome of event → cognition-trace invocation resolution."""

    availability: CausalTraceAvailability
    address: DebuggerEventAddress
    invocation_id: str | None = None
    command_kind: str | None = None
    ambiguity: bool = False
    reason_code: str | None = None
    candidate_count: int = 0
    event_record: DebuggerEventRecord | None = None

    def __post_init__(self) -> None:
        if type(self.availability) is not CausalTraceAvailability:
            raise TypeError(
                "InvocationResolveResult.availability must be "
                "CausalTraceAvailability"
            )
        if type(self.address) is not DebuggerEventAddress:
            raise TypeError(
                "InvocationResolveResult.address must be DebuggerEventAddress"
            )
        if type(self.ambiguity) is not bool:
            raise TypeError("InvocationResolveResult.ambiguity must be bool")
        object.__setattr__(
            self,
            "candidate_count",
            require_exact_nonneg_int(
                "InvocationResolveResult.candidate_count", self.candidate_count
            ),
        )
        if self.invocation_id is not None:
            object.__setattr__(
                self,
                "invocation_id",
                require_stable_id(
                    "InvocationResolveResult.invocation_id", self.invocation_id
                ),
            )
        if self.reason_code is not None:
            object.__setattr__(
                self,
                "reason_code",
                require_stable_id(
                    "InvocationResolveResult.reason_code", self.reason_code
                ),
            )
        if self.command_kind is not None:
            object.__setattr__(
                self,
                "command_kind",
                require_stable_id(
                    "InvocationResolveResult.command_kind", self.command_kind
                ),
            )
        reject_forbidden_debugger_attributes(
            self, type_name="InvocationResolveResult"
        )


def _address_from_record(
    *,
    run_id: RunId,
    record: DebuggerEventRecord,
    agent_id: AgentId | None,
) -> DebuggerEventAddress:
    return DebuggerEventAddress(
        run_id=run_id,
        tick=record.tick,
        event_id=record.event_id,
        sequence=record.sequence,
        agent_id=agent_id,
    )


def _resolve_agent_id(record: DebuggerEventRecord) -> AgentId | None:
    if record.agent_id is not None:
        return AgentId(record.agent_id)
    if record.actor_id is not None:
        return AgentId(record.actor_id)
    return None


async def resolve_invocation_for_event(
    *,
    run_id: RunId,
    traces: CognitionTraceRepository,
    events: DebuggerEventLookupPort,
    event_id: str | None = None,
    tick: int | None = None,
    sequence: int | None = None,
) -> InvocationResolveResult:
    """Resolve committed event → cognition-trace invocation (deterministic).

    Rules: actor required; command_kind match; lexicographic ``invocation_id``
    tie-break with ``ambiguity=true`` + ``multiple_invocations``; tracing-off /
    empty → ``unavailable`` / ``cognition_trace_missing``.
    """
    if event_id is None and (tick is None or sequence is None):
        _LOG.error(
            "debugger_resolve reason_code=%s",
            "incomplete_event_cursor",
        )
        raise CausalDebuggerError(
            "incomplete_event_cursor",
            "event_id or (tick, sequence) required",
        )

    record: DebuggerEventRecord | None
    if event_id is not None:
        record = await events.get_by_event_id(run_id=run_id, event_id=event_id)
    else:
        assert tick is not None and sequence is not None
        record = await events.get_by_tick_sequence(
            run_id=run_id, tick=tick, sequence=sequence
        )

    if record is None:
        # Caller / HTTP layer maps this to 404; keep typed miss here.
        placeholder_tick = 0 if tick is None else tick
        address = DebuggerEventAddress(
            run_id=run_id,
            tick=placeholder_tick,
            event_id=event_id,
            sequence=sequence,
        )
        return InvocationResolveResult(
            availability=CausalTraceAvailability.UNAVAILABLE,
            address=address,
            reason_code="event_not_found",
            candidate_count=0,
        )

    agent_id = _resolve_agent_id(record)
    address = _address_from_record(run_id=run_id, record=record, agent_id=agent_id)
    mapping = map_event_to_command_kind(
        semantic_type=record.semantic_type,
        detail_kind=record.detail_kind,
        detail_type_name=record.detail_type_name,
    )

    if mapping.status is CommandKindMappingStatus.NOT_APPLICABLE:
        _LOG.warning(
            "debugger_resolve reason_code=%s run_id=%s tick=%s event_id=%s",
            "causal_trace_not_applicable",
            run_id.value,
            record.tick,
            record.event_id,
        )
        return InvocationResolveResult(
            availability=CausalTraceAvailability.NOT_APPLICABLE,
            address=address,
            reason_code="causal_trace_not_applicable",
            event_record=record,
        )

    if mapping.status is CommandKindMappingStatus.SECONDARY_ATTACK:
        if agent_id is None:
            _LOG.warning(
                "debugger_resolve reason_code=%s run_id=%s tick=%s event_id=%s",
                "causal_trace_not_applicable",
                run_id.value,
                record.tick,
                record.event_id,
            )
            return InvocationResolveResult(
                availability=CausalTraceAvailability.NOT_APPLICABLE,
                address=address,
                reason_code="causal_trace_not_applicable",
                event_record=record,
            )

    if agent_id is None:
        _LOG.warning(
            "debugger_resolve reason_code=%s run_id=%s tick=%s event_id=%s",
            "causal_trace_not_applicable",
            run_id.value,
            record.tick,
            record.event_id,
        )
        return InvocationResolveResult(
            availability=CausalTraceAvailability.NOT_APPLICABLE,
            address=address,
            reason_code="causal_trace_not_applicable",
            event_record=record,
        )

    if mapping.status is CommandKindMappingStatus.UNMAPPED:
        _LOG.warning(
            "debugger_resolve reason_code=%s run_id=%s tick=%s event_id=%s",
            "unmapped_semantic_type",
            run_id.value,
            record.tick,
            record.event_id,
        )
        return InvocationResolveResult(
            availability=CausalTraceAvailability.NOT_APPLICABLE,
            address=address,
            reason_code="unmapped_semantic_type",
            event_record=record,
        )

    expected_kind = mapping.command_kind
    page = await traces.list_invocations(
        run_id=run_id,
        agent_id=agent_id,
        tick_min=record.tick,
        tick_max=record.tick,
        limit=100,
    )
    candidates = list(page.items)
    _LOG.debug(
        "debugger_resolve candidate_count=%s run_id=%s agent_id=%s tick=%s",
        len(candidates),
        run_id.value,
        agent_id.value,
        record.tick,
    )

    if not candidates:
        _LOG.warning(
            "debugger_resolve reason_code=%s run_id=%s agent_id=%s tick=%s",
            "cognition_trace_missing",
            run_id.value,
            agent_id.value,
            record.tick,
        )
        return InvocationResolveResult(
            availability=CausalTraceAvailability.UNAVAILABLE,
            address=address,
            reason_code="cognition_trace_missing",
            candidate_count=0,
            command_kind=expected_kind,
            event_record=record,
        )

    matched = [
        item
        for item in candidates
        if expected_kind is not None and item.command_kind == expected_kind
    ]
    pool = matched if matched else list(candidates)
    pool.sort(key=lambda item: item.invocation_id)
    selected = pool[0]
    ambiguity = len(pool) > 1
    reason: str | None = "multiple_invocations" if ambiguity else None
    if ambiguity:
        _LOG.warning(
            "debugger_resolve reason_code=%s run_id=%s agent_id=%s tick=%s "
            "candidate_count=%s",
            "multiple_invocations",
            run_id.value,
            agent_id.value,
            record.tick,
            len(pool),
        )
    else:
        _LOG.info(
            "debugger_resolve_ok run_id=%s agent_id=%s tick=%s invocation_id=%s "
            "command_kind=%s candidate_count=%s",
            run_id.value,
            agent_id.value,
            record.tick,
            selected.invocation_id,
            selected.command_kind,
            len(candidates),
        )

    return InvocationResolveResult(
        availability=CausalTraceAvailability.AVAILABLE,
        address=address,
        invocation_id=selected.invocation_id,
        command_kind=selected.command_kind,
        ambiguity=ambiguity,
        reason_code=reason,
        candidate_count=len(candidates),
        event_record=record,
    )


def _stage_status_to_node(status: CognitionTraceStageStatus) -> CausalNodeStatus:
    if status is CognitionTraceStageStatus.COMPLETED:
        return CausalNodeStatus.AVAILABLE
    if status is CognitionTraceStageStatus.UNAVAILABLE:
        return CausalNodeStatus.UNAVAILABLE
    if status is CognitionTraceStageStatus.SKIPPED:
        return CausalNodeStatus.SKIPPED
    if status is CognitionTraceStageStatus.FAILED:
        return CausalNodeStatus.FAILED
    if status is CognitionTraceStageStatus.TRUNCATED:
        return CausalNodeStatus.TRUNCATED
    return CausalNodeStatus.UNAVAILABLE


def _summary_to_node(
    summary: CognitionTraceStageSummary,
    *,
    stage_code: str,
    focus: DebuggerFocusHandle | None,
    secondary: bool = False,
) -> CausalTraceNode:
    band = None
    if summary.uncertainty_band is not None:
        band = summary.uncertainty_band.value
    refs = tuple((ref.kind.value, ref.value) for ref in summary.id_refs)
    handles = () if focus is None else (focus,)
    return CausalTraceNode(
        stage_code=stage_code,
        status=_stage_status_to_node(summary.status),
        reason_code=summary.reason_code,
        confidence=summary.confidence,
        uncertainty_band=band,
        selection_codes=summary.selection_codes,
        id_refs=refs,
        counts=None if summary.counts is None else dict(summary.counts),
        command_kind=summary.command_kind,
        intention_code=summary.intention_code,
        focus_handles=handles,
        secondary=secondary,
    )


def _unavailable_node(
    stage: ResearcherChainStage, *, reason_code: str
) -> CausalTraceNode:
    return CausalTraceNode(
        stage_code=stage.value,
        status=CausalNodeStatus.UNAVAILABLE,
        reason_code=reason_code,
    )


def _extract_counterfactual_from_trace(
    invocation: CognitionTraceInvocation,
) -> CounterfactualNodeMaterial | None:
    """Prefer structured refs already on imagined_futures / intention stages."""
    refs: list[tuple[str, str]] = []
    codes: list[str] = []
    for stage in invocation.stages:
        summary = stage.summary
        if summary.stage_kind not in (
            CognitionTraceStageKind.IMAGINED_FUTURES,
            CognitionTraceStageKind.SELECTED_INTENTION,
            CognitionTraceStageKind.BELIEFS,
        ):
            continue
        for code in summary.selection_codes:
            if "counterfactual" in code or code.startswith("cf_"):
                codes.append(code)
        decision = summary.decision_metadata
        if decision is not None:
            for code in decision.selection_codes:
                if "counterfactual" in code or code.startswith("cf_"):
                    codes.append(code)
        for ref in summary.id_refs:
            # Closed ref kinds only; keep futures when CF selection codes present.
            if codes:
                refs.append((ref.kind.value, ref.value))
    if not codes:
        return None
    return CounterfactualNodeMaterial(
        source=CounterfactualSourceKind.TRACE,
        reason_code=None,
        scenario_count=len(codes),
        id_refs=tuple(dict.fromkeys(refs)),
        selection_codes=tuple(dict.fromkeys(codes)),
    )


def select_counterfactual_material(
    invocation: CognitionTraceInvocation,
    *,
    harvest: CounterfactualNodeMaterial | None = None,
) -> CounterfactualNodeMaterial:
    """Apply locked priority: trace refs → result harvest → unavailable."""
    from_trace = _extract_counterfactual_from_trace(invocation)
    if from_trace is not None:
        _LOG.debug(
            "counterfactual_source_chosen source=%s owner=%s tick=%s "
            "scenario_count=%s ref_count=%s",
            CounterfactualSourceKind.TRACE.value,
            invocation.agent_id.value,
            invocation.tick,
            from_trace.scenario_count,
            len(from_trace.id_refs),
        )
        return from_trace
    if harvest is not None and harvest.source is CounterfactualSourceKind.RESULT:
        if harvest.scenario_count is None and not harvest.id_refs:
            _LOG.warning(
                "counterfactual_harvest_incomplete reason_code=%s owner=%s tick=%s",
                "counterfactual_result_harvest_incomplete",
                invocation.agent_id.value,
                invocation.tick,
            )
            return CounterfactualNodeMaterial(
                source=CounterfactualSourceKind.NONE,
                reason_code="counterfactual_result_harvest_incomplete",
            )
        _LOG.debug(
            "counterfactual_source_chosen source=%s owner=%s tick=%s "
            "scenario_count=%s",
            CounterfactualSourceKind.RESULT.value,
            invocation.agent_id.value,
            invocation.tick,
            harvest.scenario_count,
        )
        return harvest
    _LOG.debug(
        "counterfactual_source_chosen source=%s owner=%s tick=%s",
        CounterfactualSourceKind.NONE.value,
        invocation.agent_id.value,
        invocation.tick,
    )
    return CounterfactualNodeMaterial(
        source=CounterfactualSourceKind.NONE,
        reason_code="counterfactual_unavailable",
    )


def assemble_causal_trace(
    invocation: CognitionTraceInvocation,
    *,
    address: DebuggerEventAddress | None = None,
    counterfactual_source: CounterfactualNodeMaterial | None = None,
    ambiguity: bool = False,
    ambiguity_reason: str | None = None,
) -> CausalTrace:
    """Project researcher chain from stored stage summaries + CF sources only.

    Missing optional stages become ``unavailable`` nodes (not silent omissions).
    Rejects embedding Observation / WorldEvent / prompts via forbid checks.
    Action node uses ``planned_action`` / ``command_kind`` type codes only.
    """
    if type(invocation) is not CognitionTraceInvocation:
        raise TypeError("assemble_causal_trace requires CognitionTraceInvocation")

    addr = address
    if addr is None:
        addr = DebuggerEventAddress(
            run_id=invocation.run_id,
            tick=invocation.tick,
            agent_id=invocation.agent_id,
        )

    focus = DebuggerFocusHandle(
        run_id=addr.run_id,
        tick=addr.tick,
        sequence=addr.sequence,
        event_id=addr.event_id,
    )

    by_kind: dict[CognitionTraceStageKind, CognitionTraceStageSummary] = {}
    for stage in invocation.stages:
        by_kind[stage.summary.stage_kind] = stage.summary

    nodes: list[CausalTraceNode] = []
    for researcher_stage in RESEARCHER_CHAIN_SEQUENCE:
        if researcher_stage is ResearcherChainStage.COUNTERFACTUALS:
            material = select_counterfactual_material(
                invocation, harvest=counterfactual_source
            )
            if material.source is CounterfactualSourceKind.NONE:
                nodes.append(
                    _unavailable_node(
                        researcher_stage,
                        reason_code=material.reason_code
                        or "counterfactual_unavailable",
                    )
                )
            else:
                counts: dict[str, int] = {}
                if material.scenario_count is not None:
                    counts["scenario_count"] = material.scenario_count
                if material.skipped_count is not None:
                    counts["skipped_count"] = material.skipped_count
                if material.regret_count is not None:
                    counts["regret_count"] = material.regret_count
                if material.relief_count is not None:
                    counts["relief_count"] = material.relief_count
                if material.neutral_count is not None:
                    counts["neutral_count"] = material.neutral_count
                nodes.append(
                    CausalTraceNode(
                        stage_code=researcher_stage.value,
                        status=CausalNodeStatus.AVAILABLE,
                        reason_code=None,
                        id_refs=material.id_refs,
                        counts=counts or None,
                        selection_codes=material.selection_codes,
                        uncertainty_band=material.confidence_band,
                        focus_handles=(focus,),
                    )
                )
            continue

        stage_kind: CognitionTraceStageKind | None = None
        for kind, mapped in STAGE_KIND_TO_RESEARCHER.items():
            if mapped is researcher_stage:
                stage_kind = kind
                break
        if stage_kind is None:
            nodes.append(
                _unavailable_node(researcher_stage, reason_code="stage_unmapped")
            )
            continue
        summary = by_kind.get(stage_kind)
        if summary is None:
            nodes.append(
                _unavailable_node(researcher_stage, reason_code="stage_missing")
            )
            continue
        nodes.append(
            _summary_to_node(
                summary,
                stage_code=researcher_stage.value,
                focus=focus,
            )
        )

    supporting: list[CausalTraceNode] = []
    for secondary_kind in (
        CognitionTraceStageKind.SITUATION_MODEL,
        CognitionTraceStageKind.BUDGET_SUMMARY,
    ):
        summary = by_kind.get(secondary_kind)
        if summary is None:
            supporting.append(
                CausalTraceNode(
                    stage_code=secondary_kind.value,
                    status=CausalNodeStatus.UNAVAILABLE,
                    reason_code="stage_missing",
                    secondary=True,
                )
            )
            continue
        supporting.append(
            _summary_to_node(
                summary,
                stage_code=secondary_kind.value,
                focus=focus,
                secondary=True,
            )
        )

    unavailable_count = sum(
        1 for node in nodes if node.status is CausalNodeStatus.UNAVAILABLE
    )
    _LOG.debug(
        "causal_trace_assembled invocation_id=%s agent_id=%s tick=%s "
        "node_count=%s unavailable_count=%s",
        invocation.invocation_id,
        invocation.agent_id.value,
        invocation.tick,
        len(nodes),
        unavailable_count,
    )

    reason = ambiguity_reason if ambiguity else None
    return CausalTrace(
        address=addr,
        availability=CausalTraceAvailability.AVAILABLE,
        nodes=tuple(nodes),
        invocation_id=invocation.invocation_id,
        ambiguity=ambiguity,
        reason_code=reason,
        command_kind=invocation.command_kind,
        supporting_nodes=tuple(supporting),
    )


class CausalDebuggerService(Protocol):
    """Composition-root protocol for read-only debugger assembly."""

    async def causal_trace_for_event(
        self,
        *,
        run_id: RunId,
        event_id: str | None = None,
        tick: int | None = None,
        sequence: int | None = None,
    ) -> CausalTrace:
        """Resolve + assemble causal trace for one committed event address."""
