"""Deterministic seed, stream, id, and clock contracts."""

from __future__ import annotations

import ast
import logging
import random
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from simulation.clock import LogicalClock, Tick, require_tick
from simulation.contracts import (
    describe_run,
    log_invalid_setup,
    log_replay_mismatch,
    log_run_configured,
    make_export,
)
from simulation.identifiers import (
    derive_run_id,
    derive_scoped_id,
    reject_operational_identifier,
)
from simulation.models import (
    DERIVATION_VERSION,
    LLM_REPLAY_REQUIREMENT,
    SimulationRunConfig,
)
from simulation.randomness import StreamScope, create_named_stream, sample_stream
from world.events import EventId, WorldEvent
from world.identifiers import WorldRevision

SRC = Path(__file__).resolve().parents[2] / "src" / "simulation"

_NON_EMPTY = st.text(min_size=1, max_size=24).filter(lambda value: value.strip() != "")
_SEEDS = st.integers(min_value=0, max_value=2**31 - 1)
_SCOPES = st.builds(
    StreamScope,
    namespace=_NON_EMPTY,
    names=st.lists(_NON_EMPTY, min_size=1, max_size=4).map(tuple),
)


def test_boolean_and_negative_seeds_are_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        SimulationRunConfig(seed=True)
    with pytest.raises(ValueError, match="non-negative integer"):
        SimulationRunConfig(seed=-1)


def test_named_streams_are_order_independent_and_stable() -> None:
    config = SimulationRunConfig(seed=42)
    alpha = StreamScope(namespace="agent", names=("alpha",))
    beta = StreamScope(namespace="agent", names=("beta",))
    first_alpha = sample_stream(config, alpha, 8)
    first_beta = sample_stream(config, beta, 8)
    second_beta = sample_stream(config, beta, 8)
    second_alpha = sample_stream(config, alpha, 8)
    assert first_alpha == second_alpha
    assert first_beta == second_beta
    assert first_alpha != first_beta


@given(seed=_SEEDS, scope=_SCOPES, count=st.integers(min_value=1, max_value=16))
@settings(max_examples=40, deadline=None)
def test_property_named_streams_are_deterministic(
    seed: int, scope: StreamScope, count: int
) -> None:
    config = SimulationRunConfig(seed=seed)
    assert sample_stream(config, scope, count) == sample_stream(config, scope, count)
    assert derive_scoped_id(config, scope) == derive_scoped_id(config, scope)
    assert derive_run_id(config) == derive_run_id(config)


@given(
    seed=_SEEDS,
    left=_SCOPES,
    right=_SCOPES,
)
@settings(max_examples=40, deadline=None)
def test_property_distinct_scopes_do_not_alias(
    seed: int, left: StreamScope, right: StreamScope
) -> None:
    if left == right:
        return
    config = SimulationRunConfig(seed=seed)
    assert derive_scoped_id(config, left) != derive_scoped_id(config, right)
    assert sample_stream(config, left, 4) != sample_stream(config, right, 4)


def test_distinct_scopes_do_not_alias() -> None:
    config = SimulationRunConfig(seed=7)
    left = StreamScope(namespace="agent", names=("ab", "c"))
    right = StreamScope(namespace="agent", names=("a", "bc"))
    assert sample_stream(config, left, 4) != sample_stream(config, right, 4)
    assert derive_scoped_id(config, left) != derive_scoped_id(config, right)


@given(seed=_SEEDS, scope=_SCOPES)
@settings(max_examples=25, deadline=None)
def test_property_global_rng_state_is_unchanged(
    seed: int, scope: StreamScope
) -> None:
    before = random.getstate()
    config = SimulationRunConfig(seed=seed)
    create_named_stream(config, scope)
    sample_stream(config, scope, 8)
    assert random.getstate() == before


def test_global_rng_state_is_unchanged() -> None:
    before = random.getstate()
    config = SimulationRunConfig(seed=99)
    scope = StreamScope(namespace="world", names=("combat",))
    create_named_stream(config, scope)
    sample_stream(config, scope, 16)
    assert random.getstate() == before


def test_golden_named_stream_and_run_id() -> None:
    config = SimulationRunConfig(seed=42)
    scope = StreamScope(namespace="agent", names=("alpha",))
    assert sample_stream(config, scope, 4) == (
        887245150,
        421149059,
        385613063,
        417011656,
    )
    assert derive_run_id(config).value == (
        "a2c0644c8d97e30daaa54ef76b5c9f1719ed8ef173255a976e61d5bf19af5ff6"
    )


def test_logical_clock_requires_explicit_tick() -> None:
    with pytest.raises(ValueError, match="cannot be omitted"):
        require_tick(None)
    clock = LogicalClock(Tick(0))
    assert clock.current == Tick(0)
    assert clock.advance() == Tick(1)
    with pytest.raises(ValueError):
        Tick(True)


def test_operational_metadata_cannot_become_domain_ids() -> None:
    with pytest.raises(TypeError, match="operational metadata"):
        reject_operational_identifier("X-Request-ID", "req-123")


def test_python_hash_builtin_is_not_used() -> None:
    for path in SRC.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "hash", path


def test_describe_run_omits_random_draws(caplog: pytest.LogCaptureFixture) -> None:
    config = SimulationRunConfig(seed=42)
    run_id = derive_run_id(config)
    scope = StreamScope(namespace="agent", names=("alpha",))
    fields = describe_run(config, run_id, scope)
    assert "random" not in fields
    assert fields["seed"] == 42
    assert fields["derivation_version"] == DERIVATION_VERSION
    caplog.set_level(logging.DEBUG, logger="simulation.run")
    log_run_configured(config, run_id, scope)
    log_replay_mismatch(run_id, DERIVATION_VERSION, "v0")
    log_invalid_setup("missing seed")
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "run_configured" in messages
    assert "replay_mismatch" in messages
    assert "invalid_setup" in messages
    assert str(sample_stream(config, scope, 1)[0]) not in messages


def test_export_records_replay_limit() -> None:
    config = SimulationRunConfig(seed=1)
    run_id = derive_run_id(config)
    event = WorldEvent(
        event_id=EventId("evt-1"),
        revision=WorldRevision(0),
        kind="tick",
        payload={},
    )
    export = make_export(config, run_id, [event])
    assert export.metadata.llm_replay == LLM_REPLAY_REQUIREMENT
    assert export.events == (event,)
