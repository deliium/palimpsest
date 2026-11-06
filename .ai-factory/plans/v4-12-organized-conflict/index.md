<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-12 Organized Conflict

Mode: ultra
Branch: main
Created: 2026-11-05

## Original Request

v4-12 organized conflict

Naming requirement:

Use `v4-12-organized-conflict`.

Enable coordinated violent conflict using low-level mechanics.

Do NOT add:

world.at_war = true

Provide primitives enabling:

- coordinated attack
- defense
- movement groups
- resource capture
- structure attack
- route blocking
- retreat
- assistance

Define research analytics that detect sustained organized conflict from event patterns.

Distinguish:

individual violence

from persistent coordinated inter-group conflict.

Agents and societies may interpret the same events differently.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN unresolved references/truncation, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log participant
  or actor identities, plan/episode/version/record ids, target or side tokens,
  frame bodies, observation bodies, prompts, credentials, tokens, DSNs,
  memories, embeddings, utterance bodies, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 25.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-12-organized-conflict`; the ultra bundle directory
  is `.ai-factory/plans/v4-12-organized-conflict/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-12 claims the already-declared `organized_conflict` V4 context on
the accepted `runner-config-v56` seam, adding owner-scoped coordination beliefs,
deterministic low-level command selection, detached event-pattern detection,
four metric families, `organized-conflict-snapshot-v1`, and six read-only
routes without adding a flag, context, runner schema, command, event, observer
semantic type, write pair, `/v2` route, or migration. This plan does not edit or
close the roadmap; `$aif-roadmap` must register V4-12 in M8 and move
`organized_conflict` from unowned to owned.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01 through V4-11 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V2/V3 contact, migration, commitment,
collective-project, mediation, office, institution, collective-decision,
organization, representation, dispute, evidence, diplomacy, and treaty code and
`tests/architecture/test_v4_architecture_invariants.py`,
`test_diplomacy_boundaries.py`, `test_treaty_boundaries.py`,
`test_organization_*`, `test_formal_rule_boundaries`, `test_dispute_boundaries`,
`test_evidence_testimony_boundaries`, and
`test_delegation_representation_boundaries` govern compatibility. V4-12 claims
one already-declared V4 flag and creates no context.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-12 claims the existing `organized_conflict` flag on `runner-config-v56`; no new V4 flag, context, runner schema, root field, or per-agent runner key is added | Original Request "Enable coordinated violent conflict"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/v4_architecture.py` 170-183; `src/simulation/runner_models.py` 305-326 | Task 3 tests; Task 22 pins; Task 26 `v57` absence |
| Activation is `runner-config-v56` + `v4_capability_flags.organized_conflict`, and the declared context prerequisite `diplomacy` must also be enabled | `src/simulation/v4_architecture.py` 170-183; `src/simulation/runner.py` 2278-2345 | Task 3 tests |
| The context remains authority `objective_world` with owner packages `world`, `simulation`, `agents.cognition`; no `world` source edit is required because all physical effects use existing commands | `src/simulation/v4_architecture.py` 170-183; `src/world/actions.py` 52-246, 830-858; `src/world/_rules.py` 3384-3538 | Task 1/9/22 tests |
| No new command, event, write pair, observer semantic type, codec marker, `/v2` route, migration, or `world.at_war` field is added | Original Request "Do NOT add world.at_war"; `.ai-factory/ARCHITECTURE.md` requirements 1-6; `src/simulation/versioning.py`; `src/world/events.py` 2755-2907 | Task 22/26 pins |
| The eight requested primitives are closed operation kinds, not world states: `coordinated_attack`, `defense`, `movement_group`, `resource_capture`, `structure_attack`, `route_blocking`, `retreat`, `assistance` | Original Request examples | Task 1/4/22 tests |
| Each operation may compile only to named existing commands: attack; attack/help/move; move/transport; take/give; oppose_public_good/attack; move/attack/flee/help; flee; help/feed/transport | `src/world/actions.py` 52-246, 830-858; `src/agents/cognition/territorial.py` 1221-1378 | Task 1/9/22 tests |
| Coordination is one owner's belief. A plan, participation claim, interpretation, or contradiction never obligates another owner and never blocks a command | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `src/agents/cognition/diplomacy.py` 1-18 | Task 4/9/22 tests |
| A deterministic `Wait` replacement converts an active plan into one existing command; it cannot override any non-`Wait` selection and cannot construct a new command type | `src/agents/cognition/territorial.py` 1221-1378; `src/agents/cognition/deliberation.py` 1156-1171 | Task 9/23 tests |
| Defense is assistance and counterattack only; there is no damage mitigation, guard, shield, armor, or interception state | `src/world/_rules.py` 1469-1484, 3384-3464; `src/world/models.py` 266-309 | Task 9/22 tests |
| Resource capture is `Take` from ground or corpse custody and voluntary `Give`; no seizure from a living holder and no ownership transfer exist | `src/world/_rules.py` 1285-1335, 1375-1407, 3891-3948; `src/world/events.py` 580-634 | Task 9/11/22 tests |
| Structure attack is `OpposePublicGood` on a completed public-good project, or attacks on occupants; no generic structure-damage command or event exists | `src/world/_collective_projects.py` 528-591, 775-814; `src/world/production.py` 398-422 | Task 9/11/22 tests |
| Route blocking is coordinated presence and attack/flee at route endpoints; routes have no mutable blocked/closed state and never gain one | `src/world/regions.py` 64-99, 227-297; `src/world/_travel.py` 57-72 | Task 9/11/22 tests |
| Movement groups are independent `Move`/`Transport` commands aimed at the same destination within a window; no group-move command exists | `src/world/actions.py` 52-59, 214-226; `src/world/regions.py` 227-297 | Task 9/11/22 tests |
| Retreat is independent `Flee`; assistance is `Help`/`Feed`/`Transport`; neither is a new obligation or a command hierarchy | `src/world/actions.py` 189-246; `src/world/_rules.py` 1469-1484, 4019-4089 | Task 9/11/22 tests |
| Physical effects remain ordinary `WorldEngine` admission; no cognition helper returns, submits, or resolves an `AgentCommand` | `.ai-factory/ARCHITECTURE.md` "anti-patterns"; `src/agents/cognition/organization_agency.py` 1-14 | Task 9/22 tests |
| `WorldEngine`, perception, admission, stop selectors, memory, prompts, observer semantics, and Godot never read the coordination ledger | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" | Task 22/23 tests |
| Peer `ocf_v1` claims, targets, side tokens, and provenance are untrusted; the receiver assigns provenance from delivery | `src/agents/cognition/diplomacy_communication.py` 707-751, 964-1021 | Task 7/8/22 tests |
| `ocf_v1` is 12 fields bounded at 256 characters, carried as at most one relation inside existing `Talk`/`Ask`/`Tell`; malformed or oversize frames are dropped | `src/agents/cognition/diplomacy_communication.py` 84-95, 632-704, 1063-1132 | Task 7/8/22 tests |
| Objective detection consumes committed events only: `Attacked`, `Fled`, `Died`, `Helped`, `Fed`, `Transported`, `Taken`, `Given`, `PublicGoodOpposed`, `Moved`, `JourneyStarted`/`JourneyArrived` | `src/world/events.py` 371-472, 580-634, 744-867, 968-983, 1107-1215, 2728-2752 | Task 11/13/22 tests |
| Owner interpretations never determine objective episode classification; they are joined only after detection for researcher-only alignment | `.ai-factory/ARCHITECTURE.md` Key Principle 1; V4-08/V4-11 alignment precedent | Task 13/14/22 tests |
| `individual_violence` is one attacker against one target with no shared co-participation and no recurrence; organized requires at least two actors on a side; persistent requires two sides, repeated reciprocal windows, and sustained thresholds | Original Request "Distinguish individual violence from persistent coordinated inter-group conflict"; Task 2 locked thresholds | Task 2/13/22 tests |
| Detection policy is locked and deterministic: 6-tick window, 2 side actors, 2 hostile events, 3 windows, 24-tick sustained span, 6 hostile events across 3 ticks, 2 sides with 2 actors each, 2 reciprocal windows | Original Request "detect sustained organized conflict from event patterns" | Task 2/13/22 tests |
| Detached analysis keeps objective rows, owner-token rows, and analytical candidates in three separate types with a hard leakage guard | `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/diplomacy_layers.py` 79-111 | Task 12/22 tests |
| Conflict analysis joins `org-`/`msoc-` identities read-only and never mints, renames, splits, merges, or dissolves them | `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; `src/analysis/diplomacy_identity.py` 186-325 | Task 14/22 tests |
| Alignment is researcher-only (`consistent`, `unresolved`, `inconsistent`, `not_applicable`); no truth, lie, guilt, winner, legitimacy, or enforcement field exists | Original Request "interpret the same events differently"; `.ai-factory/ARCHITECTURE.md` "analysis is read-only" | Task 14/22 tests |
| Four families append (`organized_conflict_participation@1`, `organized_conflict_persistence@1`, `organized_conflict_outcomes@1`, `organized_conflict_interpretation@1`), raising the catalog 168 -> 172; the first 168 keep id, order, version, and value keys | Original Request "Define research analytics"; `src/analysis/specifications.py` 53, 238-245, 7384-7814, 7978-8032 | Task 15/22/25 tests |
| `organized-conflict-snapshot-v1` is a new canonical bounded snapshot; it does not rewrite `diplomacy-snapshot-v1`/`v2` or `diplomacy-store-v1` | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution"; V4-06/V4-07 snapshot precedent | Task 16/18/19/22 tests |
| Six GET routes under `/v1/simulations/{run_id}/organized-conflict` require `SUBJECTIVE_DEBUG`, return 503 `organized_conflict_disabled`, and 404 for unknown published records | `docs/research-api.md` 242-270; `src/api/routes/diplomacy.py` 199-422 | Task 20/22/23 tests |
| Cursors bind run, publication, digest, purpose, and filters; mismatch is 400 and expiry 410 | `src/simulation/diplomacy_ports.py` 96-166; `src/api/diplomacy_cursor.py` | Task 17/20/23 tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status | `src/experiments/diplomacy_publication.py` 327-414; `src/persistence/diplomacy_filesystem.py` 83-202 | Task 18/19/23 tests |
| The organized-conflict E2E runs in-process in the focused/unit lane with real ticks, real attacks, defense, retreat, capture, movement, assistance, publication, and all six routes; it is never reported as integration-only | Plan Settings; `tests/unit/test_diplomacy_e2e.py` | Task 23/24 tests |
| Every current 168 pin is swept to 172; historical revision statements and first-168 digests remain unchanged | `src/analysis/specifications.py:53`; 110 current `168` occurrences measured at plan time | Task 15 sweep and guard; Task 25 re-run |
| `organized_conflict` becomes the fifth owned V4 flag; seven remain unowned; `runner-config-v56` remains the only V4 schema | `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/runner_models.py` 320-326; `src/simulation/compatibility.py` 155-157 | Task 3/22/26 tests |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 25/26 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | No conflict ledger | No conflict metric, snapshot, publication, or route data | Task 3/8/23 tests |
| `organized_conflict` on v4 or v55 | Unchanged config | `v4_capability_requires_v56` before construction | Task 3 test |
| `organized_conflict` on v56 without `diplomacy` | Unchanged config | `v4_prerequisite_missing` at `stage="v4_capability_flags"` | Task 3 test |
| `organized_conflict` on v56 with `diplomacy` | Valid run | Conflict coordination beliefs active | Task 3/8/23 tests |
| `diplomacy` alone | Valid run | No conflict ledger or analysis | Task 3 test |
| `organizations` alone | Valid run | No conflict ledger | Task 3 test |
| `formal_rules` or `legal_disputes` alone | Valid run | Conflict stays disabled | Task 3 test |
| Another unowned V4 flag | No behavior change | Still fails closed with `capability_unimplemented` | Task 3/22 test |
| Owner proposes a coordinated attack plan | Plan + participation rows | `proposed` until joined locally; no obligation | Task 4/6/8 test |
| Owner joins a plan while `Wait` | Command replacement | One existing `Attack` command; ordinary admission decides the outcome | Task 9/23 test |
| Defense plan while `Wait` | Command replacement | `Help`, `Attack`, or `Move`; no damage mitigation | Task 9/23 test |
| Movement group plan while `Wait` | Command replacement | Independent `Move` to the shared destination; no group command | Task 9/11/23 test |
| Resource capture plan while `Wait` | Command replacement | `Take` ground/corpse item or voluntary `Give`; living-holder seizure remains impossible | Task 9/23 test |
| Structure attack plan while `Wait` | Command replacement | `OpposePublicGood` only for a completed public-good project; otherwise no physical structure damage | Task 9/23 test |
| Route blocking plan while `Wait` | Command replacement | `Move` to endpoint plus `Attack`/`Flee`/`Help`; route state unchanged | Task 9/11/23 test |
| Retreat plan while `Wait` | Command replacement | Independent `Flee`; failure is event-only | Task 9/23 test |
| Assistance plan while `Wait` | Command replacement | `Help`, `Feed`, or `Transport` | Task 9/23 test |
| Non-`Wait` command already selected | No replacement | Base selection is preserved; conflict plan does not override it | Task 9 test |
| Target is missing or unresolved | Participation/plan retained | No replacement; `unresolved_target` notice; plan expires at TTL | Task 6/9 test |
| Two owners interpret one episode differently | Two interpretation rows | Both retained; analysis reports disagreement; no reconciliation | Task 6/14/23 test |
| Single attacker and single target, no recurrence | Episode | `individual_violence`; no organized family count | Task 13/23 test |
| Two attackers on one side, repeated within windows | Episode | `coordinated_conflict` | Task 13/23 test |
| Two sides of two actors with reciprocal windows | Episode | `persistent_inter_group_conflict` | Task 13/23 test |
| Cap exceeded with droppable observations | Truncation | `organized_conflict_truncated:observations`; deterministic | Task 10 test |
| Cap exceeded with nothing droppable | Capacity error | `organized_conflict_capacity_reached` | Task 10 test |
| Snapshot exceeds 4 MiB or row caps | No publication | `organized_conflict_size_limit` | Task 16/18 test |
| Duplicate publication id with different bytes | Existing artifact untouched | `organized_conflict_publication_exists` | Task 19 test |
| `PALIMPSEST_ORGANIZED_CONFLICT_ROOT` unset | API state unset | 503 `organized_conflict_disabled`; CLI receipt `disabled` | Task 19/20/23 test |
| Cursor reused with same binding | Same page | 200; digest matches | Task 17/20 test |
| Cursor reused after any binding change | No page served | 400 `organized_conflict_cursor_invalid`; expired 410 | Task 17/20 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 18/19/23 test |
| In-process conflict E2E without PostgreSQL | No integration prerequisite | Runs in the focused/unit lane with real ticks, attacks, publication, and routes | Task 23/24 test |
| Required Compose/browser/Godot/benchmark/UI lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 24/26 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **One owned flag, one additive extension.** V4-12 claims the already-declared
   `organized_conflict` flag on `runner-config-v56`; it adds no flag, context,
   runner schema, root field, or per-agent runner key.
