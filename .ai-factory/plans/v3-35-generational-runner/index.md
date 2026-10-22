<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-35 Generational Simulation Runner

Mode: ultra
Canonical stem: `v3-35-generational-runner`
Branch: `main` (no branch creation)
Created: 2026-10-22
Planning baseline: `b79c4eb8d8e796982033a5c9dd6b749bc5b4f86e`
Status: implementation-ready; no implementation performed
Refined: 2026-10-22 — eight code-grounded improvements approved; 18 stable task IDs retained

## Original Request

v3-35 generational simulation runner

Plan naming requirement:

Generate the plan under a canonical name beginning `v3-`.

Suggested stem:

v3-35-generational-runner

Extend SimulationRunner for multi-generation historical experiments.

Support:

very long run horizons  
population births/creation  
deaths  
cohorts  
generation tracking  
migration  
multiple communities  
historical checkpoints

Add stopping conditions such as:

tick horizon  
generation horizon  
population extinction  
population threshold  
experiment-specific criteria

Preserve deterministic seed management across:

world randomness  
demography  
agent initialization  
LLM replay  
innovation  
environment

Run metadata must record enough information for reproducibility.

## Settings

- Testing: yes, confirmed by user; preserve coverage.
- Logging: verbose metadata-only DEBUG plus bounded INFO lifecycle/stop events; no payload logs.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 18.
- Git: enabled; base `main`; `create_branches=false`; do not create/switch branches or worktrees. Skip push prompt after a later commit.
- Workflow: slug plan ID; verification mode normal; artifact/UI language English; keep English technical terms.
- Execution: planning only; run no application implementation or migrations in this invocation.
- Checkpoint scope confirmed by user: **Inspection/replay**, not full durable subjective process restart.
- Research: no research artifact or marked research bundle exists; no Research Context copy is applicable.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"
Rationale: Extend existing generational population, migration, and historical evidence seams into reproducible multi-generation experiments without acquiring new world or institutional authority.

This plan deepens the owned `generational_population` seam. It does not own `institutional_economy`, `multi_hop_testimony_tracking`, or deferred kinship knowledge handoff, and does not close M7. Roadmap edits belong to its owner workflow, not this planning invocation.

## Requirements Reconciliation

Authority: applicable `AGENTS.md` and project rule hierarchy constrain all work; the original request and explicit checkpoint clarification define feature scope. `.ai-factory/ARCHITECTURE.md` constrains authority/versioning. Existing code and targeted tests establish compatibility behavior; roadmap entries are scope indicators, not detailed behavioral specifications. No unresolved material requirement conflict remains.

