"""Closed detached-analysis vocabulary for inter-society relations.

V4-15 deepens the analysis-only ``macro_society_identity`` context. It adds no
V4 capability flag, no new context, and does not change
``V4_CONTEXT_MAP_VERSION`` or the fourteen-context registry. Society-pair
panels are researcher labels over ordered ``msoc-`` endpoints; they never feed
cognition, prompts, memory, world state, stop selectors, Observation, or Godot
physics. No authoritative civilization relationship score exists.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from enum import StrEnum
from typing import Final

from analysis.diplomacy_contract import DIPLOMACY_FORBIDDEN_RESULT_FIELDS
from analysis.macro_society_contract import require_macro_society_id
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "CULTURAL_SIMILARITY_ALLOWED_VALUE_KEYS",
    "INTER_SOCIETY_DOMAIN_KEYS",
    "INTER_SOCIETY_RELATIONS_ANALYSIS_POLICY_VERSION",
    "INTER_SOCIETY_RELATIONS_ERROR_CODES",
    "INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS",
    "INTER_SOCIETY_RELATIONS_ID_HEX_CHARS",
    "INTER_SOCIETY_RELATIONS_ID_NAMESPACE",
    "INTER_SOCIETY_RELATIONS_ID_PREFIX",
    "INTER_SOCIETY_RELATION_WINDOW_TICKS",
    "InterSocietyAvailability",
    "InterSocietyDomain",
    "InterSocietyLayer",
    "InterSocietyPairStatus",
    "InterSocietyRelationsError",
    "assert_no_forbidden_fields",
    "derive_inter_society_pair_id",
    "ordered_society_pair",
    "require_inter_society_pair_id",
    "validate_cultural_similarity_keys",
]

INTER_SOCIETY_RELATIONS_ANALYSIS_POLICY_VERSION: Final[str] = (
    "inter-society-relations-analysis.v1"
)
INTER_SOCIETY_RELATIONS_ID_NAMESPACE: Final[str] = "inter-society-relations-v1"
INTER_SOCIETY_RELATIONS_ID_PREFIX: Final[str] = "isr-"
INTER_SOCIETY_RELATIONS_ID_HEX_CHARS: Final[int] = 16
# Matches CIVILIZATION_FLOW_WINDOW_TICKS (civilization_overlays.py).
INTER_SOCIETY_RELATION_WINDOW_TICKS: Final[int] = 32

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.inter_society_relations.contract"
)

_ISR_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{INTER_SOCIETY_RELATIONS_ID_PREFIX}"
    rf"[0-9a-f]{{{INTER_SOCIETY_RELATIONS_ID_HEX_CHARS}}}$"
)


class InterSocietyDomain(StrEnum):
    """Closed eight-domain vocabulary for society-pair evidence panels."""

    COOPERATION = "cooperation"
    HOSTILITY = "hostility"
    EXCHANGE = "exchange"
    MIGRATION = "migration"
    TRUST_PROXY = "trust_proxy"
    AGREEMENT = "agreement"
    CONFLICT = "conflict"
    CULTURAL_SIMILARITY = "cultural_similarity"


INTER_SOCIETY_DOMAIN_KEYS: Final[frozenset[str]] = frozenset(
    domain.value for domain in InterSocietyDomain
)


class InterSocietyAvailability(StrEnum):
    """Per-domain coverage for one pair in one window."""

    PRESENT = "present"
    PARTIAL = "partial"
    ABSENT = "absent"


class InterSocietyPairStatus(StrEnum):
    """Analytical status of one ``isr-`` candidate."""

    OBSERVED = "observed"
    PARTIAL = "partial"
    EMPTY = "empty"


class InterSocietyLayer(StrEnum):
    """Three strictly separated representations."""

    OBJECTIVE_EVIDENCE = "objective_evidence"
    ANALYTICAL_PAIR = "analytical_pair"
    COMPARISON_VIEW = "comparison_view"


INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    set(DIPLOMACY_FORBIDDEN_RESULT_FIELDS)
    | {
        "civilization_relationship_score",
        "alliance_score",
        "enmity_score",
        "relationship_score",
        "trust_score",
        "society_score",
        "pair_score",
        "relation_rank",
        "friendship",
        "enmity",
        "alliance",
    }
)

# Cultural similarity may only emit counts, Jaccard, mean pairwise similarity
# keys, and availability — never a field named ``score`` or ``*_score``.
CULTURAL_SIMILARITY_ALLOWED_VALUE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "overlap_count",
        "union_count",
        "jaccard",
        "trait_mean_pairwise_similarity",
        "semantic_mean_pairwise_similarity",
        "naming_mean_pairwise_similarity",
        "availability",
    }
)

INTER_SOCIETY_RELATIONS_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "inter_society_relations_invalid_id",
        "inter_society_relations_invalid_pair",
        "inter_society_relations_invalid_domain",
        "inter_society_relations_forbidden_result_field",
        "inter_society_relations_cultural_key_rejected",
        "inter_society_relations_layer_leak",
        "inter_society_relations_invalid_layer_view",
        "inter_society_relations_duplicate_pair",
        "inter_society_relations_analysis_invalid_input",
        "inter_society_relations_metric_input_missing",
        "inter_society_relations_comparison_invalid",
    }
)


class InterSocietyRelationsError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "inter_society_relations_analysis_invalid_input"
        return str(self.args[0])


def ordered_society_pair(society_a: str, society_b: str) -> tuple[str, str]:
    """Return a canonically ordered (``a < b``) ``msoc-`` pair."""
    left = require_macro_society_id(society_a)
    right = require_macro_society_id(society_b)
    if left == right:
        _LOG.debug(
            "inter_society_relations_contract_rejected "
            "reason_code=inter_society_relations_invalid_pair"
        )
        raise InterSocietyRelationsError("inter_society_relations_invalid_pair")
    return (left, right) if left < right else (right, left)


def derive_inter_society_pair_id(
    *,
    window_tick: int,
    society_a: str,
    society_b: str,
    domain_signature: tuple[str, ...] = (),
) -> str:
    """Content-addressed ``isr-`` id over window, ordered societies, domains."""
    tick = require_exact_nonneg_int("window_tick", window_tick)
    left, right = ordered_society_pair(society_a, society_b)
    domains: list[str] = []
    for raw in domain_signature:
        key = require_stable_id("domain_signature", raw)
        if key not in INTER_SOCIETY_DOMAIN_KEYS:
            _LOG.debug(
                "inter_society_relations_contract_rejected "
                "reason_code=inter_society_relations_invalid_domain"
            )
            raise InterSocietyRelationsError("inter_society_relations_invalid_domain")
        domains.append(key)
    domains = sorted(set(domains))
    payload = {
        "namespace": INTER_SOCIETY_RELATIONS_ID_NAMESPACE,
        "window_tick": tick,
        "society_a": left,
        "society_b": right,
        "domain_signature": domains,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return (
        f"{INTER_SOCIETY_RELATIONS_ID_PREFIX}"
        f"{digest[:INTER_SOCIETY_RELATIONS_ID_HEX_CHARS]}"
    )


def require_inter_society_pair_id(value: str) -> str:
    """Validate an exact ``isr-`` plus 16 lowercase hex characters id."""
    if not isinstance(value, str) or not _ISR_ID_PATTERN.match(value):
        _LOG.debug(
            "inter_society_relations_contract_rejected "
            "reason_code=inter_society_relations_invalid_id"
        )
        raise InterSocietyRelationsError("inter_society_relations_invalid_id")
    return value


def assert_no_forbidden_fields(mapping: object, *, path: str = "row") -> None:
    """Fail closed when a forbid-listed key appears on an analysis mapping."""
    if not isinstance(mapping, dict):
        return
    for key, value in mapping.items():
        if not isinstance(key, str):
            continue
        lowered = key.lower()
        if (
            lowered in INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS
            or lowered.endswith("_score")
        ):
            _LOG.debug(
                "inter_society_relations_contract_rejected "
                "reason_code=inter_society_relations_forbidden_result_field "
                "path=%s",
                path,
            )
            raise InterSocietyRelationsError(
                "inter_society_relations_forbidden_result_field"
            )
        if isinstance(value, dict):
            assert_no_forbidden_fields(value, path=f"{path}.{key}")


def validate_cultural_similarity_keys(mapping: object) -> None:
    """Allow only the closed cultural-similarity value key set."""
    if not isinstance(mapping, dict):
        raise InterSocietyRelationsError(
            "inter_society_relations_cultural_key_rejected"
        )
    for key in mapping:
        if not isinstance(key, str):
            raise InterSocietyRelationsError(
                "inter_society_relations_cultural_key_rejected"
            )
        if key not in CULTURAL_SIMILARITY_ALLOWED_VALUE_KEYS:
            if key == "score" or key.endswith("_score"):
                _LOG.debug(
                    "inter_society_relations_contract_rejected "
                    "reason_code=inter_society_relations_forbidden_result_field"
                )
                raise InterSocietyRelationsError(
                    "inter_society_relations_forbidden_result_field"
                )
            _LOG.debug(
                "inter_society_relations_contract_rejected "
                "reason_code=inter_society_relations_cultural_key_rejected"
            )
            raise InterSocietyRelationsError(
                "inter_society_relations_cultural_key_rejected"
            )