2. **The world is not rewritten.** All physical effects use existing commands and
   events. `src/world/` is not edited; no `world.at_war`, war state, conflict
   registry, army actor, order hierarchy, or battle object exists.
3. **Coordination is belief.** One owner retains plans, participation claims,
   observations, interpretations, outcomes, contradictions, and terminations.
4. **Eight operations are closed vocabulary.** `coordinated_attack`, `defense`,
   `movement_group`, `resource_capture`, `structure_attack`, `route_blocking`,
   `retreat`, and `assistance` are descriptive categories, never permissions.
5. **Operations compile to existing commands only.** A closed matrix maps each
   operation to named current commands; no new command type or event exists.
6. **Only `Wait` is replaced.** The deterministic replacement screen applies only
   to an exact `Wait` selection, so explicit self-preservation or plan choices
   are never overridden.
7. **No defense mechanic is invented.** Defense is `Help`, `Attack`, or `Move`;
   damage remains the existing fixed hit/damage rules.
8. **Resource capture is custody, not ownership.** `Take` from ground or corpse
   and voluntary `Give` are the only physical capture paths.
9. **Structure attack is project opposition.** Only a completed public-good
   project loses integrity through `OpposePublicGood`; generic structures remain
   unattackable.
10. **Route blocking is denial evidence.** Routes keep immutable duration and
    fatigue; coordinated presence and attacks at endpoints are the primitive.