| Decision / supported behavior | Source path and section | Verification evidence |
| --- | --- | --- |
| Engine alone admits population and commits objective effects | `.ai-factory/RULES.md` — Axioms; `.ai-factory/ARCHITECTURE.md` — Objective authority; `src/simulation/engine.py` — `_apply_lifecycle_channel` | Task 5 atomic admission/failure/replay tests. |
| Creation is a demographic experiment schedule, not biology | Original Request — births/creation; `src/simulation/runner_models.py` — `PopulationLifecycleSpec` docstring; `src/world/lifecycle.py` — generation/cohort records | Task 4 schedule/label tests; Task 16 real experiment. |
| Entrants start with explicit empty-content species profiles | `.ai-factory/ARCHITECTURE.md` — population entry; `src/simulation/new_agent_initialization.py` — `species_defaults_for`; runner synchronization | Task 5 blank-slate and initialization-forwarding regressions. |
| Independent stop selectors evaluate post-finalization and post-admission | Original Request — stopping conditions; `src/simulation/runner.py` — `run_tick`, `_evaluate_stop`, `_record_finalized_tick` | Tasks 6–8 simultaneous/cadence/failure/order tests. |
| New optional root requires a new exact runner schema | `.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract; `src/simulation/runner_serialization.py` | Task 2 v55/v54 and older root rejection/roundtrip tests. |
| v55 activation is independent of institutional modes and survives matrix expansion | `src/simulation/runner_serialization.py` — `_v54_family_root_keys`; `src/simulation/runner_models.py` — v54 decay trigger; `src/experiments/matrix_schema.py` — independent highest-wins selection | Task 2 population-only/dynamics/region family tests and embedded matrix factor-to-run roundtrip. |
| Historical checkpoints provide inspection/replay only | User clarification — Inspection/replay; `docs/simulation-runner.md` — checkpoint limitations; `src/simulation/replay.py` | Task 12 actual PostgreSQL historical seek and observation parity. |
| Communities remain analytical, migration remains normal journeys | `.ai-factory/ARCHITECTURE.md` — Important V3 seams; `src/experiments/composition.py`; `src/analysis/society_emergence.py` | Task 15 complete/partial evidence, transit conservation and no feedback tests. |
| Preserve actual versioned seed scopes rather than silently unify them | Original Request — six-channel seed management; `src/simulation/randomness.py`, `new_agent_initialization.py`, `lifespan_distribution.py`; `src/agents/cognition/practical_knowledge.py` | Task 10 same-complete-identity and channel isolation/recording tests. |
| Reproducibility requires source/config/provider/recording identity | Original Request — metadata; `src/experiments/matrix_models.py` — `RunVersionIdentity`; `src/llm/recording/store.py`; `docs/llm-providers.md` — exact reproduction | Tasks 10–11 and 17 source/recording/completion preflight tests. |
| Replay usage is provider-validated metadata, not a successful store read | `src/llm/recording/provider.py` — `_lookup` and `_result_from_record`; `tests/architecture/boundary_checker.py` — allowed imports | Task 10 post-validation callback, concurrent canonical usage digest, and no experiments-to-llm import. |
| Durable origin reruns cannot reuse an existing RunId in place | `src/persistence/sqlalchemy.py` — `create_run` conflict; `src/experiments/matrix_runner.py` — retry and state-only skip paths | Tasks 11, 16–17 complete-archive reconciliation, identity drift rejection and incomplete durable-run refusal. |
| Long horizons must not destroy authoritative history | Original Request — very long horizons; architecture append-only evidence rules; `src/simulation/engine.py` cumulative tuple histories | Tasks 13–14 bit-identical exports/hashes; Task 18 100000-tick gate. |
| Historical counts are not current compatibility pins | `.ai-factory/ROADMAP.md` — historical 103 metric count; `.ai-factory/DESCRIPTION.md` later V3-34 section and `.ai-factory/ARCHITECTURE.md` baseline — 129 | Keep metric catalog unchanged; use executable compatibility tests, not old roadmap counts. |

### Supported Combinations

These rows cover the independent selectors; they are not permission to bypass existing per-channel gates. All v55 rows require lifecycle, owned population flag, explicit initialization, finite `max_ticks`, and `stop_on_all_agents_terminal=false`.

| ID | Accepted input / validation | Persisted state | Output / transition | Side effects / invariants | Verification scenario |
| --- | --- | --- | --- | --- | --- |
| C1 | Legacy v1–v54; generational sibling absent; old policies | Unchanged old config/result keysets and objective events | Existing stop/result semantics, except scoped terminal-policy and initialization correctness fixes | No new draws/modes/artifact requirement; immutable history optimization must be transparent | v54 roundtrip and V1/V2 gates, Tasks 2, 5, 6, 13. |
| C2 | v55 with generational interval, disabled, or fixed policy; explicit init; institutional modes may all be disabled | Selected lower-family root plus generational sibling; lifecycle labels and existing events; result v3 | Newcomers act next observation; fixed-policy labels stay fixed; matrix factors retain v55 | No copied owner state/parents; no cap retry; optional old siblings retain omission semantics | Population-only/dynamics/regional roundtrips, matrix expansion, new/old policy tests, Tasks 2, 4–5, 16. |
| C3 | Generation horizon set or null; finite tick horizon always set | Realized max generation, completed tick, matched stop evidence | Stop when actual admitted max >= target, or tick budget reached | Scheduled-but-denied cohorts do not count; tick/gen simultaneity has stable precedence | Target admission, denied target, and simultaneous horizon tests, Task 6. |
| C4 | Extinction true or false; no runtime-terminal stop for v55 | Objective living/dead counts and receipts | True: stop at living=0 after admission; false: empty ticks may reach a future cohort | Death+entry same tick is not extinction; in-transit living agents count once | Gap continuation and terminal-tick admission regressions, Tasks 5–6. |
| C5 | Optional threshold with inclusive at_most/at_least comparator | Comparator/value in config and actual measured population in stop evidence | Stop after a completed boundary meeting the threshold | Threshold is separate from admission cap; no speculative precommit stop | Equality, above/below, zero and simultaneous extinction tests, Task 6. |
| C6 | Known versioned criteria; positive cadence; injected factories | IDs/versions/params, cached decisions and terminal latch/control carry | Evaluate post-finalization at cadence unless built-in wins; repeat terminal calls do not tick | No live-state access; failures/cancellation preserve actual boundary; API failures become FAILED | Registry/cadence, terminal repeat, recovered boundary, cancellation and API transition tests, Tasks 3, 6–9, 15. |
| C7 | Existing regions/migration/contact enabled or absent under v54-compatible gates | Existing journey/contact events, lifecycle and optional detached samples | Normal movement between locations/regions; analytical candidate communities only | Spawn placement is not migration; cohorts/regions are not social groups | Actual AY topology encode/run/export/replay and AZ sample tests, Tasks 12, 15–16. |
| C8 | Historical cadence absent or positive; positive requires matching durable checkpoint cadence and reader/sink | Absent: final archival metadata only; enabled: authoritative snapshots plus immutable history references | Inspect exact completed boundaries; non-cadence samples fold from nearest snapshot | No subjective restart; no pruning; missing dependency fails before run creation | Checkpoint on/off parity, eventless commits, partial finalization and sink failure, Tasks 8, 11–12. |
| C9 | Exact fake/replay and complete source/config/recording/execution-recipe identity | Seed scopes, registered intervention, exact manifests, sorted validated usage rows and hashes | Full-identity reproduction; verified archive may repair matrix completion without rerun | No live fallback; no same-database incomplete durable rerun; no secret/payload metadata or asynchronous-order hashes | Real replay validation, recipe drift, both skip gates, archive adoption, durable conflict and twins, Tasks 10–11, 16–17. |
| C10 | Very large finite tick budget; complete retained evidence | Chunk histories, indexed receipt IDs and unchanged public receipts/hashes | No artificial four-digit limit, event-prefix copies, or per-tick receipt-prefix scan | Total memory/storage remain history-sized; no evidence truncation | Sequence/membership operation counts, byte parity and 100000-tick gate, Tasks 8, 13–14, 18. |

## Architecture and Decisions

### Version and ownership budget

- New config: `runner-config-v55`, selected exact lower root family plus required population/initialization/flags and `generational_run`; cognition keys remain v54. There is no universal v54 root. v55 requires the new sibling, not institutional decay; every institutional mode may be disabled. Matrix highest-wins dispatch explicitly selects v55. Default writer stays v4.
- New result: `runner-result-v3` only for generational runs; v1/v2 accepted and legacy default stays v2.
- New archival schemas: `generational-run-manifest-v1`, `generational-history-v1`, `generational-completion-v1`, `generational-failure-v1`, `generational-recording-usage-v1`; exact field sets/nested identity contracts are in Task 11.
- No new commands/events, observer semantic types, capability flags/ownership, objective replay/codec/derivation versions, SQL migrations, metric families, HTTP versions, or protocol identities. Existing active channels still select their existing write pairs; latest available pair remains replay-v22/codec-v20.
- Pins unchanged: 43 commands, 73 observer semantic types, 129 metric families, Alembic 0017. Preserve sequential preparation.

### Generation and admission semantics

Founders are generation 0. New `generational_interval_entry` labels a successful admission at engine tick t with `1 + (t - 1) // generation_length_ticks`. An interval can produce several cohorts per generation. Cohorts distinguish admission tick and spawn stratum. This is a declared experimental calendar, not pedigree depth, reproduction, or society progression.

