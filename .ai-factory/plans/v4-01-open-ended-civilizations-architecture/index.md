<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-01 Architecture Evolution for Open-Ended Civilizations

Mode: ultra
Branch: main (remain on current branch; `git.create_branches: false`)
Created: 2026-10-30
Plan identifier: `v4-01-open-ended-civilizations-architecture`
Status: planning complete; 17 tasks across 7 phases. No task is implemented by
this planning invocation.

## Original Request

v4-01 architecture evolution for open-ended civilizations

Plan naming requirement:

The canonical plan_file_stem / ultra bundle directory MUST begin with `v4-`.

Suggested stem:

v4-01-open-ended-civilizations-architecture

Inspect the fully completed V3 repository.

Design V4 as an additive architectural evolution supporting:

- large organizations
- formalized social rules
- legal/dispute systems
- inter-society diplomacy
- organized conflict
- infrastructure networks
- supply chains
- market-like institutions
- credit
- science
- epidemics
- ecological feedback
- disasters
- societal resilience/collapse
- hundreds or potentially thousands of agents
- multi-scale Godot visualization

Preserve all V1–V3 invariants:

- WorldEngine owns objective physics.
- WorldEvents remain immutable.
- subjective state stays separate from objective state.
- Godot is read-only.
- researcher analytics are not automatically agent knowledge.
- replay/forking remains deterministic where configured.
- organizations/institutions/civilizations must not become magical actors outside agent-mediated processes.

Define:

- new bounded contexts
- schema/version evolution
- event versioning
- Observer Protocol versioning
- compatibility strategy
- feature flags
- migration sequence
- V3 regression suite

Do not implement V4 social mechanics yet.

## Settings

