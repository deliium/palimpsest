<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-44 End-to-End Generational Civilization Benchmark

Mode: ultra
Branch: main (remain on current branch; `git.create_branches: false`)
Created: 2026-10-27
Improved: 2026-10-27 (`$aif-improve`; six approved refinements; task IDs/statuses preserved)
Plan identifier: `v3-44-generational-benchmark`
Status: implementation complete (2026-10-30); Tasks 1–23 complete. Task 23 final verification passed on executable-source digest `fef95f48f5a3d461fea6325953b64b265c936a514d0f012986f7eb1e8d3d0fe7` at revision `8f050a90f90190009163f4956ab9cc69edbdd0d6`: default 6,716 passed / 0 failed / 2 documented opt-in skips, integration 93 passed / 0 skipped, Compose/browser 19 passed / 0 skipped against source-matched image `palimpsest-api:v3-44-task23`, Godot 47 suites passed, Research UI 231 tests with clean check/build, Ruff/mypy/import/whitespace gates clean, and the 30-case benchmark harness 4 passed. Task 20 is certified by the required authenticated browser gate: 19 required tests executed with zero failures and zero skips against a source-attested image. Task 21 is certified on the final source: `mypy src tests` 0 errors, `ruff` clean, 25 import contracts kept, default collection 6,686 passed / 0 failed / 2 documented opt-in skips, integration 93 passed / 0 failed / 0 skipped, Compose/browser 19 passed / 0 failed / 0 skipped against image `palimpsest-api:v3-44-task21-r2`, Godot 4.7.2 protocol suite exit 0, Research UI 231 tests plus clean check/build, and both opt-in stress probes executed separately (publication RSS and 5,000-boundary checkpoint) and passing. Task 22 is certified on a source-attested working-tree archive: all 30 mechanism cases pass, all 150 predeclared research runs complete with 13 explicit unassisted nulls, deterministic twins are artifact-identical, and the 10k/100k/historical-query scale lanes are measured with truthful incomplete outcomes. The approved compact `v3-analytical-view-v2` checkpoint replaced the blocked 145 MB representation with a 12.4 MB sealed-state-plus-row-digest form at the unchanged cap. No milestone is automatically closed; M6/M7 ownership remains explicit.

### Task 21 execution receipts (2026-10-29)

