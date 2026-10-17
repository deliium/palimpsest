"""Explicit trusted research-composition facade for cognition contracts.

Experiments configure ordinary runner policies or evaluate detached diagnostic
inputs here. This facade never supplies objective state to running agents.
"""

from agents.cognition.architectures import (
    ARCHITECTURES,
    ArchitectureDefinition,
    ArchitectureModeSnapshot,
    architecture_definition_digest,
    get_architecture,
    validate_architecture_compatibility,
)
from agents.cognition.budget import high_cost_budget_limits, low_cost_budget_limits
from agents.cognition.configuration import CognitionTerritorialClaimMode
from agents.cognition.models import (
    ActionDirection,
    CounterpartBinding,
    OwnerSafeSocialIdentity,
)
from agents.cognition.reflection import ReflectionAudit
from agents.cognition.territorial import (
    TERRITORIAL_CLAIM_POLICY_VERSION,
    ClaimChannel,
    ClaimTargetKind,
    TerritorialClaim,
    TerritorialClaimLedger,
    TerritorialEvidenceItem,
    apply_territorial_update,
    default_territorial_claim_policy,
    territorial_claim_id,
    territorial_respect_penalties,
    territorial_wait_replacement,
)

__all__ = [
    "ARCHITECTURES",
    "TERRITORIAL_CLAIM_POLICY_VERSION",
    "ActionDirection",
    "ArchitectureDefinition",
    "ArchitectureModeSnapshot",
    "ClaimChannel",
    "ClaimTargetKind",
    "CognitionTerritorialClaimMode",
    "CounterpartBinding",
    "OwnerSafeSocialIdentity",
    "ReflectionAudit",
    "TerritorialClaim",
    "TerritorialClaimLedger",
    "TerritorialEvidenceItem",
    "apply_territorial_update",
    "architecture_definition_digest",
    "default_territorial_claim_policy",
    "get_architecture",
    "high_cost_budget_limits",
    "low_cost_budget_limits",
    "territorial_claim_id",
    "territorial_respect_penalties",
    "territorial_wait_replacement",
    "validate_architecture_compatibility",
]
