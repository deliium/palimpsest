"""V4-10 diplomacy vocabulary, party grammar, and locked policy."""

from __future__ import annotations

from dataclasses import fields, make_dataclass

import pytest

from agents.cognition import (
    DIPLOMACY_AGREEMENT_MIN_PARTY_DECLARATIONS,
    DIPLOMACY_CONFLICT_ID_PREFIX,
    DIPLOMACY_CONTACT_ID_PREFIX,
    DIPLOMACY_DECLARATION_ID_PREFIX,
    DIPLOMACY_ENVOY_ID_PREFIX,
    DIPLOMACY_ID_HEX_LEN,
    DIPLOMACY_ID_PREFIXES,
    DIPLOMACY_INSTRUMENT_ID_PREFIX,
    DIPLOMACY_MISREPRESENTATION_ID_PREFIX,
    DIPLOMACY_NEGOTIATION_ID_PREFIX,
    DIPLOMACY_PARTY_ID_PREFIX,
    DIPLOMACY_POLICY_VERSION,
    DIPLOMACY_PUBLICATION_PREFIX,
    DIPLOMACY_RELATION_ID_PREFIX,
    DIPLOMACY_SCOPE_COVERAGE,
    DIPLOMACY_SEPARATOR,
    DIPLOMACY_TERMINATION_ID_PREFIX,
    DIPLOMACY_TREATY_DECLARATION_ID_PREFIX,
    DIPLOMACY_TREATY_ID_PREFIX,
    DIPLOMACY_TREATY_MISREPRESENTATION_ID_PREFIX,
    DIPLOMACY_TREATY_RECOLLECTION_ID_PREFIX,
    DIPLOMACY_TREATY_VERSION_ID_PREFIX,
    LONG_RUNNING_INSTRUMENT_KINDS,
    DiplomacyError,
    DiplomacyPolicy,
    DiplomaticConflictKind,
    DiplomaticContactKind,
    DiplomaticEnvoyStatus,
    DiplomaticInstrumentKind,
    DiplomaticInstrumentStatus,
    DiplomaticMisrepresentationKind,
    DiplomaticNegotiationStatus,
    DiplomaticPartyKind,
    DiplomaticPartyResolution,
    DiplomaticProvenance,
    DiplomaticTerminationKind,
    DiplomaticTermKind,
    assert_diplomacy_no_forbidden_fields,
    default_diplomacy_policy,
    diplomacy_record_id,
    diplomacy_scope_covers,
    require_diplomacy_id,
    require_diplomacy_subject,
    require_diplomacy_token,
)

_ALL_PREFIXES = (
    DIPLOMACY_RELATION_ID_PREFIX,
    DIPLOMACY_PARTY_ID_PREFIX,
    DIPLOMACY_CONTACT_ID_PREFIX,
    DIPLOMACY_ENVOY_ID_PREFIX,
    DIPLOMACY_NEGOTIATION_ID_PREFIX,
    DIPLOMACY_INSTRUMENT_ID_PREFIX,
    DIPLOMACY_DECLARATION_ID_PREFIX,
    DIPLOMACY_MISREPRESENTATION_ID_PREFIX,
    DIPLOMACY_TERMINATION_ID_PREFIX,
    DIPLOMACY_CONFLICT_ID_PREFIX,
    DIPLOMACY_TREATY_ID_PREFIX,
    DIPLOMACY_TREATY_VERSION_ID_PREFIX,
    DIPLOMACY_TREATY_DECLARATION_ID_PREFIX,
    DIPLOMACY_TREATY_RECOLLECTION_ID_PREFIX,
    DIPLOMACY_TREATY_MISREPRESENTATION_ID_PREFIX,
)

_ALL_SCOPES = (
    "speak_for",
    "negotiate",
    "carry_message",
    "coordinate_project",
    "decide",
    "transact",
    "unknown",
)


