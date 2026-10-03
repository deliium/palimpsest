"""Recording / cache / replay decorator around an inner ``LLMProvider``."""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import StrEnum
from typing import Final

from llm.errors import LLMError, LLMErrorCode
from llm.models import (
    EffectiveOptions,
    FinishReason,
    LLMRequest,
    LLMResult,
    LLMResultMetadata,
    ProviderDefaults,
    StructuredOutput,
    StructuredOutputMode,
    TokenUsage,
    resolve_effective_options,
    validate_structured_output,
)
from llm.recording.cache_key import (
    derive_cache_key,
    digest_request_messages,
    schema_identity_for,
)
from llm.recording.models import (
    ExchangeCorrelation,
    ExchangeEffectiveOptions,
    ExchangePromptRef,
    ExchangeUsage,
    ExchangeValidation,
    ExchangeValidationStatus,
    LLMExchangeRecord,
    SchemaIdentity,
)
from llm.recording.store import (
    CorrelationKey,
    LookupMode,
    RecordingStore,
    RecordingStoreError,
)

_LOG: Final[logging.Logger] = logging.getLogger("llm.recording")
_DIGEST_PREFIX: Final[int] = 12

MonotonicClock = Callable[[], float]


class RecordingMode(StrEnum):
    """Provider-facing record / cache / replay modes (not runner policy)."""

    LIVE = "live"
    RECORD = "record"
    CACHE = "cache"
    REPLAY = "replay"


