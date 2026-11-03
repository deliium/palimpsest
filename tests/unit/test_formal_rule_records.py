"""V4-06 formal-rule records, ledger invariants, and canonical digest."""

from __future__ import annotations

import hashlib

import pytest

from agents.cognition import (
    FORMAL_RULE_FORBIDDEN_FIELD_NAMES,
    FORMAL_RULE_POLICY_VERSION,
    FormalRule,
    FormalRuleAuthorityKind,
    FormalRuleConstraintKind,
    FormalRuleError,
    FormalRuleEvidence,
    FormalRuleEvidenceChannel,
    FormalRuleException,
    FormalRuleLedger,
    FormalRulePositionStance,
    FormalRuleProponent,
    FormalRuleProvenance,
    FormalRuleRecognition,
    FormalRuleResponse,
    FormalRuleResponseKind,
    FormalRuleRevisionKind,
    FormalRuleSanctionExpectation,
    FormalRuleSanctionKind,
    FormalRuleScope,
    FormalRuleScopeKind,
    FormalRuleStage,
    FormalRuleStatus,
    FormalRuleSystem,
    FormalRuleVersion,
    FormalRuleWrittenRepresentation,
    empty_formal_rule_ledger,
    formal_rule_evidence_id,
    formal_rule_exception_id,
    formal_rule_id,
    formal_rule_ledger_digest,
    formal_rule_position_id,
    formal_rule_response_id,
    formal_rule_system_id,
    formal_rule_version_id,
    require_owner_formal_rules,
)
from agents.models import AgentId

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
OTHER_OWNER = AgentId("agent-2")
TICK = 10
CONTENT = hashlib.sha256(b"version-content").hexdigest()
SCOPE = FormalRuleScope(FormalRuleScopeKind.ACTION, ("give",))
SYSTEM_ID = formal_rule_system_id(
    OWNER.value, SCOPE.digest, FormalRuleAuthorityKind.CUSTOM
)
RULE_ID = formal_rule_id(
    OWNER.value,
    SYSTEM_ID,
    FormalRuleConstraintKind.PROHIBITION,
    "attack",
    SCOPE.digest,
)


def _version(
    number: int = 1,
    *,
    rule_id: str = RULE_ID,
    supersedes: str | None = None,
    stage: FormalRuleStage = FormalRuleStage.HABIT,
    written: FormalRuleWrittenRepresentation | None = None,
) -> FormalRuleVersion:
    return FormalRuleVersion(
        version_id=formal_rule_version_id(
            rule_id, number, hashlib.sha256(f"content-{number}".encode()).hexdigest()
        ),
        rule_id=rule_id,
        version_number=number,
        stage=stage,
        constraint=FormalRuleConstraintKind.PROHIBITION,
        authority=FormalRuleAuthorityKind.CUSTOM,
        recognition=FormalRuleRecognition.UNRECOGNIZED,
        scope=SCOPE,
        written=written,
        tick=TICK,
        revision_kind=FormalRuleRevisionKind.INITIAL
        if number == 1
        else FormalRuleRevisionKind.STAGE_PROMOTION,
        supersedes_version_id=supersedes,
        provenance=FormalRuleProvenance.DERIVED_FROM_NORM,
    )


def _evidence(
    ordinal: int = 0,
    *,
    rule_id: str = RULE_ID,
    channel: FormalRuleEvidenceChannel = FormalRuleEvidenceChannel.OBSERVED,
) -> FormalRuleEvidence:
    return FormalRuleEvidence(
        evidence_id=formal_rule_evidence_id(
            rule_id, ordinal, channel, f"lineage-{ordinal}"
        ),
        rule_id=rule_id,
        channel=channel,
        provenance=FormalRuleProvenance.SELF_AUTHORED,
        tick=TICK,
        lineage_ref=f"lineage-{ordinal}",
    )


def _proponent(
    ordinal: int = 0, *, rule_id: str = RULE_ID, actor: str = "agent-1"
) -> FormalRuleProponent:
    return FormalRuleProponent(
        position_id=formal_rule_position_id(
            rule_id, actor, FormalRulePositionStance.PROPONENT, ordinal
        ),
        rule_id=rule_id,
        actor_id=actor,
        stance=FormalRulePositionStance.PROPONENT,
        provenance=FormalRuleProvenance.SELF_AUTHORED,
        tick=TICK,
        ordinal=ordinal,
    )


