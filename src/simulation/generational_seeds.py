"""Truthful, payload-free seed lineage for generational runs.

The manifest describes the actual stream inputs used by existing deterministic
channels. It does not unify seeds, remove reserved draws, or claim that a new
durable run ID reproduces run-ID-scoped channels.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from simulation.models import RunId
from simulation.runner_models import (
    PopulationLifecycleSpec,
    RecordingPolicy,
    SimulationRunnerConfig,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id
from world.models import physical_rules_fingerprint

_LOGGER: Final[logging.Logger] = logging.getLogger(
    "simulation.generational_seeds"
)

_DRAW_USAGE_VALUES: Final[frozenset[str]] = frozenset(
    {"absent", "reserved_ignored", "deterministic_hash", "sampled"}
)


def canonical_sha256(payload: object) -> str:
    """SHA-256 of sorted-key canonical UTF-8 JSON."""
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                require_stable_id("json key", key): _freeze_json(item)
                for key, item in value.items()
            }
        )
    if isinstance(value, tuple):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class SeedChannelLineage:
    """One channel's actual algorithm, scope, and draw usage."""

    name: str
    algorithm_version: str
    namespace: str
    identity_selector: str
    scope_fields: tuple[str, ...]
    draw_usage: str

    def __post_init__(self) -> None:
        for name in (
            "name",
            "algorithm_version",
            "namespace",
            "identity_selector",
        ):
            object.__setattr__(
                self,
                name,
                require_stable_id(
                    f"SeedChannelLineage.{name}", getattr(self, name)
                ),
            )
        fields = tuple(self.scope_fields)
        if not fields:
            raise ValueError("scope_fields must be non-empty")
        for field_name in fields:
            require_stable_id("SeedChannelLineage.scope_fields", field_name)
        object.__setattr__(self, "scope_fields", fields)
        if self.draw_usage not in _DRAW_USAGE_VALUES:
            raise ValueError("unknown draw_usage")
        _LOGGER.debug(
            "seed_channel_lineage channel=%s namespace=%s draw_usage=%s",
            self.name,
            self.namespace,
            self.draw_usage,
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "draw_usage": self.draw_usage,
            "identity_selector": self.identity_selector,
            "name": self.name,
            "namespace": self.namespace,
            "scope_fields": list(self.scope_fields),
        }


@dataclass(frozen=True, slots=True)
class InitializationSeedIdentity:
    profile_id: str
    parameter_distributions_hash: str
    lifespan_distribution_hash: str

    def __post_init__(self) -> None:
        for name in (
            "profile_id",
            "parameter_distributions_hash",
            "lifespan_distribution_hash",
        ):
            require_stable_id(
                f"InitializationSeedIdentity.{name}", getattr(self, name)
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "lifespan_distribution_hash": self.lifespan_distribution_hash,
            "parameter_distributions_hash": self.parameter_distributions_hash,
            "profile_id": self.profile_id,
        }


@dataclass(frozen=True, slots=True)
class GenerationalSeedManifest:
    seed: int
    derivation_version: str
    run_id: str
    stochastic_identity: str
    physical_rules_fingerprint: str
    schedule_fingerprint: str
    initialization_identity: InitializationSeedIdentity
    channels: tuple[SeedChannelLineage, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "seed", require_exact_nonneg_int("seed", self.seed)
        )
        for name in (
            "derivation_version",
            "run_id",
            "stochastic_identity",
            "physical_rules_fingerprint",
            "schedule_fingerprint",
        ):
            object.__setattr__(
                self,
                name,
                require_stable_id(
                    f"GenerationalSeedManifest.{name}", getattr(self, name)
                ),
            )
        if type(self.initialization_identity) is not InitializationSeedIdentity:
            raise TypeError(
                "initialization_identity must be InitializationSeedIdentity"
            )
        if isinstance(self.channels, (str, bytes, set, frozenset)) or not isinstance(
            self.channels, Sequence
        ):
            raise TypeError("channels must be an ordered sequence")
        channels = tuple(self.channels)
        for channel in channels:
            if type(channel) is not SeedChannelLineage:
                raise TypeError("channels entries must be SeedChannelLineage")
        ordered = tuple(sorted(channels, key=lambda item: item.name))
        if len({channel.name for channel in ordered}) != len(ordered):
            raise ValueError("channel names must be unique")
        object.__setattr__(self, "channels", ordered)

    @property
    def manifest_hash(self) -> str:
        return canonical_sha256(self.canonical_payload())

    def canonical_payload(self) -> dict[str, object]:
        return {
            "channels": [item.canonical_payload() for item in self.channels],
            "derivation_version": self.derivation_version,
            "initialization_identity": (
                self.initialization_identity.canonical_payload()
            ),
            "physical_rules_fingerprint": self.physical_rules_fingerprint,
            "run_id": self.run_id,
            "schedule_fingerprint": self.schedule_fingerprint,
            "seed": self.seed,
            "stochastic_identity": self.stochastic_identity,
        }


def _schedule_fingerprint(spec: PopulationLifecycleSpec) -> str:
    return canonical_sha256(
        {
            "demographic_policy_id": spec.demographic_policy_id,
            "demographic_policy_params": {
                key: _thaw(spec.demographic_policy_params[key])
                for key in sorted(spec.demographic_policy_params)
            },
        }
    )


