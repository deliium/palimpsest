"""V4-09 delegation-representation vocabulary and locked policy."""

from __future__ import annotations

from dataclasses import fields, replace

import pytest

from agents.cognition import (
    REPRESENTATION_POLICY_VERSION,
    RepresentationConflictKind,
    RepresentationDurationKind,
    RepresentationError,
    RepresentationPolicy,
    RepresentationPositionStance,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationRecognitionBasis,
    RepresentationRevocationKind,
    RepresentationScopeKind,
    RepresentationStatus,
    default_representation_policy,
    require_representation_id,
    require_representation_scope_subject,
    require_representation_token,
)
from agents.cognition.delegation_representation import (
    representation_mandate_id,
    representation_position_id,
)

pytestmark = pytest.mark.unit


def test_principal_kinds_are_closed() -> None:
    assert {member.value for member in RepresentationPrincipalKind} == {
        "agent",
        "organization",
        "settlement",
        "coalition",
        "unknown",
    }


def test_scope_duration_and_status_are_closed() -> None:
    assert {member.value for member in RepresentationScopeKind} == {
        "speak_for",
        "negotiate",
        "carry_message",
        "coordinate_project",
        "transact",
        "decide",
        "unknown",
    }
    assert {member.value for member in RepresentationDurationKind} == {
        "single_act",
        "occasion",
        "until_tick",
        "until_revoked",
        "unknown",
    }
    assert {member.value for member in RepresentationStatus} == {
        "claimed",
        "recognized",
        "contested",
        "rejected",
        "revoked",
        "expired",
        "superseded",
        "unknown",
    }


def test_provenance_positions_revocations_bases_and_conflicts_are_closed() -> None:
    assert {member.value for member in RepresentationProvenance} == {
        "self_declared",
        "principal_declared",
        "communicated",
        "witnessed_act",
        "written_record",
        "office_belief",
        "collective_decision",
        "procedure_belief",
        "unknown",
    }
    assert {member.value for member in RepresentationPositionStance} == {
        "support",
        "oppose",
        "abstain",
        "unknown",
    }
    assert {member.value for member in RepresentationRevocationKind} == {
        "principal_revoked",
        "representative_resigned",
        "collective_decision_revoked",
        "scope_expired",
        "office_lost",
        "contested",
        "unknown",
    }
    assert {member.value for member in RepresentationRecognitionBasis} == {
        "principal_declaration",
        "independent_support",
        "office_authority",
        "collective_decision",
        "written_authorization",
        "none",
        "unknown",
    }
    assert {member.value for member in RepresentationConflictKind} == {
        "duplicate_mandate",
        "contradictory_scope",
        "conflicting_principal",
        "revocation_dispute",
        "unknown",
    }


def test_policy_version_and_locked_values() -> None:
    assert REPRESENTATION_POLICY_VERSION == "delegation-representation.v1"
    policy = default_representation_policy()
    assert policy == RepresentationPolicy()
    assert policy.recognition_min_independent_roots == 2
    assert policy.max_mandates == 32
    assert policy.max_total_records == 320
    assert policy.max_frame_chars == 384


def test_policy_mutation_fails_closed() -> None:
    with pytest.raises(RepresentationError) as excinfo:
        replace(default_representation_policy(), max_mandates=33)
    assert excinfo.value.code == "representation_policy_not_locked"


def test_policy_has_no_forbidden_field_names() -> None:
    names = {field.name for field in fields(RepresentationPolicy)}
    assert not names & {
        "truth",
        "verified",
        "legitimate",
        "authority",
        "permission",
        "allowed",
        "winner",
        "proxy",
        "mandate_valid",
    }


def test_mandate_id_is_deterministic_and_owner_scoped() -> None:
    first = representation_mandate_id(
        "agent-a",
        3,
        RepresentationPrincipalKind.AGENT,
        "agent-b",
        "agent-c",
        RepresentationScopeKind.SPEAK_FOR,
        "border",
        RepresentationDurationKind.UNTIL_REVOKED,
    )
    second = representation_mandate_id(
        "agent-a",
        3,
        RepresentationPrincipalKind.AGENT,
        "agent-b",
        "agent-c",
        RepresentationScopeKind.SPEAK_FOR,
        "border",
        RepresentationDurationKind.UNTIL_REVOKED,
    )
    other_owner = representation_mandate_id(
        "agent-d",
        3,
        RepresentationPrincipalKind.AGENT,
        "agent-b",
        "agent-c",
        RepresentationScopeKind.SPEAK_FOR,
        "border",
        RepresentationDurationKind.UNTIL_REVOKED,
    )
    other_tick = representation_mandate_id(
        "agent-a",
        4,
        RepresentationPrincipalKind.AGENT,
        "agent-b",
        "agent-c",
        RepresentationScopeKind.SPEAK_FOR,
        "border",
        RepresentationDurationKind.UNTIL_REVOKED,
    )
    assert first == second
    assert first.startswith("rmd-")
    assert len(first) == 20
    assert len({first, other_owner, other_tick}) == 3


def test_position_id_is_deterministic_and_stance_sensitive() -> None:
    first = representation_position_id(
        "agent-a",
        "rmd-" + "1" * 16,
        "agent-b",
        2,
        RepresentationPositionStance.SUPPORT,
        0,
    )
    second = representation_position_id(
        "agent-a",
        "rmd-" + "1" * 16,
        "agent-b",
        2,
        RepresentationPositionStance.SUPPORT,
        0,
    )
    opposed = representation_position_id(
        "agent-a",
        "rmd-" + "1" * 16,
        "agent-b",
        2,
        RepresentationPositionStance.OPPOSE,
        0,
    )
    assert first == second
    assert first != opposed
    assert first.startswith("rmp-")


def test_id_validators_reject_foreign_prefixes_and_short_ids() -> None:
    assert require_representation_id("rmd-" + "a" * 16, "rmd-").startswith("rmd-")
    for value in ("rmd-" + "a" * 15, "rmp-" + "a" * 16, "rmd-" + "A" * 16):
        with pytest.raises(RepresentationError) as excinfo:
            require_representation_id(value, "rmd-")
        assert excinfo.value.code == "representation_invalid_id"


def test_token_and_scope_validators_are_bounded() -> None:
    assert require_representation_token("agent-1", max_chars=32) == "agent-1"
    for value in ("", " has-space", "bad\n", "x" * 33):
        with pytest.raises(RepresentationError):
            require_representation_token(value, max_chars=32)

    assert require_representation_scope_subject("border.north:1") == "border.north:1"
    for value in ("none", "UpperCase", "space here", "", "x" * 33):
        with pytest.raises(RepresentationError):
            require_representation_scope_subject(value)