- Testing: yes; full strategy. Unit, architecture, integration, Compose/browser,
  Godot, Research UI, benchmark regression, and static gates, with coverage
  enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN incomplete evidence, ERROR safe codes. `PALIMPSEST_LOG_LEVEL` controls
  operational verbosity. No private content, payload surrogates, prompts,
  credentials, tokens, DSNs, memories, or embeddings.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 16.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints below are suggestions, not
  authorization to commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-01-open-ended-civilizations-architecture`; the
  ultra bundle directory begins with `v4-`, phase files use the canonical
  `phase-NN-<slug>.md` layout inside it, and `index.md` is the canonical ultra
  entrypoint.
- Research source: no configured `RESEARCH.md` and no marked ultra research
  bundle exists; no external research conclusions are invented.
- Execution: planning only in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (provisional; register via `$aif-roadmap`)"
Rationale: V4-01 establishes the architecture, version, flag, and migration
seams for open-ended civilizations. `.ai-factory/ROADMAP.md` currently ends at
M7; this plan does not edit the roadmap and does not close any milestone.

## Requirements Reconciliation

Authority: repository/project rules constrain all edits; the Original Request
defines scope; completed V3 architecture, codecs, pins, and regression contracts
govern compatibility. V4-01 is explicitly scaffolding-only: it may declare
flags, versions, reservations, context ownership, and gates, but may not
implement a V4 social mechanic.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-01 adds no behavior; all twelve V4 flags are unowned and fail closed | Original Request "Do not implement V4 social mechanics yet"; `src/simulation/runner.py` `from_config` (2085-2138) | Tasks 4-6: encode/decode succeeds, `from_config` raises `capability_unimplemented` with `stage="v4_capability_flags"` |
| `runner-config-v56` is accepted but never the default and never auto-emitted | Original Request "schema/version evolution"; `src/simulation/runner_models.py` (149-209); `src/experiments/matrix_schema.py` (70-320) | Task 5: default stays v4, latest feature stays v55, matrix finalize preserves explicit v56 only |
| v56 wire shape is exactly the v55 keyset plus one `v4_capability_flags` sibling | `src/simulation/runner_serialization.py` `_v55_family_root_keys` (4751), `decode_runner_config` (9129) | Task 5: exact-key, missing-key, extra-key, and legacy-synthesis tests |
| Legacy runner configs v1-v55 decode with V4 flags synthesized off | `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract" | Tasks 1, 5: legacy payload tests and baseline inventory |
| Commands, events, codecs, observer semantic types, metric families, routes, and Alembic head stay at V3 values | `src/world/events.py`; `src/simulation/persistence.py` (112, 139); `src/observer/version.py`; `src/analysis/specifications.py` (53); `src/simulation/compatibility.py` | Tasks 1, 14: baseline inventory and consolidated invariant suite |
| Objective contexts are WorldEngine-owned; subjective contexts are owner-scoped; resilience is detached analysis; clients are presentation-only | `.ai-factory/ARCHITECTURE.md` "Key Principles"; Original Request invariants | Tasks 2-3, 14: authority validation and AST/import checks |
| Organizations, institutions, markets, polities, and civilizations are never actors and have no global registry | Original Request invariant; `.ai-factory/ARCHITECTURE.md` anti-patterns | Tasks 3, 14: magic-actor token scan and analysis-only authority rules |
| Observer protocol stays v1; `/version` gains only additive capability fields; v2 is reserved but not served | `src/observer/version.py`; `src/observer/contracts.py`; `docs/research-api.md` versioning policy | Task 9: manifest validation, supported-protocol tuple, 73-type pin |
| The V2/V3 `/version` non-goal is deliberately refined: V4-01 advertises protocol and capability metadata, never capability-flag values | `docs/research-api.md` (52); `tests/unit/test_godot_protocol_mirror.py` | Task 9: the mirror test forbids V3/V4 flag payloads while allowing metadata; Task 16 updates the doc |
| Multi-scale is presentation-only in V4-01; no server-side aggregation contract is added | Original Request "multi-scale Godot visualization"; `docs/observer.md` read-only split | Tasks 10-12: scale contracts, Python/GDScript parity, no route change |
| Scale is deterministic and benchmark-measured; no capacity claim is made | Original Request "hundreds or potentially thousands of agents"; `docs/long-horizon-scalability.md` | Tasks 10-11: pure partition properties, opt-in unit lane, no artifact |
| Migrations stay at `0017`; future stages require proven triggers | `docs/persistence.md`; `src/simulation/compatibility.py` `ALEMBIC_HEAD_REVISION`; `tests/unit/test_alembic_head_pin.py` | Task 8: sequence validation and no-unplanned-file test |
| Four objective contexts reserve future write pairs; the other nine reuse existing events | `src/world/events.py`; `src/simulation/persistence.py` | Task 7: reservation table, coverage, and current-maxima test |
| Required gates must execute; a skip is not a pass | `tests/compose/acceptance.py`; Original Request "V3 regression suite" | Task 15: required-mode Compose lane and explicit skip accounting |
| The existing v56-forbidden pin and the documented "no v56" statement are deliberately superseded, not silently reverted | `tests/architecture/test_path_dependence_boundaries.py` (89-92); `docs/configuration.md` (305-309) | Tasks 5, 16: v57 guard replaces the v56 guard; configuration doc corrected |
| The journal V22 decoder gap must be repaired before reserving V23 | `src/simulation/journal.py` (69, 2521-2549); `src/persistence/readers.py` (138) | Task 1: V22 persistence and ORM-shaped round-trip tests |
| No new top-level Python package is introduced; contexts map onto existing bounded packages | `tests/architecture/boundary_checker.py` `BOUNDED_PACKAGES`; `pyproject.toml` import-linter | Tasks 3, 14: owner-package validation and 13-package assertion |
| Deferred V3 flags and capabilities remain deferred | `.ai-factory/ROADMAP.md` M6/M7; `.ai-factory/ARCHITECTURE.md` capability ownership | Task 17: final claim audit |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| V4 flags all off, schema v4 | Default V3-equivalent config | Default write stays v4; no V4 code path | Tasks 5-6, 15 |
| V4 flags all off, explicit schema v56 | Accepted v56 document with `v4_capability_flags` all false | Encode/decode round-trip; matrix finalize preserves v56; no behavior | Task 5 |
| Any V4 flag enabled, schema v56 | Config accepted and serializable | `SimulationRunner.from_config` fails closed with `capability_unimplemented`, stage `v4_capability_flags` | Tasks 5-6 |
| Any V4 flag enabled, schema < v56 | No admitted config | Construction fails with `v4_capability_requires_v56` | Task 5 |
| Legacy payload v1-v55 | No V4 key present | Decodes with `V4CapabilityFlags()` all false | Task 5 |
| v56 payload missing or extra `v4_capability_flags` key | No admitted payload | Strict exact-key failure with the existing serialization code | Task 5 |
| Context registry mutation: duplicate flag, unknown owner, cycle, analysis context owning `world` or carrying a flag | No valid registry | `ValueError` with the documented `v4_context_*` code | Task 3 |
| Write-pair mutation: duplicate/gap/unknown/analysis context | No valid reservation table | `ValueError` with the documented `v4_pair_*` code | Task 7 |
| Migration mutation: reorder, duplicate, unknown flag, post-migration `False` | No valid sequence | `ValueError` with the documented `v4_migration_*` code | Task 8 |
| `/version` older or newer capability payload | v1 frames unchanged | Additive fields parsed by both clients; unknown names shown as counts | Tasks 9, 12-13 |
| Required Compose/browser lane with a missing prerequisite | No green gate | Fail closed; no skip counted as a pass | Task 15 |
| Reserved write pair or migration stage present in V4-01 | Not allowed | Invariant suite fails; no partial implementation | Tasks 7-8, 14 |

