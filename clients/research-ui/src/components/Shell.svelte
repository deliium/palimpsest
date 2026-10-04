<script lang="ts">
  type NavItem = { href: string; label: string }

  const nav: NavItem[] = [
    { href: '/research/', label: 'Runs' },
    { href: '/research/matrix', label: 'Matrix' },
  ]
</script>

<div class="shell">
  <header class="top">
    <a class="brand" href="/research/">Palimpsest Research</a>
    <nav aria-label="Primary">
      {#each nav as item (item.href)}
        <a href={item.href}>{item.label}</a>
      {/each}
    </nav>
  </header>
  <main class="outlet">
    <p class="eyebrow">Research UI</p>
    <h1>Why did it happen?</h1>
    <p class="lede">
      Analysis and debugging surface complementary to the Godot world observer.
      Run discovery, graphs, and metrics land in later tasks.
    </p>
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
    padding: 2.5rem 1.5rem 3rem;
    max-width: 42rem;
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
    font-size: clamp(1.8rem, 4vw, 2.4rem);
    font-weight: 600;
    line-height: 1.15;
  }

  .lede {
    margin: 0;
    font-size: 1.05rem;
    line-height: 1.5;
    color: #3a474e;
  }
</style>