11. **Movement groups are co-movement.** Independent `Move`/`Transport` commands
    share a destination and window; no group formation object exists.
12. **Retreat and assistance are commands.** `Flee`; `Help`/`Feed`/`Transport`;
    neither creates an obligation or a hierarchy.
13. **All physical effects are ordinary admission.** No conflict ledger,
    communication, analysis, snapshot, or publication helper submits, resolves,
    blocks, or executes an `AgentCommand`. The dedicated
    `organized_conflict_actions.organized_conflict_wait_replacement` screen may
    return one existing command value; it never submits or resolves it.
14. **The ledger never gives authority.** A plan target, role, or side is a
    belief; another owner may ignore it, and `WorldEngine` never reads it.
15. **Speech is bounded.** `ocf_v1` is 12 fields and 256 characters, at most one
    relation inside existing `Talk`/`Ask`/`Tell`; malformed frames are dropped.
16. **Peer claims are untrusted.** Speaker verification, local provenance
    assignment, and local target resolution are mandatory.
17. **The update pipeline is ordered.** collect observations and frames ->
    derive plans/participations -> interpret -> detect contradictions -> expire
    -> enforce limits.
18. **Derived rows are content-addressed and deduplicated.**
19. **Interpretation is plural.** Two owners may classify the same events
    differently; both rows are retained and never reconciled.
