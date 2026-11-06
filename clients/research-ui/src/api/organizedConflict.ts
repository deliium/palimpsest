import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type OrganizedConflictSummary = {
  run_id: string
  publication_id: string
  digest: string
  episode_count: number
  individual_episode_count: number
  coordinated_episode_count: number
  persistent_inter_group_episode_count: number
  participant_count: number
  plan_count: number
  interpretation_count: number
  outcome_count: number
  contradiction_count: number
  termination_count: number
  sustained_episode_count: number
  coverage: string
}

export type OrganizedConflictEpisode = {
  episode_id: string
  classification: string
  start_tick: number
  end_tick: number
  participant_tokens: string[]
  opponent_tokens: string[]
  side_count: number
  hostile_event_count: number
  active_window_count: number
  sustained: boolean
  org_ids: string[]
  msoc_ids: string[]
}

export type OrganizedConflictPlan = {
  plan_id: string
  owner_token: string
  operation: string
  target_kind: string
  status: string
  participant_count: number
  tick: number
}

export type OrganizedConflictInterpretation = {
  interpretation_id: string
  owner_token: string
  episode_id: string
  kind: string
  alignment: string
  tick: number
}

export type Page<T> = {
  items: T[]
  next_cursor?: string | null
  truncated?: boolean
}

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/organized-conflict`
}

export function fetchOrganizedConflictSummary(
  runId: string,
): Promise<OrganizedConflictSummary> {
  return apiFetch<OrganizedConflictSummary>(base(runId), { capability: CAPABILITY })
}

export function fetchOrganizedConflictEpisodes(
  runId: string,
  cursor?: string,
  limit = 200,
): Promise<Page<OrganizedConflictEpisode>> {
  return apiFetch<Page<OrganizedConflictEpisode>>(`${base(runId)}/episodes`, {
    capability: CAPABILITY,
    query: { limit, cursor },
  })
}

export function fetchOrganizedConflictEpisode(
  runId: string,
  episodeId: string,
): Promise<{ episode: OrganizedConflictEpisode; participants: object[] }> {
  return apiFetch(`${base(runId)}/episodes/${encodeURIComponent(episodeId)}`, {
    capability: CAPABILITY,
  })
}

export function fetchOrganizedConflictPlans(
  runId: string,
  cursor?: string,
  limit = 200,
): Promise<Page<OrganizedConflictPlan>> {
  return apiFetch<Page<OrganizedConflictPlan>>(`${base(runId)}/plans`, {
    capability: CAPABILITY,
    query: { limit, cursor },
  })
}

export function fetchOrganizedConflictPlan(
  runId: string,
  planId: string,
): Promise<{ plan: OrganizedConflictPlan; outcomes: object[] }> {
  return apiFetch(`${base(runId)}/plans/${encodeURIComponent(planId)}`, {
    capability: CAPABILITY,
  })
}

export function fetchOrganizedConflictInterpretations(
  runId: string,
  cursor?: string,
  limit = 200,
): Promise<Page<OrganizedConflictInterpretation>> {
  return apiFetch<Page<OrganizedConflictInterpretation>>(
    `${base(runId)}/interpretations`,
    { capability: CAPABILITY, query: { limit, cursor } },
  )
}
