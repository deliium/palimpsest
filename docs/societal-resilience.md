# Societal resilience

[← Disasters](disasters.md) · [Back to README](../README.md) · [Configuration →](configuration.md)

Detached analysis-only shock-response panels owned by V4-40 under
`societal_resilience`. Opt-in capture over a finalized v63 disasters-active run
produces a programmatic `societal-resilience-report-v1` with **ten independent
aligned time series**. There is no universal resilience score, ranking, or
recommendation.

## Scope

| Dimension | What is measured |
| --- | --- |
| `population_recovery` | Living bodies, entries, deaths, living vs pre-shock milli |
| `migration` | Cross-region journey arrivals (not residence-qualified moves) |
| `resource_recovery` | Managed ecological stock quantity/capacity by kind+unit |
| `institution_continuity` | Owner-recognized concept key continuity |
| `knowledge_retention` | Owner/content pair retention |
| `technology_loss` | Living technique-key union absence (not extinction) |
| `cooperation` | Helps, feeds, contributions per person-tick |
| `inequality` | Held-item-count Gini among living bodies |
| `trade_network_recovery` | Exchange-venue corridor trajectory |
| `infrastructure_recovery` | Operational assets vs baseline IDs/slots |

Windows: one eight-tick pre-shock baseline, eight eight-tick follow-ups, plus an
immediate state point at `s+1`. Flows use half-open intervals; stocks use the
exclusive-end boundary. Immediate deltas compare to `s`, not the pre-window
aggregates — so a dip that recovers by the first full post window stays visible.

Not modeled: a composite score, polity-level “society” objects, automatic
persistence/HTTP/observer surfaces, causal attribution from a single arm, or
claims that absent technology keys are irreversible extinctions.

## Programmatic capture

Capture is off by default. Trusted research code opts in once:

```python
from experiments.resilience_capture import run_with_resilience_capture
from analysis.resilience_report_codec import encode_resilience_report

captured = await run_with_resilience_capture(runner, capture=True)
if captured.report is None:
    # disabled, unsupported, aborted, or report_failed
    ...
else:
    payload = encode_resilience_report(captured.report)
    # callers may save bytes; nothing is auto-persisted
```

Requires `runner-config-v63` with `disasters` configured, empty history at start,
and horizon ≤ 512 ticks. Capture never installs an arbiter, stop selector, or
observer mode. Flags-off / capture-off runs keep ordinary event and stop parity.

Schema: `societal-resilience-report-v1`. Policy token: `societal-resilience.v1`.
Codec rejects aggregate-score fields, unknown keys, booleans-as-ints, and
non-canonical bytes.

## Shock clocks and schedule status

Only **applied** `DisasterResolved` receipts start episodes. Co-tick applied
receipts share one episode. Overlapping later shocks censor follow-up windows.

| Schedule status | Meaning |
| --- | --- |
| `applied` | Matching scheduled receipt with applied outcome |
| `not_applied` | Matching scheduled receipt with a non-applied outcome (+ event id) |
| `not_reached` | Schedule tick beyond finalized horizon (null outcome/event id) |
| `unverified` | Schedule tick beyond capture prefix |
| `receipt_missing` | Reached schedule tick with no matching scheduled receipt |

Shock status: `observed` when any applied episode exists; `no_shock` only when
the prefix is complete with no applied receipt and no `receipt_missing` entry;
otherwise `unknown`. Control arms with empty schedules are `no_shock` without a
fabricated episode.

## Coverage distinctions

| Situation | Report behavior |
| --- | --- |
| Channel disabled | Lane cells `unavailable` / `channel_off` |
| Enabled empty / fully observed | Known-zero counts where defined |
| Capture gap / missing projection | `partial` / `projection_gap`; no imputation |
| Truncated run | Right-censored posts (`run_end`) |
| Owner unsupported while living | Owner coverage retained; numerical measures withheld |
| Baseline owner still alive, source off | Raw inventory may publish; baseline-relative fields withheld |

Owner coverage (`eligible_owners`, `observed_owners`) is metadata on the three
owner lanes — never a numerical measure and never includes owner or content IDs.

## Worked immediate dip

On the V4-39 drought specimen (seed 34, scheduled drought at tick 8, 24-tick
horizon), water quantity can fall between boundaries 8 and 9 while the first
complete post window ending at 16 already shows recovery. The immediate panel
still reports the `s+1` dip and signed delta; lack of recovery is also a valid
outcome, not a failed fixture.

## Caps

Roster 128, stocks 256, infrastructure 512, frame rows 4096, horizon 512,
cumulative events 50k, applied shock ticks 32, report payload 8 MiB. Overflow
seals the prefix; sealed episodes remain truthful with censored or partial
follow-up.

## Interpretation limits

- Single-run deltas are descriptive, not treatment effects.
- Stock or asset replacement and same-key reacquisition are not continuous
  persistence.
- Cross-region arrivals are not net population gain or residence moves.
- Held-item Gini is possession-count inequality, not welfare.
- Technology-key absence is not physical extinction.
- Disasters@1 is a verification specimen, not a causality claim.

## Verification

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_resilience*.py \
  tests/architecture/test_resilience_boundaries.py -q
```

See [Disasters](disasters.md) for the upstream shock channel and
[Development](development.md) for the focused command list.

## See Also

- [Disasters](disasters.md)
- [Architecture](architecture.md)
- [Development](development.md)
