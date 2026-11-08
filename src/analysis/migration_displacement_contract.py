# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Closed detached-analysis vocabulary for migration displacement.

Analysis rows are read-only projections. They never feed cognition, prompts,
memory, world state, stop selectors, or observer semantics. No result is a
truth about why anyone moved, a refugee category, or a composite score. This
module imports no cognition module.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Final

__all__ = [
    "MIGRATION_ALIGNMENTS",
    "MIGRATION_ANALYSIS_POLICY_VERSION",
    "MIGRATION_CANDIDATE_PREFIX",
    "MIGRATION_FORBIDDEN_RESULT_FIELDS",
    "MIGRATION_LAYERS",
    "analysis_migration_candidate_id",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.migration_displacement")

MIGRATION_ANALYSIS_POLICY_VERSION: Final[str] = "migration-displacement-analysis.v1"
MIGRATION_CANDIDATE_PREFIX: Final[str] = "mig-"
MIGRATION_LAYERS: Final[frozenset[str]] = frozenset(
    {
        "objective_movement",
        "subjective_cause",
        "analytical_wave",
        "integration_outcome",
    }
)
MIGRATION_ALIGNMENTS: Final[frozenset[str]] = frozenset(
    {"consistent", "unresolved", "inconsistent", "not_applicable"}
)
MIGRATION_FORBIDDEN_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "refugee",
        "asylum",
        "forced",
        "displaced",
        "threat",
        "hardship",
        "wellbeing",
        "assimilation",
        "integration_score",
        "score",
        "composite",
        "raw_owner_id",
        "raw_entity_id",
        "raw_agent_id",
    }
)

_CANDIDATE_KINDS: Final[frozenset[str]] = frozenset({"wave", "cluster", "outcome"})
_ID_HEX_CHARS: Final[int] = 32


def analysis_migration_candidate_id(kind: str, material: str) -> str:
    """Content-addressed ``mig-`` id with the cognition helper's SHA-256 material."""
    if type(kind) is not str or kind not in _CANDIDATE_KINDS:
        _LOG.error(
            "migration_displacement_analysis_rejected field=kind "
            "reason_code=unknown_candidate_kind"
        )
        raise ValueError("kind: unknown_candidate_kind")
    if type(material) is not str or not material:
        _LOG.error(
            "migration_displacement_analysis_rejected field=material "
            "reason_code=invalid_material"
        )
        raise ValueError("material: invalid_material")
    digest = hashlib.sha256(f"mig|{kind}|{material}".encode()).hexdigest()
    return f"{MIGRATION_CANDIDATE_PREFIX}{digest[:_ID_HEX_CHARS]}"
