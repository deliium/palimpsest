import {
  type CapabilitySlot,
  credentialFor,
} from '../auth/credentials'

export type ApiErrorBody = {
  code?: string
  title?: string
  detail?: string
}

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message?: string) {
    super(message ?? code)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
  }
}

export type FetchOptions = {
  capability: CapabilitySlot
  query?: Record<string, string | number | undefined | null>
  method?: 'GET' | 'POST'
  body?: unknown
}

function buildUrl(path: string, query?: FetchOptions['query']): string {
  const url = new URL(path, window.location.origin)
  if (query !== undefined) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === '') {
        continue
      }
      url.searchParams.set(key, String(value))
    }
  }
  return url.pathname + url.search
}

export async function apiFetch<T>(
  path: string,
  options: FetchOptions,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  }
  const token = credentialFor(options.capability)
  if (token !== null) {
    headers['x-palimpsest-token'] = token
  }
  const method = options.method ?? 'GET'
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json'
  }

  const url = buildUrl(path, options.query)
  if (import.meta.env.DEV) {
    console.debug(`research_ui_fetch path=${path} capability=${options.capability}`)
  }

  const init: RequestInit = { method, headers }
  if (options.body !== undefined) {
    init.body = JSON.stringify(options.body)
  }
  const response = await fetch(url, init)

  if (import.meta.env.DEV) {
    console.debug(
      `research_ui_fetch_status path=${path} status=${response.status}`,
    )
  }

  if (!response.ok) {
    let code = `http_${response.status}`
    try {
      const problem = (await response.json()) as ApiErrorBody
      if (typeof problem.code === 'string' && problem.code !== '') {
        code = problem.code
      }
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiClientError(response.status, code)
  }

  return (await response.json()) as T
}

export type RunListItem = {
  run_id: string
  lifecycle_state: string
  ticks_committed: number
  progress_cursor: number
  config_schema_version: string | null
  terminal_reason_code: string | null
}

export type RunListOut = {
  items: RunListItem[]
  next_cursor: string | null
  count: number
}

export type ObserverRunOut = {
  run_id: string
  world_id: string
  tick: number
  latest_tick: number | null
  latest_sequence: number | null
  parent_run_id: string | null
  fork_tick: number | null
  intervention_summary: string | null
  branch_id: string | null
  protocol_version: string
}

export type ExperimentalStateOut = {
  run_id: string
  experiment_id: string | null
  membership_source: string | null
  has_assignment: boolean
  availability: string
}

export type BranchLineageOut = {
  child_run_id: string
  parent_run_id: string
  fork_tick: number
  intervention_kind: string
  intervention_summary: string
  branch_id: string
}

export function listInspectRuns(after?: string | null): Promise<RunListOut> {
  return apiFetch<RunListOut>('/v1/research/runs', {
    capability: 'objective_inspection',
    query: { after: after ?? undefined, limit: 50 },
  })
}

export function getObserverRun(runId: string): Promise<ObserverRunOut> {
  return apiFetch<ObserverRunOut>(`/v1/simulations/${runId}/observer/run`, {
    capability: 'objective_inspection',
  })
}

export function getExperimental(runId: string): Promise<ExperimentalStateOut> {
  return apiFetch<ExperimentalStateOut>(
    `/v1/simulations/${runId}/experimental`,
    { capability: 'objective_inspection' },
  )
}

export function getBranchLineage(runId: string): Promise<BranchLineageOut> {
  return apiFetch<BranchLineageOut>(`/v1/simulations/${runId}/branch`, {
    capability: 'objective_inspection',
  })
}
