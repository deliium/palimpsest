import { describe, expect, it } from 'vitest'
import {
  epistemicFromDebuggerArtifact,
  epistemicFromEvidenceClass,
  epistemicFromOverlayKind,
} from './epistemic'

describe('epistemic mapping', () => {
  it('maps analytical overlays to research_inference', () => {
    expect(epistemicFromOverlayKind('emergent_group_formation')).toBe('research_inference')
    expect(epistemicFromOverlayKind('spatial_control')).toBe('research_inference')
    expect(epistemicFromOverlayKind('historical_memory_layers')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('historical_memory_transitions')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('historical_memory_queries')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('durable_record_lineage')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('durable_record_fidelity')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('durable_record_survival')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('knowledge_repository_survival')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('knowledge_repository_access')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('knowledge_repository_organization')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('knowledge_genealogy_holders')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('knowledge_genealogy_lineage')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('knowledge_genealogy_mutation')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('bounded_experiment_trials')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('bounded_experiment_discovery')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('bounded_experiment_provenance')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('technique_lifecycle_state')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('technique_lifecycle_loss')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('technique_lifecycle_diffusion')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('possession_custody_outcomes')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('possession_claim_conflict')).toBe(
      'research_inference',
    )
    expect(epistemicFromOverlayKind('inheritance_convention_distribution')).toBe(
      'research_inference',
    )
    expect(epistemicFromEvidenceClass('ANALYTICAL_INFERRED')).toBe('research_inference')
  })

  it('maps debugger artifact kinds', () => {
    expect(epistemicFromDebuggerArtifact('observation')).toBe('agent_observation')
    expect(epistemicFromDebuggerArtifact('memory')).toBe('agent_memory')
    expect(epistemicFromDebuggerArtifact('belief')).toBe('agent_belief')
    expect(epistemicFromDebuggerArtifact('imagination')).toBe('agent_imagination')
    expect(epistemicFromDebuggerArtifact('counterfactual')).toBe('counterfactual')
    expect(epistemicFromDebuggerArtifact('objective_event')).toBe('objective_world')
  })
})