The engine processes deaths before demographic capacity. A denied scheduled slot disappears; future identities/labels depend on absolute tick, not successful admission count. The policy never assigns parents. Existing initial genealogy may coexist, but knowledge/affection/rights do not transfer. Existing explicit blank-slate species profiles are used without inventing a new inheritance/profile mechanism.

### Boundary and stop order

For tick t and completed boundary B=t+1:

```text
observe and prepare sequential owner commands
  -> engine candidate: normal effects -> lifecycle/deaths -> demographic proposals
  -> atomic objective commit (existing cadence snapshot when due)
  -> bind new owner runtimes (first action at B)
  -> finalize/ack all owner updates
  -> record receipts and normal boundary goal effects; advance cursor to B
  -> detached population progress
  -> built-in stopping; custom criteria only if no built-in stop and cadence due
  -> post-finalization historical observer
  -> attempt receipt
  -> terminal finish_run once, including run-ending goal evaluation
```

Recovery/authority/cognition failures retain their existing non-success semantics. Post-finalized custom/sink failures do not roll back or retry the committed tick. A criterion failure remains primary if the observer also fails. For successful simultaneous built-ins, precedence is injected stop, max ticks, generation horizon, extinction, threshold, then criterion. Preserve all matched built-in reasons. Custom criteria skipped due to a built-in match are explicitly marked unevaluated. Population predicates first run after a completed tick, not bootstrap.

