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
  private nextCursor: string | null = null
  private seenCursors = new Set<string>()
  private seenItems = new Map<string, string>()
  private pages = 0
  private stopReason: PagerStopReason | null = null
  private publicationId: string | null = null
  private publicationChanged = false

  constructor(
    private readonly fetchPage: (
      cursor: string | null,
    ) => Promise<PageResult<T>>,
    private readonly options: PagerOptions<T> = {},
  ) {}

  get state(): PagerState<T> {
    return {
      items: [...this.items],
      nextCursor: this.nextCursor,
      truncated: this.nextCursor !== null,
      stopReason: this.stopReason,
      publicationChanged: this.publicationChanged,
      pages: this.pages,
    }
  }

  reset(): void {
    this.items = []
    this.nextCursor = null
    this.seenCursors.clear()
    this.seenItems.clear()
    this.pages = 0
    this.stopReason = null
    this.publicationId = null
    this.publicationChanged = false
  }

  async loadMore(): Promise<PagerState<T>> {
    if (
      this.stopReason !== null &&
      this.stopReason !== 'local_cap'
    ) {
      return this.state
    }
    this.stopReason = null
    const maxItems = this.options.maxItems ?? 500
    const maxEmptyPages = this.options.maxEmptyPages ?? 8
    let emptyPages = 0
    while (true) {
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
        this.stopReason = 'fetch_error'
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
        this.nextCursor = page.nextCursor
        this.publicationChanged = true
        this.stopReason = 'publication_changed'
        return this.state
      }
      if (page.publicationId !== undefined && page.publicationId !== null) {
        this.publicationId = page.publicationId
      }
      for (const item of page.items) {
        if (this.items.length >= maxItems) {
          this.stopReason = 'local_cap'
          this.nextCursor = page.nextCursor
          return this.state
        }
        const key = this.options.keyOf?.(item) ?? String(this.items.length)
        const fingerprint = this.options.fingerprintOf?.(item) ?? ''
        const previous = this.seenItems.get(key)
        if (previous !== undefined) {
          if (previous !== fingerprint) {
            this.stopReason = 'duplicate_inconsistent_ref'
            return this.state
          }
          continue
        }
        this.seenItems.set(key, fingerprint)
        this.items.push(item)
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
