"""Deterministic owner-local theory transitions and bounded speech selection."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from typing import Final

from agents.cognition.competing_theories import (
    MAX_ECHOES,
    MAX_FOUNDING_CONTEXTS,
    MAX_OUTBOUND,
    MAX_RECEIPTS,
    CompetingTheoryLedger,
    TheoryAccount,
    TheoryBaseOutcome,
    TheoryCitation,
    TheoryCitationKind,
    TheoryCitationPolarity,
    TheoryClaim,
    TheoryContext,
    TheoryOutboundCorrelation,
    TheorySenderEcho,
    TheorySocialKind,
    TheorySocialReceipt,
    TheorySpeechAct,
    TheoryStance,
    TheoryStanceAction,
    TheoryStanceRequest,
    _bump_coverage,
    active_supported_claim,
    apply_theory_updates,
    theory_claim_id,
    theory_context_digest,
    theory_context_from_case,
)
from agents.cognition.competing_theory_communication import (
    TheoryMessage,
    decode_theory_message,
    message_from_claim,
)
from agents.cognition.competing_theory_forecasts import (
    abandon_theory_case,
    issue_theory_case,
    settle_theory_case,
)
from agents.cognition.scientific_models import (
    ForecastCase,
    ForecastCaseState,
    ScientificModelLedger,
)
from world.identifiers import AgentId

__all__ = [
    "advance_competing_theories",
    "record_theory_outbound",
    "select_theory_speech",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.competing_theory_policy"
)

_FOUNDING_PRIOR_VERSION: Final[str] = "competing-theories-prior-v1"
_MIN_SOCIAL_SUPPORTERS: Final[int] = 2


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def _self_entity_value(observation: object) -> str | None:
    body = getattr(observation, "self_body", None)
    entity_id = getattr(body, "entity_id", None)
    if entity_id is None:
        return None
    return str(getattr(entity_id, "value", entity_id))


def _event_key(communication: object) -> tuple[int, str, str, str]:
    provenance = getattr(communication, "provenance", None)
    tick = getattr(provenance, "source_tick", 0)
    event_id = getattr(provenance, "source_event_id", None)
    event_token = "" if event_id is None else str(getattr(event_id, "value", event_id))
    speaker = getattr(communication, "speaker_id", None)
    listener = getattr(communication, "listener_id", None)
    return (
        tick,
        event_token,
        "" if speaker is None else str(getattr(speaker, "value", speaker)),
        "" if listener is None else str(getattr(listener, "value", listener)),
    )


def _base_outcome(case: ForecastCase) -> TheoryBaseOutcome | None:
    if case.observed is None:
        return None
    context = theory_context_from_case(case)
    if context is None:
        return None
    return TheoryBaseOutcome(
        owner_id=case.owner_id,
        base_case_id=case.case_id,
        observed_category=case.observed.observed_class,
        observed_tick=case.observed.observed_tick,
        outcome_ref=case.observed.outcome_ref,
        location_id=context.location_id,
        season=context.origin_season,
        resource_kind=(
            case.reference_resource_kind
            if context.target_kind.value == "resource_regeneration"
            else None
        ),
        unit_token=(
            case.unit_token
            if context.target_kind.value == "resource_regeneration"
            else None
        ),
    )


def _ensure_continuity_claim(
    ledger: CompetingTheoryLedger, case: ForecastCase, *, tick: int
) -> CompetingTheoryLedger:
    context = theory_context_from_case(case)
    if context is None:
        return ledger
    claim = TheoryClaim(
        context=context,
        account=TheoryAccount.CONTINUITY,
        predicted_category=context.continuity_category,
        claim_id=theory_claim_id(
            context, TheoryAccount.CONTINUITY, context.continuity_category
        ),
        created_tick=tick,
    )
    citation = TheoryCitation(
        claim_id=claim.claim_id,
        owner_tick=tick,
        polarity=TheoryCitationPolarity.CONTEXT_ONLY,
        kind=TheoryCitationKind.OWN_OBSERVATION,
        root_ref=case.issued_observation_key,
        provenance_ref=case.case_id,
    )
    return apply_theory_updates(
        ledger,
        tick=tick,
        claims=(claim,),
        citations=(citation,),
    )


def _settle_due_cases(
    ledger: CompetingTheoryLedger,
    observation: object,
    *,
    scientific_models: ScientificModelLedger | None,
) -> CompetingTheoryLedger:
    tick = getattr(observation, "tick", 0)
    by_id = (
        {row.case_id: row for row in scientific_models.cases}
        if scientific_models is not None
        else {}
    )
    updated = ledger
    for case in tuple(ledger.pending_cases):
        base = by_id.get(case.base_case_id)
        if base is None:
            if tick >= case.target_tick:
                updated = abandon_theory_case(
                    updated, base_case_id=case.base_case_id, tick=tick
                )
            continue
        if base.state is ForecastCaseState.SCORED:
            outcome = _base_outcome(base)
            if outcome is None:
                updated = abandon_theory_case(
                    updated, base_case_id=case.base_case_id, tick=tick
                )
            else:
                updated = settle_theory_case(updated, outcome)
        elif base.state is ForecastCaseState.PENDING:
            continue
        elif base.state is ForecastCaseState.NOT_COMPARABLE:
            updated = abandon_theory_case(
                updated,
                base_case_id=case.base_case_id,
                tick=tick,
                reason="not_comparable",
            )
        else:
            updated = abandon_theory_case(
                updated, base_case_id=case.base_case_id, tick=tick
            )
    return updated


def _derive_new_claims(
    ledger: CompetingTheoryLedger,
    *,
    previous: ScientificModelLedger | None,
    current: ScientificModelLedger | None,
) -> CompetingTheoryLedger:
    if current is None:
        return ledger
    previous_ids = (
        {row.case_id for row in previous.cases if row.observed is not None}
        if previous is not None
        else set()
    )
    updated = ledger
    for case in sorted(
        current.cases,
        key=lambda row: (row.target_observation_tick, row.case_id),
    ):
        if case.observed is None or case.case_id in previous_ids:
            continue
        from agents.cognition.competing_theories import derive_local_theory_claims

        updated = derive_local_theory_claims(updated, case)
    return updated


def _ensure_known_claim(
    ledger: CompetingTheoryLedger, message: TheoryMessage, *, tick: int
) -> CompetingTheoryLedger:
    if any(row.claim_id == message.claim_id for row in ledger.claims):
        return ledger
    claim = TheoryClaim(
        context=message.context,
        account=message.account,
        predicted_category=message.predicted_category,
        claim_id=message.claim_id,
        created_tick=tick,
    )
    return apply_theory_updates(ledger, tick=tick, claims=(claim,))


def _receipt_admission(
    ledger: CompetingTheoryLedger, receipt: TheorySocialReceipt, *, tick: int
) -> CompetingTheoryLedger:
    if any(row.claim_id == receipt.claim_id for row in ledger.claims) is False:
        return replace(
            ledger,
            refused_receipts=ledger.refused_receipts + 1,
            coverage=_bump_coverage(
                ledger.coverage, reason_code="receipt_cap", tick=tick
            ),
        )
    if any(row.receipt_id == receipt.receipt_id for row in ledger.receipts):
        return ledger
    if len(ledger.receipts) >= MAX_RECEIPTS:
        return replace(
            ledger,
            refused_receipts=ledger.refused_receipts + 1,
            coverage=_bump_coverage(
                ledger.coverage, reason_code="receipt_cap", tick=tick
            ),
        )
    rows = tuple(
        sorted(
            (*ledger.receipts, receipt),
            key=lambda row: (row.tick, row.receipt_id),
        )
    )
    return replace(ledger, receipts=rows)


def _echo_admission(
    ledger: CompetingTheoryLedger, echo: TheorySenderEcho, *, tick: int
) -> CompetingTheoryLedger:
    if any(row.echo_id == echo.echo_id for row in ledger.echoes):
        return ledger
    if len(ledger.echoes) >= MAX_ECHOES:
        return ledger
    rows = tuple(
        sorted((*ledger.echoes, echo), key=lambda row: (row.observed_tick, row.echo_id))
    )
    return replace(ledger, echoes=rows)


def _ingest_communications(
    ledger: CompetingTheoryLedger, observation: object
) -> CompetingTheoryLedger:
    self_entity = _self_entity_value(observation)
    if self_entity is None:
        return ledger
    tick = getattr(observation, "tick", 0)
    communications = tuple(getattr(observation, "communications", ()))
    ordered = sorted(communications, key=_event_key)
    updated = ledger
    for communication in ordered:
        source_tick, event_token, speaker_value, listener_value = _event_key(
            communication
        )
        if not event_token or source_tick >= tick:
            continue
        if getattr(communication, "action_kind", None) == "ask":
            continue
        message = decode_theory_message(communication)
        if message is None:
            continue
        declared = getattr(getattr(communication, "utterance", None), "declared", None)
        origin = bool(
            getattr(declared, "hop_count", -1) == 0
            and str(
                getattr(getattr(declared, "immediate_source_id", None), "value", "")
            )
            == speaker_value
        )
        root_ref = (
            str(getattr(getattr(declared, "communication_id", None), "value", ""))
            if origin
            else ""
        )
        if speaker_value == self_entity:
            matched = next(
                (
                    row
                    for row in updated.outbound
                    if row.recipient_entity_id == listener_value
                    and row.claim_id == message.claim_id
                    and row.act is message.act
                ),
                None,
            )
            if matched is None:
                continue
            echo = TheorySenderEcho(
                echo_id="the-"
                + _digest(
                    updated.owner_id.value,
                    event_token,
                    matched.claim_id,
                    matched.act.value,
                ),
                recipient_entity_id=listener_value,
                claim_id=matched.claim_id,
                stance_revision=matched.stance_revision,
                act=matched.act,
                send_tick=matched.send_tick,
                observed_tick=source_tick,
                frame_digest=message.frame_digest,
                event_ref=event_token,
            )
            updated = _echo_admission(updated, echo, tick=source_tick)
            updated = replace(
                updated,
                outbound=tuple(row for row in updated.outbound if row != matched),
            )
            continue
        if listener_value != self_entity:
            continue
        updated = _ensure_known_claim(updated, message, tick=source_tick)
        kind = (
            TheorySocialKind.TAUGHT
            if message.act is TheorySpeechAct.TEACH
            else TheorySocialKind.COMMUNICATED
        )
        receipt = TheorySocialReceipt(
            receipt_id="thr-"
            + _digest(
                updated.owner_id.value,
                event_token,
                speaker_value,
                message.claim_id,
                message.act.value,
            ),
            claim_id=message.claim_id,
            speaker_id=AgentId(speaker_value),
            kind=kind,
            tick=source_tick,
            root_ref=root_ref,
            relation_ref=event_token,
            act=message.act,
            origin=origin,
        )
        updated = _receipt_admission(updated, receipt, tick=source_tick)
    return updated


def _live_peer_support(
    ledger: CompetingTheoryLedger,
) -> dict[str, dict[str, int]]:
    """Map context digest to claim id to distinct live origin supporters."""

    claims = {row.claim_id: row for row in ledger.claims}
    latest: dict[tuple[str, str], TheorySocialReceipt] = {}
    for receipt in ledger.receipts:
        if not receipt.origin:
            continue
        if receipt.act not in (TheorySpeechAct.SUPPORT, TheorySpeechAct.WITHDRAW):
            continue
        claim = claims.get(receipt.claim_id)
        if claim is None:
            continue
        key = (receipt.speaker_id.value, receipt.claim_id)
        current = latest.get(key)
        if current is None or (receipt.tick, receipt.receipt_id) > (
            current.tick,
            current.receipt_id,
        ):
            latest[key] = receipt
    context_claims: dict[str, set[str]] = {}
    for claim in ledger.claims:
        context_claims.setdefault(theory_context_digest(claim.context), set()).add(
            claim.claim_id
        )
    counts: dict[str, dict[str, int]] = {}
    for (_speaker, claim_id), receipt in latest.items():
        if receipt.act is not TheorySpeechAct.SUPPORT:
            continue
        claim = claims[claim_id]
        digest = theory_context_digest(claim.context)
        if claim_id not in context_claims.get(digest, set()):
            continue
        bucket = counts.setdefault(digest, {})
        bucket[claim_id] = bucket.get(claim_id, 0) + 1
    return counts


def _founding_preference(
    ledger: CompetingTheoryLedger, context: TheoryContext
) -> str | None:
    continuity = next(
        (
            row
            for row in ledger.claims
            if theory_context_digest(row.context) == theory_context_digest(context)
            and row.account is TheoryAccount.CONTINUITY
        ),
        None,
    )
    recurrence = min(
        (
            row
            for row in ledger.claims
            if theory_context_digest(row.context) == theory_context_digest(context)
            and row.account is TheoryAccount.RECURRENCE
            and row.locally_derived_tick is not None
        ),
        key=lambda row: (row.locally_derived_tick or 0, row.claim_id),
        default=None,
    )
    material = (
        _FOUNDING_PRIOR_VERSION
        + str(len(ledger.owner_id.value))
        + ledger.owner_id.value
        + theory_context_digest(context)
    )
    first = hashlib.sha256(material.encode("utf-8")).digest()[0]
    if first & 1 and recurrence is not None:
        return recurrence.claim_id
    return None if continuity is None else continuity.claim_id


def _choose_stances(
    ledger: CompetingTheoryLedger, *, tick: int
) -> CompetingTheoryLedger:
    counts = _live_peer_support(ledger)
    contexts: dict[str, TheoryContext] = {}
    for claim in ledger.claims:
        contexts.setdefault(theory_context_digest(claim.context), claim.context)
    updated = ledger
    for digest in sorted(contexts):
        context = contexts[digest]
        active = active_supported_claim(updated, context)
        context_counts = counts.get(digest, {})
        social = {
            claim_id: count
            for claim_id, count in context_counts.items()
            if count >= _MIN_SOCIAL_SUPPORTERS
        }
        social_choice: str | None = None
        if social:
            top = max(social.values())
            leaders = sorted(
                claim_id for claim_id, count in social.items() if count == top
            )
            if len(leaders) == 1:
                social_choice = leaders[0]
        if active is None:
            if social_choice is not None:
                updated = apply_theory_updates(
                    updated,
                    tick=tick,
                    stances=(
                        TheoryStanceRequest(
                            context, TheoryStanceAction.SUPPORT, social_choice
                        ),
                    ),
                )
                updated = _mark_founding_consumed(updated, digest)
            elif digest not in updated.founding_consumed:
                chosen = _founding_preference(updated, context)
                if chosen is not None:
                    updated = apply_theory_updates(
                        updated,
                        tick=tick,
                        stances=(
                            TheoryStanceRequest(
                                context, TheoryStanceAction.SUPPORT, chosen
                            ),
                        ),
                    )
                updated = _mark_founding_consumed(updated, digest)
            continue
        if social_choice is None or social_choice == active:
            continue
        current_count = context_counts.get(active, 0)
        top = max(social.values())
        rivals = sorted(
            claim_id
            for claim_id, count in social.items()
            if claim_id != active and count == top
        )
        if len(rivals) != 1 or top <= current_count:
            continue
        updated = apply_theory_updates(
            updated,
            tick=tick,
            stances=(
                TheoryStanceRequest(context, TheoryStanceAction.SUPPORT, rivals[0]),
            ),
        )
    return updated


def _mark_founding_consumed(
    ledger: CompetingTheoryLedger, digest: str
) -> CompetingTheoryLedger:
    if digest in ledger.founding_consumed:
        return ledger
    if len(ledger.founding_consumed) >= MAX_FOUNDING_CONTEXTS:
        return ledger
    return replace(ledger, founding_consumed=(*ledger.founding_consumed, digest))


def _expire_outbound(
    ledger: CompetingTheoryLedger, *, tick: int
) -> CompetingTheoryLedger:
    retained = tuple(row for row in ledger.outbound if row.send_tick >= tick)
    if retained == ledger.outbound:
        return ledger
    return replace(ledger, outbound=retained)


def advance_competing_theories(
    ledger: CompetingTheoryLedger,
    observation: object,
    *,
    previous_scientific_models: ScientificModelLedger | None,
    scientific_models: ScientificModelLedger | None,
) -> CompetingTheoryLedger:
    """Apply one pure owner-local theory transition."""

    if type(ledger) is not CompetingTheoryLedger:
        raise _fail("ledger", "invalid_type")
    tick = getattr(observation, "tick", None)
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise _fail("observation", "invalid_tick")
    updated = _settle_due_cases(
        ledger, observation, scientific_models=scientific_models
    )
    updated = _derive_new_claims(
        updated,
        previous=previous_scientific_models,
        current=scientific_models,
    )
    updated = _ingest_communications(updated, observation)
    updated = _expire_outbound(updated, tick=tick)
    updated = _choose_stances(updated, tick=tick)
    if scientific_models is not None:
        for base in sorted(
            scientific_models.cases,
            key=lambda row: (row.issued_observation_tick, row.case_id),
        ):
            if base.case_id in updated.issued_base_case_ids:
                continue
            if base.state is not ForecastCaseState.PENDING:
                continue
            if base.issued_observation_tick != tick:
                continue
            updated = _ensure_continuity_claim(updated, base, tick=tick)
            updated = issue_theory_case(updated, base)
    _LOG.debug(
        "competing_theory_transition owner_id=%s tick=%s claim_count=%s "
        "case_count=%s receipt_count=%s stance_count=%s",
        updated.owner_id.value,
        tick,
        len(updated.claims),
        len(updated.cases),
        len(updated.receipts),
        len(updated.stances),
    )
    return updated


def _latest_stance_rows(
    ledger: CompetingTheoryLedger,
) -> tuple[TheoryStance, ...]:
    latest: dict[str, TheoryStance] = {}
    for stance in ledger.stances:
        latest[theory_context_digest(stance.context)] = stance
    return tuple(
        sorted(
            (row for row in latest.values() if row.claim_id is not None),
            key=lambda row: (row.tick, row.claim_id or ""),
            reverse=True,
        )
    )


def _owned_citation(
    ledger: CompetingTheoryLedger, claim_id: str
) -> TheoryCitation | None:
    rows = [
        row
        for row in ledger.citations
        if row.claim_id == claim_id
        and row.kind
        in (
            TheoryCitationKind.OWN_SCORED_CASE,
            TheoryCitationKind.OWN_OBSERVATION,
        )
        and row.root_ref
    ]
    if not rows:
        return None
    return max(rows, key=lambda row: (row.owner_tick, row.citation_id))


def select_theory_speech(
    ledger: CompetingTheoryLedger,
    command: object,
    *,
    recipient_entity_id: str | None = None,
) -> tuple[TheoryMessage, TheoryStance] | None:
    """Choose one support or teaching act for an already addressed command."""

    from world.actions import Talk, Tell

    if type(command) not in (Talk, Tell):
        return None
    if recipient_entity_id is None:
        return None
    for stance in _latest_stance_rows(ledger):
        assert stance.claim_id is not None
        support_sent = any(
            row.recipient_entity_id == recipient_entity_id
            and row.claim_id == stance.claim_id
            and row.stance_revision == stance.stance_id
            and row.act is TheorySpeechAct.SUPPORT
            for row in ledger.outbound
        ) or any(
            row.recipient_entity_id == recipient_entity_id
            and row.claim_id == stance.claim_id
            and row.stance_revision == stance.stance_id
            and row.act is TheorySpeechAct.SUPPORT
            for row in ledger.echoes
        )
        if not support_sent:
            claim = next(
                row for row in ledger.claims if row.claim_id == stance.claim_id
            )
            return message_from_claim(claim, TheorySpeechAct.SUPPORT), stance
        teach_sent = any(
            row.recipient_entity_id == recipient_entity_id
            and row.claim_id == stance.claim_id
            and row.stance_revision == stance.stance_id
            and row.act is TheorySpeechAct.TEACH
            for row in ledger.outbound
        ) or any(
            row.recipient_entity_id == recipient_entity_id
            and row.claim_id == stance.claim_id
            and row.stance_revision == stance.stance_id
            and row.act is TheorySpeechAct.TEACH
            for row in ledger.echoes
        )
        if teach_sent:
            continue
        citation = _owned_citation(ledger, stance.claim_id)
        if citation is None:
            continue
        claim = next(row for row in ledger.claims if row.claim_id == stance.claim_id)
        if citation.polarity not in (
            TheoryCitationPolarity.SUPPORTS,
            TheoryCitationPolarity.CONTRADICTS,
        ):
            continue
        return message_from_claim(
            claim,
            TheorySpeechAct.TEACH,
            cited_root=citation.root_ref,
            cited_polarity=citation.polarity,
        ), stance
    return None


def record_theory_outbound(
    ledger: CompetingTheoryLedger,
    *,
    recipient_entity_id: str,
    stance: TheoryStance,
    act: TheorySpeechAct,
    frame_digest: str,
    send_tick: int,
) -> CompetingTheoryLedger:
    """Record a bounded correlation only for the final submitted frame."""

    if type(ledger) is not CompetingTheoryLedger:
        raise _fail("ledger", "invalid_type")
    if type(stance) is not TheoryStance or stance.claim_id is None:
        raise _fail("stance", "invalid_type")
    if type(act) is not TheorySpeechAct:
        raise _fail("act", "invalid_type")
    correlation = TheoryOutboundCorrelation(
        correlation_id="tho-"
        + _digest(
            ledger.owner_id.value,
            recipient_entity_id,
            stance.claim_id,
            stance.stance_id,
            act.value,
            str(send_tick),
        ),
        recipient_entity_id=recipient_entity_id,
        claim_id=stance.claim_id,
        stance_revision=stance.stance_id,
        act=act,
        send_tick=send_tick,
        frame_digest=frame_digest,
    )
    if any(row.correlation_id == correlation.correlation_id for row in ledger.outbound):
        return ledger
    rows = (*ledger.outbound, correlation)
    if len(rows) > MAX_OUTBOUND:
        rows = rows[-MAX_OUTBOUND:]
    return replace(ledger, outbound=rows)
