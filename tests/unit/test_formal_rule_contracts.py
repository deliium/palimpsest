"""V4-06 formal-rule vocabulary, stage progression, and identity grammar."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from agents.cognition import (
    FORMAL_RULE_FORBIDDEN_FIELD_NAMES,
    FORMAL_RULE_ID_HEX_LEN,
    FORMAL_RULE_POLICY_VERSION,
    FORMAL_RULE_STAGE_ORDER,
    FormalRuleAuthorityKind,
    FormalRuleConstraintKind,
    FormalRuleError,
    FormalRuleEvidenceChannel,
    FormalRulePolicy,
    FormalRulePositionStance,
    FormalRuleProvenance,
    FormalRuleRecognition,
    FormalRuleReportKind,
    FormalRuleRepresentationStatus,
    FormalRuleResponseKind,
    FormalRuleSanctionKind,
    FormalRuleScopeKind,
    FormalRuleStage,
    FormalRuleStatus,
    default_formal_rule_policy,
    formal_rule_evidence_id,
    formal_rule_exception_id,
    formal_rule_id,
    formal_rule_position_id,
    formal_rule_response_id,
    formal_rule_scope_digest,
    formal_rule_system_id,
    formal_rule_version_id,
    require_formal_rule_evidence_id,
    require_formal_rule_exception_id,
    require_formal_rule_id,
    require_formal_rule_policy,
    require_formal_rule_position_id,
    require_formal_rule_response_id,
    require_formal_rule_system_id,
    require_formal_rule_version_id,
)

pytestmark = pytest.mark.unit

MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "agents"
    / "cognition"
    / "formal_rules.py"
)
OWNER = "agent-1"
OTHER_OWNER = "agent-2"
SCOPE = hashlib.sha256(b"scope").hexdigest()
OTHER_SCOPE = hashlib.sha256(b"other-scope").hexdigest()
CONTENT = hashlib.sha256(b"content").hexdigest()

EXPECTED_LIMITS = {
    "max_systems": 8,
    "max_rules": 32,
    "max_versions_per_rule": 16,
    "max_evidence_per_rule": 64,
    "max_positions_per_rule": 64,
    "max_responses_per_rule": 64,
    "max_exceptions_per_rule": 8,
    "max_sanctions_per_rule": 8,
    "max_scope_anchors": 8,
    "max_total_records": 512,
    "min_supporters_for_recognition": 2,
    "min_enforcement_recurrence": 2,
    "version_window_ticks": 64,
    "max_frame_chars": 384,
    "max_relations": 32,
}


def _system_id(scope: str = SCOPE) -> str:
    return formal_rule_system_id(
        OWNER, scope, FormalRuleAuthorityKind.CUSTOM
    )


def _rule_id(system_id: str | None = None) -> str:
    return formal_rule_id(
        OWNER,
        _system_id() if system_id is None else system_id,
        FormalRuleConstraintKind.PROHIBITION,
        "attack",
        SCOPE,
    )


def test_policy_version_and_limits_are_locked() -> None:
    policy = default_formal_rule_policy()
    assert type(policy) is FormalRulePolicy
    assert policy.version == FORMAL_RULE_POLICY_VERSION == "formal-rules.v1"
    assert default_formal_rule_policy() is policy
    for name, expected in EXPECTED_LIMITS.items():
        assert getattr(policy, name) == expected

    for kwargs in (
        {"max_rules": 33},
        {"max_systems": 9},
        {"min_supporters_for_recognition": 1},
        {"max_frame_chars": 512},
        {"version": "formal-rules.v0"},
    ):
        with pytest.raises(FormalRuleError) as excinfo:
            FormalRulePolicy(**kwargs)
        assert excinfo.value.code == "formal_rule_policy_not_locked"

    assert require_formal_rule_policy(None) is policy
    assert require_formal_rule_policy(policy) is policy
    with pytest.raises(FormalRuleError) as excinfo:
        require_formal_rule_policy(object())
    assert excinfo.value.code == "formal_rule_policy_mismatch"


def test_every_id_prefix_round_trips_and_rejects_foreign_ids() -> None:
    system = _system_id()
    rule = _rule_id(system)
    version = formal_rule_version_id(rule, 1, CONTENT)
    evidence = formal_rule_evidence_id(
        rule, 0, FormalRuleEvidenceChannel.OBSERVED, "artifact:record-1"
    )
    position = formal_rule_position_id(
        rule, "agent-1", FormalRulePositionStance.PROPONENT, 0
    )
    response = formal_rule_response_id(
        rule, "agent-1", FormalRuleResponseKind.FOLLOW, 4
    )
    exception = formal_rule_exception_id(rule, 0, CONTENT)

    pairs = (
        (system, "frs-", require_formal_rule_system_id),
        (rule, "frl-", require_formal_rule_id),
        (version, "frv-", require_formal_rule_version_id),
        (evidence, "fre-", require_formal_rule_evidence_id),
        (position, "frp-", require_formal_rule_position_id),
        (response, "frr-", require_formal_rule_response_id),
        (exception, "frx-", require_formal_rule_exception_id),
    )
    for identifier, prefix, require in pairs:
        assert identifier.startswith(prefix)
        assert len(identifier) == len(prefix) + FORMAL_RULE_ID_HEX_LEN
        assert require(identifier) == identifier
        for _, _, other_require in pairs:
            if other_require is require:
                continue
            with pytest.raises(FormalRuleError) as excinfo:
                other_require(identifier)
            assert excinfo.value.code == "formal_rule_invalid_id"

    for malformed in (
        "",
        "frl-",
        "frl-" + "A" * FORMAL_RULE_ID_HEX_LEN,
        "frl-" + "g" * FORMAL_RULE_ID_HEX_LEN,
        "frl-" + "0" * (FORMAL_RULE_ID_HEX_LEN - 1),
        "frl-" + "0" * (FORMAL_RULE_ID_HEX_LEN + 1),
        "orgc-" + "0" * FORMAL_RULE_ID_HEX_LEN,
    ):
        with pytest.raises(FormalRuleError) as excinfo:
            require_formal_rule_id(malformed)
        assert excinfo.value.code == "formal_rule_invalid_id"


def test_system_and_rule_ids_are_content_addressed_and_owner_scoped() -> None:
    system = _system_id()
    assert system == _system_id()
    assert system != formal_rule_system_id(
        OTHER_OWNER, SCOPE, FormalRuleAuthorityKind.CUSTOM
    )
    assert system != formal_rule_system_id(
        OWNER, OTHER_SCOPE, FormalRuleAuthorityKind.CUSTOM
    )
    assert system != formal_rule_system_id(
        OWNER, SCOPE, FormalRuleAuthorityKind.OFFICE
    )

    rule = _rule_id(system)
    assert rule == _rule_id(system)
    assert rule != formal_rule_id(
        OTHER_OWNER,
        system,
        FormalRuleConstraintKind.PROHIBITION,
        "attack",
        SCOPE,
    )
    assert rule != formal_rule_id(
        OWNER,
        system,
        FormalRuleConstraintKind.OBLIGATION,
        "attack",
        SCOPE,
    )
    assert rule != formal_rule_id(
        OWNER,
        system,
        FormalRuleConstraintKind.PROHIBITION,
        "give",
        SCOPE,
    )
    assert rule != formal_rule_id(
        OWNER,
        system,
        FormalRuleConstraintKind.PROHIBITION,
        "attack",
        OTHER_SCOPE,
    )
    assert formal_rule_version_id(rule, 1, CONTENT) == formal_rule_version_id(
        rule, 1, CONTENT
    )
    assert formal_rule_version_id(rule, 1, CONTENT) != formal_rule_version_id(
        rule, 2, CONTENT
    )

    with pytest.raises(FormalRuleError) as excinfo:
        formal_rule_id(
            OWNER, system, FormalRuleConstraintKind.PROHIBITION, "Attack", SCOPE
        )
    assert excinfo.value.code == "formal_rule_invalid_action"
    with pytest.raises(FormalRuleError) as excinfo:
        formal_rule_version_id(rule, 0, CONTENT)
    assert excinfo.value.code == "formal_rule_invalid_ordinal"


def test_scope_digest_is_sorted_deduplicated_and_bounded() -> None:
    first = formal_rule_scope_digest(FormalRuleScopeKind.PLACE, ["b", "a"])
    second = formal_rule_scope_digest(FormalRuleScopeKind.PLACE, ["a", "b", "a"])
    assert first == second
    assert len(first) == 64
    assert first == first.lower()
    assert all(character in "0123456789abcdef" for character in first)

    assert first != formal_rule_scope_digest(FormalRuleScopeKind.PERSON, ["a", "b"])
    assert formal_rule_scope_digest(
        FormalRuleScopeKind.UNSPECIFIED, []
    ) == formal_rule_scope_digest(FormalRuleScopeKind.UNSPECIFIED, [])

    anchors = [f"anchor-{index}" for index in range(9)]
    with pytest.raises(FormalRuleError) as excinfo:
        formal_rule_scope_digest(FormalRuleScopeKind.PLACE, anchors)
    assert excinfo.value.code == "formal_rule_scope_limit"

    with pytest.raises(FormalRuleError) as excinfo:
        formal_rule_scope_digest(FormalRuleScopeKind.PLACE, "a")
    assert excinfo.value.code == "formal_rule_invalid_anchor"


def test_stage_progression_is_monotone_and_closed() -> None:
    assert tuple(FORMAL_RULE_STAGE_ORDER) == tuple(FormalRuleStage)
    assert list(FORMAL_RULE_STAGE_ORDER.values()) == [0, 1, 2, 3, 4]
    assert tuple(stage.value for stage in FormalRuleStage) == (
        "habit",
        "expectation",
        "norm",
        "documented",
        "recognized_enforcement",
    )


def test_constraint_vocabulary_has_no_physical_member() -> None:
    assert tuple(kind.value for kind in FormalRuleConstraintKind) == (
        "prohibition",
        "obligation",
        "permission",
    )
    for kind in FormalRuleConstraintKind:
        assert "physical" not in kind.value
        assert "impossible" not in kind.value

    for enum in (
        FormalRuleConstraintKind,
        FormalRuleScopeKind,
        FormalRuleAuthorityKind,
        FormalRuleRecognition,
        FormalRuleStatus,
        FormalRulePositionStance,
        FormalRuleResponseKind,
        FormalRuleEvidenceChannel,
        FormalRuleSanctionKind,
        FormalRuleReportKind,
        FormalRuleRepresentationStatus,
        FormalRuleProvenance,
    ):
        for member in enum:
            assert "physical_law" != member.value
            assert "world_law" != member.value


def test_forbidden_law_vocabulary_is_closed() -> None:
    expected = frozenset(
        {
            "law",
            "statute",
            "legal_code",
            "court",
            "judge",
            "police",
            "government",
            "jurisdiction",
            "sovereign",
            "rule_engine",
            "sanction_engine",
            "policy_engine",
            "enforced_by_world",
            "physical_law",
            "objective_rule",
            "global_rule_registry",
            "current_law",
            "binding_rule",
        }
    )
    assert type(FORMAL_RULE_FORBIDDEN_FIELD_NAMES) is frozenset
    assert FORMAL_RULE_FORBIDDEN_FIELD_NAMES == expected


def test_no_global_nondeterminism_imports() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)

    assert imported <= {
        "__future__",
        "agents",
        "collections",
        "dataclasses",
        "decimal",
        "enum",
        "hashlib",
        "json",
        "logging",
        "re",
        "types",
        "typing",
    }
    assert not imported & {
        "analysis",
        "api",
        "experiments",
        "infrastructure",
        "memory",
        "observer",
        "persistence",
        "simulation",
        "social",
        "world",
    }
    source = MODULE.read_text(encoding="utf-8")
    assert "hash(" not in source
    assert "uuid4" not in source
    assert "time.time" not in source
