"""Deterministic optional commons command, appraisal and speech policy.

All effects are owner interpretation or voluntary ordinary action. Nothing here
grants entitlement, schedules peers, or physically denies a draw beyond an
owner's own Drink→Wait deferral.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.cognition.commons_governance import (
    PROPOSAL_LIFETIME_TICKS,
    SPEECH_INTERVAL_TICKS,
    THIRST_DEFER_THRESHOLD,
    CommonsConsideration,
    CommonsConsiderationChoice,
    CommonsConsiderationOpportunity,
    CommonsEvidenceCode,
    CommonsLedger,
    CommonsProposalEvidence,
    CommonsStance,
    CommonsStockEvidence,
    append_commons_consideration,
    commons_lineage_ref,
    expected_turn_actor,
    mark_commons_deferral,
    proposal_is_contested,
    proposal_is_live,
    proposal_is_supported,
    record_commons_sent_speech,
    rest_applies_on_tick,
    stage_commons_outbound,
    supported_live_proposals,
)
from agents.cognition.commons_governance_communication import (
    CGO_FRAME_MAX_RELATIONS,
    CGO_FRAME_SUBJECT,
    CommonsAct,
    CommonsFrame,
    CommonsTopic,
    attach_commons_frame,
    encode_commons_frame,
)
from world.actions import AgentCommand, Drink, Talk, Tell, Wait
from world.communications import origin_utterance
from world.identifiers import EntityId, require_exact_nonneg_int
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservedOccurrence,
    VisibleBody,
)

__all__ = [
    "COMMONS_DECLINE_LOOKBACK_TICKS",
    "CommonsDeferralResult",
    "CommonsFormalRuleCandidate",
    "CommonsInstitutionCandidate",
    "CommonsNormCandidate",
    "CommonsNormCandidateKind",
    "CommonsProposalOrigin",
    "CommonsSpeechIntent",
    "CommonsSpeechPriority",
    "CommonsStanceIntent",
    "decorate_commons_speech",
    "maybe_defer_commons_drink",
    "normalized_thirst",
    "select_commons_formal_rule_candidates",
    "select_commons_institution_candidates",
    "select_commons_norm_candidates",
    "select_commons_proposal_origin",
    "select_commons_speech",
    "select_commons_stance",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.commons_governance_actions"
)

COMMONS_DECLINE_LOOKBACK_TICKS: Final[int] = 8
_MAX_UTTERANCE_RELATIONS: Final[int] = 32


class CommonsNormCandidateKind(StrEnum):
    """Typed norm expectation/response candidate from commons evidence."""

    CRITICISM = "criticism"
    CLAIM_ACCESS = "claim_access"


class CommonsSpeechPriority(StrEnum):
    """Closed speech decoration priority order (lower ordinal wins)."""

    STANCE = "stance"
    CRITICISM = "criticism"
    PROPOSAL = "proposal"
    ACCESS_CLAIM = "access_claim"
    SELF_REPORT = "self_report"


@dataclass(frozen=True, slots=True)
class CommonsProposalOrigin:
    """One voluntary proposal the owner may originate this tick."""

    stock_id: EntityId
    topic: CommonsTopic
    recipient_id: EntityId
    peer_id: EntityId | None
    origin_tick: int


@dataclass(frozen=True, slots=True)
class CommonsStanceIntent:
    """One support or opposition the owner may emit for a known proposal."""

    proposal: CommonsProposalEvidence
    stance: CommonsStance
    recipient_id: EntityId


@dataclass(frozen=True, slots=True)
class CommonsNormCandidate:
    """Typed expectation/response candidate; never a SHARED_UPKEEP belief."""

    kind: CommonsNormCandidateKind
    stock_id: EntityId
    recipient_id: EntityId
    proposal_id: str | None = None
    topic: CommonsTopic | None = None
    reported_tick: int | None = None


@dataclass(frozen=True, slots=True)
class CommonsFormalRuleCandidate:
    """RESOURCE-scoped feed prohibition candidate tagged with commons lineage."""

    stock_id: EntityId
    proposal_id: str
    actors: tuple[str, ...]
    tick: int

    @property
    def lineage_ref(self) -> str:
        return commons_lineage_ref(self.proposal_id)


@dataclass(frozen=True, slots=True)
class CommonsInstitutionCandidate:
    """PROCEDURE_RECURRENCE witness from matched turn-slot self-reports."""

    stock_id: EntityId
    proposal_id: str
    earlier_slot: int
    later_slot: int
    tick: int

    @property
    def lineage_ref(self) -> str:
        return (
            f"commons-procedure:{self.proposal_id}:"
            f"{self.earlier_slot}:{self.later_slot}"
        )


@dataclass(frozen=True, slots=True)
class CommonsSpeechIntent:
    """One staged commons frame ready for Talk/Tell decoration or Wait→Talk."""

    frame: CommonsFrame
    recipient_id: EntityId
    priority: CommonsSpeechPriority
    fingerprint: str


@dataclass(frozen=True, slots=True)
class CommonsDeferralResult:
    """Effective command adaptation plus updated consideration state."""

    command: AgentCommand
    ledger: CommonsLedger
    deferred: bool


def normalized_thirst(observation: Observation) -> float | None:
    """Return thirst need in ``[0, 1]`` from the owner self-body, if present."""

    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    body = observation.self_body
    if body is None:
        return None
    return float(body.thirst.value) / 100.0


def _living_visible_peers(observation: Observation) -> tuple[EntityId, ...]:
    peers: list[EntityId] = []
    for body in observation.visible_bodies:
        if type(body) is not VisibleBody:
            continue
        if body.life_status is not LifeStatus.ALIVE:
            continue
        peers.append(body.entity_id)
    peers.sort(key=lambda item: item.value)
    return tuple(peers)


def _lexical_identities(
    observer_id: EntityId, observation: Observation
) -> tuple[EntityId, ...]:
    identities = [observer_id, *_living_visible_peers(observation)]
    identities.sort(key=lambda item: item.value)
    return tuple(identities)


def _decline_ticks(
    ledger: CommonsLedger, stock_id: EntityId, tick: int
) -> tuple[int, ...]:
    cutoff = tick - COMMONS_DECLINE_LOOKBACK_TICKS + 1
    if cutoff < 0:
        cutoff = 0
    ticks = sorted(
        {
            row.source_tick
            for row in ledger.transitions
            if row.stock_id == stock_id
            and row.code is CommonsEvidenceCode.STOCK_DECLINED
            and row.source_tick >= cutoff
            and row.source_tick <= tick
        }
    )
    return tuple(ticks)


def _has_consecutive_declines(decline_ticks: tuple[int, ...]) -> bool:
    if len(decline_ticks) < 2:
        return False
    for index in range(1, len(decline_ticks)):
        if decline_ticks[index] == decline_ticks[index - 1] + 1:
            return True
    return False


def _stock_has_live_rest(
    stock: CommonsStockEvidence, tick: int
) -> CommonsProposalEvidence | None:
    for proposal in stock.proposals:
        if proposal.topic != CommonsTopic.REST.value:
            continue
        if not proposal_is_live(proposal, tick):
            continue
        return proposal
    return None


def _stock_had_rest(stock: CommonsStockEvidence) -> bool:
    return any(row.topic == CommonsTopic.REST.value for row in stock.proposals)


def select_commons_proposal_origin(
    ledger: CommonsLedger,
    observation: Observation,
) -> CommonsProposalOrigin | None:
    """Select at most one rest-then-turn proposal the lexical-first owner may emit."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    observer = ledger.observer_entity_id
    if observation.observer_id != observer:
        _LOG.debug("commons_proposal_skipped reason_code=wrong_observer count=1")
        return None
    identities = _lexical_identities(observer, observation)
    if not identities or identities[0] != observer:
        _LOG.debug("commons_proposal_skipped reason_code=not_lexical_first count=1")
        return None
    if len(identities) < 2:
        _LOG.debug("commons_proposal_skipped reason_code=no_peer count=1")
        return None
    recipient = identities[1]
    tick = observation.tick
    for stock in sorted(ledger.stocks, key=lambda item: item.stock_id.value):
        if stock.last_visible_tick != tick:
            continue
        declines = _decline_ticks(ledger, stock.stock_id, tick)
        if not _has_consecutive_declines(declines):
            continue
        live_rest = _stock_has_live_rest(stock, tick)
        if live_rest is not None:
            # Active rest window still open; wait for contest/expiry.
            continue
        if not _stock_had_rest(stock):
            return CommonsProposalOrigin(
                stock_id=stock.stock_id,
                topic=CommonsTopic.REST,
                recipient_id=recipient,
                peer_id=None,
                origin_tick=tick,
            )
        # Prior rest contested or expired; further declines escalate to turn.
        return CommonsProposalOrigin(
            stock_id=stock.stock_id,
            topic=CommonsTopic.TURN,
            recipient_id=recipient,
            peer_id=recipient,
            origin_tick=tick,
        )
    return None


