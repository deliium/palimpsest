"""Bounded formal-rule claims carried inside existing speech.

A rule assertion, support, opposition, challenge, reinterpretation, amendment,
withdrawal, recognition, or report must be socially expressible without granting
authority. An owner therefore states them through ordinary ``Talk``/``Tell``.
The claim travels as one closed ``fr_v1`` relation atom; delivery proves that
speech happened and never proves that a rule is objectively valid, binding, or
enforced.

No command, event, observer semantic type, or free-text payload is added, and
the V4-03 ``org_v1``, V4-04 ``org_op_v1``, V4-05 ``org_ca_v1``, and collective
decision frames are unchanged.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn, cast

from agents.cognition.formal_rules import (
    FormalRuleAuthorityKind,
    FormalRuleConstraintKind,
    FormalRuleError,
    FormalRulePolicy,
    FormalRulePositionStance,
    FormalRuleReportKind,
    FormalRuleSanctionKind,
    FormalRuleStage,
    default_formal_rule_policy,
)
from world.communications import CommunicationRelation

__all__ = [
    "FORMAL_RULE_COMMUNICATION_POLICY_VERSION",
    "FORMAL_RULE_FRAME_SUBJECT",
    "FORMAL_RULE_PREDICATES",
    "FormalRuleAct",
    "FormalRuleClaim",
    "encode_formal_rule_claim",
    "formal_rule_claim_relation",
    "formal_rule_communicate_utterance",
    "parse_formal_rule_claim",
    "parse_formal_rule_claim_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.formal_rule_communication"
)

FORMAL_RULE_COMMUNICATION_POLICY_VERSION: Final[str] = (
    "formal-rule-communication.v1"
)
FORMAL_RULE_FRAME_SUBJECT: Final[str] = "fr_v1"

_NONE_TOKEN: Final[str] = "none"
_DIGITS_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_REFERENCE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[^\s:]+$")
_ACTION_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]*$")
_REFERENCE_MAX_LEN: Final[int] = 128
_ACTION_MAX_LEN: Final[int] = 64
_MAX_VERSION: Final[int] = 9999
_MAX_REVISION: Final[int] = 9999
_MAX_ORDINAL: Final[int] = 9999


class FormalRuleAct(StrEnum):
    """Closed formal-rule speech act."""

    ASSERT = "assert"
    SUPPORT = "support"
    OPPOSE = "oppose"
    CHALLENGE = "challenge"
    REINTERPRET = "reinterpret"
    AMEND = "amend"
    WITHDRAW = "withdraw"
    RECOGNIZE = "recognize"
    REPORT = "report"


FORMAL_RULE_PREDICATES: Final[Mapping[FormalRuleAct, str]] = MappingProxyType(
    {
        FormalRuleAct.ASSERT: "fr_assert",
        FormalRuleAct.SUPPORT: "fr_support",
        FormalRuleAct.OPPOSE: "fr_oppose",
        FormalRuleAct.CHALLENGE: "fr_challenge",
        FormalRuleAct.REINTERPRET: "fr_reinterpret",
        FormalRuleAct.AMEND: "fr_amend",
        FormalRuleAct.WITHDRAW: "fr_withdraw",
        FormalRuleAct.RECOGNIZE: "fr_recognize",
        FormalRuleAct.REPORT: "fr_report",
    }
)
_PREDICATE_TO_ACT: Final[Mapping[str, FormalRuleAct]] = MappingProxyType(
    {predicate: act for act, predicate in FORMAL_RULE_PREDICATES.items()}
)
_ACT_TO_PREDICATE: Final[Mapping[FormalRuleAct, str]] = MappingProxyType(
    {act: predicate for act, predicate in FORMAL_RULE_PREDICATES.items()}
)

_STANCE_BY_ACT: Final[Mapping[FormalRuleAct, str]] = MappingProxyType(
    {
        FormalRuleAct.ASSERT: FormalRulePositionStance.PROPONENT.value,
        FormalRuleAct.SUPPORT: FormalRulePositionStance.SUPPORTER.value,
        FormalRuleAct.OPPOSE: FormalRulePositionStance.OPPONENT.value,
        FormalRuleAct.CHALLENGE: FormalRulePositionStance.CHALLENGER.value,
        FormalRuleAct.REINTERPRET: FormalRulePositionStance.REINTERPRETER.value,
        FormalRuleAct.AMEND: FormalRulePositionStance.AMENDER.value,
        FormalRuleAct.WITHDRAW: FormalRulePositionStance.WITHDRAWER.value,
        FormalRuleAct.RECOGNIZE: _NONE_TOKEN,
        FormalRuleAct.REPORT: _NONE_TOKEN,
    }
)

_REQUIRED_FIELDS: Final[Mapping[FormalRuleAct, frozenset[str]]] = MappingProxyType(
    {
        FormalRuleAct.ASSERT: frozenset(
            {
                "system_ref",
                "rule_ref",
                "version_number",
                "stage",
                "constraint_kind",
                "action_token",
                "scope_digest",
                "authority_kind",
            }
        ),
        FormalRuleAct.SUPPORT: frozenset({"system_ref", "rule_ref"}),
        FormalRuleAct.OPPOSE: frozenset({"system_ref", "rule_ref"}),
        FormalRuleAct.CHALLENGE: frozenset({"system_ref", "rule_ref"}),
        FormalRuleAct.REINTERPRET: frozenset({"system_ref", "rule_ref"}),
        FormalRuleAct.AMEND: frozenset(
            {"system_ref", "rule_ref", "revision"}
        ),
        FormalRuleAct.WITHDRAW: frozenset({"system_ref", "rule_ref"}),
        FormalRuleAct.RECOGNIZE: frozenset(
            {"system_ref", "rule_ref", "authority_kind"}
        ),
        FormalRuleAct.REPORT: frozenset({"rule_ref", "report_kind"}),
    }
)

def _policy() -> FormalRulePolicy:
    return default_formal_rule_policy()


def _fail() -> NoReturn:
    raise FormalRuleError("formal_rule_frame_invalid")


def _require_optional_ref(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value or len(value) > _REFERENCE_MAX_LEN:
        _fail()
    if _REFERENCE_PATTERN.match(value) is None:
        _fail()
    return value


def _require_optional_action(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or len(value) > _ACTION_MAX_LEN:
        _fail()
    if _ACTION_PATTERN.match(value) is None:
        _fail()
    return value


def _require_optional_digest(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or _HEX64_PATTERN.match(value) is None:
        _fail()
    return value


def _require_optional_bounded_int(value: object, maximum: int) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 1 or value > maximum:
        _fail()
    return value


def _require_optional_ordinal(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0 or value > _MAX_ORDINAL:
        _fail()
    return value


def _require_optional_enum[EnumT: StrEnum](
    value: object, enum_type: type[EnumT]
) -> EnumT | None:
    if value is None:
        return None
    if type(value) is enum_type:
        return value
    if type(value) is str and value in {member.value for member in enum_type}:
        return enum_type(value)
    _fail()


@dataclass(frozen=True, slots=True)
class FormalRuleClaim:
    """One closed self-authored formal-rule claim."""

    act: FormalRuleAct
    system_ref: str | None = None
    rule_ref: str | None = None
    version_number: int | None = None
    stage: FormalRuleStage | None = None
    constraint_kind: FormalRuleConstraintKind | None = None
    action_token: str | None = None
    scope_digest: str | None = None
    authority_kind: FormalRuleAuthorityKind | None = None
    written_artifact_ref: str | None = None
    sanction_kind: FormalRuleSanctionKind | None = None
    stance: str = _NONE_TOKEN
    report_kind: FormalRuleReportKind | None = None
    revision: int | None = None
    ordinal: int | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not FormalRuleAct:
            _fail()
        object.__setattr__(
            self, "system_ref", _require_optional_ref(self.system_ref)
        )
        object.__setattr__(self, "rule_ref", _require_optional_ref(self.rule_ref))
        object.__setattr__(
            self,
            "version_number",
            _require_optional_bounded_int(self.version_number, _MAX_VERSION),
        )
        object.__setattr__(
            self, "stage", _require_optional_enum(self.stage, FormalRuleStage)
        )
        object.__setattr__(
            self,
            "constraint_kind",
            _require_optional_enum(
                self.constraint_kind, FormalRuleConstraintKind
            ),
        )
        object.__setattr__(
            self, "action_token", _require_optional_action(self.action_token)
        )
        object.__setattr__(
            self, "scope_digest", _require_optional_digest(self.scope_digest)
        )
        object.__setattr__(
            self,
            "authority_kind",
            _require_optional_enum(
                self.authority_kind, FormalRuleAuthorityKind
            ),
        )
        object.__setattr__(
            self,
            "written_artifact_ref",
            _require_optional_ref(self.written_artifact_ref),
        )
        object.__setattr__(
            self,
            "sanction_kind",
            _require_optional_enum(
                self.sanction_kind, FormalRuleSanctionKind
            ),
        )
        expected_stance = _STANCE_BY_ACT[self.act]
        if type(self.stance) is not str or self.stance not in {
            _NONE_TOKEN,
            expected_stance,
        }:
            _fail()
        object.__setattr__(self, "stance", expected_stance)
        object.__setattr__(
            self,
            "report_kind",
            _require_optional_enum(
                self.report_kind, FormalRuleReportKind
            ),
        )
        object.__setattr__(
            self,
            "revision",
            _require_optional_bounded_int(self.revision, _MAX_REVISION),
        )
        object.__setattr__(
            self, "ordinal", _require_optional_ordinal(self.ordinal)
        )
        for name in _REQUIRED_FIELDS[self.act]:
            if getattr(self, name) is None:
                _fail()
        if self.act is not FormalRuleAct.REPORT and self.report_kind is not None:
            _fail()
        if self.act is not FormalRuleAct.ASSERT and self.stage is not None:
            _fail()
        if (
            self.act is not FormalRuleAct.ASSERT
            and self.constraint_kind is not None
        ):
            _fail()
        if self.act is not FormalRuleAct.ASSERT and self.action_token is not None:
            _fail()
        if self.act is not FormalRuleAct.ASSERT and self.scope_digest is not None:
            _fail()
        if (
            self.act
            not in (FormalRuleAct.ASSERT, FormalRuleAct.RECOGNIZE)
            and self.authority_kind is not None
        ):
            _fail()
        if self.act is not FormalRuleAct.ASSERT and self.version_number is not None:
            _fail()
        if (
            self.act is not FormalRuleAct.ASSERT
            and self.written_artifact_ref is not None
        ):
            _fail()
        if (
            self.act is not FormalRuleAct.ASSERT
            and self.sanction_kind is not None
        ):
            _fail()
        if self.act is not FormalRuleAct.AMEND and self.revision is not None:
            _fail()


def _optional_token(value: str | None) -> str:
    return _NONE_TOKEN if value is None else value


def encode_formal_rule_claim(claim: FormalRuleClaim) -> str:
    """Encode one claim into the bounded ``fr_v1`` frame."""

    if type(claim) is not FormalRuleClaim:
        raise TypeError("claim must be FormalRuleClaim")
    predicate = _ACT_TO_PREDICATE[claim.act]
    fields = (
        _optional_token(claim.system_ref),
        _optional_token(claim.rule_ref),
        _NONE_TOKEN
        if claim.version_number is None
        else str(claim.version_number),
        _NONE_TOKEN if claim.stage is None else claim.stage.value,
        _NONE_TOKEN
        if claim.constraint_kind is None
        else claim.constraint_kind.value,
        _optional_token(claim.action_token),
        _optional_token(claim.scope_digest),
        _NONE_TOKEN
        if claim.authority_kind is None
        else claim.authority_kind.value,
        _optional_token(claim.written_artifact_ref),
        _NONE_TOKEN
        if claim.sanction_kind is None
        else claim.sanction_kind.value,
        claim.stance,
        _NONE_TOKEN
        if claim.report_kind is None
        else claim.report_kind.value,
        _NONE_TOKEN if claim.revision is None else str(claim.revision),
        _NONE_TOKEN if claim.ordinal is None else str(claim.ordinal),
    )
    return f"{FORMAL_RULE_FRAME_SUBJECT}:{predicate}:" + ":".join(fields)


def _optional_int_token(value: str) -> int | None:
    if value == _NONE_TOKEN:
        return None
    if _DIGITS_PATTERN.match(value) is None:
        _fail()
    return int(value)


def _optional_enum_token[EnumT: StrEnum](
    value: str, enum_type: type[EnumT]
) -> EnumT | None:
    if value == _NONE_TOKEN:
        return None
    if value not in {member.value for member in enum_type}:
        _fail()
    return enum_type(value)


def _optional_ref_token(value: str) -> str | None:
    if value == _NONE_TOKEN:
        return None
    return _require_optional_ref(value)


def parse_formal_rule_claim(text: str) -> FormalRuleClaim:
    """Parse one strict ``fr_v1`` frame; malformed text fails closed."""

    if type(text) is not str:
        _fail()
    if len(text) > _policy().max_frame_chars:
        _fail()
    if any(character.isspace() or ord(character) < 32 for character in text):
        _fail()
    parts = text.split(":")
    if len(parts) != 16:
        _fail()
    (
        subject,
        predicate,
        system_ref,
        rule_ref,
        version_number,
        stage,
        constraint_kind,
        action_token,
        scope_digest,
        authority_kind,
        written_artifact_ref,
        sanction_kind,
        stance,
        report_kind,
        revision,
        ordinal,
    ) = parts
    if subject != FORMAL_RULE_FRAME_SUBJECT:
        _fail()
    act = _PREDICATE_TO_ACT.get(predicate)
    if act is None:
        _fail()
    if stance not in {_NONE_TOKEN, _STANCE_BY_ACT[act]}:
        _fail()
    return FormalRuleClaim(
        act=act,
        system_ref=_optional_ref_token(system_ref),
        rule_ref=_optional_ref_token(rule_ref),
        version_number=_optional_int_token(version_number),
        stage=_optional_enum_token(stage, FormalRuleStage),
        constraint_kind=_optional_enum_token(
            constraint_kind, FormalRuleConstraintKind
        ),
        action_token=(
            None
            if action_token == _NONE_TOKEN
            else _require_optional_action(action_token)
        ),
        scope_digest=(
            None
            if scope_digest == _NONE_TOKEN
            else _require_optional_digest(scope_digest)
        ),
        authority_kind=_optional_enum_token(
            authority_kind, FormalRuleAuthorityKind
        ),
        written_artifact_ref=_optional_ref_token(written_artifact_ref),
        sanction_kind=_optional_enum_token(
            sanction_kind, FormalRuleSanctionKind
        ),
        stance=stance,
        report_kind=_optional_enum_token(report_kind, FormalRuleReportKind),
        revision=_optional_int_token(revision),
        ordinal=_optional_int_token(ordinal),
    )


def formal_rule_claim_relation(
    claim: FormalRuleClaim,
) -> tuple[str, str, str]:
    """Build the ``(subject, predicate, object)`` atom for one claim."""

    if type(claim) is not FormalRuleClaim:
        raise TypeError("claim must be FormalRuleClaim")
    frame = encode_formal_rule_claim(claim)
    _, predicate, body = frame.split(":", 2)
    return FORMAL_RULE_FRAME_SUBJECT, predicate, body


def parse_formal_rule_claim_relation(
    subject: str, predicate: str, object: str
) -> FormalRuleClaim | None:
    """Parse one relation atom; unrelated atoms return ``None``."""

    if subject != FORMAL_RULE_FRAME_SUBJECT:
        return None
    if type(predicate) is not str or predicate not in _PREDICATE_TO_ACT:
        return None
    return parse_formal_rule_claim(f"{subject}:{predicate}:{object}")


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def formal_rule_communicate_utterance(
    command: object, claim: FormalRuleClaim | None
) -> object:
    """Attach at most one ``fr_v1`` relation to an already-selected utterance.

    The command type, recipient, delivery, and every existing relation are
    preserved. No command is created, replaced, or re-targeted.
    """

    if claim is None:
        return command
    if type(claim) is not FormalRuleClaim:
        raise TypeError("claim must be FormalRuleClaim or None")
    if not _is_expressible(command):
        raise FormalRuleError("formal_rule_frame_unsupported_command")
    utterance = getattr(command, "utterance", None)
    if utterance is None:
        return command
    content = getattr(utterance, "content", None)
    if content is None:
        return command
    relations = tuple(getattr(content, "relations", ()))
    if any(
        relation.subject == FORMAL_RULE_FRAME_SUBJECT
        or relation.predicate in _PREDICATE_TO_ACT
        for relation in relations
    ):
        return command
    if len(relations) >= _policy().max_relations:
        _LOG.warning("formal_rule_frame_skipped reason=relation_cap")
        return command
    subject, predicate, body = formal_rule_claim_relation(claim)
    updated_content = replace(
        content,
        relations=(
            *relations,
            CommunicationRelation(subject=subject, predicate=predicate, object=body),
        ),
    )
    updated_utterance = replace(utterance, content=updated_content)
    _LOG.debug("formal_rule_frame_encoded act=%s", claim.act.value)
    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=updated_utterance,
    )
