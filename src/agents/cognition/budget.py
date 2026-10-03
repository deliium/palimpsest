"""Per-tick computational / cognitive budget ledger.

Cross-stage accounting for LLM calls, tokens, imagination branches, planning
depth, recalled memories, ToM targets, reflection cadence, and an optional
injected monotonic clock. Exhaustion degrades gracefully; it never hard-fails
a prepare tick. This module never imports analysis, simulation, or world
mutation paths, and never calls ``time.time`` / ``time.monotonic``.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int

__all__ = [
    "COGNITIVE_BUDGET_POLICY_VERSION",
    "BudgetDimension",
    "BudgetExhaustedReason",
    "BudgetGuardedProvider",
    "CognitiveBudgetAudit",
    "CognitiveBudgetPolicy",
    "TickBudgetLedger",
    "default_cognitive_budget_policy",
    "high_cost_budget_limits",
    "low_cost_budget_limits",
    "policy_from_limits",
]

COGNITIVE_BUDGET_POLICY_VERSION: Final[str] = "cognitive-budget-v1"
_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.budget")


class BudgetDimension(StrEnum):
    """Closed tick-budget dimensions. Distinct from ProspectivePruneReason."""

    LLM = "llm"
    TOKENS = "tokens"
    BRANCHES = "branches"
    DEPTH = "depth"
    MEMORIES = "memories"
    TOM = "tom"
    REFLECTION = "reflection"
    TIMEOUT = "timeout"


class BudgetExhaustedReason(StrEnum):
    """Closed tick-ledger exhaustion codes. Distinct from ProspectivePruneReason."""

    BUDGET_LLM = "budget_llm"
    BUDGET_TOKENS = "budget_tokens"
    BUDGET_BRANCHES = "budget_branches"
    BUDGET_DEPTH = "budget_depth"
    BUDGET_MEMORIES = "budget_memories"
    BUDGET_TOM = "budget_tom"
    BUDGET_REFLECTION = "budget_reflection"
    BUDGET_TIMEOUT = "budget_timeout"


_DIMENSION_REASON: Final[Mapping[BudgetDimension, BudgetExhaustedReason]] = {
    BudgetDimension.LLM: BudgetExhaustedReason.BUDGET_LLM,
    BudgetDimension.TOKENS: BudgetExhaustedReason.BUDGET_TOKENS,
    BudgetDimension.BRANCHES: BudgetExhaustedReason.BUDGET_BRANCHES,
    BudgetDimension.DEPTH: BudgetExhaustedReason.BUDGET_DEPTH,
    BudgetDimension.MEMORIES: BudgetExhaustedReason.BUDGET_MEMORIES,
    BudgetDimension.TOM: BudgetExhaustedReason.BUDGET_TOM,
    BudgetDimension.REFLECTION: BudgetExhaustedReason.BUDGET_REFLECTION,
    BudgetDimension.TIMEOUT: BudgetExhaustedReason.BUDGET_TIMEOUT,
}


def _fail(path: str, reason_code: str) -> ValueError:
    _LOG.error("invalid_fields path=%s reason_code=%s", path, reason_code)
    return ValueError(f"{path}: {reason_code}")


def _nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(name, "invalid_type")
    if value < 0:
        raise _fail(name, "not_nonnegative")
    return value


def _positive_int(name: str, value: object) -> int:
    number = _nonnegative_int(name, value)
    if number < 1:
        raise _fail(name, "not_positive")
    return number


def _timeout_seconds(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail("timeout_seconds", "not_finite")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout < 0.0:
        raise _fail("timeout_seconds", "not_finite")
    return 0.0 if timeout == 0.0 else timeout


@dataclass(frozen=True, slots=True)
class CognitiveBudgetPolicy:
    """``cognitive-budget-v1`` per-tick limits. Clock is cognition/test-only."""

    version: str = COGNITIVE_BUDGET_POLICY_VERSION
    max_llm_calls_per_tick: int = 0
    max_tokens_per_tick: int = 0
    max_imagination_branches: int = 2
    max_planning_depth: int = 1
    max_recalled_memories: int = 2
    max_tom_targets: int = 1
    reflection_interval_ticks: int = 16
    timeout_seconds: float = 0.0
    clock: Callable[[], float] | None = None

    def __post_init__(self) -> None:
        if self.version != COGNITIVE_BUDGET_POLICY_VERSION:
            raise _fail("version", "unsupported")
        object.__setattr__(
            self,
            "max_llm_calls_per_tick",
            _nonnegative_int("max_llm_calls_per_tick", self.max_llm_calls_per_tick),
        )
        object.__setattr__(
            self,
            "max_tokens_per_tick",
            _nonnegative_int("max_tokens_per_tick", self.max_tokens_per_tick),
        )
        object.__setattr__(
            self,
            "max_imagination_branches",
            _positive_int("max_imagination_branches", self.max_imagination_branches),
        )
        object.__setattr__(
            self,
            "max_planning_depth",
            _positive_int("max_planning_depth", self.max_planning_depth),
        )
        object.__setattr__(
            self,
            "max_recalled_memories",
            _positive_int("max_recalled_memories", self.max_recalled_memories),
        )
        object.__setattr__(
            self,
            "max_tom_targets",
            _nonnegative_int("max_tom_targets", self.max_tom_targets),
        )
        object.__setattr__(
            self,
            "reflection_interval_ticks",
            _positive_int("reflection_interval_ticks", self.reflection_interval_ticks),
        )
        object.__setattr__(
            self, "timeout_seconds", _timeout_seconds(self.timeout_seconds)
        )
        if self.clock is not None and not callable(self.clock):
            raise _fail("clock", "invalid_type")
        _LOG.debug(
            "cognitive_budget_policy_constructed policy_version=%s "
            "max_llm_calls_per_tick=%s max_tokens_per_tick=%s "
            "max_imagination_branches=%s max_planning_depth=%s "
            "max_recalled_memories=%s max_tom_targets=%s "
            "reflection_interval_ticks=%s timeout_seconds=%s clock_set=%s",
            self.version,
            self.max_llm_calls_per_tick,
            self.max_tokens_per_tick,
            self.max_imagination_branches,
            self.max_planning_depth,
            self.max_recalled_memories,
            self.max_tom_targets,
            self.reflection_interval_ticks,
            self.timeout_seconds,
            self.clock is not None,
        )


def default_cognitive_budget_policy() -> CognitiveBudgetPolicy:
    """Return ``cognitive-budget-v1`` with low-cost preset magnitudes."""
    return low_cost_budget_limits()


def low_cost_budget_limits() -> CognitiveBudgetPolicy:
    """Locked Experiment AD low-cost magnitudes."""
    return CognitiveBudgetPolicy(
        max_llm_calls_per_tick=0,
        max_tokens_per_tick=0,
        max_imagination_branches=2,
        max_planning_depth=1,
        max_recalled_memories=2,
        max_tom_targets=1,
        reflection_interval_ticks=16,
        timeout_seconds=0.0,
    )


def high_cost_budget_limits() -> CognitiveBudgetPolicy:
    """Locked Experiment AD high-cost magnitudes."""
    return CognitiveBudgetPolicy(
        max_llm_calls_per_tick=4,
        max_tokens_per_tick=2048,
        max_imagination_branches=16,
        max_planning_depth=3,
        max_recalled_memories=12,
        max_tom_targets=6,
        reflection_interval_ticks=8,
        timeout_seconds=0.0,
    )


def policy_from_limits(
    *,
    max_llm_calls_per_tick: int,
    max_tokens_per_tick: int,
    max_imagination_branches: int,
    max_planning_depth: int,
    max_recalled_memories: int,
    max_tom_targets: int,
    reflection_interval_ticks: int,
    timeout_seconds: float,
    clock: Callable[[], float] | None = None,
) -> CognitiveBudgetPolicy:
    """Build a policy from flat runner / simulation limit fields."""
    return CognitiveBudgetPolicy(
        max_llm_calls_per_tick=max_llm_calls_per_tick,
        max_tokens_per_tick=max_tokens_per_tick,
        max_imagination_branches=max_imagination_branches,
        max_planning_depth=max_planning_depth,
        max_recalled_memories=max_recalled_memories,
        max_tom_targets=max_tom_targets,
        reflection_interval_ticks=reflection_interval_ticks,
        timeout_seconds=timeout_seconds,
        clock=clock,
    )


@dataclass(frozen=True, slots=True)
class CognitiveBudgetAudit:
    """End-of-prepare budget snapshot. Numeric fields only; no payloads."""

    owner_id: AgentId
    tick: int
    mode: str
    max_llm_calls_per_tick: int
    max_tokens_per_tick: int
    max_imagination_branches: int
    max_planning_depth: int
    max_recalled_memories: int
    max_tom_targets: int
    reflection_interval_ticks: int
    timeout_seconds: float
    llm_calls_used: int
    tokens_used: int
    imagination_branches_used: int
    planning_depth_reached: int
    memories_recalled: int
    tom_targets_used: int
    reflection_ran: bool
    exhausted_reasons: tuple[str, ...]
    degraded: bool
    first_exhausted_dimension: str | None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        try:
            tick = require_exact_nonneg_int("tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "not_nonnegative") from exc
        object.__setattr__(self, "tick", tick)
        if self.mode not in {"disabled", "enforced"}:
            raise _fail("mode", "invalid_mode")
        for name in (
            "max_llm_calls_per_tick",
            "max_tokens_per_tick",
            "max_imagination_branches",
            "max_planning_depth",
            "max_recalled_memories",
            "max_tom_targets",
            "reflection_interval_ticks",
            "llm_calls_used",
            "tokens_used",
            "imagination_branches_used",
            "planning_depth_reached",
            "memories_recalled",
            "tom_targets_used",
        ):
            try:
                number = require_exact_nonneg_int(name, getattr(self, name))
            except ValueError as exc:
                raise _fail(name, "not_nonnegative") from exc
            object.__setattr__(self, name, number)
        object.__setattr__(
            self, "timeout_seconds", _timeout_seconds(self.timeout_seconds)
        )
        if type(self.reflection_ran) is not bool:
            raise _fail("reflection_ran", "invalid_type")
        if type(self.degraded) is not bool:
            raise _fail("degraded", "invalid_type")
        if isinstance(self.exhausted_reasons, (set, frozenset)):
            raise _fail("exhausted_reasons", "unordered")
        reasons = tuple(self.exhausted_reasons)
        allowed = {item.value for item in BudgetExhaustedReason}
        for reason in reasons:
            if reason not in allowed:
                raise _fail("exhausted_reasons", "invalid_reason")
        object.__setattr__(self, "exhausted_reasons", reasons)
        if self.first_exhausted_dimension is not None:
            if self.first_exhausted_dimension not in {
                item.value for item in BudgetDimension
            }:
                raise _fail("first_exhausted_dimension", "invalid_dimension")


@dataclass(slots=True)
class TickBudgetLedger:
    """Mutable per-prepare account. Not frozen; one instance per prepare."""

    owner_id: AgentId
    tick: int
    policy: CognitiveBudgetPolicy
    _used: dict[BudgetDimension, int] = field(default_factory=dict, repr=False)
    _exhausted: list[BudgetExhaustedReason] = field(default_factory=list, repr=False)
    _warned: set[BudgetDimension] = field(default_factory=set, repr=False)
    _started_at: float | None = field(default=None, repr=False)
    _reflection_ran: bool = field(default=False, repr=False)
    _planning_depth_reached: int = field(default=0, repr=False)
    _first_exhausted: BudgetDimension | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        try:
            tick = require_exact_nonneg_int("tick", self.tick)
        except ValueError as exc:
            raise _fail("tick", "not_nonnegative") from exc
        self.tick = tick
        if type(self.policy) is not CognitiveBudgetPolicy:
            raise _fail("policy", "invalid_type")
        for dimension in BudgetDimension:
            self._used.setdefault(dimension, 0)
        clock = self.policy.clock
        if (
            clock is not None
            and callable(clock)
            and self.policy.timeout_seconds > 0.0
        ):
            self._started_at = float(clock())
        _LOG.debug(
            "tick_budget_created agent_id=%s tick=%s mode=enforced "
            "max_llm_calls_per_tick=%s max_tokens_per_tick=%s "
            "max_imagination_branches=%s max_planning_depth=%s "
            "max_recalled_memories=%s max_tom_targets=%s "
            "reflection_interval_ticks=%s timeout_seconds=%s",
            self.owner_id.value,
            self.tick,
            self.policy.max_llm_calls_per_tick,
            self.policy.max_tokens_per_tick,
            self.policy.max_imagination_branches,
            self.policy.max_planning_depth,
            self.policy.max_recalled_memories,
            self.policy.max_tom_targets,
            self.policy.reflection_interval_ticks,
            self.policy.timeout_seconds,
        )

    def limit_for(self, dimension: BudgetDimension) -> int | float:
        policy = self.policy
        if dimension is BudgetDimension.LLM:
            return policy.max_llm_calls_per_tick
        if dimension is BudgetDimension.TOKENS:
            return policy.max_tokens_per_tick
        if dimension is BudgetDimension.BRANCHES:
            return policy.max_imagination_branches
        if dimension is BudgetDimension.DEPTH:
            return policy.max_planning_depth
        if dimension is BudgetDimension.MEMORIES:
            return policy.max_recalled_memories
        if dimension is BudgetDimension.TOM:
            return policy.max_tom_targets
        if dimension is BudgetDimension.REFLECTION:
            return policy.reflection_interval_ticks
        if dimension is BudgetDimension.TIMEOUT:
            return policy.timeout_seconds
        raise _fail("dimension", "invalid_dimension")

    def used(self, dimension: BudgetDimension) -> int:
        if type(dimension) is not BudgetDimension:
            raise _fail("dimension", "invalid_dimension")
        return self._used[dimension]

    def remaining(self, dimension: BudgetDimension) -> int:
        if dimension is BudgetDimension.TIMEOUT:
            return 1 if not self.timed_out() else 0
        if dimension is BudgetDimension.REFLECTION:
            return 0 if self.is_exhausted(dimension) else 1
        limit = int(self.limit_for(dimension))
        return max(0, limit - self._used[dimension])

    def is_exhausted(self, dimension: BudgetDimension) -> bool:
        reason = _DIMENSION_REASON[dimension]
        return reason in self._exhausted

    def exhausted_reasons(self) -> tuple[BudgetExhaustedReason, ...]:
        return tuple(self._exhausted)

    def timed_out(self) -> bool:
        if self.is_exhausted(BudgetDimension.TIMEOUT):
            return True
        clock = self.policy.clock
        if (
            self._started_at is None
            or clock is None
            or not callable(clock)
            or self.policy.timeout_seconds <= 0.0
        ):
            return False
        elapsed = float(clock()) - self._started_at
        if elapsed >= self.policy.timeout_seconds:
            self._mark_exhausted(BudgetDimension.TIMEOUT)
            return True
        return False

    def check_timeout(self) -> bool:
        """Stage-boundary timeout probe. Returns True when timed out."""
        return self.timed_out()

    def effective_cap(self, dimension: BudgetDimension, local_cap: int) -> int:
        """``min(local_cap, tick_remaining, tick_limit)`` for overlapping dims."""
        if type(local_cap) is not int or isinstance(local_cap, bool) or local_cap < 0:
            raise _fail("local_cap", "not_nonnegative")
        if self.timed_out() and dimension in {
            BudgetDimension.LLM,
            BudgetDimension.TOKENS,
            BudgetDimension.BRANCHES,
            BudgetDimension.DEPTH,
        }:
            return 0
        limit = int(self.limit_for(dimension))
        remaining = self.remaining(dimension)
        return min(local_cap, remaining, limit)

    def try_consume(self, dimension: BudgetDimension, amount: int = 1) -> bool:
        """Charge ``amount`` when remaining; else mark exhausted and return False."""
        if type(dimension) is not BudgetDimension:
            raise _fail("dimension", "invalid_dimension")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise _fail("amount", "not_nonnegative")
        if amount == 0:
            return True
        if dimension is BudgetDimension.TIMEOUT:
            return not self.timed_out()
        if dimension is BudgetDimension.REFLECTION:
            if self.is_exhausted(dimension):
                return False
            return True
        if self.timed_out():
            return False
        remaining = self.remaining(dimension)
        if amount > remaining:
            self._mark_exhausted(dimension)
            return False
        self._used[dimension] = self._used[dimension] + amount
        _LOG.debug(
            "tick_budget_charge agent_id=%s tick=%s dimension=%s amount=%s "
            "used=%s remaining=%s",
            self.owner_id.value,
            self.tick,
            dimension.value,
            amount,
            self._used[dimension],
            self.remaining(dimension),
        )
        if self.remaining(dimension) == 0:
            self._mark_exhausted(dimension)
        if dimension is BudgetDimension.DEPTH:
            self._planning_depth_reached = max(
                self._planning_depth_reached, self._used[dimension]
            )
        return True

    def charge_llm(self, *, total_tokens: int = 0) -> bool:
        """Charge one provider generate plus allowlisted tokens when present."""
        tokens = _nonnegative_int("total_tokens", total_tokens)
        if self.timed_out():
            return False
        if not self.try_consume(BudgetDimension.LLM, 1):
            return False
        if tokens > 0 and not self.try_consume(BudgetDimension.TOKENS, tokens):
            # Call already counted; token exhaustion refuses further LLM use.
            return True
        return True

    def allow_llm(self) -> bool:
        """Pre-check before entering provider.generate (does not charge)."""
        if self.timed_out():
            return False
        if self.is_exhausted(BudgetDimension.LLM):
            return False
        if self.is_exhausted(BudgetDimension.TOKENS):
            return False
        return self.remaining(BudgetDimension.LLM) > 0

    def truncate_memories(self, ranked_count: int) -> int:
        """Return how many ranked hits to keep; charges the kept count."""
        if isinstance(ranked_count, bool) or not isinstance(ranked_count, int):
            raise _fail("ranked_count", "invalid_type")
        if ranked_count < 0:
            raise _fail("ranked_count", "not_nonnegative")
        keep = self.effective_cap(BudgetDimension.MEMORIES, ranked_count)
        if keep < ranked_count:
            self._mark_exhausted(BudgetDimension.MEMORIES)
        if keep > 0:
            self._used[BudgetDimension.MEMORIES] = (
                self._used[BudgetDimension.MEMORIES] + keep
            )
            _LOG.debug(
                "tick_budget_charge agent_id=%s tick=%s dimension=%s amount=%s "
                "used=%s remaining=%s",
                self.owner_id.value,
                self.tick,
                BudgetDimension.MEMORIES.value,
                keep,
                self._used[BudgetDimension.MEMORIES],
                self.remaining(BudgetDimension.MEMORIES),
            )
        return keep

    def try_tom_target(self) -> bool:
        """Reserve one distinct ToM / epistemic target update."""
        return self.try_consume(BudgetDimension.TOM, 1)

    def mark_reflection_skipped(self) -> None:
        self._mark_exhausted(BudgetDimension.REFLECTION)

    def mark_reflection_ran(self) -> None:
        self._reflection_ran = True

    def note_planning_depth(self, depth: int) -> None:
        depth = _nonnegative_int("depth", depth)
        self._planning_depth_reached = max(self._planning_depth_reached, depth)
        limit = int(self.limit_for(BudgetDimension.DEPTH))
        if depth >= limit:
            self._used[BudgetDimension.DEPTH] = limit
            self._mark_exhausted(BudgetDimension.DEPTH)
        else:
            self._used[BudgetDimension.DEPTH] = max(
                self._used[BudgetDimension.DEPTH], depth
            )

    def _mark_exhausted(self, dimension: BudgetDimension) -> None:
        reason = _DIMENSION_REASON[dimension]
        if reason in self._exhausted:
            return
        self._exhausted.append(reason)
        if self._first_exhausted is None:
            self._first_exhausted = dimension
        if dimension not in self._warned:
            self._warned.add(dimension)
            _LOG.warning(
                "tick_budget_exhausted agent_id=%s tick=%s dimension=%s "
                "used=%s limit=%s reason_code=%s",
                self.owner_id.value,
                self.tick,
                dimension.value,
                self._used.get(dimension, 0),
                self.limit_for(dimension),
                reason.value,
            )

    def snapshot(self) -> CognitiveBudgetAudit:
        """Frozen end-of-prepare audit."""
        reasons = tuple(reason.value for reason in self._exhausted)
        first = (
            None
            if self._first_exhausted is None
            else self._first_exhausted.value
        )
        return CognitiveBudgetAudit(
            owner_id=self.owner_id,
            tick=self.tick,
            mode="enforced",
            max_llm_calls_per_tick=self.policy.max_llm_calls_per_tick,
            max_tokens_per_tick=self.policy.max_tokens_per_tick,
            max_imagination_branches=self.policy.max_imagination_branches,
            max_planning_depth=self.policy.max_planning_depth,
            max_recalled_memories=self.policy.max_recalled_memories,
            max_tom_targets=self.policy.max_tom_targets,
            reflection_interval_ticks=self.policy.reflection_interval_ticks,
            timeout_seconds=self.policy.timeout_seconds,
            llm_calls_used=self._used[BudgetDimension.LLM],
            tokens_used=self._used[BudgetDimension.TOKENS],
            imagination_branches_used=self._used[BudgetDimension.BRANCHES],
            planning_depth_reached=self._planning_depth_reached,
            memories_recalled=self._used[BudgetDimension.MEMORIES],
            tom_targets_used=self._used[BudgetDimension.TOM],
            reflection_ran=self._reflection_ran,
            exhausted_reasons=reasons,
            degraded=bool(reasons),
            first_exhausted_dimension=first,
        )


class BudgetExhaustedError(RuntimeError):
    """Raised when a guarded provider refuses ``generate`` under tick budget."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(slots=True)
