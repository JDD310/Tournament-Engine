import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// jsdom doesn't lay pages out, so these check the CSS rules that keep the
// bracket readable on a phone rather than the rendered result.
const css = readFileSync('src/index.css', 'utf8')

function rule(selector, source = css) {
  const match = source.match(new RegExp(`(^|\\n)\\s*${selector.replace('.', '\\.')} \\{([^}]*)\\}`))
  return match?.[2] ?? ''
}

describe('mobile layout', () => {
  it('scrolls the bracket sideways inside its own box', () => {
    expect(rule('.bracket')).toMatch(/overflow-x: auto/)
    expect(rule('.bracket')).toMatch(/max-width: 100%/)
  })

  it('has narrow-screen rules for the page and the bracket', () => {
    const phone = css.match(/@media \(max-width: 30rem\) \{([\s\S]*?)\n\}/)?.[1]
    expect(phone).toBeDefined()
    expect(rule('main', phone)).toMatch(/padding/)
    expect(rule('.bracket-round', phone)).toMatch(/min-width/)
    expect(rule('.bracket-hint', phone)).toMatch(/display: block/)
  })

  it('keeps the viewport at device width', () => {
    expect(readFileSync('index.html', 'utf8')).toMatch(
      /<meta name="viewport" content="width=device-width, initial-scale=1.0" \/>/,
    )
  })
})