def _recent_decline_for(
    ledger: CommonsLedger, stock_id: EntityId, tick: int
) -> bool:
    return bool(_decline_ticks(ledger, stock_id, tick))


def _overlapping_claim(
    stock: CommonsStockEvidence, owner: EntityId, tick: int
) -> bool:
    cutoff = tick - COMMONS_DECLINE_LOOKBACK_TICKS + 1
    if cutoff < 0:
        cutoff = 0
    for claim in stock.access_claims:
        if claim.speaker_id == owner:
            continue
        if claim.source_tick >= cutoff:
            return True
    for proposal in stock.proposals:
        if not proposal_is_live(proposal, tick):
            continue
        if proposal_is_supported(proposal):
            return True
    return False


def select_commons_stance(
    ledger: CommonsLedger,
    observation: Observation,
    *,
    thirst: float | None = None,
) -> CommonsStanceIntent | None:
    """Choose support, opposition, or silence for one addressed live proposal."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    tick = observation.tick
    need = thirst if thirst is not None else normalized_thirst(observation)
    owner = ledger.observer_entity_id
    for stock in sorted(ledger.stocks, key=lambda item: item.stock_id.value):
        for proposal in sorted(stock.proposals, key=lambda item: item.proposal_id):
            if not proposal_is_live(proposal, tick):
                continue
            if proposal.proposer_id == owner:
                continue
            # Owner must be an addressed peer: rest any co-present peer, turn
            # only the named peer.
            if proposal.topic == CommonsTopic.TURN.value:
                if proposal.peer_id != owner:
                    continue
            elif proposal.topic != CommonsTopic.REST.value:
                continue
            recipient = proposal.proposer_id
            if need is not None and need + 1e-12 >= THIRST_DEFER_THRESHOLD:
                return CommonsStanceIntent(
                    proposal=proposal,
                    stance=CommonsStance.OPPOSE,
                    recipient_id=recipient,
                )
            if _overlapping_claim(stock, owner, tick):
                return CommonsStanceIntent(
                    proposal=proposal,
                    stance=CommonsStance.OPPOSE,
                    recipient_id=recipient,
                )
            if _recent_decline_for(ledger, stock.stock_id, tick):
                if (
                    proposal.topic == CommonsTopic.TURN.value
                    and proposal.peer_id != owner
                ):
                    continue
                return CommonsStanceIntent(
                    proposal=proposal,
                    stance=CommonsStance.SUPPORT,
                    recipient_id=recipient,
                )
            _LOG.debug("commons_stance_silence reason_code=no_decline count=1")
            return None
    return None


def _owner_expected_to_rest(
    proposal: CommonsProposalEvidence,
    actor_id: EntityId,
    reported_tick: int,
    support_tick: int,
) -> bool:
    if reported_tick <= support_tick:
        return False
    if reported_tick <= proposal.origin_tick:
        return False
    if proposal.topic == CommonsTopic.REST.value:
        return rest_applies_on_tick(proposal, reported_tick)
    if proposal.topic == CommonsTopic.TURN.value:
        expected = expected_turn_actor(proposal, reported_tick)
        return expected is not None and expected != actor_id
    return False


def _first_support_tick(proposal: CommonsProposalEvidence) -> int | None:
    ticks = [
        row.stance_tick
        for row in proposal.contributors
        if row.stance is CommonsStance.SUPPORT and row.stance_tick is not None
    ]
    if not ticks:
        return None
    return min(ticks)


def select_commons_norm_candidates(
    ledger: CommonsLedger,
    observation: Observation,
) -> tuple[CommonsNormCandidate, ...]:
    """Return criticism and optional claim_access candidates from local evidence."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    tick = observation.tick
    owner = ledger.observer_entity_id
    candidates: list[CommonsNormCandidate] = []
    for stock in sorted(ledger.stocks, key=lambda item: item.stock_id.value):
        for proposal in sorted(stock.proposals, key=lambda item: item.proposal_id):
            if not proposal_is_supported(proposal):
                continue
            if proposal_is_contested(proposal, stock, tick):
                continue
            support_tick = _first_support_tick(proposal)
            if support_tick is None:
                continue
            for row in ledger.transitions:
                if row.code is not CommonsEvidenceCode.REPORT_USE:
                    continue
                if row.proposal_id != proposal.proposal_id:
                    continue
                if row.actor_id is None or row.reported_tick is None:
                    continue
                if row.actor_id == owner:
                    continue
                if not _owner_expected_to_rest(
                    proposal, row.actor_id, row.reported_tick, support_tick
                ):
                    continue
                topic = (
                    CommonsTopic.REST
                    if proposal.topic == CommonsTopic.REST.value
                    else CommonsTopic.TURN
                )
                candidates.append(
                    CommonsNormCandidate(
                        kind=CommonsNormCandidateKind.CRITICISM,
                        stock_id=stock.stock_id,
                        recipient_id=row.actor_id,
                        proposal_id=proposal.proposal_id,
                        topic=topic,
                        reported_tick=row.reported_tick,
                    )
                )
        supported = any(
            proposal_is_live(proposal, tick) and proposal_is_supported(proposal)
            and not proposal_is_contested(proposal, stock, tick)
            for proposal in stock.proposals
        )
        if supported:
            continue
        own_draw = _own_recent_draw_tick(observation, owner, stock.stock_id, tick)
        if own_draw is None:
            continue
        candidates.append(
            CommonsNormCandidate(
                kind=CommonsNormCandidateKind.CLAIM_ACCESS,
                stock_id=stock.stock_id,
                recipient_id=_claim_recipient(observation, owner),
            )
        )
    # Deterministic order; at most one claim and criticisms by recipient.
    ordered: list[CommonsNormCandidate] = []
    seen_criticism: set[tuple[str, str, int]] = set()
    claim: CommonsNormCandidate | None = None
    for item in candidates:
        if item.kind is CommonsNormCandidateKind.CLAIM_ACCESS:
            if claim is None and item.recipient_id is not None:
                claim = item
            continue
        key = (
            item.proposal_id or "",
            item.recipient_id.value,
            item.reported_tick or -1,
        )
        if key in seen_criticism:
            continue
        seen_criticism.add(key)
        ordered.append(item)
    ordered.sort(
        key=lambda item: (
            item.kind.value,
            item.stock_id.value,
            item.recipient_id.value,
            item.proposal_id or "",
            item.reported_tick or -1,
        )
    )
    if claim is not None:
        ordered.append(claim)
    return tuple(ordered)


