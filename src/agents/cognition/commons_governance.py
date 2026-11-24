"""Owner-local commons monitoring and fallible social evidence.

The ledger folds only the owner's observations and actually delivered ``cgo_v1``
frames. Stock quantity changes are direct visibility evidence; peer speech is
testimony. Nothing here grants entitlement, proves a withdrawal, or consults
objective pressure receipts.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.observations import Observation, ObservedCommunication, ObservedResource
from world.values import round_physical

if TYPE_CHECKING:
    from agents.cognition.commons_governance_communication import CommonsFrame

__all__ = [
    "COMMONS_GOVERNANCE_POLICY_ID",
    "COMMONS_LINEAGE_PREFIX",
    "MAX_CONSIDERATION_ROWS",
    "MAX_CONTRIBUTORS_PER_PROPOSAL",
    "MAX_EVIDENCE_TICKS",
    "MAX_PROPOSALS_PER_STOCK",
    "MAX_SENT_SPEECH_ROWS",
    "MAX_STOCK_HEADS",
    "MAX_TRANSITION_ROWS",
    "PROPOSAL_LIFETIME_TICKS",
    "SPEECH_INTERVAL_TICKS",
    "THIRST_DEFER_THRESHOLD",
    "CommonsAccessClaim",
    "CommonsConsideration",
    "CommonsConsiderationChoice",
    "CommonsConsiderationOpportunity",
    "CommonsContributor",
    "CommonsEvidenceCode",
    "CommonsLedger",
    "CommonsProposalEvidence",
    "CommonsQuantitySignal",
    "CommonsSentSpeech",
    "CommonsStagedOutbound",
    "CommonsStance",
    "CommonsStockEvidence",
    "CommonsTransition",
    "advance_commons_evidence",
    "append_commons_consideration",
    "commons_lineage_ref",
    "commons_proposal_id",
    "empty_commons_ledger",
    "expected_turn_actor",
    "mark_commons_deferral",
    "mark_commons_speech_sent",
    "proposal_is_contested",
    "proposal_is_live",
    "proposal_is_supported",
    "record_commons_sent_speech",
    "rest_applies_on_tick",
    "stage_commons_outbound",
    "supported_live_proposals",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.commons_governance"
)

COMMONS_GOVERNANCE_POLICY_ID: Final[str] = "commons-governance.v1"
COMMONS_LINEAGE_PREFIX: Final[str] = "commons:"
MAX_STOCK_HEADS: Final[int] = 8
MAX_PROPOSALS_PER_STOCK: Final[int] = 8
MAX_CONTRIBUTORS_PER_PROPOSAL: Final[int] = 8
MAX_EVIDENCE_TICKS: Final[int] = 32
MAX_TRANSITION_ROWS: Final[int] = 128
MAX_CONSIDERATION_ROWS: Final[int] = 64
MAX_SENT_SPEECH_ROWS: Final[int] = 64
PROPOSAL_LIFETIME_TICKS: Final[int] = 16
SPEECH_INTERVAL_TICKS: Final[int] = 4
THIRST_DEFER_THRESHOLD: Final[float] = 0.65
_PROPOSAL_HEX: Final[int] = 32
_TALK_TELL: Final[frozenset[str]] = frozenset({"talk", "tell"})


class CommonsEvidenceCode(StrEnum):
    """Detached typed evidence codes retained on owner transition rows."""

    STOCK_CHECKED = "stock_checked"
    STOCK_DECLINED = "stock_declined"
    STOCK_NONDECLINE = "stock_nondecline"
    STANCE = "stance"
    ACCESS_CLAIM = "access_claim"
    REPORT_USE = "report_use"
    REPORT_REST = "report_rest"
    CRITICIZE = "criticize"
    PROPOSE = "propose"


class CommonsQuantitySignal(StrEnum):
    """Owner-visible quantity comparison between consecutive sightings."""

    BASELINE = "baseline"
    DECLINE = "decline"
    NONDECLINE = "nondecline"


class CommonsStance(StrEnum):
    """Latest stance attributed to one speaker for one proposal."""

    SUPPORT = "support"
    OPPOSE = "oppose"


class CommonsConsiderationOpportunity(StrEnum):
    """Owner-local draw opportunity class under a voluntary arrangement."""

    WAIT_EXPECTED = "wait_expected"
    TURN_EXPECTED = "turn_expected"
    NOT_APPLICABLE = "not_applicable"


class CommonsConsiderationChoice(StrEnum):
    """Owner choice recorded for one Drink consideration row."""

    DEFERRED_DRAW = "deferred_draw"
    PROCEEDED = "proceeded"


@dataclass(frozen=True, slots=True)
class CommonsTransition:
    """One immutable owner-scoped evidence row."""

    transition_id: str
    owner_id: AgentId
    stock_id: EntityId
    source_tick: int
    code: CommonsEvidenceCode
    quantity_tenths: int | None = None
    signal: CommonsQuantitySignal | None = None
    proposal_id: str | None = None
    actor_id: EntityId | None = None
    stance: CommonsStance | None = None
    reported_tick: int | None = None
    occurrence_ref: str | None = None

    def __post_init__(self) -> None:
        if type(self.transition_id) is not str or not self.transition_id:
            raise ValueError("CommonsTransition.transition_id invalid")
        if type(self.owner_id) is not AgentId:
            raise TypeError("CommonsTransition.owner_id must be AgentId")
        if type(self.stock_id) is not EntityId:
            raise TypeError("CommonsTransition.stock_id must be EntityId")
        object.__setattr__(
            self,
            "source_tick",
            require_exact_nonneg_int(
                "CommonsTransition.source_tick", self.source_tick
            ),
        )
        if type(self.code) is not CommonsEvidenceCode:
            raise TypeError("CommonsTransition.code must be CommonsEvidenceCode")


@dataclass(frozen=True, slots=True)
class CommonsContributor:
    """One attributed speaker head retained under a proposal."""

    speaker_id: EntityId
    stance: CommonsStance | None = None
    stance_tick: int | None = None
    access_claim_tick: int | None = None
    report_use_tick: int | None = None
    report_rest_tick: int | None = None
    criticize_tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.speaker_id) is not EntityId:
            raise TypeError("CommonsContributor.speaker_id must be EntityId")


@dataclass(frozen=True, slots=True)
class CommonsAccessClaim:
    """Self-attributed access claim; carries no entitlement."""

    speaker_id: EntityId
    source_tick: int
    occurrence_ref: str

    def __post_init__(self) -> None:
        if type(self.speaker_id) is not EntityId:
            raise TypeError("CommonsAccessClaim.speaker_id must be EntityId")
        object.__setattr__(
            self,
            "source_tick",
            require_exact_nonneg_int(
                "CommonsAccessClaim.source_tick", self.source_tick
            ),
        )


@dataclass(frozen=True, slots=True)
class CommonsProposalEvidence:
    """One locally known proposal with bounded contributor heads."""

    proposal_id: str
    stock_id: EntityId
    topic: str
    proposer_id: EntityId
    peer_id: EntityId | None
    origin_tick: int
    contributors: tuple[CommonsContributor, ...] = ()
    access_claims: tuple[CommonsAccessClaim, ...] = ()
    eligible: bool = True

    def __post_init__(self) -> None:
        if type(self.proposal_id) is not str or not self.proposal_id:
            raise ValueError("CommonsProposalEvidence.proposal_id invalid")
        if type(self.stock_id) is not EntityId:
            raise TypeError("CommonsProposalEvidence.stock_id must be EntityId")
        if type(self.proposer_id) is not EntityId:
            raise TypeError("CommonsProposalEvidence.proposer_id must be EntityId")
        object.__setattr__(
            self,
            "origin_tick",
            require_exact_nonneg_int(
                "CommonsProposalEvidence.origin_tick", self.origin_tick
            ),
        )
        if len(self.contributors) > MAX_CONTRIBUTORS_PER_PROPOSAL:
            raise ValueError("CommonsProposalEvidence.contributors exceed cap")


@dataclass(frozen=True, slots=True)
class CommonsStockEvidence:
    """Owner-visible stock head with last sighting and local proposals."""

    stock_id: EntityId
    last_visible_tick: int | None = None
    last_quantity_tenths: int | None = None
    proposals: tuple[CommonsProposalEvidence, ...] = ()
    access_claims: tuple[CommonsAccessClaim, ...] = ()

    def __post_init__(self) -> None:
        if type(self.stock_id) is not EntityId:
            raise TypeError("CommonsStockEvidence.stock_id must be EntityId")
        if len(self.proposals) > MAX_PROPOSALS_PER_STOCK:
            raise ValueError("CommonsStockEvidence.proposals exceed cap")
        if len(self.access_claims) > MAX_CONTRIBUTORS_PER_PROPOSAL:
            raise ValueError("CommonsStockEvidence.access_claims exceed cap")


@dataclass(frozen=True, slots=True)
class CommonsStagedOutbound:
    """Exact outbound frame awaiting confirmation on the next observation."""

    send_tick: int
    listener_id: EntityId
    encoded_frame: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "send_tick",
            require_exact_nonneg_int(
                "CommonsStagedOutbound.send_tick", self.send_tick
            ),
        )
        if type(self.listener_id) is not EntityId:
            raise TypeError("CommonsStagedOutbound.listener_id must be EntityId")
        if type(self.encoded_frame) is not str or not self.encoded_frame:
            raise ValueError("CommonsStagedOutbound.encoded_frame invalid")


@dataclass(frozen=True, slots=True)
class CommonsConsideration:
    """Bounded Drink consideration under a voluntary commons arrangement."""

    owner_id: AgentId
    tick: int
    target_id: EntityId
    proposal_id: str | None
    opportunity: CommonsConsiderationOpportunity
    choice: CommonsConsiderationChoice

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("CommonsConsideration.owner_id must be AgentId")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("CommonsConsideration.tick", self.tick),
        )
        if type(self.target_id) is not EntityId:
            raise TypeError("CommonsConsideration.target_id must be EntityId")
        if self.proposal_id is not None and (
            type(self.proposal_id) is not str or not self.proposal_id
        ):
            raise ValueError("CommonsConsideration.proposal_id invalid")
        if type(self.opportunity) is not CommonsConsiderationOpportunity:
            raise TypeError(
                "CommonsConsideration.opportunity must be "
                "CommonsConsiderationOpportunity"
            )
        if type(self.choice) is not CommonsConsiderationChoice:
            raise TypeError(
                "CommonsConsideration.choice must be CommonsConsiderationChoice"
            )


@dataclass(frozen=True, slots=True)
class CommonsSentSpeech:
    """Retention of one unchanged claim/report/criticism per recipient."""

    recipient_id: EntityId
    fingerprint: str
    send_tick: int

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("CommonsSentSpeech.recipient_id must be EntityId")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("CommonsSentSpeech.fingerprint invalid")
        object.__setattr__(
            self,
            "send_tick",
            require_exact_nonneg_int("CommonsSentSpeech.send_tick", self.send_tick),
        )


@dataclass(frozen=True, slots=True)
class CommonsLedger:
    """Bounded owner-local commons evidence state."""

    owner_id: AgentId
    observer_entity_id: EntityId
    policy_id: str = COMMONS_GOVERNANCE_POLICY_ID
    last_processed_tick: int = -1
    stocks: tuple[CommonsStockEvidence, ...] = ()
    transitions: tuple[CommonsTransition, ...] = ()
    staged_outbound: CommonsStagedOutbound | None = None
    seen_occurrences: tuple[tuple[EntityId, str], ...] = ()
    seen_roots: tuple[tuple[EntityId, str], ...] = ()
    omission_count: int = 0
    considerations: tuple[CommonsConsideration, ...] = ()
    sent_speech: tuple[CommonsSentSpeech, ...] = ()
    last_deferral_tick: int | None = None
    last_speech_tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("CommonsLedger.owner_id must be AgentId")
        if type(self.observer_entity_id) is not EntityId:
            raise TypeError("CommonsLedger.observer_entity_id must be EntityId")
        if self.policy_id != COMMONS_GOVERNANCE_POLICY_ID:
            raise ValueError("CommonsLedger.policy_id unsupported")
        object.__setattr__(
            self,
            "last_processed_tick",
            require_exact_nonneg_int(
                "CommonsLedger.last_processed_tick",
                self.last_processed_tick + 1,
            )
            - 1,
        )
        if len(self.stocks) > MAX_STOCK_HEADS:
            raise ValueError("CommonsLedger.stocks exceed cap")
        if len(self.transitions) > MAX_TRANSITION_ROWS:
            raise ValueError("CommonsLedger.transitions exceed cap")
        if len(self.considerations) > MAX_CONSIDERATION_ROWS:
            raise ValueError("CommonsLedger.considerations exceed cap")
        if len(self.sent_speech) > MAX_SENT_SPEECH_ROWS:
            raise ValueError("CommonsLedger.sent_speech exceed cap")
        if isinstance(self.omission_count, bool) or (
            type(self.omission_count) is not int
        ):
            raise TypeError("CommonsLedger.omission_count must be int")
        if self.omission_count < 0:
            raise ValueError("CommonsLedger.omission_count must be non-negative")
        if self.last_deferral_tick is not None:
            object.__setattr__(
                self,
                "last_deferral_tick",
                require_exact_nonneg_int(
                    "CommonsLedger.last_deferral_tick", self.last_deferral_tick
                ),
            )
        if self.last_speech_tick is not None:
            object.__setattr__(
                self,
                "last_speech_tick",
                require_exact_nonneg_int(
                    "CommonsLedger.last_speech_tick", self.last_speech_tick
                ),
            )


def empty_commons_ledger(
    owner_id: AgentId, observer_entity_id: EntityId
) -> CommonsLedger:
    """Return an empty owner ledger bound to one observer entity."""

    return CommonsLedger(owner_id=owner_id, observer_entity_id=observer_entity_id)


def commons_proposal_id(
    *,
    stock_id: EntityId,
    proposer_id: EntityId,
    topic: str,
    peer_id: EntityId | None,
    origin_tick: int,
) -> str:
    """Hash the canonical proposal identity material into a stable proposal ID."""

    if type(stock_id) is not EntityId:
        raise TypeError("stock_id must be EntityId")
    if type(proposer_id) is not EntityId:
        raise TypeError("proposer_id must be EntityId")
    if type(topic) is not str or not topic:
        raise ValueError("topic must be a nonempty str")
    if peer_id is not None and type(peer_id) is not EntityId:
        raise TypeError("peer_id must be EntityId or None")
    tick = require_exact_nonneg_int("origin_tick", origin_tick)
    material = json.dumps(
        [
            "commons-proposal-v1",
            stock_id.value,
            proposer_id.value,
            topic,
            None if peer_id is None else peer_id.value,
            tick,
        ],
        separators=(",", ":"),
        sort_keys=False,
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:_PROPOSAL_HEX]
    return f"cgp-{digest}"


def stage_commons_outbound(
    ledger: CommonsLedger,
    *,
    send_tick: int,
    listener_id: EntityId,
    encoded_frame: str,
) -> CommonsLedger:
    """Stage one exact outbound frame for confirmation on the next tick."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    staged = CommonsStagedOutbound(
        send_tick=send_tick,
        listener_id=listener_id,
        encoded_frame=encoded_frame,
    )
    return replace(ledger, staged_outbound=staged)


