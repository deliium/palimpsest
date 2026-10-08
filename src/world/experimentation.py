"""Public experiment enums. Law rows stay in ``world._experiment_laws``."""

from __future__ import annotations

from enum import StrEnum


class ExperimentOperator(StrEnum):
    COMBINE = "combine"
    APPLY_TOOL = "apply_tool"
    VARY_PROCESS = "vary_process"


class ExperimentOutcomeClass(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    HARM = "harm"
    UNEXPECTED = "unexpected"


class ExperimentProcessToken(StrEnum):
    HARVEST = "harvest"
    CRAFT = "craft"
    BUILD = "build"
    REPAIR = "repair"
    STORE = "store"
    NONE = "none"


class ExperimentDeltaKind(StrEnum):
    NONE = "none"
    CONSUME_OPERAND = "consume_operand"
    EMIT_CATALOG_PRODUCT = "emit_catalog_product"
    PARTIAL_EMIT = "partial_emit"
    APPLY_HARM_BAND = "apply_harm_band"


class ExperimentHarmBand(StrEnum):
    NONE = "none"
    MINOR = "minor"
    SERIOUS = "serious"


class DiscoveryMode(StrEnum):
    DELIBERATE = "deliberate"
    ACCIDENTAL = "accidental"