def test_policy_constants_are_frozen() -> None:
    assert DIPLOMACY_POLICY_VERSION == "diplomacy.v1"
    assert DIPLOMACY_ID_HEX_LEN == 16
    assert DIPLOMACY_SEPARATOR == "\x1f"
    assert DIPLOMACY_PUBLICATION_PREFIX == "dip-pub-"
    assert DIPLOMACY_AGREEMENT_MIN_PARTY_DECLARATIONS == 2
    assert DIPLOMACY_ID_PREFIXES == _ALL_PREFIXES
    assert len(set(DIPLOMACY_ID_PREFIXES)) == len(DIPLOMACY_ID_PREFIXES)


def test_party_and_contact_vocabularies_are_closed() -> None:
    assert {member.value for member in DiplomaticPartyKind} == {
        "agent",
        "organization",
        "settlement",
        "coalition",
        "unknown",
    }
    assert {member.value for member in DiplomaticPartyResolution} == {
        "resolved",
        "unresolved",
        "unknown",
    }
    assert {member.value for member in DiplomaticContactKind} == {
        "direct_co_presence",
        "mediated_message",
        "written_record",
        "third_party_report",
        "journey_presence",
        "unknown",
    }


def test_envoy_and_negotiation_vocabularies_are_closed() -> None:
    assert {member.value for member in DiplomaticEnvoyStatus} == {
        "claimed",
        "recognized",
        "contested",
        "rejected",
        "revoked",
        "expired",
        "superseded",
        "unknown",
    }
    assert DiplomaticEnvoyStatus.SUPERSEDED.value == "superseded"
    assert {member.value for member in DiplomaticNegotiationStatus} == {
        "opened",
        "ongoing",
        "stalled",
        "closed",
        "abandoned",
        "unknown",
    }


def test_instrument_vocabularies_are_closed() -> None:
    assert {member.value for member in DiplomaticInstrumentKind} == {
        "proposal",
        "promise",
        "agreement",
        "dispute",
        "shared_project",
        "unknown",
    }
    assert {member.value for member in DiplomaticInstrumentStatus} == {
        "proposed",
        "open",
        "apparently_accepted",
        "rejected",
        "withdrawn",
        "unresolved",
        "active",
        "completed_claimed",
        "superseded",
        "expired",
        "unknown",
    }
    assert {member.value for member in DiplomaticTermKind} == {
        "material_exchange",
        "shared_work",
        "passage",
        "recognition",
        "procedure",
        "unknown",
    }


def test_provenance_and_termination_vocabularies_are_closed() -> None:
    assert {member.value for member in DiplomaticProvenance} == {
        "self_declared",
        "principal_declared",
        "communicated",
        "witnessed_contact",
        "written_record",
        "representation_belief",
        "collective_decision",
        "unknown",
    }
    assert {member.value for member in DiplomaticTerminationKind} == {
        "party_withdrew",
        "envoy_recalled",
        "envoy_resigned",
        "agreement_disputed",
        "superseded",
        "expired",
        "treaty_terminated",
        "unknown",
    }


def test_misrepresentation_and_conflict_vocabularies_are_closed() -> None:
    assert {member.value for member in DiplomaticMisrepresentationKind} == {
        "mandate_unrecognized",
        "scope_exceeded",
        "contradicted_by_principal",
        "contested_by_member",
        "unknown",
    }
    assert {member.value for member in DiplomaticConflictKind} == {
        "duplicate_envoy",
        "contradictory_terms",
        "conflicting_party",
        "agreement_dispute",
        "treaty_participant_conflict",
        "treaty_record_conflict",
        "treaty_recollection_conflict",
        "unknown",
    }


@pytest.mark.parametrize("prefix", _ALL_PREFIXES)
def test_prefix_accepts_exactly_sixteen_lowercase_hex(prefix: str) -> None:
    valid = prefix + "0123456789abcdef"
    assert require_diplomacy_id(valid, prefix) == valid

    for invalid in (
        prefix + "0123456789abcde",
        prefix + "0123456789abcdef0",
        prefix + "0123456789ABCDEF",
        prefix + "g123456789abcdef",
        "dpy-" + "0" * DIPLOMACY_ID_HEX_LEN,
        valid + "0",
        None,
        123,
    ):
        with pytest.raises(DiplomacyError) as excinfo:
            require_diplomacy_id(invalid, prefix)
        assert excinfo.value.code == "diplomacy_invalid_id"


