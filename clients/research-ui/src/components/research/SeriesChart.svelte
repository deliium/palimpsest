<script lang="ts">
  import { EPISTEMIC_LABELS, type EpistemicClass } from '../../epistemic'

  export type SeriesPoint = {
    tick: number
    value: number | null
    generationIndex?: number | null
  }

  export type ChartSeries = {
    id: string
    label: string
    evidenceClass: EpistemicClass
    ownerId: string | null
    unit: string
    points: SeriesPoint[]
    coverage: number | null
    sourceRef: string | null
  }

  interface Props {
    title: string
    description: string
    series: ChartSeries[]
    onPointSelect?: (tick: number) => void
    height?: number
  }

  let { title, description, series, onPointSelect, height = 220 }: Props = $props()

  const patterns = ['', '6 3', '2 3', '10 4 2 4']

  function ticks(): number[] {
    const values = new Set<number>()
    for (const item of series) {
      for (const point of item.points) {
        values.add(point.tick)
      }
    }
    return [...values].sort((left, right) => left - right)
  }

  function allValues(): number[] {
    return series.flatMap((item) =>
      item.points
        .map((point) => point.value)
        .filter((value): value is number => value !== null && Number.isFinite(value)),
    )
  }

  function x(tick: number): number {
    const axis = ticks()
    if (axis.length <= 1) {
      return 320
    }
    const min = axis[0] ?? 0
    const max = axis[axis.length - 1] ?? min
    return 40 + ((tick - min) / Math.max(1, max - min)) * 560
  }

  function y(value: number): number {
    const values = allValues()
    const min = values.length === 0 ? 0 : Math.min(...values)
    const max = values.length === 0 ? 1 : Math.max(...values)
    if (max === min) {
      return height - 30
    }
    return 20 + (1 - (value - min) / (max - min)) * (height - 50)
  }

  function segments(points: SeriesPoint[]): SeriesPoint[][] {
    const result: SeriesPoint[][] = []
    let current: SeriesPoint[] = []
    for (const point of [...points].sort((left, right) => left.tick - right.tick)) {
      if (point.value === null || !Number.isFinite(point.value)) {
        if (current.length > 0) {
          result.push(current)
          current = []
        }
        continue
      }
      current.push(point)
    }
    if (current.length > 0) {
      result.push(current)
    }
    return result
  }

  function pathFor(points: SeriesPoint[]): string {
    return points
      .map((point, index) => {
        const command = index === 0 ? 'M' : 'L'
        return `${command}${x(point.tick).toFixed(2)},${y(point.value ?? 0).toFixed(2)}`
      })
      .join(' ')
  }

  function select(point: SeriesPoint): void {
    if (point.value === null) {
      return
    }
    onPointSelect?.(point.tick)
  }
</script>

<figure class="chart">
  <figcaption>
    <strong>{title}</strong>
    <span>{description}</span>
  </figcaption>
  <svg
    role="img"
    aria-label={title}
    viewBox={`0 0 640 ${height}`}
    preserveAspectRatio="none"
  >
    <line x1="40" y1={height - 30} x2="600" y2={height - 30} class="axis" />
    <line x1="40" y1="20" x2="40" y2={height - 30} class="axis" />
    {#each series as item, seriesIndex (item.id)}
      {#each segments(item.points) as segment, segmentIndex (segmentIndex)}
        {@const path = pathFor(segment)}
        {#if path !== ''}
          <path
            d={path}
            fill="none"
            class="series"
            stroke-dasharray={patterns[seriesIndex % patterns.length]}
          />
        {/if}
      {/each}
      {#each item.points as point (point.tick)}
        {#if point.value !== null}
          <circle
            cx={x(point.tick)}
            cy={y(point.value)}
            r="4"
            tabindex="0"
            role="button"
            aria-label={`${item.label} at tick ${point.tick}: ${point.value} ${item.unit}`}
            onclick={() => select(point)}
            onkeydown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                select(point)
              }
            }}
          />
        {/if}
      {/each}
    {/each}
    {#each ticks() as tick (tick)}
      <text x={x(tick)} y={height - 12} text-anchor="middle" class="axis-label">
        {tick}
      </text>
    {/each}
  </svg>
  <ul class="legend">
    {#each series as item (item.id)}
      <li>
        <span class="swatch" aria-hidden="true"></span>
        <span>{item.label}</span>
        <span class="muted">
          {EPISTEMIC_LABELS[item.evidenceClass]}
          {#if item.ownerId} · owner {item.ownerId}{/if}
          {#if item.unit} · {item.unit}{/if}
          {#if item.coverage !== null} · coverage {(item.coverage * 100).toFixed(0)}%{/if}
        </span>
      </li>
    {/each}
  </ul>
  <table>
    <caption>{title} data</caption>
    <thead>
      <tr>
        <th scope="col">Tick</th>
        {#each series as item (item.id)}
          <th scope="col">{item.label} ({item.unit})</th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each ticks() as tick (tick)}
        <tr>
          <th scope="row">{tick}</th>
          {#each series as item (item.id)}
            <td>
              {item.points.find((point) => point.tick === tick)?.value ?? '—'}
            </td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
</figure>

<style>
  .chart {
    margin: 0;
    display: grid;
    gap: 0.5rem;
  }

  figcaption {
    display: grid;
    gap: 0.15rem;
  }

  svg {
    width: 100%;
    height: 14rem;
    background: rgba(255, 255, 255, 0.35);
  }

  .axis {
    stroke: rgba(28, 36, 40, 0.35);
    stroke-width: 1;
  }

  .axis-label {
    font-size: 0.6rem;
    fill: #3a474e;
  }

  .series {
    stroke: #2e5c6e;
    stroke-width: 2;
  }

  circle {
    fill: #2e5c6e;
    cursor: pointer;
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 0.85rem;
  }

  .legend li {
    display: flex;
    gap: 0.35rem;
    align-items: center;
  }

  .swatch {
    width: 1rem;
    height: 0.2rem;
    background: #2e5c6e;
  }

  .muted {
    color: #5a6a72;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }

  th,
  td {
    border-bottom: 1px solid rgba(28, 36, 40, 0.12);
    padding: 0.25rem 0.4rem;
    text-align: left;
  }
</style>
