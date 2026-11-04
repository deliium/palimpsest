# Phase 3: Detached Analysis, Candidates, and Metrics

Plan: [index.md](index.md)
Tasks: 12-15
Depends on: Phase 2 / Task 11

## Objective

Build the detached research layer: harvest exported diplomacy ledgers and
objective lane evidence, derive per-lane inter-society relation rows, detect
stable analytical relation candidates, join them read-only to existing `org-` and
`msoc-` identities, project three strictly separated layers, classify
researcher-only envoy alignment, and append four metric families (catalog
160 → 164).

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/analysis/delegation_representation_contract.py` | `representation_owner_token`, `representation_principal_token`, `require_owner_token`, `derive_representation_candidate_id`, `representation_edge_id` | Hashed-token and identity precedent |
| `src/analysis/delegation_representation_layers.py` | `RepresentationObjectiveRow`, `RepresentationSubjectiveRow`, `RepresentationAnalyticalRow`, `assert_representation_layer_separation` | Three-layer and leakage-guard precedent |
| `src/analysis/delegation_representation_alignment.py` | `RepresentationAlignmentStatus`, `summarize_representation`, `representation_analysis_digest` | Researcher-only alignment precedent |
| `src/analysis/macro_society_contract.py` | `MACRO_SOCIETY_ID_PREFIX` 59; `MacroSocietyLane` 85; `derive_macro_society_id` 241 | `msoc-` identity namespace that must only be referenced |
| `src/analysis/macro_society_detection.py` | `MacroSocietyCandidate` 93; `detect_macro_society_candidates` 243 | Candidate detection and identity-input precedent |
| `src/analysis/macro_society_layers.py` | objective/subjective/analytical split 45-202 | Layer separation guards |
| `src/analysis/organization_contract.py` | `derive_organization_id` 175-200 | `org-` identity namespace that must only be referenced |
| `src/analysis/organization_agency.py` | `OrganizationAgencyHarvestRows` 255; decision rows 199 | Institutional-interaction lane input |
| `src/analysis/models.py` | `RelationshipEdgeRow` 1222; `AppliedActionRow` 966 | Agent-relationship and conflict lane inputs |
| `src/analysis/relationship_metrics.py` | deterministic row order 111 | Lane ordering convention |
| `src/analysis/objective_metrics.py` | `applied_actions_from_world_events` 105; `compute_conflict` 508; `CONFLICT_ACTION_KINDS` 293 | Conflict lane source |
| `src/analysis/exchange_functions.py` | `classify_exchange_functions` 85; `ExchangeFunctionViews` 79 | Trade lane source |
| `src/analysis/structured_commitments.py` | `CommitmentLedgerSnapshot` 31; `CommitmentSpeechView` 81 | Agreement lane source |
| `src/analysis/cultural_narrative_metrics.py` | `compute_cultural_narrative_lineage` 35 | Narrative lane source |
| `src/analysis/formal_rules.py` | `FormalRuleHarvestRows` 266 | Institutional lane source |
| `src/analysis/disputes.py` | `DisputeHarvestRows` 422 | Institutional lane source |
| `src/analysis/evidence_testimony_rows.py` | `EvidenceHarvestRows` 325 | Institutional lane source |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 53; `MetricSpecification` 312-355; `_BUILDERS` 7376; `validate_metric_catalog` 7558 | Catalog append mechanics |
| `src/analysis/metric_service.py` | `MetricComputationInputs` 218-340; `assemble_metric_documents` 408; representation block 1788-1870 | Input and assembly mechanics |
| `src/experiments/collectors.py` | harvest → `replace(inputs, ...)` 620-890; representation 846-866 | The only analysis-to-run bridge |
| `src/analysis/numerical.py` | `quantize_float` 55; `normalize_signed_zero` 106 | Quantization convention |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/analysis/diplomacy_contract.py` | create | Tokens, ids, lane enum, forbidden fields |
| `src/analysis/diplomacy_rows.py` | create | Harvested ledger rows |
| `src/analysis/diplomacy_objective.py` | create | Objective contact/exchange/attack anchors |
| `src/analysis/diplomacy_lanes.py` | create | Six per-lane evidence builders |
| `src/analysis/diplomacy_detection.py` | create | Relation candidate detection |
| `src/analysis/diplomacy_identity.py` | create | `dip-` identities, joins, lineage |
| `src/analysis/diplomacy_lineage.py` | create | Facade |
| `src/analysis/diplomacy_layers.py` | create | Three-layer projection and guard |
| `src/analysis/diplomacy_alignment.py` | create | Envoy alignment and summary |
| `src/analysis/diplomacy_metrics.py` | create | Four metric documents |
| `src/analysis/specifications.py` | modify | Four family specs; count 164 |
| `src/analysis/metric_service.py` | modify | Inputs and assembly block |
| `src/experiments/diplomacy_harvest.py` | create | Completed-run harvest |
| `src/experiments/collectors.py` | modify | Attach diplomacy inputs |
| `tests/unit/test_diplomacy_analysis.py` | create | Harvest and detection |
| `tests/unit/test_diplomacy_identity.py` | create | Candidate identity, joins, lineage |
| `tests/unit/test_diplomacy_lanes.py` | create | Six lane builders |
| `tests/unit/test_diplomacy_layers.py` | create | Layer separation and alignment |
| `tests/unit/test_diplomacy_metrics.py` | create | Four documents |
| `tests/unit/test_diplomacy_catalog.py` | create | Catalog append and stale-pin guard |

