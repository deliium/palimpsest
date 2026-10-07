"""Deterministic durable-record copy fidelity transforms.

Pure content transforms only. Never invent free-form tokens and never
"correct" marks toward world truth. Callers supply a private Random stream.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, Protocol

from world.artifacts import ArtifactContent, require_artifact_content

_LOG: Final[logging.Logger] = logging.getLogger("world.artifacts")

_FIDELITY_MODES: Final[frozenset[str]] = frozenset(
    {"perfect", "deterministic_mutation", "lossy"}
)

__all__ = [
    "CopyFidelityResult",
    "apply_copy_fidelity",
]


class _RandomLike(Protocol):
    def randrange(self, stop: int) -> int: ...

    def choice(self, seq: list[str]) -> str: ...

    def sample(self, population: range, k: int) -> list[int]: ...

    def randint(self, a: int, b: int) -> int: ...


@dataclass(frozen=True, slots=True)
class CopyFidelityResult:
    """Transformed child content plus bounded edit counts (no mark payloads)."""

    content: ArtifactContent
    fidelity_mode: str
    mark_edit_count: int
    relation_edit_count: int

    def __post_init__(self) -> None:
        require_artifact_content(self.content, field_name="CopyFidelityResult.content")
        if self.fidelity_mode not in _FIDELITY_MODES:
            raise ValueError(
                f"unknown fidelity_mode {self.fidelity_mode!r} "
                "(code=durable_copy_fidelity_invalid)"
            )
        if (
            isinstance(self.mark_edit_count, bool)
            or type(self.mark_edit_count) is not int
            or self.mark_edit_count < 0
        ):
            raise TypeError("mark_edit_count must be a non-negative int")
        if (
            isinstance(self.relation_edit_count, bool)
            or type(self.relation_edit_count) is not int
            or self.relation_edit_count < 0
        ):
            raise TypeError("relation_edit_count must be a non-negative int")


def apply_copy_fidelity(
    content: ArtifactContent,
    *,
    fidelity_mode: str,
    max_mark_edits: int,
    max_relation_edits: int,
    rng: _RandomLike | None = None,
) -> CopyFidelityResult:
    """Return child content under the closed fidelity mode.

    ``perfect`` is identity. ``deterministic_mutation`` may drop/swap marks and
    drop trailing relations within caps. ``lossy`` always reduces marks when
    any exist (within caps) and drops trailing relations.
    """
    require_artifact_content(content, field_name="apply_copy_fidelity.content")
    if fidelity_mode not in _FIDELITY_MODES:
        raise ValueError(
            f"unknown fidelity_mode {fidelity_mode!r} "
            "(code=durable_copy_fidelity_invalid)"
        )
    if isinstance(max_mark_edits, bool) or type(max_mark_edits) is not int:
        raise TypeError("max_mark_edits must be int")
    if max_mark_edits < 0:
        raise ValueError("max_mark_edits must be non-negative")
    if isinstance(max_relation_edits, bool) or type(max_relation_edits) is not int:
        raise TypeError("max_relation_edits must be int")
    if max_relation_edits < 0:
        raise ValueError("max_relation_edits must be non-negative")

    parent_marks = len(content.marks)
    parent_relations = len(content.relations)

    if fidelity_mode == "perfect":
        result = CopyFidelityResult(
            content=content,
            fidelity_mode=fidelity_mode,
            mark_edit_count=0,
            relation_edit_count=0,
        )
    elif fidelity_mode == "deterministic_mutation":
        if rng is None:
            raise TypeError("deterministic_mutation requires rng")
        result = _mutate(content, max_mark_edits, max_relation_edits, rng)
    else:
        if rng is None:
            raise TypeError("lossy requires rng")
        result = _lossy(content, max_mark_edits, max_relation_edits, rng)

    _LOG.debug(
        "durable_copy_fidelity mode=%s parent_mark_count=%s child_mark_count=%s "
        "edit_counts=%s,%s parent_relation_count=%s child_relation_count=%s",
        result.fidelity_mode,
        parent_marks,
        len(result.content.marks),
        result.mark_edit_count,
        result.relation_edit_count,
        parent_relations,
        len(result.content.relations),
    )
    return result


def _mutate(
    content: ArtifactContent,
    max_mark_edits: int,
    max_relation_edits: int,
    rng: _RandomLike,
) -> CopyFidelityResult:
    marks = list(content.marks)
    mark_edits = 0
    while mark_edits < max_mark_edits and marks:
        ops: list[str] = ["drop"]
        if len(marks) >= 2:
            ops.append("swap")
        op = rng.choice(ops)
        if op == "drop":
            idx = rng.randrange(len(marks))
            marks.pop(idx)
        else:
            i, j = rng.sample(range(len(marks)), 2)
            marks[i], marks[j] = marks[j], marks[i]
        mark_edits += 1

    relations = list(content.relations)
    relation_edits = min(max_relation_edits, len(relations))
    if relation_edits:
        relations = relations[: len(relations) - relation_edits]

    return CopyFidelityResult(
        content=ArtifactContent(marks=tuple(marks), relations=tuple(relations)),
        fidelity_mode="deterministic_mutation",
        mark_edit_count=mark_edits,
        relation_edit_count=relation_edits,
    )


def _lossy(
    content: ArtifactContent,
    max_mark_edits: int,
    max_relation_edits: int,
    rng: _RandomLike,
) -> CopyFidelityResult:
    marks = list(content.marks)
    mark_edits = 0
    if marks and max_mark_edits > 0:
        drop = rng.randint(1, min(max_mark_edits, len(marks)))
        marks = marks[: len(marks) - drop]
        mark_edits = drop

    relations = list(content.relations)
    relation_edits = min(max_relation_edits, len(relations))
    if relation_edits:
        relations = relations[: len(relations) - relation_edits]

    return CopyFidelityResult(
        content=ArtifactContent(marks=tuple(marks), relations=tuple(relations)),
        fidelity_mode="lossy",
        mark_edit_count=mark_edits,
        relation_edit_count=relation_edits,
    )
