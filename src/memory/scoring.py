"""Pure deterministic episodic memory scoring and retention decay.

No wall clocks, global RNG, Python ``hash()``, or logging. Scores are finite
floats quantized at :data:`memory.models.SCORE_QUANTUM`.

Recency age semantics default to ``STORAGE`` (``current_tick - created_tick``)
to preserve historical scoring behavior. Callers may select ``EPISODE``
(``current_tick - source_tick``) via :class:`MemoryScoringPolicy`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from memory.models import (
    AccessHistoryMode,
    MemoryAgeSemantics,
    MemoryEmbedding,
    MemoryId,
    MemoryQueryContext,
    MemoryQueryFilters,
    MemoryRankedHit,
    MemoryRetentionPolicy,
    MemoryScoreBreakdown,
    MemoryScoringPolicy,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    quantize_score,
)

__all__ = [
    "cosine_similarity",
    "logical_age_ticks",
    "matches_filters",
    "rank_traces",
    "retention_strength",
    "score_trace",
    "should_forget",
]

_ACCESS_SATURATION: int = 8


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Exact cosine similarity mapped into ``[0, 1]`` (``(-1,1) -> (0,1)``)."""
    if len(left) != len(right):
        raise ValueError("cosine_similarity: dimension_mismatch")
    if not left:
        raise ValueError("cosine_similarity: empty")
    dot = 0.0
    left_norm_sq = 0.0
    right_norm_sq = 0.0
    for a, b in zip(left, right, strict=True):
        if isinstance(a, bool) or not isinstance(a, (int, float)):
            raise TypeError("cosine_similarity: invalid_component")
        if isinstance(b, bool) or not isinstance(b, (int, float)):
            raise TypeError("cosine_similarity: invalid_component")
        af = float(a)
        bf = float(b)
        if not math.isfinite(af) or not math.isfinite(bf):
            raise ValueError("cosine_similarity: non_finite")
        dot += af * bf
        left_norm_sq += af * af
        right_norm_sq += bf * bf
    if left_norm_sq == 0.0 or right_norm_sq == 0.0:
        return 0.0
    raw = dot / math.sqrt(left_norm_sq * right_norm_sq)
    if raw < -1.0:
        raw = -1.0
    elif raw > 1.0:
        raw = 1.0
    return (raw + 1.0) * 0.5


def logical_age_ticks(
    trace: MemoryTrace,
    *,
    current_tick: int,
    age_semantics: MemoryAgeSemantics,
) -> int:
    """Return non-negative logical age under the selected semantics."""
    if type(trace) is not MemoryTrace:
        raise TypeError("logical_age_ticks: invalid_trace")
    if type(age_semantics) is not MemoryAgeSemantics:
        raise TypeError("logical_age_ticks: invalid_semantics")
    if age_semantics is MemoryAgeSemantics.EPISODE:
        return max(0, current_tick - trace.source_tick)
    if age_semantics is MemoryAgeSemantics.STORAGE:
        return max(0, current_tick - trace.created_tick)
    raise ValueError("logical_age_ticks: unsupported_semantics")


