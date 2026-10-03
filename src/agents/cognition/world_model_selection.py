"""Optional re-ranking of causal hypothesis ids through the LLM facade.

This module is not imported by the hypothesis store. Simulation loads the
store for checkpoints and audits. Only a loop that opts in loads this module.
"""

from __future__ import annotations

import json
import logging
from typing import Final

from agents.cognition.world_model import (
    CausalWorldModel,
    WorldModelPolicy,
    _fail,
    confidence_band,
)
from llm import LLMRequest, LLMRequestContext, StructuredOutput, render_prompt
from world.identifiers import require_exact_nonneg_int

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.world_model")
_SCHEMA = "world_model.selection.v1"
_PROMPT = "world_model"
_PROMPT_VERSION = "v1"


class WorldModelSelectionOutput(StructuredOutput):
    """Hypothesis ids only. No probability and no atom field."""

    selected_ids: tuple[str, ...]


def _candidate_payload(
    model: CausalWorldModel, policy: WorldModelPolicy
) -> dict[str, object]:
    rows = []
    for item in model.hypotheses:
        rows.append(
            {
                "hypothesis_id": item.hypothesis_id,
                "outcome": item.outcome.value,
                "atom_count": len(item.atoms),
                "confidence_band": confidence_band(
                    item.confidence, threshold=policy.action_threshold
                ),
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


async def select_world_model_hypotheses(
    model: CausalWorldModel,
    policy: WorldModelPolicy,
    *,
    provider: object | None,
    tick: int,
) -> CausalWorldModel:
    """Re-rank existing ids. Failures keep confidence order."""
    from dataclasses import replace

    if type(model) is not CausalWorldModel:
        raise _fail("model", "invalid_type")
    if type(policy) is not WorldModelPolicy:
        raise _fail("policy", "invalid_type")
    try:
        require_exact_nonneg_int("tick", tick)
    except ValueError as exc:
        raise _fail("tick", "not_positive") from exc
    candidates = tuple(item.hypothesis_id for item in model.hypotheses)
    if not policy.allow_provider or not candidates:
        return model
    if provider is None or not hasattr(provider, "generate"):
        _log_fallback(model, tick, len(candidates), "missing_provider")
        return replace(model, selection_fallback_used=True)
    try:
        selected = await _generate_world_model_selection(
            model, policy, provider=provider, tick=tick
        )
        _accepted_selection(candidates, selected)
    except Exception as exc:
        reason = "transport"
        message = str(exc)
        if type(exc) is ValueError and message in {
            "foreign_id",
            "schema_invalid",
            "schema_rejected",
        }:
            reason = "schema_rejected" if message != "foreign_id" else "foreign_id"
        _log_fallback(model, tick, len(candidates), reason)
        return replace(model, selection_fallback_used=True)
    _LOG.debug(
        "world_model_llm_selection owner_id=%s tick=%s candidate_count=%s "
        "selected_count=%s fallback_used=%s",
        model.owner_id.value,
        tick,
        len(candidates),
        len(selected),
        False,
    )
    return replace(model, preferred_ids=selected, selection_fallback_used=False)


def _log_fallback(
    model: CausalWorldModel, tick: int, candidate_count: int, reason: str
) -> None:
    _LOG.warning("world_model_llm_fallback reason_code=%s", reason)
    _LOG.debug(
        "world_model_llm_selection owner_id=%s tick=%s candidate_count=%s "
        "selected_count=%s fallback_used=%s",
        model.owner_id.value,
        tick,
        candidate_count,
        candidate_count,
        True,
    )


async def _generate_world_model_selection(
    model: CausalWorldModel,
    policy: WorldModelPolicy,
    *,
    provider: object,
    tick: int,
) -> tuple[str, ...]:
    rendered = render_prompt(
        _PROMPT,
        _PROMPT_VERSION,
        {
            "schema_name": _SCHEMA,
            "schema_json": json.dumps(
                WorldModelSelectionOutput.model_json_schema(),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "candidate_json": json.dumps(
                _candidate_payload(model, policy),
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )
    result = await provider.generate(  # type: ignore[attr-defined]
        LLMRequest(
            messages=rendered.messages,
            response_model=WorldModelSelectionOutput,
            context=LLMRequestContext(
                run_id="world-model",
                agent_id=model.owner_id.value,
                tick=tick,
                llm_request_id=f"world-model-{tick}-{model.owner_id.value}",
                component="world_model",
            ),
            prompt=rendered.reference,
        )
    )
    output = result.output
    if type(output) is not WorldModelSelectionOutput:
        raise ValueError("schema_rejected")
    return _accepted_selection(
        tuple(item.hypothesis_id for item in model.hypotheses),
        output.selected_ids,
    )
