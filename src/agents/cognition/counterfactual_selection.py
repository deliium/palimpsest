"""Optional ranking of already-created counterfactual scenario ids.

This module imports the LLM facade. ``counterfactual.py`` does not. A loop
that leaves the provider off never loads this module.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from agents.cognition.counterfactual import (
    CounterfactualPolicy,
    CounterfactualScenario,
    _confidence_band,
)
from llm import (
    LLMRequest,
    LLMRequestContext,
    LLMRequestOptions,
    StructuredOutput,
    render_prompt,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.counterfactual_selection"
)
_SCHEMA = "counterfactual.selection.v1"
_PROMPT = "counterfactual"
_PROMPT_VERSION = "v1"
_REJECTED = frozenset({"foreign_id", "schema_invalid", "schema_rejected"})


class CounterfactualSelectionOutput(StructuredOutput):
    """Scenario ids only. No probability, outcome atom, or command."""

    selected_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CounterfactualSelectionResult:
    selected_ids: tuple[str, ...]
    fallback_used: bool
    llm_call_count: int
    token_count: int
    reason_code: str


def _payload(scenarios: Sequence[CounterfactualScenario]) -> dict[str, object]:
    return {
        "candidates": [
            {
                "scenario_id": item.scenario_id,
                "direction_code": item.alternative_direction.value,
                "confidence_band": _confidence_band(item.confidence),
            }
            for item in scenarios
        ]
    }


def _accepted(
    candidates: tuple[str, ...], selected: tuple[str, ...]
) -> tuple[str, ...]:
    allowed = set(candidates)
    if len(set(selected)) != len(selected):
        raise ValueError("schema_rejected")
    if any(item not in allowed for item in selected):
        raise ValueError("foreign_id")
    return selected


def _log(
    *,
    owner_id: str,
    tick: int,
    candidate_count: int,
    selected_count: int,
    token_count: int,
    fallback_used: bool,
    reason_code: str,
) -> None:
    _LOG.debug(
        "counterfactual_llm_selection owner_id=%s tick=%s candidate_count=%s "
        "selected_count=%s token_count=%s fallback_used=%s",
        owner_id,
        tick,
        candidate_count,
        selected_count,
        token_count,
        fallback_used,
    )
    if fallback_used:
        _LOG.warning(
            "counterfactual_llm_fallback reason_code=%s",
            reason_code,
        )


async def rank_counterfactual_scenarios(
    scenarios: Sequence[CounterfactualScenario],
    policy: CounterfactualPolicy,
    *,
    provider: object | None,
    owner_id: str,
    tick: int,
) -> CounterfactualSelectionResult:
    """Return a subset of existing ids. Failures keep the deterministic set."""
    if type(policy) is not CounterfactualPolicy:
        raise TypeError("policy must be CounterfactualPolicy")
    candidates = tuple(item.scenario_id for item in scenarios)
    if not policy.allow_provider or not candidates:
        return CounterfactualSelectionResult(candidates, False, 0, 0, "skipped")
    if policy.max_llm_calls < 1:
        _log(
            owner_id=owner_id,
            tick=tick,
            candidate_count=len(candidates),
            selected_count=0,
            token_count=0,
            fallback_used=True,
            reason_code="budget_llm",
        )
        return CounterfactualSelectionResult(candidates, True, 0, 0, "budget_llm")
    if policy.max_tokens < 1:
        _log(
            owner_id=owner_id,
            tick=tick,
            candidate_count=len(candidates),
            selected_count=0,
            token_count=0,
            fallback_used=True,
            reason_code="budget_tokens",
        )
        return CounterfactualSelectionResult(candidates, True, 0, 0, "budget_tokens")
    if provider is None or not hasattr(provider, "generate"):
        _log(
            owner_id=owner_id,
            tick=tick,
            candidate_count=len(candidates),
            selected_count=0,
            token_count=0,
            fallback_used=True,
            reason_code="missing_provider",
        )
        return CounterfactualSelectionResult(
            candidates, True, 0, 0, "missing_provider"
        )
    tokens = policy.max_tokens
    try:
        selected = await _generate(
            scenarios,
            provider=provider,
            owner_id=owner_id,
            tick=tick,
            candidates=candidates,
            output_tokens=tokens,
        )
    except Exception as exc:
        reason = "transport"
        message = str(exc)
        if type(exc) is ValueError and message in _REJECTED:
            reason = "foreign_id" if message == "foreign_id" else "schema_rejected"
        _log(
            owner_id=owner_id,
            tick=tick,
            candidate_count=len(candidates),
            selected_count=0,
            token_count=tokens,
            fallback_used=True,
            reason_code=reason,
        )
        return CounterfactualSelectionResult(candidates, True, 1, tokens, reason)
    _log(
        owner_id=owner_id,
        tick=tick,
        candidate_count=len(candidates),
        selected_count=len(selected),
        token_count=tokens,
        fallback_used=False,
        reason_code="selected",
    )
    return CounterfactualSelectionResult(selected, False, 1, tokens, "selected")


async def _generate(
    scenarios: Sequence[CounterfactualScenario],
    *,
    provider: object,
    owner_id: str,
    tick: int,
    candidates: tuple[str, ...],
    output_tokens: int,
) -> tuple[str, ...]:
    rendered = render_prompt(
        _PROMPT,
        _PROMPT_VERSION,
        {
            "schema_name": _SCHEMA,
            "schema_json": json.dumps(
                CounterfactualSelectionOutput.model_json_schema(),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "candidate_json": json.dumps(
                _payload(scenarios),
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )
    result = await provider.generate(  # type: ignore[attr-defined]
        LLMRequest(
            messages=rendered.messages,
            response_model=CounterfactualSelectionOutput,
            context=LLMRequestContext(
                run_id="counterfactual",
                agent_id=owner_id,
                tick=tick,
                llm_request_id=f"counterfactual-{tick}-{owner_id}",
                component="counterfactual",
            ),
            prompt=rendered.reference,
            options=LLMRequestOptions(max_output_tokens=output_tokens),
        )
    )
    output = result.output
    if type(output) is not CounterfactualSelectionOutput:
        raise ValueError("schema_rejected")
    if hasattr(output, "probability"):
        raise ValueError("schema_rejected")
    return _accepted(candidates, output.selected_ids)
