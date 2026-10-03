"""Optional re-ranking of mind hypothesis ids through the LLM facade.

The updater module does not import this one. Default policy never calls it.
"""

from __future__ import annotations

import json
import logging
from typing import Final

from agents.cognition.theory_of_mind import TheoryOfMind, TheoryOfMindPolicy, _fail
from llm import LLMRequest, LLMRequestContext, StructuredOutput, render_prompt
from world.identifiers import require_exact_nonneg_int

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.theory_of_mind")
_SCHEMA = "theory_of_mind.selection.v1"
_PROMPT = "theory_of_mind"
_PROMPT_VERSION = "v1"


class TheoryOfMindSelectionOutput(StructuredOutput):
    """Hypothesis ids only. No probability and no atom field."""

    selected_ids: tuple[str, ...]


def _band(confidence: float, *, threshold: float) -> str:
    if confidence >= threshold:
        return "high"
    return "low"


def _candidate_payload(
    model: TheoryOfMind, policy: TheoryOfMindPolicy
) -> dict[str, object]:
    rows = []
    for item in model.hypotheses:
        rows.append(
            {
                "hypothesis_id": item.hypothesis_id,
                "aspect": item.aspect.value,
                "atom_count": len(item.atoms),
                "confidence_band": _band(
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


async def select_theory_of_mind_hypotheses(
    model: TheoryOfMind,
    policy: TheoryOfMindPolicy,
    *,
    provider: object | None,
    tick: int,
) -> TheoryOfMind:
    """Re-rank existing ids. Failures keep confidence order."""
    from dataclasses import replace

    if type(model) is not TheoryOfMind:
        raise _fail("model", "invalid_type")
    if type(policy) is not TheoryOfMindPolicy:
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
        selected = await _generate(model, policy, provider=provider, tick=tick)
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
        "theory_of_mind_llm_selection owner_id=%s tick=%s candidate_count=%s "
        "selected_count=%s fallback_used=%s",
        model.owner_id.value,
        tick,
        len(candidates),
        len(selected),
        False,
    )
    return replace(model, preferred_ids=selected, selection_fallback_used=False)


def _log_fallback(
    model: TheoryOfMind, tick: int, candidate_count: int, reason: str
) -> None:
    _LOG.warning("theory_of_mind_llm_fallback reason_code=%s", reason)
    _LOG.debug(
        "theory_of_mind_llm_selection owner_id=%s tick=%s candidate_count=%s "
        "selected_count=%s fallback_used=%s",
        model.owner_id.value,
        tick,
        candidate_count,
        candidate_count,
        True,
    )


async def _generate(
    model: TheoryOfMind,
    policy: TheoryOfMindPolicy,
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
                TheoryOfMindSelectionOutput.model_json_schema(),
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
            response_model=TheoryOfMindSelectionOutput,
            context=LLMRequestContext(
                run_id="theory-of-mind",
                agent_id=model.owner_id.value,
                tick=tick,
                llm_request_id=f"theory-of-mind-{tick}-{model.owner_id.value}",
                component="theory_of_mind",
            ),
            prompt=rendered.reference,
        )
    )
    output = result.output
    if type(output) is not TheoryOfMindSelectionOutput:
        raise ValueError("schema_rejected")
    return _accepted_selection(
        tuple(item.hypothesis_id for item in model.hypotheses),
        output.selected_ids,
    )
