"""Canonical DTO codecs for optional evidence spooling.

The spool port stores bytes only. This module owns the experiment/simulation
typed payload boundary: each decoded value is reconstructed through its normal
constructor, so existing scope, ordering, and conflict validation still apply.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import types
import typing
from collections.abc import Mapping, Sequence
from typing import Any, Final

from simulation.civilization_boundaries import CivilizationBoundaryInput
from simulation.civilization_capture import CivilizationEventBatch
from simulation.cultural_evidence import (
    CulturalBoundaryExport,
    CulturalChannelExport,
    cultural_ledger_type,
)

__all__ = [
    "EvidenceCodecError",
    "decode_civilization_boundary",
    "decode_civilization_event_batch",
    "decode_cultural_boundary",
    "encode_civilization_boundary",
    "encode_civilization_event_batch",
    "encode_cultural_boundary",
]

_MAX_PAYLOAD_BYTES: Final[int] = 64 * 1024 * 1024


class EvidenceCodecError(ValueError):
    """Payload-free codec failure with a stable safe code."""

    def __init__(self, code: str = "evidence_codec_invalid") -> None:
        self.code = code
        super().__init__(code)


def _plain(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        instance = typing.cast(Any, value)
        return {
            field.name: _plain(getattr(instance, field.name))
            for field in dataclasses.fields(instance)
        }
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(item) for item in value), key=repr)
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(
        _plain(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _loads(data: bytes) -> object:
    if not isinstance(data, bytes) or len(data) > _MAX_PAYLOAD_BYTES:
        raise EvidenceCodecError("evidence_codec_too_large")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise EvidenceCodecError("evidence_codec_invalid") from exc


def _matches(decoded: object, raw: object) -> bool:
    try:
        return _plain(decoded) == raw
    except Exception:
        return False


def _decode_union(args: tuple[Any, ...], value: object) -> object:
    if value is None and type(None) in args:
        return None
    matches: list[object] = []
    for candidate in args:
        if candidate is type(None):
            continue
        try:
            decoded = _decode_typed(candidate, value)
        except (TypeError, ValueError, KeyError):
            continue
        if _matches(decoded, value):
            matches.append(decoded)
    if len(matches) == 1:
        return matches[0]
    if matches:
        return matches[0]
    raise EvidenceCodecError("evidence_codec_invalid")


def _decode_typed(expected: object, value: object) -> object:
    if isinstance(expected, typing.TypeAliasType):
        return _decode_typed(expected.__value__, value)
    origin = typing.get_origin(expected)
    args = typing.get_args(expected)
    if origin in (typing.Union, types.UnionType):
        return _decode_union(args, value)
    if origin is typing.Literal:
        if value in args:
            return value
        raise EvidenceCodecError("evidence_codec_invalid")
    if origin is tuple:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise EvidenceCodecError("evidence_codec_invalid")
        if not args:
            return tuple(value)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode_typed(args[0], item) for item in value)
        if len(args) != len(value):
            raise EvidenceCodecError("evidence_codec_invalid")
        return tuple(
            _decode_typed(item_type, item)
            for item_type, item in zip(args, value, strict=True)
        )
    if origin in (list, set, frozenset):
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise EvidenceCodecError("evidence_codec_invalid")
        items = (
            tuple(_decode_typed(args[0], item) for item in value)
            if args
            else tuple(value)
        )
        if origin is list:
            return list(items)
        return origin(items)
    if origin in (dict, Mapping):
        if not isinstance(value, Mapping):
            raise EvidenceCodecError("evidence_codec_invalid")
        key_type, value_type = args if len(args) == 2 else (str, object)
        return {
            _decode_typed(key_type, key): _decode_typed(value_type, item)
            for key, item in value.items()
        }
    if origin in (Sequence,):
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise EvidenceCodecError("evidence_codec_invalid")
        return tuple(
            _decode_typed(args[0], item) for item in value
        ) if args else tuple(value)
    if isinstance(expected, type) and issubclass(expected, enum.Enum):
        return expected(value)
    if isinstance(expected, type) and dataclasses.is_dataclass(expected):
        return _decode_dataclass(expected, value)
    if expected is Any or expected is object:
        return value
    return value


def _decode_dataclass(cls: type[object], value: object) -> object:
    if not isinstance(value, Mapping):
        raise EvidenceCodecError("evidence_codec_invalid")
    hints = typing.get_type_hints(cls)
    kwargs: dict[str, object] = {}
    for field in dataclasses.fields(typing.cast(Any, cls)):
        if field.name not in value:
            raise EvidenceCodecError("evidence_codec_invalid")
        raw = value[field.name]
        if cls is CulturalChannelExport and field.name == "ledger":
            if raw is None:
                kwargs[field.name] = None
                continue
            channel = value.get("channel")
            if not isinstance(channel, str):
                raise EvidenceCodecError("evidence_codec_invalid")
            ledger_type = cultural_ledger_type(channel)
            kwargs[field.name] = _decode_dataclass(ledger_type, raw)
            continue
        kwargs[field.name] = _decode_typed(
            hints.get(field.name, object), raw
        )
    return cls(**kwargs)


def _encode(value: object) -> bytes:
    try:
        return _canonical(value)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceCodecError("evidence_codec_invalid") from exc


def _decode(data: bytes, expected: type[object]) -> object:
    raw = _loads(data)
    decoded = _decode_dataclass(expected, raw)
    if _canonical(decoded) != data:
        raise EvidenceCodecError("evidence_codec_nonisomorphic")
    return decoded


def encode_cultural_boundary(frame: CulturalBoundaryExport) -> bytes:
    if type(frame) is not CulturalBoundaryExport:
        raise EvidenceCodecError("evidence_codec_invalid")
    return _encode(frame)


def decode_cultural_boundary(data: bytes) -> CulturalBoundaryExport:
    value = _decode(data, CulturalBoundaryExport)
    if type(value) is not CulturalBoundaryExport:
        raise EvidenceCodecError("evidence_codec_invalid")
    return value


def encode_civilization_boundary(boundary: CivilizationBoundaryInput) -> bytes:
    if type(boundary) is not CivilizationBoundaryInput:
        raise EvidenceCodecError("evidence_codec_invalid")
    return _encode(boundary)


def decode_civilization_boundary(data: bytes) -> CivilizationBoundaryInput:
    value = _decode(data, CivilizationBoundaryInput)
    if type(value) is not CivilizationBoundaryInput:
        raise EvidenceCodecError("evidence_codec_invalid")
    return value


def encode_civilization_event_batch(batch: CivilizationEventBatch) -> bytes:
    if type(batch) is not CivilizationEventBatch:
        raise EvidenceCodecError("evidence_codec_invalid")
    return _encode(batch)


def decode_civilization_event_batch(data: bytes) -> CivilizationEventBatch:
    value = _decode(data, CivilizationEventBatch)
    if type(value) is not CivilizationEventBatch:
        raise EvidenceCodecError("evidence_codec_invalid")
    return value
