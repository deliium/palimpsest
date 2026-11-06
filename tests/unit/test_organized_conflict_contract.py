# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from pathlib import Path

import pytest

from agents.cognition.organized_conflict import (
    CONFLICT_CONTRADICTION_ID_PREFIX,
    CONFLICT_EPISODE_ID_PREFIX,
    CONFLICT_ID_PREFIXES,
    CONFLICT_INTERPRETATION_ID_PREFIX,
    CONFLICT_OBSERVATION_ID_PREFIX,
    CONFLICT_OPERATION_COMMANDS,
    CONFLICT_OUTCOME_ID_PREFIX,
    CONFLICT_PARTICIPATION_ID_PREFIX,
    CONFLICT_PLAN_ID_PREFIX,
    CONFLICT_TERMINATION_ID_PREFIX,
    ConflictContradictionKind,
    ConflictInterpretationKind,
    ConflictOperation,
    ConflictOutcomeKind,
    ConflictParticipationStance,
    ConflictPlanStatus,
    ConflictProvenance,
    ConflictRole,
    ConflictTargetKind,
    ConflictTerminationKind,
    OrganizedConflictError,
    assert_conflict_no_forbidden_fields,
    conflict_group_token,
    conflict_record_id,
    conflict_target_token,
    require_conflict_id,
    require_conflict_token,
)
from analysis.organized_conflict_contract import (
    ORGANIZED_CONFLICT_CANDIDATE_PREFIX,
    ORGANIZED_CONFLICT_EDGE_PREFIX,
    ORGANIZED_CONFLICT_PUBLICATION_PREFIX,
)

_SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"


def test_operation_vocabulary_is_exactly_eight() -> None:
    assert {item.value for item in ConflictOperation} == {
        "coordinated_attack",
        "defense",
        "movement_group",
        "resource_capture",
        "structure_attack",
        "route_blocking",
        "retreat",
        "assistance",
    }
    assert len(ConflictRole) == 9
    assert len(ConflictTargetKind) == 7
    assert len(ConflictPlanStatus) == 6
    assert len(ConflictParticipationStance) == 4
    assert len(ConflictInterpretationKind) == 10
    assert len(ConflictProvenance) == 5
    assert len(ConflictOutcomeKind) == 10
    assert len(ConflictContradictionKind) == 4
    assert len(ConflictTerminationKind) == 4


def test_operation_command_matrix_uses_only_existing_commands() -> None:
    assert set(CONFLICT_OPERATION_COMMANDS) == set(ConflictOperation)
    assert CONFLICT_OPERATION_COMMANDS[ConflictOperation.COORDINATED_ATTACK] == {
        "attack"
    }
    assert CONFLICT_OPERATION_COMMANDS[ConflictOperation.DEFENSE] == {
        "attack",
        "help",
        "move",
    }
    assert CONFLICT_OPERATION_COMMANDS[ConflictOperation.MOVEMENT_GROUP] == {
        "move",
        "transport",
    }
    assert CONFLICT_OPERATION_COMMANDS[ConflictOperation.RESOURCE_CAPTURE] == {
        "take",
        "give",
    }
    assert CONFLICT_OPERATION_COMMANDS[ConflictOperation.STRUCTURE_ATTACK] == {
        "oppose_public_good",
        "attack",
    }
    assert CONFLICT_OPERATION_COMMANDS[ConflictOperation.ROUTE_BLOCKING] == {
        "move",
        "attack",
        "flee",
        "help",
    }
    assert CONFLICT_OPERATION_COMMANDS[ConflictOperation.RETREAT] == {"flee"}
    assert CONFLICT_OPERATION_COMMANDS[ConflictOperation.ASSISTANCE] == {
        "help",
        "feed",
        "transport",
    }
    source = (_SOURCE_ROOT / "world" / "actions.py").read_text(encoding="utf-8")
    for names in CONFLICT_OPERATION_COMMANDS.values():
        for name in names:
            assert f'default="{name}"' in source


def test_conflict_ids_are_content_addressed_and_bounded() -> None:
    first = conflict_record_id(CONFLICT_PLAN_ID_PREFIX, "seed", 3)
    second = conflict_record_id(CONFLICT_PLAN_ID_PREFIX, "seed", 3)
    other = conflict_record_id(CONFLICT_PLAN_ID_PREFIX, "seed", 4)
    assert first == second
    assert first != other
    assert first.startswith("ocp-")
    assert len(first) == len("ocp-") + 16
    assert require_conflict_id("plan_id", first, prefixes=frozenset({"ocp-"})) == first
    for prefix in (
        CONFLICT_EPISODE_ID_PREFIX,
        CONFLICT_PLAN_ID_PREFIX,
        CONFLICT_PARTICIPATION_ID_PREFIX,
        CONFLICT_OBSERVATION_ID_PREFIX,
        CONFLICT_INTERPRETATION_ID_PREFIX,
        CONFLICT_OUTCOME_ID_PREFIX,
        CONFLICT_CONTRADICTION_ID_PREFIX,
        CONFLICT_TERMINATION_ID_PREFIX,
    ):
        value = conflict_record_id(prefix, "x")
        assert require_conflict_id("row_id", value) == value
    with pytest.raises(OrganizedConflictError):
        require_conflict_id("plan_id", "ocp-xyz", prefixes=frozenset({"ocp-"}))
    with pytest.raises(OrganizedConflictError):
        require_conflict_id("plan_id", first.upper(), prefixes=frozenset({"ocp-"}))


def test_conflict_tokens_are_opaque_and_deterministic() -> None:
    assert conflict_target_token("agent-1") == conflict_target_token("agent-1")
    assert conflict_target_token("agent-1") != conflict_target_token("agent-2")
    assert len(conflict_target_token("agent-1")) == 16
    left = conflict_group_token(["b" * 16, "a" * 16])
    right = conflict_group_token(["a" * 16, "b" * 16])
    assert left == right
    assert require_conflict_token("token", "a" * 16) == "a" * 16
    with pytest.raises(OrganizedConflictError):
        require_conflict_token("token", "not a token!")
    with pytest.raises(OrganizedConflictError):
        conflict_group_token(["not-a-token"])


def test_forbidden_war_state_fields_are_rejected() -> None:
    for name in (
        "at_war",
        "war_state",
        "army_id",
        "conflict_registry",
        "winner",
        "loser",
        "legitimacy",
        "score",
        "composite",
        "truth",
        "enforced",
    ):
        with pytest.raises(OrganizedConflictError):
            assert_conflict_no_forbidden_fields([name])
    assert_conflict_no_forbidden_fields(["plan_id", "tick"])
    assert_conflict_no_forbidden_fields({"plan_id": "ocp-" + "a" * 16})


def test_analysis_prefixes_do_not_overlap_diplomacy() -> None:
    diplomacy_prefixes = {"dip-", "dip-edge-", "dip-pub-"}
    conflict_prefixes = {
        ORGANIZED_CONFLICT_CANDIDATE_PREFIX,
        ORGANIZED_CONFLICT_EDGE_PREFIX,
        ORGANIZED_CONFLICT_PUBLICATION_PREFIX,
        *CONFLICT_ID_PREFIXES.values(),
    }
    assert conflict_prefixes.isdisjoint(diplomacy_prefixes)
    assert len(set(CONFLICT_ID_PREFIXES.values())) == 8
