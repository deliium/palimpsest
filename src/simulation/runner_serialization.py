"""Strict canonical JSON codecs and fingerprints for runner configuration.

Codecs are log-free. Errors expose only stable ``code`` and ``path`` metadata.
Credentials, base URLs, prompts, and full seed-bearing dumps never appear in
exception messages.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from agents.models import AgentId, DriveKind
from llm.factory import ProviderAdapterKind
from llm.models import StructuredOutputMode
from simulation.models import StochasticIdentity
from simulation.runner_models import (
    COGNITION_POLICY_VERSION,
    MORTALITY_POLICY_VERSION,
    PROVIDER_SETTINGS_VERSION,
    RUNNER_SCHEMA_VERSION,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CognitionFailurePolicy,
    DriveOverrideSpec,
    ExactReproducibilityMode,
    ExperimentAssignmentRef,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    RecordingPolicy,
    RunnerCheckpointPolicy,
    RunnerConfigDiagnostics,
    RunnerPersistenceSpec,
    RunnerProviderSettings,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
    runner_config_diagnostics,
)
from simulation.serialization import (
    DomainSerializationError,
    _decode_agent_body,
    _decode_item,
    _decode_location,
    _decode_physical_rules,
    _decode_resource,
    _decode_weather,
    _encode_agent_body,
    _encode_item,
    _encode_location,
    _encode_physical_rules,
    _encode_resource,
    _encode_weather,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import physical_rules_fingerprint

__all__ = [
    "RunnerSerializationError",
    "build_runner_diagnostics",
    "cognition_fingerprint",
    "decode_runner_config",
    "encode_runner_config",
    "provider_fingerprint",
    "runner_config_fingerprint",
    "scenario_fingerprint",
]


class RunnerSerializationError(ValueError):
    """Fail-closed runner codec error with stable metadata only."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}:{path}")


def _canonical_dumps(value: object) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return text.encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RunnerSerializationError("duplicate_key", "$")
        result[key] = value
    return result


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_keys(data: Mapping[str, Any], required: set[str], *, path: str) -> None:
    keys = set(data)
    if required - keys:
        raise RunnerSerializationError("missing_field", path)
    if keys - required:
        raise RunnerSerializationError("invalid_fields", path)


