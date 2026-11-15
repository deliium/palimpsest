"""Closed detached vocabulary for social-mobility analysis.

The surface measures intergenerational persistence over already-committed
genealogy and outcome evidence. It never assigns a social class, caste, stratum,
rank, merit, desert, or prestige label, and it never feeds cognition, prompts,
memory, world state, observer semantics, or stop selectors.

Stable error codes (``SocialMobilityError.reason_code``):

- ``social_mobility_invalid_input``
- ``social_mobility_invalid_policy``
- ``social_mobility_invalid_window``
- ``social_mobility_invalid_row``
- ``social_mobility_forbidden_key``
- ``social_mobility_layer_leak``
- ``social_mobility_identity_conflict``
- ``social_mobility_unmapped_owner``
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

__all__ = [
    "SOCIAL_MOBILITY_ANALYSIS_LAYER",
    "SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION",
    "SOCIAL_MOBILITY_ANALYSIS_TOKEN_HEX_LEN",
    "SOCIAL_MOBILITY_FORBIDDEN_KEYS",
    "SOCIAL_MOBILITY_LINEAGE_PREFIX",
    "SOCIAL_MOBILITY_OWNER_PREFIX",
    "SOCIAL_MOBILITY_PAIR_PREFIX",
    "SocialMobilityAvailability",
    "SocialMobilityCoverage",
    "SocialMobilityDomain",
    "SocialMobilityError",
    "SocialMobilityIdentityMap",
    "SocialMobilityLayer",
    "SocialMobilityMeasure",
    "SocialMobilityPersistence",
    "assert_social_mobility_layer_separation",
    "build_social_mobility_identity_map",
    "social_mobility_lineage_token",
    "social_mobility_measures_for",
    "social_mobility_owner_token",
    "social_mobility_pair_token",
    "social_mobility_token_hash",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_mobility.contract")

SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION: Final[str] = "social-mobility.v1"
SOCIAL_MOBILITY_OWNER_PREFIX: Final[str] = "smo-"
SOCIAL_MOBILITY_PAIR_PREFIX: Final[str] = "smp-"
SOCIAL_MOBILITY_LINEAGE_PREFIX: Final[str] = "sml-"
SOCIAL_MOBILITY_ANALYSIS_TOKEN_HEX_LEN: Final[int] = 16


class SocialMobilityDomain(StrEnum):
    """Six independent measured domains; never pooled into one index."""

    RESOURCES = "resources"
    SKILLS = "skills"
    SOCIAL_INFLUENCE = "social_influence"
    ORGANIZATION_ROLES = "organization_roles"
    EDUCATIONAL_ACCESS = "educational_access"
    PRODUCTIVE_ASSETS = "productive_assets"


class SocialMobilityMeasure(StrEnum):
    """Closed measured quantity vocabulary; one measure per domain."""

    OBSERVED_RESOURCE_ITEM_COUNT = "observed_resource_item_count"
    KNOWN_TECHNIQUE_COUNT = "known_technique_count"
    INBOUND_COMMUNICATION_PARTNER_COUNT = "inbound_communication_partner_count"
    HELD_ORGANIZATION_ROLE_COUNT = "held_organization_role_count"
    EDUCATIONAL_ACCESS_RECEIPT_COUNT = "educational_access_receipt_count"
    OBSERVED_PRODUCTIVE_ASSET_COUNT = "observed_productive_asset_count"


class SocialMobilityLayer(StrEnum):
    """Strictly separated objective, owner-scoped, and analytical layers."""

    OBJECTIVE_OUTCOME = "objective_outcome"
    OWNER_OUTCOME = "owner_outcome"
    ANALYTICAL_MOBILITY = "analytical_mobility"


SOCIAL_MOBILITY_ANALYSIS_LAYER = SocialMobilityLayer


class SocialMobilityCoverage(StrEnum):
    """Coverage of one bounded evidence or analytical family."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class SocialMobilityAvailability(StrEnum):
    """Closed availability of one statistical row."""

    AVAILABLE = "available"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    UNAVAILABLE = "unavailable"


class SocialMobilityPersistence(StrEnum):
    """Closed persistence vocabulary; never a class or status label."""

    PERSISTENT = "persistent"
    MOBILE = "mobile"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    UNAVAILABLE = "unavailable"


