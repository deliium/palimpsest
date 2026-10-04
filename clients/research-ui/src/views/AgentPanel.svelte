<script lang="ts">
  import { onMount } from 'svelte'
  import {
    ApiClientError,
    getEmotionalState,
    getGoals,
    getSelfModel,
    getTheoryOfMind,
    type EmotionalProjection,
    type GoalsProjection,
    type LedgerProjection,
    type SelfModelProjection,
  } from '../api/client'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'

  interface Props {
    runId: string
    agentId: string | null
  }

  let { runId, agentId }: Props = $props()

  let owner = $state('')
  let goals = $state<GoalsProjection | null>(null)
  let emotion = $state<EmotionalProjection | null>(null)
  let selfModel = $state<SelfModelProjection | null>(null)
  let tom = $state<LedgerProjection | null>(null)
  let error = $state<string | null>(null)
  let loading = $state(false)

  async function load(target: string): Promise<void> {
    loading = true
    error = null
    try {
      ;[goals, emotion, selfModel, tom] = await Promise.all([
        getGoals(runId, target),
        getEmotionalState(runId, target),
        getSelfModel(runId, target),
        getTheoryOfMind(runId, target),
      ])
      if (import.meta.env.DEV) {
        for (const [name, doc] of [
          ['goals', goals],
          ['emotion', emotion],
          ['self_model', selfModel],
          ['tom', tom],
        ] as const) {
          if (doc?.availability === 'unavailable') {
            console.debug(`research_ui_panel_unavailable panel=${name}`)
          }
        }
      }
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
    } finally {
      loading = false
    }
  }

  onMount(() => {
    if (agentId) {
      owner = agentId
      void load(agentId)
    }
  })

  $effect(() => {
    if (agentId && agentId !== owner) {
      owner = agentId
      void load(agentId)
    }
  })

  function submitOwner(event: Event): void {
    event.preventDefault()
    const value = owner.trim()
    if (value !== '') {
      void load(value)
    }
  }
</script>

<section class="panel">
  <header>
    <h2>Agent</h2>
    <EpistemicBadge epistemic="agent_belief" />
  </header>
  <form onsubmit={submitOwner}>
    <label>
      Owner agent id
      <input bind:value={owner} placeholder="alice" autocomplete="off" />
    </label>
    <button type="submit">Load</button>
  </form>

  {#if !owner}
    <p class="empty">Select or enter an agent id (domain AgentId).</p>
  {:else if loading}
    <p>Loading…</p>
  {:else if error !== null}
    <p class="error" role="alert">{error}</p>
  {:else}
    <div class="grid">
      <article>
        <h3>Self-model <EpistemicBadge epistemic="agent_belief" /></h3>
        {#if selfModel?.availability === 'available'}
          <p>Identity tick: {selfModel.identity_tick ?? '—'}</p>
          <p>Identity ops: {selfModel.identity_operation_count}</p>
          <p>Goals linked: {selfModel.goal_count}</p>
          <p class="muted">{selfModel.note}</p>
        {:else}
          <p class="empty">Unavailable (flag/mode/checkpoint).</p>
        {/if}
      </article>
      <article>
        <h3>Goals <EpistemicBadge epistemic="agent_belief" /></h3>
        {#if goals?.availability === 'available' && goals.head_count > 0}
          <ul>
            {#each goals.items as item (item.goal_id)}
              <li>{item.goal_id} · {item.status} · p={item.priority}</li>
            {/each}
          </ul>
        {:else if goals?.availability === 'available'}
          <p class="empty">No goals in checkpoint.</p>
        {:else}
          <p class="empty">Unavailable (flag/mode/checkpoint).</p>
        {/if}
      </article>
      <article>
        <h3>Emotion <EpistemicBadge epistemic="agent_belief" /></h3>
        {#if emotion?.availability === 'available' && emotion.head_count > 0}
          <ul>
            {#each emotion.intensities as item (item.kind)}
              <li>{item.kind}: {item.intensity}</li>
            {/each}
          </ul>
        {:else}
          <p class="empty">Unavailable or neutral/absent.</p>
        {/if}
      </article>
      <article>
        <h3>Theory of Mind <EpistemicBadge epistemic="agent_belief" /></h3>
        {#if tom?.availability === 'available' && tom.head_count > 0}
          <ul>
            {#each tom.items as item (item.item_id)}
              <li>{item.kind_code} → {item.target_id ?? '?'} ({item.strength ?? '—'})</li>
            {/each}
          </ul>
        {:else}
          <p class="empty">Unavailable (flag off or empty store).</p>
        {/if}
      </article>
    </div>
  {/if}
</section>

<style>
  .panel {
    display: grid;
    gap: 1rem;
  }

  header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  h2,
  h3 {
    margin: 0;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }

  form {
    display: flex;
    gap: 0.5rem;
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

  .grid {
    display: grid;
    gap: 0.85rem;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  }

  article {
    padding: 0.75rem;
    border: 1px solid rgba(28, 36, 40, 0.12);
    background: rgba(255, 255, 255, 0.35);
  }

  ul {
    margin: 0.4rem 0 0;
    padding-left: 1.1rem;
    font-size: 0.9rem;
  }

  .empty,
  .muted {
    color: #5a6a72;
    font-size: 0.9rem;
  }

  .error {
    color: #8a3030;
  }
</style>