## Architecture and Decisions

1. **Scaffolding only.** V4-01 owns no V4 behavior. It declares the closed
   vocabulary, version acceptance, reservations, context map, scale contract,
   and presentation negotiation. Every mechanic is deferred to V4-02+.
2. **No new top-level packages.** V4 contexts map onto the existing bounded
   packages: objective physics in `world`, orchestration/contracts in
   `simulation`, owner-scoped cognition in `agents.cognition`, detached
   measurement in `analysis`, composition in `experiments`/`research_runner`,
   and read-only presentation in `observer`/clients. This preserves the
   import-linter graph and prevents a "civilization" mega-package.
3. **Authority decides ownership.** `OBJECTIVE_WORLD` contexts must list
   `world`; `OWNER_SCOPED` contexts never claim world authority;
   `DETACHED_ANALYSIS` contexts own only `analysis`; `PRESENTATION_ONLY` never
   appears in simulation semantics.
4. **Closed, unowned flags.** Twelve flags are declared on
   `runner-config-v56`; the owned set is empty. Enabling any flag fails closed
   at runtime construction, so a later plan must explicitly claim ownership.
5. **Accepted but not emitted.** v56 is accepted for explicit scaffolding
   identity. Default writes stay v4; latest feature runner stays v55; feature
   selection never emits v56 on its own.
6. **Event expansion is minimized.** Only `infrastructure_networks`,
   `epidemics`, `ecological_feedback`, and `disasters` reserve new write pairs
   (events 23-26, codecs v21-v24). Organizations, rules, disputes, diplomacy,
   conflict, supply chains, markets/credit, science, and resilience must reuse
   existing events.
7. **Reservations are not implementations.** Reserved numbers carry no
   semantics; later plans must still prove effect-complete payloads, replay,
   and migration need.
8. **Migration is evidence-gated.** No migration in V4-01. The ordered stages
   name the trigger, prerequisites, owner, and authority impact; head stays
   `0017`.
9. **Observer evolution is additive.** Protocol v1 remains the only served
   protocol. `/version` advertises supported protocols, layout, and
   advertised/reserved capabilities. v2 is reserved; no semantic type or frame
   changes. This deliberately refines the V2/V3 `/version` non-goal; no flag
   values or configuration payloads are exposed.
10. **Multi-scale is presentation-only.** A shared Python/GDScript level
    vocabulary and row caps define agent/cohort/settlement/region/civilization
    views. No server aggregation, no engine semantics, no client authority.
11. **Scale is deterministic.** Partitioning is a pure function of a versioned
    namespace and agent id, order-preserving, and free of `hash()`/global state.
    Budgets are declarative; V4-01 adds no runtime enforcement or capacity
    claim.
