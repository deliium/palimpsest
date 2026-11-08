<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    fetchMigrationCauses,
    fetchMigrationOutcomes,
    fetchMigrationRoutes,
    fetchMigrationSummary,
    fetchMigrationWaves,
    type MigrationCause,
    type MigrationDisplacementSummary,
    type MigrationOutcome,
    type MigrationRoute,
    type MigrationWave,
  } from '../api/migrationDisplacement'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error' | 'partial'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<MigrationDisplacementSummary | null>(null)
  let routes = $state<MigrationRoute[]>([])
  let causes = $state<MigrationCause[]>([])
  let waves = $state<MigrationWave[]>([])
  let outcomes = $state<MigrationOutcome[]>([])

  const DISPLACEMENT_CAVEAT =
    'researcher-only classification from independent causal evidence; not a legal or social status'

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  function classificationLabel(value: string): string {
    if (value === 'displacement_like') {
      return 'displacement_like (analytical)'
    }
    return label(value)
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    try {
      summary = await fetchMigrationSummary(runId)
      const [routePage, causePage, wavePage, outcomePage] = await Promise.all([
        fetchMigrationRoutes(runId),
        fetchMigrationCauses(runId),
        fetchMigrationWaves(runId),
        fetchMigrationOutcomes(runId),
      ])
      routes = routePage.items
      causes = causePage.items
      waves = wavePage.items
      outcomes = outcomePage.items
      const empty =
        routes.length === 0 &&
        causes.length === 0 &&
        waves.length === 0 &&
        outcomes.length === 0
      if (empty) {
        status = 'empty'
      } else if (summary.coverage === 'partial' || summary.coverage === 'missing') {
        status = 'partial'
      } else {
        status = 'ready'
      }
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'migration_displacement_disabled' ||
          error.code === 'http_503'
            ? 'unavailable'
            : 'error'
      } else {
        status = 'error'
      }
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="migration-displacement">
  <h2>Migration and displacement</h2>
  {#if status === 'loading'}
    <p>Loading migration publication…</p>
  {:else if status === 'unavailable'}
    <p>Migration-displacement publication is disabled for this deployment.</p>
  {:else if status === 'error'}
    <p>Migration publication is unavailable. Reason: {reason ?? 'unknown'}.</p>
  {:else if status === 'empty'}
    <p>No migration-displacement rows were published for this run.</p>
  {:else if summary}
    {#if status === 'partial'}
      <p>Coverage is {label(summary.coverage)}; missing values are not zero-filled.</p>
    {/if}
    <dl>
      <dt>Candidates</dt><dd>{summary.candidate_count}</dd>
      <dt>Waves</dt><dd>{summary.wave_count}</dd>
      <dt>Clusters</dt><dd>{summary.cluster_count}</dd>
      <dt>Outcomes</dt><dd>{summary.outcome_count}</dd>
      <dt>Movements</dt><dd>{summary.movement_count}</dd>
      <dt>Causes</dt><dd>{summary.cause_count}</dd>
      <dt>Coverage</dt><dd>{label(summary.coverage)}</dd>
    </dl>

    <h3>
      Movement and routes
      <span class="epistemic-word">objective</span>
      <EpistemicBadge epistemic="objective_world" />
    </h3>
    <ul>
      {#each routes as route (route.route_token)}
        <li>
          <span>{route.origin_token}</span>
          <span>→ {route.destination_token}</span>
          <span>hops {route.route_tokens.length}</span>
          <span>{label(route.status)}</span>
          <span>duration {route.observed_duration_ticks}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>
      Cause evidence
      <span class="epistemic-word">subjective</span>
      <EpistemicBadge epistemic="agent_belief" />
    </h3>
    <ul>
      {#each causes as cause (cause.cause_token)}
        <li>
          <span>{label(cause.cause_kind)}</span>
          <span>{label(cause.source_kind)}</span>
          <span>{cause.anchor_token ? 'anchor present' : 'unresolved anchor'}</span>
          <span>{label(cause.status)}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>
    <p>
      Cause counts: {causes.length}. Same-root suppression is applied in analysis;
      unresolved anchors stay unresolved.
    </p>

    <h3>
      Waves and clusters
      <span class="epistemic-word">analytical</span>
      <EpistemicBadge epistemic="research_inference" />
    </h3>
    <ul>
      {#each waves as wave (wave.wave_token)}
        <li>
          <span
            title={wave.displacement_classification === 'displacement_like'
              ? DISPLACEMENT_CAVEAT
              : undefined}
          >
            {classificationLabel(wave.displacement_classification)}
          </span>
          <span>participants {wave.participant_tokens.length}</span>
          <span>clusters {wave.cluster_tokens.length}</span>
          <span>bases {wave.displacement_bases.length}</span>
          <span>coverage {label(wave.coverage)}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>
    <p title={DISPLACEMENT_CAVEAT}>
      displacement_like (analytical): {DISPLACEMENT_CAVEAT}
    </p>

    <h3>
      Integration outcomes
      <span class="epistemic-word">integration</span>
      <EpistemicBadge epistemic="research_inference" />
    </h3>
    <ul>
      {#each outcomes as outcome (outcome.outcome_token)}
        <li>
          <span>{label(outcome.classification)}</span>
          <span>residence {outcome.residence_ticks}</span>
          <span>access {outcome.access_evidence_count}</span>
          <span>participation {outcome.participation_evidence_count}</span>
          <span>relationship {outcome.relationship_evidence_count}</span>
          <span>conflict {outcome.conflict_evidence_count}</span>
          <span>{outcome.censored ? 'censored' : 'observed'}</span>
          <span>coverage {label(outcome.coverage)}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>
    <p>
      Settled {outcomes.filter((row) => row.classification === 'settled').length},
      transient {outcomes.filter((row) => row.classification === 'transient').length},
      returned {outcomes.filter((row) => row.classification === 'returned').length},
      onward {outcomes.filter((row) => row.classification === 'onward').length},
      unknown {outcomes.filter((row) => row.classification === 'unknown').length}.
    </p>
  {/if}
</section>

<style>
  .epistemic-word {
    font-size: 0.75rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-inline: 0.35rem;
  }
</style>
