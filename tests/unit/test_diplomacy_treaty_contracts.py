# mypy: ignore-errors
"""V4-11 treaty vocabulary, identifier grammar, and locked policy."""

from __future__ import annotations

from dataclasses import fields, make_dataclass, replace

import pytest

from agents.cognition import (
    DIPLOMACY_ID_PREFIXES,
    DIPLOMACY_POLICY_VERSION,
    DIPLOMACY_TREATY_DECLARATION_ID_PREFIX,
    DIPLOMACY_TREATY_ID_PREFIX,
    DIPLOMACY_TREATY_MISREPRESENTATION_ID_PREFIX,
    DIPLOMACY_TREATY_RECOLLECTION_ID_PREFIX,
    DIPLOMACY_TREATY_VERSION_ID_PREFIX,
    TREATY_CONTRACT_VERSION,
    TREATY_POLICY_VERSION,
    DiplomacyError,
    DiplomacyPolicy,
    DiplomaticMisrepresentationKind,
    TreatyAcceptanceBasis,
    TreatyChangeKind,
    TreatyDeclarationAct,
    TreatyPolicy,
    TreatyProvisionKind,
    TreatyRecollectionBasis,
    TreatyRecollectionStance,
    TreatyStatus,
    TreatySubjectKind,
    assert_diplomacy_no_forbidden_fields,
    default_diplomacy_policy,
    default_treaty_policy,
    diplomacy_scope_covers,
    diplomacy_treaty_declaration_id,
    diplomacy_treaty_id,
    diplomacy_treaty_misrepresentation_id,
    diplomacy_treaty_recollection_id,
    diplomacy_treaty_version_id,
    require_diplomacy_id,
)

pytestmark = pytest.mark.unit

_TREATY_PREFIXES = (
    DIPLOMACY_TREATY_ID_PREFIX,
    DIPLOMACY_TREATY_VERSION_ID_PREFIX,
    DIPLOMACY_TREATY_DECLARATION_ID_PREFIX,
    DIPLOMACY_TREATY_RECOLLECTION_ID_PREFIX,
    DIPLOMACY_TREATY_MISREPRESENTATION_ID_PREFIX,
)


def test_treaty_constants_are_frozen() -> None:
    assert TREATY_CONTRACT_VERSION == "diplomacy-treaties-v1"
    assert TREATY_POLICY_VERSION == "treaty.v1"
    for prefix in _TREATY_PREFIXES:
        assert prefix in DIPLOMACY_ID_PREFIXES


def test_subject_vocabulary_is_closed() -> None:
    assert {member.value for member in TreatySubjectKind} == {
        "ceasefire",
        "access",
        "migration",
        "resource_sharing",
        "trade",
        "territorial_understanding",
        "mutual_aid",
        "unknown",
    }


def test_change_vocabulary_is_closed() -> None:
    assert {member.value for member in TreatyChangeKind} == {
        "original",
        "amendment",
        "renewal",
        "accession",
        "withdrawal",
        "suspension",
        "termination",
        "unknown",
    }


def test_status_vocabulary_is_closed() -> None:
    assert {member.value for member in TreatyStatus} == {
        "proposed",
        "apparently_accepted",
        "suspended",
        "terminated",
        "expired",
        "superseded",
        "unknown",
    }


def test_acceptance_basis_vocabulary_is_closed() -> None:
    assert {member.value for member in TreatyAcceptanceBasis} == {
        "all_participants_declared",
        "proposer_only",
        "rejected",
        "suspended",
        "terminated",
        "expired",
        "superseded",
        "none",
        "unknown",
    }


def test_declaration_vocabulary_is_closed() -> None:
    assert {member.value for member in TreatyDeclarationAct} == {
        "propose",
        "accept",
        "reject",
        "accede",
        "withdraw",
        "amend",
        "renew",
        "suspend",
        "terminate",
        "interpret",
        "ignore",
    }


def test_provision_vocabulary_is_closed() -> None:
    assert {member.value for member in TreatyProvisionKind} == {
        "non_hostility",
        "passage",
        "resource_sharing",
        "exchange",
        "territory_acknowledgement",
        "mutual_assistance",
        "procedure",
        "unknown",
    }


def test_recollection_vocabularies_are_closed() -> None:
    assert {member.value for member in TreatyRecollectionBasis} == {
        "durable_record",
        "institutional_memory",
        "communicated_testimony",
        "narrative",
        "direct_participation",
        "unknown",
    }
    assert {member.value for member in TreatyRecollectionStance} == {
        "remember",
        "reinterpret",
        "ignore",
        "renew",
        "unknown",
    }