- Source: HEAD `8f050a90f90190009163f4956ab9cc69edbdd0d6`, with preexisting changes to `src/api/dependencies.py` and untracked `clients/godot-observer/tests/test_multigeneration_replay.gd.uid` preserved by user instruction. This is not a clean-source attestation.
- Full command output and JUnit receipts: `/tmp/opencode/v3-44/task21/`; coverage remains enabled for Python test lanes. Full default baseline finished: exit 1, 6,664 passed / 2 failed / 2 skipped, 137 deselected, 77% coverage, 1,956.57 seconds (`default.xml`). Failures: known path-dependence availability expectation and `test_simulation_branch_fork.py` expecting an unchanged child event ID after rematerialization. Skips: publication RSS and incremental-trait stress prerequisites; neither is certified as passing. This long invocation began before the bounded fixes, so it is baseline evidence, not a final-source rerun. Initial non-scale integration collected 99 of 6,805 tests: exit 1, 81 passed / 12 failed / 6 skipped, 37% coverage, against a new isolated disposable PostgreSQL/pgvector container (removed afterward). All six skips are legacy explicit API integration stubs, not missing database prerequisites. Failures include unseeded run-control foreign keys in API fixtures, a too-short credential fixture, tick revision-delta fixtures, experiment/replay count mismatches, checkpoint log expectations, concurrent memory conflict, path-dependence prefix execution, and metric transition logging.
- `uv run --frozen --python 3.12.14 ruff check src tests`: exit 0. `lint-imports`: exit 0, 25 contracts kept, 0 broken.
- `uv run --frozen --python 3.12.14 mypy src tests`: exit 1, 4,892 errors in 453 test files (1,648 source files checked); no `src/` errors reported. This required gate blocks qualification; do not suppress test checking or mark Task 21 complete.
- Godot 4.7.2: archive SHA-512 matches `clients/godot-observer/export/pins.env`; editor registration and full `res://tests/run_protocol.gd` exit 0, 47 suites passed, 0 failed.
- Research UI in Node 24.22.1 / pnpm 10.34.9: `test`, `check`, `build` exit 0, 45 test files / 231 tests passed, zero Svelte errors/warnings. Initial mount-only invocation lacked sibling Godot fixtures; rerun mounted `clients/` and passed without source changes.
- Full Compose collection: exit 0, 19 passed / 0 failed / 0 skipped, 6,786 deselected, 746.58 seconds; coverage 25% in the host process (does not measure image subprocesses). Command: `PALIMPSEST_API_IMAGE=palimpsest-api:v3-44-task20 PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1 COVERAGE_FILE=/tmp/opencode/v3-44/task21/compose.coverage uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m compose --junitxml=/tmp/opencode/v3-44/task21/compose.xml`. Browser lanes use the retained image, whose revision is `03902f22d362e13be6d72ae25a2d72bb50fca81b`; these are prior-image regression evidence, not current-HEAD release certification. Full certification also requires source-matched image evidence; the stack smoke separately builds its image from the working tree.
- Bounded production regression fixed: `SqlAlchemyMetricSetRepository.transition_metric_set` passed `version` twice to the final log call, raising after commit. Added `tests/unit/test_metric_set_transition_logging.py`; it reproduced that exact TypeError before the fix and passes after changing the new-version field to `resulting_version`. Focused Ruff and mypy pass; coverage-enabled PostgreSQL metric persistence rerun passes (1 passed, 0 failed/skipped; `metric-integration-after.xml`). Full integration results above are the pre-fix baseline, not a full post-fix rerun. No legacy assertions or count pins changed.
- Independently reproduced the known path-dependence failure in 157 seconds: `tests/unit/test_path_dependence_end_to_end.py:72` expects only `unknown`, but source-backed rows include other availability states. `path-dependence.log` retains the failure; resolving this contract/fixture mismatch must not erase valid evidence or silently relax the old assertion.
- Continuation: fixed API integration setup to persist the objective bootstrap that custom tick executors intentionally bypass; bootstrap/event IDs are unique per run; synthetic debug credentials satisfy the existing 32-character minimum. Pagination fixtures now use one revision per committed batch and an explicit final event key instead of treating a null continuation cursor as an end sentinel. No assertions changed. `DatabaseResourcesLike` uses read-only protocol properties so frozen real resources satisfy it without casts.
- Concurrent reconsolidation regression: the existing six-way PostgreSQL test failed twice before the fix. Owner/run-scoped transaction advisory locking now precedes reconstruction read/validation/insertion, so identical retries observe the committed reconstruction and remain idempotent. Normal writes and access-only batches retain their existing path. The focused PostgreSQL rerun (`integration-focused.xml`) passes all 9 selected tests with no skips, including concurrency, metric persistence, API authorization, event pagination and stream publication.
- Four legacy unit files now explicitly narrow decoded models, event details and optional initialization values; no suppressions or old assertion/count changes. All 66 runtime checks pass (`typed-regressions.xml`). Full mypy rerun falls from 4,892 errors / 453 files to 3,312 errors / 443 files (`mypy-second.log`); all 10 directly checked changed source/test files pass (`mypy-touched.log`). Full Ruff and all 25 import contracts pass again. App lifecycle plus metric logging regression: 7 passed.
- Full integration reruns: second baseline 84 passed / 9 failed / 6 skipped; third baseline 87 passed / 6 failed / 6 skipped; fourth baseline 90 passed / 3 failed / 6 skipped (`integration-second.xml`, `integration-third.xml`, `integration-fourth.xml`). These are intermediate source states, not final certification. Restoring metadata-only snapshot-selection DEBUG logging in bounded replay fixes the cadence diagnostic regression; selecting the existing V1-only Experiment A builder preserves the legacy two-arm assertion. The fourth run's failures are stale API-field and replay-event expectations plus incomplete database path-dependence composition. Its prefix uses non-durable config with durable pending-finalization adapters and fails the parent-run foreign key; do not bypass the foreign key or invent persisted history.
- User explicitly approved replacing the two stale API/replay assertions with strict current-contract checks (2026-10-29). API lifecycle now validates the complete strict response schema and enum; replay compares the exact independently retained live event suffix for ticks 3–4 (including autonomous physical events), and historical state to the persisted tick-3 checkpoint rather than tick-5 state. Compatibility/count pins remain unchanged. Fifth full integration rerun: exit 1, 92 passed / 1 failed / 6 skipped, 79.79 seconds (`integration-fifth.xml`); only database path-dependence prefix execution still fails. Latest full Ruff passes; full mypy remains 3,312 errors / 443 test files with no `src/` errors (`mypy-latest.log`, `ruff-latest.log`). Tasks 21–23 remain unchecked.
- Next continuation repaired PostgreSQL path-dependence through existing composition seams: durable specs are explicit, the CLI accepts the existing materializer callback, PostgreSQL composition uses `BranchService.materialize_objective_fork`, and runner fork continuation validates/binds the child prefix's commit hash. Partial durable setups fail before ensemble publication. No new command, schema, capability, migration, or durable subjective-resume claim. Dedicated PostgreSQL proof passes (`path-durable.xml`, 1 passed); sixth complete integration run passes all 93 executable tests with 6 legacy placeholder skips (`integration-sixth.xml`, 108.80 seconds).
- User explicitly approved correcting the two stale default-suite expectations. The fork test now pins the deterministic child-specific SHA-256 event ID and asserts parent identity/payload isolation. The smoke test requires finite, algorithm-qualified measured rows and reason-qualified unknowns, including an explicitly incomplete institution search; it never requires positive emergence. These checks plus CLI negative preflights pass (`path-unit.xml`, 8 passed). Four fail-closed durable-prefix mismatch cases plus existing continuation parity pass (`fork-prefix-guards.xml`, 8 passed).
- Four further legacy unit files now use explicit decoded-model/detail narrowing and typed helpers: `typed-second.xml`, 22 passed, and focused mypy passes. Full mypy is down to 2,806 errors / 439 test files (`mypy-current.log`), with no `src/` errors. Full Ruff and all 25 import contracts pass (`ruff-current.log`, `imports-current.log`).
- User explicitly approved retiring only the six skip-only API placeholders after their executable PostgreSQL replacements passed. Replaced them with pointers to the real integration files; no executable test was removed. Fresh integration qualification without these placeholders passes: exit 0, 93 passed / 0 failed / 0 skipped, 108.89 seconds (`integration-current.xml`). A fresh whole default collection is running with the documented synthetic publication/reducer budgets (`PALIMPSEST_V3_PUBLICATION_SCALE_FRAMES=20000`, `PALIMPSEST_V3_INCREMENTAL_SCALE_BOUNDARIES=5000`) so its two prior opt-in skips are exercised (`default-current.*`). These synthetic measurements are not 10k/100k scientific-scale certification. Tasks 21–23 remain unchecked; source-matched browser image and full typing gates are still required.
- Further type remediation: collective-project/public-good perception, civilization observer fixtures and their regional checkpoint/lifecycle helpers now pass focused mypy (5 files) and 155 coverage-enabled runtime tests (`typed-fourth.xml`). Fixed exact heterogeneous fixture tuple types, added runtime-checked row narrowing, typed helpers and explicit optional guards. Negative malformed/frozen input tests retain their checks; only the intentional frozen assignment uses a narrowly documented `ignore[misc]`.
- Restored the missing `forget_selected_ids` protocol surface in the scriptable memory fake and empty typecheck stub; fake forgetting now stamps only selected active IDs, preserves source values, rejects invalid/premature ticks and remains idempotent. Added focused cases and typed the cognition fakes' ignored optional inputs. Fake/cognition tests pass (19, no failures/skips; `fake-contracts.xml`), and focused mypy passes (4 files). Latest whole-tree mypy: 2,503 errors in 430 test files, no `src/` errors (`mypy-typing-fifth.log`). Full Ruff passes (`ruff-typing-fifth.log`). These newer test/fake edits postdate the start of `default-current`; its result is not a final-source all-tests attestation.
- Source-attested release build completed successfully as `palimpsest-api:v3-44-task21` (`release-build.log`), image ID `sha256:e415dbd2838e5229ab2420c6e9ad8dc6375a1d8c95cc2cba20af4d88dcc5011e`. Exact build context: `/tmp/opencode/v3-44/task21/release-source.tar`, committed base `8f050a90f90190009163f4956ab9cc69edbdd0d6` plus normalized overlays for all 45 modified/untracked first-party inputs. SHA-256: `ad616b7d5545b1a22b121abb4e3514baa5fc4436fde5a4492d27e96acd27fd0c`. Identity manifest: `release-source-identity.json`. Image revision and source labels match that manifest through `parse_source_identity_labels`; clean-source assertion is explicitly false. The digest identifies the actual immutable tar context supplied to Docker, including preserved preexisting inputs. Full authenticated Compose/browser collection passes against this image: exit 0, 19 passed / 0 failed / 0 skipped, 423.60 seconds (`compose-current.xml`, `PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1`). This qualifies that exact archived candidate's release lane, not arbitrary later source changes or completion of Task 21's remaining gates.
- Whole default rerun completed with both documented synthetic stress inputs enabled: exit 1, 6,673 passed / 2 failed / 0 skipped, 131 deselected, 78% coverage, 2,110.67 seconds (`default-current.xml`). The earlier functional failures are gone. Failures are the synthetic publication RSS comparison (`streamed_delta=159744`, `legacy_delta=4096`, failing the strict ordering assertion) and incremental trait checkpoint export at 5,000 boundaries (`AnalyticalViewMismatch: checkpoint_too_large`). These are explicit failed stress checks, not passes or skipped prerequisites. No resource limit, workload size, or assertion was weakened after observing them; qualification remains blocked.
- Continued strict typing without changing test semantics: added 64 proven no-value return annotations across seven civilization test modules; their 127 runtime checks pass (`return-annotations.xml`). Typed shared frame/recorder/publication helpers, added explicit receipt/row/optional guards and corrected concrete inventory return types. Helper/civilization follow-ups pass (30 tests, `civilization-helper-types.xml`); capture follow-up passes (52 tests, `capture-helper-types.xml`). Latest exact whole-tree mypy: 2,341 errors in 426 test files, no `src/` errors (`mypy-returns-final.log`). Full Ruff and whitespace checks pass (`ruff-returns-final.log`, `git diff --check`). All latest edits are test-only and postdate the archived release context; they do not change the already-qualified image's runtime source, but are not retroactively certified by that image's artifact identity.
- Publication RSS failure was a benchmark isolation defect: sequential encoders shared allocator state warmed by earlier work. Each encoder now runs in its own fresh spawned interpreter, with identical inputs, a 300-second positive worker budget, safe failure codes and child coverage collection. Exact artifact-byte equality and both original strict memory comparisons remain required. The unchanged 20,000-frame workload passes (`publication-stress.xml`, 1 passed, 0 skipped, 35.83 seconds): 2,009,610 artifact bytes, 253,952 streaming RSS delta bytes versus 8,105,984 legacy RSS delta bytes. Focused isolation/error/budget regressions pass (`rss-isolation-final.xml`, 4 passed). No application codec, workload count or performance assertion was relaxed.
- The incremental checkpoint failure is a genuine representation limit, not an arbitrary threshold to raise. A bounded 300-second diagnostic on the unchanged 5,000-boundary workload measures 145,489,296 canonical checkpoint bytes against the existing 67,108,864-byte cap; 210,017 measurement rows occupy 133,122,703 bytes, states 11,528,891 bytes, and evidence 836,700 bytes (`checkpoint-size-diagnostic.log`). The cap and complete checkpoint contents remain unchanged. Supporting this workload requires separately scoped checkpoint representation/versioning work rather than a Task 21 assertion/cap workaround; this stress gate remains failed and blocks full qualification.
- Latest post-RSS static gates: full Ruff passes; import-linter keeps all 25 contracts; whole-tree mypy remains 2,341 errors in 426 test files (1,651 files checked; `ruff-rss-final.log`, `imports-rss-final.log`, `mypy-rss-final.log`). No new full default rerun is claimed after the isolated RSS fix; the checkpoint and typing blockers remain explicit. Tasks 21–23 remain unchecked.
- Standard pytest fixture annotations preserve all runtime assertions: 194 coverage-enabled checks pass with zero failures/skips (`pytest-fixture-types.xml`). The subsequent whole-tree mypy baseline is 2,318 errors in 425 test files, 1,651 source files checked (`mypy-fixtures.log`). User explicitly authorized parallel typing remediation: six agents own disjoint unit-test inventories under `/tmp/opencode/v3-44/task21/typing-batches/batch-{1..6}.json`; parent owns the 21 non-unit/shared-helper files in `parent.json`. Agents must preserve assertions, compatibility pins, dirty work and mypy settings; they cannot edit application code or plan status. Delegation is in progress, not a passing gate.
- Parent typing remediation now passes strict mypy and Ruff across all 21 parent-owned files plus `src/research_runner/civilization_composition.py` (`mypy-parent.log`, `ruff-parent.log`). Shared helpers use concrete tuple/default types and public identity imports; integration fixtures narrow retained JSON/events and optional tick results; planner fakes accept the complete current protocol; Playwright callbacks and generic timing helpers are typed. `_RunnerSink` now accurately accepts `CivilizationCaptureSink | None`, matching the real runner rather than incorrectly promising arbitrary-object acceptance. Parent-scoped whitespace checks pass, and all 25 import contracts pass (`imports-parent.log`). Coverage-enabled non-scale PostgreSQL integration and focused architecture reruns are underway; no runtime result is claimed yet. The source annotation change postdates the archived release image, so that candidate's exact source identity does not cover the current tree. Checkpoint cap/workload and Tasks 21–23 remain unchanged and blocked.
- Parent architecture rerun passes: 8 passed, zero failures/skips, coverage enabled (17% scoped coverage, `parent-architecture.xml`, 23.69 seconds). Whole-collection integration attempt exits 2 before execution with nine collection errors from in-progress agent-owned unit imports (`integration-parent.xml`); owning agents were sent concrete corrections. This is a failed collection, not a passing integration lane. A fresh disposable-PostgreSQL rerun explicitly scoped to `tests/integration -m 'integration and not scale'` is underway (`integration-parent-scoped.*`) to verify parent changes independently; full collection must still be repeated after agent integration.
- Resumed with whole-tree mypy at 583 errors across 101 remaining unit-test files; six disjoint batches cleared all of them without new suppressions. Final static gates: `mypy src tests` exit 0 (`Success: no issues found in 1651 source files`, `mypy-final-3.log`); `ruff check src tests` exit 0 after import-order/unused-import corrections and 31 manually wrapped long lines (`ruff-final-3.log`); `lint-imports` exit 0, 25 contracts kept, 0 broken (`imports-final-2.log`); `git diff --check` clean. The only remaining ignores are four pre-existing site-specific ones; every `# type: ignore` removed by the batches had become unused.
- Compact checkpoint representation, added as an explicitly approved Task 21 scope add: `v3-analytical-view-v2` persists states, evidence, identity and the exact digest of derived final rows instead of duplicating them. `read_checkpoint` dispatches on schema version, recomputes rows for sealed views and fails closed with `view_output_digest_mismatch`; legacy `v1` files remain readable and resumable (the container version alone is normalized before the exact final-row identity check). Three regressions added (compact payload shape, legacy v1 round-trip, inconsistent digest rejection); `tests/unit/test_incremental_v3_metrics.py` passes 18 tests; `docs/long-horizon-scalability.md` and `docs/cultural-evolution-metrics.md` corrected. The unchanged 5,000-boundary probe now passes: 210,017 rows, checkpoint 12,366,660 bytes against the unchanged 67,108,864-byte cap, exact batch/incremental parity and the original footprint bound intact (346.85 seconds, `incremental-probe.log`). No workload, cap or assertion was relaxed.
- Per explicit user decision, Task 21's required default gate is the configured `addopts` collection; the two opt-in stress probes are additionally executed and reported as measurement lanes (publication RSS and incremental checkpoint), never as required-gate passes.
- Non-scale PostgreSQL integration: exit 0, 93 passed / 0 failed / 0 skipped, 120.72 seconds, coverage enabled, against a fresh disposable `palimpsest_test_r3` (PostgreSQL 17.11 + pgvector 0.8.6) on the existing host-network container (`integration-final.xml`).
- Godot 4.7.2: the pinned release archive `/tmp/opencode/godot.zip` SHA-512 equals `GODOT_LINUX_SHA512` in `clients/godot-observer/export/pins.env` (the pin covers the archive, not the extracted binary); editor registration exits 0 and the full `res://tests/run_protocol.gd` registry exits 0 with `godot_protocol_tests failed=0` (`godot-final.log`).
- Research UI with pnpm 10.34.9: `test` 45 files / 231 tests passed, `check` 0 errors and 0 warnings, `build` exit 0 (`research-ui-final2.log`). The host run first required removing root-owned `dist/assets` and `node_modules/.vite` left by an earlier container invocation; that was an `EACCES` artifact, not a source defect.
- Source-attested release image `palimpsest-api:v3-44-task21-r2`, ID `sha256:3b965ff78c8c6d547d0601bf6594f78143e6317f4d2280fc53bdde04a6787790`, built from context tar SHA-256 `a9b3a512482802d92ab4453fc32c14189397708d8fc5f516cf755f83c676d398` (committed base plus all 477 modified/untracked first-party inputs, `source-clean=false`) on HEAD `8f050a90…`; image labels match the manifest. The build required `--network=host` because the daemon bridge had no DNS; no source changed (`release-build-r2b.log`).
- Authenticated Compose/browser collection against that exact image: exit 0, 19 passed / 0 failed / 0 skipped, 426.00 seconds (`compose-final.xml`), covering the generational, civilization and V2 observer browsers, Research UI generational panels, the image-owned SPA plus real V2 matrix summary without host `dist`, V3 benchmark release markers and negative-credential isolation.
- First complete default collection on the new source: exit 1, 6,677 passed / 9 failed / 2 skipped, 1,906.90 seconds (`default-final.xml`). All nine failures were typing-remediation side effects, not product regressions: three fakes had gained a `session_factory` attribute that defeated the app's `hasattr`-based persistence attachment, and three acceptance-memory tests had been converted from the intentional duck-typed `SimpleNamespace` to the real `Observation`, whose validation rejects same-tick occurrences. Restored lean fakes with explicit `DatabaseResourcesLike` casts, restored the duck-typed observation behind a typed helper, and applied the same correction to `test_api_streaming.py`. The affected files pass focused mypy and Ruff, and their 43 tests pass. This run is superseded, not certified.
- Final-source default collection (Task 21 required gate): exit 0, 6,686 passed / 0 failed / 2 skipped, 131 deselected, 78% coverage, 1,876.22 seconds (`default-final2.xml`). Both skips are the documented opt-in stress probes (`PALIMPSEST_V3_PUBLICATION_SCALE_FRAMES` and `PALIMPSEST_V3_INCREMENTAL_SCALE_BOUNDARIES` unset); each was executed separately and passed, and neither is counted as a required-gate pass. The run covers the V1 A–E/reference gates, the V2 scientific invariants and benchmark registry, architecture/import boundaries, typecheck fixtures, generational/civilization/replay/lineage suites, and the Research UI artifact tests.
- Post-fix static gates on that same source: `mypy src tests` exit 0 (`Success: no issues found in 1651 source files`, `mypy-final-cert.log`), `ruff check src tests` exit 0 (`ruff-final-cert.log`), `lint-imports` exit 0 with 25 contracts kept and 0 broken (`imports-final-cert.log`), `git diff --check` clean (`whitespace=0`). Task 21 is certified on this source; Task 22 is next.