def _response(
    tick: int = TICK, *, rule_id: str = RULE_ID, actor: str = "agent-1"
) -> FormalRuleResponse:
    return FormalRuleResponse(
        response_id=formal_rule_response_id(
            rule_id, actor, FormalRuleResponseKind.FOLLOW, tick
        ),
        rule_id=rule_id,
        actor_id=actor,
        kind=FormalRuleResponseKind.FOLLOW,
        tick=tick,
    )


def _exception(
    ordinal: int = 0, *, rule_id: str = RULE_ID
) -> FormalRuleException:
    return FormalRuleException(
        exception_id=formal_rule_exception_id(rule_id, ordinal, CONTENT),
        rule_id=rule_id,
        condition_digest=CONTENT,
        tick=TICK,
    )


def _sanction() -> FormalRuleSanctionExpectation:
    return FormalRuleSanctionExpectation(
        kind=FormalRuleSanctionKind.CRITICISM,
        severity=0.5,
        source="norm",
    )


def _rule(
    *,
    rule_id: str = RULE_ID,
    system_id: str = SYSTEM_ID,
    owner: AgentId = OWNER,
    action: str = "attack",
    versions: tuple[FormalRuleVersion, ...] | None = None,
    evidence: tuple[FormalRuleEvidence, ...] = (),
    proponents: tuple[FormalRuleProponent, ...] = (),
    responses: tuple[FormalRuleResponse, ...] = (),
    exceptions: tuple[FormalRuleException, ...] = (),
    status: FormalRuleStatus = FormalRuleStatus.ACTIVE,
    strength: float = 0.5,
) -> FormalRule:
    return FormalRule(
        rule_id=rule_id,
        system_id=system_id,
        owner_id=owner,
        stage=FormalRuleStage.HABIT,
        constraint=FormalRuleConstraintKind.PROHIBITION,
        action_token=action,
        scope=SCOPE,
        authority=FormalRuleAuthorityKind.CUSTOM,
        recognition=FormalRuleRecognition.UNRECOGNIZED,
        status=status,
        strength=strength,
        proponents=proponents,
        versions=(_version(),) if versions is None else versions,
        evidence=evidence,
        sanctions=(_sanction(),),
        exceptions=exceptions,
        responses=responses,
        first_tick=TICK,
        last_tick=TICK,
    )


def _system(
    *,
    system_id: str = SYSTEM_ID,
    owner: AgentId = OWNER,
    rule_ids: tuple[str, ...] | None = None,
    competing: tuple[str, ...] = (),
) -> FormalRuleSystem:
    return FormalRuleSystem(
        system_id=system_id,
        owner_id=owner,
        scope=SCOPE,
        authority=FormalRuleAuthorityKind.CUSTOM,
        status=FormalRuleStatus.ACTIVE,
        rule_ids=(RULE_ID,) if rule_ids is None else rule_ids,
        competing_system_ids=competing,
        first_tick=TICK,
        last_tick=TICK,
    )


def _ledger(
    *,
    owner: AgentId = OWNER,
    systems: tuple[FormalRuleSystem, ...] | None = None,
    rules: tuple[FormalRule, ...] | None = None,
) -> FormalRuleLedger:
    return FormalRuleLedger(
        owner_id=owner,
        systems=(_system(),) if systems is None else systems,
        rules=(_rule(),) if rules is None else rules,
    )


def test_ledger_requires_one_owner_and_rejects_foreign_ledgers() -> None:
    empty = empty_formal_rule_ledger(OWNER)
    assert empty.owner_id == OWNER
    assert empty.systems == ()
    assert empty.rules == ()
    assert empty.policy_version == FORMAL_RULE_POLICY_VERSION
    assert require_owner_formal_rules(empty, OWNER, field_name="ledger") is empty
    assert require_owner_formal_rules(None, OWNER, field_name="ledger") is None

    with pytest.raises(FormalRuleError) as excinfo:
        require_owner_formal_rules(empty, OTHER_OWNER, field_name="ledger")
    assert excinfo.value.code == "formal_rule_owner_mismatch"

    with pytest.raises(TypeError, match="ledger must be FormalRuleLedger"):
        require_owner_formal_rules(object(), OWNER, field_name="ledger")

    with pytest.raises(FormalRuleError) as excinfo:
        _ledger(
            rules=(_rule(),),
            systems=(_system(owner=OTHER_OWNER),),
        )
    assert excinfo.value.code == "formal_rule_owner_mismatch"

    with pytest.raises(FormalRuleError) as excinfo:
        _ledger(owner=OTHER_OWNER)
    assert excinfo.value.code == "formal_rule_owner_mismatch"


