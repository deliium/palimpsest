import { afterEach, describe, expect, it } from 'vitest'
import { stripSecretQueryKeys } from './credentials'

describe('credential query hygiene', () => {
  afterEach(() => {
    sessionStorage.clear()
  })

  it('strips banned secret keys from search', () => {
    const { cleaned, stripped } = stripSecretQueryKeys(
      '?run_id=run-1&token=secret&view=overview',
    )
    expect(stripped).toContain('token')
    expect(cleaned).toContain('run_id=run-1')
    expect(cleaned).not.toContain('token')
  })
})
