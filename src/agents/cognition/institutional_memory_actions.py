"""Voluntary consultation and bounded decoration of already selected actions.

Nothing here creates an action, adds utility, grants authority, or mutates the
ledger during planning. A selected ``Talk``/``Tell`` may carry one bounded frame;
an already selected empty ``Inscribe`` may record one. Completion alone produces
attempt/ignore receipts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Final, cast

from agents.cognition.institutional_memory import (
    InstitutionalMemoryEntry,
    InstitutionalMemoryLedger,
    InstitutionalMemorySelection,
    InstitutionalMemorySelectionKind,
    InstitutionalMemoryUse,
    InstitutionalMemoryUseDisposition,
    append_institutional_memory_use,
    set_institutional_entry_ignored,
)
from agents.cognition.institutional_memory_frames import (
    InstitutionalMemoryFrame,
    decode_institutional_marks,
    encode_institutional_marks,
    institutional_frame_parent,
    institutional_frame_relation,
    institutional_frame_root,
    parse_institutional_frame_relation,
)
from agents.models import AgentId
from world.actions import Inscribe, Talk, Tell
from world.artifacts import ArtifactContent
from world.communications import CommunicationRelation

__all__ = [
    "InstitutionalMemoryConsultation",
    "complete_institutional_memory_use",
    "consult_institutional_memory",
    "fill_institutional_inscription",
    "institutional_memory_communicate_utterance",
    "select_institutional_memory_use",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.institutional_memory_actions"
)

_MAX_RELATIONS: Final[int] = 32


@dataclass(frozen=True, slots=True)
class InstitutionalMemoryConsultation:
    """One bounded local consultation plus its proposed use receipt."""

    entries: tuple[InstitutionalMemoryEntry, ...]
    use: InstitutionalMemoryUse

    def __repr__(self) -> str:
        return (
            f"InstitutionalMemoryConsultation(entry_count={len(self.entries)}, "
            f"disposition={self.use.disposition.value!r})"
        )


def _active_entries(
    ledger: InstitutionalMemoryLedger,
) -> tuple[InstitutionalMemoryEntry, ...]:
    return tuple(
        entry
        for entry in ledger.entries
        if entry.active and not entry.ignored and entry.channel_id is not None
    )


def _newest(
    ledger: InstitutionalMemoryLedger,
    *,
    channel_id: str | None = None,
) -> InstitutionalMemoryEntry | None:
    entries = _active_entries(ledger)
    if channel_id is not None:
        entries = tuple(entry for entry in entries if entry.channel_id == channel_id)
    if not entries:
        return None
    return max(entries, key=lambda entry: (entry.acquisition_tick, entry.entry_id))


def consult_institutional_memory(
    ledger: InstitutionalMemoryLedger,
    *,
    channel_id: str,
    tick: int,
    invocation_id: str,
) -> InstitutionalMemoryConsultation | None:
    """Select the newest nonignored entry for one explicit local channel."""
    if type(ledger) is not InstitutionalMemoryLedger:
        raise TypeError("ledger must be InstitutionalMemoryLedger")
    if type(channel_id) is not str or not channel_id:
        raise ValueError("channel_id: invalid_type")
    entry = _newest(ledger, channel_id=channel_id)
    if entry is None:
        _LOG.debug(
            "institutional_consultation_skipped owner_id=%s reason=%s",
            ledger.owner_id.value,
            "no_known_entry",
        )
        return None
    return InstitutionalMemoryConsultation(
        entries=(entry,),
        use=InstitutionalMemoryUse(
            owner_id=ledger.owner_id,
            invocation_id=f"{invocation_id}:consulted",
            entry_id=entry.entry_id,
            channel_id=entry.channel_id,
            tick=tick,
            disposition=InstitutionalMemoryUseDisposition.CONSULTED,
        ),
    )


def _is_communication(command: object) -> bool:
    return type(command) in {Talk, Tell}


def _command_relations(command: object) -> tuple[CommunicationRelation, ...]:
    if type(command) not in {Talk, Tell}:
        return ()
    utterance_command = cast("Talk | Tell", command)
    return tuple(utterance_command.utterance.content.relations)


def _with_relations(
    command: object, relations: tuple[CommunicationRelation, ...]
) -> object:
    if type(command) not in {Talk, Tell}:
        return command
    utterance_command = cast("Talk | Tell", command)
    content = replace(utterance_command.utterance.content, relations=relations)
    utterance = replace(utterance_command.utterance, content=content)
    return replace(utterance_command, utterance=utterance)


def select_institutional_memory_use(
    ledger: InstitutionalMemoryLedger,
    *,
    owner_id: AgentId,
    command: object,
    teaching_enabled: bool,
    tick: int,
) -> InstitutionalMemorySelection | None:
    """Choose at most one voluntary local use for an already selected command."""
    if type(ledger) is not InstitutionalMemoryLedger:
        raise TypeError("ledger must be InstitutionalMemoryLedger")
    if ledger.owner_id != owner_id:
        raise ValueError("ledger owner_id mismatch")
    if type(teaching_enabled) is not bool:
        raise ValueError("teaching_enabled: invalid_type")
    if _is_communication(command):
        entry = _newest(ledger)
        if entry is None:
            return None
        kind = (
            InstitutionalMemorySelectionKind.TEACH
            if teaching_enabled
            else InstitutionalMemorySelectionKind.TRANSMIT
        )
        return InstitutionalMemorySelection(
            owner_id=owner_id,
            entry_id=entry.entry_id,
            channel_id=entry.channel_id,
            tick=tick,
            kind=kind,
        )
    if type(command) is Inscribe and not command.content.marks:
        entry = _newest(ledger)
        if entry is None:
            return None
        return InstitutionalMemorySelection(
            owner_id=owner_id,
            entry_id=entry.entry_id,
            channel_id=entry.channel_id,
            tick=tick,
            kind=InstitutionalMemorySelectionKind.RECORD,
        )
    return None


def _entry_frame(
    ledger: InstitutionalMemoryLedger, entry: InstitutionalMemoryEntry
) -> InstitutionalMemoryFrame | None:
    channel = next(
        (item for item in ledger.channels if item.channel_id == entry.channel_id),
        None,
    )
    if channel is None:
        return None
    declared_root = None
    for provenance in entry.provenance:
        if provenance.declared_frame_root is not None:
            declared_root = provenance.declared_frame_root
            break
    root = declared_root or institutional_frame_root(
        f"{entry.owner_id.value}|entry|{entry.entry_id}"
    )
    return InstitutionalMemoryFrame(
        binding_kind=channel.binding_kind,
        function_token=channel.public_function_token,
        context_digest="c_" + channel.context_digest,
        root=root,
        parent=institutional_frame_parent(entry.entry_id),
        facts=entry.facts,
        declared_fact_count=entry.declared_fact_count,
    )


def institutional_memory_communicate_utterance(
    command: object,
    *,
    ledger: InstitutionalMemoryLedger,
    selection: InstitutionalMemorySelection | None,
    teaching_enabled: bool,
    tick: int,
) -> object:
    """Append at most one matching institutional frame to Talk/Tell."""
    if type(ledger) is not InstitutionalMemoryLedger:
        raise TypeError("ledger must be InstitutionalMemoryLedger")
    if type(teaching_enabled) is not bool:
        raise ValueError("teaching_enabled: invalid_type")
    if not _is_communication(command) or selection is None:
        return command
    if selection.owner_id != ledger.owner_id:
        return command
    if selection.kind not in {
        InstitutionalMemorySelectionKind.TEACH,
        InstitutionalMemorySelectionKind.TRANSMIT,
    }:
        return command
    entry = next(
        (item for item in ledger.entries if item.entry_id == selection.entry_id),
        None,
    )
    if entry is None or not entry.active or entry.ignored:
        return command
    frame = _entry_frame(ledger, entry)
    if frame is None:
        return command
    relation = institutional_frame_relation(
        frame,
        teaching=selection.kind is InstitutionalMemorySelectionKind.TEACH,
    )
    if relation is None:
        _LOG.debug(
            "institutional_decoration_skipped owner_id=%s reason=%s",
            ledger.owner_id.value,
            "frame_capacity",
        )
        return command
    relations = (*_command_relations(command), relation)
    if len(relations) > _MAX_RELATIONS:
        _LOG.debug(
            "institutional_decoration_skipped owner_id=%s reason=%s",
            ledger.owner_id.value,
            "relation_capacity",
        )
        return command
    return _with_relations(command, relations)


def fill_institutional_inscription(
    command: object,
    *,
    ledger: InstitutionalMemoryLedger,
    selection: InstitutionalMemorySelection | None,
) -> object:
    """Fill only an already selected Inscribe whose content is still empty."""
    if type(command) is not Inscribe or selection is None:
        return command
    if selection.kind is not InstitutionalMemorySelectionKind.RECORD:
        return command
    if command.content.marks or command.content.relations:
        return command
    entry = next(
        (item for item in ledger.entries if item.entry_id == selection.entry_id),
        None,
    )
    if entry is None or not entry.active or entry.ignored:
        return command
    frame = _entry_frame(ledger, entry)
    if frame is None:
        return command
    marks = encode_institutional_marks(frame)
    return replace(command, content=ArtifactContent(marks=marks, relations=()))


def _matching_frame(command: object, root: str, parent: str) -> object | None:
    if type(command) not in {Talk, Tell}:
        return None
    utterance_command = cast("Talk | Tell", command)
    for relation in utterance_command.utterance.content.relations:
        frame = parse_institutional_frame_relation(relation)
        if frame is not None and frame.root == root and frame.parent == parent:
            return frame
    return None


def _matching_inscription(command: object, root: str) -> object | None:
    if type(command) is not Inscribe or not command.content.marks:
        return None
    frame = decode_institutional_marks(command.content.marks)
    if frame is None or frame.root != root:
        return None
    return frame


def _append_use(
    ledger: InstitutionalMemoryLedger,
    *,
    owner_id: AgentId,
    invocation_id: str,
    entry: InstitutionalMemoryEntry,
    tick: int,
    disposition: InstitutionalMemoryUseDisposition,
) -> InstitutionalMemoryLedger:
    key = f"{invocation_id}:{entry.entry_id}:{disposition.value}"
    if any(
        use.invocation_id == key
        and use.entry_id == entry.entry_id
        and use.disposition is disposition
        for use in ledger.uses
    ):
        return ledger
    return append_institutional_memory_use(
        ledger,
        InstitutionalMemoryUse(
            owner_id=owner_id,
            invocation_id=key,
            entry_id=entry.entry_id,
            channel_id=entry.channel_id,
            tick=tick,
            disposition=disposition,
        ),
    )


def complete_institutional_memory_use(
    ledger: InstitutionalMemoryLedger,
    selection: InstitutionalMemorySelection,
    *,
    owner_id: AgentId,
    invocation_id: str,
    final_command: object,
    tick: int,
) -> InstitutionalMemoryLedger:
    """Apply one completed selection against the effective command."""
    if type(ledger) is not InstitutionalMemoryLedger:
        raise TypeError("ledger must be InstitutionalMemoryLedger")
    if type(selection) is not InstitutionalMemorySelection:
        raise TypeError("selection must be InstitutionalMemorySelection")
    if selection.owner_id != owner_id or ledger.owner_id != owner_id:
        raise ValueError("owner mismatch")
    entry = next(
        (item for item in ledger.entries if item.entry_id == selection.entry_id),
        None,
    )
    if entry is None:
        raise ValueError("selection: unknown_entry")
    if selection.kind is InstitutionalMemorySelectionKind.IGNORE:
        updated = set_institutional_entry_ignored(
            ledger,
            entry.entry_id,
            ignored=bool(selection.ignored),
            tick=tick,
        )
        return _append_use(
            updated,
            owner_id=owner_id,
            invocation_id=invocation_id,
            entry=entry,
            tick=tick,
            disposition=(
                InstitutionalMemoryUseDisposition.IGNORED
                if selection.ignored
                else InstitutionalMemoryUseDisposition.UNIGNORED
            ),
        )
    if selection.kind is InstitutionalMemorySelectionKind.CONSULT:
        return _append_use(
            ledger,
            owner_id=owner_id,
            invocation_id=invocation_id,
            entry=entry,
            tick=tick,
            disposition=InstitutionalMemoryUseDisposition.CONSULTED,
        )
    frame = _entry_frame(ledger, entry)
    if frame is None:
        return _append_use(
            ledger,
            owner_id=owner_id,
            invocation_id=invocation_id,
            entry=entry,
            tick=tick,
            disposition=InstitutionalMemoryUseDisposition.SUPERSEDED,
        )
    disposition = InstitutionalMemoryUseDisposition.SUPERSEDED
    matched = None
    if selection.kind in {
        InstitutionalMemorySelectionKind.TEACH,
        InstitutionalMemorySelectionKind.TRANSMIT,
    }:
        matched = _matching_frame(final_command, frame.root, frame.parent)
        if matched is not None:
            disposition = (
                InstitutionalMemoryUseDisposition.TEACHING_ATTEMPT
                if selection.kind is InstitutionalMemorySelectionKind.TEACH
                else InstitutionalMemoryUseDisposition.TRANSMISSION_ATTEMPT
            )
    elif selection.kind is InstitutionalMemorySelectionKind.RECORD:
        matched = _matching_inscription(final_command, frame.root)
        if matched is not None:
            disposition = InstitutionalMemoryUseDisposition.RECORDING_ATTEMPT
    updated = _append_use(
        ledger,
        owner_id=owner_id,
        invocation_id=invocation_id,
        entry=entry,
        tick=tick,
        disposition=(
            disposition
            if disposition is not InstitutionalMemoryUseDisposition.SUPERSEDED
            else InstitutionalMemoryUseDisposition.CONSULTED
        ),
    )
    if disposition is InstitutionalMemoryUseDisposition.SUPERSEDED:
        updated = _append_use(
            updated,
            owner_id=owner_id,
            invocation_id=invocation_id,
            entry=entry,
            tick=tick,
            disposition=InstitutionalMemoryUseDisposition.SUPERSEDED,
        )
    return updated
