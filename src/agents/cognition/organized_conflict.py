# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Owner-scoped organized conflict beliefs.

Coordination is one owner's belief about coordinated violence, defense,
movement, capture, opposition, retreat, and assistance. It is never a war
state, a conflict registry, an army actor, a command hierarchy, a permission, an
obligation, or a world capability. There is no ``world.at_war`` field and no
global conflict object anywhere.

Every physical effect remains one ordinary ``AgentCommand`` admitted by
``WorldEngine``. The only command-producing helper in the whole feature is the
deterministic ``Wait`` replacement screen in
``organized_conflict_actions``; this module stores command *names* only and
never constructs or submits a command.

The eight requested primitives are descriptive operation kinds. They compile
only to existing command names, and the mapping is closed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

__all__ = [
    "CONFLICT_CONTRADICTION_ID_PREFIX",
    "CONFLICT_EPISODE_ID_PREFIX",
    "CONFLICT_ID_HEX_LEN",
    "CONFLICT_ID_PREFIXES",
    "CONFLICT_ID_SEPARATOR",
    "CONFLICT_INTERPRETATION_ID_PREFIX",
    "CONFLICT_OBSERVATION_ID_PREFIX",
    "CONFLICT_OPERATION_COMMANDS",
    "CONFLICT_OUTCOME_ID_PREFIX",
    "CONFLICT_PARTICIPATION_ID_PREFIX",
    "CONFLICT_PLAN_ID_PREFIX",
    "CONFLICT_TERMINATION_ID_PREFIX",
    "ORGANIZED_CONFLICT_CONTRACT_VERSION",
    "ORGANIZED_CONFLICT_FRAME_FIELD_COUNT",
    "ORGANIZED_CONFLICT_FRAME_MAX_CHARS",
    "ORGANIZED_CONFLICT_FRAME_VERSION",
    "ORGANIZED_CONFLICT_ID_HEX_LEN",
    "ORGANIZED_CONFLICT_ID_SEPARATOR",
    "ORGANIZED_CONFLICT_POLICY_VALUES",
    "ORGANIZED_CONFLICT_POLICY_VERSION",
    "ConflictContradictionKind",
    "ConflictInterpretationKind",
    "ConflictOperation",
    "ConflictOutcomeKind",
    "ConflictParticipationStance",
    "ConflictPlanStatus",
    "ConflictProvenance",
    "ConflictRole",
    "ConflictTargetKind",
    "ConflictTerminationKind",
    "OrganizedConflictError",
    "OrganizedConflictPolicy",
    "assert_conflict_no_forbidden_fields",
    "conflict_group_token",
    "conflict_record_id",
    "conflict_target_token",
    "default_organized_conflict_policy",
    "require_conflict_id",
    "require_conflict_token",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.organized_conflict")

ORGANIZED_CONFLICT_POLICY_VERSION: Final[str] = "organized-conflict.v1"
ORGANIZED_CONFLICT_CONTRACT_VERSION: Final[str] = "organized-conflict-v1"
ORGANIZED_CONFLICT_ID_HEX_LEN: Final[int] = 16
ORGANIZED_CONFLICT_ID_SEPARATOR: Final[str] = "|"
ORGANIZED_CONFLICT_FRAME_VERSION: Final[str] = "ocf_v1"
ORGANIZED_CONFLICT_FRAME_MAX_CHARS: Final[int] = 256
ORGANIZED_CONFLICT_FRAME_FIELD_COUNT: Final[int] = 12

CONFLICT_ID_HEX_LEN: Final[int] = ORGANIZED_CONFLICT_ID_HEX_LEN
CONFLICT_ID_SEPARATOR: Final[str] = ORGANIZED_CONFLICT_ID_SEPARATOR

CONFLICT_EPISODE_ID_PREFIX: Final[str] = "oce-"
CONFLICT_PLAN_ID_PREFIX: Final[str] = "ocp-"
CONFLICT_PARTICIPATION_ID_PREFIX: Final[str] = "ocm-"
CONFLICT_OBSERVATION_ID_PREFIX: Final[str] = "oco-"
CONFLICT_INTERPRETATION_ID_PREFIX: Final[str] = "oci-"
CONFLICT_OUTCOME_ID_PREFIX: Final[str] = "ocx-"
CONFLICT_CONTRADICTION_ID_PREFIX: Final[str] = "occ-"
CONFLICT_TERMINATION_ID_PREFIX: Final[str] = "oct-"

CONFLICT_ID_PREFIXES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "episode": CONFLICT_EPISODE_ID_PREFIX,
        "plan": CONFLICT_PLAN_ID_PREFIX,
        "participation": CONFLICT_PARTICIPATION_ID_PREFIX,
        "observation": CONFLICT_OBSERVATION_ID_PREFIX,
        "interpretation": CONFLICT_INTERPRETATION_ID_PREFIX,
        "outcome": CONFLICT_OUTCOME_ID_PREFIX,
        "contradiction": CONFLICT_CONTRADICTION_ID_PREFIX,
        "termination": CONFLICT_TERMINATION_ID_PREFIX,
    }
)


class ConflictOperation(StrEnum):
    """Eight closed descriptive operation kinds. Never permissions."""

    COORDINATED_ATTACK = "coordinated_attack"
    DEFENSE = "defense"
    MOVEMENT_GROUP = "movement_group"
    RESOURCE_CAPTURE = "resource_capture"
    STRUCTURE_ATTACK = "structure_attack"
    ROUTE_BLOCKING = "route_blocking"
    RETREAT = "retreat"
    ASSISTANCE = "assistance"


class ConflictRole(StrEnum):
    """Closed owner-local role claim. Never an obligation."""

    ATTACKER = "attacker"
    DEFENDER = "defender"
    SCOUT = "scout"
    BLOCKER = "blocker"
    CAPTURER = "capturer"
    ASSISTANT = "assistant"
    RETREATER = "retreater"
    MESSENGER = "messenger"
    UNKNOWN = "unknown"


class ConflictTargetKind(StrEnum):
    """Closed target category. All targets stay opaque tokens."""

    AGENT = "agent"
    GROUP = "group"
    LOCATION = "location"
    ROUTE = "route"
    RESOURCE = "resource"
    STRUCTURE = "structure"
    UNKNOWN = "unknown"


class ConflictPlanStatus(StrEnum):
    """Closed owner-local plan status."""

    PROPOSED = "proposed"
    JOINED = "joined"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    EXPIRED = "expired"


class ConflictParticipationStance(StrEnum):
    """Closed participation stance. A claim, never a binding answer."""

    JOIN = "join"
    DECLINE = "decline"
    WITHDRAW = "withdraw"
    UNKNOWN = "unknown"


class ConflictInterpretationKind(StrEnum):
    """Closed owner interpretation of an observed event pattern."""

    INDIVIDUAL_VIOLENCE = "individual_violence"
    COORDINATED_CONFLICT = "coordinated_conflict"
    DEFENSE = "defense"
    RETREAT = "retreat"
    ASSISTANCE = "assistance"
    RESOURCE_CAPTURE = "resource_capture"
    ROUTE_BLOCKING = "route_blocking"
    STRUCTURE_ATTACK = "structure_attack"
    PERSISTENT_INTER_GROUP_CONFLICT = "persistent_inter_group_conflict"
    UNCLEAR = "unclear"


class ConflictProvenance(StrEnum):
    """Closed provenance code assigned locally by the receiver."""

    SELF_DECLARED = "self_declared"
    COMMUNICATED = "communicated"
    OBSERVED = "observed"
    REMEMBERED = "remembered"
    INFERRED = "inferred"


class ConflictOutcomeKind(StrEnum):
    """Closed outcome category derived from observed or declared effects."""

    HIT = "hit"
    MISS = "miss"
    DAMAGE = "damage"
    DEATH = "death"
    FLEE_SUCCESS = "flee_success"
    FLEE_FAILURE = "flee_failure"
    CUSTODY_CAPTURE = "custody_capture"
    STRUCTURE_OPPOSITION = "structure_opposition"
    ASSISTANCE = "assistance"
    CO_MOVEMENT = "co_movement"


class ConflictContradictionKind(StrEnum):
    """Closed retained contradiction kind. Never reconciled."""

    DUPLICATE_PLAN = "duplicate_plan"
    CONTRADICTORY_PLAN = "contradictory_plan"
    CONTRADICTORY_INTERPRETATION = "contradictory_interpretation"
    CONFLICTING_SIDE = "conflicting_side"


class ConflictTerminationKind(StrEnum):
    """Closed plan termination kind."""

    COMPLETED = "completed"
    ABANDONED = "abandoned"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


CONFLICT_OPERATION_COMMANDS: Final[Mapping[ConflictOperation, frozenset[str]]] = (
    MappingProxyType(
        {
            ConflictOperation.COORDINATED_ATTACK: frozenset({"attack"}),
            ConflictOperation.DEFENSE: frozenset({"attack", "help", "move"}),
            ConflictOperation.MOVEMENT_GROUP: frozenset({"move", "transport"}),
            ConflictOperation.RESOURCE_CAPTURE: frozenset({"take", "give"}),
            ConflictOperation.STRUCTURE_ATTACK: frozenset(
                {"oppose_public_good", "attack"}
            ),
            ConflictOperation.ROUTE_BLOCKING: frozenset(
                {"move", "attack", "flee", "help"}
            ),
            ConflictOperation.RETREAT: frozenset({"flee"}),
            ConflictOperation.ASSISTANCE: frozenset({"help", "feed", "transport"}),
        }
    )
)

# Every command name the operation matrix may reference. Kept separate from the
# importable command classes so this frozen vocabulary module never imports
# ``world`` and never builds a command value.
EXISTING_CONFLICT_COMMAND_NAMES: Final[frozenset[str]] = frozenset(
    name for names in CONFLICT_OPERATION_COMMANDS.values() for name in names
)

