# Competing theories

Owner-scoped, incompatible scientific explanations that coexist without a
global winner. Support and predictive accuracy are independent axes; neither
updates the other.

## Activation

Competing theories deepen the owned `science` V4 capability and use the same
prerequisites as scientific models:

- `predictive_world_model` enabled;
- a `bounded_experimentation` spec;
- `V4CapabilityFlags.science`.

`science=False` is inert. There is no new capability flag, context, command,
event, migration or `runner-config-v58`. Speech uses a bounded `thy_v1` frame
inside existing `Talk`/`Tell`; the world protocol is unchanged. Pending
transitions use `finalization-command-v5` with
`competing-theory-state-v1`; default pending remains v1.

## Two fallible accounts

Each owner keeps a bounded `CompetingTheoryLedger`. A theory context is a
season or net visible resource-change target at one location, origin season,
resource kind and unit. Two closed accounts are available:

- `continuity` — the current season persists, or visible quantity stays
  unchanged;
- `recurrence` — a previously observed matching two-tick transition recurs.

Claim identity is content-addressed from the context, account and predicted
category. Author, seed outcome, social support and display name do not change
identity. Rivals require the same context and a different predicted category.

## Evidence and citations

`TheoryCitation` records the citing owner, claim, tick, polarity (`supports`,
`contradicts`, `context_only`), kind (`own_observation`, `own_scored_case`,
`delivered_claim`, `declared_pointer`) and opaque provenance/root references.
Only the owner's resolved observations and scored cases count as independent
roots. Delivered and declared pointers remain testimony; shared roots are not
independent corroboration. Duplicate rows are no-ops and citations are bounded
per owner.

## Same-case forecasts and failures

A theory forecast is issued only on a just-admitted V4-30 season/resource case.
Up to four available claims are frozen with the existing 2:1 categorical
distribution; support never enters the distribution. The case targets the same
`t+2` owner observation. Settlement records `hit` or `failure` for each claim,
the observed category, the opaque outcome reference, an integer Brier numerator
and a terminal tick. Missing, late, foreign or non-comparable observations are
explicit non-scoring statuses, never failures. Pending cases remain right-
censored. A claim cannot enter after issuance.

## Support, communication and teaching

`thy_v1` carries exactly two relations: `claim` then `context`. Acts are
`share`, `support`, `withdraw` and `teach`. The frame is canonical
percent-escaped UTF-8, bounded per object and per utterance. Malformed frames
are ignored without suppressing ordinary speech.

Only prior committed, addressed delivery to the owner counts. A sender echo is
not learner evidence. Teaching is a receipt; it grants no practical skill and
never becomes verified evidence. Withdrawals apply only to the matching
speaker's claim. A local stance switches only when a rival has strictly more
distinct live origin endorsers; ties keep the current stance. When no stance
exists, a claim with at least two distinct addressed origin endorsers is
adopted first; only when no social alternative qualifies does the one-time
deterministic prior seed an originating preference between continuity and the
first local recurrence, after which it is consumed. Stance selection never
consults scores, failures, forecast confidence, group identity or global counts.

## Detached analysis

`analysis.competing_theories_*` consumes only tokenized completed-run facts.
It builds 32-tick windows (latest 512 retained), owner-to-claim support edges
from the latest admitted stance, weakly connected support communities per
claim/window, directed communication/teaching edges, citation aggregates and
matched performance buckets. Communities are analytical; they are not
organizations and confer no truth or authority. Popularity is never used to
rank predictions, and accuracy is never used to move support.

Six append-only families extend the catalog from 262 to **268**:

- `competing_theory_structure`
- `competing_theory_support_network`
- `competing_theory_citations`
- `competing_theory_predictions`
- `competing_theory_failures`
- `competing_theory_transmission`

## Publication, store and reads

`competing-theories-snapshot-v1` carries sorted `theories`, `support`,
`citations`, `predictions`, `failures`, `transmission` and `coverage` sections
with explicit omitted windows and first retained boundary. Prediction rows are
per case/claim and retain the frozen probability vector and observed outcome;
failure rows project observed misses only. Publication admits whole newest
windows plus their claim dependencies, stops before a section-row or 8 MiB
envelope overflow, and reports the omitted windows; an envelope that cannot fit
returns `quota_exceeded` rather than a partial artifact.
`competing-theories-store-v1` publishes atomically with digest verification and
cumulative per-run quotas; readers never write, repair or fall back to a newer
publication.

Settings are paired and optional:

- `PALIMPSEST_COMPETING_THEORIES_ROOT`;
- `PALIMPSEST_COMPETING_THEORIES_CURSOR_KEY` (at least 32 UTF-8 bytes).

Neither means disabled; exactly one is invalid. Eight GET-only routes live under
`/v1/simulations/{run_id}/competing-theories` (summary plus seven sections) and
require `SUBJECTIVE_DEBUG`. Cursors pin run, publication, digest, section,
filters, limit and position. The Research UI adds a read-only **Competing
theories** panel that renders declared support and observed performance
separately and labels citations and teaching as testimony.

## Non-goals

No global theory registry, consensus, majority ballot, universal winner, truth
inference, theory score, group actor, raw cross-owner export, new world
mutation path or analysis feedback into cognition. Autonomous nulls are legal.

## Verification

```bash
uv run --frozen --python 3.12.14 pytest -q tests/unit/test_competing_theories_*.py
uv run --frozen --python 3.12.14 pytest -q tests/architecture/test_competing_theories_boundaries.py
uv run --frozen --python 3.12.14 pytest -q -m integration tests/integration/test_competing_theories_runner.py
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src tests
uv run --frozen --python 3.12.14 lint-imports
pnpm --dir clients/research-ui test
pnpm --dir clients/research-ui check
pnpm --dir clients/research-ui build
```

### Verification receipt (2026-11-20)

Executed: default unit/architecture suite (green, 80% coverage; 12768 passed,
4 skipped, 170 deselected at the recorded run), focused competing-theory suites, the controlled
coexistence fixture and real runner→store→authorized GET integration lane, Ruff,
mypy, import-linter, Research UI vitest/check/build, V1 regression and V2
scientific invariants. PostgreSQL, Compose/browser, Godot and scale lanes were
not executed for this feature and are not claimed. Autonomous runs may produce no
disagreement; the controlled fixture demonstrates possibility, not prevalence.
The runner result API does not expose raw submitted frame bytes: the suite
asserts canonical `thy_v1` frame equality before attachment and verifies
addressed delivery through committed observations and exported receipts.

## See also

- [Scientific models](scientific-models.md)
- [Scientific hypotheses](scientific-hypotheses.md)
- [Scientific replication](scientific-replication.md)
- [Measurement instruments](measurement-instruments.md)
- [Configuration](configuration.md)
- [Research UI](research-ui.md)
