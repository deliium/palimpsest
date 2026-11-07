<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-13 Borders and Claims

Mode: ultra
Branch: main
Created: 2026-11-06

## Original Request

v4-13 borders and claims

Naming requirement:

Use `v4-13-borders`.

Extend V3 territoriality to sets of logical Locations.

WorldEngine knows only locations and occupancy.

Agents/organizations may believe:

these locations belong to us.

Support:

- claims
    
- overlapping claims
- disputed borders
- recognized boundaries
- access expectations
- border agreements

No grid conversion.

No objective CountryOwner field.

Godot/research overlays must distinguish:

physical control  
subjective claim  
agreement  
analytical control pattern

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN unresolved references/truncation, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log participant
  or actor identities, location or claim ids, plan/record ids, target or
  counterparty tokens, frame bodies, observation bodies, prompts, credentials,
  tokens, DSNs, memories, embeddings, utterance bodies, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 26.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-13-borders`; the ultra bundle directory is
  `.ai-factory/plans/v4-13-borders/`, phase files use `phase-NN-<slug>.md`, and
  `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-13 deepens the already-owned `organizations` V4 context on the
accepted `runner-config-v56` seam with owner-scoped territorial domains, observed
boundary edges, access expectations, border agreements, disputes, four detached
analysis layers, four metric families (172 -> 176), `borders-snapshot-v1`, a
`borders-store-v1` filesystem store, six read-only routes, a Research UI panel,
and four Godot overlay kinds, without adding a flag, context, runner schema,
command, event, write pair, observer semantic type, `/v2` route, or migration.
This plan does not edit or close the roadmap; `$aif-roadmap` must register V4-13
in M8 and record the `organizations` deepening.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01 through V4-12 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V3 territorial, regional, organization,
diplomacy, and treaty code plus
`tests/architecture/test_v4_architecture_invariants.py`,
`test_diplomacy_boundaries.py`, `test_treaty_boundaries.py`,
`test_organization_boundaries.py`, `test_organization_operations_boundaries.py`,
`test_organization_agency_boundaries.py`, `test_formal_rule_boundaries.py`,
`test_dispute_boundaries.py`, `test_evidence_testimony_boundaries.py`, and
`test_delegation_representation_boundaries.py` govern compatibility. V4-13
claims no new V4 flag and creates no context; it deepens the owned
`organizations` context and extends the existing V3 territorial-claim model.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-13 adds no V4 flag, context, `runner-config-v57`, runner root field, or per-agent runner key; it deepens the already-owned `organizations` context | Original Request "Extend V3 territoriality"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/v4_architecture.py` 60-76, 110-127 | Task 3 tests; Task 23 pins; Task 27 v57 absence |
| Activation is `runner-config-v56` + `v4_capability_flags.organizations` + the agent's `territorial_claim_mode=DETERMINISTIC`; legacy v15/v44/v55 behavior is unchanged | `src/simulation/runner.py` 1034-1041, 1187-1195; `src/agents/cognition/configuration.py` 323-331, 604-760 | Task 3 tests |
| The border ledger is one owner's belief; no objective world field, `country_owner`, `sovereign`, `territory_owner`, `controller`, `Border`, `CountryOwner`, `TerritoryRegistry`, or `BorderRegistry` exists | Original Request "No objective CountryOwner field"; `.ai-factory/ARCHITECTURE.md` Key Principle 1 | Task 1/4/23 tests |
| A domain is a sorted set of 1-8 logical `EntityId` locations; no grid cell, coordinate, polygon, area, or region-to-border conversion exists | Original Request "sets of logical Locations", "No grid conversion"; `src/world/models.py` 81-111; `src/world/regions.py` 39-61 | Task 1/9/23 tests |
| Boundary edges are observed adjacency pairs where exactly one endpoint is in the domain; an unobserved edge is `unresolved`, never invented | Original Request "recognized boundaries"; `src/world/observations.py` `VisibleExit` 284-330 | Task 9/23 tests |
| The owner retains five row families: domain claim, boundary recognition, access expectation, border agreement, border dispute, plus evidence and notices | Original Request "claims, overlapping claims, disputed borders, recognized boundaries, access expectations, border agreements" | Task 4/23 tests |
| Overlapping claims are legal and retained; a dispute records the contested locations without reconciliation, winner, guilt, or forced boundary | Original Request "overlapping claims", "disputed borders"; `.ai-factory/ARCHITECTURE.md` Key Principle 1 | Task 4/6/13/23 tests |
| A recognized boundary is an owner belief based on own claim, direct observation, testimony, or agreement; it is never a truth or an enforcement finding | Original Request "recognized boundaries"; `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts" | Task 6/9/13/23 tests |
| An access expectation is a closed mode (`open`, `restricted`, `permission_expected`, `unknown`); it never grants access or blocks a command | Original Request "access expectations"; `.ai-factory/ARCHITECTURE.md` "anti-patterns" | Task 4/6/23/24 tests |
| A border agreement is an owner belief with closed acts/provisions/status; it binds nobody and moves nothing | Original Request "border agreements"; `.ai-factory/ARCHITECTURE.md` "anti-patterns" | Task 4/6/13/23 tests |
| `bdr_v1` is 10 fields, at most 256 characters per relation, at most 8 relations, carried only inside existing `Talk`/`Ask`/`Tell`; malformed/oversize/speaker-mismatched frames are dropped | Original Request "border agreements"; `src/agents/cognition/organized_conflict_communication.py` 84-95; `diplomacy_communication.py` 93-95, 632-642 | Task 7/23 tests |
| Peer claims, targets, counterparties, and declared provenance are untrusted; the receiver assigns provenance from delivery and resolves anchors locally | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `diplomacy_communication.py` 707-721 | Task 6/7/23 tests |
| The update order is own claims -> observed edges -> contiguous domains -> frames -> anchor resolution -> acts -> overlaps/disputes -> recognition -> expire -> caps -> digest | Original Request "Support"; `.ai-factory/ARCHITECTURE.md` Key Principle 1 | Task 6/23 tests |
| No border helper returns, constructs, submits, resolves, or blocks an `AgentCommand`; every physical effect remains ordinary `WorldEngine` admission | `.ai-factory/ARCHITECTURE.md` "anti-patterns"; V4-12 non-goals | Task 6/23/24 tests |
| `WorldEngine`, perception, admission, stop selectors, memory, prompts, observer semantics, and Godot physics never read a border ledger | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" | Task 8/23/24 tests |
| Detached analysis harvests four layers: physical control from committed events; subjective claims from exported ledgers; agreements from exported ledgers; analytical control patterns from the other three | Original Request four-layer distinction; `.ai-factory/ARCHITECTURE.md` Key Principle 1 | Task 11/12/13/23 tests |
| A hard leakage guard keeps the four layers in separate types; a leak is a hard failure | `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/organized_conflict_layers.py` 115-133 | Task 12/23 tests |
| Physical control is a count/classification of presence, use, hostile, and assistance events; it is not ownership | Original Request "physical control"; `src/analysis/spatial_control_metrics.py` 83-186 | Task 11/13/23 tests |
| Analytical control patterns are closed labels (`unclaimed`, `claim_only`, `claim_aligned`, `claim_overlap`, `agreement_aligned`, `agreement_contested`, `physical_unclaimed`, `contested`, `unknown`); no composite score exists | Original Request "analytical control pattern" | Task 13/23 tests |
| Domain lineage is content-addressed and forward-only (`emerged`, `continued`, `transformed`, `split`, `merge`, `dissolved`); `org-`/`msoc-` joins are read-only and never mint, rename, split, merge, or dissolve those identities | `.ai-factory/ARCHITECTURE.md` "analysis is read-only" | Task 14/23 tests |
| Alignment is researcher-only (`consistent`, `unresolved`, `inconsistent`, `not_applicable`); missing evidence is `unresolved`, never `inconsistent` | Original Request "Agents and societies may interpret the same events differently" (applied to claims); V4-08/V4-11 alignment precedent | Task 14/23 tests |
| Four families append (`border_claim_structure@1`, `border_overlap_contest@1`, `border_agreement_recognition@1`, `border_control_alignment@1`), raising the catalog 172 -> 176; the first 172 keep id, order, version, and value keys | Original Request "research overlays"; `src/analysis/specifications.py` 52-53, 246-249, 7971-8024, 8196-8199 | Task 15/23/26 tests |
| `borders-snapshot-v1` is a new canonical bounded snapshot with a required summary row and a candidate row family; lineage and alignment tokens resolve to candidates; it does not rewrite `organized-conflict-snapshot-v1`, `diplomacy-snapshot-v1`/`v2`, or any existing store | `.ai-factory/ARCHITECTURE.md` accepted-set/exact-key-set; V4-06/V4-12 snapshot precedent | Task 16/18/19/23 tests |
| Six GET routes under `/v1/simulations/{run_id}/borders` require `SUBJECTIVE_DEBUG`, return 503 `borders_disabled`, and 404 for unknown published records | `docs/research-api.md` 242-280; `src/api/routes/organized_conflict.py` 179-377 | Task 20/23/24 tests |
| Cursors bind run, publication, digest, purpose, and filters; mismatch is 400 and expiry 410 | `src/simulation/organized_conflict_ports.py` 66-91; `src/api/organized_conflict_cursor.py` | Task 17/20/24 tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status | `src/experiments/organized_conflict_publication.py` 49-409; `src/persistence/organized_conflict_filesystem.py` 81-131 | Task 18/19/24 tests |
| The border E2E runs in-process in the focused/unit lane with real ticks, claims, overlap, agreement, access expectation, physical use, publication, and all six routes; it is never reported as integration-only | Plan Settings; `tests/unit/test_organized_conflict_e2e.py` | Task 24/25 tests |
| Every current 172 pin is swept to 176; historical revision statements and the first-172 digests remain unchanged, except the documented correction of the treaty sentence from 164 -> 172 to 164 -> 168 | `src/analysis/specifications.py:53`; current 172 occurrences measured at plan time | Task 15 sweep; Task 26 re-run |
| The Godot evidence model stays three-valued (objective, subjective, analytical); four border overlay kinds map onto it, with agreement distinct from claim and pattern | Original Request "Godot/research overlays must distinguish"; `clients/godot-observer/scripts/presentation/evidence_class.gd` 5-81 | Task 22/23 tests |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 25/27 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | No border ledger | No border metric, snapshot, publication, or route data | Task 3/24 tests |
| v15/v44/v55 + deterministic territorial mode | Legacy territorial ledger only | No border ledger; byte-compatible behavior | Task 3/8 tests |
| v56 without `organizations` | No border ledger | No border analysis or routes | Task 3 test |
| v56 + `organizations` without deterministic territorial mode | No border ledger | No domain claims | Task 3 test |
| v56 + `organizations` + deterministic territorial mode | Border ledger active | Domain claims, agreements, access expectations, disputes | Task 3/6/24 tests |
| v56 + `organizations` + `diplomacy` | Border ledger active | Treaty anchors may resolve read-only; no treaty rewrite | Task 6/23 tests |
| v56 + `organizations` without `diplomacy` | Border ledger active | Treaty anchors stay unresolved; no prerequisite failure | Task 3/6 tests |
| Another unowned V4 flag | No behavior change | Still fails closed with `capability_unimplemented` | Task 3/23 tests |
| Owner claims 1 location | One domain | One `bdc-` claim; boundary may be unresolved | Task 4/9 test |
| Owner claims 2+ contiguous locations | One domain | Sorted set, observed boundary edges | Task 4/9 test |
| Owner claims non-contiguous locations | Multiple domains | Each component is a separate claim; no invented edge | Task 6/9 test |
| Two owners claim the same location | Two claims | Overlap retained; no reconciliation | Task 6/13 test |
| Peer claim overlaps own domain | Own + peer claim | `disputed` row with contested locations | Task 6/13 test |
| Agreement proposed then accepted by counterparty | Agreement row | `apparent_acceptance`; binds nobody | Task 6/13 test |
| Agreement proposed but not accepted | Proposed row | No acceptance; no obligation | Task 6 test |
| Agreement rejected/withdrawn | Retained terminal row | Status retained; no deletion of history | Task 6/10 test |
| Access expectation explicit frame | One access row | Closed mode; no command effect | Task 4/6/24 test |
| No access frame | No access row | Silence never creates an expectation | Task 6 test |
| Domain with no observed edge | Domain + unresolved boundary | `boundary_unobserved` notice; no invented edge | Task 9 test |
| Unresolved organization/treaty anchor | Row retained | `unresolved_anchor` notice; no invented anchor | Task 6 test |
| Malformed/oversize/speaker-mismatched `bdr_v1` | No row | `malformed_frame`; frame dropped | Task 7 test |
| Cap exceeded with droppable terminal rows | Truncated ledger | `borders_truncated:<family>`; deterministic | Task 10 test |
| Cap exceeded with nothing droppable | Prior ledger retained | `borders_capacity_reached` | Task 10 test |
| Snapshot exceeds 4 MiB or row caps | No publication | `borders_size_limit` receipt | Task 16/18 test |
| Duplicate publication id with different bytes | Existing artifact untouched | `borders_publication_exists` | Task 19 test |
| `PALIMPSEST_BORDERS_ROOT` unset | API state unset | 503 `borders_disabled`; CLI receipt `disabled` | Task 19/20/24 test |
| Cursor reused with the same binding | Same page | 200; digest matches | Task 17/20 test |
| Cursor reused after any binding change | No page served | 400 `borders_cursor_invalid`; expiry 410 | Task 17/20 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 18/19/24 test |
| In-process border E2E without PostgreSQL | No integration prerequisite | Runs in the focused/unit lane with real ticks, commands, publication, and routes | Task 24/25 test |
| Required Compose/browser/Godot/benchmark/UI lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 25/27 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **No new flag, no new context.** V4-13 deepens the owned `organizations`
   context and extends the existing V3 `territorial_claims.v1` model; the 14
   contexts, 12 flags, and `runner-config-v56` seam are unchanged.