Latch terminal evidence/receipt before returning; repeated run_tick calls return the same receipt without additional attempts or effects until finish_run, after which ticks are rejected. Both drivers use one runner-owned attempt ledger. Supported in-process recovery reuses exact committed TickResult evidence and the same boundary pipeline; no fabricated empty result is acceptable for generational hashes. Unavailable exact evidence remains recovery-required. Python-only checkpoint carry includes control/latch state, not a durable subjective codec. API distinguishes scientific completion from FAILED orchestration. At B=0, failure evidence has no last executed tick or last objective commit.

Boundary observers provide one logical immutable record via idempotent keys, not guaranteed exactly-once callback invocation. Interrupted publication may be retried; criteria are deterministic/read-only and completed decisions are cached. Cancellation preserves the actual committed/finalized stage; it never rewinds the engine or silently reopens a terminal run. Post-finalization callback errors are caught outside the authority-abort path and do not log payload-bearing exceptions.

Generation horizon means highest **ever admitted** label reached, not age reached or generation completed. Extinction is zero objective living bodies after same-tick admission. All v55 runs disable runtime-terminal stopping so explicit extinction policy controls empty-population gaps.

### Reproducibility contract

Preserve current deterministic algorithms. Record root seed, derivation/scopes, physical rules, lifespan/distribution/profile/policy identities, config/scenario/cognition fingerprints, source/package/Python/dependency environment, assignment, criteria, execution recipe and diagnostic intervention, and validated replay usage. Require revision plus clean-source assertion or source digest for exact archives. Seed metadata distinguishes absent channels from the existing reserved-but-ignored demographic draw; no silent draw removal is planned.

World/environment derivation-v3 uses stochastic identity. Demography/init/lifespan currently retain run ID; innovation uses configured deterministic hash material. Therefore exact generational reproduction holds for the same **complete identity**, not arbitrary new run IDs with the same seed. External LLM output requires a deterministic fake or immutable validated recordings; record namespace/lookup/request-correlation and content integrity without leaking payloads or credentials.

Recording success is observed within llm only after prompt/schema compatibility and structured-output validation. Simulation maps the payload-free callback to a neutral sink; experiments/research_runner never import llm or inspect exchange records. Usage files use canonical request-identity keys and completion hashes sorted rows, independent of asynchronous return order. Standard provider composition supports exact archives; untracked custom provider factories are rejected there, while legacy library injection remains intact.

### Historical inspection, not restart

Enable historical output with an explicit cadence matching durable runner checkpoints. At B store snapshot/journal/revision references and finalized demographic/evidence identity. Cadence produces a real objective checkpoint; generation-change/terminal samples may instead reference the nearest snapshot and a journal fold target. Always distinguish these. With no historical cadence, produce final provenance/results but no historical availability claim.

No complete modern owner-ledger codec, memory/belief/relationship restoration, runtime roster reconstruction, or durable idempotency restart bundle is introduced. Python runtime carry does not establish durable subjective restart. Matrix resume may adopt a fully verified completed archive without re-execution or rerun a non-durable cell from origin in a new attempt directory. An incomplete durable RunId in the same persistence destination is non-retryable `durable_origin_rerun_unsupported`, including bootstrap-only existence. Fresh-destination reproduction is an explicit user action; never delete/relabel the original run to simulate resume. Both existing matrix skip paths validate new archival identities/hashes before acceptance.

