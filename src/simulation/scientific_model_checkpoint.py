"""Strict owner-safe checkpoint codec for ``scientific-model-state-v1``."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from enum import StrEnum
from typing import Any, Final

from agents.cognition.scientific_models import (
    CalibrationBin,
    DerivationSample,
    EmpiricalContextBin,
    ForecastCase,
    ForecastCaseState,
    ModelComparison,
    ModelComparisonStatus,
    ModelCondition,
    ModelCoverageNotice,
    ModelExecutionBinding,
    ModelExecutionComparability,
    ModelHypothesis,
    ModelHypothesisRevision,
    ModelLifecycle,
    ModelObservedOutcome,
    ModelOutcomeChannel,
    ModelPerformanceSummary,
    ModelPrediction,
    ModelPredictorVariant,
    ModelRevision,
    ModelRevisionReason,
    ModelSourceClaim,
    ModelSourceKind,
    ModelTargetKind,
    PredictiveModel,
    ScientificModelLedger,
)
from world.environment import Season
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import AgentId

__all__ = [
    "SCIENTIFIC_MODEL_STATE_VERSION",
    "ScientificModelCheckpointError",
    "decode_scientific_model_state",
    "encode_scientific_model_state",
    "scientific_model_state_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.scientific_model_checkpoint"
)

SCIENTIFIC_MODEL_STATE_VERSION: Final[str] = "scientific-model-state-v1"

_DATACLASSES: Final[dict[str, type[object]]] = {
    cls.__name__: cls
    for cls in (
        AgentId,
        CalibrationBin,
        DerivationSample,
        EmpiricalContextBin,
        ForecastCase,
        ModelComparison,
        ModelCondition,
        ModelCoverageNotice,
        ModelExecutionBinding,
        ModelHypothesis,
        ModelHypothesisRevision,
        ModelObservedOutcome,
        ModelPerformanceSummary,
        ModelPrediction,
        ModelRevision,
        ModelSourceClaim,
        PredictiveModel,
        ScientificModelLedger,
    )
}

_ENUMS: Final[dict[str, type[StrEnum]]] = {
    cls.__name__: cls
    for cls in (
        ForecastCaseState,
        ModelComparisonStatus,
        ModelExecutionComparability,
        ModelLifecycle,
        ModelOutcomeChannel,
        ModelPredictorVariant,
        ModelRevisionReason,
        ModelSourceKind,
        ModelTargetKind,
        ExperimentOperator,
        ExperimentOutcomeClass,
        ExperimentProcessToken,
        Season,
    )
}


class ScientificModelCheckpointError(ValueError):
    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> ScientificModelCheckpointError:
    return ScientificModelCheckpointError(code)


def _encode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, StrEnum):
        return {"$enum": type(value).__name__, "value": value.value}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        name = type(value).__name__
        if name not in _DATACLASSES:
            raise _fail("scientific_model_state_unknown_type")
        return {
            "$type": name,
            **{
                field.name: _encode(getattr(value, field.name))
                for field in dataclasses.fields(value)
            },
        }
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    raise _fail("scientific_model_state_unsupported")


def _decode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        raise _fail("scientific_model_state_invalid")
    if "$enum" in value:
        if set(value) != {"$enum", "value"}:
            raise _fail("scientific_model_state_invalid")
        name = value["$enum"]
        token = value["value"]
        if type(name) is not str or type(token) is not str:
            raise _fail("scientific_model_state_invalid")
        enum_cls = _ENUMS.get(name)
        if enum_cls is None:
            raise _fail("scientific_model_state_unknown_enum")
        try:
            return enum_cls(token)
        except ValueError as exc:
            raise _fail("scientific_model_state_invalid_enum") from exc
    if "$type" in value:
        name = value["$type"]
        if type(name) is not str:
            raise _fail("scientific_model_state_invalid")
        record_cls = _DATACLASSES.get(name)
        if record_cls is None:
            raise _fail("scientific_model_state_unknown_type")
        payload = {
            key: _decode(item) for key, item in value.items() if key != "$type"
        }
        try:
            return record_cls(**payload)
        except (TypeError, ValueError) as exc:
            raise _fail("scientific_model_state_invalid_value") from exc
    raise _fail("scientific_model_state_invalid")


def _canonical(mapping: object) -> str:
    return json.dumps(
        mapping,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _validate_closure(ledger: ScientificModelLedger) -> None:
    """A retained forecast must pin revisions that still exist."""

    hypotheses = {row.hypothesis_id: row for row in ledger.hypotheses}
    models = {row.model_id: row for row in ledger.models}
    for model in ledger.models:
        if model.hypothesis_id not in hypotheses:
            raise _fail("scientific_model_revision_missing")
        source = model.source_revision_ref
        if "#" not in source:
            raise _fail("scientific_model_state_invalid")
        hypothesis_id, _, index_text = source.rpartition("#")
        hypothesis = hypotheses.get(hypothesis_id)
        if hypothesis is None:
            raise _fail("scientific_model_revision_missing")
        try:
            index = int(index_text)
        except ValueError as exc:
            raise _fail("scientific_model_state_invalid") from exc
        if index >= len(hypothesis.revisions):
            raise _fail("scientific_model_revision_missing")
    for case in ledger.cases:
        for prediction in case.predictions:
            case_model = models.get(prediction.model_id)
            if case_model is None:
                raise _fail("scientific_model_revision_missing")
            source = prediction.source_revision_ref
            if "#" not in source:
                raise _fail("scientific_model_state_invalid")
            hypothesis_id, _, index_text = source.rpartition("#")
            hypothesis = hypotheses.get(hypothesis_id)
            if hypothesis is None:
                raise _fail("scientific_model_revision_missing")
            try:
                index = int(index_text)
            except ValueError as exc:
                raise _fail("scientific_model_state_invalid") from exc
            if index >= len(hypothesis.revisions):
                raise _fail("scientific_model_revision_missing")
            revision_ref = prediction.model_revision_ref
            if "#" not in revision_ref:
                raise _fail("scientific_model_state_invalid")
            model_id, _, revision_text = revision_ref.rpartition("#")
            try:
                revision_index = int(revision_text)
            except ValueError as exc:
                raise _fail("scientific_model_state_invalid") from exc
            if model_id != case_model.model_id or revision_index >= len(
                case_model.revisions
            ):
                raise _fail("scientific_model_revision_missing")


def encode_scientific_model_state(ledger: ScientificModelLedger) -> dict[str, Any]:
    if type(ledger) is not ScientificModelLedger:
        raise _fail("scientific_model_state_invalid_ledger")
    _validate_closure(ledger)
    return {
        "codec_version": SCIENTIFIC_MODEL_STATE_VERSION,
        "owner_id": ledger.owner_id.value,
        "policy_version": ledger.policy_version,
        "ledger": _encode(ledger),
    }


def decode_scientific_model_state(
    payload: object, owner_id: AgentId
) -> ScientificModelLedger:
    if not isinstance(payload, dict) or set(payload) != {
        "codec_version",
        "owner_id",
        "policy_version",
        "ledger",
    }:
        raise _fail("scientific_model_state_invalid")
    if payload["codec_version"] != SCIENTIFIC_MODEL_STATE_VERSION:
        raise _fail("scientific_model_state_unsupported_version")
    if payload["owner_id"] != owner_id.value:
        raise _fail("scientific_model_owner_mismatch")
    ledger = _decode(payload["ledger"])
    if type(ledger) is not ScientificModelLedger or ledger.owner_id != owner_id:
        raise _fail("scientific_model_state_invalid_ledger")
    if payload["policy_version"] != ledger.policy_version:
        raise _fail("scientific_model_state_policy_mismatch")
    _validate_closure(ledger)
    return ledger


def scientific_model_state_digest(ledger: ScientificModelLedger) -> str:
    material = _canonical(encode_scientific_model_state(ledger)).encode("ascii")
    return hashlib.sha256(material).hexdigest()