def _claim_recipient(observation: Observation, owner: EntityId) -> EntityId:
    peers = _living_visible_peers(observation)
    if peers:
        return peers[0]
    return owner


def _own_recent_draw_tick(
    observation: Observation,
    owner: EntityId,
    stock_id: EntityId,
    tick: int,
) -> int | None:
    cutoff = tick - COMMONS_DECLINE_LOOKBACK_TICKS + 1
    if cutoff < 0:
        cutoff = 0
    matches: list[int] = []
    for occurrence in observation.occurrences:
        if type(occurrence) is not ObservedOccurrence:
            continue
        if occurrence.kind != "drink":
            continue
        if occurrence.audience_role is not ObservationAudienceRole.ACTOR:
            continue
        if occurrence.actor_id != owner:
            continue
        if occurrence.other_entity_id != stock_id:
            continue
        source_tick = occurrence.provenance.source_tick
        if source_tick < cutoff or source_tick >= tick:
            continue
        matches.append(source_tick)
    if not matches:
        return None
    return max(matches)


def select_commons_formal_rule_candidates(
    ledger: CommonsLedger,
    tick: int,
) -> tuple[CommonsFormalRuleCandidate, ...]:
    """Feed unambiguous supported expectations into formal-rule update."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    absolute = require_exact_nonneg_int("tick", tick)
    rows: list[CommonsFormalRuleCandidate] = []
    for stock, proposal in supported_live_proposals(ledger, absolute):
        actors = sorted(
            {
                proposal.proposer_id.value,
                *(
                    row.speaker_id.value
                    for row in proposal.contributors
                    if row.stance is CommonsStance.SUPPORT
                ),
            }
        )
        rows.append(
            CommonsFormalRuleCandidate(
                stock_id=stock.stock_id,
                proposal_id=proposal.proposal_id,
                actors=tuple(actors),
                tick=absolute,
            )
        )
    return tuple(rows)


def _report_use_by_speaker(
    ledger: CommonsLedger, proposal_id: str
) -> dict[EntityId, list[int]]:
    by_speaker: dict[EntityId, list[int]] = {}
    for row in ledger.transitions:
        if row.code is not CommonsEvidenceCode.REPORT_USE:
            continue
        if row.proposal_id != proposal_id:
            continue
        if row.actor_id is None or row.reported_tick is None:
            continue
        by_speaker.setdefault(row.actor_id, []).append(row.reported_tick)
    for speaker, ticks in by_speaker.items():
        by_speaker[speaker] = sorted(set(ticks))
    return by_speaker


def select_commons_institution_candidates(
    ledger: CommonsLedger,
    tick: int,
) -> tuple[CommonsInstitutionCandidate, ...]:
    """Matched turn-slot self-reports yield PROCEDURE_RECURRENCE candidates."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    absolute = require_exact_nonneg_int("tick", tick)
    rows: list[CommonsInstitutionCandidate] = []
    seen: set[tuple[str, str, int, int]] = set()
    for stock in ledger.stocks:
        for proposal in stock.proposals:
            if proposal.topic != CommonsTopic.TURN.value:
                continue
            if proposal.peer_id is None:
                continue
            if not proposal_is_supported(proposal):
                continue
            support_tick = _first_support_tick(proposal)
            if support_tick is None:
                continue
            reports = _report_use_by_speaker(ledger, proposal.proposal_id)
            proposer_ticks = [
                item
                for item in reports.get(proposal.proposer_id, ())
                if item > support_tick
                and expected_turn_actor(proposal, item) == proposal.proposer_id
            ]
            peer_ticks = [
                item
                for item in reports.get(proposal.peer_id, ())
                if item > support_tick
                and expected_turn_actor(proposal, item) == proposal.peer_id
            ]
            # Consecutive slots: one report from each named participant for
            # adjacent two-tick slots of the same turn proposal.
            for earlier in proposer_ticks:
                earlier_slot = (earlier - proposal.origin_tick) // 2
                for later in peer_ticks:
                    later_slot = (later - proposal.origin_tick) // 2
                    if later_slot != earlier_slot + 1:
                        continue
                    key = (
                        stock.stock_id.value,
                        proposal.proposal_id,
                        earlier_slot,
                        later_slot,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        CommonsInstitutionCandidate(
                            stock_id=stock.stock_id,
                            proposal_id=proposal.proposal_id,
                            earlier_slot=earlier_slot,
                            later_slot=later_slot,
                            tick=absolute,
                        )
                    )
            for earlier in peer_ticks:
                earlier_slot = (earlier - proposal.origin_tick) // 2
                for later in proposer_ticks:
                    later_slot = (later - proposal.origin_tick) // 2
                    if later_slot != earlier_slot + 1:
                        continue
                    key = (
                        stock.stock_id.value,
                        proposal.proposal_id,
                        earlier_slot,
                        later_slot,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        CommonsInstitutionCandidate(
                            stock_id=stock.stock_id,
                            proposal_id=proposal.proposal_id,
                            earlier_slot=earlier_slot,
                            later_slot=later_slot,
                            tick=absolute,
                        )
                    )
    rows.sort(
        key=lambda item: (
            item.stock_id.value,
            item.proposal_id,
            item.earlier_slot,
            item.later_slot,
        )
    )
    return tuple(rows)


