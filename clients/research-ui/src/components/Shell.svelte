<script lang="ts">
  import { onMount } from 'svelte'
  import AuthPanel from './AuthPanel.svelte'
  import MatrixPanel from '../views/MatrixPanel.svelte'
  import RunList from '../views/RunList.svelte'
  import RunOverview from '../views/RunOverview.svelte'
  import { pushRunRoute, resolveRoute, type Route } from '../router'
  import type { ResearchSelection } from '../research/selection'

  let route = $state<Route>(resolveRoute())

  function refresh(): void {
    route = resolveRoute()
  }

  function onSelectionChange(
    patch: Partial<ResearchSelection>,
    historyMode: 'push' | 'replace' = 'push',
  ): void {
    if (route.kind !== 'run') {
      return
    }
    pushRunRoute(
      route.runId,
      patch.view ?? route.view,
      { ...route.selection, ...patch },
      historyMode,
    )
  }

  onMount(() => {
    refresh()
    window.addEventListener('popstate', refresh)
    return () => window.removeEventListener('popstate', refresh)
  })
</script>

<div class="shell">
  <header class="top">
    <a class="brand" href="/research/">Palimpsest Research</a>
    <nav aria-label="Primary">
      <a href="/research/">Runs</a>
      <a href="/research/matrix">Matrix</a>
    </nav>
    <AuthPanel />
  </header>
  <main class="outlet">
    {#if route.kind === 'run_list'}
      <RunList />
    {:else if route.kind === 'run'}
      <RunOverview
        runId={route.runId}
        view={route.view}
        deepLink={route.deepLink}
        selection={route.selection}
        {onSelectionChange}
      />
    {:else if route.kind === 'matrix_list'}
      <MatrixPanel />
    {:else if route.kind === 'matrix_detail'}
      <MatrixPanel matrixId={route.matrixId} />
    {:else if route.kind === 'route_error'}
      <section>
        <h1>Invalid research link</h1>
        <p class="lede" role="alert">
          The selection was rejected (<code>{route.code}</code>).
        </p>
        <p class="lede"><a href="/research/">Return to runs</a></p>
      </section>
    {:else}
      <section>
        <h1>Not found</h1>
        <p class="lede"><a href="/research/">Return to runs</a></p>
      </section>
    {/if}
  </main>
</div>

<style>
  .shell {
    min-height: 100vh;
    display: grid;
    grid-template-rows: auto 1fr;
    background:
      radial-gradient(ellipse 80% 50% at 10% -10%, rgba(46, 92, 110, 0.18), transparent),
      linear-gradient(165deg, #f3efe6 0%, #e4ddd0 45%, #d7e0e4 100%);
    color: #1c2428;
  }

  .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
    padding: 0.85rem 1.5rem;
    border-bottom: 1px solid rgba(28, 36, 40, 0.12);
    backdrop-filter: blur(6px);
  }

  .brand {
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    color: inherit;
    text-decoration: none;
  }

  nav {
    display: flex;
    gap: 1rem;
    margin-right: auto;
  }

  nav a {
    color: #2e5c6e;
    text-decoration: none;
    font-size: 0.95rem;
  }

  nav a:hover {
    text-decoration: underline;
  }

  .outlet {
    padding: 2rem 1.5rem 3rem;
    max-width: 56rem;
    width: 100%;
  }

</style>
