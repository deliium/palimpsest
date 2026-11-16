# Scientific hypotheses

## Purpose and scope

V4-27 extends the owned `predictive_world_model` and bounded-experimentation
seams into explicitly testable hypotheses under policy
`scientific-hypotheses.v1`. A hypothesis is one owner's belief. It is never an
objective rule, truth value, or shared registry. A test may record a
`causal_hypothesis_id` lineage link, but that link is not proof; the trial
scores the experiment's own predicted outcome.

## Activation

Science activates only when all of the following are present:

- `runner-config-v56`
- `v4_capability_flags.science`
- `capability_flags.predictive_world_model`
- `bounded_experimentation` (with its existing cultural history and provenance
  prerequisites)

`science=False` is inert. There is no `runner-config-v57`, no new runner root
field, and no per-agent `hypothesis_mode`.

## Owner ledger

The owner-scoped `ExperimentLedger` records:

- the claim (`HypothesisClaim`)
- conditions (ten closed observation slots)
- predicted result (`ExperimentOutcomeClass`)
- confidence milli
- supporting observations (`evidence_event_ids`)
- contradictions (`counter_evidence_event_ids`)
- creator/source (`HypothesisSourceKind` and token)
- formulation tick (`created_tick`) and status
- append-only historical revisions with `revision_tick`

## Conditions

`location`, `day_phase`, `weather`, `held_item_kind`, `counterpart`, `season`,
`temperature_band`, `hazard`, `action`, `concept`.

No objective law, rule row, probability, delta, product identifier, or harm band
can be a condition. An absent observed attribute is unsatisfied.

## Predicted result and matching

Predictions use `ExperimentOutcomeClass`: `success`, `partial_success`,
`failure`, `harm`, `unexpected`. Matching is strict equality except that
`unexpected` is always a contradiction.

## Confidence

Confidence is an integer support ratio
`(support + 1) / (support + counter + 2)` in milli (`0..1000`). It is not a
probability, accuracy, calibration, or score.

## Status

`provisional`, `supported`, `contradicted`, `inconclusive`, `superseded`,
`retired`. Hypotheses can be wrong. Contradictions are retained, and a
`contradicted` hypothesis remains queryable.

Source kinds are `self_formulated`, `observed`, `remembered`, `communicated`,
`recorded`, and `unknown`.

## Intentional tests

When science is deterministic, an agent whose selected command is a default
`Wait` may replace it with one existing `Experiment` command. Conditions must
hold and the per-tick trial cap must allow it. A meaningful command is never
overridden, and no new command or event is added.

## Communication

`hyp_v1` claims travel inside existing `Talk`/`Tell` speech. Adoption is
testimony, not evidence: it creates a provisional row with zero support and zero
contradictions, and copies no evidence ids. The source token is the receiving
owner's observed delivery event, never the sender's agent id.

## Revisions

Revisions are append-only with monotonic indexes and ticks, bounded at 32 per
hypothesis. Reasons include `formulated`, `prediction_revised`,
`condition_revised`, `support_added`, `contradiction_added`,
`confidence_revised`, `source_adopted`, `test_formulated`, `superseded`, and
`retired`.

## Analysis

Detached analysis uses 32-tick windows, at most 512 windows, and
`min_samples=3`. It emits six independent families:

- `scientific_hypothesis_structure`
- `scientific_hypothesis_evidence`
- `scientific_hypothesis_test_activity`
- `scientific_hypothesis_revisions`
- `scientific_hypothesis_provenance`
- `scientific_hypothesis_prediction_outcomes`

Families report counts and milli shares only. No composite scientific score,
truth value, accuracy, or calibration exists.

## Artifact

Canonical `scientific-hypotheses-snapshot-v1` is published programmatically after
completion through `scientific-hypotheses-store-v1`, which is atomic,
quota-bounded, idempotent, and corruption-safe. The snapshot carries no
wall-clock or owner field.

Seven GET-only routes require `SUBJECTIVE_DEBUG` and both gated settings:

- `/v1/simulations/{run_id}/scientific-hypotheses`
- `.../scientific-hypotheses/hypotheses`
- `.../scientific-hypotheses/evidence`
- `.../scientific-hypotheses/tests`
- `.../scientific-hypotheses/revisions`
- `.../scientific-hypotheses/sources`
- `.../scientific-hypotheses/coverage`

Errors: `scientific_hypotheses_disabled` (503),
`scientific_hypotheses_run_not_found` (404),
`scientific_hypotheses_store_corrupt` (500),
`scientific_hypotheses_cursor_invalid` (400),
`scientific_hypotheses_cursor_expired` (410).

Settings: `PALIMPSEST_SCIENTIFIC_HYPOTHESES_ROOT` and
`PALIMPSEST_SCIENTIFIC_HYPOTHESES_CURSOR_KEY` (at least 32 UTF-8 bytes).

## Limits and non-goals

No objective truth registry, global encyclopedia, scripted discovery,
technology tree, new command, new event, new write pair, runner v57, SQL
migration, or Godot overlay. Owner ids and objective rule payloads never reach
analytical rows, the snapshot, routes, or the Research UI.

## Experiment

`scientific_hypotheses` is off the V1 A-E gate and has three arms:
`science-baseline` (inert), `science-enabled`, and `science-communicated`.

## Pins

17 V4 contexts, 12 flags, 9 owned / 3 unowned (`epidemics`,
`ecological_feedback`, `disasters`), `v4-context-map-v5`, 250 metric families,
43 commands, 73 observer semantic types, replay-v27/codec `v25`, Alembic
`0017`, `/v1`, and `observer-protocol-v1`.
