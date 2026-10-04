<script lang="ts">
  import {
    ApiClientError,
    getAgentObservation,
    getBeliefSummary,
    getInspectionEvents,
    getMemorySummary,
    getMetricCatalog,
    getMetricDocument,
    type AgentVisible,
    type EventSummary,
    type GraphSummary,
  } from '../api/client'
  import type { ResearchUiDeepLink } from '../deeplink'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'

  interface Props {
    runId: string
    deepLink: ResearchUiDeepLink
  }

  let { runId, deepLink }: Props = $props()

  let events = $state<EventSummary[]>([])
  let eventsReason = $state<string | null>(null)
  let observation = $state<AgentVisible | null>(null)
  let observationReason = $state<string | null>(null)
  let memories = $state<GraphSummary | null>(null)
  let memoriesReason = $state<string | null>(null)
  let beliefs = $state<GraphSummary | null>(null)
  let beliefsReason = $state<string | null>(null)
  let driftNote = $state<string | null>(null)
  let loading = $state(true)

  function focusEvent(list: EventSummary[]): EventSummary | null {
    if (deepLink.tick !== null && deepLink.sequence !== null) {
      return (
        list.find(
          (item) =>
            item.tick === deepLink.tick && item.sequence === deepLink.sequence,
        ) ?? null
      )
    }
    if (deepLink.tick !== null) {
      return list.find((item) => item.tick === deepLink.tick) ?? null
    }
    return list[0] ?? null
  }

  async function load(): Promise<void> {
    loading = true
    eventsReason = null
    observationReason = null
    memoriesReason = null
    beliefsReason = null
    driftNote = null
    try {
      try {
        const page = await getInspectionEvents(runId, 80)
        events = page.events
      } catch (err) {
        events = []
        eventsReason = err instanceof ApiClientError ? err.code : 'fetch_failed'
      }

      if (deepLink.agentId) {
        try {
          observation = await getAgentObservation(runId, deepLink.agentId)
        } catch (err) {
          observation = null
          observationReason =
            err instanceof ApiClientError ? err.code : 'fetch_failed'
        }
        try {
          memories = await getMemorySummary(runId, deepLink.agentId)
        } catch (err) {
          memories = null
          memoriesReason =
            err instanceof ApiClientError ? err.code : 'fetch_failed'
        }
        try {
          beliefs = await getBeliefSummary(runId, deepLink.agentId)
        } catch (err) {
          beliefs = null
          beliefsReason =
            err instanceof ApiClientError ? err.code : 'fetch_failed'
        }
      } else {
        observation = null
        observationReason = 'agent_id_required'
        memories = null
        memoriesReason = 'agent_id_required'
        beliefs = null
        beliefsReason = 'agent_id_required'
      }

      try {
        const catalog = await getMetricCatalog(runId)
        const driftItem = catalog.items.find((item) =>
          /drift|transmission|memory_drift|cultural_transmission/i.test(
            item.metric_family,
          ),
        )
        if (driftItem) {
          const doc = await getMetricDocument(
            runId,
            driftItem.metric_set_id,
            driftItem.metric_family,
          )
          driftNote = `${driftItem.metric_family} · ${doc.availability}`
        } else {
          driftNote = 'no_drift_metric'
        }
      } catch (err) {
        driftNote =
          err instanceof ApiClientError ? err.code : 'metric_unavailable'
      }

      if (import.meta.env.DEV) {
        console.debug(
          `research_ui_compare objective=${eventsReason ?? 'ok'} observation=${observationReason ?? 'ok'} memory=${memoriesReason ?? 'ok'} belief=${beliefsReason ?? 'ok'} drift=${driftNote}`,
        )
      }
    } finally {
      loading = false
    }
  }

  $effect(() => {
    void runId
    void deepLink.agentId
    void deepLink.tick
    void deepLink.sequence
    void load()
  })

  const focused = $derived(focusEvent(events))
</script>

