<script lang="ts">
  import {
    ApiClientError,
    getCausalTraceByCursor,
    getCausalTraceByEvent,
    listDebuggerInvocations,
    type CausalTrace,
    type CausalTraceNode,
    type DebuggerInvocationPage,
  } from '../api/client'
  import {
    buildGodotObserverUrl,
    type ResearchUiDeepLink,
  } from '../deeplink'
  import {
    epistemicFromDebuggerArtifact,
    type EpistemicClass,
  } from '../epistemic'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'

  interface Props {
    runId: string
    deepLink: ResearchUiDeepLink
  }

  let { runId, deepLink }: Props = $props()

  let trace = $state<CausalTrace | null>(null)
  let invocations = $state<DebuggerInvocationPage | null>(null)
  let error = $state<string | null>(null)
  let loading = $state(false)

  function stageEpistemic(stageCode: string): EpistemicClass {
    const code = stageCode.toLowerCase()
    if (code.includes('observ')) {
      return epistemicFromDebuggerArtifact('observation')
    }
    if (code.includes('memor')) {
      return epistemicFromDebuggerArtifact('memory')
    }
    if (
      code.includes('belief') ||
      code.includes('goal') ||
      code.includes('emotion') ||
      code.includes('tom') ||
      code.includes('theory')
    ) {
      return epistemicFromDebuggerArtifact('belief')
    }
    if (code.includes('imagin') || code.includes('prospect')) {
      return epistemicFromDebuggerArtifact('imagination')
    }
    if (code.includes('counter')) {
      return epistemicFromDebuggerArtifact('counterfactual')
    }
    if (code.includes('action') || code.includes('command') || code.includes('world')) {
      return epistemicFromDebuggerArtifact('action')
    }
    return epistemicFromDebuggerArtifact(stageCode)
  }

  async function load(): Promise<void> {
    loading = true
    error = null
    trace = null
    invocations = null
    try {
      if (deepLink.eventId) {
        trace = await getCausalTraceByEvent(runId, deepLink.eventId)
      } else if (deepLink.tick !== null && deepLink.sequence !== null) {
        trace = await getCausalTraceByCursor(
          runId,
          deepLink.tick,
          deepLink.sequence,
        )
      } else if (deepLink.agentId) {
        invocations = await listDebuggerInvocations(
          runId,
          deepLink.agentId,
          deepLink.tick,
        )
      } else {
        error = 'focus_required'
      }
      if (import.meta.env.DEV) {
        if (trace) {
          console.debug(
            `research_ui_trace availability=${trace.availability} nodes=${trace.nodes.length}`,
          )
        }
        if (invocations) {
          console.debug(
            `research_ui_trace invocations=${invocations.count} availability=${invocations.availability}`,
          )
        }
      }
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
    } finally {
      loading = false
    }
  }

  $effect(() => {
    void deepLink.eventId
    void deepLink.tick
    void deepLink.sequence
    void deepLink.agentId
    void runId
    void load()
  })

  function openInGodot(node?: CausalTraceNode): void {
    const focus = node?.observer_focus[0]
    const href = buildGodotObserverUrl({
      runId,
      tick: focus?.tick ?? deepLink.tick ?? trace?.address.tick ?? null,
      eventId: focus?.event_id ?? deepLink.eventId ?? trace?.address.event_id ?? null,
      sequence:
        focus?.sequence ?? deepLink.sequence ?? trace?.address.sequence ?? null,
      agentId: deepLink.agentId,
      debugger: true,
    })
    window.open(href, '_blank', 'noopener,noreferrer')
  }
</script>

<section class="panel">
  <header class="head">
    <h2>Decision traces</h2>
    <button type="button" onclick={() => openInGodot()}>
      Open tick/event in World Observer
    </button>
  </header>
  <p class="lede">
    Cognition traces are observational under subjective_debug. Stages keep their
    epistemic class — never promoted to world authority.
  </p>

  {#if loading}
    <p>Loading…</p>
  {:else if error !== null}
    <p class="error" role="alert">
      {#if error === 'focus_required'}
        Provide event_id, tick+sequence, or agent_id to load a decision trace.
      {:else}
        {error}
      {/if}
    </p>
  {:else if trace}
    <p class="meta">
      availability={trace.availability}
      {#if trace.reason_code}
        · {trace.reason_code}
      {/if}
      · nodes={trace.nodes.length}
      {#if trace.ambiguity}
        · ambiguous
      {/if}
    </p>
    <ol>
      {#each trace.nodes as node, index (node.stage_code + String(index))}
        {@const epistemic = stageEpistemic(node.stage_code)}
        <li>
          <div class="row">
            <strong>{node.stage_code}</strong>
            <EpistemicBadge {epistemic} />
            <span class="status">{node.status}</span>
          </div>
          {#if node.reason_code}
            <p class="meta">reason={node.reason_code}</p>
          {/if}
          {#if node.observer_focus.length > 0}
            <button type="button" class="linkish" onclick={() => openInGodot(node)}>
              Focus in Observer
            </button>
          {/if}
        </li>
      {/each}
    </ol>
  {:else if invocations}
    <p class="meta">
      Invocations for {invocations.agent_id}: {invocations.count}
      ({invocations.availability})
    </p>
    {#if invocations.items.length === 0}
      <p class="empty">No cognition-trace invocations for this agent/tick.</p>
    {:else}
      <ul>
        {#each invocations.items as item (item.invocation_id)}
          <li>
            tick={item.tick}
            · {item.command_kind ?? 'command?'}
            · hash={item.content_hash_prefix}
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>

<style>
  .panel {
    display: grid;
    gap: 0.85rem;
  }

  .head {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
    align-items: center;
  }

  h2 {
    margin: 0;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }

  .lede,
  .meta,
  .empty {
    margin: 0;
    color: #5a6a72;
    font-size: 0.9rem;
  }

  .error {
    color: #8a3030;
  }

  ol,
  ul {
    margin: 0;
    padding-left: 1.2rem;
    display: grid;
    gap: 0.65rem;
  }

  .row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .status {
    font-size: 0.8rem;
    color: #5a6a72;
  }

  button {
    font: inherit;
    padding: 0.35rem 0.55rem;
    border: 1px solid rgba(28, 36, 40, 0.22);
    background: rgba(255, 255, 255, 0.6);
    cursor: pointer;
  }

  .linkish {
    margin-top: 0.25rem;
    font-size: 0.85rem;
  }
</style>
