"""Cross-community practical-knowledge transfer from detached audit rows."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.society_emergence import CandidateCommunityRow
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "CONTACT_KNOWLEDGE_TRANSFER_CHANNELS",
    "CONTACT_KNOWLEDGE_TRANSFER_METRIC_VERSION",
    "ContactKnowledgeTransferResult",
    "ContactPracticalKnowledgeAuditRow",
    "compute_contact_knowledge_transfer",
    "compute_contact_knowledge_transfer_metric",
]

CONTACT_KNOWLEDGE_TRANSFER_METRIC_VERSION: Final[str] = "contact_knowledge_transfer@1"
CONTACT_KNOWLEDGE_TRANSFER_CHANNELS: Final[tuple[str, ...]] = (
    "teaching",
    "imitation",
    "written_record",
    "reconstruction",
    "combination",
)
_LOG: Final[logging.Logger] = logging.getLogger("analysis.contact_knowledge_transfer")


class ContactKnowledgeTransferError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class ContactPracticalKnowledgeAuditRow:
    owner_id: str
    channel: str
    source_person_id: str | None
    teacher_person_id: str | None
    hop_index: int
    mutated: bool
    fingerprint_distance: float | None
    tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "owner_id", require_stable_id("owner_id", self.owner_id)
        )
        channel = require_stable_id("channel", self.channel)
        if channel not in CONTACT_KNOWLEDGE_TRANSFER_CHANNELS:
            raise ContactKnowledgeTransferError("unknown_transfer_channel")
        object.__setattr__(self, "channel", channel)
        for name in ("source_person_id", "teacher_person_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_stable_id(name, value))
        object.__setattr__(
            self, "hop_index", require_exact_nonneg_int("hop_index", self.hop_index)
        )
        if type(self.mutated) is not bool:
            raise ContactKnowledgeTransferError("invalid_mutated")
        if self.fingerprint_distance is not None:
            object.__setattr__(
                self,
                "fingerprint_distance",
                require_finite(self.fingerprint_distance),
            )
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))


@dataclass(frozen=True, slots=True)
class ContactKnowledgeTransferResult:
    channel_counts: tuple[tuple[str, int], ...]
    donor_recipient_pairs: tuple[tuple[str, str], ...]
    mutated_transfer_count: int
    mean_hop: float | None
    fingerprint_distance_mean: float | None
    unresolved_donor_count: int
    coverage: MetricCoverage

    def __post_init__(self) -> None:
        if type(self.coverage) is not MetricCoverage:
            raise ContactKnowledgeTransferError("invalid_coverage")

    @property
    def total_transfer_count(self) -> int:
        return sum(count for _channel, count in self.channel_counts)

    def channel_count(self, channel: str) -> int:
        return dict(self.channel_counts).get(channel, 0)


def _communities(communities: Sequence[CandidateCommunityRow]) -> dict[str, str]:
    owner: dict[str, str] = {}
    for community in communities:
        for person in community.person_ids:
            if person in owner:
                raise ContactKnowledgeTransferError(
                    "duplicate_person_across_communities"
                )
            owner[person] = community.community_id
    return owner


def compute_contact_knowledge_transfer(
    communities: Sequence[CandidateCommunityRow],
    rows: Sequence[ContactPracticalKnowledgeAuditRow],
    *,
    onset_tick_by_person: Mapping[str, int] | None = None,
) -> ContactKnowledgeTransferResult:
    community_rows = tuple(communities)
    if any(type(item) is not CandidateCommunityRow for item in community_rows):
        raise ContactKnowledgeTransferError("invalid_communities")
    owner = _communities(community_rows)
    counts: Counter[str] = Counter()
    pairs: set[tuple[str, str]] = set()
    mutated = 0
    hops: list[int] = []
    distances: list[float] = []
    unresolved = 0
    expected = 0
    for row in rows:
        if type(row) is not ContactPracticalKnowledgeAuditRow:
            raise ContactKnowledgeTransferError("invalid_transfer_row")
        if onset_tick_by_person is not None:
            onset = onset_tick_by_person.get(row.owner_id)
            if onset is None or row.tick < onset:
                continue
        expected += 1
        recipient = owner.get(row.owner_id)
        donor_person = row.teacher_person_id or row.source_person_id
        if recipient is None or donor_person is None:
            unresolved += 1
            continue
        donor = owner.get(donor_person)
        if donor is None:
            unresolved += 1
            continue
        if donor == recipient:
            continue
        counts[row.channel] += 1
        pairs.add((donor, recipient))
        hops.append(row.hop_index)
        if row.mutated:
            mutated += 1
        if row.fingerprint_distance is not None:
            distances.append(row.fingerprint_distance)
    resolved = sum(counts.values())
    coverage = MetricCoverage(
        observed=resolved,
        expected=expected,
        ratio=(
            quantize_float(require_finite(resolved / expected)) if expected else None
        ),
    )
    _LOG.info(
        "contact_knowledge_transfer_computed transfers=%s pair_count=%s unresolved=%s",
        resolved,
        len(pairs),
        unresolved,
    )
    return ContactKnowledgeTransferResult(
        channel_counts=tuple(
            (channel, counts[channel])
            for channel in CONTACT_KNOWLEDGE_TRANSFER_CHANNELS
        ),
        donor_recipient_pairs=tuple(sorted(pairs)),
        mutated_transfer_count=mutated,
        mean_hop=(
            quantize_float(require_finite(sum(hops) / len(hops))) if hops else None
        ),
        fingerprint_distance_mean=(
            quantize_float(require_finite(sum(distances) / len(distances)))
            if distances
            else None
        ),
        unresolved_donor_count=unresolved,
        coverage=coverage,
    )


def compute_contact_knowledge_transfer_metric(
    result: ContactKnowledgeTransferResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.CONTACT_KNOWLEDGE_TRANSFER)
    values: dict[str, object] = {
        "total_transfer_count": result.total_transfer_count,
        "donor_recipient_pair_count": len(result.donor_recipient_pairs),
        "mutated_transfer_count": result.mutated_transfer_count,
        "unresolved_donor_count": result.unresolved_donor_count,
    }
    for channel in CONTACT_KNOWLEDGE_TRANSFER_CHANNELS:
        values[f"{channel}_count"] = result.channel_count(channel)
    if result.mean_hop is not None:
        values["mean_hop"] = result.mean_hop
    if result.fingerprint_distance_mean is not None:
        values["fingerprint_distance_mean"] = result.fingerprint_distance_mean
    availability = (
        MetricAvailability.ABSENT
        if result.total_transfer_count == 0
        else MetricAvailability.PRESENT
    )
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
        coverage=result.coverage,
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="contact_knowledge_transfer",
            source_ids=(),
            notes_code="descriptive_contact_association",
        ),
    )
