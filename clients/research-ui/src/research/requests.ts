/** Credential- and selection-scoped request lifetime control. */

import {
  credentialGeneration,
  subscribeCredentialChanges,
} from '../auth/credentials'

export type ResearchRequestScope = {
  runId: string | null
  view: string
  tick: number | null
  evidenceClass: string | null
  ownerId: string | null
  publicationId: string | null
  filters?: Record<string, string | number | boolean | null | undefined>
}

export class StaleResearchResponse extends Error {
  constructor() {
    super('stale_research_response')
    this.name = 'StaleResearchResponse'
  }
}

export function scopeKey(scope: ResearchRequestScope): string {
  const filters = Object.entries(scope.filters ?? {})
    .filter(([, value]) => value !== undefined)
    .sort(([left], [right]) => left.localeCompare(right))
  return JSON.stringify({
    runId: scope.runId,
    view: scope.view,
    tick: scope.tick,
    evidenceClass: scope.evidenceClass,
    ownerId: scope.ownerId,
    publicationId: scope.publicationId,
    filters,
  })
}

export type RequestToken = {
  epoch: number
  key: string
  signal: AbortSignal
}

export class ResearchScopeController {
  private currentScope: ResearchRequestScope
  private currentKey: string
  private epoch = 0
  private credentialEpoch = credentialGeneration()
  private controller = new AbortController()
  private unsubscribe: () => void
  private resetListeners = new Set<() => void>()

  constructor(scope: ResearchRequestScope) {
    this.currentScope = scope
    this.currentKey = scopeKey(scope)
    this.unsubscribe = subscribeCredentialChanges(() => {
      this.credentialEpoch = credentialGeneration()
      this.reset()
    })
  }

  get key(): string {
    return this.currentKey
  }

  get generation(): number {
    return this.credentialEpoch
  }

  setScope(scope: ResearchRequestScope): boolean {
    const next = scopeKey(scope)
    this.currentScope = scope
    if (next === this.currentKey) {
      return false
    }
    this.currentKey = next
    this.abortCurrent()
    this.notifyReset()
    return true
  }

  begin(): RequestToken {
    this.epoch += 1
    return {
      epoch: this.epoch,
      key: this.currentKey,
      signal: this.currentController().signal,
    }
  }

  isCurrent(token: RequestToken): boolean {
    return (
      token.epoch === this.epoch &&
      token.key === this.currentKey &&
      !token.signal.aborted &&
      this.credentialEpoch === credentialGeneration()
    )
  }

  accept<T>(token: RequestToken, value: T): T {
    if (!this.isCurrent(token)) {
      throw new StaleResearchResponse()
    }
    return value
  }

  reset(): void {
    this.epoch += 1
    this.abortCurrent()
    this.notifyReset()
  }

  onReset(listener: () => void): () => void {
    this.resetListeners.add(listener)
    return () => this.resetListeners.delete(listener)
  }

  dispose(): void {
    this.unsubscribe()
    this.abortCurrent()
    this.resetListeners.clear()
  }

  private currentController(): AbortController {
    return this.controller
  }

  private abortCurrent(): void {
    this.controller.abort()
    this.controller = new AbortController()
  }

  private notifyReset(): void {
    for (const listener of this.resetListeners) {
      listener()
    }
  }

  get scope(): ResearchRequestScope {
    return this.currentScope
  }
}

export class BoundedRequestPool {
  private active = 0
  private readonly queue: Array<() => void> = []

  constructor(private readonly maxConcurrent = 4) {
    if (!Number.isSafeInteger(maxConcurrent) || maxConcurrent < 1) {
      throw new Error('invalid_concurrency')
    }
  }

  get inFlight(): number {
    return this.active
  }

  async run<T>(loader: () => Promise<T>): Promise<T> {
    if (this.active >= this.maxConcurrent) {
      await new Promise<void>((resolve) => this.queue.push(resolve))
    }
    this.active += 1
    try {
      return await loader()
    } finally {
      this.active -= 1
      const next = this.queue.shift()
      if (next !== undefined) {
        next()
      }
    }
  }
}
