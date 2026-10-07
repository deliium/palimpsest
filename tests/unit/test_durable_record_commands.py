"""Constructor and codec tests for durable record AgentCommands."""

from __future__ import annotations

import pytest

from simulation.serialization import _decode_command, _encode_command
from world.actions import (
    AnnotateRecord,
    CopyRecord,
    DamageRecord,
    Inscribe,
    agent_command_tag,
    require_agent_command,
)
from world.artifacts import ArtifactContent, ArtifactKind, DurableRecordGenre
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _content(*marks: str) -> ArtifactContent:
    return ArtifactContent(marks=marks)


def test_inscribe_optional_genre_and_reject_mark_genre() -> None:
    cmd = Inscribe(
        ArtifactKind.NOTE,
        _content("warn"),
        hold=False,
        record_genre=DurableRecordGenre.WARNING,
    )
    assert cmd.record_genre is DurableRecordGenre.WARNING
    assert agent_command_tag(cmd) == "inscribe"
    with pytest.raises(ValueError, match="durable_genre_kind_mismatch"):
        Inscribe(
            ArtifactKind.MARK,
            _content("glyph"),
            record_genre=DurableRecordGenre.WARNING,
        )


def test_copy_annotate_damage_constructors() -> None:
    copy = CopyRecord(EntityId("art-a"), hold=True, fidelity_override="lossy")
    annotate = AnnotateRecord(EntityId("art-a"), _content("note"))
    damage = DamageRecord(EntityId("art-a"), "partial_loss")
    assert agent_command_tag(copy) == "copy_record"
    assert agent_command_tag(annotate) == "annotate_record"
    assert agent_command_tag(damage) == "damage_record"
    assert require_agent_command(copy) is copy


def test_copy_fidelity_and_damage_mode_reject() -> None:
    with pytest.raises(ValueError, match="durable_copy_fidelity_invalid"):
        CopyRecord(EntityId("art-a"), fidelity_override="random")
    with pytest.raises(ValueError, match="durable_damage_mode_invalid"):
        DamageRecord(EntityId("art-a"), "explode")  # type: ignore[arg-type]


def test_command_json_round_trip() -> None:
    commands = (
        Inscribe(
            ArtifactKind.RECORD,
            _content("a"),
            record_genre=DurableRecordGenre.CHRONICLE,
        ),
        CopyRecord(EntityId("art-a"), hold=False, fidelity_override=None),
        AnnotateRecord(EntityId("art-a"), _content("ann")),
        DamageRecord(EntityId("art-a"), "destroy"),
    )
    for command in commands:
        tag = agent_command_tag(command)
        encoded = _encode_command(command)
        decoded = _decode_command(tag, encoded, path="$")
        assert type(decoded) is type(command)
        assert agent_command_tag(decoded) == tag  # type: ignore[arg-type]


def test_legacy_inscribe_without_genre_still_decodes() -> None:
    decoded = _decode_command(
        "inscribe",
        {
            "content": {"marks": ["a"], "relations": []},
            "hold": False,
            "kind": "note",
        },
        path="$",
    )
    assert type(decoded) is Inscribe
    assert decoded.record_genre is None
