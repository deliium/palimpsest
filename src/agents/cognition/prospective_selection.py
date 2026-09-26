"""Optional ranking of already-created prospective transition ids.

This module imports the LLM facade. The rollout module does not. A loop
that leaves the provider off never loads this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from agents.cognition.prospective import (
    ProspectivePolicy,
    ProspectiveRollout,
    confidence_band,
    log_prospective_llm_selection,
)
from llm import (
    LLMRequest,
    LLMRequestContext,
    LLMRequestOptions,
    StructuredOutput,
    render_prompt,
)

_SCHEMA = "prospective.selection.v1"
_PROMPT = "prospective"
_PROMPT_VERSION = "v1"


class ProspectiveSelectionOutput(StructuredOutput):
    """Transition ids only. No probability and no situation atom."""

    selected_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProspectiveSelectionResult:
    selected_ids: tuple[str, ...]
    fallback_used: bool
    llm_call_count: int
    token_count: int
    reason_code: str


def _candidate_payload(rollout: ProspectiveRollout) -> dict[str, object]:
    rows = []
    for item in rollout.transitions:
        if item.prune_reason is not None:
            continue
        rows.append(
            {
                "transition_id": item.transition_id,
                "depth": item.depth,
                "direction_code": item.direction.value,
                "confidence_band": confidence_band(item.uncertainty.epistemic),
            }
        )
    return {"candidates": rows}


def _accepted_selection(
    candidates: tuple[str, ...], selected: tuple[str, ...]
) -> tuple[str, ...]:
    allowed = set(candidates)
    if len(set(selected)) != len(selected):
        raise ValueError("schema_invalid")
    if any(item not in allowed for item in selected):
        raise ValueError("foreign_id")
    return selected


async def rank_prospective_transitions(
    rollout: ProspectiveRollout,
    policy: ProspectivePolicy,
    *,
    provider: object | None,
    tick: int,
    output_tokens: int,
) -> ProspectiveSelectionResult:
    """Rank existing transition ids. Failures keep the deterministic order."""
    if type(rollout) is not ProspectiveRollout:
        raise TypeError("rollout must be ProspectiveRollout")
    if type(policy) is not ProspectivePolicy:
        raise TypeError("policy must be ProspectivePolicy")
    candidates = tuple(
        item.transition_id
        for item in rollout.transitions
        if item.prune_reason is None
    )
    if not policy.allow_provider or not candidates:
        return ProspectiveSelectionResult((), False, 0, 0, "skipped")
    if provider is None or not hasattr(provider, "generate"):
        log_prospective_llm_selection(
            owner_id=rollout.owner_id.value,
            tick=tick,
            candidate_count=len(candidates),
            selected_count=0,
            token_count=0,
            fallback_used=True,
            reason_code="missing_provider",
        )
        return ProspectiveSelectionResult((), True, 0, 0, "missing_provider")
    try:
        selected = await _generate(
            rollout,
            policy,
            provider=provider,
            tick=tick,
            candidates=candidates,
            output_tokens=output_tokens,
        )
        accepted = _accepted_selection(candidates, selected)
    except Exception as exc:
        reason = "transport"
        message = str(exc)
        if type(exc) is ValueError and message in {
            "foreign_id",
            "schema_invalid",
            "schema_rejected",
        }:
            reason = "schema_rejected" if message != "foreign_id" else "foreign_id"
        log_prospective_llm_selection(
            owner_id=rollout.owner_id.value,
            tick=tick,
            candidate_count=len(candidates),
            selected_count=0,
            token_count=output_tokens,
            fallback_used=True,
            reason_code=reason,
        )
        return ProspectiveSelectionResult((), True, 1, output_tokens, reason)
    log_prospective_llm_selection(
        owner_id=rollout.owner_id.value,
        tick=tick,
        candidate_count=len(candidates),
        selected_count=len(accepted),
        token_count=output_tokens,
        fallback_used=False,
        reason_code="selected",
    )
    return ProspectiveSelectionResult(accepted, False, 1, output_tokens, "selected")


async def _generate(
    rollout: ProspectiveRollout,
    policy: ProspectivePolicy,
    *,
    provider: object,
    tick: int,
    candidates: tuple[str, ...],
    output_tokens: int,
) -> tuple[str, ...]:
    _ = policy
    rendered = render_prompt(
        _PROMPT,
        _PROMPT_VERSION,
        {
            "schema_name": _SCHEMA,
            "schema_json": json.dumps(
                ProspectiveSelectionOutput.model_json_schema(),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "candidate_json": json.dumps(
                _candidate_payload(rollout),
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )
    result = await provider.generate(  # type: ignore[attr-defined]
        LLMRequest(
            messages=rendered.messages,
            response_model=ProspectiveSelectionOutput,
            context=LLMRequestContext(
                run_id="prospective",
                agent_id=rollout.owner_id.value,
                tick=tick,
                llm_request_id=f"prospective-{tick}-{rollout.owner_id.value}",
            ),
            prompt=rendered.reference,
            options=LLMRequestOptions(max_output_tokens=output_tokens),
        )
    )
    output = result.output
    if type(output) is not ProspectiveSelectionOutput:
        raise ValueError("schema_rejected")
    return _accepted_selection(candidates, output.selected_ids)
