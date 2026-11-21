# Scientific knowledge diffusion

V4-33 tracks how owner-scoped scientific hypotheses and model representations
move through teaching, records, organizations, migration, and cross-society
communication. It joins retained V4 science evidence with the existing V3
knowledge-genealogy ledger through a detached, opt-in read model.

## Scope

The feature adds no command, world event, capability flag, V4 context,
runner/result schema, pending format, replay pair, SQL migration, or Godot
overlay. Ordinary agents keep executing experiments; durable records,
repositories, teaching, replication, offices, institutional memory, and
physical instruments remain existing channels. There is no global scientific
registry, consensus, truth verdict, or automatic model installation.

## Channels

| Channel | Evidence |
|---|---|
| Science | First-seen hypothesis and model revisions on finalized owner boundaries |
| Speech | Addressed `Talked`/`Told` delivery, native `hyp_v1` uptake, and `sdf_v1` markers |
| Teaching | A science-bearing addressed occurrence plus the recipient's exact `DeclarativeAdvice` occurrence |
| Records | An owner `ArtifactInterpretation` of the exact observed revision with an intact marker |
| Knowledge genealogy | Exact `teach:<occurrence>`, `artifact:`, or `durable:` refs linked to an existing V3 node |
| Organizations | Unique contributor/window resolution; exact same-carrier service is `organization_mediated` |
| Migration | `carried_across_region` only after a completed, alive, qualified arrival |
| Societies | Unique disjoint assignments in the latest eligible absolute 32-tick window |
| Translation | One bound application with a witnessed target; ambiguity is reported, not used |

Delivery is not uptake. A model reference, read, or relay is not ownership.
Confidence-only edits and unwired conditions never become mutation or
misunderstanding.

## Transformations

- **Mutation** — a confirmed predecessor and a later science revision or
  transmitted variant with a comparable changed field.
- **Misunderstanding** — a witnessed divergent reading or divergent initial
  adoption against a known comparable field.
- **Translation** — a bound translation application; it is a separate change
  category and does not imply mutation.
- **Loss** — an explicit owner retirement or exact carrier destruction/removal.
  Observed lineage loss additionally requires holders and carriers explicitly
  closed, two adjacent complete 32-tick windows, and complete
  science/speech/records coverage.
- **Rediscovery** — reacquisition through exact linked uptake, or independent
  rediscovery with a distinct affirmative committed local root and complete
  prior coverage. Death, eviction, unknown state, shared roots, and gaps never
  confirm loss or rediscovery.

## Capture and publication

Capture is explicit and default off:

```python
from experiments.science_diffusion_capture import run_with_science_diffusion_capture
from experiments.science_diffusion_publication import compose_science_diffusion_snapshot
from analysis.science_diffusion_lineage import derive_science_diffusion

captured = await run_with_science_diffusion_capture(runner, capture=True)
assessment = derive_science_diffusion(captured.inputs)
snapshot = compose_science_diffusion_snapshot(
    run_id=captured.result.run_id.value,
    config_fingerprint=fingerprint,
    capture_status=captured.status,
    boundary_tick=captured.result.ticks_committed,
    coverage=captured.inputs.coverage,
    versions=captured.inputs.versions,
    assessment=assessment,
)
```

A capture failure never changes scientific execution. A cap seals only a
trusted prefix; the discarded boundary is not published as complete.

Canonical artifacts are `science-diffusion-snapshot-v1` and
`science-diffusion-store-v1`. Publication is programmatic and atomic; the store
rejects symlinks, non-regular files, oversized index/blob reads, noncanonical
bytes, and changed publication identities.

## Configuration and API

Pair both settings or neither:

```
PALIMPSEST_SCIENCE_DIFFUSION_ROOT=/path/to/store
PALIMPSEST_SCIENCE_DIFFUSION_CURSOR_KEY=<at least 32 UTF-8 bytes>
```

Six GET-only routes require `SUBJECTIVE_DEBUG`:

```
/v1/simulations/{run_id}/science-diffusion
/v1/simulations/{run_id}/science-diffusion/coverage
/v1/simulations/{run_id}/science-diffusion/versions
/v1/simulations/{run_id}/science-diffusion/transmissions
/v1/simulations/{run_id}/science-diffusion/changes
/v1/simulations/{run_id}/science-diffusion/genealogy
```

Unconfigured reads return `503 science_diffusion_disabled`. Missing runs or
publications return explicit 404 codes. Cursors are purpose-bound, pinned to
run/publication/digest/query, and return `410` when expired. The Research UI
adds a read-only **Science diffusion** view.

## Metrics

Four families append the catalog (271 → 275):

- `science_diffusion_channels@1`
- `science_diffusion_fidelity@1`
- `science_diffusion_persistence@1`
- `science_diffusion_genealogy@1`

Denominators stay independent. Complete-empty observations are present zeros;
partial, unavailable, and unresolved evidence are never silent zeros. No
composite score exists.

## Off-gate experiment

`science_diffusion@1` has two paired 128-tick v56 arms (`diffusion-science`,
`diffusion-science-off`) that differ only in the owned science flag, plus a v57
instrument companion. `diffusion-science` enables deterministic artifact
interpretation, teaching, skill learning, durable records, and knowledge
genealogy. The controlled lane may schedule normally admitted commands; the
unassisted lane may retain legal nulls. Analytical classification coverage is
not an autonomous observation.

## Limitations

- Exact provenance is often absent in free runs; missing evidence remains
  unresolved rather than being treated as a null uptake.
- A stable diffusion label is evidence of a carrier event, not scientific
  quality, truth, consensus, or a predefined institution.
- Organization and cross-society joins are analytical context only.
- No cross-run identity, gap bridging, or truth verdict exists.

## See Also

- [Scientific institutions](scientific-institutions.md)
- [Scientific hypotheses](scientific-hypotheses.md)
- [Scientific models](scientific-models.md)
- [Measurement instruments](measurement-instruments.md)
- [Knowledge genealogy](knowledge-genealogy.md)
- [Analysis metrics](analysis-metrics.md)
- [Configuration](configuration.md)
- [Development](development.md)
