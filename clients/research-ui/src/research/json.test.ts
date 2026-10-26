import { describe, expect, it } from 'vitest'
import {
  ResearchJsonError,
  decodeRowsJson,
  parseBoundedJson,
} from './json'

describe('bounded research json', () => {
  it('parses escaped keys and strings', () => {
    const value = parseBoundedJson('{"a\\u002db":"line\\nbreak","emoji":"\\ud83d\\ude00"}')
    expect(value).toEqual({ 'a-b': 'line\nbreak', emoji: '😀' })
  })

  it('rejects duplicate keys at any depth', () => {
    expect(() => parseBoundedJson('{"a":1,"a":2}')).toThrow(ResearchJsonError)
    expect(() => parseBoundedJson('{"outer":{"a":1,"a":2}}')).toThrow(
      ResearchJsonError,
    )
    try {
      parseBoundedJson('{"a":1,"a":2}')
    } catch (err) {
      expect((err as ResearchJsonError).code).toBe('duplicate_key')
    }
  })

  it('rejects nonfinite numbers and trailing content', () => {
    expect(() => parseBoundedJson('[NaN]')).toThrow(ResearchJsonError)
    expect(() => parseBoundedJson('[1e999]')).toThrow(ResearchJsonError)
    expect(() => parseBoundedJson('{} extra')).toThrow(ResearchJsonError)
  })

  it('enforces byte and depth limits', () => {
    expect(() =>
      parseBoundedJson('{"a":1}', { maxBytes: 2 }),
    ).toThrow(ResearchJsonError)
    expect(() =>
      parseBoundedJson('{"a":{"b":{"c":1}}}', { maxDepth: 1 }),
    ).toThrow(ResearchJsonError)
  })

  it('checks cancellation before and after decode', () => {
    const controller = new AbortController()
    controller.abort()
    expect(() => parseBoundedJson('[]', { signal: controller.signal })).toThrow(
      DOMException,
    )
  })

  it('decodes scalar rows and rejects nested row values', () => {
    const rows = decodeRowsJson('[{"value":1,"tags":["a","b"],"ready":true}]')
    expect(rows).toHaveLength(1)
    expect(() => decodeRowsJson('[{"value":{"nested":1}}]')).toThrow(
      ResearchJsonError,
    )
  })
})
