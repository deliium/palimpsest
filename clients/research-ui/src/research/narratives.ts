/** Narrative metadata-only summaries. No story content is present. */

export type NarrativeVariant = Record<string, unknown>

export type NarrativeSummary = {
  ownerId: string
  count: number
  roots: number
  branches: number
  merges: number
  sourceLinked: number
  carriers: number
  variants: NarrativeVariant[]
}

export function narrativeSummary(
  overlay: Record<string, unknown>,
): NarrativeSummary {
  const raw = Array.isArray(overlay.variants) ? overlay.variants : []
  const variants = raw.filter(
    (row): row is NarrativeVariant =>
      row !== null && typeof row === 'object' && !Array.isArray(row),
  )
  const carriers = new Set<string>()
  for (const variant of variants) {
    const ids = Array.isArray(variant.carrier_agent_ids)
      ? variant.carrier_agent_ids
      : []
    for (const id of ids) {
      if (typeof id === 'string') {
        carriers.add(id)
      }
    }
  }
  return {
    ownerId: String(overlay.agent_id ?? overlay.owner_id ?? ''),
    count: variants.length,
    roots: variants.filter(
      (variant) =>
        Array.isArray(variant.parent_variant_ids) &&
        variant.parent_variant_ids.length === 0,
    ).length,
    branches: variants.filter(
      (variant) =>
        Array.isArray(variant.parent_variant_ids) &&
        variant.parent_variant_ids.length > 1,
    ).length,
    merges: variants.filter(
      (variant) =>
        typeof variant.merged_into_id === 'string' &&
        variant.merged_into_id !== '',
    ).length,
    sourceLinked: variants.filter(
      (variant) =>
        typeof variant.source_event_id === 'string' &&
        variant.source_event_id !== '',
    ).length,
    carriers: carriers.size,
    variants,
  }
}