def build_generational_seed_manifest(
    config: SimulationRunnerConfig, run_id: RunId
) -> GenerationalSeedManifest:
    """Build truthful lineage from the actual configuration inputs."""
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("config must be SimulationRunnerConfig")
    if type(run_id) is not RunId:
        raise TypeError("run_id must be RunId")
    if config.generational_run is None or config.population_lifecycle is None:
        raise ValueError("generational seed manifest requires generational_run")
    lifecycle = config.population_lifecycle
    channels: list[SeedChannelLineage] = [
        SeedChannelLineage(
            name="world",
            algorithm_version="derivation-v3-stream-v1",
            namespace="objective",
            identity_selector="stochastic_identity",
            scope_fields=(
                "derivation_version",
                "physical_rules_fingerprint",
                "stochastic_identity",
                "seed",
                "namespace",
                "names",
            ),
            draw_usage="sampled",
        ),
        SeedChannelLineage(
            name="demography",
            algorithm_version="derivation-v3-stream-v1",
            namespace="demographic",
            identity_selector="durable_run_id",
            scope_fields=("run_id", "world_id", "tick"),
            draw_usage="reserved_ignored",
        ),
    ]
    init_spec = config.new_agent_initialization
    if init_spec is not None:
        channels.append(
            SeedChannelLineage(
                name="agent_initialization",
                algorithm_version="derivation-v3-stream-v1",
                namespace="new_agent_init",
                identity_selector="durable_run_id",
                scope_fields=("run_id", "agent_id", "draw_name"),
                draw_usage=(
                    "sampled"
                    if init_spec.parameter_distributions.distribution_id != "none"
                    else "absent"
                ),
            )
        )
    else:
        channels.append(
            SeedChannelLineage(
                name="agent_initialization",
                algorithm_version="derivation-v3-stream-v1",
                namespace="new_agent_init",
                identity_selector="durable_run_id",
                scope_fields=("run_id", "agent_id", "draw_name"),
                draw_usage="absent",
            )
        )
    channels.append(
        SeedChannelLineage(
            name="lifespan",
            algorithm_version="derivation-v3-stream-v1",
            namespace="lifespan_distribution",
            identity_selector="durable_run_id",
            scope_fields=(
                "run_id",
                "world_id",
                "agent_id",
                "entry_tick",
                "draw_name",
            ),
            draw_usage=(
                "sampled"
                if not lifecycle.lifespan_distribution.is_passthrough_default()
                else "absent"
            ),
        )
    )
    channels.append(
        SeedChannelLineage(
            name="innovation",
            algorithm_version="sha256-practical-knowledge-v1",
            namespace="practical_knowledge",
            identity_selector="root_seed_and_content",
            scope_fields=("seed", "namespace", "entry_id", "tick"),
            draw_usage="deterministic_hash",
        )
    )
    channels.append(
        SeedChannelLineage(
            name="environment",
            algorithm_version="sha256-environment-v1",
            namespace="environment",
            identity_selector="stochastic_identity",
            scope_fields=(
                "derivation_version",
                "physical_rules_fingerprint",
                "stochastic_identity",
                "seed",
                "tick",
                "location",
            ),
            draw_usage="deterministic_hash",
        )
    )
    channels.append(
        SeedChannelLineage(
            name="llm",
            algorithm_version="provider-recording-v1",
            namespace="llm_recording",
            identity_selector="recording_artifact",
            scope_fields=(
                "namespace",
                "request_id",
                "prompt_identity",
                "response_schema_identity",
            ),
            draw_usage=(
                "sampled"
                if config.provider.recording_policy is RecordingPolicy.LIVE
                else "deterministic_hash"
            ),
        )
    )
    parameter_hash = canonical_sha256(
        init_spec.parameter_distributions.canonical_payload()
        if init_spec is not None
        else {"distribution_id": "none", "params": {}}
    )
    lifespan_hash = canonical_sha256(
        lifecycle.lifespan_distribution.canonical_payload()
    )
    manifest = GenerationalSeedManifest(
        seed=config.seed,
        derivation_version=config.derivation_version,
        run_id=run_id.value,
        stochastic_identity=config.stochastic_identity.value,
        physical_rules_fingerprint=physical_rules_fingerprint(
            config.scenario.physical_rules
        ),
        schedule_fingerprint=_schedule_fingerprint(lifecycle),
        initialization_identity=InitializationSeedIdentity(
            profile_id=(
                init_spec.species_defaults_id
                if init_spec is not None
                else "legacy_none"
            ),
            parameter_distributions_hash=parameter_hash,
            lifespan_distribution_hash=lifespan_hash,
        ),
        channels=tuple(channels),
    )
    _LOGGER.info(
        "generational_seed_manifest run_id=%s channel_count=%s "
        "derivation_version=%s",
        run_id.value,
        len(manifest.channels),
        config.derivation_version,
    )
    return manifest


__all__ = [
    "GenerationalSeedManifest",
    "InitializationSeedIdentity",
    "SeedChannelLineage",
    "build_generational_seed_manifest",
    "canonical_sha256",
]
