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

## What evidence controls, and what it never controls

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

## Source kinds

Seven requested kinds plus a closed `unknown`:

- witness testimony
- written record
- artifact
- physical state
- prior agreement
- reputation
- remembered event
- unknown

## Provenance

Every source records a closed provenance channel (`direct_observation`,
`communicated`, `remembered`, `recorded`, `derived`, `inferred`, `unknown`), an
owner-visible reference anchor, the tick, an optional attributed actor, and a
separate opaque correlation token. The correlation token is used only for
researcher-only alignment; it is never dereferenced or treated as a world event.

Direct and communicated testimony are distinct. A communicated retelling must
carry a root, a direct testimony must not, and shared roots are never independent
corroboration. A speaker cannot attribute testimony to another party: the frame
guard compares the declared witness with the verified speaker.

## Chain of custody

Custody is recorded only for artifact, written-record, and physical-state
sources, as an ordered belief chain of holder, repository custodian, location,
and observer links. Statuses are `not_applicable`, `complete_belief`,
`incomplete_belief`, `conflicting_belief`, and `unknown`.

Missing links are never synthesized. A gap or same-tick disagreement is visible
and retained; it is never repaired or compared with objective state inside
cognition.

## Confidence and interpretation

Confidence is the owner's quantized confidence in the source as understood. It
is never a probability of truth. Owners interpret a source as `supports`,
`contradicts`, `ambiguous`, `insufficient`, `irrelevant`, or `unknown` with
respect to a subject token. No free text or objective meaning is stored.

## Contradictions

A contradiction links two owner-local references with a closed kind and a
status: `unresolved`, `owner_prefers_first`, `owner_prefers_second`, or
`withdrawn`. Both rows are retained. Preferring one side is an explicit,
revisable owner belief, never a truth finding.

## Trust evaluation

Evaluation may use only the owner's own direct experience, directed relationship
trust, reputation bands, role authority, rule authority, or institution
membership. There is no global trust score, no peer-ledger read, and no trust
oracle. Missing trust information yields a neutral confidence and an
`evidence_trust_basis_missing` notice.

## Researcher-only objective alignment

Detached analysis may compare evidence rows with committed objective history and
classify the relationship as `consistent`, `unresolved`, `inconsistent`, or
`not_applicable`. That comparison is researcher-facing only. It never reaches
cognition, prompts, memory, world state, stop selectors, or observer semantics,
and it never changes the owner ledger. It is never a verdict, authenticity
claim, guilt, liability, or a correct account.

Three layers are strictly separated: objective aggregate counts, owner-scoped
rows with safe owner tokens, and `evid-` analytical candidates. A layer leak is a
hard failure.

## Metrics

The metric catalog appends three families, raising the count from 154 to 157:

- `evidence_source_structure@1`
- `evidence_provenance_continuity@1`
- `evidence_objective_alignment@1`

The first 154 families keep their id, order, version, and value keys. See
[analysis-metrics.md](analysis-metrics.md) for value keys and denominator rules.

## Publication and read surfaces

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
`400`, and expiry with `410`. The Research UI **Evidence** tab is read-only and
renders server fields without deriving truth, authenticity, guilt, liability, or
a winning account.

## Configuration

- `PALIMPSEST_EVIDENCE_ROOT` — optional snapshot store root.
- `PALIMPSEST_EVIDENCE_CURSOR_KEY` — optional cursor signing key (at least 32
  UTF-8 bytes).
- CLI: `--evidence-root`, `--evidence-max-publications` (1–1024),
  `--evidence-max-bytes` (1–268435456).

## See also

- [Disputes](disputes.md)
- [Analysis metrics](analysis-metrics.md)
- [Research UI](research-ui.md)
- [Research API](research-api.md)
