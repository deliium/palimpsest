"""Detached, metadata-only translation analysis rows and metric families.

Rows never carry raw foreign/own label tokens or message bodies. Spearker
intent and listener interpretation are resolved at harvest time from detached
ledgers; cross-community eligibility is resolved only from candidate-community
rows. Analysis is descriptive and never feeds results back to cognition.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "CROSS_GROUP_TRANSLATION_METRIC_VERSION",
    "TRANSLATION_INFLUENCE_METRIC_VERSION",
    "TRANSLATION_LEARNING_METRIC_VERSION",
    "TranslationAnalysisInputs",
    "TranslationInfluenceRow",
    "TranslationInterpretationSource",
    "TranslationMappingRow",
    "TranslationMessageRow",
    "TranslationOutcome",
    "compute_cross_group_translation",
    "compute_cross_group_translation_metric",
    "compute_translation_influence",
    "compute_translation_influence_metric",
    "compute_translation_learning",
    "compute_translation_learning_metric",
    "translation_analysis_inputs_from_harvest",
    "translation_influence_rows_from_ledgers",
    "translation_label_digest",
    "translation_mapping_rows_from_ledgers",
    "translation_referent_digest",
    "translation_source_digest",
]

TRANSLATION_LEARNING_METRIC_VERSION: Final[str] = "translation_learning@1"
CROSS_GROUP_TRANSLATION_METRIC_VERSION: Final[str] = "cross_group_translation@1"
TRANSLATION_INFLUENCE_METRIC_VERSION: Final[str] = "translation_influence@1"

_SOURCE_DIGEST_LEN: Final[int] = 16


class TranslationOutcome(StrEnum):
    """Analysis-only intent-proxy labels. Never objective truth."""

    EXACT = "exact"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    WRONG = "wrong"
    UNRESOLVED = "unresolved"
    UNRESOLVED_INTENT = "unresolved_intent"


class TranslationInterpretationSource(StrEnum):
    """Closed interpretation source for one delivered foreign term."""

    MAPPING = "mapping"
    OWN_BINDING = "own_binding"
    NONE = "none"


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _digest(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:_SOURCE_DIGEST_LEN]


def translation_source_digest(source_token: str) -> str:
    return _digest(f"translation|{source_token}")


def translation_label_digest(label_token: str) -> str:
    return _digest(f"label|{label_token}")


def translation_referent_digest(referent_kind: str, referent_id: str) -> str:
    return _digest(f"{referent_kind}|{referent_id}")


def _stable_list(values: Sequence[object], name: str) -> tuple[str, ...]:
    checked: list[str] = []
    for item in values:
        token = require_stable_id(name, item)
        if token not in checked:
            checked.append(token)
    return tuple(checked)


@dataclass(frozen=True, slots=True)
class TranslationMappingRow:
    owner_id: str
    mapping_id: str
    source_digest: str
    source_kind: str
    target_label_digests: tuple[str, ...]
    target_referent_kinds: tuple[str, ...]
    target_referent_digests: tuple[str, ...]
    status: str
    fit: str
    strength_band: str
    evidence_count: int
    usage_count: int
    channels: tuple[str, ...]
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "mapping_id",
            "source_digest",
            "source_kind",
            "status",
            "fit",
            "strength_band",
        ):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        object.__setattr__(
            self,
            "target_label_digests",
            _stable_list(self.target_label_digests, "target_label_digests"),
        )
        object.__setattr__(
            self,
            "target_referent_kinds",
            _stable_list(self.target_referent_kinds, "target_referent_kinds"),
        )
        object.__setattr__(
            self,
            "target_referent_digests",
            _stable_list(self.target_referent_digests, "target_referent_digests"),
        )
        object.__setattr__(
            self, "channels", _stable_list(self.channels, "channels")
        )
        if len(self.target_label_digests) != len(self.target_referent_kinds):
            raise ValueError("target_label_digests: length_mismatch")
        if len(self.target_label_digests) != len(self.target_referent_digests):
            raise ValueError("target_label_digests: length_mismatch")
        for name in ("evidence_count", "usage_count", "first_tick", "last_tick"):
            object.__setattr__(
                self, name, require_exact_nonneg_int(name, getattr(self, name))
            )
        if self.last_tick < self.first_tick:
            raise ValueError("last_tick: before_first_tick")


@dataclass(frozen=True, slots=True)
class TranslationMessageRow:
    message_id: str
    speaker_id: str
    listener_id: str
    tick: int
    source_digest: str
    source_kind: str
    declared_confidence_band: str
    speaker_referent_kind: str | None
    speaker_referent_digest: str | None
    listener_referent_kind: str | None
    listener_referent_digest: str | None
    outcome: TranslationOutcome
    mapping_id: str | None
    interpretation_source: TranslationInterpretationSource
    confidence_band: str
    dominant_channel: str | None
    cross_community: bool

    def __post_init__(self) -> None:
        for name in (
            "message_id",
            "speaker_id",
            "listener_id",
            "source_digest",
            "source_kind",
            "declared_confidence_band",
            "confidence_band",
        ):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        object.__setattr__(
            self, "tick", require_exact_nonneg_int("tick", self.tick)
        )
        for name in (
            "speaker_referent_kind",
            "speaker_referent_digest",
            "listener_referent_kind",
            "listener_referent_digest",
            "mapping_id",
            "dominant_channel",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_stable_id(name, value))
        if type(self.outcome) is not TranslationOutcome:
            raise TypeError("outcome: invalid_type")
        if type(self.interpretation_source) is not TranslationInterpretationSource:
            raise TypeError("interpretation_source: invalid_type")
        if type(self.cross_community) is not bool:
            raise TypeError("cross_community: invalid_type")


@dataclass(frozen=True, slots=True)
class TranslationInfluenceRow:
    owner_id: str
    mapping_id: str
    message_id: str | None
    source_digest: str
    target_label_digest: str
    effect_kind: str
    outcome: str
    tick: int
    actor_digest: str | None
    confidence_band: str
    command_kind: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "mapping_id",
            "source_digest",
            "target_label_digest",
            "effect_kind",
            "outcome",
            "confidence_band",
        ):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        if self.message_id is not None:
            object.__setattr__(
                self, "message_id", require_stable_id("message_id", self.message_id)
            )
        if self.actor_digest is not None:
            object.__setattr__(
                self,
                "actor_digest",
                require_stable_id("actor_digest", self.actor_digest),
            )
        if self.command_kind is not None and self.command_kind not in {
            "talk",
            "ask",
            "tell",
        }:
            raise ValueError("command_kind: unknown_kind")


@dataclass(frozen=True, slots=True)
class TranslationAnalysisInputs:
    mappings: tuple[TranslationMappingRow, ...] = ()
    messages: tuple[TranslationMessageRow, ...] = ()
    influences: tuple[TranslationInfluenceRow, ...] = ()
    communities: tuple[object, ...] = ()
    expected_owner_count: int = 0

    def __post_init__(self) -> None:
        if any(type(row) is not TranslationMappingRow for row in self.mappings):
            raise TypeError("mappings: invalid_item")
        if any(type(row) is not TranslationMessageRow for row in self.messages):
            raise TypeError("messages: invalid_item")
        if any(type(row) is not TranslationInfluenceRow for row in self.influences):
            raise TypeError("influences: invalid_item")
        object.__setattr__(
            self,
            "expected_owner_count",
            require_exact_nonneg_int(
                "expected_owner_count", self.expected_owner_count
            ),
        )


def _binding_referent(binding: object) -> tuple[str, str] | None:
    kind = getattr(getattr(binding, "referent_kind", None), "value", None)
    candidates = getattr(binding, "candidates", ()) or ()
    if not isinstance(kind, str) or not candidates:
        return None
    top = max(
        candidates,
        key=lambda item: (
            float(getattr(item, "confidence", 0.0)),
            str(getattr(item, "entity_id", "")),
        ),
    )
    entity = getattr(top, "entity_id", None)
    if not isinstance(entity, str) or not entity:
        return None
    return kind, entity


def _naming_index(
    naming_ledgers: Sequence[object],
) -> dict[tuple[str, str, str], tuple[str, str]]:
    index: dict[tuple[str, str, str], tuple[str, str]] = {}
    for ledger in naming_ledgers:
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        if not isinstance(owner, str):
            continue
        for binding in getattr(ledger, "bindings", ()) or ():
            token = getattr(binding, "label_token", None)
            kind_value = getattr(getattr(binding, "referent_kind", None), "value", None)
            referent = _binding_referent(binding)
            if isinstance(token, str) and isinstance(kind_value, str) and referent:
                index[(owner, token, kind_value)] = referent
    return index


def translation_mapping_rows_from_ledgers(
    translation_ledgers: Sequence[object],
    naming_ledgers: Sequence[object] = (),
) -> tuple[TranslationMappingRow, ...]:
    """Build metadata-only mapping rows in owner/ledger order."""
    naming = _naming_index(naming_ledgers)
    rows: list[TranslationMappingRow] = []
    for ledger in translation_ledgers:
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        if not isinstance(owner, str):
            continue
        for mapping in getattr(ledger, "mappings", ()) or ():
            source = getattr(mapping, "source_token", None)
            if not isinstance(source, str):
                continue
            labels: list[str] = []
            kinds: list[str] = []
            referents: list[str] = []
            for target in getattr(mapping, "targets", ()) or ():
                token = getattr(target, "label_token", None)
                kind = getattr(getattr(target, "referent_kind", None), "value", None)
                if not isinstance(token, str) or not isinstance(kind, str):
                    continue
                labels.append(translation_label_digest(token))
                kinds.append(kind)
                resolved = naming.get((owner, token, kind))
                referents.append(
                    ""
                    if resolved is None
                    else translation_referent_digest(resolved[0], resolved[1])
                )
            channels = tuple(
                sorted(
                    {
                        _enum_value(getattr(item, "channel", "context"))
                        for item in getattr(mapping, "evidence", ()) or ()
                    }
                )
            )
            rows.append(
                TranslationMappingRow(
                    owner_id=owner,
                    mapping_id=str(getattr(mapping, "mapping_id", "")),
                    source_digest=str(getattr(mapping, "source_digest", "")),
                    source_kind=str(
                        getattr(
                            getattr(mapping, "source_kind", None),
                            "value",
                            "label",
                        )
                    ),
                    target_label_digests=tuple(labels),
                    target_referent_kinds=tuple(kinds),
                    target_referent_digests=tuple(
                        item or "unknown" for item in referents
                    ),
                    status=_enum_value(getattr(mapping, "status", "candidate")),
                    fit=_enum_value(getattr(mapping, "fit", "unresolved")),
                    strength_band=_strength_band(mapping),
                    evidence_count=int(getattr(mapping, "evidence_count", 0)),
                    usage_count=int(getattr(mapping, "usage_count", 0)),
                    channels=channels,
                    first_tick=int(getattr(mapping, "first_tick", 0)),
                    last_tick=int(getattr(mapping, "last_tick", 0)),
                )
            )
    return tuple(rows)


def _strength_band(mapping: object) -> str:
    status = str(getattr(getattr(mapping, "status", None), "value", "candidate"))
    strength = float(getattr(mapping, "strength", 0.0))
    if status == "candidate":
        return "candidate"
    if strength < 0.45:
        return "low"
    if strength < 0.75:
        return "mid"
    return "high"


def _confidence_band(value: float) -> str:
    if value < 0.34:
        return "low"
    if value < 0.67:
        return "mid"
    return "high"


def _extract_message(event: object) -> tuple[str, str, str, int, object] | None:
    payload = getattr(event, "details", None)
    if payload is None:
        payload = getattr(event, "event", event)
    utterance = getattr(payload, "utterance", None)
    if utterance is None:
        return None
    recipient = getattr(payload, "recipient_id", None)
    speaker = getattr(event, "actor_id", None)
    tick = getattr(event, "tick", None)
    event_id = getattr(getattr(event, "event_id", None), "value", None)
    if recipient is None or speaker is None or not isinstance(tick, int):
        return None
    return (
        str(event_id or f"event-{tick}"),
        str(getattr(speaker, "value", speaker)),
        str(getattr(recipient, "value", recipient)),
        tick,
        utterance,
    )


def translation_message_rows_from_events(
    events: Sequence[object],
    translation_ledgers: Sequence[object],
    naming_ledgers: Sequence[object] = (),
    communities: Sequence[object] = (),
    owner_entity_ids: Mapping[str, str] | None = None,
) -> tuple[TranslationMessageRow, ...]:
    """Classify delivered foreign terms against detached intent evidence."""
    naming = _naming_index(naming_ledgers)
    entity_to_owner = (
        {}
        if owner_entity_ids is None
        else {entity: owner for owner, entity in owner_entity_ids.items()}
    )
    mapping_by_owner: dict[str, list[object]] = defaultdict(list)
    for ledger in translation_ledgers:
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        if isinstance(owner, str):
            mapping_by_owner[owner].extend(getattr(ledger, "mappings", ()) or ())
    community_of: dict[str, str] = {}
    for community in communities:
        community_id = getattr(community, "community_id", None)
        persons = getattr(community, "person_ids", ()) or ()
        if not isinstance(community_id, str):
            continue
        for person in persons:
            if isinstance(person, str):
                community_of[person] = community_id
    rows: list[TranslationMessageRow] = []
    for event in events:
        extracted = _extract_message(event)
        if extracted is None:
            continue
        message_id, speaker_entity, listener_entity, tick, utterance = extracted
        speaker = entity_to_owner.get(speaker_entity, speaker_entity)
        listener = entity_to_owner.get(listener_entity, listener_entity)
        declared = getattr(utterance, "declared", None)
        confidence = float(getattr(declared, "sender_confidence", 0.5))
        content = getattr(utterance, "content", None)
        for relation in getattr(content, "relations", ()) or ():
            if getattr(relation, "predicate", None) != "call":
                continue
            token = getattr(relation, "subject", None)
            kind = getattr(relation, "object", None)
            if not isinstance(token, str) or not isinstance(kind, str):
                continue
            speaker_intent = naming.get((speaker, token, kind))
            mapping = _select_mapping(mapping_by_owner.get(listener, ()), token)
            source_digest = translation_source_digest(token)
            if speaker_intent is None:
                outcome = TranslationOutcome.UNRESOLVED_INTENT
                source = TranslationInterpretationSource.NONE
                listener_referent = None
                mapping_id = (
                    None
                    if mapping is None
                    else str(getattr(mapping, "mapping_id", ""))
                )
                dominant = None
            else:
                target_referent = None
                if mapping is not None:
                    targets = tuple(getattr(mapping, "targets", None) or ())
                    if len(targets) == 1:
                        target = targets[0]
                        target_token = getattr(target, "label_token", None)
                        target_kind = getattr(
                            getattr(target, "referent_kind", None), "value", None
                        )
                        if isinstance(target_token, str) and isinstance(
                            target_kind, str
                        ):
                            target_referent = naming.get(
                                (listener, target_token, target_kind)
                            )
                target_referents: list[tuple[str, str]] = []
                if mapping is not None:
                    for target in getattr(mapping, "targets", ()) or ():
                        target_token = getattr(target, "label_token", None)
                        target_kind = getattr(
                            getattr(target, "referent_kind", None), "value", None
                        )
                        if isinstance(target_token, str) and isinstance(
                            target_kind, str
                        ):
                            resolved_target = naming.get(
                                (listener, target_token, target_kind)
                            )
                            if resolved_target is not None:
                                target_referents.append(resolved_target)
                source, outcome, listener_referent, mapping_id, dominant = (
                    _classify_listener(
                        mapping,
                        naming.get((listener, token, kind)),
                        speaker_intent,
                        target_referent,
                        target_referents,
                    )
                )
            cross = (
                speaker in community_of
                and listener in community_of
                and community_of[speaker] != community_of[listener]
            )
            rows.append(
                TranslationMessageRow(
                    message_id=message_id,
                    speaker_id=speaker,
                    listener_id=listener,
                    tick=tick,
                    source_digest=source_digest,
                    source_kind="label",
                    declared_confidence_band=_confidence_band(confidence),
                    speaker_referent_kind=(
                        None if speaker_intent is None else speaker_intent[0]
                    ),
                    speaker_referent_digest=(
                        None
                        if speaker_intent is None
                        else translation_referent_digest(*speaker_intent)
                    ),
                    listener_referent_kind=(
                        None if listener_referent is None else listener_referent[0]
                    ),
                    listener_referent_digest=(
                        None
                        if listener_referent is None
                        else translation_referent_digest(*listener_referent)
                    ),
                    outcome=outcome,
                    mapping_id=mapping_id,
                    interpretation_source=source,
                    confidence_band=_confidence_band(
                        float(
                            getattr(mapping, "strength", confidence)
                            if mapping is not None
                            else confidence
                        )
                    ),
                    dominant_channel=dominant,
                    cross_community=cross,
                )
            )
    return tuple(rows)


def _select_mapping(mappings: Sequence[object], token: str) -> object | None:
    candidates = [
        mapping
        for mapping in mappings
        if getattr(mapping, "source_token", None) == token
        and str(getattr(getattr(mapping, "status", None), "value", "")) == "active"
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda mapping: (
            float(getattr(mapping, "strength", 0.0)),
            str(getattr(mapping, "mapping_id", "")),
        ),
    )


def _classify_listener(
    mapping: object | None,
    own_binding: tuple[str, str] | None,
    speaker_intent: tuple[str, str],
    target_referent: tuple[str, str] | None = None,
    target_referents: Sequence[tuple[str, str]] = (),
) -> tuple[
    TranslationInterpretationSource,
    TranslationOutcome,
    tuple[str, str] | None,
    str | None,
    str | None,
]:
    if mapping is None:
        if own_binding is None:
            return (
                TranslationInterpretationSource.NONE,
                TranslationOutcome.UNRESOLVED,
                None,
                None,
                None,
            )
        outcome = (
            TranslationOutcome.EXACT
            if own_binding == speaker_intent
            else TranslationOutcome.WRONG
        )
        return (
            TranslationInterpretationSource.OWN_BINDING,
            outcome,
            own_binding,
            None,
            None,
        )
    targets = getattr(mapping, "targets", ()) or ()
    fit = str(getattr(getattr(mapping, "fit", None), "value", ""))
    if len(targets) > 1:
        if target_referents and target_referents[0] != speaker_intent:
            if speaker_intent in target_referents[1:]:
                return (
                    TranslationInterpretationSource.MAPPING,
                    TranslationOutcome.PARTIAL,
                    speaker_intent,
                    str(getattr(mapping, "mapping_id", "")),
                    _dominant_channel(mapping),
                )
        return (
            TranslationInterpretationSource.MAPPING,
            TranslationOutcome.AMBIGUOUS,
            None,
            str(getattr(mapping, "mapping_id", "")),
            _dominant_channel(mapping),
        )
    if fit in {"ambiguous", "partial"}:
        return (
            TranslationInterpretationSource.MAPPING,
            TranslationOutcome.AMBIGUOUS,
            None,
            str(getattr(mapping, "mapping_id", "")),
            _dominant_channel(mapping),
        )
    if not targets:
        return (
            TranslationInterpretationSource.MAPPING,
            TranslationOutcome.UNRESOLVED,
            None,
            str(getattr(mapping, "mapping_id", "")),
            _dominant_channel(mapping),
        )
    target = targets[0]
    kind = str(getattr(getattr(target, "referent_kind", None), "value", ""))
    if not isinstance(kind, str) or not kind:
        return (
            TranslationInterpretationSource.MAPPING,
            TranslationOutcome.UNRESOLVED,
            None,
            str(getattr(mapping, "mapping_id", "")),
            _dominant_channel(mapping),
        )
    if target_referent is None:
        outcome = (
            TranslationOutcome.EXACT
            if kind == speaker_intent[0]
            else TranslationOutcome.WRONG
        )
        listener_referent = None if outcome is TranslationOutcome.WRONG else (
            kind,
            speaker_intent[1],
        )
    else:
        listener_referent = target_referent
        outcome = (
            TranslationOutcome.EXACT
            if target_referent == speaker_intent
            else TranslationOutcome.WRONG
        )
    return (
        TranslationInterpretationSource.MAPPING,
        outcome,
        listener_referent,
        str(getattr(mapping, "mapping_id", "")),
        _dominant_channel(mapping),
    )


def _dominant_channel(mapping: object) -> str | None:
    counts = Counter(
        _enum_value(getattr(item, "channel", "context"))
        for item in getattr(mapping, "evidence", ()) or ()
    )
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def translation_influence_rows_from_ledgers(
    translation_ledgers: Sequence[object],
    messages: Sequence[TranslationMessageRow] = (),
    mapping_rows: Sequence[TranslationMappingRow] = (),
) -> tuple[TranslationInfluenceRow, ...]:
    """Derive overlay, symbolic, and outbound influence rows."""
    rows: list[TranslationInfluenceRow] = []
    target_by_mapping = {
        row.mapping_id: (
            row.target_label_digests[0]
            if row.target_label_digests
            else translation_label_digest("unknown")
        )
        for row in mapping_rows
    }
    for message in messages:
        if message.mapping_id is None:
            continue
        if message.outcome not in {
            TranslationOutcome.EXACT,
            TranslationOutcome.WRONG,
        }:
            continue
        rows.append(
            TranslationInfluenceRow(
                owner_id=message.listener_id,
                mapping_id=message.mapping_id,
                message_id=message.message_id,
                source_digest=message.source_digest,
                target_label_digest=target_by_mapping.get(
                    message.mapping_id, translation_label_digest("unknown")
                ),
                effect_kind="communicated_memory_overlay",
                outcome="applied",
                tick=message.tick,
                actor_digest=None,
                confidence_band=message.confidence_band,
            )
        )
    for ledger in translation_ledgers:
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        if not isinstance(owner, str):
            continue
        for mapping in getattr(ledger, "mappings", ()) or ():
            for application in getattr(mapping, "applications", ()) or ():
                kind = str(getattr(getattr(application, "kind", None), "value", ""))
                if not kind:
                    continue
                target = None
                if getattr(application, "target_binding_id", None) is not None:
                    for item in getattr(mapping, "targets", ()) or ():
                        if getattr(item, "binding_id", None) == (
                            application.target_binding_id
                        ):
                            target = item
                            break
                target_items = tuple(getattr(mapping, "targets", None) or ())
                if target is None and target_items:
                    target = target_items[0]
                target_token = getattr(target, "label_token", None)
                rows.append(
                    TranslationInfluenceRow(
                        owner_id=owner,
                        mapping_id=str(getattr(mapping, "mapping_id", "")),
                        message_id=getattr(application, "message_id", None),
                        source_digest=str(getattr(mapping, "source_digest", "")),
                        target_label_digest=translation_label_digest(
                            target_token if isinstance(target_token, str) else "unknown"
                        ),
                        effect_kind=kind,
                        outcome=str(
                            getattr(getattr(application, "outcome", None), "value", "")
                        ),
                        tick=int(getattr(application, "tick", 0)),
                        actor_digest=None,
                        confidence_band=_strength_band(mapping),
                        command_kind=getattr(application, "command_kind", None),
                    )
                )
    return tuple(rows)


def translation_analysis_inputs_from_harvest(
    *,
    translation_ledgers: Sequence[object] | None = None,
    naming_ledgers: Sequence[object] | None = None,
    events: Sequence[object] = (),
    communities: Sequence[object] = (),
    expected_owner_count: int = 0,
    owner_entity_ids: Mapping[str, str] | None = None,
) -> TranslationAnalysisInputs:
    mappings = translation_mapping_rows_from_ledgers(
        tuple(translation_ledgers or ()), tuple(naming_ledgers or ())
    )
    messages = translation_message_rows_from_events(
        tuple(events),
        tuple(translation_ledgers or ()),
        tuple(naming_ledgers or ()),
        tuple(communities),
        owner_entity_ids,
    )
    influences = translation_influence_rows_from_ledgers(
        tuple(translation_ledgers or ()), messages, mappings
    )
    return TranslationAnalysisInputs(
        mappings=mappings,
        messages=messages,
        influences=influences,
        communities=tuple(communities),
        expected_owner_count=expected_owner_count,
    )


@dataclass(frozen=True, slots=True)
class TranslationLearningResult:
    mapping_count: int
    active_count: int
    candidate_count: int
    retired_count: int
    fit_counts: Mapping[str, int]
    target_count: int
    multi_target_count: int
    evidence_count: int
    usage_count: int
    channel_counts: Mapping[str, int]
    strength_band_counts: Mapping[str, int]
    first_tick: int | None
    last_tick: int | None
    coverage: MetricCoverage


def compute_translation_learning(
    inputs: TranslationAnalysisInputs,
) -> TranslationLearningResult:
    rows = inputs.mappings
    fit_counts = Counter(row.fit for row in rows)
    channel_counts = Counter(channel for row in rows for channel in row.channels)
    band_counts = Counter(row.strength_band for row in rows)
    observed = len({row.owner_id for row in rows})
    expected = inputs.expected_owner_count
    coverage = MetricCoverage(
        observed=observed,
        expected=expected,
        ratio=None if expected == 0 else quantize_float(observed / expected),
    )
    return TranslationLearningResult(
        mapping_count=len(rows),
        active_count=sum(1 for row in rows if row.status == "active"),
        candidate_count=sum(1 for row in rows if row.status == "candidate"),
        retired_count=sum(1 for row in rows if row.status == "retired"),
        fit_counts=dict(sorted(fit_counts.items())),
        target_count=sum(len(row.target_label_digests) for row in rows),
        multi_target_count=sum(
            1 for row in rows if len(row.target_label_digests) > 1
        ),
        evidence_count=sum(row.evidence_count for row in rows),
        usage_count=sum(row.usage_count for row in rows),
        channel_counts=dict(sorted(channel_counts.items())),
        strength_band_counts=dict(sorted(band_counts.items())),
        first_tick=min((row.first_tick for row in rows), default=None),
        last_tick=max((row.last_tick for row in rows), default=None),
        coverage=coverage,
    )


def compute_translation_learning_metric(
    result: TranslationLearningResult, *, run_id: str, input_revision: str
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.TRANSLATION_LEARNING)
    values: dict[str, object] = {
        "mapping_count": result.mapping_count,
        "active_count": result.active_count,
        "candidate_count": result.candidate_count,
        "retired_count": result.retired_count,
        "fit_counts": _pairs(result.fit_counts),
        "target_count": result.target_count,
        "multi_target_count": result.multi_target_count,
        "evidence_count": result.evidence_count,
        "usage_count": result.usage_count,
        "channel_counts": _pairs(result.channel_counts),
        "strength_band_counts": _pairs(result.strength_band_counts),
    }
    if result.first_tick is not None:
        values["first_tick"] = result.first_tick
    if result.last_tick is not None:
        values["last_tick"] = result.last_tick
    return _document(
        spec=spec,
        run_id=run_id,
        input_revision=input_revision,
        coverage=result.coverage,
        availability=(
            MetricAvailability.ABSENT
            if result.mapping_count == 0
            else MetricAvailability.PRESENT
        ),
        values=values,
        source_kind="translation_learning",
        notes_code="descriptive_subjective_mapping_inventory",
    )


@dataclass(frozen=True, slots=True)
class CrossGroupTranslationResult:
    delivered_count: int
    mapped_count: int
    unmapped_count: int
    mapping_source_count: int
    own_binding_source_count: int
    exact_count: int
    partial_count: int
    ambiguous_count: int
    wrong_count: int
    unresolved_count: int
    unresolved_intent_count: int
    cross_community_pair_count: int
    community_pair_count: int
    dominant_channel_counts: Mapping[str, int]
    mean_confidence_exact: float | None
    mean_confidence_wrong: float | None
    coverage: MetricCoverage


def compute_cross_group_translation(
    inputs: TranslationAnalysisInputs,
) -> CrossGroupTranslationResult:
    rows = inputs.messages
    pairs = {
        (row.speaker_id, row.listener_id)
        for row in rows
        if row.cross_community
    }
    communities = {
        str(getattr(community, "community_id", "")) for community in inputs.communities
    }
    outcomes = Counter(row.outcome for row in rows if row.cross_community)
    exact = outcomes.get(TranslationOutcome.EXACT, 0)
    wrong = outcomes.get(TranslationOutcome.WRONG, 0)
    exact_conf = [
        row.confidence_band
        for row in rows
        if row.cross_community and row.outcome is TranslationOutcome.EXACT
    ]
    wrong_conf = [
        row.confidence_band
        for row in rows
        if row.cross_community and row.outcome is TranslationOutcome.WRONG
    ]
    band_value = {"low": 0.2, "mid": 0.5, "high": 0.85}
    channel_counts = Counter(
        row.dominant_channel
        for row in rows
        if row.cross_community and row.dominant_channel is not None
    )
    observed = len(pairs)
    expected = len(communities) * (len(communities) - 1)
    return CrossGroupTranslationResult(
        delivered_count=sum(1 for row in rows if row.cross_community),
        mapped_count=sum(
            1
            for row in rows
            if row.cross_community
            and row.interpretation_source is TranslationInterpretationSource.MAPPING
        ),
        unmapped_count=sum(
            1
            for row in rows
            if row.cross_community
            and row.interpretation_source is TranslationInterpretationSource.NONE
        ),
        mapping_source_count=sum(
            1
            for row in rows
            if row.cross_community
            and row.interpretation_source is TranslationInterpretationSource.MAPPING
        ),
        own_binding_source_count=sum(
            1
            for row in rows
            if row.cross_community
            and row.interpretation_source
            is TranslationInterpretationSource.OWN_BINDING
        ),
        exact_count=exact,
        partial_count=outcomes.get(TranslationOutcome.PARTIAL, 0),
        ambiguous_count=outcomes.get(TranslationOutcome.AMBIGUOUS, 0),
        wrong_count=wrong,
        unresolved_count=outcomes.get(TranslationOutcome.UNRESOLVED, 0),
        unresolved_intent_count=outcomes.get(TranslationOutcome.UNRESOLVED_INTENT, 0),
        cross_community_pair_count=len(pairs),
        community_pair_count=max(0, len(communities) * (len(communities) - 1) // 2),
        dominant_channel_counts=dict(sorted(channel_counts.items())),
        mean_confidence_exact=(
            None
            if not exact_conf
            else quantize_float(
                sum(band_value[band] for band in exact_conf) / len(exact_conf)
            )
        ),
        mean_confidence_wrong=(
            None
            if not wrong_conf
            else quantize_float(
                sum(band_value[band] for band in wrong_conf) / len(wrong_conf)
            )
        ),
        coverage=MetricCoverage(
            observed=observed,
            expected=expected,
            ratio=None if expected == 0 else quantize_float(observed / expected),
        ),
    )


def compute_cross_group_translation_metric(
    result: CrossGroupTranslationResult, *, run_id: str, input_revision: str
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.CROSS_GROUP_TRANSLATION)
    accuracy_denominator = (
        result.exact_count
        + result.partial_count
        + result.ambiguous_count
        + result.wrong_count
    )
    rates = {
        "exact_rate": (
            None
            if accuracy_denominator == 0
            else quantize_float(result.exact_count / accuracy_denominator)
        ),
        "partial_rate": (
            None
            if accuracy_denominator == 0
            else quantize_float(result.partial_count / accuracy_denominator)
        ),
        "ambiguous_rate": (
            None
            if accuracy_denominator == 0
            else quantize_float(result.ambiguous_count / accuracy_denominator)
        ),
        "wrong_rate": (
            None
            if accuracy_denominator == 0
            else quantize_float(result.wrong_count / accuracy_denominator)
        ),
    }
    values: dict[str, object] = {
        "delivered_count": result.delivered_count,
        "mapped_count": result.mapped_count,
        "unmapped_count": result.unmapped_count,
        "mapping_source_count": result.mapping_source_count,
        "own_binding_source_count": result.own_binding_source_count,
        "exact_count": result.exact_count,
        "partial_count": result.partial_count,
        "ambiguous_count": result.ambiguous_count,
        "wrong_count": result.wrong_count,
        "unresolved_count": result.unresolved_count,
        "unresolved_intent_count": result.unresolved_intent_count,
        "cross_community_pair_count": result.cross_community_pair_count,
        "community_pair_count": result.community_pair_count,
        "dominant_channel_counts": _pairs(result.dominant_channel_counts),
        "ratios": ";".join(
            f"{key}:{value}" for key, value in rates.items() if value is not None
        ),
    }
    if result.mean_confidence_exact is not None:
        values["mean_confidence_exact"] = result.mean_confidence_exact
    if result.mean_confidence_wrong is not None:
        values["mean_confidence_wrong"] = result.mean_confidence_wrong
    return _document(
        spec=spec,
        run_id=run_id,
        input_revision=input_revision,
        coverage=result.coverage,
        availability=(
            MetricAvailability.ABSENT
            if result.delivered_count == 0
            else MetricAvailability.PRESENT
        ),
        values=values,
        source_kind="cross_group_translation",
        notes_code="descriptive_intent_proxy_not_objective_truth",
    )


@dataclass(frozen=True, slots=True)
class TranslationInfluenceResult:
    overlay_count: int
    translated_relation_count: int
    symbolic_interpretation_count: int
    outbound_rewrite_count: int
    talk_rewrite_count: int
    ask_rewrite_count: int
    tell_rewrite_count: int
    wrong_mapping_influence_count: int
    ambiguous_skip_count: int
    affected_owner_count: int
    coverage: MetricCoverage


def compute_translation_influence(
    inputs: TranslationAnalysisInputs,
) -> TranslationInfluenceResult:
    rows = inputs.influences
    effect = Counter(row.effect_kind for row in rows)
    owners = {row.owner_id for row in rows}
    command_mix = Counter(
        row.command_kind
        for row in rows
        if row.effect_kind == "outbound_term" and row.command_kind is not None
    )
    wrong_outcomes = {
        row.mapping_id
        for row in inputs.messages
        if row.outcome is TranslationOutcome.WRONG
    }
    return TranslationInfluenceResult(
        overlay_count=effect.get("communicated_memory_overlay", 0),
        translated_relation_count=effect.get("communicated_memory_overlay", 0),
        symbolic_interpretation_count=effect.get("symbolic_interpretation", 0),
        outbound_rewrite_count=effect.get("outbound_term", 0),
        talk_rewrite_count=command_mix.get("talk", 0),
        ask_rewrite_count=command_mix.get("ask", 0),
        tell_rewrite_count=command_mix.get("tell", 0),
        wrong_mapping_influence_count=sum(
            1 for row in rows if row.mapping_id in wrong_outcomes
        ),
        ambiguous_skip_count=sum(1 for row in rows if row.outcome == "ambiguous"),
        affected_owner_count=len(owners),
        coverage=MetricCoverage(
            observed=len(owners),
            expected=inputs.expected_owner_count,
            ratio=(
                None
                if inputs.expected_owner_count == 0
                else quantize_float(len(owners) / inputs.expected_owner_count)
            ),
        ),
    )


def compute_translation_influence_metric(
    result: TranslationInfluenceResult, *, run_id: str, input_revision: str
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.TRANSLATION_INFLUENCE)
    total = (
        result.overlay_count
        + result.symbolic_interpretation_count
        + result.outbound_rewrite_count
    )
    return _document(
        spec=spec,
        run_id=run_id,
        input_revision=input_revision,
        coverage=result.coverage,
        availability=(
            MetricAvailability.ABSENT if total == 0 else MetricAvailability.PRESENT
        ),
        values={
            "overlay_count": result.overlay_count,
            "translated_relation_count": result.translated_relation_count,
            "symbolic_interpretation_count": result.symbolic_interpretation_count,
            "outbound_rewrite_count": result.outbound_rewrite_count,
            "talk_rewrite_count": result.talk_rewrite_count,
            "ask_rewrite_count": result.ask_rewrite_count,
            "tell_rewrite_count": result.tell_rewrite_count,
            "wrong_mapping_influence_count": result.wrong_mapping_influence_count,
            "ambiguous_skip_count": result.ambiguous_skip_count,
            "affected_owner_count": result.affected_owner_count,
        },
        source_kind="translation_influence",
        notes_code="descriptive_association_not_causal",
    )


def _pairs(values: Mapping[str, int]) -> str:
    return ";".join(f"{key}:{values[key]}" for key in sorted(values))


def _document(
    *,
    spec: MetricSpecification,
    run_id: str,
    input_revision: str,
    coverage: MetricCoverage,
    availability: MetricAvailability,
    values: Mapping[str, object],
    source_kind: str,
    notes_code: str,
) -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=require_stable_id("run_id", run_id),
        input_revision=require_stable_id("input_revision", input_revision),
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind=source_kind,
            source_ids=(),
            notes_code=notes_code,
        ),
    )
