# mypy: ignore-errors
"""Hash-seed and repeat determinism for tokens, analysis, and snapshot bytes."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_CODE = """
import hashlib, json
from analysis.scientific_hypotheses_analysis import (
    harvest_scientific_hypotheses_analysis,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_rows import HypothesisFact
from experiments.scientific_hypotheses_publication import (
    compose_scientific_hypotheses_snapshot,
)
from simulation.scientific_hypotheses_codec import encode_scientific_hypotheses_snapshot
from world.experimentation import ExperimentOutcomeClass
facts = []
for index in range(4):
    facts.append(HypothesisFact(
        owner_token=f"owner-{index}",
        hypothesis_token=f"schyp-{index}",
        claim_token=f"claim-{index}",
        causal_hypothesis_token=NONE_TOKEN,
        status=ScientificHypothesisStatus.PROVISIONAL,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        confidence_milli=500,
        created_tick=index,
        active=True,
        source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
        source_token="self",
        conditions=(),
        revisions=(),
        trials=(),
    ))
analysis = harvest_scientific_hypotheses_analysis(events=(), facts=tuple(facts))
snapshot = compose_scientific_hypotheses_snapshot(analysis, run_id="run-determinism")
payload = encode_scientific_hypotheses_snapshot(snapshot)
print(json.dumps({
    "tokens": [row.hypothesis_token for row in analysis.hypothesis_rows],
    "revisions": [row.revision_index for row in analysis.revision_rows],
    "digest": snapshot.internal_digest,
    "bytes": hashlib.sha256(payload).hexdigest(),
}))
"""


def _run(seed: str) -> dict[str, object]:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    output = subprocess.run(
        [sys.executable, "-c", _CODE],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(output.stdout.strip().splitlines()[-1])


def test_hash_seed_independence() -> None:
    assert _run("0") == _run("1")


def test_repeat_composition_is_idempotent() -> None:
    assert _run("0") == _run("0")


def test_canonical_json_has_sorted_keys_and_trailing_newline() -> None:
    from analysis.scientific_hypotheses_analysis import (
        harvest_scientific_hypotheses_analysis,
    )
    from experiments.scientific_hypotheses_publication import (
        compose_scientific_hypotheses_snapshot,
    )
    from simulation.scientific_hypotheses_codec import (
        encode_scientific_hypotheses_snapshot,
    )

    snapshot = compose_scientific_hypotheses_snapshot(
        harvest_scientific_hypotheses_analysis(events=(), facts=()),
        run_id="run-canonical",
    )
    payload = encode_scientific_hypotheses_snapshot(snapshot)
    assert payload.endswith(b"\n")
    text = payload.decode("utf-8")
    parsed = json.loads(text)
    assert text.rstrip("\n") == json.dumps(
        parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    assert hashlib.sha256(payload).hexdigest()
