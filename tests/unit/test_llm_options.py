"""Effective option precedence and deterministic retry policy."""

from __future__ import annotations

import pytest

from llm.errors import LLMError, LLMErrorCode
from llm.models import (
    EffectiveOptions,
    LLMRequestOptions,
    ProviderDefaults,
    RetryPolicy,
    StructuredOutputMode,
    resolve_effective_options,
)


def test_structured_output_mode_values() -> None:
    assert StructuredOutputMode.JSON_SCHEMA.value == "json_schema"
    assert StructuredOutputMode.JSON_OBJECT.value == "json_object"
    assert StructuredOutputMode.PROMPT_ONLY.value == "prompt_only"


def test_resolve_prefers_non_none_request_including_temperature_zero() -> None:
    defaults = ProviderDefaults(
        temperature=0.7,
        max_output_tokens=256,
        top_p=0.9,
        seed=7,
        stop=("END",),
    )
    request = LLMRequestOptions(
        temperature=0.0,
        max_output_tokens=None,
        top_p=0.5,
        seed=None,
        stop=None,
    )
    effective = resolve_effective_options(defaults, request)
    assert effective == EffectiveOptions(
        temperature=0.0,
        max_output_tokens=256,
        top_p=0.5,
        seed=7,
        stop=("END",),
    )


def test_resolve_with_none_request_uses_defaults() -> None:
    defaults = ProviderDefaults(temperature=0.2, max_output_tokens=128)
    effective = resolve_effective_options(defaults, None)
    assert effective.temperature == 0.2
    assert effective.max_output_tokens == 128
    assert effective.top_p is None
    assert effective.seed is None
    assert effective.stop is None


def test_resolve_omits_when_both_none() -> None:
    effective = resolve_effective_options(ProviderDefaults(), LLMRequestOptions())
    assert effective == EffectiveOptions()


def test_request_overrides_do_not_include_mode_or_identity_fields() -> None:
    # LLMRequestOptions / EffectiveOptions intentionally omit mode and identity.
    assert not hasattr(LLMRequestOptions(), "structured_output_mode")
    assert not hasattr(EffectiveOptions(), "structured_output_mode")
    assert not hasattr(LLMRequestOptions(), "provider_name")
    assert not hasattr(ProviderDefaults(), "base_url")
    assert not hasattr(ProviderDefaults(), "api_key")


def test_provider_defaults_reuse_request_option_validation() -> None:
    with pytest.raises(ValueError, match="temperature"):
        ProviderDefaults(temperature=3.0)
    with pytest.raises(TypeError, match="max_output_tokens"):
        ProviderDefaults(max_output_tokens=True)


def test_retry_policy_max_attempts_is_total_attempts() -> None:
    policy = RetryPolicy(max_attempts=3)
    first = LLMError(LLMErrorCode.CONNECTION, attempts=1)
    second = LLMError(LLMErrorCode.CONNECTION, attempts=2)
    third = LLMError(LLMErrorCode.CONNECTION, attempts=3)
    assert policy.should_retry(first) is True
    assert policy.should_retry(second) is True
    assert policy.should_retry(third) is False


def test_retry_policy_documents_non_retryable_codes() -> None:
    policy = RetryPolicy(max_attempts=5)
    assert policy.should_retry(LLMError(LLMErrorCode.CONFIGURATION)) is False
    assert policy.should_retry(LLMError(LLMErrorCode.AUTHENTICATION)) is False
    assert policy.should_retry(LLMError(LLMErrorCode.REFUSAL)) is False
    assert policy.should_retry(LLMError(LLMErrorCode.INCOMPLETE)) is False
    assert policy.should_retry(LLMError(LLMErrorCode.CLOSED)) is False
    assert policy.should_retry(LLMError(LLMErrorCode.PROVIDER_PROTOCOL)) is False
    assert (
        policy.should_retry(
            LLMError(
                LLMErrorCode.RETRY_EXHAUSTION,
                last_code=LLMErrorCode.TIMEOUT,
                attempts=3,
            )
        )
        is False
    )


def test_retry_policy_can_disable_format_and_schema_retries() -> None:
    enabled = RetryPolicy(max_attempts=3)
    disabled = RetryPolicy(
        max_attempts=3,
        retry_output_format=False,
        retry_output_schema=False,
    )
    format_err = LLMError(LLMErrorCode.OUTPUT_FORMAT, attempts=1)
    schema_err = LLMError(LLMErrorCode.OUTPUT_SCHEMA, attempts=1)
    assert enabled.should_retry(format_err) is True
    assert enabled.should_retry(schema_err) is True
    assert disabled.should_retry(format_err) is False
    assert disabled.should_retry(schema_err) is False


def test_deterministic_backoff_and_bounded_retry_after() -> None:
    policy = RetryPolicy(
        initial_backoff_seconds=0.5,
        backoff_multiplier=2.0,
        max_backoff_seconds=4.0,
        max_retry_after_seconds=10.0,
    )
    assert policy.backoff_seconds(1) == 0.5
    assert policy.backoff_seconds(2) == 1.0
    assert policy.backoff_seconds(3) == 2.0
    assert policy.backoff_seconds(4) == 4.0
    assert policy.backoff_seconds(5) == 4.0

    assert policy.bound_retry_after_seconds(3.5) == 3.5
    assert policy.bound_retry_after_seconds(99.0) == 10.0
    assert policy.bound_retry_after_seconds(0) is None
    assert policy.bound_retry_after_seconds(-1) is None
    assert policy.bound_retry_after_seconds(float("nan")) is None
    assert policy.bound_retry_after_seconds("5") is None
    assert policy.bound_retry_after_seconds(True) is None

    assert policy.resolve_delay_seconds(2, retry_after_seconds=7.0) == 7.0
    assert policy.resolve_delay_seconds(2, retry_after_seconds=None) == 1.0
    assert policy.resolve_delay_seconds(2, retry_after_seconds="Wed, 01 Jan") == 1.0


def test_retry_policy_validation() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError, match="per_attempt_timeout"):
        RetryPolicy(per_attempt_timeout_seconds=0)
    with pytest.raises(ValueError, match="total_deadline"):
        RetryPolicy(total_deadline_seconds=-1.0)
