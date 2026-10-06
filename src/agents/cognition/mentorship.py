"""Owner-scoped mentorship bonds and taught-content lineage contracts.

Deepens ``generational_population`` with persistent mentor/apprentice bonds
and multi-hop teaching lineages. Never copies peer internal state, society
packs, or analysis feedback into an owner. WorldEngine remains the only
objective authority; this module is subjective.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.mentorship")

MENTORSHIP_POLICY_VERSION: Final[str] = "mentorship-v1"

# Strength quantization (matches cognition unit-interval quantum elsewhere).
_STRENGTH_QUANTUM: Final[float] = 1e-6

# Alice→Bob first hop uses hop_index=0; each re-teach increments by 1.
LINEAGE_FIRST_HOP_INDEX: Final[int] = 0

_FORBIDDEN_CONTENT_KIND_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "culture_pack",
        "encyclopedia",
        "society_memory",
        "inherited_language",
        "mentor",
        "apprentice",
        "elder_teacher",
        "full_self_model_copy",
        "mentor_pack",
        "apprentice_download",
        "lineage_clone",
    }
)

__all__ = [
    "LINEAGE_FIRST_HOP_INDEX",
    "MENTORSHIP_POLICY_VERSION",
    "MentorshipAudit",
    "MentorshipBond",
    "MentorshipBondRole",
    "MentorshipContentKindId",
    "MentorshipLedger",
    "TaughtContentLineageEntry",
    "apply_mentorship_content_kind_adapters",
    "apply_mentorship_from_teaching",
    "collect_mentorship_adapter_keys",
    "decay_mentorship_bonds",
    "empty_mentorship_ledger",
    "form_or_reinforce_mentorship_bond",
    "mentorship_partner_bias_futures",
    "mutate_taught_content_lineage",
    "parse_mentorship_bond_role",
    "parse_mentorship_content_kind",
    "record_taught_content_lineage",
    "require_owner_mentorship",
    "strength_band",
]

class MentorshipContentKindId(StrEnum):
    """Closed content kinds mentorship may transmit via public teaching acts."""

    PRACTICAL_SKILLS = "practical_skills"
    FACTUAL_BELIEFS = "factual_beliefs"
    CAUSAL_HYPOTHESES = "causal_hypotheses"
    VOCABULARY = "vocabulary"
    PRODUCTION_RECIPES = "production_recipes"
    SOCIAL_PRACTICES = "social_practices"
    STORIES = "stories"
    WARNINGS = "warnings"


class MentorshipBondRole(StrEnum):
    """Owner-scoped role toward a partner (not a WorldEngine profession)."""

    MENTOR = "mentor"
    APPRENTICE = "apprentice"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "mentorship_validation_failed field=%s reason_code=%s code=%s",
        field_name,
        code,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _unit_interval(field_name: str, value: object) -> float:
    number = _finite(field_name, value)
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _quantize_unit(value: float) -> float:
    steps = round(value / _STRENGTH_QUANTUM)
    quantized = steps * _STRENGTH_QUANTUM
    if quantized < 0.0:
        quantized = 0.0
    elif quantized > 1.0:
        quantized = 1.0
    return 0.0 if quantized == 0.0 else quantized


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _reject_forbidden_content_kind_alias(raw: str) -> None:
    if raw in _FORBIDDEN_CONTENT_KIND_ALIASES:
        raise _fail("content_kind", "forbidden_content_kind_alias")


def parse_mentorship_content_kind(value: object) -> MentorshipContentKindId:
    """Parse a closed content-kind id; reject society/role/copy aliases."""
    if type(value) is MentorshipContentKindId:
        return value
    if not isinstance(value, str):
        raise _fail("content_kind", "unknown_content_kind")
    _reject_forbidden_content_kind_alias(value)
    try:
        return MentorshipContentKindId(value)
    except ValueError as exc:
        raise _fail("content_kind", "unknown_content_kind") from exc


def parse_mentorship_bond_role(value: object) -> MentorshipBondRole:
    """Parse owner-scoped bond role (mentor|apprentice)."""
    if type(value) is MentorshipBondRole:
        return value
    if not isinstance(value, str):
        raise _fail("role", "unknown_role")
    try:
        return MentorshipBondRole(value)
    except ValueError as exc:
        raise _fail("role", "unknown_role") from exc


def _parse_content_kinds(
    field_name: str, values: object
) -> tuple[MentorshipContentKindId, ...]:
    raw = _require_tuple(field_name, values)
    if not raw:
        raise _fail(field_name, "empty_forbidden")
    checked: list[MentorshipContentKindId] = []
    seen: set[str] = set()
    for item in raw:
        kind = parse_mentorship_content_kind(item)
        if kind.value in seen:
            raise _fail(field_name, "duplicate_content_kind")
        seen.add(kind.value)
        checked.append(kind)
    return tuple(checked)


@dataclass(frozen=True, slots=True)
class MentorshipBond:
    """Directed owner-scoped mentor/apprentice bond toward one partner."""

    partner_agent_id: AgentId
    role: MentorshipBondRole
    content_kinds: tuple[MentorshipContentKindId, ...]
    strength: float
    formed_tick: int
    last_teaching_tick: int
    policy_version: str = MENTORSHIP_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.partner_agent_id) is not AgentId:
            raise _fail("partner_agent_id", "invalid_type")
        role = parse_mentorship_bond_role(self.role)
        object.__setattr__(self, "role", role)
        kinds = _parse_content_kinds("content_kinds", self.content_kinds)
        object.__setattr__(self, "content_kinds", kinds)
        strength = _quantize_unit(_unit_interval("strength", self.strength))
        object.__setattr__(self, "strength", strength)
        formed = require_exact_nonneg_int("formed_tick", self.formed_tick)
        object.__setattr__(self, "formed_tick", formed)
        last = require_exact_nonneg_int("last_teaching_tick", self.last_teaching_tick)
        object.__setattr__(self, "last_teaching_tick", last)
        if self.policy_version != MENTORSHIP_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")


@dataclass(frozen=True, slots=True)
class TaughtContentLineageEntry:
    """One owner-scoped taught-content lineage row (learner is owner).

    ``hop_index`` starts at :data:`LINEAGE_FIRST_HOP_INDEX` (0) for the first
    Alice→Bob hop and increments by one on each re-teach edge.
    """

    teacher_agent_id: AgentId
    learner_agent_id: AgentId
    content_kind: MentorshipContentKindId
    content_key: str
    content_fingerprint: str
    lineage_root_id: str
    hop_index: int
    attempt_count: int
    learning_evidence_count: int
    confidence: float
    mutated: bool
    acquired_tick: int
    last_updated_tick: int
    evidence_refs: tuple[str, ...]
    parent_lineage_id: str | None = None
    lineage_id: str | None = None
    policy_version: str = MENTORSHIP_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.teacher_agent_id) is not AgentId:
            raise _fail("teacher_agent_id", "invalid_type")
        if type(self.learner_agent_id) is not AgentId:
            raise _fail("learner_agent_id", "invalid_type")
        kind = parse_mentorship_content_kind(self.content_kind)
        object.__setattr__(self, "content_kind", kind)
        content_key = require_stable_id("content_key", self.content_key)
        object.__setattr__(self, "content_key", content_key)
        fingerprint = require_stable_id(
            "content_fingerprint", self.content_fingerprint
        )
        object.__setattr__(self, "content_fingerprint", fingerprint)
        root_id = require_stable_id("lineage_root_id", self.lineage_root_id)
        object.__setattr__(self, "lineage_root_id", root_id)
        hop = require_exact_nonneg_int("hop_index", self.hop_index)
        object.__setattr__(self, "hop_index", hop)
        attempts = require_exact_nonneg_int("attempt_count", self.attempt_count)
        object.__setattr__(self, "attempt_count", attempts)
        evidence_count = require_exact_nonneg_int(
            "learning_evidence_count", self.learning_evidence_count
        )
        object.__setattr__(self, "learning_evidence_count", evidence_count)
        object.__setattr__(
            self, "confidence", _unit_interval("confidence", self.confidence)
        )
        if type(self.mutated) is not bool:
            raise _fail("mutated", "invalid_type")
        acquired = require_exact_nonneg_int("acquired_tick", self.acquired_tick)
        object.__setattr__(self, "acquired_tick", acquired)
        updated = require_exact_nonneg_int(
            "last_updated_tick", self.last_updated_tick
        )
        object.__setattr__(self, "last_updated_tick", updated)
        if self.policy_version != MENTORSHIP_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        refs = _require_tuple("evidence_refs", self.evidence_refs)
        checked_refs: list[str] = []
        for item in refs:
            token = require_stable_id("evidence_refs", item)
            if token not in checked_refs:
                checked_refs.append(token)
        if not checked_refs:
            raise _fail("evidence_refs", "provenance_required")
        object.__setattr__(self, "evidence_refs", tuple(checked_refs))
        parent = self.parent_lineage_id
        if parent is not None:
            object.__setattr__(
                self, "parent_lineage_id", require_stable_id("parent_lineage_id", parent)
            )
        lineage_id = self.lineage_id
        if lineage_id is None:
            # Deterministic opaque id from root + hop + content key (no free text).
            lineage_id = (
                f"lin:{root_id}:h{hop}:{kind.value}:{content_key}"
            )
            object.__setattr__(
                self, "lineage_id", require_stable_id("lineage_id", lineage_id)
            )
        else:
            object.__setattr__(
                self, "lineage_id", require_stable_id("lineage_id", lineage_id)
            )


@dataclass(frozen=True, slots=True)
class MentorshipLedger:
    """Private mentorship bonds + taught-content lineage for one owner."""

    owner_id: AgentId
    bonds: tuple[MentorshipBond, ...] = ()
    lineage: tuple[TaughtContentLineageEntry, ...] = ()
    policy_version: str = MENTORSHIP_POLICY_VERSION
    max_bonds: int = 64
    max_lineage_entries: int = 256

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != MENTORSHIP_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        max_bonds = require_exact_nonneg_int("max_bonds", self.max_bonds)
        if max_bonds < 1:
            raise _fail("max_bonds", "out_of_range")
        object.__setattr__(self, "max_bonds", max_bonds)
        max_lineage = require_exact_nonneg_int(
            "max_lineage_entries", self.max_lineage_entries
        )
        if max_lineage < 1:
            raise _fail("max_lineage_entries", "out_of_range")
        object.__setattr__(self, "max_lineage_entries", max_lineage)

        raw_bonds = _require_tuple("bonds", self.bonds)
        checked_bonds: list[MentorshipBond] = []
        seen_partners: set[str] = set()
        for item in raw_bonds:
            if type(item) is not MentorshipBond:
                raise _fail("bonds", "invalid_type")
            partner = item.partner_agent_id.value
            if partner == self.owner_id.value:
                raise _fail("bonds", "self_bond_forbidden")
            # Directed role is part of identity: mentor and apprentice edges
            # toward the same partner may coexist when symmetric policy allows.
            bond_key = f"{partner}:{item.role.value}"
            if bond_key in seen_partners:
                raise _fail("bonds", "duplicate_bond")
            seen_partners.add(bond_key)
            checked_bonds.append(item)
        if len(checked_bonds) > max_bonds:
            raise _fail("bonds", "cap_exceeded")
        object.__setattr__(self, "bonds", tuple(checked_bonds))

        raw_lineage = _require_tuple("lineage", self.lineage)
        checked_lineage: list[TaughtContentLineageEntry] = []
        seen_ids: set[str] = set()
        for item in raw_lineage:
            if type(item) is not TaughtContentLineageEntry:
                raise _fail("lineage", "invalid_type")
            if item.learner_agent_id != self.owner_id:
                raise _fail("lineage", "owner_mismatch")
            assert item.lineage_id is not None
            if item.lineage_id in seen_ids:
                raise _fail("lineage", "duplicate_lineage")
            seen_ids.add(item.lineage_id)
            checked_lineage.append(item)
        if len(checked_lineage) > max_lineage:
            raise _fail("lineage", "cap_exceeded")
        object.__setattr__(self, "lineage", tuple(checked_lineage))
        _LOG.debug(
            "mentorship_ledger_constructed owner_id=%s bond_count=%s "
            "lineage_count=%s",
            self.owner_id.value,
            len(checked_bonds),
            len(checked_lineage),
        )


def empty_mentorship_ledger(
    owner_id: AgentId,
    *,
    max_bonds: int = 64,
    max_lineage_entries: int = 256,
) -> MentorshipLedger:
    """Return an empty owner mentorship ledger (channel may be on; content empty)."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    ledger = MentorshipLedger(
        owner_id=owner_id,
        max_bonds=max_bonds,
        max_lineage_entries=max_lineage_entries,
    )
    _LOG.debug(
        "mentorship_ledger_empty owner_id=%s bond_count=%s lineage_count=%s",
        owner_id.value,
        0,
        0,
    )
    return ledger