_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "at_war",
        "war_state",
        "war_score",
        "army_id",
        "conflict_registry",
        "winner",
        "loser",
        "legitimacy",
        "score",
        "composite",
        "truth",
        "enforced",
        "enforcement",
    }
)

_ID_PATTERNS: Final[Mapping[str, re.Pattern[str]]] = MappingProxyType(
    {
        prefix: re.compile(rf"^{re.escape(prefix)}[0-9a-f]{{{CONFLICT_ID_HEX_LEN}}}$")
        for prefix in CONFLICT_ID_PREFIXES.values()
    }
)
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,63}$")
_HEX_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^[0-9a-f]{{{CONFLICT_ID_HEX_LEN}}}$"
)

ORGANIZED_CONFLICT_POLICY_VALUES: Final[Mapping[str, int]] = MappingProxyType(
    {
        "max_plans": 8,
        "max_participants_per_plan": 16,
        "max_observations": 64,
        "max_interpretations": 16,
        "max_outcomes": 32,
        "max_contradictions": 8,
        "max_terminations": 16,
        "max_total_records": 128,
        "max_frame_chars": 256,
        "plan_ttl_ticks": 24,
        "max_target_refs": 8,
    }
)


class OrganizedConflictError(ValueError):
    """Stable-code conflict violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise OrganizedConflictError(code)


def _canonical(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return repr(value)


@dataclass(frozen=True, slots=True)
class OrganizedConflictPolicy:
    """Locked owner-local conflict bounds.

    Every value is part of the accepted contract. Any deviation is a
    programming error and fails closed with
    ``organized_conflict_policy_not_locked``.
    """

    max_plans: int = 8
    max_participants_per_plan: int = 16
    max_observations: int = 64
    max_interpretations: int = 16
    max_outcomes: int = 32
    max_contradictions: int = 8
    max_terminations: int = 16
    max_total_records: int = 128
    max_frame_chars: int = 256
    plan_ttl_ticks: int = 24
    max_target_refs: int = 8

    def __post_init__(self) -> None:
        for field in fields(type(self)):
            if field.name in _FORBIDDEN_FIELD_NAMES:
                _fail("organized_conflict_policy_not_locked")
            expected = ORGANIZED_CONFLICT_POLICY_VALUES[field.name]
            actual = getattr(self, field.name)
            if type(actual) is not int or actual != expected:
                _fail("organized_conflict_policy_not_locked")


def default_organized_conflict_policy() -> OrganizedConflictPolicy:
    """Return the one locked policy value."""

    _LOG.info(
        "organized_conflict_policy_loaded policy_version=%s plan_cap=%s",
        ORGANIZED_CONFLICT_POLICY_VERSION,
        ORGANIZED_CONFLICT_POLICY_VALUES["max_plans"],
    )
    return OrganizedConflictPolicy()


def assert_conflict_no_forbidden_fields(value: object) -> None:
    """Reject any field name that would smuggle war state, truth, or a score."""

    names: Sequence[str]
    if isinstance(value, Mapping):
        names = tuple(str(key) for key in value)
    else:
        try:
            names = tuple(field.name for field in fields(value))  # type: ignore[arg-type]
        except TypeError:
            if isinstance(value, (list, tuple, set, frozenset)):
                names = tuple(str(item) for item in value)
            else:
                _fail("organized_conflict_invalid_record")
    if any(name in _FORBIDDEN_FIELD_NAMES for name in names):
        _fail("organized_conflict_forbidden_field")


def require_conflict_id(
    name: str,
    value: object,
    *,
    prefixes: frozenset[str] = frozenset(CONFLICT_ID_PREFIXES.values()),
) -> str:
    """Validate one owner-local record id against its closed prefix set."""

    if type(name) is not str or not name:
        _fail("organized_conflict_invalid_id")
    if type(value) is not str:
        _fail("organized_conflict_invalid_id")
    for prefix in prefixes:
        pattern = _ID_PATTERNS.get(prefix)
        if pattern is not None and pattern.match(value) is not None:
            return value
    _fail("organized_conflict_invalid_id")


def require_conflict_token(name: str, value: object) -> str:
    """Validate one bounded opaque token. Never free text or an identity."""

    if type(name) is not str or not name:
        _fail("organized_conflict_untrusted_token")
    if type(value) is not str or not value or len(value) > 64:
        _fail("organized_conflict_untrusted_token")
    if _TOKEN_PATTERN.match(value) is None and _HEX_TOKEN_PATTERN.match(value) is None:
        _fail("organized_conflict_untrusted_token")
    return value


def conflict_target_token(value: str) -> str:
    """Hash one target or side value into a bounded opaque token."""

    if type(value) is not str or not value or len(value) > 256:
        _fail("organized_conflict_untrusted_token")
    payload = (
        "palimpsest.organized_conflict.target.v1"
        f"{ORGANIZED_CONFLICT_ID_SEPARATOR}{value}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[
        :ORGANIZED_CONFLICT_ID_HEX_LEN
    ]


def conflict_group_token(tokens: Sequence[str]) -> str:
    """Hash a sorted member-token set into one bounded group token."""

    if isinstance(tokens, str):
        _fail("organized_conflict_untrusted_token")
    members: list[str] = []
    for token in tokens:
        if type(token) is not str or _HEX_TOKEN_PATTERN.match(token) is None:
            _fail("organized_conflict_untrusted_token")
        members.append(token)
    payload = (
        f"palimpsest.organized_conflict.group.v1{ORGANIZED_CONFLICT_ID_SEPARATOR}"
        + ORGANIZED_CONFLICT_ID_SEPARATOR.join(sorted(members))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[
        :ORGANIZED_CONFLICT_ID_HEX_LEN
    ]


def conflict_record_id(prefix: str, *parts: object) -> str:
    """Mint a deterministic content-addressed conflict record id from evidence."""

    if type(prefix) is not str or prefix not in _ID_PATTERNS:
        _fail("organized_conflict_invalid_id")
    material = json.dumps(
        ["palimpsest.organized_conflict.record.v1", prefix, *parts],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_canonical,
    )
    return (
        prefix
        + hashlib.sha256(material.encode("utf-8")).hexdigest()[
            :ORGANIZED_CONFLICT_ID_HEX_LEN
        ]
    )


_LOG.debug(
    "organized_conflict_vocabulary_loaded operations=%s roles=%s targets=%s",
    len(ConflictOperation),
    len(ConflictRole),
    len(ConflictTargetKind),
)


# ---------------------------------------------------------------------------
# Row vocabulary (Task 4)
# ---------------------------------------------------------------------------

_CONFIDENCE_BANDS: Final[frozenset[str]] = frozenset({"low", "mid", "high"})
_CONTRADICTION_STATUS: Final[str] = "unresolved"
_MAX_REF_CHARS: Final[int] = 64


def _require_enum(value: object, enum_type: type[StrEnum], name: str) -> None:
    if type(value) is not enum_type:
        raise TypeError(f"{name} must be {enum_type.__name__}")


def _require_tick(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise TypeError(f"{name} must be a non-negative int")
    return value


def _require_ref(value: object, name: str) -> str:
    if type(value) is not str or not value or len(value) > _MAX_REF_CHARS:
        raise TypeError(f"{name} must be a bounded opaque ref")
    if _TOKEN_PATTERN.match(value) is None and _HEX_TOKEN_PATTERN.match(value) is None:
        raise TypeError(f"{name} must be a bounded opaque ref")
    return value


def _require_refs(value: object, name: str, *, cap: int) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a sequence of opaque refs")
    refs = tuple(_require_ref(item, name) for item in value)
    if len(refs) > cap:
        raise ValueError(f"{name} exceeds the reference cap")
    if len(set(refs)) != len(refs):
        raise ValueError(f"{name} contains duplicate refs")
    return refs


def _require_optional_ref(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _require_ref(value, name)


class ConflictObservationKind(StrEnum):
    """Closed owner-visible occurrence category."""

    ATTACK = "attack"
    FLEE = "flee"
    HELP = "help"
    FEED = "feed"
    TRANSPORT = "transport"
    TAKE = "take"
    GIVE = "give"
    MOVE = "move"
    JOURNEY = "journey"
    STRUCTURE_OPPOSITION = "structure_opposition"
    CONTACT = "contact"
    UNKNOWN = "unknown"


class ConflictBasis(StrEnum):
    """Closed interpretation basis."""

    SELF_DECLARED = "self_declared"
    COMMUNICATED = "communicated"
    OBSERVED = "observed"
    REMEMBERED = "remembered"
    INFERRED = "inferred"
    RECORD = "record"


@dataclass(frozen=True, slots=True)
class ConflictEpisode:
    """One owner's local episode belief. Never a global incident."""

    episode_id: str
    start_tick: int
    end_tick: int
    participant_refs: tuple[str, ...] = ()
    opponent_refs: tuple[str, ...] = ()
    event_classes: tuple[str, ...] = ()
    interpretation_ids: tuple[str, ...] = ()
    provenance: ConflictProvenance = ConflictProvenance.OBSERVED
    last_tick: int = 0

    def __post_init__(self) -> None:
        assert_conflict_no_forbidden_fields(self)
        require_conflict_id("episode_id", self.episode_id, prefixes=frozenset({"oce-"}))
        _require_tick(self.start_tick, "ConflictEpisode.start_tick")
        _require_tick(self.end_tick, "ConflictEpisode.end_tick")
        _require_tick(self.last_tick, "ConflictEpisode.last_tick")
        object.__setattr__(
            self,
            "participant_refs",
            _require_refs(
                self.participant_refs, "ConflictEpisode.participant_refs", cap=64
            ),
        )
        object.__setattr__(
            self,
            "opponent_refs",
            _require_refs(self.opponent_refs, "ConflictEpisode.opponent_refs", cap=64),
        )
        classes = tuple(
            _require_ref(item, "ConflictEpisode.event_classes")
            for item in self.event_classes
        )
        if len(set(classes)) != len(classes):
            raise ValueError("ConflictEpisode.event_classes contains duplicates")
        object.__setattr__(self, "event_classes", classes)
        ids = tuple(
            require_conflict_id("interpretation_id", item, prefixes=frozenset({"oci-"}))
            for item in self.interpretation_ids
        )
        object.__setattr__(self, "interpretation_ids", ids)
        _require_enum(self.provenance, ConflictProvenance, "ConflictEpisode.provenance")


