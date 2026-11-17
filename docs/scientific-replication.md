# Scientific Replication

V4-28 deepens the owned `science` context with owner-scoped replication. A design
is testimony, not truth. One owner repeats another owner's described procedure
using its own visible materials and ordinary `Experiment` admission.

## Activation

Scientific replication activates only when the existing `science` prerequisites
are active: accepted `runner-config-v56`, `science`, `predictive_world_model`,
and a `bounded_experimentation` spec. No new V4 flag, context, runner root field,
command, event, observer semantic type, write pair, API version, or migration is
added. `science=False` stays inert.

## Designs and lineage

`ExperimentDesign` freezes operator, process token, selectors, prediction,
conditions, parent design, source hypothesis, and source trial. The design token
is `rdes-` plus 32 hex characters over the canonical full payload, excluding the
token itself. A revision is a new parent-linked design, never mutation of the
prior design. Exact selectors carry received reference data; `same_kind`
selectors let a receiver bind an equivalent own material. Binding uses only
current observation data and never another owner's private ledger.

## Attempts, results, and uncertainty

`ReplicationAttempt` states are `planned`, `proposed`, `observed`, `rejected`,
`unresolved`, and `cancelled`. Only an actor-visible matching
`experiment_resolved` occurrence yields `observed`. Missing or ambiguous results
remain unresolved; a rejection carries no measurement.

`ReplicationMeasurement` uses categorical `outcome_class` resolution. Current
physics exposes five categories, not calibrated numeric error bars.
Uncertainty is explicitly `unreported` or a `declared_set`; `unreported` never
means zero error. A communicated report is normalized to `communicated` basis
while the source's declared basis is preserved separately.

## Social testimony

`rep_v1` documents travel inside existing `Talk`/`Tell` as at most eight world
relations. Each object is a 37-character header plus at most 219 payload
characters, so a document is at most 1,752 encoded bytes. Parsing is
all-or-nothing within one delivered utterance; there is no cross-utterance
reassembly cache. `hyp_v1` remains unchanged.

Designs, results, invitations, participation, declines, and interpretations are
delivered testimony only. Automatic testing requires a delivered complete design
plus a delivered invitation and local acceptance. Design delivery alone does not
execute. A contested source is retained but is not automatically recruited. An
explicit owner-local `request_replication` may test an already delivered design.

Participation is attributed speech by an individual speaker. There is no group
actor, roster, organization executor, quorum, majority, or global experiment
registry. Repeated reports sharing one root are not independent corroboration.

## Interpretation and conflict

Each owner keeps append-only interpretations over retained reports. Categorical
appraisal is `compatible`, `conflicting`, `inconclusive`, or `not_comparable`.
Changed known conditions are not comparable; unknown conditions are
inconclusive. Different categories under matched conditions are retained as
conflicting. Trusted or unknown testimony may motivate inquiry; it never adds
borrowed evidence mass. No count of replications sets a hypothesis, design, or
report to `true`.

## Transactions and recovery

Science-enabled candidates are detached during `prepare`/`complete` and install
only after objective finalization. Abort discards candidates. A replaced
effective command discards its proposed attempt and test-formulated candidate.
An original local test retains a pre-action source draft and freezes its source
design only after the actor-visible result.

Pending finalization uses `finalization-command-v2` only for science/replication
transitions, carrying nested `replication-state-v1` and
`scientific-experiment-state-v1` records. Legacy `finalization-command-v1`
bytes and exact keys are unchanged. Pending v2 is not a world codec and does not
provide complete durable subjective restart. Existing forks and retirement carry
the committed owner sidecar transitively; newborns start empty.

## Detached research evidence

`analysis.replication_*` consumes neutral facts and committed execution
receipts, never cognition ledgers. It preserves objective execution receipts and
owner reports as a tagged `results` union, derives qualified comparisons, and
exposes six descriptive families:

- `scientific_replication_design_lineage@1`
- `scientific_replication_conditions@1`
- `scientific_replication_results@1`
- `scientific_replication_uncertainty@1`
- `scientific_replication_relationships@1`
- `scientific_replication_social_interpretation@1`

The catalog appends these after the historical 250 families, for 256 total.
Distinct events prove distinct executions, not statistical independence.

## Publication and reads

`scientific-replication-snapshot-v1` is an immutable sibling artifact with
canonical JSON, an internal SHA-256 digest, and `srep-` publication identity.
`scientific-replication-store-v1` stores it atomically with per-run quotas.
Publication is programmatic and opt-in after scientific completion; reads never
compose analysis or enable capture.

Set both `PALIMPSEST_SCIENTIFIC_REPLICATION_ROOT` and a
`PALIMPSEST_SCIENTIFIC_REPLICATION_CURSOR_KEY` of at least 32 UTF-8 bytes to
attach the reader. Missing settings keep the eight GET-only
`/v1/simulations/{run_id}/scientific-replication` routes disabled with
`scientific_replication_disabled`.

Routes: summary, `/designs`, `/attempts`, `/results`, `/comparisons`,
`/interpretations`, `/collaborations`, `/coverage`. They require
`SUBJECTIVE_DEBUG`, pin a publication, bind cursors to run/publication/digest
and filters, and reject unsupported filter combinations. The Research UI renders
a read-only panel with separate objective and owner-report lanes and explicit
unknown uncertainty and coverage.

## Non-goals

No objective hypothesis truth, N-replication promotion, majority consensus,
scientific merit score, calibrated numeric intervals, general multi-hop
testimony graph, cross-run live evidence import, Godot overlay, `/v2`, SQL
migration, or civilization throughput claim.
