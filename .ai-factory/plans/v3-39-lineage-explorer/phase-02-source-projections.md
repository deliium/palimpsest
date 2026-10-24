# Phase 2: Objective and owner-local source projections

Plan: [index.md](index.md)  
Tasks: 3–4  
Depends on: Tasks 1–2

## Objective
Normalize existing evidence without introducing new genealogy, learning, narrative, or office behavior.

## Current-Code Evidence

| Path | Symbols | Relevance |
|---|---|---|
| `src/world/kinship.py` | `KinshipGraph`, `stable_kinship_edge_id`, `descendants_of` | Objective parent→child DAG, death-stable edges, maximum depth 32. |
| `src/simulation/inspection.py` | `DetachedInspectionProjector.project_kinship`, `query_kinship` | Existing detached kinship projection. |
| `src/world/artifacts.py` | `InformationArtifact`, `RecordIntegrity` | Physical copy parents, revisions and damage; not meaning/truth. |
| `src/agents/cognition/mentorship.py` | `MentorshipLedger`, `TaughtContentLineageEntry` | Learner-owned lineage, first teaching hop zero, learning evidence distinct from attempts. |
| `src/agents/cognition/mentorship.py` | `MentorshipAudit` versus `TaughtContentLineageEntry` | Audit summaries omit content/root/parent/lineage IDs; detailed chain publication must use safe entry metadata. |
| `src/agents/cognition/practical_knowledge.py` | `PracticalKnowledgeLedger`, `SubjectivePracticalKnowledge` | Owner-local parents, source/teacher references, capability anchors. |
| `src/agents/cognition/offices.py` | `OfficeConceptLedger`, `OfficeSuccessionRecord` | Stable local role separate from changing or disputed occupants. |
| `src/observer/narrative_hops.py` | `project_narrative_hop_overlay` | Safe field selection reference only; simulation must not import observer. |

## Files to Change
Create `src/simulation/lineage_objective.py`, `src/simulation/lineage_subjective.py`, `tests/unit/test_lineage_objective_sources.py`, and `tests/unit/test_lineage_subjective_sources.py`. Modify `src/simulation/lineage_ports.py` for typed normalized source records only. Source domain policies remain unchanged.

## Task 3: Project genealogy and physical record ancestry

### Intent / Implementation Steps
1. Add pure `project_genealogy_lineage` over detached kinship edges and body/lifecycle facts at B; preserve native edge IDs and established ticks. Produce `parent_of` edges and agent nodes with living status at B. Birth/death facts cannot be inferred from absence from a selected roster.
2. Add pure `project_record_lineage` over snapshot artifact metadata plus bounded, ordered event detail records. Use `copied_from` for actual source→copy ancestry. Preserve annotation, damage, loss, destruction and custody as node revision/status evidence, not invented copy edges.
3. Keep destroyed artifacts as retained historical nodes/tombstones when their identity is evidenced. Missing parents become unresolved stubs. Unknown integrity is not intact. Marks, titles and free-form text are excluded.
4. Define source frame extraction in simulation, using public snapshot/inspection contracts. Persistence must not import private world authority or `world` directly. No call to mutable `observe()` or engine admission during queries.
5. Validate boundary before projecting; do not use later death/destruction events for earlier snapshots. Reuse event schema decoding rather than parsing JSON by guessed field names.

### Required Interfaces and Contracts
Inputs are bounded tuples of typed detached source records plus B and activation/coverage. Outputs are normalized node/edge batches plus source coverage. Disabled channel and enabled-empty graph differ. `living_only` later retains traversal through dead nodes. Relationship semantics never imply affection, rights, truth, or inheritance law.

### Requirement Evidence
User questions about Alice's descendants and record lineage; `world/kinship.py` objective contract; `.ai-factory/ARCHITECTURE.md` Important V3 seams.

### Error Handling and Logging
Conflicting native IDs or future facts fail the publication. Missing evidenced parents are stubs, not exceptions. Log source row/count/activation codes only.

