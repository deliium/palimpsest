"""Unit tests for developmental_learning channel bind (no acquisition yet)."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import build_cognitive_loop
from agents.cognition.loop import CognitiveLoop
from simulation.runner import _developmental_learning_loop_kwargs
from simulation.runner_models import example_developmental_learning_spec


def test_developmental_loop_kwargs_channel_off() -> None:
    class _Cfg:
        developmental_learning = None

    assert _developmental_learning_loop_kwargs(_Cfg()) == {}


def test_developmental_loop_kwargs_channel_on() -> None:
    spec = example_developmental_learning_spec()

    class _Cfg:
        developmental_learning = spec

    kwargs = _developmental_learning_loop_kwargs(_Cfg())
    assert kwargs["developmental_learning_spec"] is spec


def test_cognitive_loop_bind_logs_channel_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="agents.cognition.loop"):
        loop_off = build_cognitive_loop()
    assert isinstance(loop_off, CognitiveLoop)
    assert loop_off._developmental_learning_spec is None
    assert "developmental_learning_active=False" in caplog.text

    spec = example_developmental_learning_spec()
    with caplog.at_level(logging.INFO, logger="agents.cognition.loop"):
        loop_on = build_cognitive_loop(developmental_learning_spec=spec)
    assert loop_on._developmental_learning_spec is spec
    assert "developmental_learning_active=True" in caplog.text
    assert f"domain_count={len(spec.enabled_domains)}" in caplog.text


def test_cognitive_loop_rejects_invalid_bind_payload() -> None:
    with pytest.raises(TypeError, match="developmental_learning_spec"):
        build_cognitive_loop(developmental_learning_spec=object())
