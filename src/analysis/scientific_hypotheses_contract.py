"""Closed detached vocabulary for scientific-hypothesis analysis.

The surface represents an owner's explicitly testable hypothesis as it was
formulated, revised, and tested. It never exposes an objective experiment rule:
law rows, engine probabilities, deltas, product identifiers, harm bands, truth,
verification, accuracy, calibration, or a composite scientific score have no
place in this contract.

Stable error codes (``ScientificHypothesesError.reason_code``):

- ``scientific_hypotheses_invalid_policy``
- ``scientific_hypotheses_invalid_cap``
- ``scientific_hypotheses_invalid_hypothesis``
- ``scientific_hypotheses_invalid_condition``
- ``scientific_hypotheses_invalid_revision``
- ``scientific_hypotheses_invalid_trial``
- ``scientific_hypotheses_unstable_token``
- ``scientific_hypotheses_forbidden_key``
- ``scientific_hypotheses_layer_violation``
- ``scientific_hypotheses_nonfinite_value``
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from enum import StrEnum
from typing import Final

__all__ = [
    "CLAIM_TOKEN_PREFIX",
    "EVIDENCE_TOKEN_PREFIX",
    "HYPOTHESIS_TOKEN_PREFIX",
    "NONE_TOKEN",
    "OWNER_TOKEN_PREFIX",
    "SCIENTIFIC_HYPOTHESES_ERROR_CODES",
    "SCIENTIFIC_HYPOTHESES_FORBIDDEN_KEYS",
    "SCIENTIFIC_HYPOTHESES_POLICY_VERSION",
    "TOKEN_HEX_LEN",
    "ScientificHypothesesError",
    "ScientificHypothesisAvailability",
    "ScientificHypothesisConditionSlot",
    "ScientificHypothesisCoverage",
    "ScientificHypothesisLayer",
    "ScientificHypothesisRevisionReason",
    "ScientificHypothesisSourceKind",
    "ScientificHypothesisStatus",
    "assert_scientific_hypothesis_layer_separation",
    "mint_claim_token",
    "mint_hypothesis_token",
    "mint_owner_token",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.scientific_hypotheses.contract"
)

SCIENTIFIC_HYPOTHESES_POLICY_VERSION: Final[str] = "scientific-hypotheses.v1"
HYPOTHESIS_TOKEN_PREFIX: Final[str] = "schyp-"
OWNER_TOKEN_PREFIX: Final[str] = "owner-"
CLAIM_TOKEN_PREFIX: Final[str] = "claim-"
EVIDENCE_TOKEN_PREFIX: Final[str] = "evt:"
NONE_TOKEN: Final[str] = "none"
TOKEN_HEX_LEN: Final[int] = 16

_SEPARATOR: Final[str] = "\x1f"


class ScientificHypothesisStatus(StrEnum):
    """Owner-relative hypothesis status; never an objective truth value."""

    PROVISIONAL = "provisional"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class ScientificHypothesisSourceKind(StrEnum):
    """Descriptive provenance of one hypothesis; not a trust level."""

    SELF_FORMULATED = "self_formulated"
    OBSERVED = "observed"
    REMEMBERED = "remembered"
    COMMUNICATED = "communicated"
    RECORDED = "recorded"
    UNKNOWN = "unknown"


class ScientificHypothesisRevisionReason(StrEnum):
    """Closed reasons for one append-only hypothesis revision."""

    FORMULATED = "formulated"
    PREDICTION_REVISED = "prediction_revised"
    CONDITION_REVISED = "condition_revised"
    SUPPORT_ADDED = "support_added"
    CONTRADICTION_ADDED = "contradiction_added"
    CONFIDENCE_REVISED = "confidence_revised"
    SOURCE_ADOPTED = "source_adopted"
    TEST_FORMULATED = "test_formulated"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class ScientificHypothesisConditionSlot(StrEnum):
    """Ten closed observation slots a hypothesis may condition on."""

    LOCATION = "location"
    DAY_PHASE = "day_phase"
    WEATHER = "weather"
    HELD_ITEM_KIND = "held_item_kind"
    COUNTERPART = "counterpart"
    SEASON = "season"
    TEMPERATURE_BAND = "temperature_band"
    HAZARD = "hazard"
    ACTION = "action"
    CONCEPT = "concept"


class ScientificHypothesisLayer(StrEnum):
    """Strictly separated objective, owner, and analytical layers."""

    OBJECTIVE_EVIDENCE = "objective_evidence"
    OWNER_HYPOTHESIS = "owner_hypothesis"
    ANALYTICAL_SUMMARY = "analytical_summary"


class ScientificHypothesisCoverage(StrEnum):
    """Coverage of one bounded evidence or analytical family."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class ScientificHypothesisAvailability(StrEnum):
    """Closed availability of one prediction-outcome family."""

    AVAILABLE = "available"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    UNAVAILABLE = "unavailable"


SCIENTIFIC_HYPOTHESES_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "law",
        "laws",
        "rule",
        "rules",
        "objective_rule",
        "engine_probability",
        "success_probability",
        "probability",
        "delta",
        "product_id",
        "harm_band",
        "truth",
        "verified",
        "proven",
        "proof",
        "score",
        "accuracy",
        "calibration",
        "severity",
        "rank",
        "class",
        "merit",
        "blame",
    }
)

SCIENTIFIC_HYPOTHESES_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "scientific_hypotheses_invalid_policy",
        "scientific_hypotheses_invalid_cap",
        "scientific_hypotheses_invalid_hypothesis",
        "scientific_hypotheses_invalid_condition",
        "scientific_hypotheses_invalid_revision",
        "scientific_hypotheses_invalid_trial",
        "scientific_hypotheses_unstable_token",
        "scientific_hypotheses_forbidden_key",
        "scientific_hypotheses_layer_violation",
        "scientific_hypotheses_nonfinite_value",
    }
)