12. **No magical actors.** Organizations, institutions, markets, polities, and
    civilizations are not entities with authority. They are owner-scoped
    beliefs plus ordinary agent-mediated commands, records, and physical facts.
13. **V3 is the baseline.** The V3 completion pins are frozen in an executable
    inventory; the V22 journal decode gap is repaired so V4 reservations start
    from a correct V3 decoder.
14. **Qualification is explicit.** Required lanes must execute; skips are
    reported, not certified. Documentation is part of the deliverable, and
    contradictory statements are superseded openly.

### Context map

| Context | Flag | Authority | Owning packages | Prerequisites | Existing mechanism | Event strategy |
| --- | --- | --- | --- | --- | --- | --- |
| `organizations` | `organizations` | owner-scoped | `agents.cognition`, `social`, `simulation` | — | collective projects, public goods, mentorship | reuse |
| `formal_rules` | `formal_rules` | owner-scoped | `agents.cognition`, `simulation` | — | norms, conventions, durable records | reuse |
| `legal_disputes` | `legal_disputes` | owner-scoped | `agents.cognition`, `simulation` | `formal_rules` | mediation | reuse |
| `diplomacy` | `diplomacy` | owner-scoped | `agents.cognition`, `social`, `simulation` | `organizations` | contact, migration, commitments | reuse |
| `organized_conflict` | `organized_conflict` | objective-world | `world`, `simulation`, `agents.cognition` | `diplomacy` | physical harm/attack commands | reuse |
| `infrastructure_networks` | `infrastructure_networks` | objective-world | `world`, `simulation` | — | new physical network graph | reserve 23 / `v21` |
| `supply_chains` | `supply_chains` | objective-world | `world`, `simulation` | `infrastructure_networks` | production, storage, transport | reuse |
| `markets_credit` | `markets_credit` | owner-scoped | `agents.cognition`, `simulation` | `supply_chains`, `organizations` | exchange profile, commitments | reuse |
| `science` | `science` | owner-scoped | `agents.cognition`, `simulation` | `formal_rules` | experimentation, practical knowledge, repositories | reuse |
| `epidemics` | `epidemics` | objective-world | `world`, `simulation`, `agents.cognition` | `infrastructure_networks` | new host/transmission state | reserve 24 / `v22` |
| `ecological_feedback` | `ecological_feedback` | objective-world | `world`, `simulation` | `supply_chains` | resource regeneration/depletion | reserve 25 / `v23` |
| `disasters` | `disasters` | objective-world | `world`, `simulation` | `ecological_feedback` | environmental hazards | reserve 26 / `v24` |
| `societal_resilience` | — (analysis-only) | detached-analysis | `analysis` | — | new detached classification | reuse |

### Unchanged compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner
range adds `v56` only; events `EVENT_SCHEMA_REPLAY_V22`; codec `v20`; commands
43; observer semantic types 73; metric families 136; Alembic `0017`; `/v1`;
`observer-protocol-v1`; observer layout `observer-layout-v1`; V2 benchmark 16;
V3 benchmark 30; `prepare_parallel=False`. `institutional_economy` and
`multi_hop_testimony_tracking` remain unowned and fail closed.

## Phase Index

1. [Phase 1: Baseline and Context Map](phase-01-baseline-and-context.md) — Tasks 1-3
2. [Phase 2: Capability and Runner Evolution](phase-02-capability-and-runner.md) — Tasks 4-6
3. [Phase 3: Wire and Persistence Evolution](phase-03-wire-and-persistence.md) — Tasks 7-8
4. [Phase 4: Observer Protocol and Scale Contracts](phase-04-observer-and-scale.md) — Tasks 9-11
5. [Phase 5: Client Scaffolding](phase-05-client-scaffolding.md) — Tasks 12-13
6. [Phase 6: Invariants and Regression](phase-06-invariants-and-regression.md) — Tasks 14-15
7. [Phase 7: Documentation and Verification](phase-07-documentation-and-verification.md) — Tasks 16-17

## Cross-Phase Dependencies

