# Implementation Plan: LLM Recording / Replay Layer

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-04
Improved: 2026-10-04 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan lands research reproducibility infrastructure for structured LLM I/O (not a capability flag) and does not claim `multi_hop_testimony_tracking`.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M6 — Remaining V2 Capability Flags
INFO [aif-plan] resolved plan file: .ai-factory/plans/v2-llm-recording-replay-layer.md (format=slug)
INFO [aif-improve] applied refinement: store settings composition-only; component inventory; wrap order; REQUIRED excludes cache; fork/matrix namespace lock

## Compatibility contract

This plan replaces the stub `RecordingPolicy.RECORDED` → `DeterministicFakeLLMProvider` fallback with a real record / cache / replay layer so Python/world changes can be compared while holding validated cognition outputs constant. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only objective mutation authority. Recorded/replayed `StructuredOutput` stays non-authoritative: cognition must still translate into a fresh `AgentCommand` and use normal admission. The `llm` package stays import-closed against world/simulation/API/infrastructure/persistence and forbids vendor SDKs.
2. No new capability flag. Modes ride on existing `RunnerProviderSettings.recording_policy` (plus composition-only recording-store settings). Do **not** own `multi_hop_testimony_tracking`. Owned flags stay owned and are not required.
3. V1 regression gate stays green under flags-off, tracing-off, and default `recording_policy=deterministic_fake`. Catalog A–E and the reference scenario keep current `exact_trajectory_hash` values. Do **not** append a new experiment to `tests/unit/test_v1_regression_gate.py`.
4. No agent-cognition runner-config bump. Default write stays `runner-config-v4`. Do **not** invent `runner-config-v23` for this feature. Provider JSON stays on `provider-settings-v1` with the **same exact key-set**; only the closed `recording_policy` enum values expand. Store root, namespace, and lookup mode are **composition-only** (`RecordingStoreSettings` beside `ProviderCredentials`) — never keys in `_encode_provider`, never in `provider_fingerprint` / result docs.
5. No scripted emergence. No friend/enemy/leader/culture labels.
6. No LLM → world shortcuts. Replay returns the same validated structured output shape a live call would; it never mutates world state or bypasses admission.
7. Experiments stay reproducible. `ExactReproducibilityMode.REQUIRED` allows **only** `deterministic_fake` and `replay`. Reject `live`, `record`, and `cache` with stable errors (`exact_reproducibility_forbids_<mode>`). Prefer network-free fakes for unit/CI.
8. Optional cognition tracing stays outside the objective fold. Recording stores are non-authoritative research artifacts (like cognition-trace): they must not enter `EvidenceManifest`, objective event replay, or trajectory hashes. Recording on vs off must not change `exact_trajectory_hash` when the policy is `deterministic_fake`.

## Goal

Implement a robust LLM recording/replay layer for research reproducibility.

For each structured LLM request, persist (or look up) a versioned exchange record containing:

| Field | Source |
| --- | --- |
| provider | Local `LLMResultMetadata.provider_name` / adapter label |
| model | Local `LLMResultMetadata.model_name` |
| normalized request/schema | Canonical request projection + schema identity (`response_model` qualname + JSON Schema digest) |
| relevant parameters | Effective options (temperature, max_output_tokens, top_p, seed, stop) + structured-output mode |
| response | Validated structured output JSON (model dump) |
| validation result | Closed status + reason code (`validated` / `schema_mismatch` / …) |
| token usage | Allowlisted `TokenUsage` or absent |
| latency | Injected monotonic duration (ms); never wall-clock domain time |
| correlation ids | `run_id`, `agent_id`, `tick`, `llm_request_id` (+ optional upstream id, never logged as payload) |
| simulation / agent / tick / component | Context fields; `component` is the cognition stage/component label |

Configurable modes:

| Mode | Provider contact | Persist | Lookup |
| --- | --- | --- | --- |
| `live` | yes | no | no |
| `record` | yes | yes (append/upsert into session store) | no (always call) |
| `cache` | on miss only | yes on miss | yes by safe cache key |
| `replay` | **never** | no | yes; miss / mismatch fail closed |

`replay` must let a simulation consume previously recorded **validated** responses without contacting the provider. That enables comparing Python/world changes while holding cognition outputs constant.

