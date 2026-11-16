# Phase 3: Ledger Export, Snapshot, Store, and Publication

Plan: [index.md](index.md)
Tasks: 9-12
Depends on: Phase 2 (Tasks 5-8)

## Objective

Carry the owner experiment ledger through runtime checkpoints, final results,
newborn blank slates, and the completed-run bridge; define the canonical bounded
`scientific-hypotheses-snapshot-v1`; persist it with
`scientific-hypotheses-store-v1`; and publish it programmatically after
scientific completion. The bridge reads only the run's declared science flag and
exported owner ledgers plus committed events. It never reads objective laws,
rule rows, deltas, products, or probabilities.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/runner_models.py` | `SimulationRunnerResult` (6354), `formal_rule_ledgers` field (6403), ordered-sequence validation (6731-6743) | Runtime-only result export pattern |
| `src/simulation/runner.py` | formal-ledger collection/export (5435, 5855-5868) | Exact place to collect each loop's experiment ledger |
| `src/simulation/agent_runtime.py` | checkpoint restore (3861-3864), export (4026), world-model audit (5054-5055) | Owner-store checkpoint/export template |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint` (590), `formal_rules` (621), owner validation (838-844) | Checkpoint field pattern |
| `src/agents/cognition/loop.py` | `experiment_ledger_for` (4722-4762), loop state carry (285-334, 1811) | Public accessor the runner can call |
| `src/simulation/new_agent_initialization.py` | deny list (150-188), blank-slate stores (191-221), counts (864-896) | Admission must copy no hypothesis content |
| `src/experiments/civilization_benchmark_evidence.py` | `NOT_PERSISTED_STORES` (41-52), `STORE_PROBE_PATHS` (55-82) | Once persisted, the experiment ledger becomes measurable evidence |
| `src/experiments/formal_rule_harvest.py` | ledger harvest (50-70) | Detached owner-ledger bridge template |
| `src/experiments/collectors.py` | formal gate (1257-1264), cascade gate (587-618) | Feature gate and `replace(inputs, ...)` injection |
| `src/simulation/economic_cascades_models.py` | versions/caps (27-33), records (96-353), empty (356-380) | Snapshot model template |
| `src/simulation/economic_cascades_codec.py` | canonical JSON (76-102), digest (105-126), finalize/encode/decode (129-239) | Codec template |
| `src/simulation/economic_cascades_paging.py` | limits/purposes (18-27), page function (74-120) | Paging template |
| `src/simulation/economic_cascades_ports.py` | cursor token/purposes/fingerprint/protocols (18-84) | Ports template |
| `src/persistence/economic_cascades_filesystem.py` | atomic write (115-126), lock (129-140), publish (143-212), read (215-244) | Atomic store template |
| `src/infrastructure/settings.py` | cascade root/key (276-279), root validator (335), key validator (530-539), bootstrap (987-999) | Dual-gate settings pattern |
| `src/experiments/economic_cascades_publication.py` | compose (73-187), publish (190-249) | Publication template |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/experimentation.py` | modify | Add `require_owner_experiment_ledger` and a serializable owner export helper |
| `src/simulation/runner_models.py` | modify | Add `experiment_ledgers` to `SimulationRunnerResult` with owner/type validation |
| `src/simulation/runner.py` | modify | Collect and attach each loop's experiment ledger |
| `src/simulation/agent_runtime.py` | modify | Restore/export the checkpoint ledger |
| `src/simulation/run_control.py` | modify | Add `AgentRuntimeCheckpoint.experiment_ledger` and owner validation |
| `src/simulation/new_agent_initialization.py` | modify | Add the ledger to deny list, blank-slate stores, and counts |
| `src/experiments/civilization_benchmark_evidence.py` | modify | Remove `experiment_ledger` from not-persisted and add the runtime probe |
| `src/experiments/scientific_hypotheses_completed_run.py` | create | Map ledgers to detached facts and build the analysis |
| `src/experiments/collectors.py` | modify | Final science gate and analysis injection |
| `src/experiments/__init__.py` | modify | Export completed-run and publication symbols |
| `src/simulation/scientific_hypotheses_models.py` | create | Snapshot records, caps, empty builder |
| `src/simulation/scientific_hypotheses_codec.py` | create | Canonical encode/decode, digest, publication id |
| `src/simulation/scientific_hypotheses_paging.py` | create | Purpose-bound paging |
| `src/simulation/scientific_hypotheses_ports.py` | create | Cursor, fingerprint, reader/publisher protocols |
| `src/simulation/__init__.py` | modify | Re-export snapshot symbols |
| `src/persistence/scientific_hypotheses_filesystem.py` | create | Atomic filesystem store |
| `src/infrastructure/settings.py` | modify | Root, cursor key, validators, bootstrap flags |
| `src/experiments/scientific_hypotheses_publication.py` | create | Compose, publish, receipt |
| `tests/unit/test_scientific_hypotheses_export.py` | create | Result/checkpoint/blank-slate export |
| `tests/unit/test_scientific_hypotheses_completed_run.py` | create | Fact mapping, no-law boundary, required events |
| `tests/unit/test_scientific_hypotheses_collector.py` | create | Gate and injection |
| `tests/unit/test_scientific_hypotheses_snapshot.py` | create | Records, caps, no wall clock/owner/rule fields |
| `tests/unit/test_scientific_hypotheses_codec.py` | create | Round-trip, canonical, corruption |
| `tests/unit/test_scientific_hypotheses_paging.py` | create | Limits, windows, deterministic next key |
| `tests/unit/test_scientific_hypotheses_ports.py` | create | Fingerprint/purpose coverage |
| `tests/unit/test_scientific_hypotheses_store.py` | create | Atomicity, idempotency, quotas |
| `tests/unit/test_scientific_hypotheses_settings.py` | create | Dual gate and validation |
| `tests/unit/test_scientific_hypotheses_publication.py` | create | Receipts and compose mapping |

## Task 9: Export experiment ledgers and wire completed-run inputs

### Intent
Make the owner hypothesis ledger survive long runs, generational admission, and
the completed-run boundary, then map it to detached analysis facts without
reading objective rules. A run without `science` produces no facts and no
analysis input.

### Implementation Steps
1. In `src/agents/cognition/experimentation.py`:
   - Add `require_owner_experiment_ledger(ledger, owner_id, *, field_name)`:
     returns the ledger only when it is an `ExperimentLedger` for that exact
     owner; otherwise raises `ValueError(f"{field_name}: owner_mismatch")`.
   - The completed-run bridge reads the ledger object's public attributes
     directly; do not introduce a second wire format for the owner export.
2. In `src/simulation/run_control.py`:
   - Add `experiment_ledger: object | None = None` next to `formal_rules`
     (621).
   - In `AgentRuntimeCheckpoint.__post_init__`, validate it with
     `require_owner_experiment_ledger(self.experiment_ledger, self.agent_id,
     field_name="experiment_ledger")` when not `None`.
3. In `src/agents/cognition/loop.py`, add two public helpers next to
   `experiment_ledger_for` (4722-4762):
   - `experiment_ledger_if_present() -> ExperimentLedger | None` returns the
     current owner ledger without constructing an empty one; it returns `None`
     when science never ran for this loop.
   - `restore_experiment_ledger(ledger) -> None` validates the owner and installs
     the checkpoint ledger.
   Then in `src/simulation/agent_runtime.py`, mirror the formal-rule path:
   - in `export_runtime_checkpoint` (4007-4038), set
     `experiment_ledger=self._loop.experiment_ledger_if_present()`;
   - during restore (3861-3864), call
     `self._loop.restore_experiment_ledger(checkpoint.experiment_ledger)` when
     the checkpoint value is not `None`.
   - If the runtime checkpoint codec uses an exact key set, add the key only to
     the current checkpoint schema and keep prior checkpoints decodable. Do not
     change the replay event schema or codec maxima; replay stays v27/`v25`.
4. In `src/simulation/runner_models.py`:
   - Add `experiment_ledgers: tuple[object, ...] = ()` to
     `SimulationRunnerResult` after `formal_rule_ledgers` (6403). This is a
     runtime result field, not a `SimulationRunnerResultDocument` field; do not
     bump `runner-result-v2/v3` or add a serialized result key.
   - Validate it as an ordered sequence of `ExperimentLedger` values owned by
     the run's agents; reject sets, strings, and foreign owners. Import
     `ExperimentLedger` lazily inside `__post_init__` to avoid a module cycle.
5. In `src/simulation/runner.py`, add
   `export_experiment_ledgers()` following `export_formal_rule_ledgers`
   (5855-5868): iterate `self._runtimes`, read
   `checkpoint.experiment_ledger`, skip `None`, and return an owner-ordered
   tuple. Pass `experiment_ledgers=self.export_experiment_ledgers()` where the
   result is constructed next to `formal_rule_ledgers` (5435). Do not create a
   new empty ledger for an agent that never enabled science.
6. In `src/simulation/new_agent_initialization.py`:
   - Add `"experiment_ledger"` to `SUBJECTIVE_COPY_DENY_LIST` and
     `BLANK_SLATE_SUBJECTIVE_STORES`.
   - Add `experiment_ledger: int = 0` to `BlankSlateStoreCounts`.
   - `assert_blank_slate_subjective_state` must reject admitted newborns whose
     ledger has any hypothesis, revision, or trial.
7. In `src/experiments/civilization_benchmark_evidence.py`:
   - Remove `"experiment_ledger"` from `NOT_PERSISTED_STORES`.
   - Add `"experiment_ledger": ("runtime", "experiment_ledger")` to
     `STORE_PROBE_PATHS`.
   - Update the benchmark evidence tests that asserted it was unmeasurable.
8. Create `src/experiments/scientific_hypotheses_completed_run.py`:
   - `scientific_hypothesis_facts(runner_result) -> tuple[HypothesisFact, ...]`:
     read only `runner_result.runner_config.v4_capability_flags.science` and
     `runner_result.experiment_ledgers`; map each ledger with
     `mint_owner_token`, `mint_claim_token`, and `mint_hypothesis_token`;
     copy conditions, revisions, trials, support/counter, confidence, status,
     source kind/token, and the optional causal hypothesis token; map a missing
     prediction or causal link to `NONE_TOKEN`. For condition slot `counterpart`,
     replace the raw agent id with `mint_owner_token(value)` so the snapshot
     never carries another owner id; other slots keep stable objective
     kind/location tokens. Never read
     `runner_config.bounded_experimentation.laws`.
   - `build_completed_run_scientific_hypotheses_analysis(runner_result=None, *,
     committed_events, run_id, facts=None, policy=None, window_end=None)`:
     require `committed_events` (`scientific_hypotheses_requires_events`),
     validate `run_id`, default facts from the helper, and call
     `harvest_scientific_hypotheses_analysis`.
9. In `src/experiments/collectors.py`, add a gate after the cascade block:
   - require `events is not None`, `flags.science` is true, and
     `runner_result.experiment_ledgers` is non-empty;
   - lazily import the builder, call it with the run id and events, and
     `replace(inputs, scientific_hypotheses_analysis=analysis)`;
   - on exception log WARN `scientific_hypotheses_collection_failed` and leave
     the bundle unchanged.
10. Export the bridge from `src/experiments/__init__.py`.

### Required Interfaces and Contracts
- The bridge reads only the declared science flag, exported ledgers, and
  committed events. It never reads `WorldState`, runtime objects, stores,
  `bounded_experimentation.laws`, `world._experiment_laws`, or `world._rules`.
- No objective rule, delta, product, harm, or probability field enters a fact.
- Checkpoints preserve one owner's ledger; admission copies nothing.
- A run without science or without ledgers produces no analysis input.
- Collection failure never aborts metric assembly.

### Requirement Evidence
- Original Request "historical revisions", "creator/source", "Do not expose
  objective rules".
- `src/experiments/formal_rule_harvest.py:50-70` and
  `src/simulation/runner.py:5855-5868` (owner-ledger export pattern).
- `src/simulation/new_agent_initialization.py:150-221` (blank-slate rule).
- `.ai-factory/ARCHITECTURE.md` requirement 4 (subjective stores stay outside
  the objective fold) and analysis isolation.

### Error Handling and Logging
- INFO `scientific_hypotheses_exported owners=<n> hypotheses=<n>`.
- WARN `scientific_hypotheses_collection_failed`,
  `scientific_hypotheses_missing_events`, and
  `scientific_hypotheses_ledger_owner_mismatch` with codes only.
- ERROR `scientific_hypotheses_completed_run_invalid` with a closed code.
- Never log claims, conditions, evidence ids, owner tokens, or ledger payloads.

### Tests
- `tests/unit/test_scientific_hypotheses_export.py`:
  - result field accepts an ordered tuple of owner ledgers and rejects a set,
    string, or foreign-owner ledger.
  - checkpoint round-trips one ledger and rejects a foreign owner.
  - `experiment_ledger_if_present()` returns `None` without creating a row when
    science never ran, and returns the owner ledger after a test.
  - newborn blank-slate assertion rejects a non-empty ledger and accepts empty.
  - export contains no law/rule/probability/delta/product/harm key.
  - `civilization_benchmark_evidence` reports the store as measurable.
- `tests/unit/test_scientific_hypotheses_completed_run.py`:
  - facts tokenize owner/source and preserve all requested fields.
  - a `counterpart` condition value is tokenized; no raw agent id appears in a
    fact, row, or snapshot.
  - a ledger from a run without science is not accepted by the gate.
  - `bounded_experimentation.laws` is never read (source/boundary assertion).
  - missing events raises `scientific_hypotheses_requires_events`.
  - explicit facts override derivation.
- `tests/unit/test_scientific_hypotheses_collector.py`: gate off -> no
  analysis; gate on -> injected analysis; builder failure -> WARN and unchanged
  bundle.

### Acceptance Criteria
- Hypotheses survive checkpoints and appear in the final result.
- Newborns start with an empty ledger.
- The completed-run bridge maps every requested field with no objective rule.
- Science-off runs and empty ledgers produce no analysis input.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_export.py tests/unit/test_scientific_hypotheses_completed_run.py tests/unit/test_scientific_hypotheses_collector.py -q`
- Expected result: pass.

