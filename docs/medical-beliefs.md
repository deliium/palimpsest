# Medical beliefs

V4-35 adds optional, owner-scoped subjective explanations for the existing
`unwell` cue. The objective disease model from
[V4-34](disease-mechanics.md) is unchanged. Agents never receive infection
phase, immunity, source attribution, or confirmation that transmission
occurred.

## Configuration

`runner-config-v59` is the exact v58 disease family plus a mandatory
`medical_beliefs` sibling:

```json
{
  "schema_version": "runner-config-v59",
  "medical_beliefs": {"policy_id": "medical-beliefs.v1"}
}
```

Enable the owned `epidemics` flag and its existing prerequisites, then set
`medical_beliefs=MedicalBeliefsSpec(policy_id="medical-beliefs.v1")`.
Disease-active v58 and v59 runs both keep replay event 24 / codec `v22`.
Disease-nonactive runs retain their existing selections. `runner-config-v58`
rejects the medical sibling, and v59 requires the exact v58 disease spec.

## Owner evidence

The ledger keeps five independent cause slots (`contact`, `food`, `weather`,
`location`, `cultural`) and practice support for `leave`, `rest`, and
`ritual_pause`. It folds only the owner's consecutive observations and actually
delivered `mb_v1` testimony.

- A first observation, a gap, or an absent/dead self frame establishes a
  baseline and never a negative sample.
- An observed absent-to-present cue transition can add support from prior
  co-presence, prior visible held food, a known weather change, a changed
  location, or a visible local artifact at onset.
- A first accepted testimony root adds support; repeated roots add none.
- A cue disappearing after an attempt records `tentatively_helped`; a persisting
  cue records `not_obviously_helped`; a missing follow-up records `unknown`.
- Outlook summaries preserve the latest known non-unknown judgment even when
  history rows are evicted.
- Cause scores clamp to `[-8, 8]`, at most 128 transition rows and 128 seen roots
  are retained, and capacity-blocked roots never contribute support or a relay
  anchor.

No association is a diagnosis or a confirmed cause. Missing context never
becomes evidence.

## Actions and testimony

A remaining `Wait` for a living, settled, cue-present owner can become one
ordinary command: `Move` to the first visible exit (`leave`), `Sleep` (`rest`),
or `Wait` (`ritual_pause`). Existing science and measurement actions keep
precedence. A three-tick cooldown applies to the same cause/practice pair.
Every command still passes ordinary admission and travel rules.

Bounded `mb_v1` relations travel inside existing `Talk`/`Tell`:
`<cause>|<practice>|<outlook>|<root>|<hop>`. A hop-4 root is never relayed and
testimony alone never mints a new root. A cue-free receiver can retain and relay
a practice before ever observing its own cue; delivery is not uptake and no
speaker is verified.

## Research evidence

`experiments.run_with_medical_beliefs_capture(runner, capture=True)` runs once
and returns detached `medical-beliefs-evidence-v1` evidence with five lanes:
`belief`, `attempt`, owner-observed cue `outcome`, `interpretation`, and
receiver `transmission`. Objective resolutions are joined by
`(owner, tick, command kind)` from finalized receipts. `APPLIED` means ordinary
command application, not physical relief or a treatment effect.

Capture is default off and programmatic. It returns `unavailable` when
disabled, disease/medical mode is off, the run aborted, or the engine and runner
boundaries disagree. Omitted owners, capped roots, truncated history, nonzero
starting positions, and missing receipts produce `partial`, never a claim that
nothing happened. Capture adds no SQL table, HTTP route, metric family,
observer semantic type, Godot overlay, or client surface.

## Experiment

Off-gate `medical_beliefs@1` pairs a `beliefs-off` v58 contact-enabled disease
arm with a `beliefs-on` v59 arm. The scenario, seed, horizon, founders, and
disease policy are shared; only the runner schema and medical policy differ.
The experiment reports what occurred and retains nulls. It does not script
adoption or claim efficacy.

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_medical_beliefs_*.py tests/unit/test_disease_*.py -q
```

## Limits

- One fictional condition; no real pathogen, treatment, dosage, or efficacy
  claim.
- No `truth`, diagnosis, patient classification, or objective cause field.
- No global medical registry, public disease route, or automatic behavior
  response.
- Pending `finalization-command-v6` recovery is not full durable subjective
  restart.

## See Also

- [Disease mechanics](disease-mechanics.md)
- [Configuration](configuration.md)
- [Architecture](architecture.md)
- [Persistence](persistence.md)
- [Scientific models](scientific-models.md)
