"""LLM recording / replay contracts and store façade."""

from llm.recording.cache_key import (
    derive_cache_key,
    digest_json_schema,
    digest_request_messages,
    normalize_message_content,
    response_model_qualname,
    schema_identity_for,
)
from llm.recording.codec import (
    decode_exchange_record,
    decode_exchange_record_bytes,
    encode_exchange_record,
    encode_exchange_record_bytes,
)
from llm.recording.models import (
    LLM_EXCHANGE_SCHEMA_ID,
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
    FilesystemRecordingStore,
    LookupMode,
    RecordingStore,
    RecordingStoreError,
)

__all__ = [
    "LLM_EXCHANGE_SCHEMA_ID",
    "CorrelationKey",
    "ExchangeCorrelation",
    "ExchangeEffectiveOptions",
    "ExchangePromptRef",
    "ExchangeUsage",
    "ExchangeValidation",
    "ExchangeValidationStatus",
    "FilesystemRecordingStore",
    "LLMExchangeRecord",
    "LookupMode",
    "RecordingStore",
    "RecordingStoreError",
    "SchemaIdentity",
    "decode_exchange_record",
    "decode_exchange_record_bytes",
    "derive_cache_key",
    "digest_json_schema",
    "digest_request_messages",
    "encode_exchange_record",
    "encode_exchange_record_bytes",
    "normalize_message_content",
    "response_model_qualname",
    "schema_identity_for",
]
