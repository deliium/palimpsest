<script lang="ts">
  import {
    type EpistemicClass,
    EPISTEMIC_LABELS,
  } from '../epistemic'

  interface Props {
    epistemic: EpistemicClass
  }

  let { epistemic }: Props = $props()
</script>

<span class="badge" data-epistemic={epistemic} title={EPISTEMIC_LABELS[epistemic]}>
  {EPISTEMIC_LABELS[epistemic]}
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.72rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 0.15rem 0.45rem;
    border: 1px solid currentColor;
    background: color-mix(in srgb, currentColor 12%, transparent);
  }

  .badge::before {
    content: "";
    width: 0.55rem;
    height: 0.55rem;
    background: currentColor;
    opacity: 0.85;
    /* Pattern via repeating gradient for colorblind affordance */
    background-image: repeating-linear-gradient(
      -45deg,
      currentColor 0 1px,
      transparent 1px 3px
    );
  }

  .badge[data-epistemic='objective_world'] {
    color: var(--ep-objective-world);
  }
  .badge[data-epistemic='agent_observation'] {
    color: var(--ep-agent-observation);
  }
  .badge[data-epistemic='agent_memory'] {
    color: var(--ep-agent-memory);
  }
  .badge[data-epistemic='agent_belief'] {
    color: var(--ep-agent-belief);
  }
  .badge[data-epistemic='agent_imagination'] {
    color: var(--ep-agent-imagination);
  }
  .badge[data-epistemic='counterfactual'] {
    color: var(--ep-counterfactual);
  }
  .badge[data-epistemic='research_inference'] {
    color: var(--ep-research-inference);
  }
</style>
