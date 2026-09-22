"""Configuration-driven simulation runner construction and lifecycle ownership.

``SimulationRunner.from_config`` builds world, agents, cognition, and runtime
services from an immutable runner specification plus narrow injected factories.
It never imports environment settings, SQLAlchemy adapters, or API code.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from agents.cognition.configuration import (
    CognitionDriveOverride,
    CognitionImaginationMode,
    CognitionLoopConfig,
    CognitionMemoryMode,
    CognitionMortalityAppraisalMode,
    build_cognitive_loop,
)
from agents.cognition.memory import ReferenceMemoryRetriever, ScopedMemoryRetriever
from agents.models import Agent, AgentId
from llm.factory import (
    DisabledLLMProvider,
    ProviderAdapterKind,
    ProviderFactoryConfig,
    create_llm_provider,
)
from memory.belief_service import InMemorySemanticBeliefService
from memory.models import (
    BeliefStore,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemoryStore,
)
from memory.service import InMemoryMemoryService
from simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeStatus,
    PendingRuntimeFinalization,
    PreparedObservation,
)
from simulation.bootstrap import WorldBootstrap, registration_translator
from simulation.identifiers import derive_run_id
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from simulation.runner_models import (
    AgentCognitionSpec,
    CognitionFailurePolicy,
    MemoryMode,
    MortalityMode,
    RecordingPolicy,
    RunnerAttemptReceipt,
    RunnerAttemptStatus,
    RunnerProviderSettings,
    RunnerStopReasonCode,
    SimulationRunnerConfig,
    SimulationRunnerResult,
    describe_runner_config,
)
from simulation.runner_serialization import build_runner_diagnostics
from simulation.subjective_state import InMemorySubjectiveStateService
from social.service import InMemoryRelationshipService

_LOG: Final[logging.Logger] = logging.getLogger("simulation.runner")
_DEFAULT_SCORING_POLICY_ID: Final[str] = "runner-default"
_DEFAULT_SCORING_POLICY_VERSION: Final[str] = "1"

__all__ = [
    "AsyncCloseable",
    "ProviderCredentialResolver",
    "ProviderCredentials",
    "RunnerConstructionError",
    "RunnerConstructionErrorCode",
    "RunnerDependencyFactories",
    "SimulationRunner",
]


class RunnerConstructionErrorCode(StrEnum):
    """Stable construction/cleanup failure codes (no payloads)."""

    INVALID_CONFIG = "invalid_config"
    OWNERSHIP = "ownership"
    FACTORY_FAILED = "factory_failed"
    PROVIDER_FAILED = "provider_failed"
    CLEANUP_FAILED = "cleanup_failed"
    DURABLE_UNSUPPORTED = "durable_unsupported"
    PARTIAL_CONSTRUCTION = "partial_construction"


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


class ProviderCredentialResolver(Protocol):
    """Maps credential-free provider settings to secrets at construction."""

    def resolve(self, settings: RunnerProviderSettings) -> ProviderCredentials: ...


AsyncSleep = Callable[[float], Awaitable[None]]
MonotonicClock = Callable[[], float]


class RunnerDependencyFactories:
    """Narrow injected factories for runner-owned resource construction.

    Defaults construct in-memory owner-scoped services and a disabled LLM
    provider. Durable persistence adapters are injected by composition roots.
    """

    __slots__ = (
        "_credential_resolver",
        "_monotonic",
        "_provider_factory",
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
        sleep: AsyncSleep | None = None,
        monotonic: MonotonicClock | None = None,
    ) -> None:
        self._credential_resolver = credential_resolver
        self._provider_factory = provider_factory
        self._sleep = sleep
        self._monotonic = monotonic

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
            return self._provider_factory(settings, credentials)
        return _default_provider(
            settings,
            credentials,
            sleep=self._sleep,
            monotonic=self._monotonic,
        )


def _default_scoring_policy() -> MemoryScoringPolicy:
    return MemoryScoringPolicy(
        policy_id=_DEFAULT_SCORING_POLICY_ID,
        version=_DEFAULT_SCORING_POLICY_VERSION,
        weights=MemoryScoreWeights(recency=1.0, current_context_overlap=1.0),
    )


def _cognition_config_for(
    spec: AgentCognitionSpec,
    *,
    mortality_mode: MortalityMode,
) -> CognitionLoopConfig:
    return CognitionLoopConfig(
        memory_mode=CognitionMemoryMode(spec.memory_mode.value),
        imagination_mode=CognitionImaginationMode(spec.imagination_mode.value),
        mortality_appraisal_mode=(
            CognitionMortalityAppraisalMode.DISABLED
            if mortality_mode is MortalityMode.DISABLED
            else CognitionMortalityAppraisalMode.ENABLED
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
) -> AsyncCloseable:
    if settings.adapter_kind is ProviderAdapterKind.DISABLED:
        return DisabledLLMProvider()
    if settings.recording_policy is RecordingPolicy.DETERMINISTIC_FAKE:
        _LOG.warning(
            "provider_deterministic_fallback adapter_kind=%s recording_policy=%s",
            settings.adapter_kind.value,
            settings.recording_policy.value,
        )
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
    return create_llm_provider(factory_config, sleep=sleep, monotonic=monotonic)


@dataclass(frozen=True, slots=True)
class _AgentBundle:
    """Owner-scoped services for one registered agent."""

    runtime: AgentRuntime
    memory_service: InMemoryMemoryService
    belief_service: InMemorySemanticBeliefService
    relationship_service: InMemoryRelationshipService
    subjective_state: InMemorySubjectiveStateService


class SimulationRunner:
    """Owns configured world engine, agent runtimes, and provider lifecycle."""

    __slots__ = (
        "_agents",
        "_bootstrap",
        "_closed",
        "_config",
        "_diagnostics",
        "_engine",
        "_injected_stop",
        "_intervention_arbiter",
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
        self._closed = False
        self._started = False
        self._ticks_committed = 0
        self._injected_stop = False
        self._intervention_arbiter: object | None = None

    @property
    def config(self) -> SimulationRunnerConfig:
        return self._config

    @property
    def run_id(self) -> RunId:
        return self._run_id

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
        if config.persistence.durable:
            raise RunnerConstructionError(
                RunnerConstructionErrorCode.DURABLE_UNSUPPORTED,
                stage="persistence",
            )

        deps = factories if factories is not None else RunnerDependencyFactories()
        created_closables: list[AsyncCloseable] = []
        created_agents: list[_AgentBundle] = []
        stage = "validate"

        try:
            _LOG.debug(
                "runner_construction_start schema_version=%s agent_count=%s "
                "mortality_mode=%s durable=%s",
                config.schema_version,
                len(config.agents),
                config.mortality_mode.value,
                config.persistence.durable,
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
            resolved_run_id = run_id if run_id is not None else derive_run_id(run_config)
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
            engine = WorldEngine(
                config=run_config,
                bootstrap=bootstrap,
                run_id=resolved_run_id,
            )

            stage = "agents"
            memory_run_id = MemoryRunId(resolved_run_id.value)
            scoring_policy = _default_scoring_policy()
            runtimes: list[AgentRuntime] = []

            for ordinal, agent_spec in enumerate(config.agents):
                stage = f"agent:{ordinal}"
                owner = agent_spec.agent_id
                if translator.to_entity_id(owner) != agent_spec.entity_id:
                    raise RunnerConstructionError(
                        RunnerConstructionErrorCode.OWNERSHIP,
                        stage=stage,
                    )
                scope = MemoryScope(run_id=memory_run_id, owner_id=owner)
                memory_service = InMemoryMemoryService(scope)
                belief_service = InMemorySemanticBeliefService(scope)
                relationship_service = InMemoryRelationshipService(owner)
                subjective = InMemorySubjectiveStateService(
                    scope,
                    memory_service=memory_service,
                    belief_service=belief_service,
                    relationship_service=relationship_service,
                )
                memory_store = MemoryStore(owner)
                belief_store = BeliefStore(owner)
                loop_config = _cognition_config_for(
                    agent_spec.cognition,
                    mortality_mode=config.mortality_mode,
                )
                memory_retriever = _memory_retriever_for(
                    agent_spec.cognition.memory_mode,
                    memory_service=memory_service,
                    scoring_policy=scoring_policy,
                )
                cognitive_loop = build_cognitive_loop(
                    loop_config,
                    memory=memory_retriever,
                )
                agent = Agent(
                    agent_id=owner,
                    name=owner.value,
                    goals=(),
                    drives=agent_spec.cognition.resolve_drive_profile(),
                )
                runtime = AgentRuntime(
                    agent=agent,
                    translator=translator,
                    cognitive_loop=cognitive_loop,
                    memory_reader=memory_store,
                    memory_writer=memory_store,
                    belief_reader=belief_store,
                    belief_writer=belief_store,
                    memory_service=memory_service,
                    subjective_state=subjective,
                )
                bundle = _AgentBundle(
                    runtime=runtime,
                    memory_service=memory_service,
                    belief_service=belief_service,
                    relationship_service=relationship_service,
                    subjective_state=subjective,
                )
                created_agents.append(bundle)
                runtimes.append(runtime)
                _LOG.debug(
                    "runner_agent_constructed ordinal=%s memory_mode=%s "
                    "imagination_mode=%s mortality_mode=%s",
                    ordinal,
                    agent_spec.cognition.memory_mode.value,
                    agent_spec.cognition.imagination_mode.value,
                    config.mortality_mode.value,
                )

            diagnostics = build_runner_diagnostics(config)
            fields = describe_runner_config(diagnostics)
            _LOG.info(
                "runner_constructed run_id=%s world_id=%s agent_count=%s "
                "config_fingerprint_prefix=%s scenario_fingerprint_prefix=%s "
                "cognition_fingerprint_prefix=%s rules_fingerprint_prefix=%s "
                "mortality_mode=%s",
                resolved_run_id.value,
                bootstrap.world_id.value,
                len(runtimes),
                fields["config_fingerprint_prefix"],
                fields["scenario_fingerprint_prefix"],
                fields["cognition_fingerprint_prefix"],
                fields["rules_fingerprint_prefix"],
                config.mortality_mode.value,
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

        pendings: list[PendingRuntimeFinalization] = []
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
                        effective = maybe(
                            tick=tick_value, agent_id=runtime.agent_id
                        )
                pending = await runtime.bind_effective_command(
                    prepared, effective_command=effective
                )
                pendings.append(pending)
                submissions.append(pending.submission)

            if not submissions and all(
                runtime.status is AgentRuntimeStatus.TERMINAL
                for runtime in self._runtimes
            ):
                self._engine.resolve_tick(())
                self._ticks_committed += 1
                return RunnerAttemptReceipt(
                    tick=tick_value,
                    status=RunnerAttemptStatus.FINALIZED,
                    submission_count=0,
                    finalized_count=0,
                    stop_reason=RunnerStopReasonCode.ALL_AGENTS_TERMINAL,
                )

            tick_result = self._engine.resolve_tick(tuple(submissions))
            _LOG.debug(
                "runner_tick_committed run_id=%s tick=%s submission_count=%s",
                self._run_id.value,
                tick_result.tick.value,
                len(submissions),
            )

            finalized = 0
            for pending in pendings:
                await self._runtimes_by_agent(
                    pending.submission.agent_id
                ).finalize_pending(pending)
                finalized += 1

            self._ticks_committed += 1
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
        except AgentRuntimeError:
            for pending in reversed(pendings):
                try:
                    self._runtimes_by_agent(
                        pending.submission.agent_id
                    ).abort_pending(pending)
                except AgentRuntimeError:
                    pass
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
        except Exception:
            for pending in reversed(pendings):
                try:
                    self._runtimes_by_agent(
                        pending.submission.agent_id
                    ).abort_pending(pending)
                except AgentRuntimeError:
                    pass
            _LOG.error(
                "runner_authority_failed run_id=%s tick=%s",
                self._run_id.value,
                tick_value,
            )
            return RunnerAttemptReceipt(
                tick=tick_value,
                status=RunnerAttemptStatus.ABORTED,
                submission_count=len(submissions),
                finalized_count=0,
                stop_reason=RunnerStopReasonCode.AUTHORITY_FAILURE,
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
        result = SimulationRunnerResult(
            run_id=self._run_id,
            ticks_committed=self._ticks_committed,
            stop_reason=stop_reason,
            attempt_receipts=tuple(receipts),
        )
        _LOG.info(
            "runner_finished run_id=%s ticks_committed=%s stop_reason=%s "
            "attempt_count=%s",
            self._run_id.value,
            self._ticks_committed,
            stop_reason.value,
            len(receipts),
        )
        return result

    def _evaluate_stop(self) -> RunnerStopReasonCode | None:
        if self._injected_stop and self._config.stop_policy.allow_injected_stop:
            return RunnerStopReasonCode.INJECTED_STOP
        if self._ticks_committed >= self._config.stop_policy.max_ticks:
            return RunnerStopReasonCode.MAX_TICKS
        if self._config.stop_policy.stop_on_all_agents_terminal and all(
            runtime.status is AgentRuntimeStatus.TERMINAL
            for runtime in self._runtimes
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
    memory_service: InMemoryMemoryService,
    scoring_policy: MemoryScoringPolicy,
) -> ReferenceMemoryRetriever | ScopedMemoryRetriever:
    if mode is MemoryMode.REFERENCE:
        return ReferenceMemoryRetriever(
            memory_service,
            scoring_policy=scoring_policy,
        )
    if mode is MemoryMode.RECONSTRUCTIVE:
        return ScopedMemoryRetriever(
            memory_service,
            scoring_policy=scoring_policy,
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