### Task 22 execution receipts (2026-10-30)

- Source identity for every Task 22 run: committed revision `8f050a90f90190009163f4956ab9cc69edbdd0d6` plus explicit source-artifact digest `4e35ee066246bbe59745d5dfbf43e65aa158469565a111143d690c5bcd988891` (SHA-256 of a deterministic tar of all 2,951 tracked/untracked non-ignored first-party files; `source_clean=false`). Artifact roots: `/tmp/opencode/v3-44/task22/`; full logs/XML retained there. No synthetic identity is presented as a release attestation.
- Composition gaps found by the first real all-30 execution and fixed without weakening contracts: independent benchmark attempts previously had no execution branch (UnboundLocalError); the CLI built only the generic base world and ignored every case's declared `required_specs`/`required_modes` and mechanism arbiter; non-durable history readers reported tick numbers instead of the committed objective revision; long-run evidence exports dropped phenomena measured while owners were alive; and a stable narrative-variant ID collision aborted grouped children at tick 180. Fixes route each case through its owned domain builder/arbiter, bind the boundary reader to the live engine revision, retain measured boundary history for phenomena, and merge same-lineage frozen narrative rows with unioned measured evidence. Added `test_same_lineage_identity_collision_merges_measured_evidence`; narrative suites pass 19/19.
- New comparison contract `src/experiments/civilization_benchmark_comparison.py` and `tests/unit/test_v3_benchmark_comparison.py` (26 passed, coverage enabled). It keeps descriptive and inferential summaries separate, verifies materialized treatment scopes before contrasts, treats numeric seeds as independent blocks, records duplicate-seed and missing-pair denominators, rejects non-finite values, suppresses intervals without at least two complete paired blocks, marks founder-roster whole-population observations descriptive-only, requires every changed mode in composite initializer treatments, and delegates grouped scalar outcomes to the existing path-dependence estimator. No causal or positive-effect gate is introduced.
- `tests/benchmarks/test_v3_civilization_benchmark.py` (integration+scale) executes through the production CLI composition, verifies mechanism suites with `--require-complete`, verifies research suites for integrity while recording explicit nulls, repeats smoke research in a separate namespace as a deterministic twin, executes all five predeclared research seeds, writes `qualification-matrix.json`, and composes descriptive seed-block summaries from retained artifacts. Final run: exit 0, 4 passed, 0 failed, 0 skipped, 1,441.39 seconds (`benchmark.log`, `benchmark.xml`).
- Mechanism smoke (seed 23): 30/30 completed the declared 96 ticks with complete evidence and every required check passing. Research smoke (seed 23): 30/30 completed 96 ticks; 17 scenarios passed all mechanism checks autonomously and 13 retained explicit `unexecuted` null checks (`no_record_observed`, `no_practical_knowledge_observed`, `no_commitment_observed`, `no_exchange_negotiation_observed`, `no_completed_exchange_observed`, `no_project_contribution_observed`, `no_completed_project_observed`, `no_translation_hypothesis_observed`) because those mechanisms require deliberate controlled action. Research profile: 150/150 runs completed 192 ticks across seeds 11/23/37/53/71, including both grouped cases; 13 scenario families carry the same explicit null statuses. Nulls are never converted to passes or silently skipped.
- Deterministic twins: the research-smoke suite rerun into a separate namespace produced identical ordered artifact-hash sequences for all 30 cases. Grouped cases 29 and 30 retain the sealed-prefix protocol, unchanged parent, independent ordinary-command children and `grouped_continuation_observed` source references; case 29 succeeds at 192 ticks after the narrative-ID fix.
- Strict artifact verification: `civilization-benchmark verify --require-complete` on the mechanism suite exits 0 (`benchmark_suite_status=complete`). The same strict command on the research suite exits 1 with `incomplete_suite`, which is the explicit consequence of legal unassisted nulls; integrity verification without `--require-complete` exits 0 (`benchmark_suite_status=incomplete`). The matrix records 19 completion-criteria rows: 14 verified by passing mechanism lanes and 5 unexecuted external gates (V1/V2 regression collection, Godot, Research UI, zero-install image, long-running auditability); no external gate is claimed passed from this lane.
- V3-43 scale re-runs with coverage enabled. 10k supervised lanes: exit 0, 1 passed, 0 failed, 0 skipped, 700.39 seconds (`scale-10k.log`). Generational and evidence-rich lanes completed 10,000 ticks (5 cohorts); the flags-off control truthfully timed out at 2,189/10,000. Historical-query lanes: exit 0, 3 passed, 0 failed, 0 skipped, 75.82 seconds against disposable PostgreSQL (`scale-historical.log`). 100k predeclared attempt: exit 0 after 8,450.85 seconds (`scale-100k.log`); the generational lane completed 100,000 ticks in 1,196.68 seconds but ended with zero living owners (all nine dead), so this is an engine/envelope throughput measurement, not sustained-population capacity; evidence-rich timed out at 90,765 and the flags-off control at 8,158. No universal 100k or dense-capacity claim follows.
- Focused runtime/type verification after the fixes: `tests/unit/test_v3_benchmark_comparison.py` 26 passed with coverage; 134 focused narrative/benchmark/invariant unit tests passed; `ruff check src tests` exit 0; `mypy src tests` exit 0 (`Success: no issues found in 1654 source files`); `lint-imports` exit 0 with 25 contracts kept and 0 broken. These static gates cover the new comparison module, CLI/composition wiring, evidence fallbacks and narrative collision merge.
- Task 22 does not close M6/M7, does not own `institutional_economy` or `multi_hop_testimony_tracking`, and does not claim durable subjective restart, recorded/live LLM forks, universal 100k capacity or autonomous emergence of any institution/money/myth/government/religion. Task 23 remains for documentation and full final verification.

