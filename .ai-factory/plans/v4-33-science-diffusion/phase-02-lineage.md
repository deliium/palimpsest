# Phase 2: Attribute carriers and derive diffusion lineage

Plan: [index.md](index.md)  
Tasks: 3–5  
Depends on: Phase 1

## Objective

Report how hypotheses and model representations travel while distinguishing delivery, reading, adoption, local derivation and context.

## Current-Code Evidence

| Path | Existing seam |
|---|---|
| `src/agents/cognition/scientific_hypothesis_communication.py` | `parse_scientific_hypothesis_claim_relation`, `adopt_communicated_hypothesis`; native `hyp_v1` lacks conditions and does not forward adopted hypotheses automatically. |
| `src/agents/cognition/teaching.py`, `src/agents/cognition/artifacts.py`, `src/agents/cognition/translation.py` | `record_teaching`, `ArtifactInterpretation`, `TranslationApplication` retain exact owner evidence; generic audits lose relevant refs. |
| `src/agents/cognition/practical_knowledge.py`, `src/analysis/knowledge_genealogy.py` | Written refs use `artifact:`/`durable:`; `build_qualified_knowledge_lineage` qualifies owners but peer links can be inferred. |
| `src/analysis/macro_society_detection.py`, `src/analysis/macro_society_identity.py`, `src/experiments/scientific_institutions_context.py` | Window-local candidates, `record_at`, exact organization contributors and expiry. Endpoint maps are not historical membership. |
| `src/analysis/regional_population.py`, `src/simulation/lineage_objective.py` | `fold_regional_history` distinguishes arrival from qualification; `extract_record_source_events` preserves copies and revisions. |

## Files to Change

| Path | Action | Responsibility |
|---|---|---|
| `src/experiments/science_diffusion_carriers.py` | Create | Decode committed speech and artifact references, qualify context against boundary evidence. |
| `src/experiments/science_diffusion_genealogy.py` | Create | Explicit V3 bridge and context joins; no transitive guessing. |
| `src/experiments/scientific_institutions_context.py` | Modify | Extract reusable detached organization evidence/attribution helpers without changing V4-32 output. |
| `src/analysis/science_diffusion_lineage.py` | Create | Deterministic links and trajectory classifications over neutral rows. |
| `tests/unit/test_science_diffusion_carriers.py`, `tests/unit/test_science_diffusion_genealogy.py`, `tests/unit/test_science_diffusion_lineage.py` | Create | Positive and negative evidence tests for every lane and transformation. |

## Task 3: Project speech, teaching and records

1. Consume actual addressed `Talked`/`Told`; reject sender echoes, broadcasts without a single qualified recipient, malformed markers and unresolved owners. For `hyp_v1`, match `SOURCE_ADOPTED` via `evt:<event_id>` and the addressed recipient, preserving an exposure without adoption when local ID already existed. Attribute source only to a unique sender version retained before delivery whose **wire** fields match; unchanged confidence is not required, unwired conditions remain unknown. A model `source_refs` link to that adopted hypothesis is a new local derivation, not a copied model.
2. Introduce an opt-in research carrier marker `sdf_v1` in ordinary relations, not a new command or a runtime policy. Use `(sdf_v1, source_a, a<26>)` / `(sdf_v1, source_b, b<26>)`: split the 52 characters of unpadded lowercase base32 SHA-256 of the canonical qualified source-version key after 26 characters. Optional `variant_a`/`variant_b` encode another **qualified version key**, not a content-only digest; require the same owner, kind and local ID, a greater revision index, and both endpoints known before transmission. Optional `prior_a`/`prior_b` encode a domain-separated qualified receipt key `(run, carrier kind, occurrence or artifact revision, recipient)` for relay. Exactly one group per frame; reject missing halves, duplicate predicates, unknown `sdf_v1` predicates and noncanonical round trips; all tokens fit `ArtifactRelation`'s 32-character limit. Keep `call_a`/`call_b` speech-only, with the same split encoding.
3. For a first hop resolve the author's exact prior version; for an explicit relay require the sender/inscriber to be the recipient/reader of the exact earlier confirmed receipt and the marker to carry its unchanged source and variant. Resolve earlier hops before later ones; no silent relay from a shared hash, a same-tick unresolved read, or a missing/ambiguous parent. Physical copies preserve their origin via the committed copy evidence and a verified intact marker, not via an inferred reader. A relay edge proves retransmission, not ownership or model uptake. Missing provenance leaves an unverified reference; no automatic marker writing/learning in ordinary runs.
4. Teaching requires the same addressed science-bearing occurrence plus an actual recipient `DeclarativeAdvice` occurrence (use the same event-ID conversion as `record_teaching`). A generic teaching event or competence snapshot cannot label a science link. Record exposure requires a recipient `ArtifactInterpretation` of the exact instance/revision and verified as-of physical content; preserve unread deposits, copies, lost fragments, and readings as separate evidence. An interpreted marker that is missing or mismatched on a distorted reading is `partial_read`/`divergent_read` only if the original marker and relevant difference are both witnessed. Retrieval, survival or author inference alone does not establish a reading or adoption.

