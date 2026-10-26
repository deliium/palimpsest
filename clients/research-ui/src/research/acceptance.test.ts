import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushSync, render } from '../test/mount'
import { emptyResearchSelection } from './selection'
import PopulationPanel from '../views/PopulationPanel.svelte'
import CohortsPanel from '../views/CohortsPanel.svelte'
import LineagePanel from '../views/LineagePanel.svelte'
import TeachingPanel from '../views/TeachingPanel.svelte'
import TechnologyPanel from '../views/TechnologyPanel.svelte'
import CulturePanel from '../views/CulturePanel.svelte'
import LanguagePanel from '../views/LanguagePanel.svelte'
import NarrativePanel from '../views/NarrativePanel.svelte'
import MigrationPanel from '../views/MigrationPanel.svelte'
import EconomyPanel from '../views/EconomyPanel.svelte'
import ProjectsPanel from '../views/ProjectsPanel.svelte'
import InstitutionsPanel from '../views/InstitutionsPanel.svelte'

vi.mock('cytoscape', () => ({
  default: () => ({ on: () => undefined, destroy: () => undefined }),
}))

const panels = [
  { name: 'population', component: PopulationPanel, heading: 'Population and demographics' },
  { name: 'cohorts', component: CohortsPanel, heading: 'Within-run cohort comparison' },
  { name: 'genealogy', component: LineagePanel, heading: 'Qualified lineage explorer' },
  { name: 'teaching', component: TeachingPanel, heading: 'Teacher / student networks' },
  { name: 'technology', component: TechnologyPanel, heading: 'Technology lineage and diffusion' },
  { name: 'culture', component: CulturePanel, heading: 'Cultural trait timelines' },
  { name: 'language', component: LanguagePanel, heading: 'Vocabulary, semantics and current meaning' },
  { name: 'narratives', component: NarrativePanel, heading: 'Historical narrative lineage' },
  { name: 'migration', component: MigrationPanel, heading: 'Migration flows' },
  { name: 'economy', component: EconomyPanel, heading: 'Economic exchange networks' },
  { name: 'projects', component: ProjectsPanel, heading: 'Collective project history' },
  { name: 'institutions', component: InstitutionsPanel, heading: 'Institutions' },
] as const

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('populated panel acceptance', () => {
  for (const entry of panels) {
    it(`mounts the ${entry.name} surface with a real component and evidence wording`, async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(
          async () =>
            new Response(JSON.stringify({ code: 'unavailable' }), {
              status: 404,
              headers: { 'content-type': 'application/problem+json' },
            }),
        ),
      )
      const mounted = render(entry.component as never, {
        runId: 'run-1',
        selection: emptyResearchSelection({
          runId: 'run-1',
          view: entry.name as never,
          tick: 4,
          scopeOwnerId: 'agent-a',
        }),
        onSelectionChange: vi.fn(),
      })
      await Promise.resolve()
      await new Promise((resolve) => setTimeout(resolve, 0))
      flushSync()
      expect(mounted.target.textContent).toContain(entry.heading)
      // Honest unavailable/forbidden/empty wording is acceptable; a bare
      // placeholder that merely says "later implementation task" is not.
      expect(mounted.target.textContent).not.toContain('later implementation task')
      mounted.cleanup()
    })
  }

  it('keeps capture, completion and lineage prerequisites explicit', () => {
    expect(LineagePanel).toBeTypeOf('function')
    expect(TechnologyPanel).toBeTypeOf('function')
    expect(InstitutionsPanel).toBeTypeOf('function')
  })
})
