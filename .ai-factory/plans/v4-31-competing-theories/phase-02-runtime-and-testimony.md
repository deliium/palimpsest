# Phase 2: Runtime and testimony

Plan: [index.md](index.md)  
Tasks: 3–4  
Depends on: Phase 1 / Tasks 1–2

## Objective

Track attributed support, cited testimony and teaching in the existing cognitive tick, with deterministic finalization and no new world action.

## Current-Code Evidence

| Path | Symbols / contract | Why it matters |
|---|---|---|
| `src/agents/cognition/loop.py` | `CognitiveLoop.complete`, `advance_scientific_models` call, final `Talk`/`Tell` extension block | Owner observations and command attachment already have ordering |
| `src/agents/cognition/replication_communication.py`, `teaching.py` | `ingest_replication_communication`, `attach_replication_message`, teaching uptake | Distinguish receiver receipt, sender echo, learning and attempt |
| `src/simulation/agent_runtime.py`, `runner.py` | `bind_effective_command`, `finalize_pending`, `export_scientific_model_ledgers` | Arbitration, pending commit, checkpoints, and completed-run export |
| `src/simulation/run_control.py`, `runner_serialization.py`, `scientific_model_checkpoint.py`, `fork_checkpoint.py` | `FinalizationCommand`, exact keysets, canonical sidecar, `fork_state_digest` | Strict legacy compatibility |
| `src/simulation/persistence.py`, `runner.py` | `PENDING_FINALIZATION_ACCEPTED_VERSIONS`, recovery decoder | Separate acceptance gate currently omits v4 |
| `src/world/observations.py`, `src/world/_perception.py` | `ObservedCommunication`, `_project_communication` | Speaker/listener/occurrence are verified; declared transmission is testimony |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/agents/cognition/competing_theory_communication.py`, `competing_theory_policy.py` | Create | Bounded speech and deterministic local transitions |
| `src/agents/cognition/loop.py`, `src/agents/cognition/models.py`; `src/simulation/agent_runtime.py`, `src/simulation/run_control.py` | Modify following `scientific_model_ledger` field | Candidate attachment, owner-safe input/result, commit and restore |
| `src/simulation/competing_theory_checkpoint.py` | Create | Canonical strict theory leaf |
| `src/simulation/runner_serialization.py`, `src/simulation/fork_checkpoint.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/simulation/persistence.py` | Modify | Explicit pending schema and recovery allowlist, fork digest and frozen exports |
| `src/simulation/new_agent_initialization.py`, `src/experiments/civilization_benchmark_evidence.py`, `tests/unit/test_new_agent_blank_slate_guard.py` | Modify | Add the same theory store to admission, content counters and probes |
| `tests/unit/test_competing_theories_social.py`, `test_competing_theories_recovery.py`; `tests/architecture/test_competing_theories_boundaries.py` | Create | Test actual observation paths and recovery guarantees |

## Task 3: Track support, communication, and teaching

### Intent

Allow community divergence and transmission through existing addressed speech, without inferring consensus, objective knowledge, or truth.

### Implementation Steps

1. Implement distinct `thy_v1` with exactly two `CommunicationRelation` triples in the same `Talk`/`Tell` utterance (subject `thy_v1`, predicates `claim` then `context`, max 256 characters per object, max 32 relations for the whole utterance). Header version/act/target/account/category/origin season; context part location/resource kind/unit and at most one optional `(cited_root_token, polarity)` pair. Use canonical percent-escaped UTF-8 fields with `|` separator, strict decode/re-encode equality, no free text; reject extra, inverted or duplicate `thy_v1` parts without consuming other namespaces. Encode local context only if it fits; do not truncate. Derive claim ID, never accept it or speaker/recipient as payload. Acts: `share`, `support`, `withdraw`, `teach`. Reuse only verified observation fields for delivery provenance; a declared cited token must never be interpreted as a validated foreign reference. No malformed payload suppresses normal speech.
2. In `CognitiveLoop.complete` after `advance_scientific_models`, run `advance_competing_theories` on the previous committed ledger and owner observation. Resolve already-due cases from terminal transitions in the new science candidate; derive local claims from the frozen current case or prior-owned settled outcome; ingest only prior committed, addressed `ObservedCommunication`, sorted by occurrence and deduped by `(event_id, speaker, recipient, claim_id, act)`. Sender echoes are not learner evidence. Record speaker support/withdraw as attributed receipts; withdrawals apply only to the matching speaker’s claim. Only eligible recipient receipt proves delivery. `teach` records teacher→learner, explanation and optional cited pointer; receipt/acquisition of a previously unknown claim is distinct from later support. Duplicate instruction cannot create a second acquisition or observed corroboration; teaching does not grant practical skill.
3. Local stance policy: when owner has no active stance for a context, first consider any known claim with addressed `support` from at least two distinct speakers in prior committed ticks, excluding the owner; if none qualifies, adopt the owner's locally originated account through the one-time deterministic prior in step 4. Count only observed origin declarations (hop zero; use envelope communication ID, or observed occurrence for an origin with no declared lineage), deduplicated by speaker and origin. Retellings remain receipts but cannot count toward the threshold; do not validate an ultimate declared root as objective fact. A claimed citation root is separate and never determines endorsement identity. For an existing stance apply the same social threshold to rivals and switch only if their latest live qualifying endorsements strictly exceed the current claim's count; ties keep current stance, and ties among top alternatives mean no change. Choose at most one change per context per tick and append own support/withdraw records; a single delivery or teaching event is never itself a stance. A switch implicitly withdraws that owner's prior same-context stance, both locally and for a verified recipient processing later original support by that same actor; retain the old social record. Only original withdrawals can supersede an original support. Do not consult scores, failure, forecast confidence, researcher group identity, or global counts. At capacity require all rows necessary for a switch before committing it. Issue the new forecast bundle after these steps, using matching claims, **not** stance.
4. On an owner's first discovery of a locally derived rival in a context, permit one founding preference revision before social switching: hash `competing-theories-prior-v1` plus length-prefixed owner ID and canonical context, and use the low bit of the first digest byte to choose continuity (0) or the first locally derived recurrence (1). This is a deterministic subjective prior, not a score, group assignment, or global choice. Persist the consumed marker even if no switch is needed; consume only after the compound transition fits. Apply only when that context has no qualifying social alternative, and never reapply after consumption. This provides originating supporters on both sides without requiring propagation to create the first dissenter. Append speech last in existing `Talk`/`Tell` decorators, only when the combined utterance passes the existing budget and already has an addressed receiver. Preserve verb, target, tone and existing relations; never replace any action. Traverse supported claims in descending `(stance_tick, claim_id)` order and take the first fitting undelivered act: first tell that recipient `support`, next `teach` if an owned cited root exists, otherwise continue. Suppress repeats using committed matching sender echo, keyed by `(recipient, stance_revision, act)` with the echo correlated to its original send tick; record sender echo separately from canonical recipient receipts. Denied/replaced commands cannot count as delivery or suppress retry. `share` and `withdraw` are accepted verified acts; runtime auto-announcement is limited to support/teach, with a subsequent support superseding old stance. Saturate refusal coverage, but duplicates are no-ops.

### Required Interfaces and Contracts

`decode_theory_message` runs on the ordinary delivered view, never stores `WorldEvent`; `attach_theory_message` accepts/returns the same command type. `advance_competing_theories` is a pure, one-observation transition. No invented school roster, global truth/majority ballot, command type, objective teaching event, or another owner's ledger read.

- Read `ObservedCommunication.speaker_id`, `.listener_id`, `.provenance.source_event_id` and `.provenance.source_tick` from the observation projection, mapping the owner to `Observation.self_body.entity_id`. Require a prior tick and a concrete event ID; exclude private bystanders and `ask`. Hop zero is a declared-origin shape, not verification of lineage; require the immediate source to match the observed speaker and count that speaker at most once per context. Distinguish outcome citations from this attribution filter.
- Resolve previously pending cases first. Derive only from first-seen settled base outcomes and the current issued base case: compare against the preceding committed V4-30 ledger rather than rescanning the terminal history every tick; use the original pre-transition owner case if needed for the bound context. Then ingest addressed/echo rows, choose at most one stance change, and issue the new case under the strict prior cutoff in Task 2. For a context with a qualifying social switch, that switch takes precedence and consumes first-rival founding eligibility for that context; otherwise apply the one-time founding rule. Announce only a stance already committed at tick start. For `teach`, choose the newest retained owned citation for that stance by `(source_tick, citation_id)` and carry its pointer, not its underlying observation.
- The runner calls `CognitiveLoop.complete` on the arbiter's selected command inside `AgentRuntime.bind_effective_command`; that method must submit `require_agent_command(loop_result.command)`. Never attach during `prepare`, never decorate a replaced `Wait`, and never infer success from the attachment. Record a bounded outbound correlation only from the final submitted frame (send tick, observed body/recipient, stance revision, act, canonical frame digest); match the next committed sender echo by these values. Pending recovery preserves that correlation and does not reattach speech. A correlation without an echo expires after the next observation boundary without suppressing a retry; only addressed receiver observations become detached delivery rows.

### Requirement Evidence

`index.md` Original Request: communication, teaching, support networks and popularity diverging from accuracy. `.ai-factory/ARCHITECTURE.md` “Memory, testimony, and subjective concepts”: delivery and opaque provenance only.

### Error Handling and Logging

Absent, unaddressed, malformed, over-budget and sender-only communication are non-uptake paths. DEBUG metadata counts by act/reason only; never log claim fields, speech, cited roots, or transcript fragments.

### Tests

`test_competing_theories_social.py`: verified receiver and echo; private bystander; malformed sibling and full budget; denied/arbiter replacement vs actual delivery; two origin speakers vs repeated/retold source; late and duplicated teaching; switch with failure history preserved; prior stance only on outbound frame; valid evidence citation vs declared pointer; different recipients converge on different rivals. Task 8 asserts the same attached frame in the actual submission, committed observation and exported receipt, not only loop output.

### Acceptance Criteria and Verification

Matching addressed teaching and support produce distinct records; arbitrary utterances and hits do not create support. `uv run --frozen --python 3.12.14 pytest -q tests/unit/test_competing_theories_social.py` passes.

## Task 4: Integrate finalization and recovery

### Intent

Make the sidecar persistent wherever committed model state already is, without widening any existing wire schema.

### Implementation Steps

1. Reuse the exact science/model enablement predicate in `CognitiveLoop`. Carry a nullable candidate on result and owner subjective snapshot, validating exact type and owner. Restore the committed ledger only from the owner's checkpoint; science-off does not allocate/export it. Build it detached; after arbitration re-evaluate attachment only for metadata if needed, never edit the effective command. Objective tick abort discards the candidate. Normal and pending recovery both install the same already-staged immutable ledger once; no cognition or new testimony re-ingest on recovery.
2. Add `competing-theory-state-v1` with canonical keysets, limits, owner/context, reference closure and monotone tick validation. Extend `FinalizationCommand` and `runner_serialization.py` with exactly `finalization-command-v5` = v4 payload + mandatory non-null `competing_theory_ledger`; keep all v4 science/replication/measurement correlations. v1–v4 reject the extra field but decode prior exact payloads unchanged. Legacy checkpoint absence means empty lazily when science next executes; absence does not regenerate historical claims. Stage v5 only when a theory candidate exists; preserve default pending v1.
3. Follow the existing `scientific_model_ledger` checkpoint/snapshot plumbing under `src/simulation` (find each call site before edits); add populated-state rejection to `runner.py` admission guard, conditional leaf digest in `fork_state_digest` that leaves absent bytes unchanged, and owner-sorted active/retired `SimulationRunnerResult.competing_theory_ledgers`. Do not add data to persisted public runner-result documents, world replay or SQL. Forks share immutable prefix only and can diverge independently.
4. Close the real recovery gate: extend `PENDING_FINALIZATION_ACCEPTED_VERSIONS` in `src/simulation/persistence.py` to v1–v5 (v4 is already encoded and decoded but rejected by `_decode_pending_record` today). In runner recovery require record and embedded codec/run/owner/tick/invocation/integrity identity to agree before installing the sidecar. Extend the runtime's candidate digest with the canonical theory leaf only for v5; keep unmodified v1–v4 hash inputs. Exercise durable-commit-before-finalize interruption through the runner's repository path, then recover twice and check the exact staged ledger and non-duplication.
5. Add `competing_theory_ledger` to `SUBJECTIVE_COPY_DENY_LIST`, `BLANK_SLATE_SUBJECTIVE_STORES`, `BlankSlateStoreCounts`, `runner.py` content-count assembly and benchmark `STORE_PROBE_PATHS` (checkpoint field). Define an explicit semantic content count: an empty typed sidecar is zero, headers alone do not count, and claims/stances/history/correlations/coverage do. Use the same counter for admission and benchmark probing and update the pinned tuple test.

### Required Interfaces and Contracts

Owner-only leaf, strict `decode_competing_theory_state`/`encode_competing_theory_state`, absent-state legacy digest invariant, byte-identical v1–v4 encoding, new v5 only when activated state exists. Reuse existing failure taxonomy and value-size bounds (plan cap is a count maximum, not permission to exceed the containing byte limit).

### Requirement Evidence

`.ai-factory/ARCHITECTURE.md` “Requirements for later changes”; `docs/scientific-models.md` “Recovery and exports”.

### Error Handling and Logging

Malformed or foreign pending artifacts fail closed with path-safe codes; do not downgrade to v4 on corrupt v5. DEBUG logs may give commit kind, schema version and row counts only.

### Tests

`test_competing_theories_recovery.py`: explicit legacy v1–v4 fixture round trips; real outbox restart accepts old v4 and v5 with/without measurements; rejects mismatched envelope and tampered candidate digest; abort, replacement, retry, duplicate finalization, independent forks, retired export and exact no-science digest parity. `test_new_agent_blank_slate_guard.py`: populated, empty typed and absent probes; `test_competing_theories_boundaries.py`: authority/import/command invariants and no access to peer state.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest -q tests/unit/test_competing_theories_recovery.py tests/architecture/test_competing_theories_boundaries.py tests/unit/test_scientific_models_checkpoint.py tests/unit/test_scientific_models_recovery.py` passes without weakening legacy assertions.

## Phase Risks and Mitigations

- Interference with other science speech: use a distinct subject and append last, without stripping or retrying other relations.
- Counting delivery twice: canonicalize from receiver evidence; sender echo cannot create an extra network edge.

## Phase Completion Checklist

- Delivery, recovery and isolation cases pass.
- Update only the Task 3–4 checkboxes in `index.md`.