def commons_lineage_ref(proposal_id: str) -> str:
    """Return the tagged formal-rule lineage witness for one commons proposal."""

    if type(proposal_id) is not str or not proposal_id:
        raise ValueError("proposal_id must be a nonempty str")
    return f"{COMMONS_LINEAGE_PREFIX}{proposal_id}"


def proposal_is_live(proposal: CommonsProposalEvidence, tick: int) -> bool:
    """Return whether a proposal is still within its 16-tick activation window."""

    if type(proposal) is not CommonsProposalEvidence:
        raise TypeError("proposal must be CommonsProposalEvidence")
    absolute = require_exact_nonneg_int("tick", tick)
    if not proposal.eligible:
        return False
    return 0 <= absolute - proposal.origin_tick < PROPOSAL_LIFETIME_TICKS


def proposal_is_supported(proposal: CommonsProposalEvidence) -> bool:
    """Return whether proposer plus a distinct supporter activate the proposal."""

    if type(proposal) is not CommonsProposalEvidence:
        raise TypeError("proposal must be CommonsProposalEvidence")
    supporters = [
        row
        for row in proposal.contributors
        if row.stance is CommonsStance.SUPPORT
        and row.speaker_id != proposal.proposer_id
    ]
    if not supporters:
        return False
    if proposal.topic == "turn":
        if proposal.peer_id is None:
            return False
        return any(row.speaker_id == proposal.peer_id for row in supporters)
    return True