<section class="panel">
  <header>
    <h2>Objective vs subjective</h2>
  </header>
  <p class="lede">
    Columns stay locked to their epistemic class. Unavailable sources show reason
    codes — alignment is never fabricated.
  </p>

  {#if loading}
    <p>Loading…</p>
  {:else}
    <div class="columns">
      <article>
        <header class="col-head">
          <h3>Objective event</h3>
          <EpistemicBadge epistemic="objective_world" />
        </header>
        {#if eventsReason}
          <p class="reason">{eventsReason}</p>
        {:else if focused}
          <dl>
            <div><dt>kind</dt><dd>{focused.kind}</dd></div>
            <div><dt>tick</dt><dd>{focused.tick}</dd></div>
            <div><dt>sequence</dt><dd>{focused.sequence}</dd></div>
          </dl>
        {:else}
          <p class="reason">no_matching_event</p>
        {/if}
      </article>

      <article>
        <header class="col-head">
          <h3>Agent-visible</h3>
          <EpistemicBadge epistemic="agent_observation" />
        </header>
        {#if observationReason}
          <p class="reason">{observationReason}</p>
        {:else if observation}
          <dl>
            <div><dt>availability</dt><dd>{observation.availability}</dd></div>
            <div><dt>tick</dt><dd>{observation.tick}</dd></div>
            <div><dt>occurrences</dt><dd>{observation.occurrence_count}</dd></div>
            <div>
              <dt>communications</dt>
              <dd>{observation.communication_count}</dd>
            </div>
          </dl>
        {/if}
      </article>

      <article>
        <header class="col-head">
          <h3>Memory summary</h3>
          <EpistemicBadge epistemic="agent_memory" />
        </header>
        {#if memoriesReason}
          <p class="reason">{memoriesReason}</p>
        {:else if memories}
          <p class="meta">
            {memories.availability} · nodes={memories.count}
          </p>
          <ul>
            {#each memories.items.slice(0, 8) as item (item.node_id)}
              <li>
                {item.node_id.slice(0, 10)}… · tick={item.created_tick}
                {#if item.source_kind}
                  · {item.source_kind}
                {/if}
              </li>
            {/each}
          </ul>
        {/if}
      </article>

      <article>
        <header class="col-head">
          <h3>Belief summary</h3>
          <EpistemicBadge epistemic="agent_belief" />
        </header>
        {#if beliefsReason}
          <p class="reason">{beliefsReason}</p>
        {:else if beliefs}
          <p class="meta">
            {beliefs.availability} · nodes={beliefs.count}
          </p>
          <ul>
            {#each beliefs.items.slice(0, 8) as item (item.node_id)}
              <li>
                {item.node_id.slice(0, 10)}… · tick={item.created_tick}
                {#if item.source_kind}
                  · {item.source_kind}
                {/if}
              </li>
            {/each}
          </ul>
        {/if}
      </article>

      <article>
        <header class="col-head">
          <h3>Drift / transmission</h3>
          <EpistemicBadge epistemic="research_inference" />
        </header>
        <p class="reason">{driftNote ?? 'unavailable'}</p>
      </article>
    </div>
  {/if}
</section>

<style>
  .panel {
    display: grid;
    gap: 0.85rem;
  }

  h2,
  h3 {
    margin: 0;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }

  .lede,
  .meta,
  .reason {
    margin: 0;
    color: #5a6a72;
    font-size: 0.9rem;
  }

  .columns {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  }

  article {
    padding-top: 0.5rem;
    border-top: 1px solid rgba(28, 36, 40, 0.12);
  }

  .col-head {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 0.5rem;
  }

  dl {
    margin: 0;
    display: grid;
    gap: 0.25rem;
  }

  dl div {
    display: flex;
    gap: 0.5rem;
  }

  dt {
    color: #5a6a72;
    min-width: 6rem;
  }

  dd {
    margin: 0;
  }

  ul {
    margin: 0.35rem 0 0;
    padding-left: 1.1rem;
    font-size: 0.85rem;
  }
</style>