### Task 23 execution receipts (2026-10-30)

- Documentation checkpoint executed: created `docs/v3-benchmark-suite.md` (229 lines) with the 30-case mapping, profiles/seeds/stops, controlled versus unassisted lanes, founder/entrant and composite-profile scopes, content-empty learner pack, artifact schemas, strict-versus-integrity verification, seed-block comparison assumptions, qualification snapshot, measured 10k/100k envelope and limits, and release prerequisites. Indexed it from `README.md`, `docs/development.md`, `docs/experiments.md`, `AGENTS.md`, and updated `docs/long-horizon-scalability.md` with the current measured rows. Relative-link check: 0 broken links.
- Completion matrix retained at `/tmp/opencode/v3-44/task23/benchmark/qualification-matrix.json` from the final-source harness: 30/30 mechanism scenarios pass, 150/150 research runs completed, 13 explicit unassisted null families, twins identical, 14/19 completion criteria verified by mechanism lanes and 5 external criteria separated. No bulk evidence is committed.
- Narrow context refresh: `.ai-factory/DESCRIPTION.md` records the separate V3-44 registry, v55 fixtures, artifact/comparison/CLI seams and unchanged pins; `.ai-factory/ARCHITECTURE.md` adds the V3-44 seam and its no-authority/no-global-registry boundary. No roadmap milestone is closed; M6/M7 ownership remains explicit.
- Final verification on executable-source digest `fef95f48f5a3d461fea6325953b64b265c936a514d0f012986f7eb1e8d3d0fe7` at revision `8f050a90f90190009163f4956ab9cc69edbdd0d6`: default collection 6,716 passed / 0 failed / 2 documented opt-in stress skips / 135 deselected, 78% coverage, 1,934.54 s; PostgreSQL integration 93 passed / 0 failed / 0 skipped, 112.70 s; Compose/browser 19 passed / 0 failed / 0 skipped, 384.80 s against `palimpsest-api:v3-44-task23`; Godot 4.7.2 47 suites passed / 0 failed with the pinned archive SHA-512 matched; Research UI 45 files / 231 tests, 0 errors/warnings, build ok; Ruff clean; mypy 0 errors across 1,654 files; 25 import contracts kept; `git diff --check` clean; final benchmark harness 4 passed / 0 failed / 0 skipped, 1,455.16 s; historical queries 3 passed; 10k/100k lanes retain the truthful mixed outcomes recorded under Task 22.
- Release image `palimpsest-api:v3-44-task23` ID `sha256:532695b563b9dc6b0da96bd677d38bce94eccc33922ceaf5b337b759f5fd4b87` carries matching revision/digest labels (`source-clean=false`), so the browser gate is source-matched rather than prior-image evidence.
- Plan integrity: exactly one ultra marker, nine phase links (32 references), 23 indexed tasks mapped one-to-one to 23 `## Task N` sections with no duplicates, missing or unmapped sections. Preserved unrelated preexisting `.uid` work was not edited. `$aif-verify` and the standalone rules gate complete with no blocking findings; deferred flags, universal-100k and durable-subjective claims remain unclaimed.

### Post-verification remediation (2026-10-30)

- A subsequent independent `$aif-verify` pass returned `warn` with zero blockers: implementation, gates, pins and the shipped artifacts verified, but four non-blocking findings remained. All four are addressed here. No task status, compatibility pin, benchmark contract, assertion or count was changed, and no milestone was closed.
- Required-mode gating was only partially enforced: `tests/compose/conftest.py` skipped a missing Docker CLI, Playwright or `PALIMPSEST_API_IMAGE` even under `PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1`, so only the CI XML post-check prevented a false green. New `tests/compose/acceptance.py` owns the switch; `conftest.py`, `test_stack.py` and `test_observer_browser.py` now fail closed. Behavioural proofs: optional run → 1 skipped; required without an image → 1 failed with `required release acceptance cannot skip`; required with `palimpsest-api:v3-44-task23` → 1 passed. New `tests/unit/test_compose_acceptance_gate.py` covers all three modes (4 passed).
- Evidence-retention wording: the Task 22/23 artifact roots under `/tmp/opencode/v3-44/` no longer exist, and two shipped pages asserted retention there. `docs/v3-benchmark-suite.md` and `docs/long-horizon-scalability.md` now state that artifacts are caller-rooted, uncommitted and regenerated by re-running the lanes. No matrix or bulk evidence is committed, and no historical measurement value was altered.
- Harness documentation: `docs/development.md` now documents `PALIMPSEST_V3_ACCEPTANCE_REQUIRED`, both opt-in stress-probe gates (`PALIMPSEST_V3_PUBLICATION_SCALE_FRAMES`, `PALIMPSEST_V3_INCREMENTAL_SCALE_BOUNDARIES`) and the `PALIMPSEST_SOURCE_CLEAN` / `PALIMPSEST_SOURCE_ARTIFACT_DIGEST` build attestations, including the conflicting-attestation, missing-revision and malformed-digest failures the Dockerfile enforces.
- Roadmap drift: `.ai-factory/ROADMAP.md` M7 lists `v3-44-generational-benchmark` with its exact seams and records that it adds no capability flag, schema, command, event, observer semantic type, metric family, route or migration. M7 stays open for `institutional_economy` and deferred kinship handoff; M6 stays open for `multi_hop_testimony_tracking`.
- Re-verification after the changes: `ruff check src tests` clean, `mypy src tests` exit 0 (`Success: no issues found in 1656 source files`), `lint-imports` 25 contracts kept / 0 broken, `git diff --check` clean, and the full required Compose/browser lane re-executed against the source-matched image: 19 passed / 0 failed / 0 errors / 0 skipped, 387.74 s.

