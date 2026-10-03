"""World authority stays free of myth and narrative predicates."""

from __future__ import annotations

import inspect
import logging

import pytest

from experiments.cultural_narratives_scenario import cultural_narratives_scenario
from tests.unit.test_world_rules import _accept, _state
from world._operations import OperationAccepted, validate_action_request
from world._rules import RuleDisposition, apply_operation
from world.actions import ActionRequest, Talk, Wait, require_agent_command
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision


def _admitted(application: object) -> None:
    disposition = application.result.disposition  # type: ignore[attr-defined]
    assert disposition in {RuleDisposition.MUTATE, RuleDisposition.EVENT_ONLY}
    assert application.result.emits_event is True  # type: ignore[attr-defined]


def test_wait_and_story_talk_still_admit_without_myth_checks() -> None:
    state = _state()
    waited = apply_operation(state, _accept(Wait()))
    _admitted(waited)
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=waited.next_state,
        request=ActionRequest(
            request_id=RequestId("r-story"),
            proposal_id=ProposalId("p-1"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-1"),
            revision=WorldRevision(1),
            command=require_agent_command(
                Talk(
                    recipient_id=EntityId("body-2"),
                    utterance=origin_utterance(
                        text="tell_story",
                        speaker_id=EntityId("body-1"),
                        relations=(
                            CommunicationRelation(
                                subject="water",
                                predicate="tell_story",
                                object="gone",
                            ),
                        ),
                        concepts=("water", "gone"),
                    ),
                )
            ),
        ),
    )
    assert isinstance(outcome, OperationAccepted)
    talked = apply_operation(waited.next_state, outcome.operation)
    _admitted(talked)


def test_scenario_rejects_myth_legend_culture_roster_kwargs() -> None:
    parameters = inspect.signature(cultural_narratives_scenario).parameters
    assert set(parameters) == {"seed", "max_ticks"}
    for forbidden in ("myth", "myths", "legend", "culture", "tradition", "narrative"):
        assert forbidden not in parameters
    with pytest.raises(TypeError):
        cultural_narratives_scenario(myths=("flood",))  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        cultural_narratives_scenario(legend="old_story")  # type: ignore[call-arg]


def test_world_info_logs_omit_story_tokens(caplog: pytest.LogCaptureFixture) -> None:
    state = _state()
    caplog.set_level(logging.INFO, logger="world")
    apply_operation(state, _accept(Wait()))
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "tell_story" not in messages
    assert "merge_story" not in messages
    assert "cultural_narratives" not in messages
