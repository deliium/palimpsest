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

  it('drains a buffered page suffix before requesting the next page', async () => {
    const cursors: Array<string | null> = []
    const pager = new ExplicitPager<Row>(
      async (cursor) => {
        cursors.push(cursor)
        if (cursor === null) {
          return {
            items: [
              { id: 'a', value: 1 },
              { id: 'b', value: 2 },
              { id: 'c', value: 3 },
            ],
            nextCursor: 'p2',
          }
        }
        return { items: [{ id: 'd', value: 4 }], nextCursor: null }
      },
      { maxItems: 2, keyOf: (row) => row.id },
    )
    const first = await pager.loadMore()
    expect(first.items.map((row) => row.id)).toEqual(['a', 'b'])
    expect(first.stopReason).toBe('local_cap')
    expect(first.limited).toBe(true)
    expect(cursors).toEqual([null])
    const second = await pager.loadMore()
    expect(second.items.map((row) => row.id)).toEqual(['a', 'b', 'c', 'd'])
    expect(cursors).toEqual([null, 'p2'])
    expect(second.stopReason).toBe('exhausted')
    expect(new Set(second.items.map((row) => row.id)).size).toBe(4)
  })

  it('does not restart the first page after an exact page-boundary cap', async () => {
    const cursors: Array<string | null> = []
    const pager = new ExplicitPager<Row>(
      async (cursor) => {
        cursors.push(cursor)
        return cursor === null
          ? { items: [{ id: 'a', value: 1 }], nextCursor: 'p2' }
          : { items: [{ id: 'b', value: 2 }], nextCursor: null }
      },
      { maxItems: 1, keyOf: (row) => row.id },
    )
    const first = await pager.loadMore()
    expect(first.stopReason).toBeNull()
    expect(first.truncated).toBe(true)
    const second = await pager.loadMore()
    expect(cursors).toEqual([null, 'p2'])
    expect(second.items.map((row) => row.id)).toEqual(['a', 'b'])
  })

  it('ignores an in-flight page after reset', async () => {
    const pendingPage: {
      resolve: ((value: { items: Row[]; nextCursor: string | null }) => void) | null
    } = { resolve: null }
    const pager = new ExplicitPager<Row>(
      () =>
        new Promise((resolve) => {
          pendingPage.resolve = resolve
        }),
    )
    const pending = pager.loadMore()
    pager.reset()
    pendingPage.resolve?.({
      items: [{ id: 'late', value: 9 }],
      nextCursor: null,
    })
    const state = await pending
    expect(state.items).toEqual([])
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
