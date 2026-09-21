"""Deterministic scripted ``LLMProvider`` for network-free tests.

Scripts validated outputs or typed :class:`~llm.errors.LLMError` failures only.
Retry behavior stays owned by real providers. Call records retain safe
correlation and model metadata — never credentials, prompt content, schemas,
or output dumps.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from llm.errors import LLMError
from llm.models import (
    FinishReason,
    LLMRequest,
    LLMResult,
    LLMResultMetadata,
    StructuredOutput,
    TokenUsage,
)

__all__ = [
    "FakeCallRecord",
    "FakeClock",
    "FakeLLMFailureCode",
    "FakeLLMProvider",
    "FakeLLMProviderError",
    "ScriptedFailure",
    "ScriptedSuccess",
]

_LOG: Final[logging.Logger] = logging.getLogger("tests.fakes.llm")

_DEFAULT_PROVIDER_NAME: Final[str] = "fake"
_DEFAULT_MODEL_NAME: Final[str] = "scripted"


class FakeLLMFailureCode(StrEnum):
    """Stable harness failure codes (not provider wire codes)."""

    UNEXPECTED_REQUEST_ID = "unexpected_request_id"
    EXHAUSTED_SCRIPT = "exhausted_script"
    DUPLICATE_ACTIVE_ID = "duplicate_active_id"
    RESPONSE_MODEL_MISMATCH = "response_model_mismatch"
    DUPLICATE_ORDINAL = "duplicate_ordinal"


class FakeLLMProviderError(Exception):
    """Test-harness failure for unexpected or invalid fake usage.

    Messages identify only safe correlation/model metadata and a stable code.
    """

    def __init__(
        self,
        code: FakeLLMFailureCode,
        *,
        llm_request_id: str | None = None,
        response_model: str | None = None,
        ordinal: int | None = None,
    ) -> None:
        if not isinstance(code, FakeLLMFailureCode):
            raise TypeError("code must be FakeLLMFailureCode")
        self.code = code
        self.llm_request_id = llm_request_id
        self.response_model = response_model
        self.ordinal = ordinal
        parts = [f"code={code.value}"]
        if llm_request_id is not None:
            parts.append(f"llm_request_id={llm_request_id}")
        if response_model is not None:
            parts.append(f"response_model={response_model}")
        if ordinal is not None:
            parts.append(f"ordinal={ordinal}")
        super().__init__(" ".join(parts))
        self.__cause__ = None
        self.__context__ = None
        self.__suppress_context__ = True

    def __repr__(self) -> str:
        return (
            "FakeLLMProviderError("
            f"code={self.code.value!r}, "
            f"llm_request_id={self.llm_request_id!r}, "
            f"response_model={self.response_model!r}, "
            f"ordinal={self.ordinal!r})"
        )


class FakeClock:
    """Deterministic monotonic clock and async sleeper for exact assertions.

    ``sleep`` advances virtual time by the requested delay, records the delay,
    and yields once so cancellation and concurrent scheduling remain observable
    without wall-clock waits.
    """

    def __init__(self, *, start: float = 0.0) -> None:
        if isinstance(start, bool) or not isinstance(start, (int, float)):
            raise TypeError("start must be a finite number")
        value = float(start)
        if value != value or value in {float("inf"), float("-inf")}:
            raise ValueError("start must be finite")
        self._now = value
        self._sleeps: list[float] = []

    def monotonic(self) -> float:
        """Return the current virtual monotonic time."""
        return self._now

    async def sleep(self, seconds: float) -> None:
        """Record ``seconds``, yield for cancellation, then advance the clock."""
        delay = _require_non_negative_finite("seconds", seconds)
        self._sleeps.append(delay)
        await asyncio.sleep(0)
        self._now += delay

    @property
    def sleeps(self) -> tuple[float, ...]:
        """Defensive copy of recorded sleep delays."""
        return tuple(self._sleeps)

    def advance(self, seconds: float) -> None:
        """Advance virtual time without recording a sleep."""
        delay = _require_non_negative_finite("seconds", seconds)
        self._now += delay

    def reset(self, *, start: float = 0.0) -> None:
        """Reset virtual time and clear recorded sleeps."""
        if isinstance(start, bool) or not isinstance(start, (int, float)):
            raise TypeError("start must be a finite number")
        value = float(start)
        if value != value or value in {float("inf"), float("-inf")}:
            raise ValueError("start must be finite")
        self._now = value
        self._sleeps.clear()

    def __repr__(self) -> str:
        return f"FakeClock(now={self._now!r}, sleep_count={len(self._sleeps)})"


@dataclass(frozen=True, slots=True)
class ScriptedSuccess:
    """Scripted validated output. Does not perform retries."""

    output: StructuredOutput
    metadata: LLMResultMetadata | None = None
    delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.output, StructuredOutput):
            raise TypeError("output must be a StructuredOutput instance")
        if self.metadata is not None and type(self.metadata) is not LLMResultMetadata:
            raise TypeError("metadata must be LLMResultMetadata")
        object.__setattr__(
            self,
            "delay_seconds",
            _require_non_negative_finite("delay_seconds", self.delay_seconds),
        )

    def __repr__(self) -> str:
        return (
            "ScriptedSuccess("
            f"output_type={type(self.output).__name__!r}, "
            f"has_metadata={self.metadata is not None}, "
            f"delay_seconds={self.delay_seconds})"
        )


@dataclass(frozen=True, slots=True)
class ScriptedFailure:
    """Scripted typed provider failure. Does not perform retries."""

    error: LLMError
    delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        if type(self.error) is not LLMError:
            raise TypeError("error must be LLMError")
        object.__setattr__(
            self,
            "delay_seconds",
            _require_non_negative_finite("delay_seconds", self.delay_seconds),
        )

    def __repr__(self) -> str:
        return (
            "ScriptedFailure("
            f"code={self.error.code.value!r}, "
            f"delay_seconds={self.delay_seconds})"
        )


@dataclass(frozen=True, slots=True)
class FakeCallRecord:
    """Safe metadata for one ``generate`` invocation.

    Omits credentials, rendered prompt content, schemas, and output dumps.
    """

    llm_request_id: str
    invocation_ordinal: int
    response_model: str
    message_count: int
    has_prompt: bool
    prompt_name: str | None
    prompt_version: str | None
    has_options: bool
    started_at: float
    finished_at: float
    outcome: str
    error_code: str | None = None

    def __repr__(self) -> str:
        return (
            "FakeCallRecord("
            f"llm_request_id={self.llm_request_id!r}, "
            f"invocation_ordinal={self.invocation_ordinal}, "
            f"response_model={self.response_model!r}, "
            f"outcome={self.outcome!r})"
        )


def _require_non_negative_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a non-negative finite number")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"{name} must be finite")
    if number < 0.0:
        raise ValueError(f"{name} must be >= 0")
    return number


def _require_positive_ordinal(ordinal: object) -> int:
    if isinstance(ordinal, bool) or not isinstance(ordinal, int):
        raise TypeError("ordinal must be a positive integer")
    if ordinal < 1:
        raise ValueError("ordinal must be >= 1")
    return ordinal


def _copy_token_usage(usage: TokenUsage | None) -> TokenUsage | None:
    if usage is None:
        return None
    return TokenUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
    )


def _copy_metadata(metadata: LLMResultMetadata) -> LLMResultMetadata:
    return LLMResultMetadata(
        provider_name=metadata.provider_name,
        model_name=metadata.model_name,
        finish_reason=metadata.finish_reason,
        usage=_copy_token_usage(metadata.usage),
        upstream_request_id=metadata.upstream_request_id,
        attempts=metadata.attempts,
    )


def _copy_output[T: StructuredOutput](output: T) -> T:
    return output.model_copy(deep=True)


def _copy_error(error: LLMError) -> LLMError:
    return LLMError(
        error.code,
        retryable=error.retryable,
        attempts=error.attempts,
        status=error.status,
        last_code=error.last_code,
    )


def _copy_outcome(
    outcome: ScriptedSuccess | ScriptedFailure,
) -> ScriptedSuccess | ScriptedFailure:
    if isinstance(outcome, ScriptedSuccess):
        metadata = (
            None if outcome.metadata is None else _copy_metadata(outcome.metadata)
        )
        return ScriptedSuccess(
            output=_copy_output(outcome.output),
            metadata=metadata,
            delay_seconds=outcome.delay_seconds,
        )
    return ScriptedFailure(
        error=_copy_error(outcome.error),
        delay_seconds=outcome.delay_seconds,
    )


def _default_metadata() -> LLMResultMetadata:
    return LLMResultMetadata(
        provider_name=_DEFAULT_PROVIDER_NAME,
        model_name=_DEFAULT_MODEL_NAME,
        finish_reason=FinishReason.STOP,
    )


class FakeLLMProvider:
    """Scripted async provider implementing the public ``LLMProvider`` contract.

    Outcomes are queued per ``llm_request_id`` with explicit 1-based invocation
    ordinals. Concurrent calls with the same request id are rejected. Distinct
    ids run in isolation and cannot consume each other's scripts.
    """

    def __init__(self, *, clock: FakeClock | None = None) -> None:
        self._clock = clock if clock is not None else FakeClock()
        self._scripts: dict[str, dict[int, ScriptedSuccess | ScriptedFailure]] = {}
        self._next_ordinal: dict[str, int] = {}
        self._active: set[str] = set()
        self._calls: list[FakeCallRecord] = []
        self._lock = asyncio.Lock()

    @property
    def clock(self) -> FakeClock:
        """Deterministic clock shared with scripted delays."""
        return self._clock

    def script(
        self,
        *,
        llm_request_id: str,
        ordinal: int,
        outcome: ScriptedSuccess | ScriptedFailure,
    ) -> None:
        """Register ``outcome`` for ``llm_request_id`` at explicit ``ordinal``."""
        request_id = _require_request_id(llm_request_id)
        ord_value = _require_positive_ordinal(ordinal)
        if not isinstance(outcome, (ScriptedSuccess, ScriptedFailure)):
            raise TypeError("outcome must be ScriptedSuccess or ScriptedFailure")
        queue = self._scripts.setdefault(request_id, {})
        if ord_value in queue:
            raise FakeLLMProviderError(
                FakeLLMFailureCode.DUPLICATE_ORDINAL,
                llm_request_id=request_id,
                ordinal=ord_value,
            )
        queue[ord_value] = _copy_outcome(outcome)
        self._next_ordinal.setdefault(request_id, 1)

    def enqueue(
        self,
        llm_request_id: str,
        *outcomes: ScriptedSuccess | ScriptedFailure,
    ) -> None:
        """Append ``outcomes`` with consecutive ordinals after existing scripts."""
        request_id = _require_request_id(llm_request_id)
        if not outcomes:
            raise ValueError("enqueue requires at least one outcome")
        queue = self._scripts.setdefault(request_id, {})
        next_ordinal = max(queue.keys(), default=0) + 1
        for outcome in outcomes:
            if not isinstance(outcome, (ScriptedSuccess, ScriptedFailure)):
                raise TypeError("outcome must be ScriptedSuccess or ScriptedFailure")
            queue[next_ordinal] = _copy_outcome(outcome)
            next_ordinal += 1
        self._next_ordinal.setdefault(request_id, 1)

    def remaining(self, llm_request_id: str) -> Mapping[int, str]:
        """Return remaining ordinals mapped to outcome kind names (defensive)."""
        request_id = _require_request_id(llm_request_id)
        queue = self._scripts.get(request_id, {})
        return {
            ordinal: type(outcome).__name__
            for ordinal, outcome in sorted(queue.items())
        }

    def calls(self) -> tuple[FakeCallRecord, ...]:
        """Return a defensive copy of safe call records."""
        return tuple(
            FakeCallRecord(
                llm_request_id=record.llm_request_id,
                invocation_ordinal=record.invocation_ordinal,
                response_model=record.response_model,
                message_count=record.message_count,
                has_prompt=record.has_prompt,
                prompt_name=record.prompt_name,
                prompt_version=record.prompt_version,
                has_options=record.has_options,
                started_at=record.started_at,
                finished_at=record.finished_at,
                outcome=record.outcome,
                error_code=record.error_code,
            )
            for record in self._calls
        )

    def active_ids(self) -> frozenset[str]:
        """Return currently in-flight ``llm_request_id`` values."""
        return frozenset(self._active)

    def clear(self) -> None:
        """Drop scripts and call history. Active calls are unchanged."""
        self._scripts.clear()
        self._next_ordinal.clear()
        self._calls.clear()

    async def generate[T: StructuredOutput](
        self, request: LLMRequest[T]
    ) -> LLMResult[T]:
        """Consume the next scripted outcome for ``request.context.llm_request_id``."""
        if type(request) is not LLMRequest:
            raise TypeError("request must be LLMRequest")

        request_id = request.context.llm_request_id
        model_name = request.response_model.__name__
        started = self._clock.monotonic()

        async with self._lock:
            if request_id in self._active:
                self._fail_locked(
                    FakeLLMFailureCode.DUPLICATE_ACTIVE_ID,
                    llm_request_id=request_id,
                    response_model=model_name,
                    started_at=started,
                    request=request,
                )
            if request_id not in self._scripts:
                self._fail_locked(
                    FakeLLMFailureCode.UNEXPECTED_REQUEST_ID,
                    llm_request_id=request_id,
                    response_model=model_name,
                    started_at=started,
                    request=request,
                )
            ordinal = self._next_ordinal.get(request_id, 1)
            queue = self._scripts[request_id]
            if ordinal not in queue:
                self._fail_locked(
                    FakeLLMFailureCode.EXHAUSTED_SCRIPT,
                    llm_request_id=request_id,
                    response_model=model_name,
                    ordinal=ordinal,
                    started_at=started,
                    request=request,
                )
            outcome = queue.pop(ordinal)
            self._next_ordinal[request_id] = ordinal + 1
            self._active.add(request_id)

        try:
            if outcome.delay_seconds > 0.0:
                await self._clock.sleep(outcome.delay_seconds)
            else:
                # Preserve cancellation checkpoints even for zero-delay scripts.
                await asyncio.sleep(0)

            if isinstance(outcome, ScriptedFailure):
                error = _copy_error(outcome.error)
                finished = self._clock.monotonic()
                self._record(
                    request=request,
                    ordinal=ordinal,
                    started_at=started,
                    finished_at=finished,
                    outcome_kind="failure",
                    error_code=error.code.value,
                )
                raise error

            if type(outcome.output) is not request.response_model:
                finished = self._clock.monotonic()
                self._record(
                    request=request,
                    ordinal=ordinal,
                    started_at=started,
                    finished_at=finished,
                    outcome_kind="harness_error",
                    error_code=FakeLLMFailureCode.RESPONSE_MODEL_MISMATCH.value,
                )
                self._log_unexpected(
                    FakeLLMFailureCode.RESPONSE_MODEL_MISMATCH,
                    llm_request_id=request_id,
                    response_model=model_name,
                    ordinal=ordinal,
                )
                raise FakeLLMProviderError(
                    FakeLLMFailureCode.RESPONSE_MODEL_MISMATCH,
                    llm_request_id=request_id,
                    response_model=model_name,
                    ordinal=ordinal,
                )

            output = _copy_output(outcome.output)
            metadata = (
                _default_metadata()
                if outcome.metadata is None
                else _copy_metadata(outcome.metadata)
            )
            result: LLMResult[T] = LLMResult(output=output, metadata=metadata)
            finished = self._clock.monotonic()
            self._record(
                request=request,
                ordinal=ordinal,
                started_at=started,
                finished_at=finished,
                outcome_kind="success",
            )
            return result
        except asyncio.CancelledError:
            finished = self._clock.monotonic()
            self._record(
                request=request,
                ordinal=ordinal,
                started_at=started,
                finished_at=finished,
                outcome_kind="cancelled",
            )
            raise
        finally:
            async with self._lock:
                self._active.discard(request_id)

    def _fail_locked(
        self,
        code: FakeLLMFailureCode,
        *,
        llm_request_id: str,
        response_model: str,
        started_at: float,
        request: LLMRequest[Any],
        ordinal: int | None = None,
    ) -> None:
        finished = self._clock.monotonic()
        self._record(
            request=request,
            ordinal=ordinal if ordinal is not None else 0,
            started_at=started_at,
            finished_at=finished,
            outcome_kind="harness_error",
            error_code=code.value,
        )
        self._log_unexpected(
            code,
            llm_request_id=llm_request_id,
            response_model=response_model,
            ordinal=ordinal,
        )
        raise FakeLLMProviderError(
            code,
            llm_request_id=llm_request_id,
            response_model=response_model,
            ordinal=ordinal,
        )

    def _record(
        self,
        *,
        request: LLMRequest[Any],
        ordinal: int,
        started_at: float,
        finished_at: float,
        outcome_kind: str,
        error_code: str | None = None,
    ) -> None:
        prompt = request.prompt
        record = FakeCallRecord(
            llm_request_id=request.context.llm_request_id,
            invocation_ordinal=ordinal,
            response_model=request.response_model.__name__,
            message_count=len(request.messages),
            has_prompt=prompt is not None,
            prompt_name=None if prompt is None else prompt.name,
            prompt_version=None if prompt is None else prompt.version,
            has_options=request.options is not None,
            started_at=started_at,
            finished_at=finished_at,
            outcome=outcome_kind,
            error_code=error_code,
        )
        # Defensive detach: store a fresh frozen record (already immutable).
        self._calls.append(deepcopy(record))

    @staticmethod
    def _log_unexpected(
        code: FakeLLMFailureCode,
        *,
        llm_request_id: str,
        response_model: str,
        ordinal: int | None,
    ) -> None:
        _LOG.error(
            "fake_llm_unexpected code=%s llm_request_id=%s response_model=%s "
            "ordinal=%s",
            code.value,
            llm_request_id,
            response_model,
            "-" if ordinal is None else ordinal,
        )

    def __repr__(self) -> str:
        return (
            "FakeLLMProvider("
            f"scripted_ids={len(self._scripts)}, "
            f"call_count={len(self._calls)}, "
            f"active_count={len(self._active)})"
        )


def _require_request_id(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("llm_request_id must be a string")
    if not value or value.strip() != value or not value.strip():
        raise ValueError("llm_request_id must be a non-blank string")
    return value
