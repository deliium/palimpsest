<script lang="ts">
  import { buildGodotObserverUrl, type ResearchUiDeepLink } from '../deeplink'

  interface Props {
    deepLink: ResearchUiDeepLink
  }

  let { deepLink }: Props = $props()

  let failed = $state(false)
  let show = $state(false)

  const src = $derived(
    buildGodotObserverUrl({
      runId: deepLink.runId,
      tick: deepLink.tick,
      eventId: deepLink.eventId,
      sequence: deepLink.sequence,
      agentId: deepLink.agentId,
      debugger: false,
    }),
  )

  function onError(): void {
    failed = true
    if (import.meta.env.DEV) {
      console.debug('research_ui_embed embed_fallback_new_tab')
    }
  }

  function openTab(): void {
    window.open(src, '_blank', 'noopener,noreferrer')
  }

  function toggle(): void {
    show = !show
    failed = false
    if (show && import.meta.env.DEV) {
      console.debug(`research_ui_embed load src=${src}`)
    }
  }
</script>

<section class="embed">
  <header>
    <h3>World Observer (adjacent)</h3>
    <div class="actions">
      <button type="button" onclick={toggle}>{show ? 'Hide embed' : 'Show embed'}</button>
      <button type="button" onclick={openTab}>Open in new tab</button>
    </div>
  </header>
  {#if show}
    {#if failed}
      <p class="note">
        Embed bootstrap failed — use new tab. Same-origin iframe only; no shared store.
      </p>
    {:else}
      <iframe
        title="Godot World Observer"
        {src}
        onerror={onError}
        onload={() => {
          if (import.meta.env.DEV) {
            console.debug('research_ui_embed loaded')
          }
        }}
      ></iframe>
    {/if}
  {/if}
</section>

<style>
  .embed {
    display: grid;
    gap: 0.5rem;
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid rgba(28, 36, 40, 0.12);
  }

  header {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
    align-items: center;
  }

  h3 {
    margin: 0;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }

  .actions {
    display: flex;
    gap: 0.4rem;
  }

  button {
    font: inherit;
    padding: 0.3rem 0.5rem;
    border: 1px solid rgba(28, 36, 40, 0.22);
    background: rgba(255, 255, 255, 0.6);
    cursor: pointer;
  }

  iframe {
    width: 100%;
    min-height: 22rem;
    border: 1px solid rgba(28, 36, 40, 0.18);
    background: #1c2428;
  }

  .note {
    margin: 0;
    color: #5a6a72;
  }
</style>
