"""Process-local continuation state owned by ``CognitiveLoop``.

Only behavior-significant loop fields that are not reconstructed from static
configuration are carried here. Frozen values may be shared; mutable containers
are defensively rebuilt on restore.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from agents.cognition.counterfactual import CounterfactualState

COGNITIVE_LOOP_FORK_STATE_VERSION: Final[str] = "cognitive-loop-fork-state-v1"


class CognitiveLoopForkStateError(ValueError):
    """Fail-closed loop fork-state error with a stable reason code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail or code}")


def _tuple(name: str, value: object) -> tuple[object, ...]:
    if isinstance(value, (str, bytes, set, frozenset, Mapping)):
        raise CognitiveLoopForkStateError(
            "fork_state_invalid", f"{name} must be an ordered sequence"
        )
    if not isinstance(value, Sequence):
        raise CognitiveLoopForkStateError(
            "fork_state_invalid", f"{name} must be an ordered sequence"
        )
    return tuple(value)


@dataclass(frozen=True, slots=True)
class CognitiveLoopForkState:
    """Captured mutable state from one cognitive loop at a finalized boundary."""

    counterfactual_state: CounterfactualState
    last_counterfactual_scenarios: tuple[object, ...]
    deferred_dissonance: tuple[object, ...]
    last_developmental_audits: tuple[object, ...]
    last_mentorship_audits: tuple[object, ...]
    last_cultural_feature_audits: tuple[object, ...]
    last_practical_knowledge_audits: tuple[object, ...]
    last_cognitive_budget_audit: object | None
    tick_budget_ledger: object | None
    prepared_institutional_decay: object | None
    symbolic_translation_applications: tuple[object, ...]
    developmental_entity_learning_rates: tuple[tuple[str, float], ...]
    developmental_stage_learning_rates: tuple[tuple[str, float], ...]
    experiment_ledger: object | None
    state_format_version: str = COGNITIVE_LOOP_FORK_STATE_VERSION

    def __post_init__(self) -> None:
        if self.state_format_version != COGNITIVE_LOOP_FORK_STATE_VERSION:
            raise CognitiveLoopForkStateError(
                "fork_state_unsupported", "unsupported loop fork-state version"
            )
        if type(self.counterfactual_state) is not CounterfactualState:
            raise CognitiveLoopForkStateError(
                "fork_state_invalid", "invalid counterfactual state"
            )
        for name in (
            "last_counterfactual_scenarios",
            "deferred_dissonance",
            "last_developmental_audits",
            "last_mentorship_audits",
            "last_cultural_feature_audits",
            "last_practical_knowledge_audits",
            "symbolic_translation_applications",
        ):
            object.__setattr__(
                self, name, _tuple(name, getattr(self, name))
            )
        for name in (
            "developmental_entity_learning_rates",
            "developmental_stage_learning_rates",
        ):
            entries = _tuple(name, getattr(self, name))
            cleaned: list[tuple[str, float]] = []
            seen: set[str] = set()
            for entry in entries:
                if not isinstance(entry, tuple) or len(entry) != 2:
                    raise CognitiveLoopForkStateError(
                        "fork_state_invalid", f"invalid {name} entry"
                    )
                key, rate = entry
                if type(key) is not str or key in seen:
                    raise CognitiveLoopForkStateError(
                        "fork_state_invalid", f"invalid {name} key"
                    )
                if isinstance(rate, bool) or not isinstance(rate, (int, float)):
                    raise CognitiveLoopForkStateError(
                        "fork_state_invalid", f"invalid {name} rate"
                    )
                seen.add(key)
                cleaned.append((key, float(rate)))
            object.__setattr__(self, name, tuple(cleaned))


__all__ = [
    "COGNITIVE_LOOP_FORK_STATE_VERSION",
    "CognitiveLoopForkState",
    "CognitiveLoopForkStateError",
]
