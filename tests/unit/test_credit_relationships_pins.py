"""Pins for the V4-22 credit cognition contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.cognition.credit_relationships import (
    CREDIT_ANCHOR_PREFIX,
    CREDIT_RELATIONSHIPS_POLICY_VERSION,
    CREDIT_ROW_PREFIX,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_policy_token_and_prefixes_are_pinned() -> None:
    assert CREDIT_RELATIONSHIPS_POLICY_VERSION == "credit-relationships.v1"
    assert CREDIT_ANCHOR_PREFIX == "crd-"
    assert CREDIT_ROW_PREFIX == "cred-"


def test_credit_modules_do_not_encode_a_runner_schema_bump() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in SRC.rglob("*credit_relationships*.py")
        if "runner-config-v57" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_final_v4_22_pins() -> None:
    from typing import get_args

    from agents.cognition.credit_relationships import (
        CREDIT_RELATIONSHIPS_POLICY_VERSION,
    )
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
    from world.credit_relationships import CREDIT_FRAME_SUBJECT

    assert CREDIT_RELATIONSHIPS_POLICY_VERSION == "credit-relationships.v1"
    assert CREDIT_FRAME_SUBJECT == "crd_v1"
    assert METRIC_FAMILY_COUNT == 216
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(get_args(AgentCommand)) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 8
    assert "markets_credit" in V4_OWNED_CAPABILITY_FLAGS
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert not list((ROOT / "alembic" / "versions").glob("0018*"))
    assert max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27
    assert "v25" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"


def test_route_count_and_settings_names_are_pinned() -> None:
    from api.routes.credit_relationships import (
        CREDIT_RELATIONSHIPS_ROUTE_COUNT,
    )
    from infrastructure.settings import Settings

    assert CREDIT_RELATIONSHIPS_ROUTE_COUNT == 7
    fields = Settings.model_fields
    assert "credit_relationships_root" in fields
    assert "credit_relationships_cursor_key" in fields


def test_snapshot_store_and_policy_tokens_are_exact() -> None:
    from persistence.credit_relationships_filesystem import (
        CREDIT_RELATIONSHIPS_STORE_VERSION,
    )
    from simulation.credit_relationships_models import (
        CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY,
        CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
    )

    assert CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION == (
        "credit-relationships-snapshot-v1"
    )
    assert CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY == "credit-relationships.v1"
    assert CREDIT_RELATIONSHIPS_STORE_VERSION == "credit-relationships-store-v1"


def test_no_godot_overlay_mentions_credit() -> None:
    godot = ROOT / "clients" / "godot-observer"
    if not godot.exists():
        pytest.skip("Godot client is absent")
    for path in godot.rglob("*"):
        if (
            not path.is_file()
            or path.suffix not in {".gd", ".tscn", ".tres", ".gdshader"}
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        assert "credit_relationships" not in text, str(path)
        assert "crd_v1" not in text, str(path)
        assert "credit-relationships" not in text, str(path)
