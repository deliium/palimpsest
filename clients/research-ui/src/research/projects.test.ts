import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { projectRows, progressDifference, sampledProgress } from './projects'

const fixture = JSON.parse(
  readFileSync(
    resolve(process.cwd(), '../godot-observer/fixtures/protocol/civilization/map_projects.json'),
    'utf8',
  ),
) as Record<string, unknown>
const rows = (fixture.rows as Record<string, unknown>[]) ?? []

describe('project history adapters', () => {
  it('keeps counters and retained tails distinct', () => {
    const projects = projectRows(rows)
    expect(projects.length).toBe(rows.length)
    expect(projects[0]?.acceptedContributionCount).toBeGreaterThanOrEqual(
      projects[0]?.retainedContributions.length ?? 0,
    )
    expect(projects[0]?.detailTruncated).toBeDefined()
  })

  it('deduplicates identical receipts but never invents distinct events', () => {
    const projects = projectRows(rows)
    const receipts = projects.flatMap((project) => project.retainedContributions)
    const identities = new Set(receipts.map((item) => item.identity))
    expect(identities.size).toBeLessThanOrEqual(receipts.length)
  })

  it('computes only observed display differences', () => {
    const projects = projectRows(rows)
    const first = { ...projects[0]!, boundaryTick: 4 }
    const synthetic = {
      ...first,
      key: `${first.projectId}:later`,
      boundaryTick: (first.boundaryTick ?? 0) + 5,
      laborProgress: first.laborProgress + 3,
      materialProgress: first.materialProgress + 1,
    }
    expect(progressDifference(first, synthetic)).toEqual({ labor: 3, material: 1 })
    expect(progressDifference(first, first)).toBeNull()
    expect(sampledProgress([synthetic, first]).map((item) => item.tick)).toEqual([
      first.boundaryTick,
      synthetic.boundaryTick,
    ])
  })
})
