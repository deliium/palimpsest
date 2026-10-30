/** Strict parser for the public `GET /version` payload. */

import {
  ResearchSchemaError,
  isRecord,
  requireArray,
  requireOptionalString,
  requireRecord,
  requireString,
} from './researchSchemas'

export type VersionPayload = {
  application_version: string | null
  protocol_version: string
  supported_observer_protocols: string[]
  observer_layout_version: string
  observer_capabilities: string[]
  observer_reserved_capabilities: string[]
  export_engine: string | null
  export_renderer: string | null
  revision: string | null
  research_ui_configured: boolean
}

function fail(code = 'version_payload_invalid'): never {
  throw new ResearchSchemaError(code)
}

function requireStringArray(value: unknown): string[] {
  const items = requireArray(value)
  const parsed: string[] = []
  for (const item of items) {
    const text = requireString(item)
    if (parsed.includes(text)) {
      fail('version_payload_duplicate_entry')
    }
    parsed.push(text)
  }
  return parsed
}

export function parseVersionPayload(value: unknown): VersionPayload {
  if (!isRecord(value)) {
    fail()
  }
  const record: Record<string, unknown> = requireRecord(value)
  const protocolVersion = requireString(record.protocol_version)
  const layoutVersion = requireString(record.observer_layout_version)
  const supported = requireStringArray(record.supported_observer_protocols)
  const capabilities = requireStringArray(record.observer_capabilities)
  const reserved = requireStringArray(record.observer_reserved_capabilities)

  if (!supported.includes(protocolVersion)) {
    fail('version_payload_protocol_unsupported')
  }
  if (capabilities.some((name) => reserved.includes(name))) {
    fail('version_payload_capability_overlap')
  }
  const researchUiConfigured = record.research_ui_configured
  if (typeof researchUiConfigured !== 'boolean') {
    fail()
  }

  return {
    application_version: requireOptionalString(record.application_version),
    protocol_version: protocolVersion,
    supported_observer_protocols: supported,
    observer_layout_version: layoutVersion,
    observer_capabilities: capabilities,
    observer_reserved_capabilities: reserved,
    export_engine: requireOptionalString(record.export_engine),
    export_renderer: requireOptionalString(record.export_renderer),
    revision: requireOptionalString(record.revision),
    research_ui_configured: researchUiConfigured,
  }
}