def _matching_arrangement(
    ledger: CommonsLedger,
    owner: EntityId,
    stock_id: EntityId,
    tick: int,
) -> tuple[CommonsProposalEvidence | None, CommonsConsiderationOpportunity]:
    for stock, proposal in supported_live_proposals(ledger, tick):
        if stock.stock_id != stock_id:
            continue
        if proposal.topic == CommonsTopic.REST.value:
            if rest_applies_on_tick(proposal, tick):
                return proposal, CommonsConsiderationOpportunity.WAIT_EXPECTED
            return proposal, CommonsConsiderationOpportunity.NOT_APPLICABLE
        if proposal.topic == CommonsTopic.TURN.value:
            if owner not in {proposal.proposer_id, proposal.peer_id}:
                return proposal, CommonsConsiderationOpportunity.NOT_APPLICABLE
            expected = expected_turn_actor(proposal, tick)
            if expected is None:
                return proposal, CommonsConsiderationOpportunity.NOT_APPLICABLE
            if expected == owner:
                return proposal, CommonsConsiderationOpportunity.TURN_EXPECTED
            return proposal, CommonsConsiderationOpportunity.WAIT_EXPECTED
    return None, CommonsConsiderationOpportunity.NOT_APPLICABLE


def maybe_defer_commons_drink(
    ledger: CommonsLedger,
    observation: Observation,
    command: AgentCommand,
    *,
    overridden: bool = False,
) -> CommonsDeferralResult:
    """Optionally replace Drink with Wait under an uncontested rest/out-of-turn."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if overridden or type(command) is not Drink:
        return CommonsDeferralResult(command=command, ledger=ledger, deferred=False)
    tick = observation.tick
    target = command.source_id
    stock_ids = {row.stock_id for row in ledger.stocks}
    if target not in stock_ids:
        return CommonsDeferralResult(command=command, ledger=ledger, deferred=False)
    visible = {row.entity_id for row in observation.resources}
    if target not in visible:
        _LOG.debug("commons_deferral_skipped reason_code=stock_not_visible count=1")
        return CommonsDeferralResult(command=command, ledger=ledger, deferred=False)
    need = normalized_thirst(observation)
    owner = ledger.observer_entity_id
    proposal, opportunity = _matching_arrangement(ledger, owner, target, tick)
    should_defer = (
        opportunity is CommonsConsiderationOpportunity.WAIT_EXPECTED
        and need is not None
        and need + 1e-12 < THIRST_DEFER_THRESHOLD
        and ledger.last_deferral_tick != tick - 1
    )
    choice = (
        CommonsConsiderationChoice.DEFERRED_DRAW
        if should_defer
        else CommonsConsiderationChoice.PROCEEDED
    )
    row = CommonsConsideration(
        owner_id=ledger.owner_id,
        tick=tick,
        target_id=target,
        proposal_id=None if proposal is None else proposal.proposal_id,
        opportunity=opportunity,
        choice=choice,
    )
    updated = append_commons_consideration(ledger, row)
    if not should_defer:
        reason = (
            opportunity.value
            if opportunity is not CommonsConsiderationOpportunity.WAIT_EXPECTED
            else "thirst_or_prior"
        )
        _LOG.debug(
            "commons_deferral_skipped reason_code=%s count=1",
            reason,
        )
        return CommonsDeferralResult(command=command, ledger=updated, deferred=False)
    updated = mark_commons_deferral(updated, tick)
    _LOG.debug("commons_deferral_applied reason_code=wait_expected count=1")
    return CommonsDeferralResult(command=Wait(), ledger=updated, deferred=True)


def _speech_fingerprint(frame: CommonsFrame) -> str:
    return encode_commons_frame(frame)


def _already_sent(
    ledger: CommonsLedger, recipient_id: EntityId, fingerprint: str, tick: int
) -> bool:
    cutoff = tick - PROPOSAL_LIFETIME_TICKS + 1
    if cutoff < 0:
        cutoff = 0
    for row in ledger.sent_speech:
        if row.recipient_id != recipient_id:
            continue
        if row.fingerprint != fingerprint:
            continue
        if row.send_tick >= cutoff:
            return True
    return False


def _relation_capacity(command: Talk | Tell) -> bool:
    relations = tuple(command.utterance.content.relations)
    if any(getattr(row, "subject", None) == CGO_FRAME_SUBJECT for row in relations):
        return False
    return len(relations) + CGO_FRAME_MAX_RELATIONS <= _MAX_UTTERANCE_RELATIONS


def _is_native_command(command: Talk | Tell) -> bool:
    declared = command.utterance.declared
    return (
        declared.hop_count == 0
        and declared.parent_communication_id is None
        and len(declared.source_agent_chain) == 1
        and declared.root_communication_id == declared.communication_id
    )


def select_commons_speech(
    ledger: CommonsLedger,
    observation: Observation,
    *,
    deferred_draw: bool = False,
    thirst: float | None = None,
) -> CommonsSpeechIntent | None:
    """Select one prioritized commons speech intent for this owner tick."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    tick = observation.tick
    if ledger.last_speech_tick is not None:
        if tick - ledger.last_speech_tick < SPEECH_INTERVAL_TICKS:
            _LOG.debug("commons_speech_skipped reason_code=interval count=1")
            return None
    if ledger.staged_outbound is not None:
        _LOG.debug("commons_speech_skipped reason_code=staged_pending count=1")
        return None
    intents: list[CommonsSpeechIntent] = []
    stance = select_commons_stance(ledger, observation, thirst=thirst)
    if stance is not None:
        topic = (
            CommonsTopic.REST
            if stance.proposal.topic == CommonsTopic.REST.value
            else CommonsTopic.TURN
        )
        act = (
            CommonsAct.SUPPORT
            if stance.stance is CommonsStance.SUPPORT
            else CommonsAct.OPPOSE
        )
        frame = CommonsFrame(
            act=act,
            topic=topic,
            stock_id=stance.proposal.stock_id,
            proposal_id=stance.proposal.proposal_id,
        )
        fingerprint = _speech_fingerprint(frame)
        if not _already_sent(ledger, stance.recipient_id, fingerprint, tick):
            intents.append(
                CommonsSpeechIntent(
                    frame=frame,
                    recipient_id=stance.recipient_id,
                    priority=CommonsSpeechPriority.STANCE,
                    fingerprint=fingerprint,
                )
            )
    for candidate in select_commons_norm_candidates(ledger, observation):
        if candidate.kind is CommonsNormCandidateKind.CRITICISM:
            if candidate.proposal_id is None or candidate.topic is None:
                continue
            if candidate.reported_tick is None:
                continue
            frame = CommonsFrame(
                act=CommonsAct.CRITICIZE,
                topic=candidate.topic,
                stock_id=candidate.stock_id,
                proposal_id=candidate.proposal_id,
                reported_tick=candidate.reported_tick,
            )
            fingerprint = _speech_fingerprint(frame)
            if _already_sent(ledger, candidate.recipient_id, fingerprint, tick):
                continue
            intents.append(
                CommonsSpeechIntent(
                    frame=frame,
                    recipient_id=candidate.recipient_id,
                    priority=CommonsSpeechPriority.CRITICISM,
                    fingerprint=fingerprint,
                )
            )
        elif candidate.kind is CommonsNormCandidateKind.CLAIM_ACCESS:
            frame = CommonsFrame(
                act=CommonsAct.CLAIM_ACCESS,
                topic=CommonsTopic.ACCESS,
                stock_id=candidate.stock_id,
            )
            fingerprint = _speech_fingerprint(frame)
            if _already_sent(ledger, candidate.recipient_id, fingerprint, tick):
                continue
            intents.append(
                CommonsSpeechIntent(
                    frame=frame,
                    recipient_id=candidate.recipient_id,
                    priority=CommonsSpeechPriority.ACCESS_CLAIM,
                    fingerprint=fingerprint,
                )
            )
    origin = select_commons_proposal_origin(ledger, observation)
    if origin is not None:
        frame = CommonsFrame(
            act=CommonsAct.PROPOSE,
            topic=origin.topic,
            stock_id=origin.stock_id,
            peer_id=origin.peer_id,
        )
        fingerprint = _speech_fingerprint(frame)
        if not _already_sent(ledger, origin.recipient_id, fingerprint, tick):
            intents.append(
                CommonsSpeechIntent(
                    frame=frame,
                    recipient_id=origin.recipient_id,
                    priority=CommonsSpeechPriority.PROPOSAL,
                    fingerprint=fingerprint,
                )
            )
    report = _select_self_report(ledger, observation, deferred_draw=deferred_draw)
    if report is not None:
        intents.append(report)
    if not intents:
        return None
    priority_order = {
        CommonsSpeechPriority.STANCE: 0,
        CommonsSpeechPriority.CRITICISM: 1,
        CommonsSpeechPriority.PROPOSAL: 2,
        CommonsSpeechPriority.ACCESS_CLAIM: 3,
        CommonsSpeechPriority.SELF_REPORT: 4,
    }
    intents.sort(
        key=lambda item: (
            priority_order[item.priority],
            item.recipient_id.value,
            item.fingerprint,
        )
    )
    return intents[0]


