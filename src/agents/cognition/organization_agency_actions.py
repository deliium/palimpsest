"""Pure classifiers for collective-agency implementation evidence.

These helpers compare an owner's decision belief with what the owner actually
observed. They classify, match, and filter only: no helper returns, constructs,
submits, or resolves an ``AgentCommand``, and no helper moves a resource or
executes a physical action.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Final

from agents.cognition.organization_agency import (
    ORGANIZATION_AGENCY_CONTRARY_EFFECTS,
    ORGANIZATION_AGENCY_DOMAIN_EFFECTS,
    ORGANIZATION_AGENCY_EFFECTS,
    OrganizationAgencyEffect,
    OrganizationAgencyImplementationMode,
    organization_agency_ref,
)
from agents.cognition.organization_operations import OrganizationOperationDomain

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.organization_agency_actions"
)

_EVIDENCE_ROLES: Final[frozenset[str]] = frozenset({"actor", "witness"})

_ANCHOR_FACTS_BY_EFFECT: Final[Mapping[OrganizationAgencyEffect, tuple[str, ...]]] = {
    OrganizationAgencyEffect.GIVE: ("give_item_ids", "target_id"),
    OrganizationAgencyEffect.ITEM_STORED: ("target_id", "repository_id"),
    OrganizationAgencyEffect.REPOSITORY_MEMBER_DEPOSITED: (
        "repository_id",
        "target_id",
    ),
    OrganizationAgencyEffect.REPOSITORY_MEMBER_RETRIEVED: (
        "repository_id",
        "target_id",
    ),
    OrganizationAgencyEffect.REPOSITORY_ESTABLISHED: ("repository_id",),
    OrganizationAgencyEffect.REPOSITORY_MAINTAINED: ("repository_id",),
    OrganizationAgencyEffect.ARTIFACT_CREATED: ("artifact_id", "target_id"),
    OrganizationAgencyEffect.ARTIFACT_MODIFIED: ("artifact_id", "target_id"),
    OrganizationAgencyEffect.ARTIFACT_DESTROYED: ("artifact_id", "target_id"),
    OrganizationAgencyEffect.PROJECT_CONTRIBUTED: ("project_id",),
    OrganizationAgencyEffect.PUBLIC_GOOD_MAINTAINED: ("public_good_id", "project_id"),
    OrganizationAgencyEffect.PUBLIC_GOOD_OPPOSED: ("public_good_id", "project_id"),
    OrganizationAgencyEffect.PUBLIC_GOOD_BENEFIT: ("public_good_id", "project_id"),
    OrganizationAgencyEffect.MOVE: (),
    OrganizationAgencyEffect.HELP: (),
    OrganizationAgencyEffect.FEED: (),
    OrganizationAgencyEffect.TRANSPORT: (),
    OrganizationAgencyEffect.COMMITMENT_DECLARED: (),
    OrganizationAgencyEffect.EXCHANGE_COMPLETED: (
        "give_item_ids",
        "take_item_ids",
    ),
}


def organization_agency_effect_for_kind(
    kind: object,
) -> OrganizationAgencyEffect | None:
    """Map one real observed kind to a closed agency effect, or ``None``."""

    if type(kind) is not str or kind not in ORGANIZATION_AGENCY_EFFECTS:
        return None
    return OrganizationAgencyEffect(kind)


def organization_agency_domain_allows(domain: object, effect: object) -> bool:
    """Return whether a domain admits an expected effect."""

    if type(domain) is not OrganizationOperationDomain:
        return False
    if type(effect) is not OrganizationAgencyEffect:
        return False
    return effect.value in ORGANIZATION_AGENCY_DOMAIN_EFFECTS[domain]


def organization_agency_implementation_mode(
    effect: object,
) -> OrganizationAgencyImplementationMode:
    """Classify a proposal effect as physical or testimonial."""

    if type(effect) is not OrganizationAgencyEffect:
        raise TypeError("effect must be OrganizationAgencyEffect")
    if effect is OrganizationAgencyEffect.NONE:
        return OrganizationAgencyImplementationMode.TESTIMONIAL
    return OrganizationAgencyImplementationMode.PHYSICAL


def organization_agency_actor_value(occurrence: object) -> str | None:
    """Return the normalized actor value for one observed occurrence."""

    actor = getattr(occurrence, "actor_id", None)
    value = getattr(actor, "value", None)
    if value is None:
        return None
    return str(value).removeprefix("body-")


def organization_agency_occurrence_eligible(occurrence: object) -> bool:
    """Only actor/witness rows with a successful or role-visible effect count."""

    role = getattr(occurrence, "audience_role", None)
    if role not in _EVIDENCE_ROLES:
        return False
    return True


def organization_agency_occurrence_target_values(
    occurrence: object,
) -> tuple[str, ...]:
    """Extract effect-specific anchor values from one observed occurrence."""

    kind = getattr(occurrence, "kind", None)
    effect = organization_agency_effect_for_kind(kind)
    if effect is None:
        return ()
    values: list[str] = []
    facts = getattr(occurrence, "public_facts", None)
    facts_mapping: Mapping[str, object] = facts if isinstance(facts, Mapping) else {}
    for key in _ANCHOR_FACTS_BY_EFFECT.get(effect, ()):
        raw = facts_mapping.get(key)
        if isinstance(raw, (tuple, list)):
            values.extend(str(item) for item in raw)
        elif raw is not None:
            values.append(str(raw))
    for attribute in ("destination_id", "other_entity_id", "target_id"):
        raw = getattr(occurrence, attribute, None)
        value = getattr(raw, "value", None)
        if value is not None:
            values.append(str(value))
    return tuple(dict.fromkeys(values))


def organization_agency_occurrence_matches(
    decision: object, occurrence: object
) -> bool:
    """Return whether one occurrence plausibly implements one decision."""

    from agents.cognition.organization_agency import (
        OrganizationCollectiveDecision,
    )

    if type(decision) is not OrganizationCollectiveDecision:
        raise TypeError("decision must be OrganizationCollectiveDecision")
    if not organization_agency_occurrence_eligible(occurrence):
        return False
    if organization_agency_effect_for_kind(getattr(occurrence, "kind", None)) is not (
        decision.effect
    ):
        return False
    if decision.target_kind in ("none", "unknown"):
        return True
    if decision.target_ref is None:
        return False
    for value in organization_agency_occurrence_target_values(occurrence):
        if organization_agency_ref(value, namespace="target") == decision.target_ref:
            return True
    return False


def organization_agency_contrary_effect(
    kind: object, public_facts: object = None
) -> bool:
    """Classify one observed kind as a closed contrary effect."""

    if kind == "repository_maintained":
        facts = public_facts if isinstance(public_facts, Mapping) else {}
        return facts.get("mode") == "destroy"
    if type(kind) is not str or kind not in ORGANIZATION_AGENCY_CONTRARY_EFFECTS:
        return False
    return True


def organization_agency_report_matches(actor_value: str, communication: object) -> bool:
    """Return whether a delivered communication is an explicit actor report."""

    speaker = getattr(communication, "speaker_id", None)
    value = getattr(speaker, "value", None)
    if value is None or str(value).removeprefix("body-") != actor_value:
        return False
    utterance = getattr(communication, "utterance", None)
    content = getattr(utterance, "content", None)
    relations = () if content is None else tuple(content.relations)
    return bool(relations)


__all__ = [
    "organization_agency_actor_value",
    "organization_agency_contrary_effect",
    "organization_agency_domain_allows",
    "organization_agency_effect_for_kind",
    "organization_agency_implementation_mode",
    "organization_agency_occurrence_eligible",
    "organization_agency_occurrence_matches",
    "organization_agency_occurrence_target_values",
    "organization_agency_report_matches",
]