@dataclass(frozen=True, slots=True)
class ConflictPlan:
    """One owner's coordination plan belief. Never an obligation or permission."""

    plan_id: str
    operation: ConflictOperation
    target_kind: ConflictTargetKind
    target_ref: str
    role: ConflictRole
    side_ref: str
    participant_refs: tuple[str, ...] = ()
    opponent_refs: tuple[str, ...] = ()
    coordinator_ref: str | None = None
    start_tick: int = 0
    end_tick: int = 0
    status: ConflictPlanStatus = ConflictPlanStatus.PROPOSED
    provenance: ConflictProvenance = ConflictProvenance.SELF_DECLARED
    evidence_refs: tuple[str, ...] = ()
    revision: int = 0
    last_tick: int = 0

    def __post_init__(self) -> None:
        assert_conflict_no_forbidden_fields(self)
        require_conflict_id("plan_id", self.plan_id, prefixes=frozenset({"ocp-"}))
        _require_enum(self.operation, ConflictOperation, "ConflictPlan.operation")
        _require_enum(self.target_kind, ConflictTargetKind, "ConflictPlan.target_kind")
        _require_ref(self.target_ref, "ConflictPlan.target_ref")
        _require_enum(self.role, ConflictRole, "ConflictPlan.role")
        _require_ref(self.side_ref, "ConflictPlan.side_ref")
        object.__setattr__(
            self,
            "participant_refs",
            _require_refs(
                self.participant_refs, "ConflictPlan.participant_refs", cap=16
            ),
        )
        object.__setattr__(
            self,
            "opponent_refs",
            _require_refs(self.opponent_refs, "ConflictPlan.opponent_refs", cap=16),
        )
        object.__setattr__(
            self,
            "coordinator_ref",
            _require_optional_ref(self.coordinator_ref, "ConflictPlan.coordinator_ref"),
        )
        _require_tick(self.start_tick, "ConflictPlan.start_tick")
        _require_tick(self.end_tick, "ConflictPlan.end_tick")
        _require_tick(self.last_tick, "ConflictPlan.last_tick")
        _require_tick(self.revision, "ConflictPlan.revision")
        _require_enum(self.status, ConflictPlanStatus, "ConflictPlan.status")
        _require_enum(self.provenance, ConflictProvenance, "ConflictPlan.provenance")
        refs = tuple(
            _require_ref(item, "ConflictPlan.evidence_refs")
            for item in self.evidence_refs
        )
        if len(refs) > 8:
            raise ValueError("ConflictPlan.evidence_refs exceeds the reference cap")
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True, slots=True)
class ConflictParticipation:
    """One owner's retained participation claim. Never a binding answer."""

    participation_id: str
    plan_id: str
    participant_ref: str
    role: ConflictRole
    stance: ConflictParticipationStance
    provenance: ConflictProvenance
    tick: int
    active: bool = True
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        assert_conflict_no_forbidden_fields(self)
        require_conflict_id(
            "participation_id", self.participation_id, prefixes=frozenset({"ocm-"})
        )
        require_conflict_id("plan_id", self.plan_id, prefixes=frozenset({"ocp-"}))
        _require_ref(self.participant_ref, "ConflictParticipation.participant_ref")
        _require_enum(self.role, ConflictRole, "ConflictParticipation.role")
        _require_enum(
            self.stance,
            ConflictParticipationStance,
            "ConflictParticipation.stance",
        )
        _require_enum(
            self.provenance,
            ConflictProvenance,
            "ConflictParticipation.provenance",
        )
        _require_tick(self.tick, "ConflictParticipation.tick")
        if type(self.active) is not bool:
            raise TypeError("ConflictParticipation.active must be bool")
        refs = tuple(
            _require_ref(item, "ConflictParticipation.evidence_refs")
            for item in self.evidence_refs
        )
        if len(refs) > 8:
            raise ValueError(
                "ConflictParticipation.evidence_refs exceeds the reference cap"
            )
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True, slots=True)
class ConflictObservation:
    """One owner-visible occurrence retained as a conflict observation."""

    observation_id: str
    event_class: ConflictObservationKind
    actor_ref: str
    other_ref: str | None
    tick: int
    source_event_token: str
    success: bool | None = None
    magnitude: int = 0
    provenance: ConflictProvenance = ConflictProvenance.OBSERVED

    def __post_init__(self) -> None:
        assert_conflict_no_forbidden_fields(self)
        require_conflict_id(
            "observation_id", self.observation_id, prefixes=frozenset({"oco-"})
        )
        _require_enum(
            self.event_class, ConflictObservationKind, "ConflictObservation.event_class"
        )
        _require_ref(self.actor_ref, "ConflictObservation.actor_ref")
        object.__setattr__(
            self,
            "other_ref",
            _require_optional_ref(self.other_ref, "ConflictObservation.other_ref"),
        )
        _require_tick(self.tick, "ConflictObservation.tick")
        _require_ref(self.source_event_token, "ConflictObservation.source_event_token")
        if self.success is not None and type(self.success) is not bool:
            raise TypeError("ConflictObservation.success must be bool or None")
        _require_tick(self.magnitude, "ConflictObservation.magnitude")
        _require_enum(
            self.provenance, ConflictProvenance, "ConflictObservation.provenance"
        )


@dataclass(frozen=True, slots=True)
class ConflictInterpretation:
    """One owner's interpretation; owners may classify the same events differently."""

    interpretation_id: str
    episode_ref: str | None
    kind: ConflictInterpretationKind
    basis: ConflictBasis
    confidence_band: str
    tick: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        assert_conflict_no_forbidden_fields(self)
        require_conflict_id(
            "interpretation_id", self.interpretation_id, prefixes=frozenset({"oci-"})
        )
        object.__setattr__(
            self,
            "episode_ref",
            _require_optional_ref(
                self.episode_ref, "ConflictInterpretation.episode_ref"
            ),
        )
        _require_enum(
            self.kind, ConflictInterpretationKind, "ConflictInterpretation.kind"
        )
        _require_enum(self.basis, ConflictBasis, "ConflictInterpretation.basis")
        if self.confidence_band not in _CONFIDENCE_BANDS:
            raise ValueError("ConflictInterpretation.confidence_band is not closed")
        _require_tick(self.tick, "ConflictInterpretation.tick")
        refs = tuple(
            _require_ref(item, "ConflictInterpretation.evidence_refs")
            for item in self.evidence_refs
        )
        if len(refs) > 8:
            raise ValueError(
                "ConflictInterpretation.evidence_refs exceeds the reference cap"
            )
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True, slots=True)
class ConflictOutcome:
    """One owner-observed outcome linked to an active plan."""

    outcome_id: str
    plan_id: str
    kind: ConflictOutcomeKind
    target_ref: str
    tick: int
    magnitude: int = 0

    def __post_init__(self) -> None:
        assert_conflict_no_forbidden_fields(self)
        require_conflict_id("outcome_id", self.outcome_id, prefixes=frozenset({"ocx-"}))
        require_conflict_id("plan_id", self.plan_id, prefixes=frozenset({"ocp-"}))
        _require_enum(self.kind, ConflictOutcomeKind, "ConflictOutcome.kind")
        _require_ref(self.target_ref, "ConflictOutcome.target_ref")
        _require_tick(self.tick, "ConflictOutcome.tick")
        _require_tick(self.magnitude, "ConflictOutcome.magnitude")


@dataclass(frozen=True, slots=True)
class ConflictContradiction:
    """One retained contradiction. Never reconciled or resolved."""

    contradiction_id: str
    member_ids: tuple[str, ...]
    kind: ConflictContradictionKind
    tick: int
    status: str = _CONTRADICTION_STATUS

    def __post_init__(self) -> None:
        assert_conflict_no_forbidden_fields(self)
        require_conflict_id(
            "contradiction_id", self.contradiction_id, prefixes=frozenset({"occ-"})
        )
        members = tuple(
            require_conflict_id("member_id", item, prefixes=frozenset({"ocp-", "oci-"}))
            for item in self.member_ids
        )
        if len(members) < 2:
            raise ValueError("ConflictContradiction requires at least two members")
        object.__setattr__(self, "member_ids", members)
        _require_enum(
            self.kind, ConflictContradictionKind, "ConflictContradiction.kind"
        )
        _require_tick(self.tick, "ConflictContradiction.tick")
        if self.status != _CONTRADICTION_STATUS:
            raise ValueError("ConflictContradiction.status must be unresolved")


@dataclass(frozen=True, slots=True)
class ConflictTermination:
    """One plan termination belief."""

    termination_id: str
    plan_id: str
    kind: ConflictTerminationKind
    tick: int

    def __post_init__(self) -> None:
        assert_conflict_no_forbidden_fields(self)
        require_conflict_id(
            "termination_id", self.termination_id, prefixes=frozenset({"oct-"})
        )
        require_conflict_id("plan_id", self.plan_id, prefixes=frozenset({"ocp-"}))
        _require_enum(self.kind, ConflictTerminationKind, "ConflictTermination.kind")
        _require_tick(self.tick, "ConflictTermination.tick")