## Task 10: Add snapshot models, codec, paging, and ports

### Intent
Define the canonical, digest-addressed, wall-clock-free snapshot and its bounded
read contract. The snapshot exposes hypothesis-level tokens, counts, confidence
milli, statuses, sources, revisions, tests, and coverage; it exposes no owner id,
objective rule, law, delta, product, harm, probability, truth, or score.

### Implementation Steps
1. Create `src/simulation/scientific_hypotheses_models.py`:
   - `SCIENTIFIC_HYPOTHESES_SNAPSHOT_VERSION =
     "scientific-hypotheses-snapshot-v1"`,
     `SCIENTIFIC_HYPOTHESES_POLICY_VERSION = "scientific-hypotheses.v1"`,
     `SCIENTIFIC_HYPOTHESES_PUBLICATION_PREFIX = "schyp-"`,
     `MAX_SCIENTIFIC_HYPOTHESIS_ROWS = 4_096`,
     `MAX_SCIENTIFIC_HYPOTHESIS_EVIDENCE_ROWS = 4_096`,
     `MAX_SCIENTIFIC_HYPOTHESIS_REVISION_ROWS = 8_192`,
     `MAX_SCIENTIFIC_HYPOTHESIS_TRIAL_ROWS = 4_096`,
     `MAX_SCIENTIFIC_HYPOTHESES_SNAPSHOT_BYTES = 8_388_608`,
     `MAX_SCIENTIFIC_HYPOTHESES_WINDOW_INDEX = 511`.
   - Frozen records:
     `ScientificHypothesisSummaryRecord` (`window_tick`, `window_count`,
     `coverage`, `availability`, `owner_count`, `hypothesis_count`,
     `active_count`, `supported_count`, `contradicted_count`,
     `inconclusive_count`, `revision_count`, `trial_count`,
     `matched_count`, `mismatched_count`),
     `ScientificHypothesisRecord` (`window_index`, `window_tick`,
     `hypothesis_token`, `claim_token`, `causal_hypothesis_token`, `status`,
     `predicted_outcome`, `confidence_milli`, `condition_count`,
     `condition_pairs`, `support_count`, `contradiction_count`,
     `revision_count`, `source_kind`, `active`, `created_tick`, `coverage`) —
     `condition_pairs` is an ordered tuple of at most eight
     `(slot, value_token)` pairs and carries no objective-rule field,
     `ScientificHypothesisEvidenceRecord` (`window_index`, `window_tick`,
     `hypothesis_token`, `support_observation_count`, `contradiction_count`,
     `evidence_event_count`, `unlinked_event_count`, `coverage`),
     `ScientificHypothesisTestRecord` (`window_index`, `window_tick`,
     `hypothesis_token`, `trial_count`, `matched_count`, `mismatched_count`,
     `inconclusive_count`, `last_trial_tick`, `coverage`),
     `ScientificHypothesisRevisionRecord` (`window_index`, `window_tick`,
     `hypothesis_token`, `revision_index`, `revision_tick`, `reason`,
     `claim_token`, `predicted_outcome`, `condition_pairs`,
     `confidence_milli`, `coverage`),
     `ScientificHypothesisSourceRecord` (`window_index`, `window_tick`,
     `source_kind`, `hypothesis_count`, `adopted_count`, `coverage`),
     `ScientificHypothesisCoverageRecord` (`window_index`, `window_tick`,
     `window_count`, `event_count`, `owner_count`, `hypothesis_count`,
     `condition_count`, `revision_count`, `trial_count`, `truncated`,
     `coverage`, `availability`).
   - `ScientificHypothesesSnapshot` (`snapshot_version`, `policy_version`,
     `run_id`, `generated_from_tick`, `summary`, `hypotheses`, `evidence`,
     `tests`, `revisions`, `sources`, `coverage`, `internal_digest`,
     `publication_id`) with independent row caps and no wall-clock, owner,
     objective-rule, truth, or score field.
   - `empty_scientific_hypotheses_snapshot(run_id=...)`.
