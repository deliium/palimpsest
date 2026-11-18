"""Owner-scoped measurement evidence and fallible reliability beliefs."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from typing import Final, Literal

from agents.models import AgentId
from world.identifiers import EntityId
from world.measurement import (
    MEASUREMENT_CATEGORY_VALUES,
    MeasurementQuantity,
    MeasurementUnit,
)

__all__ = [
    "MEASUREMENT_BELIEF_POLICY_VERSION",
    "InstrumentReliabilityBelief",
    "MeasurementBeliefRevision",
    "MeasurementEvidence",
    "MeasurementLedger",
    "compare_measurement_evidence",
    "empty_measurement_ledger",
    "ingest_measurement_observations",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.measurement")

MEASUREMENT_BELIEF_POLICY_VERSION: Final[str] = "measurement-beliefs.v1"
MAX_EVIDENCE_ROWS: Final[int] = 128
MAX_BELIEFS: Final[int] = 64
MAX_REVISIONS: Final[int] = 512
MAX_ROOT_RECEIPTS: Final[int] = 1024
_MAX_CONFIDENCE: Final[int] = 950
_MIN_CONFIDENCE: Final[int] = 50
_INITIAL_CONFIDENCE: Final[int] = 500


def _flag(name: str) -> bool:
    raise TypeError(f"{name} must be bool")


@dataclass(frozen=True, slots=True)
class MeasurementEvidence:
    """One display the owner acquired, with its actual basis."""

    evidence_id: str
    owner_id: AgentId
    instrument_id: EntityId
    target_id: EntityId
    quantity: MeasurementQuantity
    unit: MeasurementUnit
    value_kind: Literal["scalar", "category"]
    displayed_scalar_milli: int | None
    displayed_category: str | None
    nominal_division_milli: int
    observed_tick: int
    source_kind: Literal["own_observation", "communicated"]
    source_event_id: str
    delivery_event_id: str | None
    declared_root: str
    condition_tokens: tuple[str, ...] = ()
    speaker_confidence_milli: int | None = None
    observed_wear: str | None = None
    adjustment_mark_present: bool | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("owner_id must be AgentId")
        if type(self.instrument_id) is not EntityId:
            raise TypeError("instrument_id must be EntityId")
        if type(self.target_id) is not EntityId:
            raise TypeError("target_id must be EntityId")
        if type(self.quantity) is not MeasurementQuantity:
            raise TypeError("quantity must be MeasurementQuantity")
        if type(self.unit) is not MeasurementUnit:
            raise TypeError("unit must be MeasurementUnit")
        if self.value_kind not in {"scalar", "category"}:
            raise ValueError("invalid_value_kind")
        if self.value_kind == "scalar":
            if (
                isinstance(self.displayed_scalar_milli, bool)
                or type(self.displayed_scalar_milli) is not int
                or self.displayed_category is not None
            ):
                raise ValueError("invalid_display")
        elif (
            self.displayed_category not in MEASUREMENT_CATEGORY_VALUES
            or self.displayed_scalar_milli is not None
        ):
            raise ValueError("invalid_display")
        for name in ("nominal_division_milli", "observed_tick"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise ValueError(f"invalid_{name}")
        if self.nominal_division_milli < 1:
            raise ValueError("invalid_nominal_division_milli")
        if self.source_kind not in {"own_observation", "communicated"}:
            raise ValueError("invalid_source_kind")
        if self.source_kind == "own_observation":
            if self.delivery_event_id is not None:
                raise ValueError("own_observation_must_not_have_delivery")
        elif self.delivery_event_id is None:
            raise ValueError("communicated_requires_delivery")
        if self.speaker_confidence_milli is not None and (
            isinstance(self.speaker_confidence_milli, bool)
            or type(self.speaker_confidence_milli) is not int
            or not 0 <= self.speaker_confidence_milli <= 1000
        ):
            raise ValueError("invalid_speaker_confidence")
        if not self.evidence_id or len(self.evidence_id) > 128:
            raise ValueError("invalid_evidence_id")
        if not self.source_event_id or len(self.source_event_id) > 128:
            raise ValueError("invalid_source_event_id")
        if not self.declared_root or len(self.declared_root) > 128:
            raise ValueError("invalid_declared_root")
        if isinstance(self.condition_tokens, (str, bytes)) or not isinstance(
            self.condition_tokens, tuple
        ):
            raise TypeError("condition_tokens must be tuple")
        if len(self.condition_tokens) > 16 or any(
            type(token) is not str or not token for token in self.condition_tokens
        ):
            raise ValueError("invalid_condition_tokens")
        if self.observed_wear not in {
            None,
            "intact",
            "worn",
            "damaged",
            "broken",
        }:
            raise ValueError("invalid_observed_wear")
        if self.adjustment_mark_present is not None and type(
            self.adjustment_mark_present
        ) is not bool:
            raise TypeError("adjustment_mark_present must be bool or None")


@dataclass(frozen=True, slots=True)
class InstrumentReliabilityBelief:
    """The owner's revisable appraisal. Never objective instrument truth."""

    instrument_id: EntityId
    quantity: MeasurementQuantity
    unit: MeasurementUnit
    expected_resolution_milli: int
    estimated_error_band_milli: int | None
    confidence_milli: int
    observed_wear: str
    adjustment_mark_present: bool
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.instrument_id) is not EntityId:
            raise TypeError("instrument_id must be EntityId")
        if type(self.quantity) is not MeasurementQuantity:
            raise TypeError("quantity must be MeasurementQuantity")
        if type(self.unit) is not MeasurementUnit:
            raise TypeError("unit must be MeasurementUnit")
        for name in ("expected_resolution_milli", "confidence_milli"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int:
                raise ValueError(f"invalid_{name}")
        if self.expected_resolution_milli < 1:
            raise ValueError("invalid_expected_resolution_milli")
        if not 0 <= self.confidence_milli <= 1000:
            raise ValueError("invalid_confidence_milli")
        if self.estimated_error_band_milli is not None and (
            isinstance(self.estimated_error_band_milli, bool)
            or type(self.estimated_error_band_milli) is not int
            or self.estimated_error_band_milli < 0
        ):
            raise ValueError("invalid_error_band")
        if type(self.adjustment_mark_present) is not bool:
            raise TypeError("adjustment_mark_present must be bool")
        if self.observed_wear not in {"intact", "worn", "damaged", "broken"}:
            raise ValueError("invalid_observed_wear")


@dataclass(frozen=True, slots=True)
class MeasurementBeliefRevision:
    """Append-only record of one appraisal change."""

    revision_id: str
    instrument_id: EntityId
    quantity: MeasurementQuantity
    observed_tick: int
    previous_confidence_milli: int
    new_confidence_milli: int
    evidence_id: str
    agreement: Literal["agreement", "disagreement", "initial", "no_comparison"]

    def __post_init__(self) -> None:
        if type(self.instrument_id) is not EntityId:
            raise TypeError("instrument_id must be EntityId")
        if type(self.quantity) is not MeasurementQuantity:
            raise TypeError("quantity must be MeasurementQuantity")
        if self.agreement not in {
            "agreement",
            "disagreement",
            "initial",
            "no_comparison",
        }:
            raise ValueError("invalid_agreement")
        for name in (
            "observed_tick",
            "previous_confidence_milli",
            "new_confidence_milli",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int:
                raise ValueError(f"invalid_{name}")
        if not 0 <= self.new_confidence_milli <= 1000:
            raise ValueError("invalid_new_confidence_milli")


@dataclass(frozen=True, slots=True)
class MeasurementLedger:
    """Bounded owner-local evidence, beliefs, revisions and receipts."""

    owner_id: AgentId
    policy_version: str = MEASUREMENT_BELIEF_POLICY_VERSION
    evidence: tuple[MeasurementEvidence, ...] = ()
    beliefs: tuple[InstrumentReliabilityBelief, ...] = ()
    revisions: tuple[MeasurementBeliefRevision, ...] = ()
    receipts: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("owner_id must be AgentId")
        if self.policy_version != MEASUREMENT_BELIEF_POLICY_VERSION:
            raise ValueError("unsupported_measurement_belief_policy")
        for name in ("evidence", "beliefs", "revisions", "receipts", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise TypeError(f"{name} must be tuple")
        if len(self.evidence) > MAX_EVIDENCE_ROWS:
            raise ValueError("evidence_cap_exceeded")
        if len(self.beliefs) > MAX_BELIEFS:
            raise ValueError("belief_cap_exceeded")
        if len(self.revisions) > MAX_REVISIONS:
            raise ValueError("revision_cap_exceeded")
        if len(self.receipts) > MAX_ROOT_RECEIPTS:
            raise ValueError("receipt_cap_exceeded")
        if any(row.owner_id != self.owner_id for row in self.evidence):
            raise ValueError("evidence_owner_mismatch")
        evidence_ids = {row.evidence_id for row in self.evidence}
        if len(evidence_ids) != len(self.evidence):
            raise ValueError("duplicate_evidence")
        receipt_set = set(self.receipts)
        if len(receipt_set) != len(self.receipts):
            raise ValueError("duplicate_receipt")


def empty_measurement_ledger(owner_id: AgentId) -> MeasurementLedger:
    return MeasurementLedger(owner_id=owner_id)


def _owner_conditions(observation: object) -> tuple[str, ...]:
    tokens: list[str] = []
    for name in ("day_phase", "weather_condition", "season", "temperature_band"):
        value = getattr(observation, name, None)
        if value is None:
            continue
        token = getattr(value, "value", value)
        if isinstance(token, str):
            tokens.append(f"{name}:{token}")
    visibility = getattr(observation, "visibility", None)
    if isinstance(visibility, (int, float)) and not isinstance(visibility, bool):
        if visibility < 0.34:
            tokens.append("visibility:low")
        elif visibility < 0.67:
            tokens.append("visibility:medium")
        else:
            tokens.append("visibility:high")
    return tuple(sorted(tokens))


def _receipt_key(evidence: MeasurementEvidence) -> str:
    if evidence.source_kind == "own_observation":
        return f"own:{evidence.source_event_id}"
    return (
        f"communicated:{evidence.delivery_event_id}:"
        f"{evidence.declared_root}"
    )


def _evidence_id(owner_id: AgentId, receipt: str) -> str:
    digest = hashlib.sha256(
        f"{owner_id.value}|{receipt}".encode()
    ).hexdigest()
    return f"mev:{digest[:32]}"


def _belief_key(belief: InstrumentReliabilityBelief) -> tuple[str, str]:
    return belief.instrument_id.value, belief.quantity.value


def _latest_prior(
    ledger: MeasurementLedger, evidence: MeasurementEvidence
) -> MeasurementEvidence | None:
    candidates = [
        row
        for row in ledger.evidence
        if row.source_kind == "own_observation"
        and row.evidence_id != evidence.evidence_id
        and row.instrument_id == evidence.instrument_id
        and row.target_id == evidence.target_id
        and row.quantity is evidence.quantity
        and row.unit == evidence.unit
        and row.declared_root != evidence.declared_root
        and row.condition_tokens == evidence.condition_tokens
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row.observed_tick, row.evidence_id))


def _appraise(
    ledger: MeasurementLedger, evidence: MeasurementEvidence
) -> MeasurementLedger:
    key = (evidence.instrument_id.value, evidence.quantity.value)
    existing = next(
        (row for row in ledger.beliefs if _belief_key(row) == key), None
    )
    if evidence.source_kind != "own_observation":
        return ledger
    if existing is None:
        belief = InstrumentReliabilityBelief(
            instrument_id=evidence.instrument_id,
            quantity=evidence.quantity,
            unit=evidence.unit,
            expected_resolution_milli=evidence.nominal_division_milli,
            estimated_error_band_milli=None,
            confidence_milli=_INITIAL_CONFIDENCE,
            observed_wear=evidence.observed_wear or "intact",
            adjustment_mark_present=bool(evidence.adjustment_mark_present),
            evidence_ids=(evidence.evidence_id,),
        )
        revision = MeasurementBeliefRevision(
            revision_id=f"mrev:{evidence.evidence_id}",
            instrument_id=evidence.instrument_id,
            quantity=evidence.quantity,
            observed_tick=evidence.observed_tick,
            previous_confidence_milli=0,
            new_confidence_milli=_INITIAL_CONFIDENCE,
            evidence_id=evidence.evidence_id,
            agreement="initial",
        )
        return _with_belief(ledger, belief, revision)
    prior = _latest_prior(ledger, evidence)
    agreement: Literal[
        "agreement", "disagreement", "initial", "no_comparison"
    ] = "no_comparison"
    error_band = existing.estimated_error_band_milli
    confidence = existing.confidence_milli
    if prior is not None:
        if evidence.value_kind == "category":
            agrees = prior.displayed_category == evidence.displayed_category
        else:
            assert prior.displayed_scalar_milli is not None
            assert evidence.displayed_scalar_milli is not None
            difference = abs(
                prior.displayed_scalar_milli - evidence.displayed_scalar_milli
            )
            agrees = difference <= 2 * max(
                prior.nominal_division_milli, evidence.nominal_division_milli
            )
            error_band = difference + max(
                prior.nominal_division_milli, evidence.nominal_division_milli
            )
        if agrees:
            agreement = "agreement"
            confidence = min(_MAX_CONFIDENCE, confidence + 50)
        else:
            agreement = "disagreement"
            confidence = max(_MIN_CONFIDENCE, confidence - 100)
    belief = replace(
        existing,
        expected_resolution_milli=max(
            existing.expected_resolution_milli,
            evidence.nominal_division_milli,
        ),
        estimated_error_band_milli=error_band,
        confidence_milli=confidence,
        observed_wear=evidence.observed_wear or existing.observed_wear,
        adjustment_mark_present=(
            existing.adjustment_mark_present
            or bool(evidence.adjustment_mark_present)
        ),
        evidence_ids=(*existing.evidence_ids, evidence.evidence_id),
    )
    revision = MeasurementBeliefRevision(
        revision_id=f"mrev:{evidence.evidence_id}",
        instrument_id=evidence.instrument_id,
        quantity=evidence.quantity,
        observed_tick=evidence.observed_tick,
        previous_confidence_milli=existing.confidence_milli,
        new_confidence_milli=confidence,
        evidence_id=evidence.evidence_id,
        agreement=agreement,
    )
    return _with_belief(ledger, belief, revision)


def _with_belief(
    ledger: MeasurementLedger,
    belief: InstrumentReliabilityBelief,
    revision: MeasurementBeliefRevision,
) -> MeasurementLedger:
    beliefs = tuple(
        row
        for row in ledger.beliefs
        if _belief_key(row) != _belief_key(belief)
    )
    if len(beliefs) >= MAX_BELIEFS:
        return replace(
            ledger,
            notices=(*ledger.notices, "measurement_belief_cap"),
        )
    revisions = ledger.revisions
    if len(revisions) >= MAX_REVISIONS:
        return replace(
            ledger,
            notices=(*ledger.notices, "measurement_revision_cap"),
        )
    return replace(
        ledger,
        beliefs=(*beliefs, belief),
        revisions=(*revisions, revision),
    )


def _trim_evidence(
    rows: list[MeasurementEvidence],
) -> tuple[MeasurementEvidence, ...]:
    if len(rows) <= MAX_EVIDENCE_ROWS:
        return tuple(rows)
    ordered = sorted(rows, key=lambda row: (row.observed_tick, row.evidence_id))
    return tuple(ordered[-MAX_EVIDENCE_ROWS:])


def ingest_measurement_observations(
    ledger: MeasurementLedger, observation: object
) -> MeasurementLedger:
    """Ingest actor-only measurement occurrences from one owner observation."""
    if type(ledger) is not MeasurementLedger:
        raise TypeError("ledger must be MeasurementLedger")
    observer_id = getattr(observation, "observer_id", None)
    if type(observer_id) is not EntityId:
        raise TypeError("observation must expose observer_id")
    owner_id = ledger.owner_id
    from world.observations import ObservationAudienceRole

    conditions = _owner_conditions(observation)
    instrument_cues = {
        item.entity_id: item.instrument
        for item in getattr(observation, "items", ())
        if getattr(item, "instrument", None) is not None
    }
    additions: list[MeasurementEvidence] = []
    for occurrence in getattr(observation, "occurrences", ()):
        if occurrence.kind != "measurement_taken":
            continue
        if occurrence.audience_role is not ObservationAudienceRole.ACTOR:
            continue
        facts = occurrence.public_facts
        if facts.get("value_kind") not in {"scalar", "category"}:
            continue
        provenance = occurrence.provenance
        source_event_id = provenance.source_event_id.value
        receipt = f"own:{source_event_id}"
        if receipt in ledger.receipts:
            continue
        instrument_id = EntityId(str(facts["instrument_id"]))
        appearance = instrument_cues.get(instrument_id)
        additions.append(
            MeasurementEvidence(
                evidence_id=_evidence_id(owner_id, receipt),
                owner_id=owner_id,
                instrument_id=instrument_id,
                target_id=EntityId(str(facts["target_id"])),
                quantity=MeasurementQuantity(str(facts["quantity"])),
                unit=_unit_from_facts(facts),
                value_kind=str(facts["value_kind"]),  # type: ignore[arg-type]
                displayed_scalar_milli=facts.get("display_scalar_milli"),
                displayed_category=facts.get("display_category"),
                nominal_division_milli=int(facts["nominal_division_milli"]),
                observed_tick=provenance.source_tick,
                source_kind="own_observation",
                source_event_id=source_event_id,
                delivery_event_id=None,
                declared_root=source_event_id,
                condition_tokens=conditions,
                observed_wear=None if appearance is None else appearance.wear.value,
                adjustment_mark_present=(
                    None
                    if appearance is None
                    else appearance.adjustment_mark_present
                ),
            )
        )
    if not additions:
        return ledger
    updated = ledger
    for addition in additions:
        receipt = _receipt_key(addition)
        if len(updated.receipts) >= MAX_ROOT_RECEIPTS:
            updated = replace(
                updated,
                notices=(*updated.notices, "measurement_receipt_cap"),
            )
            break
        rows = [*updated.evidence, addition]
        updated = replace(
            updated,
            evidence=_trim_evidence(rows),
            receipts=(*updated.receipts, receipt),
        )
        updated = _appraise(updated, addition)
    return updated


def _unit_from_facts(facts: dict[str, object]) -> MeasurementUnit:
    from world.measurement import MeasurementUnitKind

    kind = MeasurementUnitKind(str(facts["unit_kind"]))
    resource = facts.get("unit_resource")
    return MeasurementUnit(kind, None if resource is None else str(resource))


def compare_measurement_evidence(
    ledger: MeasurementLedger, evidence: MeasurementEvidence
) -> MeasurementLedger:
    """Apply the owner policy to one already-ingested evidence row."""
    if type(ledger) is not MeasurementLedger:
        raise TypeError("ledger must be MeasurementLedger")
    if type(evidence) is not MeasurementEvidence:
        raise TypeError("evidence must be MeasurementEvidence")
    if evidence.owner_id != ledger.owner_id:
        raise ValueError("evidence_owner_mismatch")
    return _appraise(ledger, evidence)