@dataclass(frozen=True, slots=True)
class ConflictActionAudit:
    """Runtime-only audit of one deterministic replacement. Never published raw."""

    owner_id: str
    tick: int
    plan_id: str
    operation: ConflictOperation
    role: ConflictRole
    reason_code: str
    target_kind: ConflictTargetKind

    def __post_init__(self) -> None:
        if type(self.owner_id) is not str or not self.owner_id:
            raise TypeError("ConflictActionAudit.owner_id must be a bounded str")
        _require_tick(self.tick, "ConflictActionAudit.tick")
        require_conflict_id("plan_id", self.plan_id, prefixes=frozenset({"ocp-"}))
        _require_enum(
            self.operation, ConflictOperation, "ConflictActionAudit.operation"
        )
        _require_enum(self.role, ConflictRole, "ConflictActionAudit.role")
        if type(self.reason_code) is not str or not self.reason_code:
            raise TypeError("ConflictActionAudit.reason_code must be a bounded str")
        _require_enum(
            self.target_kind, ConflictTargetKind, "ConflictActionAudit.target_kind"
        )


def conflict_episode_id(
    owner_id: object,
    start_tick: int,
    participant_refs: Sequence[str],
    event_classes: Sequence[str],
) -> str:
    return conflict_record_id(
        CONFLICT_EPISODE_ID_PREFIX,
        str(owner_id),
        start_tick,
        tuple(sorted(participant_refs)),
        tuple(sorted(event_classes)),
    )


def conflict_plan_id(
    owner_id: object,
    operation: ConflictOperation,
    target_kind: ConflictTargetKind,
    target_ref: str,
    start_tick: int,
    participant_refs: Sequence[str],
) -> str:
    return conflict_record_id(
        CONFLICT_PLAN_ID_PREFIX,
        str(owner_id),
        operation.value,
        target_kind.value,
        target_ref,
        start_tick,
        tuple(sorted(participant_refs)),
    )


def conflict_participation_id(
    plan_id: str,
    participant_ref: str,
    stance: ConflictParticipationStance,
    tick: int,
) -> str:
    return conflict_record_id(
        CONFLICT_PARTICIPATION_ID_PREFIX,
        plan_id,
        participant_ref,
        stance.value,
        tick,
    )


def conflict_observation_id(
    owner_id: object,
    source_event_token: str,
    event_class: ConflictObservationKind,
    tick: int,
) -> str:
    return conflict_record_id(
        CONFLICT_OBSERVATION_ID_PREFIX,
        str(owner_id),
        source_event_token,
        event_class.value,
        tick,
    )


def conflict_interpretation_id(
    owner_id: object,
    episode_ref: str | None,
    kind: ConflictInterpretationKind,
    tick: int,
    basis: ConflictBasis,
) -> str:
    return conflict_record_id(
        CONFLICT_INTERPRETATION_ID_PREFIX,
        str(owner_id),
        episode_ref or "none",
        kind.value,
        tick,
        basis.value,
    )


def conflict_outcome_id(
    plan_id: str,
    kind: ConflictOutcomeKind,
    target_ref: str,
    tick: int,
) -> str:
    return conflict_record_id(
        CONFLICT_OUTCOME_ID_PREFIX, plan_id, kind.value, target_ref, tick
    )


def conflict_contradiction_id(
    owner_id: object,
    kind: ConflictContradictionKind,
    tick: int,
    member_ids: Sequence[str],
) -> str:
    return conflict_record_id(
        CONFLICT_CONTRADICTION_ID_PREFIX,
        str(owner_id),
        kind.value,
        tick,
        tuple(sorted(member_ids)),
    )


def conflict_termination_id(
    plan_id: str, kind: ConflictTerminationKind, tick: int
) -> str:
    return conflict_record_id(CONFLICT_TERMINATION_ID_PREFIX, plan_id, kind.value, tick)


# ---------------------------------------------------------------------------
# Owner ledger (Task 5)
# ---------------------------------------------------------------------------


class OrganizedConflictCapacityError(ValueError):
    """Hard-cap overflow with no payload detail."""

    code = "organized_conflict_capacity_reached"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class ConflictLedger:
    """One owner's retained conflict beliefs.

    ``None`` means the mode is off. Rows are immutable and sorted by primary id.
    """

    owner_id: object
    tick: int = 0
    revision: int = 0
    policy_version: str = ORGANIZED_CONFLICT_POLICY_VERSION
    contract_version: str = ORGANIZED_CONFLICT_CONTRACT_VERSION
    episodes: tuple[ConflictEpisode, ...] = ()
    plans: tuple[ConflictPlan, ...] = ()
    participations: tuple[ConflictParticipation, ...] = ()
    observations: tuple[ConflictObservation, ...] = ()
    interpretations: tuple[ConflictInterpretation, ...] = ()
    outcomes: tuple[ConflictOutcome, ...] = ()
    contradictions: tuple[ConflictContradiction, ...] = ()
    terminations: tuple[ConflictTermination, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        from agents.models import AgentId

        assert_conflict_no_forbidden_fields(self)
        if type(self.owner_id) is not AgentId:
            raise TypeError("ConflictLedger.owner_id must be AgentId")
        _require_tick(self.tick, "ConflictLedger.tick")
        _require_tick(self.revision, "ConflictLedger.revision")
        if self.policy_version != ORGANIZED_CONFLICT_POLICY_VERSION:
            raise ValueError("conflict_policy_mismatch")
        if self.contract_version != ORGANIZED_CONFLICT_CONTRACT_VERSION:
            raise ValueError("conflict_contract_mismatch")

        families = (
            ("episodes", self.episodes, ConflictEpisode),
            ("plans", self.plans, ConflictPlan),
            ("participations", self.participations, ConflictParticipation),
            ("observations", self.observations, ConflictObservation),
            ("interpretations", self.interpretations, ConflictInterpretation),
            ("outcomes", self.outcomes, ConflictOutcome),
            ("contradictions", self.contradictions, ConflictContradiction),
            ("terminations", self.terminations, ConflictTermination),
        )
        for name, rows, row_type in families:
            if isinstance(rows, (str, bytes, Mapping, set, frozenset)):
                raise TypeError(f"ConflictLedger.{name} must be an ordered tuple")
            if not isinstance(rows, tuple):
                raise TypeError(f"ConflictLedger.{name} must be a tuple")
            for row in rows:
                if type(row) is not row_type:
                    raise TypeError(
                        f"ConflictLedger.{name} must contain {row_type.__name__}"
                    )
        notices = tuple(self.notices)
        for notice in notices:
            if type(notice) is not str or not notice or len(notice) > 64:
                raise ValueError("ConflictLedger.notices contains an invalid notice")
        object.__setattr__(self, "notices", notices)
        self._validate_ordering()
        self._validate_references()

    def _validate_ordering(self) -> None:
        pairs = (
            (self.episodes, "episode_id"),
            (self.plans, "plan_id"),
            (self.participations, "participation_id"),
            (self.observations, "observation_id"),
            (self.interpretations, "interpretation_id"),
            (self.outcomes, "outcome_id"),
            (self.contradictions, "contradiction_id"),
            (self.terminations, "termination_id"),
        )
        for rows, id_name in pairs:
            ids = [getattr(row, id_name) for row in rows]
            if ids != sorted(ids):
                raise ValueError("conflict_unsorted_rows")
            if len(set(ids)) != len(ids):
                raise ValueError("conflict_duplicate_id")

    def _validate_references(self) -> None:
        plan_ids = {row.plan_id for row in self.plans}
        episode_ids = {row.episode_id for row in self.episodes}
        interpretation_ids = {row.interpretation_id for row in self.interpretations}
        for row in self.participations:
            if row.plan_id not in plan_ids:
                raise ValueError("conflict_foreign_reference")
        for row in self.outcomes:
            if row.plan_id not in plan_ids:
                raise ValueError("conflict_foreign_reference")
        for row in self.terminations:
            if row.plan_id not in plan_ids:
                raise ValueError("conflict_foreign_reference")
        for row in self.interpretations:
            if row.episode_ref is not None and row.episode_ref not in episode_ids:
                raise ValueError("conflict_foreign_reference")
        for row in self.episodes:
            for ref in row.interpretation_ids:
                if ref not in interpretation_ids:
                    raise ValueError("conflict_foreign_reference")
        for row in self.contradictions:
            for ref in row.member_ids:
                if ref not in plan_ids and ref not in interpretation_ids:
                    raise ValueError("conflict_foreign_reference")
        for rows in (
            self.episodes,
            self.plans,
            self.participations,
            self.observations,
            self.interpretations,
            self.outcomes,
            self.contradictions,
            self.terminations,
        ):
            for row in rows:
                for ref_name in ("participant_refs", "opponent_refs", "evidence_refs"):
                    refs = getattr(row, ref_name, ())
                    if len(refs) > _MAX_REF_CHARS:
                        raise ValueError("conflict_reference_cap")


def empty_organized_conflict_ledger(owner_id: object, *, tick: int) -> ConflictLedger:
    """Return an empty owner ledger."""

    return ConflictLedger(owner_id=owner_id, tick=tick)


def require_owner_conflict(
    ledger: object | None,
    owner_id: object,
    *,
    field_name: str = "conflict",
) -> None:
    """Validate that a carried ledger belongs to the given owner."""

    if ledger is None:
        return
    if type(ledger) is not ConflictLedger:
        raise TypeError(f"{field_name} must be ConflictLedger or None")
    if ledger.owner_id != owner_id:
        raise ValueError("conflict_owner_mismatch")


def _row_dict(row: object) -> dict[str, object]:
    return {
        field.name: _canonical(getattr(row, field.name))
        for field in fields(row)  # type: ignore[arg-type]
    }


def organized_conflict_ledger_digest(ledger: ConflictLedger) -> str:
    """Return the canonical digest of one owner's complete conflict ledger."""

    material = {
        "domain": "palimpsest.organized_conflict.ledger.v1",
        "owner_id": str(ledger.owner_id),
        "tick": ledger.tick,
        "revision": ledger.revision,
        "policy_version": ledger.policy_version,
        "contract_version": ledger.contract_version,
        "episodes": [_row_dict(row) for row in ledger.episodes],
        "plans": [_row_dict(row) for row in ledger.plans],
        "participations": [_row_dict(row) for row in ledger.participations],
        "observations": [_row_dict(row) for row in ledger.observations],
        "interpretations": [_row_dict(row) for row in ledger.interpretations],
        "outcomes": [_row_dict(row) for row in ledger.outcomes],
        "contradictions": [_row_dict(row) for row in ledger.contradictions],
        "terminations": [_row_dict(row) for row in ledger.terminations],
        "notices": list(ledger.notices),
    }
    payload = json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    _LOG.debug(
        "organized_conflict_ledger_digest plans=%s observations=%s digest_prefix=%s",
        len(ledger.plans),
        len(ledger.observations),
        digest[:8],
    )
    return digest


# ---------------------------------------------------------------------------
# Ordered update pipeline (Task 6)
# ---------------------------------------------------------------------------

_OCCURRENCE_KIND_MAP: Final[Mapping[str, ConflictObservationKind]] = MappingProxyType(
    {
        "attack": ConflictObservationKind.ATTACK,
        "flee": ConflictObservationKind.FLEE,
        "help": ConflictObservationKind.HELP,
        "feed": ConflictObservationKind.FEED,
        "transport": ConflictObservationKind.TRANSPORT,
        "take": ConflictObservationKind.TAKE,
        "give": ConflictObservationKind.GIVE,
        "move": ConflictObservationKind.MOVE,
        "journey_started": ConflictObservationKind.JOURNEY,
        "journey_arrived": ConflictObservationKind.JOURNEY,
        "public_good_opposed": ConflictObservationKind.STRUCTURE_OPPOSITION,
        "contact_recorded": ConflictObservationKind.CONTACT,
        "died": ConflictObservationKind.ATTACK,
    }
)
_HOSTILE_KINDS: Final[frozenset[ConflictObservationKind]] = frozenset(
    {ConflictObservationKind.ATTACK}
)
_ASSISTANCE_KINDS: Final[frozenset[ConflictObservationKind]] = frozenset(
    {
        ConflictObservationKind.HELP,
        ConflictObservationKind.FEED,
        ConflictObservationKind.TRANSPORT,
    }
)
_DROPPABLE_EVENT_KINDS: Final[frozenset[ConflictObservationKind]] = frozenset(
    set(ConflictObservationKind) - _HOSTILE_KINDS
)
_AUTHORITY_TYPE_NAMES: Final[frozenset[str]] = frozenset(
    {"WorldState", "WorldEvent", "ObservationToken", "ActionSubmission"}
)
_FORBIDDEN_MODULE_PREFIXES: Final[tuple[str, ...]] = (
    "world._",
    "simulation.engine",
    "simulation.persistence",
    "persistence",
    "api",
)


def _reject_authority_input(value: object, name: str) -> None:
    module = type(value).__module__
    if type(value).__name__ in _AUTHORITY_TYPE_NAMES:
        raise TypeError(f"{name} must not be objective authority")
    if any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in _FORBIDDEN_MODULE_PREFIXES
    ):
        raise TypeError(f"{name} must not be objective authority")