def test_no_forbidden_treaty_members_exist() -> None:
    forbidden = {
        "war",
        "peace",
        "border",
        "polity",
        "citizenship",
        "misremembered",
        "enforced",
        "binding",
        "legitimate",
    }
    for enum_type in (
        TreatySubjectKind,
        TreatyChangeKind,
        TreatyStatus,
        TreatyAcceptanceBasis,
        TreatyDeclarationAct,
        TreatyProvisionKind,
        TreatyRecollectionBasis,
        TreatyRecollectionStance,
    ):
        assert forbidden.isdisjoint({member.value for member in enum_type})


def test_treaty_id_helpers_are_deterministic_and_sensitive() -> None:
    treaty_id = diplomacy_treaty_id(
        "owner-1", "dpl-" + "0" * 16, TreatySubjectKind.CEASEFIRE, 3
    )
    assert require_diplomacy_id(treaty_id, DIPLOMACY_TREATY_ID_PREFIX) == treaty_id
    assert treaty_id == diplomacy_treaty_id(
        "owner-1", "dpl-" + "0" * 16, TreatySubjectKind.CEASEFIRE, 3
    )
    assert treaty_id != diplomacy_treaty_id(
        "owner-2", "dpl-" + "0" * 16, TreatySubjectKind.CEASEFIRE, 3
    )
    assert treaty_id != diplomacy_treaty_id(
        "owner-1", "dpl-" + "0" * 16, TreatySubjectKind.TRADE, 3
    )
    assert treaty_id != diplomacy_treaty_id(
        "owner-1", "dpl-" + "0" * 16, TreatySubjectKind.CEASEFIRE, 4
    )
    with pytest.raises(DiplomacyError):
        diplomacy_treaty_id("owner-1", "dpl-" + "0" * 16, "ceasefire", 3)  # type: ignore[arg-type]


def test_version_id_is_sensitive_to_index_kind_and_digest() -> None:
    base = diplomacy_treaty_version_id(
        "owner-1",
        "dpg-" + "0" * 16,
        1,
        TreatyChangeKind.ORIGINAL,
        "a" * 16,
    )
    assert require_diplomacy_id(base, DIPLOMACY_TREATY_VERSION_ID_PREFIX) == base
    assert base != diplomacy_treaty_version_id(
        "owner-1",
        "dpg-" + "0" * 16,
        2,
        TreatyChangeKind.ORIGINAL,
        "a" * 16,
    )
    assert base != diplomacy_treaty_version_id(
        "owner-1",
        "dpg-" + "0" * 16,
        1,
        TreatyChangeKind.RENEWAL,
        "a" * 16,
    )
    assert base != diplomacy_treaty_version_id(
        "owner-1",
        "dpg-" + "0" * 16,
        1,
        TreatyChangeKind.ORIGINAL,
        "b" * 16,
    )


def test_declaration_and_recollection_ids_are_deterministic() -> None:
    declaration = diplomacy_treaty_declaration_id(
        "owner-1",
        "dpg-" + "0" * 16,
        "dpv-" + "0" * 16,
        "dpp-" + "0" * 16,
        TreatyDeclarationAct.ACCEPT,
        4,
        1,
    )
    assert (
        require_diplomacy_id(declaration, DIPLOMACY_TREATY_DECLARATION_ID_PREFIX)
        == declaration
    )
    recollection = diplomacy_treaty_recollection_id(
        "owner-1",
        "dpg-" + "0" * 16,
        "dpv-" + "0" * 16,
        TreatyRecollectionBasis.DURABLE_RECORD,
        TreatyRecollectionStance.REMEMBER,
        7,
    )
    assert (
        require_diplomacy_id(recollection, DIPLOMACY_TREATY_RECOLLECTION_ID_PREFIX)
        == recollection
    )
    observation = diplomacy_treaty_misrepresentation_id(
        "owner-1",
        "dpv-" + "0" * 16,
        "envoy-1",
        DiplomaticMisrepresentationKind.SCOPE_EXCEEDED,
        8,
    )
    assert (
        require_diplomacy_id(observation, DIPLOMACY_TREATY_MISREPRESENTATION_ID_PREFIX)
        == observation
    )


def test_treaty_scope_covers_negotiate_and_decide() -> None:
    for scope in ("negotiate", "decide"):
        assert diplomacy_scope_covers(
            scope_kind=scope,
            duration_kind="until_revoked",
            instrument_kind="treaty",
            scope_subject="ceasefire",
            topic_subject="ceasefire",
        )


