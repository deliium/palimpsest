import { describe, expect, it } from 'vitest'
import { parseVersionPayload } from './versionSchema'
import { ResearchSchemaError } from './researchSchemas'

const complete = {
  application_version: '0.1.0',
  protocol_version: 'observer-protocol-v1',
  supported_observer_protocols: ['observer-protocol-v1'],
  observer_layout_version: 'observer-layout-v1',
  observer_capabilities: ['structured_manifest', 'replay_cursors'],
  observer_reserved_capabilities: ['network_rows'],
  export_engine: '4.7.2-stable',
  export_renderer: 'gl_compatibility',
  revision: 'abc123',
  research_ui_configured: false,
}

describe('version payload parser', () => {
  it('accepts a complete payload', () => {
    expect(parseVersionPayload(complete)).toEqual(complete)
  })

  it('accepts empty capability arrays', () => {
    const parsed = parseVersionPayload({
      ...complete,
      observer_capabilities: [],
      observer_reserved_capabilities: [],
    })
    expect(parsed.observer_capabilities).toEqual([])
    expect(parsed.observer_reserved_capabilities).toEqual([])
  })

  it('rejects a missing protocol version', () => {
    const { protocol_version: _unused, ...rest } = complete
    expect(() => parseVersionPayload(rest)).toThrow(ResearchSchemaError)
  })

  it('rejects duplicate capability entries', () => {
    expect(() =>
      parseVersionPayload({
        ...complete,
        observer_capabilities: ['replay_cursors', 'replay_cursors'],
      }),
    ).toThrow(/version_payload_duplicate_entry/)
  })

  it('rejects advertised/reserved overlap', () => {
    expect(() =>
      parseVersionPayload({
        ...complete,
        observer_capabilities: ['structured_manifest'],
        observer_reserved_capabilities: ['structured_manifest'],
      }),
    ).toThrow(/version_payload_capability_overlap/)
  })

  it('rejects a supported list missing the active protocol', () => {
    expect(() =>
      parseVersionPayload({
        ...complete,
        supported_observer_protocols: ['observer-protocol-v2'],
      }),
    ).toThrow(/version_payload_protocol_unsupported/)
  })

  it('rejects a non-boolean research_ui_configured', () => {
    expect(() =>
      parseVersionPayload({ ...complete, research_ui_configured: 'yes' }),
    ).toThrow(ResearchSchemaError)
  })

  it('rejects a non-object payload', () => {
    expect(() => parseVersionPayload(null)).toThrow(ResearchSchemaError)
  })
})
