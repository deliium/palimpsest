"""Voluntary consultation and bounded decoration of selected commands."""

from __future__ import annotations

from dataclasses import replace

from agents.cognition.institutional_memory import (
    InstitutionalBindingKind,
    InstitutionalChannel,
    InstitutionalFact,
    InstitutionalMemoryChannel,
    InstitutionalMemoryEntry,
    InstitutionalMemoryLedger,
    InstitutionalMemorySelection,
    InstitutionalMemorySelectionKind,
    InstitutionalMemoryUseDisposition,
    InstitutionalProvenance,
    empty_institutional_memory_ledger,
    institutional_channel_id,
    institutional_entry_id,
    set_institutional_entry_ignored,
)
from agents.cognition.institutional_memory_actions import (
    complete_institutional_memory_use,
    consult_institutional_memory,
    fill_institutional_inscription,
    institutional_memory_communicate_utterance,
    select_institutional_memory_use,
)
from agents.cognition.institutional_memory_frames import (
    parse_institutional_frame_relation,
)
from agents.models import AgentId
from world.actions import Ask, Inscribe, Talk, Wait
from world.artifacts import ArtifactContent, ArtifactKind
from world.communications import (
    CommunicationRelation,
    origin_utterance,
)
from world.identifiers import EntityId

_OWNER = AgentId("alice")
_INCEPTION = "a" * 64
_OFFICE = "b" * 64
_CONTEXT = "c" * 16
_FUNCTION = "exchange_aaaaaaaa"


def _channel() -> InstitutionalChannel:
    return InstitutionalChannel(
        owner_id=_OWNER,
        channel_id=institutional_channel_id(
            _OWNER, InstitutionalBindingKind.ROLE, _INCEPTION
        ),
        binding_kind=InstitutionalBindingKind.ROLE,
        inception_reference=_INCEPTION,
        current_local_reference=_OFFICE,
        public_function_token=_FUNCTION,
        context_digest=_CONTEXT,
        first_tick=1,
        last_tick=1,
        revision_count=0,
    )


def _entry(
    channel: InstitutionalChannel,
    *,
    ordinal: int = 0,
    tick: int = 1,
    ignored: bool = False,
) -> InstitutionalMemoryEntry:
    return InstitutionalMemoryEntry(
        owner_id=_OWNER,
        entry_id=institutional_entry_id(_OWNER, channel.channel_id, ordinal),
        channel_id=channel.channel_id,
        ordinal=ordinal,
        revision=0,
        facts=(InstitutionalFact("trade", "owes", "grain"),),
        declared_fact_count=1,
        acquisition_tick=tick,
        confidence=0.7,
        distorted=False,
        partial=False,
        active=True,
        ignored=ignored,
        provenance=(
            InstitutionalProvenance(
                immediate_channel=InstitutionalMemoryChannel.OBSERVATION
            ),
        ),
    )


def _ledger(
    *, entry_count: int = 1
) -> tuple[InstitutionalMemoryLedger, InstitutionalChannel]:
    channel = _channel()
    entries = tuple(
        _entry(channel, ordinal=index, tick=index + 1) for index in range(entry_count)
    )
    return (
        InstitutionalMemoryLedger(
            owner_id=_OWNER, channels=(channel,), entries=entries
        ),
        channel,
    )


def _talk() -> Talk:
    utterance = origin_utterance(
        text="the record says so",
        speaker_id=EntityId("alice-body"),
        relations=(CommunicationRelation("trade", "offers", "salt"),),
    )
    return Talk(recipient_id=EntityId("bob-body"), utterance=utterance)


def test_consultation_selects_newest_nonignored_entry() -> None:
    ledger, channel = _ledger(entry_count=3)
    consultation = consult_institutional_memory(
        ledger, channel_id=channel.channel_id, tick=4, invocation_id="inv"
    )
    assert consultation is not None
    assert len(consultation.entries) == 1
    assert consultation.entries[0].ordinal == 2
    assert consultation.use.disposition is InstitutionalMemoryUseDisposition.CONSULTED


