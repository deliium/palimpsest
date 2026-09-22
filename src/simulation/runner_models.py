"""Immutable simulation runner configuration contracts.

These specifications are replay-significant and credential-free. Credentials,
base URLs, seeds in diagnostic projections, drive values in logs, and story
payloads are out of scope for this module's public diagnostics.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import (
    REQUIRED_DRIVE_KINDS,
    AgentId,
    DriveDisposition,
    DriveKind,
    DriveProfile,
)
from llm.factory import ProviderAdapterKind
from llm.models import StructuredOutputMode
from simulation.bootstrap import AgentRegistration
from simulation.clock import require_exact_nonneg_int
from simulation.models import (
    DERIVATION_VERSION_V3,
    StochasticIdentity,
    require_derivation_version,
    require_seed,
    require_stochastic_identity,
    stochastic_identity_fingerprint,
)
from world.identifiers import EntityId, WorldId, WorldRevision, require_stable_id
from world.models import (
    AgentBody,
    Item,
    Location,
    PhysicalRules,
    Resource,
    Weather,
    physical_rules_fingerprint,
)

_LOGGER = logging.getLogger("simulation.runner_models")

RUNNER_SCHEMA_VERSION: Final[str] = "runner-config-v1"
COGNITION_POLICY_VERSION: Final[str] = "cognition-policy-v1"
PROVIDER_SETTINGS_VERSION: Final[str] = "provider-settings-v1"
MORTALITY_POLICY_VERSION: Final[str] = "mortality-policy-v1"

_OVERRIDEABLE_DRIVE_KINDS: Final[frozenset[DriveKind]] = frozenset(
    {
        DriveKind.CURIOSITY,
        DriveKind.SAFETY,
        DriveKind.BELONGING,
        DriveKind.STATUS,
    }
)

_DEFAULT_MAX_REQUEST_BYTES: Final[int] = 1_048_576
_DEFAULT_MAX_RESPONSE_BYTES: Final[int] = 1_048_576
_DEFAULT_MAX_HEADER_BYTES: Final[int] = 8_192


def _unit_interval(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_unit_interval")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    if number == 0.0:
        return 0.0
    return number


class MemoryMode(StrEnum):
    """Closed memory retrieval treatments for experiment arms."""

    REFERENCE = "reference"
    RECONSTRUCTIVE = "reconstructive"


class ImaginationMode(StrEnum):
    """Closed imagination treatments. Disabled is non-counterfactual."""

    DISABLED = "disabled"
    ENABLED = "enabled"


class MortalityMode(StrEnum):
    """Closed mortality treatment applied to physical rules and appraisal."""

    DISABLED = "disabled"
    ENABLED = "enabled"


class RunnerStopReasonCode(StrEnum):
    """Closed stop reasons evaluable at finalized committed boundaries."""

    MAX_TICKS = "max_ticks"
    ALL_AGENTS_TERMINAL = "all_agents_terminal"
    INJECTED_STOP = "injected_stop"
    CANCELLED = "cancelled"
    COGNITION_FAILURE = "cognition_failure"
    AUTHORITY_FAILURE = "authority_failure"
    FINALIZATION_RECOVERY_REQUIRED = "finalization_recovery_required"


class CognitionFailurePolicy(StrEnum):
    """Policy when one agent's cognition fails during a tick."""

    ABORT_TICK = "abort_tick"
    OMIT_FAILED_AGENT = "omit_failed_agent"


class RecordingPolicy(StrEnum):
    """LLM reproducibility policy for runner provider settings."""

    LIVE = "live"
    DETERMINISTIC_FAKE = "deterministic_fake"
    RECORDED = "recorded"


class ExactReproducibilityMode(StrEnum):
    """Whether exact reproduction is required for the run."""

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"


def _require_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive int")
    return value