def test_unknown_prefix_is_rejected() -> None:
    with pytest.raises(DiplomacyError) as excinfo:
        require_diplomacy_id("dpy-" + "0" * 16, "dpy-")
    assert excinfo.value.code == "diplomacy_invalid_id"


@pytest.mark.parametrize(
    "token",
    (
        "owner-a",
        "run.1:owner/alpha",
        "agent@host",
        "x",
    ),
)
def test_token_accepts_bounded_opaque_shapes(token: str) -> None:
    assert require_diplomacy_token(token, max_chars=64) == token


@pytest.mark.parametrize(
    "token",
    (
        "",
        " leading",
        "trailing ",
        "has space",
        "line\nbreak",
        "x" * 65,
        None,
        7,
    ),
)
def test_token_rejects_unbounded_or_free_text(token: object) -> None:
    with pytest.raises(DiplomacyError) as excinfo:
        require_diplomacy_token(token, max_chars=64)
    assert excinfo.value.code == "diplomacy_untrusted_token"


def test_subject_grammar_rejects_none_and_free_text() -> None:
    assert require_diplomacy_subject("trade.route:1") == "trade.route:1"
    assert require_diplomacy_subject("a") == "a"
    for invalid in (
        "none",
        "Trade",
        "two words",
        "",
        "a" * 33,
        None,
        1,
    ):
        with pytest.raises(DiplomacyError) as excinfo:
            require_diplomacy_subject(invalid)
        assert excinfo.value.code == "diplomacy_invalid_subject"


def test_locked_policy_rejects_any_mutation() -> None:
    policy = default_diplomacy_policy()
    assert policy == DiplomacyPolicy()
    assert policy.agreement_min_party_declarations == 2
    assert policy.max_relations == 24
    assert policy.max_parties == 32
    assert policy.max_contacts_per_relation == 16
    assert policy.max_envoys_per_relation == 8
    assert policy.max_negotiations_per_relation == 8
    assert policy.max_instruments_per_relation == 24
    assert policy.max_declarations_per_instrument == 16
    assert policy.max_anchor_refs == 8
    assert policy.max_total_records == 320
    assert policy.max_frame_chars == 320

    with pytest.raises(DiplomacyError) as excinfo:
        DiplomacyPolicy(max_relations=25)
    assert excinfo.value.code == "diplomacy_policy_not_locked"

    with pytest.raises(DiplomacyError) as excinfo:
        DiplomacyPolicy(max_relations=24.0)  # type: ignore[arg-type]
    assert excinfo.value.code == "diplomacy_policy_not_locked"


def test_policy_has_no_forbidden_field_names() -> None:
    assert_diplomacy_no_forbidden_fields(
        [field.name for field in fields(DiplomacyPolicy)]
    )

    bad = make_dataclass("BadDiplomacyRecord", [("overall_relation", float)])
    with pytest.raises(DiplomacyError) as excinfo:
        assert_diplomacy_no_forbidden_fields([field.name for field in fields(bad)])
    assert excinfo.value.code == "diplomacy_forbidden_field"


def test_error_exposes_only_a_stable_code() -> None:
    error = DiplomacyError("diplomacy_invalid_id")
    assert error.code == "diplomacy_invalid_id"
    assert str(error) == "diplomacy_invalid_id"
    assert error.args == ("diplomacy_invalid_id",)


@pytest.mark.parametrize("prefix", _ALL_PREFIXES)
def test_record_ids_are_deterministic_and_owner_scoped(prefix: str) -> None:
    first = diplomacy_record_id(prefix, "owner-a", 1, "subject")
    again = diplomacy_record_id(prefix, "owner-a", 1, "subject")
    other_owner = diplomacy_record_id(prefix, "owner-b", 1, "subject")
    other_tick = diplomacy_record_id(prefix, "owner-a", 2, "subject")

    assert first == again
    assert first != other_owner
    assert first != other_tick
    assert first.startswith(prefix)
    assert len(first) == len(prefix) + DIPLOMACY_ID_HEX_LEN
    assert require_diplomacy_id(first, prefix) == first