- Task 2 depends on Task 1: the decision record must describe the repaired and
  pinned V3 baseline.
- Task 3 depends on Task 2: the registry must match the documented context map.
- Task 4 depends on Tasks 2-3: flag names come from the registry decisions.
- Task 5 depends on Task 4: v56 carries the V4 flag object.
- Task 6 depends on Tasks 4-5: profiles and gates need the flag vocabulary and
  the accepted schema.
- Task 7 depends on Tasks 3 and 5: reservations are keyed by context and target
  the V3 maximum after v56 is accepted.
- Task 8 depends on Tasks 3 and 7: migration stages reference contexts, flags,
  and the reserved order.
- Task 9 depends on Tasks 2-3: capability names must align with the context map
  without becoming simulation semantics.
- Task 10 depends on Tasks 3 and 7: scale partitions are execution-contract
  metadata for the future objective contexts.
- Task 11 depends on Task 10: the measurement lane exercises the partition
  contract.
- Task 12 depends on Task 9: the Godot side consumes `/version` and defines its
  own presentation scale vocabulary.
- Task 13 depends on Task 9: the SPA consumes the additive `/version` contract.
- Task 14 depends on Tasks 3-13: the invariant suite covers every new module and
  pin.
- Task 15 depends on Task 14: regression runs only after the invariant gate is
  green.
- Task 16 depends on Tasks 3-15: documentation describes the registry,
  reservations, migration sequence, and verified surfaces.
- Task 17 depends on Tasks 15-16: final verification needs regression receipts
  and the final docs.

## Tasks

