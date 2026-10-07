"""Owner-scoped opt-in artifact interpretation.

Meaning stays private. Updates read one owner's Observation and prior ledger
only. They never read WorldState, WorldEvent, PhysicalRules, another owner's
ledger, or analysis/metric documents. Observation presence alone does not
download marks into episodic memory — that path is
``ArtifactInterpretationMemoryUpdateHook`` only.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.artifacts import ArtifactKind, ArtifactRelation
from world.identifiers import EntityId, EventId, require_exact_nonneg_int
from world.models import LifeStatus
from world.observations import Observation, ObservedArtifact

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.artifacts")

ARTIFACT_INTERPRETATION_MEMORY_POLICY_VERSION: Final[str] = (
    "artifact-interpretation-memory.v1"
)
_MAX_INTERPRETATIONS: Final[int] = 16
_DISTORTION_VISIBILITY: Final[float] = 0.75
_DISTORTION_FATIGUE: Final[float] = 0.70
_CONFIDENCE_CLEAN: Final[float] = 0.85
_CONFIDENCE_DISTORTED: Final[float] = 0.55
_PENALTY: Final[float] = 0.30
_CONCEPT_PREFIX: Final[str] = "artifact_reading:"
_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "unresolved_entity",
        "no_candidate",
    }
)
_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {"WorldState", "WorldEvent", "PhysicalRules", "MetricDocument"}
)

__all__ = [
    "ARTIFACT_INTERPRETATION_MEMORY_POLICY_VERSION",
    "ArtifactInterpretation",
    "ArtifactInterpretationLedger",
    "ArtifactInterpretationMemoryUpdateHook",
    "ArtifactInterpretationMode",
    "ArtifactReadingRelation",
    "apply_artifact_interpretation_update",
    "artifact_inscribe_command",
    "artifact_inscribe_penalties",
    "artifact_inscribe_preferred",
    "empty_artifact_interpretation_ledger",
    "require_owner_artifact_interpretations",
]


class ArtifactInterpretationMode(StrEnum):
    """Opt-in private reading of objective marks. Default off.

    Lockstep with runner ``artifact_interpretation_mode`` (Task 8). This is not
    a ``V2CapabilityFlags`` slot. ``DISABLED`` leaves the snapshot field unset
    and does not compile artifact commands from cognition.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "artifact_interpretation_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _reject_forbidden(value: object) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    name = type(value).__name__
    module = type(value).__module__
    if (
        name in _FORBIDDEN_TYPES
        or module.startswith("analysis")
        or module.startswith("analysis.")
        or module.startswith("world._")
    ):
        raise TypeError(f"{name}: forbidden_input")
    if isinstance(value, Mapping):
        # Metric/analysis document duck-type: mapping with family-like keys.
        keys = {str(key) for key in value}
        if "metric_family" in keys or "availability" in keys:
            raise TypeError(f"{name}: forbidden_input")


@dataclass(frozen=True, slots=True)
class ArtifactReadingRelation:
    """Private reading of one objective subject/predicate/object triple."""

    subject: str
    predicate: str
    object: str

    def __post_init__(self) -> None:
        for field_name in ("subject", "predicate", "object"):
            token = getattr(self, field_name)
            if not isinstance(token, str) or not token:
                raise _fail(f"reading_relations.{field_name}", "invalid_type")


