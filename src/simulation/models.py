"""Simulation run configuration and export metadata.

Exact replay of external LLM calls requires recorded responses or
deterministic stubs; local seed/stream derivation is not sufficient.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from simulation.clock import require_exact_nonneg_int
from world.events import WorldEvent
from world.identifiers import require_stable_id
from world.models import (
    PhysicalRules,
    canonical_physical_rules_bytes,
    physical_rules_fingerprint,
)

DERIVATION_VERSION_V1: Final[str] = "v1"
DERIVATION_VERSION_V2: Final[str] = "v2"
DERIVATION_VERSION_V3: Final[str] = "v3"
# Legacy/default write version for runs without physical rules.
DERIVATION_VERSION: Final[str] = DERIVATION_VERSION_V1
LLM_REPLAY_REQUIREMENT: Final[Literal["recorded_or_stub"]] = "recorded_or_stub"

_SUPPORTED_DERIVATION_VERSIONS: Final[frozenset[str]] = frozenset(
    {DERIVATION_VERSION_V1, DERIVATION_VERSION_V2, DERIVATION_VERSION_V3}
)
_LOGGER = logging.getLogger("simulation.models")


def require_seed(seed: object) -> int:
    """Accept only exact non-boolean ``int`` seeds ``>= 0``."""
    try:
        return require_exact_nonneg_int("SimulationRunConfig.seed", seed)
    except ValueError as exc:
        raise ValueError(
            "SimulationRunConfig.seed must be a non-negative integer"
        ) from exc


def require_derivation_version(version: object) -> str:
    if not isinstance(version, str) or not version:
        raise ValueError("derivation_version must be a non-empty string")
    if version not in _SUPPORTED_DERIVATION_VERSIONS:
        raise ValueError(f"unsupported derivation_version {version!r}")
    return version


@dataclass(frozen=True, slots=True)
class StochasticIdentity:
    """Opaque comparison identity shared by paired experiment arms.

    Equal seed + stochastic identity + world-significant configuration produce
    equal objective RNG streams and world-derived identifiers even when durable
    ``RunId`` values differ. Cognition/experiment condition fingerprints must
    never populate this value.
    """

    value: str

    def __post_init__(self) -> None:
        require_stable_id("StochasticIdentity.value", self.value)


def require_stochastic_identity(value: object) -> StochasticIdentity:
    """Accept ``StochasticIdentity`` or a validated stable-id string."""
    if type(value) is StochasticIdentity:
        return value
    if isinstance(value, str):
        return StochasticIdentity(value)
    raise TypeError("stochastic_identity must be StochasticIdentity or str")


def stochastic_identity_fingerprint(identity: StochasticIdentity) -> str:
    """SHA-256 hex digest of the identity value for diagnostics only."""
    if type(identity) is not StochasticIdentity:
        raise TypeError("stochastic_identity_fingerprint requires StochasticIdentity")
    return hashlib.sha256(identity.value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SimulationRunConfig:
    """Canonical run input. ``seed`` is required and never taken from the clock.

    Legacy derivation-v1 configs omit ``physical_rules`` and stochastic identity.
    Derivation-v2 requires world-owned ``PhysicalRules`` so equal seeds with
    different rules cannot alias. Derivation-v3 additionally requires an
    explicit ``stochastic_identity`` so paired cognitive arms can share
    objective randomness without sharing durable ``RunId`` values.
    """

    seed: int
    physical_rules: PhysicalRules | None = None
    derivation_version: str | None = None
    stochastic_identity: StochasticIdentity | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "seed", require_seed(self.seed))
        if (
            self.physical_rules is not None
            and type(self.physical_rules) is not PhysicalRules
        ):
            raise TypeError("SimulationRunConfig.physical_rules must be PhysicalRules")
        if self.stochastic_identity is not None:
            object.__setattr__(
                self,
                "stochastic_identity",
                require_stochastic_identity(self.stochastic_identity),
            )
        if self.derivation_version is None:
            if self.stochastic_identity is not None:
                resolved = DERIVATION_VERSION_V3
            elif self.physical_rules is not None:
                resolved = DERIVATION_VERSION_V2
            else:
                resolved = DERIVATION_VERSION_V1
        else:
            resolved = require_derivation_version(self.derivation_version)
        object.__setattr__(self, "derivation_version", resolved)
        if resolved == DERIVATION_VERSION_V1:
            if self.physical_rules is not None:
                raise ValueError(
                    "derivation-v1 forbids physical_rules "
                    "(code=derivation_rules_mismatch)"
                )
            if self.stochastic_identity is not None:
                raise ValueError(
                    "derivation-v1 forbids stochastic_identity "
                    "(code=stochastic_identity_mismatch)"
                )
        elif resolved == DERIVATION_VERSION_V2:
            if self.physical_rules is None:
                raise ValueError(
                    "derivation-v2 requires physical_rules "
                    "(code=derivation_rules_mismatch)"
                )
            if self.stochastic_identity is not None:
                raise ValueError(
                    "derivation-v2 forbids stochastic_identity "
                    "(code=stochastic_identity_mismatch)"
                )
        elif resolved == DERIVATION_VERSION_V3:
            if self.physical_rules is None:
                raise ValueError(
                    "derivation-v3 requires physical_rules "
                    "(code=derivation_rules_mismatch)"
                )
            if self.stochastic_identity is None:
                raise ValueError(
                    "derivation-v3 requires stochastic_identity "
                    "(code=stochastic_identity_absent)"
                )
        _LOGGER.debug(
            "run_config_validated derivation_version=%s has_rules=%s "
            "has_stochastic_identity=%s",
            resolved,
            self.physical_rules is not None,
            self.stochastic_identity is not None,
        )


def fingerprint_physical_rules(rules: PhysicalRules) -> str:
    """Public simulation facade for physical-rules fingerprint digests.

    Persistence and other adapters must call this instead of importing
    ``world.models`` directly.
    """
    if type(rules) is not PhysicalRules:
        raise TypeError("fingerprint_physical_rules requires PhysicalRules")
    fingerprint = physical_rules_fingerprint(rules)
    _LOGGER.debug(
        "[FIX] fingerprint_physical_rules rules_version=%s fingerprint_prefix=%s",
        rules.version,
        fingerprint[:12],
    )
    return fingerprint


def canonical_physical_rules_document(rules: PhysicalRules) -> dict[str, Any]:
    """Public simulation facade for the canonical physical-rules JSON document."""
    if type(rules) is not PhysicalRules:
        raise TypeError("canonical_physical_rules_document requires PhysicalRules")
    document = json.loads(canonical_physical_rules_bytes(rules).decode("utf-8"))
    if not isinstance(document, dict):
        raise TypeError("canonical physical rules bytes must decode to an object")
    _LOGGER.debug(
        "[FIX] canonical_physical_rules_document rules_version=%s keys=%s",
        rules.version,
        len(document),
    )
    return document


@dataclass(frozen=True, slots=True)
class RunId:
    value: str

    def __post_init__(self) -> None:
        require_stable_id("RunId.value", self.value)


@dataclass(frozen=True, slots=True)
class ExportMetadata:
    run_id: RunId
    seed: int
    derivation_version: str
    llm_replay: Literal["recorded_or_stub"] = LLM_REPLAY_REQUIREMENT
    stochastic_identity: StochasticIdentity | None = None

    def __post_init__(self) -> None:
        require_seed(self.seed)
        require_derivation_version(self.derivation_version)
        if self.derivation_version == DERIVATION_VERSION_V3:
            if self.stochastic_identity is None:
                raise ValueError(
                    "export metadata derivation-v3 requires stochastic_identity "
                    "(code=stochastic_identity_absent)"
                )
            object.__setattr__(
                self,
                "stochastic_identity",
                require_stochastic_identity(self.stochastic_identity),
            )
        elif self.stochastic_identity is not None:
            raise ValueError(
                "export metadata forbids stochastic_identity outside derivation-v3 "
                "(code=stochastic_identity_mismatch)"
            )


@dataclass(frozen=True, slots=True)
class SimulationExport:
    """Read-only export. Events are immutable snapshots, not live aggregates."""

    metadata: ExportMetadata
    events: Sequence[WorldEvent]

    def __post_init__(self) -> None:
        from world.events import normalize_events

        object.__setattr__(self, "events", normalize_events(self.events))
