"""Optional ranking of competence domain tokens through the LLM facade.

``competence.py`` does not import this module. The loop imports it only when
``CompetenceBeliefPolicy.allow_provider`` is true.
"""

from __future__ import annotations

import json
import logging
from typing import Final

from agents.cognition.competence import (
    CompetenceBeliefPolicy,
    CompetenceDomain,
    CompetenceSelfModel,
    _fail,
)
from llm import LLMRequest, LLMRequestContext, StructuredOutput, render_prompt
from world.identifiers import require_exact_nonneg_int

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.competence")
_SCHEMA = "competence.selection.v1"
_PROMPT = "competence"
_PROMPT_VERSION = "v1"


class CompetenceSelectionOutput(StructuredOutput):
    """Domain tokens already on the owner's model. No level and no command."""

    selected_domains: tuple[str, ...]


def _payload(model: CompetenceSelfModel) -> dict[str, object]:
    rows = []
    for belief in model.beliefs:
        rows.append(
            {
                "domain": belief.domain.value,
                "believed_level": belief.believed_level,
            }
        )
    return {"domains": rows}


def _accepted(
    candidates: tuple[str, ...], selected: tuple[str, ...]
) -> tuple[str, ...]:
    allowed = set(candidates)
    if len(set(selected)) != len(selected):
        raise ValueError("schema_invalid")
    if any(item not in allowed for item in selected):
        raise ValueError("foreign_id")
    for token in selected:
        CompetenceDomain(token)
    return selected


async def select_competence_domains(
    model: CompetenceSelfModel,
    policy: CompetenceBeliefPolicy,
    *,
    provider: object | None,
    tick: int,
) -> CompetenceSelfModel:
    """Return a subset of the owner's domain tokens, or the deterministic model."""
    if type(model) is not CompetenceSelfModel:
        raise _fail("model", "invalid_type")
    if type(policy) is not CompetenceBeliefPolicy:
        raise _fail("policy", "invalid_type")
    try:
        require_exact_nonneg_int("tick", tick)
    except ValueError as exc:
        raise _fail("tick", "not_positive") from exc
    candidates = tuple(item.domain.value for item in model.beliefs)
    if not policy.allow_provider or not candidates:
        return model
    if provider is None or not hasattr(provider, "generate"):
        _fallback(model, "missing_provider")
        return _marked(model, preferred=(), fallback=True)
    try:
        selected = await _generate(model, provider=provider, tick=tick)
        checked = _accepted(candidates, selected)
    except Exception as exc:
        reason = "transport"
        message = str(exc)
        if type(exc) is ValueError and message in {
            "foreign_id",
            "schema_invalid",
            "schema_rejected",
        }:
            reason = "schema_rejected" if message != "foreign_id" else "foreign_id"
        _fallback(model, reason)
        return _marked(model, preferred=(), fallback=True)
    _LOG.debug(
        "competence_selection owner_id=%s selected_count=%s fallback_used=%s",
        model.owner_id.value,
        len(checked),
        False,
    )
    return _marked(model, preferred=checked, fallback=False)


def _marked(
    model: CompetenceSelfModel, *, preferred: tuple[str, ...], fallback: bool
) -> CompetenceSelfModel:
    return CompetenceSelfModel(
        owner_id=model.owner_id,
        beliefs=model.beliefs,
        cursors=model.cursors,
        preferred_domains=preferred,
        selection_fallback_used=fallback,
    )


def _fallback(model: CompetenceSelfModel, reason: str) -> None:
    _LOG.warning("competence_selection_fallback reason_code=%s", reason)
    _LOG.debug(
        "competence_selection owner_id=%s selected_count=%s fallback_used=%s",
        model.owner_id.value,
        0,
        True,
    )


async def _generate(
    model: CompetenceSelfModel, *, provider: object, tick: int
) -> tuple[str, ...]:
    rendered = render_prompt(
        _PROMPT,
        _PROMPT_VERSION,
        {
            "schema_name": _SCHEMA,
            "schema_json": json.dumps(
                CompetenceSelectionOutput.model_json_schema(),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "candidate_json": json.dumps(
                _payload(model),
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )
    result = await provider.generate(  # type: ignore[attr-defined]
        LLMRequest(
            messages=rendered.messages,
            response_model=CompetenceSelectionOutput,
            context=LLMRequestContext(
                run_id="competence",
                agent_id=model.owner_id.value,
                tick=tick,
                llm_request_id=f"competence-{tick}-{model.owner_id.value}",
                component="competence",
            ),
            prompt=rendered.reference,
        )
    )
    output = result.output
    if type(output) is not CompetenceSelectionOutput:
        raise ValueError("schema_rejected")
    return output.selected_domains