def test_record_id_rejects_unknown_prefix() -> None:
    with pytest.raises(DiplomacyError) as excinfo:
        diplomacy_record_id("dpy-", "owner-a", 1)
    assert excinfo.value.code == "diplomacy_invalid_id"


def test_scope_coverage_matrix_is_closed() -> None:
    for instrument_kind, allowed in DIPLOMACY_SCOPE_COVERAGE.items():
        for scope in _ALL_SCOPES:
            covered = diplomacy_scope_covers(
                scope_kind=scope,
                duration_kind="until_revoked",
                instrument_kind=instrument_kind,
                scope_subject=None,
                topic_subject=None,
            )
            assert covered is (scope in allowed), (instrument_kind, scope)

    for scope in _ALL_SCOPES:
        assert (
            diplomacy_scope_covers(
                scope_kind=scope,
                duration_kind="until_revoked",
                instrument_kind="unknown",
                scope_subject=None,
                topic_subject=None,
            )
            is False
        )


@pytest.mark.parametrize(
    ("instrument_kind", "covering_scope"),
    (
        ("agreement", "negotiate"),
        ("promise", "speak_for"),
        ("shared_project", "coordinate_project"),
    ),
)
def test_short_mandates_never_cover_long_running_instruments(
    instrument_kind: str, covering_scope: str
) -> None:
    assert instrument_kind in LONG_RUNNING_INSTRUMENT_KINDS
    for duration in ("single_act", "occasion"):
        assert (
            diplomacy_scope_covers(
                scope_kind=covering_scope,
                duration_kind=duration,
                instrument_kind=instrument_kind,
                scope_subject=None,
                topic_subject=None,
            )
            is False
        )
    for duration in ("until_tick", "until_revoked"):
        assert (
            diplomacy_scope_covers(
                scope_kind=covering_scope,
                duration_kind=duration,
                instrument_kind=instrument_kind,
                scope_subject=None,
                topic_subject=None,
            )
            is True
        )


def test_short_mandates_still_cover_single_act_instruments() -> None:
    assert (
        diplomacy_scope_covers(
            scope_kind="negotiate",
            duration_kind="single_act",
            instrument_kind="proposal",
            scope_subject=None,
            topic_subject=None,
        )
        is True
    )


def test_named_scope_subject_must_match_the_topic() -> None:
    assert (
        diplomacy_scope_covers(
            scope_kind="negotiate",
            duration_kind="until_revoked",
            instrument_kind="agreement",
            scope_subject="trade",
            topic_subject="trade",
        )
        is True
    )
    assert (
        diplomacy_scope_covers(
            scope_kind="negotiate",
            duration_kind="until_revoked",
            instrument_kind="agreement",
            scope_subject="trade",
            topic_subject="passage",
        )
        is False
    )
    assert (
        diplomacy_scope_covers(
            scope_kind="negotiate",
            duration_kind="until_revoked",
            instrument_kind="agreement",
            scope_subject="trade",
            topic_subject=None,
        )
        is False
    )
    assert (
        diplomacy_scope_covers(
            scope_kind="negotiate",
            duration_kind="until_revoked",
            instrument_kind="agreement",
            scope_subject=None,
            topic_subject="trade",
        )
        is True
    )


def test_scope_coverage_accepts_enum_inputs() -> None:
    assert (
        diplomacy_scope_covers(
            scope_kind="negotiate",
            duration_kind="until_revoked",
            instrument_kind=DiplomaticInstrumentKind.AGREEMENT,
            scope_subject=None,
            topic_subject=None,
        )
        is True
    )
    assert (
        diplomacy_scope_covers(
            scope_kind="carry_message",
            duration_kind="until_tick",
            instrument_kind=DiplomaticInstrumentKind.AGREEMENT,
            scope_subject=None,
            topic_subject=None,
        )
        is False
    )
