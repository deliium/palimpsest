[← Formal social rules](formal-rules.md) · [Back to README](../README.md) · [Analysis metrics →](analysis-metrics.md)

# Dispute resolution

Structured disputes extend V2/V3 mediation, structured commitments, subjective
value, offices, institutions, organizations, and formal rules. A dispute is
**one owner's belief** about attributed claims, testimony, evidence, rule
interpretations, mediation links, and proposed or declared resolutions. It is
never a shared case file, court record, judgment, or objective truth.

## What a dispute can and cannot do

A dispute belief can retain what an owner heard, remembers, cited, and proposed.
It can bias that owner's declared responses and link the owner's own mediation
records. It cannot decide who is right.

`WorldEngine` never reads a dispute ledger. A socially disputed but
physically possible command is still admitted, and a physically impossible command is still rejected by the existing admission rules with no dispute
attribution.

There is **no objective justice oracle**. No component returns a verdict, guilt,
liability, damages, ownership truth, or a binding settlement. There is no court,
judge, jury, verdict, judgment, jurisdiction, liability engine, sanction engine,
or **global** dispute **registry**. A party is never labelled guilty, liable, or
the true owner by this feature; no claim makes a party liable.

## Claims and counterclaims

Each claim is attributed to its verified claimant and to the party it concerns.
Claims and counterclaims are separate owner-local `dcl-` records; opposing claims
coexist and are never reconciled into one neutral proposition, winner, or
liability finding. A speaker cannot attribute another party's claim to that
party: the actor remains the verified speaker.

The six requested dispute kinds are represented as closed kinds:

| Kind | Token |
| --- | --- |
| Contested debt | `contested_debt` |
| Ownership claim | `ownership_claim` |
| Contract interpretation | `contract_interpretation` |
| Injury | `injury` |
| Broken promise | `broken_promise` |
| Resource appropriation | `resource_appropriation` |

`other` is the closed fallback. Claim role (`claim`, `counterclaim`,
`supplementary`), polarity (`affirm`, `deny`, `uncertain`), and claim kind are
closed vocabularies. Polarity is a stance, never a truth finding.

Two owners may sincerely disagree because their remembered evidence differs.
The ledger keeps both memory references and never corrects either against
objective history. A counterclaim is not a refutation and a denial is not proof.

## Testimony and evidence

Testimony is an attributed account, not truth. Direct (`channel=direct`) and
communicated (`channel=communicated`) testimony are distinct. A retold account
that shares a **shared root** with another account is not independent
corroboration; `independently_evidenced` is set only when the testimony root is
distinct. Repetition is not corroboration, and silence is never inferred as
testimony.

Evidence references are closed, typed, owner-visible anchors:

- observed occurrences and communications carry only an opaque `EventId`
  correlation — never a `WorldEvent`, `WorldState`, or event store;
- memory traces and reconstructed memories carry owner-local ids without
  ground-truth correction;
- artifact, durable-record, repository-entry, commitment, valuation, mediation,
  rule, office, institution, and organization references are anchors, not
  payload copies.

No helper reads another owner's ledger or copies an evidence body.

## Rule references

A rule reference points only to the owner's own formal-rule ledger (`frs-`,
`frl-`, `frv-`). The reference records applicability and interpretation beliefs,
never permission, prohibition, or enforcement. Resolution is closed:

- `resolved` when the cited rule is present in the owner's ledger;
- `orphaned` when the rule is absent — no rule is invented and the claim still
  stands;
- `version_mismatch` when the cited version differs — there is no silent
  upgrade;
- `contested` or `retired` when the owner's rule belief itself is contested or
  retired.

`legal_disputes` may run without the `formal_rules` capability flag. In that
case every rule reference stays `orphaned`; no world law or global rule set is
consulted.

## Mediation and institutional roles

The dispute ledger reads only the owner's own `MediationLedger`. Mediation
cases, recommendations, responses, and outcomes are linked as beliefs
(`dmr-` records) and are **not binding**. A mediator recommendation becomes a
proposed dispute resolution with `source=mediator`; it creates no verdict,
settlement, or obligation.

