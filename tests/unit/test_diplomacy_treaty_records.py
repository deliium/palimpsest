# mypy: ignore-errors
"""V4-11 treaty anchors, immutable versions, anchors, and digest."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition import (
    DIPLOMACY_TREATY_ID_PREFIX,
    DIPLOMACY_TREATY_VERSION_ID_PREFIX,
    DiplomacyError,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatySubjectKind,
    apply_diplomacy_update,
    diplomacy_ledger_digest,
    diplomacy_treaty_version_id,
    treaty_terms_digest,
)
from agents.cognition.diplomacy_communication import TreatyAct, TreatyFrame

pytestmark = pytest.mark.unit

OWNER = "alice"
PEER = "bob"
OBS = SimpleNamespace(communications=(), occurrences=())


def _propose(
    *, subject: TreatySubjectKind = TreatySubjectKind.CEASEFIRE, tick: int = 1
):
    frame = TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        subject_kind=subject,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=tick,
        envoy_ref=OWNER,
    )
    return apply_diplomacy_update(
        owner_id=OWNER,
        tick=tick,
        observation=OBS,
        prior=None,
        frames=(frame,),
    )


def test_two_party_anchor_has_owner_self_party_first() -> None:
    ledger = _propose()
    assert len(ledger.treaties) == 1
    treaty = ledger.treaties[0]
    assert treaty.participant_party_ids[0] == ledger.relations[0].party_ids[0]
    assert len(treaty.participant_party_ids) == 2
    assert treaty.treaty_id.startswith(DIPLOMACY_TREATY_ID_PREFIX)
    assert len(ledger.treaty_versions) == 1
    assert ledger.treaty_versions[0].version_id.startswith(
        DIPLOMACY_TREATY_VERSION_ID_PREFIX
    )


def test_fewer_than_two_participants_is_rejected() -> None:
    with pytest.raises(DiplomacyError):
        TreatyFrame(
            act=TreatyAct.TREATY_PROPOSE,
            participant_refs=(f"agent:{OWNER}",),
            subject_kind=TreatySubjectKind.CEASEFIRE,
            change_kind=TreatyChangeKind.ORIGINAL,
            provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
            envoy_ref=OWNER,
        )


def test_duplicate_participants_are_rejected_by_the_ledger() -> None:
    ledger = _propose()
    treaty = ledger.treaties[0]
    with pytest.raises(DiplomacyError):
        replace(
            ledger,
            treaties=(
                replace(
                    treaty,
                    participant_party_ids=(
                        treaty.participant_party_ids[0],
                        treaty.participant_party_ids[0],
                    ),
                ),
            ),
        )


def test_self_party_not_first_fails() -> None:
    ledger = _propose()
    treaty = ledger.treaties[0]
    with pytest.raises(DiplomacyError, match="diplomacy_treaty_lineage_invalid"):
        replace(
            ledger,
            treaties=(
                replace(
                    treaty,
                    participant_party_ids=tuple(reversed(treaty.participant_party_ids)),
                ),
            ),
        )


def test_original_version_lineage_is_exact() -> None:
    ledger = _propose()
    version = ledger.treaty_versions[0]
    assert version.version_index == 1
    assert version.change_kind is TreatyChangeKind.ORIGINAL
    assert version.parent_version_ids == ()
    with pytest.raises(DiplomacyError):
        replace(version, version_index=2)
    with pytest.raises(DiplomacyError):
        replace(version, parent_version_ids=(version.version_id,))


def test_non_original_version_requires_a_parent() -> None:
    ledger = _propose()
    version = ledger.treaty_versions[0]
    with pytest.raises(DiplomacyError, match="diplomacy_treaty_lineage_invalid"):
        replace(version, change_kind=TreatyChangeKind.RENEWAL)


def test_forward_and_foreign_parent_references_fail() -> None:
    ledger = _propose()
    version = ledger.treaty_versions[0]
    with pytest.raises(DiplomacyError):
        replace(
            ledger,
            treaty_versions=(
                replace(
                    version,
                    change_kind=TreatyChangeKind.RENEWAL,
                    parent_version_ids=("dpv-" + "0" * 16,),
                ),
            ),
        )


def test_non_contiguous_indices_fail() -> None:
    ledger = _propose()
    version = ledger.treaty_versions[0]
    with pytest.raises(DiplomacyError, match="diplomacy_treaty_lineage_invalid"):
        replace(
            ledger,
            treaty_versions=(replace(version, version_index=2),),
        )


def test_terms_digest_is_deterministic_owner_independent_and_sensitive() -> None:
    kwargs = dict(
        subject_kind=TreatySubjectKind.CEASEFIRE,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        effective_tick=1,
        end_tick=10,
    )
    first = treaty_terms_digest(**kwargs)
    assert first == treaty_terms_digest(**kwargs)
    assert len(first) == 64
    assert first == first.lower()
    assert first != treaty_terms_digest(
        **{**kwargs, "subject_kind": TreatySubjectKind.TRADE}
    )
    assert first != treaty_terms_digest(
        **{**kwargs, "provision_kinds": (TreatyProvisionKind.PASSAGE,)}
    )
    assert first != treaty_terms_digest(**{**kwargs, "effective_tick": 2})


def test_record_and_memory_anchors_are_bounded_and_sorted() -> None:
    ledger = _propose()
    version = ledger.treaty_versions[0]
    sorted_version = replace(
        version,
        record_refs=("z-record", "a-record"),
        institutional_memory_refs=("b" * 64, "a" * 64),
    )
    assert sorted_version.record_refs == ("a-record", "z-record")
    assert sorted_version.institutional_memory_refs == ("a" * 64, "b" * 64)
    with pytest.raises(DiplomacyError):
        replace(version, record_refs=("bad text",))
    with pytest.raises(DiplomacyError):
        replace(version, record_refs=tuple(f"r{i}" for i in range(9)))
    with pytest.raises(DiplomacyError):
        replace(version, institutional_memory_refs=("A" * 64,))
    with pytest.raises(DiplomacyError):
        replace(
            version,
            institutional_memory_refs=tuple("a" * 63 for _ in range(1)),
        )


def test_digest_changes_with_any_treaty_row() -> None:
    ledger = _propose()
    baseline = diplomacy_ledger_digest(ledger)
    assert baseline == diplomacy_ledger_digest(_propose())
    changed = replace(
        ledger,
        treaty_versions=(
            replace(ledger.treaty_versions[0], record_refs=("record-1",)),
        ),
    )
    assert diplomacy_ledger_digest(changed) != baseline


def test_version_id_matches_minted_version() -> None:
    ledger = _propose()
    version = ledger.treaty_versions[0]
    assert version.version_id == diplomacy_treaty_version_id(
        OWNER,
        version.treaty_id,
        version.version_index,
        version.change_kind,
        version.terms_digest,
    )


def test_structurally_invalid_versions_fail_closed_before_conflicts() -> None:
    ledger = _propose()
    version = ledger.treaty_versions[0]
    duplicate = replace(
        version,
        version_id=DIPLOMACY_TREATY_VERSION_ID_PREFIX + "9" * 16,
        terms_digest="b" * 64,
    )
    with pytest.raises(DiplomacyError):
        replace(ledger, treaty_versions=(version, duplicate))

    orphan = replace(
        version,
        version_id=DIPLOMACY_TREATY_VERSION_ID_PREFIX + "8" * 16,
        version_index=2,
        parent_version_ids=(DIPLOMACY_TREATY_VERSION_ID_PREFIX + "7" * 16,),
        change_kind=TreatyChangeKind.RENEWAL,
        terms_digest="c" * 64,
    )
    with pytest.raises(DiplomacyError):
        replace(ledger, treaty_versions=(version, orphan))