## Original Request

v3-44 V3 end-to-end generational civilization benchmark

Plan naming requirement:

The final plan artifact MUST use a canonical stem beginning with `v3-`.

Suggested stem:

v3-44-generational-benchmark

Create the final V3 integration and research benchmark suite.

Run all V1 and V2 regression suites.

Create multiple deterministic/small-statistical scenarios rather than one giant scripted demo.

Include scenarios covering:

1. New agents entering a society without inherited memories.
    
2. Dependent young agents requiring social care.
    
3. Intergenerational skill transmission.
    
4. Cultural knowledge mutating across generations.
    
5. Eyewitness memory becoming communicative memory and later cultural memory.
    
6. A written record preserving information after all witnesses die.
    
7. A false written record preserving misinformation.
    
8. Technology discovery.
    
9. Technology diffusion.
    
10. Technology loss after all knowledge holders disappear.
    
11. Independent technology rediscovery.
    
12. Emergent inheritance practices after a death.
    
13. Long-term promise/debt fulfillment and violation.
    
14. Negotiated barter with subjective valuations.
    
15. Candidate medium-of-exchange behavior without hard-coded money.
    
16. Collective project coordination.
    
17. Public-good contribution/free-riding patterns.
    
18. Migration between regions.
    
19. Two isolated populations developing different cultural patterns.
    
20. Re-contact and knowledge/cultural exchange.
    
21. Symbolic vocabulary divergence.
    
22. Semantic drift across generations.
    
23. Cross-cultural mistranslation.
    
24. Historical narrative surviving after eyewitness extinction.
    
25. Emergence of a persistent social role.
    
26. Succession of an office after its occupant dies.
    
27. Institutional persistence across generations.
    
28. Institutional decay or disappearance.
    
29. Same initial world with a small founder-event intervention creating divergent histories.
    
30. A multi-generation forked replay experiment.
    

### Scientific constraints

Do not assert:

a government must emerge

money must emerge

religion must emerge

a myth must emerge

an institution must emerge

Instead validate:

mechanisms exist

events remain correctly sourced

provenance is preserved

emergence can be measured when it occurs

null results remain valid research outcomes

### Generational invariants

Verify:

new agents never inherit arbitrary parent memories

agents cannot access objective historical truth unless perceived through valid channels

dead agents stop acting

records persist only through physical world mechanisms

records may contain false information

technology can be lost

knowledge lineage remains auditable

institutional roles remain subjective/social constructs

objective possession remains separate from legitimacy beliefs

multiple societies do not magically share knowledge

migration occurs through WorldEngine actions

presentation coordinates never enter simulation semantics

Godot observer remains read-only

### Replay invariants

Verify:

multi-generation deterministic replay works

birth/new-agent creation replays identically

death replays identically

genealogy reconstructs identically

technology lineage reconstructs identically

forked historical experiments preserve parent/child run lineage

recorded LLM cognition can be replayed where configured

### Visualization acceptance

Verify the zero-install release workflow still requires only:

container runtime

browser

and does NOT require:

local Godot installation

Godot editor

manual Web export

manual frontend build

Validate that Godot can visually replay a multi-generation scenario containing:

new agents  
deaths  
migration  
teaching  
collective project  
technology spread  
cultural divergence  
institutional succession

### Research UI acceptance

Verify researchers can inspect:

genealogy  
knowledge lineage  
technology history  
cultural evolution  
historical narratives  
institutions  
migration  
population  
forked historical runs

### V3 completion criteria

V3 is complete when:

- V1 and V2 invariants remain valid.
    
- Population can change across time.
    
- Multiple generations can coexist and replace one another.
    
- New agents learn culture rather than receiving copied memories.
    
- Knowledge can persist beyond individual lifetimes.
    
- Knowledge can also be lost.
    
- Technologies can emerge, spread, mutate and disappear.
    
- Cultural traits can be measured across generations.
    
- Separate populations can culturally diverge.
    
- Populations can later interact without magically synchronizing knowledge.
    
- Persistent social roles/institutions can be observed without scripting their existence.
    
- Institutions can survive occupant death.
    
- Institutions can transform or disappear.
    
- Historical narratives may outlive all witnesses.
    
- Small historical interventions can be compared through forked multi-generation runs.
    
- Godot can observe generational history without affecting it.
    
- Research UI can analyze lineage and long-term societal change.
    
- Normal deployment remains zero-install with respect to Godot.
    
- Long-running generational experiments remain reproducible and scientifically auditable.

## Settings

- Testing: yes; all requested regression/invariant/replay/client gates, coverage enabled.
- Logging: verbose metadata-only; bounded DEBUG flow/counts, INFO milestones, WARN incomplete evidence and ERROR safe codes. `PALIMPSEST_LOG_LEVEL` controls operational verbosity; no private content, payload surrogates, prompts, credentials or DSNs.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 23.
- Language: English UI/artifacts; preserve technical terms.
- Git: enabled; base `main`; no branch/worktree creation; skip-push preference retained. Commit checkpoints below are suggestions, not authorization to commit during planning.
- Workflow: slug IDs; normal verification, with explicit complete required-gate certification.
- Naming: canonical stem `v3-44-generational-benchmark`; phase filenames also start with `v3-`. `index.md` is the canonical ultra entrypoint.
- Research source: no configured RESEARCH file or marked research bundle exists; no external research conclusions are invented.
- Execution: planning only in this invocation. All proposed module/type/CLI/schema names are new unless identified as existing in phase evidence tables.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"
Rationale: Integrate and qualify the existing V3 mechanisms, generational research, replay and read-only release surfaces without scripting civilizational outcomes.

M7 remains open for unowned `institutional_economy` and deferred kinship cultural/knowledge handoff; M6 remains open for `multi_hop_testimony_tracking`. This plan does not implement or claim those capabilities. Closing this suite is not automatic roadmap closure; use the milestone owner workflow/user decision.

## Requirements Reconciliation

