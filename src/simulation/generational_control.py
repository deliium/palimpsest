"""Trusted generational orchestration ports (criteria and boundary observers).

Simulation owns these narrow protocols. Concrete analysis or experiment
implementations are injected by outer composition; no dynamic import, eval, or
process-global registry is involved.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, Protocol

from simulation.generational_models import (
    ExperimentCriterionSpec,
    GenerationalBoundary,
    StopEvidence,
)
from world.identifiers import require_stable_id


class GenerationalControlError(RuntimeError):
    """Fail-closed orchestration error with a stable, payload-free code."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if detail is None else f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class CriterionDecision:
    """One trusted criterion decision (no messages, commands, or content)."""

    matched: bool
    measurements: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if type(self.matched) is not bool:
            raise TypeError("CriterionDecision.matched must be bool")
        if isinstance(self.measurements, (str, bytes)) or not isinstance(
            self.measurements, Mapping
        ):
            raise TypeError("CriterionDecision.measurements must be a mapping")
        frozen: dict[str, object] = {}
        for key, value in self.measurements.items():
            require_stable_id("CriterionDecision.measurements key", key)
            if type(value) not in (bool, int, float):
                raise TypeError(
                    "CriterionDecision.measurements values must be finite "
                    "numbers or bool"
                )
            if type(value) is float and not math.isfinite(value):
                raise ValueError(
                    "CriterionDecision.measurements values must be finite"
                )
            frozen[key] = value
        object.__setattr__(
            self, "measurements", MappingProxyType(dict(sorted(frozen.items())))
        )


class ExperimentStopCriterion(Protocol):
    """Trusted read-only criterion evaluated at a finalized boundary."""

    @property
    def criterion_id(self) -> str: ...

    @property
    def version(self) -> str: ...

    async def evaluate(self, boundary: GenerationalBoundary) -> CriterionDecision:
        """Return a detached decision; never mutate world or owner state."""


CriterionFactory = Callable[[ExperimentCriterionSpec], ExperimentStopCriterion]


@dataclass(frozen=True, slots=True)
class RecordingUsageEvidence:
    """Neutral, payload-free consumed replay metadata crossing into simulation."""

    agent_id: str
    tick: int
    component: str
    request_id: str
    lookup_mode: str
    namespace: str
    cache_key: str
    record_integrity_hash: str
    prompt_identity: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    response_schema_identity: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        for name in (
            "agent_id",
            "component",
            "request_id",
            "lookup_mode",
            "namespace",
            "cache_key",
            "record_integrity_hash",
        ):
            require_stable_id(f"RecordingUsageEvidence.{name}", getattr(self, name))
        if isinstance(self.tick, bool) or type(self.tick) is not int or self.tick < 0:
            raise ValueError("RecordingUsageEvidence.tick must be non-negative int")
        for name in ("prompt_identity", "response_schema_identity"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise TypeError(f"RecordingUsageEvidence.{name} must be a mapping")
            frozen = {
                require_stable_id(f"{name} key", key): require_stable_id(
                    f"{name} value", item
                )
                for key, item in value.items()
            }
            object.__setattr__(
                self, name, MappingProxyType(dict(sorted(frozen.items())))
            )

    @property
    def usage_key(self) -> str:
        import hashlib
        import json

        encoded = json.dumps(
            {
                "agent_id": self.agent_id,
                "component": self.component,
                "lookup_mode": self.lookup_mode,
                "request_id": self.request_id,
                "tick": self.tick,
            },
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class RecordingUsageSink(Protocol):
    """Persistence port for validated replay-consumption metadata."""

    def put_usage(self, evidence: RecordingUsageEvidence) -> None: ...


class FinalizedBoundaryObserver(Protocol):
    """Post-finalization observer for detached historical artifacts."""

    async def observe(
        self,
        boundary: GenerationalBoundary,
        stop_evidence: StopEvidence | None,
    ) -> None:
        """Persist detached output; must be idempotent for one boundary key."""


def unsupported_criterion_factory(
    spec: ExperimentCriterionSpec,
) -> ExperimentStopCriterion:
    """Default factory: request a trusted criterion before run creation."""
    raise GenerationalControlError(
        "unsupported_experiment_criterion",
        f"{spec.criterion_id}@{spec.version}",
    )


DEFAULT_CRITERION_FACTORY: Final = unsupported_criterion_factory

__all__ = [
    "DEFAULT_CRITERION_FACTORY",
    "CriterionDecision",
    "CriterionFactory",
    "ExperimentStopCriterion",
    "FinalizedBoundaryObserver",
    "GenerationalControlError",
    "RecordingUsageEvidence",
    "RecordingUsageSink",
    "unsupported_criterion_factory",
]
