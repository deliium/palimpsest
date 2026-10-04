<script lang="ts">
  import { onMount } from 'svelte'
  import AuthPanel from './AuthPanel.svelte'
  import RunList from '../views/RunList.svelte'
  import RunOverview from '../views/RunOverview.svelte'
  import { resolveRoute, type Route } from '../router'

  let route = $state<Route>(resolveRoute())

  function refresh(): void {
    route = resolveRoute()
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
      <RunOverview runId={route.runId} view={route.view} deepLink={route.deepLink} />
    {:else if route.kind === 'matrix_list' || route.kind === 'matrix_detail'}
      <section>
        <p class="eyebrow">Matrix</p>
        <h1>Experiment matrices</h1>
        <p class="lede">
          Matrix overview lands in a later task. Configure
          <code>PALIMPSEST_RESEARCH_MATRIX_ROOT</code> when ready.
        </p>
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

  .eyebrow {
    margin: 0 0 0.35rem;
    font-size: 0.8rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5a6a72;
  }

  h1 {
    margin: 0 0 0.75rem;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    font-size: clamp(1.6rem, 3.5vw, 2.1rem);
    font-weight: 600;
  }

  .lede {
    margin: 0;
    font-size: 1.05rem;
    line-height: 1.5;
    color: #3a474e;
  }
</style>