2. Create `src/simulation/scientific_hypotheses_codec.py`:
   - Canonical JSON: sorted keys, compact separators, ASCII, `allow_nan=False`,
     trailing newline.
   - `finalize_scientific_hypotheses_snapshot`: blank digest/publication id,
     SHA-256 over the canonical body, set `internal_digest`, set
     `publication_id = "schyp-" + digest[:16]`.
   - `encode_scientific_hypotheses_snapshot` enforces the byte cap.
   - `decode_scientific_hypotheses_snapshot` rejects duplicate keys, unknown
     fields, version mismatch, run mismatch, digest mismatch, non-canonical
     bytes, and oversize with closed codes.
3. Create `src/simulation/scientific_hypotheses_paging.py`:
   - `DEFAULT_SCIENTIFIC_HYPOTHESES_LIMIT = 100`,
     `MAX_SCIENTIFIC_HYPOTHESES_LIMIT = 500`.
   - Purposes `hypotheses`, `evidence`, `tests`, `revisions`, `sources`,
     `coverage`; `windows` projects `(window_index, window_tick)` from coverage.
   - `page_scientific_hypothesis_rows(snapshot, *, purpose, window_index=None,
     limit=100, after=None)` returns `(rows, next_key)`; filter by window before
     paging; deterministic stable sort.
