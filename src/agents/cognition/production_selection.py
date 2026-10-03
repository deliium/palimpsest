"""Optional recipe-id selection through the LLM facade.

``production.py`` does not import this module. The loop imports it only when
``allow_provider`` is true. The provider may return only a recipe id already
supported on the owner's set.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Final

from agents.cognition.production import RecipeBeliefSet
from llm import LLMRequest, LLMRequestContext, StructuredOutput, render_prompt
from world.identifiers import RecipeId, require_exact_nonneg_int

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.production")
_SCHEMA = "production.selection.v1"
_PROMPT = "production"
_PROMPT_VERSION = "v1"


class ProductionSelectionOutput(StructuredOutput):
    """One recipe id copied from the supported candidate list."""

    recipe_id: str


@dataclass(frozen=True, slots=True)
class ProductionSelection:
    """Chosen id, or a deterministic fallback when the provider is unusable."""

    recipe_id: RecipeId | None
    fallback_used: bool


def _candidates(beliefs: RecipeBeliefSet) -> tuple[str, ...]:
    return tuple(
        belief.recipe_id.value for belief in beliefs.beliefs if belief.supported
    )


async def select_production_recipe(
    beliefs: RecipeBeliefSet,
    *,
    allow_provider: bool,
    provider: object | None,
    tick: int,
) -> ProductionSelection:
    """Return one supported recipe id, or fall back to the deterministic choice."""
    if type(beliefs) is not RecipeBeliefSet:
        raise TypeError("beliefs must be RecipeBeliefSet")
    if type(allow_provider) is not bool:
        raise TypeError("allow_provider must be bool")
    try:
        require_exact_nonneg_int("tick", tick)
    except ValueError as exc:
        raise TypeError("tick must be a non-negative int") from exc
    candidates = _candidates(beliefs)
    if not allow_provider or not candidates:
        return ProductionSelection(recipe_id=None, fallback_used=False)
    _LOG.debug("production_llm_start candidate_count=%s", len(candidates))
    if provider is None or not hasattr(provider, "generate"):
        _reject("missing_provider", len(candidates))
        return ProductionSelection(recipe_id=None, fallback_used=True)
    try:
        selected = await _generate(beliefs, provider=provider, tick=tick)
        if selected not in candidates:
            raise ValueError("foreign_id")
        recipe_id = RecipeId(selected)
    except Exception as exc:
        reason = "transport"
        message = str(exc)
        if type(exc) is ValueError and message in {
            "foreign_id",
            "schema_invalid",
            "schema_rejected",
        }:
            reason = message
        _reject(reason, len(candidates))
        return ProductionSelection(recipe_id=None, fallback_used=True)
    _LOG.debug(
        "production_llm_complete selected_count=%s fallback_used=%s",
        1,
        False,
    )
    return ProductionSelection(recipe_id=recipe_id, fallback_used=False)


def _reject(reason: str, candidate_count: int) -> None:
    _LOG.info(
        "production_llm_rejected reason_code=%s candidate_count=%s",
        reason,
        candidate_count,
    )


async def _generate(
    beliefs: RecipeBeliefSet, *, provider: object, tick: int
) -> str:
    rendered = render_prompt(
        _PROMPT,
        _PROMPT_VERSION,
        {
            "schema_name": _SCHEMA,
            "schema_json": json.dumps(
                ProductionSelectionOutput.model_json_schema(),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "candidate_json": json.dumps(
                {"recipe_ids": list(_candidates(beliefs))},
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )
    result = await provider.generate(  # type: ignore[attr-defined]
        LLMRequest(
            messages=rendered.messages,
            response_model=ProductionSelectionOutput,
            context=LLMRequestContext(
                run_id="production",
                agent_id=beliefs.owner_id.value,
                tick=tick,
                llm_request_id=f"production-{tick}-{beliefs.owner_id.value}",
                component="production",
            ),
            prompt=rendered.reference,
        )
    )
    output = result.output
    if type(output) is not ProductionSelectionOutput:
        raise ValueError("schema_rejected")
    if type(output.recipe_id) is not str or not output.recipe_id:
        raise ValueError("schema_invalid")
    return output.recipe_id
