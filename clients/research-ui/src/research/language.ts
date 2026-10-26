/** Retained semantic-history adapters and subjective as-of metadata cards. */

export type SemanticRow = Record<string, unknown>

export type SemanticTransition = {
  key: string
  ownerId: string
  source: string
  localId: string
  termDigest: string
  fromTick: number
  toTick: number
  trigger: string
  previousReferent: string | null
  nextReferent: string | null
  changed: boolean
  confidence: number | null
}

export type SemanticTimeline = {
  ownerId: string
  source: string
  checkpointTick: number | null
  retainedOnly: boolean
  prefixComplete: boolean
  availability: string
  reason: string | null
  groups: Array<{
    key: string
    ownerId: string
    source: string
    localId: string
    termDigest: string
    rows: SemanticRow[]
  }>
  transitions: SemanticTransition[]
}

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function semanticTimeline(
  history: Record<string, unknown>,
): SemanticTimeline {
  const rawRows = Array.isArray(history.rows) ? history.rows : []
  const rows = rawRows.filter(
    (row): row is SemanticRow =>
      row !== null && typeof row === 'object' && !Array.isArray(row),
  )
  const groups = new Map<string, SemanticTimeline['groups'][number]>()
  for (const row of rows) {
    const source = String(row.term_source ?? history.source ?? '')
    const localId = String(row.local_id ?? '')
    const termDigest = String(row.term_digest ?? '')
    const ownerId = String(history.agent_id ?? '')
    const key = `${ownerId}:${source}:${localId}:${termDigest}`
    const group =
      groups.get(key) ??
      {
        key,
        ownerId,
        source,
        localId,
        termDigest,
        rows: [],
      }
    group.rows.push(row)
    groups.set(key, group)
  }
  const transitions: SemanticTransition[] = []
  for (const group of groups.values()) {
    group.rows.sort(
      (left, right) =>
        Number(left.tick ?? 0) - Number(right.tick ?? 0) ||
        Number(left.ordinal ?? 0) - Number(right.ordinal ?? 0),
    )
    for (let index = 1; index < group.rows.length; index += 1) {
      const previous = group.rows[index - 1]!
      const next = group.rows[index]!
      const previousReferent =
        typeof previous.referent_digest === 'string'
          ? previous.referent_digest
          : null
      const nextReferent =
        typeof next.referent_digest === 'string' ? next.referent_digest : null
      transitions.push({
        key: `${group.key}:${index}`,
        ownerId: group.ownerId,
        source: group.source,
        localId: group.localId,
        termDigest: group.termDigest,
        fromTick: Number(previous.tick ?? 0),
        toTick: Number(next.tick ?? 0),
        trigger: String(next.trigger ?? ''),
        previousReferent,
        nextReferent,
        changed: previousReferent !== nextReferent,
        confidence: num(next.confidence),
      })
    }
  }
  return {
    ownerId: String(history.agent_id ?? ''),
    source: String(history.source ?? ''),
    checkpointTick:
      typeof history.checkpoint_tick === 'number'
        ? history.checkpoint_tick
        : null,
    retainedOnly: history.retained_only === true,
    prefixComplete: history.prefix_complete === true,
    availability: String(history.availability ?? 'unavailable'),
    reason: typeof history.reason === 'string' ? history.reason : null,
    groups: [...groups.values()],
    transitions,
  }
}

export type CurrentSemanticCard = {
  layer: string
  ownerId: string
  count: number
  asOf: 'current_checkpoint'
  note: string
}

export function currentMetadataCard(
  overlay: Record<string, unknown>,
  layer: string,
  note: string,
): CurrentSemanticCard {
  return {
    layer,
    ownerId: String(overlay.agent_id ?? ''),
    count: Number(overlay.count ?? 0),
    asOf: 'current_checkpoint',
    note,
  }
}