_OBJECTIVE_FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "hypothesis_token",
        "claim_token",
        "owner_token",
        "causal_hypothesis_token",
        "condition_pairs",
        "predicted_outcome",
        "confidence_milli",
        "status",
        "source_kind",
        "source_token",
    }
)
_ANALYTICAL_FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {"owner_token", "source_token", "event_token", "body_token"}
)
_OWNER_ROW_NAMES: Final[frozenset[str]] = frozenset(
    {"ScientificHypothesisRow", "ScientificRevisionRow"}
)
_OBJECTIVE_ROW_NAMES: Final[frozenset[str]] = frozenset(
    {"ScientificObjectiveEvidenceRow"}
)


class ScientificHypothesesError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "scientific_hypotheses_invalid_hypothesis"
        return str(self.args[0])


def _stable_part(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise ScientificHypothesesError("scientific_hypotheses_unstable_token")
    if len(value) > 128 or value != value.strip():
        raise ScientificHypothesesError("scientific_hypotheses_unstable_token")
    if any(ord(char) < 32 for char in value):
        raise ScientificHypothesesError("scientific_hypotheses_unstable_token")
    return value


def _enum_or_text(name: str, value: object) -> str:
    if isinstance(value, StrEnum):
        return _stable_part(name, value.value)
    return _stable_part(name, value)


def _digest(parts: Sequence[str]) -> str:
    material = _SEPARATOR.join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:TOKEN_HEX_LEN]


def mint_owner_token(owner_token: str) -> str:
    """Mint the stable ``owner-`` analysis token for one owner identity."""

    return f"{OWNER_TOKEN_PREFIX}{_digest((_stable_part('owner_token', owner_token),))}"


def mint_claim_token(
    operator: object,
    operand_a_id: object,
    operand_b_id: object,
    process_token: object,
    predicted_outcome: object,
) -> str:
    """Mint the stable ``claim-`` token over the claim components."""

    parts = (
        _enum_or_text("operator", operator),
        _stable_part("operand_a_id", operand_a_id),
        _stable_part("operand_b_id", operand_b_id),
        _enum_or_text("process_token", process_token),
        _enum_or_text("predicted_outcome", predicted_outcome),
    )
    return f"{CLAIM_TOKEN_PREFIX}{_digest(parts)}"


def mint_hypothesis_token(
    owner_token: str,
    claim_token: str,
    created_tick: int,
) -> str:
    """Mint the stable ``schyp-`` token for one owner-relative hypothesis."""

    if isinstance(created_tick, bool) or type(created_tick) is not int:
        raise ScientificHypothesesError("scientific_hypotheses_unstable_token")
    if created_tick < 0:
        raise ScientificHypothesesError("scientific_hypotheses_unstable_token")
    parts = (
        _stable_part("owner_token", owner_token),
        _stable_part("claim_token", claim_token),
        str(created_tick),
    )
    return f"{HYPOTHESIS_TOKEN_PREFIX}{_digest(parts)}"


def _fields(row: object) -> tuple[str, ...]:
    names = getattr(type(row), "__dataclass_fields__", None)
    if names is None:
        raise ScientificHypothesesError("scientific_hypotheses_layer_violation")
    return tuple(names)


def _forbid_keys(row: object) -> None:
    if set(_fields(row)) & SCIENTIFIC_HYPOTHESES_FORBIDDEN_KEYS:
        _LOG.warning("scientific_hypotheses_forbidden_key")
        raise ScientificHypothesesError("scientific_hypotheses_forbidden_key")


def _row_layer(row: object) -> ScientificHypothesisLayer:
    name = type(row).__name__
    if name in _OBJECTIVE_ROW_NAMES:
        return ScientificHypothesisLayer.OBJECTIVE_EVIDENCE
    if name in _OWNER_ROW_NAMES or name.endswith("Fact"):
        return ScientificHypothesisLayer.OWNER_HYPOTHESIS
    return ScientificHypothesisLayer.ANALYTICAL_SUMMARY


def assert_scientific_hypothesis_layer_separation(
    *groups: Sequence[object],
) -> None:
    """Reject any leak between objective, owner, and analytical layers.

    Every positional group must already be homogeneous. The objective layer may
    not carry owner or claim identities, the analytical layer may not carry
    owner, source, event, or body tokens, and no row may declare a forbidden
    objective-rule, truth, or scoring key.
    """

    for group in groups:
        if isinstance(group, (str, bytes)) or not isinstance(group, Sequence):
            raise ScientificHypothesesError(
                "scientific_hypotheses_layer_violation"
            )
        layers = {_row_layer(row) for row in group}
        if len(layers) > 1:
            _LOG.warning("scientific_hypotheses_layer_violation")
            raise ScientificHypothesesError(
                "scientific_hypotheses_layer_violation"
            )
        for row in group:
            _forbid_keys(row)
            names = set(_fields(row))
            layer = _row_layer(row)
            if layer is ScientificHypothesisLayer.OBJECTIVE_EVIDENCE:
                if names & _OBJECTIVE_FORBIDDEN_FIELDS:
                    _LOG.warning("scientific_hypotheses_layer_violation")
                    raise ScientificHypothesesError(
                        "scientific_hypotheses_layer_violation"
                    )
            elif layer is ScientificHypothesisLayer.ANALYTICAL_SUMMARY:
                if names & _ANALYTICAL_FORBIDDEN_FIELDS:
                    _LOG.warning("scientific_hypotheses_layer_violation")
                    raise ScientificHypothesesError(
                        "scientific_hypotheses_layer_violation"
                    )