20. **Objective detection ignores owner claims.** Episodes are detected from
    committed events and the locked analysis policy only.
21. **Classification is closed.** `individual_violence`,
    `coordinated_conflict`, `persistent_inter_group_conflict`; no war/peace label.
22. **Alignment is researcher-only.** `consistent`, `unresolved`,
    `inconsistent`, `not_applicable`; it never reaches cognition, prompts,
    memory, world state, observer semantics, or stop selectors.
23. **Detached analysis keeps three layers.** Objective counts, owner-token rows,
    and analytical candidates are separate; leakage is a hard failure.
24. **Identity joins are read-only.** `org-` and `msoc-` identities are joined,
    never minted, renamed, split, merged, or dissolved.
25. **Four families append.** 168 -> 172; the first 168 keep id, order, version,
    and value keys; no composite violence, war, legitimacy, or winner score.
26. **A new snapshot and store.** `organized-conflict-snapshot-v1` and
    `organized-conflict-store-v1` are additive; diplomacy v1/v2 remain unchanged.
27. **Six new GET routes.** All require `SUBJECTIVE_DEBUG`, fail closed with
    `organized_conflict_disabled`, and never serve unpublished memory.
28. **Publication is opt-in and non-interfering.** A storage or composition
    failure changes only the receipt, never the scientific result.
29. **The UI is read-only.** It renders episodes, roles, plans, interpretations,
    and outcomes; it derives no authority, legitimacy, enforcement, score,
    winner, or war status.
30. **No new wire surface beyond the snapshot and routes.** No event, codec
    marker, command, observer semantic type, write pair, `/v2` route,
    `observer-protocol-v2`, or SQL migration.
31. **Deterministic by construction.** Sorted ordering, content-addressed IDs,
    canonical JSON digests, quantized ratios, integer counts, no `hash()`, no
    UUID, and no wall-clock domain values.
32. **Pin sweeps distinguish current from historical.** Current pins move to
    172 and five owned flags; historical revision statements and the first-168
    order keep their original numbers.
33. **No automatic generalization.** V4-12 implements no infrastructure,
    supply-chain, market, credit, science, epidemic, ecological, disaster,
    resilience, or macro-society behavior.

### Compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner
adds `v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands
43; observer semantic types 73; metric families **172 (V4-12 change)**; Alembic
`0017` with no `0018`; `/v1`; `observer-protocol-v1`; observer layout
`observer-layout-v1`; observer capabilities 4 advertised / 6 reserved; four
reserved write pairs (events 23-26 / codecs `v21`-`v24`);
`prepare_parallel=False`; six GET organization, six GET formal-rule, six GET
dispute, six GET evidence, six GET representation, eight GET diplomacy, and
**six GET organized-conflict** routes; eight cursor purposes per diplomacy
context and **six per organized-conflict context**; snapshots
`organization-snapshot-v1`/`v2`/`v3`, `formal-rule-snapshot-v1`,
`dispute-resolution-snapshot-v1`, `evidence-testimony-snapshot-v1`,
`delegation-representation-snapshot-v1`, `diplomacy-snapshot-v1`/`v2`, and
**`organized-conflict-snapshot-v1`**; stores `organization-store-v1`,
`formal-rule-store-v1`, `dispute-resolution-store-v1`,
`evidence-testimony-store-v1`, `delegation-representation-store-v1`,
`diplomacy-store-v1`, and **`organized-conflict-store-v1`**; 14 V4 contexts /
12 flags / **5 owned flags** (`organizations`, `formal_rules`,
`legal_disputes`, `diplomacy`, `organized_conflict`) / **7 unowned**
(`infrastructure_networks`, `supply_chains`, `markets_credit`, `science`,
`epidemics`, `ecological_feedback`, `disasters`). The other capability sets
still hold `institutional_economy` and `multi_hop_testimony_tracking` unowned;
they are not part of the 12 V4 flags. `/version` is unchanged;
`organization_rows` remains reserved.

## Phase Index

1. [Phase 1: Conflict Contract and Seam](phase-01-conflict-contract-and-seam.md) — Tasks 1-3
2. [Phase 2: Owner-Scoped Conflict Beliefs](phase-02-conflict-beliefs.md) — Tasks 4-10
3. [Phase 3: Detached Detection and Metrics](phase-03-detached-detection.md) — Tasks 11-15
4. [Phase 4: Organized-Conflict Snapshot](phase-04-snapshot.md) — Tasks 16-17
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 18-19
6. [Phase 6: Read-Only API and Research UI](phase-06-read-only-surfaces.md) — Tasks 20-21
7. [Phase 7: Invariants, End-to-End Conflict, and Regression](phase-07-invariants-and-regression.md) — Tasks 22-24
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 25-26

## Cross-Phase Dependencies

- All phases assume the completed V2/V3 contact, migration, commitment,
  collective-project, mediation, office, institution, collective-decision, and
  organization stacks plus V4-01 through V4-11; V4-12 does not rewrite them, but
  Tasks 22/24 must keep their suites green.
- Task 2 depends on Task 1: the locked policy uses the frozen vocabulary.
- Task 3 depends on Tasks 1-2: activation tests consume the contract and policy.
- Task 4 depends on Tasks 2-3: rows use the policy, IDs, and ledger seam.
- Task 5 depends on Task 4: IDs/digest cover the row families.
- Task 6 depends on Tasks 4-5: the pipeline mutates the complete ledger.
- Task 7 depends on Task 4: `ocf_v1` encodes the plan vocabulary.
- Task 8 depends on Tasks 6-7: collection consumes frames and the prepared
  ledger.
- Task 9 depends on Tasks 6-8: replacement reads the prepared ledger.
- Task 10 depends on Tasks 6-9: caps and export cover the complete ledger.
- Task 11 depends on Task 10: harvest reads exported ledgers and committed
  events.
- Task 12 depends on Task 11: layers consume harvested rows.
- Task 13 depends on Tasks 11-12: detection consumes objective rows.
- Task 14 depends on Tasks 11-13: alignment and identity consume episodes and
  owner rows.
- Task 15 depends on Tasks 11-14: metrics consume rows, episodes, and alignment.
- Task 16 depends on Tasks 10-15: the snapshot mirrors derived state and metric
  provenance.
- Task 17 depends on Task 16: paging and ports select typed rows.
- Task 18 depends on Tasks 10, 13, 15, and 17: the composer derives
  classifications and analysis at publication time.
- Task 19 depends on Tasks 16-18: the store and CLI call the composer.
- Task 20 depends on Task 19: the API reads the committed store.
- Task 21 depends on Task 20: the panel consumes the new routes.
- Task 22 depends on Tasks 2-21: the suite asserts every authority claim.
- Task 23 depends on Tasks 9-21: the E2E uses real ticks, commands, publication,
  and routes.
- Task 24 depends on Tasks 22-23: regression runs after invariant/E2E gates.
- Task 25 depends on Tasks 2-24: documentation describes verified surfaces.
- Task 26 depends on Tasks 24-25: final certification needs receipts and docs.

## Tasks

### Phase 1: Conflict Contract and Seam
- [x] Task 1: Freeze the conflict vocabulary identifier grammar and command matrix ([details](phase-01-conflict-contract-and-seam.md#task-1-freeze-the-conflict-vocabulary-identifier-grammar-and-command-matrix))
- [x] Task 2: Add the locked cognition and analysis policies ([details](phase-01-conflict-contract-and-seam.md#task-2-add-the-locked-cognition-and-analysis-policies)) (depends on 1)
- [x] Task 3: Claim organized_conflict and enforce the diplomacy prerequisite ([details](phase-01-conflict-contract-and-seam.md#task-3-claim-organized_conflict-and-enforce-the-diplomacy-prerequisite)) (depends on 1, 2)

### Phase 2: Owner-Scoped Conflict Beliefs
- [x] Task 4: Define conflict plans participations observations interpretations outcomes and contradictions ([details](phase-02-conflict-beliefs.md#task-4-define-conflict-plans-participations-observations-interpretations-outcomes-and-contradictions)) (depends on 2, 3)
- [x] Task 5: Add content-addressed ids ledger digest and canonical owner ledger ([details](phase-02-conflict-beliefs.md#task-5-add-content-addressed-ids-ledger-digest-and-canonical-owner-ledger)) (depends on 4)
- [x] Task 6: Implement the ordered conflict update pipeline ([details](phase-02-conflict-beliefs.md#task-6-implement-the-ordered-conflict-update-pipeline)) (depends on 4, 5)
- [x] Task 7: Add bounded ocf_v1 conflict speech frames ([details](phase-02-conflict-beliefs.md#task-7-add-bounded-ocf_v1-conflict-speech-frames)) (depends on 4)
- [x] Task 8: Wire conflict beliefs through cognition and runtime carry ([details](phase-02-conflict-beliefs.md#task-8-wire-conflict-beliefs-through-cognition-and-runtime-carry)) (depends on 6, 7)
- [x] Task 9: Compile active plans to existing commands on Wait ([details](phase-02-conflict-beliefs.md#task-9-compile-active-plans-to-existing-commands-on-wait)) (depends on 6-8)
- [x] Task 10: Enforce conflict caps notices and owner export ([details](phase-02-conflict-beliefs.md#task-10-enforce-conflict-caps-notices-and-owner-export)) (depends on 6-9)

### Phase 3: Detached Detection and Metrics
- [x] Task 11: Harvest objective conflict rows from committed events ([details](phase-03-detached-detection.md#task-11-harvest-objective-conflict-rows-from-committed-events)) (depends on 10)
- [x] Task 12: Harvest owner rows and keep three layers separate ([details](phase-03-detached-detection.md#task-12-harvest-owner-rows-and-keep-three-layers-separate)) (depends on 11)
- [x] Task 13: Detect individual organized and persistent inter-group episodes ([details](phase-03-detached-detection.md#task-13-detect-individual-organized-and-persistent-inter-group-episodes)) (depends on 11, 12)
- [x] Task 14: Add episode lineage read-only identity joins and interpretation alignment ([details](phase-03-detached-detection.md#task-14-add-episode-lineage-read-only-identity-joins-and-interpretation-alignment)) (depends on 11-13)
- [x] Task 15: Add four metric families and raise the catalog to 172 ([details](phase-03-detached-detection.md#task-15-add-four-metric-families-and-raise-the-catalog-to-172)) (depends on 11-14)

### Phase 4: Organized-Conflict Snapshot
- [x] Task 16: Define organized-conflict-snapshot-v1 and canonical codec ([details](phase-04-snapshot.md#task-16-define-organized-conflict-snapshot-v1-and-canonical-codec)) (depends on 10-15)
- [x] Task 17: Add conflict ports cursor purposes and bounded paging ([details](phase-04-snapshot.md#task-17-add-conflict-ports-cursor-purposes-and-bounded-paging)) (depends on 16)

### Phase 5: Composition and Durable Publication
- [x] Task 18: Compose completed-run conflict views and receipts ([details](phase-05-composition-publication.md#task-18-compose-completed-run-conflict-views-and-receipts)) (depends on 10, 13, 15, 17)
- [x] Task 19: Add the filesystem store settings and CLI producer ([details](phase-05-composition-publication.md#task-19-add-the-filesystem-store-settings-and-cli-producer)) (depends on 16-18)

### Phase 6: Read-Only API and Research UI
- [x] Task 20: Add six GET conflict routes schemas and app wiring ([details](phase-06-read-only-surfaces.md#task-20-add-six-get-conflict-routes-schemas-and-app-wiring)) (depends on 19)
- [x] Task 21: Add the read-only Research UI conflict view ([details](phase-06-read-only-surfaces.md#task-21-add-the-read-only-research-ui-conflict-view)) (depends on 20)

### Phase 7: Invariants, End-to-End Conflict, and Regression
- [x] Task 22: Add the conflict boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-22-add-the-conflict-boundary-and-determinism-suite)) (depends on 2-21)
- [x] Task 23: Add the organized-conflict end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-23-add-the-organized-conflict-end-to-end-scenario)) (depends on 9-21)
- [x] Task 24: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-24-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 22, 23)

### Phase 8: Documentation and Final Verification
- [x] Task 25: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-25-execute-the-documentation-checkpoint)) (depends on 2-24)
- [x] Task 26: Perform final V4-12 verification ([details](phase-08-docs-and-verification.md#task-26-perform-final-v4-12-verification)) (depends on 24, 25)

## Verification Receipt (Tasks 24 and 26)

To be completed by Task 24 and audited by Task 26. Every required lane must be
recorded as exactly one of `executed_passed`, `executed_failed`, or
`unexecuted`. An `unexecuted` lane carries its missing prerequisite and blocks
certification; it is never a skip-pass. Initial planning state is `unexecuted`
for every lane because nothing has run yet.

| Lane | State | Evidence |
| --- | --- | --- |
| Python unit + architecture with coverage | executed_passed | `uv run pytest tests/unit tests/architecture -q`: 9,191 passed in 525.51s; the 79% coverage baseline from the coverage-enabled run is retained. |
| Focused V4-12 suite | executed_passed | Contract, policy, ledger/caps, update, communication, actions, carry, export, events, detection, layers, identity, alignment, metrics, catalog, snapshot, ports, publication, store, composition, API, boundary, determinism, docs, collector, and E2E tests green (146 tests). |
| Focused in-process conflict E2E | executed_passed | `tests/unit/test_organized_conflict_e2e.py`: real `WorldEngine` ticks; individual, coordinated/persistent, defense/help, retreat/flee, movement, capture-from-corpse, publication store, and all six GET routes; no PostgreSQL. |
| V1/V2/V3/V4 regression selection | executed_passed | Included in the 9,191-test unit + architecture run; no regressions. |
| Documentation parity | executed_passed | 62 docs tests plus `docs/organized-conflict.md`, metric/API/UI/configuration/architecture/README updates, and V4-12 context seams. |
| Ruff | executed_passed | `uv run ruff check src tests` — all checks passed. |
| Mypy | executed_passed | `uv run mypy` — success, 2,123 source files. |
| Import-linter | executed_passed | `uv run lint-imports` — 25 contracts kept, 0 broken. |
| Integration (`-m "integration and not scale"`) | unexecuted | Requires a disposable PostgreSQL/pgvector instance. |
| Integration including scale | unexecuted | Requires a disposable PostgreSQL/pgvector instance and the long-run harness. |
| Docker Compose config | executed_passed | `docker compose config --quiet` — exit 0. |
| Compose/browser acceptance | unexecuted | Requires Docker, a real browser driver, and a source-attested image. |
| Godot 4.7.2 regression | unexecuted | Requires pinned Godot 4.7.2 and its export toolchain. |
| Benchmark/scale lane | unexecuted | Requires the multi-hour benchmark harness. |
| Research UI tests | executed_passed | `npx pnpm@10.34.9 test --run`: 55 files, 277 tests passed. |
| Research UI type/static checks | executed_passed | `npx pnpm@10.34.9 check`: 0 errors, 0 warnings. |
| Research UI build | executed_passed | `npx pnpm@10.34.9 build`: 5-file build tree emitted. |

Certification outcome: **not certified** — implementation and focused/static/UI lanes are green; integration, Compose/browser, Godot, and benchmark/scale lanes remain unexecuted and block certification.

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-3: `feat(v4): claim organized conflict and freeze the contract`
2. After Tasks 4-8: `feat(v4): add owner-scoped conflict coordination beliefs`
3. After Tasks 9-10: `feat(v4): compile conflict roles to existing commands`
4. After Tasks 11-15: `feat(v4): detect organized conflict and append metrics`
5. After Tasks 16-19: `feat(v4): publish organized-conflict-snapshot-v1`
6. After Tasks 20-21: `feat(v4): serve read-only organized-conflict surfaces`
7. After Tasks 22-26: `test(v4): enforce organized-conflict invariants and certify`

## Blocking Conditions and Non-Goals

- Adding a new V4 flag, `runner-config-v57`, a new context, a runner root field,
  or a per-agent runner key to make this plan work is a blocking scope
  violation. Stop and re-plan.
- Claiming `infrastructure_networks`, `supply_chains`, `markets_credit`,
  `science`, `epidemics`, `ecological_feedback`, `disasters`,
  `institutional_economy`, or `multi_hop_testimony_tracking` is forbidden.
- Adding `world.at_war`, a war/peace field, `WarState`, `ConflictRegistry`,
  `ArmyActor`, `Legion`, `Battalion`, `Battle`, `Front`, `Polity`, `Border`,
  `Citizenship`, `VictoryOracle`, `LegitimacyOracle`, or a command hierarchy is
  forbidden.
- Adding a `Defend`, `Guard`, `Protect`, `Block`, `Seize`, `Raid`, `Siege`, or
  group-move command is forbidden. Use the existing command matrix.
- Adding a new event, observer semantic type, write pair, artifact kind, wire
  record genre, `/v2` route, `observer-protocol-v2` serving, or SQL migration is
  forbidden.
- Editing `src/world/` to create structure damage, route closure, living-holder
  seizure, damage mitigation, or group movement is forbidden. Those are explicit
  non-goals of this wire-constrained plan. Physical structure damage and physical
  route closure are deferred to a separate plan that extends world semantics,
  events, replay, and possibly a migration; they must not be folded into V4-12.
- Letting `WorldEngine`, perception, admission, stop selectors, memory, prompts,
  observer semantics, or the Godot client read a conflict ledger is forbidden.
- Letting any conflict ledger, communication, analysis, snapshot, publication,
  or API helper return, construct, submit, resolve, block, or execute an
  `AgentCommand` is forbidden. The only exception is the dedicated
  `organized_conflict_actions.organized_conflict_wait_replacement` screen, which
  may return one existing command value and never submits or resolves it.
- Treating a plan, role, side, interpretation, or alignment as permission,
  obligation, prohibition, truth, guilt, liability, enforcement, legitimacy, or
  a binding finding is forbidden.
- Inferring a plan, participation, interpretation, or outcome from silence, an
  unobserved act, or another owner's ledger is forbidden.
- Treating a peer-supplied `ocf_v1` frame `provenance`, target, side, or plan
  reference as trusted is forbidden.
- Reading a peer owner's relationship, reputation, commitment, rule, office,
  institution, organization, decision, dispute, evidence, representation,
  diplomacy, treaty, or institutional-memory ledger to evaluate conflict is
  forbidden.
- Reconciling conflicting interpretations, episodes, plans, targets, or sides
  into one authoritative conflict is forbidden. Analysis may classify alignment
  for researchers only.
- Minting, renaming, splitting, merging, or dissolving `org-` or `msoc-`
  identities from conflict analysis is forbidden.
- Computing, storing, publishing, or rendering a violence score, war score,
  escalation index, legitimacy score, winner, loser, trust value, or composite
  relation score is forbidden. All outputs are counts, durations, ratios, and
  closed labels.
- Rewriting `diplomacy-snapshot-v1`/`v2`, `diplomacy-store-v1`, `dip_v1`,
  `trt_v1`, or the `diplomacy.v1`/`treaty.v1` contracts is forbidden.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`, replay
  v22, codec v20, command count, observer semantic count, context count) is
  forbidden. The only intentional pin changes are 168 -> 172 metric families,
  the four conflict families, the six additional organized-conflict GET routes,
  the new v1 snapshot, the new store, and 4 -> 5 owned flags.