### Errors, tests, and acceptance

Expose `unverified_reference`, `ambiguous_source`, `unaddressed`, `marker_incomplete`, `relay_parent_missing`, `record_revision_missing` as closed exclusions; never log marker content, full events, or frame digests. Test native claim adoption/no-op, teaching exact and same-tick unrelated advice, valid and invalid publication of a model ref, two-hop speech-to-record relay, unaddressed relay/changed variant/forward parent, original/copy instance lineage, amendment, destruction, reading without uptake, malformed split digest, and preserved pre-destruction reads. Requirements: original request (teaching and records), architecture §§ “Memory, testimony, and subjective concepts” and V4 science seams.

**Verification:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_science_diffusion_carriers.py -q`.

## Task 4: Join V3 genealogy, organizations, migration and cross-society context

1. Bridge only typed exact refs: same recipient and exact `teach:<occurrence>` matching retained `DeclarativeAdvice.occurrence_id`, or same recipient with `artifact:`/`durable:` instance reference plus a compatible as-of interpretation revision at acquisition. Use `knowledge_genealogy_harvest_from_run` and `build_qualified_knowledge_lineage` for V3 interpretation and retain the existing origin (`teaching`, `written_record`, `reconstruction`, etc.). Prefilter audit observation tick **before** latest-row normalization; obtain exact refs from owner entries rather than audit rows. If competing revisions or roots exist, emit one ambiguity diagnosis, not multiple fabricated parents. Output an evidence link to the existing V3 node; never rewrite the V3 graph or equate `tech:` with a hypothesis/model ID.
2. The V4-32 `build_scientific_institution_context` expects full boundaries and is not a diffusion input. Extract narrow helpers for owner/member projection, expiry and typed service witnesses from `scientific_institutions_context.py`; call them while the current finalized boundary is in hand, retaining only bounded neutral rows and absolute complete `[32k,32(k+1))` windows. Use `detect_organization_candidates_with_contributors` and forward identity assignment over the available prefix, retaining exact contributor keys and expiry. At occurrence `t`, use the latest complete window with `end <= t` and `t - end <= 32`; require the unique candidate, unexpired applicable contributor and exact prior service on the same still-qualified carrier instance for `organization_mediated`. Shared membership alone is `shared_org_context`. Keep the V4-32 output byte-stable.
3. For societies, assemble fixed absolute 32-tick windows from objective edge producers used in `macro_society_completed_run.py`, without using its completed-run wrapper that widens/drops windows and densifies indices. Run `detect_macro_society_candidates` then `assign_macro_society_identities` using completed evidence only; map internal indices back to explicit ranges and preserve empty and incomplete windows in diffusion coverage. Require both owners uniquely and unambiguously assigned to different disjoint candidates in the same latest eligible window as above. Use `record_at` for the forward identity, never endpoint membership or delivery itself to infer the crossing.
4. Migration creates `carried_across_region` only for the same owner/version witnessed at departure and arrival and a real arrival that later qualifies through `fold_regional_history`. Use real journey ID where applicable; pair direct movements to their own event and exclude timeout, death in transit and merely pending movement. Confirm at `qualified_boundary`, not arrival. Delivery before qualification has no migration-mediated label; later delivery additionally requires sender in destination as of delivery. Adoption remains its own edge; co-presence is context only.
5. The translation ledger records a message and mapping, not a relation index. Require a unique symbolic `call` triple identified by the canonical triple digest in `call_a`/`call_b` and a unique source **constituent occurrence** in the utterance using the existing `translation_source_digest`; if the same source part can resolve in another eligible triple or slot, report ambiguity. Match exactly one addressed-owner application by real message ID and mapping ID/source digest, with selected target binding witnessed as of application for `applied`. `ambiguous` outcomes report ambiguity, not use. Require a same or earlier retained mapping/binding snapshot; don't use endpoint state to fill historical fields. Say “translation used on linked representation,” not translation of the full hypothesis/model or semantic equivalence. Context flags are nonadditive.

### Errors, tests, and acceptance

Use reason codes `genealogy_anchor_missing`, `membership_unknown`, `overlapping_membership`, `unqualified_arrival`, `translation_unbound`; debug counts only. Tests cover exact and guessed genealogy links, copy revisions, future audit, donor/recipient mismatch, expiry/overlap, movement alone, qualified transport with subsequent delivery, exact targeted mapping, and unrelated same-message translation. Requirements: original request (V3/V4 bridge and contextual channels); architecture § “Important V3 seams.”

**Verification:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_science_diffusion_genealogy.py tests/unit/test_science_diffusion_carriers.py -q`.