def _require_finite_float(name: str, value: object, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if number < minimum or number > maximum:
        raise ValueError(f"{name} out of range")
    return number


def _require_positive_float(name: str, value: object) -> float:
    return _require_finite_float(name, value, minimum=math.ulp(0.0), maximum=1e12)


def _copy_ordered(name: str, values: Sequence[object], *, model_type: type) -> tuple:
    if isinstance(values, (set, frozenset)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    for item in copied:
        if type(item) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
    return copied


@dataclass(frozen=True, slots=True)
class DriveOverrideSpec:
    """Sparse override for one experiment-controlled drive disposition."""

    kind: DriveKind
    baseline: float | None = None
    sensitivity: float | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not DriveKind:
            raise TypeError("DriveOverrideSpec.kind must be DriveKind")
        if self.kind not in _OVERRIDEABLE_DRIVE_KINDS:
            raise ValueError("DriveOverrideSpec.kind is not overrideable")
        if self.baseline is None and self.sensitivity is None:
            raise ValueError("DriveOverrideSpec requires baseline or sensitivity")
        if self.baseline is not None:
            object.__setattr__(
                self, "baseline", _unit_interval("DriveOverrideSpec.baseline", self.baseline)
            )
        if self.sensitivity is not None:
            object.__setattr__(
                self,
                "sensitivity",
                _unit_interval("DriveOverrideSpec.sensitivity", self.sensitivity),
            )


@dataclass(frozen=True, slots=True)
class AgentCognitionSpec:
    """Per-agent cognition/memory/imagination/drive treatment."""

    agent_id: AgentId
    memory_mode: MemoryMode = MemoryMode.RECONSTRUCTIVE
    imagination_mode: ImaginationMode = ImaginationMode.ENABLED
    drive_overrides: tuple[DriveOverrideSpec, ...] = ()
    policy_version: str = COGNITION_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("AgentCognitionSpec.agent_id must be AgentId")
        if type(self.memory_mode) is not MemoryMode:
            raise TypeError("AgentCognitionSpec.memory_mode must be MemoryMode")
        if type(self.imagination_mode) is not ImaginationMode:
            raise TypeError("AgentCognitionSpec.imagination_mode must be ImaginationMode")
        if self.policy_version != COGNITION_POLICY_VERSION:
            raise ValueError("unsupported cognition policy_version")
        overrides = _copy_ordered(
            "AgentCognitionSpec.drive_overrides",
            self.drive_overrides,
            model_type=DriveOverrideSpec,
        )
        seen: set[DriveKind] = set()
        for override in overrides:
            if override.kind in seen:
                raise ValueError("DriveOverrideSpec kinds must be unique")
            seen.add(override.kind)
        object.__setattr__(self, "drive_overrides", overrides)

    def resolve_drive_profile(self) -> DriveProfile:
        """Build a complete owner-scoped profile with sparse overrides applied."""
        override_map = {item.kind: item for item in self.drive_overrides}
        dispositions: list[DriveDisposition] = []
        for kind in REQUIRED_DRIVE_KINDS:
            baseline = 0.5
            sensitivity = 0.5
            override = override_map.get(kind)
            if override is not None:
                if override.baseline is not None:
                    baseline = override.baseline
                if override.sensitivity is not None:
                    sensitivity = override.sensitivity
            dispositions.append(
                DriveDisposition(kind=kind, baseline=baseline, sensitivity=sensitivity)
            )
        return DriveProfile(owner_id=self.agent_id, dispositions=tuple(dispositions))


@dataclass(frozen=True, slots=True)
class AgentRunnerSpec:
    """One registered agent with body ownership and cognition treatment."""

    agent_id: AgentId
    entity_id: EntityId
    cognition: AgentCognitionSpec

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("AgentRunnerSpec.agent_id must be AgentId")
        if type(self.entity_id) is not EntityId:
            raise TypeError("AgentRunnerSpec.entity_id must be EntityId")
        if type(self.cognition) is not AgentCognitionSpec:
            raise TypeError("AgentRunnerSpec.cognition must be AgentCognitionSpec")
        if self.cognition.agent_id != self.agent_id:
            raise ValueError("AgentRunnerSpec cognition.agent_id must match agent_id")

    def registration(self) -> AgentRegistration:
        return AgentRegistration(agent_id=self.agent_id, entity_id=self.entity_id)


@dataclass(frozen=True, slots=True)
class WorldScenarioSpec:
    """Replay-significant world topology and initial objective state."""

    world_id: WorldId
    revision: WorldRevision
    physical_rules: PhysicalRules
    locations: tuple[Location, ...]
    bodies: tuple[AgentBody, ...]
    items: tuple[Item, ...] = ()
    resources: tuple[Resource, ...] = ()
    weather: tuple[Weather, ...] = ()

    def __post_init__(self) -> None:
        if type(self.world_id) is not WorldId:
            raise TypeError("WorldScenarioSpec.world_id must be WorldId")
        if type(self.revision) is not WorldRevision:
            raise TypeError("WorldScenarioSpec.revision must be WorldRevision")
        if type(self.physical_rules) is not PhysicalRules:
            raise TypeError("WorldScenarioSpec.physical_rules must be PhysicalRules")
        object.__setattr__(
            self,
            "locations",
            _copy_ordered("WorldScenarioSpec.locations", self.locations, model_type=Location),
        )
        object.__setattr__(
            self,
            "bodies",
            _copy_ordered("WorldScenarioSpec.bodies", self.bodies, model_type=AgentBody),
        )
        object.__setattr__(
            self,
            "items",
            _copy_ordered("WorldScenarioSpec.items", self.items, model_type=Item),
        )
        object.__setattr__(
            self,
            "resources",
            _copy_ordered(
                "WorldScenarioSpec.resources", self.resources, model_type=Resource
            ),
        )
        object.__setattr__(
            self,
            "weather",
            _copy_ordered("WorldScenarioSpec.weather", self.weather, model_type=Weather),
        )
        if not self.locations:
            raise ValueError("WorldScenarioSpec.locations must be non-empty")
        if not self.bodies:
            raise ValueError("WorldScenarioSpec.bodies must be non-empty")
        body_ids = {body.entity_id for body in self.bodies}
        if len(body_ids) != len(self.bodies):
            raise ValueError("WorldScenarioSpec.bodies entity_ids must be unique")


@dataclass(frozen=True, slots=True)
class RunnerStopPolicy:
    """Closed stop evaluation policy for a configured run."""

    max_ticks: int
    stop_on_all_agents_terminal: bool = True
    allow_injected_stop: bool = True
    allow_cancellation: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "max_ticks", _require_positive_int("RunnerStopPolicy.max_ticks", self.max_ticks)
        )
        if type(self.stop_on_all_agents_terminal) is not bool:
            raise TypeError("stop_on_all_agents_terminal must be bool")
        if type(self.allow_injected_stop) is not bool:
            raise TypeError("allow_injected_stop must be bool")
        if type(self.allow_cancellation) is not bool:
            raise TypeError("allow_cancellation must be bool")


@dataclass(frozen=True, slots=True)
class RunnerCheckpointPolicy:
    """Durable checkpoint cadence. Cadence is in committed ticks."""

    enabled: bool = False
    cadence_ticks: int | None = None

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise TypeError("RunnerCheckpointPolicy.enabled must be bool")
        if self.enabled:
            if self.cadence_ticks is None:
                raise ValueError("checkpoint cadence_ticks required when enabled")
            object.__setattr__(
                self,
                "cadence_ticks",
                _require_positive_int(
                    "RunnerCheckpointPolicy.cadence_ticks", self.cadence_ticks
                ),
            )
        elif self.cadence_ticks is not None:
            raise ValueError("checkpoint cadence_ticks forbidden when disabled")


@dataclass(frozen=True, slots=True)
class RunnerPersistenceSpec:
    """Whether the run is durable and how checkpoints are taken."""

    durable: bool = False
    checkpoint: RunnerCheckpointPolicy = RunnerCheckpointPolicy()

    def __post_init__(self) -> None:
        if type(self.durable) is not bool:
            raise TypeError("RunnerPersistenceSpec.durable must be bool")
        if type(self.checkpoint) is not RunnerCheckpointPolicy:
            raise TypeError("checkpoint must be RunnerCheckpointPolicy")
        if self.checkpoint.enabled and not self.durable:
            raise ValueError("checkpoints require durable persistence")


@dataclass(frozen=True, slots=True)
class RunnerProviderSettings:
    """Credential-free, fingerprintable LLM settings for a run.

    API keys and base URLs are resolved by an injected credential/provider
    resolver at construction time and never appear in this contract.
    """

    adapter_kind: ProviderAdapterKind = ProviderAdapterKind.DISABLED
    model: str | None = None
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.JSON_SCHEMA
    temperature: float | None = None
    top_p: float | None = None
    provider_seed: int | None = None
    max_output_tokens: int | None = None
    stop_sequences: tuple[str, ...] = ()
    retry_count: int = 3
    per_attempt_timeout_seconds: float = 30.0
    total_deadline_seconds: float | None = None
    max_request_bytes: int = _DEFAULT_MAX_REQUEST_BYTES
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES
    max_header_bytes: int = _DEFAULT_MAX_HEADER_BYTES
    send_correlation_header: bool = False
    recording_policy: RecordingPolicy = RecordingPolicy.DETERMINISTIC_FAKE
    exact_reproducibility: ExactReproducibilityMode = ExactReproducibilityMode.REQUIRED
    settings_version: str = PROVIDER_SETTINGS_VERSION

    def __post_init__(self) -> None:
        if type(self.adapter_kind) is not ProviderAdapterKind:
            raise TypeError("adapter_kind must be ProviderAdapterKind")
        if type(self.structured_output_mode) is not StructuredOutputMode:
            raise TypeError("structured_output_mode must be StructuredOutputMode")
        if type(self.recording_policy) is not RecordingPolicy:
            raise TypeError("recording_policy must be RecordingPolicy")
        if type(self.exact_reproducibility) is not ExactReproducibilityMode:
            raise TypeError("exact_reproducibility must be ExactReproducibilityMode")
        if self.settings_version != PROVIDER_SETTINGS_VERSION:
            raise ValueError("unsupported provider settings_version")
        if self.model is not None:
            require_stable_id("RunnerProviderSettings.model", self.model)
        if self.temperature is not None:
            object.__setattr__(
                self,
                "temperature",
                _require_finite_float(
                    "temperature", self.temperature, minimum=0.0, maximum=2.0
                ),
            )
        if self.top_p is not None:
            object.__setattr__(
                self,
                "top_p",
                _require_finite_float("top_p", self.top_p, minimum=math.ulp(0.0), maximum=1.0),
            )
        if self.provider_seed is not None:
            object.__setattr__(
                self,
                "provider_seed",
                require_exact_nonneg_int("provider_seed", self.provider_seed),
            )
        if self.max_output_tokens is not None:
            object.__setattr__(
                self,
                "max_output_tokens",
                _require_positive_int("max_output_tokens", self.max_output_tokens),
            )
        stops = _copy_ordered(
            "stop_sequences", self.stop_sequences, model_type=str
        ) if self.stop_sequences else ()
        if len(stops) > 8:
            raise ValueError("stop_sequences exceeds maximum entries")
        for item in stops:
            if not item or item.strip() != item:
                raise ValueError("stop_sequences entries must be non-blank")
            if len(item) > 64:
                raise ValueError("stop_sequences entry exceeds maximum length")
        object.__setattr__(self, "stop_sequences", stops)
        object.__setattr__(
            self, "retry_count", _require_positive_int("retry_count", self.retry_count)
        )
        object.__setattr__(
            self,
            "per_attempt_timeout_seconds",
            _require_positive_float(
                "per_attempt_timeout_seconds", self.per_attempt_timeout_seconds
            ),
        )
        if self.total_deadline_seconds is not None:
            object.__setattr__(
                self,
                "total_deadline_seconds",
                _require_positive_float(
                    "total_deadline_seconds", self.total_deadline_seconds
                ),
            )
        object.__setattr__(
            self,
            "max_request_bytes",
            _require_positive_int("max_request_bytes", self.max_request_bytes),
        )
        object.__setattr__(
            self,
            "max_response_bytes",
            _require_positive_int("max_response_bytes", self.max_response_bytes),
        )
        object.__setattr__(
            self,
            "max_header_bytes",
            _require_positive_int("max_header_bytes", self.max_header_bytes),
        )
        if type(self.send_correlation_header) is not bool:
            raise TypeError("send_correlation_header must be bool")
        if self.exact_reproducibility is ExactReproducibilityMode.REQUIRED:
            if self.recording_policy is RecordingPolicy.LIVE:
                raise ValueError(
                    "exact reproducibility requires deterministic_fake or recorded "
                    "recording_policy"
                )
            if self.adapter_kind not in {
                ProviderAdapterKind.DISABLED,
            } and self.recording_policy is RecordingPolicy.LIVE:
                raise ValueError("live adapter incompatible with exact reproducibility")
        forbidden = {"api_key", "base_url", "endpoint", "authorization"}
        # Structural guard: dataclass has no credential fields by construction.
        for name in forbidden:
            if hasattr(self, name):
                raise ValueError(f"provider settings must not include {name}")


@dataclass(frozen=True, slots=True)
class ExperimentAssignmentRef:
    """Optional experiment condition/replicate identity for a run."""

    experiment_id: str
    condition_id: str
    replicate_index: int = 0
    seed_ordinal: int = 0

    def __post_init__(self) -> None:
        require_stable_id("experiment_id", self.experiment_id)
        require_stable_id("condition_id", self.condition_id)
        object.__setattr__(
            self,
            "replicate_index",
            require_exact_nonneg_int("replicate_index", self.replicate_index),
        )
        object.__setattr__(
            self,
            "seed_ordinal",
            require_exact_nonneg_int("seed_ordinal", self.seed_ordinal),
        )


@dataclass(frozen=True, slots=True)
class SimulationRunnerConfig:
    """Top-level immutable runner specification for one configured run.

    Durable ``RunId`` is assigned at construction/execution time and is not part
    of this replay-significant world/cognition specification. Paired arms share
    ``seed`` + ``stochastic_identity`` + scenario while varying cognition modes.
    """

    seed: int
    stochastic_identity: StochasticIdentity
    scenario: WorldScenarioSpec
    agents: tuple[AgentRunnerSpec, ...]
    stop_policy: RunnerStopPolicy
    mortality_mode: MortalityMode = MortalityMode.ENABLED
    cognition_failure_policy: CognitionFailurePolicy = CognitionFailurePolicy.ABORT_TICK
    provider: RunnerProviderSettings = RunnerProviderSettings()
    persistence: RunnerPersistenceSpec = RunnerPersistenceSpec()
    experiment: ExperimentAssignmentRef | None = None
    schema_version: str = RUNNER_SCHEMA_VERSION
    derivation_version: str = DERIVATION_VERSION_V3
    mortality_policy_version: str = MORTALITY_POLICY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "seed", require_seed(self.seed))
        object.__setattr__(
            self,
            "stochastic_identity",
            require_stochastic_identity(self.stochastic_identity),
        )
        if type(self.scenario) is not WorldScenarioSpec:
            raise TypeError("scenario must be WorldScenarioSpec")
        agents = _copy_ordered(
            "SimulationRunnerConfig.agents", self.agents, model_type=AgentRunnerSpec
        )
        if not agents:
            raise ValueError("agents must be non-empty")
        agent_ids = [agent.agent_id for agent in agents]
        entity_ids = [agent.entity_id for agent in agents]
        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError("agent_ids must be unique")
        if len(set(entity_ids)) != len(entity_ids):
            raise ValueError("entity_ids must be unique")
        body_ids = {body.entity_id for body in self.scenario.bodies}
        for agent in agents:
            if agent.entity_id not in body_ids:
                raise ValueError("agent entity_id must reference a scenario body")
        if set(entity_ids) != body_ids:
            raise ValueError("agents must cover scenario bodies exactly")
        object.__setattr__(self, "agents", agents)
        if type(self.stop_policy) is not RunnerStopPolicy:
            raise TypeError("stop_policy must be RunnerStopPolicy")
        if type(self.mortality_mode) is not MortalityMode:
            raise TypeError("mortality_mode must be MortalityMode")
        if type(self.cognition_failure_policy) is not CognitionFailurePolicy:
            raise TypeError("cognition_failure_policy must be CognitionFailurePolicy")
        if type(self.provider) is not RunnerProviderSettings:
            raise TypeError("provider must be RunnerProviderSettings")
        if type(self.persistence) is not RunnerPersistenceSpec:
            raise TypeError("persistence must be RunnerPersistenceSpec")
        if self.experiment is not None and type(self.experiment) is not ExperimentAssignmentRef:
            raise TypeError("experiment must be ExperimentAssignmentRef or None")
        if self.schema_version != RUNNER_SCHEMA_VERSION:
            raise ValueError("unsupported runner schema_version")
        if require_derivation_version(self.derivation_version) != DERIVATION_VERSION_V3:
            raise ValueError("runner config requires derivation-v3")
        if self.mortality_policy_version != MORTALITY_POLICY_VERSION:
            raise ValueError("unsupported mortality_policy_version")
        _LOGGER.debug(
            "runner_config_validated schema_version=%s agent_count=%s "
            "location_count=%s max_ticks=%s mortality_mode=%s",
            self.schema_version,
            len(self.agents),
            len(self.scenario.locations),
            self.stop_policy.max_ticks,
            self.mortality_mode.value,
        )

    def ordered_registrations(self) -> tuple[AgentRegistration, ...]:
        return tuple(agent.registration() for agent in self.agents)