class BudgetGuardedProvider:
    """Wrap an ``LLMProvider`` and charge the tick ledger on each generate.

    Pre-checks that refuse before the boundary do not charge. Entering
    ``generate`` charges one call (and tokens when metadata is present) even
    when the inner call later falls back.
    """

    inner: object
    ledger: TickBudgetLedger

    async def generate(self, request: object) -> object:
        if not self.ledger.allow_llm():
            dimension = BudgetDimension.TIMEOUT
            if self.ledger.is_exhausted(BudgetDimension.TOKENS) or (
                self.ledger.remaining(BudgetDimension.TOKENS) <= 0
                and self.ledger.policy.max_tokens_per_tick == 0
            ):
                dimension = BudgetDimension.TOKENS
            elif self.ledger.is_exhausted(BudgetDimension.LLM) or (
                self.ledger.remaining(BudgetDimension.LLM) <= 0
            ):
                dimension = BudgetDimension.LLM
            if not self.ledger.is_exhausted(dimension):
                self.ledger._mark_exhausted(dimension)
            reason = _DIMENSION_REASON[dimension]
            _LOG.warning(
                "tick_budget_llm_refused agent_id=%s tick=%s reason_code=%s",
                self.ledger.owner_id.value,
                self.ledger.tick,
                reason.value,
            )
            raise BudgetExhaustedError(reason.value)
        if not self.ledger.try_consume(BudgetDimension.LLM, 1):
            raise BudgetExhaustedError(BudgetExhaustedReason.BUDGET_LLM.value)
        result = await self.inner.generate(request)  # type: ignore[attr-defined]
        metadata = getattr(result, "metadata", None)
        total = getattr(metadata, "total_tokens", None)
        if isinstance(total, int) and not isinstance(total, bool) and total > 0:
            if not self.ledger.try_consume(BudgetDimension.TOKENS, total):
                _LOG.debug(
                    "tick_budget_tokens_exhausted_after_call agent_id=%s tick=%s "
                    "tokens=%s",
                    self.ledger.owner_id.value,
                    self.ledger.tick,
                    total,
                )
        return result