### Phase 1: Baseline and Context Map
- [x] Task 1: Repair and pin the V3 completion baseline ([details](phase-01-baseline-and-context.md#task-1-repair-and-pin-the-v3-completion-baseline))
- [x] Task 2: Author the V4 architecture decision record ([details](phase-01-baseline-and-context.md#task-2-author-the-v4-architecture-decision-record)) (depends on 1)
- [x] Task 3: Add the machine-readable V4 context registry ([details](phase-01-baseline-and-context.md#task-3-add-the-machine-readable-v4-context-registry)) (depends on 2)

### Phase 2: Capability and Runner Evolution
- [x] Task 4: Add closed V4 capability flags ([details](phase-02-capability-and-runner.md#task-4-add-closed-v4-capability-flags)) (depends on 2, 3)
- [x] Task 5: Accept runner-config-v56 with an exact keyset ([details](phase-02-capability-and-runner.md#task-5-accept-runner-config-v56-with-an-exact-keyset)) (depends on 4)
- [x] Task 6: Add V4 regression profiles and fail-closed gates ([details](phase-02-capability-and-runner.md#task-6-add-v4-regression-profiles-and-fail-closed-gates)) (depends on 4, 5)

### Phase 3: Wire and Persistence Evolution
- [x] Task 7: Reserve future event and codec write pairs ([details](phase-03-wire-and-persistence.md#task-7-reserve-future-event-and-codec-write-pairs)) (depends on 3, 5)
- [x] Task 8: Define the ordered migration sequence ([details](phase-03-wire-and-persistence.md#task-8-define-the-ordered-migration-sequence)) (depends on 3, 7)

### Phase 4: Observer Protocol and Scale Contracts
- [ ] Task 9: Add observer protocol negotiation and capabilities ([details](phase-04-observer-and-scale.md#task-9-add-observer-protocol-negotiation-and-capabilities)) (depends on 2, 3)
- [ ] Task 10: Add deterministic scale contracts ([details](phase-04-observer-and-scale.md#task-10-add-deterministic-scale-contracts)) (depends on 3, 7)
- [ ] Task 11: Add the opt-in V4 scale qualification lane ([details](phase-04-observer-and-scale.md#task-11-add-the-opt-in-v4-scale-qualification-lane)) (depends on 10)

### Phase 5: Client Scaffolding
- [ ] Task 12: Add Godot multi-scale and protocol scaffolding ([details](phase-05-client-scaffolding.md#task-12-add-godot-multi-scale-and-protocol-scaffolding)) (depends on 9)
- [ ] Task 13: Add Research UI version and capability scaffolding ([details](phase-05-client-scaffolding.md#task-13-add-research-ui-version-and-capability-scaffolding)) (depends on 9)

### Phase 6: Invariants and Regression
- [ ] Task 14: Add the V4 architecture invariant suite ([details](phase-06-invariants-and-regression.md#task-14-add-the-v4-architecture-invariant-suite)) (depends on 3-13)
- [ ] Task 15: Execute the V3 regression lanes under V4 flags off ([details](phase-06-invariants-and-regression.md#task-15-execute-the-v3-regression-lanes-under-v4-flags-off)) (depends on 14)

### Phase 7: Documentation and Verification
- [ ] Task 16: Execute the mandatory documentation checkpoint ([details](phase-07-documentation-and-verification.md#task-16-execute-the-mandatory-documentation-checkpoint)) (depends on 3-15)
- [ ] Task 17: Perform final V4-01 verification ([details](phase-07-documentation-and-verification.md#task-17-perform-final-v4-01-verification)) (depends on 15, 16)

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-3: `feat(v4): pin the V3 baseline and define the V4 context map`
2. After Tasks 4-6: `feat(v4): scaffold closed V4 capability flags on runner-config-v56`
3. After Tasks 7-8: `feat(v4): reserve wire versions and order the migration sequence`
4. After Tasks 9-11: `feat(v4): add observer protocol negotiation and scale contracts`
5. After Tasks 12-13: `feat(v4): scaffold multi-scale read-only clients`
6. After Tasks 14-17: `test(v4): enforce V4 scaffolding invariants and V3 regression`

## Blocking Conditions and Non-Goals

- Full qualification requires a disposable PostgreSQL/pgvector instance, the
  pinned Godot 4.7.2 archive, a source-matched release image, a real browser
  driver, and explicit time/disk/RAM budgets. A missing prerequisite leaves the
  lane unexecuted and blocks the claim; it does not become a skip-pass.
- Any need to add a V4 behavior, command, event, semantic type, metric family,
  route, migration, or global registry to make a scaffold test pass is a
  blocking scope violation. Stop and re-plan.
- If repairing the V22 journal decoder requires a schema change or a new event
  version, stop and re-plan; the intended fix is a bound/import correction only.
- If v56 cannot be accepted without weakening legacy decode, stop and re-plan.
- No new top-level Python package, no distributed infrastructure, no vendor LLM
  SDK, no `/v2` HTTP route, no `observer-protocol-v2` serving.
- No behavior ownership: every V4 flag stays unowned in V4-01.
- No capacity claim: the scale lane measures partition mapping only.
- No roadmap edit and no milestone closure. M6 (`multi_hop_testimony_tracking`),
  M7 (`institutional_economy`, deferred kinship handoff), durable subjective
  resume, and recorded/live LLM forks remain exactly as in V3.
- Do not rewrite the attached V3-44 plan or any completed V3 plan. It is
  contextual evidence only.
- Do not delete or weaken existing pins, assertions, caps, or workloads. The
  only intentional pin changes are the v56-forbidden assertion (becomes v57) and
  the additive `/version` key set.

## Definition of Done

- All 17 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- Thirteen V4 contexts are declared: twelve closed capability flags and one
  analysis-only context; none is owned by an implementation.
- `runner-config-v56` is accepted with an exact keyset, never emitted
  automatically, and every V4 flag fails closed at runtime construction.
- Four future write pairs and six migration stages are ordered and validated;
  current event/codec maxima and Alembic `0017` are unchanged.
- Observer v1 remains the only served protocol; `/version` advertises supported
  protocols, layout, and advertised/reserved capabilities additively.
- Scale partitioning is deterministic and measured only through an opt-in lane;
  no capacity claim is made.
- Both clients consume the additive contract and remain read-only.
- The consolidated invariant suite and the complete V3 regression lanes execute
  and pass with V4 flags off; no required skip is certified.
- Documentation covers architecture, versioning, migration, and scale, and the
  stale "no v56" claim is replaced.
- No V4 social mechanic, milestone closure, deferred-flag claim, or capacity
  claim is included.