SOCIAL_MOBILITY_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "class",
        "social_class",
        "caste",
        "stratum",
        "stratum_label",
        "elite",
        "underclass",
        "wealth",
        "prestige",
        "merit",
        "desert",
        "mobility_score",
        "social_score",
        "rank",
        "score",
        "status_label",
        "legitimate_heir",
        "inheritance_right",
    }
)

_DOMAIN_MEASURES: Final[dict[SocialMobilityDomain, SocialMobilityMeasure]] = {
    SocialMobilityDomain.RESOURCES: (
        SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT
    ),
    SocialMobilityDomain.SKILLS: SocialMobilityMeasure.KNOWN_TECHNIQUE_COUNT,
    SocialMobilityDomain.SOCIAL_INFLUENCE: (
        SocialMobilityMeasure.INBOUND_COMMUNICATION_PARTNER_COUNT
    ),
    SocialMobilityDomain.ORGANIZATION_ROLES: (
        SocialMobilityMeasure.HELD_ORGANIZATION_ROLE_COUNT
    ),
    SocialMobilityDomain.EDUCATIONAL_ACCESS: (
        SocialMobilityMeasure.EDUCATIONAL_ACCESS_RECEIPT_COUNT
    ),
    SocialMobilityDomain.PRODUCTIVE_ASSETS: (
        SocialMobilityMeasure.OBSERVED_PRODUCTIVE_ASSET_COUNT
    ),
}


class SocialMobilityError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "social_mobility_invalid_input"
        return str(self.args[0])


def social_mobility_measures_for(
    domain: SocialMobilityDomain,
) -> tuple[SocialMobilityMeasure, ...]:
    """Return the single closed measure for ``domain``."""

    if type(domain) is not SocialMobilityDomain:
        raise SocialMobilityError("social_mobility_invalid_input")
    return (_DOMAIN_MEASURES[domain],)


def social_mobility_token_hash(prefix: str, *parts: str) -> str:
    """Length-prefixed content-addressed token helper."""

    material = "\x1f".join(f"{len(part)}:{part}" for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:SOCIAL_MOBILITY_ANALYSIS_TOKEN_HEX_LEN]}"


def social_mobility_owner_token(owner_id: str) -> str:
    """Mint the stable ``smo-`` owner token used by detached rows."""

    if type(owner_id) is not str or not owner_id:
        raise SocialMobilityError("social_mobility_invalid_input")
    return social_mobility_token_hash(SOCIAL_MOBILITY_OWNER_PREFIX, owner_id)


def social_mobility_pair_token(parent_id: str, child_id: str) -> str:
    """Mint the stable ``smp-`` ancestor→descendant pair token."""

    if type(parent_id) is not str or not parent_id:
        raise SocialMobilityError("social_mobility_invalid_input")
    if type(child_id) is not str or not child_id:
        raise SocialMobilityError("social_mobility_invalid_input")
    return social_mobility_token_hash(SOCIAL_MOBILITY_PAIR_PREFIX, parent_id, child_id)


def social_mobility_lineage_token(root_id: str, tail_id: str) -> str:
    """Mint the stable ``sml-`` ancestor-chain token."""

    if type(root_id) is not str or not root_id:
        raise SocialMobilityError("social_mobility_invalid_input")
    if type(tail_id) is not str or not tail_id:
        raise SocialMobilityError("social_mobility_invalid_input")
    return social_mobility_token_hash(SOCIAL_MOBILITY_LINEAGE_PREFIX, root_id, tail_id)


def _layer_group(layer: object) -> str:
    value = layer.value if hasattr(layer, "value") else str(layer)
    if value == SocialMobilityLayer.OBJECTIVE_OUTCOME.value:
        return "objective"
    if value == SocialMobilityLayer.OWNER_OUTCOME.value:
        return "owner"
    if value == SocialMobilityLayer.ANALYTICAL_MOBILITY.value:
        return "analytical"
    raise SocialMobilityError("social_mobility_layer_leak")


def _row_layers(row: object) -> tuple[object, ...]:
    layers = getattr(row, "source_layers", None)
    if layers is not None:
        return tuple(layers)
    layer = getattr(row, "layer", None)
    if layer is None:
        raise SocialMobilityError("social_mobility_layer_leak")
    return (layer,)


