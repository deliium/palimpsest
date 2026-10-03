"""Unit tests for filesystem RecordingStore atomic write and dual lookup."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from llm.models import StructuredOutputMode
from llm.recording.codec import encode_exchange_record_bytes
from llm.recording.models import (
    ExchangeCorrelation,
    ExchangeEffectiveOptions,
    ExchangeValidation,
    ExchangeValidationStatus,
    LLMExchangeRecord,
    SchemaIdentity,
)
from llm.recording.store import (
    CorrelationKey,
    FilesystemRecordingStore,
    RecordingStoreError,
)

_DIGEST = "d" * 64
_DIGEST_B = "e" * 64


def _record(
    *,
    cache_namespace: str = "run-1",
    agent_id: str = "agent-1",
    tick: int = 0,
    component: str = "reconstructive_memory",
    llm_request_id: str = "req-1",
    response: dict[str, object] | None = None,
) -> LLMExchangeRecord:
    return LLMExchangeRecord(
        provider="fake",
        model="scripted",
        structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
        schema_identity=SchemaIdentity(
            qualname="tests.Sample",
            digest=_DIGEST,
        ),
        prompt=None,
        request_digest=_DIGEST_B,
        effective_options=ExchangeEffectiveOptions(temperature=0.0),
        validation=ExchangeValidation(
            status=ExchangeValidationStatus.VALIDATED,
            reason_code="validated",
        ),
        response={"kind": "wait"} if response is None else response,
        usage=None,
        latency_ms=5,
        correlation=ExchangeCorrelation(
            run_id="run-1",
            agent_id=agent_id,
            tick=tick,
            llm_request_id=llm_request_id,
        ),
        component=component,
        cache_namespace=cache_namespace,
    )


def test_put_get_by_cache_key_and_correlation(tmp_path: Path) -> None:
    store = FilesystemRecordingStore(tmp_path)
    record = _record()
    store.put(record, cache_key=_DIGEST)
    loaded = store.get_by_cache_key(_DIGEST, cache_namespace="run-1")
    assert loaded == record
    by_corr = store.get_by_correlation(
        CorrelationKey(
            cache_namespace="run-1",
            agent_id="agent-1",
            tick=0,
            component="reconstructive_memory",
            llm_request_id="req-1",
        )
    )
    assert by_corr == record
    assert store.count() == 1
    assert store.list_cache_keys(cache_namespace="run-1") == (_DIGEST,)


def test_namespace_isolation(tmp_path: Path) -> None:
    store = FilesystemRecordingStore(tmp_path)
    store.put(_record(cache_namespace="run-a"), cache_key=_DIGEST)
    assert store.get_by_cache_key(_DIGEST, cache_namespace="run-b") is None


def test_cache_key_idempotent_same_payload(tmp_path: Path) -> None:
    store = FilesystemRecordingStore(tmp_path)
    record = _record()
    store.put(record, cache_key=_DIGEST)
    store.put(record, cache_key=_DIGEST)
    assert store.count() == 1


def test_cache_key_conflict_fails_closed(tmp_path: Path) -> None:
    store = FilesystemRecordingStore(tmp_path)
    store.put(_record(response={"kind": "wait"}), cache_key=_DIGEST)
    with pytest.raises(RecordingStoreError, match="cache_key_conflict"):
        store.put(_record(response={"kind": "talk"}), cache_key=_DIGEST)


def test_correlation_overwrite_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = FilesystemRecordingStore(tmp_path)
    first = _record(response={"kind": "wait"})
    second = _record(response={"kind": "talk"})
    # Distinct cache keys, same correlation → last-write-wins on corr index.
    store.put(first, cache_key=_DIGEST)
    with caplog.at_level(logging.WARNING, logger="llm.recording"):
        store.put(second, cache_key=_DIGEST_B)
    assert any(
        "correlation_overwrite" in record.getMessage() for record in caplog.records
    )
    loaded = store.get_by_correlation(
        CorrelationKey(
            cache_namespace="run-1",
            agent_id="agent-1",
            tick=0,
            component="reconstructive_memory",
            llm_request_id="req-1",
        )
    )
    assert loaded is not None
    assert loaded.response == {"kind": "talk"}


def test_corrupt_record_fails_closed(tmp_path: Path) -> None:
    store = FilesystemRecordingStore(tmp_path)
    store.put(_record(), cache_key=_DIGEST)
    path = next((tmp_path / "ns").glob("*/keys/*.json"))
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(RecordingStoreError, match="corrupt_or_unknown_schema"):
        store.get_by_cache_key(_DIGEST, cache_namespace="run-1")


def test_unknown_schema_fails_closed(tmp_path: Path) -> None:
    store = FilesystemRecordingStore(tmp_path)
    record = _record()
    store.put(record, cache_key=_DIGEST)
    path = next((tmp_path / "ns").glob("*/keys/*.json"))
    path.write_bytes(
        encode_exchange_record_bytes(record).replace(
            b"llm-exchange-v1", b"llm-exchange-v0"
        )
    )
    with pytest.raises(RecordingStoreError, match="corrupt_or_unknown_schema"):
        store.get_by_cache_key(_DIGEST, cache_namespace="run-1")


def test_path_traversal_rejected(tmp_path: Path) -> None:
    store = FilesystemRecordingStore(tmp_path)
    with pytest.raises(RecordingStoreError, match="invalid_agent_id"):
        store.get_by_correlation(
            CorrelationKey(
                cache_namespace="run-1",
                agent_id="../escape",
                tick=0,
                component="reconstructive_memory",
                llm_request_id="req-1",
            )
        )


def test_open_log_avoids_home_path(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="llm.recording"):
        FilesystemRecordingStore(tmp_path)
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert "recording_store_open" in joined
    assert str(tmp_path.resolve()) not in joined
