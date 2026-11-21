# mypy: ignore-errors
"""V4-33 real-run capture, controlled mechanism, publication and gated read."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from tests.unit.test_scientific_institutions_scenario import _base

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    admit_hypothesis,
    empty_experiment_ledger,
    formulate_hypothesis,
)
from agents.cognition.scientific_hypothesis_communication import (
    attach_scientific_hypothesis_claim,
)
from agents.models import AgentId
from analysis.science_diffusion_contract import (
    DiffusionInputs,
    DiffusionLane,
    DiffusionResolution,
    DiffusionStage,
    ScienceKind,
    ScienceVersionKey,
)
from analysis.science_diffusion_lineage import V3Link, derive_science_diffusion
from api.app import create_app
from experiments.science_diffusion_capture import (
    run_with_science_diffusion_capture,
)
from experiments.science_diffusion_carriers import encode_marker_triples
from experiments.science_diffusion_genealogy import join_science_diffusion_context
from experiments.science_diffusion_publication import (
    compose_science_diffusion_snapshot,
)
from experiments.science_diffusion_scenario import science_diffusion_scenario
from infrastructure.settings import Settings
from persistence.science_diffusion_filesystem import (
    FilesystemScienceDiffusionStore,
)
from simulation import runner_config_fingerprint
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import ImaginationMode, RunnerStopPolicy
from world.actions import Experiment, Inscribe, Move, Talk, Wait
from world.artifacts import ArtifactContent, ArtifactKind, ArtifactRelation, DurableRecordGenre
from world.communications import CommunicationRelation, origin_utterance
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.integration

RUN = "run-sdf-integration"
TOKEN = "science-diffusion-token-" + "y" * 32
HEADERS = {"x-palimpsest-token": TOKEN}
HYP_ID = "hyp:sdf-fixed"
OWNER = AgentId("agent-1")


def _config():
    definition = science_diffusion_scenario(_base(), max_ticks=128)
    return {row.condition_id: row.runner_config for row in definition.conditions}


def _fixed_hypothesis():
    return formulate_hypothesis(
        owner_id=OWNER,
        hypothesis_id=HYP_ID,
        operator=ExperimentOperator.VARY_PROCESS,
        operand_a_id="tool-1",
        operand_b_id=None,
        process_token=ExperimentProcessToken.HARVEST,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(),
        created_tick=0,
    )


def _seed_sender_ledger(runner: SimulationRunner, hypothesis) -> None:
    binding = ExperimentCognitionBinding(8, 1, 2, False, False)
    ledger = admit_hypothesis(empty_experiment_ledger(OWNER, binding), hypothesis)
    for runtime in runner.runtimes:
        if runtime.agent_id == OWNER:
            runtime._loop.restore_experiment_ledger(ledger, OWNER)
            return
    raise AssertionError("sender runtime missing")


class _MechanismArbiter:
    """Finite override: co-locate, experiment, teach hyp_v1, then marker Inscribe."""

    def __init__(self, hypothesis, *, run_id: str) -> None:
        self._hypothesis = hypothesis
        self._marker_relations = tuple(
            CommunicationRelation(*triple)
            for triple in encode_marker_triples(
                ScienceVersionKey(
                    run_id=run_id,
                    owner_id=OWNER.value,
                    kind=ScienceKind.HYPOTHESIS,
                    local_id=HYP_ID,
                    revision_index=0,
                )
            )
        )
        self._inscribe_relations = tuple(
            ArtifactRelation(*triple) for triple in encode_marker_triples(
                ScienceVersionKey(
                    run_id=run_id,
                    owner_id=OWNER.value,
                    kind=ScienceKind.HYPOTHESIS,
                    local_id=HYP_ID,
                    revision_index=0,
                )
            )
        )

    def maybe_replace(self, *, tick, agent_id, proposed_command):
        del proposed_command
        owner = agent_id.value
        if tick == 0 and owner == "agent-2":
            return Move(destination_id=EntityId("loc-1"))
        if tick == 0 and owner == "agent-1":
            return Experiment(
                operator=ExperimentOperator.VARY_PROCESS,
                operand_a_id=EntityId("tool-1"),
                process_token=ExperimentProcessToken.HARVEST,
                hypothesis_id=HYP_ID,
            )
        if tick == 2 and owner == "agent-1":
            talk = Talk(
                recipient_id=EntityId("body-2"),
                utterance=origin_utterance(
                    text="teach-science",
                    speaker_id=EntityId("body-1"),
                    relations=(
                        CommunicationRelation(
                            "skill", "explain", "crafting:high"
                        ),
                        *self._marker_relations,
                    ),
                ),
            )
            return attach_scientific_hypothesis_claim(talk, self._hypothesis)
        if tick == 3 and owner == "agent-2":
            return Inscribe(
                kind=ArtifactKind.RECORD,
                content=ArtifactContent(relations=self._inscribe_relations),
                record_genre=DurableRecordGenre.INSTRUCTION,
            )
        return Wait()


def _assess(captured, *, boundary, inventory, config):
    assert captured.inputs is not None
    joined = join_science_diffusion_context(
        boundary,
        inventory,
        occurrences=captured.inputs.occurrences,
        versions=captured.inputs.versions,
        observed_boundary=captured.result.ticks_committed,
    )
    inputs = DiffusionInputs(
        run_id=captured.inputs.run_id,
        versions=captured.inputs.versions,
        occurrences=joined.occurrences,
        coverage=captured.inputs.coverage,
    )
    links = tuple(
        V3Link(
            transmission_key=row.transmission_key,
            v3_node_key=row.v3_node_key,
            origin=row.origin,
            relation=row.relation,
            ambiguous=row.ambiguous,
        )
        for row in joined.genealogy
    )
    assessment = derive_science_diffusion(inputs, v3_links=links)
    snapshot = compose_science_diffusion_snapshot(
        run_id=captured.result.run_id.value,
        config_fingerprint=runner_config_fingerprint(config),
        capture_status=captured.status,
        boundary_tick=captured.result.ticks_committed,
        coverage=inputs.coverage,
        versions=inputs.versions,
        assessment=assessment,
    )
    return joined, assessment, snapshot


@pytest.mark.asyncio
async def test_capture_compose_publish_and_read(tmp_path: Path) -> None:
    config = _config()["diffusion-science"]
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_science_diffusion_capture(runner, capture=True)
    assert captured.status in {"captured", "captured_sealed"}
    assert captured.inputs is not None
    assert captured.result.ticks_committed == 128
    assert captured.prefix is not None

    assessment = derive_science_diffusion(captured.inputs)
    snapshot = compose_science_diffusion_snapshot(
        run_id=RUN,
        config_fingerprint=runner_config_fingerprint(config),
        capture_status=captured.status,
        boundary_tick=captured.result.ticks_committed,
        coverage=captured.inputs.coverage,
        versions=captured.inputs.versions,
        assessment=assessment,
    )
    store = FilesystemScienceDiffusionStore(tmp_path)
    receipt = store.publish(snapshot)
    assert receipt.stored is True

    settings = Settings(
        _env_file=None,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
        science_diffusion_root=tmp_path,
        science_diffusion_cursor_key=SecretStr("k" * 32),
    )
    app = create_app(settings, attach_default_manager=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/science-diffusion", headers=HEADERS
        )
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["publication_id"] == snapshot.publication_id
        assert payload["schema_version"] == "science-diffusion-snapshot-v1"
        for section in ("coverage", "versions", "transmissions", "changes"):
            page = await client.get(
                f"/v1/simulations/{RUN}/science-diffusion/{section}",
                headers=HEADERS,
                params={"publication_id": snapshot.publication_id, "limit": 10},
            )
            assert page.status_code == 200, (section, page.text)
            body = page.json()
            assert body["publication_id"] == snapshot.publication_id


@pytest.mark.asyncio
async def test_controlled_mechanism_teaching_uptake_v3_and_marker_record(
    tmp_path: Path,
) -> None:
    config = _config()["diffusion-science"]
    config = replace(
        config,
        stop_policy=RunnerStopPolicy(max_ticks=8),
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    imagination_mode=ImaginationMode.DISABLED,
                ),
            )
            for agent in config.agents
        ),
    )
    run_id = RUN + "-mechanism"
    hypothesis = _fixed_hypothesis()
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(run_id),
        factories=RunnerDependencyFactories(),
    )
    _seed_sender_ledger(runner, hypothesis)
    runner.set_intervention_arbiter(
        _MechanismArbiter(hypothesis, run_id=run_id)
    )
    async with runner:
        captured = await run_with_science_diffusion_capture(runner, capture=True)
        boundary = await runner.export_finalized_research_boundary()
        inventory = runner.engine.detached_objective_facts()

    assert captured.status in {"captured", "captured_sealed"}
    assert captured.inputs is not None
    events = tuple(runner.engine.export_events().events)
    assert any(type(event.details).__name__ == "Talked" for event in events)
    assert any(type(event.details).__name__ == "ArtifactCreated" for event in events)

    receiver = next(
        owner for owner in boundary.owners if owner.owner_id.value == "agent-2"
    )
    ledger = receiver.runtime_checkpoint.experiment_ledger
    assert any(
        revision.reason.value == "source_adopted"
        for hypothesis_row in ledger.hypotheses
        for revision in hypothesis_row.revisions
    )
    pk = receiver.runtime_checkpoint.practical_knowledge
    assert pk is not None
    assert any(
        entry.origin.value == "teaching"
        and any(ref.startswith("teach:") for ref in entry.evidence_refs)
        for entry in pk.entries
    )

    joined, assessment, snapshot = _assess(
        captured, boundary=boundary, inventory=inventory, config=config
    )
    speech = [
        row
        for row in joined.occurrences
        if row.lane is DiffusionLane.SPEECH
        and row.stage is DiffusionStage.ADOPTED
        and row.resolution is DiffusionResolution.CONFIRMED
    ]
    teaching = [
        row
        for row in joined.occurrences
        if row.lane is DiffusionLane.TEACHING
        and row.resolution is DiffusionResolution.CONFIRMED
        and row.source_version is not None
    ]
    markers = [
        row
        for row in joined.occurrences
        if row.occurrence_kind == "marker_report"
    ]
    assert speech
    assert teaching
    assert markers
    assert assessment.v3_links
    assert any(link.relation == "teaching_uptake" for link in assessment.v3_links)
    marked_records = [
        artifact
        for artifact in inventory.artifacts
        if any(
            getattr(relation, "subject", None) == "sdf_v1"
            for relation in artifact.content.relations
        )
    ]
    assert marked_records

    store = FilesystemScienceDiffusionStore(tmp_path)
    assert store.publish(snapshot).stored is True
    settings = Settings(
        _env_file=None,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
        science_diffusion_root=tmp_path,
        science_diffusion_cursor_key=SecretStr("k" * 32),
    )
    app = create_app(settings, attach_default_manager=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        genealogy = await client.get(
            f"/v1/simulations/{run_id}/science-diffusion/genealogy",
            headers=HEADERS,
            params={"publication_id": snapshot.publication_id, "limit": 10},
        )
        assert genealogy.status_code == 200, genealogy.text
        body = genealogy.json()
        assert body["publication_id"] == snapshot.publication_id
        assert body["rows"]
        assert any(row["relation"] == "teaching_uptake" for row in body["rows"])


@pytest.mark.asyncio
async def test_capture_off_parity_and_science_off_inert() -> None:
    config = _config()["diffusion-science"]
    on_runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN + "-on"),
        factories=RunnerDependencyFactories(),
    )
    async with on_runner:
        captured = await run_with_science_diffusion_capture(on_runner, capture=True)
    off_runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN + "-off"),
        factories=RunnerDependencyFactories(),
    )
    async with off_runner:
        skipped = await run_with_science_diffusion_capture(off_runner, capture=False)
    assert skipped.status == "unavailable"
    assert skipped.inputs is None
    assert skipped.result.ticks_committed == captured.result.ticks_committed
    assert len(off_runner.engine.export_events().events) == len(
        on_runner.engine.export_events().events
    )

    science_off = _config()["diffusion-science-off"]
    inert_runner = await SimulationRunner.from_config(
        science_off,
        run_id=RunId(RUN + "-science-off"),
        factories=RunnerDependencyFactories(),
    )
    async with inert_runner:
        inert = await run_with_science_diffusion_capture(
            inert_runner, capture=True
        )
    assert inert.status == "unavailable"
    assert inert.inputs is None
    assert inert.samples == ()
