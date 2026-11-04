"""V4-08 provenance summaries and chain-of-custody beliefs."""

from __future__ import annotations

import pytest

from agents.cognition import (
    EvidenceCustodyRole,
    EvidenceCustodyStatus,
    EvidenceError,
    EvidenceLedger,
    EvidenceProvenanceChannel,
    EvidenceReferenceKind,
    EvidenceSourceKind,
    EvidenceTestimonyChannel,
    apply_custody_links,
    build_custody_chain,
    derive_all_provenance,
    derive_provenance_summary,
)
from tests.unit.evidence_testimony_helpers import (
    OTHER_OWNER,
    OWNER,
    make_custody,
    make_source,
    make_testimony,
)

pytestmark = pytest.mark.unit


def test_non_portable_source_is_not_applicable() -> None:
    source = make_source(
        kind=EvidenceSourceKind.REPUTATION,
        reference_kind=EvidenceReferenceKind.REPUTATION_RECORD,
        provenance=EvidenceProvenanceChannel.INFERRED,
    )
    ledger = EvidenceLedger(owner_id=OWNER, sources=(source,))
    chain = build_custody_chain(ledger, source.source_id)
    assert chain.status is EvidenceCustodyStatus.NOT_APPLICABLE
    assert chain.links == ()
    assert chain.first_tick is None


def test_zero_links_is_unknown() -> None:
    source = make_source()
    ledger = EvidenceLedger(owner_id=OWNER, sources=(source,))
    assert build_custody_chain(ledger, source.source_id).status is (
        EvidenceCustodyStatus.UNKNOWN
    )


def test_contiguous_links_are_complete() -> None:
    source = make_source()
    first = make_custody(source_id=source.source_id, link_index=0, tick=1)
    second = make_custody(
        source_id=source.source_id,
        link_index=1,
        tick=2,
        role=EvidenceCustodyRole.OBSERVER,
        holder_token=None,
        witnessed=True,
    )
    ledger = EvidenceLedger(
        owner_id=OWNER, sources=(source,), custody_links=(first, second)
    )
    chain = build_custody_chain(ledger, source.source_id)
    assert chain.status is EvidenceCustodyStatus.COMPLETE_BELIEF
    assert chain.gap_count == 0
    assert chain.conflict_count == 0
    assert chain.first_tick == 1
    assert chain.last_tick == 2
    assert ledger.custody_gap_count == 0
    assert ledger.custody_conflict_count == 0


def test_missing_index_and_tick_gaps_are_incomplete() -> None:
    source = make_source()
    first = make_custody(source_id=source.source_id, link_index=0, tick=1)
    third = make_custody(
        source_id=source.source_id,
        link_index=2,
        tick=5,
        role=EvidenceCustodyRole.OBSERVER,
        holder_token=None,
        witnessed=True,
    )
    ledger = EvidenceLedger(
        owner_id=OWNER, sources=(source,), custody_links=(first, third)
    )
    chain = build_custody_chain(ledger, source.source_id)
    assert chain.status is EvidenceCustodyStatus.INCOMPLETE_BELIEF
    assert chain.gap_count == 4
    assert ledger.custody_gap_count == 4


def test_same_tick_disagreement_is_conflicting_and_retained() -> None:
    source = make_source()
    first = make_custody(
        source_id=source.source_id, link_index=0, tick=3, holder_token="agent-2"
    )
    second = make_custody(
        source_id=source.source_id, link_index=1, tick=3, holder_token="agent-3"
    )
    ledger = EvidenceLedger(
        owner_id=OWNER, sources=(source,), custody_links=(second, first)
    )
    chain = build_custody_chain(ledger, source.source_id)
    assert chain.status is EvidenceCustodyStatus.CONFLICTING_BELIEF
    assert chain.conflict_count == 1
    assert {link.holder_token for link in chain.links} == {"agent-2", "agent-3"}
    assert ledger.custody_conflict_count == 1


def test_communicated_testimony_provenance_references_a_root() -> None:
    source = make_source()
    statement = make_testimony(
        channel=EvidenceTestimonyChannel.COMMUNICATED,
        root_ref="root-1",
        source_id=source.source_id,
    )
    ledger = EvidenceLedger(owner_id=OWNER, sources=(source,), testimony=(statement,))
    summary = derive_provenance_summary(ledger, source.source_id)
    assert summary.channel is EvidenceProvenanceChannel.DIRECT_OBSERVATION
    assert summary.opaque_correlation_present is True
    assert summary.attributed_actor is None
    assert summary.independent_root is False

    assert len(derive_all_provenance(ledger)) == 1
    assert derive_all_provenance(ledger)[0] == summary


def test_apply_custody_links_rejects_foreign_and_unknown_rows() -> None:
    source = make_source()
    ledger = EvidenceLedger(owner_id=OWNER, sources=(source,))

    own = make_custody(source_id=source.source_id, link_index=0, tick=1)
    updated = apply_custody_links(ledger, (own,))
    assert updated.custody_links == (own,)

    foreign = make_custody(
        owner=OTHER_OWNER, source_id=source.source_id, link_index=1, tick=2
    )
    with pytest.raises(EvidenceError) as error:
        apply_custody_links(ledger, (foreign,))
    assert error.value.code == "evidence_owner_mismatch"

    with pytest.raises(EvidenceError) as error:
        apply_custody_links(ledger, (own,), owner_id=OTHER_OWNER)
    assert error.value.code == "evidence_owner_mismatch"

    other_source = make_source(reference_id="artifact-2", ordinal=1)
    unknown = make_custody(source_id=other_source.source_id)
    with pytest.raises(EvidenceError) as error:
        apply_custody_links(ledger, (unknown,))
    assert error.value.code == "evidence_unknown_reference"


def test_unknown_source_provenance_fails_closed() -> None:
    ledger = EvidenceLedger(owner_id=OWNER)
    with pytest.raises(EvidenceError) as error:
        derive_provenance_summary(ledger, "evs-" + "0" * 16)
    assert error.value.code == "evidence_unknown_reference"
