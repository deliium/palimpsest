import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(
  resolve(process.cwd(), 'src/views/InstitutionsPanel.svelte'),
  'utf-8',
)

describe('institutions view', () => {
  it('reads institution families through the generic metric endpoints', () => {
    expect(source).toContain('getMetricCatalog')
    expect(source).toContain('getMetricDocument')
    expect(source).toContain("'institution_emergence'")
    expect(source).toContain("'institutional_persistence'")
  })

  it('renders analytical results under research inference chrome', () => {
    expect(source).toContain('EpistemicBadge')
    expect(source).toContain('epistemic="research_inference"')
    expect(source).toContain('never enter')
  })
})
