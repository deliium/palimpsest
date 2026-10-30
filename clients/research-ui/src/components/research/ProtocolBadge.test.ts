import { describe, expect, it } from 'vitest'
import type { VersionPayload } from '../../api/versionSchema'
import { render } from '../../test/mount'
import ProtocolBadge from './ProtocolBadge.svelte'

const version: VersionPayload = {
  application_version: '0.1.0',
  protocol_version: 'observer-protocol-v1',
  supported_observer_protocols: ['observer-protocol-v1'],
  observer_layout_version: 'observer-layout-v1',
  observer_capabilities: ['structured_manifest', 'replay_cursors'],
  observer_reserved_capabilities: ['network_rows', 'disaster_rows'],
  export_engine: '4.7.2-stable',
  export_renderer: 'gl_compatibility',
  revision: 'abc123',
  research_ui_configured: false,
}

describe('protocol badge', () => {
  it('renders the protocol and capability counts', () => {
    const mounted = render(ProtocolBadge as never, {
      version,
      unavailableReason: null,
    })
    const text = mounted.target.textContent ?? ''
    expect(text).toContain('protocol observer-protocol-v1')
    expect(text).toContain('2 capabilities')
    expect(text).toContain('2 reserved')
    expect(text).toContain('layout observer-layout-v1')
    mounted.cleanup()
  })

  it('renders the unavailable reason when the payload is missing', () => {
    const mounted = render(ProtocolBadge as never, {
      version: null,
      unavailableReason: 'version_payload_invalid',
    })
    const text = mounted.target.textContent ?? ''
    expect(text).toContain('version unavailable')
    expect(text).toContain('version_payload_invalid')
    mounted.cleanup()
  })

  it('renders nothing actionable', () => {
    const mounted = render(ProtocolBadge as never, {
      version,
      unavailableReason: null,
    })
    expect(mounted.target.querySelectorAll('button, a')).toHaveLength(0)
    mounted.cleanup()
  })
})
