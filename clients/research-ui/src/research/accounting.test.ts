import { describe, expect, it } from 'vitest'
import { parseResearchSelection } from './selection'

describe('accounting ledger selection', () => {
  it('accepts the run-scoped view with a run id', () => {
    const parsed = parseResearchSelection('run_id=run-1&view=accounting-ledgers')
    expect(parsed.ok).toBe(true)
    if (parsed.ok) expect(parsed.selection.view).toBe('accounting-ledgers')
  })

  it('rejects the view without a run id', () => {
    const parsed = parseResearchSelection('view=accounting-ledgers')
    expect(parsed.ok).toBe(false)
    if (!parsed.ok) expect(parsed.reasonCode).toBe('run_id_missing')
  })
})
