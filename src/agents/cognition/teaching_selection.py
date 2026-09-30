"""Optional act choice through the LLM facade.

``teaching.py`` does not import this module. ``CognitiveLoop`` imports it
only when ``TeachingClaimPolicy.allow_provider`` is true.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Final

from agents.cognition.teaching import (
    AdviceAct,
    AdviceDomain,
    TeachingClaimPolicy,
    _fail,
)
from llm import LLMRequest, LLMRequestContext, StructuredOutput, render_prompt
from world.identifiers import require_exact_nonneg_int

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.teaching")
_SCHEMA = "teaching.selection.v1"
_PROMPT = "teaching"
_PROMPT_VERSION = "v1"


class TeachingSelectionOutput(StructuredOutput):
    """One act and domain the deterministic policy already permits."""

    act: str
    domain: str


@dataclass(frozen=True, slots=True)
class TeachingActChoice:
    """A permitted pair. ``fallback_used`` keeps the deterministic act."""

    act: AdviceAct
    domain: AdviceDomain
    fallback_used: bool


def permitted_pairs(model: object) -> tuple[tuple[str, str], ...]:
    """Acts and domains the owner may name. No band and no command."""
    domains = tuple(
        belief.domain.value
        for belief in getattr(model, "beliefs", ())
        if type(getattr(belief, "domain", None)).__name__ == "CompetenceDomain"
    )
    if not domains:
        domains = tuple(item.value for item in AdviceDomain)
    pairs = []
    for act in AdviceAct:
        for domain in domains:
            pairs.append((act.value, domain))
    return tuple(pairs)


async def select_teaching_act(
    model: object,
    policy: object,
    *,
    provider: object | None,
    tick: int,
    observation: object | None = None,
) -> TeachingActChoice:
    """Return one permitted pair, or a fallback marker."""
    _ = observation
    if type(model).__name__ != "CompetenceSelfModel":
        raise _fail("model", "invalid_type")
    if type(policy) is not TeachingClaimPolicy:
        raise _fail("policy", "invalid_type")
    try:
        require_exact_nonneg_int("tick", tick)
    except ValueError as exc:
        raise _fail("tick", "not_positive") from exc
    pairs = permitted_pairs(model)
    placeholder = TeachingActChoice(
        act=AdviceAct.DEMONSTRATE,
        domain=AdviceDomain.FORAGING,
        fallback_used=True,
    )
    if not policy.allow_provider or not pairs:
        return placeholder
    if provider is None or not hasattr(provider, "generate"):
        _LOG.warning("teaching_selection_fallback reason_code=missing_provider")
        return placeholder
    try:
        selected = await _generate(model, pairs, provider=provider, tick=tick)
        act_token, domain_token = _accepted(pairs, selected)
    except Exception as exc:
        reason = "transport"
        message = str(exc)
        if type(exc) is ValueError and message in {
            "foreign_id",
            "schema_invalid",
            "schema_rejected",
        }:
            reason = message
        _LOG.warning("teaching_selection_fallback reason_code=%s", reason)
        return placeholder
    return TeachingActChoice(
        act=AdviceAct(act_token),
        domain=AdviceDomain(domain_token),
        fallback_used=False,
    )


def _accepted(
    pairs: tuple[tuple[str, str], ...], selected: tuple[str, str]
) -> tuple[str, str]:
    if selected not in pairs:
        raise ValueError("foreign_id")
    return selected


async def _generate(
    model: object,
    pairs: tuple[tuple[str, str], ...],
    *,
    provider: object,
    tick: int,
) -> tuple[str, str]:
    payload = {
        "pairs": [{"act": act, "domain": domain} for act, domain in pairs],
    }
    rendered = render_prompt(
        _PROMPT,
        _PROMPT_VERSION,
        {
            "schema_name": _SCHEMA,
            "schema_json": json.dumps(
                TeachingSelectionOutput.model_json_schema(),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "candidate_json": json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            ),
        },
    )
    owner = getattr(getattr(model, "owner_id", None), "value", "")
    result = await provider.generate(  # type: ignore[attr-defined]
        LLMRequest(
            messages=rendered.messages,
            response_model=TeachingSelectionOutput,
            context=LLMRequestContext(
                run_id="teaching",
                agent_id=owner,
                tick=tick,
                llm_request_id=f"teaching-{tick}-{owner}",
            ),
            prompt=rendered.reference,
        )
    )
    output = result.output
    if type(output) is not TeachingSelectionOutput:
        raise ValueError("schema_rejected")
    return output.act, output.domain