Also keep existing `deterministic_fake` as the default offline path (unchanged synthesis behavior).

## Design Decisions (locked)

### Placement and boundaries

- Own the recording core inside `src/llm/recording/` (new package) so the trust boundary stays with `llm`.
- Public façade re-exports from `llm` / `llm.recording` only. No imports of `simulation`, `agents`, `infrastructure`, `persistence`, `api`.
- `RecordingLLMProvider` is an `LLMProvider` decorator around an inner provider (live adapter, `DeterministicFakeLLMProvider`, or test `FakeLLMProvider`).
- Filesystem store uses stdlib `pathlib` + atomic writes only. Composition roots (`simulation.runner._default_provider`, tests) construct the store and wrap the provider — they do not put credentials into records.
- Logs stay metadata-only (`logging.getLogger("llm.recording")`): mode, store hit/miss, reason codes, digests prefixes, counts, latency — never prompts, messages, schemas, validated dumps, paths that embed secrets, or `exc_info` on validation failures.
- Do **not** add a new `LLMErrorCode`. Replay miss / mismatch / missing component use `LLMErrorCode.CONFIGURATION` plus log reason codes (`replay_miss`, `schema_or_prompt_version_mismatch`, `component_required_for_recording`).

### Modes vs current `RecordingPolicy`

Expand `RecordingPolicy` in `src/simulation/runner_models.py`:

| Value | Meaning |
| --- | --- |
| `live` | unchanged — contact configured adapter |
| `deterministic_fake` | unchanged — default; no recording store |
| `record` | **new** — wrap live/fake inner provider; persist every successful validated exchange |
| `cache` | **new** — scoped cache lookup; miss → inner generate → persist |
| `replay` | **rename/replace stub `recorded`** — never call inner network provider; load from store only |

Migration rules:

- Wire value `recorded` remains accepted on decode as an alias of `replay` for one compatibility window. In `_decode_provider`, map the string `recorded` → `replay` **before** `RecordingPolicy(...)` construction; log once at `WARNING` with reason `recording_policy_recorded_alias`. Encode writes `replay` going forward.
- Remove the `provider_recorded_fallback` path that silently substituted `DeterministicFakeLLMProvider`. `replay` without a configured store fails closed at construction (`recording_store_required`).
- `ExactReproducibilityMode.REQUIRED` allows `deterministic_fake` and `replay` only. Reject `live`, `record`, and `cache`.

### Exchange record schema

- Document id: `llm-exchange-v1` (frozen dataclass + canonical JSON codec in `llm.recording`).
- Exact key-set codec (fail closed on extras/missing): `schema_id`, `provider`, `model`, `structured_output_mode`, `schema_identity` (qualname + digest), `prompt` (nullable ref object), `request_digest`, `effective_options`, `validation` (`status` + `reason_code`), `response` (object or null), `usage` (nullable), `latency_ms`, `correlation` (`run_id`, `agent_id`, `tick`, `llm_request_id`, optional `upstream_request_id`), `component`, `cache_namespace`, optional `recorded_at_monotonic_offset`.
- Response payloads live **only** in the store file — never in structlog/result documents/trajectory hashes.
- Fail closed on unknown exchange schema versions when loading for replay/cache.

### Safe cache keys (collision resistance + privacy)

Cache/replay lookup must not accidentally share private agent cognition across unrelated runs.

**Cache key material (SHA-256 over canonical length-prefixed bytes), all required unless noted:**

1. `cache_namespace` — explicit composition-provided scope (default: `run_id`; matrix cells may set `matrix:<batch_id>:<cell_id>`). Empty/missing namespace is a construction error in `cache` / `replay` / `record`.
2. `provider_name` + `model_name` + `structured_output_mode`
3. Schema identity: `response_model` import qualname + canonical JSON Schema digest (Pydantic schema dump, sorted keys, SHA-256)
4. Prompt identity: `PromptReference.name|version|digest` or a stable `prompt_absent` sentinel
5. Canonical request body digest: ordered roles + normalized message bytes (UTF-8 LF) — content is hashed into the key, not logged
6. Effective options (including preserved `temperature=0`)
7. Isolation tuple: `agent_id` + `component` (required non-blank for cache/replay writes). `tick` and `llm_request_id` are **stored** on the record and used for **by_correlation** lookup, but are **not** sole cache-key material without (1)–(6).

