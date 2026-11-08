<script lang="ts">
  import { onMount } from 'svelte'
  import {
    ApiClientError,
    getBranchLineage,
    getExperimental,
    getObserverRun,
    type BranchLineageOut,
    type ExperimentalStateOut,
    type ObserverRunOut,
  } from '../api/client'
  import { buildGodotObserverUrl, type ResearchUiDeepLink } from '../deeplink'
  import {
    godotFocusOptions,
    type ResearchSelection,
    type ResearchUiView,
  } from '../research/selection'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'
  import GodotEmbed from '../embed/GodotEmbed.svelte'
  import AgentPanel from './AgentPanel.svelte'
  import AnalyticsPanel from './AnalyticsPanel.svelte'
  import DecisionTracePanel from './DecisionTracePanel.svelte'
  import ForkComparePanel from './ForkComparePanel.svelte'
  import GraphsPanel from './GraphsPanel.svelte'
  import ObjSubjComparePanel from './ObjSubjComparePanel.svelte'
  import SocietiesPanel from './SocietiesPanel.svelte'
  import InstitutionsPanel from './InstitutionsPanel.svelte'
  import ContactPanel from './ContactPanel.svelte'
  import PopulationPanel from './PopulationPanel.svelte'
  import CohortsPanel from './CohortsPanel.svelte'
  import LineagePanel from './LineagePanel.svelte'
  import TeachingPanel from './TeachingPanel.svelte'
  import TechnologyPanel from './TechnologyPanel.svelte'
  import CulturePanel from './CulturePanel.svelte'
  import LanguagePanel from './LanguagePanel.svelte'
  import NarrativePanel from './NarrativePanel.svelte'
  import MigrationPanel from './MigrationPanel.svelte'
  import EconomyPanel from './EconomyPanel.svelte'
  import MacroSocietiesPanel from './MacroSocietiesPanel.svelte'
  import FormalRulesPanel from './FormalRulesPanel.svelte'
  import DisputesPanel from './DisputesPanel.svelte'
  import EvidencePanel from './EvidencePanel.svelte'
  import RepresentationPanel from './RepresentationPanel.svelte'
  import DiplomacyPanel from './DiplomacyPanel.svelte'
  import OrganizedConflictPanel from './OrganizedConflictPanel.svelte'
  import BordersPanel from './BordersPanel.svelte'
  import MigrationDisplacementPanel from './MigrationDisplacementPanel.svelte'
  import OrganizationsPanel from './OrganizationsPanel.svelte'
  import ProjectsPanel from './ProjectsPanel.svelte'

  interface Props {
    runId: string
    view: ResearchUiView
    deepLink: ResearchUiDeepLink
    selection: ResearchSelection
    onSelectionChange: (
      patch: Partial<ResearchSelection>,
      historyMode?: 'push' | 'replace',
    ) => void
  }

  let { runId, view, deepLink, selection, onSelectionChange }: Props = $props()

  const tabGroups: { label: string; tabs: { id: ResearchUiView; label: string }[] }[] =
    [
      {
        label: 'Overview',
        tabs: [
          { id: 'overview', label: 'Overview' },
          { id: 'graphs', label: 'Graphs' },
          { id: 'agent', label: 'Agent' },
          { id: 'analytics', label: 'Analytics' },
        ],
      },
      {
        label: 'Population',
        tabs: [
          { id: 'population', label: 'Population' },
          { id: 'cohorts', label: 'Cohorts' },
        ],
      },
      {
        label: 'Lineage',
        tabs: [
          { id: 'lineage', label: 'Lineage' },
          { id: 'teaching', label: 'Teaching' },
          { id: 'technology', label: 'Technology' },
        ],
      },
      {
        label: 'Culture',
        tabs: [
          { id: 'culture', label: 'Culture' },
          { id: 'language', label: 'Language' },
          { id: 'narratives', label: 'Narratives' },
        ],
      },
      {
        label: 'Space',
        tabs: [{ id: 'migration', label: 'Migration' }],
      },
      {
        label: 'Institutions',
        tabs: [
          { id: 'institutions', label: 'Institutions' },
          { id: 'societies', label: 'Societies' },
          { id: 'macro-societies', label: 'Macro-societies' },
          { id: 'organizations', label: 'Organizations' },
          { id: 'formal-rules', label: 'Formal rules' },
          { id: 'disputes', label: 'Disputes' },
          { id: 'evidence', label: 'Evidence' },
          { id: 'representation', label: 'Representation' },
          { id: 'conflict', label: 'Organized conflict' },
          { id: 'borders', label: 'Borders and claims' },
          { id: 'migration-displacement', label: 'Migration and displacement' },
          { id: 'contact', label: 'Contact' },
        ],
      },
      {
        label: 'Economy',
        tabs: [
          { id: 'economy', label: 'Economy' },
          { id: 'projects', label: 'Projects' },
        ],
      },
      {
        label: 'Debug',
        tabs: [
          { id: 'traces', label: 'Traces' },
          { id: 'compare', label: 'Compare' },
        ],
      },
    ]

  const allTabs = tabGroups.flatMap((group) => group.tabs)

  let run = $state<ObserverRunOut | null>(null)
  let experimental = $state<ExperimentalStateOut | null>(null)
  let branch = $state<BranchLineageOut | null>(null)
  let branchReason = $state<string | null>(null)
  let error = $state<string | null>(null)
  let loading = $state(true)
  let loadedFor = $state<string | null>(null)

  async function load(target: string): Promise<void> {
    loading = true
    error = null
    branchReason = null
    try {
      run = await getObserverRun(target)
      experimental = await getExperimental(target)
      try {
        branch = await getBranchLineage(target)
      } catch (err) {
        branch = null
        branchReason =
          err instanceof ApiClientError ? err.code : 'branch_unavailable'
      }
      loadedFor = target
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
      run = null
    } finally {
      loading = false
    }
  }

  onMount(() => {
    void load(runId)
  })

  $effect(() => {
    if (loadedFor !== runId) {
      void load(runId)
    }
  })

  function selectTab(next: ResearchUiView): void {
    onSelectionChange({ view: next })
  }

  function openObserver(withDebugger: boolean): void {
    const href = buildGodotObserverUrl({
      runId,
      tick: selection.tick ?? run?.tick ?? null,
      eventId: selection.eventId,
      sequence: selection.sequence,
      agentId: deepLink.agentId,
      debugger: withDebugger,
      options: godotFocusOptions(selection),
    })
    window.open(href, '_blank', 'noopener,noreferrer')
  }
