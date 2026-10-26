/**
 * Bounded JSON decoder for nested research metric rows.
 *
 * `JSON.parse` silently keeps the last duplicate key, so this parser validates
 * duplicate keys, depth, byte size and finite numbers before returning data.
 * Cancellation is checked at entry and after parsing.
 */

export const MAX_RESEARCH_JSON_BYTES = 16 * 1024 * 1024
export const MAX_RESEARCH_JSON_DEPTH = 32

export class ResearchJsonError extends Error {
  readonly code: string

  constructor(code: string) {
    super(code)
    this.name = 'ResearchJsonError'
    this.code = code
  }
}

export type BoundedJsonOptions = {
  maxBytes?: number
  maxDepth?: number
  signal?: AbortSignal | undefined
}

class Parser {
  private index = 0

  constructor(
    private readonly text: string,
    private readonly maxDepth: number,
    private readonly signal: AbortSignal | undefined,
  ) {}

  parse(): unknown {
    const value = this.value(0)
    this.skipWhitespace()
    if (this.index !== this.text.length) {
      throw new ResearchJsonError('invalid_trailing_content')
    }
    return value
  }

  private checkAbort(): void {
    if (this.signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }
  }

  private skipWhitespace(): void {
    while (this.index < this.text.length) {
      const char = this.text[this.index]
      if (char === ' ' || char === '\t' || char === '\n' || char === '\r') {
        this.index += 1
      } else {
        break
      }
    }
  }

  private value(depth: number): unknown {
    this.checkAbort()
    if (depth > this.maxDepth) {
      throw new ResearchJsonError('excessive_depth')
    }
    this.skipWhitespace()
    const char = this.text[this.index]
    if (char === undefined) {
      throw new ResearchJsonError('invalid_json')
    }
    if (char === '{') {
      return this.object(depth + 1)
    }
    if (char === '[') {
      return this.array(depth + 1)
    }
    if (char === '"') {
      return this.string()
    }
    if (char === '-' || (char >= '0' && char <= '9')) {
      return this.number()
    }
    if (this.text.startsWith('true', this.index)) {
      this.index += 4
      return true
    }
    if (this.text.startsWith('false', this.index)) {
      this.index += 5
      return false
    }
    if (this.text.startsWith('null', this.index)) {
      this.index += 4
      return null
    }
    throw new ResearchJsonError('invalid_json')
  }

  private object(depth: number): Record<string, unknown> {
    this.index += 1
    const result: Record<string, unknown> = {}
    this.skipWhitespace()
    if (this.text[this.index] === '}') {
      this.index += 1
      return result
    }
    while (true) {
      this.checkAbort()
      this.skipWhitespace()
      if (this.text[this.index] !== '"') {
        throw new ResearchJsonError('invalid_json')
      }
      const key = this.string()
      if (Object.prototype.hasOwnProperty.call(result, key)) {
        throw new ResearchJsonError('duplicate_key')
      }
      this.skipWhitespace()
      if (this.text[this.index] !== ':') {
        throw new ResearchJsonError('invalid_json')
      }
      this.index += 1
      result[key] = this.value(depth)
      this.skipWhitespace()
      const char = this.text[this.index]
      if (char === ',') {
        this.index += 1
        continue
      }
      if (char === '}') {
        this.index += 1
        return result
      }
      throw new ResearchJsonError('invalid_json')
    }
  }

  private array(depth: number): unknown[] {
    this.index += 1
    const result: unknown[] = []
    this.skipWhitespace()
    if (this.text[this.index] === ']') {
      this.index += 1
      return result
    }
    while (true) {
      result.push(this.value(depth))
      this.skipWhitespace()
      const char = this.text[this.index]
      if (char === ',') {
        this.index += 1
        continue
      }
      if (char === ']') {
        this.index += 1
        return result
      }
      throw new ResearchJsonError('invalid_json')
    }
  }

  private string(): string {
    this.index += 1
    let result = ''
    while (this.index < this.text.length) {
      const char = this.text[this.index]
      this.index += 1
      if (char === '"') {
        return result
      }
      if (char === '\\') {
        const escape = this.text[this.index]
        this.index += 1
        switch (escape) {
          case '"':
          case '\\':
          case '/':
            result += escape
            break
          case 'b':
            result += '\b'
            break
          case 'f':
            result += '\f'
            break
          case 'n':
            result += '\n'
            break
          case 'r':
            result += '\r'
            break
          case 't':
            result += '\t'
            break
          case 'u': {
            const hex = this.text.slice(this.index, this.index + 4)
            if (!/^[0-9a-fA-F]{4}$/.test(hex)) {
              throw new ResearchJsonError('invalid_json')
            }
            result += String.fromCharCode(Number.parseInt(hex, 16))
            this.index += 4
            break
          }
          default:
            throw new ResearchJsonError('invalid_json')
        }
        continue
      }
      if (char === undefined) {
        throw new ResearchJsonError('invalid_json')
      }
      const code = char.charCodeAt(0)
      if (code < 0x20) {
        throw new ResearchJsonError('invalid_json')
      }
      result += char
    }
    throw new ResearchJsonError('invalid_json')
  }

  private number(): number {
    const match = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(
      this.text.slice(this.index),
    )
    if (match === null) {
      throw new ResearchJsonError('invalid_json')
    }
    const raw = match[0]
    this.index += raw.length
    const value = Number(raw)
    if (!Number.isFinite(value)) {
      throw new ResearchJsonError('nonfinite_number')
    }
    return value
  }
}

export function parseBoundedJson(
  text: string,
  options: BoundedJsonOptions = {},
): unknown {
  if (options.signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError')
  }
  const maxBytes = options.maxBytes ?? MAX_RESEARCH_JSON_BYTES
  const encoded = new TextEncoder().encode(text)
  if (encoded.byteLength > maxBytes) {
    throw new ResearchJsonError('rows_json_too_large')
  }
  const value = new Parser(
    text,
    options.maxDepth ?? MAX_RESEARCH_JSON_DEPTH,
    options.signal,
  ).parse()
  if (options.signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError')
  }
  return value
}

function isScalar(value: unknown): boolean {
  return (
    value === null ||
    typeof value === 'string' ||
    typeof value === 'boolean' ||
    (typeof value === 'number' && Number.isFinite(value))
  )
}

export function decodeRowsJson(
  raw: string,
  options: BoundedJsonOptions = {},
): ReadonlyArray<Record<string, unknown>> {
  const value = parseBoundedJson(raw, options)
  if (!Array.isArray(value)) {
    throw new ResearchJsonError('invalid_rows_json')
  }
  const rows: Record<string, unknown>[] = []
  for (const row of value) {
    if (row === null || typeof row !== 'object' || Array.isArray(row)) {
      throw new ResearchJsonError('invalid_rows_json')
    }
    for (const item of Object.values(row)) {
      if (isScalar(item)) {
        continue
      }
      if (Array.isArray(item) && item.every(isScalar)) {
        continue
      }
      throw new ResearchJsonError('invalid_rows_json')
    }
    rows.push(row as Record<string, unknown>)
  }
  return rows
}