def matches_filters(trace: MemoryTrace, filters: MemoryQueryFilters) -> bool:
    """Return whether ``trace`` passes structured filters (pre-scoring)."""
    if type(trace) is not MemoryTrace:
        raise TypeError("matches_filters: invalid_trace")
    if type(filters) is not MemoryQueryFilters:
        raise TypeError("matches_filters: invalid_filters")
    if filters.require_active and trace.forgotten_at_tick is not None:
        return False
    if (
        filters.created_tick_min is not None
        and trace.created_tick < filters.created_tick_min
    ):
        return False
    if (
        filters.created_tick_max is not None
        and trace.created_tick > filters.created_tick_max
    ):
        return False
    if (
        filters.source_tick_min is not None
        and trace.source_tick < filters.source_tick_min
    ):
        return False
    if (
        filters.source_tick_max is not None
        and trace.source_tick > filters.source_tick_max
    ):
        return False
    if (
        filters.location_id is not None
        and trace.context.location_id != filters.location_id
    ):
        return False
    if (
        filters.provenance_kind is not None
        and trace.provenance.kind is not filters.provenance_kind
    ):
        return False
    if filters.min_confidence is not None and trace.confidence < filters.min_confidence:
        return False
    if (
        filters.min_salience is not None
        and trace.emotional_salience < filters.min_salience
    ):
        return False
    if filters.concepts:
        present = {item.concept for item in trace.concepts}
        if any(concept not in present for concept in filters.concepts):
            return False
    if filters.entity_ids:
        present_ids = {
            item.entity_id for item in trace.entities if item.entity_id is not None
        }
        if any(entity_id not in present_ids for entity_id in filters.entity_ids):
            return False
    if filters.relation_predicates:
        present_preds = {item.predicate for item in trace.relations}
        if any(pred not in present_preds for pred in filters.relation_predicates):
            return False
    if filters.context_tags:
        present_tags = set(trace.context.tags)
        if any(tag not in present_tags for tag in filters.context_tags):
            return False
    return True


def score_trace(
    trace: MemoryTrace,
    *,
    policy: MemoryScoringPolicy,
    current_tick: int,
    context: MemoryQueryContext,
    query_embedding: MemoryEmbedding | None,
    trace_embedding: MemoryEmbedding | None,
) -> tuple[float, MemoryScoreBreakdown, tuple[MentionId, ...], tuple[MentionId, ...]]:
    """Compute quantized weighted score and matched mention IDs."""
    if type(trace) is not MemoryTrace:
        raise TypeError("score_trace: invalid_trace")
    if type(policy) is not MemoryScoringPolicy:
        raise TypeError("score_trace: invalid_policy")
    if type(context) is not MemoryQueryContext:
        raise TypeError("score_trace: invalid_context")
    if current_tick < 0:
        raise ValueError("score_trace: invalid_tick")

    semantic = 0.0
    if policy.weights.semantic_relevance > 0.0:
        if query_embedding is None or trace_embedding is None:
            semantic = 0.0
        else:
            if query_embedding.dimension != trace_embedding.dimension:
                raise ValueError("score_trace: embedding_dimension_mismatch")
            semantic = cosine_similarity(query_embedding.vector, trace_embedding.vector)

    age = logical_age_ticks(
        trace, current_tick=current_tick, age_semantics=policy.age_semantics
    )
    recency = 1.0 / (1.0 + float(age))
    salience = trace.emotional_salience
    context_overlap = _context_overlap(trace, context)
    social = _social_relevance(trace, context)
    access = _access_history_score(trace.access_count, policy.access_history_mode)

    breakdown = MemoryScoreBreakdown(
        semantic_relevance=semantic,
        recency=recency,
        emotional_salience=salience,
        current_context_overlap=context_overlap,
        social_relevance=social,
        access_history=access,
    )
    weighted = (
        policy.weights.semantic_relevance * breakdown.semantic_relevance
        + policy.weights.recency * breakdown.recency
        + policy.weights.emotional_salience * breakdown.emotional_salience
        + policy.weights.current_context_overlap * breakdown.current_context_overlap
        + policy.weights.social_relevance * breakdown.social_relevance
        + policy.weights.access_history * breakdown.access_history
    )
    if policy.generation_influence > 0.0:
        generation_factor = float(trace.lineage.generation) / (
            1.0 + float(trace.lineage.generation)
        )
        weighted = (
            1.0 - policy.generation_influence
        ) * weighted + policy.generation_influence * generation_factor
    score = quantize_score(min(1.0, max(0.0, weighted)))
    matched_concepts, matched_entities = _matched_mentions(trace, context)
    return score, breakdown, matched_concepts, matched_entities


