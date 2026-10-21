"""Mediation compatibility pins, redaction, and determinism invariants."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.mediation import (
    MediationAccount,
    MediationEvidenceChannel,
    MediationLedger,
    default_mediation_policy,
)
from agents.models import AgentId
from analysis.specifications import METRIC_FAMILY_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22


def test_closed_wire_and_catalog_pins() -> None:
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert METRIC_FAMILY_COUNT == 129
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert default_mediation_policy().version == "mediation.v1"


def test_no_durable_or_api_surface_was_added() -> None:
    from agents.cognition import mediation

    text = mediation.__doc__ or ""
    assert "owner-scoped" in text.lower()
    assert "durable" not in text.lower()


def test_ledger_repr_and_logs_redact_subjective_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.mediation")
    account = MediationAccount(
        account_id="a" * 64,
        owner_id=AgentId("ada"),
        actor_id=AgentId("bob"),
        case_ref="b" * 64,
        subject_token="private_subject",
        claim_token="private_claim",
        direct=True,
        channel=MediationEvidenceChannel.COMMUNICATED,
        root_ref="communication|one",
        first_tick=1,
        last_tick=1,
        evidence_id="c" * 64,
    )
    ledger = MediationLedger(owner_id=AgentId("ada"), accounts=(account,))
    assert "private_claim" not in repr(account)
    assert "private_subject" not in repr(account)
    assert "private_claim" not in repr(ledger)
    for record in caplog.records:
        assert "private_claim" not in record.getMessage()


def test_ledger_is_bounded_at_construction() -> None:
    from agents.cognition.mediation import MediationCase

    policy = default_mediation_policy()
    assert policy.max_cases == 16
    assert policy.max_accounts == 32
    assert policy.max_terms == 8
    assert policy.max_evidence == 24
    assert MediationCase.__dataclass_fields__ is not None


def test_owner_isolation_is_enforced() -> None:
    with pytest.raises(ValueError, match="owner_mismatch"):
        MediationLedger(
            owner_id=AgentId("ada"),
            accounts=(
                MediationAccount(
                    account_id="a" * 64,
                    owner_id=AgentId("bob"),
                    actor_id=AgentId("bob"),
                    case_ref="b" * 64,
                    subject_token="subject",
                    claim_token="claim",
                    direct=True,
                    channel=MediationEvidenceChannel.OBSERVED,
                    root_ref="root",
                    first_tick=1,
                    last_tick=1,
                    evidence_id="c" * 64,
                ),
            ),
        )
