"""V4-09 detached representation harvest, detection, and identity."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
    default_representation_policy,
)
from agents.cognition.delegation_representation import (
    RepresentationLedger,
    apply_representation_update,
)
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
)
from analysis.delegation_representation_contract import (
    RepresentationAnalysisError,
    RepresentationCandidateStatus,
    representation_owner_token,
    representation_principal_token,
)
from analysis.delegation_representation_detection import (
    detect_representation_window_candidates,
)
from analysis.delegation_representation_identity import (
    derive_representation_lineage,
)
from analysis.delegation_representation_objective import (
    RepresentationObjectiveAnchorKind,
    build_representation_windows,
    representation_objective_anchor_rows_from_events,
)
from analysis.delegation_representation_rows import (
    harvest_representation_rows,
)
from world.identifiers import EventId

pytestmark = pytest.mark.unit

_OWNER = "agent-owner"
_PRINCIPAL = "agent-principal"
_REP = "agent-representative"


def _frame(
    act: RepresentationAct = RepresentationAct.CLAIM,
    *,
    mandate_ref: str | None = None,
    representative_ref: str = _REP,
    actor_ref: str = _REP,
    principal_kind: RepresentationPrincipalKind = RepresentationPrincipalKind.AGENT,
    principal_ref: str | None = _PRINCIPAL,
    scope_kind: RepresentationScopeKind = RepresentationScopeKind.SPEAK_FOR,
    scope_subject: str | None = "border",
) -> RepresentationFrame:
    if act in {RepresentationAct.CLAIM, RepresentationAct.DELEGATE}:
        mandate_ref = None
    elif mandate_ref is None:
        mandate_ref = "rmd-" + "1" * 16
    return RepresentationFrame(
        act=act,
        mandate_ref=mandate_ref,
        principal_kind=principal_kind,
        principal_ref=principal_ref,
        representative_ref=representative_ref,
        scope_kind=scope_kind,
        scope_subject=scope_subject,
        duration_kind=RepresentationDurationKind.UNTIL_REVOKED,
        provenance=RepresentationProvenance.SELF_DECLARED,
        actor_ref=actor_ref,
    )


def _apply(
    *frames: RepresentationFrame,
    prior: RepresentationLedger | None = None,
    tick: int = 1,
) -> RepresentationLedger:
    return apply_representation_update(
        owner_id=_OWNER,
        tick=tick,
        observation=None,
        prior=prior,
        frames=frames,
        policy=default_representation_policy(),
    )


def _claimed() -> RepresentationLedger:
    return _apply(_frame())


def test_harvest_tokens_are_deterministic_and_agent_principals_are_hashed() -> None:
    ledger = _claimed()
    first = harvest_representation_rows([ledger], entity_to_agent={})
    second = harvest_representation_rows([ledger], entity_to_agent={})
    assert first.mandates[0].owner_token == representation_owner_token(_OWNER)
    assert first.mandates[0].principal_token == representation_principal_token(
        "agent", _PRINCIPAL
    )
    assert first.mandates[0].principal_token != _PRINCIPAL
    assert first.mandates[0].representative_token != _REP
    assert first == second


def test_collective_principal_token_keeps_owner_safe_anchor() -> None:
    collective = "orgc-" + "1" * 16
    ledger = _apply(
        _frame(
            principal_kind=RepresentationPrincipalKind.ORGANIZATION,
            principal_ref=collective,
        )
    )
    rows = harvest_representation_rows([ledger], entity_to_agent={})
    assert rows.mandates[0].principal_token == collective
    assert rows.mandates[0].unresolved_principal is True


def test_invalid_harvest_input_raises_safe_code() -> None:
    with pytest.raises(RepresentationAnalysisError) as excinfo:
        harvest_representation_rows([object()], entity_to_agent={})
    assert excinfo.value.code == "representation_harvest_invalid"


def test_event_kind_mapping_and_entity_mapping() -> None:
    utterance = type(
        "Utterance",
        (),
        {"declared": type("Declared", (), {"communication_id": "comm-1"})()},
    )()
    details = type(
        "Told",
        (),
        {
            "speaker_id": "entity-speaker",
            "recipient_id": "entity-listener",
            "utterance": utterance,
        },
    )()
    event = type(
        "Event",
        (),
        {"details": details, "tick": 2, "event_id": EventId("event-2")},
    )()
    rows = representation_objective_anchor_rows_from_events(
        [event], {"entity-speaker": "agent-speaker"}
    )
    assert rows[0].kind is RepresentationObjectiveAnchorKind.COMMUNICATION
    assert rows[0].actor_token == "agent-speaker"
    assert rows[0].subject_token == "comm-1"


def test_windows_bucket_and_mark_empty_partial() -> None:
    ledger = _claimed()
    rows = harvest_representation_rows([ledger], entity_to_agent={})
    windows = build_representation_windows(rows, window_ticks=10)
    assert windows
    assert any(not window.partial for window in windows)


def test_candidate_identity_is_stable_and_status_covered() -> None:
    ledger = _claimed()
    rows = harvest_representation_rows([ledger], entity_to_agent={})
    first = detect_representation_window_candidates(rows)
    second = detect_representation_window_candidates(rows)
    assert first == second
    assert first[0].candidate_id.startswith("rep-")
    assert first[0].status is RepresentationCandidateStatus.CLAIMED
    analysis = derive_representation_lineage(rows)
    assert analysis.candidates == first
    assert analysis.transitions[0].kind.value == "emerged"


def test_candidate_fragmented_and_dissolved_statuses() -> None:
    ledger = _apply(_frame())
    second = _apply(
        _frame(
            RepresentationAct.CLAIM,
            representative_ref="agent-other",
            actor_ref="agent-other",
        ),
        prior=ledger,
        tick=2,
    )
    rows = harvest_representation_rows(
        [replace(second, owner_id="agent-other-owner")], entity_to_agent={}
    )
    candidates = detect_representation_window_candidates(rows)
    assert candidates[0].status in {
        RepresentationCandidateStatus.CLAIMED,
        RepresentationCandidateStatus.FRAGMENTED,
    }
    assert len(candidates[0].representative_tokens) == 2
