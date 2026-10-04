import { describe, expect, it } from 'vitest'
import { EPISTEMIC_LABELS } from '../epistemic'

describe('epistemic badge labels', () => {
  it('labels research_inference as analytical result', () => {
    expect(EPISTEMIC_LABELS.research_inference).toBe('Analytical result')
  })

  it('keeps objective and belief chrome distinct', () => {
    expect(EPISTEMIC_LABELS.objective_world).toBe('Objective world')
    expect(EPISTEMIC_LABELS.agent_belief).toBe('Agent belief')
    expect(EPISTEMIC_LABELS.counterfactual).toBe('Counterfactual')
  })
})