4. Create `src/simulation/scientific_hypotheses_ports.py`:
   - `SCIENTIFIC_HYPOTHESES_CURSOR_TOKEN =
     "palimpsest.scientific_hypotheses.cursor.v1"`,
     `SCIENTIFIC_HYPOTHESES_CURSOR_PURPOSES`,
     `ScientificHypothesesCursor` (`purpose`, `window_index`, `after`,
     `query_fingerprint`),
     `scientific_hypotheses_query_fingerprint(...)`, and
     `ScientificHypothesesReader` / `ScientificHypothesesPublisher` protocols.
5. Re-export the public symbols from `src/simulation/__init__.py`.

### Required Interfaces and Contracts
- Snapshot bytes are canonical and digest-addressed; no wall-clock field.
- Hypothesis records carry `created_tick`; revision records carry
  `revision_tick`, so historical order is explicit without wall-clock time.
- Decode is strict and fail-closed.
- Paging is pure, snapshot-bound, and window-bound.
- Row caps are enforced by the model, not only by the codec.
- No snapshot field can carry an owner id, objective rule, law, delta, product,
  harm, probability, truth, verified, proven, accuracy, calibration, or score.

### Requirement Evidence
- `src/simulation/economic_cascades_models.py:27-380` and
  `src/simulation/economic_cascades_codec.py:76-239`.
