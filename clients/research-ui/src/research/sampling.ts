/** Bounded history sampling and marker high-water pinning. */

export type SamplingMarker = {
  generationIndex: number
  seekTick: number
}

export type SamplingRange = {
  fromTick: number
  toTick: number
}

export type SamplingResult = {
  ticks: number[]
  sampled: boolean
  omittedCount: number
  range: SamplingRange
}

export function pinHighWater(run: {
  tick: number
  latest_tick: number | null
}): number {
  const latest = run.latest_tick
  return latest !== null && latest >= run.tick ? latest : run.tick
}

export function defaultSamplingRange(selectedTick: number): SamplingRange {
  return { fromTick: selectedTick, toTick: selectedTick }
}

export function sampleBoundaries(
  markers: readonly SamplingMarker[],
  range: SamplingRange,
  maxSamples = 32,
): SamplingResult {
  const from = Math.min(range.fromTick, range.toTick)
  const to = Math.max(range.fromTick, range.toTick)
  if (!Number.isSafeInteger(maxSamples) || maxSamples < 2) {
    throw new Error('invalid_max_samples')
  }
  const candidates = new Set<number>([from, to])
  for (const marker of markers) {
    if (
      Number.isSafeInteger(marker.seekTick) &&
      marker.seekTick >= from &&
      marker.seekTick <= to
    ) {
      candidates.add(marker.seekTick)
    }
  }
  const ordered = [...candidates].sort((left, right) => left - right)
  if (ordered.length <= maxSamples) {
    return {
      ticks: ordered,
      sampled: false,
      omittedCount: 0,
      range: { fromTick: from, toTick: to },
    }
  }
  const picked = new Set<number>([from, to])
  const slots = maxSamples - 2
  for (let index = 0; index < slots; index += 1) {
    const position = Math.round(((index + 1) * (ordered.length - 1)) / (slots + 1))
    picked.add(ordered[position] ?? from)
  }
  const ticks = [...picked].sort((left, right) => left - right).slice(0, maxSamples)
  return {
    ticks,
    sampled: true,
    omittedCount: ordered.length - ticks.length,
    range: { fromTick: from, toTick: to },
  }
}

export type MarkerHighWaterState = {
  runId: string
  highWater: number
  revision: number
  credentialGeneration: number
}

/**
 * Marker discovery is pinned to finalized high-water H.
 * View time never lowers H; only an explicit refresh may advance it.
 */
export class MarkerHighWater {
  private state: MarkerHighWaterState | null = null

  observe(
    runId: string,
    run: { tick: number; latest_tick: number | null },
    revision: number,
    credentialGeneration: number,
  ): { changed: boolean; highWater: number } {
    if (
      this.state === null ||
      this.state.runId !== runId ||
      this.state.revision !== revision ||
      this.state.credentialGeneration !== credentialGeneration
    ) {
      this.state = {
        runId,
        highWater: pinHighWater(run),
        revision,
        credentialGeneration,
      }
      return { changed: true, highWater: this.state.highWater }
    }
    return { changed: false, highWater: this.state.highWater }
  }

  refresh(
    runId: string,
    run: { tick: number; latest_tick: number | null },
    revision: number,
    credentialGeneration: number,
  ): { changed: boolean; highWater: number } {
    const next = pinHighWater(run)
    const changed =
      this.state === null ||
      this.state.runId !== runId ||
      this.state.highWater !== next ||
      this.state.revision !== revision ||
      this.state.credentialGeneration !== credentialGeneration
    this.state = {
      runId,
      highWater: next,
      revision,
      credentialGeneration,
    }
    return { changed, highWater: next }
  }

  acceptsContinuation(cursorHighWater: number): boolean {
    return this.state !== null && cursorHighWater === this.state.highWater
  }

  get highWater(): number | null {
    return this.state?.highWater ?? null
  }

  get cacheKey(): string | null {
    if (this.state === null) {
      return null
    }
    return [
      this.state.runId,
      this.state.highWater,
      this.state.revision,
      this.state.credentialGeneration,
    ].join(':')
  }
}