def test_consultation_skips_ignored_and_unbound_entries() -> None:
    ledger, channel = _ledger()
    ignored = set_institutional_entry_ignored(
        ledger, ledger.entries[0].entry_id, ignored=True, tick=2
    )
    assert (
        consult_institutional_memory(
            ignored, channel_id=channel.channel_id, tick=2, invocation_id="inv"
        )
        is None
    )
    unbound = replace(
        ledger,
        entries=(
            replace(
                ledger.entries[0],
                channel_id=None,
                entry_id=institutional_entry_id(_OWNER, None, 0),
            ),
        ),
    )
    assert (
        consult_institutional_memory(
            unbound, channel_id=channel.channel_id, tick=2, invocation_id="inv"
        )
        is None
    )


def test_default_selector_teaches_or_transmits_but_not_ask() -> None:
    ledger, _ = _ledger()
    telling = select_institutional_memory_use(
        ledger,
        owner_id=_OWNER,
        command=_talk(),
        teaching_enabled=True,
        tick=2,
    )
    assert telling is not None
    assert telling.kind is InstitutionalMemorySelectionKind.TEACH
    transmitting = select_institutional_memory_use(
        ledger,
        owner_id=_OWNER,
        command=_talk(),
        teaching_enabled=False,
        tick=2,
    )
    assert transmitting is not None
    assert transmitting.kind is InstitutionalMemorySelectionKind.TRANSMIT
    asking = Ask(
        recipient_id=EntityId("bob-body"),
        utterance=_talk().utterance,
    )
    assert (
        select_institutional_memory_use(
            ledger,
            owner_id=_OWNER,
            command=asking,
            teaching_enabled=False,
            tick=2,
        )
        is None
    )


def test_decoration_preserves_native_envelope_and_other_relations() -> None:
    ledger, _ = _ledger()
    command = _talk()
    selection = select_institutional_memory_use(
        ledger,
        owner_id=_OWNER,
        command=command,
        teaching_enabled=False,
        tick=2,
    )
    assert selection is not None
    decorated = institutional_memory_communicate_utterance(
        command,
        ledger=ledger,
        selection=selection,
        teaching_enabled=False,
        tick=2,
    )
    assert type(decorated) is Talk
    assert decorated.utterance.declared is command.utterance.declared
    assert decorated.utterance.content.text == command.utterance.content.text
    assert decorated.recipient_id == command.recipient_id
    assert len(decorated.utterance.content.relations) == 2
    frame = parse_institutional_frame_relation(decorated.utterance.content.relations[1])
    assert frame is not None
    assert frame.facts[0].object == "grain"


def test_full_relation_capacity_leaves_command_unchanged() -> None:
    ledger, _ = _ledger()
    base = _talk()
    relations = tuple(
        CommunicationRelation("trade", "offers", f"item_{index}") for index in range(32)
    )
    command = replace(
        base,
        utterance=replace(
            base.utterance,
            content=replace(base.utterance.content, relations=relations),
        ),
    )
    selection = select_institutional_memory_use(
        ledger,
        owner_id=_OWNER,
        command=command,
        teaching_enabled=False,
        tick=2,
    )
    assert selection is not None
    assert (
        institutional_memory_communicate_utterance(
            command,
            ledger=ledger,
            selection=selection,
            teaching_enabled=False,
            tick=2,
        )
        is command
    )


def test_empty_inscription_is_filled_but_nonempty_is_not() -> None:
    ledger, _ = _ledger()
    command = Inscribe(kind=ArtifactKind.RECORD, content=ArtifactContent())
    selection = select_institutional_memory_use(
        ledger,
        owner_id=_OWNER,
        command=command,
        teaching_enabled=False,
        tick=2,
    )
    assert selection is not None
    assert selection.kind is InstitutionalMemorySelectionKind.RECORD
    filled = fill_institutional_inscription(command, ledger=ledger, selection=selection)
    assert type(filled) is Inscribe
    assert len(filled.content.marks) == 10
    assert filled.kind is ArtifactKind.RECORD

    nonempty = Inscribe(
        kind=ArtifactKind.RECORD,
        content=ArtifactContent(marks=("trade",)),
    )
    assert (
        fill_institutional_inscription(nonempty, ledger=ledger, selection=selection)
        is nonempty
    )


