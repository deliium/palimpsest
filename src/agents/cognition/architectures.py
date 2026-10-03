"""Named cognitive architecture variants as composition tables.

Architectures expand into existing cognition modes and capability flags.
``CognitiveLoop`` never stores or branches on ``architecture_id`` — only
mode enums, injected policies, and table-selected stage bindings.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from agents.cognition.configuration import (
    COGNITION_FACTORY_VERSION,
    CognitionEmotionalStateMode,
    CognitionIdentityMode,
    CognitionImaginationMode,
    CognitionLoopConfig,
    CognitionMemoryMode,
    CognitionMortalityAppraisalMode,
    CognitionProspectiveMode,
    CognitionReflectionMode,
    CognitionTheoryOfMindMode,
    CognitionWorldModelMode,
)
from agents.cognition.defaults import (
    LiteralPerceptionInterpreter,
    PresentStateImagination,
    SubjectiveRevisionHook,
)
from agents.cognition.deliberation import (
    CommandPlanner,
    MultiCriteriaIntentionSelector,
)
from agents.cognition.imagination import ImaginationEngine
from agents.cognition.motivation import MotivationAppraisal
from agents.cognition.reflection import default_reflection_policy
from agents.cognition.theory_of_mind import default_theory_of_mind_policy
from agents.cognition.world_model import default_world_model_policy

__all__ = [
    "ARCHITECTURES",
    "OWNED_CAPABILITY_FLAG_NAMES",
    "STAGE_FACTORY_TABLE",
    "ArchitectureCompatibilityError",
    "ArchitectureDefinition",
    "ArchitectureModeSnapshot",
    "CapabilityDeclaration",
    "StageSlot",
    "architecture_definition_digest",
    "compose_loop_config_from_snapshot",
    "get_architecture",
    "resolve_stage",
    "validate_architecture_compatibility",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.architectures")

OWNED_CAPABILITY_FLAG_NAMES: Final[frozenset[str]] = frozenset(
    {
        "advanced_social_inference",
        "predictive_world_model",
        "extended_self_model",
        "short_term_emotional_state",
    }
)
_UNIMPLEMENTED_FLAG: Final[str] = "multi_hop_testimony_tracking"
_ALL_FLAG_NAMES: Final[frozenset[str]] = OWNED_CAPABILITY_FLAG_NAMES | frozenset(
    {_UNIMPLEMENTED_FLAG}
)

# Runner schema tokens used by presets (experiments import these for expand).
SCHEMA_V4: Final[str] = "runner-config-v4"
SCHEMA_V6: Final[str] = "runner-config-v6"
SCHEMA_V7: Final[str] = "runner-config-v7"

# Declaration-only tokens: expand to MemoryMode; runner injects retrievers.
_RETRIEVAL_DECLARATION_KEYS: Final[frozenset[str]] = frozenset(
    {"reference", "reconstructive", "reconstructive_v2"}
)


class StageSlot(StrEnum):
    """Stable stage-slot identifiers for architecture composition."""

    PERCEPTION = "perception"
    RETRIEVAL = "retrieval"
    RECONSTRUCTION = "reconstruction"
    BELIEFS = "beliefs"
    WORLD_MODEL = "world_model"
    REFLECTION = "reflection"
    IMAGINATION = "imagination"
    MOTIVATION = "motivation"
    THEORY_OF_MIND = "theory_of_mind"
    PLANNING = "planning"


class ArchitectureCompatibilityError(Exception):
    """Fail-closed architecture validation error with a stable reason code."""

    def __init__(self, reason_code: str, *, architecture_id: str = "") -> None:
        code = reason_code.strip()
        if not code:
            raise ValueError("reason_code must be non-blank")
        self.reason_code = code
        self.architecture_id = architecture_id.strip()
        parts = [f"reason_code={code}"]
        if self.architecture_id:
            parts.append(f"architecture_id={self.architecture_id}")
        super().__init__(",".join(parts))


@dataclass(frozen=True, slots=True)
class CapabilityDeclaration:
    """Required/forbidden flags, modes, slots, and implementation keys."""

    required_flags: frozenset[str] = frozenset()
    forbidden_flags: frozenset[str] = frozenset()
    required_modes: Mapping[str, str] = field(default_factory=dict)
    forbidden_modes: Mapping[str, frozenset[str]] = field(default_factory=dict)
    required_slots: frozenset[StageSlot] = frozenset()
    implementation_keys: Mapping[StageSlot, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "required_flags", frozenset(self.required_flags)
        )
        object.__setattr__(
            self, "forbidden_flags", frozenset(self.forbidden_flags)
        )
        object.__setattr__(
            self, "required_slots", frozenset(self.required_slots)
        )
        modes = {str(k): str(v) for k, v in dict(self.required_modes).items()}
        object.__setattr__(self, "required_modes", modes)
        forbidden: dict[str, frozenset[str]] = {}
        for key, values in dict(self.forbidden_modes).items():
            forbidden[str(key)] = frozenset(str(v) for v in values)
        object.__setattr__(self, "forbidden_modes", forbidden)
        keys: dict[StageSlot, str] = {}
        for slot, impl in dict(self.implementation_keys).items():
            if type(slot) is not StageSlot:
                _LOG.error(
                    "architecture_invalid reason_code=architecture_unknown_slot "
                    "slot=%s",
                    slot,
                )
                raise ValueError("architecture_unknown_slot")
            token = str(impl).strip()
            if not token:
                _LOG.error(
                    "architecture_invalid reason_code=architecture_blank_impl "
                    "slot=%s",
                    slot.value,
                )
                raise ValueError("architecture_blank_impl")
            keys[slot] = token
        object.__setattr__(self, "implementation_keys", keys)
        unknown_flags = (self.required_flags | self.forbidden_flags) - _ALL_FLAG_NAMES
        if unknown_flags:
            _LOG.error(
                "architecture_invalid reason_code=architecture_unknown_flag "
                "flags=%s",
                ",".join(sorted(unknown_flags)),
            )
            raise ValueError("architecture_unknown_flag")
        _LOG.debug(
            "capability_declaration_constructed required_flags=%s "
            "forbidden_flags=%s required_mode_keys=%s slot_count=%s",
            ",".join(sorted(self.required_flags)) or "-",
            ",".join(sorted(self.forbidden_flags)) or "-",
            ",".join(sorted(self.required_modes)) or "-",
            len(self.implementation_keys),
        )


@dataclass(frozen=True, slots=True)
class ArchitectureDefinition:
    """Named architecture: capability declaration plus stage bindings."""

    architecture_id: str
    capabilities: CapabilityDeclaration
    schema_version: str
    implementation_keys: Mapping[StageSlot, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        arch_id = self.architecture_id.strip()
        if not arch_id:
            _LOG.error(
                "architecture_invalid reason_code=architecture_blank_id"
            )
            raise ValueError("architecture_blank_id")
        object.__setattr__(self, "architecture_id", arch_id)
        if type(self.capabilities) is not CapabilityDeclaration:
            _LOG.error(
                "architecture_invalid reason_code=architecture_bad_capabilities "
                "architecture_id=%s",
                arch_id,
            )
            raise TypeError("capabilities must be CapabilityDeclaration")
        schema = self.schema_version.strip()
        if schema not in {SCHEMA_V4, SCHEMA_V6, SCHEMA_V7}:
            _LOG.error(
                "architecture_invalid reason_code=architecture_bad_schema "
                "architecture_id=%s schema_version=%s",
                arch_id,
                schema,
            )
            raise ValueError("architecture_bad_schema")
        object.__setattr__(self, "schema_version", schema)
        keys = dict(self.implementation_keys) or dict(
            self.capabilities.implementation_keys
        )
        normalized: dict[StageSlot, str] = {}
        for slot, impl in keys.items():
            if type(slot) is not StageSlot:
                _LOG.error(
                    "architecture_invalid reason_code=architecture_unknown_slot "
                    "architecture_id=%s slot=%s",
                    arch_id,
                    slot,
                )
                raise ValueError("architecture_unknown_slot")
            token = str(impl).strip()
            if not token:
                _LOG.error(
                    "architecture_invalid reason_code=architecture_blank_impl "
                    "architecture_id=%s slot=%s",
                    arch_id,
                    slot.value,
                )
                raise ValueError("architecture_blank_impl")
            normalized[slot] = token
        object.__setattr__(self, "implementation_keys", normalized)
        # Keep capability declaration keys aligned with definition bindings.
        if dict(self.capabilities.implementation_keys) != normalized:
            object.__setattr__(
                self,
                "capabilities",
                CapabilityDeclaration(
                    required_flags=self.capabilities.required_flags,
                    forbidden_flags=self.capabilities.forbidden_flags,
                    required_modes=self.capabilities.required_modes,
                    forbidden_modes=self.capabilities.forbidden_modes,
                    required_slots=self.capabilities.required_slots,
                    implementation_keys=normalized,
                ),
            )
        _LOG.debug(
            "architecture_definition_constructed architecture_id=%s "
            "schema_version=%s slot_count=%s",
            arch_id,
            schema,
            len(normalized),
        )


@dataclass(frozen=True, slots=True)
class ArchitectureModeSnapshot:
    """Cognition-local flag/mode snapshot for fail-closed validation.

    Filled at the experiments/simulation boundary. Must not import
    ``SimulationRunnerConfig``.
    """

    flags: Mapping[str, bool] = field(default_factory=dict)
    modes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        flags = {str(k): bool(v) for k, v in dict(self.flags).items()}
        modes = {str(k): str(v) for k, v in dict(self.modes).items()}
        object.__setattr__(self, "flags", flags)
        object.__setattr__(self, "modes", modes)


def _default_bindings(
    *,
    retrieval: str,
    reconstruction: str,
    imagination: str,
    world_model: str,
    reflection: str,
    theory_of_mind: str,
    motivation: str = "motivation_appraisal",
) -> dict[StageSlot, str]:
    return {
        StageSlot.PERCEPTION: "literal",
        StageSlot.RETRIEVAL: retrieval,
        StageSlot.RECONSTRUCTION: reconstruction,
        StageSlot.BELIEFS: "subjective_revision",
        StageSlot.WORLD_MODEL: world_model,
        StageSlot.REFLECTION: reflection,
        StageSlot.IMAGINATION: imagination,
        StageSlot.MOTIVATION: motivation,
        StageSlot.THEORY_OF_MIND: theory_of_mind,
        StageSlot.PLANNING: "command_planner",
    }


def _declaration(
    *,
    required_flags: frozenset[str],
    forbidden_flags: frozenset[str],
    memory_mode: str,
    imagination_mode: str,
    reflection_mode: str,
    prospective_mode: str,
    mortality_appraisal: str,
    bindings: Mapping[StageSlot, str],
) -> CapabilityDeclaration:
    return CapabilityDeclaration(
        required_flags=required_flags,
        forbidden_flags=forbidden_flags,
        required_modes={
            "memory_mode": memory_mode,
            "imagination_mode": imagination_mode,
            "reflection_mode": reflection_mode,
            "prospective_mode": prospective_mode,
            "mortality_appraisal": mortality_appraisal,
        },
        forbidden_modes={},
        required_slots=frozenset(StageSlot),
        implementation_keys=dict(bindings),
    )


def _preset(
    architecture_id: str,
    *,
    schema_version: str,
    required_flags: frozenset[str],
    forbidden_flags: frozenset[str],
    memory_mode: str,
    imagination_mode: str,
    reflection_mode: str,
    prospective_mode: str,
    mortality_appraisal: str,
    retrieval: str,
    reconstruction: str,
    imagination_key: str,
    world_model: str,
    reflection_key: str,
    theory_of_mind: str,
    motivation: str = "motivation_appraisal",
) -> ArchitectureDefinition:
    bindings = _default_bindings(
        retrieval=retrieval,
        reconstruction=reconstruction,
        imagination=imagination_key,
        world_model=world_model,
        reflection=reflection_key,
        theory_of_mind=theory_of_mind,
        motivation=motivation,
    )
    return ArchitectureDefinition(
        architecture_id=architecture_id,
        schema_version=schema_version,
        capabilities=_declaration(
            required_flags=required_flags,
            forbidden_flags=forbidden_flags,
            memory_mode=memory_mode,
            imagination_mode=imagination_mode,
            reflection_mode=reflection_mode,
            prospective_mode=prospective_mode,
            mortality_appraisal=mortality_appraisal,
            bindings=bindings,
        ),
        implementation_keys=bindings,
    )


_OFF_FLAGS: Final[frozenset[str]] = frozenset()
_ALL_OWNED_OFF_FORBIDDEN: Final[frozenset[str]] = frozenset(
    OWNED_CAPABILITY_FLAG_NAMES | {_UNIMPLEMENTED_FLAG}
)


def _build_registry() -> dict[str, ArchitectureDefinition]:
    return {
        "reactive_baseline": _preset(
            "reactive_baseline",
            schema_version=SCHEMA_V4,
            required_flags=_OFF_FLAGS,
            forbidden_flags=_ALL_OWNED_OFF_FORBIDDEN,
            memory_mode="reference",
            imagination_mode="disabled",
            reflection_mode="disabled",
            prospective_mode="disabled",
            mortality_appraisal="disabled",
            retrieval="reference",
            reconstruction="reference_passthrough",
            imagination_key="present_state",
            world_model="passthrough",
            reflection_key="disabled",
            theory_of_mind="passthrough",
            motivation="motivation_appraisal_off",
        ),
        "v1_memory_agent": _preset(
            "v1_memory_agent",
            schema_version=SCHEMA_V4,
            required_flags=_OFF_FLAGS,
            forbidden_flags=_ALL_OWNED_OFF_FORBIDDEN,
            memory_mode="reconstructive",
            imagination_mode="enabled",
            reflection_mode="disabled",
            prospective_mode="disabled",
            mortality_appraisal="enabled",
            retrieval="reconstructive",
            reconstruction="deterministic",
            imagination_key="imagination_engine",
            world_model="passthrough",
            reflection_key="disabled",
            theory_of_mind="passthrough",
        ),
        "reconstructive_memory_agent": _preset(
            "reconstructive_memory_agent",
            schema_version=SCHEMA_V4,
            required_flags=_OFF_FLAGS,
            forbidden_flags=_ALL_OWNED_OFF_FORBIDDEN,
            memory_mode="reconstructive_v2",
            imagination_mode="enabled",
            reflection_mode="disabled",
            prospective_mode="disabled",
            mortality_appraisal="enabled",
            retrieval="reconstructive_v2",
            reconstruction="reconstructive_v2",
            imagination_key="imagination_engine",
            world_model="passthrough",
            reflection_key="disabled",
            theory_of_mind="passthrough",
        ),
        "imagination_agent": _preset(
            "imagination_agent",
            schema_version=SCHEMA_V7,
            required_flags=_OFF_FLAGS,
            forbidden_flags=_ALL_OWNED_OFF_FORBIDDEN,
            memory_mode="reconstructive",
            imagination_mode="enabled",
            reflection_mode="disabled",
            prospective_mode="deterministic",
            mortality_appraisal="enabled",
            retrieval="reconstructive",
            reconstruction="deterministic",
            imagination_key="imagination_engine",
            world_model="passthrough",
            reflection_key="disabled",
            theory_of_mind="passthrough",
        ),
        "reflection_agent": _preset(
            "reflection_agent",
            schema_version=SCHEMA_V6,
            required_flags=_OFF_FLAGS,
            forbidden_flags=_ALL_OWNED_OFF_FORBIDDEN,
            memory_mode="reconstructive",
            imagination_mode="enabled",
            reflection_mode="deterministic",
            prospective_mode="disabled",
            mortality_appraisal="enabled",
            retrieval="reconstructive",
            reconstruction="deterministic",
            imagination_key="imagination_engine",
            world_model="passthrough",
            reflection_key="deterministic",
            theory_of_mind="passthrough",
        ),
        "theory_of_mind_agent": _preset(
            "theory_of_mind_agent",
            schema_version=SCHEMA_V4,
            required_flags=frozenset({"advanced_social_inference"}),
            forbidden_flags=frozenset(
                {
                    "predictive_world_model",
                    "extended_self_model",
                    "short_term_emotional_state",
                    _UNIMPLEMENTED_FLAG,
                }
            ),
            memory_mode="reconstructive",
            imagination_mode="enabled",
            reflection_mode="disabled",
            prospective_mode="disabled",
            mortality_appraisal="enabled",
            retrieval="reconstructive",
            reconstruction="deterministic",
            imagination_key="imagination_engine",
            world_model="passthrough",
            reflection_key="disabled",
            theory_of_mind="enabled",
        ),
        "full_v2_agent": _preset(
            "full_v2_agent",
            schema_version=SCHEMA_V6,
            required_flags=frozenset(OWNED_CAPABILITY_FLAG_NAMES),
            forbidden_flags=frozenset({_UNIMPLEMENTED_FLAG}),
            memory_mode="reconstructive_v2",
            imagination_mode="enabled",
            reflection_mode="deterministic",
            prospective_mode="disabled",
            mortality_appraisal="enabled",
            retrieval="reconstructive_v2",
            reconstruction="reconstructive_v2",
            imagination_key="imagination_engine",
            world_model="enabled",
            reflection_key="deterministic",
            theory_of_mind="enabled",
        ),
    }


ARCHITECTURES: Final[Mapping[str, ArchitectureDefinition]] = _build_registry()


def get_architecture(architecture_id: str) -> ArchitectureDefinition:
    """Return a registered architecture or fail closed."""
    key = architecture_id.strip()
    definition = ARCHITECTURES.get(key)
    if definition is None:
        _LOG.error(
            "architecture_lookup_failed reason_code=architecture_unknown "
            "architecture_id=%s",
            key,
        )
        raise ArchitectureCompatibilityError(
            "architecture_unknown", architecture_id=key
        )
    _LOG.debug("architecture_lookup_ok architecture_id=%s", key)
    return definition


# --- Service-free stage factories (no MemoryService / runner injection) ---


class _PassthroughWorldModelStage:
    async def select(
        self,
        model: object,
        *,
        tick: int,
        provider: object | None = None,
    ) -> object:
        _ = tick, provider
        _LOG.debug("world_model_stage_passthrough")
        return model


class _EnabledWorldModelStage:
    def __init__(self) -> None:
        self._policy = default_world_model_policy(allow_provider=False)

    async def select(
        self,
        model: object,
        *,
        tick: int,
        provider: object | None = None,
    ) -> object:
        from agents.cognition.world_model_selection import (
            select_world_model_hypotheses,
        )

        _LOG.debug("world_model_stage_enabled tick=%s", tick)
        return await select_world_model_hypotheses(
            model, self._policy, provider=provider, tick=tick
        )


class _PassthroughTheoryOfMindStage:
    async def select(
        self,
        model: object,
        *,
        tick: int,
        provider: object | None = None,
    ) -> object:
        _ = tick, provider
        _LOG.debug("theory_of_mind_stage_passthrough")
        return model


class _EnabledTheoryOfMindStage:
    def __init__(self) -> None:
        self._policy = default_theory_of_mind_policy(allow_provider=False)

    async def select(
        self,
        model: object,
        *,
        tick: int,
        provider: object | None = None,
    ) -> object:
        from agents.cognition.theory_of_mind_selection import (
            select_theory_of_mind_hypotheses,
        )

        _LOG.debug("theory_of_mind_stage_enabled tick=%s", tick)
        return await select_theory_of_mind_hypotheses(
            model, self._policy, provider=provider, tick=tick
        )


class _DisabledReflectionStage:
    def plan(
        self,
        *,
        context: object,
        triggers: object,
        mode: str,
        consolidation: object | None = None,
        acknowledged_goal_ids: tuple[object, ...] = (),
        selected_ids: tuple[str, ...] | None = None,
        fallback_used: bool = False,
        causal_world_model: object | None = None,
    ) -> object | None:
        _ = (
            context,
            triggers,
            mode,
            consolidation,
            acknowledged_goal_ids,
            selected_ids,
            fallback_used,
            causal_world_model,
        )
        _LOG.debug("reflection_stage_disabled")
        return None


class _DeterministicReflectionStage:
    def __init__(self) -> None:
        self._policy = default_reflection_policy(allow_provider=False)

    def plan(
        self,
        *,
        context: object,
        triggers: object,
        mode: str,
        consolidation: object | None = None,
        acknowledged_goal_ids: tuple[object, ...] = (),
        selected_ids: tuple[str, ...] | None = None,
        fallback_used: bool = False,
        causal_world_model: object | None = None,
    ) -> object | None:
        from agents.cognition.reflection import plan_reflection

        _LOG.debug("reflection_stage_deterministic mode=%s", mode)
        return plan_reflection(
            context=context,
            triggers=triggers,
            mode=mode,
            consolidation=consolidation,
            acknowledged_goal_ids=acknowledged_goal_ids,  # type: ignore[arg-type]
            selected_ids=selected_ids,
            fallback_used=fallback_used,
            causal_world_model=causal_world_model,
        )


def _factory_literal_perception() -> object:
    return LiteralPerceptionInterpreter()


def _factory_present_state_imagination() -> object:
    return PresentStateImagination()


def _factory_imagination_engine() -> object:
    return ImaginationEngine()


def _factory_motivation_appraisal() -> object:
    return MotivationAppraisal(mortality_appraisal_enabled=True)


def _factory_motivation_appraisal_off() -> object:
    return MotivationAppraisal(mortality_appraisal_enabled=False)


def _factory_command_planner() -> object:
    return CommandPlanner()


def _factory_intention_selector() -> object:
    return MultiCriteriaIntentionSelector()


def _factory_subjective_revision() -> object:
    return SubjectiveRevisionHook()


def _factory_passthrough_world_model() -> object:
    return _PassthroughWorldModelStage()


def _factory_enabled_world_model() -> object:
    return _EnabledWorldModelStage()


def _factory_passthrough_tom() -> object:
    return _PassthroughTheoryOfMindStage()


def _factory_enabled_tom() -> object:
    return _EnabledTheoryOfMindStage()


def _factory_disabled_reflection() -> object:
    return _DisabledReflectionStage()


def _factory_deterministic_reflection() -> object:
    return _DeterministicReflectionStage()


def _declaration_token_factory(token: str) -> Callable[[], object]:
    """Record retrieval/reconstruction tokens without constructing services."""

    def _factory() -> object:
        _LOG.debug("stage_declaration_token token=%s", token)
        return token

    return _factory


STAGE_FACTORY_TABLE: Final[Mapping[tuple[StageSlot, str], Callable[[], object]]] = {
    (StageSlot.PERCEPTION, "literal"): _factory_literal_perception,
    (StageSlot.RETRIEVAL, "reference"): _declaration_token_factory("reference"),
    (StageSlot.RETRIEVAL, "reconstructive"): _declaration_token_factory(
        "reconstructive"
    ),
    (StageSlot.RETRIEVAL, "reconstructive_v2"): _declaration_token_factory(
        "reconstructive_v2"
    ),
    (StageSlot.RECONSTRUCTION, "reference_passthrough"): _declaration_token_factory(
        "reference_passthrough"
    ),
    (StageSlot.RECONSTRUCTION, "deterministic"): _declaration_token_factory(
        "deterministic"
    ),
    (StageSlot.RECONSTRUCTION, "reconstructive_v2"): _declaration_token_factory(
        "reconstructive_v2"
    ),
    (StageSlot.BELIEFS, "subjective_revision"): _factory_subjective_revision,
    (StageSlot.WORLD_MODEL, "passthrough"): _factory_passthrough_world_model,
    (StageSlot.WORLD_MODEL, "enabled"): _factory_enabled_world_model,
    (StageSlot.REFLECTION, "disabled"): _factory_disabled_reflection,
    (StageSlot.REFLECTION, "deterministic"): _factory_deterministic_reflection,
    (StageSlot.IMAGINATION, "present_state"): _factory_present_state_imagination,
    (StageSlot.IMAGINATION, "imagination_engine"): _factory_imagination_engine,
    (StageSlot.MOTIVATION, "motivation_appraisal"): _factory_motivation_appraisal,
    (
        StageSlot.MOTIVATION,
        "motivation_appraisal_off",
    ): _factory_motivation_appraisal_off,
    (StageSlot.THEORY_OF_MIND, "passthrough"): _factory_passthrough_tom,
    (StageSlot.THEORY_OF_MIND, "enabled"): _factory_enabled_tom,
    (StageSlot.PLANNING, "command_planner"): _factory_command_planner,
    (StageSlot.PLANNING, "intention_selector"): _factory_intention_selector,
}


def resolve_stage(slot: StageSlot, implementation_key: str) -> object:
    """Build a service-free stage from the closed factory table."""
    if type(slot) is not StageSlot:
        raise TypeError("slot must be StageSlot")
    key = implementation_key.strip()
    factory = STAGE_FACTORY_TABLE.get((slot, key))
    if factory is None:
        _LOG.error(
            "stage_resolve_failed reason_code=architecture_unknown_impl "
            "slot=%s implementation_key=%s",
            slot.value,
            key,
        )
        raise ArchitectureCompatibilityError("architecture_unknown_impl")
    instance = factory()
    _LOG.debug(
        "stage_resolved slot=%s implementation_key=%s type=%s",
        slot.value,
        key,
        type(instance).__name__,
    )
    return instance


def validate_architecture_compatibility(
    definition: ArchitectureDefinition,
    mode_snapshot: ArchitectureModeSnapshot,
) -> None:
    """Fail closed when definition and snapshot disagree."""
    if type(definition) is not ArchitectureDefinition:
        raise TypeError("definition must be ArchitectureDefinition")
    if type(mode_snapshot) is not ArchitectureModeSnapshot:
        raise TypeError("mode_snapshot must be ArchitectureModeSnapshot")

    arch_id = definition.architecture_id
    caps = definition.capabilities
    _LOG.debug(
        "architecture_validate_start architecture_id=%s flag_names=%s "
        "mode_tokens=%s",
        arch_id,
        ",".join(sorted(mode_snapshot.flags)) or "-",
        ",".join(f"{k}={v}" for k, v in sorted(mode_snapshot.modes.items())) or "-",
    )

    if _UNIMPLEMENTED_FLAG in caps.required_flags:
        _LOG.error(
            "architecture_validate_failed reason_code=architecture_unimplemented_flag "
            "architecture_id=%s flag=%s",
            arch_id,
            _UNIMPLEMENTED_FLAG,
        )
        raise ArchitectureCompatibilityError(
            "architecture_unimplemented_flag", architecture_id=arch_id
        )

    if mode_snapshot.flags.get(_UNIMPLEMENTED_FLAG, False):
        _LOG.error(
            "architecture_validate_failed reason_code=capability_unimplemented "
            "architecture_id=%s flag=%s",
            arch_id,
            _UNIMPLEMENTED_FLAG,
        )
        raise ArchitectureCompatibilityError(
            "capability_unimplemented", architecture_id=arch_id
        )

    keys = definition.implementation_keys
    for slot in caps.required_slots:
        if slot not in keys:
            _LOG.error(
                "architecture_validate_failed reason_code=architecture_slot_unbound "
                "architecture_id=%s slot=%s",
                arch_id,
                slot.value,
            )
            raise ArchitectureCompatibilityError(
                "architecture_slot_unbound", architecture_id=arch_id
            )

    for slot, impl in keys.items():
        if (slot, impl) not in STAGE_FACTORY_TABLE:
            _LOG.error(
                "architecture_validate_failed reason_code=architecture_unknown_impl "
                "architecture_id=%s slot=%s implementation_key=%s",
                arch_id,
                slot.value,
                impl,
            )
            raise ArchitectureCompatibilityError(
                "architecture_unknown_impl", architecture_id=arch_id
            )

    for flag in caps.required_flags:
        if not mode_snapshot.flags.get(flag, False):
            _LOG.error(
                "architecture_validate_failed reason_code=architecture_missing_flag "
                "architecture_id=%s flag=%s",
                arch_id,
                flag,
            )
            raise ArchitectureCompatibilityError(
                "architecture_missing_flag", architecture_id=arch_id
            )

    for flag in caps.forbidden_flags:
        if mode_snapshot.flags.get(flag, False):
            _LOG.error(
                "architecture_validate_failed reason_code=architecture_forbidden_flag "
                "architecture_id=%s flag=%s",
                arch_id,
                flag,
            )
            raise ArchitectureCompatibilityError(
                "architecture_forbidden_flag", architecture_id=arch_id
            )

    for mode_key, expected in caps.required_modes.items():
        actual = mode_snapshot.modes.get(mode_key)
        if actual != expected:
            _LOG.error(
                "architecture_validate_failed reason_code=architecture_mode_mismatch "
                "architecture_id=%s mode_key=%s expected=%s actual=%s",
                arch_id,
                mode_key,
                expected,
                actual,
            )
            raise ArchitectureCompatibilityError(
                "architecture_mode_mismatch", architecture_id=arch_id
            )

    for mode_key, forbidden in caps.forbidden_modes.items():
        actual = mode_snapshot.modes.get(mode_key)
        if actual is not None and actual in forbidden:
            _LOG.error(
                "architecture_validate_failed reason_code=architecture_mode_mismatch "
                "architecture_id=%s mode_key=%s forbidden=%s",
                arch_id,
                mode_key,
                actual,
            )
            raise ArchitectureCompatibilityError(
                "architecture_mode_mismatch", architecture_id=arch_id
            )

    _LOG.info(
        "architecture_validated architecture_id=%s schema_version=%s",
        arch_id,
        definition.schema_version,
    )


def architecture_definition_digest(definition: ArchitectureDefinition) -> str:
    """Stable SHA-256 hex digest over definition fields (diagnostics only)."""
    if type(definition) is not ArchitectureDefinition:
        raise TypeError("definition must be ArchitectureDefinition")
    caps = definition.capabilities
    lines = [
        f"architecture_id={definition.architecture_id}",
        f"schema_version={definition.schema_version}",
        "required_flags="
        + ",".join(sorted(caps.required_flags)),
        "forbidden_flags="
        + ",".join(sorted(caps.forbidden_flags)),
        "required_modes="
        + ";".join(
            f"{k}:{caps.required_modes[k]}" for k in sorted(caps.required_modes)
        ),
        "forbidden_modes="
        + ";".join(
            f"{k}:{','.join(sorted(caps.forbidden_modes[k]))}"
            for k in sorted(caps.forbidden_modes)
        ),
        "required_slots="
        + ",".join(sorted(s.value for s in caps.required_slots)),
        "implementation_keys="
        + ";".join(
            f"{slot.value}:{definition.implementation_keys[slot]}"
            for slot in sorted(definition.implementation_keys, key=lambda s: s.value)
        ),
    ]
    payload = "\n".join(lines) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    _LOG.debug(
        "architecture_definition_digest architecture_id=%s digest=%s",
        definition.architecture_id,
        digest,
    )
    return digest


def compose_loop_config_from_snapshot(
    snapshot: ArchitectureModeSnapshot,
    *,
    architecture_id: str | None = None,
) -> CognitionLoopConfig:
    """Compose ``CognitionLoopConfig`` from mode/flag tokens only.

    Flag→mode mapping stays consistent with
    ``simulation.runner._cognition_config_for``. Never branches on
    ``architecture_id`` for control flow (log metadata only).
    """
    if type(snapshot) is not ArchitectureModeSnapshot:
        raise TypeError("snapshot must be ArchitectureModeSnapshot")

    modes = snapshot.modes
    flags = snapshot.flags

    memory_token = modes.get("memory_mode", "reconstructive")
    memory_mode = CognitionMemoryMode(memory_token)

    imagination_token = modes.get("imagination_mode", "enabled")
    imagination_mode = CognitionImaginationMode(imagination_token)

    mortality_token = modes.get("mortality_appraisal", "enabled")
    mortality_appraisal_mode = CognitionMortalityAppraisalMode(mortality_token)

    reflection_token = modes.get("reflection_mode", "disabled")
    reflection_mode = CognitionReflectionMode(reflection_token)
    reflection_policy = None
    if reflection_mode is not CognitionReflectionMode.DISABLED:
        reflection_policy = default_reflection_policy(allow_provider=False)

    prospective_token = modes.get("prospective_mode", "disabled")
    prospective_mode = CognitionProspectiveMode(prospective_token)

    emotional_mode = (
        CognitionEmotionalStateMode.ENABLED
        if flags.get("short_term_emotional_state", False)
        else CognitionEmotionalStateMode.PASSTHROUGH
    )
    identity_mode = (
        CognitionIdentityMode.ENABLED
        if flags.get("extended_self_model", False)
        else CognitionIdentityMode.PASSTHROUGH
    )
    world_model_mode = (
        CognitionWorldModelMode.ENABLED
        if flags.get("predictive_world_model", False)
        else CognitionWorldModelMode.PASSTHROUGH
    )
    world_model_policy = default_world_model_policy(allow_provider=False)
    mind_mode = (
        CognitionTheoryOfMindMode.ENABLED
        if flags.get("advanced_social_inference", False)
        else CognitionTheoryOfMindMode.PASSTHROUGH
    )
    mind_policy = default_theory_of_mind_policy(allow_provider=False)

    config = CognitionLoopConfig(
        memory_mode=memory_mode,
        imagination_mode=imagination_mode,
        mortality_appraisal_mode=mortality_appraisal_mode,
        emotional_state_mode=emotional_mode,
        reflection_mode=reflection_mode,
        reflection_policy=reflection_policy,
        identity_mode=identity_mode,
        world_model_mode=world_model_mode,
        world_model_policy=world_model_policy,
        theory_of_mind_mode=mind_mode,
        theory_of_mind_policy=mind_policy,
        prospective_mode=prospective_mode,
        factory_version=COGNITION_FACTORY_VERSION,
    )
    _LOG.info(
        "cognitive_loop_composed_from_snapshot factory_version=%s "
        "architecture_id=%s memory_mode=%s imagination_mode=%s "
        "reflection_mode=%s prospective_mode=%s",
        config.factory_version,
        architecture_id or "-",
        config.memory_mode.value,
        config.imagination_mode.value,
        config.reflection_mode.value,
        config.prospective_mode.value,
    )
    return config


def snapshot_from_definition(
    definition: ArchitectureDefinition,
    *,
    extra_flags: Mapping[str, bool] | None = None,
) -> ArchitectureModeSnapshot:
    """Build a mode snapshot that satisfies ``definition`` capability rules."""
    flags = {name: False for name in _ALL_FLAG_NAMES}
    for name in definition.capabilities.required_flags:
        flags[name] = True
    if extra_flags:
        flags.update({str(k): bool(v) for k, v in extra_flags.items()})
    return ArchitectureModeSnapshot(
        flags=flags,
        modes=dict(definition.capabilities.required_modes),
    )


def memory_mode_for_retrieval_key(implementation_key: str) -> str:
    """Map retrieval declaration token to a memory_mode string."""
    key = implementation_key.strip()
    if key not in _RETRIEVAL_DECLARATION_KEYS:
        raise ArchitectureCompatibilityError("architecture_unknown_impl")
    return key
