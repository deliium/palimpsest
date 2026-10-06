"""Configuration-driven simulation runner construction and lifecycle ownership.

``SimulationRunner.from_config`` builds world, agents, cognition, and runtime
services from an immutable runner specification plus narrow injected factories.
It never imports environment settings, SQLAlchemy adapters, or API code.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol

from agents.cognition.communication_strategy import (
    default_communication_strategy_policy,
)
from agents.cognition.competence import CompetenceBeliefPolicy
from agents.cognition.configuration import (
    CognitionCommunicationStrategyMode,
    CognitionConsolidationMode,
    CognitionCounterfactualMode,
    CognitionDriveOverride,
    CognitionEmotionalStateMode,
    CognitionIdentityMode,
    CognitionImaginationMode,
    CognitionLoopConfig,
    CognitionMemoryMode,
    CognitionMortalityAppraisalMode,
    CognitionProspectiveMode,
    CognitionReflectionMode,
    CognitionReputationMode,
    CognitionSkillLearningMode,
    CognitionTeachingInteractionMode,
    CognitionTheoryOfMindMode,
    CognitionWorldModelMode,
    build_cognitive_loop,
    default_theory_of_mind_policy,
    default_world_model_policy,
)
from agents.cognition.counterfactual import default_counterfactual_policy
from agents.cognition.memory import ReferenceMemoryRetriever, ScopedMemoryRetriever
from agents.cognition.models import ComponentKind
from agents.cognition.prospective import default_prospective_policy
from agents.cognition.reconstruction import LLMMemoryReconstructor
from agents.cognition.reflection import default_reflection_policy
from agents.cognition.reputation import default_reputation_policy
from agents.models import Agent, AgentId, Goal, GoalStatus
from llm.factory import (
    DeterministicFakeLLMProvider,
    DisabledLLMProvider,
    ProviderAdapterKind,
    ProviderFactoryConfig,
    create_llm_provider,
)
from llm.recording import (
    LookupMode,
    RecordingMode,
    create_filesystem_recording_store,
    wrap_recording_provider,
)
from memory.belief_service import InMemorySemanticBeliefService
from memory.contracts import MemoryReconstructor, MemoryService, SemanticBeliefService
from memory.models import (
    BeliefStore,
    MemoryReconstructionPolicy,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemoryStore,
)
from memory.reconstruction import DeterministicMemoryReconstructor
from memory.service import InMemoryMemoryService
from simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeStatus,
    PendingRuntimeFinalization,
    PreparedObservation,
)
from simulation.bootstrap import (
    RegistrationTranslator,
    WorldBootstrap,
    registration_translator,
)
from simulation.clock import Tick
from simulation.cognition_trace import (
    CognitionTraceRepository,
    select_cognition_trace_repository,
)
from simulation.engine import WorldEngine
from simulation.identifiers import derive_run_id
from simulation.journal import hash_snapshot
from simulation.lifecycle import (
    ActionResolution,
    ActionResolutionStatus,
    ActionSubmission,
    TickResult,
)
from simulation.models import DERIVATION_VERSION_V3, RunId, SimulationRunConfig
from simulation.persistence import (
    LEGACY_PENDING_FINALIZATION_CODEC_VERSION,
    PENDING_FINALIZATION_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    PendingFinalizationRecord,
    PendingFinalizationRepository,
    PendingFinalizationStatus,
    RunCreateRequest,
    ScientificEvidenceRepository,
    SimulationRunRepository,
    SnapshotId,
    TickJournalRepository,
    WorldSnapshot,
    checkpoint_schema_for_production,
)
from simulation.run_control import (
    FinalizationCommand,
    ResumeMode,
    RunnerCrashInjected,
    RunnerCrashPoint,
    RunnerResumePlan,
    RunnerRuntimeCheckpoint,
    classify_resume_mode,
)
from simulation.runner_models import (
    _V2_CAPABILITY_FLAG_NAMES,
    RUNNER_SCHEMA_VERSION_V25,
    RUNNER_SCHEMA_VERSION_V26,
    RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CognitionCounters,
    CognitionFailurePolicy,
    DetachedObjectiveProjection,
    ExperimentalObservationSink,
    FinalizedTickReceipt,
    GoalEvaluationEvidence,
    GoalTransitionReceipt,
    MemoryMode,
    MortalityMode,
    ObservationDelivery,
    RecordingPolicy,
    RunnerAttemptReceipt,
    RunnerAttemptStatus,
    RunnerProviderSettings,
    RunnerStopReasonCode,
    SimulationRunnerConfig,
    SimulationRunnerResult,
    SkillAudit,
    SkillAuditSide,
    SkillLearningMode,
    TeachingAudit,
    TeachingAuditStore,
    TeachingInteractionMode,
    V2CapabilityFlags,
    build_detached_objective_projection,
    describe_runner_config,
    detach_action_resolution_evidence,
    evaluate_goals_after_finalization,
)
from simulation.runner_serialization import (
    build_runner_diagnostics,
    decode_finalization_command,
    finalization_command_to_mapping,
    objective_projection_hash,
)
from simulation.service import PersistentSimulationService
from simulation.subjective_state import (
    InMemorySubjectiveOwnerBundle,
    SubjectiveOwnerBundle,
    SubjectiveStateService,
)
from social.contracts import RelationshipService
from social.service import InMemoryRelationshipService
from world.actions import AgentCommand, require_agent_command
from world.identifiers import EntityId, WorldRevision

_LOG: Final[logging.Logger] = logging.getLogger("simulation.runner")
_DEFAULT_SCORING_POLICY_ID: Final[str] = "runner-default"
_DEFAULT_SCORING_POLICY_VERSION: Final[str] = "1"
_DEFAULT_RECONSTRUCTION_POLICY_ID: Final[str] = "runner-reconstruction"
_DEFAULT_RECONSTRUCTION_POLICY_VERSION: Final[str] = "1"

__all__ = [
    "AsyncCloseable",
    "BeliefServiceFactory",
    "MemoryServiceFactory",
    "ProviderCredentialResolver",
    "ProviderCredentials",
    "RecordingStoreSettings",
    "RelationshipServiceFactory",
    "RunnerConstructionError",
    "RunnerConstructionErrorCode",
    "RunnerDependencyFactories",
    "SimulationRunner",
    "SubjectiveBundleFactory",
]

_LLM_ASSISTED_POLICIES: Final[frozenset[RecordingPolicy]] = frozenset(
    {
        RecordingPolicy.LIVE,
        RecordingPolicy.RECORD,
        RecordingPolicy.CACHE,
        RecordingPolicy.REPLAY,
    }
)
_RECORDING_STORE_POLICIES: Final[frozenset[RecordingPolicy]] = frozenset(
    {
        RecordingPolicy.RECORD,
        RecordingPolicy.CACHE,
        RecordingPolicy.REPLAY,
    }
)


class RunnerConstructionErrorCode(StrEnum):
    """Stable construction/cleanup failure codes (no payloads)."""

    INVALID_CONFIG = "invalid_config"
    OWNERSHIP = "ownership"
    FACTORY_FAILED = "factory_failed"
    PROVIDER_FAILED = "provider_failed"
    CLEANUP_FAILED = "cleanup_failed"
    DURABLE_UNSUPPORTED = "durable_unsupported"
    PARTIAL_CONSTRUCTION = "partial_construction"
    CAPABILITY_UNIMPLEMENTED = "capability_unimplemented"


class RunnerConstructionError(ValueError):
    """Fail-closed runner construction error with a stable reason code."""

    def __init__(
        self,
        code: RunnerConstructionErrorCode,
        *,
        stage: str | None = None,
    ) -> None:
        if type(code) is not RunnerConstructionErrorCode:
            raise TypeError("code must be RunnerConstructionErrorCode")
        self.code = code
        self.stage = stage
        parts = [f"code={code.value}"]
        if stage is not None:
            parts.append(f"stage={stage}")
        super().__init__(",".join(parts))

    def __repr__(self) -> str:
        return f"RunnerConstructionError({self})"


class AsyncCloseable(Protocol):
    """Minimal async resource lifecycle protocol for injected providers."""

    async def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ProviderCredentials:
    """Resolved credential material. Never fingerprinted or persisted."""

    api_key: str | None = None
    base_url: str | None = None


@dataclass(frozen=True, slots=True)
class RecordingStoreSettings:
    """Composition-only recording store settings (never in provider JSON)."""

    root_dir: Path | str
    cache_namespace: str
    lookup_mode: LookupMode

    def __post_init__(self) -> None:
        if not isinstance(self.root_dir, (Path, str)):
            raise TypeError("root_dir must be Path or str")
        if not isinstance(self.cache_namespace, str) or not (
            self.cache_namespace.strip()
        ):
            raise ValueError("cache_namespace must be a non-blank string")
        if type(self.lookup_mode) is not LookupMode:
            raise TypeError("lookup_mode must be LookupMode")
        object.__setattr__(self, "cache_namespace", self.cache_namespace.strip())

    def __repr__(self) -> str:
        root_name = (
            self.root_dir.name
            if isinstance(self.root_dir, Path)
            else Path(self.root_dir).name
        )
        return (
            "RecordingStoreSettings("
            f"root_basename={root_name!r}, "
            f"namespace_chars={len(self.cache_namespace)}, "
            f"lookup_mode={self.lookup_mode.value!r})"
        )


class ProviderCredentialResolver(Protocol):
    """Maps credential-free provider settings to secrets at construction."""

    def resolve(self, settings: RunnerProviderSettings) -> ProviderCredentials: ...


AsyncSleep = Callable[[float], Awaitable[None]]
MonotonicClock = Callable[[], float]


class MemoryServiceFactory(Protocol):
    """Injectable factory for owner-scoped episodic memory services."""

    def __call__(
        self,
        scope: MemoryScope,
        *,
        reconstructor: MemoryReconstructor | None = None,
    ) -> MemoryService: ...


class BeliefServiceFactory(Protocol):
    """Injectable factory for owner-scoped semantic belief services."""

    def __call__(self, scope: MemoryScope) -> SemanticBeliefService: ...


class RelationshipServiceFactory(Protocol):
    """Injectable factory for owner-scoped relationship services."""

    def __call__(self, owner_id: AgentId) -> RelationshipService: ...


class SubjectiveBundleFactory(Protocol):
    """Injectable factory for owner-scoped subjective bundles."""

    def __call__(
        self,
        scope: MemoryScope,
        *,
        memory_service: MemoryService,
        belief_service: SemanticBeliefService,
        relationship_service: RelationshipService,
    ) -> SubjectiveOwnerBundle: ...


class RunnerDependencyFactories:
    """Narrow injected factories for runner-owned resource construction.

    Defaults construct in-memory owner-scoped services and a deterministic-fake
    or disabled LLM provider. Durable persistence adapters are injected by
    composition roots via the protocol factories below.
    """

    __slots__ = (
        "_belief_factory",
        "_bundle_factory",
        "_cognition_trace_repository",
        "_credential_resolver",
        "_journal",
        "_llm_max_concurrency",
        "_memory_factory",
        "_monotonic",
        "_pending_finalizations",
        "_provider_factory",
        "_recording_store",
        "_relationship_factory",
        "_run_repository",
        "_scientific_evidence",
        "_sleep",
    )

    def __init__(
        self,
        *,
        credential_resolver: ProviderCredentialResolver | None = None,
        provider_factory: (
            Callable[
                [RunnerProviderSettings, ProviderCredentials],
                AsyncCloseable,
            ]
            | None
        ) = None,
        recording_store: RecordingStoreSettings | None = None,
        memory_factory: MemoryServiceFactory | None = None,
        belief_factory: BeliefServiceFactory | None = None,
        relationship_factory: RelationshipServiceFactory | None = None,
        bundle_factory: SubjectiveBundleFactory | None = None,
        sleep: AsyncSleep | None = None,
        monotonic: MonotonicClock | None = None,
        run_repository: SimulationRunRepository | None = None,
        journal: TickJournalRepository | None = None,
        pending_finalizations: PendingFinalizationRepository | None = None,
        cognition_trace_repository: CognitionTraceRepository | None = None,
        scientific_evidence: ScientificEvidenceRepository | None = None,
        llm_max_concurrency: int = 1,
    ) -> None:
        if (
            isinstance(llm_max_concurrency, bool)
            or type(llm_max_concurrency) is not int
            or llm_max_concurrency < 1
        ):
            raise ValueError("llm_max_concurrency must be >= 1")
        self._credential_resolver = credential_resolver
        self._provider_factory = provider_factory
        self._recording_store = recording_store
        self._memory_factory = memory_factory
        self._belief_factory = belief_factory
        self._relationship_factory = relationship_factory
        self._bundle_factory = bundle_factory
        self._sleep = sleep
        self._monotonic = monotonic
        self._run_repository = run_repository
        self._journal = journal
        self._pending_finalizations = pending_finalizations
        self._cognition_trace_repository = cognition_trace_repository
        self._scientific_evidence = scientific_evidence
        self._llm_max_concurrency = llm_max_concurrency

    @property
    def run_repository(self) -> SimulationRunRepository | None:
        return self._run_repository

    @property
    def journal(self) -> TickJournalRepository | None:
        return self._journal

    @property
    def pending_finalizations(self) -> PendingFinalizationRepository | None:
        return self._pending_finalizations

    @property
    def cognition_trace_repository(self) -> CognitionTraceRepository | None:
        return self._cognition_trace_repository

    @property
    def scientific_evidence(self) -> ScientificEvidenceRepository | None:
        return self._scientific_evidence

    def resolve_credentials(
        self, settings: RunnerProviderSettings
    ) -> ProviderCredentials:
        if self._credential_resolver is not None:
            return self._credential_resolver.resolve(settings)
        return ProviderCredentials()

    def create_provider(
        self,
        settings: RunnerProviderSettings,
        credentials: ProviderCredentials,
    ) -> AsyncCloseable:
        if self._provider_factory is not None:
            provider = self._provider_factory(settings, credentials)
        else:
            provider = _default_provider(
                settings,
                credentials,
                sleep=self._sleep,
                monotonic=self._monotonic,
                recording_store=self._recording_store,
            )
        from llm.factory import wrap_llm_concurrency

        return wrap_llm_concurrency(  # type: ignore[return-value]
            provider, max_concurrency=self._llm_max_concurrency
        )

    def create_memory_service(
        self,
        scope: MemoryScope,
        *,
        reconstructor: MemoryReconstructor | None = None,
    ) -> MemoryService:
        if self._memory_factory is not None:
            return self._memory_factory(scope, reconstructor=reconstructor)
        return InMemoryMemoryService(scope, reconstructor=reconstructor)

    def create_belief_service(self, scope: MemoryScope) -> SemanticBeliefService:
        if self._belief_factory is not None:
            return self._belief_factory(scope)
        return InMemorySemanticBeliefService(scope)

    def create_relationship_service(self, owner_id: AgentId) -> RelationshipService:
        if self._relationship_factory is not None:
            return self._relationship_factory(owner_id)
        return InMemoryRelationshipService(owner_id)

    def create_subjective_bundle(
        self,
        scope: MemoryScope,
        *,
        memory_service: MemoryService,
        belief_service: SemanticBeliefService,
        relationship_service: RelationshipService,
    ) -> SubjectiveOwnerBundle:
        if self._bundle_factory is not None:
            return self._bundle_factory(
                scope,
                memory_service=memory_service,
                belief_service=belief_service,
                relationship_service=relationship_service,
            )
        return InMemorySubjectiveOwnerBundle(
            scope,
            memory_service=memory_service,
            belief_service=belief_service,
            relationship_service=relationship_service,
        )


def _default_scoring_policy() -> MemoryScoringPolicy:
    return MemoryScoringPolicy(
        policy_id=_DEFAULT_SCORING_POLICY_ID,
        version=_DEFAULT_SCORING_POLICY_VERSION,
        weights=MemoryScoreWeights(recency=1.0, current_context_overlap=1.0),
    )


def _default_reconstruction_policy(
    *, allow_provider: bool
) -> MemoryReconstructionPolicy:
    return MemoryReconstructionPolicy(
        policy_id=_DEFAULT_RECONSTRUCTION_POLICY_ID,
        version=_DEFAULT_RECONSTRUCTION_POLICY_VERSION,
        allow_provider=allow_provider,
        reconsolidate=True,
    )



def _caregiving_loop_kwargs(config: object) -> dict[str, object]:
    """Bind caregiving cognition from dependency_care only (no AgentCognitionSpec)."""
    care = getattr(config, "dependency_care", None)
    if care is None:
        return {}
    mode = getattr(care, "caregiving_cognition_mode", "disabled")
    return {
        "caregiving_cognition_mode": mode,
        "care_action_policy": getattr(care, "care_action_policy", None),
    }


def _developmental_stage_learning_rates(config: object) -> dict[str, float]:
    """Extract stage_id → learning_rate_factor from population_lifecycle effects."""
    lifecycle = getattr(config, "population_lifecycle", None)
    if lifecycle is None:
        return {}
    effects = getattr(lifecycle, "stage_capability_effects", ()) or ()
    rates: dict[str, float] = {}
    for effect in effects:
        stage = getattr(effect, "stage_id", None)
        factor = getattr(effect, "learning_rate_factor", None)
        if stage is None or factor is None:
            continue
        stage_key = getattr(stage, "value", stage)
        if isinstance(stage_key, str):
            rates[stage_key] = float(factor)
    return rates


def _developmental_learning_loop_kwargs(config: object) -> dict[str, object]:
    """Bind developmental_learning channel (no AgentCognitionSpec enum)."""
    spec = getattr(config, "developmental_learning", None)
    if spec is None:
        return {}
    return {
        "developmental_learning_spec": spec,
        "developmental_stage_learning_rates": _developmental_stage_learning_rates(
            config
        ),
    }


def _cognition_config_for(
    spec: AgentCognitionSpec,
    *,
    mortality_mode: MortalityMode,
    capability_flags: V2CapabilityFlags,
) -> CognitionLoopConfig:
    emotional_flag = capability_flags.short_term_emotional_state
    emotional_mode = (
        CognitionEmotionalStateMode.ENABLED
        if emotional_flag
        else CognitionEmotionalStateMode.PASSTHROUGH
    )
    _LOG.debug(
        "cognition_config_emotional_state_mode flag=%s mode=%s",
        emotional_flag,
        emotional_mode.value,
    )
    identity_flag = capability_flags.extended_self_model
    identity_mode = (
        CognitionIdentityMode.ENABLED
        if identity_flag
        else CognitionIdentityMode.PASSTHROUGH
    )
    _LOG.debug(
        "cognition_config_identity_mode flag=%s mode=%s",
        identity_flag,
        identity_mode.value,
    )
    world_model_flag = capability_flags.predictive_world_model
    world_model_mode = (
        CognitionWorldModelMode.ENABLED
        if world_model_flag
        else CognitionWorldModelMode.PASSTHROUGH
    )
    world_model_policy = default_world_model_policy(allow_provider=False)
    _LOG.debug(
        "cognition_config_world_model_mode flag=%s mode=%s policy_version=%s",
        world_model_flag,
        world_model_mode.value,
        world_model_policy.version,
    )
    mind_flag = capability_flags.advanced_social_inference
    mind_mode = (
        CognitionTheoryOfMindMode.ENABLED
        if mind_flag
        else CognitionTheoryOfMindMode.PASSTHROUGH
    )
    mind_policy = default_theory_of_mind_policy(allow_provider=False)
    _LOG.debug(
        "cognition_config_theory_of_mind_mode flag=%s mode=%s policy_version=%s",
        mind_flag,
        mind_mode.value,
        mind_policy.version,
    )
    reflection_mode = CognitionReflectionMode(spec.reflection_mode.value)
    reflection_policy = None
    if reflection_mode is not CognitionReflectionMode.DISABLED:
        reflection_policy = default_reflection_policy(
            allow_provider=reflection_mode is CognitionReflectionMode.LLM_ASSISTED
        )
    _LOG.debug(
        "cognition_config_reflection_mode mode=%s policy_version=%s",
        reflection_mode.value,
        None if reflection_policy is None else reflection_policy.version,
    )
    prospective_mode = CognitionProspectiveMode(spec.prospective_mode.value)
    prospective_policy = None
    if prospective_mode is not CognitionProspectiveMode.DISABLED:
        prospective_policy = default_prospective_policy(
            allow_provider=(prospective_mode is CognitionProspectiveMode.LLM_ASSISTED)
        )
    _LOG.debug(
        "cognition_config_prospective_mode mode=%s policy_version=%s",
        prospective_mode.value,
        None if prospective_policy is None else prospective_policy.version,
    )
    counterfactual_mode = CognitionCounterfactualMode(spec.counterfactual_mode.value)
    counterfactual_policy = None
    if counterfactual_mode is not CognitionCounterfactualMode.DISABLED:
        counterfactual_policy = default_counterfactual_policy(
            allow_provider=(
                counterfactual_mode is CognitionCounterfactualMode.LLM_ASSISTED
            )
        )
    _LOG.debug(
        "cognition_config_counterfactual_mode mode=%s policy_version=%s",
        counterfactual_mode.value,
        None if counterfactual_policy is None else counterfactual_policy.version,
    )
    strategy_mode = CognitionCommunicationStrategyMode(
        spec.communication_strategy_mode.value
    )
    strategy_policy = None
    if strategy_mode is CognitionCommunicationStrategyMode.DETERMINISTIC:
        strategy_policy = default_communication_strategy_policy()
    _LOG.debug(
        "cognition_config_communication_strategy_mode mode=%s policy_version=%s",
        strategy_mode.value,
        None if strategy_policy is None else strategy_policy.version,
    )
    reputation_mode = CognitionReputationMode(spec.reputation_mode.value)
    reputation_policy = None
    if reputation_mode is CognitionReputationMode.DETERMINISTIC:
        reputation_policy = default_reputation_policy()
    _LOG.debug(
        "cognition_config_reputation_mode mode=%s policy_version=%s",
        reputation_mode.value,
        None if reputation_policy is None else reputation_policy.version,
    )
    skill_mode = CognitionSkillLearningMode(spec.skill_learning_mode.value)
    belief_policy = None
    if skill_mode is CognitionSkillLearningMode.DETERMINISTIC:
        belief_policy = CompetenceBeliefPolicy(
            belief_practice_rate=spec.belief_practice_rate,
            belief_success_rate=spec.belief_success_rate,
            belief_failure_rate=spec.belief_failure_rate,
            belief_instruction_rate=spec.belief_instruction_rate,
            belief_observation_rate=spec.belief_observation_rate,
            belief_prior=spec.belief_prior,
            belief_action_weight=spec.belief_action_weight,
            allow_provider=False,
        )
    _LOG.debug(
        "cognition_config_skill_learning_mode mode=%s policy_version=%s",
        skill_mode.value,
        None if belief_policy is None else belief_policy.version,
    )
    from agents.cognition.configuration import (
        CognitionGroupFormationMode,
        CognitionTerritorialClaimMode,
    )
    from agents.cognition.group_formation import default_group_formation_policy
    from agents.cognition.production import (
        ProductionKnowledgeMode as CognitionProductionKnowledgeMode,
    )
    from agents.cognition.teaching import TeachingClaimPolicy
    from agents.cognition.territorial import default_territorial_claim_policy

    teaching_mode = CognitionTeachingInteractionMode(
        spec.teaching_interaction_mode.value
    )
    teaching_policy = None
    teaching_policy_version = None
    if teaching_mode is CognitionTeachingInteractionMode.DETERMINISTIC:
        teaching_policy = TeachingClaimPolicy(
            belief_explain_rate=spec.belief_explain_rate,
            explain_low_below=spec.explain_low_below,
            explain_high_at=spec.explain_high_at,
            teaching_response_weight=spec.teaching_response_weight,
            belief_prior=spec.belief_prior,
        )
        teaching_policy_version = teaching_policy.version
    _LOG.debug(
        "cognition_config_teaching_mode mode=%s policy_version=%s",
        teaching_mode.value,
        teaching_policy_version,
    )
    territorial_mode = CognitionTerritorialClaimMode(spec.territorial_claim_mode.value)
    territorial_policy = None
    if territorial_mode is CognitionTerritorialClaimMode.DETERMINISTIC:
        territorial_policy = default_territorial_claim_policy()
    _LOG.debug(
        "cognition_config_territorial_claim_mode mode=%s policy_version=%s",
        territorial_mode.value,
        None if territorial_policy is None else territorial_policy.version,
    )
    group_mode = CognitionGroupFormationMode(spec.group_formation_mode.value)
    group_policy = None
    if group_mode is CognitionGroupFormationMode.DETERMINISTIC:
        group_policy = default_group_formation_policy()
    _LOG.debug(
        "cognition_config_group_formation_mode mode=%s policy_version=%s",
        group_mode.value,
        None if group_policy is None else group_policy.version,
    )
    from agents.cognition.configuration import CognitionSocialNormMode
    from agents.cognition.social_norms import default_social_norm_policy

    norm_mode = CognitionSocialNormMode(spec.social_norm_mode.value)
    norm_policy = None
    if norm_mode is CognitionSocialNormMode.DETERMINISTIC:
        norm_policy = default_social_norm_policy()
    _LOG.debug(
        "cognition_config_social_norm_mode mode=%s policy_version=%s",
        norm_mode.value,
        None if norm_policy is None else norm_policy.version,
    )
    from agents.cognition.configuration import CognitionSocialConventionMode
    from agents.cognition.social_conventions import default_social_convention_policy

    convention_mode = CognitionSocialConventionMode(spec.social_convention_mode.value)
    convention_policy = None
    if convention_mode is CognitionSocialConventionMode.DETERMINISTIC:
        convention_policy = default_social_convention_policy()
    _LOG.debug(
        "cognition_config_social_convention_mode mode=%s policy_version=%s",
        convention_mode.value,
        None if convention_policy is None else convention_policy.version,
    )
    from agents.cognition.artifacts import ArtifactInterpretationMode
    from agents.cognition.configuration import CognitionSemanticNamingMode
    from agents.cognition.semantic_naming import default_semantic_naming_policy

    artifact_mode = ArtifactInterpretationMode(spec.artifact_interpretation_mode.value)
    _LOG.debug(
        "cognition_config_artifact_interpretation_mode mode=%s",
        artifact_mode.value,
    )
    naming_mode = CognitionSemanticNamingMode(spec.semantic_naming_mode.value)
    naming_policy = None
    if naming_mode is CognitionSemanticNamingMode.DETERMINISTIC:
        naming_policy = default_semantic_naming_policy()
    _LOG.debug(
        "cognition_config_semantic_naming_mode mode=%s policy_version=%s",
        naming_mode.value,
        None if naming_policy is None else naming_policy.version,
    )
    from agents.cognition.budget import policy_from_limits
    from agents.cognition.configuration import (
        CognitionBudgetMode,
        CognitionCulturalNarrativeMode,
    )
    from agents.cognition.cultural_narratives import default_cultural_narrative_policy

    narrative_mode = CognitionCulturalNarrativeMode(
        spec.cultural_narrative_mode.value
    )
    narrative_policy = None
    if narrative_mode is CognitionCulturalNarrativeMode.DETERMINISTIC:
        narrative_policy = default_cultural_narrative_policy()
    _LOG.debug(
        "cognition_config_cultural_narrative_mode mode=%s policy_version=%s",
        narrative_mode.value,
        None if narrative_policy is None else narrative_policy.version,
    )
    budget_mode = CognitionBudgetMode(spec.cognitive_budget_mode.value)
    budget_policy = None
    if budget_mode is CognitionBudgetMode.ENFORCED:
        limits = spec.cognitive_budget_limits
        if limits is None:
            raise ValueError(
                "cognitive_budget_limits required when mode is ENFORCED "
                "(code=limits_required)"
            )
        budget_policy = policy_from_limits(
            max_llm_calls_per_tick=limits.max_llm_calls_per_tick,
            max_tokens_per_tick=limits.max_tokens_per_tick,
            max_imagination_branches=limits.max_imagination_branches,
            max_planning_depth=limits.max_planning_depth,
            max_recalled_memories=limits.max_recalled_memories,
            max_tom_targets=limits.max_tom_targets,
            reflection_interval_ticks=limits.reflection_interval_ticks,
            timeout_seconds=limits.timeout_seconds,
            clock=None,
        )
    _LOG.debug(
        "cognition_config_cognitive_budget_mode mode=%s policy_version=%s",
        budget_mode.value,
        None if budget_policy is None else budget_policy.version,
    )
    return CognitionLoopConfig(
        memory_mode=CognitionMemoryMode(spec.memory_mode.value),
        imagination_mode=CognitionImaginationMode(spec.imagination_mode.value),
        mortality_appraisal_mode=(
            CognitionMortalityAppraisalMode.DISABLED
            if mortality_mode is MortalityMode.DISABLED
            else CognitionMortalityAppraisalMode.ENABLED
        ),
        emotional_state_mode=emotional_mode,
        identity_mode=identity_mode,
        world_model_mode=world_model_mode,
        world_model_policy=world_model_policy,
        theory_of_mind_mode=mind_mode,
        theory_of_mind_policy=mind_policy,
        consolidation_mode=CognitionConsolidationMode(spec.consolidation_mode.value),
        reflection_mode=reflection_mode,
        reflection_policy=reflection_policy,
        prospective_mode=prospective_mode,
        prospective_policy=prospective_policy,
        counterfactual_mode=counterfactual_mode,
        counterfactual_policy=counterfactual_policy,
        communication_strategy_mode=strategy_mode,
        communication_strategy_policy=strategy_policy,
        reputation_mode=reputation_mode,
        reputation_policy=reputation_policy,
        skill_learning_mode=skill_mode,
        competence_belief_policy=belief_policy,
        teaching_interaction_mode=teaching_mode,
        teaching_claim_policy=teaching_policy,
        territorial_claim_mode=territorial_mode,
        territorial_claim_policy=territorial_policy,
        group_formation_mode=group_mode,
        group_formation_policy=group_policy,
        social_norm_mode=norm_mode,
        social_norm_policy=norm_policy,
        social_convention_mode=convention_mode,
        social_convention_policy=convention_policy,
        artifact_interpretation_mode=artifact_mode,
        semantic_naming_mode=naming_mode,
        semantic_naming_policy=naming_policy,
        cultural_narrative_mode=narrative_mode,
        cultural_narrative_policy=narrative_policy,
        cognitive_budget_mode=budget_mode,
        cognitive_budget_policy=budget_policy,
        production_knowledge_mode=CognitionProductionKnowledgeMode(
            spec.production_knowledge_mode.value
        ),
        drive_overrides=tuple(
            CognitionDriveOverride(
                kind=item.kind,
                baseline=item.baseline,
                sensitivity=item.sensitivity,
            )
            for item in spec.drive_overrides
        ),
    )


def _default_provider(
    settings: RunnerProviderSettings,
    credentials: ProviderCredentials,
    *,
    sleep: AsyncSleep | None,
    monotonic: MonotonicClock | None,
    recording_store: RecordingStoreSettings | None = None,
) -> AsyncCloseable:
    if settings.recording_policy is RecordingPolicy.DETERMINISTIC_FAKE:
        _LOG.info(
            "provider_deterministic_fake adapter_kind=%s recording_policy=%s "
            "store_configured=%s",
            settings.adapter_kind.value,
            settings.recording_policy.value,
            False,
        )
        return DeterministicFakeLLMProvider()

    if settings.recording_policy in _RECORDING_STORE_POLICIES:
        if recording_store is None:
            _LOG.error(
                "provider_construction_failed reason=recording_store_required "
                "recording_policy=%s",
                settings.recording_policy.value,
            )
            raise RunnerConstructionError(
                RunnerConstructionErrorCode.PROVIDER_FAILED,
                stage="recording_store_required",
            )
        if monotonic is None:
            raise RunnerConstructionError(
                RunnerConstructionErrorCode.PROVIDER_FAILED,
                stage="provider_clocks",
            )
        inner = _inner_provider_for_recording(
            settings,
            credentials,
            sleep=sleep,
            monotonic=monotonic,
        )
        store = create_filesystem_recording_store(recording_store.root_dir)
        mode = RecordingMode(settings.recording_policy.value)
        _LOG.info(
            "provider_recording_wrap mode=%s adapter_kind=%s store_configured=%s "
            "lookup_mode=%s",
            mode.value,
            settings.adapter_kind.value,
            True,
            recording_store.lookup_mode.value,
        )
        _LOG.debug(
            "recording_store_configured namespace_prefix=%s lookup_mode=%s",
            hashlib.sha256(recording_store.cache_namespace.encode("utf-8")).hexdigest()[
                :12
            ],
            recording_store.lookup_mode.value,
        )
        return wrap_recording_provider(
            inner=inner,
            mode=mode,
            store=store,
            cache_namespace=recording_store.cache_namespace,
            lookup_mode=recording_store.lookup_mode,
            structured_output_mode=settings.structured_output_mode,
            provider_name=(
                "openai_compatible"
                if settings.adapter_kind is ProviderAdapterKind.OPENAI_COMPATIBLE
                else settings.adapter_kind.value
            ),
            model_name=settings.model or "unspecified",
            monotonic=monotonic,
        )

    if settings.adapter_kind is ProviderAdapterKind.DISABLED:
        return DisabledLLMProvider()
    if sleep is None or monotonic is None:
        raise RunnerConstructionError(
            RunnerConstructionErrorCode.PROVIDER_FAILED,
            stage="provider_clocks",
        )
    factory_config = ProviderFactoryConfig(
        adapter_kind=settings.adapter_kind,
        model=settings.model,
        base_url=credentials.base_url,
        api_key=credentials.api_key,
        mode=settings.structured_output_mode,
        temperature=settings.temperature,
        max_attempts=settings.retry_count,
        per_attempt_timeout_seconds=settings.per_attempt_timeout_seconds,
        total_deadline_seconds=settings.total_deadline_seconds,
        max_request_bytes=settings.max_request_bytes,
        max_response_bytes=settings.max_response_bytes,
        max_header_bytes=settings.max_header_bytes,
        send_correlation_header=settings.send_correlation_header,
    )
    _LOG.info(
        "provider_live adapter_kind=%s recording_policy=%s store_configured=%s",
        settings.adapter_kind.value,
        settings.recording_policy.value,
        False,
    )
    return create_llm_provider(factory_config, sleep=sleep, monotonic=monotonic)


def _inner_provider_for_recording(
    settings: RunnerProviderSettings,
    credentials: ProviderCredentials,
    *,
    sleep: AsyncSleep | None,
    monotonic: MonotonicClock,
) -> AsyncCloseable:
    """Build the inner provider for record/cache/replay wraps."""
    if settings.recording_policy is RecordingPolicy.REPLAY:
        # Non-network stub; generate must never be reached on a store hit.
        return DeterministicFakeLLMProvider(provider_name="replay_stub")
    if settings.adapter_kind is ProviderAdapterKind.DISABLED:
        return DisabledLLMProvider()
    if settings.adapter_kind is ProviderAdapterKind.OPENAI_COMPATIBLE:
        if sleep is None:
            raise RunnerConstructionError(
                RunnerConstructionErrorCode.PROVIDER_FAILED,
                stage="provider_clocks",
            )
        return create_llm_provider(
            ProviderFactoryConfig(
                adapter_kind=settings.adapter_kind,
                model=settings.model,
                base_url=credentials.base_url,
                api_key=credentials.api_key,
                mode=settings.structured_output_mode,
                temperature=settings.temperature,
                max_attempts=settings.retry_count,
                per_attempt_timeout_seconds=settings.per_attempt_timeout_seconds,
                total_deadline_seconds=settings.total_deadline_seconds,
                max_request_bytes=settings.max_request_bytes,
                max_response_bytes=settings.max_response_bytes,
                max_header_bytes=settings.max_header_bytes,
                send_correlation_header=settings.send_correlation_header,
            ),
            sleep=sleep,
            monotonic=monotonic,
        )
    return DeterministicFakeLLMProvider()


def _consolidation_selector_for(
    settings: RunnerProviderSettings,
    provider: AsyncCloseable,
    mode: CognitionConsolidationMode,
) -> object | None:
    """Bind a consolidation selector only for LLM-assisted sleep."""
    if mode is not CognitionConsolidationMode.LLM_ASSISTED:
        return None
    from agents.cognition.consolidation import LLMOfflineConsolidationSelector

    if _llm_assisted_provider_bound(settings):
        return LLMOfflineConsolidationSelector(provider)  # type: ignore[arg-type]
    return LLMOfflineConsolidationSelector(None)


def _reflection_selector_for(
    settings: RunnerProviderSettings,
    provider: AsyncCloseable,
    mode: CognitionReflectionMode,
) -> object | None:
    """Bind a reflection selector only for LLM-assisted reflection."""
    if mode is not CognitionReflectionMode.LLM_ASSISTED:
        return None
    from agents.cognition.reflection import LLMReflectionSelector

    if _llm_assisted_provider_bound(settings):
        return LLMReflectionSelector(provider)  # type: ignore[arg-type]
    return LLMReflectionSelector(None)


def _llm_assisted_provider_bound(settings: RunnerProviderSettings) -> bool:
    """Whether LLM-assisted cognition may use the constructed provider."""
    if settings.recording_policy not in _LLM_ASSISTED_POLICIES:
        return False
    if settings.recording_policy is RecordingPolicy.LIVE:
        return settings.adapter_kind is ProviderAdapterKind.OPENAI_COMPATIBLE
    return True


def _reconstructor_for(
    settings: RunnerProviderSettings,
    provider: AsyncCloseable,
) -> MemoryReconstructor:
    if settings.recording_policy is RecordingPolicy.DETERMINISTIC_FAKE:
        return DeterministicMemoryReconstructor()
    if (
        settings.adapter_kind is ProviderAdapterKind.DISABLED
        and settings.recording_policy is RecordingPolicy.LIVE
    ):
        return DeterministicMemoryReconstructor()
    if settings.recording_policy in _LLM_ASSISTED_POLICIES:
        return LLMMemoryReconstructor(provider)  # type: ignore[arg-type]
    return DeterministicMemoryReconstructor()


def _counterpart_resolver(
    translator: RegistrationTranslator,
) -> Callable[[EntityId], AgentId | None]:
    def resolve(entity_id: EntityId) -> AgentId | None:
        try:
            return translator.to_agent_id(entity_id)
        except KeyError:
            return None

    return resolve


def _unwrap_arbiter_decision(decision: object | None) -> AgentCommand | None:
    """Normalize typed arbiter decisions and legacy raw commands."""
    if decision is None:
        return None
    command = getattr(decision, "command", None)
    if command is not None and getattr(decision, "milestone_id", None) is not None:
        return require_agent_command(command)
    return require_agent_command(decision)


@dataclass(frozen=True, slots=True)
class _AgentBundle:
    """Owner-scoped services for one registered agent."""

    runtime: AgentRuntime
    bundle: SubjectiveOwnerBundle
    memory_service: MemoryService
    belief_service: SemanticBeliefService
    relationship_service: RelationshipService
    subjective_state: SubjectiveStateService
    memory_retriever: ReferenceMemoryRetriever | ScopedMemoryRetriever | None = None


class SimulationRunner:
    """Owns configured world engine, agent runtimes, and provider lifecycle."""

    __slots__ = (
        "_agents",
        "_bootstrap",
        "_closed",
        "_cognition_counters",
        "_config",
        "_crash_hook",
        "_diagnostics",
        "_durable",
        "_engine",
        "_factories",
        "_finalized_tick_receipts",
        "_goal_transition_receipts",
        "_injected_stop",
        "_intervention_arbiter",
        "_observation_sink",
        "_pending_finalizations",
        "_provider",
        "_run_config",
        "_run_id",
        "_runtimes",
        "_started",
        "_ticks_committed",
    )

    def __init__(
        self,
        *,
        config: SimulationRunnerConfig,
        run_id: RunId,
        run_config: SimulationRunConfig,
        bootstrap: WorldBootstrap,
        engine: WorldEngine,
        runtimes: Sequence[AgentRuntime],
        agents: Sequence[_AgentBundle],
        provider: AsyncCloseable,
        diagnostics: object,
        durable: PersistentSimulationService | None = None,
        pending_finalizations: PendingFinalizationRepository | None = None,
        observation_sink: ExperimentalObservationSink | None = None,
        crash_hook: Callable[[RunnerCrashPoint, int | None], None] | None = None,
        factories: RunnerDependencyFactories | None = None,
    ) -> None:
        self._config = config
        self._run_id = run_id
        self._run_config = run_config
        self._bootstrap = bootstrap
        self._engine = engine
        self._runtimes = tuple(runtimes)
        self._agents = tuple(agents)
        self._provider = provider
        self._diagnostics = diagnostics
        self._durable = durable
        self._pending_finalizations = pending_finalizations
        self._observation_sink = (
            observation_sink
            if observation_sink is not None
            else ExperimentalObservationSink()
        )
        self._crash_hook = crash_hook
        self._factories = (
            factories if factories is not None else RunnerDependencyFactories()
        )
        self._closed = False
        self._started = False
        self._ticks_committed = 0
        self._injected_stop = False
        self._intervention_arbiter: object | None = None
        self._finalized_tick_receipts: list[FinalizedTickReceipt] = []
        self._goal_transition_receipts: list[GoalTransitionReceipt] = []
        self._cognition_counters = CognitionCounters()

    @property
    def config(self) -> SimulationRunnerConfig:
        return self._config

    @property
    def run_id(self) -> RunId:
        return self._run_id

    @property
    def ticks_committed(self) -> int:
        return self._ticks_committed

    @property
    def run_config(self) -> SimulationRunConfig:
        return self._run_config

    @property
    def bootstrap(self) -> WorldBootstrap:
        return self._bootstrap

    @property
    def engine(self) -> WorldEngine:
        return self._engine

    @property
    def runtimes(self) -> tuple[AgentRuntime, ...]:
        return self._runtimes

    @classmethod
    async def from_config(
        cls,
        config: SimulationRunnerConfig,
        *,
        run_id: RunId | None = None,
        factories: RunnerDependencyFactories | None = None,
    ) -> SimulationRunner:
        """Construct a fully wired runner from immutable configuration.

        Construction failure closes already-created providers/services in
        reverse order and never starts runtimes or exposes a partial runner.
        """
        if type(config) is not SimulationRunnerConfig:
            raise TypeError("from_config requires SimulationRunnerConfig")

        deps = factories if factories is not None else RunnerDependencyFactories()
        if config.persistence.durable and (
            deps.run_repository is None or deps.journal is None
        ):
            raise RunnerConstructionError(
                RunnerConstructionErrorCode.DURABLE_UNSUPPORTED,
                stage="persistence",
            )

        created_closables: list[AsyncCloseable] = []
        created_agents: list[_AgentBundle] = []
        stage = "validate"

        try:
            enabled_flags = config.capability_flags.enabled_names()
            owned_enabled = config.capability_flags.owned_enabled_names()
            unimplemented_flags = config.capability_flags.unimplemented_enabled_names()
            v3_enabled_flags = config.v3_capability_flags.enabled_names()
            v3_unimplemented = (
                config.v3_capability_flags.unimplemented_enabled_names()
            )
            _LOG.debug(
                "runner_construction_start schema_version=%s agent_count=%s "
                "mortality_mode=%s durable=%s capability_flag_count=%s "
                "enabled_flag_count=%s owned_enabled_flag_count=%s "
                "unimplemented_flag_count=%s owned_enabled_flags=%s "
                "unimplemented_flags=%s v3_enabled_flag_count=%s "
                "v3_unimplemented_flag_count=%s",
                config.schema_version,
                len(config.agents),
                config.mortality_mode.value,
                config.persistence.durable,
                len(_V2_CAPABILITY_FLAG_NAMES),
                len(enabled_flags),
                len(owned_enabled),
                len(unimplemented_flags),
                ",".join(owned_enabled) if owned_enabled else "",
                ",".join(unimplemented_flags) if unimplemented_flags else "",
                len(v3_enabled_flags),
                len(v3_unimplemented),
            )
            if unimplemented_flags:
                _LOG.error(
                    "runner_construction_capability_unimplemented "
                    "schema_version=%s flag_count=%s unimplemented_flags=%s "
                    "reason_code=%s",
                    config.schema_version,
                    len(unimplemented_flags),
                    ",".join(unimplemented_flags),
                    RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED.value,
                )
                raise RunnerConstructionError(
                    RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED,
                    stage="capability_flags",
                )
            if v3_unimplemented:
                _LOG.error(
                    "runner_construction_v3_capability_unimplemented "
                    "schema_version=%s flag_count=%s unimplemented_flags=%s "
                    "reason_code=%s",
                    config.schema_version,
                    len(v3_unimplemented),
                    ",".join(v3_unimplemented),
                    RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED.value,
                )
                raise RunnerConstructionError(
                    RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED,
                    stage="v3_capability_flags",
                )

            stage = "physical_rules"
            physical_rules = config.resolve_physical_rules()

            stage = "run_config"
            run_config = SimulationRunConfig(
                seed=config.seed,
                physical_rules=physical_rules,
                derivation_version=config.derivation_version,
                stochastic_identity=config.stochastic_identity,
            )
            resolved_run_id = (
                run_id if run_id is not None else derive_run_id(run_config)
            )
            if type(resolved_run_id) is not RunId:
                raise TypeError("run_id must be RunId")

            stage = "bootstrap"
            registrations = config.ordered_registrations()
            bootstrap = WorldBootstrap(
                world_id=config.scenario.world_id,
                revision=config.scenario.revision,
                locations=config.scenario.locations,
                items=config.scenario.items,
                resources=config.scenario.resources,
                bodies=config.scenario.bodies,
                weather=config.scenario.weather,
                artifacts=config.scenario.artifacts,
                registrations=registrations,
            )
            translator = registration_translator(bootstrap)
            _validate_registration_ownership(config, bootstrap)

            stage = "provider"
            credentials = deps.resolve_credentials(config.provider)
            provider = deps.create_provider(config.provider, credentials)
            created_closables.append(provider)
            _LOG.debug(
                "runner_provider_created adapter_kind=%s recording_policy=%s",
                config.provider.adapter_kind.value,
                config.provider.recording_policy.value,
            )

            stage = "engine"
            skill_ids = tuple(
                agent.entity_id
                for agent in config.agents
                if agent.cognition.skill_learning_mode
                is SkillLearningMode.DETERMINISTIC
            )
            skill_kwargs: dict[str, object] = {}
            if skill_ids:
                from world._skills import ObjectiveSkillPolicy

                rate_spec = config.agents[0].cognition
                skill_kwargs = {
                    "skill_policy": ObjectiveSkillPolicy(
                        practice_rate=rate_spec.practice_rate,
                        success_rate=rate_spec.success_rate,
                        failure_rate=rate_spec.failure_rate,
                        instruction_rate=rate_spec.instruction_rate,
                        observation_rate=rate_spec.observation_rate,
                        probability_gain=rate_spec.probability_gain,
                        efficiency_gain=rate_spec.efficiency_gain,
                    ),
                    "skill_entity_ids": skill_ids,
                }
            teaching_ids = frozenset(
                agent.entity_id
                for agent in config.agents
                if agent.cognition.teaching_interaction_mode
                is TeachingInteractionMode.DETERMINISTIC
            )
            teaching_kwargs: dict[str, object] = {}
            if teaching_ids:
                from world._teaching import TeachingInteractionPolicy

                rate_spec = config.agents[0].cognition
                teaching_kwargs = {
                    "teaching_policy": TeachingInteractionPolicy(
                        demonstration_rate=rate_spec.demonstration_rate,
                        practice_together_rate=rate_spec.practice_together_rate,
                        offer_window=rate_spec.offer_window,
                        belief_explain_rate=rate_spec.belief_explain_rate,
                        explain_low_below=rate_spec.explain_low_below,
                        explain_high_at=rate_spec.explain_high_at,
                        teaching_response_weight=rate_spec.teaching_response_weight,
                        allow_provider=False,
                    ),
                    "teaching_entity_ids": teaching_ids,
                }
            catalog = config.agents[0].cognition.production_catalog
            production_catalog = catalog if catalog.recipe_count > 0 else None
            artifacts_active = bool(bootstrap.artifacts) or config.artifacts_enabled
            lifecycle_channel = (
                config.v3_capability_flags.generational_population
                and config.population_lifecycle is not None
            )
            kinship_channel = (
                config.v3_capability_flags.kinship_inheritance
                and config.kinship is not None
            )
            dependency_care_channel = config.dependency_care is not None
            lifecycle_records = ()
            if lifecycle_channel:
                from simulation.runner_models import seed_bootstrap_lifecycle_records

                lifecycle_records = seed_bootstrap_lifecycle_records(
                    registrations=registrations,
                    spec=config.population_lifecycle,
                    run_config=run_config,
                    run_id=resolved_run_id.value,
                    world_id=config.scenario.world_id.value,
                )
            engine = WorldEngine(
                config=run_config,
                bootstrap=bootstrap,
                run_id=resolved_run_id,
                production_catalog=production_catalog,
                environmental_dynamics=config.environmental_dynamics,
                artifacts_enabled=artifacts_active,
                population_lifecycle=(
                    config.population_lifecycle if lifecycle_channel else None
                ),
                lifecycle_records=lifecycle_records if lifecycle_channel else None,
                new_agent_initialization=(
                    config.new_agent_initialization
                    if (
                        lifecycle_channel
                        and config.schema_version
                        in {
                            RUNNER_SCHEMA_VERSION_V25,
                            RUNNER_SCHEMA_VERSION_V26,
                            RUNNER_SCHEMA_VERSION_V27,
                            RUNNER_SCHEMA_VERSION_V28,
                            RUNNER_SCHEMA_VERSION_V29,
                        }
                        and config.new_agent_initialization is not None
                    )
                    else None
                ),
                kinship_spec=config.kinship if kinship_channel else None,
                dependency_care_spec=(
                    config.dependency_care if dependency_care_channel else None
                ),
                **skill_kwargs,
                **teaching_kwargs,
            )
            _LOG.debug(
                "artifact_write_pair_inputs artifacts_active=%s "
                "seed_artifact_count=%s artifacts_enabled=%s",
                artifacts_active,
                len(bootstrap.artifacts),
                config.artifacts_enabled,
            )
            _LOG.debug(
                "runner_construction_lifecycle_channel lifecycle_channel=%s "
                "bootstrap_lifecycle_record_count=%s owned_v3_flags=%s",
                "on" if lifecycle_channel else "off",
                len(lifecycle_records),
                ",".join(config.v3_capability_flags.owned_enabled_names()),
            )
            from simulation.new_agent_initialization import (
                default_new_agent_initialization_spec,
            )

            if not lifecycle_channel:
                new_agent_init_mode = "off"
                species_defaults_id = "-"
            elif config.new_agent_initialization is None:
                new_agent_init_mode = "default"
                species_defaults_id = (
                    default_new_agent_initialization_spec().species_defaults_id
                )
            else:
                default_payload = (
                    default_new_agent_initialization_spec().canonical_payload()
                )
                explicit = config.new_agent_initialization.canonical_payload()
                new_agent_init_mode = (
                    "default" if explicit == default_payload else "on"
                )
                species_defaults_id = (
                    config.new_agent_initialization.species_defaults_id
                )
            _LOG.info(
                "runner_construction_new_agent_init new_agent_init=%s "
                "species_defaults_id=%s schema_version=%s",
                new_agent_init_mode,
                species_defaults_id,
                config.schema_version,
            )
            developmental_learning_active = config.developmental_learning is not None
            if developmental_learning_active:
                assert config.developmental_learning is not None
                _LOG.info(
                    "runner_construction_developmental_learning "
                    "developmental_learning_active=%s domain_count=%s source_count=%s",
                    True,
                    len(config.developmental_learning.enabled_domains),
                    len(config.developmental_learning.enabled_sources),
                )
            else:
                _LOG.info(
                    "runner_construction_developmental_learning "
                    "developmental_learning_active=%s domain_count=%s source_count=%s",
                    False,
                    0,
                    0,
                )

            stage = "agents"
            memory_run_id = MemoryRunId(resolved_run_id.value)
            scoring_policy = _default_scoring_policy()
            allow_provider = _llm_assisted_provider_bound(config.provider)
            reconstruction_policy = _default_reconstruction_policy(
                allow_provider=allow_provider
            )
            reconstructor = _reconstructor_for(config.provider, provider)
            counterpart = _counterpart_resolver(translator)
            runtimes: list[AgentRuntime] = []
            cognition_trace_repository: CognitionTraceRepository = (
                select_cognition_trace_repository(
                    enabled=config.cognition_trace.enabled,
                    durable=deps.cognition_trace_repository,
                )
            )
            if config.cognition_trace.enabled:
                _LOG.info(
                    "runner_cognition_trace_enabled detail=%s "
                    "sample_every_n_ticks=%s max_bytes_per_invocation=%s",
                    config.cognition_trace.detail.value,
                    config.cognition_trace.sample_every_n_ticks,
                    config.cognition_trace.max_bytes_per_invocation,
                )

            for ordinal, agent_spec in enumerate(config.agents):
                stage = f"agent:{ordinal}"
                owner = agent_spec.agent_id
                if translator.to_entity_id(owner) != agent_spec.entity_id:
                    raise RunnerConstructionError(
                        RunnerConstructionErrorCode.OWNERSHIP,
                        stage=stage,
                    )
                scope = MemoryScope(run_id=memory_run_id, owner_id=owner)
                memory_service = deps.create_memory_service(
                    scope, reconstructor=reconstructor
                )
                belief_service = deps.create_belief_service(scope)
                relationship_service = deps.create_relationship_service(owner)
                owner_bundle = deps.create_subjective_bundle(
                    scope,
                    memory_service=memory_service,
                    belief_service=belief_service,
                    relationship_service=relationship_service,
                )
                # Legacy Belief store remains available for WRITE_BELIEF intents only.
                legacy_beliefs = BeliefStore(owner)
                loop_config = _cognition_config_for(
                    agent_spec.cognition,
                    mortality_mode=config.mortality_mode,
                    capability_flags=config.capability_flags,
                )
                memory_retriever = _memory_retriever_for(
                    agent_spec.cognition.memory_mode,
                    memory_service=memory_service,
                    scoring_policy=scoring_policy,
                    reconstruction_policy=reconstruction_policy,
                    belief_reader=None,
                    emotion_bias=(
                        loop_config.emotional_state_mode
                        is CognitionEmotionalStateMode.ENABLED
                    ),
                )
                cognitive_loop = build_cognitive_loop(
                    loop_config,
                    memory=memory_retriever,
                    resolve_counterpart=counterpart,
                    identity_history=owner_bundle.semantic_belief_reader.history,
                    consolidation_selector=_consolidation_selector_for(
                        config.provider,
                        provider,
                        loop_config.consolidation_mode,
                    ),
                    reflection_selector=_reflection_selector_for(
                        config.provider,
                        provider,
                        loop_config.reflection_mode,
                    ),
                    **_caregiving_loop_kwargs(config),
                    **_developmental_learning_loop_kwargs(config),
                )
                agent = Agent(
                    agent_id=owner,
                    name=(
                        agent_spec.name if agent_spec.name is not None else owner.value
                    ),
                    goals=agent_spec.initial_goals,
                    drives=agent_spec.cognition.resolve_drive_profile(),
                )
                runtime = AgentRuntime(
                    agent=agent,
                    translator=translator,
                    cognitive_loop=cognitive_loop,
                    memory_reader=owner_bundle.memory_reader,
                    memory_writer=MemoryStore(owner),
                    belief_reader=legacy_beliefs,
                    belief_writer=legacy_beliefs,
                    memory_service=memory_service,
                    semantic_belief_reader=owner_bundle.semantic_belief_reader,
                    relationship_reader=owner_bundle.relationship_reader,
                    subjective_state=owner_bundle.commit_service,
                    run_id=resolved_run_id,
                    cognition_trace_repository=cognition_trace_repository,
                    cognition_trace_spec=config.cognition_trace,
                    scientific_evidence=deps.scientific_evidence,
                )
                bundle = _AgentBundle(
                    runtime=runtime,
                    bundle=owner_bundle,
                    memory_service=memory_service,
                    belief_service=belief_service,
                    relationship_service=relationship_service,
                    subjective_state=owner_bundle.commit_service,
                    memory_retriever=memory_retriever,
                )
                created_agents.append(bundle)
                runtimes.append(runtime)
                _LOG.debug(
                    "runner_agent_constructed ordinal=%s memory_mode=%s "
                    "imagination_mode=%s mortality_mode=%s "
                    "emotional_state_mode=%s short_term_emotional_state=%s "
                    "identity_mode=%s extended_self_model=%s "
                    "world_model_mode=%s predictive_world_model=%s "
                    "allow_provider=%s",
                    ordinal,
                    agent_spec.cognition.memory_mode.value,
                    agent_spec.cognition.imagination_mode.value,
                    config.mortality_mode.value,
                    loop_config.emotional_state_mode.value,
                    config.capability_flags.short_term_emotional_state,
                    loop_config.identity_mode.value,
                    config.capability_flags.extended_self_model,
                    loop_config.world_model_mode.value,
                    config.capability_flags.predictive_world_model,
                    allow_provider,
                )

            diagnostics = build_runner_diagnostics(config)
            fields = describe_runner_config(diagnostics)
            durable_service: PersistentSimulationService | None = None
            if config.persistence.durable:
                stage = "durable_create_run"
                assert deps.run_repository is not None
                assert deps.journal is not None
                bootstrap_snapshot = _bootstrap_snapshot(engine)
                await deps.run_repository.create_run(
                    RunCreateRequest(
                        run_id=resolved_run_id,
                        world_id=bootstrap.world_id,
                        seed=run_config.seed,
                        config=run_config,
                        derivation_version=(
                            run_config.derivation_version or DERIVATION_VERSION_V3
                        ),
                        event_schema_version=bootstrap_snapshot.event_schema_version,
                        projector_version=PROJECTOR_VERSION,
                        persistence_codec_version=(
                            bootstrap_snapshot.persistence_codec_version
                        ),
                        bootstrap=bootstrap_snapshot,
                    )
                )
                durable_service = PersistentSimulationService(engine, deps.journal)
                _LOG.info(
                    "runner_durable_service_ready run_id=%s",
                    resolved_run_id.value,
                )
            _LOG.info(
                "runner_constructed run_id=%s world_id=%s agent_count=%s "
                "config_fingerprint_prefix=%s scenario_fingerprint_prefix=%s "
                "cognition_fingerprint_prefix=%s rules_fingerprint_prefix=%s "
                "mortality_mode=%s durable=%s",
                resolved_run_id.value,
                bootstrap.world_id.value,
                len(runtimes),
                fields["config_fingerprint_prefix"],
                fields["scenario_fingerprint_prefix"],
                fields["cognition_fingerprint_prefix"],
                fields["rules_fingerprint_prefix"],
                config.mortality_mode.value,
                config.persistence.durable,
            )
            return cls(
                config=config,
                run_id=resolved_run_id,
                run_config=run_config,
                bootstrap=bootstrap,
                engine=engine,
                runtimes=runtimes,
                agents=created_agents,
                provider=provider,
                diagnostics=diagnostics,
                durable=durable_service,
                pending_finalizations=deps.pending_finalizations,
                factories=deps,
            )
        except RunnerConstructionError:
            await _cleanup_created(created_closables, stage=stage)
            raise
        except Exception:
            _LOG.error(
                "runner_construction_failed code=%s stage=%s",
                RunnerConstructionErrorCode.FACTORY_FAILED.value,
                stage,
            )
            await _cleanup_created(created_closables, stage=stage)
            raise RunnerConstructionError(
                RunnerConstructionErrorCode.FACTORY_FAILED,
                stage=stage,
            ) from None

    def request_stop(self) -> None:
        """Request stop at the next fully finalized committed boundary."""
        if not self._config.stop_policy.allow_injected_stop:
            raise RunnerConstructionError(
                RunnerConstructionErrorCode.INVALID_CONFIG,
                stage="injected_stop",
            )
        self._injected_stop = True
        _LOG.info("runner_stop_requested run_id=%s", self._run_id.value)

    def set_intervention_arbiter(self, arbiter: object | None) -> None:
        """Attach a trusted pre-admission intervention arbiter (experiments only)."""
        self._intervention_arbiter = arbiter

    def _acknowledge_arbiter(self, resolutions: Sequence[ActionResolution]) -> None:
        """Acknowledge one-shot arbiter status from committed resolutions."""
        arbiter = self._intervention_arbiter
        if arbiter is None:
            return
        acknowledge = getattr(arbiter, "acknowledge_resolutions", None)
        if callable(acknowledge):
            acknowledge(resolutions)
            return
        mark = getattr(arbiter, "mark_committed", None)
        if not callable(mark):
            return
        # Legacy arbiter path when acknowledge_resolutions is unavailable.
        for resolution in resolutions:
            if type(resolution) is not ActionResolution:
                continue
            accepted = resolution.status is ActionResolutionStatus.APPLIED
            mark(accepted=accepted)
            break

    def set_crash_hook(
        self,
        hook: Callable[[RunnerCrashPoint, int | None], None] | None,
    ) -> None:
        """Install a fault-injection hook for recovery tests (never production)."""
        self._crash_hook = hook

    def set_observation_sink(self, sink: ExperimentalObservationSink) -> None:
        """Replace the post-finalization observation sink."""
        if type(sink) is not ExperimentalObservationSink and not hasattr(
            sink, "deliver"
        ):
            raise TypeError("sink must implement deliver()")
        self._observation_sink = sink

    def _maybe_crash(
        self, point: RunnerCrashPoint, *, ordinal: int | None = None
    ) -> None:
        if self._crash_hook is None:
            return
        self._crash_hook(point, ordinal)

    def _ensure_started(self) -> None:
        if self._started:
            return
        for runtime in self._runtimes:
            if runtime.status is AgentRuntimeStatus.CREATED:
                runtime.start()
        self._started = True
        _LOG.info(
            "runner_started run_id=%s agent_count=%s max_ticks=%s",
            self._run_id.value,
            len(self._runtimes),
            self._config.stop_policy.max_ticks,
        )
        _LOG.info(
            "[simulation.runner] prepare_parallel enabled=%s agent_count=%s",
            False,
            len(self._runtimes),
        )

    def _bind_developmental_entity_learning_rates(self, tick: int) -> None:
        """Publish objective learning_rate_by_entity into each cognitive loop."""
        if getattr(self._config, "developmental_learning", None) is None:
            return
        raw = self._engine.learning_rate_by_entity(tick=tick)
        rates = {
            entity_id.value: float(factor) for entity_id, factor in raw.items()
        }
        for runtime in self._runtimes:
            binder = getattr(
                runtime, "bind_developmental_entity_learning_rates", None
            )
            if callable(binder):
                binder(rates)
        _LOG.debug(
            "developmental_entity_learning_rates_published run_id=%s tick=%s "
            "entity_count=%s",
            self._run_id.value,
            tick,
            len(rates),
        )

    async def run_tick(self) -> RunnerAttemptReceipt:
        """Observe, prepare, bind, commit, and finalize one tick."""
        if self._closed:
            raise RunnerConstructionError(
                RunnerConstructionErrorCode.INVALID_CONFIG,
                stage="closed",
            )
        self._ensure_started()
        if self._ticks_committed >= self._config.stop_policy.max_ticks:
            return RunnerAttemptReceipt(
                tick=self._ticks_committed,
                status=RunnerAttemptStatus.ABORTED,
                submission_count=0,
                finalized_count=0,
                stop_reason=RunnerStopReasonCode.MAX_TICKS,
            )

        batch = self._engine.observe()
        tick_value = batch.tick.value
        _LOG.debug(
            "runner_tick_observe run_id=%s tick=%s registration_count=%s",
            self._run_id.value,
            tick_value,
            len(self._runtimes),
        )
        self._bind_developmental_entity_learning_rates(tick_value)

        pendings: list[PendingRuntimeFinalization] = []
        commands: list[FinalizationCommand] = []
        submissions: list[ActionSubmission] = []

        try:
            for ordinal, runtime in enumerate(self._runtimes):
                observation = self._engine.observation_for(runtime.agent_id)
                prepared = await runtime.prepare_observation(
                    observation, token=batch.token
                )
                if type(prepared) is not PreparedObservation:
                    _LOG.debug(
                        "runner_agent_terminal_skip run_id=%s tick=%s ordinal=%s",
                        self._run_id.value,
                        tick_value,
                        ordinal,
                    )
                    continue
                effective = None
                arbiter = self._intervention_arbiter
                if arbiter is not None:
                    maybe = getattr(arbiter, "maybe_replace", None)
                    if callable(maybe):
                        proposed = prepared.proposal.proposed_command
                        decision = maybe(
                            tick=tick_value,
                            agent_id=runtime.agent_id,
                            proposed_command=proposed,
                        )
                        effective = _unwrap_arbiter_decision(decision)
                pending = await runtime.bind_effective_command(
                    prepared, effective_command=effective
                )
                command = pending.to_finalization_command(run_id=self._run_id)
                assert type(command) is FinalizationCommand
                pendings.append(pending)
                commands.append(command)
                submissions.append(pending.submission)

            if not submissions and all(
                runtime.status is AgentRuntimeStatus.TERMINAL
                for runtime in self._runtimes
            ):
                tick_result = await self._commit_tick(())
                await self._sync_mid_run_population_entries()
                await self._record_finalized_tick(tick_result, pendings=())
                self._ticks_committed += 1
                return RunnerAttemptReceipt(
                    tick=tick_value,
                    status=RunnerAttemptStatus.FINALIZED,
                    submission_count=0,
                    finalized_count=0,
                    stop_reason=RunnerStopReasonCode.ALL_AGENTS_TERMINAL,
                )

            if self._pending_finalizations is not None:
                for command in commands:
                    await self._pending_finalizations.append_pending(
                        _pending_record_from_command(command)
                    )
                    _LOG.debug(
                        "runner_pending_recorded run_id=%s tick=%s "
                        "invocation_id=%s codec_version=%s",
                        self._run_id.value,
                        tick_value,
                        command.invocation_id,
                        command.codec_version,
                    )

            self._maybe_crash(RunnerCrashPoint.BEFORE_OBJECTIVE_COMMIT)
            tick_result = await self._commit_tick(tuple(submissions))
            _LOG.debug(
                "runner_tick_committed run_id=%s tick=%s submission_count=%s",
                self._run_id.value,
                tick_value,
                len(submissions),
            )
            await self._sync_mid_run_population_entries()
            self._acknowledge_arbiter(tick_result.resolutions)
            self._maybe_crash(RunnerCrashPoint.AFTER_OBJECTIVE_COMMIT)

            finalized = await self._finalize_and_acknowledge(
                pendings=tuple(pendings),
                commands=tuple(commands),
                tick_result=tick_result,
            )
            stop_reason = self._evaluate_stop()
            _LOG.info(
                "runner_tick_finalized run_id=%s tick=%s submission_count=%s "
                "finalized_count=%s stop_reason=%s",
                self._run_id.value,
                tick_value,
                len(submissions),
                finalized,
                "-" if stop_reason is None else stop_reason.value,
            )
            return RunnerAttemptReceipt(
                tick=tick_value,
                status=RunnerAttemptStatus.FINALIZED,
                submission_count=len(submissions),
                finalized_count=finalized,
                stop_reason=stop_reason,
            )
        except RunnerCrashInjected as crash:
            _LOG.warning(
                "runner_crash_injected run_id=%s tick=%s point=%s",
                self._run_id.value,
                tick_value,
                crash.point.value,
            )
            if crash.point is RunnerCrashPoint.BEFORE_OBJECTIVE_COMMIT:
                for pending in reversed(pendings):
                    try:
                        self._runtimes_by_agent(
                            pending.submission.agent_id
                        ).abort_pending(pending)
                    except AgentRuntimeError:
                        pass
                if self._pending_finalizations is not None:
                    for command in commands:
                        try:
                            await self._pending_finalizations.mark_aborted(
                                run_id=self._run_id,
                                agent_id=command.agent_id.value,
                                invocation_id=command.invocation_id,
                            )
                        except Exception:
                            _LOG.error(
                                "runner_pending_abort_failed run_id=%s "
                                "invocation_id=%s",
                                self._run_id.value,
                                command.invocation_id,
                            )
            raise
        except AgentRuntimeError:
            for pending in reversed(pendings):
                try:
                    self._runtimes_by_agent(pending.submission.agent_id).abort_pending(
                        pending
                    )
                except AgentRuntimeError:
                    pass
            if self._pending_finalizations is not None:
                for command in commands:
                    try:
                        await self._pending_finalizations.mark_aborted(
                            run_id=self._run_id,
                            agent_id=command.agent_id.value,
                            invocation_id=command.invocation_id,
                        )
                    except Exception:
                        _LOG.error(
                            "runner_pending_abort_failed run_id=%s invocation_id=%s",
                            self._run_id.value,
                            command.invocation_id,
                        )
            policy = self._config.cognition_failure_policy
            _LOG.error(
                "runner_cognition_failed run_id=%s tick=%s policy=%s",
                self._run_id.value,
                tick_value,
                policy.value,
            )
            if policy is CognitionFailurePolicy.ABORT_TICK:
                return RunnerAttemptReceipt(
                    tick=tick_value,
                    status=RunnerAttemptStatus.ABORTED,
                    submission_count=len(submissions),
                    finalized_count=0,
                    stop_reason=RunnerStopReasonCode.COGNITION_FAILURE,
                )
            raise
        except Exception as exc:
            for pending in reversed(pendings):
                try:
                    self._runtimes_by_agent(pending.submission.agent_id).abort_pending(
                        pending
                    )
                except AgentRuntimeError:
                    pass
            _LOG.error(
                "runner_authority_failed run_id=%s tick=%s reason=%s",
                self._run_id.value,
                tick_value,
                type(exc).__name__,
                exc_info=True,
            )
            return RunnerAttemptReceipt(
                tick=tick_value,
                status=RunnerAttemptStatus.ABORTED,
                submission_count=len(submissions),
                finalized_count=0,
                stop_reason=RunnerStopReasonCode.AUTHORITY_FAILURE,
            )

    async def _finalize_and_acknowledge(
        self,
        *,
        pendings: tuple[PendingRuntimeFinalization, ...],
        commands: tuple[FinalizationCommand, ...],
        tick_result: TickResult | None,
        record_receipt: bool = True,
    ) -> int:
        finalized = 0
        for ordinal, (pending, command) in enumerate(
            zip(pendings, commands, strict=True)
        ):
            self._maybe_crash(
                RunnerCrashPoint.DURING_OWNER_FINALIZATION, ordinal=ordinal
            )
            runtime = self._runtimes_by_agent(pending.submission.agent_id)
            await runtime.finalize_pending(pending)
            self._maybe_crash(
                RunnerCrashPoint.BEFORE_COLLECTOR_PUBLICATION, ordinal=ordinal
            )
            assert command.delivery_id is not None
            assert command.delivery_content_hash is not None
            delivery = ObservationDelivery(
                delivery_id=command.delivery_id,
                content_hash=command.delivery_content_hash,
                tick=command.tick,
                kind="finalized_tick_owner",
            )
            ack = self._observation_sink.deliver(delivery)
            _LOG.debug(
                "runner_delivery_ack run_id=%s tick=%s delivery_id=%s",
                self._run_id.value,
                command.tick,
                ack.delivery_id,
            )
            self._maybe_crash(RunnerCrashPoint.AFTER_ACKNOWLEDGEMENT, ordinal=ordinal)
            if self._pending_finalizations is not None:
                await self._pending_finalizations.mark_finalized(
                    run_id=self._run_id,
                    agent_id=command.agent_id.value,
                    invocation_id=command.invocation_id,
                )
            finalized += 1
            _LOG.info(
                "runner_owner_finalized run_id=%s tick=%s invocation_id=%s ordinal=%s",
                self._run_id.value,
                command.tick,
                command.invocation_id,
                ordinal,
            )
        if record_receipt and tick_result is not None:
            already = any(
                receipt.tick == tick_result.tick.value
                for receipt in self._finalized_tick_receipts
            )
            if not already:
                await self._record_finalized_tick(tick_result, pendings=pendings)
            if self._ticks_committed <= tick_result.tick.value:
                self._ticks_committed = tick_result.tick.value + 1
        return finalized

    async def recover_pending_finalizations(self) -> RunnerAttemptReceipt:
        """Complete pending subjective finalizations without rerunning cognition.

        Distinguishes pending-subjective recovery from continued execution.
        Committed objective history is never rolled back or duplicated.
        """
        self._ensure_started()
        if self._pending_finalizations is None:
            plan = classify_resume_mode(
                run_id=self._run_id,
                ticks_committed=self._ticks_committed,
                engine_tick=self._engine.tick.value,
                pending_count=0,
                pending_tick=None,
            )
            _LOG.debug(
                "runner_recovery_noop run_id=%s mode=%s ticks_committed=%s",
                self._run_id.value,
                plan.mode.value,
                self._ticks_committed,
            )
            return RunnerAttemptReceipt(
                tick=self._ticks_committed,
                status=RunnerAttemptStatus.FINALIZED,
                submission_count=0,
                finalized_count=0,
            )

        records = await self._pending_finalizations.list_pending_for_run(
            run_id=self._run_id
        )
        plan = classify_resume_mode(
            run_id=self._run_id,
            ticks_committed=self._ticks_committed,
            engine_tick=self._engine.tick.value,
            pending_count=len(records),
            pending_tick=None if not records else records[0].tick,
        )
        _LOG.debug(
            "runner_recovery_boundary run_id=%s mode=%s pending_count=%s "
            "ticks_committed=%s engine_tick=%s",
            self._run_id.value,
            plan.mode.value,
            plan.pending_count,
            plan.ticks_committed,
            self._engine.tick.value,
        )
        if plan.mode is ResumeMode.CONTINUED_EXECUTION:
            return RunnerAttemptReceipt(
                tick=self._ticks_committed,
                status=RunnerAttemptStatus.FINALIZED,
                submission_count=0,
                finalized_count=0,
            )
        if plan.mode is ResumeMode.OBJECTIVE_REPLAY:
            _LOG.info(
                "runner_objective_replay_required run_id=%s ticks_committed=%s "
                "engine_tick=%s",
                self._run_id.value,
                self._ticks_committed,
                self._engine.tick.value,
            )
            # Objective authority already advanced; align runner cursor only.
            self._ticks_committed = self._engine.tick.value
            return RunnerAttemptReceipt(
                tick=self._ticks_committed,
                status=RunnerAttemptStatus.FINALIZED,
                submission_count=0,
                finalized_count=0,
            )

        # PENDING_SUBJECTIVE_RECOVERY
        by_tick: dict[int, list[FinalizationCommand]] = {}
        for record in records:
            command = _command_from_pending_record(record)
            by_tick.setdefault(command.tick, []).append(command)

        total_finalized = 0
        last_tick = self._ticks_committed
        for tick in sorted(by_tick):
            commands = tuple(by_tick[tick])
            pendings: list[PendingRuntimeFinalization] = []
            for command in commands:
                runtime = self._runtimes_by_agent(command.agent_id)
                pending = runtime.restore_pending_from_command(command)
                pendings.append(pending)
            # Objective already committed for this tick; synthesize receipt cursor.
            resulting_tick = Tick(tick + 1)
            if self._engine.tick.value < resulting_tick.value:
                _LOG.error(
                    "runner_recovery_corrupt run_id=%s code=objective_not_committed "
                    "tick=%s engine_tick=%s",
                    self._run_id.value,
                    tick,
                    self._engine.tick.value,
                )
                for command in commands:
                    await self._pending_finalizations.mark_aborted(
                        run_id=self._run_id,
                        agent_id=command.agent_id.value,
                        invocation_id=command.invocation_id,
                    )
                return RunnerAttemptReceipt(
                    tick=tick,
                    status=RunnerAttemptStatus.ABORTED,
                    submission_count=len(commands),
                    finalized_count=0,
                    stop_reason=RunnerStopReasonCode.AUTHORITY_FAILURE,
                )
            revision = self._engine.revision
            tick_result = TickResult(
                tick=Tick(tick),
                resulting_tick=resulting_tick,
                base_revision=WorldRevision(max(0, revision.value - 1)),
                resulting_revision=revision if revision.value > 0 else WorldRevision(0),
                resolutions=(),
                events=(),
            )
            # Fix revision pairing when engine revision did not advance.
            if tick_result.resulting_revision.value < tick_result.base_revision.value:
                tick_result = TickResult(
                    tick=Tick(tick),
                    resulting_tick=resulting_tick,
                    base_revision=WorldRevision(0),
                    resulting_revision=WorldRevision(0),
                    resolutions=(),
                    events=(),
                )
            elif (
                tick_result.resulting_revision.value
                > tick_result.base_revision.value + 1
            ):
                tick_result = TickResult(
                    tick=Tick(tick),
                    resulting_tick=resulting_tick,
                    base_revision=WorldRevision(revision.value),
                    resulting_revision=WorldRevision(revision.value),
                    resolutions=(),
                    events=(),
                )
            finalized = await self._finalize_and_acknowledge(
                pendings=tuple(pendings),
                commands=commands,
                tick_result=tick_result,
            )
            total_finalized += finalized
            last_tick = tick
            _LOG.info(
                "runner_pending_recovered run_id=%s tick=%s finalized_count=%s",
                self._run_id.value,
                tick,
                finalized,
            )
        return RunnerAttemptReceipt(
            tick=last_tick,
            status=RunnerAttemptStatus.FINALIZED,
            submission_count=total_finalized,
            finalized_count=total_finalized,
            stop_reason=self._evaluate_stop(),
        )

    def export_runtime_checkpoint(self) -> RunnerRuntimeCheckpoint:
        """Export rehydratable runner state (no subjective payloads)."""
        pending_tick = None
        pending_count = 0
        states = tuple(
            runtime.export_runtime_checkpoint() for runtime in self._runtimes
        )
        return RunnerRuntimeCheckpoint(
            run_id=self._run_id,
            ticks_committed=self._ticks_committed,
            engine_tick=self._engine.tick.value,
            engine_revision=self._engine.revision.value,
            runtime_states=states,  # type: ignore[arg-type]
            finalized_tick_receipts=tuple(self._finalized_tick_receipts),
            goal_transition_receipts=tuple(self._goal_transition_receipts),
            cognition_counters=self._cognition_counters,
            pending_tick=pending_tick,
            pending_count=pending_count,
        )

    def apply_runtime_checkpoint(self, checkpoint: RunnerRuntimeCheckpoint) -> None:
        """Restore runner cursors and per-owner runtime state after construction."""
        if type(checkpoint) is not RunnerRuntimeCheckpoint:
            raise TypeError("checkpoint must be RunnerRuntimeCheckpoint")
        if checkpoint.run_id != self._run_id:
            raise ValueError("run_id mismatch")
        by_agent = {state.agent_id: state for state in checkpoint.runtime_states}
        for runtime in self._runtimes:
            state = by_agent.get(runtime.agent_id)
            if state is None:
                continue
            runtime.restore_runtime_checkpoint(state)
        self._ticks_committed = checkpoint.ticks_committed
        self._finalized_tick_receipts = list(checkpoint.finalized_tick_receipts)
        self._goal_transition_receipts = list(checkpoint.goal_transition_receipts)
        self._cognition_counters = checkpoint.cognition_counters
        self._started = True
        _LOG.info(
            "runner_rehydrated run_id=%s ticks_committed=%s runtime_count=%s",
            self._run_id.value,
            self._ticks_committed,
            len(checkpoint.runtime_states),
        )

    def classify_resume(
        self, *, pending_count: int, pending_tick: int | None
    ) -> RunnerResumePlan:
        """Classify resume mode from durable pending and engine cursors."""
        return classify_resume_mode(
            run_id=self._run_id,
            ticks_committed=self._ticks_committed,
            engine_tick=self._engine.tick.value,
            pending_count=pending_count,
            pending_tick=pending_tick,
        )

    async def run(self) -> SimulationRunnerResult:
        """Run until a closed stop reason is reached at a finalized boundary."""
        self._ensure_started()
        receipts: list[RunnerAttemptReceipt] = []
        stop_reason: RunnerStopReasonCode | None = None
        while stop_reason is None:
            receipt = await self.run_tick()
            receipts.append(receipt)
            if receipt.status is RunnerAttemptStatus.ABORTED:
                stop_reason = (
                    receipt.stop_reason
                    if receipt.stop_reason is not None
                    else RunnerStopReasonCode.AUTHORITY_FAILURE
                )
                break
            stop_reason = receipt.stop_reason
            if (
                stop_reason is None
                and self._ticks_committed >= self._config.stop_policy.max_ticks
            ):
                stop_reason = RunnerStopReasonCode.MAX_TICKS
        assert stop_reason is not None
        projection = self.final_objective_projection()
        objective_hash = objective_projection_hash(projection)
        goal_receipts = self._evaluate_goals_at_boundary(
            tick=max(0, self._ticks_committed - 1) if self._ticks_committed else 0,
            run_ending=True,
            projection=projection,
        )
        self._goal_transition_receipts.extend(goal_receipts)
        await self._apply_objective_goal_receipts(goal_receipts)
        audits = self.export_memory_dynamics_audits()
        consolidation_audits = self.export_offline_consolidation_audits()
        reflection_audits = self.export_reflection_audits()
        result = SimulationRunnerResult(
            run_id=self._run_id,
            ticks_committed=self._ticks_committed,
            stop_reason=stop_reason,
            attempt_receipts=tuple(receipts),
            finalized_tick_receipts=tuple(self._finalized_tick_receipts),
            goal_transition_receipts=tuple(self._goal_transition_receipts),
            cognition_counters=self._cognition_counters,
            final_objective_projection=projection,
            objective_state_hash=objective_hash,
            memory_dynamics_audits=audits,
            offline_consolidation_audits=consolidation_audits,
            reflection_audits=reflection_audits,
            world_model_audits=self.export_world_model_audits(),
            mind_audits=self.export_mind_audits(),
            prospective_audits=self.export_prospective_audits(),
            counterfactual_audits=self.export_counterfactual_audits(),
            communication_intent_audits=self.export_communication_intent_audits(),
            cognitive_budget_audits=self.export_cognitive_budget_audits(),
            skill_audits=self.export_skill_audits(),
            teaching_audits=self.export_teaching_audits(),
            developmental_acquisition_audits=(
                self.export_developmental_acquisition_audits()
            ),
        )
        _LOG.info(
            "runner_finished run_id=%s ticks_committed=%s stop_reason=%s "
            "attempt_count=%s finalized_tick_count=%s goal_transition_count=%s "
            "objective_hash_prefix=%s memory_dynamics_audit_count=%s",
            self._run_id.value,
            self._ticks_committed,
            stop_reason.value,
            len(receipts),
            len(self._finalized_tick_receipts),
            len(self._goal_transition_receipts),
            objective_hash[:12],
            len(audits),
        )
        return result

    def export_memory_dynamics_audits(self) -> tuple[object, ...]:
        """Harvest in-run V2 recall audits from scoped retrievers (IDs only)."""
        from agents.cognition.memory import ScopedMemoryRetriever
        from memory.models import RecallAuditRecord

        collected: list[RecallAuditRecord] = []
        for bundle in self._agents:
            retriever = bundle.memory_retriever
            if type(retriever) is not ScopedMemoryRetriever:
                continue
            for audit in retriever.export_audits():
                if type(audit) is not RecallAuditRecord:
                    raise TypeError("memory_dynamics_audits: invalid_item")
                collected.append(audit)
        _LOG.debug(
            "memory_dynamics_audit_export",
            extra={
                "runner": {
                    "run_id": self._run_id.value,
                    "audit_export_count": len(collected),
                }
            },
        )
        return tuple(collected)

    def export_counterfactual_audits(self) -> tuple[object, ...]:
        """Harvest counterfactual audits. Not part of result JSON."""
        from agents.cognition.counterfactual import CounterfactualAudit

        collected: list[CounterfactualAudit] = []
        for bundle in self._agents:
            runtime = bundle.runtime
            export = getattr(runtime, "export_counterfactual_audits", None)
            if export is None:
                continue
            for audit in export():
                if type(audit) is not CounterfactualAudit:
                    raise TypeError("counterfactual_audits: invalid_item")
                collected.append(audit)
                _LOG.debug(
                    "counterfactual_audit run_id=%s owner_id=%s tick=%s "
                    "scenario_count=%s regret_count=%s fallback_used=%s",
                    self._run_id.value,
                    audit.owner_id.value,
                    audit.tick,
                    audit.scenario_count,
                    audit.regret_count,
                    audit.fallback_used,
                )
        return tuple(collected)

    def export_prospective_audits(self) -> tuple[object, ...]:
        """Harvest prospective audits. Not part of result JSON."""
        from agents.cognition.prospective import ProspectiveAudit

        collected: list[ProspectiveAudit] = []
        for bundle in self._agents:
            runtime = bundle.runtime
            export = getattr(runtime, "export_prospective_audits", None)
            if export is None:
                continue
            for audit in export():
                if type(audit) is not ProspectiveAudit:
                    raise TypeError("prospective_audits: invalid_item")
                collected.append(audit)
                _LOG.debug(
                    "prospective_audit run_id=%s owner_id=%s tick=%s "
                    "expanded_count=%s pruned_count=%s timeout_hit=%s",
                    self._run_id.value,
                    audit.owner_id.value,
                    audit.tick,
                    audit.expanded_count,
                    audit.pruned_count,
                    audit.timeout_hit,
                )
        _LOG.debug(
            "prospective_audit run_id=%s audit_count=%s",
            self._run_id.value,
            len(collected),
        )
        return tuple(collected)

    def export_cognitive_budget_audits(self) -> tuple[object, ...]:
        """Harvest cognitive budget audits. Not part of result JSON."""
        from agents.cognition.budget import CognitiveBudgetAudit

        collected: list[CognitiveBudgetAudit] = []
        for bundle in self._agents:
            runtime = bundle.runtime
            export = getattr(runtime, "export_cognitive_budget_audits", None)
            if export is None:
                continue
            for audit in export():
                if type(audit) is not CognitiveBudgetAudit:
                    raise TypeError("cognitive_budget_audits: invalid_item")
                collected.append(audit)
                _LOG.debug(
                    "cognitive_budget_audit_exported run_id=%s agent_id=%s "
                    "tick=%s exhausted_count=%s",
                    self._run_id.value,
                    audit.owner_id.value,
                    audit.tick,
                    len(audit.exhausted_reasons),
                )
        return tuple(collected)

    def export_communication_intent_audits(self) -> tuple[object, ...]:
        """Harvest per-utterance strategy audits. Not part of result JSON."""
        from agents.cognition.communication_strategy import CommunicationIntentAudit

        collected: list[CommunicationIntentAudit] = []
        for bundle in self._agents:
            runtime = bundle.runtime
            export = getattr(runtime, "export_communication_intent_audits", None)
            if export is None:
                continue
            for audit in export():
                if type(audit) is not CommunicationIntentAudit:
                    raise TypeError("communication_intent_audits: invalid_item")
                collected.append(audit)
        _LOG.debug(
            "communication_intent_audit_export run_id=%s audit_count=%s",
            self._run_id.value,
            len(collected),
        )
        return tuple(collected)

    def export_developmental_acquisition_audits(self) -> tuple[object, ...]:
        """Harvest metadata-only developmental acquisition audits."""
        from agents.cognition.developmental_learning import (
            DevelopmentalAcquisitionAudit,
        )

        collected: list[DevelopmentalAcquisitionAudit] = []
        for runtime in self._runtimes:
            export = getattr(
                runtime, "export_developmental_acquisition_audits", None
            )
            if export is None:
                continue
            for audit in export():
                if type(audit) is not DevelopmentalAcquisitionAudit:
                    raise TypeError(
                        "developmental_acquisition_audits: invalid_item"
                    )
                collected.append(audit)
        _LOG.debug(
            "developmental_acquisition_audit_export run_id=%s audit_count=%s",
            self._run_id.value,
            len(collected),
        )
        return tuple(collected)

    def export_skill_audits(self) -> tuple[SkillAudit, ...]:
        """Harvest objective and subjective skill rows. Not part of result JSON."""
        from world._skills import SkillDomain

        ledger = self._engine._skill_ledger
        if ledger is None:
            return ()
        tick = self._engine.tick.value
        agent_for = {agent.entity_id: agent.agent_id for agent in self._config.agents}
        rows: list[SkillAudit] = []
        for entity_id in ledger.entity_ids():
            agent_id = agent_for.get(entity_id)
            if agent_id is None:
                continue
            for domain in SkillDomain:
                rows.append(
                    SkillAudit(
                        agent_id=agent_id,
                        side=SkillAuditSide.OBJECTIVE,
                        domain=domain.value,
                        level=ledger.level(entity_id, domain),
                        tick=tick,
                    )
                )
        for runtime in self._runtimes:
            checkpoint = runtime.export_runtime_checkpoint()
            model = getattr(checkpoint, "competence_model", None)
            if model is None:
                continue
            owner = getattr(model, "owner_id", None)
            beliefs = getattr(model, "beliefs", ())
            for belief in beliefs:
                domain = belief.domain.value
                rows.append(
                    SkillAudit(
                        agent_id=owner,
                        side=SkillAuditSide.SUBJECTIVE,
                        domain=domain,
                        level=belief.believed_level,
                        tick=tick,
                    )
                )
        return tuple(rows)

    def export_teaching_audits(self) -> tuple[TeachingAudit, ...]:
        """Harvest advice, belief, and objective teaching rows.

        Objective rows copy the skill audit's agent id. The ledger stays in the
        engine. Disabled teaching returns no rows.
        """
        from agents.cognition.competence import CompetenceDomain

        participants = {
            agent.agent_id
            for agent in self._config.agents
            if agent.cognition.teaching_interaction_mode
            is TeachingInteractionMode.DETERMINISTIC
        }
        if not participants:
            return ()
        tick = self._engine.tick.value
        rows: list[TeachingAudit] = []
        for runtime in self._runtimes:
            if runtime.agent_id not in participants:
                continue
            checkpoint = runtime.export_runtime_checkpoint()
            advice = getattr(checkpoint, "declarative_advice", None)
            if advice is not None and getattr(advice, "owner_id", None) == (
                runtime.agent_id
            ):
                for record in advice.rows:
                    rows.append(
                        TeachingAudit(
                            agent_id=runtime.agent_id,
                            store=TeachingAuditStore.ADVICE,
                            token=record.act.value,
                            band_or_level=record.band.value,
                            tick=record.delivery_tick,
                            domain=record.domain.value,
                            source_agent_id=record.source_agent_id,
                        )
                    )
            model = getattr(checkpoint, "competence_model", None)
            if model is None or getattr(model, "owner_id", None) != runtime.agent_id:
                continue
            for domain in CompetenceDomain:
                belief = model.belief_for(domain)
                level = round(belief.believed_level / 1e-6) * 1e-6
                rows.append(
                    TeachingAudit(
                        agent_id=runtime.agent_id,
                        store=TeachingAuditStore.BELIEF,
                        token=domain.value,
                        band_or_level=format(level, ".6f"),
                        tick=tick,
                        domain=domain.value,
                    )
                )
        for skill_row in self.export_skill_audits():
            if skill_row.side is not SkillAuditSide.OBJECTIVE:
                continue
            if skill_row.agent_id not in participants:
                continue
            level = round(skill_row.level / 1e-6) * 1e-6
            rows.append(
                TeachingAudit(
                    agent_id=skill_row.agent_id,
                    store=TeachingAuditStore.OBJECTIVE,
                    token=skill_row.domain,
                    band_or_level=format(level, ".6f"),
                    tick=skill_row.tick,
                    domain=skill_row.domain,
                )
            )
        for row in rows:
            _LOG.debug(
                "teaching_audit agent_id=%s store=%s domain=%s tick=%s",
                row.agent_id.value,
                row.store.value,
                row.domain,
                row.tick,
            )
        return tuple(rows)

    def export_world_model_audits(self) -> tuple[object, ...]:
        """Harvest causal world-model audits. Not part of result JSON."""
        from agents.cognition.world_model import WorldModelAudit

        collected: list[WorldModelAudit] = []
        for bundle in self._agents:
            runtime = bundle.runtime
            export = getattr(runtime, "export_world_model_audits", None)
            if export is None:
                continue
            for audit in export():
                if type(audit) is not WorldModelAudit:
                    raise TypeError("world_model_audits: invalid_item")
                collected.append(audit)
        _LOG.debug(
            "world_model_audit_export run_id=%s audit_count=%s",
            self._run_id.value,
            len(collected),
        )
        return tuple(collected)

    def export_mind_audits(self) -> tuple[object, ...]:
        """Harvest theory-of-mind audits. Not part of result JSON."""
        from agents.cognition.theory_of_mind import MindAudit

        collected: list[MindAudit] = []
        for bundle in self._agents:
            runtime = bundle.runtime
            export = getattr(runtime, "export_mind_audits", None)
            if export is None:
                continue
            for audit in export():
                if type(audit) is not MindAudit:
                    raise TypeError("mind_audits: invalid_item")
                collected.append(audit)
        _LOG.debug(
            "mind_audit_export run_id=%s audit_count=%s",
            self._run_id.value,
            len(collected),
        )
        return tuple(collected)

    def export_offline_consolidation_audits(self) -> tuple[object, ...]:
        """Harvest applied sleep-consolidation audits. Not part of result JSON."""
        from memory.models import OfflineConsolidationAudit

        collected: list[OfflineConsolidationAudit] = []
        for bundle in self._agents:
            runtime = bundle.runtime
            export = getattr(runtime, "export_offline_consolidation_audits", None)
            if export is None:
                continue
            for audit in export():
                if type(audit) is not OfflineConsolidationAudit:
                    raise TypeError("offline_consolidation_audits: invalid_item")
                collected.append(audit)
        _LOG.debug(
            "offline_consolidation_audit_export run_id=%s audit_count=%s",
            self._run_id.value,
            len(collected),
        )
        return tuple(collected)

    def export_reflection_audits(self) -> tuple[object, ...]:
        """Harvest applied reflection audits. Not part of result JSON."""
        from agents.cognition.reflection import ReflectionAudit

        collected: list[ReflectionAudit] = []
        for bundle in self._agents:
            runtime = bundle.runtime
            export = getattr(runtime, "export_reflection_audits", None)
            if export is None:
                continue
            for audit in export():
                if type(audit) is not ReflectionAudit:
                    raise TypeError("reflection_audits: invalid_item")
                collected.append(audit)
        _LOG.debug(
            "reflection_audit_export run_id=%s audit_count=%s",
            self._run_id.value,
            len(collected),
        )
        return tuple(collected)

    def final_objective_projection(self) -> DetachedObjectiveProjection:
        """Detached final objective projection without private engine access."""
        return build_detached_objective_projection(
            tick=self._engine.tick.value,
            revision=self._engine.revision.value,
            bodies=self._engine.detached_bodies(),
        )

    async def _record_finalized_tick(
        self,
        tick_result: TickResult,
        *,
        pendings: tuple[PendingRuntimeFinalization, ...],
    ) -> None:
        projection = build_detached_objective_projection(
            tick=tick_result.resulting_tick.value,
            revision=tick_result.resulting_revision.value,
            bodies=self._engine.detached_bodies(),
        )
        state_hash = objective_projection_hash(projection)
        receipt = FinalizedTickReceipt(
            tick=tick_result.tick.value,
            resulting_tick=tick_result.resulting_tick.value,
            base_revision=tick_result.base_revision.value,
            resulting_revision=tick_result.resulting_revision.value,
            resolutions=tuple(
                detach_action_resolution_evidence(item)
                for item in tick_result.resolutions
            ),
            objective_state_hash=state_hash,
            event_count=len(tick_result.events),
        )
        self._finalized_tick_receipts.append(receipt)
        cognition_invocations = self._cognition_counters.cognition_invocations
        imagination_evaluations = self._cognition_counters.imagination_evaluations
        imagined_future_count = self._cognition_counters.imagined_future_count
        for pending in pendings:
            cognition_invocations += 1
            if pending.has_futures_boundary:
                imagination_evaluations += 1
            else:
                for record in pending.loop_result.boundary_records:
                    if record.component_kind is ComponentKind.FUTURES:
                        imagination_evaluations += 1
                        break
            # Imagined futures are not exposed on CognitiveLoopResult; count
            # FUTURES stage completions only (never GoalEffect as outcomes).
        self._cognition_counters = CognitionCounters(
            cognition_invocations=cognition_invocations,
            imagination_evaluations=imagination_evaluations,
            imagined_future_count=imagined_future_count,
        )
        mid_receipts = self._evaluate_goals_at_boundary(
            tick=tick_result.tick.value,
            run_ending=False,
            projection=projection,
        )
        self._goal_transition_receipts.extend(mid_receipts)
        await self._apply_objective_goal_receipts(mid_receipts)
        _LOG.debug(
            "finalized_tick_receipt run_id=%s tick=%s resolution_count=%s "
            "event_count=%s objective_hash_prefix=%s cognition_invocations=%s",
            self._run_id.value,
            receipt.tick,
            len(receipt.resolutions),
            receipt.event_count,
            state_hash[:12],
            cognition_invocations,
        )

    async def _apply_objective_goal_receipts(
        self,
        receipts: tuple[GoalTransitionReceipt, ...],
    ) -> None:
        """Mutate live Agent.goals from objective receipts and publish revisions."""
        if not receipts:
            return
        by_owner: dict[AgentId, list[GoalTransitionReceipt]] = {}
        for item in receipts:
            by_owner.setdefault(item.owner_id, []).append(item)
        for owner_id, owned in by_owner.items():
            runtime = self._runtimes_by_agent(owner_id)
            applied = runtime.apply_goal_status_transitions(owned)
            await runtime.publish_goal_revisions(applied)

    def _evaluate_goals_at_boundary(
        self,
        *,
        tick: int,
        run_ending: bool,
        projection: DetachedObjectiveProjection,
    ) -> tuple[GoalTransitionReceipt, ...]:
        goals: list[Goal] = []
        completed_ids = {item.goal_id for item in self._goal_transition_receipts}
        for runtime in self._runtimes:
            for goal in runtime.agent.goals:
                if goal.goal_id in completed_ids:
                    continue
                # ACTIVE for normal evaluation; FAILED/SUSPENDED remain eligible
                # so same-tick objective COMPLETED can overwrite subjective status.
                if goal.status is GoalStatus.ACTIVE or goal.status in (
                    GoalStatus.FAILED,
                    GoalStatus.SUSPENDED,
                ):
                    goals.append(goal)
        owner_entity_ids = {
            agent.agent_id.value: agent.entity_id.value for agent in self._config.agents
        }
        evidence = GoalEvaluationEvidence(
            tick=tick,
            run_ending=run_ending,
            owner_entity_ids=owner_entity_ids,
            bodies=projection.bodies,
        )
        return evaluate_goals_after_finalization(tuple(goals), evidence)

    def _evaluate_stop(self) -> RunnerStopReasonCode | None:
        if self._injected_stop and self._config.stop_policy.allow_injected_stop:
            return RunnerStopReasonCode.INJECTED_STOP
        if self._ticks_committed >= self._config.stop_policy.max_ticks:
            return RunnerStopReasonCode.MAX_TICKS
        if self._config.stop_policy.stop_on_all_agents_terminal and all(
            runtime.status is AgentRuntimeStatus.TERMINAL for runtime in self._runtimes
        ):
            return RunnerStopReasonCode.ALL_AGENTS_TERMINAL
        return None

    def _runtimes_by_agent(self, agent_id: AgentId) -> AgentRuntime:
        for runtime in self._runtimes:
            if runtime.agent_id == agent_id:
                return runtime
        raise RunnerConstructionError(
            RunnerConstructionErrorCode.OWNERSHIP,
            stage="runtime_lookup",
        )

    async def _sync_mid_run_population_entries(self) -> None:
        """Bind AgentBundles for engine admits and refresh translators.

        Per-tick ordinal is registration order including mid-run appends.
        New agents are eligible on the next observe tick.
        """
        if not self._engine.lifecycle_channel_active:
            return
        translator = self._engine.registration_translator
        for runtime in self._runtimes:
            runtime.replace_translator(translator)
        known = {runtime.agent_id for runtime in self._runtimes}
        new_registrations = [
            registration
            for registration in self._engine.ordered_registrations
            if registration.agent_id not in known
        ]
        if not new_registrations:
            return
        from simulation.new_agent_initialization import (
            BlankSlateStoreCounts,
            assert_blank_slate_subjective_state,
            default_new_agent_initialization_spec,
            species_defaults_for,
        )

        init_spec = self._config.new_agent_initialization
        if init_spec is None:
            init_spec = default_new_agent_initialization_spec()
        allow_provider = _llm_assisted_provider_bound(self._config.provider)
        scoring_policy = _default_scoring_policy()
        reconstruction_policy = _default_reconstruction_policy(
            allow_provider=allow_provider
        )
        reconstructor = _reconstructor_for(self._config.provider, self._provider)
        counterpart = _counterpart_resolver(translator)
        memory_run_id = MemoryRunId(self._run_id.value)
        cognition_trace_repository: CognitionTraceRepository = (
            select_cognition_trace_repository(
                enabled=self._config.cognition_trace.enabled,
                durable=self._factories.cognition_trace_repository,
            )
        )
        deps = self._factories
        agents = list(self._agents)
        runtimes = list(self._runtimes)
        for registration in new_registrations:
            pack = species_defaults_for(
                init_spec.species_defaults_id, agent_id=registration.agent_id
            )
            cognition = pack.cognition
            agent_spec = AgentRunnerSpec(
                agent_id=registration.agent_id,
                entity_id=registration.entity_id,
                cognition=cognition,
                name=registration.agent_id.value,
                initial_goals=(),
            )
            owner = agent_spec.agent_id
            scope = MemoryScope(run_id=memory_run_id, owner_id=owner)
            memory_service = deps.create_memory_service(
                scope, reconstructor=reconstructor
            )
            belief_service = deps.create_belief_service(scope)
            relationship_service = deps.create_relationship_service(owner)
            owner_bundle = deps.create_subjective_bundle(
                scope,
                memory_service=memory_service,
                belief_service=belief_service,
                relationship_service=relationship_service,
            )
            legacy_beliefs = BeliefStore(owner)
            loop_config = _cognition_config_for(
                agent_spec.cognition,
                mortality_mode=self._config.mortality_mode,
                capability_flags=self._config.capability_flags,
            )
            memory_retriever = _memory_retriever_for(
                agent_spec.cognition.memory_mode,
                memory_service=memory_service,
                scoring_policy=scoring_policy,
                reconstruction_policy=reconstruction_policy,
                belief_reader=None,
                emotion_bias=(
                    loop_config.emotional_state_mode
                    is CognitionEmotionalStateMode.ENABLED
                ),
            )
            cognitive_loop = build_cognitive_loop(
                loop_config,
                memory=memory_retriever,
                resolve_counterpart=counterpart,
                identity_history=owner_bundle.semantic_belief_reader.history,
                consolidation_selector=_consolidation_selector_for(
                    self._config.provider,
                    self._provider,
                    loop_config.consolidation_mode,
                ),
                reflection_selector=_reflection_selector_for(
                    self._config.provider,
                    self._provider,
                    loop_config.reflection_mode,
                ),
                **_caregiving_loop_kwargs(self._config),
                **_developmental_learning_loop_kwargs(self._config),
            )
            agent = Agent(
                agent_id=owner,
                name=agent_spec.name if agent_spec.name is not None else owner.value,
                goals=agent_spec.initial_goals,
                drives=pack.drive_profile,
            )
            runtime = AgentRuntime(
                agent=agent,
                translator=translator,
                cognitive_loop=cognitive_loop,
                memory_reader=owner_bundle.memory_reader,
                memory_writer=MemoryStore(owner),
                belief_reader=legacy_beliefs,
                belief_writer=legacy_beliefs,
                memory_service=memory_service,
                semantic_belief_reader=owner_bundle.semantic_belief_reader,
                relationship_reader=owner_bundle.relationship_reader,
                subjective_state=owner_bundle.commit_service,
                run_id=self._run_id,
                cognition_trace_repository=cognition_trace_repository,
                cognition_trace_spec=self._config.cognition_trace,
                scientific_evidence=deps.scientific_evidence,
            )
            if self._started and runtime.status is AgentRuntimeStatus.CREATED:
                runtime.start()
            mark_admit = getattr(
                cognitive_loop, "mark_developmental_mid_run_admit", None
            )
            if callable(mark_admit):
                mark_admit()
            assert_blank_slate_subjective_state(owner, BlankSlateStoreCounts())
            bundle = _AgentBundle(
                runtime=runtime,
                bundle=owner_bundle,
                memory_service=memory_service,
                belief_service=belief_service,
                relationship_service=relationship_service,
                subjective_state=owner_bundle.commit_service,
                memory_retriever=memory_retriever,
            )
            agents.append(bundle)
            runtimes.append(runtime)
            _LOG.debug(
                "new_agent_bundle_constructed agent_id=%s ordinal=%s "
                "species_defaults_id=%s",
                owner.value,
                len(runtimes) - 1,
                init_spec.species_defaults_id,
            )
            _LOG.info(
                "runner_mid_run_agent_bound agent_id=%s body_id=%s "
                "registration_ordinal=%s",
                owner.value,
                registration.entity_id.value,
                len(runtimes) - 1,
            )
        self._agents = tuple(agents)
        self._runtimes = tuple(runtimes)
        # Ordinal semantics: registration order including mid-run appends.
        assert [rt.agent_id for rt in self._runtimes] == [
            reg.agent_id for reg in self._engine.ordered_registrations
        ]

    async def _commit_tick(
        self, submissions: tuple[ActionSubmission, ...]
    ) -> TickResult:
        """Commit through exactly one authority path; never fall back."""
        if self._durable is not None:
            if self._durable.fenced:
                raise RunnerConstructionError(
                    RunnerConstructionErrorCode.DURABLE_UNSUPPORTED,
                    stage="fenced",
                )
            checkpoint_id: SnapshotId | None = None
            policy = self._config.persistence.checkpoint
            next_committed = self._ticks_committed + 1
            if (
                policy.enabled
                and policy.cadence_ticks is not None
                and next_committed % policy.cadence_ticks == 0
            ):
                checkpoint_id = SnapshotId(
                    f"ckpt-{self._run_id.value}-t{next_committed}"
                )
                _LOG.debug(
                    "checkpoint_cadence_hit run_id=%s committed_ticks=%s "
                    "cadence_ticks=%s snapshot_id=%s",
                    self._run_id.value,
                    next_committed,
                    policy.cadence_ticks,
                    checkpoint_id.value,
                )
            await self._durable.resolve_tick(submissions, checkpoint_id=checkpoint_id)
            if checkpoint_id is not None:
                _LOG.info(
                    "runner_checkpoint_committed run_id=%s committed_ticks=%s "
                    "snapshot_id=%s",
                    self._run_id.value,
                    next_committed,
                    checkpoint_id.value,
                )
                _LOG.debug(
                    "[persistence.snapshots] write_policy run_id=%s "
                    "cadence_ticks=%s snapshot_count=%s",
                    self._run_id.value,
                    policy.cadence_ticks,
                    next_committed // policy.cadence_ticks
                    if policy.cadence_ticks
                    else 0,
                )
            result = self._engine.last_tick_result
            if result is None:
                raise RunnerConstructionError(
                    RunnerConstructionErrorCode.INVALID_CONFIG,
                    stage="missing_tick_result",
                )
            return result
        return self._engine.resolve_tick(submissions)

    async def aclose(self) -> None:
        """Close owned providers. Idempotent."""
        if self._closed:
            return
        self._closed = True
        try:
            await self._provider.close()
            _LOG.debug(
                "runner_closed run_id=%s",
                self._run_id.value,
            )
        except Exception:
            _LOG.error(
                "runner_cleanup_failed code=%s",
                RunnerConstructionErrorCode.CLEANUP_FAILED.value,
            )
            raise RunnerConstructionError(
                RunnerConstructionErrorCode.CLEANUP_FAILED,
                stage="close",
            ) from None

    async def __aenter__(self) -> SimulationRunner:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()


def _memory_retriever_for(
    mode: MemoryMode,
    *,
    memory_service: MemoryService,
    scoring_policy: MemoryScoringPolicy,
    reconstruction_policy: MemoryReconstructionPolicy | None = None,
    belief_reader: object | None = None,
    emotion_bias: bool = False,
) -> ReferenceMemoryRetriever | ScopedMemoryRetriever:
    from memory.models import default_memory_dynamics_policy

    if mode is MemoryMode.REFERENCE:
        _LOG.debug(
            "memory_retriever_constructed",
            extra={
                "runner": {
                    "memory_mode": mode.value,
                    "dynamics_policy_version": "none",
                    "emotion_bias": emotion_bias,
                }
            },
        )
        return ReferenceMemoryRetriever(
            memory_service,
            scoring_policy=scoring_policy,
            belief_reader=belief_reader,  # type: ignore[arg-type]
            emotion_bias=emotion_bias,
        )
    if mode is MemoryMode.RECONSTRUCTIVE:
        _LOG.debug(
            "memory_retriever_constructed",
            extra={
                "runner": {
                    "memory_mode": mode.value,
                    "dynamics_policy_version": "none",
                    "emotion_bias": emotion_bias,
                }
            },
        )
        return ScopedMemoryRetriever(
            memory_service,
            scoring_policy=scoring_policy,
            reconstruction_policy=reconstruction_policy,
            belief_reader=belief_reader,  # type: ignore[arg-type]
            emotion_bias=emotion_bias,
        )
    if mode is MemoryMode.RECONSTRUCTIVE_V2:
        dynamics = default_memory_dynamics_policy()
        _LOG.debug(
            "memory_retriever_constructed",
            extra={
                "runner": {
                    "memory_mode": mode.value,
                    "dynamics_policy_version": dynamics.version,
                    "emotion_bias": emotion_bias,
                }
            },
        )
        return ScopedMemoryRetriever(
            memory_service,
            scoring_policy=scoring_policy,
            reconstruction_policy=reconstruction_policy,
            belief_reader=belief_reader,  # type: ignore[arg-type]
            emotion_bias=emotion_bias,
            dynamics_policy=dynamics,
        )
    _LOG.error(
        "memory_retriever_unsupported_mode",
        extra={
            "runner": {
                "memory_mode": getattr(mode, "value", str(mode)),
                "stage": "memory_mode",
            }
        },
    )
    raise RunnerConstructionError(
        RunnerConstructionErrorCode.INVALID_CONFIG,
        stage="memory_mode",
    )


def _validate_registration_ownership(
    config: SimulationRunnerConfig,
    bootstrap: WorldBootstrap,
) -> None:
    expected = config.ordered_registrations()
    actual = tuple(bootstrap.registrations)
    if expected != actual:
        raise RunnerConstructionError(
            RunnerConstructionErrorCode.OWNERSHIP,
            stage="registrations",
        )
    agent_ids = [item.agent_id for item in expected]
    entity_ids = [item.entity_id for item in expected]
    if len(set(agent_ids)) != len(agent_ids):
        raise RunnerConstructionError(
            RunnerConstructionErrorCode.OWNERSHIP,
            stage="agent_ids",
        )
    if len(set(entity_ids)) != len(entity_ids):
        raise RunnerConstructionError(
            RunnerConstructionErrorCode.OWNERSHIP,
            stage="entity_ids",
        )
    body_ids = {body.entity_id for body in bootstrap.bodies}
    if set(entity_ids) != body_ids:
        raise RunnerConstructionError(
            RunnerConstructionErrorCode.OWNERSHIP,
            stage="bodies",
        )


async def _cleanup_created(
    closables: Sequence[AsyncCloseable],
    *,
    stage: str,
) -> None:
    for resource in reversed(tuple(closables)):
        try:
            await resource.close()
        except Exception:
            _LOG.error(
                "runner_cleanup_failed code=%s stage=%s",
                RunnerConstructionErrorCode.CLEANUP_FAILED.value,
                stage,
            )


def _bootstrap_snapshot(engine: WorldEngine) -> WorldSnapshot:
    """Build the tick-0 durable bootstrap checkpoint from a live engine."""
    schema_version, codec_version = checkpoint_schema_for_production(
        production_active=engine._production_catalog is not None,
        dynamics_active=engine._environmental_dynamics is not None,
        artifacts_active=engine._artifacts_enabled,
        lifecycle_active=engine.lifecycle_channel_active,
        new_agent_provenance_active=engine.new_agent_provenance_active,
        kinship_active=engine.kinship_channel_active,
        dependency_care_active=engine.dependency_care_channel_active,
    )
    state = engine._snapshot.world.state
    production_rows: dict[str, tuple[object, ...]] = {}
    if codec_version in {"v3", "v4", "v5", "v6", "v7", "v8", "v9"}:
        production_rows = {
            "structures": tuple(state.structures.values()),
            "production_jobs": tuple(state.production_jobs.values()),
            "tool_marks": tuple(state.tool_marks.values()),
        }
    if codec_version in {"v4", "v5", "v6", "v7", "v8", "v9"}:
        production_rows["active_hazards"] = tuple(state.active_hazards)
    if codec_version in {"v5", "v6", "v7", "v8", "v9"}:
        production_rows["artifacts"] = tuple(state.artifacts.values())
    if codec_version in {"v6", "v7", "v8", "v9"}:
        production_rows["lifecycle_records"] = tuple(engine.lifecycle_records)
    if codec_version in {"v8", "v9"}:
        kinship_graph = engine.kinship_graph
        from world.kinship import KinshipGraph

        if type(kinship_graph) is KinshipGraph:
            production_rows["kinship_edges"] = kinship_graph.edges
    if codec_version == "v9":
        production_rows["dependency_need_registers"] = tuple(
            engine._dependency_need_registers.values()
        )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(f"bootstrap-{engine.run_id.value}"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=tuple(engine._snapshot.world.state.items.values()),
        resources=tuple(engine._snapshot.world.state.resources.values()),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=schema_version,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=codec_version,
        derivation_version=engine._config.derivation_version or DERIVATION_VERSION_V3,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        **production_rows,
    )
    return WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=None,
        structures=draft.structures,
        production_jobs=draft.production_jobs,
        tool_marks=draft.tool_marks,
        active_hazards=draft.active_hazards,
        artifacts=draft.artifacts,
        lifecycle_records=draft.lifecycle_records,
        kinship_edges=getattr(draft, "kinship_edges", ()),
        dependency_need_registers=getattr(draft, "dependency_need_registers", ()),
    )


def _pending_record_from_command(
    command: FinalizationCommand,
) -> PendingFinalizationRecord:
    """Persist the versioned finalization command (privacy-reviewed payload)."""
    return PendingFinalizationRecord(
        run_id=command.run_id,
        agent_id=command.agent_id.value,
        tick=command.tick,
        invocation_id=command.invocation_id,
        integrity_hash=command.integrity_hash,
        codec_version=PENDING_FINALIZATION_CODEC_VERSION,
        payload=finalization_command_to_mapping(command),
        status=PendingFinalizationStatus.PENDING,
    )


def _command_from_pending_record(
    record: PendingFinalizationRecord,
) -> FinalizationCommand:
    """Decode a durable pending row into a finalization command."""
    if record.codec_version == LEGACY_PENDING_FINALIZATION_CODEC_VERSION:
        _LOG.error(
            "runner_recovery_legacy run_id=%s invocation_id=%s codec_version=%s",
            record.run_id.value,
            record.invocation_id,
            record.codec_version,
        )
        raise RunnerConstructionError(
            RunnerConstructionErrorCode.INVALID_CONFIG,
            stage="legacy_pending_finalization",
        )
    if record.codec_version != PENDING_FINALIZATION_CODEC_VERSION:
        _LOG.error(
            "runner_recovery_corrupt run_id=%s code=unsupported_codec "
            "invocation_id=%s codec_version=%s",
            record.run_id.value,
            record.invocation_id,
            record.codec_version,
        )
        raise RunnerConstructionError(
            RunnerConstructionErrorCode.INVALID_CONFIG,
            stage="pending_codec",
        )
    command = decode_finalization_command(record.payload)
    assert type(command) is FinalizationCommand
    return command


def _pending_record(
    run_id: RunId, pending: PendingRuntimeFinalization
) -> PendingFinalizationRecord:
    """Compatibility wrapper: encode the full finalization command."""
    command = pending.to_finalization_command(run_id=run_id)
    assert type(command) is FinalizationCommand
    return _pending_record_from_command(command)