def rank_traces(
    traces: Sequence[MemoryTrace],
    *,
    policy: MemoryScoringPolicy,
    current_tick: int,
    filters: MemoryQueryFilters,
    context: MemoryQueryContext,
    query_embedding: MemoryEmbedding | None,
    embeddings: dict[str, MemoryEmbedding] | None,
    limit: int,
) -> tuple[tuple[MemoryRankedHit, ...], int]:
    """Filter, score, and order traces; return dense ranks and candidate count."""
    if limit < 1:
        raise ValueError("rank_traces: invalid_limit")
    candidates: list[MemoryTrace] = []
    for trace in traces:
        if matches_filters(trace, filters):
            candidates.append(trace)
    scored: list[
        tuple[
            float,
            int,
            str,
            MemoryTrace,
            MemoryScoreBreakdown,
            tuple[MentionId, ...],
            tuple[MentionId, ...],
        ]
    ] = []
    embed_map = embeddings if embeddings is not None else {}
    for trace in candidates:
        score, breakdown, matched_c, matched_e = score_trace(
            trace,
            policy=policy,
            current_tick=current_tick,
            context=context,
            query_embedding=query_embedding,
            trace_embedding=embed_map.get(trace.memory_id.value),
        )
        scored.append(
            (
                score,
                trace.created_tick,
                trace.memory_id.value,
                trace,
                breakdown,
                matched_c,
                matched_e,
            )
        )
    # score DESC, created_tick DESC, memory_id ASC
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    if policy.ancestry_dedup:
        scored = _ancestry_dedup(scored)
    hits: list[MemoryRankedHit] = []
    for index, item in enumerate(scored[:limit], start=1):
        score, _created, _mid, trace, breakdown, matched_c, matched_e = item
        hits.append(
            MemoryRankedHit(
                rank=index,
                trace=trace,
                score=score,
                breakdown=breakdown,
                matched_concept_mention_ids=matched_c,
                matched_entity_mention_ids=matched_e,
                scoring_policy_id=policy.policy_id,
                scoring_policy_version=policy.version,
                retrieval_tick=current_tick,
            )
        )
    return tuple(hits), len(candidates)


def retention_strength(
    *,
    created_tick: int,
    current_tick: int,
    half_life_ticks: int,
) -> float:
    """Deterministic exponential retention from explicit logical ticks."""
    if half_life_ticks < 1:
        raise ValueError("retention_strength: invalid_half_life")
    if current_tick < created_tick:
        raise ValueError("retention_strength: tick_before_created")
    age = current_tick - created_tick
    strength = 0.5 ** (float(age) / float(half_life_ticks))
    return quantize_score(min(1.0, max(0.0, strength)))


def should_forget(
    trace: MemoryTrace,
    *,
    current_tick: int,
    policy: MemoryRetentionPolicy,
) -> bool:
    """Whether a trace should soft-forget under ``policy`` at ``current_tick``."""
    if type(trace) is not MemoryTrace:
        raise TypeError("should_forget: invalid_trace")
    if type(policy) is not MemoryRetentionPolicy:
        raise TypeError("should_forget: invalid_policy")
    if trace.forgotten_at_tick is not None:
        return False
    if trace.expires_at_tick is not None and current_tick >= trace.expires_at_tick:
        return True
    strength = retention_strength(
        created_tick=trace.created_tick,
        current_tick=current_tick,
        half_life_ticks=policy.half_life_ticks,
    )
    return strength < policy.forget_threshold


