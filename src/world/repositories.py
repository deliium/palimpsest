"""WorldEngine-owned knowledge repository containers (objective only).

Cultural labels (library / archive / sacred / …) are subjective framing only —
never stored as authoritative kind enums on these models.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("world.repositories")

__all__ = [
    "FORBIDDEN_REPOSITORY_FIELD_NAMES",
    "KnowledgeRepositoriesRuleContext",
    "KnowledgeRepository",
    "RepositoryAccessMode",
    "RepositoryIndexEntry",
    "RepositoryStatus",
    "index_repositories",
    "require_repository_access_mode",
    "require_repository_status",
]

FORBIDDEN_REPOSITORY_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "library",
        "archive",
        "sacred",
        "family_records",
        "trade_ledger",
        "librarian",
        "archivist",
        "library_institution",
        "global_archive",
        "society_library",
        "canonical_catalog",
        "true_history_index",
        "meaning",
        "interpretation",
        "truth",
        "verified",
    }
)


class RepositoryStatus(StrEnum):
    """Physical/decay status of a knowledge repository container."""

    INTACT = "intact"
    NEGLECTED = "neglected"
    INACCESSIBLE = "inaccessible"
    DESTROYED = "destroyed"


class RepositoryAccessMode(StrEnum):
    """Deterministic access gate — not institutional roles."""

    OPEN = "open"
    COLOCATED_ONLY = "colocated_only"
    FOUNDER_LIST = "founder_list"


_REPOSITORY_STATUS_VALUES: Final[frozenset[str]] = frozenset(
    status.value for status in RepositoryStatus
)
_REPOSITORY_ACCESS_MODE_VALUES: Final[frozenset[str]] = frozenset(
    mode.value for mode in RepositoryAccessMode
)


def require_repository_status(
    value: object, *, field_name: str = "status"
) -> RepositoryStatus:
    if type(value) is RepositoryStatus:
        return value
    if type(value) is str:
        if value not in _REPOSITORY_STATUS_VALUES:
            raise ValueError(
                f"unknown repository status {value!r} "
                f"(code=repository_status_invalid field={field_name})"
            )
        return RepositoryStatus(value)
    raise TypeError(f"{field_name} must be RepositoryStatus")


def require_repository_access_mode(
    value: object, *, field_name: str = "access_mode"
) -> RepositoryAccessMode:
    if type(value) is RepositoryAccessMode:
        return value
    if type(value) is str:
        if value not in _REPOSITORY_ACCESS_MODE_VALUES:
            raise ValueError(
                f"unknown repository access mode {value!r} "
                f"(code=repository_access_mode_invalid field={field_name})"
            )
        return RepositoryAccessMode(value)
    raise TypeError(f"{field_name} must be RepositoryAccessMode")


@dataclass(frozen=True, slots=True)
class RepositoryIndexEntry:
    """Imperfect organization metadata — not a truth catalog."""

    entry_id: str
    artifact_id: EntityId | None
    label_tokens: tuple[str, ...]
    revision: int

    def __post_init__(self) -> None:
        entry_id = require_stable_id(
            "RepositoryIndexEntry.entry_id", self.entry_id
        )
        object.__setattr__(self, "entry_id", entry_id)
        if self.artifact_id is not None and type(self.artifact_id) is not EntityId:
            raise TypeError("RepositoryIndexEntry.artifact_id must be EntityId or None")
        if isinstance(self.label_tokens, (str, bytes)) or not isinstance(
            self.label_tokens, Sequence
        ):
            raise TypeError("label_tokens must be a sequence")
        tokens: list[str] = []
        for index, raw in enumerate(self.label_tokens):
            token = require_stable_id(
                f"RepositoryIndexEntry.label_tokens[{index}]", raw
            )
            if token in FORBIDDEN_REPOSITORY_FIELD_NAMES:
                raise ValueError(
                    f"forbidden index label token {token!r} "
                    "(code=repository_index_forbidden_token)"
                )
            tokens.append(token)
        object.__setattr__(self, "label_tokens", tuple(tokens))
        object.__setattr__(
            self,
            "revision",
            require_exact_nonneg_int("RepositoryIndexEntry.revision", self.revision),
        )


@dataclass(frozen=True, slots=True)
class KnowledgeRepository:
    """Objective storage container for durable artifact membership."""

    repository_id: EntityId
    location_id: EntityId
    founder_ids: tuple[EntityId, ...]
    established_tick: int
    access_mode: RepositoryAccessMode
    status: RepositoryStatus = RepositoryStatus.INTACT
    structure_id: EntityId | None = None
    member_artifact_ids: tuple[EntityId, ...] = ()
    index_entries: tuple[RepositoryIndexEntry, ...] = ()
    last_maintained_tick: int = 0
    neglect_streak: int = 0

    def __post_init__(self) -> None:
        forbidden = FORBIDDEN_REPOSITORY_FIELD_NAMES.intersection(
            getattr(self, "__dataclass_fields__", {})
        )
        if forbidden:
            raise ValueError(
                f"forbidden repository fields {sorted(forbidden)!r} "
                "(code=repository_forbidden_field)"
            )
        if type(self.repository_id) is not EntityId:
            raise TypeError("repository_id must be EntityId")
        if type(self.location_id) is not EntityId:
            raise TypeError("location_id must be EntityId")
        if self.structure_id is not None and type(self.structure_id) is not EntityId:
            raise TypeError("structure_id must be EntityId or None")
        if isinstance(self.founder_ids, (str, bytes)) or not isinstance(
            self.founder_ids, Sequence
        ):
            raise TypeError("founder_ids must be a sequence")
        founders: list[EntityId] = []
        seen: set[EntityId] = set()
        for raw in self.founder_ids:
            if type(raw) is not EntityId:
                raise TypeError("founder_ids entries must be EntityId")
            if raw in seen:
                raise ValueError(
                    f"duplicate founder_id {raw.value!r} "
                    "(code=repository_founder_duplicate)"
                )
            seen.add(raw)
            founders.append(raw)
        if not founders:
            raise ValueError(
                "founder_ids must be non-empty (code=repository_founder_empty)"
            )
        object.__setattr__(self, "founder_ids", tuple(founders))
        object.__setattr__(
            self,
            "established_tick",
            require_exact_nonneg_int(
                "KnowledgeRepository.established_tick", self.established_tick
            ),
        )
        object.__setattr__(
            self,
            "access_mode",
            require_repository_access_mode(
                self.access_mode, field_name="KnowledgeRepository.access_mode"
            ),
        )
        object.__setattr__(
            self,
            "status",
            require_repository_status(
                self.status, field_name="KnowledgeRepository.status"
            ),
        )
        if isinstance(self.member_artifact_ids, (str, bytes)) or not isinstance(
            self.member_artifact_ids, Sequence
        ):
            raise TypeError("member_artifact_ids must be a sequence")
        members: list[EntityId] = []
        seen_members: set[EntityId] = set()
        for raw in self.member_artifact_ids:
            if type(raw) is not EntityId:
                raise TypeError("member_artifact_ids entries must be EntityId")
            if raw in seen_members:
                raise ValueError(
                    f"duplicate member_artifact_id {raw.value!r} "
                    "(code=repository_member_duplicate)"
                )
            seen_members.add(raw)
            members.append(raw)
        object.__setattr__(self, "member_artifact_ids", tuple(members))
        if isinstance(self.index_entries, (str, bytes)) or not isinstance(
            self.index_entries, Sequence
        ):
            raise TypeError("index_entries must be a sequence")
        entries: list[RepositoryIndexEntry] = []
        seen_entry_ids: set[str] = set()
        for raw in self.index_entries:
            if type(raw) is not RepositoryIndexEntry:
                raise TypeError("index_entries entries must be RepositoryIndexEntry")
            if raw.entry_id in seen_entry_ids:
                raise ValueError(
                    f"duplicate index entry_id {raw.entry_id!r} "
                    "(code=repository_index_entry_duplicate)"
                )
            seen_entry_ids.add(raw.entry_id)
            entries.append(raw)
        object.__setattr__(self, "index_entries", tuple(entries))
        object.__setattr__(
            self,
            "last_maintained_tick",
            require_exact_nonneg_int(
                "KnowledgeRepository.last_maintained_tick",
                self.last_maintained_tick,
            ),
        )
        object.__setattr__(
            self,
            "neglect_streak",
            require_exact_nonneg_int(
                "KnowledgeRepository.neglect_streak", self.neglect_streak
            ),
        )
        _LOG.debug(
            "repository_constructed repository_id=%s status=%s member_count=%s "
            "index_count=%s access_mode=%s",
            self.repository_id.value,
            self.status.value,
            len(self.member_artifact_ids),
            len(self.index_entries),
            self.access_mode.value,
        )


def index_repositories(
    repositories: Sequence[KnowledgeRepository],
) -> Mapping[EntityId, KnowledgeRepository]:
    """Build an immutable repository id → repository map."""
    indexed: dict[EntityId, KnowledgeRepository] = {}
    for repository in repositories:
        if type(repository) is not KnowledgeRepository:
            raise TypeError("repositories entries must be KnowledgeRepository")
        if repository.repository_id in indexed:
            raise ValueError(
                f"duplicate repository_id {repository.repository_id.value!r}"
            )
        indexed[repository.repository_id] = repository
    return MappingProxyType(indexed)


@dataclass(frozen=True, slots=True)
class KnowledgeRepositoriesRuleContext:
    """Ephemeral repository gates for evaluate/apply (not checkpointed).

    Built by WorldEngine from KnowledgeRepositoriesSpec. Absent context means
    the knowledge-repositories channel is off.
    """

    default_access_mode: str
    deposit_requires_colocation: bool
    retrieve_requires_colocation: bool
    founder_list_survives_death: bool
    max_repositories: int
    max_members_per_repository: int
    max_index_entries: int
    neglect_ticks: int
    allow_destruction: bool
    inaccessible_blocks_access: bool
    neglect_corrupts_index: bool
    index_optional: bool
    max_entries_per_index_op: int
    allow_corrupt_entries: bool

    def __post_init__(self) -> None:
        mode = require_repository_access_mode(
            self.default_access_mode, field_name="default_access_mode"
        )
        object.__setattr__(self, "default_access_mode", mode.value)
        for name in (
            "deposit_requires_colocation",
            "retrieve_requires_colocation",
            "founder_list_survives_death",
            "allow_destruction",
            "inaccessible_blocks_access",
            "neglect_corrupts_index",
            "index_optional",
            "allow_corrupt_entries",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        for name in (
            "max_repositories",
            "max_members_per_repository",
            "max_index_entries",
            "neglect_ticks",
            "max_entries_per_index_op",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(name, getattr(self, name)),
            )