def _forbidden_field_names(row: object) -> frozenset[str]:
    names = getattr(type(row), "__dataclass_fields__", None)
    if names is None:
        return frozenset()
    return frozenset(names) & SOCIAL_MOBILITY_FORBIDDEN_KEYS


def assert_social_mobility_layer_separation(
    *row_groups: Iterable[object],
) -> None:
    """Reject a group that mixes layers or carries forbidden vocabulary.

    Each argument is one row group (for example objective outcome rows). A group
    must be homogeneous in its layer; objective, owner-scoped, and analytical
    rows are never mixed inside one group.
    """

    for group in row_groups:
        observed: set[str] = set()
        for row in group:
            if _forbidden_field_names(row):
                _LOG.error("social_mobility_forbidden_key")
                raise SocialMobilityError("social_mobility_forbidden_key")
            try:
                observed.update(_layer_group(layer) for layer in _row_layers(row))
            except (TypeError, SocialMobilityError) as error:
                _LOG.error("social_mobility_layer_leak")
                raise SocialMobilityError("social_mobility_layer_leak") from error
        if len(observed) > 1:
            _LOG.error("social_mobility_layer_leak")
            raise SocialMobilityError("social_mobility_layer_leak")


@dataclass(frozen=True, slots=True)
class SocialMobilityIdentityMap:
    """Immutable agent-id ↔ body-token translation built once per run."""

    forward: Mapping[str, str]
    reverse: Mapping[str, str]

    def token_for_agent(self, agent_id: str) -> str | None:
        if type(agent_id) is not str or not agent_id:
            raise SocialMobilityError("social_mobility_invalid_input")
        return self.forward.get(agent_id)

    def agent_for_token(self, token: str) -> str | None:
        if type(token) is not str or not token:
            raise SocialMobilityError("social_mobility_invalid_input")
        return self.reverse.get(token)

    def require_token(self, agent_id: str) -> str:
        token = self.token_for_agent(agent_id)
        if token is None:
            _LOG.warning("social_mobility_unmapped_owner")
            raise SocialMobilityError("social_mobility_unmapped_owner")
        return token

    @property
    def owner_count(self) -> int:
        return len(self.forward)


class _IdentityBuilder:
    def __init__(self) -> None:
        self.forward: dict[str, str] = {}
        self.reverse: dict[str, str] = {}

    def add(self, agent_id: object, body_id: object) -> None:
        raw_agent = getattr(agent_id, "value", agent_id)
        if type(raw_agent) is not str or not raw_agent:
            raise SocialMobilityError("social_mobility_invalid_input")
        raw_body = getattr(body_id, "value", body_id)
        if type(raw_body) is not str or not raw_body:
            raise SocialMobilityError("social_mobility_invalid_input")
        token = social_mobility_owner_token(raw_body)
        existing = self.forward.get(raw_agent)
        if existing is not None and existing != token:
            _LOG.error("social_mobility_identity_conflict")
            raise SocialMobilityError("social_mobility_identity_conflict")
        reverse_owner = self.reverse.get(token)
        if reverse_owner is not None and reverse_owner != raw_agent:
            _LOG.error("social_mobility_identity_conflict")
            raise SocialMobilityError("social_mobility_identity_conflict")
        self.forward[raw_agent] = token
        self.reverse[token] = raw_agent


def build_social_mobility_identity_map(
    *,
    runner_config: object,
    events: Sequence[object],
) -> SocialMobilityIdentityMap:
    """Build the one identity map from founder config plus committed events."""

    builder = _IdentityBuilder()
    agents = getattr(runner_config, "agents", ()) or ()
    for spec in agents:
        builder.add(spec.agent_id, spec.entity_id)

    for event in events:
        details = getattr(event, "details", None)
        if details is None:
            continue
        kind = getattr(details, "kind", None)
        if kind in {
            "agent_created",
            "agent_entered_world",
            "agent_initialization_recorded",
        }:
            builder.add(
                getattr(details, "agent_id", None),
                getattr(details, "body_id", None),
            )

    _LOG.debug("social_mobility_identity_map_built owners=%d", len(builder.forward))
    return SocialMobilityIdentityMap(
        forward=MappingProxyType(dict(sorted(builder.forward.items()))),
        reverse=MappingProxyType(dict(sorted(builder.reverse.items()))),
    )
