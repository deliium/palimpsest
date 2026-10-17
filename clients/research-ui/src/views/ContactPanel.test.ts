import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(process.cwd(), 'src/views/ContactPanel.svelte'), 'utf8')

describe('contact view', () => {
  it('lists all six contact families', () => {
    for (const family of [
      'society_contact',
      'contact_cultural_change',
      'contact_hybrid_practice',
      'contact_knowledge_transfer',
      'contact_lexical_borrowing',
      'contact_reputation_transfer',
    ]) {
      expect(source).toContain(family)
    }
  })

  it('uses analytical inference chrome and no agent-visible claims', () => {
    expect(source).toContain('epistemic="research_inference"')
    expect(source).not.toContain('agent_visible')
  })
})
