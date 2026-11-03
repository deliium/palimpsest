/** Read-only formal-rule snapshot client. */

import { apiFetch } from './client'

const CAPABILITY = 'subjective_debug' as const

export type FormalRuleCoverage = {
  observed: number
  expected: number
  partial: boolean
}

export type FormalRuleSummary = {
  run_id: string
  publication_id: string
  schema_version: string
  generated_tick: number
  candidate_count: number
  rule_count: number
  version_count: number
  window_count: number
  coverage: FormalRuleCoverage
  provenance_code: string
  snapshot_digest: string
}

export type FormalRuleCandidate = {
  candidate_id: string
  status: string
  scope_kind: string
  stage: string
  action_token: string
  constraint_kinds: string[]
  authority_kinds: string[]
  system_count: number
  rule_count: number
  version_count: number
  competing_candidate_ids: string[]
  first_tick: number
  last_tick: number
}

export type FormalRuleCandidateDetail = {
  candidate: FormalRuleCandidate
  coverage: FormalRuleCoverage
}

export type FormalRuleWrittenRepresentation = {
  status: string
  artifact_present: boolean
  artifact_revision: number | null
  repository_present: boolean
}

export type FormalRule = {
  rule_id: string
  candidate_id: string
  stage: string
  constraint_kind: string
  scope_kind: string
  action_token: string
  authority_kind: string
  recognition: string
  written_representation: FormalRuleWrittenRepresentation
  sanction_kinds: string[]
  exception_count: number
  version_count: number
  latest_version: number
  proponent_count: number
  response_counts: Array<[string, number]>
}

export type FormalRuleVersion = {
  version_id: string
  rule_id: string
  version_number: number
  stage: string
  constraint_kind: string
  scope_kind: string
  scope_digest: string
  action_token: string
  authority_kind: string
  recognition: string
  written_representation: FormalRuleWrittenRepresentation
  sanction_kinds: string[]
  exception_count: number
  tick: number
  revision_kind: string
  supersedes_version_id: string | null
}

export type FormalRuleLineageEdge = {
  edge_id: string
  source_candidate_id: string
  target_candidate_id: string
  kind: string
  tick: number
  jaccard: number
  containment: number
}

type Page<T> = { items: T[]; next_cursor: string | null; truncated: boolean }

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/formal-rules`
}

export function getFormalRuleSummary(runId: string): Promise<FormalRuleSummary> {
  return apiFetch<FormalRuleSummary>(base(runId), { capability: CAPABILITY })
}

export function getFormalRuleCandidates(
  runId: string,
  options: { status?: string; limit?: number; cursor?: string } = {},
): Promise<Page<FormalRuleCandidate>> {
  return apiFetch<Page<FormalRuleCandidate>>(`${base(runId)}/candidates`, {
    capability: CAPABILITY,
    query: {
      status: options.status,
      limit: options.limit,
      cursor: options.cursor,
    },
  })
}

export function getFormalRuleCandidate(
  runId: string,
  candidateId: string,
): Promise<FormalRuleCandidateDetail> {
  return apiFetch<FormalRuleCandidateDetail>(
    `${base(runId)}/candidates/${encodeURIComponent(candidateId)}`,
    { capability: CAPABILITY },
  )
}

export function getFormalRuleRules(
  runId: string,
  candidateId: string,
  options: { stage?: string; limit?: number; cursor?: string } = {},
): Promise<Page<FormalRule>> {
  return apiFetch<Page<FormalRule>>(
    `${base(runId)}/candidates/${encodeURIComponent(candidateId)}/rules`,
    {
      capability: CAPABILITY,
      query: {
        stage: options.stage,
        limit: options.limit,
        cursor: options.cursor,
      },
    },
  )
}

export function getFormalRuleVersions(
  runId: string,
  candidateId: string,
  options: { ruleId?: string; limit?: number; cursor?: string } = {},
): Promise<Page<FormalRuleVersion>> {
  return apiFetch<Page<FormalRuleVersion>>(
    `${base(runId)}/candidates/${encodeURIComponent(candidateId)}/versions`,
    {
      capability: CAPABILITY,
      query: {
        rule_id: options.ruleId,
        limit: options.limit,
        cursor: options.cursor,
      },
    },
  )
}

export function getFormalRuleLineage(
  runId: string,
  options: { kind?: string; limit?: number; cursor?: string } = {},
): Promise<Page<FormalRuleLineageEdge>> {
  return apiFetch<Page<FormalRuleLineageEdge>>(`${base(runId)}/lineage`, {
    capability: CAPABILITY,
    query: {
      kind: options.kind,
      limit: options.limit,
      cursor: options.cursor,
    },
  })
}