def _select_self_report(
    ledger: CommonsLedger,
    observation: Observation,
    *,
    deferred_draw: bool,
) -> CommonsSpeechIntent | None:
    tick = observation.tick
    owner = ledger.observer_entity_id
    for stock, proposal in supported_live_proposals(ledger, tick):
        if proposal.origin_tick >= tick:
            continue
        topic = (
            CommonsTopic.REST
            if proposal.topic == CommonsTopic.REST.value
            else CommonsTopic.TURN
        )
        recipient = proposal.peer_id
        if recipient is None:
            recipient = proposal.proposer_id if proposal.proposer_id != owner else None
        if recipient is None or recipient == owner:
            peers = _living_visible_peers(observation)
            if not peers:
                continue
            recipient = peers[0]
        if deferred_draw and ledger.last_deferral_tick is not None:
            reported = ledger.last_deferral_tick
            if not (proposal.origin_tick < reported < tick):
                continue
            frame = CommonsFrame(
                act=CommonsAct.REPORT_REST,
                topic=topic,
                stock_id=stock.stock_id,
                proposal_id=proposal.proposal_id,
                reported_tick=reported,
            )
            fingerprint = _speech_fingerprint(frame)
            if _already_sent(ledger, recipient, fingerprint, tick):
                continue
            return CommonsSpeechIntent(
                frame=frame,
                recipient_id=recipient,
                priority=CommonsSpeechPriority.SELF_REPORT,
                fingerprint=fingerprint,
            )
        draw_tick = _own_recent_draw_tick(
            observation, owner, stock.stock_id, tick
        )
        if draw_tick is None:
            continue
        if not (proposal.origin_tick < draw_tick < tick):
            continue
        frame = CommonsFrame(
            act=CommonsAct.REPORT_USE,
            topic=topic,
            stock_id=stock.stock_id,
            proposal_id=proposal.proposal_id,
            reported_tick=draw_tick,
        )
        fingerprint = _speech_fingerprint(frame)
        if _already_sent(ledger, recipient, fingerprint, tick):
            continue
        return CommonsSpeechIntent(
            frame=frame,
            recipient_id=recipient,
            priority=CommonsSpeechPriority.SELF_REPORT,
            fingerprint=fingerprint,
        )
    return None