**Hard rules:**

- Never key only on `llm_request_id` or only on message text.
- Never share a store directory across runs without distinct `cache_namespace` values.
- Two different namespaces with identical prompts must not collide (namespace is first key field).
- Schema digest or prompt digest change ⇒ different key ⇒ cache miss; in `replay`, treat as fail-closed `schema_or_prompt_version_mismatch` (do not soft-serve a sibling record).
- Reject serving a record whose stored schema digest ≠ current request schema digest even if the map key matched (defense in depth).

### Fork / matrix namespace isolation

- Default `cache_namespace = run_id`. A research fork child (`derive_branch_run_id`) therefore **does not** see the parent’s recordings unless the composition root deliberately passes a shared namespace.
- Shared namespace across parent/child or matrix cells is **opt-in only** and must be an explicit `RecordingStoreSettings.cache_namespace`. Document this; unit-test that distinct namespaces never hit even with identical prompts/agents/components.
- Do not auto-propagate parent namespaces on fork in this plan.

### Replay lookup strategy

Support two lookup modes on the store (selected at construction via `RecordingStoreSettings.lookup_mode`; default `by_cache_key` for cache, `by_correlation` for replay of a whole run):

1. **`by_cache_key`** — content-addressed within `cache_namespace` (for cache mode and prompt-stable reruns).
2. **`by_correlation`** — exact match on `(cache_namespace, agent_id, tick, component, llm_request_id)` for bit-stable cognition replay when Python changed but call sites keep stable ids.

`replay` miss → `LLMError(CONFIGURATION)` + log reason `replay_miss`. Do not call the inner provider.

Duplicate correlation puts: last-write-wins via atomic `os.replace` on the correlation index file; log `WARNING` reason `correlation_overwrite` (metadata only). Cache-key puts are content-addressed and idempotent when the payload digests match; conflicting payload under the same key fails closed (`cache_key_conflict`).

### Context: component field

- Add optional `component: str | None = None` to `LLMRequestContext` (`src/llm/models.py`), validated as a safe segment when present (same family as prompt segments / header-safe ids).
- Closed production labels (exact strings):

| Call site module | `component` |
| --- | --- |
| `agents.cognition.reconstruction` | `reconstructive_memory` |
| `agents.cognition.reflection` | `reflection` |
| `agents.cognition.consolidation` | `offline_consolidation` |
| `agents.cognition.world_model_selection` | `world_model` |
| `agents.cognition.prospective_selection` | `prospective` |
| `agents.cognition.counterfactual_selection` | `counterfactual` |
| `agents.cognition.theory_of_mind_selection` | `theory_of_mind` |
| `agents.cognition.competence_selection` | `competence` |
| `agents.cognition.teaching_selection` | `teaching` |
| `agents.cognition.production_selection` | `production` |

- `record` / `cache` / `replay` require non-`None` component at generate time (`component_required_for_recording`).

### Provider wrap order

Locked stack (outer → inner):

```text
BudgetGuardedProvider          # per-prepare, agents.cognition.budget
  → RecordingLLMProvider       # run-scoped, llm.recording
    → inner LLMProvider        # live / deterministic_fake / FakeLLMProvider
```

- Budget still charges on replay hits (entering `generate` counts).
- Refusals that raise before calling into `RecordingLLMProvider.generate` create **no** store rows.
- Persist only validated successes; do not cache/record transport failures, `LLMError`, or `BudgetExhaustedError`.
- `RecordingLLMProvider` is constructed once per runner provider; `BudgetGuardedProvider` wraps that shared instance per prepare when budgets are enforced.

### Runner / factory wiring

- `_default_provider` in `src/simulation/runner.py`:
  - `deterministic_fake` → unchanged
  - `live` → existing OpenAI-compatible / disabled path
  - `record` / `cache` → build inner provider (live or fake as configured), wrap with `RecordingLLMProvider(mode=…, store=…)`
  - `replay` → wrap a **non-network** inner stub that is never invoked on hit; construction requires store; generate path must not open httpx
