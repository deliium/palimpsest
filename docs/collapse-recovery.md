# Collapse and recovery

[← Societal resilience](societal-resilience.md) · [Back to README](../README.md) · [Configuration →](configuration.md)

Detached analysis-only composition owned by V4-41. Opt-in capture over an
ordinary finalized run produces a programmatic `collapse-recovery-report-v1`
with **eight independent indicator axes**, reversible episode annotations, and
a forward-only societal succession graph. There is no `CivilizationCollapsed`
boolean, composite score, root-cause diagnosis, or world authority.

## Scope

| Axis (group) | What is measured |
| --- | --- |
| `population_decline` (people) | Living bodies at window end vs prior complete window |
| `institutional_failure` (continuity) | Same-owner recognition-lapse proxy among surviving carriers |
| `knowledge_loss` (continuity) | Owner/content retention; technique union is descriptive only |
| `trade_disruption` (material) | Completed exchanges per person-tick |
| `infrastructure_decay` (material) | Surviving operational asset IDs vs baseline set |
| `migration` (people) | Cross-region journey arrivals (regional net; run-wide gross) |
| `conflict` (security) | Committed attack receipt counts per person-tick |
| `production_decline` (material) | Successful harvest/craft completions per person-tick |

Fixed 32-tick half-open windows from tick 0. Episode policy
`collapse-recovery.v1` requires ≥5 comparable axes, ≥3 stressed spanning ≥2
groups with at least one non-people stress, confirmed across two adjacent
windows against a **frozen** baseline. Recovery needs two adjacent cleared
assessments. Missing evidence never means “no collapse.”

Societal lineage is independent of collapse classification: window-local
candidates from communication, cooperative interaction, and completed exchange
edges; conservative continuation/split/merge edges; institution and technique
continuity annotations without publishing membership or key IDs.

## Programmatic capture

Capture is off by default. Disasters are not required. Trusted research code
opts in once:

```python
from experiments.collapse_recovery_capture import run_with_collapse_recovery_capture
from analysis.collapse_recovery_report_codec import encode_collapse_recovery_report

captured = await run_with_collapse_recovery_capture(runner, capture=True)
if captured.report is None:
    # disabled, unsupported, aborted, sealed-without-report, or report_failed
    ...
else:
    payload = encode_collapse_recovery_report(captured.report)
    # callers may save bytes; nothing is auto-persisted
```

Requires a fresh empty-history runner with horizon in `1..512` and at most 128
registered bodies. Capture never installs an arbiter, stop selector, or
observer mode. Capture-off and capture-on preserve committed execution and
`objective_state_hash` parity on the V4-39 drought specimen.

Schema: `collapse-recovery-report-v1`. Policy: `collapse-recovery.v1`. Codec
rejects score/authority fields, unknown keys, booleans-as-ints, one-child
splits, dangling edges, and non-canonical bytes. Public bytes never include
body, concept, or technique key identifiers.

## Coverage distinctions

| Situation | Report behavior |
| --- | --- |
| Channel disabled / source off | Axis `unavailable` / `channel_off` |
| Enabled empty / fully observed | Known-zero counts where defined |
| Attribution gap / incomplete clock | Lineage window `unknown` |
| Empty roster / no two-lane candidate | Lineage `observed_empty` |
| Capture gap / missing projection | `partial`; no imputation |
| Truncated run | Partial final window; open episodes may censor |
| Owner source off / unsupported | Continuity coverage `unavailable`; edges kept |

## Worked split with continuity and branch loss

Eight living members form one two-lane candidate in `[0,32)`, then two
four-member cliques in `[32,64)`. The graph emits one parent and two
`split_successor` edges with four unambiguous witnesses each. Same-holder
institution recognition can remain continuous on both branches while one
branch loses a technique key that the sibling still holds. Two adjacent
continuation windows of cohort-stable absence confirm `observed_branch_loss`
on the confirmation node — sibling retention does not invalidate branch-local
loss, and absence is not extinction.

A decline episode can recover while a technique remains absent in a branch; a
split can occur with no collapse episode at all.

## Caps

Horizon 512, roster 128, regions 64, infrastructure 512, frame rows 4096,
cumulative frame rows 262144, raw events 50k, receipts 100k, 64 candidates per
window, 256 links per boundary, report payload 8 MiB. Overflow seals the
prefix; report size or validation failure returns `report_failed` with the run
result unchanged.

## Interpretation limits

- Indicators are fixed-region physical/scoped proxies, not a census of
  analytical societies.
- Institutional “failure” is recognition lapse among living carriers, not an
  objective authority ending.
- Technique absence is observed branch-local loss, not irreversible extinction.
- Region presence is projected location, not residence or polity membership.
- Succession edges are evidence-backed observations, not inheritance of
  collapse labels.
- Quiet runs and fully unavailable lanes are valid outcomes.
- No `CivilizationCollapsed` flag feeds cognition, memory, prompts, stop
  selection, observer, API, or clients.

## Verification

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_collapse_recovery*.py \
  tests/architecture/test_collapse_recovery_boundaries.py -q
```

See [Societal resilience](societal-resilience.md) for the adjacent shock-aligned
panels and [Development](development.md) for focused commands. Real-run drought
parity qualifies non-interference; synthetic fixtures exercise episode and
graph mechanisms without claiming prevalence or causality.

## See Also

- [Societal resilience](societal-resilience.md)
- [Disasters](disasters.md)
- [Development](development.md)
