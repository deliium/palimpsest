<script lang="ts">
  import {
    ApiClientError,
    compareBranches,
    getBranchLineage,
    listBranchChildren,
    type BranchLineageOut,
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
  let parentRunId = $state<string | null>(null)
  let forkTick = $state<number | null>(null)
  let children = $state<BranchLineageOut[]>([])
  let childrenCursor = $state<string | null>(null)
  let childrenError = $state<string | null>(null)
  let childrenLoading = $state(false)
  let selectedChildren = $state<string[]>([])
  let result = $state<BranchTimelineCompare | null>(null)
  let error = $state<string | null>(null)
  let loading = $state(false)

  $effect(() => {
    const current = runId
    leftId = current
    rightId = ''
    result = null
    error = null
    parentRunId = null
    forkTick = null
    children = []
    childrenCursor = null
    childrenError = null
    selectedChildren = []
    void loadLineage(current)
    void loadChildren(current, null)
  })

  async function loadLineage(target: string): Promise<void> {
    try {
      const lineage = await getBranchLineage(target)
      if (target !== runId) {
        return
      }
      parentRunId = lineage.parent_run_id
      forkTick = lineage.fork_tick
      if (rightId === '') {
        rightId = lineage.parent_run_id
      }
    } catch {
      // parent optional: a root run has no branch lineage
    }
  }

  async function loadChildren(
    target: string,
    after: string | null,
  ): Promise<void> {
    childrenLoading = true
    childrenError = null
    try {
      const page = await listBranchChildren(target, after)
      if (target !== runId) {
        return
      }
      children = after === null ? page.items : [...children, ...page.items]
      childrenCursor = page.next_cursor
    } catch (err) {
      if (target !== runId) {
        return
      }
      childrenError =
        err instanceof ApiClientError ? err.code : 'children_fetch_failed'
    } finally {
      childrenLoading = false
    }
  }

  function toggleChild(childRunId: string): void {
    if (selectedChildren.includes(childRunId)) {
      selectedChildren = selectedChildren.filter((item) => item !== childRunId)
      return
    }
    selectedChildren = [...selectedChildren, childRunId].slice(-2)
  }

  function compareSelectedChildren(): void {
    if (selectedChildren.length !== 2) {
      return
    }
    void compare(selectedChildren[0]!, selectedChildren[1]!)
  }

  async function runCompare(event: Event): Promise<void> {
    event.preventDefault()
    await compare(leftId, rightId)
  }

  async function compare(left: string, right: string): Promise<void> {
    const leftRun = left.trim()
    const rightRun = right.trim()
    if (leftRun === '' || rightRun === '') {
      error = 'run_id_required'
      return
    }
    leftId = leftRun
    rightId = rightRun
    loading = true
    error = null
    result = null
    try {
      result = await compareBranches({
        left_run_id: leftRun,
        right_run_id: rightRun,
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

  function observerHref(targetRun: string): string {
    return buildGodotObserverUrl({
      runId: targetRun,
      tick: result?.diverge_tick ?? deepLink.tick,
      eventId: null,
      sequence: result?.diverge_sequence ?? null,
      agentId: deepLink.agentId,
      debugger: false,
    })
  }

  function researchHref(targetRun: string): string {
    return buildResearchUiPath({
      runId: targetRun,
      tick: result?.diverge_tick ?? null,
      eventId: null,
      sequence: result?.diverge_sequence ?? null,
      agentId: deepLink.agentId,
      view: 'compare',
    })
  }

  function shortHash(value: string | null): string {
    return value === null || value === ''
      ? 'not recorded'
      : `${value.slice(0, 12)}…`
  }

  function eventKindCount(compare: BranchTimelineCompare): number {
    return compare.event_kind_counts === null
      ? 0
      : Object.keys(compare.event_kind_counts).length
  }

  const parentHref = $derived(
    parentRunId === null
      ? null
      : buildResearchUiPath({
          runId: parentRunId,
          tick: forkTick ?? deepLink.tick,
          eventId: null,
          sequence: null,
          agentId: deepLink.agentId,
          view: 'overview',
        }),
  )
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

  {#if parentHref !== null}
    <p class="lede">
      Forked from <a href={parentHref}>parent run</a>{#if forkTick !== null}
        at tick {forkTick}{/if}.
    </p>
  {/if}

  <section class="children">
    <h3>Child runs at this fork</h3>
    {#if childrenError !== null}
      <p class="error" role="alert">{childrenError}</p>
    {:else if children.length === 0}
      <p class="muted">
        {childrenLoading
          ? 'Loading child runs…'
          : 'No child runs are indexed for this run.'}
      </p>
    {:else}
      <ul>
        {#each children as child (child.child_run_id)}
          <li>
            <button
              type="button"
              class:selected={selectedChildren.includes(child.child_run_id)}
              aria-pressed={selectedChildren.includes(child.child_run_id)}
              onclick={() => toggleChild(child.child_run_id)}
            >
              {child.child_run_id}
            </button>
            <span class="muted">
              {child.intervention_kind} · fork tick {child.fork_tick}
            </span>
          </li>
        {/each}
      </ul>
      {#if childrenCursor !== null}
        <button
          type="button"
          onclick={() => void loadChildren(runId, childrenCursor)}
          disabled={childrenLoading}
        >
          Load more child runs
        </button>
      {/if}
      <button
        type="button"
        onclick={compareSelectedChildren}
        disabled={selectedChildren.length !== 2}
      >
        Compare selected children
      </button>
    {/if}
  </section>

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
    <h3>Comparison coverage</h3>
    <dl>
      <div>
        <dt>prefix coverage</dt>
        <dd>{compare.prefix_equivalent ? 'equivalent' : 'diverged'}</dd>
      </div>
      <div>
        <dt>post-fork left</dt>
        <dd>{shortHash(compare.left_post_fork_trajectory_hash)}</dd>
      </div>
      <div>
        <dt>post-fork right</dt>
        <dd>{shortHash(compare.right_post_fork_trajectory_hash)}</dd>
      </div>
      <div>
        <dt>event kind groups</dt>
        <dd>{eventKindCount(compare)}</dd>
      </div>
    </dl>
    <div class="actions">
      <a
        href={observerHref(compare.left_run_id)}
        target="_blank"
        rel="noopener noreferrer">Left in Observer</a
      >
      <a
        href={observerHref(compare.right_run_id)}
        target="_blank"
        rel="noopener noreferrer">Right in Observer</a
      >
      <a href={researchHref(compare.left_run_id)}>Left in Research</a>
      <a href={researchHref(compare.right_run_id)}>Right in Research</a>
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

  .lede a {
    color: #2e5c6e;
  }

  .error {
    color: #8a3030;
  }

  .muted {
    color: #5a6a72;
    font-size: 0.85rem;
  }

  .children {
    display: grid;
    gap: 0.4rem;
  }

  .children ul {
    margin: 0;
    padding-left: 0;
    list-style: none;
    display: grid;
    gap: 0.3rem;
  }

  .children li {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .children button.selected {
    background: rgba(46, 92, 110, 0.18);
    border-color: rgba(46, 92, 110, 0.55);
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

  .actions a {
    font: inherit;
    padding: 0.35rem 0.55rem;
    border: 1px solid rgba(28, 36, 40, 0.22);
    background: rgba(255, 255, 255, 0.6);
    color: inherit;
    text-decoration: none;
  }

  .actions a:hover {
    text-decoration: underline;
  }
</style>
