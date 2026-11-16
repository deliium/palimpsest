"""Completed-run bridge from owner ledgers to detached hypothesis facts."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.scientific_hypotheses_analysis import (
    ScientificHypothesesAnalysis,
    harvest_scientific_hypotheses_analysis,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesisConditionSlot,
    ScientificHypothesisRevisionReason,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
    mint_claim_token,
    mint_hypothesis_token,
    mint_owner_token,
)
from analysis.scientific_hypotheses_policy import ScientificHypothesesPolicy
from analysis.scientific_hypotheses_rows import (
    HypothesisConditionFact,
    HypothesisFact,
    HypothesisRevisionFact,
    HypothesisTrialFact,
)
from world.events import WorldEvent
from world.experimentation import (
    DiscoveryMode,
    ExperimentOutcomeClass,
)
from world.identifiers import require_stable_id

__all__ = [
    "build_completed_run_scientific_hypotheses_analysis",
    "scientific_hypothesis_facts",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_hypotheses_completed_run"
)


def _predicted(hypothesis: object) -> str:
    value = getattr(hypothesis, "predicted_outcome", None)
    return NONE_TOKEN if value is None else str(value)


def _claim_token(hypothesis: object) -> str:
    return mint_claim_token(
        getattr(getattr(hypothesis, "operator", None), "value", ""),
        str(getattr(hypothesis, "operand_a_id", "")),
        str(getattr(hypothesis, "operand_b_id", None) or NONE_TOKEN),
        getattr(getattr(hypothesis, "process_token", None), "value", ""),
        _predicted(hypothesis),
    )


def _condition_pairs(hypothesis: object) -> tuple[
    tuple[ScientificHypothesisConditionSlot, str], ...
]:
    pairs: list[tuple[ScientificHypothesisConditionSlot, str]] = []
    for condition in getattr(hypothesis, "conditions", ()) or ():
        slot = getattr(getattr(condition, "slot", None), "value", None)
        value = getattr(condition, "value_token", None)
        if type(slot) is not str or type(value) is not str or not value:
            continue
        if slot == "counterpart":
            value = mint_owner_token(value)
        pairs.append((ScientificHypothesisConditionSlot(slot), value))
    return tuple(pairs)


def _matched(hypothesis: object, trial: object) -> bool:
    event_id = getattr(trial, "event_id", None)
    if event_id in (getattr(hypothesis, "evidence_event_ids", ()) or ()):
        return True
    return False


def _revision_fact(
    hypothesis: object, revision: object
) -> HypothesisRevisionFact:
    claim = getattr(revision, "claim", None)
    return HypothesisRevisionFact(
        revision_index=int(getattr(revision, "revision_index", 0)),
        tick=int(getattr(revision, "tick", 0)),
        reason=ScientificHypothesisRevisionReason(
            getattr(getattr(revision, "reason", None), "value", "formulated")
        ),
        claim_token=mint_claim_token(
            getattr(getattr(claim, "operator", None), "value", ""),
            str(getattr(claim, "operand_a_id", "")),
            str(getattr(claim, "operand_b_id", None) or NONE_TOKEN),
            getattr(getattr(claim, "process_token", None), "value", ""),
            (
                NONE_TOKEN
                if getattr(claim, "predicted_outcome", None) is None
                else str(claim.predicted_outcome)
            ),
        ),
        predicted_outcome=(
            NONE_TOKEN
            if getattr(claim, "predicted_outcome", None) is None
            else str(claim.predicted_outcome)
        ),
        condition_pairs=tuple(
            (
                ScientificHypothesisConditionSlot(
                    getattr(getattr(condition, "slot", None), "value", "location")
                ),
                (
                    mint_owner_token(str(getattr(condition, "value_token", "")))
                    if getattr(getattr(condition, "slot", None), "value", None)
                    == "counterpart"
                    else str(getattr(condition, "value_token", ""))
                ),
            )
            for condition in getattr(revision, "conditions", ()) or ()
        ),
        confidence_milli=int(getattr(revision, "confidence_milli", 0) or 0),
        evidence_ref=str(getattr(revision, "evidence_ref", "") or ""),
    )


def _trial_fact(hypothesis: object, trial: object) -> HypothesisTrialFact:
    outcome = ExperimentOutcomeClass(str(getattr(trial, "outcome_class", "success")))
    matched = _matched(hypothesis, trial) and (
        outcome is not ExperimentOutcomeClass.UNEXPECTED
    )
    return HypothesisTrialFact(
        tick=int(getattr(trial, "tick", 0)),
        event_token=f"evt:{getattr(trial, 'event_id', '')}",
        outcome_class=outcome,
        discovery_mode=DiscoveryMode(str(getattr(trial, "discovery_mode", "deliberate"))),  # noqa: E501
        predicted_outcome=_predicted(hypothesis),
        matched=matched,
    )


def _fact(ledger: object, hypothesis: object) -> HypothesisFact:
    owner = getattr(ledger, "owner_id", None)
    owner_value = str(getattr(owner, "value", ""))
    owner_token = mint_owner_token(owner_value)
    claim_token = _claim_token(hypothesis)
    created_tick = int(getattr(hypothesis, "created_tick", 0))
    causal_id = str(getattr(hypothesis, "causal_hypothesis_id", "") or "")
    return HypothesisFact(
        owner_token=owner_token,
        hypothesis_token=mint_hypothesis_token(
            owner_token, claim_token, created_tick
        ),
        claim_token=claim_token,
        causal_hypothesis_token=causal_id or NONE_TOKEN,
        status=ScientificHypothesisStatus(
            getattr(getattr(hypothesis, "status", None), "value", "provisional")
        ),
        predicted_outcome=_predicted(hypothesis),
        confidence_milli=int(getattr(hypothesis, "confidence_milli", 0) or 0),
        created_tick=created_tick,
        active=bool(getattr(hypothesis, "active", True)),
        source_kind=ScientificHypothesisSourceKind(
            getattr(getattr(hypothesis, "source_kind", None), "value", "unknown")
        ),
        source_token=str(getattr(hypothesis, "source_token", "unknown")),
        conditions=tuple(
            HypothesisConditionFact(slot=slot, value_token=value)
            for slot, value in _condition_pairs(hypothesis)
        ),
        revisions=tuple(
            _revision_fact(hypothesis, revision)
            for revision in getattr(hypothesis, "revisions", ()) or ()
        ),
        trials=tuple(
            _trial_fact(hypothesis, trial)
            for trial in getattr(ledger, "trials", ()) or ()
            if getattr(trial, "hypothesis_id", "") == getattr(hypothesis, "hypothesis_id", "")  # noqa: E501
        ),
    )


def scientific_hypothesis_facts(runner_result: object) -> tuple[HypothesisFact, ...]:
    """Map exported owner ledgers to detached facts; no objective rule is read."""

    config = getattr(runner_result, "runner_config", None)
    if config is not None:
        flags = getattr(config, "v4_capability_flags", None)
        if not getattr(flags, "science", False):
            _LOG.warning("scientific_hypotheses_missing_science_flag")
            return ()
    ledgers = tuple(getattr(runner_result, "experiment_ledgers", ()) or ())
    facts: list[HypothesisFact] = []
    for ledger in ledgers:
        for hypothesis in getattr(ledger, "hypotheses", ()) or ():
            try:
                facts.append(_fact(ledger, hypothesis))
            except (TypeError, ValueError):
                _LOG.warning("scientific_hypotheses_ledger_owner_mismatch")
    _LOG.info(
        "scientific_hypotheses_exported owners=%s hypotheses=%s",
        len(ledgers),
        len(facts),
    )
    return tuple(facts)


def build_completed_run_scientific_hypotheses_analysis(
    runner_result: object = None,
    *,
    committed_events: Sequence[WorldEvent],
    run_id: str,
    facts: Sequence[HypothesisFact] | None = None,
    policy: ScientificHypothesesPolicy | None = None,
    window_end: int | None = None,
) -> ScientificHypothesesAnalysis:
    """Build the detached analysis or fail closed without committed events."""

    if isinstance(committed_events, (str, bytes)) or not committed_events:
        _LOG.warning("scientific_hypotheses_missing_events")
        raise ValueError("scientific_hypotheses_requires_events")
    require_stable_id("run_id", run_id)
    derived = (
        tuple(facts)
        if facts is not None
        else scientific_hypothesis_facts(runner_result)
    )
    return harvest_scientific_hypotheses_analysis(
        events=committed_events,
        facts=derived,
        policy=policy,
        window_end=window_end,
    )