### Tests / Acceptance / Verification
In `test_lineage_objective_sources.py`: two-parent DAG, dead intermediate parent with living grandchild, no future newborn at B, initial B=0 edges, record copy chain/branch, damaged copy, destroyed ancestor, missing source, disabled versus empty. Cross-check small graphs against public kinship query results and use real `InformationArtifact`/kinship constructors from existing tests, not handcrafted output JSON.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_objective_sources.py tests/unit/test_kinship_death_persistence.py tests/unit/test_durable_record_harvest.py --cov=simulation --cov-report=term-missing -q`. Acceptance: projected ancestry agrees with native contracts and contains no text payloads.

## Task 4: Project mentorship, knowledge, technology, narratives, and offices

### Intent / Implementation Steps
1. Introduce typed owner-source extraction from `AgentRuntimeCheckpoint` and existing runner exports; enforce owner equality at extraction. Do not query another owner's state to resolve a local reference.
2. Mentorship: represent owner-believed bonds separately from content acquisition. Emit `taught_content_to` only when native learning evidence supports uptake; preserve attempt/status evidence otherwise. Preserve hop zero, lineage root, teacher and parent-lineage references. Teacher nodes are references, not access to the teacher's ledger.
   Extract the Task 1 `MentorshipLineageRecord` from each native entry, excluding fingerprints. Retain its original learner owner and current update/boundary; its parent is an owner-local native reference unless an explicit detached cross-owner inference qualifies it. Summary audits alone are not a detailed source. A missing parent is not automatically a record in the teacher's ledger.
3. Knowledge: emit entry nodes, owner-local parent edges preserving mutation/combination distinctions, holder references, and unresolved source references. Technology is a separate query view of practical knowledge restricted to evidenced capability/technique anchors; never derive objective competence from knowledge possession or merge different roots by equal content keys.
4. Narrative: emit owner-qualified variants, root references, native parent/merge edges and opaque source-event references. Event roots are `claimed_event_origin` references, not proof that a narrative is true. Source loss, witness death, reactivation and competing variants remain native statuses. Do not import observer into simulation.
5. Office succession: emit stable office nodes and distinct claim/transition nodes retaining native prior/proposed occupants, succession kind, tick, predecessor office and evidence refs. Preserve vacancy, dispute and uncertainty. No `current_occupant` global authority; no inference from duty labels alone.
6. Implement `merge_lineage_observations(previous, current, B)` over normalized metadata only. For each stable qualified key, a valid current observation at B replaces the previous descriptor/status, provided its native revision/update time does not regress. A repeated identical observation is idempotent; conflicting rows at the same source revision within current input are corruption. A current concrete node upgrades an earlier unresolved stub in place without changing its key or losing incident edges. Previous-only records retain their actual last observed boundary and become `archived`; never relabel them as freshly observed at B. Absence does not prove death, forgetting or collapse. Reappearance restores the current observed status with fresh provenance.
7. Preserve old relation evidence for historical browsing, but give edges explicit last-observed boundary and source-presence state. Old `holds`, bond, occupant or attempt evidence is not current authority just because it remains in the graph. A retracted/disputed/retired source is represented with its native status; a resolved parent stub does not erase the earlier missing-source coverage. Do not combine two different same-key revisions into one contradictory record, and do not copy full checkpoints into artifacts.

### Required Interfaces and Contracts
`project_owner_lineage(owner_source, family, boundary)` returns only that owner's class=`subjective` graph. Node metadata uses closed family-specific dataclasses. Extract only selected fields; no serialization of entire ledgers or arbitrary `getattr` dictionaries. New owner admissions start with their actual empty ledgers and never inherit captured state.

### Requirement Evidence
User teacher/student, technique, narrative and office requests; source contracts in the evidence table. `.ai-factory/RULES.md` owner-scoped memory axiom and architecture's no automatic content transfer rule.

### Error Handling and Logging
Reject foreign-owner records and impossible future acquisitions. Valid disputed/missing/pruned evidence is not corruption. Do not label every practical-knowledge parent `taught_by`. Safe logs: family, owner, counts, reason codes.

### Tests / Acceptance / Verification
`test_lineage_subjective_sources.py`: zero-hop teaching, failed attempt, detailed mentorship record extraction despite missing audit fields, local ID collision, two-parent technique combination, independent emergence with equal content key, archival-only technique, narrative branch/merge/source loss, claim-based event root, vacant/disputed office, linked successor role, eviction retaining history, newborn empty state. Add multi-boundary cases: confidence/status update replaces prior descriptor, unresolved parent becomes concrete with stable identity, missing-current record retains its old observation boundary, reappearance, retraction/retirement and conflicting same-revision input. Use native constructors/export fixtures from `test_mentorship_lineage.py`, `test_practical_knowledge_carry.py`, `test_generational_narrative_persistence.py`, and `test_offices_succession.py`.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_lineage_subjective_sources.py tests/unit/test_mentorship_lineage.py tests/unit/test_practical_knowledge_carry.py tests/unit/test_generational_narrative_persistence.py tests/unit/test_offices_succession.py --cov=simulation --cov-report=term-missing -q`. Acceptance: all five views preserve native uncertainty and owner isolation.

## Phase Risks and Mitigations
- Ledger summaries lose transitions: use native checkpoints for offices, not analysis office-summary digests.
- Query projections change behavior: pure adapters, no writes or installed cognitive modes.

## Phase Completion Checklist
- Source projections and existing regression cases pass; update `index.md` only.
