"""Cross-community lexical borrowing from metadata-only naming evidence."""

from __future__ import annotations

import logging
from collections import defaultdict
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
    "CONTACT_LEXICAL_BORROWING_METRIC_VERSION",
    "ContactLexicalBorrowingResult",
    "ContactNamingEvidenceRow",
    "compute_contact_lexical_borrowing",
    "compute_contact_lexical_borrowing_metric",
]

CONTACT_LEXICAL_BORROWING_METRIC_VERSION: Final[str] = "contact_lexical_borrowing@1"
_COMMUNICATED_CHANNELS: Final[frozenset[str]] = frozenset(
    {"communication", "testimony", "talk", "tell", "ask", "retelling"}
)
_OBSERVED_CHANNELS: Final[frozenset[str]] = frozenset({"observation", "direct"})
_LOG: Final[logging.Logger] = logging.getLogger("analysis.contact_lexical_borrowing")


class ContactLexicalBorrowingError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class ContactNamingEvidenceRow:
    owner_id: str
    label_token: str
    referent_kind: str
    actor_id: str | None
    channel: str
    first_tick: int
    last_tick: int
    evidence_tick: int
    strength: float
    transmission: str

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "label_token",
            "referent_kind",
            "channel",
            "transmission",
        ):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        if self.actor_id is not None:
            object.__setattr__(
                self, "actor_id", require_stable_id("actor_id", self.actor_id)
            )
        for name in ("first_tick", "last_tick", "evidence_tick"):
            object.__setattr__(
                self, name, require_exact_nonneg_int(name, getattr(self, name))
            )
        if self.last_tick < self.first_tick:
            raise ContactLexicalBorrowingError("invalid_binding_window")
        object.__setattr__(self, "strength", require_finite(self.strength))


@dataclass(frozen=True, slots=True)
class ContactLexicalBorrowingResult:
    borrowed_label_count: int
    borrowing_event_count: int
    donor_recipient_pairs: tuple[tuple[str, str], ...]
    new_adoption_count: int
    reinforcement_count: int
    merge_count: int
    competition_count: int
    mean_binding_strength: float | None
    unresolved_actor_count: int
    coverage: MetricCoverage

    def __post_init__(self) -> None:
        if type(self.coverage) is not MetricCoverage:
            raise ContactLexicalBorrowingError("invalid_coverage")


def _communities(communities: Sequence[CandidateCommunityRow]) -> dict[str, str]:
    owner: dict[str, str] = {}
    for community in communities:
        for person in community.person_ids:
            if person in owner:
                raise ContactLexicalBorrowingError(
                    "duplicate_person_across_communities"
                )
            owner[person] = community.community_id
    return owner


def compute_contact_lexical_borrowing(
    communities: Sequence[CandidateCommunityRow],
    rows: Sequence[ContactNamingEvidenceRow],
    *,
    onset_tick_by_person: Mapping[str, int] | None = None,
) -> ContactLexicalBorrowingResult:
    community_rows = tuple(communities)
    if any(type(item) is not CandidateCommunityRow for item in community_rows):
        raise ContactLexicalBorrowingError("invalid_communities")
    owner = _communities(community_rows)
    pairs: set[tuple[str, str]] = set()
    labels: set[tuple[str, str]] = set()
    events = 0
    new_adoption = 0
    reinforcement = 0
    unresolved = 0
    strengths: list[float] = []
    expected = 0
    seen_referents: dict[tuple[str, str], set[str]] = defaultdict(set)
    seen_donors: dict[tuple[str, str], set[str]] = defaultdict(set)
    merge = 0
    competition = 0
    for row in rows:
        if type(row) is not ContactNamingEvidenceRow:
            raise ContactLexicalBorrowingError("invalid_naming_row")
        if onset_tick_by_person is not None:
            onset = onset_tick_by_person.get(row.owner_id)
            if onset is None or row.evidence_tick < onset:
                continue
        expected += 1
        recipient = owner.get(row.owner_id)
        if row.channel in _OBSERVED_CHANNELS:
            continue
        if row.channel not in _COMMUNICATED_CHANNELS:
            continue
        if row.actor_id is None:
            unresolved += 1
            continue
        donor = owner.get(row.actor_id)
        if recipient is None or donor is None:
            unresolved += 1
            continue
        if donor == recipient:
            continue
        events += 1
        labels.add((row.owner_id, row.label_token))
        pairs.add((donor, recipient))
        strengths.append(row.strength)
        referent_tokens = seen_referents[(row.owner_id, row.referent_kind)]
        if referent_tokens and row.label_token not in referent_tokens:
            competition += 1
        label_key = (row.owner_id, row.label_token)
        if row.evidence_tick == row.first_tick:
            new_adoption += 1
        elif donor in seen_donors[label_key]:
            reinforcement += 1
        elif seen_donors[label_key]:
            merge += 1
        else:
            reinforcement += 1
        seen_donors[label_key].add(donor)
        referent_tokens.add(row.label_token)
    coverage = MetricCoverage(
        observed=events,
        expected=expected,
        ratio=(quantize_float(require_finite(events / expected)) if expected else None),
    )
    _LOG.info(
        "contact_lexical_borrowing_computed events=%s labels=%s unresolved=%s",
        events,
        len(labels),
        unresolved,
    )
    return ContactLexicalBorrowingResult(
        borrowed_label_count=len(labels),
        borrowing_event_count=events,
        donor_recipient_pairs=tuple(sorted(pairs)),
        new_adoption_count=new_adoption,
        reinforcement_count=reinforcement,
        merge_count=merge,
        competition_count=competition,
        mean_binding_strength=(
            quantize_float(require_finite(sum(strengths) / len(strengths)))
            if strengths
            else None
        ),
        unresolved_actor_count=unresolved,
        coverage=coverage,
    )


def compute_contact_lexical_borrowing_metric(
    result: ContactLexicalBorrowingResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.CONTACT_LEXICAL_BORROWING)
    values: dict[str, object] = {
        "borrowed_label_count": result.borrowed_label_count,
        "borrowing_event_count": result.borrowing_event_count,
        "donor_recipient_pair_count": len(result.donor_recipient_pairs),
        "new_adoption_count": result.new_adoption_count,
        "reinforcement_count": result.reinforcement_count,
        "merge_count": result.merge_count,
        "competition_count": result.competition_count,
        "unresolved_actor_count": result.unresolved_actor_count,
    }
    if result.mean_binding_strength is not None:
        values["mean_binding_strength"] = result.mean_binding_strength
    availability = (
        MetricAvailability.ABSENT
        if result.borrowing_event_count == 0
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
            source_kind="contact_lexical_borrowing",
            source_ids=(),
            notes_code="descriptive_contact_association",
        ),
    )