def _sorted_unique(rows: Sequence[object], id_name: str) -> tuple[object, ...]:
    by_id: dict[str, object] = {}
    for row in rows:
        by_id[getattr(row, id_name)] = row
    return tuple(by_id[key] for key in sorted(by_id))


def _merge_family(
    prior: Sequence[object], new: Sequence[object], id_name: str
) -> tuple[object, ...]:
    return _sorted_unique([*prior, *new], id_name)


def _token(value: object) -> str:
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return conflict_target_token(str(raw))


def _observation_source_token(observation: object, index: int) -> str:
    provenance = getattr(observation, "provenance", None)
    source_event_id = getattr(provenance, "source_event_id", None)
    raw = getattr(source_event_id, "value", None)
    if raw:
        return conflict_target_token(str(raw))
    return conflict_target_token(f"occurrence:{index}")


def _collect_observations(
    *, owner_id: object, tick: int, observation: object
) -> tuple[ConflictObservation, ...]:
    rows: list[ConflictObservation] = []
    occurrences = getattr(observation, "occurrences", ())
    for index, occurrence in enumerate(occurrences):
        kind = _OCCURRENCE_KIND_MAP.get(getattr(occurrence, "kind", ""))
        if kind is None:
            continue
        actor = getattr(occurrence, "actor_id", None)
        other = getattr(occurrence, "other_entity_id", None)
        if actor is None and other is None:
            continue
        actor_ref = _token(actor if actor is not None else other)
        other_ref = _token(other) if other is not None else None
        source = _observation_source_token(occurrence, index)
        success = getattr(occurrence, "success", None)
        rows.append(
            ConflictObservation(
                observation_id=conflict_observation_id(owner_id, source, kind, tick),
                event_class=kind,
                actor_ref=actor_ref,
                other_ref=other_ref,
                tick=tick,
                source_event_token=source,
                success=success,
                magnitude=1,
                provenance=ConflictProvenance.OBSERVED,
            )
        )
    return tuple(rows)


def _frame_operation(value: object) -> ConflictOperation:
    if isinstance(value, ConflictOperation):
        return value
    return ConflictOperation(str(value))


def _frame_role(value: object) -> ConflictRole:
    if isinstance(value, ConflictRole):
        return value
    return ConflictRole(str(value))


def _frame_target_kind(value: object) -> ConflictTargetKind:
    if isinstance(value, ConflictTargetKind):
        return value
    return ConflictTargetKind(str(value))


def _interpret_kind(
    observations: Sequence[ConflictObservation], owner_ref: str
) -> ConflictInterpretationKind | None:
    hostile = [row for row in observations if row.event_class in _HOSTILE_KINDS]
    assistance = [row for row in observations if row.event_class in _ASSISTANCE_KINDS]
    flees = [
        row for row in observations if row.event_class is ConflictObservationKind.FLEE
    ]
    takes = [
        row for row in observations if row.event_class is ConflictObservationKind.TAKE
    ]
    structures = [
        row
        for row in observations
        if row.event_class is ConflictObservationKind.STRUCTURE_OPPOSITION
    ]
    if structures:
        return ConflictInterpretationKind.STRUCTURE_ATTACK
    if takes:
        return ConflictInterpretationKind.RESOURCE_CAPTURE
    if hostile:
        actors = {row.actor_ref for row in hostile}
        if len(actors) >= 2:
            return ConflictInterpretationKind.COORDINATED_CONFLICT
        return ConflictInterpretationKind.INDIVIDUAL_VIOLENCE
    if flees:
        return ConflictInterpretationKind.RETREAT
    if assistance:
        return ConflictInterpretationKind.ASSISTANCE
    return None


def _hostile_signature(
    observations: Sequence[ConflictObservation], owner_ref: str
) -> bool:
    return any(
        row.actor_ref == owner_ref or row.other_ref == owner_ref
        for row in observations
        if row.event_class in _HOSTILE_KINDS
    )