def proposal_is_contested(
    proposal: CommonsProposalEvidence,
    stock: CommonsStockEvidence,
    tick: int,
) -> bool:
    """Return whether opposition or competing live proposals block activation."""

    if type(proposal) is not CommonsProposalEvidence:
        raise TypeError("proposal must be CommonsProposalEvidence")
    if type(stock) is not CommonsStockEvidence:
        raise TypeError("stock must be CommonsStockEvidence")
    if not proposal_is_live(proposal, tick):
        return True
    if any(row.stance is CommonsStance.OPPOSE for row in proposal.contributors):
        return True
    competing = [
        row
        for row in stock.proposals
        if row.proposal_id != proposal.proposal_id
        and proposal_is_live(row, tick)
        and proposal_is_supported(row)
    ]
    return len(competing) >= 1 and proposal_is_supported(proposal)


def supported_live_proposals(
    ledger: CommonsLedger, tick: int
) -> tuple[tuple[CommonsStockEvidence, CommonsProposalEvidence], ...]:
    """Return uncontested supported live proposals visible to the owner."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    absolute = require_exact_nonneg_int("tick", tick)
    rows: list[tuple[CommonsStockEvidence, CommonsProposalEvidence]] = []
    for stock in ledger.stocks:
        for proposal in stock.proposals:
            if not proposal_is_live(proposal, absolute):
                continue
            if not proposal_is_supported(proposal):
                continue
            if proposal_is_contested(proposal, stock, absolute):
                continue
            rows.append((stock, proposal))
    rows.sort(key=lambda item: (item[0].stock_id.value, item[1].proposal_id))
    return tuple(rows)


def expected_turn_actor(
    proposal: CommonsProposalEvidence, tick: int
) -> EntityId | None:
    """Derive the expected turn actor from absolute tick and proposal origin."""

    if type(proposal) is not CommonsProposalEvidence:
        raise TypeError("proposal must be CommonsProposalEvidence")
    if proposal.topic != "turn" or proposal.peer_id is None:
        return None
    absolute = require_exact_nonneg_int("tick", tick)
    if absolute < proposal.origin_tick:
        return None
    slot = (absolute - proposal.origin_tick) // 2
    if slot % 2 == 0:
        return proposal.proposer_id
    return proposal.peer_id


def rest_applies_on_tick(proposal: CommonsProposalEvidence, tick: int) -> bool:
    """Return whether a rest arrangement expects waiting on this tick parity."""

    if type(proposal) is not CommonsProposalEvidence:
        raise TypeError("proposal must be CommonsProposalEvidence")
    if proposal.topic != "rest":
        return False
    absolute = require_exact_nonneg_int("tick", tick)
    return absolute % 2 == proposal.origin_tick % 2


def append_commons_consideration(
    ledger: CommonsLedger, row: CommonsConsideration
) -> CommonsLedger:
    """Append one bounded consideration row, dropping the oldest on overflow."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    if type(row) is not CommonsConsideration:
        raise TypeError("row must be CommonsConsideration")
    rows = [*list(ledger.considerations), row]
    if len(rows) > MAX_CONSIDERATION_ROWS:
        rows = rows[-MAX_CONSIDERATION_ROWS:]
    return replace(ledger, considerations=tuple(rows))