def require_owner_mentorship(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` is passthrough."""
    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not MentorshipLedger:
        _LOG.warning("mentorship_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be MentorshipLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "mentorship_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("mentorship_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


def mentorship_partner_bias_futures(
    *,
    ledger: MentorshipLedger | None,
    partner_bias: object | None,
    futures: Sequence[object],
) -> dict[str, float]:
    """Float bias toward communicate futures targeting bonded partners.

    Integer pairwise votes still dominate; this only adjusts the float term.
    Mode ``ignore`` (or absent bias/ledger) is passthrough.
    When ``content_kind_affinity`` is true, bonds that already carry content
    kinds add a small deterministic boost (still float-term only).
    """
    if ledger is None or partner_bias is None or not futures:
        return {}
    mode = getattr(partner_bias, "mode", "ignore")
    if mode != "prefer_bonded":
        _LOG.debug(
            "mentorship_partner_bias_skip reason_code=%s",
            "bias_ignore",
        )
        return {}
    weight = _unit_interval(
        "communicate_weight", getattr(partner_bias, "communicate_weight", 0.0)
    )
    if weight <= 0.0:
        return {}
    affinity = bool(getattr(partner_bias, "content_kind_affinity", False))
    bonded: dict[str, tuple[float, frozenset[str]]] = {
        bond.partner_agent_id.value: (
            bond.strength,
            frozenset(kind.value for kind in bond.content_kinds),
        )
        for bond in ledger.bonds
    }
    if not bonded:
        return {}
    biases: dict[str, float] = {}
    for future in futures:
        future_id = getattr(future, "future_id", None)
        direction = getattr(getattr(future, "direction", None), "value", None)
        if future_id is None or direction != "communicate":
            continue
        target_agent = getattr(future, "target_agent_id", None)
        target_token = getattr(target_agent, "value", None)
        if not isinstance(target_token, str):
            continue
        bond_meta = bonded.get(target_token)
        if bond_meta is None:
            continue
        strength, kinds = bond_meta
        applied = _quantize_unit(weight * max(strength, 0.01))
        if affinity and kinds:
            applied = _quantize_unit(min(1.0, applied + 0.05))
        biases[str(future_id)] = applied
        _LOG.debug(
            "mentorship_partner_bias_applied partner_id=%s weight_band=%s "
            "reason_code=%s",
            target_token,
            strength_band(applied),
            "bond_prefer",
        )
    return biases


def collect_mentorship_adapter_keys(
    *,
    observation: object | None,
    advice_delta: Sequence[object] = (),
    semantic_naming: object | None = None,
    social_conventions: object | None = None,
    cultural_narratives: object | None = None,
) -> dict[str, tuple[tuple[str, str, str], ...]]:
    """Collect opaque (teacher, content_key, fingerprint) rows for adapters.

    Never copies peer store payloads — only stable opaque keys / digests.
    """
    belief_keys: list[tuple[str, str, str]] = []
    causal_keys: list[tuple[str, str, str]] = []
    naming_keys: list[tuple[str, str, str]] = []
    convention_keys: list[tuple[str, str, str]] = []
    story_keys: list[tuple[str, str, str]] = []

    for row in advice_delta:
        teacher = getattr(row, "source_agent_id", None)
        teacher_token = getattr(teacher, "value", None)
        if not isinstance(teacher_token, str):
            continue
        domain = getattr(getattr(row, "domain", None), "value", None) or "skill"
        band = getattr(getattr(row, "band", None), "value", "unspecified")
        occurrence = getattr(row, "occurrence_id", "teach")
        # Factual / warning style claims from structured teaching advice.
        belief_keys.append(
            (
                teacher_token,
                f"claim:{domain}:{occurrence}",
                f"fp:{teacher_token}:{domain}:{band}",
            )
        )
        if domain in {"healing", "hazard", "warning"}:
            # Also surface as warnings via teaching path; adapters skip duplicates.
            pass

    if observation is not None:
        for communication in getattr(observation, "communications", ()) or ():
            speaker = getattr(communication, "speaker_id", None)
            speaker_token = getattr(speaker, "value", None)
            if not isinstance(speaker_token, str):
                continue
            utterance = getattr(communication, "utterance", None)
            declared = getattr(utterance, "declared", None)
            claim = getattr(declared, "claim_id", None) or getattr(
                declared, "proposition_id", None
            )
            hop = getattr(declared, "hop_count", 0)
            if claim is None:
                claim = f"comm:{speaker_token}:{getattr(communication, 'event_id', hop)}"
            claim_token = getattr(claim, "value", claim)
            if not isinstance(claim_token, str):
                continue
            belief_keys.append(
                (
                    speaker_token,
                    f"fact:{claim_token}",
                    f"fp:fact:{speaker_token}:{claim_token}:{hop}",
                )
            )
            if int(hop) >= 0 and "cause" in claim_token.lower():
                causal_keys.append(
                    (
                        speaker_token,
                        f"cause:{claim_token}",
                        f"fp:cause:{speaker_token}:{claim_token}",
                    )
                )

    def _ledger_keys(
        ledger: object | None, *, prefix: str
    ) -> list[tuple[str, str, str]]:
        if ledger is None:
            return []
        out: list[tuple[str, str, str]] = []
        entries = getattr(ledger, "entries", ()) or ()
        for entry in entries:
            teacher = getattr(entry, "source_agent_id", None) or getattr(
                entry, "teacher_agent_id", None
            )
            teacher_token = getattr(teacher, "value", None)
            if not isinstance(teacher_token, str):
                # Peer-origin unknown — skip (no invented teachers).
                continue
            key = (
                getattr(entry, "term_id", None)
                or getattr(entry, "convention_id", None)
                or getattr(entry, "narrative_id", None)
                or getattr(entry, "concept_key", None)
                or getattr(entry, "name_id", None)
            )
            key_token = getattr(key, "value", key)
            if not isinstance(key_token, str):
                continue
            fp = getattr(entry, "fingerprint", None) or f"fp:{prefix}:{key_token}"
            fp_token = getattr(fp, "value", fp)
            if not isinstance(fp_token, str):
                fp_token = f"fp:{prefix}:{key_token}"
            out.append((teacher_token, f"{prefix}:{key_token}", fp_token))
        return out

    naming_keys.extend(_ledger_keys(semantic_naming, prefix="vocab"))
    convention_keys.extend(_ledger_keys(social_conventions, prefix="practice"))
    story_keys.extend(_ledger_keys(cultural_narratives, prefix="story"))
    return {
        "belief_claim_keys": tuple(belief_keys),
        "causal_claim_keys": tuple(causal_keys),
        "naming_keys": tuple(naming_keys),
        "convention_keys": tuple(convention_keys),
        "story_keys": tuple(story_keys),
    }


def strength_band(strength: float) -> str:
    """Closed metadata band for logging (never free text / payloads)."""
    value = _unit_interval("strength", strength)
    if value < 0.25:
        return "low"
    if value < 0.75:
        return "mid"
    return "high"


def _evict_weakest_bonds(
    bonds: list[MentorshipBond], *, max_bonds: int, owner_id: AgentId
) -> list[MentorshipBond]:
    if len(bonds) <= max_bonds:
        return bonds
    ordered = sorted(
        bonds,
        key=lambda bond: (
            bond.strength,
            bond.formed_tick,
            bond.partner_agent_id.value,
            bond.role.value,
        ),
    )
    drop_count = len(bonds) - max_bonds
    dropped = ordered[:drop_count]
    keep_ids = {id(bond) for bond in ordered[drop_count:]}
    kept = [bond for bond in bonds if id(bond) in keep_ids]
    for bond in dropped:
        _LOG.debug(
            "mentorship_bond_evict owner_id=%s partner_id=%s strength_band=%s "
            "reason_code=%s",
            owner_id.value,
            bond.partner_agent_id.value,
            strength_band(bond.strength),
            "max_bonds_cap",
        )
    return kept


def form_or_reinforce_mentorship_bond(
    ledger: MentorshipLedger,
    *,
    partner_agent_id: AgentId,
    owner_role: MentorshipBondRole | str,
    content_kinds: Sequence[object],
    tick: int,
    successful_act_count: int,
    projected_trust: float,
    form_after_successful_acts: int,
    min_trust: float,
    reinforce_on_learning_evidence: bool,
    learning_evidence: bool = False,
    reinforce_delta: float = 0.05,
    initial_strength: float = 0.35,
) -> MentorshipLedger:
    """Form a directed bond after act/trust floors, or reinforce an existing one.

    Bonds never form from kinship edges or lifecycle stage alone.
    """
    if type(ledger) is not MentorshipLedger:
        raise _fail("ledger", "invalid_type")
    if type(partner_agent_id) is not AgentId:
        raise _fail("partner_agent_id", "invalid_type")
    if partner_agent_id == ledger.owner_id:
        raise _fail("partner_agent_id", "self_bond_forbidden")
    role = parse_mentorship_bond_role(owner_role)
    kinds = _parse_content_kinds("content_kinds", content_kinds)
    tick_i = require_exact_nonneg_int("tick", tick)
    acts = require_exact_nonneg_int("successful_act_count", successful_act_count)
    form_after = require_exact_nonneg_int(
        "form_after_successful_acts", form_after_successful_acts
    )
    trust = _unit_interval("projected_trust", projected_trust)
    floor = _unit_interval("min_trust", min_trust)
    if type(reinforce_on_learning_evidence) is not bool:
        raise _fail("reinforce_on_learning_evidence", "invalid_type")
    if type(learning_evidence) is not bool:
        raise _fail("learning_evidence", "invalid_type")

    existing_idx: int | None = None
    for index, bond in enumerate(ledger.bonds):
        if bond.partner_agent_id == partner_agent_id and bond.role is role:
            existing_idx = index
            break

    if existing_idx is None:
        if acts < form_after:
            _LOG.debug(
                "mentorship_bond_skip owner_id=%s partner_id=%s reason_code=%s",
                ledger.owner_id.value,
                partner_agent_id.value,
                "form_after_acts",
            )
            return ledger
        if trust < floor:
            _LOG.debug(
                "mentorship_bond_skip owner_id=%s partner_id=%s reason_code=%s",
                ledger.owner_id.value,
                partner_agent_id.value,
                "min_trust",
            )
            return ledger
        bond = MentorshipBond(
            partner_agent_id=partner_agent_id,
            role=role,
            content_kinds=kinds,
            strength=initial_strength,
            formed_tick=tick_i,
            last_teaching_tick=tick_i,
        )
        bonds = list(ledger.bonds)
        bonds.append(bond)
        bonds = _evict_weakest_bonds(
            bonds, max_bonds=ledger.max_bonds, owner_id=ledger.owner_id
        )
        result = MentorshipLedger(
            owner_id=ledger.owner_id,
            bonds=tuple(bonds),
            lineage=ledger.lineage,
            policy_version=ledger.policy_version,
            max_bonds=ledger.max_bonds,
            max_lineage_entries=ledger.max_lineage_entries,
        )
        _LOG.debug(
            "mentorship_bond_form owner_id=%s partner_id=%s strength_band=%s "
            "reason_code=%s",
            ledger.owner_id.value,
            partner_agent_id.value,
            strength_band(bond.strength),
            "bond_formed",
        )
        return result

    current = ledger.bonds[existing_idx]
    strength = current.strength
    reason = "bond_touch"
    if reinforce_on_learning_evidence and learning_evidence:
        strength = _quantize_unit(
            min(1.0, strength + _unit_interval("reinforce_delta", reinforce_delta))
        )
        reason = "bond_reinforce"
    merged_kinds = tuple(
        dict.fromkeys([*current.content_kinds, *kinds])
    )
    updated = MentorshipBond(
        partner_agent_id=current.partner_agent_id,
        role=current.role,
        content_kinds=merged_kinds,
        strength=strength,
        formed_tick=current.formed_tick,
        last_teaching_tick=tick_i,
        policy_version=current.policy_version,
    )
    bonds = list(ledger.bonds)
    bonds[existing_idx] = updated
    result = MentorshipLedger(
        owner_id=ledger.owner_id,
        bonds=tuple(bonds),
        lineage=ledger.lineage,
        policy_version=ledger.policy_version,
        max_bonds=ledger.max_bonds,
        max_lineage_entries=ledger.max_lineage_entries,
    )
    _LOG.debug(
        "mentorship_bond_reinforce owner_id=%s partner_id=%s strength_band=%s "
        "reason_code=%s",
        ledger.owner_id.value,
        partner_agent_id.value,
        strength_band(updated.strength),
        reason,
    )
    return result


def decay_mentorship_bonds(
    ledger: MentorshipLedger,
    *,
    tick: int,
    decay_per_tick: float,
    idle_ticks_before_decay: int = 1,
) -> MentorshipLedger:
    """Apply deterministic strength decay when teaching has been idle."""
    if type(ledger) is not MentorshipLedger:
        raise _fail("ledger", "invalid_type")
    tick_i = require_exact_nonneg_int("tick", tick)
    decay = _unit_interval("decay_per_tick", decay_per_tick)
    idle_floor = require_exact_nonneg_int(
        "idle_ticks_before_decay", idle_ticks_before_decay
    )
    if decay == 0.0 or not ledger.bonds:
        return ledger
    updated_bonds: list[MentorshipBond] = []
    changed = False
    for bond in ledger.bonds:
        idle = tick_i - bond.last_teaching_tick
        if idle < idle_floor:
            updated_bonds.append(bond)
            continue
        new_strength = _quantize_unit(max(0.0, bond.strength - decay))
        if new_strength != bond.strength:
            changed = True
            _LOG.debug(
                "mentorship_bond_decay owner_id=%s partner_id=%s strength_band=%s "
                "reason_code=%s",
                ledger.owner_id.value,
                bond.partner_agent_id.value,
                strength_band(new_strength),
                "decay_per_tick",
            )
        if new_strength <= 0.0:
            _LOG.debug(
                "mentorship_bond_drop owner_id=%s partner_id=%s strength_band=%s "
                "reason_code=%s",
                ledger.owner_id.value,
                bond.partner_agent_id.value,
                "low",
                "strength_zero",
            )
            changed = True
            continue
        updated_bonds.append(
            MentorshipBond(
                partner_agent_id=bond.partner_agent_id,
                role=bond.role,
                content_kinds=bond.content_kinds,
                strength=new_strength,
                formed_tick=bond.formed_tick,
                last_teaching_tick=bond.last_teaching_tick,
                policy_version=bond.policy_version,
            )
        )
    if not changed:
        return ledger
    return MentorshipLedger(
        owner_id=ledger.owner_id,
        bonds=tuple(updated_bonds),
        lineage=ledger.lineage,
        policy_version=ledger.policy_version,
        max_bonds=ledger.max_bonds,
        max_lineage_entries=ledger.max_lineage_entries,
    )


def record_taught_content_lineage(
    ledger: MentorshipLedger,
    *,
    teacher_agent_id: AgentId,
    content_kind: MentorshipContentKindId | str,
    content_key: str,
    content_fingerprint: str,
    tick: int,
    evidence_refs: Sequence[str],
    confidence: float,
    uptake_succeeded: bool,
    record_attempts: bool,
    max_hop_depth: int,
    parent_lineage_id: str | None = None,
    lineage_root_id: str | None = None,
    parent_hop_index: int | None = None,
) -> MentorshipLedger:
    """Append or update a taught-content lineage row (owner is learner).

    First hop uses ``hop_index=0`` (:data:`LINEAGE_FIRST_HOP_INDEX`). Exceeding
    ``max_hop_depth`` fails closed with ``mentorship_hop_cap``.
    """
    if type(ledger) is not MentorshipLedger:
        raise _fail("ledger", "invalid_type")
    if type(teacher_agent_id) is not AgentId:
        _LOG.error(
            "mentorship_lineage_rejected owner_id=%s reason_code=%s code=%s",
            ledger.owner_id.value,
            "provenance_required",
            "provenance_required",
        )
        raise _fail("teacher_agent_id", "provenance_required")
    kind = parse_mentorship_content_kind(content_kind)
    key = require_stable_id("content_key", content_key)
    refs = _require_tuple("evidence_refs", evidence_refs)
    if not refs and not (record_attempts and not uptake_succeeded):
        _LOG.error(
            "mentorship_lineage_rejected owner_id=%s reason_code=%s code=%s",
            ledger.owner_id.value,
            "provenance_required",
            "provenance_required",
        )
        raise _fail("evidence_refs", "provenance_required")
    if not uptake_succeeded and not record_attempts:
        _LOG.debug(
            "mentorship_lineage_skip owner_id=%s content_kind=%s reason_code=%s",
            ledger.owner_id.value,
            kind.value,
            "attempt_not_recorded",
        )
        return ledger

    tick_i = require_exact_nonneg_int("tick", tick)
    hop = LINEAGE_FIRST_HOP_INDEX
    root_id = lineage_root_id
    if parent_lineage_id is not None:
        parent_token = require_stable_id("parent_lineage_id", parent_lineage_id)
        parent_entry = next(
            (row for row in ledger.lineage if row.lineage_id == parent_token),
            None,
        )
        if parent_entry is not None:
            hop = parent_entry.hop_index + 1
            root_id = parent_entry.lineage_root_id
        elif parent_hop_index is not None:
            hop = require_exact_nonneg_int("parent_hop_index", parent_hop_index) + 1
        else:
            hop = 1
        if root_id is None:
            root_id = parent_token
    if root_id is None:
        root_id = f"root:{teacher_agent_id.value}:{kind.value}:{key}"
    root_id = require_stable_id("lineage_root_id", root_id)
    depth_cap = require_exact_nonneg_int("max_hop_depth", max_hop_depth)
    if depth_cap < 1:
        raise _fail("max_hop_depth", "out_of_range")
    if hop >= depth_cap:
        _LOG.error(
            "mentorship_lineage_rejected owner_id=%s content_kind=%s "
            "hop_index=%s reason_code=%s code=%s",
            ledger.owner_id.value,
            kind.value,
            hop,
            "mentorship_hop_cap",
            "mentorship_hop_cap",
        )
        raise ValueError("hop_index: mentorship_hop_cap")

    conf = _unit_interval("confidence", confidence)
    fingerprint = require_stable_id("content_fingerprint", content_fingerprint)
    checked_refs = [
        require_stable_id("evidence_refs", item) for item in refs if item is not None
    ]
    if not checked_refs:
        checked_refs = [f"attempt:{tick_i}:{kind.value}:{key}"]

    existing_idx: int | None = None
    for index, row in enumerate(ledger.lineage):
        if (
            row.content_kind is kind
            and row.content_key == key
            and row.teacher_agent_id == teacher_agent_id
            and row.lineage_root_id == root_id
        ):
            existing_idx = index
            break

    if existing_idx is None:
        entry = TaughtContentLineageEntry(
            teacher_agent_id=teacher_agent_id,
            learner_agent_id=ledger.owner_id,
            content_kind=kind,
            content_key=key,
            content_fingerprint=fingerprint,
            parent_lineage_id=parent_lineage_id,
            lineage_root_id=root_id,
            hop_index=hop,
            attempt_count=1,
            learning_evidence_count=1 if uptake_succeeded else 0,
            confidence=conf,
            mutated=False,
            acquired_tick=tick_i,
            last_updated_tick=tick_i,
            evidence_refs=tuple(dict.fromkeys(checked_refs)),
        )
        rows = list(ledger.lineage)
        rows.append(entry)
        if len(rows) > ledger.max_lineage_entries:
            rows_sorted = sorted(
                rows, key=lambda row: (row.acquired_tick, row.lineage_id or "")
            )
            drop = rows_sorted[0]
            rows = [row for row in rows if row is not drop]
            _LOG.debug(
                "mentorship_lineage_evict owner_id=%s content_kind=%s "
                "reason_code=%s",
                ledger.owner_id.value,
                drop.content_kind.value,
                "max_lineage_cap",
            )
        result = MentorshipLedger(
            owner_id=ledger.owner_id,
            bonds=ledger.bonds,
            lineage=tuple(rows),
            policy_version=ledger.policy_version,
            max_bonds=ledger.max_bonds,
            max_lineage_entries=ledger.max_lineage_entries,
        )
        _LOG.debug(
            "mentorship_lineage_write content_kind=%s hop_index=%s mutated=%s "
            "attempt_count=%s evidence_count=%s reason_code=%s",
            kind.value,
            hop,
            False,
            1,
            entry.learning_evidence_count,
            "lineage_recorded" if uptake_succeeded else "attempt_recorded",
        )
        return result

    current = ledger.lineage[existing_idx]
    entry = TaughtContentLineageEntry(
        teacher_agent_id=current.teacher_agent_id,
        learner_agent_id=current.learner_agent_id,
        content_kind=current.content_kind,
        content_key=current.content_key,
        content_fingerprint=(
            fingerprint if uptake_succeeded else current.content_fingerprint
        ),
        parent_lineage_id=current.parent_lineage_id,
        lineage_root_id=current.lineage_root_id,
        hop_index=current.hop_index,
        attempt_count=current.attempt_count + 1,
        learning_evidence_count=(
            current.learning_evidence_count + (1 if uptake_succeeded else 0)
        ),
        confidence=conf if uptake_succeeded else current.confidence,
        mutated=current.mutated,
        acquired_tick=current.acquired_tick,
        last_updated_tick=tick_i,
        evidence_refs=tuple(
            dict.fromkeys([*current.evidence_refs, *checked_refs])
        ),
        lineage_id=current.lineage_id,
        policy_version=current.policy_version,
    )
    rows = list(ledger.lineage)
    rows[existing_idx] = entry
    result = MentorshipLedger(
        owner_id=ledger.owner_id,
        bonds=ledger.bonds,
        lineage=tuple(rows),
        policy_version=ledger.policy_version,
        max_bonds=ledger.max_bonds,
        max_lineage_entries=ledger.max_lineage_entries,
    )
    _LOG.debug(
        "mentorship_lineage_write content_kind=%s hop_index=%s mutated=%s "
        "attempt_count=%s evidence_count=%s reason_code=%s",
        kind.value,
        entry.hop_index,
        entry.mutated,
        entry.attempt_count,
        entry.learning_evidence_count,
        "lineage_updated",
    )
    return result


def mutate_taught_content_lineage(
    ledger: MentorshipLedger,
    *,
    lineage_id: str,
    content_fingerprint: str,
    confidence: float,
    tick: int,
    allow_learner_mutation: bool,
    mutation_requires_evidence: bool,
    owner_evidence_present: bool,
) -> MentorshipLedger:
    """Revise learner fingerprint/confidence after uptake when policy allows."""
    if type(ledger) is not MentorshipLedger:
        raise _fail("ledger", "invalid_type")
    if not allow_learner_mutation:
        _LOG.debug(
            "mentorship_mutation_skip owner_id=%s reason_code=%s",
            ledger.owner_id.value,
            "mutation_disabled",
        )
        return ledger
    if mutation_requires_evidence and not owner_evidence_present:
        _LOG.debug(
            "mentorship_mutation_skip owner_id=%s reason_code=%s",
            ledger.owner_id.value,
            "mutation_requires_evidence",
        )
        return ledger
    token = require_stable_id("lineage_id", lineage_id)
    tick_i = require_exact_nonneg_int("tick", tick)
    fingerprint = require_stable_id("content_fingerprint", content_fingerprint)
    conf = _unit_interval("confidence", confidence)
    rows: list[TaughtContentLineageEntry] = []
    found = False
    for row in ledger.lineage:
        if row.lineage_id != token:
            rows.append(row)
            continue
        found = True
        rows.append(
            TaughtContentLineageEntry(
                teacher_agent_id=row.teacher_agent_id,
                learner_agent_id=row.learner_agent_id,
                content_kind=row.content_kind,
                content_key=row.content_key,
                content_fingerprint=fingerprint,
                parent_lineage_id=row.parent_lineage_id,
                lineage_root_id=row.lineage_root_id,
                hop_index=row.hop_index,
                attempt_count=row.attempt_count,
                learning_evidence_count=row.learning_evidence_count,
                confidence=conf,
                mutated=True,
                acquired_tick=row.acquired_tick,
                last_updated_tick=tick_i,
                evidence_refs=row.evidence_refs,
                lineage_id=row.lineage_id,
                policy_version=row.policy_version,
            )
        )
        _LOG.debug(
            "mentorship_lineage_write content_kind=%s hop_index=%s mutated=%s "
            "attempt_count=%s evidence_count=%s reason_code=%s",
            row.content_kind.value,
            row.hop_index,
            True,
            row.attempt_count,
            row.learning_evidence_count,
            "learner_mutation",
        )
    if not found:
        raise _fail("lineage_id", "unknown_lineage")
    return MentorshipLedger(
        owner_id=ledger.owner_id,
        bonds=ledger.bonds,
        lineage=tuple(rows),
        policy_version=ledger.policy_version,
        max_bonds=ledger.max_bonds,
        max_lineage_entries=ledger.max_lineage_entries,
    )


_DOMAIN_TO_CONTENT_KIND: Final[Mapping[str, MentorshipContentKindId]] = {
    "foraging": MentorshipContentKindId.PRACTICAL_SKILLS,
    "navigation": MentorshipContentKindId.PRACTICAL_SKILLS,
    "resource_detection": MentorshipContentKindId.PRACTICAL_SKILLS,
    "crafting": MentorshipContentKindId.PRODUCTION_RECIPES,
    "building": MentorshipContentKindId.PRODUCTION_RECIPES,
    "healing": MentorshipContentKindId.WARNINGS,
    "communication": MentorshipContentKindId.SOCIAL_PRACTICES,
    "teaching": MentorshipContentKindId.PRACTICAL_SKILLS,
}


@dataclass(frozen=True, slots=True)
class MentorshipAudit:
    """Metadata-only mentorship audit row (analysis harvest; never payloads)."""

    owner_id: AgentId
    partner_agent_id: AgentId
    role: MentorshipBondRole
    content_kind: MentorshipContentKindId
    hop_index: int
    attempt_count: int
    learning_evidence_count: int
    confidence_band: str
    mutated: bool
    tick: int
    reason_code: str

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.partner_agent_id) is not AgentId:
            raise _fail("partner_agent_id", "invalid_type")
        object.__setattr__(self, "role", parse_mentorship_bond_role(self.role))
        object.__setattr__(
            self, "content_kind", parse_mentorship_content_kind(self.content_kind)
        )
        object.__setattr__(
            self, "hop_index", require_exact_nonneg_int("hop_index", self.hop_index)
        )
        object.__setattr__(
            self,
            "attempt_count",
            require_exact_nonneg_int("attempt_count", self.attempt_count),
        )
        object.__setattr__(
            self,
            "learning_evidence_count",
            require_exact_nonneg_int(
                "learning_evidence_count", self.learning_evidence_count
            ),
        )
        band = require_stable_id("confidence_band", self.confidence_band)
        if band not in {"none", "low", "mid", "high"}:
            raise _fail("confidence_band", "unknown_band")
        object.__setattr__(self, "confidence_band", band)
        if type(self.mutated) is not bool:
            raise _fail("mutated", "invalid_type")
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self, "reason_code", require_stable_id("reason_code", self.reason_code)
        )


def _confidence_band(confidence: float) -> str:
    value = _unit_interval("confidence", confidence)
    if value <= 0.0:
        return "none"
    if value < 0.34:
        return "low"
    if value < 0.67:
        return "mid"
    return "high"


def apply_mentorship_from_teaching(
    ledger: MentorshipLedger,
    *,
    enabled_content_kinds: Sequence[str],
    advice_delta: Sequence[object],
    tick: int,
    bond_policy: object,
    lineage_policy: object,
    projected_trust_by_teacher: Mapping[str, float] | None = None,
) -> tuple[MentorshipLedger, tuple[MentorshipAudit, ...]]:
    """Update bonds/lineage from delivered teaching advice without copying internals.

    Maps closed skill domains onto enabled content kinds. Incorrect teaching
    (false bands) remains legal; this only records owner-scoped lineage.
    """
    if type(ledger) is not MentorshipLedger:
        raise _fail("ledger", "invalid_type")
    enabled = {
        parse_mentorship_content_kind(item).value for item in enabled_content_kinds
    }
    if not advice_delta:
        return ledger, ()
    form_after = int(getattr(bond_policy, "form_after_successful_acts", 2))
    min_trust = float(getattr(bond_policy, "min_trust", 0.2))
    reinforce = bool(getattr(bond_policy, "reinforce_on_learning_evidence", True))
    record_attempts = bool(getattr(lineage_policy, "record_attempts", True))
    max_hop = int(getattr(lineage_policy, "max_hop_depth", 4))
    trust_map = dict(projected_trust_by_teacher or {})
    audits: list[MentorshipAudit] = []
    current = ledger
    act_counts: dict[str, int] = {}
    for row in advice_delta:
        teacher = getattr(row, "source_agent_id", None)
        if type(teacher) is not AgentId:
            continue
        act_counts[teacher.value] = act_counts.get(teacher.value, 0) + 1

    for row in advice_delta:
        teacher = getattr(row, "source_agent_id", None)
        domain = getattr(getattr(row, "domain", None), "value", None)
        act = getattr(getattr(row, "act", None), "value", None)
        occurrence = getattr(row, "occurrence_id", None)
        band = getattr(getattr(row, "band", None), "value", "unspecified")
        if type(teacher) is not AgentId or not isinstance(domain, str):
            continue
        kind = _DOMAIN_TO_CONTENT_KIND.get(domain)
        if kind is None or kind.value not in enabled:
            _LOG.debug(
                "mentorship_uptake content_kind=%s act=%s band=%s reason_code=%s",
                domain,
                act,
                band,
                "content_kind_disabled",
            )
            continue
        content_key = f"skill:{domain}"
        fingerprint = f"fp:{ledger.owner_id.value}:{domain}:{band}"
        trust = float(trust_map.get(teacher.value, 0.5))
        try:
            current = record_taught_content_lineage(
                current,
                teacher_agent_id=teacher,
                content_kind=kind,
                content_key=content_key,
                content_fingerprint=fingerprint,
                tick=tick,
                evidence_refs=(str(occurrence),) if occurrence else (),
                confidence=min(1.0, max(0.0, trust)),
                uptake_succeeded=True,
                record_attempts=record_attempts,
                max_hop_depth=max_hop,
            )
        except ValueError as exc:
            if "mentorship_hop_cap" in str(exc):
                continue
            raise
        current = form_or_reinforce_mentorship_bond(
            current,
            partner_agent_id=teacher,
            owner_role=MentorshipBondRole.APPRENTICE,
            content_kinds=(kind,),
            tick=tick,
            successful_act_count=act_counts.get(teacher.value, 1),
            projected_trust=trust,
            form_after_successful_acts=form_after,
            min_trust=min_trust,
            reinforce_on_learning_evidence=reinforce,
            learning_evidence=True,
        )
        entry = next(
            (
                row_l
                for row_l in current.lineage
                if row_l.teacher_agent_id == teacher and row_l.content_key == content_key
            ),
            None,
        )
        hop = 0 if entry is None else entry.hop_index
        attempts = 1 if entry is None else entry.attempt_count
        evidence = 0 if entry is None else entry.learning_evidence_count
        conf = 0.0 if entry is None else entry.confidence
        mutated = False if entry is None else entry.mutated
        audits.append(
            MentorshipAudit(
                owner_id=ledger.owner_id,
                partner_agent_id=teacher,
                role=MentorshipBondRole.APPRENTICE,
                content_kind=kind,
                hop_index=hop,
                attempt_count=attempts,
                learning_evidence_count=evidence,
                confidence_band=_confidence_band(conf),
                mutated=mutated,
                tick=tick,
                reason_code="teaching_uptake",
            )
        )
        _LOG.debug(
            "mentorship_uptake content_kind=%s act=%s band=%s reason_code=%s",
            kind.value,
            act,
            band,
            "uptake_recorded",
        )
    return current, tuple(audits)


def apply_mentorship_content_kind_adapters(
    ledger: MentorshipLedger,
    *,
    enabled_content_kinds: Sequence[str],
    tick: int,
    semantic_naming_on: bool = False,
    social_convention_on: bool = False,
    cultural_narrative_on: bool = False,
    predictive_world_model: bool = False,
    belief_claim_keys: Sequence[tuple[str, str, str]] = (),
    # (teacher_id, content_key, fingerprint) for factual_beliefs
    causal_claim_keys: Sequence[tuple[str, str, str]] = (),
    naming_keys: Sequence[tuple[str, str, str]] = (),
    convention_keys: Sequence[tuple[str, str, str]] = (),
    story_keys: Sequence[tuple[str, str, str]] = (),
    bond_policy: object | None = None,
    lineage_policy: object | None = None,
) -> tuple[MentorshipLedger, tuple[MentorshipAudit, ...]]:
    """Record lineage for non-skill content kinds without cloning peer stores.

    Each key tuple is (teacher_agent_id, content_key, fingerprint). Mode-off
    kinds skip with stable DEBUG reasons.
    """
    if type(ledger) is not MentorshipLedger:
        raise _fail("ledger", "invalid_type")
    enabled = {
        parse_mentorship_content_kind(item).value for item in enabled_content_kinds
    }
    if bond_policy is None or lineage_policy is None:
        return ledger, ()
    record_attempts = bool(getattr(lineage_policy, "record_attempts", True))
    max_hop = int(getattr(lineage_policy, "max_hop_depth", 4))
    form_after = int(getattr(bond_policy, "form_after_successful_acts", 2))
    min_trust = float(getattr(bond_policy, "min_trust", 0.2))
    reinforce = bool(getattr(bond_policy, "reinforce_on_learning_evidence", True))
    current = ledger
    audits: list[MentorshipAudit] = []

    def _ingest(
        *,
        kind: MentorshipContentKindId,
        mode_on: bool,
        skip_code: str,
        rows: Sequence[tuple[str, str, str]],
    ) -> None:
        nonlocal current
        if kind.value not in enabled:
            return
        if not mode_on:
            _LOG.debug(
                "mentorship_adapter_skip content_kind=%s mode_on=%s reason_code=%s",
                kind.value,
                False,
                skip_code,
            )
            return
        for teacher_raw, content_key, fingerprint in rows:
            teacher = AgentId(teacher_raw)
            try:
                current = record_taught_content_lineage(
                    current,
                    teacher_agent_id=teacher,
                    content_kind=kind,
                    content_key=content_key,
                    content_fingerprint=fingerprint,
                    tick=tick,
                    evidence_refs=(f"adapter:{kind.value}:{content_key}",),
                    confidence=0.4,
                    uptake_succeeded=True,
                    record_attempts=record_attempts,
                    max_hop_depth=max_hop,
                )
            except ValueError as exc:
                if "mentorship_hop_cap" in str(exc):
                    continue
                raise
            current = form_or_reinforce_mentorship_bond(
                current,
                partner_agent_id=teacher,
                owner_role=MentorshipBondRole.APPRENTICE,
                content_kinds=(kind,),
                tick=tick,
                successful_act_count=form_after,
                projected_trust=max(min_trust, 0.5),
                form_after_successful_acts=form_after,
                min_trust=min_trust,
                reinforce_on_learning_evidence=reinforce,
                learning_evidence=True,
            )
            entry = next(
                (
                    row_l
                    for row_l in current.lineage
                    if row_l.content_key == content_key
                    and row_l.teacher_agent_id == teacher
                ),
                None,
            )
            audits.append(
                MentorshipAudit(
                    owner_id=ledger.owner_id,
                    partner_agent_id=teacher,
                    role=MentorshipBondRole.APPRENTICE,
                    content_kind=kind,
                    hop_index=0 if entry is None else entry.hop_index,
                    attempt_count=1 if entry is None else entry.attempt_count,
                    learning_evidence_count=(
                        0 if entry is None else entry.learning_evidence_count
                    ),
                    confidence_band=_confidence_band(
                        0.0 if entry is None else entry.confidence
                    ),
                    mutated=False if entry is None else entry.mutated,
                    tick=tick,
                    reason_code="adapter_uptake",
                )
            )
            _LOG.debug(
                "mentorship_adapter_write content_kind=%s mode_on=%s mutated=%s "
                "reason_code=%s",
                kind.value,
                True,
                False,
                "adapter_uptake",
            )

    _ingest(
        kind=MentorshipContentKindId.FACTUAL_BELIEFS,
        mode_on=True,
        skip_code="factual_beliefs_unavailable",
        rows=belief_claim_keys,
    )
    _ingest(
        kind=MentorshipContentKindId.CAUSAL_HYPOTHESES,
        mode_on=predictive_world_model,
        skip_code="causal_hypotheses_requires_flag",
        rows=causal_claim_keys,
    )
    _ingest(
        kind=MentorshipContentKindId.VOCABULARY,
        mode_on=semantic_naming_on,
        skip_code="vocabulary_mode_off",
        rows=naming_keys,
    )
    _ingest(
        kind=MentorshipContentKindId.SOCIAL_PRACTICES,
        mode_on=social_convention_on,
        skip_code="social_practices_mode_off",
        rows=convention_keys,
    )
    _ingest(
        kind=MentorshipContentKindId.STORIES,
        mode_on=cultural_narrative_on,
        skip_code="stories_mode_off",
        rows=story_keys,
    )
    return current, tuple(audits)
