"""Encode and parse collective-decision speech over existing utterances.

The six acts travel as bounded ``CommunicationRelation`` atoms inside ordinary
``Talk``/``Ask``/``Tell`` speech. Delivery proves that speech happened; it never
proves that a proposal exists as described, that a third party endorsed it, or
that a claimed outcome occurred.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final, cast

from agents.cognition.collective_decisions import (
    COLLECTIVE_DECISION_POLICY_VERSION,
    CollectiveAct,
    CollectiveDecisionLedger,
    CollectiveDecisionPolicy,
    CollectiveExecutionStatus,
    CollectiveTopic,
)
from agents.cognition.models import OwnerSafeSocialIdentity
from agents.models import AgentId
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId
from world.observations import Observation

__all__ = [
    "COLLECTIVE_DECISION_COMMUNICATION_POLICY_VERSION",
    "COLLECTIVE_DECISION_PREDICATES",
    "ParsedCollectiveRelation",
    "collective_decision_communicate_utterance",
    "encode_collective_decision_relation",
    "parse_collective_decision_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.collective_decision_communication"
)

COLLECTIVE_DECISION_COMMUNICATION_POLICY_VERSION: Final[str] = (
    "collective-decisions-communication.v1"
)

COLLECTIVE_DECISION_PREDICATES: Final[dict[CollectiveAct, str]] = {
    CollectiveAct.PROPOSE: "collective_propose",
    CollectiveAct.SUPPORT: "collective_support",
    CollectiveAct.OPPOSE: "collective_oppose",
    CollectiveAct.DELEGATE: "collective_delegate",
    CollectiveAct.WITHDRAW_SUPPORT: "collective_withdraw",
    CollectiveAct.COORDINATE: "collective_coordinate",
}
_PREDICATE_TO_ACT: Final[dict[str, CollectiveAct]] = {
    predicate: act for act, predicate in COLLECTIVE_DECISION_PREDICATES.items()
}
_MARKER_SUBJECT: Final[str] = "collective-decisions"
_MARKER_PREDICATE: Final[str] = "collective_policy"


@dataclass(frozen=True, slots=True)
class ParsedCollectiveRelation:
    """Parsed closed recipe; actors are always the verified observed speaker."""

    act: CollectiveAct
    topic: CollectiveTopic
    proposal_ref: str
    revision: int
    action_token: str | None = None
    target_token: str | None = None
    terms: tuple[str, ...] = ()
    window_first_tick: int | None = None
    window_last_tick: int | None = None
    context_key: str | None = None
    delegate_entity: EntityId | None = None
    retract_kind: str | None = None
    retract_id: str | None = None
    claimed_status: CollectiveExecutionStatus = CollectiveExecutionStatus.UNKNOWN


def _optional_token(token: str) -> str | None:
    value = token.strip()
    if not value or value == "-":
        return None
    return value.lower()


def _parse_revision(token: str) -> int | None:
    try:
        value = int(token)
    except ValueError:
        return None
    return value if value >= 0 else None


def encode_collective_decision_relation(
    *,
    act: CollectiveAct,
    topic: CollectiveTopic,
    proposal_ref: str,
    revision: int,
    action_token: str | None = None,
    target_token: str | None = None,
    terms: tuple[str, ...] = (),
    window_first_tick: int | None = None,
    window_last_tick: int | None = None,
    context_key: str | None = None,
    delegate_entity: EntityId | None = None,
    retract_kind: str | None = None,
    retract_id: str | None = None,
    claimed_status: CollectiveExecutionStatus = CollectiveExecutionStatus.UNKNOWN,
) -> CommunicationRelation:
    """Build one bounded relation atom for a selected act."""
    if type(act) is not CollectiveAct:
        raise TypeError("act must be CollectiveAct")
    if type(topic) is not CollectiveTopic:
        raise TypeError("topic must be CollectiveTopic")
    if not isinstance(proposal_ref, str) or len(proposal_ref) != 64:
        raise ValueError("proposal_ref must be a 64-char hex id")
    if isinstance(revision, bool) or type(revision) is not int or revision < 0:
        raise ValueError("revision must be a nonnegative int")
    predicate = COLLECTIVE_DECISION_PREDICATES[act]
    if act is CollectiveAct.PROPOSE:
        if action_token is None or context_key is None:
            raise ValueError("propose requires action_token and context_key")
        first = 0 if window_first_tick is None else window_first_tick
        last = first if window_last_tick is None else window_last_tick
        if last < first:
            raise ValueError("window_last_tick before window_first_tick")
        object_payload = "|".join(
            (
                proposal_ref,
                str(revision),
                action_token,
                "-" if target_token is None else target_token,
                "-" if not terms else ",".join(terms),
                str(first),
                str(last),
                context_key,
            )
        )
    elif act in {CollectiveAct.SUPPORT, CollectiveAct.OPPOSE}:
        object_payload = f"{proposal_ref}|{revision}|-"
    elif act is CollectiveAct.DELEGATE:
        if delegate_entity is None:
            raise ValueError("delegate requires delegate_entity")
        object_payload = f"{proposal_ref}|{revision}|{delegate_entity.value}"
    elif act is CollectiveAct.WITHDRAW_SUPPORT:
        if retract_kind not in {"position", "delegation"} or retract_id is None:
            raise ValueError("withdraw requires target kind and id")
        object_payload = f"{proposal_ref}|{revision}|{retract_kind}|{retract_id}"
    else:
        object_payload = "|".join(
            (
                proposal_ref,
                str(revision),
                "-" if action_token is None else action_token,
                "-" if target_token is None else target_token,
                claimed_status.value,
            )
        )
    return CommunicationRelation(
        subject=topic.value,
        predicate=predicate,
        object=object_payload,
    )


def policy_marker_relation() -> CommunicationRelation:
    return CommunicationRelation(
        subject=_MARKER_SUBJECT,
        predicate=_MARKER_PREDICATE,
        object=COLLECTIVE_DECISION_POLICY_VERSION,
    )


def parse_collective_decision_relation(
    relation: CommunicationRelation,
) -> ParsedCollectiveRelation | None:
    """Parse one closed recipe; malformed or unrelated atoms return ``None``."""
    if type(relation) is not CommunicationRelation:
        raise TypeError("relation must be CommunicationRelation")
    act = _PREDICATE_TO_ACT.get(relation.predicate)
    if act is None:
        return None
    try:
        topic = CollectiveTopic(relation.subject)
    except ValueError:
        return None
    parts = relation.object.split("|")
    if len(parts) < 2:
        return None
    ref = parts[0].strip()
    if len(ref) != 64 or any(char not in "0123456789abcdef" for char in ref):
        return None
    revision = _parse_revision(parts[1])
    if revision is None:
        return None
    if act is CollectiveAct.PROPOSE:
        if len(parts) != 8:
            return None
        first = _parse_revision(parts[5])
        last = _parse_revision(parts[6])
        if first is None or last is None or last < first:
            return None
        context = parts[7].strip()
        if len(context) != 16:
            return None
        terms = (
            ()
            if parts[4].strip() in {"", "-"}
            else tuple(item.lower() for item in parts[4].split(",") if item.strip())
        )
        return ParsedCollectiveRelation(
            act=act,
            topic=topic,
            proposal_ref=ref,
            revision=revision,
            action_token=_optional_token(parts[2]),
            target_token=_optional_token(parts[3]),
            terms=terms,
            window_first_tick=first,
            window_last_tick=last,
            context_key=context,
        )
    if act in {CollectiveAct.SUPPORT, CollectiveAct.OPPOSE}:
        if len(parts) != 3:
            return None
        return ParsedCollectiveRelation(
            act=act, topic=topic, proposal_ref=ref, revision=revision
        )
    if act is CollectiveAct.DELEGATE:
        if len(parts) != 3:
            return None
        entity_token = parts[2].strip()
        try:
            entity = EntityId(entity_token)
        except ValueError:
            return None
        return ParsedCollectiveRelation(
            act=act,
            topic=topic,
            proposal_ref=ref,
            revision=revision,
            delegate_entity=entity,
        )
    if act is CollectiveAct.WITHDRAW_SUPPORT:
        if len(parts) != 4 or parts[2].strip() not in {"position", "delegation"}:
            return None
        target_id = parts[3].strip()
        if len(target_id) != 64:
            return None
        return ParsedCollectiveRelation(
            act=act,
            topic=topic,
            proposal_ref=ref,
            revision=revision,
            retract_kind=parts[2].strip(),
            retract_id=target_id,
        )
    if len(parts) != 5:
        return None
    try:
        status = CollectiveExecutionStatus(parts[4].strip())
    except ValueError:
        status = CollectiveExecutionStatus.UNKNOWN
    return ParsedCollectiveRelation(
        act=act,
        topic=topic,
        proposal_ref=ref,
        revision=revision,
        action_token=_optional_token(parts[2]),
        target_token=_optional_token(parts[3]),
        claimed_status=status,
    )


def _is_communication_command(command: object) -> bool:
    from world.actions import Ask, Talk, Tell

    return type(command) in {Talk, Ask, Tell}


def _select_speech(
    ledger: CollectiveDecisionLedger,
    owner_id: AgentId,
    tick: int,
) -> ParsedCollectiveRelation | None:
    for proposal in sorted(ledger.proposals, key=lambda item: item.proposal_id):
        if proposal.window_last_tick < tick:
            continue
        own_positions = [
            item
            for item in ledger.positions
            if item.proposal_ref == proposal.proposal_ref
            and item.revision == proposal.revision
            and item.actor_id == owner_id
            and item.active
        ]
        if not own_positions:
            return ParsedCollectiveRelation(
                act=CollectiveAct.PROPOSE
                if proposal.originator_id == owner_id
                else (CollectiveAct.SUPPORT),
                topic=proposal.topic,
                proposal_ref=proposal.proposal_ref,
                revision=proposal.revision,
                action_token=proposal.action_token,
                target_token=proposal.target_token,
                terms=proposal.terms,
                window_first_tick=proposal.window_first_tick,
                window_last_tick=proposal.window_last_tick,
                context_key=proposal.context_key,
            )
    return None


def collective_decision_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    mode: object | None,
    act: CollectiveAct | None = None,
    parsed: ParsedCollectiveRelation | None = None,
    policy: CollectiveDecisionPolicy | None = None,
) -> object:
    """Stamp an existing Talk/Ask/Tell with one selected collective relation.

    Only selected, already-admissible speech is decorated. The recipient forms
    fresh local evidence; no sender ledger row is copied.
    """
    if getattr(mode, "value", None) != "deterministic":
        return command
    if type(observation) is not Observation or observation.tick != tick:
        return command
    if not _is_communication_command(command):
        return command
    if type(ledger) is not CollectiveDecisionLedger or not ledger.has_content:
        return command
    if identity is None or ledger.owner_id != owner_id:
        return command
    selected = parsed
    if selected is None:
        if act is None:
            selected = _select_speech(ledger, owner_id, tick)
        else:
            selected = _select_speech(ledger, owner_id, tick)
            if selected is None or selected.act is not act:
                return command
    if selected is None:
        return command
    relation = encode_collective_decision_relation(
        act=selected.act,
        topic=selected.topic,
        proposal_ref=selected.proposal_ref,
        revision=selected.revision,
        action_token=selected.action_token,
        target_token=selected.target_token,
        terms=selected.terms,
        window_first_tick=selected.window_first_tick,
        window_last_tick=selected.window_last_tick,
        context_key=selected.context_key,
        delegate_entity=selected.delegate_entity,
        retract_kind=selected.retract_kind,
        retract_id=selected.retract_id,
        claimed_status=selected.claimed_status,
    )
    relations = (
        *_selected_command_relations(command),
        relation,
        policy_marker_relation(),
    )
    if len(relations) > 32:
        return command
    utterance = origin_utterance(
        text="collective_decision",
        speaker_id=identity.owner_entity_id,
        communication_id=(
            f"collective-{owner_id.value}-{tick}-{selected.proposal_ref[:8]}"
        ),
        relations=relations,
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug(
        "collective_decision_response_selected owner_id=%s tick=%s act=%s "
        "relation_count=%s",
        owner_id.value,
        tick,
        selected.act.value,
        len(relations),
    )
    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=utterance,
    )


def _selected_command_relations(command: object) -> tuple[CommunicationRelation, ...]:
    utterance = getattr(command, "utterance", None)
    content = getattr(utterance, "content", None)
    relations = getattr(content, "relations", ())
    return tuple(relations)
