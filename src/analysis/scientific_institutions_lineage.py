"""Forward-only analytical lineage for stable scientific practice episodes.

Episodes are separate `sci-inst-` research identities. They are not
organization identities, offices, or world facts, and no gap is bridged without
exact adjacent evidence.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.organization_identity import (
    OrganizationIdentityAssignment,
    OrganizationTransition,
)
from analysis.scientific_institutions_contract import (
    SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
    PracticeStatus,
    ScientificInstitutionsError,
)
from analysis.scientific_institutions_detection import (
    PracticeWindowState,
    ScientificPracticeAssessment,
    ScientificPracticeRow,
)

__all__ = [
    "SCIENTIFIC_INSTITUTIONS_EPISODE_PREFIX",
    "PracticeEpisode",
    "PracticeEpisodeNode",
    "PracticeLineageKind",
    "PracticeLineageTransition",
    "ScientificPracticeLineage",
    "build_scientific_practice_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.scientific_institutions_lineage"
)

SCIENTIFIC_INSTITUTIONS_EPISODE_PREFIX: Final[str] = "sci-inst-"
_EPISODE_HEX: Final[int] = 16


class PracticeLineageKind(StrEnum):
    """Closed forward-only episode transitions."""

    EMERGED = "emerged"
    CONTINUED = "continued"
    HANDOFF = "handoff"
    SPLIT = "split"
    MERGED = "merged"
    SPLIT_MERGED = "split_merged"
    LAPSED = "lapsed"
    CONTINUITY_UNKNOWN = "continuity_unknown"
    REOBSERVED_AFTER_GAP = "reobserved_after_gap"


@dataclass(frozen=True, slots=True)
class PracticeEpisode:
    episode_id: str
    organization_id: str
    operator: str
    process_token: str
    first_stable_window: int
    last_stable_window: int
    windows: tuple[int, ...]
    carrier_tokens: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not _is_episode_id(self.episode_id):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_episode"
            )
        if self.last_stable_window < self.first_stable_window:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_episode"
            )


@dataclass(frozen=True, slots=True)
class PracticeEpisodeNode:
    episode_id: str
    window_index: int
    organization_id: str
    operator: str
    process_token: str
    actor_tokens: tuple[str, ...]
    carrier_tokens: tuple[tuple[str, str], ...]
    known_at_window: int

    def __post_init__(self) -> None:
        if not _is_episode_id(self.episode_id):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_episode"
            )
        if self.known_at_window < self.window_index:
            raise ScientificInstitutionsError(
                "scientific_institutions_known_before_observed"
            )


@dataclass(frozen=True, slots=True)
class PracticeLineageTransition:
    kind: PracticeLineageKind
    from_episode_id: str | None
    to_episode_id: str | None
    from_window: int | None
    to_window: int | None
    known_at_window: int
    from_organization_id: str | None
    to_organization_id: str | None
    carrier_tokens: tuple[tuple[str, str], ...] = ()
    organization_transition_refs: tuple[tuple[str, str, int], ...] = ()

    def __post_init__(self) -> None:
        for value in (self.from_episode_id, self.to_episode_id):
            if value is not None and not _is_episode_id(value):
                raise ScientificInstitutionsError(
                    "scientific_institutions_invalid_episode"
                )
        if self.to_window is not None and self.from_window is not None:
            if self.to_window <= self.from_window:
                raise ScientificInstitutionsError(
                    "scientific_institutions_lineage_time"
                )
        if self.known_at_window < 0:
            raise ScientificInstitutionsError(
                "scientific_institutions_lineage_time"
            )


@dataclass(frozen=True, slots=True)
class ScientificPracticeLineage:
    run_id: str
    policy_version: str
    episodes: tuple[PracticeEpisode, ...]
    nodes: tuple[PracticeEpisodeNode, ...]
    transitions: tuple[PracticeLineageTransition, ...]

    def __post_init__(self) -> None:
        identifiers = [episode.episode_id for episode in self.episodes]
        if len(set(identifiers)) != len(identifiers):
            raise ScientificInstitutionsError(
                "scientific_institutions_duplicate_episode"
            )
        node_keys = [(node.episode_id, node.window_index) for node in self.nodes]
        if len(set(node_keys)) != len(node_keys):
            raise ScientificInstitutionsError(
                "scientific_institutions_duplicate_node"
            )
        transition_keys = [
            (
                item.kind.value,
                item.from_episode_id or "",
                item.to_episode_id or "",
                item.from_window if item.from_window is not None else -1,
                item.to_window if item.to_window is not None else -1,
                item.known_at_window,
            )
            for item in self.transitions
        ]
        if len(set(transition_keys)) != len(transition_keys):
            raise ScientificInstitutionsError(
                "scientific_institutions_duplicate_transition"
            )

    def known_through(self, window_index: int) -> ScientificPracticeLineage:
        """Prefix view that hides transitions learned after the boundary."""

        return ScientificPracticeLineage(
            run_id=self.run_id,
            policy_version=self.policy_version,
            episodes=tuple(
                episode
                for episode in self.episodes
                if episode.first_stable_window <= window_index
            ),
            nodes=tuple(
                node
                for node in self.nodes
                if node.known_at_window <= window_index
            ),
            transitions=tuple(
                item
                for item in self.transitions
                if item.known_at_window <= window_index
            ),
        )


def _is_episode_id(value: str) -> bool:
    if type(value) is not str or not value.startswith(
        SCIENTIFIC_INSTITUTIONS_EPISODE_PREFIX
    ):
        return False
    suffix = value[len(SCIENTIFIC_INSTITUTIONS_EPISODE_PREFIX) :]
    return len(suffix) == _EPISODE_HEX and all(
        char in "0123456789abcdef" for char in suffix
    )


def _episode_id(
    *,
    run_id: str,
    row: ScientificPracticeRow,
) -> str:
    carrier = min(row.carrier_tokens or (("", ""),))
    payload = "\x1f".join(
        (
            SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
            run_id,
            row.organization_id,
            row.operator,
            row.process_token,
            str(row.window_index),
            carrier[0],
            carrier[1],
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{SCIENTIFIC_INSTITUTIONS_EPISODE_PREFIX}{digest[:_EPISODE_HEX]}"


def _stable_by_window(
    assessment: ScientificPracticeAssessment,
) -> dict[int, tuple[ScientificPracticeRow, ...]]:
    by_window: dict[int, list[ScientificPracticeRow]] = {}
    for row in assessment.rows:
        if row.status is not PracticeStatus.STABLE:
            continue
        by_window.setdefault(row.window_index, []).append(row)
    return {
        index: tuple(
            sorted(rows, key=lambda item: (item.organization_id, item.activity_key))
        )
        for index, rows in by_window.items()
    }


def _supported_by_window(
    assessment: ScientificPracticeAssessment,
) -> dict[int, tuple[ScientificPracticeRow, ...]]:
    by_window: dict[int, list[ScientificPracticeRow]] = {}
    for row in assessment.rows:
        if row.status not in {
            PracticeStatus.STABLE,
            PracticeStatus.SUPPORTED,
            PracticeStatus.OBSERVED_ONLY,
        }:
            continue
        by_window.setdefault(row.window_index, []).append(row)
    return {
        index: tuple(
            sorted(rows, key=lambda item: (item.organization_id, item.activity_key))
        )
        for index, rows in by_window.items()
    }


def _shared_carrier(
    left: ScientificPracticeRow, right: ScientificPracticeRow
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(set(left.surviving_carrier_tokens) & set(right.surviving_carrier_tokens))
    )


def _window_complete(
    assessment: ScientificPracticeAssessment, window_index: int
) -> bool:
    for window in assessment.windows:
        if window.window_index == window_index:
            return window.state in {
                PracticeWindowState.COMPLETE,
                PracticeWindowState.COMPLETE_EMPTY,
            }
    return False


def _window_exists(
    assessment: ScientificPracticeAssessment, window_index: int
) -> bool:
    return any(
        window.window_index == window_index for window in assessment.windows
    )


def _organization_transition_refs(
    lineage: Sequence[OrganizationTransition],
    *,
    from_id: str,
    to_id: str,
    window_index: int,
) -> tuple[tuple[str, str, int], ...]:
    refs = [
        (transition.from_id or "", transition.to_id, transition.window_index)
        for transition in lineage
        if transition.from_id == from_id
        and transition.to_id == to_id
        and transition.window_index == window_index
    ]
    return tuple(sorted(refs))


def _handoff_sources(
    supported: dict[int, tuple[ScientificPracticeRow, ...]],
    *,
    target: ScientificPracticeRow,
    window_index: int,
) -> tuple[ScientificPracticeRow, ...]:
    sources: list[ScientificPracticeRow] = []
    for candidate in supported.get(window_index - 1, ()):
        if candidate.organization_id != target.organization_id:
            continue
        if candidate.activity_key != target.activity_key:
            continue
        if candidate.status is not PracticeStatus.SUPPORTED:
            continue
        if not _shared_carrier(candidate, target):
            continue
        for prior in supported.get(window_index - 2, ()):
            if prior.organization_id == candidate.organization_id:
                continue
            if prior.activity_key != target.activity_key:
                continue
            if prior.status is not PracticeStatus.STABLE:
                continue
            if not _shared_carrier(prior, candidate):
                continue
            if not _shared_carrier(prior, target):
                continue
            sources.append(prior)
    by_org: dict[str, ScientificPracticeRow] = {}
    for row in sources:
        by_org[row.organization_id] = row
    return tuple(sorted(by_org.values(), key=lambda item: item.organization_id))


def build_scientific_practice_lineage(
    assessment: ScientificPracticeAssessment,
    organization_assignment: OrganizationIdentityAssignment,
    organization_lineage: Sequence[OrganizationTransition],
) -> ScientificPracticeLineage:
    """Derive forward-only stable-practice episodes and transition records."""

    if type(assessment) is not ScientificPracticeAssessment:
        raise ScientificInstitutionsError("scientific_institutions_invalid_assessment")
    if type(organization_assignment) is not OrganizationIdentityAssignment:
        raise ScientificInstitutionsError("scientific_institutions_invalid_assignment")
    if isinstance(organization_lineage, (str, bytes)) or not isinstance(
        organization_lineage, Sequence
    ):
        raise ScientificInstitutionsError("scientific_institutions_invalid_lineage")
    stable = _stable_by_window(assessment)
    supported = _supported_by_window(assessment)
    episodes: dict[str, PracticeEpisode] = {}
    nodes: list[PracticeEpisodeNode] = []
    transitions: list[PracticeLineageTransition] = []
    episode_by_org_key: dict[tuple[str, str, str], str] = {}
    last_stable: dict[tuple[str, str, str], int] = {}
    for window_index in sorted(stable):
        for row in stable[window_index]:
            key = (row.organization_id, row.operator, row.process_token)
            previous_id = episode_by_org_key.get(key)
            previous_row = next(
                (
                    item
                    for item in stable.get(window_index - 1, ())
                    if item.organization_id == row.organization_id
                    and item.activity_key == row.activity_key
                ),
                None,
            )
            handoff_sources = _handoff_sources(
                supported, target=row, window_index=window_index
            )
            episode_id: str
            if previous_id is not None and previous_row is not None:
                episode_id = previous_id
                shared = _shared_carrier(previous_row, row)
                transitions.append(
                    PracticeLineageTransition(
                        kind=PracticeLineageKind.CONTINUED,
                        from_episode_id=episode_id,
                        to_episode_id=episode_id,
                        from_window=window_index - 1,
                        to_window=window_index,
                        known_at_window=window_index,
                        from_organization_id=row.organization_id,
                        to_organization_id=row.organization_id,
                        carrier_tokens=shared,
                    )
                )
            else:
                episode_id = _episode_id(run_id=assessment.run_id, row=row)
                episode_by_org_key[key] = episode_id
                kind = PracticeLineageKind.EMERGED
                append_initial = True
                refs: list[tuple[str, str, int]] = []
                if handoff_sources:
                    source_ids = [
                        episode_by_org_key.get(
                            (
                                source.organization_id,
                                source.operator,
                                source.process_token,
                            )
                        )
                        for source in handoff_sources
                    ]
                    source_ids = [item for item in source_ids if item is not None]
                    targets = [
                        target
                        for target in stable.get(window_index, ())
                        if target.activity_key == row.activity_key
                    ]
                    if len(source_ids) == 1 and len(targets) == 1:
                        kind = PracticeLineageKind.HANDOFF
                    elif len(source_ids) == 1 and len(targets) > 1:
                        kind = PracticeLineageKind.SPLIT
                    elif len(source_ids) > 1 and len(targets) == 1:
                        kind = PracticeLineageKind.MERGED
                    else:
                        kind = PracticeLineageKind.SPLIT_MERGED
                    for source, source_id in zip(
                        handoff_sources, source_ids, strict=False
                    ):
                        source_refs = _organization_transition_refs(
                            organization_lineage,
                            from_id=source.organization_id,
                            to_id=row.organization_id,
                            window_index=window_index - 1,
                        )
                        if not source_refs:
                            continue
                        refs.extend(source_refs)
                        transitions.append(
                            PracticeLineageTransition(
                                kind=kind,
                                from_episode_id=source_id,
                                to_episode_id=episode_id,
                                from_window=window_index - 2,
                                to_window=window_index,
                                known_at_window=window_index,
                                from_organization_id=source.organization_id,
                                to_organization_id=row.organization_id,
                                carrier_tokens=_shared_carrier(source, row),
                                organization_transition_refs=source_refs,
                            )
                        )
                    if refs:
                        append_initial = False
                    else:
                        kind = PracticeLineageKind.EMERGED
                else:
                    gap_observed = any(
                        assessment.windows[window.window_index].state
                        is PracticeWindowState.PARTIAL
                        for window in assessment.windows
                        if window.window_index == window_index - 1
                    )
                    if gap_observed and previous_id is not None:
                        prior = episodes.get(previous_id)
                        transitions.append(
                            PracticeLineageTransition(
                                kind=PracticeLineageKind.REOBSERVED_AFTER_GAP,
                                from_episode_id=previous_id,
                                to_episode_id=episode_id,
                                from_window=(
                                    None
                                    if prior is None
                                    else prior.last_stable_window
                                ),
                                to_window=window_index,
                                known_at_window=window_index,
                                from_organization_id=row.organization_id,
                                to_organization_id=row.organization_id,
                                carrier_tokens=row.carrier_tokens,
                            )
                        )
                        append_initial = False
                if append_initial:
                    transitions.append(
                        PracticeLineageTransition(
                            kind=kind,
                            from_episode_id=None,
                            to_episode_id=episode_id,
                            from_window=None,
                            to_window=window_index,
                            known_at_window=window_index,
                            from_organization_id=None,
                            to_organization_id=row.organization_id,
                            carrier_tokens=row.carrier_tokens,
                        )
                    )
            existing = episodes.get(episode_id)
            windows = (
                tuple(sorted({*existing.windows, window_index}))
                if existing is not None
                else (window_index,)
            )
            episodes[episode_id] = PracticeEpisode(
                episode_id=episode_id,
                organization_id=row.organization_id,
                operator=row.operator,
                process_token=row.process_token,
                first_stable_window=(
                    existing.first_stable_window
                    if existing is not None
                    else window_index
                ),
                last_stable_window=window_index,
                windows=windows,
                carrier_tokens=tuple(
                    sorted(
                        {
                            *(
                                existing.carrier_tokens
                                if existing is not None
                                else ()
                            ),
                            *row.carrier_tokens,
                        }
                    )
                ),
            )
            nodes.append(
                PracticeEpisodeNode(
                    episode_id=episode_id,
                    window_index=window_index,
                    organization_id=row.organization_id,
                    operator=row.operator,
                    process_token=row.process_token,
                    actor_tokens=row.actor_tokens,
                    carrier_tokens=row.carrier_tokens,
                    known_at_window=window_index,
                )
            )
            last_stable[key] = window_index
    for (organization_id, operator, process_token), window_index in sorted(
        last_stable.items()
    ):
        episode_id = episode_by_org_key[
            (organization_id, operator, process_token)
        ]
        if not _window_exists(assessment, window_index + 1):
            continue
        if _window_complete(assessment, window_index + 1):
            has_continuation = any(
                row.organization_id == organization_id
                and row.activity_key == (operator, process_token)
                for row in stable.get(window_index + 1, ())
            )
            if not has_continuation:
                transitions.append(
                    PracticeLineageTransition(
                        kind=PracticeLineageKind.LAPSED,
                        from_episode_id=episode_id,
                        to_episode_id=None,
                        from_window=window_index,
                        to_window=window_index + 1,
                        known_at_window=window_index + 1,
                        from_organization_id=organization_id,
                        to_organization_id=None,
                    )
                )
        else:
            transitions.append(
                PracticeLineageTransition(
                    kind=PracticeLineageKind.CONTINUITY_UNKNOWN,
                    from_episode_id=episode_id,
                    to_episode_id=None,
                    from_window=window_index,
                    to_window=window_index + 1,
                    known_at_window=window_index + 1,
                    from_organization_id=organization_id,
                    to_organization_id=None,
                )
            )
    _LOG.debug(
        "scientific_practice_lineage run_id=%s episodes=%s nodes=%s transitions=%s",
        assessment.run_id,
        len(episodes),
        len(nodes),
        len(transitions),
    )
    return ScientificPracticeLineage(
        run_id=assessment.run_id,
        policy_version=SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
        episodes=tuple(
            sorted(episodes.values(), key=lambda item: item.episode_id)
        ),
        nodes=tuple(
            sorted(
                nodes,
                key=lambda item: (
                    item.window_index,
                    item.episode_id,
                ),
            )
        ),
        transitions=tuple(
            sorted(
                transitions,
                key=lambda item: (
                    item.known_at_window,
                    item.kind.value,
                    item.from_episode_id or "",
                    item.to_episode_id or "",
                ),
            )
        ),
    )
