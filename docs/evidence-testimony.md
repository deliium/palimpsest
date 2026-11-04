# Evidence and testimony

V4-08 deepens the owned `legal_disputes` context with a general,
owner-scoped social evidence ledger. Evidence is one owner's belief about a
source, its provenance, an optional chain of custody, the owner's confidence,
the owner's interpretation, and the contradictions that owner retains. It is
never truth.

The evidence ledger is active exactly when `legal_disputes` is enabled on
`runner-config-v56`. V4-08 adds no capability flag, runner schema
(`runner-config-v57` does not exist), root field, per-agent runner key, command,
event, observer semantic type, write pair, `/v2` route, or migration.

## What evidence can and cannot do

Evidence controls only the owner's own beliefs and deliberation inputs. It never
controls objective action, admission, physical rules, world state, memory
correction, prompts, stop selectors, or observer semantics. A socially contested
but physically possible command is still admitted; a physically impossible
command is still rejected.

There is no evidence oracle, truth engine, proof engine, authenticator,
verifier, chain-of-custody authority, polygraph, lie detector, witness
authority, evidence registry, court, verdict, guilt, liability, authenticity,
or binding finding. Witnesses may misremember, records may be wrong, and
artifacts may be misinterpreted; the ledger keeps the owner's version.

## Sources

Seven requested kinds plus a closed `unknown`:

- witness testimony
- written record
- artifact
- physical state
- prior agreement
- reputation
- remembered event
- unknown

A source records an owner-visible reference anchor, an optional attributed actor,
a tick, an integrity belief, and a separate opaque correlation token. Sources
are collected from the owner's own observation, recall, commitments, and
reputation; no peer ledger or objective event body is copied.

## Provenance

Every source records a closed provenance channel (`direct_observation`,
`communicated`, `remembered`, `recorded`, `derived`, `inferred`, `unknown`), an
owner-visible reference anchor, the tick, an optional attributed actor, and a
separate opaque correlation token. The correlation token is used only for
researcher-only alignment; it is never dereferenced or treated as a world event.

## Chain of custody

Custody is recorded only for artifact, written-record, and physical-state
sources, as an ordered belief chain of holder, repository custodian, location,
and observer links. Statuses are `not_applicable`, `complete_belief`,
`incomplete_belief`, `conflicting_belief`, and `unknown`.

Missing links are never synthesized. A gap or same-tick disagreement is visible
and retained; it is never repaired or compared with objective state inside
cognition. `witnessed` records only that the owner believes a link was witnessed,
not that a witness objectively exists.

## Confidence

Confidence is the owner's quantized confidence in the source as understood. It
is never a probability of truth. Confidence is quantized to a policy-defined
step and bounded to `[0.0, 1.0]`; trust weights are integer basis points.

## Agent interpretation

Owners interpret a source as `supports`, `contradicts`, `ambiguous`,
`insufficient`, `irrelevant`, or `unknown` with respect to a subject token. No
free text or objective meaning is stored. An interpretation may be retracted, and
the row remains with status `retracted` rather than being deleted.

## Contradictions

A contradiction links two owner-local references with a closed kind and a
status: `unresolved`, `owner_prefers_first`, `owner_prefers_second`, or
`withdrawn`. Both rows are retained. Preferring one side is an explicit,
revisable owner belief, never a truth finding. Conflicting memories, records, and
interpretations coexist; analysis may classify alignment for researchers only.

## Witness testimony and independence

Direct and communicated testimony are distinct. A communicated retelling must
carry a root, a direct testimony must not, and shared roots are never independent
corroboration. A speaker cannot attribute testimony to another party: the frame
guard compares the declared witness with the verified speaker. Testimony travels
as one bounded `ev_v1` relation inside existing `Talk`/`Ask`/`Tell`; no command or
event type is added.

## Evaluation under the owner's own trust models

Evaluation may use only the owner's own direct experience, directed relationship
trust, reputation bands, role authority, rule authority, or institution
membership. There is no global trust score, no peer-ledger read, and no trust
oracle. Missing trust information yields a neutral confidence and an
`evidence_trust_basis_missing` notice. No evaluation writes to memory, beliefs,
relationships, reputation, rules, or world state.

## Objective alignment (researcher only)

Detached analysis may compare evidence rows with committed objective history and
classify the relationship as `consistent`, `unresolved`, `inconsistent`, or
`not_applicable`. That comparison is researcher-facing only. It never reaches
cognition, prompts, memory, world state, stop selectors, or observer semantics,
and it never changes the owner ledger. It is never a verdict, authenticity
claim, guilt, liability, or a correct account.

Three layers are strictly separated: objective aggregate counts, owner-scoped
rows with safe owner tokens, and `evid-` analytical candidates. A layer leak is a
hard failure.

