"""Deterministic scripted reconstructor for controlled drift proofs.

Applies a versioned schedule of structured edits across successive recalls.
Never invents objective authority and never reads WorldEvent content.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from agents.models import AgentId
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryRelation,
    MemorySituationContext,
    MentionId,
    RecallEvidence,
    ReconstructedMemory,
    RelationEndpoint,
    RelationEndpointKind,
    validate_reconstructed_memory,
)

__all__ = [
    "SCRIPTED_DRIFT_SCHEDULE_VERSION",
    "DriftEdit",
    "ScriptedDriftReconstructor",
    "apply_drift_edit",
    "project_primary_source",
]

SCRIPTED_DRIFT_SCHEDULE_VERSION: Final[str] = "scripted-drift-v1"


@dataclass(frozen=True, slots=True)
class DriftEdit:
    """One schedule step: remove, mutate, and/or add structured details."""

    remove_concepts: frozenset[str] = frozenset()
    mutate_concepts: Mapping[str, str] | None = None
    add_concepts: tuple[str, ...] = ()
    remove_entity_labels: frozenset[str] = frozenset()
    add_entity_labels: tuple[str, ...] = ()
    remove_context_tags: frozenset[str] = frozenset()
    add_context_tags: tuple[str, ...] = ()
    add_relations: tuple[tuple[str, str, str], ...] = ()
    narrative_suffix: str = ""
    confidence_delta: float = 0.0
    salience_delta: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mutate_concepts",
            dict(self.mutate_concepts or {}),
        )


@dataclass(frozen=True, slots=True)
class _WorkingEpisode:
    concepts: tuple[str, ...]
    entity_labels: tuple[str, ...]
    relations: tuple[tuple[str, str, str], ...]
    context_tags: tuple[str, ...]
    narrative: str
    confidence: float
    salience: float


def project_primary_source(evidence: RecallEvidence) -> _WorkingEpisode:
    """Project the rank-1 source into a mutable working episode."""
    if not evidence.sources:
        raise ValueError("ScriptedDriftReconstructor: empty_sources")
    primary = min(evidence.sources, key=lambda item: item.rank)
    return _WorkingEpisode(
        concepts=tuple(item.concept for item in primary.concepts),
        entity_labels=tuple(item.label for item in primary.entities),
        relations=tuple(
            (
                item.predicate,
                item.subject.mention_id.value,
                item.object.mention_id.value,
            )
            for item in primary.relations
        ),
        context_tags=tuple(primary.context.tags),
        narrative="",
        confidence=primary.confidence,
        salience=primary.emotional_salience,
    )


def apply_drift_edit(episode: _WorkingEpisode, edit: DriftEdit) -> _WorkingEpisode:
    """Apply one versioned edit; pure and deterministic."""
    mutate = dict(edit.mutate_concepts or {})
    concepts: list[str] = []
    for concept in episode.concepts:
        if concept in edit.remove_concepts:
            continue
        concepts.append(mutate.get(concept, concept))
    for concept in edit.add_concepts:
        if concept not in concepts:
            concepts.append(concept)

    entity_labels = [
        label
        for label in episode.entity_labels
        if label not in edit.remove_entity_labels
    ]
    for label in edit.add_entity_labels:
        if label not in entity_labels:
            entity_labels.append(label)

    tags = [tag for tag in episode.context_tags if tag not in edit.remove_context_tags]
    for tag in edit.add_context_tags:
        if tag not in tags:
            tags.append(tag)

    relations = list(episode.relations)
    for relation in edit.add_relations:
        if relation not in relations:
            relations.append(relation)

    confidence = max(0.0, min(1.0, episode.confidence + edit.confidence_delta))
    salience = max(0.0, min(1.0, episode.salience + edit.salience_delta))
    narrative = episode.narrative
    if edit.narrative_suffix:
        narrative = (
            f"{narrative}{edit.narrative_suffix}"
            if narrative
            else edit.narrative_suffix
        )
    if not narrative:
        narrative = "scripted:" + ",".join(concepts) if concepts else "scripted:empty"

    return _WorkingEpisode(
        concepts=tuple(concepts),
        entity_labels=tuple(entity_labels),
        relations=tuple(relations),
        context_tags=tuple(tags),
        narrative=narrative[:512],
        confidence=confidence,
        salience=salience,
    )


class ScriptedDriftReconstructor:
    """Versioned schedule of edits applied on successive reconstruct calls.

    Call ``N`` applies ``schedule[min(N, len(schedule)-1)]`` cumulatively from
    the primary source (all steps ``0..N`` inclusive when ``N < len``).
    """

    schedule_version: Final[str] = SCRIPTED_DRIFT_SCHEDULE_VERSION

    def __init__(self, schedule: Sequence[DriftEdit]) -> None:
        if not schedule:
            raise ValueError("ScriptedDriftReconstructor: empty_schedule")
        self._schedule = tuple(schedule)
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def schedule(self) -> tuple[DriftEdit, ...]:
        return self._schedule

    def reset(self) -> None:
        self._call_count = 0

    def expected_episode_after(
        self, evidence: RecallEvidence, steps: int
    ) -> _WorkingEpisode:
        """Pure projection of the cumulative schedule through ``steps`` recalls."""
        episode = project_primary_source(evidence)
        limit = max(0, min(steps, len(self._schedule)))
        for index in range(limit):
            episode = apply_drift_edit(episode, self._schedule[index])
        return episode

    async def reconstruct(self, evidence: RecallEvidence) -> ReconstructedMemory:
        if type(evidence) is not RecallEvidence:
            raise TypeError("ScriptedDriftReconstructor: invalid_evidence")
        if type(evidence.owner_id) is not AgentId:
            raise TypeError("ScriptedDriftReconstructor: invalid_owner")
        if not evidence.sources:
            raise ValueError("ScriptedDriftReconstructor: empty_sources")

        step = self._call_count
        self._call_count += 1
        episode = self.expected_episode_after(evidence, steps=step + 1)

        concepts = tuple(
            ConceptMention(mention_id=MentionId(f"sc-{index}"), concept=concept)
            for index, concept in enumerate(episode.concepts, start=1)
        )
        entities = tuple(
            EntityMention(mention_id=MentionId(f"se-{index}"), label=label)
            for index, label in enumerate(episode.entity_labels, start=1)
        )
        label_to_mention = {
            label: MentionId(f"se-{index}")
            for index, label in enumerate(episode.entity_labels, start=1)
        }
        relations: list[MemoryRelation] = []
        for index, (predicate, subject_key, object_key) in enumerate(
            episode.relations, start=1
        ):
            subject_id = label_to_mention.get(subject_key)
            object_id = label_to_mention.get(object_key)
            if subject_id is None or object_id is None:
                continue
            relations.append(
                MemoryRelation(
                    relation_id=MentionId(f"sr-{index}"),
                    predicate=predicate,
                    subject=RelationEndpoint(
                        kind=RelationEndpointKind.ENTITY,
                        mention_id=subject_id,
                    ),
                    object=RelationEndpoint(
                        kind=RelationEndpointKind.ENTITY,
                        mention_id=object_id,
                    ),
                )
            )

        source_ids = tuple(item.memory_id for item in evidence.sources)
        generation = 1 + max(item.generation for item in evidence.sources)
        reconstructed = ReconstructedMemory(
            reconstruction_id=evidence.reconstruction_id,
            owner_id=evidence.owner_id,
            narrative=episode.narrative,
            concepts=concepts,
            entities=entities,
            relations=tuple(relations),
            context=MemorySituationContext(tags=episode.context_tags),
            confidence=episode.confidence,
            emotional_salience=episode.salience,
            source_memory_ids=source_ids,
            generation=generation,
            reconstructed_at_tick=evidence.current_tick,
            policy_id=evidence.policy.policy_id,
            policy_version=evidence.policy.version,
            used_provider=False,
            fallback_used=False,
            prompt_version=None,
            schema_version=self.schedule_version,
        )
        return validate_reconstructed_memory(reconstructed, evidence=evidence)