def test_system_rule_and_version_references_are_closed() -> None:
    ledger = _ledger()
    assert ledger.systems[0].rule_ids == (RULE_ID,)

    with pytest.raises(FormalRuleError) as excinfo:
        _ledger(systems=(_system(rule_ids=()),), rules=(_rule(),))
    assert excinfo.value.code == "formal_rule_invalid_ledger"

    other_system = formal_rule_system_id(
        OWNER.value, SCOPE.digest, FormalRuleAuthorityKind.OFFICE
    )
    with pytest.raises(FormalRuleError) as excinfo:
        _ledger(
            systems=(_system(),),
            rules=(_rule(system_id=other_system),),
        )
    assert excinfo.value.code == "formal_rule_invalid_ledger"

    wrong_rule = formal_rule_id(
        OWNER.value,
        SYSTEM_ID,
        FormalRuleConstraintKind.OBLIGATION,
        "give",
        SCOPE.digest,
    )
    with pytest.raises(FormalRuleError) as excinfo:
        _rule(evidence=(_evidence(rule_id=wrong_rule),))
    assert excinfo.value.code == "formal_rule_invalid_ledger"


def test_competing_system_links_are_symmetric() -> None:
    first_scope = FormalRuleScope(FormalRuleScopeKind.PLACE, ("square",))
    second_scope = FormalRuleScope(FormalRuleScopeKind.PLACE, ("market",))
    first_id = formal_rule_system_id(
        OWNER.value, first_scope.digest, FormalRuleAuthorityKind.CUSTOM
    )
    second_id = formal_rule_system_id(
        OWNER.value, second_scope.digest, FormalRuleAuthorityKind.OFFICE
    )
    first_rule = formal_rule_id(
        OWNER.value,
        first_id,
        FormalRuleConstraintKind.PROHIBITION,
        "attack",
        first_scope.digest,
    )
    second_rule = formal_rule_id(
        OWNER.value,
        second_id,
        FormalRuleConstraintKind.PERMISSION,
        "attack",
        second_scope.digest,
    )

    first = FormalRuleSystem(
        system_id=first_id,
        owner_id=OWNER,
        scope=first_scope,
        authority=FormalRuleAuthorityKind.CUSTOM,
        status=FormalRuleStatus.CONTESTED,
        rule_ids=(first_rule,),
        competing_system_ids=(second_id,),
        first_tick=TICK,
        last_tick=TICK,
    )
    second = FormalRuleSystem(
        system_id=second_id,
        owner_id=OWNER,
        scope=second_scope,
        authority=FormalRuleAuthorityKind.OFFICE,
        status=FormalRuleStatus.CONTESTED,
        rule_ids=(second_rule,),
        competing_system_ids=(first_id,),
        first_tick=TICK,
        last_tick=TICK,
    )
    rules = (
        _rule(
            rule_id=first_rule,
            system_id=first_id,
            versions=(_version(rule_id=first_rule),),
        ),
        _rule(
            rule_id=second_rule,
            system_id=second_id,
            versions=(_version(rule_id=second_rule),),
        ),
    )
    ledger = _ledger(systems=(first, second), rules=rules)
    assert ledger.systems[0].competing_system_ids == (second_id,)
    assert ledger.systems[1].competing_system_ids == (first_id,)

    asymmetric = FormalRuleSystem(
        system_id=second_id,
        owner_id=OWNER,
        scope=second_scope,
        authority=FormalRuleAuthorityKind.OFFICE,
        status=FormalRuleStatus.CONTESTED,
        rule_ids=(second_rule,),
        first_tick=TICK,
        last_tick=TICK,
    )
    with pytest.raises(FormalRuleError) as excinfo:
        _ledger(systems=(first, asymmetric), rules=rules)
    assert excinfo.value.code == "formal_rule_invalid_ledger"

    with pytest.raises(FormalRuleError):
        FormalRuleSystem(
            system_id=second_id,
            owner_id=OWNER,
            scope=second_scope,
            authority=FormalRuleAuthorityKind.OFFICE,
            status=FormalRuleStatus.CONTESTED,
            rule_ids=(second_rule,),
            competing_system_ids=(first_id, first_id),
            first_tick=TICK,
            last_tick=TICK,
        )


