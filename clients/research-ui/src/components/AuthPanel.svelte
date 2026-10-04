<script lang="ts">
  import {
    CAPABILITY_LABELS,
    type CapabilitySlot,
    type CredentialStore,
    loadCredentials,
    saveCredentials,
  } from '../auth/credentials'

  const slots: CapabilitySlot[] = [
    'objective_inspection',
    'agent_visible',
    'subjective_debug',
    'simulation_control',
  ]

  let open = $state(false)
  let draft: CredentialStore = $state(loadCredentials())

  function persist(): void {
    saveCredentials(draft)
    open = false
  }
</script>

<div class="auth">
  <button type="button" class="toggle" onclick={() => (open = !open)}>
    Credentials
  </button>
  {#if open}
    <div class="panel" role="dialog" aria-label="Capability credentials">
      <p class="hint">
        Tokens stay in sessionStorage / memory and are sent only as
        <code>x-palimpsest-token</code> matching each route capability. Open-local
        when API credentials are unset.
      </p>
      {#each slots as slot (slot)}
        <label>
          <span>{CAPABILITY_LABELS[slot]}</span>
          <input
            type="password"
            autocomplete="off"
            spellcheck="false"
            bind:value={draft[slot]}
            placeholder="optional"
          />
        </label>
      {/each}
      <div class="actions">
        <button type="button" onclick={persist}>Save</button>
        <button type="button" class="ghost" onclick={() => (open = false)}>Close</button>
      </div>
    </div>
  {/if}
</div>

<style>
  .auth {
    position: relative;
  }

  .toggle,
  .actions button {
    font: inherit;
    cursor: pointer;
    border: 1px solid rgba(28, 36, 40, 0.25);
    background: rgba(255, 255, 255, 0.55);
    padding: 0.35rem 0.7rem;
  }

  .ghost {
    background: transparent;
  }

  .panel {
    position: absolute;
    right: 0;
    top: calc(100% + 0.4rem);
    z-index: 20;
    width: min(22rem, 90vw);
    padding: 0.9rem;
    background: #f7f3ea;
    border: 1px solid rgba(28, 36, 40, 0.18);
    box-shadow: 0 8px 24px rgba(28, 36, 40, 0.12);
    display: grid;
    gap: 0.55rem;
  }

  .hint {
    margin: 0;
    font-size: 0.8rem;
    color: #4a565c;
    line-height: 1.35;
  }

  label {
    display: grid;
    gap: 0.2rem;
    font-size: 0.8rem;
  }

  input {
    font: inherit;
    padding: 0.35rem 0.45rem;
    border: 1px solid rgba(28, 36, 40, 0.2);
    background: #fff;
  }

  .actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }
</style>
