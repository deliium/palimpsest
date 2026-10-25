"""Strict canonical encoding for the closed civilization contract vocabulary.

Storage encoding is independent of legacy observer/lineage protocols. Child
documents do not receive their own hash or their parent's hash from this codec.
HTTP serializers must explicitly select their independent envelope schemas.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import types
from dataclasses import fields, is_dataclass
from enum import StrEnum
from functools import cache, lru_cache
from typing import (
    Literal,
    TypeAliasType,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from simulation import civilization_models as models
from simulation import civilization_rows as rows
from simulation.civilization_models import CivilizationError, _count, _id

__all__ = [
    "civilization_digest",
    "decode_civilization_value",
    "encode_civilization_value",
    "validate_civilization_value",
]

_LOG = logging.getLogger(__name__)
MAX_ROW_BYTES = 64 * 1024
MAX_JSON_DEPTH = 32


@lru_cache(maxsize=1)
def _contracts() -> dict[str, type]:
    from simulation import civilization_ports as ports

    return {
        name: value
        for module in (models, rows, ports)
        for name in module.__all__
        if isinstance(value := getattr(module, name), type) and is_dataclass(value)
    }


@cache
def _hints(cls: type) -> dict[str, object]:
    return get_type_hints(cls)


def _primitive(value: object, expected: object) -> object:
    if expected is str:
        return _id(value)
    if expected is int:
        return _count(value)
    if expected is float:
        if type(value) not in (int, float):
            raise CivilizationError()
        number = float(cast(int | float, value))
        if not math.isfinite(number) or number < 0:
            raise CivilizationError()
        return number
    if expected is bool and type(value) is bool:
        return value
    if expected is type(None) and value is None:
        return None
    raise CivilizationError()


def _typed(value: object, expected: object, *, decoding: bool, depth: int) -> object:
    if depth > MAX_JSON_DEPTH:
        raise CivilizationError()
    if isinstance(expected, TypeAliasType):
        return _typed(value, expected.__value__, decoding=decoding, depth=depth + 1)
    origin = get_origin(expected)
    args = get_args(expected)
    if origin in (types.UnionType, Union):
        for choice in args:
            try:
                return _typed(value, choice, decoding=decoding, depth=depth + 1)
            except CivilizationError:
                continue
        raise CivilizationError()
    if origin is Literal:
        if not any(type(value) is type(choice) and value == choice for choice in args):
            raise CivilizationError()
        return value
    if origin is tuple:
        if not isinstance(value, (tuple, list)) or len(value) > 200:
            raise CivilizationError()
        return tuple(
            _typed(item, args[0], decoding=decoding, depth=depth + 1) for item in value
        )
    if isinstance(expected, type) and issubclass(expected, StrEnum):
        if type(value) is expected:
            return value
        if decoding and type(value) is str:
            try:
                return expected(value)
            except ValueError:
                pass
        raise CivilizationError()
    if isinstance(expected, type) and is_dataclass(expected):
        if decoding:
            if type(value) is not dict or value.get("$type") != expected.__name__:
                raise CivilizationError()
            return _decode_dataclass(value, expected, depth=depth + 1)
        if type(value) is not expected:
            raise CivilizationError()
        return value
    return _primitive(value, expected)


def validate_civilization_value(value: object) -> None:
    """Validate and detach only declared row fields, including nested detail caps."""
    if type(value).__name__ not in _contracts() or not is_dataclass(value):
        raise CivilizationError()
    for field in fields(value):
        normalized = _typed(
            getattr(value, field.name),
            _hints(cast(type, type(value)))[field.name],
            decoding=False,
            depth=0,
        )
        object.__setattr__(value, field.name, normalized)
        if isinstance(normalized, tuple):
            if len(set(normalized)) != len(normalized):
                raise CivilizationError()
            cap = 32 if field.name in {"source_refs", "anchors"} else 64
            if field.name in {"rows", "boundaries", "children", "scopes"}:
                cap = 200
            if len(normalized) > cap:
                raise CivilizationError()
    rows._require_row_semantics(value)


def _document(value: object, depth: int = 0) -> object:
    if depth > MAX_JSON_DEPTH:
        raise CivilizationError()
    if is_dataclass(value) and not isinstance(value, type):
        if _contracts().get(type(value).__name__) is not type(value):
            raise CivilizationError()
        return {
            "$type": type(value).__name__,
            **{
                field.name: _document(getattr(value, field.name), depth + 1)
                for field in fields(value)
            },
        }
    if isinstance(value, StrEnum):
        return value.value
    if type(value) is tuple:
        return [_document(item, depth + 1) for item in value]
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise CivilizationError()


def encode_civilization_value(value: object) -> bytes:
    """Canonical sorted compact UTF-8, ending with exactly one LF."""
    try:
        encoded = (
            json.dumps(
                _document(value),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise CivilizationError() from None
    if len(encoded) > MAX_ROW_BYTES:
        raise CivilizationError("civilization_row_too_large")
    _LOG.debug("civilization_encoded byte_count=%s", len(encoded))
    return encoded


def civilization_digest(canonical_bytes: bytes) -> str:
    """Hash child bytes before constructing parents; never inject a digest."""
    if type(canonical_bytes) is not bytes:
        raise CivilizationError()
    return hashlib.sha256(canonical_bytes).hexdigest()


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CivilizationError()
        result[key] = value
    return result


def _decode_dataclass(document: dict[str, object], cls: type, *, depth: int) -> object:
    names = {field.name for field in fields(cls)}
    if set(document) != names | {"$type"}:
        raise CivilizationError()
    kwargs = {
        name: _typed(document[name], _hints(cls)[name], decoding=True, depth=depth)
        for name in names
    }
    try:
        return cls(**kwargs)
    except (TypeError, ValueError):
        raise CivilizationError() from None


def decode_civilization_value(encoded: bytes) -> object:
    """Reject unknown/duplicate fields, coercions, nonfinite and oversized input."""
    if type(encoded) is not bytes or len(encoded) > MAX_ROW_BYTES:
        raise CivilizationError("civilization_row_too_large")
    try:
        document = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(CivilizationError()),
        )
        if type(document) is not dict:
            raise CivilizationError()
        tag = document.get("$type")
        if type(tag) is not str or tag not in _contracts():
            raise CivilizationError()
        result = _decode_dataclass(document, _contracts()[tag], depth=0)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise CivilizationError() from None
    _LOG.debug("civilization_decoded byte_count=%s", len(encoded))
    return result
