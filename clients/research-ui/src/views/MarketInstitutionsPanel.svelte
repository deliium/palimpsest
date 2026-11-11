<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    fetchMarketCandidates,
    fetchMarketExpectations,
    fetchMarketGatherings,
    fetchMarketInstitutionsSummary,
    fetchMarketRecords,
    fetchMarketRoles,
    fetchMarketVenues,
    type MarketCandidate,
    type MarketExpectation,
    type MarketGathering,
    type MarketInstitutionsSummary,
    type MarketLineage,
    type MarketRecord,
    type MarketRole,
    type MarketVenue,
  } from '../api/marketInstitutions'
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
  let summary = $state<MarketInstitutionsSummary | null>(null)
  let venues = $state<MarketVenue[]>([])
  let gatherings = $state<MarketGathering[]>([])
  let expectations = $state<MarketExpectation[]>([])
  let roles = $state<MarketRole[]>([])
  let records = $state<MarketRecord[]>([])
  let markets = $state<MarketCandidate[]>([])
  let lineage = $state<MarketLineage[]>([])
  let windowInput = $state('')

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  function windowIndex(): number | undefined {
    if (windowInput.trim() === '') return undefined
    const parsed = Number(windowInput)
    return Number.isInteger(parsed) && parsed >= 0 ? parsed : undefined
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    const index = windowIndex()
    try {
      summary = await fetchMarketInstitutionsSummary(runId)
      const [venuePage, gatheringPage, expectationPage, rolePage, recordPage, marketPage] =
        await Promise.all([
          fetchMarketVenues(runId, { windowIndex: index }),
          fetchMarketGatherings(runId, { windowIndex: index }),
          fetchMarketExpectations(runId, { windowIndex: index }),
          fetchMarketRoles(runId, { windowIndex: index }),
          fetchMarketRecords(runId, { windowIndex: index }),
          fetchMarketCandidates(runId, { windowIndex: index }),
        ])
      venues = venuePage.rows
      gatherings = gatheringPage.rows
      expectations = expectationPage.rows
      roles = rolePage.rows
      records = recordPage.rows
      markets = marketPage.rows
      lineage = marketPage.lineage
      const hasRows =
        venues.length +
          gatherings.length +
          expectations.length +
          roles.length +
          records.length +
          markets.length >
        0
      status = hasRows ? 'ready' : 'empty'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'market_institutions_disabled' || error.code === 'http_503'
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

<section class="market-institutions">
  <h2>Market-like institutions <EpistemicBadge epistemic="research_inference" /></h2>
  <p>
    Repeated exchange gatherings, owner meeting expectations, emergent role and
    record references, and forward-only market lineage. Counts, closed tokens,
    and descriptive lineage only; no commercial or advisory fields exist.
  </p>
  <label>
    Window index
    <input
      type="number"
      min="0"
      max="511"
      bind:value={windowInput}
      onchange={() => void load()}
    />
  </label>

  {#if status === 'loading'}
    <p>Loading exchange venues…</p>
  {:else if status === 'unavailable'}
    <p>Market-like institutions are disabled for this run.</p>
  {:else if status === 'error'}
    <p>Market-like institutions could not be read. Reason: {reason ?? 'unknown'}.</p>
  {:else if status === 'empty'}
    <p>No market-like institution evidence was published for this run and window.</p>
  {:else if summary}
    <dl>
      <dt>Venues</dt><dd>{summary.venue_count}</dd>
      <dt>Gatherings</dt><dd>{summary.gathering_count}</dd>
      <dt>Persistent venues</dt><dd>{summary.market_like_venue_count}</dd>
      <dt>Markets</dt><dd>{summary.market_count}</dd>
      <dt>Expectation rows</dt><dd>{summary.expectation_row_count}</dd>
      <dt>Role rows</dt><dd>{summary.role_row_count}</dd>
      <dt>Coverage</dt><dd>{label(summary.coverage)}</dd>
    </dl>

    <h3>Venues</h3>
    <ul>
      {#each venues as venue (venue.venue_id)}
        <li>
          {venue.window_index}: {label(venue.status)}, exchanges {venue.exchange_count},
          parties {venue.distinct_party_count}, recurrence {venue.recurrence_milli} milli
        </li>
      {/each}
    </ul>

    <h3>Expectations</h3>
    <ul>
      {#each expectations as row (`${row.venue_id}-${row.window_index}-${row.owner_token}`)}
        <li>
          {row.window_index}: {label(row.expectation)}, {label(row.cadence)},
          alignment {label(row.alignment)}
        </li>
      {/each}
    </ul>

    <h3>Roles and records</h3>
    <ul>
      {#each roles as row (`${row.venue_id}-${row.window_index}-${row.actor_token}`)}
        <li>{row.window_index}: {label(row.role_kind)} ({label(row.role_basis)})</li>
      {/each}
      {#each records as row (`${row.venue_id}-${row.window_index}-${row.anchor_token}`)}
        <li>{row.window_index}: {label(row.record_kind)} record reference</li>
      {/each}
    </ul>

    <h3>Markets and lineage</h3>
    <ul>
      {#each markets as market (market.market_id)}
        <li>{market.window_index}: {market.venue_ids.length} venues</li>
      {/each}
      {#each lineage as row (`${row.window_index}-${row.market_id}`)}
        <li>{row.window_index}: {label(row.status)}</li>
      {/each}
    </ul>
  {/if}
</section>
