<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    fetchOrganizedConflictEpisodes,
    fetchOrganizedConflictInterpretations,
    fetchOrganizedConflictPlans,
    fetchOrganizedConflictSummary,
    type OrganizedConflictEpisode,
    type OrganizedConflictInterpretation,
    type OrganizedConflictPlan,
    type OrganizedConflictSummary,
  } from '../api/organizedConflict'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'available' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<OrganizedConflictSummary | null>(null)
  let episodes = $state<OrganizedConflictEpisode[]>([])
  let plans = $state<OrganizedConflictPlan[]>([])
  let interpretations = $state<OrganizedConflictInterpretation[]>([])

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    try {
      summary = await fetchOrganizedConflictSummary(runId)
      const [episodePage, planPage, interpretationPage] = await Promise.all([
        fetchOrganizedConflictEpisodes(runId),
        fetchOrganizedConflictPlans(runId),
        fetchOrganizedConflictInterpretations(runId),
      ])
      episodes = episodePage.items
      plans = planPage.items
      interpretations = interpretationPage.items
      status = episodes.length === 0 && plans.length === 0 ? 'empty' : 'available'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'organized_conflict_disabled' || error.code === 'http_503'
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

<section class="organized-conflict">
  <h2>Organized conflict</h2>
  {#if status === 'loading'}
    <p>Loading conflict evidence…</p>
  {:else if status === 'unavailable'}
    <p>Organized-conflict publication is not configured for this run.</p>
  {:else if status === 'error'}
    <p>Organized-conflict evidence is unavailable. Reason: {reason ?? 'unknown'}.</p>
  {:else if status === 'empty'}
    <p>No organized-conflict evidence was published for this run.</p>
  {:else if summary}
    <dl>
      <dt>Episodes</dt><dd>{summary.episode_count}</dd>
      <dt>Individual violence</dt><dd>{summary.individual_episode_count}</dd>
      <dt>Coordinated conflict</dt><dd>{summary.coordinated_episode_count}</dd>
      <dt>Persistent inter-group conflict</dt>
      <dd>{summary.persistent_inter_group_episode_count}</dd>
      <dt>Plans</dt><dd>{summary.plan_count}</dd>
      <dt>Interpretations</dt><dd>{summary.interpretation_count}</dd>
      <dt>Coverage</dt><dd>{label(summary.coverage)}</dd>
    </dl>

    <h3>Episodes</h3>
    <ul>
      {#each episodes as episode (episode.episode_id)}
        <li>
          <span>{episode.episode_id}</span>
          <span>{label(episode.classification)}</span>
          <span>participants {episode.participant_tokens.length}</span>
          <span>sustained {episode.sustained ? 'yes' : 'no'}</span>
        </li>
      {/each}
    </ul>

    <h3>Plans</h3>
    <ul>
      {#each plans as plan (plan.plan_id)}
        <li>
          <span>{plan.plan_id}</span>
          <span>{label(plan.operation)}</span>
          <span>{label(plan.target_kind)}</span>
        </li>
      {/each}
    </ul>

    <h3>Interpretations</h3>
    <ul>
      {#each interpretations as interpretation (interpretation.interpretation_id)}
        <li>
          <span>{interpretation.interpretation_id}</span>
          <span>{label(interpretation.kind)}</span>
          <span>alignment {label(interpretation.alignment)}</span>
        </li>
      {/each}
    </ul>
  {/if}
</section>