## Snapshot, publication, and routes

`evidence-testimony-snapshot-v1` is canonical, bounded, immutable after
publication, and stored atomically by `evidence-testimony-store-v1`. Publication
is opt-in, post-completion, quota-bounded, and isolated from scientific status:
a storage or composition failure changes only the receipt.

Six GET-only routes require `SUBJECTIVE_DEBUG`:

- `GET /v1/simulations/{run_id}/evidence`
- `GET /v1/simulations/{run_id}/evidence/candidates`
- `GET /v1/simulations/{run_id}/evidence/candidates/{candidate_id}`
- `GET /v1/simulations/{run_id}/evidence/candidates/{candidate_id}/sources`
- `GET /v1/simulations/{run_id}/evidence/candidates/{candidate_id}/contradictions`
- `GET /v1/simulations/{run_id}/evidence/lineage`

Unconfigured storage returns `503 evidence_testimony_disabled`. Cursors bind run,
publication, digest, purpose, filter, and offset; a changed binding fails with
`400 evidence_testimony_cursor_invalid`, and expiry with
`410 evidence_testimony_cursor_expired`. The Research UI **Evidence** tab is
read-only and renders server fields without deriving truth, authenticity, guilt,
liability, or a winning account.

## Metrics

The metric catalog appends three families, raising the count from 154 to 157:

- `evidence_source_structure@1`
- `evidence_provenance_continuity@1`
- `evidence_objective_alignment@1`

The first 154 families keep their id, order, version, and value keys. See
[analysis-metrics.md](analysis-metrics.md) for value keys and denominator rules.

## Configuration

- `PALIMPSEST_EVIDENCE_ROOT` — optional snapshot store root. Unset disables the
  read service and yields `503 evidence_testimony_disabled`.
- `PALIMPSEST_EVIDENCE_CURSOR_KEY` — optional cursor signing key (at least 32
  UTF-8 bytes); keeps cursors restart-stable.
- CLI: `--evidence-root`, `--evidence-max-publications` (1–1024),
  `--evidence-max-bytes` (1–268435456).

## Limits and non-goals

- Adding a V4 flag, `runner-config-v57`, a new context, a runner root field, or a
  per-agent runner key is out of scope. V4-08 deepens `legal_disputes` only.
- No EvidenceOracle, TruthEngine, ProofEngine, Authenticator, Verifier,
  ChainOfCustodyAuthority, Polygraph, LieDetector, WitnessAuthority,
  EvidenceRegistry, global evidence registry, verdict, guilt, liability,
  authenticity, or binding finding exists.
- `WorldEngine`, perception, admission, stop selectors, memory, prompts, observer
  semantics, and the Godot client never read an evidence ledger.
- No evidence helper returns, constructs, submits, or resolves an `AgentCommand`,
  moves a resource, or executes a physical action.
- A source, testimony, record, artifact, custody claim, confidence,
  interpretation, evaluation, or contradiction is never objective truth, proof,
  authenticity, permission, prohibition, guilt, liability, or a binding finding.
- Sources, testimony, interpretations, contradictions, and evaluations are never
  inferred from silence, an unobserved act, or another owner's ledger.
- Conflicting memories, records, or interpretations are never reconciled into one
  authoritative account. Analysis may classify alignment for researchers only.
- A peer owner's relationship, reputation, commitment, rule, office,
  institution, organization, or evidence ledger is never read to evaluate
  evidence.
- No new event, command, observer semantic type, write pair, artifact kind,
  durable-record genre, `/v2` route, `observer-protocol-v2` serving, or SQL
  migration is added.
- The V3 mediation, structured-commitment, subjective-value, institution,
  office, durable-record, and V4 organization/formal-rule/dispute contracts are
  not rewritten; evidence is additive.
- No other V4 context (`diplomacy`, `organized_conflict`,
  `infrastructure_networks`, `supply_chains`, `markets_credit`, `science`,
  `epidemics`, `ecological_feedback`, `disasters`, `societal_resilience`,
  `macro_society_identity`, or another organization/formal-rule/dispute
  extension) is implemented here.

## Non-claims

This contract claims no prevalence, emergence probability, predictive power,
accuracy, or reliability of witnesses in general, and no moral correctness. It
does not produce a composite evidence-quality score. It does not decide which
account is true, who is guilty or liable, or which party should win.

## See also

- [Disputes](disputes.md)
- [Analysis metrics](analysis-metrics.md)
- [Research UI](research-ui.md)
- [Research API](research-api.md)
- [Configuration](configuration.md)

Current catalog note: the evidence families remain in place, and the current
closed catalog is **164** families after the V4-09 representation and V4-10
diplomacy appends.