</script>

<section class="page">
  <header class="head">
    <div>
      <p class="eyebrow">Run</p>
      <h1>{runId}</h1>
      <p class="lede">Simulation metadata (seeds and condition values never shown).</p>
    </div>
    <div class="actions">
      <EpistemicBadge epistemic="objective_world" />
      <button
        type="button"
        onclick={() => openObserver(false)}
        disabled={selection.generationIndex !== null && selection.tick === null}
        title={selection.generationIndex !== null && selection.tick === null
          ? 'Resolve the generation marker before opening Godot.'
          : undefined}
      >
        Open in World Observer
      </button>
      <button type="button" class="ghost" onclick={() => openObserver(true)}>Open Why?</button>
    </div>
  </header>

  <nav class="tabs" aria-label="Run views">
    {#each tabGroups as group (group.label)}
      <div class="tab-group">
        <span class="tab-group-label">{group.label}</span>
        <div class="tab-row">
          {#each group.tabs as tab (tab.id)}
            <button
              type="button"
              class:active={view === tab.id}
              aria-current={view === tab.id ? 'page' : undefined}
              onclick={() => selectTab(tab.id)}
            >
              {tab.label}
            </button>
          {/each}
        </div>
      </div>
    {/each}
    {#if !allTabs.some((tab) => tab.id === view)}
      <p class="status error" role="alert">Unknown view: {view}</p>
    {/if}
  </nav>

  {#if loading}
    <p class="status">Loading…</p>
  {:else if error !== null}
    <p class="status error" role="alert">Unable to load run: {error}</p>
  {:else if view === 'overview' && run !== null}
    <dl class="meta">
      <div><dt>World</dt><dd>{run.world_id}</dd></div>
      <div><dt>Tick</dt><dd>{run.tick}</dd></div>
      <div><dt>Latest tick</dt><dd>{run.latest_tick ?? '—'}</dd></div>
      <div><dt>Protocol</dt><dd>{run.protocol_version}</dd></div>
      <div>
        <dt>Experiment</dt>
        <dd>
          {#if experimental?.has_assignment}
            {experimental.experiment_id ?? 'assigned'}
            <span class="muted">({experimental.membership_source ?? 'membership'})</span>
          {:else}
            none
          {/if}
        </dd>
      </div>
      <div>
        <dt>Lineage</dt>
        <dd>
          {#if branch !== null}
            parent {branch.parent_run_id} @ fork tick {branch.fork_tick}
            <br />
            <span class="muted">{branch.intervention_summary}</span>
            <EpistemicBadge epistemic="counterfactual" />
            <span class="muted"> Research fork</span>
          {:else if run.parent_run_id}
            parent {run.parent_run_id}
            {#if run.fork_tick !== null}
              @ {run.fork_tick}
            {/if}
            {#if run.intervention_summary}
              — {run.intervention_summary}
            {/if}
          {:else}
            root run
            {#if branchReason !== null}
              <span class="muted">({branchReason})</span>
            {/if}
          {/if}
        </dd>
      </div>
    </dl>
  {:else if view === 'agent'}
    <AgentPanel
      {runId}
      agentId={selection.focus?.kind === 'agent' &&
      selection.focus.source === 'objective'
        ? selection.focus.agentId
        : deepLink.agentId}
    />
  {:else if view === 'population'}
    <PopulationPanel {runId} {selection} {onSelectionChange} />
  {:else if view === 'cohorts'}
    <CohortsPanel {runId} {selection} {onSelectionChange} />
  {:else if view === 'lineage'}
    <LineagePanel {runId} {selection} {onSelectionChange} />
  {:else if view === 'teaching'}
    <TeachingPanel {runId} {selection} {onSelectionChange} />
  {:else if view === 'technology'}
    <TechnologyPanel {runId} {selection} {onSelectionChange} />
  {:else if view === 'culture'}
    <CulturePanel {runId} {selection} />
  {:else if view === 'language'}
    <LanguagePanel {runId} {selection} />
  {:else if view === 'narratives'}
    <NarrativePanel {runId} {selection} {onSelectionChange} />
  {:else if view === 'migration'}
    <MigrationPanel {runId} {selection} />
  {:else if view === 'economy'}
    <EconomyPanel {runId} {selection} />
  {:else if view === 'projects'}
    <ProjectsPanel {runId} {selection} />
  {:else if view === 'graphs'}
    <GraphsPanel {runId} agentId={deepLink.agentId} eventId={deepLink.eventId} />
  {:else if view === 'analytics'}
    <AnalyticsPanel {runId} agentId={deepLink.agentId} />
  {:else if view === 'societies'}
    <SocietiesPanel {runId} {selection} />
  {:else if view === 'macro-societies'}
    <MacroSocietiesPanel {runId} {selection} />
  {:else if view === 'organizations'}
    <OrganizationsPanel {runId} {selection} />
  {:else if view === 'formal-rules'}
    <FormalRulesPanel {runId} {selection} />
  {:else if view === 'disputes'}
    <DisputesPanel {runId} {selection} />
  {:else if view === 'evidence'}
    <EvidencePanel {runId} {selection} />
  {:else if view === 'representation'}
    <RepresentationPanel {runId} {selection} />
  {:else if view === 'diplomacy'}
    <DiplomacyPanel {runId} {selection} />
  {:else if view === 'conflict'}
    <OrganizedConflictPanel {runId} {selection} />
  {:else if view === 'borders'}
    <BordersPanel {runId} {selection} />
  {:else if view === 'migration-displacement'}
    <MigrationDisplacementPanel {runId} {selection} />
  {:else if view === 'institutions'}
    <InstitutionsPanel {runId} {selection} {onSelectionChange} />
  {:else if view === 'contact'}
    <ContactPanel {runId} />
  {:else if view === 'traces'}
    <DecisionTracePanel {runId} {deepLink} />
  {:else if view === 'compare'}
    <ObjSubjComparePanel {runId} {deepLink} />
    <ForkComparePanel {runId} {deepLink} />
  {:else if allTabs.some((tab) => tab.id === view)}
    <p class="status empty">
      {view} research evidence is reachable; its populated panel arrives in a later
      implementation task.
    </p>
  {:else}
    <p class="status empty">Unknown view.</p>
  {/if}

  {#if view === 'overview'}
    <GodotEmbed {deepLink} />
  {/if}
</section>

<style>
  .page {
    display: grid;
    gap: 1.1rem;
  }

  .head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .eyebrow {
    margin: 0 0 0.25rem;
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5a6a72;
  }

  h1 {
    margin: 0 0 0.35rem;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    font-size: 1.6rem;
    word-break: break-all;
  }

  .lede {
    margin: 0;
    color: #3a474e;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }

  .actions button,
  .tabs button {
    font: inherit;
    cursor: pointer;
    border: 1px solid rgba(28, 36, 40, 0.22);
    background: rgba(255, 255, 255, 0.55);
    padding: 0.35rem 0.7rem;
  }

  .ghost {
    background: transparent;
  }

  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    border-bottom: 1px solid rgba(28, 36, 40, 0.12);
    padding-bottom: 0.35rem;
  }

  .tab-group {
    display: grid;
    gap: 0.2rem;
  }

  .tab-group-label {
    color: #5a6a72;
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .tab-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .tabs button.active {
    border-color: #2e5c6e;
    color: #2e5c6e;
    font-weight: 600;
  }

  .meta {
    display: grid;
    gap: 0.75rem;
    margin: 0;
  }

  .meta div {
    display: grid;
    grid-template-columns: 8rem 1fr;
    gap: 0.5rem;
  }

  dt {
    margin: 0;
    color: #5a6a72;
    font-size: 0.85rem;
  }

  dd {
    margin: 0;
  }

  .muted {
    color: #5a6a72;
    font-size: 0.9rem;
  }

  .status {
    margin: 0;
  }

  .error {
    color: #8a3030;
  }

  .empty {
    font-style: italic;
    color: #3a474e;
  }
</style>
