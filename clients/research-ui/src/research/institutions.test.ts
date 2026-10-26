import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  institutionRows,
  laneRows,
  officeClaims,
  timelineGaps,
} from './institutions'

const fixture = JSON.parse(
  readFileSync(
    resolve(process.cwd(), '../godot-observer/fixtures/protocol/civilization/overlay_institutions.json'),
    'utf8',
  ),
) as Record<string, unknown>
const rows = (fixture.rows as Record<string, unknown>[]) ?? []

describe('institution lanes', () => {
  it('keeps concept, episode and office lanes separate', () => {
    const parsed = institutionRows(rows)
    expect(parsed.length).toBe(rows.length)
    for (const lane of ['concept', 'episode', 'office'] as const) {
      expect(laneRows(parsed, lane).every((row) => row.lane === lane)).toBe(true)
    }
  })

  it('keeps native identity owner separate from shared rows', () => {
    const parsed = institutionRows([
      ...rows,
      {
        ...rows[0],
        native_owner_id: 'agent-a',
        native_id: 'same-local',
        context: { ...(rows[0]?.context as Record<string, unknown>), row_id: 'owner-a' },
      },
      {
        ...rows[0],
        native_owner_id: 'agent-b',
        native_id: 'same-local',
        context: { ...(rows[0]?.context as Record<string, unknown>), row_id: 'owner-b' },
      },
    ])
    const owners = parsed
      .filter((row) => row.nativeId === 'same-local')
      .map((row) => row.ownerId)
    expect(owners).toEqual(['agent-a', 'agent-b'])
  })

  it('does not join episodes by label or owner-office ID', () => {
    const parsed = institutionRows(rows)
    const episodeKeys = parsed.filter((row) => row.lane === 'episode').map((row) => row.key)
    expect(new Set(episodeKeys).size).toBe(episodeKeys.length)
  })

  it('marks gaps and returns office claims without selecting a global occupant', () => {
    const parsed = institutionRows(rows)
    expect(timelineGaps(parsed).every((tick) => tick > 0)).toBe(true)
    for (const claim of officeClaims(parsed)) {
      expect(claim.lane).toBe('office')
    }
  })
})
