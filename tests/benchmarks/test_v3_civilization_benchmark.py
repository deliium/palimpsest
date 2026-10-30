"""Opt-in V3 generational civilization benchmark qualification harness.

Run with the dedicated scale lane::

    PALIMPSEST_V3_SOURCE_REVISION=<rev> \
    PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST=<sha256> \
      uv run pytest -m 'integration and scale' \
      tests/benchmarks/test_v3_civilization_benchmark.py

The harness executes every registered case through the production benchmark CLI
composition, writes immutable sibling artifacts into isolated per-lane roots,
verifies each suite strictly, repeats the research smoke selection in a separate
namespace as an exact-identity deterministic twin, and publishes a completion
matrix that distinguishes measured outcomes from unexecuted external gates.

Test-local identities are explicitly synthetic test evidence. They are never a
release-source attestation; pass the environment variables above for real runs.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from experiments.civilization_benchmark_artifacts import (
    RUN_SCHEMA_ID,
    BenchmarkArtifactStore,
    decode_document,
)
from experiments.civilization_benchmark_comparison import (
    BenchmarkComparisonObservation,
    V3BenchmarkComparison,
    build_v3_benchmark_comparison,
)
from experiments.civilization_benchmark_models import (
    V3_BENCHMARK_SCENARIO_COUNT,
    V3BenchmarkExecutionKind,
    V3BenchmarkProfile,
)
from experiments.civilization_benchmark_suite import (
    RESEARCH_SEEDS,
    SMOKE_SEED,
    list_v3_benchmark_scenarios,
)
from research_runner.cli import main as matrix_main

pytestmark = [pytest.mark.integration, pytest.mark.scale]

_LOG: Final[logging.Logger] = logging.getLogger("benchmark.v3.civilization")

_ROOT_ENV: Final[str] = "PALIMPSEST_V3_BENCHMARK_ROOT"
_REVISION_ENV: Final[str] = "PALIMPSEST_V3_SOURCE_REVISION"
_DIGEST_ENV: Final[str] = "PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST"
_TIMEOUT_ENV: Final[str] = "PALIMPSEST_V3_BENCHMARK_TIMEOUT_SECONDS"
_COMPOSE_STATUS_ENV: Final[str] = "PALIMPSEST_V3_COMPOSE_STATUS"
_DEFAULT_ROOT: Final[Path] = Path("/tmp/opencode/v3-44/task22/benchmark")
_DEFAULT_TIMEOUT_SECONDS: Final[int] = 300
_SYNTHETIC_REVISION: Final[str] = "synthetic-test-v3-44"
_SYNTHETIC_DIGEST: Final[str] = "a" * 64
_MATRIX_SCHEMA: Final[str] = "v3-benchmark-qualification-matrix-v1"
_GATE_STATUSES: Final[frozenset[str]] = frozenset(
    {"passed", "failed", "unexecuted"}
)


@dataclass(frozen=True, slots=True)
class _Qualification:
    root: Path
    mechanisms: tuple[dict[str, object], ...]
    research_smoke: tuple[dict[str, object], ...]
    twin: tuple[dict[str, object], ...]
    research: tuple[dict[str, object], ...]
    comparison: V3BenchmarkComparison
    matrix: dict[str, object]
    twin_matches: bool


def _benchmark_root() -> Path:
    raw = os.environ.get(_ROOT_ENV, "").strip()
    return Path(raw) if raw else _DEFAULT_ROOT


def _timeout_seconds() -> int:
    raw = os.environ.get(_TIMEOUT_ENV, "").strip()
    if not raw:
        return _DEFAULT_TIMEOUT_SECONDS
    value = int(raw)
    assert value > 0
    return value


def _source_arguments() -> tuple[str, ...]:
    revision = os.environ.get(_REVISION_ENV, "").strip() or _SYNTHETIC_REVISION
    digest = os.environ.get(_DIGEST_ENV, "").strip()
    if digest:
        return ("--code-revision", revision, "--source-artifact-digest", digest)
    return (
        "--code-revision",
        revision,
        "--source-artifact-digest",
        _SYNTHETIC_DIGEST,
    )


def _run_lane(
    root: Path,
    *,
    profile: str,
    lane: str,
    scenarios: Sequence[str] | None = None,
    seeds: Sequence[int] | None = None,
    expect_gate_pass: bool = True,
) -> None:
    arguments = [
        "civilization-benchmark",
        "run",
        "--profile",
        profile,
        "--lane",
        lane,
        "--output",
        str(root),
        "--timeout-seconds",
        str(_timeout_seconds()),
        *_source_arguments(),
    ]
    for scenario in scenarios or ():
        arguments.extend(("--scenario", scenario))
    for seed in seeds or ():
        arguments.extend(("--seed", str(seed)))
    _LOG.info(
        "v3_benchmark_lane_start profile=%s lane=%s scenario_count=%s seed_count=%s",
        profile,
        lane,
        len(scenarios or ()),
        len(seeds or ()),
    )
    exit_code = matrix_main(arguments)
    if expect_gate_pass:
        assert exit_code == 0
    else:
        # Unexercised mechanisms in an unassisted research lane are explicit
        # null statuses, not silent skips or fabricated passes.
        assert exit_code in {0, 1}


def _verify(root: Path, *, require_complete: bool) -> dict[str, object]:
    arguments = [
        "civilization-benchmark",
        "verify",
        "--output",
        str(root),
        *_source_arguments(),
    ]
    if require_complete:
        arguments.insert(4, "--require-complete")
    assert matrix_main(arguments) == 0
    from experiments.generational_artifacts import (
        source_identity_preflight,
    )

    source_identity = source_identity_preflight(
        code_revision=_source_arguments()[1],
        source_clean=False,
        source_artifact_digest=_source_arguments()[3],
    )
    return BenchmarkArtifactStore(
        root, profile=V3BenchmarkProfile.SMOKE
    ).verify(
        source_identity=source_identity, require_complete=require_complete
    )


def _documents(root: Path) -> tuple[dict[str, object], ...]:
    suite_path = root / "suite.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    runs = suite.get("runs")
    assert isinstance(runs, list)
    documents: list[dict[str, object]] = []
    for entry in runs:
        assert isinstance(entry, Mapping)
        relative = entry.get("path")
        assert isinstance(relative, str)
        documents.append(
            decode_document((root / relative).read_bytes(), schema_id=RUN_SCHEMA_ID)
        )
    return tuple(documents)


def _execution_summary(document: Mapping[str, object]) -> dict[str, object]:
    execution = document["execution"]
    outcome = document["outcome"]
    assert isinstance(execution, Mapping) and isinstance(outcome, Mapping)
    checks = document["checks"]
    assert isinstance(checks, list)
    return {
        "status": execution["status"],
        "ticks_committed": execution["ticks_committed"],
        "declared_horizon": execution["declared_horizon"],
        "coverage": outcome["coverage"],
        "evidence": outcome["evidence"],
        "phenomenon": outcome["phenomenon"],
        "check_count": len(checks),
        "passing_check_count": sum(
            1
            for check in checks
            if isinstance(check, Mapping) and check.get("status") == "pass"
        ),
        "null_check_count": sum(
            1
            for check in checks
            if isinstance(check, Mapping) and check.get("status") == "unexecuted"
        ),
        "passes": (
            execution["status"] == "completed"
            and execution["ticks_committed"] == execution["declared_horizon"]
            and outcome["evidence"] == "complete"
            and all(
                isinstance(check, Mapping) and check.get("status") == "pass"
                for check in checks
            )
        ),
        "reason_codes": sorted(
            {
                str(check.get("reason_code"))
                for check in checks
                if isinstance(check, Mapping)
            }
        ),
        "artifact_hash": document["artifact_hash"],
        "seed": document["seed"],
        "arm_id": document["arm_id"],
    }


def _gate_status(name: str) -> str:
    raw = os.environ.get(f"PALIMPSEST_V3_GATE_{name.upper()}", "").strip()
    return raw if raw in _GATE_STATUSES else "unexecuted"


def _comparison_observations(
    documents: Sequence[Mapping[str, object]],
) -> tuple[BenchmarkComparisonObservation, ...]:
    observations: list[BenchmarkComparisonObservation] = []
    for document in documents:
        checks = document["checks"]
        execution = document["execution"]
        outcome = document["outcome"]
        assert isinstance(checks, list)
        assert isinstance(execution, Mapping) and isinstance(outcome, Mapping)
        seed = document["seed"]
        assert type(seed) is int
        for check in checks:
            if not isinstance(check, Mapping):
                continue
            numerator = check.get("numerator")
            denominator = check.get("denominator")
            if (
                type(numerator) is not int
                or type(denominator) is not int
                or denominator < 1
                or numerator > denominator
            ):
                continue
            observations.append(
                BenchmarkComparisonObservation(
                    cell_id=(
                        f"{document['scenario_id']}:{document['lane']}:"
                        f"{document['arm_id']}:{document['seed']}:"
                        f"{check['selector_id']}"
                    ),
                    scenario_id=str(document["scenario_id"]),
                    contrast_id="none",
                    arm_id=str(document["arm_id"]),
                    numeric_seed=seed,
                    seed_ordinal=(
                        RESEARCH_SEEDS.index(seed)
                        if seed in RESEARCH_SEEDS
                        else 0
                    ),
                    replicate=0,
                    outcome_key=str(check["selector_id"]),
                    window_id="declared-horizon",
                    value=numerator / denominator,
                    execution_status=str(execution["status"]),
                    declared_horizon=int(execution["declared_horizon"]),
                    ticks_committed=int(execution["ticks_committed"]),
                    evidence=str(outcome["evidence"]),
                    population_scope="whole_population",
                )
            )
    return tuple(observations)


_COMPLETION_CRITERIA: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("V1 and V2 invariants remain valid", ()),
    ("Population can change across time", ("v3-bench-01-blank-slate",)),
    (
        "Multiple generations coexist and replace one another",
        ("v3-bench-01-blank-slate", "v3-bench-02-dependent-care"),
    ),
    (
        "New agents learn culture instead of receiving copied memories",
        (
            "v3-bench-01-blank-slate",
            "v3-bench-03-intergenerational-teaching",
            "v3-bench-04-cultural-mutation",
        ),
    ),
    (
        "Knowledge persists beyond individual lifetimes",
        ("v3-bench-06-record-after-witnesses", "v3-bench-07-false-record"),
    ),
    ("Knowledge can also be lost", ("v3-bench-10-technology-loss",)),
    (
        "Technologies emerge, spread, mutate and disappear",
        (
            "v3-bench-08-technology-discovery",
            "v3-bench-09-technology-diffusion",
            "v3-bench-10-technology-loss",
            "v3-bench-11-technology-rediscovery",
        ),
    ),
    (
        "Cultural traits are measured across generations",
        (
            "v3-bench-04-cultural-mutation",
            "v3-bench-22-generational-semantic-drift",
        ),
    ),
    (
        "Separate populations can culturally diverge",
        ("v3-bench-19-isolated-divergence",),
    ),
    (
        "Populations interact without magically synchronizing knowledge",
        ("v3-bench-20-recontact-exchange",),
    ),
    (
        "Persistent social roles and institutions are observed without scripting",
        (
            "v3-bench-25-persistent-role",
            "v3-bench-27-institutional-persistence",
        ),
    ),
    (
        "Institutions survive occupant death",
        ("v3-bench-26-office-succession",),
    ),
    (
        "Institutions can transform or disappear",
        ("v3-bench-27-institutional-persistence", "v3-bench-28-institutional-decay"),
    ),
    (
        "Historical narratives may outlive all witnesses",
        ("v3-bench-24-narrative-after-witnesses",),
    ),
    (
        "Small interventions are compared through forked multi-generation runs",
        (
            "v3-bench-29-founder-contingency",
            "v3-bench-30-multigeneration-fork",
        ),
    ),
    ("Godot observes generational history without affecting it", ()),
    ("Research UI analyzes lineage and long-term societal change", ()),
    ("Normal deployment remains zero-install with respect to Godot", ()),
    ("Long-running experiments remain reproducible and auditable", ()),
)

def _completion_criteria(
    scenarios: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    by_id = {str(item["scenario_id"]): item for item in scenarios}
    rows: list[dict[str, object]] = []
    for criterion, scenario_ids in _COMPLETION_CRITERIA:
        evidence: list[str] = []
        for scenario_id in scenario_ids:
            entry = by_id.get(scenario_id)
            mechanism = None if entry is None else entry.get("mechanism")
            if isinstance(mechanism, Mapping) and mechanism.get("passes") is True:
                evidence.append(scenario_id)
        external = not scenario_ids
        status = (
            "unexecuted_external_gate"
            if external
            else (
                "verified_by_mechanism_lane"
                if len(evidence) == len(scenario_ids)
                else "blocked"
            )
        )
        rows.append(
            {
                "criterion": criterion,
                "scenario_ids": list(scenario_ids),
                "verified_scenario_ids": evidence,
                "status": status,
            }
        )
    return rows


def _matrix(
    *,
    mechanisms: Sequence[Mapping[str, object]],
    research_smoke: Sequence[Mapping[str, object]],
    research: Sequence[Mapping[str, object]],
    twin_matches: bool,
) -> dict[str, object]:
    by_scenario: dict[str, dict[str, object]] = {
        spec.scenario_id: {
            "request_number": spec.request_number,
            "scenario_id": spec.scenario_id,
            "title": spec.title,
            "execution_kind": spec.execution_kind.value,
            "mechanism": None,
            "research": None,
        }
        for spec in list_v3_benchmark_scenarios()
    }
    for document in mechanisms:
        scenario_id = str(document["scenario_id"])
        by_scenario[scenario_id]["mechanism"] = _execution_summary(document)
    for document in research_smoke:
        scenario_id = str(document["scenario_id"])
        by_scenario[scenario_id]["research"] = _execution_summary(document)
    research_seed_counts: dict[str, set[int]] = {}
    for document in research:
        scenario_id = str(document["scenario_id"])
        seed = document["seed"]
        assert type(seed) is int
        research_seed_counts.setdefault(scenario_id, set()).add(seed)
    scenarios: list[dict[str, object]] = []
    for entry in by_scenario.values():
        mechanism = entry["mechanism"]
        research_entry = entry["research"]
        seeds_retained = sorted(
            research_seed_counts.get(str(entry["scenario_id"]), set())
        )
        mechanism_passes = (
            isinstance(mechanism, Mapping) and mechanism.get("passes") is True
        )
        research_completed = (
            isinstance(research_entry, Mapping)
            and research_entry.get("status") == "completed"
            and research_entry.get("ticks_committed")
            == research_entry.get("declared_horizon")
        )
        scenarios.append(
            {
                **entry,
                "research_seeds_retained": seeds_retained,
                "complete": (
                    mechanism_passes
                    and research_completed
                    and len(seeds_retained) == len(RESEARCH_SEEDS)
                ),
            }
        )
    grouped = [
        item
        for item in scenarios
        if item["execution_kind"] == V3BenchmarkExecutionKind.GROUPED.value
    ]
    criteria = [
        {
            "criterion": "all_thirty_scenarios_executed",
            "evidence": f"{len(scenarios)} scenario entries",
            "status": (
                "present"
                if len(scenarios) == V3_BENCHMARK_SCENARIO_COUNT
                else "incomplete"
            ),
        },
        {
            "criterion": "mechanism_and_research_lanes_separated",
            "evidence": "mechanism/research summaries per scenario",
            "status": "present",
        },
        {
            "criterion": "deterministic_twins_match",
            "evidence": "separate-namespace run artifacts",
            "status": "present" if twin_matches else "incomplete",
        },
        {
            "criterion": "grouped_historical_forks_retained",
            "evidence": f"{len(grouped)} grouped scenario entries",
            "status": "present" if len(grouped) == 2 else "incomplete",
        },
        {
            "criterion": "predeclared_research_seed_blocks",
            "evidence": f"seeds={list(RESEARCH_SEEDS)}",
            "status": "present",
        },
    ]
    gates = {
        "default_regression": _gate_status("default"),
        "integration": _gate_status("integration"),
        "compose_browser": (
            os.environ.get(_COMPOSE_STATUS_ENV, "").strip()
            if os.environ.get(_COMPOSE_STATUS_ENV, "").strip() in _GATE_STATUSES
            else "unexecuted"
        ),
        "godot": _gate_status("godot"),
        "research_ui": _gate_status("research_ui"),
        "mypy": _gate_status("mypy"),
        "ruff": _gate_status("ruff"),
        "import_contracts": _gate_status("imports"),
    }
    limitations = [
        "Synthetic test identity is not a release-source attestation.",
        "Supported scale claims stop at the separately measured V3-43 envelope.",
        (
            "Null results and absent institutions/money/myths/government/"
            "religion are valid."
        ),
        (
            "Durable subjective restart and recorded/live LLM fork "
            "continuation remain unsupported."
        ),
        "institutional_economy and multi_hop_testimony_tracking remain unowned.",
    ]
    if any(status != "passed" for status in gates.values()):
        limitations.append(
            "One or more external gates are unexecuted or failed; no full release "
            "certification follows from this matrix."
        )
    return {
        "schema": _MATRIX_SCHEMA,
        "suite_id": "v3-generational-civilization-benchmark-v1",
        "source_identity": {
            "code_revision": _source_arguments()[1],
            "source_artifact_digest": _source_arguments()[3],
            "source_clean": False,
            "evidence_kind": (
                "explicit_source_identity"
                if os.environ.get(_DIGEST_ENV, "").strip()
                else "synthetic_test_identity"
            ),
        },
        "profiles": {
            "mechanism_smoke": {
                "seed": SMOKE_SEED,
                "run_count": len(mechanisms),
                "completed_count": sum(
                    1
                    for document in mechanisms
                    if _execution_summary(document)["status"] == "completed"
                ),
            },
            "research_smoke": {
                "seed": SMOKE_SEED,
                "run_count": len(research_smoke),
                "completed_count": sum(
                    1
                    for document in research_smoke
                    if _execution_summary(document)["status"] == "completed"
                ),
            },
            "research": {
                "seeds": list(RESEARCH_SEEDS),
                "run_count": len(research),
                "completed_count": sum(
                    1
                    for document in research
                    if _execution_summary(document)["status"] == "completed"
                ),
            },
        },
        "scenarios": scenarios,
        "completion_criteria": _completion_criteria(scenarios),
        "criteria": criteria,
        "gates": gates,
        "limitations": limitations,
    }


@pytest.fixture(scope="module")
def qualification() -> _Qualification:
    root = _benchmark_root()
    if root.exists():
        shutil.rmtree(root)
    scenario_ids = tuple(
        spec.scenario_id for spec in list_v3_benchmark_scenarios()
    )
    mechanism_root = root / "mechanism"
    research_smoke_root = root / "research-smoke"
    twin_root = root / "research-smoke-twin"
    research_root = root / "research"

    _run_lane(mechanism_root, profile="smoke", lane="mechanism")
    _verify(mechanism_root, require_complete=True)
    _run_lane(
        research_smoke_root,
        profile="smoke",
        lane="research",
        expect_gate_pass=False,
    )
    _verify(research_smoke_root, require_complete=False)
    _run_lane(
        twin_root,
        profile="smoke",
        lane="research",
        expect_gate_pass=False,
    )
    _verify(twin_root, require_complete=False)
    _run_lane(
        research_root,
        profile="research",
        lane="research",
        expect_gate_pass=False,
    )
    _verify(research_root, require_complete=False)

    mechanisms = _documents(mechanism_root)
    research_smoke = _documents(research_smoke_root)
    twin = _documents(twin_root)
    research = _documents(research_root)
    assert len(mechanisms) == len(scenario_ids)
    assert len(research_smoke) == len(scenario_ids)
    assert len(research) == len(scenario_ids) * len(RESEARCH_SEEDS)
    twin_matches = tuple(
        document["artifact_hash"] for document in research_smoke
    ) == tuple(document["artifact_hash"] for document in twin)

    comparison = build_v3_benchmark_comparison(
        _comparison_observations(research)
    )
    matrix = _matrix(
        mechanisms=mechanisms,
        research_smoke=research_smoke,
        research=research,
        twin_matches=twin_matches,
    )
    matrix["comparison"] = comparison.to_payload()
    matrix_path = root / "qualification-matrix.json"
    matrix_path.write_text(
        json.dumps(
            matrix, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    return _Qualification(
        root=root,
        mechanisms=mechanisms,
        research_smoke=research_smoke,
        twin=twin,
        research=research,
        comparison=comparison,
        matrix=matrix,
        twin_matches=twin_matches,
    )


def test_every_required_run_completed_its_declared_horizon(
    qualification: _Qualification,
) -> None:
    for document in qualification.mechanisms:
        summary = _execution_summary(document)
        assert summary["status"] == "completed"
        assert summary["ticks_committed"] == summary["declared_horizon"]
        assert summary["evidence"] == "complete"
        assert summary["passing_check_count"] == summary["check_count"]
        assert summary["phenomenon"] in {"detected", "not_detected", "unknown"}
    for document in (
        *qualification.research_smoke,
        *qualification.research,
        *qualification.twin,
    ):
        summary = _execution_summary(document)
        assert summary["status"] == "completed"
        assert summary["ticks_committed"] == summary["declared_horizon"]
        assert summary["coverage"] == "exercised"
        assert summary["evidence"] in {"complete", "partial"}
        assert summary["phenomenon"] in {
            "detected",
            "not_detected",
            "unknown",
            "not_applicable",
        }
        checks = document["checks"]
        assert isinstance(checks, list)
        for check in checks:
            assert isinstance(check, Mapping)
            assert check["status"] in {"pass", "unexecuted"}
            if check["status"] == "unexecuted":
                assert check["evidence"] in {"complete", "partial"}


def test_deterministic_twins_match_in_a_separate_namespace(
    qualification: _Qualification,
) -> None:
    assert qualification.twin_matches is True
    assert len(qualification.research_smoke) == len(qualification.twin)
    for left, right in zip(
        qualification.research_smoke, qualification.twin, strict=True
    ):
        assert left["scenario_id"] == right["scenario_id"]
        assert left["seed"] == right["seed"]
        assert left["artifact_hash"] == right["artifact_hash"]


def test_completion_matrix_covers_every_request_and_limitations(
    qualification: _Qualification,
) -> None:
    matrix = qualification.matrix
    scenarios = matrix["scenarios"]
    assert isinstance(scenarios, list)
    assert len(scenarios) == V3_BENCHMARK_SCENARIO_COUNT
    assert {item["request_number"] for item in scenarios} == set(
        range(1, V3_BENCHMARK_SCENARIO_COUNT + 1)
    )
    assert all(item["complete"] for item in scenarios)
    criteria = matrix["criteria"]
    assert isinstance(criteria, list)
    assert all(item["status"] == "present" for item in criteria)
    completion = matrix["completion_criteria"]
    assert isinstance(completion, list)
    assert len(completion) == 19
    for item in completion:
        assert item["status"] in {
            "verified_by_mechanism_lane",
            "unexecuted_external_gate",
            "blocked",
        }
        if item["status"] == "verified_by_mechanism_lane":
            assert item["verified_scenario_ids"] == item["scenario_ids"]
    limitations = matrix["limitations"]
    assert isinstance(limitations, list)
    assert any("null" in line.lower() for line in limitations)
    gates = matrix["gates"]
    assert isinstance(gates, dict)
    assert set(gates.values()) <= {"passed", "failed", "unexecuted"}
    assert (qualification.root / "qualification-matrix.json").exists()


def test_comparison_keeps_descriptive_blocks_without_forcing_effects(
    qualification: _Qualification,
) -> None:
    comparison = qualification.comparison
    assert comparison.schema_version == "civilization-benchmark-comparison-v1"
    assert comparison.descriptive
    assert comparison.contrasts == ()
    for summary in comparison.descriptive:
        assert summary.block_count <= len(RESEARCH_SEEDS)
        assert summary.raw_observation_count >= summary.block_count
        assert summary.inference_status in {
            "present",
            "insufficient_independent_seeds",
            "uncontrolled_provider_variation",
        }
        if summary.block_count < 2:
            assert summary.ci_low is None and summary.ci_high is None