- `src/simulation/economic_cascades_paging.py:18-120`.
- `src/simulation/economic_cascades_ports.py:18-84`.
- Original Request representation list and "Do not expose objective rules".

### Error Handling and Logging
- WARN `scientific_hypotheses_snapshot_capped`,
  `scientific_hypotheses_snapshot_oversize`.
- ERROR `scientific_hypotheses_snapshot_invalid` with a code only.
- Never log row contents, digests as payload surrogates, or owner tokens.

### Tests
- `tests/unit/test_scientific_hypotheses_snapshot.py`: record validation,
  independent caps, empty snapshot, no wall-clock/owner/rule fields,
  `created_tick`/`revision_tick` timelines.
- `tests/unit/test_scientific_hypotheses_codec.py`: canonical round-trip,
  digest stability, tamper/unknown/oversize/run-mismatch rejection.
- `tests/unit/test_scientific_hypotheses_paging.py`: default/max limits, window
  filter before paging, deterministic next key, invalid purpose/limit.
- `tests/unit/test_scientific_hypotheses_ports.py`: cursor token/purposes,
  fingerprint sensitivity to run/publication/digest/purpose/window/limit.

### Acceptance Criteria
- Snapshot round-trips byte-identically after one finalize.
- Corrupt or widened payloads are rejected, never partially read.
- No paging purpose can read another purpose's rows.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_snapshot.py tests/unit/test_scientific_hypotheses_codec.py tests/unit/test_scientific_hypotheses_paging.py tests/unit/test_scientific_hypotheses_ports.py -q`
- Expected result: pass.

