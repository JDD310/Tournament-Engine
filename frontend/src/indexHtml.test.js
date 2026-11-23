import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('index.html', () => {
  it('keeps the organizer token out of cross-origin Referer headers', () => {
    const doc = new DOMParser().parseFromString(readFileSync('index.html', 'utf8'), 'text/html')

    expect(doc.querySelector('meta[name="referrer"]')?.getAttribute('content')).toBe('same-origin')
  })
})
