import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type ScientificHypothesesSummary = {
  run_id: string
  publication_id: string
  digest: string
  snapshot_version: string
  policy_version: string
  generated_from_tick: number
  window_tick: number
  window_count: number
  coverage: string
  availability: string
  owner_count: number
  hypothesis_count: number
  active_count: number
  supported_count: number
  contradicted_count: number
  inconclusive_count: number
  revision_count: number
  trial_count: number
  matched_count: number
  mismatched_count: number
}

export type ScientificHypothesesPage<T> = {
  run_id: string
  publication_id: string
  window_index: number | null
  rows: T[]
  next_cursor: string | null
  coverage: string
}

export type ScientificHypothesisRow = {
  window_index: number
  window_tick: number
  hypothesis_token: string
  claim_token: string
  causal_hypothesis_token: string
  status: string
  predicted_outcome: string
  confidence_milli: number
  condition_count: number
  condition_pairs: [string, string][]
  support_count: number
  contradiction_count: number
  revision_count: number
  source_kind: string
  active: boolean
  created_tick: number
  coverage: string
}

export type ScientificHypothesisEvidenceRow = {
  window_index: number
  window_tick: number
  hypothesis_token: string
  support_observation_count: number
  contradiction_count: number
  evidence_event_count: number
  unlinked_event_count: number
  coverage: string
}

export type ScientificHypothesisTestRow = {
  window_index: number
  window_tick: number
  hypothesis_token: string
  trial_count: number
  matched_count: number
  mismatched_count: number
  inconclusive_count: number
  last_trial_tick: number
  coverage: string
}

export type ScientificHypothesisRevisionRow = {
  window_index: number
  window_tick: number
  hypothesis_token: string
  revision_index: number
  revision_tick: number
  reason: string
  claim_token: string
  predicted_outcome: string
  condition_pairs: [string, string][]
  confidence_milli: number
  coverage: string
}

export type ScientificHypothesisSourceRow = {
  window_index: number
  window_tick: number
  source_kind: string
  hypothesis_count: number
  adopted_count: number
  coverage: string
}

export type ScientificHypothesisCoverageRow = {
  window_index: number
  window_tick: number
  window_count: number
  event_count: number
  owner_count: number
  hypothesis_count: number
  condition_count: number
  revision_count: number
  trial_count: number
  truncated: boolean
  coverage: string
  availability: string
}

type PageOptions = {
  limit?: number | undefined
  cursor?: string | null | undefined
  windowIndex?: number | undefined
}

export function buildScientificHypothesesQuery(
  options: PageOptions = {},
): string {
  const params = new URLSearchParams()
  if (options.limit !== undefined) params.set('limit', String(options.limit))
  if (options.cursor) params.set('cursor', options.cursor)
  if (options.windowIndex !== undefined) {
    params.set('window_index', String(options.windowIndex))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

const base = (runId: string): string =>
  `/v1/simulations/${encodeURIComponent(runId)}/scientific-hypotheses`

export function getScientificHypothesesSummary(
  runId: string,
): Promise<ScientificHypothesesSummary> {
  return apiFetch<ScientificHypothesesSummary>(base(runId), {
    capability: CAPABILITY,
  })
}

function getPage<T>(
  runId: string,
  purpose: string,
  options: PageOptions,
): Promise<ScientificHypothesesPage<T>> {
  return apiFetch<ScientificHypothesesPage<T>>(
    `${base(runId)}/${purpose}${buildScientificHypothesesQuery(options)}`,
    { capability: CAPABILITY },
  )
}

export function getScientificHypotheses(
  runId: string,
  options: PageOptions = {},
): Promise<ScientificHypothesesPage<ScientificHypothesisRow>> {
  return getPage(runId, 'hypotheses', options)
}

export function getScientificHypothesisEvidence(
  runId: string,
  options: PageOptions = {},
): Promise<ScientificHypothesesPage<ScientificHypothesisEvidenceRow>> {
  return getPage(runId, 'evidence', options)
}

export function getScientificHypothesisTests(
  runId: string,
  options: PageOptions = {},
): Promise<ScientificHypothesesPage<ScientificHypothesisTestRow>> {
  return getPage(runId, 'tests', options)
}

export function getScientificHypothesisRevisions(
  runId: string,
  options: PageOptions = {},
): Promise<ScientificHypothesesPage<ScientificHypothesisRevisionRow>> {
  return getPage(runId, 'revisions', options)
}

export function getScientificHypothesisSources(
  runId: string,
  options: PageOptions = {},
): Promise<ScientificHypothesesPage<ScientificHypothesisSourceRow>> {
  return getPage(runId, 'sources', options)
}

export function getScientificHypothesisCoverage(
  runId: string,
  options: PageOptions = {},
): Promise<ScientificHypothesesPage<ScientificHypothesisCoverageRow>> {
  return getPage(runId, 'coverage', options)
}
