"""Composition helpers for recording providers (no infrastructure imports)."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Final

from llm.models import ProviderDefaults, StructuredOutputMode
from llm.recording.provider import RecordingLLMProvider, RecordingMode
from llm.recording.store import (
    FilesystemRecordingStore,
    LookupMode,
    RecordingStore,
)

_LOG: Final[logging.Logger] = logging.getLogger("llm.recording")
_DIGEST_PREFIX: Final[int] = 12

MonotonicClock = Callable[[], float]


def create_filesystem_recording_store(root_dir: Path | str) -> FilesystemRecordingStore:
    """Construct a filesystem store at an explicit root path."""
    store = FilesystemRecordingStore(root_dir)
    _LOG.debug(
        "recording_store_factory root_basename=%s",
        store.root_dir.name,
    )
    return store


def wrap_recording_provider(
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
) -> RecordingLLMProvider:
    """Wrap ``inner`` with a recording decorator using explicit composition args."""
    namespace_prefix = ""
    if cache_namespace:
        namespace_prefix = hashlib.sha256(cache_namespace.encode("utf-8")).hexdigest()[
            :_DIGEST_PREFIX
        ]
    _LOG.debug(
        "wrap_recording_provider mode=%s lookup_mode=%s namespace_prefix=%s "
        "store_configured=%s",
        mode.value,
        lookup_mode.value,
        namespace_prefix,
        store is not None,
    )
    return RecordingLLMProvider(
        inner=inner,
        mode=mode,
        store=store,
        cache_namespace=cache_namespace,
        lookup_mode=lookup_mode,
        structured_output_mode=structured_output_mode,
        provider_name=provider_name,
        model_name=model_name,
        monotonic=monotonic,
        defaults=defaults,
    )
