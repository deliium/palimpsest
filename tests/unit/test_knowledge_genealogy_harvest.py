"""Knowledge-genealogy harvest composition + collector opt-in wiring."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from experiments.composition import knowledge_genealogy_harvest_from_run
from experiments.metric_collection import inputs_with_opt_in_metric_rows
from simulation.runner_models import example_knowledge_genealogy_spec

pytestmark = pytest.mark.unit
_LOG = logging.getLogger("tests.knowledge_genealogy_harvest")


def _audit(**kwargs) -> SimpleNamespace:
    base = dict(
        owner_id="alice",
        entry_id="e1",
        kind="foraging_method",
        content_key="tech:foraging",
        origin="independent_discovery",
        parent_entry_ids=(),
        lineage_root_id="root:alice:foraging_method:tech:foraging",
        hop_index=0,
        mutated=False,
        acquired_tick=1,
        tick=1,
        active=True,
        source_agent_id=None,
        teacher_agent_id=None,
        capability_anchor="foraging",
        fingerprint_distance_q=0.0,
        reason_code="formed",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_harvest_skips_when_genealogy_absent() -> None:
    _LOG.debug("case_id=harvest_skip")
    assert knowledge_genealogy_harvest_from_run(knowledge_genealogy_spec=None) is None


def test_harvest_derives_death_ticks_from_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    audits = (_audit(),)
    events = (
        SimpleNamespace(
            tick=4,
            kind="Died",
            details=SimpleNamespace(kind="Died", agent_id="alice", tick=4),
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="experiments.composition"):
        payload = knowledge_genealogy_harvest_from_run(
            knowledge_genealogy_spec=example_knowledge_genealogy_spec(),
            practical_knowledge_audits=audits,
            events=events,
        )
    assert payload is not None
    assert payload["practical_knowledge_audits"] == audits
    assert payload["death_ticks"]["alice"] == 4
    assert payload["origin_counts"]["independent_discovery"] == 1
    assert "knowledge_genealogy_harvest_built" in caplog.text


def test_harvest_warns_when_enabled_but_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="experiments.composition"):
        payload = knowledge_genealogy_harvest_from_run(
            knowledge_genealogy_spec=example_knowledge_genealogy_spec(),
            practical_knowledge_audits=(),
            events=(),
        )
    assert payload is not None
    assert payload["practical_knowledge_audits"] == ()
    assert "genealogy_enabled_rows_empty" in caplog.text


def test_opt_in_attaches_genealogy_rows_to_assemble() -> None:
    audits = (
        _audit(),
        _audit(
            owner_id="bob",
            entry_id="e2",
            origin="teaching",
            hop_index=1,
            teacher_agent_id="alice",
            source_agent_id="alice",
            acquired_tick=2,
            tick=2,
        ),
    )
    base = MetricComputationInputs(
        run_id="run-g",
        input_revision="rev-1",
        window_end=5,
    )
    updated = inputs_with_opt_in_metric_rows(
        base,
        practical_knowledge_audits=audits,
        death_ticks={"alice": 3},
    )
    assert updated.practical_knowledge_audits == audits
    assert updated.death_ticks == {"alice": 3}
    bundle = assemble_metric_documents(updated)
    families = {doc.metric_family: doc for doc in bundle.documents}
    assert "knowledge_genealogy_holders" in families
    assert "knowledge_genealogy_lineage" in families
    assert "knowledge_genealogy_mutation" in families
    assert (
        families["knowledge_genealogy_holders"].availability
        is MetricAvailability.PRESENT
    )
