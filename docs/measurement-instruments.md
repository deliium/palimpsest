# Measurement Instruments

Physical measurement tools turn existing world facts into fallible *displays*.
A display is an actor observation, never the sampled truth.

## Scope

Five dimensions are supported:

| Quantity | Target | Unit | Display |
| --- | --- | --- | --- |
| `ambient_temperature` | actor location | `celsius` | signed milli-C |
| `resource_amount` | visible local resource | exact resource unit | nonnegative milli-unit |
| `elapsed_duration` | the held timer | `simulated_tick` | nonnegative milli-tick |
| `travel_time_estimate` | adjacent route destination | `simulated_tick` | nonnegative milli-tick |
| `load_category` | held or visible item | `simulated_load` | `light` / `medium` / `heavy` |

Physical distance and SI mass are not modeled. Travel is a duration estimate and
load is simulation load.

## Configuration

Instruments are explicit scenario `TOOL` items plus one `measurement_instruments`
sibling on `runner-config-v57`:

```json
{
  "policy_version": "measurement-instruments.v1",
  "instruments": [
    {
      "item_id": "item:thermometer",
      "quantity": "ambient_temperature",
      "unit": {"kind": "celsius", "resource_unit": null},
      "nominal_step_milli": 1000,
      "intrinsic_bias_milli": 0,
      "base_error_bound_milli": 0,
      "damage_milli": 0,
      "correction_milli": 0,
      "calibration_state": "never_adjusted",
      "calibration_revision": 0,
      "last_adjustment_tick": null,
      "damage_at_adjustment_milli": null,
      "timer_epoch_tick": null
    }
  ],
  "references": [
    {
      "item_id": "item:reference",
      "unit": {"kind": "celsius", "resource_unit": null},
      "nominal_value_milli": 20000,
      "physical_value_milli": 21000
    }
  ]
}
```

The spec requires `science` and its existing prerequisites. Both records are
bounded to 64 entries and anchored to distinct scenario `TOOL` items. There is
no implicit tool, reference, or crafting recipe.

## Actions

- `Measure(instrument_id, target_id, quantity)` replaces only a default `Wait`
  when cognition selects it.
- `CalibrateInstrument(instrument_id, reference_id)` adjusts one working tool
  against an eligible same-unit reference.

Both are ordinary admitted commands. Channel-off, unheld/broken tools,
ineligible targets, and wrong-unit references are denied. Each applied action
costs one tick and wears the tool by 10 milli-damage.

## Epistemic limits

- Precision is the display quantization interval, not accuracy.
- Intrinsic bias, noise, correction, wear and reference physical value are
  engine-private.
- A calibration replaces correction, never repairs damage or clears bias.
- A biased reference can make later readings worse.
- An agent may consistently trust an inaccurate tool. Reliability beliefs are
  owner-scoped heuristics and never world truth.
- `msr_v1` speech is testimony. Same-root retellings are not independent
  evidence and never increase reliability confidence.

Retention is bounded: 128 evidence rows, 64 beliefs, 512 revisions, and 1024
root receipts per owner. Missing retained rows are explicitly unavailable.

## Persistence

- Active instrument runs write replay event 28 / codec `v26`.
- Measurement-bearing domain values use envelope schema 2.
- Pending subjective transitions use `finalization-command-v3` with
  `measurement-state-v1`.
- No metric family, API route, SQL migration, observer semantic type, or Godot
  overlay is added.

## Reproduction

Run the focused suites:

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_*.py -q
```

The off-gate `measurement_instruments@1` experiment exposes four arms:
`measurement-absent`, `measurement-unbiased`, `measurement-biased`, and
`measurement-damaged`. A legal null (no autonomous tool use) is acceptable; the
experiment does not script scientific success or consensus.

## See Also

- [Physical Simulation](physical-simulation.md)
- [Scientific Hypotheses](scientific-hypotheses.md)
- [Scientific Replication](scientific-replication.md)
- [Scientific Models](scientific-models.md)
- [Disease mechanics](disease-mechanics.md)
- [Persistence](persistence.md)
- [Configuration](configuration.md)
