/**
 * The three global rules in `main.css` that carry shared-chrome behaviour and that no other test could see
 * break (code review of PR 172, finding 1): the brand mark's crop, the keyboard-focus default and the
 * scroll margin of the "How it works" target. Each was mutated (ratio changed, rule wrapped in an
 * unreachable `@media`, rule deleted) and left every earlier test green, because they were checked, if at
 * all, by a regex on the source text. These RESOLVE the rule (`effectiveExact` honours the media block it
 * sits in) and compare it with something that is not in the stylesheet: the logo file's own alpha box, the
 * Figma reference frame, and the anchor token.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { describe } from 'node:test'

import { effectiveExact, mediaMatches, parseCss, resolvePx, rootProperties, type Env } from './fixtures/cssSource.ts'
import { alphaBox, decodePng, inkBox } from './fixtures/png.ts'

const read = (url: string) => readFileSync(new URL(url, import.meta.url), 'utf8')
const bytes = (url: string) => new Uint8Array(readFileSync(new URL(url, import.meta.url)))

const mainCss = read('../src/assets/styles/main.css')
const rules = [
  ...parseCss(read('../src/assets/styles/tokens.css')),
  ...parseCss(mainCss),
  ...parseCss(read('../src/assets/styles/anchors.css')),
]
const DESKTOP: Env = { width: 1440 }
const MOBILE: Env = { width: 375 }
/** Every environment a visitor can be in: no width, pointer, motion or forced-colors setting may switch a global rule off. */
const ENVS: Env[] = [
  { width: 320 },
  MOBILE,
  { width: 768 },
  { width: 1024 },
  DESKTOP,
  { width: 1440, pointer: 'coarse' },
  { width: 1440, forcedColors: true },
  { width: 1440, reducedMotion: true },
]

describe('the brand mark crop (shared-chrome-03)', () => {
  const logo = decodePng(bytes('../public/selahcue-logo.png'))
  const art = alphaBox(logo)
  const artHeight = art.y1 - art.y0

  /**
   * How much of the box the artwork's height fills. Figma draws its mark with some air round it: the ink of
   * the nav mark measures 26 x 28 in a 32px box, the footer's 22 x 24 in a 28px one (both re-measured below
   * from the committed reference frame, not taken on trust). 0.875 is the nav's 28/32; the footer's 24/28 is
   * 0.857, 0.5px apart at that size.
   */
  const INK_FRACTION = 0.875

  const css = effectiveExact(rules, '.brand-mark img', DESKTOP)
  const ratio = (value: string | undefined) => {
    const m = /^calc\(var\(--mark-size, 32px\) \* (-?\d+(?:\.\d+)?)\)$/.exec(value ?? '')
    assert.ok(m, `not calc(var(--mark-size, 32px) * N): ${value}`)
    return Number.parseFloat(m?.[1] ?? '')
  }

  test('the logo file is the one the crop was cut for: 1254 x 1254 with its artwork at 760 x 835', () => {
    assert.deepEqual([logo.width, logo.height], [1254, 1254])
    assert.deepEqual([art.x0, art.y0, art.x1, art.y1], [247, 215, 1007, 1050])
  })

  test('the crop ratios centre the artwork and size it to the Figma fraction of the box, derived from the file\'s own alpha box', () => {
    const scale = INK_FRACTION / artHeight // box-sizes per source pixel
    const expected = {
      width: logo.width * scale,
      height: logo.height * scale,
      left: 0.5 - ((art.x0 + art.x1) / 2) * scale,
      top: 0.5 - ((art.y0 + art.y1) / 2) * scale,
    }
    assert.ok(Math.abs(ratio(css['width']) - expected.width) < 0.002, `width ${ratio(css['width'])} vs ${expected.width}`)
    assert.ok(Math.abs(ratio(css['height']) - expected.height) < 0.002, `height ${ratio(css['height'])} vs ${expected.height}`)
    assert.ok(Math.abs(ratio(css['left']) - expected.left) < 0.002, `left ${ratio(css['left'])} vs ${expected.left}`)
    assert.ok(Math.abs(ratio(css['top']) - expected.top) < 0.002, `top ${ratio(css['top'])} vs ${expected.top}`)
    assert.equal(css['position'], 'absolute')
    assert.equal(css['max-width'], 'none', 'the global img max-width would squash the oversized image back into the box')
  })

  test('the window is a square of --mark-size, 32px unless a component says otherwise, and hides the rest of the file', () => {
    const box = effectiveExact(rules, '.brand-mark', DESKTOP)
    assert.equal(box['width'], 'var(--mark-size, 32px)')
    assert.equal(box['height'], 'var(--mark-size, 32px)')
    assert.equal(box['overflow'], 'hidden')
    assert.equal(box['flex-shrink'], '0')
  })

  test('the resulting ink matches the Figma reference frame: nav 28px tall at 32, footer 24px at 28 (within 1px), centred in the box', () => {
    const home = decodePng(bytes('../../../docs/design/visual-parity/marketing/reference/home.png'))
    const nav = inkBox(home, { x0: 40, y0: 16, x1: 84, y1: 64 })
    const footer = inkBox(home, { x0: 90, y0: 6500, x1: 130, y1: 6548 })
    const built = (size: number) => ({ w: ((art.x1 - art.x0) * INK_FRACTION * size) / artHeight, h: INK_FRACTION * size })
    assert.ok(Math.abs(built(32).h - (nav.y1 - nav.y0)) <= 1, `nav ink: build ${built(32).h}px vs Figma ${nav.y1 - nav.y0}px`)
    assert.ok(Math.abs(built(32).w - (nav.x1 - nav.x0)) <= 1.5, `nav ink width: build ${built(32).w}px vs Figma ${nav.x1 - nav.x0}px`)
    assert.ok(Math.abs(built(28).h - (footer.y1 - footer.y0)) <= 1, `footer ink: build ${built(28).h}px vs Figma ${footer.y1 - footer.y0}px`)
    // centred: the Figma ink sits in the middle of its 32px box (x 48..80)
    assert.ok(Math.abs((nav.x0 + nav.x1) / 2 - 64) <= 1, 'Figma nav mark is not centred where the build centres it')
  })

  test('control: the guard bites. A crop at ratio 1 (artwork the full height of the box) is more than 1px off the Figma ink', () => {
    assert.ok(Math.abs(1 * 32 - 28) > 1)
    const tamperedWidth = 1 * logo.width * (1 / artHeight)
    assert.ok(Math.abs(tamperedWidth - ratio(css['width'])) > 0.002)
  })
})