- Claiming prevalence, emergence probability, predictive power, accuracy,
  reliability, moral correctness, or a composite conflict score is forbidden.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope;
  `$aif-roadmap` owns that.
- Changing the Godot client, observer protocol, observer capabilities, or
  `/version` is out of scope; the Research UI is the only client change.
- Enabling V4 flags in matrix lanes is out of scope; `experiments.matrix_schema`
  keeps its rejection gate.
- V4-12 does not add a command selector, prompt, or speech-generation bias
  outside the explicit deterministic `Wait` replacement and `ocf_v1` attachment.
- Full qualification requires a disposable PostgreSQL/pgvector instance,
  Docker, a real browser driver, and the pinned Node/pnpm and Godot toolchains.
  A missing prerequisite leaves the lane unexecuted and blocks certification; it
  never becomes a skip-pass.
- Do not implement any other V4 context in this plan.

## Definition of Done

- All 26 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- `organized_conflict` is the fifth owned V4 flag; no `v57`, new flag, context,
  root field, or per-agent runner key exists; the other seven V4 flags remain
  unowned and fail closed.
- The context registry validates at 14 contexts, 12 flags,
  `v4-context-map-v2`, and five owned flags.
- Activation requires `runner-config-v56`, `organized_conflict`, and
  `diplomacy`; missing diplomacy fails closed with a stable prerequisite code.