Institutional roles are existing beliefs too. Office, institution, organization,
collective-decision, procedure, and written-record references are cited as
authority beliefs. The existing `conflict_mediation` office function and
mediation-authority appraisal provide evidence only. No judge, court,
jurisdiction, or new role object is created.

No dispute helper constructs, submits, resolves, or executes an `AgentCommand`.
The only supported undertaking path delegates to the existing mediation
compiler for an exact owner-selected `Give`, and the resulting physical effect
is an ordinary admitted command.

## Proposed resolutions and declarations

A resolution is a proposal. Its status describes owner knowledge only:

| Status | Meaning |
| --- | --- |
| `proposed` | Offered terms, no active declarations yet |
| `partially_accepted` | Some named parties actively accept |
| `apparently_accepted` | Every named party has an active accept declaration |
| `contested` | A named party actively rejects or counter-proposes |
| `withdrawn` | The proposer withdrew the proposal |
| `expired` | The bounded resolution window elapsed |
| `superseded` | A later proposal replaced it |

`apparently_accepted` is deliberately named: every named party's active
declaration is required, and it still binds nobody. There is no forced
transfer, sanction, or enforcement.

Acceptance requires a proposal observed in a **prior committed tick**. A
same-tick proposal and acceptance is refused with
`dispute_resolution_requires_prior_tick`. Responses are closed per-party
declarations: `accept`, `reject`, `counterpropose`, `defer`, and `withdraw`.
A speaker claiming another party's acceptance does not forge that party's
declaration.

## Objective alignment (researcher only)

Detached analysis may join owner rows with committed objective history to
classify claim support for **researchers** only:

- `supported`;
- `unresolved`;
- `inconsistent`;
- `not_applicable`.

This classification never reaches cognition, prompts, memory, world state,
observer semantics, or stop selectors. It is not a verdict, guilt finding,
liability finding, or true-owner determination. Claims without an objective
anchor are excluded from the objective denominator rather than counted as
inconsistent.

## Snapshot, publication, and routes

Detached analysis harvests exported ledgers, builds bounded windows, detects
overlapping candidates, mints stable `disp-` analytical identities, and derives
forward-only lineage. Objective counts, owner claims, and analytical summaries
remain three separated layers; leakage is a hard failure. Dispute candidates
never create, split, merge, dissolve, or re-identify a formal-rule,
organization, office, institution, or mediation candidate.

`dispute-resolution-snapshot-v1` is an independent canonical artifact.
Organization snapshots v1/v2/v3 and `formal-rule-snapshot-v1` stay decodable and
byte-verifiable. Publication is opt-in, post-completion, atomic, quota-bounded,
and isolated from scientific status. A storage or composition failure changes
only the receipt, never the scientific result.

The filesystem store is `dispute-resolution-store-v1`. The research CLI producer
uses `--dispute-root` (or `PALIMPSEST_DISPUTE_ROOT`),
`--dispute-max-publications` (default 16), and `--dispute-max-bytes` (default
8 MiB), and writes a `dispute-publication-{run_id}.json` receipt.

Six GET-only `/v1` routes require `SUBJECTIVE_DEBUG`:

| Route | Purpose |
| --- | --- |
| `GET /v1/simulations/{run_id}/disputes` | Summary |
| `GET /v1/simulations/{run_id}/disputes/candidates` | Candidate page |
| `GET /v1/simulations/{run_id}/disputes/candidates/{candidate_id}` | Candidate detail |
| `GET /v1/simulations/{run_id}/disputes/candidates/{candidate_id}/claims` | Claim page |
| `GET /v1/simulations/{run_id}/disputes/candidates/{candidate_id}/resolutions` | Resolution page |
| `GET /v1/simulations/{run_id}/disputes/lineage` | Lineage page |

`PALIMPSEST_DISPUTE_ROOT` unset returns `503 dispute_disabled`. Cursors bind run,
publication, digest, purpose, filter, and offset; changed bindings fail with
`400 dispute_cursor_invalid`, and expiry fails with `410 dispute_cursor_expired`.
An oversized response fails with `400 dispute_size_limit`.

## Metrics

