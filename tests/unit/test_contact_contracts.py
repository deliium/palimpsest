"""Neutral cultural-contact contracts: exact validation and detached copies."""

from __future__ import annotations

import dataclasses

import pytest

from world.contact import ContactMode, CulturalContactSpec
from world.events import ContactRecorded
from world.identifiers import EntityId


def _ids(*values: str) -> tuple[EntityId, ...]:
    return tuple(EntityId(value) for value in values)


def _journey_contact(**overrides: object) -> ContactRecorded:
    values: dict[str, object] = {
        "relocation_kind": "journey_arrived",
        "journey_id": "journey-1",
        "location_id": EntityId("loc-b"),
        "participant_ids": _ids("body-1", "body-2"),
        "present_ids": _ids("body-3"),
        "origin_region_id": "north",
        "destination_region_id": "south",
    }
    values.update(overrides)
    return ContactRecorded(**values)  # type: ignore[arg-type]


def test_contact_mode_values_are_closed() -> None:
    assert set(ContactMode) == {ContactMode.DISABLED, ContactMode.DETERMINISTIC}


def test_spec_round_trips_and_reports_enabled() -> None:
    spec = CulturalContactSpec(mode=ContactMode.DETERMINISTIC)
    assert spec.enabled is True
    assert spec.canonical() == {"mode": "deterministic"}
    assert CulturalContactSpec(mode=ContactMode.DISABLED).enabled is False


def test_spec_rejects_unknown_or_wrong_mode() -> None:
    with pytest.raises(ValueError, match="invalid_mode"):
        CulturalContactSpec(mode="deterministic")  # type: ignore[arg-type]


def test_journey_contact_round_trips_and_does_not_alias_caller_lists() -> None:
    participants = list(_ids("body-2", "body-1"))
    present = list(_ids("body-3"))
    contact = ContactRecorded(
        relocation_kind="journey_arrived",
        journey_id="journey-1",
        location_id=EntityId("loc-b"),
        participant_ids=tuple(sorted(participants, key=lambda item: item.value)),
        present_ids=present,
        origin_region_id="north",
        destination_region_id="south",
    )
    assert contact.participant_ids == _ids("body-1", "body-2")
    present.append(EntityId("body-4"))
    participants.append(EntityId("body-9"))
    assert contact.present_ids == _ids("body-3")
    assert contact.participant_ids == _ids("body-1", "body-2")
    assert dataclasses.replace(contact, present_ids=_ids("body-5")).present_ids == _ids(
        "body-5"
    )


def test_flee_and_move_omit_journey_id() -> None:
    for kind in ("fled", "move"):
        contact = _journey_contact(relocation_kind=kind, journey_id=None)
        assert contact.journey_id is None
        assert contact.relocation_kind == kind


def test_journey_arrived_requires_journey_id() -> None:
    with pytest.raises(ValueError, match="missing_journey_id"):
        _journey_contact(journey_id=None)


def test_non_journey_rejects_journey_id() -> None:
    with pytest.raises(ValueError, match="unexpected_journey_id"):
        _journey_contact(relocation_kind="fled")


def test_unknown_relocation_kind_rejects() -> None:
    with pytest.raises(ValueError, match="invalid_relocation_kind"):
        _journey_contact(relocation_kind="teleport")


def test_sets_must_be_nonempty_unique_sorted_and_disjoint() -> None:
    with pytest.raises(ValueError, match="empty_participants"):
        _journey_contact(participant_ids=())
    with pytest.raises(ValueError, match="empty_present"):
        _journey_contact(present_ids=())
    with pytest.raises(ValueError, match="unsorted_participants"):
        _journey_contact(participant_ids=_ids("body-2", "body-1"))
    with pytest.raises(ValueError, match="unsorted_present"):
        _journey_contact(present_ids=_ids("body-4", "body-3"))
    with pytest.raises(ValueError, match="overlapping_ids"):
        _journey_contact(present_ids=_ids("body-1"))


def test_duplicate_ids_reject() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _journey_contact(participant_ids=_ids("body-1", "body-1"))


def test_equal_or_missing_regions_reject() -> None:
    with pytest.raises(ValueError, match="equal_regions"):
        _journey_contact(destination_region_id="north")
    with pytest.raises(ValueError):
        _journey_contact(origin_region_id="")


def test_malformed_ids_reject() -> None:
    with pytest.raises(TypeError):
        _journey_contact(location_id="loc-b")
    with pytest.raises(TypeError):
        _journey_contact(participant_ids=("body-1",))
    with pytest.raises(ValueError):
        _journey_contact(origin_region_id=" north")


def test_contract_has_no_group_attitude_or_policy_fields() -> None:
    fields = {item.name for item in dataclasses.fields(ContactRecorded)}
    assert fields == {
        "relocation_kind",
        "location_id",
        "participant_ids",
        "present_ids",
        "origin_region_id",
        "destination_region_id",
        "journey_id",
        "kind",
    }