def decorate_commons_speech(
    ledger: CommonsLedger,
    observation: Observation,
    command: AgentCommand,
    *,
    deferred_draw: bool = False,
    thirst: float | None = None,
) -> tuple[AgentCommand, CommonsLedger]:
    """Decorate Talk/Tell or replace ordinary Wait with one commons frame."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    intent = select_commons_speech(
        ledger,
        observation,
        deferred_draw=deferred_draw,
        thirst=thirst,
    )
    if intent is None:
        return command, ledger
    tick = observation.tick
    if type(command) is Talk or type(command) is Tell:
        if command.recipient_id != intent.recipient_id:
            _LOG.debug("commons_speech_skipped reason_code=recipient_mismatch count=1")
            return command, ledger
        if not _is_native_command(command):
            _LOG.debug("commons_speech_skipped reason_code=not_native count=1")
            return command, ledger
        if not _relation_capacity(command):
            _LOG.debug("commons_speech_skipped reason_code=capacity count=1")
            return command, ledger
        decorated = attach_commons_frame(command, intent.frame)
        if decorated is command:
            return command, ledger
        updated = record_commons_sent_speech(
            ledger,
            recipient_id=intent.recipient_id,
            fingerprint=intent.fingerprint,
            send_tick=tick,
        )
        updated = stage_commons_outbound(
            updated,
            send_tick=tick,
            listener_id=intent.recipient_id,
            encoded_frame=intent.fingerprint,
        )
        return decorated, updated
    if type(command) is Wait and not deferred_draw:
        utterance = origin_utterance(
            text="commons",
            speaker_id=ledger.observer_entity_id,
            communication_id=f"cgo-{ledger.owner_id.value}-{tick}",
            relations=(),
        )
        talk = Talk(recipient_id=intent.recipient_id, utterance=utterance)
        decorated = attach_commons_frame(talk, intent.frame)
        updated = record_commons_sent_speech(
            ledger,
            recipient_id=intent.recipient_id,
            fingerprint=intent.fingerprint,
            send_tick=tick,
        )
        updated = stage_commons_outbound(
            updated,
            send_tick=tick,
            listener_id=intent.recipient_id,
            encoded_frame=intent.fingerprint,
        )
        return decorated, updated
    _LOG.debug("commons_speech_skipped reason_code=command_unavailable count=1")
    return command, ledger
