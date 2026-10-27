/** Explicit continuation paging with local caps and identity checks. */

export type PageResult<T> = {
  items: readonly T[]
  nextCursor: string | null
  publicationId?: string | null
}

export type PagerStopReason =
  | 'exhausted'
  | 'repeated_cursor'
  | 'local_cap'
  | 'publication_changed'
  | 'duplicate_inconsistent_ref'
  | 'fetch_error'

export type PagerState<T> = {
  items: readonly T[]
  nextCursor: string | null
  truncated: boolean
  limited: boolean
  stopReason: PagerStopReason | null
  publicationChanged: boolean
  pages: number
}

export type PagerOptions<T> = {
  keyOf?: (item: T) => string
  maxItems?: number
  maxEmptyPages?: number
  fingerprintOf?: (item: T) => string
}

export class ExplicitPager<T> {
  private items: T[] = []
  private buffered: T[] = []
  private bufferedNextCursor: string | null = null
  private nextCursor: string | null = null
  private seenCursors = new Set<string>()
  private seenItems = new Map<string, string>()
  private pages = 0
  private stopReason: PagerStopReason | null = null
  private publicationId: string | null = null
  private publicationChanged = false
  private epoch = 0
  private activeLoad: Promise<PagerState<T>> | null = null

  constructor(
    private readonly fetchPage: (
      cursor: string | null,
    ) => Promise<PageResult<T>>,
    private readonly options: PagerOptions<T> = {},
  ) {}

  get state(): PagerState<T> {
    const limited = this.stopReason === 'local_cap'
    return {
      items: [...this.items],
      nextCursor: this.nextCursor,
      truncated: limited || this.nextCursor !== null,
      limited,
      stopReason: this.stopReason,
      publicationChanged: this.publicationChanged,
      pages: this.pages,
    }
  }

  reset(): void {
    this.epoch += 1
    this.items = []
    this.buffered = []
    this.bufferedNextCursor = null
    this.nextCursor = null
    this.seenCursors.clear()
    this.seenItems.clear()
    this.pages = 0
    this.stopReason = null
    this.publicationId = null
    this.publicationChanged = false
  }

  async loadMore(): Promise<PagerState<T>> {
    if (this.activeLoad !== null) {
      return this.activeLoad
    }
    this.activeLoad = this.loadPages().finally(() => {
      this.activeLoad = null
    })
    return this.activeLoad
  }

  private async loadPages(): Promise<PagerState<T>> {
    if (this.stopReason !== null && this.stopReason !== 'local_cap') {
      return this.state
    }
    const epoch = this.epoch
    this.stopReason = null
    const maxItems = this.options.maxItems ?? 500
    const maxEmptyPages = this.options.maxEmptyPages ?? 8
    const budget = { delivered: 0 }
    let emptyPages = 0
    while (true) {
      if (this.buffered.length === 0 && this.bufferedNextCursor !== null) {
        this.nextCursor = this.bufferedNextCursor
        this.bufferedNextCursor = null
      }
      if (this.buffered.length > 0) {
        const outcome = this.deliverBuffered(maxItems, budget)
        if (outcome === 'cap') {
          if (this.buffered.length === 0 && this.bufferedNextCursor === null) {
            this.stopReason = 'exhausted'
            return this.state
          }
          this.stopReason = 'local_cap'
          return this.state
        }
        this.nextCursor = this.bufferedNextCursor
        this.bufferedNextCursor = null
        if (this.nextCursor === null) {
          this.stopReason = 'exhausted'
          return this.state
        }
        continue
      }
      const cursor = this.nextCursor
      if (cursor !== null) {
        if (this.seenCursors.has(cursor)) {
          this.stopReason = 'repeated_cursor'
          return this.state
        }
        this.seenCursors.add(cursor)
      }
      let page: PageResult<T>
      try {
        page = await this.fetchPage(cursor)
      } catch {
        if (epoch !== this.epoch) {
          return this.state
        }
        this.stopReason = 'fetch_error'
        return this.state
      }
      if (epoch !== this.epoch) {
        return this.state
      }
      this.pages += 1
      if (
        page.publicationId !== undefined &&
        page.publicationId !== null &&
        this.publicationId !== null &&
        page.publicationId !== this.publicationId
      ) {
        this.items = []
        this.buffered = []
        this.bufferedNextCursor = null
        this.nextCursor = page.nextCursor
        this.publicationChanged = true
        this.stopReason = 'publication_changed'
        return this.state
      }
      if (page.publicationId !== undefined && page.publicationId !== null) {
        this.publicationId = page.publicationId
      }
      const pageItems = [...page.items]
      const outcome = this.deliver(pageItems, maxItems, budget)
      if (outcome === 'cap' || outcome === 'inconsistent') {
        if (outcome === 'inconsistent') {
          this.stopReason = 'duplicate_inconsistent_ref'
          return this.state
        }
        if (this.buffered.length === 0) {
          if (page.nextCursor === null) {
            this.stopReason = 'exhausted'
            return this.state
          }
          this.nextCursor = page.nextCursor
        } else {
          this.bufferedNextCursor = page.nextCursor
          this.nextCursor = null
        }
        this.stopReason = 'local_cap'
        return this.state
      }
      this.nextCursor = page.nextCursor
      if (page.items.length === 0 && page.nextCursor !== null) {
        emptyPages += 1
        if (emptyPages < maxEmptyPages) {
          continue
        }
      }
      if (this.nextCursor === null) {
        this.stopReason = 'exhausted'
      }
      return this.state
    }
  }

  private deliverBuffered(
    maxItems: number,
    budget: { delivered: number },
  ): 'ok' | 'cap' | 'inconsistent' {
    const pending = this.buffered
    this.buffered = []
    const result = this.deliver(pending, maxItems, budget)
    if (result === 'cap') {
      // deliver() retained the undelivered suffix in this.buffered.
      return 'cap'
    }
    return result
  }

  private deliver(
    pageItems: T[],
    maxItems: number,
    budget: { delivered: number },
  ): 'ok' | 'cap' | 'inconsistent' {
    for (let index = 0; index < pageItems.length; index += 1) {
      if (budget.delivered >= maxItems) {
        this.buffered = pageItems.slice(index)
        return 'cap'
      }
      const item = pageItems[index] as T
      const key = this.options.keyOf?.(item) ?? String(this.items.length)
      const fingerprint = this.options.fingerprintOf?.(item) ?? ''
      const previous = this.seenItems.get(key)
      if (previous !== undefined) {
        if (previous !== fingerprint) {
          return 'inconsistent'
        }
        continue
      }
      this.seenItems.set(key, fingerprint)
      this.items.push(item)
      budget.delivered += 1
    }
    return 'ok'
  }
}

export type GraphCaps = {
  maxNodes?: number
  maxEdges?: number
}

export type CappedGraph<TNode, TEdge> = {
  nodes: readonly TNode[]
  edges: readonly TEdge[]
  nodesTruncated: boolean
  edgesTruncated: boolean
}

export function applyGraphCaps<TNode, TEdge>(
  nodes: readonly TNode[],
  edges: readonly TEdge[],
  caps: GraphCaps = {},
): CappedGraph<TNode, TEdge> {
  const maxNodes = caps.maxNodes ?? 500
  const maxEdges = caps.maxEdges ?? 1500
  return {
    nodes: nodes.slice(0, maxNodes),
    edges: edges.slice(0, maxEdges),
    nodesTruncated: nodes.length > maxNodes,
    edgesTruncated: edges.length > maxEdges,
  }
}