### Long-horizon limits

Use immutable structural-sharing event/resolution histories, indexed finalized-receipt membership, and streaming byte-equivalent trajectory hashing. Rebuild the receipt index once on supported checkpoint carry, never per tick. Retain complete historical state/audits/receipts and final exports. Do not claim constant memory, bounded disk, or linear runtime for optional full-history channels. Validate 100000 sparse-demography ticks with operation-count proofs; positive admissions at multiples of 1000 through executed tick 99999 yield 99 due cohorts, not an extra tick-100000 entry.

### Multiple communities

Existing regions/journeys remain objective physics. Candidate communities and cultural/social comparisons remain detached analysis. Use exact completed-boundary evidence and complete journey inputs; mark unavailable dimensions as partial, never absent facts or zero. Community IDs are sample-local. A trusted analytical termination callback can stop the outer experiment but cannot install communities or affect agent cognition.

The new sampler explicitly reconstructs prefix state at W=max(0,B-window_ticks), then folds [W,B) to derive actual clipped residence/transit intervals. Legacy cumulative first_tick=0 adapters do not provide this behavior. Join agent-keyed lifecycle records through detached registration mapping to body-keyed society persons. Filter community rows/edges to the living-at-B roster, including an explicit empty case to prevent fallback inference of dead nodes. Source-evidence completeness is independent of clustered-person coverage: a fully observed singleton is not missing evidence. Unassisted BL cognition is not guaranteed isolation; the separate AZ fixture supplies isolated-community evidence.

## Approved Refinement Record

All eight findings were approved before editing; task IDs/settings/original request and checkpoint scope remain unchanged.

1. Task 2 now pins feature-family root selection and v55-only activation independently of institutional decay.
2. Tasks 2 and 16 exercise the real matrix version-finalization path rather than bypassing expansion.
3. Task 10 moves replay-success observation inside the provider and uses neutral, canonically ordered metadata across package boundaries.
4. Tasks 11, 16–17 reconcile completed archives and refuse unsupported same-destination durable origin reruns.
5. Tasks 3 and 6–9 define terminal latching, exact in-process recovery evidence, cancellation/publication idempotency, shared attempt collection, and API failure classification.
6. Tasks 8, 13 and 18 remove and verify the remaining quadratic finalized-receipt scan.
7. Task 15 specifies trailing-window prefix state, roster/identity projection, transit, and truthful evidence completeness.
8. Tasks 11 and 16–17 pin artifact schemas, registered execution/intervention recipes, standalone assignment construction, and unassisted-versus-isolated semantics.

## Phase Index

1. [Phase 1: Versioned execution contracts](phase-01-contracts.md) — Tasks 1–3
2. [Phase 2: Demography and finalized stops](phase-02-demography-and-stops.md) — Tasks 4–6
3. [Phase 3: Boundary orchestration and consumers](phase-03-boundary-orchestration.md) — Tasks 7–9
4. [Phase 4: Reproducibility and historical checkpoints](phase-04-reproducibility-and-history.md) — Tasks 10–12
5. [Phase 5: Long-horizon costs and communities](phase-05-long-horizon-and-communities.md) — Tasks 13–15
6. [Phase 6: Experiment, CLI, and release gates](phase-06-experiment-and-release.md) — Tasks 16–18

## Cross-Phase Dependencies

- Task 2 depends on 1; Task 3 depends on 1–2 for coherent config/result validation.
- Task 4 depends on 1–2; Task 5 depends on 4; Task 6 depends on 3–5.
- Task 7 depends on 1–3 and 6; Task 8 depends on 6–7; Task 9 depends on 3 and 8.
- Task 10 depends on 1–2 and 7–8; Task 11 depends on 3, 8, 10; Task 12 depends on 5, 8, 11.
- Task 13 depends on 5 and 12 to protect admission/restore parity. Task 14 depends on 3 and 13. Task 15 depends on 7, 11–12.
- Task 16 depends on 4–15; Task 17 depends on 9–12 and 16; Task 18 depends on all prior tasks.
- Execute phases in order. Shared edits to `runner.py` and schema modules are sequential, not parallel agent work by default.