- The eight requested operations exist as closed owner beliefs and compile only
  to the documented existing commands; no new command, event, write pair, or
  migration exists.
- Defense, resource capture, structure attack, route blocking, movement groups,
  retreat, and assistance are honestly bounded: no damage mitigation, living
  seizure, generic structure damage, route closure, group-move command, or
  command hierarchy.
- A deterministic `Wait` replacement performs one existing command per active
  plan; non-`Wait` selections are never overridden, and every physical effect is
  ordinary `WorldEngine` admission.
- `ocf_v1` is bounded at 12 fields and 256 characters, at most one relation in
  existing `Talk`/`Ask`/`Tell`; malformed, oversize, or speaker-mismatched frames
  are dropped.
- The owner ledger retains plans, participations, observations, interpretations,
  outcomes, contradictions, and terminations with content-addressed IDs, a
  canonical digest, ordered updates, and bounded caps.
- Two owners may retain different interpretations of the same event pattern;
  both are published, and no reconciliation or truth verdict exists.
- Detached analysis harvests objective rows from existing committed events,
  keeps three layers separate, detects individual, coordinated, and persistent
  inter-group episodes with locked deterministic thresholds, derives forward-only
  lineage, joins `org-`/`msoc-` read-only, and classifies researcher-only
  interpretation alignment.