## Task 5: Fold trajectory changes, loss and rediscovery

1. Expose `derive_science_diffusion(inputs) -> DiffusionAssessment`. Produce forward evidence edges keyed by run, endpoints, closed edge kind, and first confirming witness; repeated exposure stays separately countable while each adoption/revision edge is deduplicated. Order by causal evidence, never fabricate an order from hashes. Reject backward/cyclic exact edges. Keep distinct normalized stages `delivered`, `interpreted`, `adopted`, `locally_derived`, `reported_reference` and `carried`. Mixed or ambiguous channels annotate the one occurrence.
2. `mutation`: a confirmed predecessor and subsequent science revision or verified explicit transmitted variant with a comparable changed field (report field category, not content). `misunderstanding_signal`: a divergent initial reading/adoption against a known comparable delivered field, or a positively recorded partial/distorted reading of the exact marker; label observed divergence, never mental intent. Malformed solicitations, nonresponses, confidence-only edits and unwired conditions are not misunderstanding. A faithful translation can coexist with no mutation; a changed representation needs a positive difference witness regardless of translation.
3. `local_loss`: explicit owner retirement (`HypothesisStatus.RETIRED` or `ModelLifecycle.RETIRED` paired with an observed transition), or exact physical carrier destruction/verified marker removal; distinguish scopes. Track a universe of all owner/version states and physical instances with observed paths from the lineage root; new verified successors join this universe. Supersession with a known successor is a revision edge, not loss. For `observed_lineage_loss`, start only after an explicit positive loss and require two adjacent complete absolute 32-tick windows, both starting after the witness boundary (or exactly at it), with all known holders and instances explicitly ended; unknown last state, eviction, or death alone never closes an entry. Require complete science/speech/record coverage for these windows and restart after a gap only using a new positive post-gap loss witness. Confirm at the second window end; never claim global extinction. `reacquired` requires exact linked uptake after confirmation. For `independent_rediscovery`, require a new owner/version of the same kind and exact complete comparable descriptor after confirmation, a distinct affirmative committed local root evidenced at formation, and complete prior owner lifetime coverage of speech, teaching, records, and science through formation. A lane known disabled for its full interval contributes no possible exposure only when its underlying carrier is also proven inactive; missing/partial/ambiguous or unrooted rows yield `origin_unresolved`. Reappearance after gaps or shared roots is not rediscovery; independently rooted matches without prior loss are convergence candidates only.

### Errors, tests, and acceptance

Log outcome counts and reject impossible temporal inputs without printing identifiers derived from content. Test replay/permutation stability, confidence-only change, witnessed mutation and misunderstanding, loss confirmation, a lost record with a surviving copy, gaps, independent root, shared root, and transmitted reacquisition. Property test that removing coverage never increases confirmed loss, cross-society, or independent rediscovery for fixed witnesses. Requirements: original request (all five transformations); V4-32 architecture § “Scientific-institutions seam” (non-backdating and no gap bridging).

**Verification:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_science_diffusion_lineage.py -q`.

## Phase Risks and Mitigations

- Many ordinary runs lack exact provenance. Report the observed carrier and its unresolved lineage rather than treating missing evidence as a null uptake or manufacturing a scientific pathway.

## Phase Completion Checklist

- Verify each carrier, V3 bridge and transformation; update progress only in `index.md`.
