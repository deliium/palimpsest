import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type MigrationDisplacementSummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  candidate_count: number
  wave_count: number
  cluster_count: number
  outcome_count: number
  movement_count: number
  cause_count: number
  displacement_like_count: number
  mixed_count: number
  not_displacement_like_count: number
  unknown_count: number
  coverage: string
}

export type MigrationWave = {
  wave_token: string
  origin_token: string
  destination_token: string
  participant_tokens: string[]
  route_tokens: string[]
  start_tick: number
  end_tick: number
  cause_support_counts: [string, number][]
  displacement_classification: string
  displacement_bases: string[]
  independent_cause_count: number
  cluster_tokens: string[]
  coverage: string
  lineage_tokens?: string[]
  alignment_tokens?: string[]
}

export type MigrationRoute = {
  route_token: string
  owner_token: string
  origin_token: string
  destination_token: string
  route_tokens: string[]
  observed_duration_ticks: number
  fatigue_cost: number
  basis: string
  status: string
  first_tick: number
  last_tick: number
}

export type MigrationCause = {
  cause_token: string
  owner_token: string
  cause_kind: string
  source_kind: string
  anchor_token: string
  confidence: number
  tick: number
  status: string
}

export type MigrationOutcome = {
  outcome_token: string
  participant_token: string
  destination_token: string
  residence_ticks: number
  access_evidence_count: number
  participation_evidence_count: number
  relationship_evidence_count: number
  conflict_evidence_count: number
  classification: string
  coverage: string
  censored: boolean
}

export type Page<T> = {
  items: T[]
  next_cursor?: string | null
}

export type MigrationListOptions = {
  cursor?: string
  limit?: number
  classification?: string
  cause_kind?: string
  outcome?: string
  origin_token?: string
  destination_token?: string
  cluster_token?: string
}

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/migration`
}

export function fetchMigrationSummary(
  runId: string,
): Promise<MigrationDisplacementSummary> {
  return apiFetch<MigrationDisplacementSummary>(base(runId), {
    capability: CAPABILITY,
  })
}

export function fetchMigrationWaves(
  runId: string,
  options: MigrationListOptions = {},
): Promise<Page<MigrationWave>> {
  return apiFetch<Page<MigrationWave>>(`${base(runId)}/waves`, {
    capability: CAPABILITY,
    query: {
      cursor: options.cursor,
      limit: options.limit ?? 200,
      classification: options.classification,
      origin_token: options.origin_token,
      destination_token: options.destination_token,
      cluster_token: options.cluster_token,
    },
  })
}

export function fetchMigrationWave(
  runId: string,
  waveId: string,
): Promise<MigrationWave> {
  return apiFetch<MigrationWave>(
    `${base(runId)}/waves/${encodeURIComponent(waveId)}`,
    { capability: CAPABILITY },
  )
}

export function fetchMigrationRoutes(
  runId: string,
  options: MigrationListOptions = {},
): Promise<Page<MigrationRoute>> {
  return apiFetch<Page<MigrationRoute>>(`${base(runId)}/routes`, {
    capability: CAPABILITY,
    query: {
      cursor: options.cursor,
      limit: options.limit ?? 200,
      origin_token: options.origin_token,
      destination_token: options.destination_token,
    },
  })
}

export function fetchMigrationCauses(
  runId: string,
  options: MigrationListOptions = {},
): Promise<Page<MigrationCause>> {
  return apiFetch<Page<MigrationCause>>(`${base(runId)}/causes`, {
    capability: CAPABILITY,
    query: {
      cursor: options.cursor,
      limit: options.limit ?? 200,
      cause_kind: options.cause_kind,
    },
  })
}

export function fetchMigrationOutcomes(
  runId: string,
  options: MigrationListOptions = {},
): Promise<Page<MigrationOutcome>> {
  return apiFetch<Page<MigrationOutcome>>(`${base(runId)}/outcomes`, {
    capability: CAPABILITY,
    query: {
      cursor: options.cursor,
      limit: options.limit ?? 200,
      outcome: options.outcome,
      destination_token: options.destination_token,
    },
  })
}