def _ancestry_dedup(
    scored: list[
        tuple[
            float,
            int,
            str,
            MemoryTrace,
            MemoryScoreBreakdown,
            tuple[MentionId, ...],
            tuple[MentionId, ...],
        ]
    ],
) -> list[
    tuple[
        float,
        int,
        str,
        MemoryTrace,
        MemoryScoreBreakdown,
        tuple[MentionId, ...],
        tuple[MentionId, ...],
    ]
]:
    """Prefer higher-generation descendants over direct ancestors in the result set.

    Dropped ancestors remain available via direct fetch; they are only removed
    from the ranked retrieval window.
    """
    score_by_id = {item[2]: item[0] for item in scored}
    descendants: dict[str, set[str]] = {item[2]: set() for item in scored}
    for item in scored:
        trace = item[3]
        mid = item[2]
        for source in trace.lineage.source_memory_ids:
            if source.value in descendants:
                descendants[source.value].add(mid)
        if (
            trace.lineage.supersedes_memory_id is not None
            and trace.lineage.supersedes_memory_id.value in descendants
        ):
            descendants[trace.lineage.supersedes_memory_id.value].add(mid)

    keep: list[
        tuple[
            float,
            int,
            str,
            MemoryTrace,
            MemoryScoreBreakdown,
            tuple[MentionId, ...],
            tuple[MentionId, ...],
        ]
    ] = []
    for item in scored:
        mid = item[2]
        ancestor_score = item[0]
        child_ids = descendants.get(mid, set())
        if any(score_by_id[child] >= ancestor_score for child in child_ids):
            continue
        keep.append(item)
    return keep


def _context_overlap(trace: MemoryTrace, context: MemoryQueryContext) -> float:
    score = 0.0
    parts = 0
    if context.location_id is not None:
        parts += 1
        if trace.context.location_id == context.location_id:
            score += 1.0
    if context.tags:
        parts += 1
        present = set(trace.context.tags)
        matched = sum(1 for tag in context.tags if tag in present)
        score += matched / float(len(context.tags))
    if parts == 0:
        return 0.0
    return score / float(parts)


def _social_relevance(trace: MemoryTrace, context: MemoryQueryContext) -> float:
    if not context.related_entity_ids:
        return 0.0
    present = {item.entity_id for item in trace.entities if item.entity_id is not None}
    if not present:
        # Communicated speaker counts as a social signal when grounded.
        if (
            trace.provenance.kind is MemorySourceKind.COMMUNICATED
            and trace.provenance.speaker_id is not None
            and trace.provenance.speaker_id in set(context.related_entity_ids)
        ):
            return 1.0
        return 0.0
    matched = sum(1 for entity_id in context.related_entity_ids if entity_id in present)
    return matched / float(len(context.related_entity_ids))


def _access_history_score(access_count: int, mode: AccessHistoryMode) -> float:
    if mode is AccessHistoryMode.FAMILIARITY:
        return min(1.0, float(access_count) / float(_ACCESS_SATURATION))
    if mode is AccessHistoryMode.NOVELTY:
        return 1.0 / (1.0 + float(access_count))
    raise ValueError("access_history: unsupported_mode")


def _matched_mentions(
    trace: MemoryTrace, context: MemoryQueryContext
) -> tuple[tuple[MentionId, ...], tuple[MentionId, ...]]:
    concept_ids = tuple(item.mention_id for item in trace.concepts)
    related = set(context.related_entity_ids)
    entity_ids = tuple(
        item.mention_id
        for item in trace.entities
        if item.entity_id is not None and item.entity_id in related
    )
    return concept_ids, entity_ids


def collect_ancestry_ids(
    traces: Mapping[MemoryId, MemoryTrace],
    root_id: MemoryId,
) -> tuple[MemoryId, ...]:
    """Traverse direct source edges depth-first; reject cycles with a reason code."""
    if root_id not in traces:
        raise ValueError("collect_ancestry_ids: unknown_root")
    ordered: list[MemoryId] = []
    seen: set[str] = set()
    stack = [root_id]
    while stack:
        current = stack.pop()
        if current.value in seen:
            raise ValueError("collect_ancestry_ids: cycle")
        seen.add(current.value)
        ordered.append(current)
        trace = traces[current]
        for source in reversed(trace.lineage.source_memory_ids):
            if source not in traces:
                raise ValueError("collect_ancestry_ids: dangling_source")
            stack.append(source)
    return tuple(ordered)