Authority: repository/project rules constrain all edits; the Original Request defines scope. Existing architecture, exact codecs and scientific contracts govern compatibility. The request's positive scenario descriptions are refined by its explicit null-result constraints: mechanism/provenance tests are mandatory; autonomous emergence and effect direction are not. No conflicting source is silently rewritten.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| Separate V3 30-case registry, preserve V2 16-case registry and V1 A–E/reference gates | Original Request; `src/experiments/benchmark_suite.py`; `docs/v2-benchmark-suite.md` | Tasks 1, 21: exact registry pins and whole default/integration/Compose/client collections |
| Controlled mechanism fixtures may schedule normally admitted commands, but cannot seed subjective state or count as autonomous emergence | Original Request Scientific constraints; `src/experiments/interventions.py` | Tasks 4, 6–13: applied acknowledgements, intervention receipts, arbiter-free independent research; grouped research retains declared treatment controls |
| Every actual newborn store is measured before first cognition; modes are not inherited content | Original Request scenarios 1–4; `src/simulation/new_agent_initialization.py`; runner's existing synthetic-zero assertion | Tasks 3–4, 6, 14: real measured snapshots and poisoned-store negative test |
| Descendant symbolic/translation/institution modes need an explicit content-empty profile, not silently expanded old packs | Existing `species_defaults_for` packs; Original Request scenarios 21–28 | Task 3 v55-only new policy ID; old-pack canonical parity; no new runner schema/flag |
| v55 must preserve selected exact lower-family root, not concatenate all historical builder JSON | `src/experiments/generational_execution.py`; `src/simulation/runner_serialization.py` | Tasks 2, 6–13: all recipe codec round-trips and exact prerequisite checks |
| Declared tick horizons require explicitly disabled competing stop selectors; nonfailure early stop is not full coverage | `GenerationalRunSpec`; comparison base cap 6 and BN smoke cap 16 | Tasks 2, 13, 22: no inherited generation/extinction/threshold/criteria cutoffs; actual final boundary equals H |
| Founder-mode changes do not disable the same modes in newborn profiles | `src/simulation/runner.py` `_sync_mid_run_population_entries` / `species_defaults_for` | Tasks 2–3, 12, 22: actual founder/entrant mode vectors, scoped estimands and composite-profile labels |
| Truth labels stay analysis-only; false record marks are physically legal | Original Request scenarios 5–7; `src/experiments/interventions.py` StoryTruthSpec; architecture trust boundary | Tasks 7, 14: real inscription/reading/death plus missing/destroyed/false controls |
| Complete-empty inventory differs from unknown/disabled/truncated capture | `docs/cultural-evolution-metrics.md`; `docs/lineage-explorer.md` | Tasks 4–5, 8, 12: required coverage per selector/arm, censored loss/collapse |
| Objective replay does not reconstruct absent subjective technology lineage | Original Request Replay invariants; `src/simulation/replay.py`; lineage capture contracts | Task 15 separately proves objective fold, deterministic rerun, in-process fork and source-backed lineage rebuild |
| Terminal research inspection must not depend on a terminal-ineligible fork checkpoint | `src/simulation/runner.py` `export_finalized_research_boundary` currently delegates to `capture_fork_checkpoint` | Tasks 4, 13, 15: terminal-safe projection after finish; pending-finalization rejection; strict fork guard preserved |
| True grouped forks require common prefix and complete process-local owner state | `docs/historical-contingency.md`; `src/experiments/path_dependence_catalog.py` | Tasks 13, 15: parent unchanged, same-identity twin, qualified children, process-loss limits |
| Recorded cognition replay is independent from recorded-LLM fork continuation, which remains unsupported | Original Request "where configured"; `SimulationRunner.from_fork_checkpoint` guard | Task 16 whole configured stage/run recording replay, positive usage and zero fallback; recorded forks reject |
| Archival recording usage rejects untracked custom provider factories | `RunnerDependencyFactories.with_generational_control`; `_default_provider` / `_inner_provider_for_recording` | Task 16 uses normal provider/store construction, RECORD not-required versus REPLAY required provenance, positive archived usage and custom-factory rejection |
| Source revision alone is not a clean-source assertion or source-artifact identity | `src/experiments/generational_artifacts.py` `source_identity_preflight` | Tasks 5, 19–20, 22: explicit revision plus exactly one clean/digest assertion, verified image labels, missing/dirty/no-Git tests |
| Positive visual acceptance must use source-backed real history, never substitute mocked evidence or mandate autonomous institutions | Original Request Visualization acceptance and Scientific constraints | Tasks 17, 20: one controlled real fixture, eight actual markers, separately labeled synthetic rendering tests and null research |
| Release image must include Research UI as well as Godot; no host asset build | Original Request zero-install requirements; `Dockerfile`; `compose.yaml` | Tasks 19–20 clean image-only startup and real browser workflows |
| Researchers inspect populated evidence, not only headings/unavailable states | Original Request Research UI acceptance; current `acceptance.test.ts` and browser suite | Tasks 18, 20: actual rows/edges, nine domains, fork comparison, history navigation and negative credential tests |
| Release Research UI checks cannot require host `dist` or unauthenticated external matrix setup | `tests/compose/test_research_ui_wiring.py` local-DIST guard and external matrix GET | Tasks 19–21: authenticated test-owned image stack, real V2 matrix summary, missing host output irrelevant |
| Small-statistical inference uses distinct numeric seed blocks and predeclared comparisons, no positive effect gate | Original Request nulls; cultural/path-dependence comparison contracts | Task 22 zero-difference and missing-pair tests, five fixed seeds, pointwise qualified intervals |
| V3 completion qualification does not own deferred flags or expand measured scale limits | `.ai-factory/ROADMAP.md` M6/M7; `docs/long-horizon-scalability.md` Verified Envelope | Tasks 22–23 completion matrix lists unowned slots, verified 10k and incomplete 100k separately |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Independent mechanism lane, valid bounded schedule | v55 config + recipe + normal journal + applied/rejected override receipts | Controlled mechanism checks; no forced research conclusion | Tasks 4, 6–12 |
| Independent research cases 01–28, no schedule/arbiter | Same setup identities; ordinary cognition + sources | Unassisted detected/not-detected/unknown outcomes; null allowed | Tasks 4, 22 |
| Grouped cases 29–30, eligible prefix, deterministic fake, mechanism or research lane | BN design/prefix controls/assigned treatment/parent/child/outcome artifacts + actual capture | `grouped_intervention`, not unassisted; independent ordinary-command children; unchanged parent | Tasks 13, 22 |
| Grouped case sent through independent executor or recorded/live provider | No execution/publication | Fail-closed preflight, no fabricated children | Tasks 4, 13, 16 |
| New learner pack on v55 with exact prerequisite specs | Creation policy identity and empty owner state | Fresh learning modes only; later learning through ordinary sources | Tasks 2–4 |
| New learner pack on older schema / missing prerequisites | No admitted invalid configuration | Reject; old packs unchanged | Task 3 |
| Founder-mode contrast with a shared newborn profile | Actual founder and first-entrant mode vectors; declared `founder_roster` scope | Direct estimates use fixed founders' eligible lifetime windows; entrants are not falsely labeled disabled | Tasks 2–3, 12, 22 |
| Different initializer packs across arms | Per-arm creation/profile identities and enumerated mode differences | Explicit `initializer_profile` / `composite_profile` treatment, not isolated single-mode effect | Tasks 2–3, 22 |
| Capture off/on/failed/quota-exhausted | None or immutable bounded source evidence; science unaffected | Disabled/complete/partial/unavailable distinct; missing required evidence blocks acceptance | Tasks 4–5, 14 |
| Complete no phenomenon versus incomplete search | Empty result with complete window versus censored source | `not_detected` versus `unknown`; only complete evidence can prove absence/loss | Tasks 5, 8, 12, 22 |
| Valid addressed/visible learning versus no-contact or foreign-owner source | Fresh owner trace/revision or no uptake | No copying/history download; provenance retained | Tasks 6–12, 14 |
| Deterministic-fake objective replay versus captured subjective lineage | Objective journal versus independent owner capture | Separate qualified parity receipts; no invented subjective fold | Task 15 |
| Fully finalized terminal research read versus pending/aborted-incomplete boundary | Detached finished-stage projection or explicit refusal | Exact terminal H can be inspected without weakening checkpoint guards; unavailable probe does not alter science | Tasks 4, 13, 15 |
| Independent recording available versus miss/schema/component drift | Verified recording references/usage or safe failure | Offline exact reproduction or fail closed, no live fallback | Task 16 |
| Inspection/debug credentials valid/absent/revoked; capture complete/partial | No client writer or truth backchannel | Existing auth/availability and snapshot-pinned reads; no private-data leaks | Tasks 18, 20 |
| All required regression/browser/DB gates executed versus missing prerequisite | Per-gate counts/results | Certified only if required gates pass; missing gate stays unexecuted | Tasks 20–23 |
| Valid revision plus clean/digest assertion versus missing/conflicting source metadata | Same explicit source identity across archive/grouped/report/image producer | Valid no-Git container execution or preflight rejection; never invented source cleanliness | Tasks 5, 19–20, 22 |
| Completed 10k versus incomplete 100k stress attempt | Actual counts/boundaries/budgets, immutable sources | Qualified measured-through claim only; never universal capacity | Task 22 |

## Architecture and Decisions

1. **Separate registry and outer composition.** New `experiments.civilization_benchmark_*` modules own immutable specs, recipes, evidence checks and report composition; `research_runner` owns SQL/filesystem/provider adapters and CLI. Simulation never imports benchmark/analysis/API/persistence. No private world imports, new HTTP routes or client authority.
2. **Thirty small cases, two lanes.** Each requested scenario has a stable ID and controlled valid-channel mechanism lane. Independent cases 01–28 have autonomous research lanes; grouped cases 29–30 have explicitly intervention-based research lanes retaining the predeclared prefix controls/treatments. Shared worlds reduce duplication, not requirement coverage. All results keep execution, invariants, mechanism coverage, measurement, phenomenon, publication and comparison separate.
3. **No scripted knowledge or institutional state.** Physical setup, laws, resources and bounded command interventions are declared experiments. No preloaded parent memories, global vocabulary, technology/office registries or objective legitimacy. Policy-level synthetic positive detector tests are labeled and never substituted for real trajectory evidence.
4. **Explicit learner profile.** Add one v55-only versioned, opt-in, empty-content species pack for descendant modes; keep all old packs unchanged. This is the only deliberate new scientific configuration policy identifier; defaults and capability ownership stay unchanged.
5. **Finite predeclared budgets.** Smoke: seed 23, 96 ticks, four founders, interval 8/generation 16/lifespan 24/cap 12. Research: seeds 11/23/37/53/71, 192 ticks, same base policy. Case 30 declares faster cohort labels (interval 2/generation 4) and F=12. Visual: seed 23, 160 ticks, six founders/cap 16. Set generation cap/threshold to none, extinction stop false and custom stop criteria empty; ordinary runtime-terminal stopping remains disabled. Full lanes must actually reach H. Profiles are fixtures, not capacity claims. No seed hunting or posthoc horizon extension.
6. **Reuse exact scientific contracts.** Existing cultural families and BN seven-domain estimators supply measurements. New strict benchmark run/suite sibling schemas do not alter runner/result/archive logical schemas or catalog family counts. Existing root spec/mode validators remain authoritative.
7. **Replay guarantees stay distinct.** Objective creation/death/genealogy/physical record replay, deterministic full rerun, process-local supported subjective fork continuation and captured lineage rebuild are separately proven. Full durable subjective restart and recorded/live LLM forks are not promised.
8. **Source-backed release acceptance.** One bounded controlled visual history covers the eight requested displays. Thirty independent small cases remain the scientific suite. Source-backed positive visual markers do not force an emergence finding; if unavailable, that positive visual acceptance is blocked rather than fabricated.
9. **Zero-install for users, not build machines.** The image builds Godot Web and the Svelte SPA internally; runtime is non-root, without editor/Node tooling. End users pull/run and browse; CI may use pinned Godot/pnpm/Playwright. `/research/` mounts before Godot `/`; debug/capture remain opt-in.
10. **Qualified completion, not slogan.** Full suite certification needs executed required gates, not skips. Measured scale and deferred ownership remain explicit. No M6/M7 milestone is closed by this plan itself.
11. **Scoped effects and source attestations.** Per-agent mode contrasts are founder-roster-scoped with unchanged entrant packs; initializer-pack differences are composite treatments. Explicit source revision plus exactly one verified clean/digest assertion accompanies every run, including image-owned producers without Git. Image-only UI checks use authenticated real matrix sources and no host frontend output.

