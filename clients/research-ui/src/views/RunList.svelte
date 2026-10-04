<script lang="ts">
  import { onMount } from 'svelte'
  import {
    ApiClientError,
    listInspectRuns,
    type RunListItem,
  } from '../api/client'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'
  import { pushRunRoute } from '../router'

  let items = $state<RunListItem[]>([])
  let error = $state<string | null>(null)
  let loading = $state(true)
  let nextCursor = $state<string | null>(null)

  async function load(after?: string | null): Promise<void> {
    loading = true
    error = null
    try {
      const page = await listInspectRuns(after)
      items = after ? [...items, ...page.items] : page.items
      nextCursor = page.next_cursor
    } catch (err) {
      error =
        err instanceof ApiClientError
          ? err.code
          : 'fetch_failed'
    } finally {
      loading = false
    }
  }

  onMount(() => {
    void load()
  })
</script>

<section class="page">
  <header class="head">
    <div>
      <p class="eyebrow">Discovery</p>
      <h1>Runs</h1>
      <p class="lede">Inspect-scoped index (<code>GET /v1/research/runs</code>).</p>
    </div>
    <EpistemicBadge epistemic="objective_world" />
  </header>

  {#if loading && items.length === 0}
    <p class="status">Loading…</p>
  {:else if error !== null}
    <p class="status error" role="alert">Unable to list runs: {error}</p>
  {:else if items.length === 0}
    <p class="status empty">No runs found.</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th scope="col">Run</th>
          <th scope="col">Lifecycle</th>
          <th scope="col">Ticks</th>
          <th scope="col">Schema</th>
        </tr>
      </thead>
      <tbody>
        {#each items as item (item.run_id)}
          <tr>
            <td>
              <button type="button" class="link" onclick={() => pushRunRoute(item.run_id, 'overview')}>
                {item.run_id}
              </button>
            </td>
            <td>{item.lifecycle_state}</td>
            <td>{item.ticks_committed}</td>
            <td>{item.config_schema_version ?? '—'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
    {#if nextCursor !== null}
      <button type="button" class="more" onclick={() => void load(nextCursor)} disabled={loading}>
        Load more
      </button>
    {/if}
  {/if}
</section>

<style>
  .page {
    display: grid;
    gap: 1.25rem;
  }

  .head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
  }

  .eyebrow {
    margin: 0 0 0.25rem;
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5a6a72;
  }

  h1 {
    margin: 0 0 0.35rem;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    font-size: 1.8rem;
  }

  .lede {
    margin: 0;
    color: #3a474e;
  }

  .status {
    margin: 0;
    color: #3a474e;
  }

  .error {
    color: #8a3030;
  }

  .empty {
    font-style: italic;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95rem;
  }

  th,
  td {
    text-align: left;
    padding: 0.55rem 0.4rem;
    border-bottom: 1px solid rgba(28, 36, 40, 0.12);
  }

  .link,
  .more {
    font: inherit;
    cursor: pointer;
    border: none;
    background: none;
    color: #2e5c6e;
    padding: 0;
    text-decoration: underline;
  }

  .more {
    justify-self: start;
    border: 1px solid rgba(28, 36, 40, 0.2);
    padding: 0.4rem 0.75rem;
    text-decoration: none;
    background: rgba(255, 255, 255, 0.5);
  }
</style>