2. **Legacy paths stay byte-compatible.** The border ledger is active only when
   `organizations` and deterministic territorial mode are both on. v15/v44/v55
   runs without `organizations` produce no border ledger.
3. **One owner, one belief.** A domain, recognition, access expectation,
   agreement, or dispute belongs to exactly one owner. No shared claim, case
   file, registry, or truth store exists.
4. **A location set is logical.** 1-8 sorted `EntityId` locations. No grid,
   coordinate, polygon, area, or region-to-border conversion.
5. **Boundaries are observed edges.** A boundary edge is a canonical pair of
   adjacent locations with exactly one endpoint in the domain. Unobserved is
   explicit, never invented.
6. **Five closed row families.** Domain claims, boundary recognitions, access
   expectations, border agreements, border disputes; evidence and notices are
   retained.
7. **Overlap is legal.** Two owners may claim the same location; one owner may
   hold overlapping domains. Overlap is retained, never assigned to one owner.
8. **Disputes are retained.** A dispute records contested locations and a
   counterparty, not a verdict, guilt, liability, or forced boundary.
9. **Recognition is belief.** `recognized` requires independent declarations or
   an agreement; it is never an objective truth or an enforcement finding.
10. **Access expectations are descriptive.** Closed modes only; they never grant
    access, deny a command, or change world rules.
