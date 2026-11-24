# mypy: ignore-errors

"""Canonical commons-governance-state-v1 encode/decode/digest tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.commons_governance import (
    CommonsConsideration,
    CommonsConsiderationChoice,
    CommonsConsiderationOpportunity,
    CommonsEvidenceCode,
    CommonsLedger,
    CommonsQuantitySignal,
    CommonsTransition,
    empty_commons_ledger,
)
from agents.models import AgentId
from simulation.commons_governance_checkpoint import (
    COMMONS_GOVERNANCE_STATE_VERSION,
    CommonsGovernanceCheckpointError,
    commons_governance_state_digest,
    decode_commons_governance_state,
    encode_commons_governance_state,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-a")
_ENTITY = EntityId("body-a")
_STOCK = EntityId("stock-a")


def _ledger() -> CommonsLedger:
    base = empty_commons_ledger(_OWNER, _ENTITY)
    return replace(
        base,
        last_processed_tick=3,
        transitions=(
            CommonsTransition(
                transition_id="t1",
                owner_id=_OWNER,
                stock_id=_STOCK,
                source_tick=3,
                code=CommonsEvidenceCode.STOCK_CHECKED,
                quantity_tenths=40,
                signal=CommonsQuantitySignal.BASELINE,
            ),
        ),
        considerations=(
            CommonsConsideration(
                owner_id=_OWNER,
                tick=3,
                target_id=_STOCK,
                proposal_id=None,
                opportunity=CommonsConsiderationOpportunity.NOT_APPLICABLE,
                choice=CommonsConsiderationChoice.PROCEEDED,
            ),
        ),
    )


def test_encode_decode_round_trip() -> None:
    ledger = _ledger()
    payload = encode_commons_governance_state(ledger)
    assert payload["codec_version"] == COMMONS_GOVERNANCE_STATE_VERSION
    assert payload["owner_id"] == _OWNER.value
    assert set(payload) == {
        "codec_version",
        "owner_id",
        "policy_id",
        "ledger",
    }
    decoded = decode_commons_governance_state(payload, _OWNER)
    assert decoded == ledger


def test_digest_stable_and_sensitive() -> None:
    ledger = _ledger()
    digest = commons_governance_state_digest(ledger)
    assert digest == commons_governance_state_digest(ledger)
    mutated = replace(ledger, omission_count=1)
    assert commons_governance_state_digest(mutated) != digest


def test_owner_mismatch_and_unknown_version_rejected() -> None:
    payload = encode_commons_governance_state(_ledger())
    with pytest.raises(CommonsGovernanceCheckpointError) as owner_exc:
        decode_commons_governance_state(payload, AgentId("agent-b"))
    assert owner_exc.value.code == "commons_governance_state_owner_mismatch"

    bad_version = {**payload, "codec_version": "commons-governance-state-v0"}
    with pytest.raises(CommonsGovernanceCheckpointError) as version_exc:
        decode_commons_governance_state(bad_version, _OWNER)
    assert version_exc.value.code == "commons_governance_state_unsupported_version"


def test_tampered_keyset_rejected() -> None:
    payload = encode_commons_governance_state(_ledger())
    with pytest.raises(CommonsGovernanceCheckpointError) as excinfo:
        decode_commons_governance_state({**payload, "extra": True}, _OWNER)
    assert excinfo.value.code == "commons_governance_state_invalid"
