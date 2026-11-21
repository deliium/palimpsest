"""Bounded carriers for scientific-knowledge diffusion.

The module encodes one opt-in research marker (``sdf_v1``) inside ordinary
communication relations or artifact relation triples. A marker names a frozen
source version by an opaque digest; it never carries claim text, parameters, or
a truth value. Reading, teaching, relay, and adoption remain separate evidence.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from analysis.science_diffusion_contract import (
    DiffusionContextFlag,
    DiffusionError,
    DiffusionLane,
    DiffusionOccurrence,
    DiffusionReason,
    DiffusionResolution,
    DiffusionStage,
    EvidenceKind,
    EvidenceRef,
    ScienceKind,
    ScienceVersion,
    ScienceVersionKey,
)
from experiments.science_diffusion_projection import (
    ArtifactSnapshot,
    project_artifacts,
)
from simulation import ObjectiveFacts
from simulation.fork_checkpoint import (
    FinalizedResearchBoundary,
    FinalizedResearchOwnerSnapshot,
)
from world.events import (
    ArtifactCopied,
    Talked,
    Told,
    WorldEvent,
)

__all__ = [
    "SCIENCE_DIFFUSION_MARKER",
    "CarrierMarker",
    "CarrierProjection",
    "decode_marker",
    "encode_call_triples",
    "encode_marker_triples",
    "encode_receipt_triples",
    "project_carrier_occurrences",
    "qualified_version_digest",
    "receipt_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.science_diffusion_carriers"
)

SCIENCE_DIFFUSION_MARKER: Final[str] = "sdf_v1"
_BASE32: Final[str] = "abcdefghijklmnopqrstuvwxyz234567"
_DIGEST_CHARS: Final[int] = 52
_SPLIT: Final[int] = 26
_MARKER_PREDICATES: Final[frozenset[str]] = frozenset(
    {
        "source_a",
        "source_b",
        "variant_a",
        "variant_b",
        "prior_a",
        "prior_b",
        "call_a",
        "call_b",
    }
)
_OPTIONAL_PAIRS: Final[tuple[tuple[str, str], ...]] = (
    ("variant_a", "variant_b"),
    ("prior_a", "prior_b"),
    ("call_a", "call_b"),
)
_GENERIC_OBSERVATION_TOKENS: Final[frozenset[str]] = frozenset(
    {"observation", "observed", "memory", "remembered", "none", ""}
)


@dataclass(frozen=True, slots=True)
class CarrierMarker:
    """One verified marker group: digests only, never content."""

    source_digest: str
    variant_digest: str = ""
    prior_digest: str = ""
    call_digest: str = ""

    def __post_init__(self) -> None:
        for name in (
            "source_digest",
            "variant_digest",
            "prior_digest",
            "call_digest",
        ):
            value = getattr(self, name)
            if value and (type(value) is not str or not _valid_digest(value)):
                raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)


@dataclass(frozen=True, slots=True)
class CarrierProjection:
    """Per-boundary carrier occurrences and per-lane availability."""

    occurrences: tuple[DiffusionOccurrence, ...]
    speech_state: str
    teaching_state: str
    records_state: str
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _Claim:
    operator: str
    operand_a_id: str
    operand_b_id: str | None
    process_token: str
    predicted_outcome: str | None
    conditions: tuple[tuple[str, str], ...]
    claim_token: str
    source_kind: str
    source_token: str


def _parse_hypothesis_claim(relation: Any) -> _Claim | None:
    subject = getattr(relation, "subject", None)
    predicate = getattr(relation, "predicate", None)
    body = getattr(relation, "object", None)
    if subject != "hyp_v1" or predicate != "claim":
        return None
    if type(body) is not str or not body or len(body) > 512:
        return None
    parts = body.split(":")
    if len(parts) != 10:
        return None
    (
        operator,
        operand_a,
        operand_b,
        process,
        predicted,
        _confidence,
        conds,
        source_kind,
        source_token,
        claim_token,
    ) = parts
    conditions: tuple[tuple[str, str], ...] = ()
    if conds not in {"", "none"}:
        rows: list[tuple[str, str]] = []
        for item in conds.split("|"):
            if "=" not in item:
                return None
            slot, value = item.split("=", 1)
            rows.append((slot, value))
        conditions = tuple(sorted(rows))
    return _Claim(
        operator=operator,
        operand_a_id=operand_a,
        operand_b_id=None if operand_b in {"", "none"} else operand_b,
        process_token=process,
        predicted_outcome=None if predicted in {"", "none"} else predicted,
        conditions=conditions,
        claim_token=claim_token,
        source_kind=source_kind,
        source_token=source_token,
    )


def _b32_digest(payload: bytes) -> str:
    encoded = base64.b32encode(payload).decode("ascii").lower().rstrip("=")
    return encoded


def _valid_token(value: str) -> bool:
    if type(value) is not str or len(value) != _SPLIT + 1:
        return False
    head = value[0]
    if head not in {"a", "b"}:
        return False
    return all(char in _BASE32 for char in value[1:])


def _valid_digest(value: str) -> bool:
    if type(value) is not str or len(value) != _DIGEST_CHARS:
        return False
    return all(char in _BASE32 for char in value)


def _require_digest(value: Any) -> str:
    if type(value) is not str or not _valid_digest(value):
        raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
    return value


def _split_digest(digest: str) -> tuple[str, str]:
    value = _require_digest(digest)
    return (f"a{value[:_SPLIT]}", f"b{value[_SPLIT:]}")


def _join_tokens(left: Any, right: Any) -> str:
    if type(left) is not str or type(right) is not str:
        raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
    if not _valid_token(left) or not _valid_token(right):
        raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
    if left[0] != "a" or right[0] != "b":
        raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
    digest = f"{left[1:]}{right[1:]}"
    canonical_left, canonical_right = _split_digest(digest)
    if canonical_left != left or canonical_right != right:
        raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
    return digest


def _canonical_key_payload(key: ScienceVersionKey) -> bytes:
    return json.dumps(
        key.as_tuple(),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def qualified_version_digest(key: ScienceVersionKey) -> str:
    """Return the unpadded lowercase base32 digest of a qualified version key."""

    if type(key) is not ScienceVersionKey:
        raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
    framed = b"science-diffusion-version-key.v1\x1f" + _canonical_key_payload(key)
    return _b32_digest(hashlib.sha256(framed).digest())


def receipt_digest(
    *,
    run_id: str,
    carrier_kind: str,
    reference: str,
    recipient_id: str,
) -> str:
    """Return a domain-separated qualified receipt digest."""

    for value in (run_id, carrier_kind, reference, recipient_id):
        if type(value) is not str or not value:
            raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
    payload = json.dumps(
        [run_id, carrier_kind, reference, recipient_id],
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    framed = b"science-diffusion-receipt-key.v1\x1f" + payload
    return _b32_digest(hashlib.sha256(framed).digest())


def call_digest(subject: str, predicate: str, object_token: str) -> str:
    """Return the canonical triple digest used for translation binding."""

    payload = json.dumps(
        [subject, predicate, object_token],
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return _b32_digest(
        hashlib.sha256(b"science-diffusion-call-key.v1\x1f" + payload).digest()
    )


def _triples(
    *, source: str, variant: str, prior: str, call: str
) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = [
        (SCIENCE_DIFFUSION_MARKER, "source_a", _split_digest(source)[0]),
        (SCIENCE_DIFFUSION_MARKER, "source_b", _split_digest(source)[1]),
    ]
    if variant:
        rows.extend(
            [
                (SCIENCE_DIFFUSION_MARKER, "variant_a", _split_digest(variant)[0]),
                (SCIENCE_DIFFUSION_MARKER, "variant_b", _split_digest(variant)[1]),
            ]
        )
    if prior:
        rows.extend(
            [
                (SCIENCE_DIFFUSION_MARKER, "prior_a", _split_digest(prior)[0]),
                (SCIENCE_DIFFUSION_MARKER, "prior_b", _split_digest(prior)[1]),
            ]
        )
    if call:
        rows.extend(
            [
                (SCIENCE_DIFFUSION_MARKER, "call_a", _split_digest(call)[0]),
                (SCIENCE_DIFFUSION_MARKER, "call_b", _split_digest(call)[1]),
            ]
        )
    for _, _, token in rows:
        if len(token) > 32:
            raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
    return tuple(rows)


def encode_marker_triples(
    key: ScienceVersionKey,
    *,
    variant: ScienceVersionKey | None = None,
    prior: str = "",
    call: str = "",
) -> tuple[tuple[str, str, str], ...]:
    """Encode one marker group; callers place the triples in ordinary relations."""

    if type(key) is not ScienceVersionKey:
        raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
    variant_digest = ""
    if variant is not None:
        if (
            variant.run_id != key.run_id
            or variant.owner_id != key.owner_id
            or variant.kind is not key.kind
            or variant.local_id != key.local_id
            or variant.revision_index <= key.revision_index
        ):
            raise DiffusionError(DiffusionReason.SOURCE_NOT_PRIOR.value)
        variant_digest = qualified_version_digest(variant)
    if prior:
        prior = _require_digest(prior)
    if call:
        call = _require_digest(call)
    return _triples(
        source=qualified_version_digest(key),
        variant=variant_digest,
        prior=prior,
        call=call,
    )


def encode_receipt_triples(
    *,
    run_id: str,
    carrier_kind: str,
    reference: str,
    source: ScienceVersionKey,
    variant: ScienceVersionKey | None = None,
    recipient_id: str,
) -> tuple[tuple[str, str, str], ...]:
    """Encode a relay marker carrying its exact prior receipt digest."""

    return encode_marker_triples(
        source,
        variant=variant,
        prior=receipt_digest(
            run_id=run_id,
            carrier_kind=carrier_kind,
            reference=reference,
            recipient_id=recipient_id,
        ),
    )


def encode_call_triples(
    subject: str, predicate: str, object_token: str
) -> tuple[tuple[str, str, str], ...]:
    """Return speech-only ``call_a``/``call_b`` triples for a translation triple."""

    value = call_digest(subject, predicate, object_token)
    return (
        (SCIENCE_DIFFUSION_MARKER, "call_a", _split_digest(value)[0]),
        (SCIENCE_DIFFUSION_MARKER, "call_b", _split_digest(value)[1]),
    )


def _as_triple(relation: Any) -> tuple[str, str, str]:
    if isinstance(relation, tuple) and len(relation) == 3:
        subject, predicate, object_token = relation
        if (
            type(subject) is str
            and type(predicate) is str
            and type(object_token) is str
        ):
            return (subject, predicate, object_token)
        raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
    subject = getattr(relation, "subject", None)
    predicate = getattr(relation, "predicate", None)
    object_token = getattr(relation, "object", None)
    if (
        type(subject) is not str
        or type(predicate) is not str
        or type(object_token) is not str
    ):
        raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)
    return (subject, predicate, object_token)


def decode_marker(relations: Iterable[object]) -> CarrierMarker | None:
    """Parse exactly one marker group, or return ``None`` when absent."""

    rows = [_as_triple(relation) for relation in relations]
    marker_rows = [row for row in rows if row[0] == SCIENCE_DIFFUSION_MARKER]
    if not marker_rows:
        return None
    predicates: dict[str, str] = {}
    for subject, predicate, object_token in marker_rows:
        if subject != SCIENCE_DIFFUSION_MARKER or predicate not in _MARKER_PREDICATES:
            raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
        if predicate in predicates:
            raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
        predicates[predicate] = object_token
    if "source_a" not in predicates or "source_b" not in predicates:
        raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
    source = _join_tokens(predicates.pop("source_a"), predicates.pop("source_b"))
    optional: dict[str, str] = {}
    for left, right in _OPTIONAL_PAIRS:
        has_left = left in predicates
        has_right = right in predicates
        if has_left != has_right:
            raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
        if has_left:
            optional[left] = _join_tokens(predicates.pop(left), predicates.pop(right))
    if predicates:
        raise DiffusionError(DiffusionReason.MARKER_INCOMPLETE.value)
    return CarrierMarker(
        source_digest=source,
        variant_digest=optional.get("variant_a", ""),
        prior_digest=optional.get("prior_a", ""),
        call_digest=optional.get("call_a", ""),
    )


def _version_digest_map(
    versions: Sequence[ScienceVersion],
) -> tuple[dict[str, ScienceVersionKey], dict[ScienceVersionKey, ScienceVersion]]:
    by_digest: dict[str, ScienceVersionKey] = {}
    by_key: dict[ScienceVersionKey, ScienceVersion] = {}
    for version in versions:
        digest = qualified_version_digest(version.key)
        prior = by_digest.get(digest)
        if prior is not None and prior != version.key:
            raise DiffusionError(DiffusionReason.IDENTITY_CONFLICT.value)
        by_digest[digest] = version.key
        by_key[version.key] = version
    return by_digest, by_key


def _entity_owner_map(
    boundary: FinalizedResearchBoundary, inventory: ObjectiveFacts
) -> tuple[dict[str, str], dict[str, str]]:
    entity_to_owner = {
        registration.entity_id.value: registration.agent_id.value
        for registration in inventory.registrations
    }
    owner_to_entity = {
        registration.agent_id.value: registration.entity_id.value
        for registration in inventory.registrations
    }
    _ = boundary
    return entity_to_owner, owner_to_entity


def _event_ref(event: WorldEvent) -> EvidenceRef:
    return EvidenceRef(
        kind=EvidenceKind.EVENT,
        run_id=event.run_id,
        tick=event.tick,
        event_id=event.event_id.value,
        sequence=event.sequence,
    )


def _owner_row_ref(
    owner_id: str, local_id: str, revision_index: int, tick: int, run_id: str
) -> EvidenceRef:
    return EvidenceRef(
        kind=EvidenceKind.OWNER_ROW,
        run_id=run_id,
        tick=tick,
        owner_id=owner_id,
        local_id=local_id,
        revision_index=revision_index,
    )


def _hypothesis_wire_from_claim(
    claim: Any,
) -> dict[str, str]:
    conditions = "none"
    if claim.conditions:
        conditions = "|".join(
            sorted(
                f"{slot}={value}" for slot, value in claim.conditions
            )
        )
    outcome = "none" if claim.predicted_outcome is None else claim.predicted_outcome
    return {
        "operator": claim.operator,
        "operand_a": claim.operand_a_id,
        "operand_b": "none" if claim.operand_b_id is None else claim.operand_b_id,
        "process": claim.process_token,
        "predicted_outcome": outcome,
        "conditions": conditions,
    }


def _hypothesis_wire_from_version(version: ScienceVersion) -> dict[str, str]:
    assert version.hypothesis is not None
    conditions = "none"
    if version.hypothesis.conditions:
        conditions = "|".join(
            sorted(
                f"{slot}={value}" for slot, value in version.hypothesis.conditions
            )
        )
    operand_refs = version.hypothesis.operand_refs
    return {
        "operator": version.hypothesis.operator,
        "operand_a": operand_refs[0].split(":", 1)[-1],
        "operand_b": (
            "none"
            if len(operand_refs) < 2
            else operand_refs[1].split(":", 1)[-1]
        ),
        "process": version.hypothesis.process,
        "predicted_outcome": (
            "none"
            if version.hypothesis.predicted_outcome is None
            else version.hypothesis.predicted_outcome
        ),
        "conditions": conditions,
    }


def _match_hypothesis_source(
    claim: Any,
    *,
    sender_owner: str,
    event_tick: int,
    versions: Sequence[ScienceVersion],
) -> tuple[ScienceVersionKey | None, str | None]:
    expected = _hypothesis_wire_from_claim(claim)
    matches: list[ScienceVersionKey] = []
    for version in versions:
        if version.key.kind is not ScienceKind.HYPOTHESIS:
            continue
        if version.key.owner_id != sender_owner:
            continue
        if version.occurrence_tick >= event_tick:
            continue
        actual = _hypothesis_wire_from_version(version)
        if all(
            actual.get(name) == expected[name]
            for name in (
                "operator",
                "operand_a",
                "operand_b",
                "process",
                "predicted_outcome",
                "conditions",
            )
        ):
            matches.append(version.key)
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, DiffusionReason.UNVERIFIED_REFERENCE.value
    fingerprints = {
        next(item for item in versions if item.key == key).content_fingerprint()
        for key in matches
    }
    if len(fingerprints) == 1:
        chosen = max(matches, key=lambda item: item.revision_index)
        return chosen, None
    return None, DiffusionReason.AMBIGUOUS_SOURCE.value


def _adopted_by_recipient(
    owner: FinalizedResearchOwnerSnapshot,
    *,
    event_id: str,
) -> bool:
    checkpoint = owner.runtime_checkpoint
    if checkpoint is None:
        return False
    ledger = getattr(checkpoint, "experiment_ledger", None)
    if ledger is None or not hasattr(ledger, "hypotheses"):
        return False
    token = f"evt:{event_id}"
    for hypothesis in ledger.hypotheses:
        for revision in hypothesis.revisions:
            if (
                revision.evidence_ref == token
                and revision.reason.value == "source_adopted"
            ):
                return True
    return False


def _advice_occurrence(
    owner: FinalizedResearchOwnerSnapshot, *, event_id: str
) -> str | None:
    checkpoint = owner.runtime_checkpoint
    if checkpoint is None:
        return None
    store = getattr(checkpoint, "declarative_advice", None)
    if store is None or not hasattr(store, "rows"):
        return None
    for row in store.rows:
        if row.occurrence_id == event_id:
            return str(row.act.value)
    return None


def _artifact_content_marker(
    artifact: ArtifactSnapshot,
    inventory: ObjectiveFacts,
) -> tuple[tuple[str, str, str], ...]:
    for current in inventory.artifacts:
        if current.artifact_id.value != artifact.artifact_id:
            continue
        if current.content_revision != artifact.content_revision:
            return ()
        return tuple(
            (relation.subject, relation.predicate, relation.object)
            for relation in current.content.relations
        )
    return ()


def _find_event(
    boundary: FinalizedResearchBoundary, event_id: str
) -> WorldEvent | None:
    for event in boundary.events:
        if event.event_id.value == event_id:
            return event
    return None


def _science_versions_by_owner(
    versions: Sequence[ScienceVersion], owner_id: str
) -> tuple[ScienceVersion, ...]:
    return tuple(
        row for row in versions if row.key.owner_id == owner_id
    )


def project_carrier_occurrences(
    boundary: FinalizedResearchBoundary,
    inventory: ObjectiveFacts,
    *,
    versions: Sequence[ScienceVersion],
    observed_boundary: int,
    prior_occurrences: Sequence[DiffusionOccurrence] = (),
) -> CarrierProjection:
    """Project addressed speech, teaching, reading, and copy carriers."""

    run_id = boundary.run_id.value
    entity_to_owner, _ = _entity_owner_map(boundary, inventory)
    owners = {row.owner_id.value: row for row in boundary.owners}
    by_digest, by_key = _version_digest_map(versions)
    prior_receipts: dict[str, DiffusionOccurrence] = {}
    for row in prior_occurrences:
        if row.counterparty_id is None:
            continue
        digest = receipt_digest(
            run_id=run_id,
            carrier_kind=f"{row.lane.value}:{row.occurrence_kind}",
            reference=row.evidence.qualified_key().__repr__(),
            recipient_id=row.counterparty_id,
        )
        prior_receipts[digest] = row
    occurrences: list[DiffusionOccurrence] = []
    diagnostics: list[str] = []
    artifacts = project_artifacts(inventory)
    artifacts_by_id = {row.artifact_id: row for row in artifacts}

    for event in boundary.events:
        details = event.details
        if not isinstance(details, (Talked, Told)):
            continue
        speaker_entity = event.actor_id.value if event.actor_id is not None else ""
        recipient_entity = details.recipient_id.value
        speaker = entity_to_owner.get(speaker_entity)
        recipient = entity_to_owner.get(recipient_entity)
        if speaker is None or recipient is None or speaker == recipient:
            diagnostics.append(DiffusionReason.UNADDRESSED.value)
            continue
        relations = tuple(details.utterance.content.relations)
        science_sources: list[ScienceVersionKey | None] = []
        hyp_claims: list[_Claim] = []
        for relation in relations:
            claim = _parse_hypothesis_claim(relation)
            if claim is not None:
                hyp_claims.append(claim)
        for claim in hyp_claims:
            source, reason = _match_hypothesis_source(
                claim,
                sender_owner=speaker,
                event_tick=event.tick,
                versions=versions,
            )
            science_sources.append(source)
            adopted = _adopted_by_recipient(
                owners[recipient], event_id=event.event_id.value
            )
            occurrence = DiffusionOccurrence(
                run_id=run_id,
                lane=DiffusionLane.SPEECH,
                occurrence_kind="hypothesis_delivery",
                tick=event.tick,
                first_observed_boundary=max(observed_boundary, event.tick),
                evidence=_event_ref(event),
                stage=(
                    DiffusionStage.ADOPTED if adopted else DiffusionStage.DELIVERED
                ),
                confirmation_boundary=(
                    max(observed_boundary, event.tick) if adopted else None
                ),
                actor_id=speaker,
                counterparty_id=recipient,
                source_version=source,
                detail=(
                    ("adopted", "1" if adopted else "0"),
                    ("claim_present", "1"),
                    ("exposure_only", "0" if adopted else "1"),
                ),
                resolution=(
                    DiffusionResolution.CONFIRMED
                    if reason is None
                    else DiffusionResolution.UNRESOLVED
                ),
                reason=None if reason is None else DiffusionReason(reason),
            )
            occurrences.append(occurrence)
        try:
            marker = decode_marker(relations)
        except DiffusionError as exc:
            diagnostics.append(exc.reason_code)
            marker = None
        if marker is not None:
            occurrence = _marker_speech_occurrence(
                marker,
                event=event,
                run_id=run_id,
                speaker=speaker,
                recipient=recipient,
                observed_boundary=observed_boundary,
                by_digest=by_digest,
                by_key=by_key,
                prior_receipts=prior_receipts,
                versions=versions,
            )
            occurrences.append(occurrence)
            science_sources.append(occurrence.source_version)
        advice_act = _advice_occurrence(
            owners[recipient], event_id=event.event_id.value
        )
        if advice_act is not None and science_sources:
            source = next((item for item in science_sources if item is not None), None)
            occurrences.append(
                DiffusionOccurrence(
                    run_id=run_id,
                    lane=DiffusionLane.TEACHING,
                    occurrence_kind="science_teaching",
                    tick=event.tick,
                    first_observed_boundary=max(observed_boundary, event.tick),
                    evidence=_event_ref(event),
                    stage=DiffusionStage.DELIVERED,
                    actor_id=speaker,
                    counterparty_id=recipient,
                    source_version=source,
                    detail=(("advice_act", advice_act),),
                )
            )

    for owner_id, owner in owners.items():
        checkpoint = owner.runtime_checkpoint
        if checkpoint is None:
            continue
        ledger = getattr(checkpoint, "artifact_interpretations", None)
        if ledger is None:
            continue
        if not hasattr(ledger, "interpretations"):
            continue
        for reading in ledger.interpretations:
            artifact = artifacts_by_id.get(reading.artifact_id.value)
            if artifact is None:
                diagnostics.append(DiffusionReason.RECORD_REVISION_MISSING.value)
                continue
            if artifact.content_revision != reading.observed_revision:
                diagnostics.append(DiffusionReason.RECORD_REVISION_MISSING.value)
                continue
            actual_relations = _artifact_content_marker(artifact, inventory)
            try:
                actual_marker = decode_marker(actual_relations)
            except DiffusionError as exc:
                diagnostics.append(exc.reason_code)
                continue
            if actual_marker is None:
                continue
            try:
                reading_marker = decode_marker(reading.reading_relations)
            except DiffusionError as exc:
                diagnostics.append(exc.reason_code)
                reading_marker = None
            source = by_digest.get(actual_marker.source_digest)
            if source is None:
                diagnostics.append(DiffusionReason.UNVERIFIED_REFERENCE.value)
                continue
            divergent = reading_marker is None or (
                reading_marker.source_digest != actual_marker.source_digest
            )
            source_event = (
                _find_event(boundary, reading.source_event_id.value)
                if reading.source_event_id is not None
                else None
            )
            evidence = (
                _event_ref(source_event)
                if source_event is not None
                else _owner_row_ref(
                    owner_id,
                    artifact.artifact_id,
                    reading.observed_revision,
                    reading.source_tick,
                    run_id,
                )
            )
            occurrences.append(
                DiffusionOccurrence(
                    run_id=run_id,
                    lane=DiffusionLane.RECORDS,
                    occurrence_kind="record_reading",
                    tick=reading.source_tick,
                    first_observed_boundary=max(
                        observed_boundary, reading.source_tick
                    ),
                    evidence=evidence,
                    stage=DiffusionStage.INTERPRETED,
                    actor_id=owner_id,
                    source_version=source,
                    carrier_kind=artifact.kind,
                    carrier_id=artifact.artifact_id,
                    content_revision=artifact.content_revision,
                    context_flags=(DiffusionContextFlag.PHYSICAL_CARRIER,),
                    detail=(
                        ("distorted", "1" if reading.distorted else "0"),
                        ("divergent_read", "1" if divergent else "0"),
                        ("marker_intact", "1"),
                    ),
                    resolution=(
                        DiffusionResolution.CONFIRMED
                        if not divergent
                        else DiffusionResolution.AMBIGUOUS
                    ),
                    reason=(
                        None if not divergent else DiffusionReason.DIVERGENT_READ
                    ),
                )
            )

    for event in boundary.events:
        details = event.details
        if not isinstance(details, ArtifactCopied):
            continue
        copy = artifacts_by_id.get(details.child_artifact_id.value)
        if copy is None or copy.content_revision != 0:
            continue
        source_artifact = artifacts_by_id.get(copy.source_artifact_id or "")
        if source_artifact is None:
            continue
        source_relations = _artifact_content_marker(source_artifact, inventory)
        copy_relations = _artifact_content_marker(copy, inventory)
        try:
            source_marker = decode_marker(source_relations)
            copy_marker = decode_marker(copy_relations)
        except DiffusionError as exc:
            diagnostics.append(exc.reason_code)
            continue
        if source_marker is None or copy_marker != source_marker:
            continue
        source = by_digest.get(copy_marker.source_digest)
        if source is None:
            diagnostics.append(DiffusionReason.UNVERIFIED_REFERENCE.value)
            continue
        actor_entity = event.actor_id.value if event.actor_id is not None else ""
        actor = entity_to_owner.get(actor_entity)
        if actor is None:
            diagnostics.append(DiffusionReason.UNADDRESSED.value)
            continue
        occurrences.append(
            DiffusionOccurrence(
                run_id=run_id,
                lane=DiffusionLane.RECORDS,
                occurrence_kind="record_copy",
                tick=event.tick,
                first_observed_boundary=max(observed_boundary, event.tick),
                evidence=_event_ref(event),
                stage=DiffusionStage.CARRIED,
                actor_id=actor,
                source_version=source,
                carrier_kind=copy.kind,
                carrier_id=copy.artifact_id,
                content_revision=copy.content_revision,
                context_flags=(DiffusionContextFlag.PHYSICAL_CARRIER,),
                detail=(("copy_generation", str(copy.copy_generation)),),
            )
        )

    speech_state = "complete"
    teaching_state = (
        "complete"
        if any(
            getattr(owner.runtime_checkpoint, "declarative_advice", None)
            is not None
            for owner in owners.values()
            if owner.runtime_checkpoint is not None
        )
        else "unavailable"
    )
    records_state = (
        "complete"
        if any(
            getattr(owner.runtime_checkpoint, "artifact_interpretations", None)
            is not None
            for owner in owners.values()
            if owner.runtime_checkpoint is not None
        )
        or any(row.lane is DiffusionLane.RECORDS for row in occurrences)
        else "unavailable"
    )
    return CarrierProjection(
        occurrences=tuple(sorted(occurrences, key=lambda row: row.sort_key())),
        speech_state=speech_state,
        teaching_state=teaching_state,
        records_state=records_state,
        diagnostics=tuple(sorted(set(diagnostics))),
    )


def _marker_speech_occurrence(
    marker: CarrierMarker,
    *,
    event: WorldEvent,
    run_id: str,
    speaker: str,
    recipient: str,
    observed_boundary: int,
    by_digest: Mapping[str, ScienceVersionKey],
    by_key: Mapping[ScienceVersionKey, ScienceVersion],
    prior_receipts: Mapping[str, DiffusionOccurrence],
    versions: Sequence[ScienceVersion],
) -> DiffusionOccurrence:
    source = by_digest.get(marker.source_digest)
    reason: DiffusionReason | None = None
    if source is None:
        reason = DiffusionReason.UNVERIFIED_REFERENCE
    variant: ScienceVersionKey | None = None
    if marker.variant_digest:
        variant = by_digest.get(marker.variant_digest)
        if variant is None:
            reason = DiffusionReason.UNVERIFIED_REFERENCE
        elif (
            source is not None
            and (
                variant.run_id != source.run_id
                or variant.owner_id != source.owner_id
                or variant.kind is not source.kind
                or variant.local_id != source.local_id
                or variant.revision_index <= source.revision_index
            )
        ):
            reason = DiffusionReason.SOURCE_NOT_PRIOR
            variant = None
    if reason is None and source is not None:
        prior = prior_receipts.get(marker.prior_digest) if marker.prior_digest else None
        if marker.prior_digest and prior is None:
            reason = DiffusionReason.RELAY_PARENT_MISSING
        elif prior is not None:
            if prior.counterparty_id != speaker:
                reason = DiffusionReason.RELAY_PARENT_MISSING
            elif prior.source_version != source:
                reason = DiffusionReason.UNVERIFIED_REFERENCE
            elif prior.variant_version != variant:
                reason = DiffusionReason.UNVERIFIED_REFERENCE
        owner_versions = _science_versions_by_owner(versions, speaker)
        if not any(item.key == source for item in owner_versions):
            reason = DiffusionReason.UNVERIFIED_REFERENCE
    return DiffusionOccurrence(
        run_id=run_id,
        lane=DiffusionLane.SPEECH,
        occurrence_kind="marker_report",
        tick=event.tick,
        first_observed_boundary=max(observed_boundary, event.tick),
        evidence=_event_ref(event),
        stage=DiffusionStage.REPORTED_REFERENCE,
        actor_id=speaker,
        counterparty_id=recipient,
        source_version=source,
        variant_version=variant,
        detail=(
            ("marker", SCIENCE_DIFFUSION_MARKER),
            ("relay", "1" if marker.prior_digest else "0"),
        ),
        resolution=(
            DiffusionResolution.CONFIRMED
            if reason is None
            else (
                DiffusionResolution.AMBIGUOUS
                if reason is DiffusionReason.AMBIGUOUS_SOURCE
                else DiffusionResolution.UNRESOLVED
            )
        ),
        reason=reason,
    )