@dataclass(frozen=True, slots=True)
class RunnerConfigDiagnostics:
    """Metadata-only projection safe for DEBUG/INFO logs."""

    schema_version: str
    derivation_version: str
    agent_count: int
    location_count: int
    resource_count: int
    max_ticks: int
    memory_modes: tuple[str, ...]
    imagination_modes: tuple[str, ...]
    mortality_mode: str
    provider_adapter: str
    recording_policy: str
    durable: bool
    config_fingerprint_prefix: str
    scenario_fingerprint_prefix: str
    cognition_fingerprint_prefix: str
    provider_fingerprint_prefix: str
    stochastic_fingerprint_prefix: str
    rules_fingerprint_prefix: str


def runner_config_diagnostics(
    config: SimulationRunnerConfig,
    *,
    config_fingerprint: str,
    scenario_fingerprint: str,
    cognition_fingerprint: str,
    provider_fingerprint: str,
) -> RunnerConfigDiagnostics:
    """Build a payload-free diagnostic projection for logging."""
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("runner_config_diagnostics requires SimulationRunnerConfig")
    return RunnerConfigDiagnostics(
        schema_version=config.schema_version,
        derivation_version=config.derivation_version,
        agent_count=len(config.agents),
        location_count=len(config.scenario.locations),
        resource_count=len(config.scenario.resources),
        max_ticks=config.stop_policy.max_ticks,
        memory_modes=tuple(agent.cognition.memory_mode.value for agent in config.agents),
        imagination_modes=tuple(
            agent.cognition.imagination_mode.value for agent in config.agents
        ),
        mortality_mode=config.mortality_mode.value,
        provider_adapter=config.provider.adapter_kind.value,
        recording_policy=config.provider.recording_policy.value,
        durable=config.persistence.durable,
        config_fingerprint_prefix=config_fingerprint[:12],
        scenario_fingerprint_prefix=scenario_fingerprint[:12],
        cognition_fingerprint_prefix=cognition_fingerprint[:12],
        provider_fingerprint_prefix=provider_fingerprint[:12],
        stochastic_fingerprint_prefix=stochastic_identity_fingerprint(
            config.stochastic_identity
        )[:12],
        rules_fingerprint_prefix=physical_rules_fingerprint(
            config.scenario.physical_rules
        )[:12],
    )