## Tasks

### Phase 1: Contracts

- [x] Task 1: Add immutable run and boundary models ([details](phase-01-contracts.md#task-1-add-immutable-run-and-boundary-models)).
- [x] Task 2: Add exact v55 config encoding and compatibility gates ([details](phase-01-contracts.md#task-2-add-exact-v55-config-encoding-and-compatibility-gates)) (depends on 1).
- [x] Task 3: Version generational results and stop evidence ([details](phase-01-contracts.md#task-3-version-generational-results-and-stop-evidence)) (depends on 1, 2).

### Phase 2: Population and stopping

- [x] Task 4: Implement deterministic multi-location generational entry ([details](phase-02-demography-and-stops.md#task-4-implement-deterministic-multi-location-generational-entry)) (depends on 1, 2).
- [x] Task 5: Bind correctly initialized entrants through atomic tick admission ([details](phase-02-demography-and-stops.md#task-5-bind-correctly-initialized-entrants-through-atomic-tick-admission)) (depends on 4).
- [x] Task 6: Unify empty-population progression and built-in stopping ([details](phase-02-demography-and-stops.md#task-6-unify-empty-population-progression-and-built-in-stopping)) (depends on 3, 4, 5).

### Phase 3: Orchestration

- [x] Task 7: Add trusted, versioned experiment criterion injection ([details](phase-03-boundary-orchestration.md#task-7-add-trusted-versioned-experiment-criterion-injection)) (depends on 1, 2, 3, 6).
- [x] Task 8: Centralize finalized-boundary publication and idempotent finishing ([details](phase-03-boundary-orchestration.md#task-8-centralize-finalized-boundary-publication-and-idempotent-finishing)) (depends on 6, 7).
- [x] Task 9: Update API and matrix stop/result consumers ([details](phase-03-boundary-orchestration.md#task-9-update-api-and-matrix-stopresult-consumers)) (depends on 3, 8).

### Phase 4: Reproducibility and history

- [x] Task 10: Record actual seed lineage and external LLM replay identity ([details](phase-04-reproducibility-and-history.md#task-10-record-actual-seed-lineage-and-external-llm-replay-identity)) (depends on 1, 2, 7, 8).
- [x] Task 11: Persist immutable experiment manifests and historical boundary index ([details](phase-04-reproducibility-and-history.md#task-11-persist-immutable-experiment-manifests-and-historical-boundary-index)) (depends on 3, 8, 10).
- [x] Task 12: Compose durable snapshot references and verify historical replay ([details](phase-04-reproducibility-and-history.md#task-12-compose-durable-snapshot-references-and-verify-historical-replay)) (depends on 5, 8, 11).

### Phase 5: Long horizons and communities

- [x] Task 13: Replace cumulative history tuple copying with immutable chunks ([details](phase-05-long-horizon-and-communities.md#task-13-replace-cumulative-history-tuple-copying-with-immutable-chunks)) (depends on 5, 12).
- [ ] Task 14: Stream canonical hashes without dropping retained evidence ([details](phase-05-long-horizon-and-communities.md#task-14-stream-canonical-hashes-without-dropping-retained-evidence)) (depends on 3, 13).
- [ ] Task 15: Sample cohorts, migration, and candidate communities outside simulation ([details](phase-05-long-horizon-and-communities.md#task-15-sample-cohorts-migration-and-candidate-communities-outside-simulation)) (depends on 7, 11, 12).

### Phase 6: Experiment and release

- [ ] Task 16: Add a real multi-generation experiment and per-assignment execution context ([details](phase-06-experiment-and-release.md#task-16-add-a-real-multi-generation-experiment-and-per-assignment-execution-context)) (depends on 4–15).
- [ ] Task 17: Expose generational CLI composition and reproducibility preflight ([details](phase-06-experiment-and-release.md#task-17-expose-generational-cli-composition-and-reproducibility-preflight)) (depends on 9, 10, 11, 12, 16).
- [ ] Task 18: Prove long-horizon gates and document exact guarantees ([details](phase-06-experiment-and-release.md#task-18-prove-long-horizon-gates-and-document-exact-guarantees)) (depends on 1–17).

## Commit Plan

These are implementation checkpoints, not authorization to commit during planning.

- Commit 1, after Tasks 1–3: `feat(simulation): define versioned generational run contracts`
- Commit 2, after Tasks 4–6: `feat(simulation): advance demographic generations and population stops`
- Commit 3, after Tasks 7–9: `feat(simulation): unify finalized experiment orchestration`
- Commit 4, after Tasks 10–12: `feat(experiments): archive reproducible generational history`
- Commit 5, after Tasks 13–15: `perf(simulation): reduce long-horizon history and hash copying`
- Commit 6, after Tasks 16–18: `feat(research): expose verified generational experiments`

## Risks, Gaps, and Explicit Deferrals

- **Scoped pre-existing defects:** reproduce then correct empty-terminal stopping and newer-schema initialization forwarding. Decoding old persisted events remains supported; re-execution of affected configs intentionally no longer reproduces those bugs.
- **Deferred parent-link defects:** public admission can mutate auxiliary state before invalid-parent rejection, and current internal demographic admission does not establish candidate parent links. This policy emits no parents and uses atomic tick admission; do not expand this feature into genealogy-aware reproduction.
- **No full durable subjective restart:** modern ledger codecs, owner-store/dynamic roster restart and durable idempotency remain separate. New Python-only control carry and same-process publication recovery do not remove this limitation.
- **No silent seed unification:** demographic/init/lifespan run-ID scoping is recorded and tested; changing it needs a later versioned identity contract.
- **Resource limits:** complete world/evidence/runtime history remains in memory/disk; expensive optional full-history consumers remain explicit limitations. No pruning or bounded-total-memory claim.
- **Partial community evidence:** no criterion match from incomplete source coverage; do not confuse source completeness with clustering coverage or claim cumulative/lightweight adapters implement windowed isolation audits.
- **Durable retry limitation:** attempt directories do not avoid persistent RunId conflicts. Reconcile valid completed metadata without reexecution; otherwise refuse incomplete durable origin reruns in place.
- **No provider lifecycle expansion in API:** unsupported callbacks/recording/history composition fail closed. New executable archival composition is owned by the research CLI.
- **Missing research artifact:** normal, not a blocker. Historical roadmap counts are not rewritten here.
- **No blocking open question:** checkpoint semantics were clarified; the remaining choices above are committed implementation decisions.

## Definition of Done

- All 18 index tasks verified, with phase-specific tests and matching implementation behavior.
- v55/result-v3 roundtrip and legacy exact-keyset acceptance remain correct; default writers and unchanged pins stay intact.
- Multiple actual generations/cohorts are admitted blank-slate; deaths, migration, transit and empty-population gaps are represented accurately.
- Tick/generation/extinction/threshold/custom stopping works identically through both drivers; terminal decisions latch, supported recovery uses exact evidence, and cancellation/post-commit failure cannot duplicate ticks or finishing. API failures are FAILED, not COMPLETED.
- Complete provenance identifies source/config/environment/seed scopes/validated recordings/execution recipes. Exact artifact schemas, canonical concurrent usage order and both matrix skip gates are verified; required-artifact failure cannot yield success.
- Historical checkpoint references reconstruct the advertised objective boundary, including dynamic population/migration and observation parity; no subjective restart is advertised.
- Real AY-derived BL experiment and detached AZ/community evidence paths verify supported combinations, not only synthetic fixtures.
- Long-horizon history/receipt-index/hash changes preserve exact exports/hashes and avoid prefix work in per-tick idempotency. The opt-in 100000-tick durable gate passes or is explicitly reported unverified when its environment is unavailable.
- V1 regression, V2 scientific invariants, architecture/import rules, Ruff and mypy pass with coverage retained. Mandatory `$aif-docs` checkpoint completes.
- No unowned capability is enabled; no unrelated historical plans, requirements, roadmap, architecture or application files were modified by planning.

## Execution Handoff

Read this index, then the complete linked phase before implementing its tasks. Checkboxes exist only here. Preserve all phase files; do not flatten this bundle into a single plan. Use an explicit plan path because branch creation is disabled and other plans coexist:

`$aif-implement @.ai-factory/plans/v3-35-generational-runner/index.md`