The general evidence ledger that composes with disputes is documented in [evidence-testimony.md](evidence-testimony.md). The catalog grows from 151 to **154** with three appended families:

- `dispute_claim_structure@1` — candidates, cases, attributed claims,
  counterclaim ratio, claim-kind and polarity histograms, and evidence/rule/
  multiparty coverage;
- `dispute_testimony_independence@1` — direct and communicated testimony,
  distinct roots, shared-root duplication, independently evidenced rows, and
  contradictory testimony;
- `dispute_resolution_alignment@1` — proposed, apparently accepted, and contested
  resolutions, per-party accept/reject ratios, mediation-linked resolutions, and
  researcher-only objective alignment.

The first 151 families keep their ids, order, versions, and value keys. An
absent ledger or channel yields `ABSENT`; an enabled empty ledger yields
`PRESENT` with zero counts. Missing rows stay unknown and are never coerced to
zero or false.

## Configuration

| Setting | Purpose |
| --- | --- |
| `legal_disputes` | Third owned V4 capability flag on `runner-config-v56` |
| `PALIMPSEST_DISPUTE_ROOT` | Published snapshot root for the six read-only routes |
| `PALIMPSEST_DISPUTE_CURSOR_KEY` | At least 32 UTF-8 bytes; keeps cursors restart-stable |
| `--dispute-root` | Research CLI publication root (opt-in) |
| `--dispute-max-publications` | Publication quota (default 16) |
| `--dispute-max-bytes` | Artifact byte quota (default 8 MiB) |

`legal_disputes` is the third owned V4 flag alongside `organizations` and
`formal_rules`. It requires `v4_capability_flags` on the accepted
`runner-config-v56` keyset. There is no `runner-config-v57`, no new runner root
field, and no per-agent runner mode.

**Pins:** 14 V4 contexts, 12 capability flags, and **4 owned** flags
(`organizations`, `formal_rules`, `legal_disputes`, `diplomacy`); 188 metric families;
43 commands; 73 observer semantic types; replay `EVENT_SCHEMA_REPLAY_V22`
(22) / codec `v20`; Alembic head `0017` with **no `0018`**; `/v1`; and
`observer-protocol-v1`.

## Limits and non-goals

The owner ledger is bounded to 16 cases, 16 claims per case, 32 testimony rows
per case, 16 evidence references per claim, 8 rule references, 8 authority
references, 4 mediation references, 4 resolutions per case, 8 responses per
resolution, 8 parties, 4 terms per resolution, 640 total records, a 64-tick
resolution window, and a 768-character frame. Exceeding a bound yields
`dispute_truncated`, never a silent drop.

A published snapshot is bounded to 2048 candidates, 4096 cases, 8192 claims,
8192 testimony rows, 16384 evidence references, 4096 resolutions, 16384
responses, 512 windows, 4096 objective rows, 4 MiB per artifact, and 500 rows
per page. Exceeding a bound yields `dispute_size_limit`. Duplicate publication
ids with different bytes are refused with `dispute_publication_exists`.

No `diplomacy`, `organized_conflict`, `infrastructure_networks`, `markets_credit`,
`science`, or other V4 context is implemented here. No court, judge, jury,
jurisdiction, verdict, binding settlement, global registry, or justice engine
exists. No objective meaning is downloaded from an artifact or another owner.
No new event, command, observer semantic type, write pair, `/v2` route,
`observer-protocol-v2`, or SQL migration is added.

## Non-claims

A dispute belief is not objective truth, guilt, liability, moral correctness, a
verdict, or a binding settlement. Objective alignment is a researcher-only
classification, not an agent belief. Counts describe detached candidates under
stated coverage. This feature makes no prevalence, emergence-probability,
predictive-power, capacity, throughput, or composite-civilization-score claim.

## See also

- [Evidence and testimony](evidence-testimony.md)
- [Conflict mediation](mediation.md)
- [Formal social rules](formal-rules.md)
- [V4 architecture](v4-architecture.md)
- [Configuration](configuration.md)
- [Research API](research-api.md)
- [Analysis metrics](analysis-metrics.md)
