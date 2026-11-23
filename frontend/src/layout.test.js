import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// A smoke test only. jsdom doesn't lay pages out, so this checks that the CSS
// rules which keep the bracket readable on a phone are still there. The real
// layout check is loading the page in headless Chrome at 360px and 400px wide.
const css = readFileSync('src/index.css', 'utf8')

// Parse with jsdom's own CSS parser (the test environment), so formatting,
// comments and nested @media blocks don't matter.
function parse(source) {
  const style = document.createElement('style')
  style.textContent = source
  document.head.append(style)
  const rules = [...style.sheet.cssRules]
  style.remove()
  return rules
}

// The value `property` ends up with for `selector`: the last declaration wins,
// so a later rule overriding an earlier one is taken into account. `media`
// limits the search to rules inside an @media block with that condition.
function declared(selector, property, { media = null, source = css } = {}) {
  let value = ''
  const visit = (rules, inMedia) => {
    for (const rule of rules) {
      if (rule.media) {
        visit(rule.cssRules, rule.media.mediaText)
      } else if (
        inMedia === media &&
        rule.selectorText?.split(',').some((s) => s.trim() === selector)
      ) {
        value = rule.style.getPropertyValue(property) || value
      }
    }
  }
  visit(parse(source), null)
  return value
}

const PHONE = { media: '(max-width: 30rem)' }

describe('mobile layout (smoke test)', () => {
  it('scrolls the bracket sideways inside its own box', () => {
    expect(declared('.bracket', 'overflow-x')).toBe('auto')
    expect(declared('.bracket', 'max-width')).toBe('100%')
  })

  it('has narrow-screen rules for the page and the bracket', () => {
    expect(declared('main', 'padding', PHONE)).not.toBe('')
    expect(declared('.bracket-round', 'min-width', PHONE)).not.toBe('')
    expect(declared('.bracket-hint', 'display', PHONE)).toBe('block')
  })

  it("doesn't depend on how the CSS is formatted", () => {
    const squashed = css.replace(/\s+/g, ' ').replace(/\s*([{};:])\s*/g, '$1')
    expect(declared('.bracket', 'overflow-x', { source: squashed })).toBe('auto')
    expect(declared('.bracket-hint', 'display', { ...PHONE, source: squashed })).toBe('block')
  })

  it('sees a later rule that overrides an earlier one', () => {
    const overridden = `${css}\n.bracket { overflow-x: hidden; }`
    expect(declared('.bracket', 'overflow-x', { source: overridden })).toBe('hidden')
  })

  it('keeps the viewport at device width', () => {
    expect(readFileSync('index.html', 'utf8')).toMatch(
      /<meta name="viewport" content="width=device-width, initial-scale=1.0" \/>/,
    )
  })
})
