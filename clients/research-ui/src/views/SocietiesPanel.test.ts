import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(
  resolve(process.cwd(), 'src/views/SocietiesPanel.svelte'),
  'utf-8',
)

describe('societies view', () => {
  it('reads society metric families through the generic metric endpoints', () => {
    expect(source).toContain('getMetricCatalog')
    expect(source).toContain('getMetricDocument')
    expect(source).toContain("'society_emergence'")
    expect(source).toContain("'society_divergence'")
    expect(source).toContain("'society_isolation'")
  })

  it('renders analytical results under research inference chrome', () => {
    expect(source).toContain('EpistemicBadge')
    expect(source).toContain('epistemic="research_inference"')
    expect(source).toContain('never enter')
  })
})

describe('societies candidate lanes', () => {
  it('renders analytical group basis, missing lanes and policy without a society registry', () => {
    expect(source).toContain('getCivilizationOverlays')
    expect(source).toContain("layer: 'social_groups'")
    expect(source).toContain('missingLanes')
    expect(source).toContain('policyVersion')
    expect(source).toContain('no polity or society registry')
  })
})
