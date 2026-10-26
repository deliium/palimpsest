import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  groundAnchors,
  migrationRows,
  societyGroups,
  topologyFromMap,
} from './spatial'

const root = resolve(process.cwd(), '../godot-observer/fixtures/protocol/civilization')
function fixture(name: string): Record<string, unknown> {
  return JSON.parse(readFileSync(resolve(root, `${name}.json`), 'utf8')) as Record<string, unknown>
}
function rows(name: string): Record<string, unknown>[] {
  return (fixture(name).rows as Record<string, unknown>[]) ?? []
}

describe('spatial adapters', () => {
  it('builds layout-independent locations, regions and routes', () => {
    const topology = topologyFromMap({
      locations: rows('map_locations'),
      regions: rows('map_regions'),
      routes: rows('map_routes'),
    })
    expect(topology.nodes.some((node) => node.kind === 'region')).toBe(true)
    expect(topology.nodes.some((node) => node.kind === 'location')).toBe(true)
    expect(topology.edges.some((edge) => edge.label.startsWith('route'))).toBe(true)
  })

  it('deduplicates repeated journey snapshots by journey/window/boundary', () => {
    const source = rows('overlay_migration')
    expect(migrationRows([...source, ...source])).toHaveLength(source.length)
  })

  it('labels historical anchors and unlocated rows distinctly', () => {
    const source = rows('overlay_migration')
    const anchored = {
      ...source[0],
      context: {
        ...(source[0]?.context as Record<string, unknown>),
        anchors: [
          {
            kind: 'location',
            location_id: 'loc-old',
            entity_id: null,
            evidence_ref: { source_kind: 'migration', source_id: 'j1', tick: 2, owner_id: null },
            evidence_tick: 2,
          },
          {
            kind: 'location',
            location_id: 'loc-missing',
            entity_id: null,
            evidence_ref: { source_kind: 'migration', source_id: 'j1', tick: 2, owner_id: null },
            evidence_tick: 2,
          },
        ],
      },
    }
    const grounded = groundAnchors([anchored], new Set(['loc-old']), 5)
    expect(grounded.located[0]?.historical).toBe(true)
    expect(grounded.located[0]?.evidenceTick).toBe(2)
    expect(grounded.unlocated[0]?.reason).toBe('missing_regional_layout')
  })

  it('keeps group basis, missing lanes and policy versions separate', () => {
    const groups = societyGroups(rows('overlay_social_groups'))
    expect(groups.length).toBeGreaterThan(0)
    expect(groups[0]?.basis).toBeTruthy()
    expect(Array.isArray(groups[0]?.missingLanes)).toBe(true)
    expect(groups[0]?.policyVersion).toBeTruthy()
  })
})