@dataclass(frozen=True, slots=True)
class ArtifactInterpretation:
    """One owner's private reading of one observed artifact revision."""

    artifact_id: EntityId
    observed_revision: int
    reading_marks: tuple[str, ...]
    reading_relations: tuple[ArtifactReadingRelation, ...]
    confidence: float
    distorted: bool
    source_tick: int
    source_event_id: EventId | None = None

    def __post_init__(self) -> None:
        if type(self.artifact_id) is not EntityId:
            raise _fail("artifact_id", "invalid_type")
        if (
            isinstance(self.observed_revision, bool)
            or type(self.observed_revision) is not int
            or self.observed_revision < 0
        ):
            raise _fail("observed_revision", "invalid_type")
        marks = _require_tuple("reading_marks", self.reading_marks)
        checked_marks: list[str] = []
        for mark in marks:
            if not isinstance(mark, str) or not mark:
                raise _fail("reading_marks", "invalid_type")
            checked_marks.append(mark)
        relations = _require_tuple("reading_relations", self.reading_relations)
        checked_relations: list[ArtifactReadingRelation] = []
        for item in relations:
            if type(item) is not ArtifactReadingRelation:
                raise _fail("reading_relations", "invalid_type")
            checked_relations.append(item)
        confidence = _finite("confidence", self.confidence)
        if confidence < 0.0 or confidence > 1.0:
            raise _fail("confidence", "out_of_range")
        if type(self.distorted) is not bool:
            raise _fail("distorted", "invalid_type")
        object.__setattr__(
            self,
            "source_tick",
            require_exact_nonneg_int(
                "ArtifactInterpretation.source_tick", self.source_tick
            ),
        )
        if (
            self.source_event_id is not None
            and type(self.source_event_id) is not EventId
        ):
            raise _fail("source_event_id", "invalid_type")
        object.__setattr__(self, "reading_marks", tuple(checked_marks))
        object.__setattr__(self, "reading_relations", tuple(checked_relations))
        object.__setattr__(self, "confidence", confidence)