def apply_organized_conflict_update(
    *,
    owner_id: object,
    tick: int,
    observation: object,
    prior: ConflictLedger,
    representation: object | None = None,
    diplomacy: object | None = None,
    identity: object | None = None,
    relationships: Sequence[object] | None = None,
    policy: OrganizedConflictPolicy,
) -> ConflictLedger:
    """Apply the fixed nine-step owner update pipeline.

    Steps: collect observations, collect frames, derive plans, derive
    participations, interpret, derive outcomes, retain contradictions, expire,
    enforce limits. Reads only the owner's observation and the owner's own
    carried ledger; never world state, committed events, or a peer ledger.
    """

    from agents.cognition.organized_conflict_communication import (
        ConflictAct,
        conflict_frames_from_observation,
    )
    from world.observations import Observation

    _require_tick(tick, "tick")
    if type(owner_id).__name__ != "AgentId":
        raise TypeError("owner_id must be AgentId")
    if type(prior) is not ConflictLedger:
        raise TypeError("prior must be ConflictLedger")
    if prior.owner_id != owner_id:
        raise ValueError("conflict_owner_mismatch")
    _reject_authority_input(observation, "observation")
    if not isinstance(observation, Observation):
        raise TypeError("observation must be Observation")
    _reject_authority_input(representation, "representation")
    _reject_authority_input(diplomacy, "diplomacy")
    _reject_authority_input(identity, "identity")

    owner_ref = conflict_target_token(str(getattr(owner_id, "value", owner_id)))
    notices: list[str] = []

    # 1. Collect owner-visible observations.
    new_observations = _collect_observations(
        owner_id=owner_id, tick=tick, observation=observation
    )

    # 2. Collect bounded communicated frames.
    frames = conflict_frames_from_observation(observation)
    if any(frame is None for frame in frames):
        notices.append("malformed_frame")
    valid_frames = tuple(frame for frame in frames if frame is not None)

    new_plans: list[ConflictPlan] = []
    new_participations: list[ConflictParticipation] = []
    new_interpretations: list[ConflictInterpretation] = []
    new_outcomes: list[ConflictOutcome] = []
    new_contradictions: list[ConflictContradiction] = []
    new_terminations: list[ConflictTermination] = []

    plan_by_id = {row.plan_id: row for row in prior.plans}
    interpretation_by_id = {row.interpretation_id: row for row in prior.interpretations}

    # 3. Derive plans from proposal/coordination frames.
    for frame in valid_frames:
        if frame.act not in {ConflictAct.PROPOSE, ConflictAct.COORDINATE}:
            continue
        if frame.operation is None or frame.target_kind is None:
            notices.append("malformed_frame")
            continue
        if (
            frame.target_kind is ConflictTargetKind.UNKNOWN
            or frame.target_ref == "none"
        ):
            notices.append("unresolved_target")
            continue
        if frame.act is ConflictAct.COORDINATE and frame.plan_ref != "none":
            existing = plan_by_id.get(frame.plan_ref)
            if existing is None:
                notices.append("unknown_plan")
                continue
            if (
                frame.side_ref != existing.coordinator_ref
                and frame.side_ref not in existing.participant_refs
            ):
                new_contradictions.append(
                    ConflictContradiction(
                        contradiction_id=conflict_contradiction_id(
                            owner_id,
                            ConflictContradictionKind.CONFLICTING_SIDE,
                            tick,
                            (existing.plan_id,),
                        ),
                        member_ids=(existing.plan_id, existing.plan_id),
                        kind=ConflictContradictionKind.CONFLICTING_SIDE,
                        tick=tick,
                    )
                )
                continue
            updated = ConflictPlan(
                plan_id=existing.plan_id,
                operation=_frame_operation(frame.operation),
                target_kind=_frame_target_kind(frame.target_kind),
                target_ref=frame.target_ref,
                role=_frame_role(frame.role),
                side_ref=existing.side_ref,
                participant_refs=existing.participant_refs,
                opponent_refs=existing.opponent_refs,
                coordinator_ref=existing.coordinator_ref,
                start_tick=existing.start_tick,
                end_tick=(
                    existing.end_tick
                    if frame.window_end == "none"
                    else int(frame.window_end)
                ),
                status=ConflictPlanStatus.ACTIVE,
                provenance=existing.provenance,
                evidence_refs=existing.evidence_refs,
                revision=existing.revision + 1,
                last_tick=tick,
            )
            new_plans.append(updated)
            plan_by_id[existing.plan_id] = updated
            continue
        participants = tuple(sorted(set(frame.participant_refs)))
        plan_id = conflict_plan_id(
            owner_id,
            _frame_operation(frame.operation),
            _frame_target_kind(frame.target_kind),
            frame.target_ref,
            tick,
            participants,
        )
        status = (
            ConflictPlanStatus.PROPOSED
            if frame.act is ConflictAct.PROPOSE
            else ConflictPlanStatus.ACTIVE
        )
        plan = ConflictPlan(
            plan_id=plan_id,
            operation=_frame_operation(frame.operation),
            target_kind=_frame_target_kind(frame.target_kind),
            target_ref=frame.target_ref,
            role=_frame_role(frame.role),
            side_ref=frame.side_ref,
            participant_refs=participants,
            coordinator_ref=frame.side_ref,
            start_tick=tick,
            end_tick=0 if frame.window_end == "none" else int(frame.window_end),
            status=status,
            provenance=(
                ConflictProvenance.SELF_DECLARED
                if frame.side_ref == owner_ref
                else ConflictProvenance.COMMUNICATED
            ),
            evidence_refs=(() if frame.episode_ref == "none" else (frame.episode_ref,)),
            revision=0,
            last_tick=tick,
        )
        existing = plan_by_id.get(plan_id)
        if existing is not None and existing != plan:
            new_contradictions.append(
                ConflictContradiction(
                    contradiction_id=conflict_contradiction_id(
                        owner_id,
                        ConflictContradictionKind.DUPLICATE_PLAN,
                        tick,
                        (existing.plan_id, plan.plan_id),
                    ),
                    member_ids=(existing.plan_id, plan.plan_id),
                    kind=ConflictContradictionKind.DUPLICATE_PLAN,
                    tick=tick,
                )
            )
            continue
        if existing is None:
            new_plans.append(plan)
            plan_by_id[plan_id] = plan

    # 3b. Infer an owner plan from observed repeated hostile co-participation.
    owner_body_ref = conflict_target_token(
        str(getattr(getattr(observation, "observer_id", None), "value", ""))
    )
    if not new_plans and _hostile_signature(new_observations, owner_body_ref):
        hostile = [row for row in new_observations if row.event_class in _HOSTILE_KINDS]
        actors = sorted({row.actor_ref for row in hostile})
        if len(actors) >= 2 and owner_body_ref in actors:
            participants = tuple(sorted({owner_ref, *actors}))
            opponent = next(
                (row.other_ref for row in hostile if row.other_ref), actors[-1]
            )
            existing_active = next(
                (
                    existing
                    for existing in plan_by_id.values()
                    if existing.status is ConflictPlanStatus.ACTIVE
                    and existing.operation is ConflictOperation.COORDINATED_ATTACK
                    and existing.target_kind is ConflictTargetKind.AGENT
                    and existing.target_ref == (opponent or owner_ref)
                    and existing.side_ref == owner_ref
                ),
                None,
            )
            if existing_active is not None:
                plan = replace(
                    existing_active,
                    participant_refs=tuple(
                        sorted(
                            set(existing_active.participant_refs)
                            | set(participants)
                        )
                    ),
                    revision=existing_active.revision + 1,
                    last_tick=tick,
                )
            else:
                plan = ConflictPlan(
                    plan_id=conflict_plan_id(
                        owner_id,
                        ConflictOperation.COORDINATED_ATTACK,
                        ConflictTargetKind.AGENT,
                        opponent or owner_ref,
                        tick,
                        actors,
                    ),
                    operation=ConflictOperation.COORDINATED_ATTACK,
                    target_kind=ConflictTargetKind.AGENT,
                    target_ref=opponent or owner_ref,
                    role=ConflictRole.ATTACKER,
                    side_ref=owner_ref,
                    participant_refs=participants,
                    start_tick=tick,
                    end_tick=0,
                    status=ConflictPlanStatus.ACTIVE,
                    provenance=ConflictProvenance.INFERRED,
                    last_tick=tick,
                )
            new_plans.append(plan)
            plan_by_id[plan.plan_id] = plan

    # 4. Derive participations from join/decline/withdraw frames and owner roles.
    stance_map = {
        ConflictAct.JOIN: ConflictParticipationStance.JOIN,
        ConflictAct.DECLINE: ConflictParticipationStance.DECLINE,
        ConflictAct.WITHDRAW: ConflictParticipationStance.WITHDRAW,
    }
    for frame in valid_frames:
        stance = stance_map.get(frame.act)
        if stance is None:
            continue
        if frame.plan_ref == "none" or frame.plan_ref not in plan_by_id:
            notices.append("unknown_plan")
            continue
        participant = frame.side_ref
        new_participations.append(
            ConflictParticipation(
                participation_id=conflict_participation_id(
                    frame.plan_ref, participant, stance, tick
                ),
                plan_id=frame.plan_ref,
                participant_ref=participant,
                role=_frame_role(frame.role),
                stance=stance,
                provenance=(
                    ConflictProvenance.SELF_DECLARED
                    if participant == owner_ref
                    else ConflictProvenance.COMMUNICATED
                ),
                tick=tick,
                active=stance is ConflictParticipationStance.JOIN,
            )
        )
    for plan in new_plans:
        if owner_ref in plan.participant_refs or plan.side_ref == owner_ref:
            stance = (
                ConflictParticipationStance.JOIN
                if plan.status in {ConflictPlanStatus.ACTIVE, ConflictPlanStatus.JOINED}
                else ConflictParticipationStance.UNKNOWN
            )
            new_participations.append(
                ConflictParticipation(
                    participation_id=conflict_participation_id(
                        plan.plan_id, owner_ref, stance, tick
                    ),
                    plan_id=plan.plan_id,
                    participant_ref=owner_ref,
                    role=plan.role,
                    stance=stance,
                    provenance=plan.provenance,
                    tick=tick,
                    active=stance is ConflictParticipationStance.JOIN,
                )
            )

    # 5. Interpret observed patterns as owner beliefs.
    if new_observations:
        kind = _interpret_kind(new_observations, owner_ref)
        if kind is not None:
            participants = sorted(
                {
                    ref
                    for row in new_observations
                    for ref in (row.actor_ref, row.other_ref)
                    if ref
                }
            )
            classes = sorted({row.event_class.value for row in new_observations})
            episode = ConflictEpisode(
                episode_id=conflict_episode_id(owner_id, tick, participants, classes),
                start_tick=tick,
                end_tick=tick,
                participant_refs=tuple(participants),
                event_classes=tuple(classes),
                provenance=ConflictProvenance.OBSERVED,
                last_tick=tick,
            )
            interpretation = ConflictInterpretation(
                interpretation_id=conflict_interpretation_id(
                    owner_id, episode.episode_id, kind, tick, ConflictBasis.OBSERVED
                ),
                episode_ref=episode.episode_id,
                kind=kind,
                basis=ConflictBasis.OBSERVED,
                confidence_band="mid",
                tick=tick,
                evidence_refs=tuple(row.observation_id for row in new_observations[:8]),
            )
            new_interpretations.append(interpretation)
            interpretation_by_id[interpretation.interpretation_id] = interpretation
            # Contradictory interpretations of one episode are retained.
            for existing in prior.interpretations:
                if (
                    existing.episode_ref == episode.episode_id
                    and existing.kind is not kind
                ):
                    new_contradictions.append(
                        ConflictContradiction(
                            contradiction_id=conflict_contradiction_id(
                                owner_id,
                                ConflictContradictionKind.CONTRADICTORY_INTERPRETATION,
                                tick,
                                (
                                    existing.interpretation_id,
                                    interpretation.interpretation_id,
                                ),
                            ),
                            member_ids=(
                                existing.interpretation_id,
                                interpretation.interpretation_id,
                            ),
                            kind=ConflictContradictionKind.CONTRADICTORY_INTERPRETATION,
                            tick=tick,
                        )
                    )
        else:
            episode = None
    else:
        episode = None

    # 6. Derive outcomes for observations linked to owner-active plans.
    active_plans = [
        plan
        for plan in [*prior.plans, *new_plans]
        if plan.status
        in {
            ConflictPlanStatus.PROPOSED,
            ConflictPlanStatus.JOINED,
            ConflictPlanStatus.ACTIVE,
        }
        and (plan.side_ref == owner_ref or owner_ref in plan.participant_refs)
    ]
    for row in new_observations:
        outcome_kind: ConflictOutcomeKind | None = None
        if row.event_class is ConflictObservationKind.ATTACK:
            outcome_kind = (
                ConflictOutcomeKind.HIT
                if row.success is not False
                else ConflictOutcomeKind.MISS
            )
        elif row.event_class is ConflictObservationKind.FLEE:
            outcome_kind = (
                ConflictOutcomeKind.FLEE_SUCCESS
                if row.success is not False
                else ConflictOutcomeKind.FLEE_FAILURE
            )
        elif row.event_class in _ASSISTANCE_KINDS:
            outcome_kind = ConflictOutcomeKind.ASSISTANCE
        elif row.event_class is ConflictObservationKind.TAKE:
            outcome_kind = ConflictOutcomeKind.CUSTODY_CAPTURE
        elif row.event_class is ConflictObservationKind.STRUCTURE_OPPOSITION:
            outcome_kind = ConflictOutcomeKind.STRUCTURE_OPPOSITION
        elif row.event_class is ConflictObservationKind.MOVE:
            outcome_kind = ConflictOutcomeKind.CO_MOVEMENT
        if outcome_kind is None:
            continue
        for plan in active_plans:
            if plan.target_ref not in {row.other_ref, row.actor_ref}:
                continue
            new_outcomes.append(
                ConflictOutcome(
                    outcome_id=conflict_outcome_id(
                        plan.plan_id, outcome_kind, plan.target_ref, tick
                    ),
                    plan_id=plan.plan_id,
                    kind=outcome_kind,
                    target_ref=plan.target_ref,
                    tick=tick,
                    magnitude=row.magnitude,
                )
            )

    # 7. Retain contradictions without reconciliation.
    for frame in valid_frames:
        if frame.act is not ConflictAct.PROPOSE:
            continue
        for plan in prior.plans:
            if (
                plan.target_ref == frame.target_ref
                and plan.side_ref != frame.side_ref
                and plan.status
                in {
                    ConflictPlanStatus.PROPOSED,
                    ConflictPlanStatus.JOINED,
                    ConflictPlanStatus.ACTIVE,
                }
            ):
                new_contradictions.append(
                    ConflictContradiction(
                        contradiction_id=conflict_contradiction_id(
                            owner_id,
                            ConflictContradictionKind.CONFLICTING_SIDE,
                            tick,
                            (plan.plan_id,),
                        ),
                        member_ids=(plan.plan_id, plan.plan_id),
                        kind=ConflictContradictionKind.CONFLICTING_SIDE,
                        tick=tick,
                    )
                )
    side_by_participant: dict[str, set[str]] = {}
    for plan in prior.plans:
        for ref in plan.participant_refs:
            side_by_participant.setdefault(ref, set()).add(plan.side_ref)
    for participant, sides in side_by_participant.items():
        if len(sides) > 1:
            members = tuple(
                plan.plan_id
                for plan in prior.plans
                if participant in plan.participant_refs
            )[:2]
            if len(members) == 2:
                new_contradictions.append(
                    ConflictContradiction(
                        contradiction_id=conflict_contradiction_id(
                            owner_id,
                            ConflictContradictionKind.CONFLICTING_SIDE,
                            tick,
                            members,
                        ),
                        member_ids=members,
                        kind=ConflictContradictionKind.CONFLICTING_SIDE,
                        tick=tick,
                    )
                )

    # 8. Expire stale plans; append one termination per expired plan.
    updated_plans: list[ConflictPlan] = []
    for plan in [*prior.plans, *new_plans]:
        if plan.status in {
            ConflictPlanStatus.COMPLETED,
            ConflictPlanStatus.ABANDONED,
            ConflictPlanStatus.EXPIRED,
        }:
            updated_plans.append(plan)
            continue
        expired = tick - plan.start_tick > policy.plan_ttl_ticks or (
            plan.end_tick and tick >= plan.end_tick
        )
        if expired:
            updated_plans.append(
                ConflictPlan(
                    plan_id=plan.plan_id,
                    operation=plan.operation,
                    target_kind=plan.target_kind,
                    target_ref=plan.target_ref,
                    role=plan.role,
                    side_ref=plan.side_ref,
                    participant_refs=plan.participant_refs,
                    opponent_refs=plan.opponent_refs,
                    coordinator_ref=plan.coordinator_ref,
                    start_tick=plan.start_tick,
                    end_tick=plan.end_tick,
                    status=ConflictPlanStatus.EXPIRED,
                    provenance=plan.provenance,
                    evidence_refs=plan.evidence_refs,
                    revision=plan.revision + 1,
                    last_tick=tick,
                )
            )
            new_terminations.append(
                ConflictTermination(
                    termination_id=conflict_termination_id(
                        plan.plan_id, ConflictTerminationKind.EXPIRED, tick
                    ),
                    plan_id=plan.plan_id,
                    kind=ConflictTerminationKind.EXPIRED,
                    tick=tick,
                )
            )
        else:
            updated_plans.append(plan)

    episodes = _merge_family(
        prior.episodes,
        () if episode is None else (episode,),
        "episode_id",
    )
    plans = _sorted_unique(updated_plans, "plan_id")
    participations = _merge_family(
        prior.participations, new_participations, "participation_id"
    )
    observations = _merge_family(prior.observations, new_observations, "observation_id")
    interpretations = _merge_family(
        prior.interpretations, new_interpretations, "interpretation_id"
    )
    outcomes = _merge_family(prior.outcomes, new_outcomes, "outcome_id")
    contradictions = _merge_family(
        prior.contradictions, new_contradictions, "contradiction_id"
    )
    terminations = _merge_family(prior.terminations, new_terminations, "termination_id")

    ledger = ConflictLedger(
        owner_id=owner_id,
        tick=tick,
        revision=prior.revision + 1,
        episodes=episodes,
        plans=plans,
        participations=participations,
        observations=observations,
        interpretations=interpretations,
        outcomes=outcomes,
        contradictions=contradictions,
        terminations=terminations,
        notices=tuple(sorted(set(notices))),
    )

    # 9. Enforce limits.
    ledger = enforce_organized_conflict_limits(ledger, policy)
    _LOG.debug(
        "organized_conflict_update owner_token=%s plans=%s participations=%s "
        "observations=%s interpretations=%s contradictions=%s",
        owner_ref[:8],
        len(ledger.plans),
        len(ledger.participations),
        len(ledger.observations),
        len(ledger.interpretations),
        len(ledger.contradictions),
    )
    if "unresolved_target" in ledger.notices:
        _LOG.warning("organized_conflict_unresolved_target count=1")
    if "unknown_plan" in ledger.notices:
        _LOG.warning("organized_conflict_unknown_plan count=1")
    return ledger


