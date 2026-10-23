# Agent Context Budget

Apply these rules to repository exploration, especially `aif-plan` and
`aif-implement`.

## Excluded context

Do not read, search inside, or recursively list these paths (at any depth):

- Environments and dependencies: `.venv/`, `venv/`, `.uv/`, `node_modules/`.
- Lockfiles: `uv.lock` (use `pyproject.toml` for dependency intent).
- Caches: `__pycache__/`, `.cache/`, `.pytest_cache/`, `.mypy_cache/`,
  `.ruff_cache/`, `.hypothesis/`, `.grimp_cache/`, `.import_linter_cache/`,
  `.tox/`, `.nox/`, `.godot/`.
- Generated output: `build/`, `dist/`, `htmlcov/`, `docs/_build/`,
  `*.egg-info/`, `.coverage`, `.coverage.*`, `coverage.xml`, `*.pyc`, `*.pyo`.
- Tool internals: `.git/`, `.idea/`.

Do not bypass these exclusions through shell commands, scripts, or other tools.
Running tools that use these paths internally is allowed: for example,
`uv run`, `uv sync --locked`, tests, linters, builds, and Git commands.
Dependency changes may regenerate `uv.lock` with `uv`; do not dump its contents
or full diff into context.

Only inspect an excluded artifact when the user explicitly requests it and the
agent's permissions permit it. Keep any such inspection narrowly scoped.

## Focused exploration

- Start with the task, applicable project rules, and required AI Factory context.
  Read `.ai-factory/config.yaml`, `DESCRIPTION.md`, `ARCHITECTURE.md`, and the
  active plan as required by the invoked skill.
- Scope searches to relevant first-party paths: `src/`, `tests/`, `alembic/`,
  `clients/`, `scripts/`, and relevant `docs/` pages. Use filename discovery,
  then targeted content searches and bounded reads.
- Avoid repository-wide recursive listings, unrestricted searches, and full-file
  dumps when a symbol search or a relevant section is sufficient. Respect Git
  ignore rules; do not use unfiltered hidden/ignored-file searches.
- Load only the invoked skill and references needed for the current task.
  Do not scan the duplicate skill installations in `.agents/skills/`,
  `.codex/skills/`, and `.cursor/skills/` as application code.
- Discover plan filenames before reading the active plan. Read historical plans,
  archives, patches, and references only when required by the skill or task.
- Reuse information already in context. Summarize command results; request more
  output only when needed to diagnose a failure.
- Treat tests, documentation, migrations, and infrastructure as task-specific
  context, not default bulk context:
  - Find relevant tests by filename or symbol; read only the cases and fixtures
    needed for the change. Keep test coverage enabled.
  - Read only relevant documentation sections; do not preload `docs/` or the
    entire README for unrelated implementation tasks.
  - Inspect `alembic/versions/` only for migration work, schema history, or a
    relevant regression. Models alone do not describe migration dependencies.
  - Read Docker/Compose files, launch scripts, `.github/`, and `.python-version`
    only for relevant runtime, packaging, CI, or development-environment tasks.
  - Do not scan `scripts/` or assistant configuration directories by default;
    load a specific script, skill, or configuration only when needed.
- Keep required `.ai-factory/` rules, project context, and the active plan
  accessible. Do not exclude useful first-party files through `.gitignore` or
  blanket read denials just to reduce context.
- Keep tool output bounded: request matching filenames or short excerpts first,
  use targeted Git diffs, and summarize test/linter output. If output is
  truncated, narrow the request rather than dumping the full result.

OpenCode enforces direct-read exclusions in `opencode.json`. These instructions
also cover searches and shell access; they are behavioral rules for other agents.

## AI Context Files

| Path | Description |
| --- | --- |
| `.ai-factory/ARCHITECTURE.md` | Bounded-package architecture, trust boundaries, and versioned extension rules |

## Documentation

| Document | Path | Description |
| --- | --- | --- |
| README | `README.md` | Project landing page and complete documentation index |
| Architecture | `docs/architecture.md` | Authority boundaries and regional migration contract |
| Experiments | `docs/experiments.md` | AY treatments, reproduction, and demographic interpretation |
| Cultural metrics | `docs/cultural-evolution-metrics.md` | Opt-in capture, six families, seed-block intervals, provenance limits |
| Observer | `docs/observer.md` | Read-only region and journey presentation |
| Physical simulation | `docs/physical-simulation.md` | Discrete journeys, fatigue, capacity, and death |
| Configuration | `docs/configuration.md` | Exact regional specification and optional capability gates |
| Development | `docs/development.md` | Verification commands and pinned Godot suite |