describe('the keyboard focus default (shared-chrome-08)', () => {
  const SELECTOR = ":where(a, button, summary, [role='button'], [tabindex='0']):focus-visible"

  test('a 2px brand ring with a 2px offset, in EVERY environment: no media block switches it off', () => {
    for (const env of ENVS) {
      const d = effectiveExact(rules, SELECTOR, env)
      assert.equal(d['outline'], '2px solid var(--sc-primary)', JSON.stringify(env))
      assert.equal(d['outline-offset'], '2px', JSON.stringify(env))
    }
  })

  test('it is written at ZERO specificity (:where), so any component rule wins and nothing needs !important', () => {
    assert.ok(mainCss.includes(':where(a, button, summary'), 'the default must stay inside :where()')
    assert.doesNotMatch(mainCss.slice(mainCss.indexOf(':where(a, button')), /^[^}]*!important/)
  })

  test('form fields are not in it: they draw their own focus state', () => {
    assert.doesNotMatch(SELECTOR, /input|select|textarea/)
    const declared = rules.filter((r) => r.selectors.some((s) => s.startsWith(':where(a, button')))
    assert.equal(declared.length, 1)
    assert.ok(declared[0]?.selectors.every((s) => !/input|select|textarea/.test(s)))
  })

  test('control: a rule that can never apply reads as absent (the guard sees an unreachable @media)', () => {
    const wrapped = parseCss(`@media (min-width: 99999px) { ${SELECTOR} { outline: 2px solid var(--sc-primary); outline-offset: 2px; } }`)
    assert.deepEqual(effectiveExact(wrapped, SELECTOR, DESKTOP), {})
    assert.equal(mediaMatches('(min-width: 99999px)', DESKTOP), false)
  })
})

describe('the How it works target clears the sticky bar on a cold load (shared-chrome-07)', () => {
  test('the target carries scroll-margin-top from the anchor offset token', () => {
    for (const env of ENVS) assert.equal(effectiveExact(rules, '#how-it-works', env)['scroll-margin-top'], 'var(--sc-anchor-offset)', JSON.stringify(env))
  })

  test('and that token resolves to the real bar plus the gap: 95px beside the 79px bar, 85px beside the 69px phone bar', () => {
    const offset = (env: Env) => resolvePx('var(--sc-anchor-offset)', rootProperties(rules, env))
    assert.deepEqual([DESKTOP, { width: 1024 }, { width: 768 }, MOBILE].map(offset), [95, 95, 95, 85])
  })

  test('control: a deleted rule reads as absent', () => {
    const without = rules.filter((r) => !r.selectors.includes('#how-it-works'))
    assert.deepEqual(effectiveExact(without, '#how-it-works', DESKTOP), {})
  })
})