def _str_field(data: Mapping[str, Any], key: str, *, path: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise RunnerSerializationError("invalid_string", f"{path}.{key}")
    return value


def _bool_field(data: Mapping[str, Any], key: str, *, path: str) -> bool:
    value = data[key]
    if type(value) is not bool:
        raise RunnerSerializationError("invalid_bool", f"{path}.{key}")
    return value


def _nonneg_int_field(data: Mapping[str, Any], key: str, *, path: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RunnerSerializationError("invalid_int", f"{path}.{key}")
    return value


def _optional_float(data: Mapping[str, Any], key: str, *, path: str) -> float | None:
    if key not in data or data[key] is None:
        return None
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RunnerSerializationError("invalid_number", f"{path}.{key}")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise RunnerSerializationError("non_finite_number", f"{path}.{key}")
    return number


def _map_domain(exc: DomainSerializationError) -> RunnerSerializationError:
    code = exc.code
    if code == "non_finite_float":
        code = "non_finite_number"
    return RunnerSerializationError(code, exc.path)


def _raise_invalid_object(path: str) -> bool:
    raise RunnerSerializationError("invalid_object", path)


def _encode_drive_override(value: DriveOverrideSpec) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": value.kind.value}
    if value.baseline is not None:
        payload["baseline"] = value.baseline
    if value.sensitivity is not None:
        payload["sensitivity"] = value.sensitivity
    return payload


def _decode_drive_override(data: dict[str, Any], *, path: str) -> DriveOverrideSpec:
    allowed = {"kind", "baseline", "sensitivity"}
    if set(data) - allowed or "kind" not in data:
        raise RunnerSerializationError("invalid_fields", path)
    try:
        kind = DriveKind(_str_field(data, "kind", path=path))
    except ValueError as exc:
        raise RunnerSerializationError("invalid_enum", f"{path}.kind") from exc
    try:
        return DriveOverrideSpec(
            kind=kind,
            baseline=_optional_float(data, "baseline", path=path),
            sensitivity=_optional_float(data, "sensitivity", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_cognition(value: AgentCognitionSpec) -> dict[str, Any]:
    return {
        "agent_id": value.agent_id.value,
        "drive_overrides": [
            _encode_drive_override(item) for item in value.drive_overrides
        ],
        "imagination_mode": value.imagination_mode.value,
        "memory_mode": value.memory_mode.value,
        "policy_version": value.policy_version,
    }


def _decode_cognition(data: dict[str, Any], *, path: str) -> AgentCognitionSpec:
    _require_keys(
        data,
        {
            "agent_id",
            "memory_mode",
            "imagination_mode",
            "drive_overrides",
            "policy_version",
        },
        path=path,
    )
    overrides_raw = data["drive_overrides"]
    if not isinstance(overrides_raw, list):
        raise RunnerSerializationError("invalid_array", f"{path}.drive_overrides")
    overrides: list[DriveOverrideSpec] = []
    for index, item in enumerate(overrides_raw):
        if not isinstance(item, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.drive_overrides[{index}]"
            )
        overrides.append(
            _decode_drive_override(item, path=f"{path}.drive_overrides[{index}]")
        )
    try:
        return AgentCognitionSpec(
            agent_id=AgentId(_str_field(data, "agent_id", path=path)),
            memory_mode=MemoryMode(_str_field(data, "memory_mode", path=path)),
            imagination_mode=ImaginationMode(
                _str_field(data, "imagination_mode", path=path)
            ),
            drive_overrides=tuple(overrides),
            policy_version=_str_field(data, "policy_version", path=path),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_agent(value: AgentRunnerSpec) -> dict[str, Any]:
    return {
        "agent_id": value.agent_id.value,
        "cognition": _encode_cognition(value.cognition),
        "entity_id": value.entity_id.value,
    }


def _decode_agent(data: dict[str, Any], *, path: str) -> AgentRunnerSpec:
    _require_keys(data, {"agent_id", "entity_id", "cognition"}, path=path)
    cognition_raw = data["cognition"]
    if not isinstance(cognition_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.cognition")
    try:
        return AgentRunnerSpec(
            agent_id=AgentId(_str_field(data, "agent_id", path=path)),
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            cognition=_decode_cognition(cognition_raw, path=f"{path}.cognition"),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_scenario(value: WorldScenarioSpec) -> dict[str, Any]:
    try:
        return {
            "bodies": [_encode_agent_body(body) for body in value.bodies],
            "items": [_encode_item(item) for item in value.items],
            "locations": [_encode_location(loc) for loc in value.locations],
            "physical_rules": _encode_physical_rules(value.physical_rules),
            "resources": [_encode_resource(item) for item in value.resources],
            "revision": value.revision.value,
            "rules_fingerprint": physical_rules_fingerprint(value.physical_rules),
            "weather": [_encode_weather(item) for item in value.weather],
            "world_id": value.world_id.value,
        }
    except DomainSerializationError as exc:
        raise _map_domain(exc) from exc


def _decode_scenario(data: dict[str, Any], *, path: str) -> WorldScenarioSpec:
    _require_keys(
        data,
        {
            "world_id",
            "revision",
            "physical_rules",
            "rules_fingerprint",
            "locations",
            "bodies",
            "items",
            "resources",
            "weather",
        },
        path=path,
    )
    rules_raw = data["physical_rules"]
    if not isinstance(rules_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.physical_rules")
    try:
        rules = _decode_physical_rules(rules_raw, path=f"{path}.physical_rules")
    except DomainSerializationError as exc:
        raise _map_domain(exc) from exc
    expected = _str_field(data, "rules_fingerprint", path=path)
    if physical_rules_fingerprint(rules) != expected:
        raise RunnerSerializationError("hash_mismatch", f"{path}.rules_fingerprint")

    def _decode_list(key: str, decoder: Any) -> tuple[Any, ...]:
        raw = data[key]
        if not isinstance(raw, list):
            raise RunnerSerializationError("invalid_array", f"{path}.{key}")
        items: list[Any] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise RunnerSerializationError(
                    "invalid_object", f"{path}.{key}[{index}]"
                )
            try:
                items.append(decoder(item, path=f"{path}.{key}[{index}]"))
            except DomainSerializationError as exc:
                raise _map_domain(exc) from exc
        return tuple(items)

    try:
        return WorldScenarioSpec(
            world_id=WorldId(_str_field(data, "world_id", path=path)),
            revision=WorldRevision(_nonneg_int_field(data, "revision", path=path)),
            physical_rules=rules,
            locations=_decode_list("locations", _decode_location),
            bodies=_decode_list("bodies", _decode_agent_body),
            items=_decode_list("items", _decode_item),
            resources=_decode_list("resources", _decode_resource),
            weather=_decode_list("weather", _decode_weather),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _require_positive_number_field(
    data: Mapping[str, Any], key: str, *, path: str
) -> float:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RunnerSerializationError("invalid_number", f"{path}.{key}")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")} or number <= 0.0:
        raise RunnerSerializationError("invalid_number", f"{path}.{key}")
    return number


def _encode_provider(value: RunnerProviderSettings) -> dict[str, Any]:
    return {
        "adapter_kind": value.adapter_kind.value,
        "exact_reproducibility": value.exact_reproducibility.value,
        "max_header_bytes": value.max_header_bytes,
        "max_output_tokens": value.max_output_tokens,
        "max_request_bytes": value.max_request_bytes,
        "max_response_bytes": value.max_response_bytes,
        "model": value.model,
        "per_attempt_timeout_seconds": value.per_attempt_timeout_seconds,
        "provider_seed": value.provider_seed,
        "recording_policy": value.recording_policy.value,
        "retry_count": value.retry_count,
        "send_correlation_header": value.send_correlation_header,
        "settings_version": value.settings_version,
        "stop_sequences": list(value.stop_sequences),
        "structured_output_mode": value.structured_output_mode.value,
        "temperature": value.temperature,
        "top_p": value.top_p,
        "total_deadline_seconds": value.total_deadline_seconds,
    }


def _decode_provider(data: dict[str, Any], *, path: str) -> RunnerProviderSettings:
    required = {
        "adapter_kind",
        "model",
        "structured_output_mode",
        "temperature",
        "top_p",
        "provider_seed",
        "max_output_tokens",
        "stop_sequences",
        "retry_count",
        "per_attempt_timeout_seconds",
        "total_deadline_seconds",
        "max_request_bytes",
        "max_response_bytes",
        "max_header_bytes",
        "send_correlation_header",
        "recording_policy",
        "exact_reproducibility",
        "settings_version",
    }
    _require_keys(data, required, path=path)
    if any(key in data for key in ("api_key", "base_url", "endpoint", "authorization")):
        raise RunnerSerializationError("credentials_forbidden", path)
    stops_raw = data["stop_sequences"]
    if not isinstance(stops_raw, list):
        raise RunnerSerializationError("invalid_array", f"{path}.stop_sequences")
    stops: list[str] = []
    for index, item in enumerate(stops_raw):
        if not isinstance(item, str):
            raise RunnerSerializationError(
                "invalid_string", f"{path}.stop_sequences[{index}]"
            )
        stops.append(item)
    model = data["model"]
    if model is not None and not isinstance(model, str):
        raise RunnerSerializationError("invalid_string", f"{path}.model")
    max_output = data["max_output_tokens"]
    provider_seed = data["provider_seed"]
    try:
        return RunnerProviderSettings(
            adapter_kind=ProviderAdapterKind(
                _str_field(data, "adapter_kind", path=path)
            ),
            model=model,
            structured_output_mode=StructuredOutputMode(
                _str_field(data, "structured_output_mode", path=path)
            ),
            temperature=_optional_float(data, "temperature", path=path),
            top_p=_optional_float(data, "top_p", path=path),
            provider_seed=(
                None
                if provider_seed is None
                else _nonneg_int_field(data, "provider_seed", path=path)
            ),
            max_output_tokens=(
                None
                if max_output is None
                else _nonneg_int_field(data, "max_output_tokens", path=path)
            ),
            stop_sequences=tuple(stops),
            retry_count=_nonneg_int_field(data, "retry_count", path=path),
            per_attempt_timeout_seconds=_require_positive_number_field(
                data, "per_attempt_timeout_seconds", path=path
            ),
            total_deadline_seconds=_optional_float(
                data, "total_deadline_seconds", path=path
            ),
            max_request_bytes=_nonneg_int_field(data, "max_request_bytes", path=path),
            max_response_bytes=_nonneg_int_field(data, "max_response_bytes", path=path),
            max_header_bytes=_nonneg_int_field(data, "max_header_bytes", path=path),
            send_correlation_header=_bool_field(
                data, "send_correlation_header", path=path
            ),
            recording_policy=RecordingPolicy(
                _str_field(data, "recording_policy", path=path)
            ),
            exact_reproducibility=ExactReproducibilityMode(
                _str_field(data, "exact_reproducibility", path=path)
            ),
            settings_version=_str_field(data, "settings_version", path=path),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_runner_document(config: SimulationRunnerConfig) -> dict[str, Any]:
    document: dict[str, Any] = {
        "agents": [_encode_agent(agent) for agent in config.agents],
        "cognition_failure_policy": config.cognition_failure_policy.value,
        "derivation_version": config.derivation_version,
        "mortality_mode": config.mortality_mode.value,
        "mortality_policy_version": config.mortality_policy_version,
        "persistence": {
            "checkpoint": {
                "cadence_ticks": config.persistence.checkpoint.cadence_ticks,
                "enabled": config.persistence.checkpoint.enabled,
            },
            "durable": config.persistence.durable,
        },
        "provider": _encode_provider(config.provider),
        "scenario": _encode_scenario(config.scenario),
        "schema_version": config.schema_version,
        "seed": config.seed,
        "stochastic_identity": config.stochastic_identity.value,
        "stop_policy": {
            "allow_cancellation": config.stop_policy.allow_cancellation,
            "allow_injected_stop": config.stop_policy.allow_injected_stop,
            "max_ticks": config.stop_policy.max_ticks,
            "stop_on_all_agents_terminal": (
                config.stop_policy.stop_on_all_agents_terminal
            ),
        },
    }
    if config.experiment is not None:
        document["experiment"] = {
            "condition_id": config.experiment.condition_id,
            "experiment_id": config.experiment.experiment_id,
            "replicate_index": config.experiment.replicate_index,
            "seed_ordinal": config.experiment.seed_ordinal,
        }
    else:
        document["experiment"] = None
    return document


def encode_runner_config(config: SimulationRunnerConfig) -> bytes:
    """Encode a runner config to strict canonical UTF-8 JSON bytes."""
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("encode_runner_config requires SimulationRunnerConfig")
    return _canonical_dumps(_encode_runner_document(config))


def decode_runner_config(payload: bytes) -> SimulationRunnerConfig:
    """Decode strict canonical runner config bytes."""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("decode_runner_config requires bytes")
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
        data = decoder.decode(bytes(payload).decode("utf-8"))
    except RunnerSerializationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerSerializationError("invalid_json", "$") from exc
    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", "$")
    _require_keys(
        data,
        {
            "schema_version",
            "derivation_version",
            "seed",
            "stochastic_identity",
            "scenario",
            "agents",
            "stop_policy",
            "mortality_mode",
            "mortality_policy_version",
            "cognition_failure_policy",
            "provider",
            "persistence",
            "experiment",
        },
        path="$",
    )
    if _str_field(data, "schema_version", path="$") != RUNNER_SCHEMA_VERSION:
        raise RunnerSerializationError("unsupported_version", "$.schema_version")
    if _str_field(data, "mortality_policy_version", path="$") != MORTALITY_POLICY_VERSION:
        raise RunnerSerializationError(
            "unsupported_version", "$.mortality_policy_version"
        )
    scenario_raw = data["scenario"]
    provider_raw = data["provider"]
    agents_raw = data["agents"]
    stop_raw = data["stop_policy"]
    persistence_raw = data["persistence"]
    if not isinstance(scenario_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.scenario")
    if not isinstance(provider_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.provider")
    if not isinstance(agents_raw, list):
        raise RunnerSerializationError("invalid_array", "$.agents")
    if not isinstance(stop_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.stop_policy")
    if not isinstance(persistence_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.persistence")
    _require_keys(
        stop_raw,
        {
            "max_ticks",
            "stop_on_all_agents_terminal",
            "allow_injected_stop",
            "allow_cancellation",
        },
        path="$.stop_policy",
    )
    _require_keys(persistence_raw, {"durable", "checkpoint"}, path="$.persistence")
    checkpoint_raw = persistence_raw["checkpoint"]
    if not isinstance(checkpoint_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.persistence.checkpoint")
    _require_keys(
        checkpoint_raw, {"enabled", "cadence_ticks"}, path="$.persistence.checkpoint"
    )
    experiment: ExperimentAssignmentRef | None = None
    experiment_raw = data["experiment"]
    if experiment_raw is not None:
        if not isinstance(experiment_raw, dict):
            raise RunnerSerializationError("invalid_object", "$.experiment")
        _require_keys(
            experiment_raw,
            {"experiment_id", "condition_id", "replicate_index", "seed_ordinal"},
            path="$.experiment",
        )
        try:
            experiment = ExperimentAssignmentRef(
                experiment_id=_str_field(
                    experiment_raw, "experiment_id", path="$.experiment"
                ),
                condition_id=_str_field(
                    experiment_raw, "condition_id", path="$.experiment"
                ),
                replicate_index=_nonneg_int_field(
                    experiment_raw, "replicate_index", path="$.experiment"
                ),
                seed_ordinal=_nonneg_int_field(
                    experiment_raw, "seed_ordinal", path="$.experiment"
                ),
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", "$.experiment") from exc
    agents_list: list[AgentRunnerSpec] = []
    for index, item in enumerate(agents_raw):
        if not isinstance(item, dict):
            raise RunnerSerializationError("invalid_object", f"$.agents[{index}]")
        agents_list.append(_decode_agent(item, path=f"$.agents[{index}]"))
    cadence = checkpoint_raw["cadence_ticks"]
    if cadence is not None and (
        isinstance(cadence, bool) or not isinstance(cadence, int) or cadence < 0
    ):
        raise RunnerSerializationError(
            "invalid_int", "$.persistence.checkpoint.cadence_ticks"
        )
    try:
        return SimulationRunnerConfig(
            seed=_nonneg_int_field(data, "seed", path="$"),
            stochastic_identity=StochasticIdentity(
                _str_field(data, "stochastic_identity", path="$")
            ),
            scenario=_decode_scenario(scenario_raw, path="$.scenario"),
            agents=tuple(agents_list),
            stop_policy=RunnerStopPolicy(
                max_ticks=_nonneg_int_field(stop_raw, "max_ticks", path="$.stop_policy"),
                stop_on_all_agents_terminal=_bool_field(
                    stop_raw, "stop_on_all_agents_terminal", path="$.stop_policy"
                ),
                allow_injected_stop=_bool_field(
                    stop_raw, "allow_injected_stop", path="$.stop_policy"
                ),
                allow_cancellation=_bool_field(
                    stop_raw, "allow_cancellation", path="$.stop_policy"
                ),
            ),
            mortality_mode=MortalityMode(_str_field(data, "mortality_mode", path="$")),
            cognition_failure_policy=CognitionFailurePolicy(
                _str_field(data, "cognition_failure_policy", path="$")
            ),
            provider=_decode_provider(provider_raw, path="$.provider"),
            persistence=RunnerPersistenceSpec(
                durable=_bool_field(persistence_raw, "durable", path="$.persistence"),
                checkpoint=RunnerCheckpointPolicy(
                    enabled=_bool_field(
                        checkpoint_raw, "enabled", path="$.persistence.checkpoint"
                    ),
                    cadence_ticks=cadence,
                ),
            ),
            experiment=experiment,
            schema_version=_str_field(data, "schema_version", path="$"),
            derivation_version=_str_field(data, "derivation_version", path="$"),
            mortality_policy_version=_str_field(
                data, "mortality_policy_version", path="$"
            ),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", "$") from exc


def runner_config_fingerprint(config: SimulationRunnerConfig) -> str:
    return _sha256_hex(encode_runner_config(config))


def scenario_fingerprint(config: SimulationRunnerConfig) -> str:
    document = {
        "derivation_version": config.derivation_version,
        "scenario": _encode_scenario(config.scenario),
        "seed": config.seed,
        "stochastic_identity": config.stochastic_identity.value,
    }
    return _sha256_hex(_canonical_dumps(document))


def cognition_fingerprint(config: SimulationRunnerConfig) -> str:
    document = {
        "agents": [
            {
                "agent_id": agent.agent_id.value,
                "cognition": _encode_cognition(agent.cognition),
            }
            for agent in config.agents
        ],
        "mortality_mode": config.mortality_mode.value,
        "mortality_policy_version": config.mortality_policy_version,
        "policy_version": COGNITION_POLICY_VERSION,
    }
    return _sha256_hex(_canonical_dumps(document))


def provider_fingerprint(config: SimulationRunnerConfig) -> str:
    document = {
        "provider": _encode_provider(config.provider),
        "settings_version": PROVIDER_SETTINGS_VERSION,
    }
    return _sha256_hex(_canonical_dumps(document))


def build_runner_diagnostics(
    config: SimulationRunnerConfig,
) -> RunnerConfigDiagnostics:
    """Convenience wrapper used by contracts logging helpers."""
    return runner_config_diagnostics(
        config,
        config_fingerprint=runner_config_fingerprint(config),
        scenario_fingerprint=scenario_fingerprint(config),
        cognition_fingerprint=cognition_fingerprint(config),
        provider_fingerprint=provider_fingerprint(config),
    )


def encode_runner_result_document(document: object) -> bytes:
    """Encode a result document as strict canonical JSON bytes."""
    from simulation.runner_models import RESULT_SCHEMA_VERSION, SimulationRunnerResultDocument

    if type(document) is not SimulationRunnerResultDocument:
        raise TypeError("encode_runner_result_document requires SimulationRunnerResultDocument")
    payload = {
        "schema_version": document.schema_version,
        "run_id": document.run_id,
        "stop_reason": document.stop_reason,
        "ticks_committed": document.ticks_committed,
        "config_fingerprint": document.config_fingerprint,
        "scenario_fingerprint": document.scenario_fingerprint,
        "cognition_fingerprint": document.cognition_fingerprint,
        "exact_trajectory_hash": document.exact_trajectory_hash,
        "replica_normalized_trajectory_hash": document.replica_normalized_trajectory_hash,
        "attempt_count": document.attempt_count,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def runner_result_fingerprint(document: object) -> str:
    return hashlib.sha256(encode_runner_result_document(document)).hexdigest()


def build_runner_result_document(
    *,
    result: object,
    config: SimulationRunnerConfig,
) -> object:
    """Build a versioned result document from a finalized runner result."""
    from simulation.runner_models import (
        RESULT_SCHEMA_VERSION,
        SimulationRunnerResult,
        SimulationRunnerResultDocument,
    )

    if type(result) is not SimulationRunnerResult:
        raise TypeError("result must be SimulationRunnerResult")
    return SimulationRunnerResultDocument(
        schema_version=RESULT_SCHEMA_VERSION,
        run_id=result.run_id.value,
        stop_reason=result.stop_reason.value,
        ticks_committed=result.ticks_committed,
        config_fingerprint=runner_config_fingerprint(config),
        scenario_fingerprint=scenario_fingerprint(config),
        cognition_fingerprint=cognition_fingerprint(config),
        exact_trajectory_hash=hashlib.sha256(
            f"exact|{result.run_id.value}|{result.ticks_committed}".encode()
        ).hexdigest(),
        replica_normalized_trajectory_hash=hashlib.sha256(
            f"replica|{config.stochastic_identity.value}|{result.ticks_committed}".encode()
        ).hexdigest(),
        attempt_count=len(result.attempt_receipts),
    )
