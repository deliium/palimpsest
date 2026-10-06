"""Researcher-analytical cultural traits (analysis-only; never cognition)."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.numerical import quantize_float
from world.identifiers import require_stable_id

__all__ = [
    "AnalyticalCulturalTrait",
    "compute_analytical_cultural_traits",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.cultural_traits")


@dataclass(frozen=True, slots=True)
class AnalyticalCulturalTrait:
    """Post-run analytical cluster row — never written into agent stores."""

    trait_id: str
    feature_kind: str
    cluster_fingerprint: str
    carrier_count: int
    channel_histogram: Mapping[str, int]
    mean_hop_index: float
    mutation_rate: float
    recombination_rate: float
    generation_spread: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "trait_id", require_stable_id("trait_id", self.trait_id)
        )
        object.__setattr__(
            self,
            "feature_kind",
            require_stable_id("feature_kind", self.feature_kind),
        )
        object.__setattr__(
            self,
            "cluster_fingerprint",
            require_stable_id("cluster_fingerprint", self.cluster_fingerprint),
        )
        if self.carrier_count < 0:
            raise ValueError("carrier_count: out_of_range")
        if not isinstance(self.channel_histogram, Mapping):
            raise TypeError("channel_histogram must be a mapping")
        object.__setattr__(
            self,
            "mean_hop_index",
            quantize_float(float(self.mean_hop_index)),
        )
        object.__setattr__(
            self,
            "mutation_rate",
            quantize_float(float(self.mutation_rate)),
        )
        object.__setattr__(
            self,
            "recombination_rate",
            quantize_float(float(self.recombination_rate)),
        )


def _audit_rows(audits: Sequence[object]) -> tuple[object, ...]:
    if isinstance(audits, (set, frozenset, Mapping, str)) or not isinstance(
        audits, Sequence
    ):
        raise ValueError("audits_not_ordered")
    rows: list[object] = []
    for audit in audits:
        if type(audit).__name__ != "CulturalFeatureAudit":
            raise ValueError("invalid_audit_type")
        rows.append(audit)
    return tuple(rows)


def compute_analytical_cultural_traits(
    audits: Sequence[object],
    *,
    generation_index_by_owner: Mapping[str, int] | None = None,
) -> tuple[AnalyticalCulturalTrait, ...]:
    """Cluster harvested audits by feature kind + digest token (metadata only)."""
    rows = _audit_rows(audits)
    if not rows:
        return ()
    clusters: dict[tuple[str, str], list[object]] = {}
    for row in rows:
        kind = getattr(getattr(row, "feature_kind", None), "value", None)
        digest = getattr(row, "digest_id_token", None)
        if not isinstance(kind, str) or not isinstance(digest, str):
            continue
        clusters.setdefault((kind, digest), []).append(row)
    traits: list[AnalyticalCulturalTrait] = []
    for (kind, digest), group in sorted(clusters.items()):
        channels: Counter[str] = Counter()
        hop_sum = 0.0
        mutated = 0
        recombined = 0
        owners: set[str] = set()
        generations: set[int] = set()
        for row in group:
            channel = getattr(getattr(row, "channel", None), "value", "unknown")
            channels[channel] += 1
            hop_sum += int(getattr(row, "hop_index", 0))
            if bool(getattr(row, "mutated", False)):
                mutated += 1
            if bool(getattr(row, "recombined", False)):
                recombined += 1
            owner = getattr(getattr(row, "owner_id", None), "value", None)
            if isinstance(owner, str):
                owners.add(owner)
                if generation_index_by_owner and owner in generation_index_by_owner:
                    generations.add(generation_index_by_owner[owner])
        count = len(group)
        trait_id = f"trait:{kind}:{digest}"
        traits.append(
            AnalyticalCulturalTrait(
                trait_id=trait_id,
                feature_kind=kind,
                cluster_fingerprint=digest,
                carrier_count=len(owners) or count,
                channel_histogram=dict(channels),
                mean_hop_index=hop_sum / count,
                mutation_rate=mutated / count,
                recombination_rate=recombined / count,
                generation_spread=len(generations) if generations else None,
            )
        )
    _LOG.info(
        "analytical_cultural_traits trait_count=%s audit_count=%s",
        len(traits),
        len(rows),
    )
    return tuple(traits)
