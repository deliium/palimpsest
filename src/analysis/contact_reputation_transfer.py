"""Cross-community reputation transfer from detached reputation evidence."""

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
    "CONTACT_REPUTATION_TRANSFER_METRIC_VERSION",
    "ContactReputationEvidenceRow",
    "ContactReputationTransferResult",
    "compute_contact_reputation_transfer",
    "compute_contact_reputation_transfer_metric",
]

CONTACT_REPUTATION_TRANSFER_METRIC_VERSION: Final[str] = "contact_reputation_transfer@1"
_TRANSFER_CHANNELS: Final[frozenset[str]] = frozenset(
    {"communication", "third_party_story"}
)
_FIRST_HAND_CHANNELS: Final[frozenset[str]] = frozenset(
    {"direct_observation", "remembered_interaction"}
)
_LOG: Final[logging.Logger] = logging.getLogger("analysis.contact_reputation_transfer")


class ContactReputationTransferError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class ContactReputationEvidenceRow:
    owner_id: str
    target_id: str
    source_id: str | None
    dimension: str
    channel: str
    trust_band: str
    tick: int

    def __post_init__(self) -> None:
        for name in ("owner_id", "target_id", "dimension", "channel", "trust_band"):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        if self.source_id is not None:
            object.__setattr__(
                self, "source_id", require_stable_id("source_id", self.source_id)
            )
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))


@dataclass(frozen=True, slots=True)
class ContactReputationTransferResult:
    transfer_event_count: int
    donor_recipient_pairs: tuple[tuple[str, str], ...]
    target_count: int
    dimension_counts: tuple[tuple[str, int], ...]
    channel_counts: tuple[tuple[str, int], ...]
    trust_band_counts: tuple[tuple[str, int], ...]
    unresolved_source_count: int
    direct_observation_coverage_count: int
    remembered_interaction_coverage_count: int
    coverage: MetricCoverage

    def __post_init__(self) -> None:
        if type(self.coverage) is not MetricCoverage:
            raise ContactReputationTransferError("invalid_coverage")


def _communities(communities: Sequence[CandidateCommunityRow]) -> dict[str, str]:
    owner: dict[str, str] = {}
    for community in communities:
        for person in community.person_ids:
            if person in owner:
                raise ContactReputationTransferError(
                    "duplicate_person_across_communities"
                )
            owner[person] = community.community_id
    return owner


def compute_contact_reputation_transfer(
    communities: Sequence[CandidateCommunityRow],
    rows: Sequence[ContactReputationEvidenceRow],
    *,
    onset_tick_by_person: Mapping[str, int] | None = None,
) -> ContactReputationTransferResult:
    community_rows = tuple(communities)
    if any(type(item) is not CandidateCommunityRow for item in community_rows):
        raise ContactReputationTransferError("invalid_communities")
    owner = _communities(community_rows)
    pairs: set[tuple[str, str]] = set()
    targets: set[str] = set()
    dimensions: Counter[str] = Counter()
    channels: Counter[str] = Counter()
    trust_bands: Counter[str] = Counter()
    direct = 0
    remembered = 0
    unresolved = 0
    transfers = 0
    expected = 0
    for row in rows:
        if type(row) is not ContactReputationEvidenceRow:
            raise ContactReputationTransferError("invalid_reputation_row")
        if onset_tick_by_person is not None:
            onset = onset_tick_by_person.get(row.owner_id)
            if onset is None or row.tick < onset:
                continue
        expected += 1
        if row.channel in _FIRST_HAND_CHANNELS:
            if row.channel == "direct_observation":
                direct += 1
            else:
                remembered += 1
            continue
        if row.channel not in _TRANSFER_CHANNELS:
            continue
        if row.source_id is None:
            unresolved += 1
            continue
        recipient = owner.get(row.owner_id)
        donor = owner.get(row.source_id)
        if recipient is None or donor is None:
            unresolved += 1
            continue
        if row.source_id == row.target_id:
            continue
        if donor == recipient:
            continue
        transfers += 1
        pairs.add((donor, recipient))
        targets.add(row.target_id)
        dimensions[row.dimension] += 1
        channels[row.channel] += 1
        trust_bands[row.trust_band] += 1
    coverage = MetricCoverage(
        observed=transfers,
        expected=expected,
        ratio=(
            quantize_float(require_finite(transfers / expected)) if expected else None
        ),
    )
    _LOG.info(
        "contact_reputation_transfer_computed transfers=%s targets=%s unresolved=%s",
        transfers,
        len(targets),
        unresolved,
    )
    return ContactReputationTransferResult(
        transfer_event_count=transfers,
        donor_recipient_pairs=tuple(sorted(pairs)),
        target_count=len(targets),
        dimension_counts=tuple(sorted(dimensions.items())),
        channel_counts=tuple(sorted(channels.items())),
        trust_band_counts=tuple(sorted(trust_bands.items())),
        unresolved_source_count=unresolved,
        direct_observation_coverage_count=direct,
        remembered_interaction_coverage_count=remembered,
        coverage=coverage,
    )


def compute_contact_reputation_transfer_metric(
    result: ContactReputationTransferResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.CONTACT_REPUTATION_TRANSFER)
    values: dict[str, object] = {
        "transfer_event_count": result.transfer_event_count,
        "donor_recipient_pair_count": len(result.donor_recipient_pairs),
        "target_count": result.target_count,
        "unresolved_source_count": result.unresolved_source_count,
        "direct_observation_coverage_count": result.direct_observation_coverage_count,
        "remembered_interaction_coverage_count": (
            result.remembered_interaction_coverage_count
        ),
        "communication_channel_count": dict(result.channel_counts).get(
            "communication", 0
        ),
        "third_party_story_channel_count": dict(result.channel_counts).get(
            "third_party_story", 0
        ),
    }
    for dimension, count in result.dimension_counts:
        values[f"dimension_{dimension}_count"] = count
    for band, count in result.trust_band_counts:
        values[f"trust_band_{band}_count"] = count
    availability = (
        MetricAvailability.ABSENT
        if result.transfer_event_count == 0
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
            source_kind="contact_reputation_transfer",
            source_ids=(),
            notes_code="descriptive_contact_association",
        ),
    )