def test_version_numbers_are_contiguous_and_supersede_the_previous_version() -> None:
    first = _version(1)
    second = _version(2, supersedes=first.version_id)
    assert _ledger(rules=(_rule(versions=(second, first)),)).rules

    gap = (
        first,
        _version(3, supersedes=first.version_id),
    )
    with pytest.raises(FormalRuleError) as excinfo:
        _rule(versions=gap)
    assert excinfo.value.code == "formal_rule_invalid_ledger"

    broken_chain = (first, _version(2))
    with pytest.raises(FormalRuleError) as excinfo:
        _rule(versions=broken_chain)
    assert excinfo.value.code == "formal_rule_invalid_ledger"

    starts_late = (_version(2, supersedes=first.version_id),)
    with pytest.raises(FormalRuleError) as excinfo:
        _rule(versions=starts_late)
    assert excinfo.value.code == "formal_rule_invalid_ledger"


def test_caps_and_total_record_limit_are_enforced() -> None:
    versions: list[FormalRuleVersion] = []
    previous: str | None = None
    for number in range(1, 18):
        version = _version(number, supersedes=previous)
        versions.append(version)
        previous = version.version_id
    with pytest.raises(FormalRuleError) as excinfo:
        _ledger(rules=(_rule(versions=tuple(versions)),))
    assert excinfo.value.code == "formal_rule_invalid_ledger"

    rules: list[FormalRule] = []
    rule_ids: list[str] = []
    for index in range(33):
        identifier = formal_rule_id(
            OWNER.value,
            SYSTEM_ID,
            FormalRuleConstraintKind.PROHIBITION,
            f"action{index}",
            SCOPE.digest,
        )
        rule_ids.append(identifier)
        rules.append(
            _rule(
                rule_id=identifier,
                action=f"action{index}",
                versions=(_version(rule_id=identifier),),
            )
        )
    with pytest.raises(FormalRuleError) as excinfo:
        _ledger(systems=(_system(rule_ids=tuple(rule_ids)),), rules=tuple(rules))
    assert excinfo.value.code == "formal_rule_invalid_ledger"

    total_rules: list[FormalRule] = []
    total_ids: list[str] = []
    for index in range(32):
        identifier = formal_rule_id(
            OWNER.value,
            SYSTEM_ID,
            FormalRuleConstraintKind.PROHIBITION,
            f"total{index}",
            SCOPE.digest,
        )
        total_ids.append(identifier)
        rule_versions: list[FormalRuleVersion] = []
        previous = None
        for number in range(1, 17):
            version = _version(
                number, rule_id=identifier, supersedes=previous
            )
            rule_versions.append(version)
            previous = version.version_id
        total_rules.append(
            _rule(
                rule_id=identifier,
                action=f"total{index}",
                versions=tuple(rule_versions),
            )
        )
    with pytest.raises(FormalRuleError) as excinfo:
        _ledger(
            systems=(_system(rule_ids=tuple(total_ids)),),
            rules=tuple(total_rules),
        )
    assert excinfo.value.code == "formal_rule_invalid_ledger"


def test_no_physical_truth_binding_or_enforced_fields_exist() -> None:
    record_types = (
        FormalRule,
        FormalRuleEvidence,
        FormalRuleException,
        FormalRuleLedger,
        FormalRuleProponent,
        FormalRuleResponse,
        FormalRuleSanctionExpectation,
        FormalRuleScope,
        FormalRuleSystem,
        FormalRuleVersion,
        FormalRuleWrittenRepresentation,
    )
    forbidden = {"truth", "valid", "binding", "enforced", "objective"}
    for record_type in record_types:
        names = set(record_type.__dataclass_fields__)
        assert names.isdisjoint(FORMAL_RULE_FORBIDDEN_FIELD_NAMES), record_type
        assert names.isdisjoint(forbidden), record_type

    assert "physical" not in {kind.value for kind in FormalRuleConstraintKind}


def test_ledger_digest_is_stable_and_float_quantized() -> None:
    first = _ledger()
    second = _ledger()
    digest = formal_rule_ledger_digest(first)
    assert digest == formal_rule_ledger_digest(second)
    assert len(digest) == 64
    assert all(character in "0123456789abcdef" for character in digest)

    quantized = _ledger(rules=(_rule(strength=0.5000004),))
    exact = _ledger(rules=(_rule(strength=0.5),))
    assert formal_rule_ledger_digest(quantized) == formal_rule_ledger_digest(exact)

    different = _ledger(rules=(_rule(status=FormalRuleStatus.CONTESTED),))
    assert formal_rule_ledger_digest(different) != digest

    with pytest.raises(TypeError, match="requires FormalRuleLedger"):
        formal_rule_ledger_digest(object())
