# Research UI

Researcher-oriented V2 web UI for Palimpsest analysis and debugging
(complementary to the Godot world observer).

**Stack:** Svelte + Vite + TypeScript (strict). No world canvas / WebGL map.
Graph libraries (e.g. Cytoscape.js) are added when research graphs land.

## Build

```bash
pnpm install
pnpm build
```

Artifacts land in `dist/`. Point the API at them with:

```bash
export PALIMPSEST_RESEARCH_WEB_ROOT=/absolute/path/to/clients/research-ui/dist
```

The API serves the SPA at `/research/` (HTML5 history fallback). Godot keeps `/`.

## Scripts

| Script | Purpose |
| --- | --- |
| `pnpm dev` | Vite dev server |
| `pnpm build` | Production build → `dist/` (+ `research_ui_build_ok` log) |
| `pnpm check` / `pnpm lint` | `svelte-check` + `tsc` |
| `pnpm test` | Vitest unit tests |

## Responsibility

Owns run list, matrices, graphs, subjective ledgers, metrics, fork compare,
decision traces, and deep links. Does **not** own authoritative world rendering
or tick mutation.