### Unchanged compatibility pins

Default runner/result v4/v2; latest feature runner v55; commands 43; observer semantic types 73; metric families 136; feature-selected replay-v22/codec-v20; Alembic 0017; `/v1`; `observer-protocol-v1`; `prepare_parallel=False`. V2 benchmark count remains 16. Unowned `institutional_economy` and `multi_hop_testimony_tracking` continue failing closed.

## Scenario Coverage

All IDs below have prefix `v3-bench-`. Phase tables define required sources, controlled checks, autonomous outcomes and controls.

| Request # | ID suffix | Detailed task |
| --- | --- | --- |
| 1 | `01-blank-slate` | 6 |
| 2 | `02-dependent-care` | 6 |
| 3 | `03-intergenerational-teaching` | 6 |
| 4 | `04-cultural-mutation` | 6 |
| 5 | `05-memory-layers` | 7 |
| 6 | `06-record-after-witnesses` | 7 |
| 7 | `07-false-record` | 7 |
| 8 | `08-technology-discovery` | 8 |
| 9 | `09-technology-diffusion` | 8 |
| 10 | `10-technology-loss` | 8 |
| 11 | `11-technology-rediscovery` | 8 |
| 12 | `12-inheritance-practices` | 9 |
| 13 | `13-long-term-commitments` | 9 |
| 14 | `14-subjective-barter` | 9 |
| 15 | `15-candidate-exchange-medium` | 9 |
| 16 | `16-collective-project` | 10 |
| 17 | `17-public-good-patterns` | 10 |
| 18 | `18-regional-migration` | 10 |
| 19 | `19-isolated-divergence` | 10 |
| 20 | `20-recontact-exchange` | 10 |
| 21 | `21-vocabulary-divergence` | 11 |
| 22 | `22-generational-semantic-drift` | 11 |
| 23 | `23-cross-cultural-mistranslation` | 11 |
| 24 | `24-narrative-after-witnesses` | 12 |
| 25 | `25-persistent-role` | 12 |
| 26 | `26-office-succession` | 12 |
| 27 | `27-institutional-persistence` | 12 |
| 28 | `28-institutional-decay` | 12 |
| 29 | `29-founder-contingency` | 13 |
| 30 | `30-multigeneration-fork` | 13 |

### Completion criteria traceability

| Requested completion criterion | Required evidence/tasks |
| --- | --- |
| V1/V2 invariants remain valid | 14, 21: full regression collections, not only named gates |
| Changing population; coexisting/replacing generations | 2, 6, 15: actual admissions/deaths/cohort boundaries and replay |
| New agents learn culture, not copied memories | 3–4, 6–7, 14: measured blank state and later valid sources |
| Knowledge persists beyond lifetimes and can be lost | 7–8: witness extinction, physical record reading, complete holder/archive loss |
| Technology emerges/spreads/mutates/disappears | 8: experimentation, actual practical-knowledge acquisition/mutation/recombination parentage and lifecycle evidence; cultural-trait mutation alone is insufficient; observed nulls allowed |
| Cultural traits measured across generations | 6, 11–12, 22: retained cultural inventories and existing families/seed-block estimands |
| Isolated populations can diverge and re-contact without synchronization | 10–11: exposure separation, ordinary journeys and fresh recipient uptake |
| Persistent social roles/institutions observed without scripted existence | 12, 22: owner-local policies, independent evidence, autonomous runs and null-capable detection |
| Institutions survive occupant death, transform or disappear | 12, 15: role identity, succession, memory/decay and complete/censored windows |
| Narratives may outlive witnesses | 7, 12: actual extinction and later sourced owner narrative |
| Small interventions compared through multi-generation forks | 13, 15, 22: common prefix, children, no-op twin, predeclared seed blocks |
| Godot observes without affecting history | 14, 17, 20: coordinate/read noninterference and actual Web replay |
| Research UI analyzes lineage and long-term change | 18, 20: nine populated domains, qualified sources, real history/fork navigation |
| Normal deployment is zero-install with respect to Godot | 19–20: image-only runtime/browser, no host export/build |
| Long-running reproducibility and scientific auditability | 5, 15–16, 22–23: immutable manifests, recording/replay, real scale envelopes and complete source references |

## Phase Index

1. [Phase 1: Contracts and composition](v3-44-phase-01-contracts.md) — Tasks 1–3
2. [Phase 2: Execution and artifacts](v3-44-phase-02-execution.md) — Tasks 4–5
3. [Phase 3: Population and memory](v3-44-phase-03-population-and-memory.md) — Tasks 6–7
4. [Phase 4: Technology and exchange](v3-44-phase-04-technology-and-exchange.md) — Tasks 8–9
5. [Phase 5: Regions and language](v3-44-phase-05-regions-and-language.md) — Tasks 10–11
6. [Phase 6: Institutions and forks](v3-44-phase-06-institutions-and-forks.md) — Tasks 12–13
7. [Phase 7: Invariants and replay](v3-44-phase-07-invariants-and-replay.md) — Tasks 14–16
8. [Phase 8: Presentation and release](v3-44-phase-08-presentation-and-release.md) — Tasks 17–20
9. [Phase 9: Qualification](v3-44-phase-09-qualification.md) — Tasks 21–23

## Cross-Phase Dependencies

- Tasks 1→2→3 establish registry, valid atomic configurations and empty descendant modes. Task 4 depends on all three; Task 5 depends on 4.
- Tasks 6–7 depend on 1–5. Task 7 additionally reuses Task 6's witness/entry probes.
- Task 8 depends on 6–7 for firsthand acquisition/record loss; Task 9 depends on 4–5 and actual death/learning probes from 6–8.
- Task 10 depends on 6–9 for actual skill/knowledge/physical exchanges; Task 11 depends on 10 and the new profile (3).
- Task 12 depends on 7 and 10–11; Task 13 depends on the execution/artifact framework (4–5) and source projections proven through 12.
- Task 14 depends on implemented cases 6–13; Task 15 depends on 14 and the real artifact sources; Task 16 depends on 4–5 and 15's comparison oracle.
- Task 17 depends on 6–16; Task 18 depends on 5, 12–16. Task 19 uses existing client build inputs and can begin after 1, but is not complete until integration tests verify the package. Task 20 requires 17–19 and production artifact publishers.
- Task 21 requires completed implementation/client phases; Task 22 requires 21 and retained real gate evidence; Task 23 requires 22. Execute numeric order by default; no task may be marked complete before its dependencies' required evidence exists.

## Tasks