def test_completion_records_attempt_or_superseded() -> None:
    ledger, _ = _ledger()
    command = _talk()
    selection = select_institutional_memory_use(
        ledger,
        owner_id=_OWNER,
        command=command,
        teaching_enabled=False,
        tick=2,
    )
    assert selection is not None
    decorated = institutional_memory_communicate_utterance(
        command,
        ledger=ledger,
        selection=selection,
        teaching_enabled=False,
        tick=2,
    )
    completed = complete_institutional_memory_use(
        ledger,
        selection,
        owner_id=_OWNER,
        invocation_id="inv",
        final_command=decorated,
        tick=2,
    )
    assert [use.disposition for use in completed.uses] == [
        InstitutionalMemoryUseDisposition.TRANSMISSION_ATTEMPT
    ]
    superseded = complete_institutional_memory_use(
        ledger,
        selection,
        owner_id=_OWNER,
        invocation_id="inv-2",
        final_command=Wait(),
        tick=2,
    )
    assert {use.disposition for use in superseded.uses} == {
        InstitutionalMemoryUseDisposition.CONSULTED,
        InstitutionalMemoryUseDisposition.SUPERSEDED,
    }


def test_ignore_and_unignore_are_completion_only() -> None:
    ledger, _ = _ledger()
    entry = ledger.entries[0]
    ignore = InstitutionalMemorySelection(
        owner_id=_OWNER,
        entry_id=entry.entry_id,
        channel_id=entry.channel_id,
        tick=2,
        kind=InstitutionalMemorySelectionKind.IGNORE,
        ignored=True,
    )
    ignored = complete_institutional_memory_use(
        ledger,
        ignore,
        owner_id=_OWNER,
        invocation_id="inv",
        final_command=Wait(),
        tick=2,
    )
    assert ignored.entries[0].ignored is True
    assert ignored.uses[0].disposition is InstitutionalMemoryUseDisposition.IGNORED

    unignore = replace(ignore, ignored=False)
    unignored = complete_institutional_memory_use(
        ignored,
        unignore,
        owner_id=_OWNER,
        invocation_id="inv-2",
        final_command=Wait(),
        tick=3,
    )
    assert unignored.entries[0].ignored is False
    assert unignored.uses[-1].disposition is InstitutionalMemoryUseDisposition.UNIGNORED


def test_completion_rejects_foreign_selection() -> None:
    ledger, _ = _ledger()
    selection = InstitutionalMemorySelection(
        owner_id=AgentId("bob"),
        entry_id=ledger.entries[0].entry_id,
        channel_id=ledger.entries[0].channel_id,
        tick=2,
        kind=InstitutionalMemorySelectionKind.CONSULT,
    )
    try:
        complete_institutional_memory_use(
            ledger,
            selection,
            owner_id=_OWNER,
            invocation_id="inv",
            final_command=Wait(),
            tick=2,
        )
    except ValueError:
        pass
    else:  # pragma: no cover - explicit failure
        raise AssertionError("foreign selection must fail")


def test_disabled_empty_ledger_returns_no_selection() -> None:
    ledger = empty_institutional_memory_ledger(_OWNER)
    assert (
        select_institutional_memory_use(
            ledger,
            owner_id=_OWNER,
            command=_talk(),
            teaching_enabled=True,
            tick=2,
        )
        is None
    )


def test_ask_is_never_decorated() -> None:
    ledger, _ = _ledger()
    ask = Ask(recipient_id=EntityId("bob-body"), utterance=_talk().utterance)
    selection = InstitutionalMemorySelection(
        owner_id=_OWNER,
        entry_id=ledger.entries[0].entry_id,
        channel_id=ledger.entries[0].channel_id,
        tick=2,
        kind=InstitutionalMemorySelectionKind.TRANSMIT,
    )
    assert (
        institutional_memory_communicate_utterance(
            ask,
            ledger=ledger,
            selection=selection,
            teaching_enabled=False,
            tick=2,
        )
        is ask
    )
