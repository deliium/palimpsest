"""Filesystem recording store with atomic writes and dual lookup indexes."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol

from llm.recording.codec import (
    decode_exchange_record_bytes,
    encode_exchange_record_bytes,
)
from llm.recording.models import LLMExchangeRecord

_LOG: Final[logging.Logger] = logging.getLogger("llm.recording")

_HEX64_RE: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")
# Matches the LLM safe-id / header-safe family (includes ':'); traversal rejected separately.
_SAFE_SEGMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)
_DIGEST_PREFIX: Final[int] = 12


class LookupMode(StrEnum):
    """Store lookup strategy selected at composition time."""

    BY_CACHE_KEY = "by_cache_key"
    BY_CORRELATION = "by_correlation"


class RecordingStoreError(Exception):
    """Fail-closed store error with a stable reason code only."""

    def __init__(self, reason: str) -> None:
        if not isinstance(reason, str) or not reason:
            raise TypeError("reason must be a non-empty string")
        self.reason = reason
        super().__init__(reason)
        self.__cause__ = None
        self.__context__ = None
        self.__suppress_context__ = True

    def __repr__(self) -> str:
        return f"RecordingStoreError(reason={self.reason!r})"


@dataclass(frozen=True, slots=True)
class CorrelationKey:
    """Exact correlation tuple for bit-stable replay lookup."""

    cache_namespace: str
    agent_id: str
    tick: int
    component: str
    llm_request_id: str


class RecordingStore(Protocol):
    """Persist and look up validated LLM exchange records."""

    def put(self, record: LLMExchangeRecord, *, cache_key: str) -> None:
        """Persist ``record`` under ``cache_key`` and its correlation tuple."""
        ...

    def get_by_cache_key(
        self, cache_key: str, *, cache_namespace: str
    ) -> LLMExchangeRecord | None:
        """Load by content-addressed key within ``cache_namespace``."""
        ...

    def get_by_correlation(
        self, key: CorrelationKey
    ) -> LLMExchangeRecord | None:
        """Load by exact correlation tuple."""
        ...

    def count(self) -> int:
        """Count exchange payload files under the key index."""
        ...

    def list_cache_keys(self, *, cache_namespace: str) -> tuple[str, ...]:
        """List cache-key digests present for ``cache_namespace``."""
        ...


def _namespace_dir_name(cache_namespace: str) -> str:
    return hashlib.sha256(cache_namespace.encode("utf-8")).hexdigest()


def _require_cache_key(cache_key: str) -> str:
    if not isinstance(cache_key, str) or _HEX64_RE.fullmatch(cache_key) is None:
        raise RecordingStoreError("invalid_cache_key")
    return cache_key


def _require_safe_segment(name: str, value: str) -> str:
    if not isinstance(value, str) or _SAFE_SEGMENT_RE.fullmatch(value) is None:
        raise RecordingStoreError(f"invalid_{name}")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise RecordingStoreError(f"invalid_{name}")
    return value


def _require_namespace(cache_namespace: str) -> str:
    if not isinstance(cache_namespace, str) or not cache_namespace.strip():
        raise RecordingStoreError("empty_cache_namespace")
    if cache_namespace.strip() != cache_namespace:
        raise RecordingStoreError("empty_cache_namespace")
    return cache_namespace


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _payload_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class FilesystemRecordingStore:
    """Stdlib filesystem store rooted at ``root_dir``.

    Layout (namespace directories are SHA-256 of the logical namespace string)::

        <root>/ns/<namespace_digest>/keys/<cache_key>.json
        <root>/ns/<namespace_digest>/corr/<agent>/<tick>/<component>/<req>.json
    """

    def __init__(self, root_dir: Path | str) -> None:
        if isinstance(root_dir, str):
            root = Path(root_dir)
        elif isinstance(root_dir, Path):
            root = root_dir
        else:
            raise TypeError("root_dir must be Path or str")
        resolved = root.expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        self._root = resolved
        _LOG.info(
            "recording_store_open root_basename=%s",
            resolved.name,
        )

    @property
    def root_dir(self) -> Path:
        return self._root

    def _ns_root(self, cache_namespace: str) -> Path:
        digest = _namespace_dir_name(_require_namespace(cache_namespace))
        return self._root / "ns" / digest

    def _key_path(self, *, cache_namespace: str, cache_key: str) -> Path:
        key = _require_cache_key(cache_key)
        path = self._ns_root(cache_namespace) / "keys" / f"{key}.json"
        self._assert_under_root(path)
        return path

    def _corr_path(self, key: CorrelationKey) -> Path:
        namespace = _require_namespace(key.cache_namespace)
        agent = _require_safe_segment("agent_id", key.agent_id)
        if isinstance(key.tick, bool) or not isinstance(key.tick, int) or key.tick < 0:
            raise RecordingStoreError("invalid_tick")
        component = _require_safe_segment("component", key.component)
        request_id = _require_safe_segment("llm_request_id", key.llm_request_id)
        path = (
            self._ns_root(namespace)
            / "corr"
            / agent
            / str(key.tick)
            / component
            / f"{request_id}.json"
        )
        self._assert_under_root(path)
        return path

    def _assert_under_root(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self._root)
        except ValueError as exc:
            _LOG.error("recording_store_path_rejected reason=path_traversal")
            raise RecordingStoreError("path_traversal") from exc

    def put(self, record: LLMExchangeRecord, *, cache_key: str) -> None:
        if type(record) is not LLMExchangeRecord:
            raise TypeError("record must be LLMExchangeRecord")
        key = _require_cache_key(cache_key)
        namespace = _require_namespace(record.cache_namespace)
        payload = encode_exchange_record_bytes(record)
        key_path = self._key_path(cache_namespace=namespace, cache_key=key)
        if key_path.exists():
            existing = key_path.read_bytes()
            if _payload_digest(existing) != _payload_digest(payload):
                _LOG.error(
                    "recording_store_put_failed reason=cache_key_conflict "
                    "key_prefix=%s",
                    key[:_DIGEST_PREFIX],
                )
                raise RecordingStoreError("cache_key_conflict")
            _LOG.debug(
                "recording_store_put reason=cache_key_idempotent key_prefix=%s",
                key[:_DIGEST_PREFIX],
            )
        else:
            _atomic_write(key_path, payload)
            _LOG.info(
                "recording_store_put reason=cache_key_written key_prefix=%s",
                key[:_DIGEST_PREFIX],
            )

        corr = CorrelationKey(
            cache_namespace=namespace,
            agent_id=record.correlation.agent_id,
            tick=record.correlation.tick,
            component=record.component,
            llm_request_id=record.correlation.llm_request_id,
        )
        corr_path = self._corr_path(corr)
        if corr_path.exists():
            existing_corr = corr_path.read_bytes()
            if _payload_digest(existing_corr) != _payload_digest(payload):
                _LOG.warning(
                    "recording_store_put reason=correlation_overwrite "
                    "agent_id=%s tick=%s component=%s",
                    corr.agent_id,
                    corr.tick,
                    corr.component,
                )
        _atomic_write(corr_path, payload)
        _LOG.debug(
            "recording_store_put reason=correlation_written "
            "namespace_prefix=%s",
            _namespace_dir_name(namespace)[:_DIGEST_PREFIX],
        )

    def get_by_cache_key(
        self, cache_key: str, *, cache_namespace: str
    ) -> LLMExchangeRecord | None:
        path = self._key_path(
            cache_namespace=_require_namespace(cache_namespace),
            cache_key=cache_key,
        )
        if not path.exists():
            _LOG.debug(
                "recording_store_get reason=cache_key_miss key_prefix=%s",
                cache_key[:_DIGEST_PREFIX],
            )
            return None
        return self._load(path, reason_prefix="cache_key")

    def get_by_correlation(self, key: CorrelationKey) -> LLMExchangeRecord | None:
        if type(key) is not CorrelationKey:
            raise TypeError("key must be CorrelationKey")
        path = self._corr_path(key)
        if not path.exists():
            _LOG.debug(
                "recording_store_get reason=correlation_miss agent_id=%s tick=%s "
                "component=%s",
                key.agent_id,
                key.tick,
                key.component,
            )
            return None
        return self._load(path, reason_prefix="correlation")

    def _load(self, path: Path, *, reason_prefix: str) -> LLMExchangeRecord:
        try:
            raw = path.read_bytes()
            record = decode_exchange_record_bytes(raw)
        except ValueError:
            _LOG.error(
                "recording_store_get_failed reason=%s_corrupt",
                reason_prefix,
            )
            raise RecordingStoreError("corrupt_or_unknown_schema") from None
        _LOG.debug(
            "recording_store_get reason=%s_hit schema_digest_prefix=%s",
            reason_prefix,
            record.schema_identity.digest[:_DIGEST_PREFIX],
        )
        return record

    def count(self) -> int:
        total = 0
        keys_root = self._root / "ns"
        if not keys_root.exists():
            return 0
        for path in keys_root.glob("*/keys/*.json"):
            if path.is_file():
                total += 1
        return total

    def list_cache_keys(self, *, cache_namespace: str) -> tuple[str, ...]:
        directory = self._ns_root(cache_namespace) / "keys"
        if not directory.exists():
            return ()
        keys: list[str] = []
        for path in sorted(directory.glob("*.json")):
            stem = path.stem
            if _HEX64_RE.fullmatch(stem) is not None:
                keys.append(stem)
        return tuple(keys)
