"""Pins for the V4-23 accounting cognition contract."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path

import pytest

from agents.cognition.accounting_ledgers import (
    ACCOUNTING_ENTRY_ANCHOR_PREFIX,
    ACCOUNTING_ENTRY_ID_PREFIX,
    ACCOUNTING_LEDGERS_POLICY_VERSION,
    ACCOUNTING_RECORD_PREDICATE,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_policy_token_and_prefixes_are_pinned() -> None:
    assert ACCOUNTING_LEDGERS_POLICY_VERSION == "accounting-ledgers.v1"
    assert ACCOUNTING_ENTRY_ANCHOR_PREFIX == "acct-"
    assert ACCOUNTING_ENTRY_ID_PREFIX == "acce-"
    assert ACCOUNTING_RECORD_PREDICATE == "acc_v1"


def test_accounting_modules_do_not_encode_a_runner_schema_bump() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in SRC.rglob("*accounting_ledgers*.py")
        if "runner-config-v57" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_versions_routes_settings_and_reason_codes_are_pinned() -> None:
    from agents.cognition.accounting_ledgers_communication import (
        ACCOUNTING_COMMUNICATION_POLICY_VERSION,
    )
    from api.routes.accounting_ledgers import ACCOUNTING_LEDGERS_ROUTE_COUNT
    from experiments.accounting_ledgers_publication import (
        AccountingLedgersReceipt,
    )
    from infrastructure.settings import Settings
    from persistence.accounting_ledgers_filesystem import (
        ACCOUNTING_LEDGERS_STORE_VERSION,
    )
    from simulation.accounting_ledgers_models import (
        ACCOUNTING_LEDGERS_SNAPSHOT_VERSION,
    )

    assert ACCOUNTING_COMMUNICATION_POLICY_VERSION == (
        "accounting-ledgers-communication.v1"
    )
    assert ACCOUNTING_LEDGERS_SNAPSHOT_VERSION == (
        "accounting-ledgers-snapshot-v1"
    )
    assert ACCOUNTING_LEDGERS_STORE_VERSION == "accounting-ledgers-store-v1"
    assert ACCOUNTING_LEDGERS_ROUTE_COUNT == 7
    fields = Settings.model_fields
    assert "accounting_ledgers_root" in fields
    assert "accounting_ledgers_cursor_key" in fields
    assert AccountingLedgersReceipt.__dataclass_fields__["reason_code"]
    import experiments.accounting_ledgers_publication as publication

    assert publication._REASON_CODES == {
        "published",
        "publication_disabled",
        "publication_missing",
        "store_quota_exceeded",
        "store_corrupt",
    }


def test_no_cli_producer_exists() -> None:
    for path in (SRC / "research_runner").rglob("*accounting*"):
        raise AssertionError(f"unexpected CLI producer: {path}")


def test_final_v4_23_pins() -> None:
    from typing import get_args

    from analysis.specifications import METRIC_FAMILY_COUNT
    from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_EVENT_TYPES
    from simulation.compatibility import (
        ALEMBIC_HEAD_REVISION,
        V4_OWNED_CAPABILITY_FLAGS,
    )
    from simulation.persistence import (
        ACCEPTED_EVENT_SCHEMA_VERSIONS,
        ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
    )
    from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
    from simulation.v4_architecture import V4_CAPABILITY_FLAGS, V4_CONTEXTS
    from world._rules import COMMAND_RULE_MATRIX
    from world.actions import AgentCommand

    assert METRIC_FAMILY_COUNT == 220
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(get_args(AgentCommand)) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 8
    assert "organizations" in V4_OWNED_CAPABILITY_FLAGS
    assert "markets_credit" in V4_OWNED_CAPABILITY_FLAGS
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert not list((ROOT / "alembic" / "versions").glob("0018*"))
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27
    assert "v25" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
