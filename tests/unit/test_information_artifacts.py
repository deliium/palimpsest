"""Unit tests for objective information-artifact types and commands."""

from __future__ import annotations

import pytest

from tests.physical_helpers import two_location_fixture
from world.actions import (
    Amend,
    Erase,
    Inscribe,
    TransferArtifact,
    require_agent_command,
)
from world.artifacts import (
    MAX_ARTIFACT_MARKS,
    MAX_ARTIFACT_RELATIONS,
    MAX_HELD_ARTIFACTS_PER_BODY,
    ArtifactContent,
    ArtifactKind,
    ArtifactRelation,
    InformationArtifact,
)
from world.identifiers import EntityId, WorldRevision
from world._state import WorldState

pytestmark = pytest.mark.unit


def _eid(value: str) -> EntityId:
    return EntityId(value)


def _content(
    *marks: str,
    relations: tuple[ArtifactRelation, ...] = (),
) -> ArtifactContent:
    return ArtifactContent(marks=marks, relations=relations)


def test_empty_content_is_legal() -> None:
    content = ArtifactContent()
    assert content.marks == ()
    assert content.relations == ()


def test_content_rejects_invalid_tokens_and_overlong_tuples() -> None:
    with pytest.raises(ValueError, match="artifact_content_invalid"):
        ArtifactContent(marks=("BadToken",))
    with pytest.raises(ValueError, match="artifact_content_invalid"):
        ArtifactContent(marks=tuple(f"m{i}" for i in range(MAX_ARTIFACT_MARKS + 1)))
    with pytest.raises(ValueError, match="artifact_content_invalid"):
        ArtifactContent(
            relations=tuple(
                ArtifactRelation("a", "at", "b")
                for _ in range(MAX_ARTIFACT_RELATIONS + 1)
            )
        )


def test_portable_and_fixed_placement_rules() -> None:
    content = _content("water", "north")
    note = InformationArtifact(
        artifact_id=_eid("art-note"),
        kind=ArtifactKind.NOTE,
        author_id=_eid("body-a"),
        created_tick=0,
        content=content,
        location_id=_eid("loc-a"),
    )
    assert note.holder_id is None
    held = InformationArtifact(
        artifact_id=_eid("art-held"),
        kind=ArtifactKind.MARK,
        author_id=_eid("body-a"),
        created_tick=0,
        content=content,
        holder_id=_eid("body-a"),
    )
    assert held.location_id is None
    with pytest.raises(ValueError, match="artifact_content_invalid"):
        InformationArtifact(
            artifact_id=_eid("art-both"),
            kind=ArtifactKind.NOTE,
            author_id=_eid("body-a"),
            created_tick=0,
            content=content,
            location_id=_eid("loc-a"),
            holder_id=_eid("body-a"),
        )
    with pytest.raises(ValueError, match="artifact_not_portable"):
        InformationArtifact(
            artifact_id=_eid("art-sign"),
            kind=ArtifactKind.SIGN,
            author_id=_eid("body-a"),
            created_tick=0,
            content=content,
            holder_id=_eid("body-a"),
        )


def test_world_state_artifacts_default_empty_and_hold_cap() -> None:
    fixture = two_location_fixture()
    empty = fixture.as_state()
    assert dict(empty.artifacts) == {}

    body_id = fixture.bodies[0].entity_id
    held = [
        InformationArtifact(
            artifact_id=_eid(f"art-{i}"),
            kind=ArtifactKind.NOTE,
            author_id=body_id,
            created_tick=0,
            content=_content("cue"),
            holder_id=body_id,
        )
        for i in range(MAX_HELD_ARTIFACTS_PER_BODY + 1)
    ]
    with pytest.raises(ValueError, match="artifact_hold_cap"):
        WorldState(
            WorldRevision(0),
            locations=fixture.locations,
            bodies=fixture.bodies,
            weather=fixture.weather,
            artifacts=tuple(held),
        )


def test_inscribe_amend_erase_transfer_command_rules() -> None:
    content = _content("water")
    from world.actions import agent_command_tag

    cmd = Inscribe(kind=ArtifactKind.NOTE, content=content, hold=True)
    assert cmd.kind is ArtifactKind.NOTE
    assert agent_command_tag(cmd) == "inscribe"
    assert require_agent_command(cmd) is cmd
    with pytest.raises(ValueError, match="invalid_artifact_hold"):
        Inscribe(kind=ArtifactKind.SIGN, content=content, hold=True)
    amend = Amend(artifact_id=_eid("art-1"), content=content)
    assert amend.kind == "amend"
    erase = Erase(artifact_id=_eid("art-1"))
    assert erase.kind == "erase"
    deposit = TransferArtifact(artifact_id=_eid("art-1"), mode="deposit")
    assert deposit.kind == "transfer_artifact"
    with pytest.raises(ValueError, match="artifact_transfer_mode_invalid"):
        TransferArtifact(
            artifact_id=_eid("art-1"),
            mode="deposit",
            recipient_id=_eid("body-b"),
        )
    with pytest.raises(ValueError, match="artifact_transfer_mode_invalid"):
        TransferArtifact(artifact_id=_eid("art-1"), mode="give")
    give = TransferArtifact(
        artifact_id=_eid("art-1"),
        mode="give",
        recipient_id=_eid("body-b"),
    )
    assert give.recipient_id == _eid("body-b")


def test_held_artifact_not_in_inventory_agreement() -> None:
    """Held artifacts are parallel to inventory; no inventory membership required."""
    fixture = two_location_fixture()
    body = fixture.bodies[0]
    artifact = InformationArtifact(
        artifact_id=_eid("art-1"),
        kind=ArtifactKind.MAP,
        author_id=body.entity_id,
        created_tick=0,
        content=_content("path"),
        holder_id=body.entity_id,
    )
    state = WorldState(
        WorldRevision(0),
        locations=fixture.locations,
        bodies=fixture.bodies,
        weather=fixture.weather,
        artifacts=(artifact,),
    )
    assert artifact.artifact_id in state.artifacts
    assert artifact.artifact_id not in body.inventory
    assert state.artifacts[artifact.artifact_id].holder_id == body.entity_id