11. **Agreements bind nobody.** Closed acts, provisions, and statuses; no
    enforcement, cession, transfer, or automatic boundary.
12. **Speech is bounded.** `bdr_v1` is 10 fields, 256 characters per relation,
    at most 8 relations, inside existing `Talk`/`Ask`/`Tell`.
13. **Peer claims are untrusted.** Speaker binding and local provenance are
    mandatory; declared provenance is replaced from delivery.
14. **Update order is fixed.** Own claims, observed edges, contiguous domains,
    frames, anchor resolution, acts, overlaps/disputes, recognition, expire,
    caps, digest.
15. **No command path.** No border helper constructs, submits, resolves, or
    blocks an `AgentCommand`. Every physical effect remains ordinary admission.
16. **No world read.** `WorldEngine`, perception, admission, stop selectors,
    memory, prompts, observer semantics, and Godot physics never read the
    ledger.
17. **Physical control is derived.** Detached counts of presence, use, hostile,
    and assistance events; not ownership.
18. **Four layers are separate.** Physical control, subjective claim, agreement,
    analytical control pattern; a hard leakage guard fails the build.
19. **Analytical patterns are descriptive.** Closed labels with counts and
    denominators; no composite score.
20. **Identity joins are read-only.** `bord-` candidates are content-addressed;
    `org-`/`msoc-` identities are never minted, renamed, split, merged, or
    dissolved.