### Phase 1
- [x] Task 1: Define the executable thirty-scenario registry ([details](v3-44-phase-01-contracts.md#task-1-define-the-executable-thirty-scenario-registry))
- [x] Task 2: Build bounded and comparable v55 benchmark worlds ([details](v3-44-phase-01-contracts.md#task-2-build-bounded-and-comparable-v55-benchmark-worlds)) (depends on 1)
- [x] Task 3: Add an explicit blank civilization learner profile ([details](v3-44-phase-01-contracts.md#task-3-add-an-explicit-blank-civilization-learner-profile)) (depends on 1, 2)

### Phase 2
- [x] Task 4: Execute independent lanes with real owner and admission probes ([details](v3-44-phase-02-execution.md#task-4-execute-independent-lanes-with-real-owner-and-admission-probes)) (depends on 1, 2, 3)
- [x] Task 5: Publish reproducible sibling reports and a bounded CLI ([details](v3-44-phase-02-execution.md#task-5-publish-reproducible-sibling-reports-and-a-bounded-cli)) (depends on 4)

### Phase 3
- [x] Task 6: Exercise blank entry, care, teaching and cultural mutation ([details](v3-44-phase-03-population-and-memory.md#task-6-exercise-blank-entry-care-teaching-and-cultural-mutation)) (depends on 1, 2, 3, 4, 5)
- [x] Task 7: Exercise memory layers and true or false surviving records ([details](v3-44-phase-03-population-and-memory.md#task-7-exercise-memory-layers-and-true-or-false-surviving-records)) (depends on 6)

### Phase 4
- [x] Task 8: Exercise discovery, diffusion, loss and independent rediscovery ([details](v3-44-phase-04-technology-and-exchange.md#task-8-exercise-discovery-diffusion-loss-and-independent-rediscovery)) (depends on 6, 7)
- [x] Task 9: Exercise inheritance claims, delayed commitments, barter and exchange functions ([details](v3-44-phase-04-technology-and-exchange.md#task-9-exercise-inheritance-claims-delayed-commitments-barter-and-exchange-functions)) (depends on 4, 5, 6, 7, 8)

### Phase 5
- [x] Task 10: Exercise collective work, public goods, migration and re-contact ([details](v3-44-phase-05-regions-and-language.md#task-10-exercise-collective-work-public-goods-migration-and-re-contact)) (depends on 6, 7, 8, 9)
- [x] Task 11: Exercise vocabulary divergence, semantic drift and mistranslation ([details](v3-44-phase-05-regions-and-language.md#task-11-exercise-vocabulary-divergence-semantic-drift-and-mistranslation)) (depends on 3, 10)

### Phase 6
- [x] Task 12: Exercise narrative survival, roles, succession, persistence and decay ([details](v3-44-phase-06-institutions-and-forks.md#task-12-exercise-narrative-survival-roles-succession-persistence-and-decay)) (depends on 7, 10, 11)
- [x] Task 13: Execute founder perturbations and multigeneration grouped forks ([details](v3-44-phase-06-institutions-and-forks.md#task-13-execute-founder-perturbations-and-multigeneration-grouped-forks)) (depends on 4, 5, 12)

### Phase 7
- [x] Task 14: Gate all generational scientific invariants ([details](v3-44-phase-07-invariants-and-replay.md#task-14-gate-all-generational-scientific-invariants)) (depends on 6, 7, 8, 9, 10, 11, 12, 13)
- [x] Task 15: Qualify objective replay and captured subjective lineage separately ([details](v3-44-phase-07-invariants-and-replay.md#task-15-qualify-objective-replay-and-captured-subjective-lineage-separately)) (depends on 14)
- [x] Task 16: Replay recorded LLM cognition in a real independent generational run ([details](v3-44-phase-07-invariants-and-replay.md#task-16-replay-recorded-llm-cognition-in-a-real-independent-generational-run)) (depends on 4, 5, 15)

### Phase 8
- [x] Task 17: Replay one real multi-generation visual fixture in Godot ([details](v3-44-phase-08-presentation-and-release.md#task-17-replay-one-real-multi-generation-visual-fixture-in-godot)) (depends on 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)
- [x] Task 18: Inspect populated evidence and fork history in the Research UI ([details](v3-44-phase-08-presentation-and-release.md#task-18-inspect-populated-evidence-and-fork-history-in-the-research-ui)) (depends on 5, 12, 13, 14, 15, 16)
- [x] Task 19: Ship both Web clients in the normal release image ([details](v3-44-phase-08-presentation-and-release.md#task-19-ship-both-web-clients-in-the-normal-release-image)) (depends on 1)
- [x] Task 20: Gate release on authenticated real-browser benchmark acceptance ([details](v3-44-phase-08-presentation-and-release.md#task-20-gate-release-on-authenticated-real-browser-benchmark-acceptance)) (depends on 17, 18, 19)

### Phase 9
- [x] Task 21: Execute all V1 and V2 regression lanes without silent skips ([details](v3-44-phase-09-qualification.md#task-21-execute-all-v1-and-v2-regression-lanes-without-silent-skips)) (depends on 14, 15, 16, 17, 18, 19, 20)
- [x] Task 22: Run deterministic smoke and predeclared small-statistical research qualification ([details](v3-44-phase-09-qualification.md#task-22-run-deterministic-smoke-and-predeclared-small-statistical-research-qualification)) (depends on 21)
- [x] Task 23: Document the qualified V3 completion contract and perform final verification ([details](v3-44-phase-09-qualification.md#task-23-document-the-qualified-v3-completion-contract-and-perform-final-verification)) (depends on 22)

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1–3: `feat(experiments): define V3 benchmark contracts and blank learner policy`
2. After Tasks 4–5: `feat(research): execute and verify generational benchmark artifacts`
3. After Tasks 6–7: `test(v3): cover population learning and historical memory channels`
4. After Tasks 8–9: `test(v3): cover technology continuity and subjective exchange`
5. After Tasks 10–11: `test(v3): cover coordination migration and language divergence`
6. After Tasks 12–13: `test(v3): cover subjective institutions and grouped historical forks`
7. After Tasks 14–16: `test(v3): enforce generational boundaries and replay qualification`
8. After Tasks 17–20: `feat(release): qualify populated generational clients in one image`
9. After Tasks 21–23: `test(v3): qualify end-to-end generational civilization benchmarks`

## Blocking Conditions and Non-Goals

No unresolved architecture question blocks starting Task 1. Actual trajectories, positive visual marker coverage, performance and external environment availability must be measured, not invented. The plan commits the procedure and the failure status, not future success.

- Full qualification requires disposable PostgreSQL/pgvector, the pinned Godot suite, a built release image, real browser driver and explicit time/disk/RAM budgets. Missing prerequisites leave the corresponding gate unexecuted and block a full certification claim.
- If valid current policies cannot produce a required controlled positive visual trajectory within the fixed budget, report that acceptance blocker. Do not seed a ledger, create an objective institution, search for a favorable seed or weaken null-capable research checks. A new behavior policy beyond the explicit learner profile requires separate scoped planning.
- No new SQL migration, world command/event, observer semantic type, API version, metric family, capability slot, global truth/technique/culture/office registry or distributed infrastructure.
- No durable subjective resume, adaptive/nested forks, recorded/live LLM fork continuation, forced emergence, automatic debt/inheritance law or deletion of historical provenance.
- Leave preexisting untracked `clients/godot-observer/scripts/net/research_focus.gd.uid`, `clients/godot-observer/scripts/ui/research_focus_panel.gd.uid` and `clients/godot-observer/tests/test_research_focus.gd.uid` untouched.
- Active V3-43 work is treated as completed contextual evidence only where documented: its index reports Tasks 1–21 complete with a browser gate unexecuted. Do not preload its phase history or infer browser certification.

## Approved Refinements

Approved during `$aif-improve` on 2026-10-27. Original Request bytes, all 23 task IDs, task states, phase links and commit groups are preserved; no new task or dependency is introduced.

1. Tasks 2, 13, 22: explicitly disable competing generation/extinction/threshold/criteria stops, synchronize grouped horizons/windows, and require full H coverage rather than any nonfailure result.
2. Tasks 2–3, 12, 22: verify actual founder/newborn mode vectors, scope founder-only effects to founder lifetime windows, and label changed initializer packs as composite treatments.
3. Tasks 4, 13, 15: define a terminal-safe detached research projection and isolated observation lifecycle; preserve fork/finalization guards and science under probe failure.
4. Task 16: exercise real archival RECORD/REPLAY composition through normal provider/store construction with truthful reproducibility modes, positive usage receipts and the existing untracked-custom-provider rejection.
5. Tasks 5, 19–20, 22: define revision plus clean/digest source arguments, verified image labels and no-Git producer forwarding; update commands and failure tests without inventing source cleanliness.
6. Tasks 19–21: refactor release Research UI wiring tests to the authenticated image-owned stack, produce the real V2 matrix summary and eliminate the host frontend-build prerequisite.

## Definition of Done

- All 23 indexed tasks have verified completion evidence; only this index holds task progress checkboxes.
- All 30 requested scenarios have individual executable recipes, mechanism coverage, source-preserving measurements and honest null/unavailable states.
- All thirteen generational invariants and seven replay requirements have explicit checks with applicable source kinds, including nonvacuous independent recorded cognition replay.
- Required V1/V2/default/integration/Compose/Godot/Research UI regressions actually execute and pass; no required skipped lane is silently certified.
- Both release clients inspect source-backed populated multi-generation history, the eight visual markers and nine Research UI domains, without mutating science or requiring host export/build tools.
- Five predeclared numeric-seed research blocks and deterministic twins have reproducible retained artifacts and qualified inference; no emergence/effect direction is required.
- Long-horizon attempts preserve provenance and measured/incomplete distinctions; supported claims stop at verified workloads.
- Documentation and final verification match actual source/release artifacts. Deferred flags and roadmap ownership remain explicit and unchanged.
