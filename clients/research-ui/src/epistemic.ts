/** Closed Research UI epistemic classes (presentation-only). */

export const EPISTEMIC_CLASSES = [
  'objective_world',
  'agent_observation',
  'agent_memory',
  'agent_belief',
  'agent_imagination',
  'counterfactual',
  'research_inference',
] as const

export type EpistemicClass = (typeof EPISTEMIC_CLASSES)[number]

export const EPISTEMIC_LABELS: Record<EpistemicClass, string> = {
  objective_world: 'Objective world',
  agent_observation: 'Agent observation',
  agent_memory: 'Agent memory',
  agent_belief: 'Agent belief',
  agent_imagination: 'Agent imagination',
  counterfactual: 'Counterfactual',
  research_inference: 'Analytical result',
}

/** Wire EvidenceClass values from Godot / observer overlays. */
export type EvidenceClassWire =
  | 'OBJECTIVE'
  | 'SUBJECTIVE_TO_SELECTED_AGENT'
  | 'ANALYTICAL_INFERRED'
  | 'SUBJECTIVE'
  | 'ANALYTICAL'

/** Closed debugger artifact kinds (inspector chrome). */
export type DebuggerArtifactKind =
  | 'objective_event'
  | 'observation'
  | 'memory'
  | 'belief'
  | 'imagination'
  | 'counterfactual'
  | 'analytical_inference'

const ANALYTICAL_OVERLAYS = new Set([
  'spatial_control',
  'emergent_group_formation',
  'emergent_social_norms',
  'persistent_social_conventions',
  'distributed_reputation',
  'cultural_narrative_lineage',
  'communication_strategy',
  'communication_strategy_audit',
  'cultural_transmission',
  'skill_learning',
  'historical_memory_layers',
  'historical_memory_transitions',
  'historical_memory_queries',
  'durable_record_lineage',
  'durable_record_fidelity',
  'durable_record_survival',
  'knowledge_repository_survival',
  'knowledge_repository_access',
  'knowledge_repository_organization',
  'metric',
  'phenomenon_panel',
  'matrix_stats',
])

const SUBJECTIVE_OVERLAYS = new Set([
  'subjective_labels',
  'relationships',
  'territorial_claims',
  'narrative_hops',
  'group_formation_ledger',
  'social_norms_ledger',
  'social_conventions_ledger',
  'cultural_narratives_ledger',
])

export function epistemicFromEvidenceClass(value: string): EpistemicClass {
  const key = value.trim().toUpperCase()
  if (key === 'OBJECTIVE' || key === 'OBJECTIVE_WORLD') {
    return 'objective_world'
  }
  if (
    key === 'SUBJECTIVE_TO_SELECTED_AGENT' ||
    key === 'SUBJECTIVE' ||
    key === 'AGENT_BELIEF'
  ) {
    return 'agent_belief'
  }
  if (key === 'ANALYTICAL_INFERRED' || key === 'ANALYTICAL' || key === 'RESEARCH_INFERENCE') {
    return 'research_inference'
  }
  return 'research_inference'
}

export function epistemicFromDebuggerArtifact(kind: string): EpistemicClass {
  switch (kind.trim().toLowerCase()) {
    case 'objective_event':
    case 'action':
      return 'objective_world'
    case 'observation':
      return 'agent_observation'
    case 'memory':
      return 'agent_memory'
    case 'belief':
      return 'agent_belief'
    case 'imagination':
      return 'agent_imagination'
    case 'counterfactual':
      return 'counterfactual'
    case 'analytical_inference':
      return 'research_inference'
    default:
      return 'research_inference'
  }
}

export function epistemicFromOverlayKind(kind: string): EpistemicClass {
  const key = kind.trim().toLowerCase()
  if (key === 'communication_flows') {
    return 'objective_world'
  }
  if (SUBJECTIVE_OVERLAYS.has(key)) {
    return 'agent_belief'
  }
  if (ANALYTICAL_OVERLAYS.has(key)) {
    return 'research_inference'
  }
  return 'research_inference'
}

export function isEpistemicClass(value: string): value is EpistemicClass {
  return (EPISTEMIC_CLASSES as readonly string[]).includes(value)
}