def record_organized_conflict_utterance(
    ledger: ConflictLedger,
    command: object,
    *,
    owner_id: object,
    tick: int,
    policy: OrganizedConflictPolicy,
) -> ConflictLedger:
    """Record one owner's own selected ``ocf_v1`` speech without command authority.

    The selected command is consumed read-only; this helper never submits,
    resolves, blocks, or executes it. Peer speech is recorded by the update
    pipeline from the observation, not here.
    """

    from agents.cognition.organized_conflict_communication import (
        ConflictAct,
        conflict_frames_from_command,
    )

    if type(ledger) is not ConflictLedger or ledger.owner_id != owner_id:
        raise ValueError("conflict_owner_mismatch")
    _require_tick(tick, "tick")
    frames = conflict_frames_from_command(command, owner_id)
    if not frames:
        return ledger
    plan_by_id = {row.plan_id: row for row in ledger.plans}
    new_plans: list[ConflictPlan] = []
    new_participations: list[ConflictParticipation] = []
    for frame in frames:
        if frame.act in {ConflictAct.PROPOSE, ConflictAct.COORDINATE}:
            if frame.operation is None or frame.target_kind is None:
                continue
            if (
                frame.target_kind is ConflictTargetKind.UNKNOWN
                or frame.target_ref == "none"
            ):
                continue
            participants = tuple(sorted(set(frame.participant_refs)))
            plan_id = conflict_plan_id(
                owner_id,
                _frame_operation(frame.operation),
                _frame_target_kind(frame.target_kind),
                frame.target_ref,
                tick,
                participants,
            )
            status = (
                ConflictPlanStatus.PROPOSED
                if frame.act is ConflictAct.PROPOSE
                else ConflictPlanStatus.ACTIVE
            )
            plan = ConflictPlan(
                plan_id=plan_id,
                operation=_frame_operation(frame.operation),
                target_kind=_frame_target_kind(frame.target_kind),
                target_ref=frame.target_ref,
                role=_frame_role(frame.role),
                side_ref=frame.side_ref,
                participant_refs=participants,
                coordinator_ref=frame.side_ref,
                start_tick=tick,
                end_tick=0 if frame.window_end == "none" else int(frame.window_end),
                status=status,
                provenance=ConflictProvenance.SELF_DECLARED,
                revision=0,
                last_tick=tick,
            )
            existing = plan_by_id.get(plan_id)
            if existing is None:
                new_plans.append(plan)
                plan_by_id[plan_id] = plan
            continue
        stance = {
            ConflictAct.JOIN: ConflictParticipationStance.JOIN,
            ConflictAct.DECLINE: ConflictParticipationStance.DECLINE,
            ConflictAct.WITHDRAW: ConflictParticipationStance.WITHDRAW,
        }.get(frame.act)
        if stance is None or frame.plan_ref not in plan_by_id:
            continue
        participant = frame.side_ref
        new_participations.append(
            ConflictParticipation(
                participation_id=conflict_participation_id(
                    frame.plan_ref, participant, stance, tick
                ),
                plan_id=frame.plan_ref,
                participant_ref=participant,
                role=_frame_role(frame.role),
                stance=stance,
                provenance=ConflictProvenance.SELF_DECLARED,
                tick=tick,
                active=stance is ConflictParticipationStance.JOIN,
            )
        )
    if not new_plans and not new_participations:
        return ledger
    updated = ConflictLedger(
        owner_id=ledger.owner_id,
        tick=tick,
        revision=ledger.revision + 1,
        episodes=ledger.episodes,
        plans=_merge_family(ledger.plans, new_plans, "plan_id"),
        participations=_merge_family(
            ledger.participations, new_participations, "participation_id"
        ),
        observations=ledger.observations,
        interpretations=ledger.interpretations,
        outcomes=ledger.outcomes,
        contradictions=ledger.contradictions,
        terminations=ledger.terminations,
        notices=ledger.notices,
    )
    return enforce_organized_conflict_limits(updated, policy)