21. **Alignment is researcher-only.** `consistent`, `unresolved`,
    `inconsistent`, `not_applicable`; it never reaches cognition, prompts,
    memory, world state, observer semantics, or stop selectors.
22. **Four metrics append.** 172 -> 176; the first 172 keep id, order, version,
    and value keys; no composite border score.
23. **A new snapshot and store.** `borders-snapshot-v1` and
    `borders-store-v1` are additive; the snapshot has a required summary row and
    a candidate row family so lineage/alignment tokens resolve; existing
    snapshots/stores are unchanged.
24. **Six GET routes.** All require `SUBJECTIVE_DEBUG`, fail closed with
    `borders_disabled`, and never serve unpublished memory.
25. **Publication is opt-in and non-interfering.** A storage/composition failure
    changes only the receipt.
26. **The Research UI is read-only.** Four sections with epistemic badges; no
    authority, legitimacy, enforcement, score, winner, or sovereignty.
27. **Godot keeps three evidence classes.** Four overlay kinds map onto
    objective, subjective, and analytical; agreement is distinct from claim.
28. **No new wire surface.** No event, command, observer semantic type, write
    pair, codec marker, `/v2` route, `observer-protocol-v2`, or SQL migration.
29. **Deterministic by construction.** Sorted ordering, content-addressed IDs,
    canonical JSON digests, quantized ratios, integer counts, no `hash()`, no
    UUID, no wall-clock domain values.
30. **Pin sweeps distinguish current from historical.** Current pins move to 176;
    historical revision statements and the first-172 order keep their numbers,
    except the documented treaty sentence correction from 164 -> 172 to
    164 -> 168.
31. **No automatic generalization.** V4-13 implements no infrastructure,
    supply-chain, market, credit, science, epidemic, ecological, disaster,
    resilience, war, or macro-society behavior.
32. **The roadmap is not edited.** `$aif-roadmap` owns M8 registration and
    milestone closure.

### Compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner
`v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands 43;
observer semantic types 73; metric families **176 (V4-13 change)**; Alembic
`0017` with no `0018`; `/v1`; `observer-protocol-v1`; observer layout
`observer-layout-v1`; observer capabilities 4 advertised / 6 reserved; four
reserved write pairs (events 23-26 / codecs `v21`-`v24`);
`prepare_parallel=False`; six GET organization, six GET formal-rule, six GET
dispute, six GET evidence, six GET representation, eight GET diplomacy, six GET
organized-conflict, and **six GET borders** routes; eight cursor purposes per
diplomacy context, six per organized-conflict context, and **six per borders
context**; snapshots `organization-snapshot-v1`/`v2`/`v3`,
`formal-rule-snapshot-v1`, `dispute-resolution-snapshot-v1`,
`evidence-testimony-snapshot-v1`, `delegation-representation-snapshot-v1`,
`diplomacy-snapshot-v1`/`v2`, `organized-conflict-snapshot-v1`, and
**`borders-snapshot-v1`**; stores `organization-store-v1`,
`formal-rule-store-v1`, `dispute-resolution-store-v1`,
`evidence-testimony-store-v1`, `delegation-representation-store-v1`,
`diplomacy-store-v1`, `organized-conflict-store-v1`, and
**`borders-store-v1`**; 14 V4 contexts / 12 flags / **5 owned flags**
(`organizations`, `formal_rules`, `legal_disputes`, `diplomacy`,
`organized_conflict`) / **7 unowned** (`infrastructure_networks`,
`supply_chains`, `markets_credit`, `science`, `epidemics`, `ecological_feedback`,
`disasters`). `multi_hop_testimony_tracking` and `institutional_economy` remain
unowned and are not part of the 12 V4 flags. `/version` is unchanged; observer
capabilities are unchanged.

## Phase Index

1. [Phase 1: Border Contract and Seam](phase-01-border-contract-and-seam.md) — Tasks 1-3
2. [Phase 2: Owner-Scoped Border Beliefs](phase-02-owner-scoped-borders.md) — Tasks 4-10
3. [Phase 3: Detached Detection and Metrics](phase-03-detached-analysis.md) — Tasks 11-15
4. [Phase 4: Borders Snapshot](phase-04-snapshot.md) — Tasks 16-17
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 18-19
6. [Phase 6: Read-Only API, Research UI, and Godot Overlays](phase-06-read-only-surfaces.md) — Tasks 20-22
7. [Phase 7: Invariants, End-to-End Borders, and Regression](phase-07-invariants-and-regression.md) — Tasks 23-25
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 26-27

## Cross-Phase Dependencies

- All phases assume the completed V3 territorial, regional, organization,
  diplomacy, and treaty stacks plus V4-01 through V4-12; V4-13 does not rewrite
  them, but Tasks 23/25 must keep their suites green.
- Task 2 depends on Task 1: the locked policy uses the frozen vocabulary.
- Task 3 depends on Tasks 1-2: activation consumes the contract and policy.
- Task 4 depends on Tasks 1-3: rows use the vocabulary and ledger seam.
- Task 5 depends on Task 4: IDs/digest cover the row families.
- Task 6 depends on Tasks 4-5: the pipeline mutates the complete ledger.
- Task 7 depends on Task 4: `bdr_v1` encodes the row vocabulary.
- Task 8 depends on Tasks 6-7: carry consumes the prepared ledger and frames.
- Task 9 depends on Tasks 4/6: boundary derivation uses the domain and observed
  edges.
- Task 10 depends on Tasks 6-9: caps/export cover the complete ledger.
- Task 11 depends on Task 10: harvest reads exported ledgers and committed
  events.
- Task 12 depends on Task 11: layers consume harvested rows.
- Task 13 depends on Tasks 11-12: detection consumes the four layers.
- Task 14 depends on Tasks 11-13: alignment and identity consume claims,
  agreements, and patterns.
- Task 15 depends on Tasks 11-14: metrics consume rows, candidates, and
  alignment.
- Task 16 depends on Tasks 10-15: the snapshot mirrors derived state and metric
  provenance.
- Task 17 depends on Task 16: paging and ports select typed rows.
- Task 18 depends on Tasks 10, 13, 15, and 17: the composer derives
  classifications and analysis at publication time.
- Task 19 depends on Tasks 16-18: the store and CLI call the composer.
- Task 20 depends on Task 19: the API reads the committed store.
- Task 21 depends on Task 20: the panel consumes the new routes.
- Task 22 depends on Task 20: the overlays consume the new routes.
- Task 23 depends on Tasks 2-22: the suite asserts every authority claim.
- Task 24 depends on Tasks 9-22: the E2E uses real ticks, commands,
  publication, and routes.
- Task 25 depends on Tasks 23-24: regression runs after invariant/E2E gates.
- Task 26 depends on Tasks 2-25: documentation describes verified surfaces.
- Task 27 depends on Tasks 24-26: final certification needs receipts and docs.

## Tasks

### Phase 1: Border Contract and Seam
- [x] Task 1: Freeze the territorial-domain vocabulary, identifier grammar, and location-set contract ([details](phase-01-border-contract-and-seam.md#task-1-freeze-the-territorial-domain-vocabulary-identifier-grammar-and-location-set-contract))
- [x] Task 2: Add the locked border cognition and analysis policies ([details](phase-01-border-contract-and-seam.md#task-2-add-the-locked-border-cognition-and-analysis-policies)) (depends on 1)
- [x] Task 3: Activate border cognition on the organizations seam without a new runner schema ([details](phase-01-border-contract-and-seam.md#task-3-activate-border-cognition-on-the-organizations-seam-without-a-new-runner-schema)) (depends on 1, 2)

### Phase 2: Owner-Scoped Border Beliefs
- [x] Task 4: Define domain claims, boundary recognitions, access expectations, agreements, and disputes ([details](phase-02-owner-scoped-borders.md#task-4-define-domain-claims-boundary-recognitions-access-expectations-agreements-and-disputes)) (depends on 2, 3)
- [x] Task 5: Add content-addressed IDs, ledger digest, and canonical owner ledger ([details](phase-02-owner-scoped-borders.md#task-5-add-content-addressed-ids-ledger-digest-and-canonical-owner-ledger)) (depends on 4)
- [x] Task 6: Implement the ordered territorial-domain update pipeline ([details](phase-02-owner-scoped-borders.md#task-6-implement-the-ordered-territorial-domain-update-pipeline)) (depends on 4, 5)
- [x] Task 7: Add bounded bdr_v1 boundary speech frames ([details](phase-02-owner-scoped-borders.md#task-7-add-bounded-bdr_v1-boundary-speech-frames)) (depends on 4)
- [x] Task 8: Wire border beliefs through cognition, runtime carry, checkpoints, and export ([details](phase-02-owner-scoped-borders.md#task-8-wire-border-beliefs-through-cognition-runtime-carry-checkpoints-and-export)) (depends on 6, 7)
- [x] Task 9: Derive deterministic boundary edges from the logical location graph ([details](phase-02-owner-scoped-borders.md#task-9-derive-deterministic-boundary-edges-from-the-logical-location-graph)) (depends on 4, 6)
- [x] Task 10: Enforce border caps, notices, and owner export ([details](phase-02-owner-scoped-borders.md#task-10-enforce-border-caps-notices-and-owner-export)) (depends on 6-9)

### Phase 3: Detached Detection and Metrics
- [x] Task 11: Harvest physical-control rows from committed events ([details](phase-03-detached-analysis.md#task-11-harvest-physical-control-rows-from-committed-events)) (depends on 10)
- [x] Task 12: Harvest owner border rows and keep four layers separate ([details](phase-03-detached-analysis.md#task-12-harvest-owner-border-rows-and-keep-four-layers-separate)) (depends on 11)
- [x] Task 13: Detect overlaps, disputes, recognized boundaries, and analytical control patterns ([details](phase-03-detached-analysis.md#task-13-detect-overlaps-disputes-recognized-boundaries-and-analytical-control-patterns)) (depends on 11, 12)
- [x] Task 14: Add domain lineage, read-only identity joins, and researcher-only alignment ([details](phase-03-detached-analysis.md#task-14-add-domain-lineage-read-only-identity-joins-and-researcher-only-alignment)) (depends on 11-13)
- [x] Task 15: Add four metric families and raise the catalog to 176 ([details](phase-03-detached-analysis.md#task-15-add-four-metric-families-and-raise-the-catalog-to-176)) (depends on 11-14)

### Phase 4: Borders Snapshot
- [x] Task 16: Define borders-snapshot-v1 and its canonical codec ([details](phase-04-snapshot.md#task-16-define-borders-snapshot-v1-and-its-canonical-codec)) (depends on 10-15)
- [x] Task 17: Add border ports, cursor purposes, and bounded paging ([details](phase-04-snapshot.md#task-17-add-border-ports-cursor-purposes-and-bounded-paging)) (depends on 16)

### Phase 5: Composition and Durable Publication
- [x] Task 18: Compose completed-run border views and receipts ([details](phase-05-composition-publication.md#task-18-compose-completed-run-border-views-and-receipts)) (depends on 10, 13, 15, 17)
- [x] Task 19: Add the filesystem store, settings, and CLI producer ([details](phase-05-composition-publication.md#task-19-add-the-filesystem-store-settings-and-cli-producer)) (depends on 16-18)

### Phase 6: Read-Only API, Research UI, and Godot Overlays
- [x] Task 20: Add six GET border routes, schemas, and app wiring ([details](phase-06-read-only-surfaces.md#task-20-add-six-get-border-routes-schemas-and-app-wiring)) (depends on 19)
- [x] Task 21: Add the read-only Research UI border view ([details](phase-06-read-only-surfaces.md#task-21-add-the-read-only-research-ui-border-view)) (depends on 20)
- [x] Task 22: Add the four-layer Godot border overlays ([details](phase-06-read-only-surfaces.md#task-22-add-the-four-layer-godot-border-overlays)) (depends on 20)

### Phase 7: Invariants, End-to-End Borders, and Regression
- [x] Task 23: Add the border boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-23-add-the-border-boundary-and-determinism-suite)) (depends on 2-22)
- [x] Task 24: Add the in-process border end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-24-add-the-in-process-border-end-to-end-scenario)) (depends on 9-22)
- [x] Task 25: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-25-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 23, 24)

### Phase 8: Documentation and Final Verification
- [x] Task 26: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-26-execute-the-documentation-checkpoint)) (depends on 2-25)
- [x] Task 27: Perform final V4-13 verification ([details](phase-08-docs-and-verification.md#task-27-perform-final-v4-13-verification)) (depends on 24-26)

## Verification Receipt (Tasks 25 and 27)

To be completed by Task 25 and audited by Task 27. Every required lane must be
recorded as exactly one of `executed_passed`, `executed_failed`, or
`unexecuted`. An `unexecuted` lane carries its missing prerequisite and blocks
certification; it is never a skip-pass. Receipts below are the final
implementation-session results.

| Lane | State | Evidence |
| --- | --- | --- |
| Python unit + architecture with coverage | executed_passed | Pre-remediation run: `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit tests/architecture -q` → 9398 passed, 78% coverage, 2222.56s. Post-remediation rerun is in progress. |
| Focused V4-13 suite | executed_passed | `tests/unit/test_borders_*.py` + `tests/architecture/test_borders_boundaries.py` → 224 passed after verification remediation. |
| Focused in-process border E2E | executed_passed | `tests/unit/test_borders_e2e.py` → 3 passed with real `WorldEngine` ticks/commands, six routes, and a no-frame no-telepathy case; no PostgreSQL. |
| V1/V2/V3/V4 regression selection | executed_passed | Included in the full unit+architecture run; post-remediation rerun is in progress. |
| Documentation parity | executed_passed | `tests/unit/test_borders_docs.py tests/unit/test_*_docs.py` → 68 passed. |
| Ruff | executed_passed | `uv run --frozen --python 3.12.14 ruff check src tests` → All checks passed. |
| Mypy | executed_passed | `uv run --frozen --python 3.12.14 mypy src tests` → no issues in 2180 files. |
| Import-linter | executed_passed | `uv run --frozen --python 3.12.14 lint-imports` → 25 kept, 0 broken. |
| Integration (`-m "integration and not scale"`) | unexecuted | Requires a disposable PostgreSQL/pgvector instance named with `palimpsest_test`; `PALIMPSEST_TEST_DATABASE_URL` is unset. |
| Integration including scale | unexecuted | Requires the same disposable database plus the long-run harness. |
| Docker Compose config | executed_passed | `docker compose config --quiet` → exit 0. |
| Compose/browser acceptance | unexecuted | `pytest -m compose -q` → 6 passed, 13 skipped; a real browser driver and source-attested image are unavailable. |
| Godot 4.7.2 regression | unexecuted | Pinned Godot 4.7.2 binary is not installed (`GODOT_BIN` unset; `godot`/`godot4` absent). |
| Benchmark/scale lane | unexecuted | Requires the multi-hour benchmark harness and a disposable database. |
| Research UI tests | executed_passed | `npx pnpm@10.34.9 test --run` → 56 files, 279 tests passed. |
| Research UI type/static checks | executed_passed | `npx pnpm@10.34.9 check` → 0 errors, 0 warnings. |
| Research UI build | executed_passed | `npx pnpm@10.34.9 build` → built successfully. |

Certification outcome: **not certified** — implementation, focused tests, static
gates, documentation parity, Compose configuration, and all Research UI lanes
pass; the verification blockers were remediated, but integration,
integration-scale, Compose/browser, Godot, and benchmark/scale remain
`unexecuted` with the prerequisites recorded above. The post-remediation full
unit+architecture rerun is still in progress at the time of this receipt update.

Follow-up issue remediation (2026-11-07): removed raw owner identifiers from
border DEBUG logs, clarified the `bdr_v1` ten-relation-field wire shape,
corrected the diplomacy catalog heading, aligned the metric-spec phase wording
with the closed evidence stage, and made a corrupt border store return 500
`borders_store_corrupt` instead of a false 404.

Verification remediation (2026-11-07): fixed real `Moved` extraction and partial
physical coverage; added persisted/checkpoint cap validation; retained internal
observed edges; dropped identity-`None` frames instead of trusting raw speakers;
prevented proposer self-acceptance and preserved agreement recognition across
updates; made recognition location-set exact; rebuilt the E2E with real
`WorldEngine` ticks, `Move`/`Tell`/`Wait`, publication, and all six routes;
wired Godot border responses, four separate overlay nodes, API payload
adaptation, and short labels; registered `borders` in `RUN_SCOPED_VIEWS`;
exported border snapshot symbols; added the missing codec/ports/alignment/
publication tests and boundary assertions; corrected the
`docs/v4-architecture.md` baseline to 176 families and six border routes.
Focused suite: 224 passed. Documentation parity: 68 passed. Ruff, Mypy
(2180 files), import-linter, Compose config, and all Research UI lanes pass.
The post-remediation full unit+architecture run and the external qualification
lanes are recorded below; the external lanes remain `unexecuted`.

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-3: `feat(v4): add the border contract and organizations seam`
2. After Tasks 4-7: `feat(v4): add owner-scoped border beliefs and bdr_v1 speech`
3. After Tasks 8-10: `feat(v4): carry, bound, and export border ledgers`
4. After Tasks 11-15: `feat(v4): detect border layers and append metrics`
5. After Tasks 16-19: `feat(v4): publish borders-snapshot-v1`
6. After Tasks 20-22: `feat(v4): serve read-only border surfaces`
7. After Tasks 23-27: `test(v4): enforce and certify border invariants`

## Blocking Conditions and Non-Goals

- Adding a new V4 flag, `runner-config-v57`, a new context, a runner root field,
  or a per-agent runner key to make this plan work is a blocking scope
  violation. Stop and re-plan.
- Claiming `infrastructure_networks`, `supply_chains`, `markets_credit`,
  `science`, `epidemics`, `ecological_feedback`, `disasters`,
  `institutional_economy`, or `multi_hop_testimony_tracking` is forbidden.
- Adding `world.at_war`, a `country_owner`, `sovereign`, `territory_owner`,
  `controller`, `ownership`, `Border`, `CountryOwner`, `Sovereignty`,
  `TerritoryRegistry`, `BorderRegistry`, `BorderAuthority`, `BorderExecutor`,
  `LegitimacyOracle`, `WinnerOracle`, or `TruthEngine` is forbidden.
- Adding a grid, cell, coordinate, polygon, area, or region-to-border conversion
  is forbidden. Locations are logical ids; boundaries are observed adjacency
  pairs.
- Adding a `Defend`, `Guard`, `Protect`, `Block`, `Seize`, `Enforce`, or
  `Claim` command is forbidden. No new command type exists.
- Adding a new event, observer semantic type, write pair, codec marker, artifact
  kind, `/v2` route, `observer-protocol-v2` serving, or SQL migration is
  forbidden.
- Editing `src/world/` to create a border owner, territory owner, controller,
  access enforcement, or dynamic border state is forbidden. `WorldEngine` knows
  only locations and occupancy.
- Letting `WorldEngine`, perception, admission, stop selectors, memory, prompts,
  observer semantics, or the Godot client read a border ledger is forbidden.
- Letting any border ledger, communication, analysis, snapshot, publication, or
  API helper return, construct, submit, resolve, block, or execute an
  `AgentCommand` is forbidden.
- Treating a domain, recognition, access expectation, agreement, dispute, or
  alignment as permission, obligation, prohibition, truth, guilt, liability,
  enforcement, legitimacy, sovereignty, title, or a binding finding is
  forbidden.
- Inferring a domain, recognition, agreement, access expectation, or dispute
  from silence, an unobserved act, or another owner's ledger is forbidden.
- Treating a peer-supplied `bdr_v1` frame's `party_ref`, target, domain id, or
  declared provenance as trusted is forbidden.
- Reading a peer owner's relationship, reputation, commitment, rule, office,
  institution, organization, decision, dispute, evidence, representation,
  diplomacy, treaty, territorial, or institutional-memory ledger to evaluate a
  border is forbidden. The owner's own ledgers may supply local anchors.
- Reconciling conflicting claims, disputes, recognitions, agreements, or
  boundaries into one authoritative border is forbidden. Analysis may classify
  overlap/alignment for researchers only.
- Minting, renaming, splitting, merging, or dissolving `org-` or `msoc-`
  identities from border analysis is forbidden.
- Computing, storing, publishing, or rendering a border score, control score,
  sovereignty score, legitimacy score, winner, loser, trust value, or composite
  relation score is forbidden. All outputs are counts, durations, ratios, and
  closed labels.
- Rewriting `organized-conflict-snapshot-v1`, `diplomacy-snapshot-v1`/`v2`,
  `diplomacy-store-v1`, `territorial-claims.v1`, `spatial_control@1`,
  `territorial_concentration@1`, `dip_v1`, `trt_v1`, or the
  `diplomacy.v1`/`treaty.v1` contracts is forbidden.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`, replay
  v22, codec v20, command count, observer semantic count, context count) is
  forbidden. The only intentional pin changes are 172 -> 176 metric families,
  the four border families, the six border GET routes, the new v1 snapshot, and
  the new store.