- `RecordingStoreSettings` (frozen): `root_dir`, `cache_namespace`, `lookup_mode`. Parallel to `ProviderCredentials` — composition constructor arg on `SimulationRunner`, not env inside `llm`, not provider JSON.
- LLM-assisted selectors / reconstructors currently gate on `RecordingPolicy.LIVE` only. Widen the “provider may be used” gate to `{LIVE, RECORD, CACHE, REPLAY}`; `DETERMINISTIC_FAKE` keeps today’s deterministic reconstructors/selectors.

### Schema / prompt version changes

- On `record`/`cache` write: persist schema digest + prompt digest.
- On `cache` read: key mismatch ⇒ miss ⇒ live generate.
- On `replay` read: if a correlation hit exists but digest fields differ → fail closed (`schema_or_prompt_version_mismatch`), never return the stale payload.
- Unit tests must pin that editing a prompt resource digest or schema field breaks replay and does not silently succeed.

### Testing strategy

- Unit: canonical cache-key stability, namespace isolation (including fork-style distinct `run_id` namespaces), digest mismatch fail-closed, mode matrix, metadata-only logs, architecture import bounds, `provider_fingerprint` unchanged by store settings.
- Integration (`pytest.mark.integration`, network-free): `FakeLLMProvider` + `RecordingLLMProvider` under `record`, then `replay` with inner call-counter asserted at 0; identical `StructuredOutput`; fail-closed miss / component mismatch / schema-digest mismatch. Prefer a minimal reconstructor or single-selector path over a full WorldEngine. No Docker/PostgreSQL.

## Non-Goals