# ---------------------------------------------------------------------------
# Caps, notices, and owner export (Task 10)
# ---------------------------------------------------------------------------


def _take_newest(
    rows: Sequence[object],
    cap: int,
    *,
    protected_ids: frozenset[str] = frozenset(),
    id_name: str = "",
) -> tuple[object, ...]:
    """Keep protected rows plus the newest remaining rows up to ``cap``.

    Content-addressed ids do not encode recency, so "newest" is the row tick
    followed by the primary id. Protected rows are never dropped; exceeding the
    cap through protected rows is a hard-cap error.
    """

    ordered = sorted(
        rows,
        key=lambda row: (
            int(getattr(row, "last_tick", getattr(row, "tick", 0))),
            str(getattr(row, id_name, "")) if id_name else "",
        ),
    )
    protected = [
        row for row in ordered if str(getattr(row, id_name, "")) in protected_ids
    ]
    if len(protected) > cap:
        _LOG.error(
            "organized_conflict_capacity_reached protected=%s cap=%s",
            len(protected),
            cap,
        )
        raise OrganizedConflictCapacityError()
    remaining = [
        row for row in ordered if str(getattr(row, id_name, "")) not in protected_ids
    ]
    keep_remaining = max(cap - len(protected), 0)
    if len(remaining) > keep_remaining:
        remaining = remaining[-keep_remaining:] if keep_remaining else []
    return tuple(
        sorted(
            [*protected, *remaining],
            key=lambda row: str(getattr(row, id_name, "")),
        )
    )


def enforce_organized_conflict_limits(
    ledger: ConflictLedger, policy: OrganizedConflictPolicy
) -> ConflictLedger:
    """Prune droppable rows in the locked order, then fail closed on hard caps.

    Terminations and contradictions are retained, so the plans and
    interpretations they reference are protected from pruning. Episodes are
    retained, so the interpretations they reference are protected too.
    """

    notices = set(ledger.notices)
    cutoff = ledger.tick - policy.plan_ttl_ticks

    active_plan_ids = {
        plan.plan_id
        for plan in ledger.plans
        if plan.status
        in {
            ConflictPlanStatus.PROPOSED,
            ConflictPlanStatus.JOINED,
            ConflictPlanStatus.ACTIVE,
        }
    }
    active_episode_refs = {
        plan.evidence_refs[0]
        for plan in ledger.plans
        if plan.plan_id in active_plan_ids and plan.evidence_refs
    }
    referenced_plan_ids = {
        row.plan_id for row in ledger.terminations
    } | {
        member
        for row in ledger.contradictions
        for member in row.member_ids
        if member.startswith(CONFLICT_PLAN_ID_PREFIX)
    }
    retained_episode_ids = {
        episode.episode_id
        for episode in ledger.episodes
        if episode.last_tick >= cutoff
        or episode.episode_id in active_episode_refs
    }
    episodes = tuple(
        episode
        for episode in ledger.episodes
        if episode.episode_id in retained_episode_ids
    )
    if len(episodes) != len(ledger.episodes):
        notices.add("organized_conflict_truncated:episodes")

    referenced_interpretation_ids = {
        member
        for row in ledger.contradictions
        for member in row.member_ids
        if member.startswith(CONFLICT_INTERPRETATION_ID_PREFIX)
    } | {
        member
        for episode in episodes
        for member in episode.interpretation_ids
    }

    observations = tuple(row for row in ledger.observations if row.tick >= cutoff)
    if len(observations) != len(ledger.observations):
        notices.add("organized_conflict_truncated:observations")

    interpretations = tuple(
        row
        for row in ledger.interpretations
        if (
            row.tick >= cutoff
            or (row.episode_ref in active_episode_refs)
            or row.interpretation_id in referenced_interpretation_ids
        )
        and (row.episode_ref is None or row.episode_ref in retained_episode_ids)
    )
    if len(interpretations) != len(ledger.interpretations):
        notices.add("organized_conflict_truncated:interpretations")

    terminal_plans = [
        plan
        for plan in ledger.plans
        if plan.status
        in {
            ConflictPlanStatus.COMPLETED,
            ConflictPlanStatus.ABANDONED,
            ConflictPlanStatus.EXPIRED,
        }
    ]
    retained_plan_ids = {
        plan.plan_id
        for plan in ledger.plans
        if plan.plan_id in active_plan_ids
        or plan.last_tick >= cutoff
        or plan.plan_id in referenced_plan_ids
    }
    if len(retained_plan_ids) != len(terminal_plans) + len(active_plan_ids):
        notices.add("organized_conflict_truncated:plans")
    plans = tuple(plan for plan in ledger.plans if plan.plan_id in retained_plan_ids)
    participations = tuple(
        row for row in ledger.participations if row.plan_id in retained_plan_ids
    )
    outcomes = tuple(row for row in ledger.outcomes if row.plan_id in retained_plan_ids)

    observations = _take_newest(  # type: ignore[assignment]
        observations,
        policy.max_observations,
        id_name="observation_id",
    )
    if (
        len(observations) == policy.max_observations
        and len(ledger.observations) > policy.max_observations
    ):
        notices.add("organized_conflict_truncated:observations")
    interpretations = _take_newest(  # type: ignore[assignment]
        interpretations,
        policy.max_interpretations,
        protected_ids=frozenset(referenced_interpretation_ids),
        id_name="interpretation_id",
    )
    plans = _take_newest(  # type: ignore[assignment]
        plans,
        policy.max_plans,
        protected_ids=frozenset(active_plan_ids | referenced_plan_ids),
        id_name="plan_id",
    )
    contradictions = _take_newest(
        ledger.contradictions,
        policy.max_contradictions,
        protected_ids=frozenset(
            row.contradiction_id for row in ledger.contradictions
        ),
        id_name="contradiction_id",
    )
    terminations = _take_newest(
        ledger.terminations,
        policy.max_terminations,
        protected_ids=frozenset(row.termination_id for row in ledger.terminations),
        id_name="termination_id",
    )

    # Participations and outcomes follow the retained plans, then hard caps.
    retained = {plan.plan_id for plan in plans}
    participations = tuple(row for row in participations if row.plan_id in retained)
    outcomes = tuple(row for row in outcomes if row.plan_id in retained)

    ledger = ConflictLedger(
        owner_id=ledger.owner_id,
        tick=ledger.tick,
        revision=ledger.revision,
        episodes=episodes,
        plans=plans,
        participations=participations,
        observations=observations,
        interpretations=interpretations,
        outcomes=outcomes,
        contradictions=contradictions,
        terminations=terminations,
        notices=tuple(sorted(notices)),
    )

    total = (
        len(ledger.episodes)
        + len(ledger.plans)
        + len(ledger.participations)
        + len(ledger.observations)
        + len(ledger.interpretations)
        + len(ledger.outcomes)
        + len(ledger.contradictions)
        + len(ledger.terminations)
    )
    if total > policy.max_total_records:
        _LOG.error(
            "organized_conflict_capacity_reached plans=%s observations=%s",
            len(ledger.plans),
            len(ledger.observations),
        )
        raise OrganizedConflictCapacityError()
    return ledger


def export_organized_conflict_ledger(ledger: ConflictLedger) -> ConflictLedger:
    """Return a detached, owner-scoped, sorted copy of one owner's ledger."""

    return ConflictLedger(
        owner_id=ledger.owner_id,
        tick=ledger.tick,
        revision=ledger.revision,
        policy_version=ledger.policy_version,
        contract_version=ledger.contract_version,
        episodes=tuple(ledger.episodes),
        plans=tuple(ledger.plans),
        participations=tuple(ledger.participations),
        observations=tuple(ledger.observations),
        interpretations=tuple(ledger.interpretations),
        outcomes=tuple(ledger.outcomes),
        contradictions=tuple(ledger.contradictions),
        terminations=tuple(ledger.terminations),
        notices=tuple(ledger.notices),
    )
