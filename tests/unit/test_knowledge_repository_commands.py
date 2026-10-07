"""Constructor and tag tests for knowledge repository AgentCommands."""

from __future__ import annotations

import pytest

from simulation.serialization import _decode_command, _encode_command
from world.actions import (
    DepositRecord,
    EstablishRepository,
    IndexRepository,
    MaintainRepository,
    RetrieveRecord,
    agent_command_tag,
    require_agent_command,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _eid(value: str) -> EntityId:
    return EntityId(value)


def test_establish_repository_defaults() -> None:
    cmd = EstablishRepository(location_id=_eid("loc-1"))
    assert agent_command_tag(cmd) == "establish_repository"
    assert cmd.access_mode is None
    assert cmd.structure_id is None
    assert require_agent_command(cmd) is cmd


def test_establish_repository_invalid_access_mode() -> None:
    with pytest.raises(ValueError, match="repository_access_mode_invalid"):
        EstablishRepository(
            location_id=_eid("loc-1"), access_mode="librarian"
        )


def test_deposit_retrieve_maintain_index_tags() -> None:
    deposit = DepositRecord(
        repository_id=_eid("repo-1"), artifact_id=_eid("art-1")
    )
    retrieve = RetrieveRecord(
        repository_id=_eid("repo-1"), artifact_id=_eid("art-1"), hold=False
    )
    maintain = MaintainRepository(
        repository_id=_eid("repo-1"), mode="destroy"
    )
    index = IndexRepository(
        repository_id=_eid("repo-1"),
        entries=({"entry_id": "e1", "artifact_id": "art-1"},),
    )
    assert agent_command_tag(deposit) == "deposit_record"
    assert agent_command_tag(retrieve) == "retrieve_record"
    assert agent_command_tag(maintain) == "maintain_repository"
    assert agent_command_tag(index) == "index_repository"
    assert retrieve.hold is False


def test_maintain_mode_invalid() -> None:
    with pytest.raises(ValueError, match="repository_maintain_mode_invalid"):
        MaintainRepository(repository_id=_eid("repo-1"), mode="archive")  # type: ignore[arg-type]


def test_command_json_round_trip_establish() -> None:
    cmd = EstablishRepository(
        location_id=_eid("loc-1"),
        access_mode="founder_list",
        structure_id=_eid("struct-1"),
    )
    encoded = _encode_command(cmd)
    decoded = _decode_command("establish_repository", encoded, path="$")
    assert type(decoded) is EstablishRepository
    assert decoded.location_id == cmd.location_id
    assert decoded.access_mode == "founder_list"
    assert decoded.structure_id == cmd.structure_id


def test_command_json_round_trip_deposit_retrieve_maintain_index() -> None:
    deposit = DepositRecord(
        repository_id=_eid("repo-1"), artifact_id=_eid("art-1")
    )
    retrieve = RetrieveRecord(
        repository_id=_eid("repo-1"), artifact_id=_eid("art-1"), hold=True
    )
    maintain = MaintainRepository(
        repository_id=_eid("repo-1"), mode="maintain"
    )
    index = IndexRepository(
        repository_id=_eid("repo-1"),
        entries=({"entry_id": "e1", "label_tokens": ["token_a"]},),
    )
    for cmd, tag in (
        (deposit, "deposit_record"),
        (retrieve, "retrieve_record"),
        (maintain, "maintain_repository"),
        (index, "index_repository"),
    ):
        round_trip = _decode_command(tag, _encode_command(cmd), path="$")
        assert type(round_trip) is type(cmd)
        assert agent_command_tag(round_trip) == tag
