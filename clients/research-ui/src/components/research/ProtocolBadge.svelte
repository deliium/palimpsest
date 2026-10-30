<script lang="ts">
  import type { VersionPayload } from '../../api/versionSchema'

  interface Props {
    version: VersionPayload | null
    unavailableReason: string | null
  }

  let { version, unavailableReason }: Props = $props()
</script>

<div class="protocol-badge" data-available={version !== null} role="status">
  {#if version === null}
    <span class="unavailable">
      version unavailable{unavailableReason !== null ? ` (${unavailableReason})` : ''}
    </span>
  {:else}
    <span class="protocol">protocol {version.protocol_version}</span>
    <span class="count">{version.observer_capabilities.length} capabilities</span>
    <span class="count">{version.observer_reserved_capabilities.length} reserved</span>
    <span class="layout">layout {version.observer_layout_version}</span>
  {/if}
</div>

<style>
  .protocol-badge {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 0.7rem;
    align-items: center;
    font-size: 0.8rem;
    color: #4a5a62;
  }

  .protocol {
    font-family: ui-monospace, monospace;
  }

  .layout {
    font-family: ui-monospace, monospace;
    color: #6a7a82;
  }

  .unavailable {
    color: #8a3030;
  }
</style>