## Task 11: Add the atomic store and dual-gated settings

### Intent
Persist science publications safely and keep the reader off unless both settings
are present, matching every other V4 detached surface.

### Implementation Steps
1. Create `src/persistence/scientific_hypotheses_filesystem.py`:
   - `SCIENTIFIC_HYPOTHESES_STORE_VERSION =
     "scientific-hypotheses-store-v1"`, `STATE_FILE = "state.json"`,
     `LOCK_FILE = "store.lock"`.
   - `ScientificHypothesesPublisherOptions(max_publications=16,
     max_bytes=8_388_608)` with range validation.
   - Atomic commit: temp file in the run directory, `flush`, `fsync`,
     `os.replace`; `state.json` is the publication index; the artifact is
     `root/<run_id>/<publication_id>.json`.
   - `fcntl.flock` around state reads/writes.
   - Idempotency: same publication id and digest -> `stored=False`; same id with
     a different digest -> `scientific_hypotheses_publication_exists`.
   - Quotas: per-snapshot byte cap, publication count, cumulative bytes; closed
     codes `scientific_hypotheses_store_quota_exceeded`,
     `scientific_hypotheses_store_corrupt`,
     `scientific_hypotheses_publication_missing`.
   - Reader selects the latest publication when no id is supplied; corruption
     or missing state fails closed.
   - Public factories `scientific_hypotheses_store_reader(root, ...)` and
     `scientific_hypotheses_store_publisher(root, options=...)`.
2. In `src/infrastructure/settings.py`:
   - Add `scientific_hypotheses_root: Path | None = None` and
     `scientific_hypotheses_cursor_key: SecretStr | None = None`.
   - Register the root in the empty-string -> `None` validator and the key in a
     ≥32-byte validator.
   - Add `has_scientific_hypotheses_root`,
     `has_scientific_hypotheses_cursor_key`,
     `scientific_hypotheses_enabled`, and
     `scientific_hypotheses_cursor_enabled` to `bootstrap_fields()`.
3. Keep `extra="forbid"` and the `PALIMPSEST_` prefix; no secret is required at
   import time.

### Required Interfaces and Contracts
- Environment names are `PALIMPSEST_SCIENTIFIC_HYPOTHESES_ROOT` and
  `PALIMPSEST_SCIENTIFIC_HYPOTHESES_CURSOR_KEY`.
- Store writes are atomic and lock-protected; a partial write is never visible.
- Settings default to `None`; the feature is off unless both are set.
- No SQL table, migration, or runner flag is added.

### Requirement Evidence
- `src/persistence/economic_cascades_filesystem.py:115-244`.
- `src/infrastructure/settings.py:276-279,335,530-539,987-999`.
- `.ai-factory/ARCHITECTURE.md` requirement 5 (SQL only for a proven
  inspection need).

### Error Handling and Logging
- INFO `scientific_hypotheses_store_published publications=<n> bytes=<n>`.
- WARN `scientific_hypotheses_store_quota_exceeded`,
  `scientific_hypotheses_publication_exists`.
- ERROR `scientific_hypotheses_store_corrupt` with a code only.
- Never log paths, digests, publication ids, or payloads.

### Tests
- `tests/unit/test_scientific_hypotheses_store.py`: atomic replace, idempotent
  republish, conflict on differing digest, count/byte quotas, corrupt state,
  missing run, lock contention simulation.
