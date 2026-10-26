import { describe, expect, it } from 'vitest'
import { ExplicitPager, applyGraphCaps } from './paging'

type Row = { id: string; value: number }

describe('explicit pager', () => {
  it('continues across empty pages with a cursor', async () => {
    const pages: Record<string, { items: Row[]; nextCursor: string | null }> = {
      start: { items: [], nextCursor: 'p2' },
      p2: { items: [{ id: 'a', value: 1 }], nextCursor: null },
    }
    let calls = 0
    const pager = new ExplicitPager<Row>(async (cursor) => {
      calls += 1
      const page = pages[cursor ?? 'start']
      if (page === undefined) {
        throw new Error('missing_page')
      }
      return page
    })
    const state = await pager.loadMore()
    expect(calls).toBe(2)
    expect(state.items).toEqual([{ id: 'a', value: 1 }])
    expect(state.stopReason).toBe('exhausted')
  })

  it('stops on a repeated cursor', async () => {
    const pager = new ExplicitPager<Row>(async () => ({
      items: [],
      nextCursor: 'same',
    }))
    let state = await pager.loadMore()
    expect(state.nextCursor).toBe('same')
    state = await pager.loadMore()
    expect(state.stopReason).toBe('repeated_cursor')
  })

  it('enforces local item caps', async () => {
    const pager = new ExplicitPager<Row>(
      async () => ({
        items: [
          { id: 'a', value: 1 },
          { id: 'b', value: 2 },
        ],
        nextCursor: 'more',
      }),
      { maxItems: 1 },
    )
    const state = await pager.loadMore()
    expect(state.items).toHaveLength(1)
    expect(state.stopReason).toBe('local_cap')
    expect(state.truncated).toBe(true)
  })

  it('restarts when the publication changes', async () => {
    let call = 0
    const pager = new ExplicitPager<Row>(async () => {
      call += 1
      return call === 1
        ? { items: [{ id: 'a', value: 1 }], nextCursor: 'next', publicationId: 'p1' }
        : { items: [{ id: 'b', value: 2 }], nextCursor: null, publicationId: 'p2' }
    })
    await pager.loadMore()
    const state = await pager.loadMore()
    expect(state.publicationChanged).toBe(true)
    expect(state.items).toEqual([])
    expect(state.stopReason).toBe('publication_changed')
  })

  it('rejects duplicate keys with inconsistent contents', async () => {
    const pager = new ExplicitPager<Row>(
      async () => ({
        items: [
          { id: 'a', value: 1 },
          { id: 'a', value: 2 },
        ],
        nextCursor: null,
      }),
      {
        keyOf: (row) => row.id,
        fingerprintOf: (row) => String(row.value),
      },
    )
    const state = await pager.loadMore()
    expect(state.stopReason).toBe('duplicate_inconsistent_ref')
  })

  it('applies graph caps before rendering', () => {
    const capped = applyGraphCaps(
      Array.from({ length: 4 }, (_, index) => index),
      Array.from({ length: 4 }, (_, index) => index),
      { maxNodes: 2, maxEdges: 3 },
    )
    expect(capped.nodes).toEqual([0, 1])
    expect(capped.edges).toEqual([0, 1, 2])
    expect(capped.nodesTruncated).toBe(true)
    expect(capped.edgesTruncated).toBe(true)
  })
})