@dataclass(frozen=True, slots=True)
class ArtifactInterpretationLedger:
    """Private readings for one owner. ``None`` means the mode is off."""

    owner_id: AgentId
    interpretations: tuple[ArtifactInterpretation, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        items = _require_tuple("interpretations", self.interpretations)
        checked: list[ArtifactInterpretation] = []
        seen: set[str] = set()
        for item in items:
            if type(item) is not ArtifactInterpretation:
                raise _fail("interpretations", "invalid_type")
            if item.artifact_id.value in seen:
                raise _fail("interpretations", "duplicate_artifact")
            seen.add(item.artifact_id.value)
            checked.append(item)
        if len(checked) > _MAX_INTERPRETATIONS:
            raise _fail("interpretations", "cap_exceeded")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        ordered = tuple(sorted(checked, key=lambda entry: entry.artifact_id.value))
        object.__setattr__(self, "interpretations", ordered)
        object.__setattr__(self, "notices", tuple(checked_notices))
        _LOG.debug(
            "artifact_interpretation_ledger_constructed owner_id=%s entry_count=%s",
            self.owner_id.value,
            len(ordered),
        )


def empty_artifact_interpretation_ledger(
    owner_id: AgentId,
) -> ArtifactInterpretationLedger:
    """Empty owner ledger. Disabled mode does not call this."""
    return ArtifactInterpretationLedger(owner_id=owner_id)


def require_owner_artifact_interpretations(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` is passthrough."""
    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not ArtifactInterpretationLedger:
        _LOG.warning("artifact_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be ArtifactInterpretationLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "artifact_interpretation_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("artifact_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


def _notice(notices: list[str], reason: str) -> None:
    if reason not in notices:
        notices.append(reason)


def _reading_from_relation(relation: ArtifactRelation) -> ArtifactReadingRelation:
    return ArtifactReadingRelation(
        subject=relation.subject,
        predicate=relation.predicate,
        object=relation.object,
    )


def _distortion_trigger(observation: Observation) -> bool:
    visibility = observation.visibility
    if visibility is not None:
        number = _finite("visibility", visibility)
        if number < _DISTORTION_VISIBILITY:
            return True
    body = observation.self_body
    if body is None:
        return False
    fatigue = _finite("fatigue", body.fatigue.value) / 100.0
    return fatigue >= _DISTORTION_FATIGUE


def _interpret_artifact(
    artifact: ObservedArtifact,
    *,
    tick: int,
    distort: bool,
) -> ArtifactInterpretation:
    from world.artifacts import RecordIntegrity

    marks = tuple(artifact.content.marks)
    relations = [_reading_from_relation(item) for item in artifact.content.relations]
    # Damaged / partially-lost records force private distortion (V3-11).
    integrity = getattr(artifact, "integrity", None)
    force_integrity = integrity is not None and integrity is not RecordIntegrity.INTACT
    if force_integrity and not distort:
        _LOG.debug("interpretation_distorted reason=record_integrity")
        distort = True
    if distort:
        if relations:
            relations = relations[:-1]
        return ArtifactInterpretation(
            artifact_id=artifact.entity_id,
            observed_revision=artifact.content_revision,
            reading_marks=marks,
            reading_relations=tuple(relations),
            confidence=_CONFIDENCE_DISTORTED,
            distorted=True,
            source_tick=tick,
            source_event_id=None,
        )
    return ArtifactInterpretation(
        artifact_id=artifact.entity_id,
        observed_revision=artifact.content_revision,
        reading_marks=marks,
        reading_relations=tuple(relations),
        confidence=_CONFIDENCE_CLEAN,
        distorted=False,
        source_tick=tick,
        source_event_id=None,
    )


def apply_artifact_interpretation_update(
    observation: object,
    owner_id: object,
    previous: object = None,
) -> ArtifactInterpretationLedger:
    """Apply one tick of private readings for a single owner.

    Disabled callers do not call this function. Passing world authority or a
    metric document raises ``TypeError``. Cap 16; further new artifacts drop
    with ``cap_exceeded``. Higher ``content_revision`` replaces an entry.
    """
    _LOG.debug(
        "apply_artifact_interpretation_update owner_id=%s tick=%s",
        getattr(owner_id, "value", None),
        getattr(observation, "tick", None),
    )
    for value in (observation, owner_id, previous):
        _reject_forbidden(value)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if previous is not None and type(previous) is not ArtifactInterpretationLedger:
        raise TypeError("previous must be ArtifactInterpretationLedger or None")
    if previous is not None and previous.owner_id != owner_id:
        raise TypeError("ArtifactInterpretationLedger: foreign_ledger")

    notices: list[str] = []
    by_id: dict[str, ArtifactInterpretation] = {}
    if previous is not None:
        for entry in previous.interpretations:
            by_id[entry.artifact_id.value] = entry

    distort = _distortion_trigger(observation)
    tick = observation.tick
    for artifact in observation.artifacts:
        if type(artifact) is not ObservedArtifact:
            raise TypeError("observation.artifacts entries must be ObservedArtifact")
        if type(artifact.kind) is not ArtifactKind:
            raise _fail("kind", "unknown_kind")
        key = artifact.entity_id.value
        existing = by_id.get(key)
        if (
            existing is not None
            and artifact.content_revision <= existing.observed_revision
        ):
            continue
        if existing is None and len(by_id) >= _MAX_INTERPRETATIONS:
            _notice(notices, "cap_exceeded")
            _LOG.warning("cap_exceeded")
            continue
        by_id[key] = _interpret_artifact(artifact, tick=tick, distort=distort)

    ledger = ArtifactInterpretationLedger(
        owner_id=owner_id,
        interpretations=tuple(by_id.values()),
        notices=tuple(notices),
    )
    distorted_count = sum(1 for item in ledger.interpretations if item.distorted)
    _LOG.debug(
        "artifact_interpretation_updated owner_id=%s entry_count=%s distorted_count=%s",
        owner_id.value,
        len(ledger.interpretations),
        distorted_count,
    )
    return ledger


def _future_id(future: object) -> str | None:
    value = getattr(future, "future_id", None)
    return value if isinstance(value, str) and value else None


def _direction_value(future: object) -> str | None:
    direction = getattr(future, "direction", None)
    value = getattr(direction, "value", None)
    return value if isinstance(value, str) else None


def _living_listeners_visible(observation: Observation) -> bool:
    for body in observation.visible_bodies:
        status = getattr(body, "life_status", None)
        if status is LifeStatus.ALIVE:
            return True
        if getattr(status, "value", None) == LifeStatus.ALIVE.value:
            return True
    return False


def _unread_need_to_speak(
    observation: Observation, inbox: Sequence[object] | None
) -> bool:
    if inbox:
        return True
    observer = observation.observer_id
    for communication in observation.communications:
        listener = getattr(communication, "listener_id", None)
        if listener == observer:
            return True
    return False


def artifact_inscribe_preferred(
    observation: object,
    futures: Sequence[object],
    *,
    mode: object | None = None,
    inbox: Sequence[object] | None = None,
) -> bool:
    """True when the locked deposit/inscribe preference should bias futures."""
    _reject_forbidden(observation)
    if mode is not ArtifactInterpretationMode.DETERMINISTIC:
        return False
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if _living_listeners_visible(observation):
        return False
    if _unread_need_to_speak(observation, inbox):
        return False
    return any(_direction_value(future) == "communicate" for future in futures)


def artifact_inscribe_penalties(
    observation: object,
    futures: Sequence[object],
    *,
    mode: object | None = None,
    inbox: Sequence[object] | None = None,
) -> Mapping[str, float]:
    """Penalize non-communicate futures when inscription is preferred.

    Does not construct commands. Missing communicate candidate records
    ``no_candidate`` and returns an empty map.
    """
    _reject_forbidden(observation)
    if mode is not ArtifactInterpretationMode.DETERMINISTIC:
        return {}
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if _living_listeners_visible(observation):
        return {}
    if _unread_need_to_speak(observation, inbox):
        return {}
    communicate_ids = [
        future_id
        for future in futures
        if (future_id := _future_id(future)) is not None
        and _direction_value(future) == "communicate"
    ]
    if not communicate_ids:
        _LOG.info("artifact_command_withheld reason_code=%s", "no_candidate")
        return {}
    penalties: dict[str, float] = {}
    for future in futures:
        future_id = _future_id(future)
        if future_id is None or future_id in communicate_ids:
            continue
        total = penalties.get(future_id, 0.0) + _PENALTY
        if total < 0.0:
            raise _fail("penalty", "negative_penalty")
        penalties[future_id] = total
    _LOG.debug(
        "artifact_inscribe_penalty_applied future_count=%s",
        len(penalties),
    )
    return penalties


def artifact_inscribe_command(
    command: object,
    *,
    observation: object,
    mode: object | None,
    preferred: bool,
    inbox: Sequence[object] | None = None,
) -> object:
    """Compile ``Inscribe`` only when the preferred communicate future won.

    Disabled mode and unmet preference leave the command unchanged. Never
    inserts an artifact command without a preferred win.
    """
    from world.actions import Inscribe, Talk
    from world.artifacts import ArtifactContent, ArtifactKind

    if mode is not ArtifactInterpretationMode.DETERMINISTIC:
        return command
    if not preferred:
        return command
    if type(observation) is not Observation:
        return command
    if _living_listeners_visible(observation) or _unread_need_to_speak(
        observation, inbox
    ):
        _LOG.info("artifact_command_withheld reason_code=%s", "no_candidate")
        return command
    if type(command) is not Talk:
        # Preferred win without a communicate compile path — withhold insert.
        _LOG.info("artifact_command_withheld reason_code=%s", "no_candidate")
        return command
    _LOG.debug(
        "artifact_inscribe_compiled owner_id=%s tick=%s kind=%s",
        observation.observer_id.value,
        observation.tick,
        ArtifactKind.NOTE.value,
    )
    return Inscribe(kind=ArtifactKind.NOTE, content=ArtifactContent(), hold=False)


class ArtifactInterpretationMemoryUpdateHook:
    """Propose WRITE_MEMORY intents for private artifact readings only.

    Policy ``artifact-interpretation-memory.v1``. Concepts are prefixed
    ``artifact_reading:``. Disabled mode returns no intents.
    """

    __slots__ = ("_mode",)

    def __init__(
        self,
        mode: ArtifactInterpretationMode = ArtifactInterpretationMode.DISABLED,
    ) -> None:
        if type(mode) is not ArtifactInterpretationMode:
            raise TypeError("mode must be ArtifactInterpretationMode")
        self._mode = mode

    async def propose_updates(
        self,
        loop_input: object,
        plan: object,
        perception: object,
        memory: object,
        intention: object,
        self_state: object | None = None,
    ) -> tuple[object, ...]:
        _ = plan, memory, intention, self_state
        if self._mode is not ArtifactInterpretationMode.DETERMINISTIC:
            return ()
        from agents.cognition.models import MemoryUpdateIntent, MemoryUpdateKind
        from memory.models import (
            ConceptMention,
            EntityMention,
            MemoryId,
            MemoryLineage,
            MemoryProvenance,
            MemoryRelation,
            MemorySituationContext,
            MemorySourceKind,
            MemoryTrace,
            MentionId,
            RelationEndpoint,
            RelationEndpointKind,
        )

        owner = getattr(loop_input, "agent_id", None)
        observation = getattr(loop_input, "observation", None)
        if type(owner) is not AgentId or type(observation) is not Observation:
            return ()
        snapshot = getattr(loop_input, "snapshot", None)
        prior = None if snapshot is None else getattr(
            snapshot, "artifact_interpretations", None
        )
        if prior is not None and type(prior) is not ArtifactInterpretationLedger:
            prior = None
        ledger = apply_artifact_interpretation_update(observation, owner, prior)
        location_id = getattr(perception, "location_id", None)
        seen: set[str] = set()
        if snapshot is not None:
            for trace in getattr(snapshot, "memories", ()) or ():
                memory_id = getattr(getattr(trace, "memory_id", None), "value", None)
                if isinstance(memory_id, str):
                    seen.add(memory_id)

        intents: list[object] = []
        for entry in ledger.interpretations:
            if entry.source_tick != observation.tick:
                continue
            raw = (
                f"artifact-reading-{owner.value}-{entry.artifact_id.value}"
                f"-r{entry.observed_revision}-t{entry.source_tick}"
            )
            if len(raw) > 128:
                raw = raw[:128]
            memory_id = MemoryId(raw)
            if memory_id.value in seen:
                continue
            concepts: list[ConceptMention] = []
            for index, mark in enumerate(entry.reading_marks):
                concepts.append(
                    ConceptMention(
                        mention_id=MentionId(f"c-mark-{index}"),
                        concept=f"{_CONCEPT_PREFIX}{mark}",
                    )
                )
            entities = (
                EntityMention(
                    mention_id=MentionId("e-artifact"),
                    label="artifact",
                    entity_id=entry.artifact_id,
                ),
            )
            relations: list[MemoryRelation] = []
            for index, relation in enumerate(entry.reading_relations):
                subject_id = MentionId(f"c-rel-s-{index}")
                object_id = MentionId(f"c-rel-o-{index}")
                concepts.append(
                    ConceptMention(
                        mention_id=subject_id,
                        concept=f"{_CONCEPT_PREFIX}{relation.subject}",
                    )
                )
                concepts.append(
                    ConceptMention(
                        mention_id=object_id,
                        concept=f"{_CONCEPT_PREFIX}{relation.object}",
                    )
                )
                relations.append(
                    MemoryRelation(
                        relation_id=MentionId(f"r-reading-{index}"),
                        predicate=f"{_CONCEPT_PREFIX}{relation.predicate}",
                        subject=RelationEndpoint(
                            kind=RelationEndpointKind.CONCEPT,
                            mention_id=subject_id,
                        ),
                        object=RelationEndpoint(
                            kind=RelationEndpointKind.CONCEPT,
                            mention_id=object_id,
                        ),
                    )
                )
            if not concepts and not relations:
                concepts.append(
                    ConceptMention(
                        mention_id=MentionId("c-empty"),
                        concept=f"{_CONCEPT_PREFIX}empty",
                    )
                )
            intents.append(
                MemoryUpdateIntent(
                    owner_id=owner,
                    kind=MemoryUpdateKind.WRITE_MEMORY,
                    memory=MemoryTrace(
                        memory_id=memory_id,
                        owner_id=owner,
                        world_revision=observation.revision,
                        concepts=tuple(concepts[:32]),
                        entities=entities,
                        relations=tuple(relations[:32]),
                        context=MemorySituationContext(
                            location_id=location_id
                            if type(location_id) is EntityId
                            else None,
                            tags=(
                                "artifact_reading",
                                ARTIFACT_INTERPRETATION_MEMORY_POLICY_VERSION,
                            ),
                        ),
                        emotional_salience=0.2,
                        confidence=entry.confidence,
                        provenance=MemoryProvenance(
                            kind=MemorySourceKind.DIRECT_OBSERVATION,
                            source_tick=entry.source_tick,
                            observed_source_id=entry.source_event_id,
                        ),
                        created_tick=observation.tick,
                        source_tick=entry.source_tick,
                        last_access_tick=observation.tick,
                        access_count=0,
                        lineage=MemoryLineage(),
                    ),
                )
            )
            seen.add(memory_id.value)
        _LOG.debug(
            "artifact_interpretation_memory_batch owner_id=%s proposed_count=%s "
            "policy_version=%s",
            owner.value,
            len(intents),
            ARTIFACT_INTERPRETATION_MEMORY_POLICY_VERSION,
        )
        return tuple(intents)
