[← Research causal debugger](research-causal-debugger.md) · [Back to README](../README.md) · [Institutional memory →](institutional-memory.md)

# Institutional decay

Institutional decay is an **opt-in, owner-scoped subjective** process. An agent
may stop recognizing a recurring role/procedure pattern when its own fresh
evidence no longer renews the supporting channels. Nothing here creates an
objective institution, schedules a collapse, removes permissions, transfers
property, or forces a command. Collapse, transformation, split and reappearance
are **detached analytical classifications**, never world events.

## Configuration

`institutional_decay_mode` is per-agent and defaults to `disabled`. Enabling it
requires `runner-config-v54` and requires that **same owner** to enable
`institution_concept_mode`. Office succession and institutional memory are
optional companions. Older schemas reject the new key; v54 requires at least one
enabled decay owner. The default runner write remains `runner-config-v4`.

Exact v54 cognition keyset = the v53 keyset plus `institutional_decay_mode`.
Institutional memory profiles remain accepted on v53 and v54; the institutional
memory learner profile stays decay-disabled and content-empty.

## Six strengths versus five dimensions

Institution concepts retain six private strength channels:

`role_recognition`, `procedure_recurrence`, `social_expectation`,
`legitimacy_belief`, `succession_observed`, `generational_continuity`.

Decay does not rename or average those strengths into a health scalar. Separately,
the research layer tracks five dimensions:

| Dimension | Numerator | Denominator |
|---|---|---|
| Support | distinct independently evidenced supporters | stable observed cohort |
| Participation | distinct actors with fresh accepted actions | stable observed cohort |
| Procedure repetition | covered updates with fresh performed procedure | four covered updates |
| Succession continuity | completed eligible transitions | eligible transitions |
| Knowledge continuity | retained before-entry pairs | before-entry pairs |

Missing scope or denominators are `unknown`, `disabled`, `partial`, or
`not_applicable`; they are never silently converted to zero. Actor ratios are
reported against an **observed cohort**, not total population or objective
eligibility.

## Subjective attrition

The locked policy is `institutional-decay.v1`:

- channel loss: `0.04` per executed update for each channel receiving no fresh
  credit;
- unit clamp `[0,1]` with quantum `0.000001`;
- fresh evidence refreshes only the channels it supports;
- new patterns start from empty state;
- same-owner/same-tick repeats are idempotent; decreasing ticks fail closed;
- a skipped tick is one executed update, not synthetic elapsed-tick loss.

Recognition uses the existing institution-concept thresholds. Fresh legitimate
evidence can strengthen a retired pattern again; there is no rebirth event.

Retention is bounded per owner: 16 patterns, 256 raw samples, 512 receipts.
Samples prune by `(observation_tick, pattern)`; receipts by
`(source_tick, evidence_key)`. Per-pattern sample and receipt boundaries are
retained separately. Factual inception/activity witnesses survive sample
eviction, but they do not prove an unavailable earlier stable/collapsed state.

## Windows and lifecycle

Analysis uses four consecutive observation/update ticks as one window. Lifecycle
confirmation compares two adjacent non-overlapping windows, for example
`[t-7,t-4]` and `[t-3,t]`. Native source intervals are retained separately:
an observation timestamp is not an action timestamp.

Locked analytical policy: `institutional-lifecycle.v1`; strong `0.50`, low
`0.10`, renewal `0.30`, weakening decline `0.10`. These are descriptive research
thresholds, not rules of the world.

- **Emerging**: locally recognized pattern with fresh structural practice.
- **Stable**: recognized evidence in both windows, at least two available core
  measures at/above `0.50`, and fresh participation or repeated procedure.
- **Weakening**: prior stable history plus a comparable core or legitimacy
  decline of at least `0.10`.
- **Collapsed**: prior confirmed stability, two complete low/no-renewal windows,
  at least two core measures at/below `0.10` including participation or
  procedure, no core ratio above `0.30`, and no fresh associated practice.

Collapse is confirmed only at the second window end and is never backdated.
Missing visibility, denominators or history censor the result. End of run is
right-censoring, not collapse. Mechanisms such as legitimacy decline,
succession discontinuity, population loss, resource failure, record
unavailability, role abandonment, competing patterns and cultural change are
nonexclusive **descriptive associations**, not causal estimates.

## Episode identity and lineage

Episode identity is a hash of the lineage policy version, owner/scope, retained
local-pattern ID, absolute activity-span start, and structural-revision witness.
It never uses a sliding-history ordinal, current sample index, label, supporter
set or aggregate content hash.

Stable binding, anchor growth, occupant replacement, renaming and changed
support keep the same episode. A changed structural pattern can produce a
`transformed` or `split` edge only when it has the same context/function, at
least two shared structural component anchors, Jaccard overlap at least `0.50`,
and repeated successor practice. A local office predecessor may replace the
overlap test but still requires practice and time ordering. Ambiguous matches are
reported, not tie-broken. Pruned predecessors become explicit stubs with the same
absolute ID; a stub cannot prove prior stability, collapse or knowledge handoff.

`continued` edges are not transform/split/reappearance counts. A collapse followed
by renewed recognition on the same retained binding is `reappeared`; independent
reinvention is unrelated emergence.

## Metrics

Three versioned catalog families (126 → 129):

- `institutional_decay@1` — five dimension panels, comparable-window deltas,
  legitimacy strength, mechanism associations, coverage, and the canonical
  `dimension_trajectories_json` / `mechanism_evidence_json` strings.
- `institution_lifecycle@1` — scoped state counts, transitions, confirmation
  ticks, censoring, and `episodes_json`.
- `institution_lineage@1` — episode/root counts, confirmed and continued edges,
  ambiguity, pruning, and `lineage_graph_json`.

All scalar summaries remain ordinary metric values. Detailed graphs and
trajectories are canonical schema-tagged **JSON strings**; the shared metric
model and wire codec stay scalar-only. These strings are research output and are
never logged or consumed by cognition.

## Experiment BK

`institutional_decay@1` (Experiment BK) is off the V1 gate. Six opportunity arms:
`bk-baseline`, `bk-decay-off`, `bk-decay-on`, `bk-record-opportunities`,
`bk-teaching-opportunities`, `bk-limited-opportunities`. Arms change only
declared existing opportunities. No deaths, shocks, record destruction,
abandonment, competing institutions, cultural change or collapse ticks are
scheduled. An arm may produce no stable institution or no collapse; that is a
valid research outcome.

## Limitations

- Runtime checkpoint continuation of one owner's decay sidecar is supported.
  This is **not** a new durable subjective database or universal restart
  guarantee.
- Lineage and lifecycle conclusions are bounded by retained samples, receipts,
  witnesses and coverage. Whole-run history is not promised.
- Objective replay remains event-only; analytical output never feeds prompts,
  memory or the engine.
- No new command, event, observer semantic type, write-pair, migration, API route
  or capability flag is introduced. `institutional_economy` remains unowned.

## See also

- [Institutional memory](institutional-memory.md)
- [Configuration](configuration.md)
- [Analysis metrics](analysis-metrics.md)
- [Experiments](experiments.md)
- [Architecture](architecture.md)