- The metric catalog is exactly 172 with four appended families; the first 168
  are unchanged; real completed-run assembly emits all four documents; no
  composite, war, or winner score exists.
- No test file or current-pin doc line still asserts 168; the stale-pin guard
  passes while historical revision statements and the first-168 order remain.
- `organized-conflict-snapshot-v1` and `organized-conflict-store-v1` are
  canonical, bounded, atomic, and immutable after publication; diplomacy v1/v2
  and its store remain unchanged.
- Snapshot rows and API responses contain only hashed tokens, content-addressed
  IDs, opaque anchors, and composer-derived labels; no raw agent id, free-text
  target, frame body, or observation content is published.
- Six GET-only organized-conflict routes require `SUBJECTIVE_DEBUG`, have an
  explicit `organized_conflict_disabled` state, return 404 for unknown published
  records, and are consumed by a read-only Research UI view that derives no
  authority, legitimacy, enforcement, score, winner, or war status.
- Cursor reuse works on conflict pages; a changed run/publication/digest/purpose/
  filter fails with 400 and expiry with 410.
- `WorldEngine` never reads a conflict ledger; a plan or interpretation never
  blocks a physically possible command, and a physically impossible command is
  still rejected by existing world rules.
- The boundary suite proves owner-only authority, the absence of war/army/
  registry/score objects, no command construction outside the `Wait` screen, no
  peer-ledger reads, no world-ledger reads, no `org-`/`msoc-` mutation, and no
  new commands/events/migrations; observer and migration pins are unchanged.
- The focused in-process conflict E2E runs without PostgreSQL in the focused/
  unit lane and is never reported as an integration-only prerequisite.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what organized conflict controls (a belief and a
  deterministic command screen), what it never controls (war state, permission,
  obligation, truth, enforcement, score, or winner), how the eight operations map
  to existing commands, how `ocf_v1` works, how detection distinguishes
  individual from persistent inter-group conflict, and every count matches the
  code. The docs sweep updates every current 168 pin and leaves historical seam
  pins intact.
- `docs/organized-conflict.md` is the canonical contract;
  `docs/analysis-metrics.md` documents the four families,
  `docs/research-api.md` documents the six routes, `docs/research-ui.md`
  documents the view, `docs/v4-architecture.md` records the V4-12 seam, and
  README plus `docs/diplomacy.md` and `docs/architecture.md` link the contract.