class RecordingLLMProvider:
    """Decorator that persists or replays validated structured LLM exchanges.

    Wrap order (outer → inner): ``BudgetGuardedProvider`` → this → inner provider.
    ``replay`` never calls the inner provider. Persist only validated successes.
    """

    __slots__ = (
        "_cache_namespace",
        "_defaults",
        "_inner",
        "_lookup_mode",
        "_mode",
        "_model_name",
        "_monotonic",
        "_provider_name",
        "_store",
        "_structured_output_mode",
    )

    def __init__(
        self,
        *,
        inner: object,
        mode: RecordingMode,
        store: RecordingStore | None,
        cache_namespace: str,
        lookup_mode: LookupMode,
        structured_output_mode: StructuredOutputMode,
        provider_name: str,
        model_name: str,
        monotonic: MonotonicClock,
        defaults: ProviderDefaults | None = None,
    ) -> None:
        if not isinstance(mode, RecordingMode):
            raise TypeError("mode must be RecordingMode")
        if not isinstance(lookup_mode, LookupMode):
            raise TypeError("lookup_mode must be LookupMode")
        if not isinstance(structured_output_mode, StructuredOutputMode):
            raise TypeError("structured_output_mode must be StructuredOutputMode")
        if not callable(monotonic):
            raise TypeError("monotonic must be callable")
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name must be a non-blank string")
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must be a non-blank string")
        if defaults is not None and type(defaults) is not ProviderDefaults:
            raise TypeError("defaults must be ProviderDefaults")

        if mode is not RecordingMode.LIVE:
            if store is None:
                _LOG.error(
                    "recording_provider_init_failed reason=recording_store_required "
                    "mode=%s",
                    mode.value,
                )
                raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
            if not isinstance(cache_namespace, str) or not cache_namespace.strip():
                _LOG.error(
                    "recording_provider_init_failed reason=empty_cache_namespace "
                    "mode=%s",
                    mode.value,
                )
                raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)

        self._inner = inner
        self._mode = mode
        self._store = store
        self._cache_namespace = cache_namespace.strip() if cache_namespace else ""
        self._lookup_mode = lookup_mode
        self._structured_output_mode = structured_output_mode
        self._provider_name = provider_name.strip()
        self._model_name = model_name.strip()
        self._defaults = defaults if defaults is not None else ProviderDefaults()
        self._monotonic = monotonic
        _LOG.debug(
            "recording_provider_init mode=%s lookup_mode=%s "
            "store_configured=%s namespace_chars=%s",
            mode.value,
            lookup_mode.value,
            store is not None,
            len(self._cache_namespace),
        )

    @property
    def mode(self) -> RecordingMode:
        return self._mode

    @property
    def inner(self) -> object:
        return self._inner

    def __repr__(self) -> str:
        return (
            "RecordingLLMProvider("
            f"mode={self._mode.value!r}, "
            f"lookup_mode={self._lookup_mode.value!r}, "
            f"store_configured={self._store is not None}, "
            f"namespace_chars={len(self._cache_namespace)})"
        )

    async def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if close is not None and callable(close):
            await close()

    async def generate[T: StructuredOutput](
        self, request: LLMRequest[T]
    ) -> LLMResult[T]:
        if type(request) is not LLMRequest:
            raise TypeError("request must be LLMRequest")

        if self._mode is RecordingMode.LIVE:
            _LOG.debug(
                "recording_generate mode=live llm_request_id=%s",
                request.context.llm_request_id,
            )
            return await self._inner.generate(request)  # type: ignore[no-any-return]

        self._require_component(request)
        started = self._monotonic()
        schema_identity = schema_identity_for(request.response_model)
        request_digest = digest_request_messages(request.messages)
        effective = resolve_effective_options(self._defaults, request.options)
        cache_key = derive_cache_key(
            cache_namespace=self._cache_namespace,
            provider_name=self._provider_name,
            model_name=self._model_name,
            structured_output_mode=self._structured_output_mode,
            schema_identity=schema_identity,
            prompt=request.prompt,
            request_digest=request_digest,
            effective_options=effective,
            agent_id=request.context.agent_id,
            component=request.context.component or "",
        )
        _LOG.debug(
            "recording_generate mode=%s llm_request_id=%s key_prefix=%s "
            "lookup_mode=%s",
            self._mode.value,
            request.context.llm_request_id,
            cache_key[:_DIGEST_PREFIX],
            self._lookup_mode.value,
        )

        if self._mode is RecordingMode.REPLAY:
            return self._replay(
                request,
                cache_key=cache_key,
                schema_identity=schema_identity,
                request_digest=request_digest,
                started=started,
            )

        if self._mode is RecordingMode.CACHE:
            hit = self._lookup(
                request,
                cache_key=cache_key,
                schema_identity=schema_identity,
                fail_on_digest_mismatch=False,
            )
            if hit is not None:
                latency_ms = self._latency_ms(started)
                _LOG.info(
                    "recording_generate mode=cache outcome=hit key_prefix=%s "
                    "latency_ms=%s",
                    cache_key[:_DIGEST_PREFIX],
                    latency_ms,
                )
                return hit
            _LOG.info(
                "recording_generate mode=cache outcome=miss key_prefix=%s",
                cache_key[:_DIGEST_PREFIX],
            )

        result = await self._inner.generate(request)  # type: ignore[misc]
        latency_ms = self._latency_ms(started)
        self._persist_success(
            request,
            result=result,
            cache_key=cache_key,
            schema_identity=schema_identity,
            request_digest=request_digest,
            effective=effective,
            latency_ms=latency_ms,
        )
        _LOG.info(
            "recording_generate mode=%s outcome=persisted key_prefix=%s "
            "latency_ms=%s",
            self._mode.value,
            cache_key[:_DIGEST_PREFIX],
            latency_ms,
        )
        return result

    def _require_component[T: StructuredOutput](self, request: LLMRequest[T]) -> None:
        component = request.context.component
        if component is None or not component.strip():
            _LOG.error(
                "recording_generate_failed reason=component_required_for_recording "
                "mode=%s llm_request_id=%s",
                self._mode.value,
                request.context.llm_request_id,
            )
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)

    def _latency_ms(self, started: float) -> int:
        elapsed = self._monotonic() - started
        if elapsed < 0:
            elapsed = 0.0
        return int(elapsed * 1000.0)

    def _replay[T: StructuredOutput](
        self,
        request: LLMRequest[T],
        *,
        cache_key: str,
        schema_identity: SchemaIdentity,
        request_digest: str,
        started: float,
    ) -> LLMResult[T]:
        result = self._lookup(
            request,
            cache_key=cache_key,
            schema_identity=schema_identity,
            fail_on_digest_mismatch=True,
        )
        if result is None:
            _LOG.error(
                "recording_generate_failed reason=replay_miss mode=replay "
                "key_prefix=%s llm_request_id=%s",
                cache_key[:_DIGEST_PREFIX],
                request.context.llm_request_id,
            )
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        latency_ms = self._latency_ms(started)
        _LOG.info(
            "recording_generate mode=replay outcome=hit key_prefix=%s "
            "request_digest_prefix=%s latency_ms=%s",
            cache_key[:_DIGEST_PREFIX],
            request_digest[:_DIGEST_PREFIX],
            latency_ms,
        )
        return result

    def _lookup[T: StructuredOutput](
        self,
        request: LLMRequest[T],
        *,
        cache_key: str,
        schema_identity: SchemaIdentity,
        fail_on_digest_mismatch: bool,
    ) -> LLMResult[T] | None:
        assert self._store is not None
        try:
            if self._lookup_mode is LookupMode.BY_CORRELATION:
                record = self._store.get_by_correlation(
                    CorrelationKey(
                        cache_namespace=self._cache_namespace,
                        agent_id=request.context.agent_id,
                        tick=request.context.tick,
                        component=request.context.component or "",
                        llm_request_id=request.context.llm_request_id,
                    )
                )
            else:
                record = self._store.get_by_cache_key(
                    cache_key, cache_namespace=self._cache_namespace
                )
        except RecordingStoreError:
            _LOG.error(
                "recording_lookup_failed reason=store_error mode=%s",
                self._mode.value,
            )
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False) from None

        if record is None:
            return None

        if not self._digests_compatible(
            record, schema_identity=schema_identity, request=request
        ):
            if fail_on_digest_mismatch:
                _LOG.error(
                    "recording_generate_failed "
                    "reason=schema_or_prompt_version_mismatch mode=%s "
                    "schema_digest_prefix=%s",
                    self._mode.value,
                    schema_identity.digest[:_DIGEST_PREFIX],
                )
                raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
            _LOG.info(
                "recording_lookup mode=%s outcome=digest_mismatch_as_miss "
                "key_prefix=%s",
                self._mode.value,
                cache_key[:_DIGEST_PREFIX],
            )
            return None

        return self._result_from_record(request, record)

    def _digests_compatible[T: StructuredOutput](
        self,
        record: LLMExchangeRecord,
        *,
        schema_identity: SchemaIdentity,
        request: LLMRequest[T],
    ) -> bool:
        if record.schema_identity.digest != schema_identity.digest:
            return False
        if record.schema_identity.qualname != schema_identity.qualname:
            return False
        current_prompt = request.prompt
        stored = record.prompt
        if current_prompt is None and stored is None:
            return True
        if current_prompt is None or stored is None:
            return False
        return (
            current_prompt.name == stored.name
            and current_prompt.version == stored.version
            and current_prompt.digest == stored.digest
        )

    def _result_from_record[T: StructuredOutput](
        self,
        request: LLMRequest[T],
        record: LLMExchangeRecord,
    ) -> LLMResult[T]:
        if record.response is None:
            _LOG.error(
                "recording_generate_failed reason=empty_stored_response mode=%s",
                self._mode.value,
            )
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        try:
            output = validate_structured_output(
                request.response_model, record.response
            )
        except (TypeError, ValueError):
            _LOG.error(
                "recording_generate_failed reason=stored_response_invalid mode=%s",
                self._mode.value,
            )
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False) from None

        usage: TokenUsage | None = None
        if record.usage is not None:
            usage = TokenUsage(
                input_tokens=record.usage.input_tokens,
                output_tokens=record.usage.output_tokens,
                total_tokens=record.usage.total_tokens,
            )
        return LLMResult(
            output=output,
            metadata=LLMResultMetadata(
                provider_name=record.provider,
                model_name=record.model,
                finish_reason=FinishReason.STOP,
                usage=usage,
                upstream_request_id=record.correlation.upstream_request_id,
            ),
        )

    def _persist_success[T: StructuredOutput](
        self,
        request: LLMRequest[T],
        *,
        result: LLMResult[T],
        cache_key: str,
        schema_identity: SchemaIdentity,
        request_digest: str,
        effective: EffectiveOptions,
        latency_ms: int,
    ) -> None:
        assert self._store is not None
        prompt_ref: ExchangePromptRef | None = None
        if request.prompt is not None:
            prompt_ref = ExchangePromptRef(
                name=request.prompt.name,
                version=request.prompt.version,
                digest=request.prompt.digest,
            )
        usage: ExchangeUsage | None = None
        if result.metadata.usage is not None:
            usage = ExchangeUsage(
                input_tokens=result.metadata.usage.input_tokens,
                output_tokens=result.metadata.usage.output_tokens,
                total_tokens=result.metadata.usage.total_tokens,
            )
        record = LLMExchangeRecord(
            provider=result.metadata.provider_name,
            model=result.metadata.model_name,
            structured_output_mode=self._structured_output_mode,
            schema_identity=schema_identity,
            prompt=prompt_ref,
            request_digest=request_digest,
            effective_options=ExchangeEffectiveOptions(
                temperature=effective.temperature,
                max_output_tokens=effective.max_output_tokens,
                top_p=effective.top_p,
                seed=effective.seed,
                stop=effective.stop,
            ),
            validation=ExchangeValidation(
                status=ExchangeValidationStatus.VALIDATED,
                reason_code="validated",
            ),
            response=result.output.model_dump(mode="json"),
            usage=usage,
            latency_ms=latency_ms,
            correlation=ExchangeCorrelation(
                run_id=request.context.run_id,
                agent_id=request.context.agent_id,
                tick=request.context.tick,
                llm_request_id=request.context.llm_request_id,
                upstream_request_id=result.metadata.upstream_request_id,
            ),
            component=request.context.component or "",
            cache_namespace=self._cache_namespace,
        )
        try:
            self._store.put(record, cache_key=cache_key)
        except RecordingStoreError as exc:
            _LOG.error(
                "recording_persist_failed reason=%s mode=%s key_prefix=%s",
                exc.reason,
                self._mode.value,
                cache_key[:_DIGEST_PREFIX],
            )
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False) from None
