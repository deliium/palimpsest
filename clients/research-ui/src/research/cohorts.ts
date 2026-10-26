/** Composite cohort identity and descriptive survival-share tables. */

import type { DemographicsEnvelope } from '../api/researchSchemas'

export type CohortIdentity = {
  runId: string
  generationIndex: number
  entryTick: number
  cohortId: string
}

export type CohortRow = CohortIdentity & {
  admitted: number
  living: number
  dead: number
  exposureTicks: number | null
}

export type NamedCohortRow = CohortRow & {
  key: string
}

export function cohortKey(identity: CohortIdentity): string {
  return [
    identity.runId,
    identity.generationIndex,
    identity.entryTick,
    identity.cohortId,
  ].join(':')
}

export function cohortRows(
  runId: string,
  envelopes: readonly DemographicsEnvelope[],
): NamedCohortRow[] {
  const rows = new Map<string, CohortRow>()
  for (const envelope of envelopes) {
    for (const cohort of envelope.cohorts) {
      const identity: CohortIdentity = {
        runId,
        generationIndex: cohort.generation_index,
        entryTick: cohort.entry_tick,
        cohortId: cohort.cohort_id,
      }
      const key = cohortKey(identity)
      if (rows.has(key)) {
        continue
      }
      rows.set(key, {
        ...identity,
        admitted: cohort.admitted,
        living: cohort.living,
        dead: cohort.dead,
        exposureTicks:
          envelope.availability === 'available'
            ? Math.max(0, envelope.resolved_tick - cohort.entry_tick)
            : null,
      })
    }
  }
  return [...rows.values()]
    .map((row) => ({ ...row, key: cohortKey(row) }))
    .sort(
      (left, right) =>
        left.generationIndex - right.generationIndex ||
        left.entryTick - right.entryTick ||
        left.cohortId.localeCompare(right.cohortId),
    )
}

export function survivalShare(row: CohortRow): number | null {
  return row.admitted === 0 ? null : row.living / row.admitted
}

export type CohortResolution =
  | { kind: 'resolved'; row: NamedCohortRow }
  | { kind: 'none' }
  | { kind: 'ambiguous' }
  | { kind: 'incomplete' }

export function resolveCohortSelection(
  rows: readonly NamedCohortRow[],
  selection: {
    cohortGenerationIndex?: number | null
    cohortEntryTick?: number | null
    cohortId?: string | null
  },
): CohortResolution {
  const generation = selection.cohortGenerationIndex ?? null
  const entry = selection.cohortEntryTick ?? null
  const id = selection.cohortId ?? null
  const present = [generation, entry, id].filter((value) => value !== null).length
  if (present === 0) {
    return { kind: 'none' }
  }
  if (present !== 3) {
    if (id === null || generation !== null || entry !== null) {
      return { kind: 'incomplete' }
    }
    const matches = rows.filter((row) => row.cohortId === id)
    if (matches.length === 0) {
      return { kind: 'none' }
    }
    if (matches.length > 1) {
      return { kind: 'ambiguous' }
    }
    const only = matches[0]
    return only === undefined ? { kind: 'none' } : { kind: 'resolved', row: only }
  }
  const found = rows.find(
    (row) =>
      row.generationIndex === generation &&
      row.entryTick === entry &&
      row.cohortId === id,
  )
  return found === undefined ? { kind: 'none' } : { kind: 'resolved', row: found }
}

export function cohortPatch(row: NamedCohortRow) {
  return {
    cohort: {
      generationIndex: row.generationIndex,
      entryTick: row.entryTick,
      cohortId: row.cohortId,
    },
  }
}

export type CohortComparisonFacet = {
  key: string
  label: string
  admitted: number
  living: number
  dead: number
  share: number | null
  exposureTicks: number | null
  provenance: string
}

export function compareCohorts(
  rows: readonly NamedCohortRow[],
): CohortComparisonFacet[] {
  return rows.map((row) => ({
    key: row.key,
    label: `gen ${row.generationIndex} · entry ${row.entryTick} · ${row.cohortId}`,
    admitted: row.admitted,
    living: row.living,
    dead: row.dead,
    share: survivalShare(row),
    exposureTicks: row.exposureTicks,
    provenance: 'within-run census; not Kaplan–Meier or a causal effect',
  }))
}