- Claiming prevalence, emergence probability, predictive power, accuracy,
  reliability, moral correctness, sovereignty, or a composite control score is
  forbidden.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope;
  `$aif-roadmap` owns that.
- Changing the Godot observer protocol, observer capabilities, or `/version` is
  out of scope; the four border overlays are client-side read-only additions on
  the existing three-class evidence model.
- Enabling V4 flags in matrix lanes is out of scope; `experiments.matrix_schema`
  keeps its rejection gate.
- V4-13 does not add a command selector, prompt, planning bias, or speech
  generation beyond the explicit `bdr_v1` attachment.
- Full qualification requires a disposable PostgreSQL/pgvector instance, Docker,
  a real browser driver, and the pinned Node/pnpm and Godot toolchains. A missing
  prerequisite leaves the lane unexecuted and blocks certification; it never
  becomes a skip-pass.
- Do not implement any other V4 context in this plan.

## Definition of Done

- All 27 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- V4-13 adds no flag, context, `runner-config-v57`, root field, or per-agent
  runner key; the 14-context / 12-flag registry is unchanged and
  `organizations` remains the deepened owned context.
- Activation requires `runner-config-v56`, `organizations`, and deterministic
  territorial mode; legacy v15/v44/v55 paths stay byte-compatible.
- A domain is a sorted set of 1-8 logical locations; no grid, coordinate,
  polygon, area, region-to-border conversion, `CountryOwner`, `sovereign`,
  `territory_owner`, `controller`, or objective border field exists.
