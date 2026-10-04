<script lang="ts">
  import {
    ApiClientError,
    compareBranches,
    getBranchLineage,
    type BranchTimelineCompare,
  } from '../api/client'
  import {
    buildGodotObserverUrl,
    buildResearchUiPath,
    type ResearchUiDeepLink,
  } from '../deeplink'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'

  interface Props {
    runId: string
    deepLink: ResearchUiDeepLink
  }

  let { runId, deepLink }: Props = $props()

  let leftId = $state('')
  let rightId = $state('')
  let result = $state<BranchTimelineCompare | null>(null)
  let error = $state<string | null>(null)
  let loading = $state(false)

  $effect(() => {
    leftId = runId
    void getBranchLineage(runId)
      .then((lineage) => {
        if (rightId === '') {
          rightId = lineage.parent_run_id
        }
      })
      .catch(() => {
        // parent optional
      })
  })

  async function runCompare(event: Event): Promise<void> {
    event.preventDefault()
    loading = true
    error = null
    result = null
    try {
      result = await compareBranches({
        left_run_id: leftId.trim(),
        right_run_id: rightId.trim(),
        include_event_kind_counts: true,
      })
      if (import.meta.env.DEV) {
        console.debug(
          `research_ui_fork_compare diverge_tick=${result.diverge_tick ?? 'none'} kinds=${result.event_kind_counts ? Object.keys(result.event_kind_counts).length : 0}`,
        )
      }
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
    } finally {
      loading = false
    }
  }

  function openObserver(targetRun: string): void {
    const href = buildGodotObserverUrl({
      runId: targetRun,
      tick: result?.diverge_tick ?? deepLink.tick,
      eventId: null,
      sequence: result?.diverge_sequence ?? null,
      agentId: deepLink.agentId,
      debugger: false,
    })
    window.open(href, '_blank', 'noopener,noreferrer')
  }

  function openResearch(targetRun: string): void {
    const href = buildResearchUiPath({
      runId: targetRun,
      tick: result?.diverge_tick ?? null,
      eventId: null,
      sequence: result?.diverge_sequence ?? null,
      agentId: deepLink.agentId,
      view: 'compare',
    })
    window.location.assign(href)
  }
</script>

<section class="panel">
  <header class="head">
    <h2>Forked run comparison</h2>
    <EpistemicBadge epistemic="counterfactual" />
    <span class="label">Research fork</span>
  </header>
  <p class="lede">
    Timeline compare via branches/compare — not a dual World Observer viewport.
    Distinct from agent imagination.
  </p>

  <form onsubmit={(e) => void runCompare(e)}>
    <label>
      Left run
      <input bind:value={leftId} autocomplete="off" />
    </label>
    <label>
      Right run
      <input bind:value={rightId} autocomplete="off" />
    </label>
    <button type="submit" disabled={loading}>Compare</button>
  </form>

  {#if error !== null}
    <p class="error" role="alert">{error}</p>
  {:else if result !== null}
    {@const compare = result}
    <dl>
      <div><dt>fork_tick</dt><dd>{compare.fork_tick}</dd></div>
      <div>
        <dt>prefix_equivalent</dt>
        <dd>{compare.prefix_equivalent ? 'yes' : 'no'}</dd>
      </div>
      <div>
        <dt>diverge</dt>
        <dd>
          {#if compare.diverge_tick !== null}
            tick {compare.diverge_tick}
            {#if compare.diverge_sequence !== null}
              / seq {compare.diverge_sequence}
            {/if}
          {:else}
            none
          {/if}
        </dd>
      </div>
      {#if compare.reason_code}
        <div><dt>reason</dt><dd>{compare.reason_code}</dd></div>
      {/if}
    </dl>
    {#if compare.event_kind_counts}
      <h3>Event kind deltas</h3>
      <ul>
        {#each Object.entries(compare.event_kind_counts) as [side, counts] (side)}
          <li>
            <strong>{side}</strong>:
            {Object.entries(counts)
              .map(([kind, n]) => `${kind}=${n}`)
              .join(', ') || '(empty)'}
          </li>
        {/each}
      </ul>
    {/if}
    <div class="actions">
      <button type="button" onclick={() => openObserver(compare.left_run_id)}>
        Left in Observer
      </button>
      <button type="button" onclick={() => openObserver(compare.right_run_id)}>
        Right in Observer
      </button>
      <button type="button" onclick={() => openResearch(compare.left_run_id)}>
        Left in Research
      </button>
      <button type="button" onclick={() => openResearch(compare.right_run_id)}>
        Right in Research
      </button>
    </div>
  {/if}
</section>

<style>
  .panel {
    display: grid;
    gap: 0.75rem;
  }

  .head {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  h2,
  h3 {
    margin: 0;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }

  .label {
    font-size: 0.75rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ep-counterfactual);
  }

  .lede,
  .error {
    margin: 0;
  }

  .lede {
    color: #5a6a72;
  }

  .error {
    color: #8a3030;
  }

  form {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    align-items: end;
  }

  label {
    display: grid;
    gap: 0.25rem;
    font-size: 0.85rem;
  }

  input,
  button {
    font: inherit;
    padding: 0.35rem 0.55rem;
    border: 1px solid rgba(28, 36, 40, 0.22);
  }

  button {
    cursor: pointer;
    background: rgba(255, 255, 255, 0.6);
  }

  dl {
    margin: 0;
    display: grid;
    gap: 0.3rem;
  }

  dl div {
    display: flex;
    gap: 0.75rem;
  }

  dt {
    min-width: 8rem;
    color: #5a6a72;
  }

  dd {
    margin: 0;
  }

  ul {
    margin: 0;
    padding-left: 1.1rem;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
</style>
