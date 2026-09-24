"""Pure deterministic V2 reconstructive memory dynamics.

No wall clocks, global RNG, Python ``hash()``, or logging. All scores are
quantized at :data:`memory.models.SCORE_QUANTUM`. Confusion and competition
are pure functions of cue + trace IDs + tick.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryDistortionCode,
    MemoryDynamicsPolicy,
    MemoryId,
    MemoryQueryContext,
    MemoryRecallContext,
    MemoryRelation,
    MemorySituationContext,
    MemoryTrace,
    RecallAuditRecord,
    RecallEvidence,
    RecallSourceEvidence,
    ReconstructedMemory,
    StrengthDeltaSummary,
    quantize_score,
    validate_reconstructed_memory,
)

__all__ = [
    "DynamicsCandidate",
    "DynamicsReconstructionResult",
    "SemanticizationHint",
    "apply_interference",
    "compete_traces",
    "confidence_degradation",
    "cue_overlap",
    "deterministic_unit",
    "effective_confidence",
    "effective_salience",
    "reconstruct_v2",
    "retrieval_strength",
    "salience_biased_survival",
    "semanticization_trigger",
    "source_confusion_attribution",
    "testing_effect_deltas",
    "trace_similarity",
]

_MODULUS: int = 1_000_003


@dataclass(frozen=True, slots=True)
class DynamicsCandidate:
    """Scored recall candidate for V2 competition."""

    source: RecallSourceEvidence
    access_count: int = 0
    strength: float = 0.0

    def __post_init__(self) -> None:
        if type(self.source) is not RecallSourceEvidence:
            raise TypeError("DynamicsCandidate.source: invalid_type")
        if isinstance(self.access_count, bool) or not isinstance(
            self.access_count, int
        ):
            raise TypeError("DynamicsCandidate.access_count: invalid_type")
        if self.access_count < 0:
            raise ValueError("DynamicsCandidate.access_count: negative")
        if isinstance(self.strength, bool) or not isinstance(
            self.strength, (int, float)
        ):
            raise ValueError("DynamicsCandidate.strength: not_finite")
        number = float(self.strength)
        if not math.isfinite(number):
            raise ValueError("DynamicsCandidate.strength: not_finite")
        object.__setattr__(self, "strength", quantize_score(max(0.0, min(1.0, number))))


@dataclass(frozen=True, slots=True)
class SemanticizationHint:
    """Whether repeated similar episodes should enqueue belief revision."""

    should_revise: bool
    gist_concepts: tuple[str, ...]
    source_memory_ids: tuple[MemoryId, ...]

    def __repr__(self) -> str:
        return (
            f"SemanticizationHint(should_revise={self.should_revise}, "
            f"gist_concept_count={len(self.gist_concepts)}, "
            f"source_count={len(self.source_memory_ids)})"
        )


@dataclass(frozen=True, slots=True)
class DynamicsReconstructionResult:
    """V2 reconstruct output: agent memory + audit (+ optional semanticization)."""

    reconstructed: ReconstructedMemory
    audit: RecallAuditRecord
    semanticization: SemanticizationHint | None = None

    def __repr__(self) -> str:
        return (
            f"DynamicsReconstructionResult("
            f"reconstruction_id={self.reconstructed.reconstruction_id.value!r}, "
            f"audit_source_count={len(self.audit.source_memory_ids)}, "
            f"semanticization={self.semanticization is not None})"
        )


def deterministic_unit(*parts: str) -> float:
    """Map ordered string parts to a quantized unit interval without ``hash()``."""
    acc = 0
    for part in parts:
        if not isinstance(part, str):
            raise TypeError("deterministic_unit: invalid_part")
        for ch in part:
            acc = (acc * 31 + ord(ch)) % _MODULUS
    return quantize_score(acc / float(_MODULUS))


def effective_confidence(
    confidence: float,
    *,
    age_ticks: int,
    salience: float,
    policy: MemoryDynamicsPolicy,
) -> float:
    """Decay confidence with logical age; salience resists decay."""
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("effective_confidence: invalid_policy")
    if isinstance(age_ticks, bool) or not isinstance(age_ticks, int) or age_ticks < 0:
        raise ValueError("effective_confidence: invalid_age")
    conf = _clamp_unit("effective_confidence.confidence", confidence)
    sal = _clamp_unit("effective_confidence.salience", salience)
    resistance = quantize_score(1.0 - policy.salience_resistance * sal)
    decay = quantize_score(policy.decay_rate * float(age_ticks) * resistance)
    return quantize_score(max(policy.confidence_floor, conf * (1.0 - min(1.0, decay))))


def effective_salience(
    salience: float,
    *,
    age_ticks: int,
    policy: MemoryDynamicsPolicy,
) -> float:
    """Decay salience with age; high salience resists its own decay."""
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("effective_salience: invalid_policy")
    if isinstance(age_ticks, bool) or not isinstance(age_ticks, int) or age_ticks < 0:
        raise ValueError("effective_salience: invalid_age")
    sal = _clamp_unit("effective_salience.salience", salience)
    resistance = quantize_score(1.0 - policy.salience_resistance * sal)
    decay = quantize_score(policy.decay_rate * float(age_ticks) * resistance)
    return quantize_score(max(0.0, sal * (1.0 - min(1.0, decay))))


def retrieval_strength(
    *,
    age_ticks: int,
    access_count: int,
    salience: float,
    confidence: float,
    policy: MemoryDynamicsPolicy,
) -> float:
    """Ephemeral retrieval strength from age x access x salience x confidence."""
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("retrieval_strength: invalid_policy")
    if isinstance(age_ticks, bool) or not isinstance(age_ticks, int) or age_ticks < 0:
        raise ValueError("retrieval_strength: invalid_age")
    if (
        isinstance(access_count, bool)
        or not isinstance(access_count, int)
        or access_count < 0
    ):
        raise ValueError("retrieval_strength: invalid_access_count")
    conf = effective_confidence(
        confidence, age_ticks=age_ticks, salience=salience, policy=policy
    )
    sal = effective_salience(salience, age_ticks=age_ticks, policy=policy)
    access_factor = quantize_score(
        float(access_count) / (1.0 + float(access_count))
    )
    age_factor = quantize_score(1.0 / (1.0 + float(age_ticks)))
    raw = 0.35 * conf + 0.35 * sal + 0.2 * access_factor + 0.1 * age_factor
    return quantize_score(max(0.0, min(1.0, raw)))


def trace_similarity(
    left: RecallSourceEvidence | MemoryTrace,
    right: RecallSourceEvidence | MemoryTrace,
) -> float:
    """Jaccard overlap over concepts, entity IDs, and relation predicates."""
    left_tokens = _content_tokens(left)
    right_tokens = _content_tokens(right)
    if not left_tokens and not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    if union == 0:
        return 0.0
    return quantize_score(float(intersection) / float(union))


def cue_overlap(
    source: RecallSourceEvidence | MemoryTrace,
    cue: MemoryRecallContext | MemoryQueryContext,
) -> float:
    """Cue-dependent overlap in ``[0, 1]`` (tags + related entities + location)."""
    tokens = _content_tokens(source)
    cue_tokens: set[str] = set()
    for tag in cue.tags:
        cue_tokens.add(f"tag:{tag}")
    location = getattr(cue, "location_id", None)
    if location is not None:
        cue_tokens.add(f"loc:{location.value}")
    related = getattr(cue, "related_entity_ids", ())
    for entity_id in related:
        cue_tokens.add(f"entity:{entity_id.value}")
    # MemoryQueryContext may expose concept cues via matched filters elsewhere;
    # overlap on empty cue returns a neutral mid weight so ranking still works.
    if not cue_tokens:
        return quantize_score(0.5)
    if not tokens:
        return 0.0
    intersection = len(tokens & cue_tokens)
    return quantize_score(float(intersection) / float(len(cue_tokens)))


def apply_interference(
    strengths: Mapping[str, float],
    similarities: Mapping[tuple[str, str], float],
    *,
    policy: MemoryDynamicsPolicy,
) -> dict[str, float]:
    """Suppress similar traces in the ranked window (symmetric pair interference)."""
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("apply_interference: invalid_policy")
    out: dict[str, float] = {}
    ids = sorted(strengths)
    for mid in ids:
        base = _clamp_unit(f"apply_interference[{mid}]", strengths[mid])
        suppression = 0.0
        for other in ids:
            if other == mid:
                continue
            key = (mid, other) if mid < other else (other, mid)
            sim = similarities.get(key, 0.0)
            other_strength = _clamp_unit(
                f"apply_interference[{other}]", strengths[other]
            )
            suppression = quantize_score(
                suppression
                + policy.interference_strength
                * _clamp_unit("sim", sim)
                * other_strength
            )
        out[mid] = quantize_score(max(0.0, base * (1.0 - min(1.0, suppression))))
    return out


def compete_traces(
    candidates: Sequence[DynamicsCandidate],
    *,
    cue: MemoryRecallContext | MemoryQueryContext,
    policy: MemoryDynamicsPolicy,
    max_selected: int = 3,
) -> tuple[tuple[DynamicsCandidate, ...], tuple[DynamicsCandidate, ...]]:
    """Cue-dependent competition → selected winners and remaining competitors."""
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("compete_traces: invalid_policy")
    if (
        isinstance(max_selected, bool)
        or not isinstance(max_selected, int)
        or max_selected < 1
    ):
        raise ValueError("compete_traces: invalid_max_selected")
    if not candidates:
        return (), ()

    base_strengths: dict[str, float] = {}
    by_id: dict[str, DynamicsCandidate] = {}
    for item in candidates:
        if type(item) is not DynamicsCandidate:
            raise TypeError("compete_traces: invalid_candidate")
        mid = item.source.memory_id.value
        if mid in by_id:
            raise ValueError("compete_traces: duplicate_memory_id")
        cue_w = cue_overlap(item.source, cue)
        strength = quantize_score(item.strength * (0.25 + 0.75 * cue_w))
        base_strengths[mid] = strength
        by_id[mid] = DynamicsCandidate(
            source=item.source,
            access_count=item.access_count,
            strength=strength,
        )

    similarities: dict[tuple[str, str], float] = {}
    ids = sorted(by_id)
    for i, left_id in enumerate(ids):
        for right_id in ids[i + 1 :]:
            sim = trace_similarity(by_id[left_id].source, by_id[right_id].source)
            similarities[(left_id, right_id)] = sim

    interfered = apply_interference(base_strengths, similarities, policy=policy)
    ranked = sorted(
        (
            DynamicsCandidate(
                source=by_id[mid].source,
                access_count=by_id[mid].access_count,
                strength=interfered[mid],
            )
            for mid in ids
        ),
        key=lambda c: (-c.strength, c.source.memory_id.value),
    )
    selected = tuple(ranked[:max_selected])
    competitors = tuple(ranked[max_selected:])
    return selected, competitors


def salience_biased_survival(
    fragments: Sequence[ConceptMention],
    *,
    salience: float,
    policy: MemoryDynamicsPolicy,
) -> tuple[ConceptMention, ...]:
    """Keep fragments with probability biased by salience (deterministic gate)."""
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("salience_biased_survival: invalid_policy")
    sal = effective_salience(salience, age_ticks=0, policy=policy)
    kept: list[ConceptMention] = []
    for index, fragment in enumerate(fragments):
        if type(fragment) is not ConceptMention:
            raise TypeError("salience_biased_survival: invalid_fragment")
        gate = deterministic_unit(
            fragment.mention_id.value, fragment.concept, str(index)
        )
        threshold = quantize_score(1.0 - (0.5 + 0.5 * sal))
        if gate >= threshold or sal >= 0.9:
            kept.append(fragment)
    if not kept and fragments:
        # Always retain the first fragment so reconstructions stay non-empty.
        kept.append(fragments[0])
    return tuple(kept)


def confidence_degradation(
    source_aggregate: float,
    *,
    age_ticks: int,
    blend_count: int,
    competition_mass: float,
    policy: MemoryDynamicsPolicy,
) -> float:
    """Reconstruction confidence ≤ source aggregate under age/mix/competition."""
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("confidence_degradation: invalid_policy")
    if isinstance(age_ticks, bool) or not isinstance(age_ticks, int) or age_ticks < 0:
        raise ValueError("confidence_degradation: invalid_age")
    if (
        isinstance(blend_count, bool)
        or not isinstance(blend_count, int)
        or blend_count < 1
    ):
        raise ValueError("confidence_degradation: invalid_blend_count")
    base = _clamp_unit("confidence_degradation.source", source_aggregate)
    mix_penalty = quantize_score(0.05 * float(blend_count - 1))
    age_penalty = quantize_score(policy.decay_rate * float(age_ticks))
    comp_penalty = quantize_score(
        policy.competition_blend * _clamp_unit("competition", competition_mass)
    )
    penalty = min(1.0, mix_penalty + age_penalty + comp_penalty)
    degraded = quantize_score(
        max(policy.confidence_floor, base * (1.0 - penalty))
    )
    return quantize_score(min(base, degraded))


def source_confusion_attribution(
    *,
    true_source_ids: Sequence[MemoryId],
    competitor_ids: Sequence[MemoryId],
    reconstruction_id: str,
    tick: int,
    policy: MemoryDynamicsPolicy,
) -> tuple[tuple[MemoryId, ...], bool]:
    """Deterministic agent-visible attribution; may disagree with true sources."""
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("source_confusion_attribution: invalid_policy")
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        raise ValueError("source_confusion_attribution: invalid_tick")
    true_ids = tuple(true_source_ids)
    for item in true_ids:
        if type(item) is not MemoryId:
            raise TypeError("source_confusion_attribution: invalid_true_id")
    competitors = tuple(competitor_ids)
    for item in competitors:
        if type(item) is not MemoryId:
            raise TypeError("source_confusion_attribution: invalid_competitor_id")
    if not true_ids:
        return (), False
    if not competitors or policy.source_confusion_mass <= 0.0:
        return true_ids, False
    roll = deterministic_unit(
        reconstruction_id,
        str(tick),
        *(item.value for item in true_ids),
        *(item.value for item in competitors),
    )
    if roll >= policy.source_confusion_mass:
        return true_ids, False
    pick = deterministic_unit(
        "confuse",
        reconstruction_id,
        str(tick),
        *(item.value for item in competitors),
    )
    index = int(pick * len(competitors)) % len(competitors)
    confused = list(true_ids)
    # Replace the last true source with a competitor (stable, auditable).
    confused[-1] = competitors[index]
    return tuple(confused), True


def testing_effect_deltas(
    *,
    selected_ids: Sequence[MemoryId],
    competitor_ids: Sequence[MemoryId],
    policy: MemoryDynamicsPolicy,
) -> tuple[StrengthDeltaSummary, ...]:
    """Strengthen retrieved traces; weaken competitors (ephemeral audit deltas)."""
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("testing_effect_deltas: invalid_policy")
    deltas: list[StrengthDeltaSummary] = []
    for mid in selected_ids:
        if type(mid) is not MemoryId:
            raise TypeError("testing_effect_deltas: invalid_selected")
        deltas.append(
            StrengthDeltaSummary(memory_id=mid, delta=policy.testing_effect_gain)
        )
    for mid in competitor_ids:
        if type(mid) is not MemoryId:
            raise TypeError("testing_effect_deltas: invalid_competitor")
        deltas.append(
            StrengthDeltaSummary(
                memory_id=mid, delta=quantize_score(-policy.testing_effect_loss)
            )
        )
    deltas.sort(key=lambda item: item.memory_id.value)
    return tuple(deltas)


def semanticization_trigger(
    selected: Sequence[RecallSourceEvidence],
    *,
    policy: MemoryDynamicsPolicy,
    access_counts: Mapping[str, int] | None = None,
) -> SemanticizationHint:
    """Repeated similar episodes → belief gist intent when thresholds met."""
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("semanticization_trigger: invalid_policy")
    if len(selected) < 2:
        return SemanticizationHint(
            should_revise=False,
            gist_concepts=(),
            source_memory_ids=tuple(item.memory_id for item in selected),
        )
    pairs = 0
    similar_pairs = 0
    for i, left in enumerate(selected):
        for right in selected[i + 1 :]:
            pairs += 1
            if (
                trace_similarity(left, right)
                >= policy.semanticization_similarity_threshold
            ):
                similar_pairs += 1
    mean_access = 0.0
    counts = access_counts or {}
    if selected:
        total = 0
        for item in selected:
            total += max(0, int(counts.get(item.memory_id.value, 0)))
        mean_access = float(total) / float(len(selected))
    similar_ratio = (
        0.0 if pairs == 0 else quantize_score(float(similar_pairs) / float(pairs))
    )
    should = (
        similar_ratio >= policy.semanticization_similarity_threshold
        and mean_access >= float(policy.semanticization_repeat_threshold)
    )
    gist: list[str] = []
    seen: set[str] = set()
    if should:
        for item in selected:
            for concept in item.concepts:
                if concept.concept not in seen:
                    seen.add(concept.concept)
                    gist.append(concept.concept)
        gist.sort()
    return SemanticizationHint(
        should_revise=should,
        gist_concepts=tuple(gist),
        source_memory_ids=tuple(item.memory_id for item in selected),
    )


def reconstruct_v2(
    evidence: RecallEvidence,
    *,
    policy: MemoryDynamicsPolicy,
    access_counts: Mapping[str, int] | None = None,
) -> DynamicsReconstructionResult:
    """Compose V2 dynamics into reconstructed memory + audit record."""
    if type(evidence) is not RecallEvidence:
        raise TypeError("reconstruct_v2: invalid_evidence")
    if type(policy) is not MemoryDynamicsPolicy:
        raise TypeError("reconstruct_v2: invalid_policy")
    if not evidence.sources:
        raise ValueError("reconstruct_v2: empty_sources")

    counts = access_counts or {}
    candidates: list[DynamicsCandidate] = []
    distortion: list[MemoryDistortionCode] = []
    for source in evidence.sources:
        age = source.episode_age_ticks
        access = int(counts.get(source.memory_id.value, 0))
        strength = retrieval_strength(
            age_ticks=age,
            access_count=access,
            salience=source.emotional_salience,
            confidence=source.confidence,
            policy=policy,
        )
        if strength < source.confidence:
            if MemoryDistortionCode.TEMPORAL_DECAY not in distortion:
                distortion.append(MemoryDistortionCode.TEMPORAL_DECAY)
        candidates.append(
            DynamicsCandidate(source=source, access_count=access, strength=strength)
        )

    selected, competitors = compete_traces(
        candidates,
        cue=evidence.recall_context,
        policy=policy,
        max_selected=min(3, evidence.policy.max_source_traces),
    )
    if competitors and any(
        trace_similarity(a.source, b.source) > 0.0
        for a in selected
        for b in competitors
    ):
        distortion.append(MemoryDistortionCode.INTERFERENCE)
    if len(selected) > 1 or policy.competition_blend > 0.0:
        distortion.append(MemoryDistortionCode.COMPETITION)

    true_ids = tuple(item.source.memory_id for item in selected)
    competitor_ids = tuple(item.source.memory_id for item in competitors)
    agent_ids, confused = source_confusion_attribution(
        true_source_ids=true_ids,
        competitor_ids=competitor_ids,
        reconstruction_id=evidence.reconstruction_id.value,
        tick=evidence.current_tick,
        policy=policy,
    )
    if confused:
        distortion.append(MemoryDistortionCode.SOURCE_CONFUSION)

    used_sources = tuple(item.source for item in selected)
    blend_weights = _blend_weights(selected, policy=policy)

    concepts = _weighted_merge_concepts(used_sources, blend_weights, policy=policy)
    mean_salience = _weighted_mean(
        [item.source.emotional_salience for item in selected], blend_weights
    )
    if any(c.source.emotional_salience >= 0.5 for c in selected):
        distortion.append(MemoryDistortionCode.SALIENCE_BIAS)
    concepts = salience_biased_survival(
        concepts, salience=mean_salience, policy=policy
    )
    entities = _merge_entities(used_sources)
    relations = _merge_relations(used_sources, concepts=concepts, entities=entities)
    context = _merge_context(used_sources, recall_context=evidence.recall_context)
    narrative = _deterministic_narrative(used_sources)
    if len(narrative) > evidence.policy.max_narrative_chars:
        narrative = narrative[: evidence.policy.max_narrative_chars]

    source_aggregate = _weighted_mean(
        [item.source.confidence for item in selected], blend_weights
    )
    max_age = max(item.source.episode_age_ticks for item in selected)
    competition_mass = quantize_score(
        sum(item.strength for item in competitors) / max(1.0, float(len(candidates)))
    )
    confidence_before = quantize_score(source_aggregate)
    confidence_after = confidence_degradation(
        source_aggregate,
        age_ticks=max_age,
        blend_count=len(selected),
        competition_mass=competition_mass,
        policy=policy,
    )
    if confidence_after < confidence_before:
        distortion.append(MemoryDistortionCode.CONFIDENCE_DEGRADATION)

    deltas = testing_effect_deltas(
        selected_ids=true_ids,
        competitor_ids=competitor_ids,
        policy=policy,
    )
    if deltas:
        distortion.append(MemoryDistortionCode.TESTING_EFFECT)

    hint = semanticization_trigger(
        used_sources, policy=policy, access_counts=counts
    )
    if hint.should_revise:
        distortion.append(MemoryDistortionCode.SEMANTICIZATION)

    # Stable unique ordered codes
    seen_codes: set[MemoryDistortionCode] = set()
    ordered_codes: list[MemoryDistortionCode] = []
    for code in distortion:
        if code not in seen_codes:
            seen_codes.add(code)
            ordered_codes.append(code)

    generation = 1 + max(item.generation for item in evidence.sources)
    reconstructed = ReconstructedMemory(
        reconstruction_id=evidence.reconstruction_id,
        owner_id=evidence.owner_id,
        narrative=narrative,
        concepts=concepts,
        entities=entities,
        relations=relations,
        context=context,
        confidence=confidence_after,
        emotional_salience=mean_salience,
        source_memory_ids=agent_ids,
        generation=generation,
        reconstructed_at_tick=evidence.current_tick,
        policy_id=evidence.policy.policy_id,
        policy_version=evidence.policy.version,
        used_provider=False,
        fallback_used=False,
    )
    reconstructed = validate_reconstructed_memory(reconstructed, evidence=evidence)

    audit = RecallAuditRecord(
        reconstruction_id=evidence.reconstruction_id,
        owner_id=evidence.owner_id,
        tick=evidence.current_tick,
        source_memory_ids=true_ids,
        competitor_ids=competitor_ids,
        selected_ids=agent_ids,
        distortion_codes=tuple(ordered_codes),
        confidence_before=confidence_before,
        confidence_after=confidence_after,
        strength_deltas=deltas,
    )
    return DynamicsReconstructionResult(
        reconstructed=reconstructed,
        audit=audit,
        semanticization=hint if hint.should_revise else None,
    )


def _clamp_unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name}: not_finite")
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: out_of_unit_interval")
    return quantize_score(0.0 if number == 0.0 else number)


def _content_tokens(source: RecallSourceEvidence | MemoryTrace) -> set[str]:
    tokens: set[str] = set()
    for concept in source.concepts:
        tokens.add(f"concept:{concept.concept}")
    for entity in source.entities:
        tokens.add(f"entity:{entity.entity_id.value}")
        tokens.add(f"label:{entity.label}")
    for relation in source.relations:
        tokens.add(f"pred:{relation.predicate}")
    for tag in source.context.tags:
        tokens.add(f"tag:{tag}")
    if source.context.location_id is not None:
        tokens.add(f"loc:{source.context.location_id.value}")
    return tokens


def _blend_weights(
    selected: Sequence[DynamicsCandidate],
    *,
    policy: MemoryDynamicsPolicy,
) -> tuple[float, ...]:
    if not selected:
        return ()
    if len(selected) == 1:
        return (1.0,)
    blend = policy.competition_blend
    winner_mass = quantize_score(1.0 - blend)
    share = quantize_score(blend / float(len(selected)))
    weights: list[float] = []
    for index, _item in enumerate(selected):
        if index == 0:
            weights.append(quantize_score(winner_mass + share))
        else:
            weights.append(share)
    total = sum(weights)
    if total <= 0.0:
        equal = quantize_score(1.0 / float(len(selected)))
        return tuple(equal for _ in selected)
    return tuple(quantize_score(w / total) for w in weights)


def _weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    if len(values) != len(weights) or not values:
        raise ValueError("_weighted_mean: length_mismatch")
    total_w = sum(weights)
    if total_w <= 0.0:
        return quantize_score(sum(values) / float(len(values)))
    return quantize_score(
        sum(v * w for v, w in zip(values, weights, strict=True)) / total_w
    )


def _weighted_merge_concepts(
    sources: Sequence[RecallSourceEvidence],
    weights: Sequence[float],
    *,
    policy: MemoryDynamicsPolicy,
) -> tuple[ConceptMention, ...]:
    del policy  # reserved for future blend thresholds
    if len(sources) != len(weights):
        raise ValueError("_weighted_merge_concepts: length_mismatch")
    # Order sources by weight DESC then memory_id for first-wins stability.
    ordered = sorted(
        zip(sources, weights, strict=True),
        key=lambda pair: (-pair[1], pair[0].memory_id.value),
    )
    seen: set[str] = set()
    out: list[ConceptMention] = []
    for source, _weight in ordered:
        for concept in source.concepts:
            if concept.mention_id.value in seen:
                continue
            seen.add(concept.mention_id.value)
            out.append(concept)
    return tuple(out)


def _merge_entities(
    sources: Sequence[RecallSourceEvidence],
) -> tuple[EntityMention, ...]:
    seen: set[str] = set()
    out: list[EntityMention] = []
    for source in sources:
        for entity in source.entities:
            if entity.mention_id.value in seen:
                continue
            seen.add(entity.mention_id.value)
            out.append(entity)
    return tuple(out)


def _merge_relations(
    sources: Sequence[RecallSourceEvidence],
    *,
    concepts: Sequence[ConceptMention],
    entities: Sequence[EntityMention],
) -> tuple[MemoryRelation, ...]:
    concept_ids = {item.mention_id.value for item in concepts}
    entity_ids = {item.mention_id.value for item in entities}
    seen: set[str] = set()
    out: list[MemoryRelation] = []
    for source in sources:
        for relation in source.relations:
            rid = relation.relation_id.value
            if rid in seen or rid in concept_ids or rid in entity_ids:
                continue
            subject_ok = (
                relation.subject.mention_id.value in concept_ids
                or relation.subject.mention_id.value in entity_ids
            )
            object_ok = (
                relation.object.mention_id.value in concept_ids
                or relation.object.mention_id.value in entity_ids
            )
            if not (subject_ok and object_ok):
                continue
            seen.add(rid)
            out.append(relation)
    return tuple(out)


def _merge_context(
    sources: Sequence[RecallSourceEvidence],
    *,
    recall_context: MemoryRecallContext,
) -> MemorySituationContext:
    location = recall_context.location_id
    tags: list[str] = []
    seen_tags: set[str] = set()
    if location is None:
        for source in sources:
            if source.context.location_id is not None:
                location = source.context.location_id
                break
    for tag in recall_context.tags:
        if tag not in seen_tags:
            seen_tags.add(tag)
            tags.append(tag)
    for source in sources:
        for tag in source.context.tags:
            if tag not in seen_tags:
                seen_tags.add(tag)
                tags.append(tag)
    return MemorySituationContext(location_id=location, tags=tuple(tags))


def _deterministic_narrative(sources: Sequence[RecallSourceEvidence]) -> str:
    parts: list[str] = []
    for source in sources:
        concepts = ",".join(item.concept for item in source.concepts) or "empty"
        parts.append(f"{source.memory_id.value}:{concepts}")
    return ";".join(parts)