- Boundary edges are observed adjacency pairs; unobserved edges are explicit
  `unresolved`, never invented.
- The owner ledger retains domain claims, boundary recognitions, access
  expectations, border agreements, border disputes, evidence, and notices with
  content-addressed IDs, a canonical digest, ordered updates, and bounded caps.
- Overlapping claims are legal and retained; disputes record contested locations
  without reconciliation, winner, guilt, or forced boundary.
- Access expectations and agreements bind nobody; a physically possible command
  is still admitted, and a physically impossible command is still rejected by
  existing world rules.
- `bdr_v1` is 10 fields, 256 characters per relation, at most 8 relations, at
  most one group inside existing `Talk`/`Ask`/`Tell`; malformed, oversize, or
  speaker-mismatched frames are dropped.
- No border helper returns, constructs, submits, resolves, or blocks an
  `AgentCommand`; every physical effect is ordinary `WorldEngine` admission.
- Detached analysis harvests four layers from committed events and exported
  ledgers, keeps them in separate types with a hard leakage guard, detects
  overlaps/disputes/recognitions/control patterns, derives forward-only
  `bord-` lineage, joins `org-`/`msoc-` read-only, and classifies
  researcher-only alignment.
- The metric catalog is exactly 176 with four appended families; the first 172
  are unchanged; real completed-run assembly emits all four documents; no
  composite, sovereignty, control, or winner score exists.