## Task 12: Harvest diplomacy rows and six inter-society evidence lanes

### Intent

Analysis must never read live cognition. It consumes exported owner ledgers and
objective committed evidence, normalizes them into detached rows, and derives six
independent lane views. No lane produces a bilateral score.

### Implementation Steps

1. Create `src/analysis/diplomacy_contract.py` with
   `DIPLOMACY_ANALYSIS_POLICY_VERSION = "diplomacy-analysis.v1"`,
   `DIPLOMACY_IDENTITY_VERSION`,
   `DIPLOMACY_CANDIDATE_PREFIX = "dip-"`,
   `DIPLOMACY_EDGE_PREFIX = "dip-edge-"`,
   `DIPLOMACY_PUBLICATION_PREFIX = "dip-pub-"`, the closed party/status tuples,
   the `InterSocietyLane` enum (six members), `DIPLOMACY_FORBIDDEN_RESULT_FIELDS`
   (`score`, `relation_score`, `trust`, `rank`, `valence`, `index`, `composite`,
   `overall_relation`, `bilateral_score`, `mean_score`), token hashers, and
   `require_diplomacy_token`/`require_diplomacy_candidate_id`.
2. Create `src/analysis/diplomacy_rows.py` with frozen row types mirroring the
   ledger: `DiplomacyRelationRow`, `DiplomacyPartyRow`, `DiplomacyContactRow`,
   `DiplomacyEnvoyRow`, `DiplomacyNegotiationRow`, `DiplomacyInstrumentRow`,
   `DiplomacyDeclarationRow`, `DiplomacyMisrepresentationRow`,
   `DiplomacyTerminationRow`, `DiplomacyConflictRow`, `DiplomacyHarvestRows`,
   and `harvest_diplomacy_rows(ledgers, *, entity_to_agent, policy=None)`.