- `tests/unit/test_scientific_hypotheses_settings.py`: both unset, root only,
  key only, both set, short key rejection, empty root normalization, bootstrap
  flags.

### Acceptance Criteria
- Republishing the same digest is a no-op.
- A corrupt state file never yields rows.
- Both settings are required for `scientific_hypotheses_enabled`.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_store.py tests/unit/test_scientific_hypotheses_settings.py -q`
- Expected result: pass.

## Task 12: Compose and publish completed-run snapshots

### Intent
Map the analysis to the canonical snapshot and publish it after completion with
closed receipts. Publication is a caller decision; a disabled publication leaves
scientific status untouched.

### Implementation Steps
1. Create `src/experiments/scientific_hypotheses_publication.py`:
   - `compose_scientific_hypotheses_snapshot(analysis, *, run_id,
     generated_from_tick=None) -> ScientificHypothesesSnapshot` mapping:
     summary from analysis counts and availability; hypotheses from hypothesis
     rows (drop `owner_token`, keep `created_tick`, `condition_pairs`, and
     `causal_hypothesis_token`); evidence records from hypothesis evidence counts
     (objective events with no owner trial link contribute only to coverage and
     the summary event count); tests from trial rows; revisions from revision
     rows (keep `revision_tick`); sources from source rows; coverage from
     coverage rows. Call `finalize_scientific_hypotheses_snapshot`.
   - `publish_scientific_hypotheses_snapshot(*, analysis, run_id, reader=None,
     publisher=None, enabled=True, options=None) ->
     ScientificHypothesesPublicationReceipt` with statuses
     `publication_missing`, `publication_disabled`, `store_quota_exceeded`,
     `store_corrupt`, `published`. A disabled or missing analysis writes nothing
     and reports the status; it never raises for an environment gate.
   - `build_scientific_hypotheses_harvest_result(analysis, publication)`
     returning analysis plus receipt.
2. Call publication only from the programmatic completed-run path; do not add a
   CLI command, runner flag, or API write.
3. Export the public functions from `src/experiments/__init__.py`.

### Required Interfaces and Contracts
- Snapshot composition is pure; publication is the only side effect.
- Scientific status is never changed by publication.
- A quota or corruption failure is reported, never retried silently.
- No wall-clock value, owner id, objective rule, truth, or score enters the
  snapshot.
- The mapping drops every `owner_token` before serialization.

### Requirement Evidence
- `src/experiments/economic_cascades_publication.py:73-249`.
- Original Request "Do not expose objective rules" and the artifact pattern of
  V4-24 through V4-26.

### Error Handling and Logging
- INFO `scientific_hypotheses_published publication=<status>` (status token
  only).
- WARN `scientific_hypotheses_publication_disabled`,
  `scientific_hypotheses_publication_quota_exceeded`.
- ERROR `scientific_hypotheses_publication_failed` with a code only.
- Never log digests, ids, rows, or subject-tied byte counts.

### Tests
- `tests/unit/test_scientific_hypotheses_publication.py`: compose mapping,
  owner-token removal, all five receipt statuses, disabled path writes nothing,
  quota path writes nothing, idempotent republish, no wall-clock field.

### Acceptance Criteria
- A composed snapshot validates and carries no owner id or objective rule.
- Every failure maps to one closed receipt status.
- Publication is never invoked by simulation or API code.

### Verification
- `uv run pytest tests/unit/test_scientific_hypotheses_publication.py -q`
- Expected result: pass.

## Phase Risks and Mitigations
- Risk: ledger export carries law rows or objective deltas.
  Mitigation: the export allowlist and boundary tests reject every rule field.
- Risk: checkpointing changes replay identity.
  Mitigation: the checkpoint field is optional and owner-validated; no replay
  event/codec constant changes, and a checkpoint round-trip test pins it.
- Risk: publication leaks owner tokens.
  Mitigation: composition drops `owner_token` and the codec test scans bytes.
- Risk: a corrupt store returns partial rows.
  Mitigation: strict decode before row access and a corruption test per layer.

## Phase Completion Checklist
- Ledgers survive checkpoints and appear in final results.
- Newborns start empty; admission copies nothing.
- The completed-run bridge maps all requested fields with no objective rule.
- Snapshot, store, and publication are canonical, atomic, and read-only.
- `index.md` Tasks 9-12 checkboxes are updated after verification.