def mark_commons_deferral(ledger: CommonsLedger, tick: int) -> CommonsLedger:
    """Record that an explicit Drink→Wait deferral finalized on this tick."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    absolute = require_exact_nonneg_int("tick", tick)
    return replace(ledger, last_deferral_tick=absolute)


def record_commons_sent_speech(
    ledger: CommonsLedger,
    *,
    recipient_id: EntityId,
    fingerprint: str,
    send_tick: int,
) -> CommonsLedger:
    """Retain one unchanged speech fingerprint per recipient within the window."""

    if type(ledger) is not CommonsLedger:
        raise TypeError("ledger must be CommonsLedger")
    absolute = require_exact_nonneg_int("send_tick", send_tick)
    if type(recipient_id) is not EntityId:
        raise TypeError("recipient_id must be EntityId")
    if type(fingerprint) is not str or not fingerprint:
        raise ValueError("fingerprint must be a nonempty str")
    cutoff = absolute - MAX_EVIDENCE_TICKS + 1
    if cutoff < 0:
        cutoff = 0
    kept = [
        row
        for row in ledger.sent_speech
        if row.send_tick >= cutoff
        and not (
            row.recipient_id == recipient_id and row.fingerprint == fingerprint
        )
    ]
    kept.append(
        CommonsSentSpeech(
            recipient_id=recipient_id,
            fingerprint=fingerprint,
            send_tick=absolute,
        )
    )
    if len(kept) > MAX_SENT_SPEECH_ROWS:
        kept = kept[-MAX_SENT_SPEECH_ROWS:]
    return replace(
        ledger,
        sent_speech=tuple(kept),
        last_speech_tick=absolute,
    )


def mark_commons_speech_sent(
    ledger: CommonsLedger,
    *,
    recipient_id: EntityId,
    fingerprint: str,
    send_tick: int,
) -> CommonsLedger:
    """Alias for ``record_commons_sent_speech`` used by speech decoration."""

    return record_commons_sent_speech(
        ledger,
        recipient_id=recipient_id,
        fingerprint=fingerprint,
        send_tick=send_tick,
    )


def _exact_tenths(quantity: float) -> int | None:
    try:
        rounded = round_physical(quantity)
    except (TypeError, ValueError):
        return None
    if rounded != float(quantity):
        return None
    return round(rounded * 10.0)


def _digest(*parts: object) -> str:
    return hashlib.sha256(
        json.dumps(list(parts), separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def _transition_id(*parts: object) -> str:
    return f"cgt-{_digest(*parts)[:32]}"


def _visible_configured(
    observation: Observation, stock_ids: frozenset[EntityId]
) -> dict[EntityId, ObservedResource]:
    found: dict[EntityId, ObservedResource] = {}
    for resource in observation.resources:
        if type(resource) is not ObservedResource:
            continue
        if resource.entity_id not in stock_ids:
            continue
        found[resource.entity_id] = resource
    return found


def _stock_map(
    stocks: tuple[CommonsStockEvidence, ...]
) -> dict[EntityId, CommonsStockEvidence]:
    return {row.stock_id: row for row in stocks}


def _append_transition(
    transitions: list[CommonsTransition],
    row: CommonsTransition,
    *,
    omissions: list[int],
) -> None:
    transitions.append(row)
    if len(transitions) <= MAX_TRANSITION_ROWS:
        return
    transitions.sort(
        key=lambda item: (item.source_tick, item.transition_id)
    )
    del transitions[0]
    omissions[0] += 1


def _expire_window(
    ledger: CommonsLedger, tick: int
) -> tuple[
    tuple[CommonsStockEvidence, ...],
    tuple[CommonsTransition, ...],
    int,
]:
    cutoff = tick - MAX_EVIDENCE_TICKS + 1
    if cutoff < 0:
        cutoff = 0
    omissions = 0
    kept_transitions = tuple(
        row for row in ledger.transitions if row.source_tick >= cutoff
    )
    omissions += len(ledger.transitions) - len(kept_transitions)
    stocks: list[CommonsStockEvidence] = []
    for stock in ledger.stocks:
        proposals: list[CommonsProposalEvidence] = []
        for proposal in stock.proposals:
            if proposal.origin_tick < cutoff:
                omissions += 1
                continue
            # Activation window is 16 ticks; evidence retention is longer.
            eligible = 0 <= tick - proposal.origin_tick < PROPOSAL_LIFETIME_TICKS
            proposals.append(
                replace(proposal, eligible=eligible)
                if proposal.eligible != eligible
                else proposal
            )
        stocks.append(replace(stock, proposals=tuple(proposals)))
    return tuple(stocks), kept_transitions, omissions


def _evict_stocks(
    stocks: list[CommonsStockEvidence], *, omissions: list[int]
) -> list[CommonsStockEvidence]:
    if len(stocks) <= MAX_STOCK_HEADS:
        return stocks
    stocks.sort(
        key=lambda item: (
            -1 if item.last_visible_tick is None else item.last_visible_tick,
            item.stock_id.value,
        )
    )
    removed = len(stocks) - MAX_STOCK_HEADS
    omissions[0] += removed
    return stocks[removed:]


def _evict_proposals(
    proposals: list[CommonsProposalEvidence], *, omissions: list[int]
) -> list[CommonsProposalEvidence]:
    if len(proposals) <= MAX_PROPOSALS_PER_STOCK:
        return proposals
    proposals.sort(key=lambda item: (item.origin_tick, item.proposal_id))
    removed = len(proposals) - MAX_PROPOSALS_PER_STOCK
    omissions[0] += removed
    return proposals[removed:]


def _is_native_origin(communication: ObservedCommunication) -> bool:
    declared = communication.utterance.declared
    if declared.hop_count != 0:
        return False
    if declared.parent_communication_id is not None:
        return False
    if declared.immediate_source_id != communication.speaker_id:
        return False
    if len(declared.source_agent_chain) != 1:
        return False
    if declared.source_agent_chain[0] != communication.speaker_id:
        return False
    if declared.root_communication_id != declared.communication_id:
        return False
    return True


def _frame_from_communication(
    communication: ObservedCommunication,
) -> CommonsFrame | None:
    from agents.cognition.commons_governance_communication import (
        CGO_FRAME_SUBJECT,
        parse_commons_frame_relation,
    )

    relations = tuple(communication.utterance.content.relations)
    cgo_rows = [
        row for row in relations if getattr(row, "subject", None) == CGO_FRAME_SUBJECT
    ]
    if len(cgo_rows) != 1:
        return None
    try:
        return parse_commons_frame_relation(cgo_rows[0])
    except Exception:
        _LOG.debug("commons_evidence_rejected reason_code=malformed_frame count=1")
        return None


def _find_proposal(
    stocks: dict[EntityId, CommonsStockEvidence], proposal_id: str
) -> tuple[EntityId, CommonsProposalEvidence] | None:
    for stock_id, stock in stocks.items():
        for proposal in stock.proposals:
            if proposal.proposal_id == proposal_id:
                return stock_id, proposal
    return None


def _upsert_contributor(
    proposal: CommonsProposalEvidence,
    speaker_id: EntityId,
    *,
    stance: CommonsStance | None = None,
    stance_tick: int | None = None,
    access_claim_tick: int | None = None,
    report_use_tick: int | None = None,
    report_rest_tick: int | None = None,
    criticize_tick: int | None = None,
    omissions: list[int],
) -> CommonsProposalEvidence | None:
    contributors = {
        row.speaker_id: row for row in proposal.contributors
    }
    existing = contributors.get(speaker_id)
    if existing is None and len(contributors) >= MAX_CONTRIBUTORS_PER_PROPOSAL:
        omissions[0] += 1
        return None
    base = existing or CommonsContributor(speaker_id=speaker_id)
    updated = replace(
        base,
        stance=base.stance if stance is None else stance,
        stance_tick=base.stance_tick if stance_tick is None else stance_tick,
        access_claim_tick=(
            base.access_claim_tick
            if access_claim_tick is None
            else access_claim_tick
        ),
        report_use_tick=(
            base.report_use_tick if report_use_tick is None else report_use_tick
        ),
        report_rest_tick=(
            base.report_rest_tick if report_rest_tick is None else report_rest_tick
        ),
        criticize_tick=(
            base.criticize_tick if criticize_tick is None else criticize_tick
        ),
    )
    contributors[speaker_id] = updated
    ordered = tuple(
        contributors[key]
        for key in sorted(contributors, key=lambda item: item.value)
    )
    return replace(proposal, contributors=ordered)


def _replace_proposal(
    stocks: dict[EntityId, CommonsStockEvidence],
    stock_id: EntityId,
    proposal: CommonsProposalEvidence,
) -> None:
    stock = stocks[stock_id]
    proposals = [
        proposal if row.proposal_id == proposal.proposal_id else row
        for row in stock.proposals
    ]
    if all(row.proposal_id != proposal.proposal_id for row in stock.proposals):
        proposals.append(proposal)
    omission_box = [0]
    proposals = _evict_proposals(list(proposals), omissions=omission_box)
    stocks[stock_id] = replace(stock, proposals=tuple(proposals))


def _fold_stock_visibility(
    *,
    owner_id: AgentId,
    stocks: dict[EntityId, CommonsStockEvidence],
    visible: dict[EntityId, ObservedResource],
    tick: int,
    transitions: list[CommonsTransition],
    omissions: list[int],
) -> None:
    for stock_id, resource in sorted(
        visible.items(), key=lambda item: item[0].value
    ):
        tenths = _exact_tenths(resource.quantity)
        if tenths is None:
            _LOG.debug(
                "commons_evidence_rejected reason_code=quantity_not_tenths count=1"
            )
            continue
        prior = stocks.get(stock_id)
        last_tick = None if prior is None else prior.last_visible_tick
        last_qty = None if prior is None else prior.last_quantity_tenths
        consecutive = last_tick is not None and last_tick == tick - 1
        if not consecutive or last_qty is None:
            signal = CommonsQuantitySignal.BASELINE
            signal_code: CommonsEvidenceCode | None = None
        elif tenths < last_qty:
            signal = CommonsQuantitySignal.DECLINE
            signal_code = CommonsEvidenceCode.STOCK_DECLINED
        else:
            signal = CommonsQuantitySignal.NONDECLINE
            signal_code = CommonsEvidenceCode.STOCK_NONDECLINE
        checked = CommonsTransition(
            transition_id=_transition_id(
                owner_id.value,
                stock_id.value,
                tick,
                CommonsEvidenceCode.STOCK_CHECKED.value,
                tenths,
                signal.value,
            ),
            owner_id=owner_id,
            stock_id=stock_id,
            source_tick=tick,
            code=CommonsEvidenceCode.STOCK_CHECKED,
            quantity_tenths=tenths,
            signal=signal,
        )
        _append_transition(transitions, checked, omissions=omissions)
        if signal_code is not None:
            _append_transition(
                transitions,
                CommonsTransition(
                    transition_id=_transition_id(
                        owner_id.value,
                        stock_id.value,
                        tick,
                        signal_code.value,
                        tenths,
                        signal.value,
                    ),
                    owner_id=owner_id,
                    stock_id=stock_id,
                    source_tick=tick,
                    code=signal_code,
                    quantity_tenths=tenths,
                    signal=signal,
                ),
                omissions=omissions,
            )
        proposals = () if prior is None else prior.proposals
        access_claims = () if prior is None else prior.access_claims
        stocks[stock_id] = CommonsStockEvidence(
            stock_id=stock_id,
            last_visible_tick=tick,
            last_quantity_tenths=tenths,
            proposals=proposals,
            access_claims=access_claims,
        )


def _mark_seen(
    seen_occurrences: set[tuple[EntityId, str]],
    seen_roots: set[tuple[EntityId, str]],
    *,
    speaker_id: EntityId,
    occurrence_ref: str,
    root_ref: str,
) -> bool:
    occurrence_key = (speaker_id, occurrence_ref)
    root_key = (speaker_id, root_ref)
    if occurrence_key in seen_occurrences or root_key in seen_roots:
        return False
    seen_occurrences.add(occurrence_key)
    seen_roots.add(root_key)
    return True


def _apply_frame(
    *,
    owner_id: AgentId,
    observer_id: EntityId,
    stocks: dict[EntityId, CommonsStockEvidence],
    visible_ids: frozenset[EntityId],
    frame: CommonsFrame,
    speaker_id: EntityId,
    listener_id: EntityId,
    source_tick: int,
    occurrence_ref: str,
    root_ref: str,
    transitions: list[CommonsTransition],
    omissions: list[int],
    seen_occurrences: set[tuple[EntityId, str]],
    seen_roots: set[tuple[EntityId, str]],
    outbound_self: bool,
    current_tick: int,
) -> None:
    from agents.cognition.commons_governance_communication import (
        CommonsAct,
        CommonsTopic,
    )

    if frame.stock_id not in visible_ids and not outbound_self:
        _LOG.debug(
            "commons_evidence_rejected reason_code=stock_not_visible count=1"
        )
        return
    if not _mark_seen(
        seen_occurrences,
        seen_roots,
        speaker_id=speaker_id,
        occurrence_ref=occurrence_ref,
        root_ref=root_ref,
    ):
        _LOG.debug("commons_evidence_rejected reason_code=duplicate count=1")
        return
    cutoff = current_tick - MAX_EVIDENCE_TICKS + 1
    if cutoff < 0:
        cutoff = 0

    act = frame.act
    if act is CommonsAct.PROPOSE:
        expected = commons_proposal_id(
            stock_id=frame.stock_id,
            proposer_id=speaker_id,
            topic=frame.topic.value,
            peer_id=frame.peer_id,
            origin_tick=source_tick,
        )
        if frame.topic is CommonsTopic.TURN:
            if frame.peer_id is None or listener_id != frame.peer_id:
                _LOG.debug(
                    "commons_evidence_rejected reason_code=turn_addressee count=1"
                )
                return
        stock = stocks.get(frame.stock_id)
        if stock is None:
            stock = CommonsStockEvidence(stock_id=frame.stock_id)
            stocks[frame.stock_id] = stock
        if any(row.proposal_id == expected for row in stock.proposals):
            _LOG.debug(
                "commons_evidence_rejected reason_code=duplicate_proposal count=1"
            )
            return
        proposal = CommonsProposalEvidence(
            proposal_id=expected,
            stock_id=frame.stock_id,
            topic=frame.topic.value,
            proposer_id=speaker_id,
            peer_id=frame.peer_id,
            origin_tick=source_tick,
            eligible=source_tick >= cutoff,
        )
        proposals = [*list(stock.proposals), proposal]
        proposals = _evict_proposals(proposals, omissions=omissions)
        stocks[frame.stock_id] = replace(stock, proposals=tuple(proposals))
        _append_transition(
            transitions,
            CommonsTransition(
                transition_id=_transition_id(
                    owner_id.value,
                    expected,
                    source_tick,
                    CommonsEvidenceCode.PROPOSE.value,
                    speaker_id.value,
                ),
                owner_id=owner_id,
                stock_id=frame.stock_id,
                source_tick=source_tick,
                code=CommonsEvidenceCode.PROPOSE,
                proposal_id=expected,
                actor_id=speaker_id,
                occurrence_ref=occurrence_ref,
            ),
            omissions=omissions,
        )
        return

    if act is CommonsAct.CLAIM_ACCESS:
        stock = stocks.get(frame.stock_id)
        if stock is None:
            stock = CommonsStockEvidence(stock_id=frame.stock_id)
            stocks[frame.stock_id] = stock
        claim = CommonsAccessClaim(
            speaker_id=speaker_id,
            source_tick=source_tick,
            occurrence_ref=occurrence_ref,
        )
        claims = [
            row for row in stock.access_claims if row.speaker_id != speaker_id
        ]
        claims.append(claim)
        claims.sort(key=lambda row: (row.source_tick, row.speaker_id.value))
        if len(claims) > MAX_CONTRIBUTORS_PER_PROPOSAL:
            omissions[0] += len(claims) - MAX_CONTRIBUTORS_PER_PROPOSAL
            claims = claims[-MAX_CONTRIBUTORS_PER_PROPOSAL:]
        stocks[frame.stock_id] = replace(stock, access_claims=tuple(claims))
        _append_transition(
            transitions,
            CommonsTransition(
                transition_id=_transition_id(
                    owner_id.value,
                    frame.stock_id.value,
                    source_tick,
                    CommonsEvidenceCode.ACCESS_CLAIM.value,
                    speaker_id.value,
                    occurrence_ref,
                ),
                owner_id=owner_id,
                stock_id=frame.stock_id,
                source_tick=source_tick,
                code=CommonsEvidenceCode.ACCESS_CLAIM,
                actor_id=speaker_id,
                occurrence_ref=occurrence_ref,
            ),
            omissions=omissions,
        )
        return

    found = _find_proposal(stocks, frame.proposal_id or "")
    if found is None:
        _LOG.debug("commons_evidence_rejected reason_code=unknown_proposal count=1")
        return
    stock_id, proposal = found
    if not proposal.eligible or proposal.origin_tick < cutoff:
        _LOG.debug("commons_evidence_rejected reason_code=expired_proposal count=1")
        return
    if proposal.origin_tick >= source_tick:
        _LOG.debug(
            "commons_evidence_rejected reason_code=proposal_not_earlier count=1"
        )
        return
    if proposal.stock_id != frame.stock_id or proposal.topic != frame.topic.value:
        _LOG.debug("commons_evidence_rejected reason_code=proposal_mismatch count=1")
        return
    if act in {CommonsAct.SUPPORT, CommonsAct.OPPOSE}:
        if speaker_id == proposal.proposer_id and act is CommonsAct.SUPPORT:
            _LOG.debug(
                "commons_evidence_rejected reason_code=self_support count=1"
            )
            return
        stance = (
            CommonsStance.SUPPORT
            if act is CommonsAct.SUPPORT
            else CommonsStance.OPPOSE
        )
        updated = _upsert_contributor(
            proposal,
            speaker_id,
            stance=stance,
            stance_tick=source_tick,
            omissions=omissions,
        )
        if updated is None:
            return
        _replace_proposal(stocks, stock_id, updated)
        _append_transition(
            transitions,
            CommonsTransition(
                transition_id=_transition_id(
                    owner_id.value,
                    proposal.proposal_id,
                    source_tick,
                    CommonsEvidenceCode.STANCE.value,
                    speaker_id.value,
                    stance.value,
                ),
                owner_id=owner_id,
                stock_id=stock_id,
                source_tick=source_tick,
                code=CommonsEvidenceCode.STANCE,
                proposal_id=proposal.proposal_id,
                actor_id=speaker_id,
                stance=stance,
                occurrence_ref=occurrence_ref,
            ),
            omissions=omissions,
        )
        return

    if act is CommonsAct.CRITICIZE:
        # Criticism targets the reporting actor (listener); never a third-party
        # draw accusation and never self-addressed outbound criticism.
        if outbound_self and listener_id == speaker_id:
            _LOG.debug(
                "commons_evidence_rejected reason_code=criticize_self count=1"
            )
            return
        reporter = next(
            (
                row
                for row in proposal.contributors
                if row.speaker_id == listener_id
                and (
                    row.report_use_tick is not None
                    or row.report_rest_tick is not None
                )
            ),
            None,
        )
        if reporter is None:
            _LOG.debug(
                "commons_evidence_rejected reason_code=criticize_no_report count=1"
            )
            return
        updated = _upsert_contributor(
            proposal,
            speaker_id,
            criticize_tick=source_tick,
            omissions=omissions,
        )
        if updated is None:
            return
        _replace_proposal(stocks, stock_id, updated)
        _append_transition(
            transitions,
            CommonsTransition(
                transition_id=_transition_id(
                    owner_id.value,
                    proposal.proposal_id,
                    source_tick,
                    CommonsEvidenceCode.CRITICIZE.value,
                    speaker_id.value,
                    frame.reported_tick,
                ),
                owner_id=owner_id,
                stock_id=stock_id,
                source_tick=source_tick,
                code=CommonsEvidenceCode.CRITICIZE,
                proposal_id=proposal.proposal_id,
                actor_id=speaker_id,
                reported_tick=frame.reported_tick,
                occurrence_ref=occurrence_ref,
            ),
            omissions=omissions,
        )
        return

    if act is CommonsAct.REPORT_USE:
        updated = _upsert_contributor(
            proposal,
            speaker_id,
            report_use_tick=source_tick,
            omissions=omissions,
        )
        if updated is None:
            return
        _replace_proposal(stocks, stock_id, updated)
        _append_transition(
            transitions,
            CommonsTransition(
                transition_id=_transition_id(
                    owner_id.value,
                    proposal.proposal_id,
                    source_tick,
                    CommonsEvidenceCode.REPORT_USE.value,
                    speaker_id.value,
                    frame.reported_tick,
                ),
                owner_id=owner_id,
                stock_id=stock_id,
                source_tick=source_tick,
                code=CommonsEvidenceCode.REPORT_USE,
                proposal_id=proposal.proposal_id,
                actor_id=speaker_id,
                reported_tick=frame.reported_tick,
                occurrence_ref=occurrence_ref,
            ),
            omissions=omissions,
        )
        return

    if act is CommonsAct.REPORT_REST:
        updated = _upsert_contributor(
            proposal,
            speaker_id,
            report_rest_tick=source_tick,
            omissions=omissions,
        )
        if updated is None:
            return
        _replace_proposal(stocks, stock_id, updated)
        _append_transition(
            transitions,
            CommonsTransition(
                transition_id=_transition_id(
                    owner_id.value,
                    proposal.proposal_id,
                    source_tick,
                    CommonsEvidenceCode.REPORT_REST.value,
                    speaker_id.value,
                    frame.reported_tick,
                ),
                owner_id=owner_id,
                stock_id=stock_id,
                source_tick=source_tick,
                code=CommonsEvidenceCode.REPORT_REST,
                proposal_id=proposal.proposal_id,
                actor_id=speaker_id,
                reported_tick=frame.reported_tick,
                occurrence_ref=occurrence_ref,
            ),
            omissions=omissions,
        )
        return


def _fold_communications(
    *,
    owner_id: AgentId,
    observer_id: EntityId,
    prior: CommonsLedger,
    observation: Observation,
    stocks: dict[EntityId, CommonsStockEvidence],
    visible_ids: frozenset[EntityId],
    transitions: list[CommonsTransition],
    omissions: list[int],
) -> tuple[
    CommonsStagedOutbound | None,
    set[tuple[EntityId, str]],
    set[tuple[EntityId, str]],
]:
    from agents.cognition.commons_governance_communication import encode_commons_frame

    seen_occurrences = set(prior.seen_occurrences)
    seen_roots = set(prior.seen_roots)
    staged = prior.staged_outbound
    matched_staged = False

    deliveries: list[tuple[int, str, ObservedCommunication, bool]] = []
    for communication in observation.communications:
        if type(communication) is not ObservedCommunication:
            continue
        if communication.action_kind not in _TALK_TELL:
            continue
        event_id = communication.provenance.source_event_id
        if event_id is None:
            continue
        source_tick = communication.provenance.source_tick
        if source_tick >= observation.tick:
            continue
        if not _is_native_origin(communication):
            _LOG.debug("commons_evidence_rejected reason_code=relay count=1")
            continue
        inbound = (
            communication.listener_id == observer_id
            and communication.speaker_id != observer_id
        )
        outbound = (
            communication.speaker_id == observer_id
            and staged is not None
            and communication.listener_id == staged.listener_id
            and source_tick == staged.send_tick
        )
        if not inbound and not outbound:
            continue
        deliveries.append(
            (source_tick, event_id.value, communication, outbound)
        )

    deliveries.sort(key=lambda item: (item[0], item[1]))
    for source_tick, occurrence_ref, communication, outbound in deliveries:
        frame = _frame_from_communication(communication)
        if frame is None:
            continue
        if outbound:
            assert staged is not None
            try:
                encoded = encode_commons_frame(frame)
            except Exception:
                _LOG.debug(
                    "commons_evidence_rejected reason_code=outbound_frame count=1"
                )
                continue
            if encoded != staged.encoded_frame:
                _LOG.debug(
                    "commons_evidence_rejected reason_code=outbound_mismatch count=1"
                )
                continue
            matched_staged = True
        root_ref = communication.utterance.declared.root_communication_id.value
        _apply_frame(
            owner_id=owner_id,
            observer_id=observer_id,
            stocks=stocks,
            visible_ids=visible_ids,
            frame=frame,
            speaker_id=communication.speaker_id,
            listener_id=communication.listener_id,
            source_tick=source_tick,
            occurrence_ref=occurrence_ref,
            root_ref=root_ref,
            transitions=transitions,
            omissions=omissions,
            seen_occurrences=seen_occurrences,
            seen_roots=seen_roots,
            outbound_self=outbound,
            current_tick=observation.tick,
        )

    next_staged: CommonsStagedOutbound | None
    if staged is None or matched_staged:
        next_staged = None
    elif observation.tick > staged.send_tick:
        _LOG.debug("commons_staged_expired reason_code=unmatched count=1")
        next_staged = None
    else:
        next_staged = staged
    return next_staged, seen_occurrences, seen_roots


def advance_commons_evidence(
    owner_id: AgentId,
    prior: CommonsLedger,
    observation: Observation,
    stock_ids: tuple[EntityId, ...] | list[EntityId],
) -> CommonsLedger:
    """Fold one finalized observation into a pure owner commons ledger."""

    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if type(prior) is not CommonsLedger:
        raise TypeError("prior must be CommonsLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if isinstance(stock_ids, (str, bytes)) or not isinstance(stock_ids, (tuple, list)):
        raise TypeError("stock_ids must be a sequence of EntityId")
    if prior.owner_id != owner_id:
        raise ValueError("commons_governance_wrong_owner")
    if observation.observer_id != prior.observer_entity_id:
        raise ValueError("commons_governance_wrong_owner")
    for index, stock_id in enumerate(stock_ids):
        if type(stock_id) is not EntityId:
            raise TypeError(f"stock_ids[{index}] must be EntityId")
    if observation.tick < prior.last_processed_tick:
        raise ValueError("commons_governance_tick_rewind")
    if observation.tick == prior.last_processed_tick:
        return prior

    configured = frozenset(stock_ids)
    expired_stocks, expired_transitions, expired_omissions = _expire_window(
        prior, observation.tick
    )
    stocks = _stock_map(expired_stocks)
    transitions = list(expired_transitions)
    omissions = [expired_omissions + prior.omission_count]
    visible = _visible_configured(observation, configured)
    visible_ids = frozenset(visible)

    _fold_stock_visibility(
        owner_id=owner_id,
        stocks=stocks,
        visible=visible,
        tick=observation.tick,
        transitions=transitions,
        omissions=omissions,
    )

    staged, seen_occurrences, seen_roots = _fold_communications(
        owner_id=owner_id,
        observer_id=prior.observer_entity_id,
        prior=prior,
        observation=observation,
        stocks=stocks,
        visible_ids=visible_ids,
        transitions=transitions,
        omissions=omissions,
    )

    stock_list = _evict_stocks(list(stocks.values()), omissions=omissions)
    stock_list.sort(key=lambda item: item.stock_id.value)
    transitions.sort(key=lambda item: (item.source_tick, item.transition_id))
    if len(transitions) > MAX_TRANSITION_ROWS:
        overflow = len(transitions) - MAX_TRANSITION_ROWS
        transitions = transitions[overflow:]
        omissions[0] += overflow

    seen_occ_tuple = tuple(
        sorted(seen_occurrences, key=lambda item: (item[0].value, item[1]))
    )
    seen_root_tuple = tuple(
        sorted(seen_roots, key=lambda item: (item[0].value, item[1]))
    )
    # Bound dedupe retention to the evidence window size.
    if len(seen_occ_tuple) > MAX_TRANSITION_ROWS:
        seen_occ_tuple = seen_occ_tuple[-MAX_TRANSITION_ROWS:]
        omissions[0] += 1
    if len(seen_root_tuple) > MAX_TRANSITION_ROWS:
        seen_root_tuple = seen_root_tuple[-MAX_TRANSITION_ROWS:]
        omissions[0] += 1

    consideration_cutoff = observation.tick - MAX_EVIDENCE_TICKS + 1
    if consideration_cutoff < 0:
        consideration_cutoff = 0
    kept_considerations = tuple(
        row for row in prior.considerations if row.tick >= consideration_cutoff
    )
    if len(kept_considerations) < len(prior.considerations):
        omissions[0] += len(prior.considerations) - len(kept_considerations)
    kept_sent = tuple(
        row for row in prior.sent_speech if row.send_tick >= consideration_cutoff
    )
    if len(kept_sent) < len(prior.sent_speech):
        omissions[0] += len(prior.sent_speech) - len(kept_sent)

    _LOG.debug(
        "commons_evidence_advanced tick=%s stock_count=%s transition_count=%s "
        "omission_count=%s",
        observation.tick,
        len(stock_list),
        len(transitions),
        omissions[0],
    )
    return CommonsLedger(
        owner_id=owner_id,
        observer_entity_id=prior.observer_entity_id,
        last_processed_tick=observation.tick,
        stocks=tuple(stock_list),
        transitions=tuple(transitions),
        staged_outbound=staged,
        seen_occurrences=seen_occ_tuple,
        seen_roots=seen_root_tuple,
        omission_count=omissions[0],
        considerations=kept_considerations,
        sent_speech=kept_sent,
        last_deferral_tick=prior.last_deferral_tick,
        last_speech_tick=prior.last_speech_tick,
    )