def describe_runner_config(diagnostics: RunnerConfigDiagnostics) -> Mapping[str, object]:
    """Dict form of diagnostics for structured logs (no secrets/payloads)."""
    if type(diagnostics) is not RunnerConfigDiagnostics:
        raise TypeError("describe_runner_config requires RunnerConfigDiagnostics")
    return {
        "schema_version": diagnostics.schema_version,
        "derivation_version": diagnostics.derivation_version,
        "agent_count": diagnostics.agent_count,
        "location_count": diagnostics.location_count,
        "resource_count": diagnostics.resource_count,
        "max_ticks": diagnostics.max_ticks,
        "memory_modes": diagnostics.memory_modes,
        "imagination_modes": diagnostics.imagination_modes,
        "mortality_mode": diagnostics.mortality_mode,
        "provider_adapter": diagnostics.provider_adapter,
        "recording_policy": diagnostics.recording_policy,
        "durable": diagnostics.durable,
        "config_fingerprint_prefix": diagnostics.config_fingerprint_prefix,
        "scenario_fingerprint_prefix": diagnostics.scenario_fingerprint_prefix,
        "cognition_fingerprint_prefix": diagnostics.cognition_fingerprint_prefix,
        "provider_fingerprint_prefix": diagnostics.provider_fingerprint_prefix,
        "stochastic_fingerprint_prefix": diagnostics.stochastic_fingerprint_prefix,
        "rules_fingerprint_prefix": diagnostics.rules_fingerprint_prefix,
    }
