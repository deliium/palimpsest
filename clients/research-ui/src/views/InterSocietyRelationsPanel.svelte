<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    fetchInterSocietyComparisonByPairs,
    fetchInterSocietyPairs,
    fetchInterSocietyPairSeries,
    fetchInterSocietyRelationsSummary,
    fetchInterSocietyWindows,
    type InterSocietyComparison,
    type InterSocietyDomainPanel,
    type InterSocietyPair,
    type InterSocietyRelationsSummary,
    type InterSocietySeriesPoint,
  } from '../api/interSocietyRelations'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<InterSocietyRelationsSummary | null>(null)
  let pairs = $state<InterSocietyPair[]>([])
  let windows = $state<InterSocietySeriesPoint[]>([])
  let selectedId = $state<string | null>(null)
  let series = $state<InterSocietySeriesPoint[]>([])
  let comparison = $state<InterSocietyComparison | null>(null)

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  function panelLine(panel: InterSocietyDomainPanel): string {
    return `${label(panel.domain)} · ${label(panel.availability)} · events ${panel.event_count}`
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    selectedId = null
    series = []
    comparison = null
    try {
      summary = await fetchInterSocietyRelationsSummary(runId)
      const [pairPage, windowPage] = await Promise.all([
        fetchInterSocietyPairs(runId),
        fetchInterSocietyWindows(runId),
      ])
      pairs = pairPage.items
      windows = windowPage.items
      const left = pairs[0]
      const right = pairs[1]
      if (left !== undefined && right !== undefined) {
        comparison = await fetchInterSocietyComparisonByPairs(
          runId,
          left.pair_id,
          right.pair_id,
        )
      }
      status = pairs.length === 0 ? 'empty' : 'ready'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'inter_society_relations_disabled' ||
          error.code === 'http_503'
            ? 'unavailable'
            : 'error'
      } else {
        status = 'error'
      }
    }
  }

  async function selectPair(pairId: string): Promise<void> {
    selectedId = pairId
    try {
      const page = await fetchInterSocietyPairSeries(runId, pairId)
      series = page.items
    } catch (error) {
      reason = error instanceof ApiClientError ? error.code : 'inter_society_relations_read_failed'
      series = []
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="inter-society-relations">
  <h2>Inter-society relations</h2>
  {#if status === 'loading'}
    <p>Loading inter-society relation panels…</p>
  {:else if status === 'unavailable'}
    <p>Inter-society relations publication is disabled for this deployment.</p>
  {:else if status === 'error'}
    <p>Inter-society relations could not be read. Reason: {reason ?? 'unknown'}.</p>
  {:else if status === 'empty'}
    <p>No society-pair relation panels were published for this run.</p>
  {:else if summary}
    <dl>
      <dt>Pairs</dt><dd>{summary.pair_count}</dd>
      <dt>Windows</dt><dd>{summary.window_count}</dd>
      <dt>Series points</dt><dd>{summary.series_point_count}</dd>
      <dt>Comparisons</dt><dd>{summary.comparison_count}</dd>
      <dt>Coverage</dt><dd>{label(summary.coverage)}</dd>
    </dl>

    <h3>
      Society pairs
      <span class="epistemic-word">analytical</span>
      <EpistemicBadge epistemic="research_inference" />
    </h3>
    <p>
      Eight domain panels report counts and availability only — never a single
      relationship rank or composite chrome.
    </p>
    <ul>
      {#each pairs as pair (pair.pair_id)}
        <li>
          <button type="button" onclick={() => selectPair(pair.pair_id)}>
            {pair.pair_id}
          </button>
          <span>{pair.society_a} · {pair.society_b}</span>
          <span>{label(pair.status)}</span>
          <span>overlap {pair.overlap_member_count}</span>
          <ul>
            {#each pair.panels as panel (panel.domain)}
              <li>{panelLine(panel)}</li>
            {/each}
          </ul>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>
      Window series
      <span class="epistemic-word">analytical</span>
      <EpistemicBadge epistemic="research_inference" />
    </h3>
    <ul>
      {#each (selectedId ? series : windows) as point (point.pair_id + ':' + point.window_index)}
        <li>
          <span>{point.pair_id}</span>
          <span>window {point.window_index}</span>
          <span>{point.window_start_tick}–{point.window_end_tick}</span>
          <span>domains {point.panels.length}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>
      Pair comparison
      <span class="epistemic-word">analytical</span>
      <EpistemicBadge epistemic="research_inference" />
    </h3>
    {#if comparison}
      <p>
        {comparison.left_pair_id} vs {comparison.right_pair_id}
        (ticks {comparison.left_window_tick} / {comparison.right_window_tick})
      </p>
      <ul>
        {#each comparison.domain_deltas as delta (delta.domain)}
          <li>
            <span>{label(delta.domain)}</span>
            <span>delta {delta.count_delta}</span>
            <span>{label(delta.left_availability)} → {label(delta.right_availability)}</span>
          </li>
        {/each}
      </ul>
    {:else}
      <p>Comparison requires at least two published pairs.</p>
    {/if}
  {/if}
</section>

<style>
  .inter-society-relations {
    display: grid;
    gap: 0.75rem;
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.25rem 1rem;
  }

  ul {
    margin: 0;
    padding-left: 1.25rem;
  }

  .epistemic-word {
    font-size: 0.85em;
    opacity: 0.8;
  }
</style>
