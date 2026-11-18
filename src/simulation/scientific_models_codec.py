"""Strict canonical codec for scientific-model snapshots."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from enum import StrEnum
from typing import Any, Final

from simulation.scientific_models_models import (
    MAX_SCIENTIFIC_MODELS_SNAPSHOT_BYTES,
    ScientificCalibrationRow,
    ScientificComparisonRow,
    ScientificCoverageRow,
    ScientificModelRow,
    ScientificModelsSnapshot,
    ScientificOutcomeRow,
    ScientificPredictionRow,
    ScientificRevisionRow,
)

__all__ = [
    "ScientificModelsError",
    "decode_scientific_models_snapshot",
    "encode_scientific_models_snapshot",
    "scientific_models_snapshot_bytes",
    "scientific_models_snapshot_digest",
]

_CLASSES: Final[dict[str, type[object]]] = {
    cls.__name__: cls
    for cls in (
        ScientificCalibrationRow,
        ScientificComparisonRow,
        ScientificCoverageRow,
        ScientificModelRow,
        ScientificModelsSnapshot,
        ScientificOutcomeRow,
        ScientificPredictionRow,
        ScientificRevisionRow,
    )
}

_SORT_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "models": ("model_token",),
    "predictions": ("prediction_token",),
    "outcomes": ("case_token",),
    "calibration": ("group_token",),
    "revisions": ("model_token", "revision_index"),
    "comparisons": ("group_token",),
    "coverage": ("reason_code", "target_kind"),
}


class ScientificModelsError(ValueError):
    """Safe publication/read error with a closed code."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or not code:
            raise ValueError("scientific_models_invalid_code")
        self.code = code
        super().__init__(code)


def _fail(code: str) -> ScientificModelsError:
    return ScientificModelsError(code)


def _encode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, StrEnum):
        return {"$enum": type(value).__name__, "value": value.value}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        name = type(value).__name__
        if name not in _CLASSES:
            raise _fail("scientific_models_unknown_type")
        return {
            "$type": name,
            **{
                field.name: _encode(getattr(value, field.name))
                for field in dataclasses.fields(value)
            },
        }
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    raise _fail("scientific_models_unsupported")


def _decode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        raise _fail("scientific_models_invalid")
    if "$enum" in value:
        if set(value) != {"$enum", "value"} or type(value["value"]) is not str:
            raise _fail("scientific_models_invalid")
        return value["value"]
    if "$type" in value:
        name = value["$type"]
        if type(name) is not str:
            raise _fail("scientific_models_invalid")
        record_cls = _CLASSES.get(name)
        if record_cls is None:
            raise _fail("scientific_models_unknown_type")
        payload = {key: _decode(item) for key, item in value.items() if key != "$type"}
        try:
            return record_cls(**payload)
        except (TypeError, ValueError) as exc:
            raise _fail("scientific_models_invalid_value") from exc
    raise _fail("scientific_models_invalid")


def _canonical(mapping: object) -> str:
    return json.dumps(
        mapping,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sorted_snapshot(snapshot: ScientificModelsSnapshot) -> ScientificModelsSnapshot:
    return ScientificModelsSnapshot(
        schema_version=snapshot.schema_version,
        policy_version=snapshot.policy_version,
        run_token=snapshot.run_token,
        publication_id=snapshot.publication_id,
        finalized_through_tick=snapshot.finalized_through_tick,
        coverage_status=snapshot.coverage_status,
        models=tuple(sorted(snapshot.models, key=lambda row: row.model_token)),
        predictions=tuple(
            sorted(snapshot.predictions, key=lambda row: row.prediction_token)
        ),
        outcomes=tuple(sorted(snapshot.outcomes, key=lambda row: row.case_token)),
        calibration=tuple(
            sorted(snapshot.calibration, key=lambda row: row.group_token)
        ),
        revisions=tuple(
            sorted(
                snapshot.revisions,
                key=lambda row: (row.model_token, row.revision_index),
            )
        ),
        comparisons=tuple(
            sorted(snapshot.comparisons, key=lambda row: row.group_token)
        ),
        coverage=tuple(
            sorted(
                snapshot.coverage,
                key=lambda row: (row.reason_code, row.target_kind),
            )
        ),
        notices=snapshot.notices,
    )


def encode_scientific_models_snapshot(
    snapshot: ScientificModelsSnapshot,
) -> dict[str, Any]:
    if type(snapshot) is not ScientificModelsSnapshot:
        raise _fail("scientific_models_invalid_snapshot")
    canonical = _sorted_snapshot(snapshot)
    payload = {
        "codec_version": canonical.schema_version,
        "snapshot": _encode(canonical),
    }
    if len(_canonical(payload).encode("utf-8")) > MAX_SCIENTIFIC_MODELS_SNAPSHOT_BYTES:
        raise _fail("scientific_models_snapshot_too_large")
    return payload


def scientific_models_snapshot_bytes(
    snapshot: ScientificModelsSnapshot,
) -> bytes:
    return _canonical(encode_scientific_models_snapshot(snapshot)).encode("ascii")


def decode_scientific_models_snapshot(
    payload: object,
) -> ScientificModelsSnapshot:
    if not isinstance(payload, dict) or set(payload) != {"codec_version", "snapshot"}:
        raise _fail("scientific_models_invalid_envelope")
    if payload["codec_version"] != "scientific-models-snapshot-v1":
        raise _fail("scientific_models_unsupported_version")
    snapshot = _decode(payload["snapshot"])
    if type(snapshot) is not ScientificModelsSnapshot:
        raise _fail("scientific_models_invalid_snapshot")
    canonical = _canonical(encode_scientific_models_snapshot(snapshot))
    if len(canonical.encode("utf-8")) > MAX_SCIENTIFIC_MODELS_SNAPSHOT_BYTES:
        raise _fail("scientific_models_snapshot_too_large")
    return snapshot


def scientific_models_snapshot_digest(snapshot: ScientificModelsSnapshot) -> str:
    return hashlib.sha256(scientific_models_snapshot_bytes(snapshot)).hexdigest()
