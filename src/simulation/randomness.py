"""Isolated random streams derived from an explicit simulation seed.

This is the only module allowed to import :mod:`random`. Callers receive
private :class:`random.Random` instances; module-level ``random.*`` functions
are never used.
"""

from __future__ import annotations

import hashlib
import logging
import random
from collections.abc import Mapping
from dataclasses import dataclass

from simulation.models import (
    DERIVATION_VERSION_V2,
    DERIVATION_VERSION_V3,
    RunId,
    SimulationRunConfig,
    require_seed,
    stochastic_identity_fingerprint,
)
from world.models import physical_rules_fingerprint
from world.values import WeatherCondition

_LOGGER = logging.getLogger("simulation.randomness")


@dataclass(frozen=True, slots=True)
class StreamScope:
    """Canonical stream identity. Distinct name tuples never share a digest."""

    namespace: str
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.namespace:
            raise ValueError("StreamScope.namespace must be a non-empty string")
        if not self.names:
            raise ValueError("StreamScope.names must contain at least one name")
        for name in self.names:
            if not name:
                raise ValueError("StreamScope names must be non-empty strings")


def canonical_scope_bytes(scope: StreamScope) -> bytes:
    """Length-prefixed encoding so ('ab','c') does not alias ('a','bc')."""
    chunks = [_length_prefixed(scope.namespace.encode("utf-8"))]
    for name in scope.names:
        chunks.append(_length_prefixed(name.encode("utf-8")))
    return b"".join(chunks)


def _length_prefixed(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def _mix_config_material(hasher: object, config: SimulationRunConfig) -> None:
    """Mix versioned replay-significant config into a derivation hasher."""
    assert config.derivation_version is not None
    update = hasher.update  # type: ignore[attr-defined]
    update(config.derivation_version.encode("utf-8"))
    if config.derivation_version in {DERIVATION_VERSION_V2, DERIVATION_VERSION_V3}:
        assert config.physical_rules is not None
        fingerprint = physical_rules_fingerprint(config.physical_rules).encode("ascii")
        update(_length_prefixed(fingerprint))
    if config.derivation_version == DERIVATION_VERSION_V3:
        assert config.stochastic_identity is not None
        identity_bytes = config.stochastic_identity.value.encode("utf-8")
        update(_length_prefixed(b"stochastic"))
        update(_length_prefixed(identity_bytes))


def objective_stream_identity(config: SimulationRunConfig, *, run_id: RunId) -> str:
    """Return the scope identity used for objective world RNG streams.

    Derivation-v3 substitutes ``stochastic_identity`` for durable ``RunId`` so
    paired experiment arms share objective streams. Legacy v1/v2 retain
    ``run_id`` for bit-compatible replay of persisted history.
    """
    if type(run_id) is not RunId:
        raise TypeError("objective_stream_identity requires RunId")
    assert config.derivation_version is not None
    if config.derivation_version == DERIVATION_VERSION_V3:
        if config.stochastic_identity is None:
            raise ValueError(
                "derivation-v3 requires stochastic_identity "
                "(code=stochastic_identity_absent)"
            )
        identity = config.stochastic_identity.value
        _LOGGER.debug(
            "objective_stream_identity derivation_version=%s "
            "stochastic_fingerprint_prefix=%s",
            config.derivation_version,
            stochastic_identity_fingerprint(config.stochastic_identity)[:12],
        )
        return identity
    _LOGGER.debug(
        "objective_stream_identity derivation_version=%s run_id=%s",
        config.derivation_version,
        run_id.value,
    )
    return run_id.value


def derive_stream_seed(config: SimulationRunConfig, scope: StreamScope) -> int:
    hasher = hashlib.sha256()
    _mix_config_material(hasher, config)
    hasher.update(_length_prefixed(b"stream"))
    hasher.update(_length_prefixed(str(config.seed).encode("utf-8")))
    hasher.update(canonical_scope_bytes(scope))
    return int.from_bytes(hasher.digest(), "big")


def create_rng(seed: int) -> random.Random:
    """Return a private ``Random`` instance for ``seed``.

    The process-global random module state is not read or written.
    """
    return random.Random(require_seed(seed))


def create_named_stream(
    config: SimulationRunConfig, scope: StreamScope
) -> random.Random:
    """Derive an independent stream from canonical seed and scope inputs."""
    return random.Random(derive_stream_seed(config, scope))


def sample_stream(
    config: SimulationRunConfig, scope: StreamScope, count: int
) -> tuple[int, ...]:
    """Draw ``count`` bounded integers from a fresh named stream."""
    rng = create_named_stream(config, scope)
    return tuple(rng.randrange(1_000_000_000) for _ in range(count))


def sample_bernoulli(rng: random.Random, probability: float) -> bool:
    """Bernoulli draw: ``random() < probability`` on a private stream."""
    if type(rng) is not random.Random:
        raise TypeError("sample_bernoulli requires random.Random")
    if isinstance(probability, bool) or not isinstance(probability, (int, float)):
        raise TypeError("probability must be a float in [0.0, 1.0]")
    value = float(probability)
    if value < 0.0 or value > 1.0:
        raise ValueError("probability must be in [0.0, 1.0]")
    return rng.random() < value


def sample_attack_damage(
    rng: random.Random, *, minimum: int, maximum_exclusive: int
) -> int:
    """Integer damage via ``randrange(minimum, maximum_exclusive)``."""
    if type(rng) is not random.Random:
        raise TypeError("sample_attack_damage requires random.Random")
    if (
        isinstance(minimum, bool)
        or type(minimum) is not int
        or isinstance(maximum_exclusive, bool)
        or type(maximum_exclusive) is not int
    ):
        raise TypeError("damage bounds must be ints")
    if minimum < 0 or maximum_exclusive <= minimum:
        raise ValueError("damage bounds must satisfy 0 <= min < max_exclusive")
    return rng.randrange(minimum, maximum_exclusive)


def sample_destination_index(rng: random.Random, destination_count: int) -> int:
    """Uniform destination selector via ``randrange(len(sorted_destinations))``."""
    if type(rng) is not random.Random:
        raise TypeError("sample_destination_index requires random.Random")
    if (
        isinstance(destination_count, bool)
        or type(destination_count) is not int
        or destination_count <= 0
    ):
        raise ValueError("destination_count must be a positive int")
    return rng.randrange(destination_count)


def sample_weather_condition(
    rng: random.Random,
    transitions: Mapping[WeatherCondition, float],
) -> WeatherCondition:
    """Sample weather against cumulative half-open probability intervals."""
    if type(rng) is not random.Random:
        raise TypeError("sample_weather_condition requires random.Random")
    if isinstance(transitions, (str, bytes)) or not isinstance(transitions, Mapping):
        raise TypeError("transitions must be a mapping")
    ordered = tuple(WeatherCondition)
    cumulative = 0.0
    draw = rng.random()
    for condition in ordered:
        if condition not in transitions:
            raise ValueError("transitions must define every WeatherCondition")
        probability = transitions[condition]
        if isinstance(probability, bool) or not isinstance(probability, (int, float)):
            raise TypeError("transition probabilities must be floats")
        probability = float(probability)
        if probability < 0.0:
            raise ValueError("transition probabilities must be non-negative")
        next_cumulative = cumulative + probability
        if cumulative <= draw < next_cumulative:
            return condition
        cumulative = next_cumulative
    if abs(cumulative - 1.0) > 1e-9:
        raise ValueError("transition probabilities must sum to 1.0")
    return ordered[-1]