- API/`compose.yaml` provider lifecycle ownership (still deferred)
- `research_runner` / `palimpsest-matrix` CLI flags for store root (composition/tests pass `RecordingStoreSettings` directly; CLI can come later)
- Auto-sharing parent recording namespaces onto research fork children
- Anthropic-native adapters
- Persisting recordings into PostgreSQL / Alembic
- Putting exchange payloads into cognition-trace HTTP debugger
- Owning `multi_hop_testimony_tracking`
- Changing objective event replay codecs or the `LLM_REPLAY_REQUIREMENT` literal (still `recorded_or_stub`; docs clarify that `deterministic_fake` or `replay` stores satisfy it)
- New `LLMErrorCode` members

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat(llm): add exchange records and safe cache keys`
- **Commit 2** (after tasks 4–6): `feat(llm): implement recording provider modes`
- **Commit 3** (after tasks 7–8b): `feat(simulation): wire record/cache/replay provider policy`
- **Commit 4** (after tasks 9–10): `test(llm): exact replay integration and isolation proofs`
- **Commit 5** (after task 11): `docs(llm): document recording and replay modes`

Each checkpoint is a git commit on `main` created when those tasks are done. Do not squash them into one commit at the end. `git.create_branches` is false, so implementation stays on the current branch.

## Tasks

### Phase 1: Contracts and store

- [x] Task 1: Extend request context and define `llm-exchange-v1` record contracts
  - Deliverable: Add optional `component` to `LLMRequestContext` with safe-segment validation; keep existing callers valid (`None` default). Add frozen dataclasses + exact key-set canonical JSON codec for `LLMExchangeRecord` (`llm-exchange-v1`) per Design Decisions. Re-export from `llm` / `llm.recording` façades without leaking private helpers. Unit tests cover construction, reject extras/missing keys, and safe `__repr__`.
  - Logging: codec/models remain log-free; `__repr__` must not dump response payloads or message text (counts/digests only).
  - Files: `src/llm/models.py`, `src/llm/recording/__init__.py`, `src/llm/recording/models.py`, `src/llm/recording/codec.py`, `src/llm/__init__.py`, `tests/unit/test_llm_recording_models.py`
  - Dependencies: none.

- [x] Task 2: Implement safe cache-key derivation and schema/prompt digests
  - Deliverable: Canonical SHA-256 key material per Design Decisions (namespace first; include schema + prompt digests + effective options + agent/component isolation). Helpers to digest Pydantic JSON Schema and normalize request messages deterministically. Property/unit tests: key stability; different namespaces never collide; schema or prompt digest change changes key; keys never log raw content.
  - Logging: DEBUG may log key hex prefix + reason codes only.
  - Files: `src/llm/recording/cache_key.py`, `tests/unit/test_llm_recording_cache_key.py`
  - Dependencies: Task 1.

- [x] Task 3: Filesystem `RecordingStore` with atomic write and dual lookup
  - Deliverable: Protocol + filesystem implementation: put/get by cache key; put/get by correlation tuple; list/count for diagnostics. Atomic create (`*.tmp` + `os.replace`); reject path traversal; fail closed on corrupt/unknown schema; correlation overwrite WARN; cache-key payload conflict fails closed.
  - Logging: INFO for store open (root basename + namespace hash prefix only); WARNING/ERROR with stable reason codes — never full home paths, never payloads.
  - Files: `src/llm/recording/store.py`, `tests/unit/test_llm_recording_store.py`
  - Dependencies: Tasks 1–2.

### Phase 2: Recording provider

- [ ] Task 4: Implement `RecordingLLMProvider` mode machine
  - Deliverable: Modes `live` (passthrough), `record`, `cache`, `replay`. Inject monotonic clock for latency; no `time.time` domain decisions. Honor wrap-order contract (Recording is the inner provider that Budget wraps). `replay` never calls inner; miss/mismatch → `LLMError(CONFIGURATION)`. Persist only validated successes. Re-validate stored JSON through the request’s `response_model` before returning.
  - Logging: DEBUG start/lookup; INFO hit/miss/persist with mode + digests prefixes + latency; ERROR terminal reason codes. Metadata allowlist only.
  - Files: `src/llm/recording/provider.py`, `src/llm/recording/__init__.py`, `tests/unit/test_llm_recording_provider.py`
  - Dependencies: Task 3.

- [ ] Task 5: Factory helpers without infrastructure imports
  - Deliverable: Add `wrap_recording_provider(...)` / store factory in `src/llm/recording/factory.py` that accepts explicit root path + namespace + lookup mode + mode + inner provider + clocks. Keep `create_llm_provider` unchanged for non-recording construction.
  - Logging: DEBUG construction mode + namespace prefix.
  - Files: `src/llm/recording/factory.py`, `src/llm/factory.py` (re-export if needed), `tests/unit/test_llm_factory.py`, `tests/unit/test_llm_recording_factory.py`
  - Dependencies: Task 4.

- [ ] Task 6: Architecture gates for `llm.recording`
  - Deliverable: Ensure import-linter + AST checker keep `llm.recording` inside `llm` only; forbid recording modules from importing simulation/agents/infrastructure. Extend isolation tests.
  - Logging: n/a (tests).
  - Files: `pyproject.toml` (if contracts need an entry), `tests/architecture/boundary_checker.py`, `tests/architecture/test_llm_provider_isolation.py`
  - Dependencies: Task 4.

### Phase 3: Simulation wiring

- [ ] Task 7: Expand `RecordingPolicy` and exact-reproducibility rules
  - Deliverable: Add `RECORD`, `CACHE`, `REPLAY`. In `_decode_provider`, alias `recorded` → `replay` before enum construction; encode `replay`. Update `ExactReproducibilityMode.REQUIRED` guards to allow only `deterministic_fake` and `replay`. Keep `provider-settings-v1` exact key-set unchanged. Update diagnostics / serialization tests.
  - Logging: one WARNING on alias decode; construction errors stay exception codes without payload.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/__init__.py`, `tests/unit/test_runner_models.py`, `tests/unit/test_v2_golden_runner_configs.py` (only if provider blobs appear there)
  - Dependencies: Task 5.

- [ ] Task 8: Wire `_default_provider` and LLM-assisted cognition gates
  - Deliverable: Replace `recorded_fallback` fake with real recording wrap; require store for `record`/`cache`/`replay`. Widen LIVE-only gates for memory/reflection/consolidation (and any peer LIVE-only provider binds) to `{LIVE, RECORD, CACHE, REPLAY}`. Leave component labeling and store-settings type to Tasks 8a/8b.
  - Logging: keep `provider_*` events; add mode + `store_configured` boolean (not path).
  - Files: `src/simulation/runner.py`, `tests/unit/test_simulation_runner_construction.py`
  - Dependencies: Task 7.