@pytest.mark.parametrize("duration", ("single_act", "occasion"))
def test_treaty_scope_rejects_short_mandates(duration: str) -> None:
    assert not diplomacy_scope_covers(
        scope_kind="negotiate",
        duration_kind=duration,
        instrument_kind="treaty",
        scope_subject=None,
        topic_subject="ceasefire",
    )


def test_treaty_scope_rejects_narrow_scopes_and_mismatched_subjects() -> None:
    for scope in ("speak_for", "carry_message"):
        assert not diplomacy_scope_covers(
            scope_kind=scope,
            duration_kind="until_revoked",
            instrument_kind="treaty",
            scope_subject=None,
            topic_subject="ceasefire",
        )
    assert not diplomacy_scope_covers(
        scope_kind="negotiate",
        duration_kind="until_revoked",
        instrument_kind="treaty",
        scope_subject="trade",
        topic_subject="ceasefire",
    )


@pytest.mark.parametrize(
    "name",
    (
        "treaty_store",
        "treaty_authority",
        "treaty_registry",
        "enforced",
        "enforcement",
        "war_state",
        "ceasefire_state",
        "misremembered",
        "false_belief",
        "truth_value",
        "legitimacy",
        "reliability",
        "truth",
        "authority",
        "binding",
        "score",
        "treaty",
    ),
)
def test_forbidden_treaty_field_names_are_rejected(name: str) -> None:
    with pytest.raises(DiplomacyError):
        assert_diplomacy_no_forbidden_fields([name])


def test_treaty_fields_are_allowed_by_the_exact_name_guard() -> None:
    assert_diplomacy_no_forbidden_fields(
        ["treaty_id", "treaty_ref", "version_id", "record_refs"]
    )


def test_treaty_policy_is_locked() -> None:
    policy = default_treaty_policy()
    assert type(policy) is TreatyPolicy
    assert [field.name for field in fields(TreatyPolicy)] == [
        "max_treaties_per_relation",
        "max_versions_per_treaty",
        "max_treaty_declarations_per_version",
        "max_treaty_recollections",
        "max_participants_per_treaty",
        "max_provisions",
        "max_record_refs",
        "max_institutional_memory_refs",
        "max_treaty_frame_chars",
    ]
    assert policy == TreatyPolicy(
        max_treaties_per_relation=8,
        max_versions_per_treaty=16,
        max_treaty_declarations_per_version=32,
        max_treaty_recollections=64,
        max_participants_per_treaty=32,
        max_provisions=8,
        max_record_refs=8,
        max_institutional_memory_refs=8,
        max_treaty_frame_chars=832,
    )


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("max_treaties_per_relation", 9),
        ("max_versions_per_treaty", 15),
        ("max_treaty_declarations_per_version", 31),
        ("max_treaty_recollections", 63),
        ("max_participants_per_treaty", 31),
        ("max_provisions", 7),
        ("max_record_refs", 7),
        ("max_institutional_memory_refs", 7),
        ("max_treaty_frame_chars", 831),
    ),
)
def test_treaty_policy_drift_fails_closed(name: str, value: int) -> None:
    with pytest.raises(DiplomacyError, match="diplomacy_policy_not_locked"):
        replace(TreatyPolicy(), **{name: value})


def test_treaty_policy_rejects_forbidden_field_names() -> None:
    bad_type = make_dataclass(
        "BadTreatyPolicy",
        [("enforced", int, 1)],
        bases=(TreatyPolicy,),
        frozen=True,
    )
    with pytest.raises(DiplomacyError, match="diplomacy_policy_not_locked"):
        bad_type()


def test_v4_10_diplomacy_policy_is_unchanged() -> None:
    policy = default_diplomacy_policy()
    assert type(policy) is DiplomacyPolicy
    assert policy == DiplomacyPolicy(
        agreement_min_party_declarations=2,
        max_relations=24,
        max_parties=32,
        max_contacts_per_relation=16,
        max_envoys_per_relation=8,
        max_negotiations_per_relation=8,
        max_instruments_per_relation=24,
        max_declarations_per_instrument=16,
        max_anchor_refs=8,
        max_total_records=320,
        max_frame_chars=320,
    )
    assert DIPLOMACY_POLICY_VERSION == "diplomacy.v1"
    assert not hasattr(policy, "max_treaties_per_relation")