3. Mirror `src/analysis/delegation_representation_contract.py` 166-191:
   one shared `diplomacy_agent_token(value)` hashes an agent id in a single
   domain used by owner, envoy, actor, and **agent-party** tokens, so
   `party_member_tokens` can match lane rows. `diplomacy_party_token(kind, ref)`
   delegates to `diplomacy_agent_token` for `agent` and returns owner-safe
   `orgc-`/region anchors for organization, coalition, and settlement;
   `diplomacy_subject_token` hashes free-text subjects. Rows carry
   tokens/anchors and closed enums, never raw agent ids or free-text subjects.
   Add a cross-context test proving the agent token matches V4-09's
   `representation_owner_token` for the same agent (or document the intentional
   domain alias if V4-09's owner/principal domains stay distinct).
4. Create `src/analysis/diplomacy_objective.py` mirroring
   `delegation_representation_objective.py`: `DiplomacyObjectiveAnchorRow`,
   `diplomacy_objective_anchor_rows_from_events(events, entity_to_agent)`, and
   `build_diplomacy_windows(...)` for contact, exchange, and attack counts by
   tick/region. It never reads live cognition and carries no owner token in
   objective rows.
5. Create `src/analysis/diplomacy_lanes.py` with `InterSocietyRelationRow`
   (`lane`, `left_token`, `right_token` sorted lexicographically, `tick`,
   `event_count`, `denominator`, `provenance_ref`) and six builders:
   - `relation_rows_from_agent_relationships(rows)` from
     `RelationshipEdgeRow`, counting directed edges and distinct pairs.
   - `relation_rows_from_trade(events, spec)` from committed
     `ExchangeCompleted` only, counting completed exchanges per pair. A one-way
     `Given` is a transfer, never a trade row; expose it, if at all, through a
     separate `transfer_count` that is not part of the trade lane.
   - `relation_rows_from_conflict(rows)` from `AppliedActionRow` rows whose action
     kind is in `CONFLICT_ACTION_KINDS`.
   - `relation_rows_from_agreements(declarations, commitments)` from
     `apparently_accepted` declarations plus structured-commitment speech.
   - `relation_rows_from_narratives(rows)` from shared narrative variant ids
     across owners.
   - `relation_rows_from_institutional_interaction(formal_rule_rows,
     dispute_rows, evidence_rows, organization_agency_rows)` from shared
     referenced rule/dispute/evidence/decision anchors.
6. Every builder sorts rows by `(lane, left_token, right_token, tick)`, dedupes
   identical rows, and rejects forbidden result fields.
7. A lane with absent inputs yields an empty tuple, never a zero-filled row.
8. `src/experiments/diplomacy_harvest.py` builds `DiplomacyHarvest` from
   `runner_result.diplomacy_ledgers` plus committed objective events and existing
   harvested lane inputs; it takes `entity_to_agent` like
   `build_completed_run_representation_harvest` (54-66), is the only bridge, and
   imports analysis contracts, never live agents.

### Required Interfaces and Contracts

```python
class InterSocietyLane(StrEnum):
    AGENT_RELATIONSHIPS = "agent_relationships"
    TRADE = "trade"
    CONFLICT = "conflict"
    AGREEMENTS = "agreements"
    NARRATIVES = "narratives"
    INSTITUTIONAL_INTERACTION = "institutional_interaction"
```

- Lane rows are person-pair evidence. They are not candidate-pair claims and
  carry no score.
- `event_count` is a non-negative integer; `denominator` names the exposure used
  by the source lane.
- No builder may import `agents`, `simulation`, `experiments`, `persistence`, or
  `api`.

### Requirement Evidence (when reconciliation applies)

- Original Request: "Macro-level relationship metrics must be derived from: agent
  relationships, trade, conflict, agreements, narratives, institutional
  interaction".
- `.ai-factory/ARCHITECTURE.md` "analysis is read-only": analysis joins objective
  and subjective evidence after the fact.

### Error Handling and Logging

- Codes: `diplomacy_analysis_policy_not_locked`,
  `diplomacy_forbidden_result_field`, `diplomacy_duplicate_row`.
- `DEBUG diplomacy_harvest rows=%s lanes=%s`.
- `WARN diplomacy_lane_empty lane=%s`.
- Never log tokens, anchors, or row payloads.

### Tests

- `tests/unit/test_diplomacy_lanes.py`: each builder produces deterministic,
  sorted rows; absent input yields `()`; duplicate rows collapse; lane enum is
  closed at six; no forbidden field appears on any row; tokens are stable across
  runs and differ across owners; `Given` alone produces no trade row;
  `ExchangeCompleted` does; a lane row never carries a score.
- `tests/unit/test_diplomacy_analysis.py`: harvest from a real exported ledger
  fixture with `entity_to_agent`; relation/termination rows are present; owner
  token and owner-safe `orgc-`/region anchors are present; raw ids and free-text
  subjects are absent from every row `repr`; the agent token equals V4-09's
  representation token for the same agent.

### Acceptance Criteria

- Six lanes exist and are independently derivable.
- Harvested rows contain only tokens and closed enums.

### Verification

- `uv run pytest tests/unit/test_diplomacy_lanes.py tests/unit/test_diplomacy_analysis.py -q`
- Expected: pass.

## Task 13: Detect relation candidates, join candidate identities, and derive forward-only lineage

### Intent

A diplomatic relation candidate is an analytical pair label with a `dip-`
identity. It is not a country, actor, or score, and it never creates, renames,
splits, merges, or dissolves an `org-` or `msoc-` identity.

### Implementation Steps

1. Create `src/analysis/diplomacy_detection.py` with `DiplomaticRelationMember`
   (owner token, party token, party kind, evidence lane counts) and
   `DiplomaticRelationCandidate` (`candidate_key`, owner token, party tokens,
   lanes with evidence, status).
2. `detect_diplomacy_candidates(diplomacy_rows, lane_rows, *,
   max_candidates=2048)` groups by unordered owner-token/party-token pair,
   merges lane evidence, and assigns a closed status:
   `observed` (contact/negotiation/instrument evidence), `fragmented` (only one
   lane and one tick), `contested` (retained conflict or misrepresentation),
   `dormant` (no evidence in the final window), `unknown`.
3. Create `src/analysis/diplomacy_identity.py` with `DiplomacyAnalysis`,
   `DiplomacyLineageEdge`, `assign_diplomacy_identities`,
   `derive_diplomacy_lineage`, and `join_diplomacy_parties`.
4. `assign_diplomacy_identities` mints `dip-` ids from creation evidence only
   (first observed pair key and structurally stable anchors) and matches prior
   records across windows; it never re-mints an existing pair.
5. `derive_diplomacy_lineage` emits forward-only
   `continued|transformed|split|merge|dormant|ended` edges with `dip-edge-` ids.
   Split/merge require disjoint/overlapping party-token sets and are
   deterministic.
6. `join_diplomacy_parties(candidates, organization_rows,
   macro_society_analysis)` maps each party token to:
   - `organization_candidate_ids`: existing `org-` ids whose member rows or
     `orgc-` concept anchors match the party token;
   - `macro_society_candidate_ids`: existing `msoc-` ids whose member set or
     `region:<id>` token matches.
   The join is read-only and relies on Task 12's owner-safe anchors, never on a
   hashed `orgc-`/region value that would destroy the match. It must never call
   an identity minting function for `org-` or `msoc-`, and must never derive one
   from the other.
7. Add `party_member_tokens(party_token, *, organization_rows,
   macro_society_analysis) -> tuple[str, ...]`: an `agent` party maps to the
   shared `diplomacy_agent_token` identity (never a differently-domained party
   hash); an organization/coalition party maps to the agent tokens of its matched
   `org-` candidate member rows; a settlement party maps to the person tokens
   whose residence/region token matches. Missing members yield an empty tuple.
8. Lane aggregation rule (deterministic): a lane row `(a, b, lane)` contributes
   to candidate `(A, B)` when `a` is in `party_member_tokens(A)` and `b` is in
   `party_member_tokens(B)`, or the reverse orientation; sum `event_count` and
   `denominator`, and record the lane once. A candidate with no resolvable
   members keeps only its diplomacy evidence and records zero lane coverage.
9. Store both identity joins as opaque id tuples on the analytical row; an
   unmatched join is empty, not guessed.
10. Create `src/analysis/diplomacy_lineage.py` as a compatibility facade
    re-exporting the identity symbols, mirroring
    `delegation_representation_lineage.py`.

### Required Interfaces and Contracts

```python
def detect_diplomacy_candidates(
    diplomacy_rows: DiplomacyHarvestRows,
    lane_rows: Sequence[InterSocietyRelationRow],
    *,
    max_candidates: int = 2048,
) -> tuple[DiplomaticRelationCandidate, ...]: ...

def derive_diplomacy_candidate_id(candidate: DiplomaticRelationCandidate) -> str: ...

def join_diplomacy_parties(
    candidates: Sequence[DiplomaticRelationCandidate],
    *,
    organization_rows: Sequence[object] = (),
    macro_society_analysis: object | None = None,
) -> tuple[DiplomaticPartyJoinRow, ...]: ...
```

- `dip-` ids are content-addressed from creation evidence and stable across
  windows.
- `org-`/`msoc-` ids appear only as referenced strings; the analysis suite must
  prove no `derive_organization_id`/`derive_macro_society_id` call exists in
  diplomacy modules.
- Overlapping, fragmented, disputed, and unmatched candidates are legal.

### Requirement Evidence (when reconciliation applies)

- Original Request: "long-running relationships between macro-society candidates
  and organizations".
- `src/analysis/macro_society_contract.py` 59, 241 and
  `src/analysis/organization_contract.py` 175-200: independent immutable
  identity namespaces.
- `docs/macro-societies.md`: `msoc-` candidates are analytical labels, never
  actors.

### Error Handling and Logging

- Codes: `diplomacy_candidate_capacity_reached`,
  `diplomacy_foreign_identity_mutation`, `diplomacy_unmatched_join`.
- `INFO diplomacy_candidates count=%s lineage_edges=%s`.
- `DEBUG diplomacy_join matched=%s unmatched=%s`.
- Never log candidate ids or party tokens at INFO.

### Tests

- `tests/unit/test_diplomacy_identity.py`: stable id across windows; new id only
  for a new creation evidence pair; relation rows join into candidates;
  forward-only lineage kinds; split/merge determinism; join matches `org-` by
  `orgc-` anchors and `msoc-` by member/region tokens without minting; a hashed
  anchor would fail the join (guard test); unmatched join stays empty;
  overlapping candidates legal; AST scan proves no
  `derive_organization_id`/`derive_macro_society_id` import or call in
  `src/analysis/diplomacy_*.py`.

### Acceptance Criteria

- Candidates are stable, overlapping, and read-only over existing identities.
- No macro-society or organization identity is created or changed.

### Verification

- `uv run pytest tests/unit/test_diplomacy_identity.py -q`
- Expected: pass.

## Task 14: Project three layers and researcher-only envoy alignment

### Intent

Objective counts, owner-token claims, and analytical candidates must never mix.
Envoy alignment is a research classification only and must never reach a prompt,
memory, world state, stop selector, or observer semantic.

### Implementation Steps

1. Create `src/analysis/diplomacy_layers.py` with:
   `DiplomacyObjectiveRow` (`tick`, `region_token`, `contact_event_count`,
   `exchange_event_count`, `attack_event_count`), `DiplomacySubjectiveRow`
   (`owner_token`, `party_token`, `status_counts`, `lane_counts`),
   `DiplomacyAnalyticalRow` (`candidate_id`, `party_tokens`,
   `organization_candidate_ids`, `macro_society_candidate_ids`, `lanes`,
   `status`), `DiplomacyLayerView`, `project_diplomacy_layers`, and
   `assert_diplomacy_layer_separation`.
2. The leakage guard rejects any objective row carrying an owner token or
   candidate id, any subjective row carrying a candidate id, any analytical row
   carrying a raw agent id, and any row carrying a forbidden score field.
3. Create `src/analysis/diplomacy_alignment.py` with
   `DiplomacyEnvoyAlignmentStatus` (`consistent`, `unresolved`, `inconsistent`,
   `not_applicable`) and `classify_diplomacy_envoy_alignment(rows,
   representation_rows, *, ...) -> tuple[DiplomacyEnvoyAlignmentRow, ...]`.
   Join on the Task 12 agent token domain and reuse the same closed
   scope/duration matrix as Task 9:
   - `consistent`: the declaration's envoy had an owner-believed `recognized`
     mandate and `diplomacy_scope_covers` is true for the instrument kind,
     duration, and subject.
   - `unresolved`: no mandate row, `unknown` standing, or missing scope data.
   - `inconsistent`: mandate `rejected`/`revoked`/`expired`/`superseded`/
     `contested`, or `diplomacy_scope_covers` is false.
   - `not_applicable`: contact/report/recall acts that assert no authority.
   The alignment row carries a hashed envoy token and a subject token, never a
   raw mandate id or free-text subject.
4. `summarize_diplomacy(rows, candidates, layers)` returns
   `DiplomacyAnalysisSummary` with status counts, lane histogram, coverage, and
   no composite value.
5. `diplomacy_analysis_digest(summary)` is canonical JSON over sorted keys.
6. Assert at import/test time that `DiplomacyEnvoyAlignmentStatus` values do not
   appear under `src/agents`, `src/simulation` (except the analysis-independent
   snapshot/ports modules), `src/world`, `src/observer`, or `src/api` schemas.

### Required Interfaces and Contracts

- Objective rows are aggregate committed-act counts by tick/region only.
- Subjective rows carry hashed owner tokens and counts only.
- Analytical rows carry `dip-` ids and referenced `org-`/`msoc-` ids only.
- Alignment is researcher-only and read-only.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` Key Principle 1 and "analysis is read-only".
- Original Request: "Macro-level relationship metrics must be derived from…"
  implies researcher-facing derivation, never agent-facing truth.

### Error Handling and Logging

- Codes: `diplomacy_layer_leak`, `diplomacy_alignment_input_missing`.
- `DEBUG diplomacy_layers objective=%s subjective=%s analytical=%s`.
- `WARN diplomacy_alignment_unresolved count=%s`.
- Never log tokens, ids, or status sets.

### Tests

- `tests/unit/test_diplomacy_layers.py`: each leakage case raises
  `diplomacy_layer_leak`; valid rows project and sort; alignment statuses for all
  four cases; a `superseded` mandate and a `single_act` long-running mismatch are
  `inconsistent`; a matching owner-safe `orgc-`/region anchor joins the V4-09
  representation rows; alignment enum never appears in cognition/world/observer
  modules (source scan); summary has no score key; digest stable.

### Acceptance Criteria

- The three layers are structurally separate and guarded.
- Alignment cannot cross into cognition.

### Verification

- `uv run pytest tests/unit/test_diplomacy_layers.py -q`
- Expected: pass.

## Task 15: Add four metric families and raise the catalog to 164

### Intent

The catalog must grow by exactly four appended families, with the first 160
unchanged, and real completed-run assembly must emit all four.

### Implementation Steps

1. In `src/analysis/specifications.py`, add `MetricFamilyId` members
   `DIPLOMATIC_CONTACT_STRUCTURE`,
   `DIPLOMATIC_INSTRUMENT_OUTCOMES`, `DIPLOMATIC_ENVOY_ALIGNMENT`, and
   `INTER_SOCIETY_RELATION_LANES`, with builder functions appended after the
   representation builders in `_BUILDERS` (7376).
2. Define specs:
   - `diplomatic_contact_structure@1` — population
     `final_window_diplomacy_relations`, denominator
     `diplomacy_relations_with_contact_evidence`, value keys
     `relation_count, party_count, contact_count, envoy_count,
     negotiation_count, party_kind_histogram, contact_kind_histogram,
     envoy_status_histogram, negotiation_status_histogram, coverage`.
   - `diplomatic_instrument_outcomes@1` — denominator
     `diplomacy_instruments`, value keys `instrument_count, proposal_count,
     promise_count, agreement_count, dispute_count, shared_project_count,
     apparently_accepted_count, rejected_count, withdrawn_count,
     unresolved_count, superseded_count, misrepresentation_count,
     misrepresentation_kind_histogram, declaration_count, acceptance_ratio,
     coverage`.
   - `diplomatic_envoy_alignment@1` — denominator
     `diplomacy_declarations_with_authority_claim`, value keys
     `consistent_count, unresolved_count, inconsistent_count,
     not_applicable_count, aligned_declaration_count, consistency_ratio,
     inconsistency_ratio, coverage`.
   - `inter_society_relation_lanes@1` — population
     `relation_candidate_pairs_with_identity_join`, denominator
     `relation_candidate_pairs`, value keys `pair_count,
     lane_pair_count_histogram, agent_relationship_pair_count,
     trade_pair_count, conflict_pair_count, agreement_pair_count,
     narrative_pair_count, institutional_interaction_pair_count,
     pairs_with_any_lane, pairs_with_multiple_lanes, lane_coverage_ratio,
     coverage`.
3. Set `METRIC_FAMILY_COUNT = 164` (line 53). The first 160 keep id, order,
   version, and value keys.
4. Create `src/analysis/diplomacy_metrics.py` with
   `compute_diplomatic_contact_structure`,
   `compute_diplomatic_instrument_outcomes`,
   `compute_diplomatic_envoy_alignment`, and
   `compute_inter_society_relation_lanes`; each returns an empty value mapping
   when its required inputs are absent and a present document with zero counts
   when an enabled-but-empty ledger is supplied.
5. Add only the raw inputs to `MetricComputationInputs`: `diplomacy_rows`,
   `diplomacy_objective_rows`, and `diplomacy_lane_rows`. Mirror V4-09, which
   exposes `representation_rows` + `representation_objective_rows` (319-320) and
   derives analysis/layers/summary inside the assembly block.
6. Add an assembly block in `assemble_metric_documents` (after the
   representation block, 1788-1875) that harvests or accepts `diplomacy_rows`,
   builds `DiplomacyObjectiveAnchorRow` windows, derives
   `DiplomacyAnalysis`/`DiplomacyAnalysisSummary`/`DiplomacyLayerView`, and only
   then calls the four metric builders. Do not pre-derive those fields on the
   inputs dataclass.
7. In `src/experiments/collectors.py`, attach the harvest at 846-866 following
   the representation wiring, including `entity_to_agent`.
8. Sweep every **current** pin assertion and doc line from 160 to 164. The
   measured test sweep is 49 files / 78 `== 160` occurrences (including
   `test_metric_specifications.py`, `test_dispute_docs.py`,
   `test_evidence_testimony_docs.py`, `test_formal_rule_docs.py`,
   `test_organization_docs.py`, and `test_organization_operations_docs.py`).
   Current doc lines: `src/analysis/specifications.py:53`,
   `docs/analysis-metrics.md:41`, `docs/architecture.md` 565/596/659,
   `docs/disputes.md:225`, `docs/evidence-testimony.md:211`,
   `docs/delegation-representation.md:137`, `.ai-factory/ARCHITECTURE.md`
   184/844-845, `.ai-factory/DESCRIPTION.md` 385/390.
9. Do **not** rewrite historical revision statements. Keep
   `docs/analysis-metrics.md` 507/532 (`(catalog 160)` section labels),
   `docs/architecture.md:654` (`157 -> 160`),
   `docs/delegation-representation.md` 129/135 (`157 to 160` / `first 157`),
   `docs/evidence-testimony.md:143` (`154 to 157`), and
   `.ai-factory/ARCHITECTURE.md` 808/843 (`154 to 157` / `157 -> 160`).
   Keep the first-154 digest pin.
10. Replace the stale-pin guard in
    `tests/unit/test_delegation_representation_catalog.py` (93-108) with a V4-10
    guard that scans current-count assertions for `160` and fails if one
    remains; rename the test accordingly. Add a corresponding V4-10 catalog
    test.
11. Assert no family exposes `score`, `relation_score`, `trust`, `rank`,
    `valence`, `index`, `composite`, `mean_score`, or `overall_relation`, and
    that `agreement_count` uses `is_agreement_view` rather than a non-existent
    `AGREEMENT` instrument kind.

### Required Interfaces and Contracts

- Catalog cardinality is exactly 164; family order is append-only.
- `MetricComputationInputs` exposes only `diplomacy_rows`,
  `diplomacy_objective_rows`, and `diplomacy_lane_rows`; analysis/layers/summary
  are derived inside `assemble_metric_documents`.
- `inter_society_relation_lanes@1` has no aggregate/composite key and no key that
  arithmetically mixes lanes.
- Every ratio uses an explicit denominator and quantized float output.
- Empty/absent behavior is documented per family.

### Requirement Evidence (when reconciliation applies)

- Original Request: "Macro-level relationship metrics must be derived from: agent
  relationships, trade, conflict, agreements, narratives, institutional
  interaction"; "Do not create magical bilateral relationship scores".
- `src/analysis/specifications.py` 312-355: spec shape; `valid_metric_catalog`
  rejects unknown policy and duplicate keys.

### Error Handling and Logging

- Codes: `diplomacy_metric_input_missing`,
  `diplomacy_metric_forbidden_value_key`.
- `DEBUG diplomacy_metric family=%s values=%s` may log key names only.
- `INFO metric_catalog_families count=164`.

### Tests

- `tests/unit/test_diplomacy_metrics.py`: all four documents compute from real
  fixtures; absent inputs → no document; enabled-empty ledger → zero counts;
  acceptance/consistency ratios quantized; lane histogram is canonical JSON; no
  forbidden key; `agreement_count` counts an every-party proposal view and never
  a phantom `AGREEMENT` row; the trade lane count excludes `Given`.
- `tests/unit/test_diplomacy_catalog.py`: count 164; first 160 ids/order/versions
  unchanged; the four new families last; stale-pin guard finds no current `160`
  assertion; synthetic completed-run assembly derives analysis/layers/summary
  and emits all four; the historical pins listed in step 9 still contain their
  original numbers.
- `tests/unit/test_metric_specifications.py` current-count assertion moves to
  164.

### Acceptance Criteria

- Catalog is 164 with four appended families.
- Real assembly, not only unit fixtures, emits the documents.

### Verification

- `uv run pytest tests/unit/test_diplomacy_metrics.py tests/unit/test_diplomacy_catalog.py tests/unit/test_metric_specifications.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: a lane silently becomes a composite relationship score.
  Mitigation: lane rows are counts only; family 4 has no aggregate key and a
  forbidden-key test.
- Risk: analysis mints or mutates `org-`/`msoc-` identity.
  Mitigation: Task 13 read-only join plus an AST scan for the minting functions.
- Risk: alignment leaks into agent cognition.
  Mitigation: Task 14 source scan and the Task 22 boundary suite.
- Risk: the catalog sweep misses a pin or rewrites history.
  Mitigation: explicit stale-pin guard, the measured 49-file/78-occurrence list,
  and a separate historical-pin assertion before Task 24.
- Risk: token hashing breaks the `org-`/`msoc-` or V4-09 joins.
  Mitigation: Task 12 mirrors `representation_principal_token`, and Task 13/14
  include a cross-context join test.

## Phase Completion Checklist

- Every task in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