- [ ] Task 8a: Composition-only `RecordingStoreSettings`
  - Deliverable: Add frozen `RecordingStoreSettings` (`root_dir`, `cache_namespace`, `lookup_mode`) parallel to `ProviderCredentials`. Thread through `SimulationRunner` construction. Prove store settings never appear in `_encode_provider`, `provider_fingerprint`, or result documents. Construction fails closed when policy is `record`/`cache`/`replay` and settings are missing.
  - Logging: DEBUG `recording_store_configured namespace_prefix=%s lookup_mode=%s` (no absolute paths at INFO).
  - Files: `src/simulation/runner_models.py` (or adjacent), `src/simulation/runner.py`, `src/simulation/__init__.py`, `tests/unit/test_simulation_runner_construction.py`, `tests/unit/test_runner_models.py`
  - Dependencies: Task 7.

- [ ] Task 8b: Label every production `LLMRequestContext` with closed component strings
  - Deliverable: Pass the closed labels from the Design Decisions table at all ten call sites. Unit-assert each site supplies non-blank `component` (parametrized or snapshot of construction helpers).
  - Logging: existing cognition LLM start/complete events may include `component=` when already metadata-safe; never log prompts/outputs.
  - Files: `src/agents/cognition/reconstruction.py`, `reflection.py`, `consolidation.py`, `world_model_selection.py`, `prospective_selection.py`, `counterfactual_selection.py`, `theory_of_mind_selection.py`, `competence_selection.py`, `teaching_selection.py`, `production_selection.py`, `tests/unit/test_llm_request_components.py`
  - Dependencies: Task 1.

### Phase 4: Tests and docs

- [ ] Task 9: Unit proofs for isolation, drift, and fingerprint hygiene
  - Deliverable: Cross-namespace non-leak tests (identical prompts/agents, different namespaces ⇒ no hit), including distinct `run_id`-style namespaces (fork-child case). Schema field change and prompt digest change ⇒ replay fail-closed; cache miss. Metadata-only log assertions. Assert `RecordingStoreSettings` does not alter `provider_fingerprint` for otherwise-equal provider JSON.
  - Logging: assert allowlist; fail if message/content/schema dump appears.
  - Files: `tests/unit/test_llm_recording_isolation.py`, `tests/unit/test_llm_recording_drift.py`
  - Dependencies: Tasks 4, 8a.

- [ ] Task 10: Integration tests for exact replay
  - Deliverable: Network-free `@pytest.mark.integration` module using `FakeLLMProvider` + `RecordingLLMProvider(record)` then `replay`: inner call-counter stays 0; identical `StructuredOutput` on a minimal reconstructor or single-selector path; fail-closed on miss, component mismatch, and schema-digest mismatch. No Docker/PostgreSQL/WorldEngine required.
  - Logging: metadata-only; no payload assertions via log text.
  - Files: `tests/integration/test_llm_recording_replay.py`, fixtures under `tests/fakes/` if needed
  - Dependencies: Tasks 8, 8a, 8b.

- [ ] Task 11: Documentation checkpoint (`/aif-docs`)
  - Deliverable: Update `docs/llm-providers.md` (modes table, cache-key rules, wrap order, schema/prompt drift, privacy, fork/matrix namespace opt-in). Update `docs/simulation-runner.md` LLM reproducibility section and short pointers in `docs/configuration.md` / `docs/architecture.md` (`LLM_REPLAY_REQUIREMENT` satisfied by `deterministic_fake` or `replay` stores). Keep README lean.
  - Logging: document metadata-only policy for `llm.recording`.
  - Files: `docs/llm-providers.md`, `docs/simulation-runner.md`, `docs/configuration.md`, `docs/architecture.md` (short cross-links only)
  - Dependencies: Tasks 9–10.

## Implementation notes for `/aif-implement`

- Prefer extending existing fakes (`tests/fakes/llm.py`) over new network tests.
- Do not bump Alembic or add SQL tables.
- Do not change `v1_regression_profile` or catalog A–E trajectories.
- Keep `provider-settings-v1` exact key-set; store settings are composition-only.
- After Task 11, run `/aif-docs` per Docs: yes.