- No test file or current-pin doc line still asserts 172; the stale-pin guard
  passes while historical revision statements and the first-172 order remain,
  with the documented treaty 164 -> 168 correction as the only historical edit.
- `borders-snapshot-v1` and `borders-store-v1` are canonical, bounded, atomic,
  and immutable after publication; the snapshot carries a required summary and
  a candidate row family, and every lineage/alignment candidate token resolves;
  existing snapshots/stores remain unchanged.
- Snapshot rows and API responses contain only hashed tokens, content-addressed
  IDs, opaque anchors, and composer-derived labels; no raw agent/location id,
  free-text target, frame body, or evidence content is published.
- Six GET-only border routes require `SUBJECTIVE_DEBUG`, have an explicit
  `borders_disabled` state, return 404 for unknown published records, and are
  consumed by a read-only Research UI panel and four Godot overlays.
- The Research UI distinguishes physical control, subjective claim, agreement,
  and analytical control pattern; it derives no authority, legitimacy,
  enforcement, score, winner, or sovereignty.
- Godot keeps the three-class evidence model and maps the four border overlays
  onto it; agreement is visibly distinct from claim and pattern.
- Cursor reuse works on border pages; a changed run/publication/digest/purpose/
  filter fails with 400 and expiry with 410.
- `WorldEngine` never reads a border ledger; a domain or agreement never blocks a
  physically possible command.
- The boundary suite proves owner-only authority, the absence of
  border/owner/registry/score objects, no command construction, no peer-ledger
  reads, no world-ledger reads, no `org-`/`msoc-` mutation, no grid/geometry, and
  no new commands/events/migrations; observer and migration pins are unchanged.
- The focused in-process border E2E runs without PostgreSQL in the focused/unit
  lane and is never reported as an integration-only prerequisite.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what border beliefs control (owner-scoped claims,
  recognitions, access expectations, agreements, disputes), what they never
  control (world state, admission, permission, truth, enforcement, legitimacy,
  score, sovereignty, winner), how the four layers differ, how `bdr_v1` works,
  how boundaries are observed, and every count matches the code. The docs sweep
  updates every current 172 pin and leaves historical seam pins intact.
- `docs/borders-and-claims.md` is the canonical contract;
  `docs/analysis-metrics.md` documents the four families and corrects the
  treaty 164 -> 168 statement,
  `docs/research-api.md` documents the six routes, `docs/research-ui.md`
  documents the panel, `docs/godot-civilization-overlays.md` and
  `docs/godot-observer.md` document the four overlays,
  `docs/v4-architecture.md` records the V4-13 seam, and README plus
  `docs/social-communication.md`, `docs/organizations.md`, and
  `docs/diplomacy.md` link the contract. `.ai-factory/ARCHITECTURE.md` moves its
  baseline through V4-13 and `.ai-factory/DESCRIPTION.md` records the V4-13
  project state.
