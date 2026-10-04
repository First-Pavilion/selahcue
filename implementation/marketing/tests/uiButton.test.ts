/**
 * What a UiButton looks like, resolved from its own stylesheet (ClickUp 17tnw2b2cev,
 * audit findings shared-chrome-27 to 30).
 *
 * The audit measured the same `size` rendering at 41-47px (sm), 47-50.5px (md) and 51-58px (lg)
 * depending on the parent's line-height, every variant a 999px pill, a gradient fill standing in for
 * the solid primary, a secondary with no border, no white/outlined pair for gradient bands, and a
 * focus ring made only of a box-shadow (which forced-colors mode deletes). Figma draws fixed heights of
 * 39/41/44/47/49, radius 10 (compact, small) and 11 (medium, large), and solid fills.
 *
 * These tests RESOLVE the rules (`fixtures/cssSource.ts`) instead of grepping, so a later rule or a
 * media block cannot make a stale value pass. The pixels themselves are proved in a browser by the
 * harness and the responsive sweep; this names the rule that moved.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { describe } from 'node:test'

import { box, contrast, effective, hexToRgb, parseCss, px, rootProperties, styleOf, type Env } from './fixtures/cssSource.ts'

const src = readFileSync(new URL('../src/components/UiButton.vue', import.meta.url), 'utf8')
const rules = parseCss(styleOf(src))
const DESKTOP: Env = { width: 1440 }

const SIZES = ['compact', 'sm', 'md', 'lg'] as const

function look(size: string, variant: string, env: Env = DESKTOP, pseudo: string | null = null) {
  return effective(rules, ['ui-button', `variant-${variant}`, `size-${size}`], env, pseudo)
}

/** Painted height of a single-line button: border-box, so padding + line box + border, both sides. */
function height(size: string, variant: string): number {
  const d = look(size, variant)
  const [top, , bottom] = box(d['padding'])
  const border = px((d['border'] ?? '').split(/\s+/)[0])
  return top + bottom + px(d['line-height']) + 2 * border
}

describe('fixed heights that do not follow the parent', () => {
  test('every size resolves to the Figma height for the solid primary: 39, 41, 44, 49', () => {
    assert.deepEqual(
      SIZES.map((s) => height(s, 'primary')),
      [39, 41, 44, 49],
    )
  })

  test('large bordered / quiet variants are 47 (Figma: hero secondary, band outline), large solid ones 49', () => {
    for (const v of ['secondary', 'outline', 'ghost', 'inverse-outline']) assert.equal(height('lg', v), 47, v)
    for (const v of ['primary', 'inverse', 'gradient']) assert.equal(height('lg', v), 49, v)
  })

  test('the height is the same in every variant of a size (a solid and an outlined button line up)', () => {
    for (const s of ['compact', 'sm', 'md']) {
      const heights = ['primary', 'secondary', 'ghost', 'outline', 'inverse', 'inverse-outline', 'gradient'].map((v) => height(s, v))
      assert.ok(heights.every(Number.isFinite), `${s}: a height could not be resolved (${heights.join(', ')})`)
      assert.equal(new Set(heights).size, 1, `${s}: ${heights.join(', ')}`)
    }
  })

  test('the line box is a px length on every size, so the parent line-height cannot change it', () => {
    for (const s of SIZES) {
      const lh = look(s, 'primary')['line-height']
      assert.ok(Number.isFinite(px(lh)), `${s} line-height is ${lh}, must be a px length (inherit / normal / a bare number follow the parent)`)
    }
  })

  test('every variant has a border box (a transparent border keeps solid and outlined buttons the same height)', () => {
    for (const v of ['primary', 'secondary', 'ghost', 'outline', 'inverse', 'inverse-outline', 'gradient']) {
      assert.match(look('md', v)['border'] ?? '', /^1px solid\b/, v)
    }
  })

  test('control: the arithmetic bites. A size with a taller padding is reported as the wrong height', () => {
    const tampered = parseCss(styleOf(src).replace(/(\.size-md\s*\{[^}]*padding:\s*)\d+px/, '$118px'))
    const d = effective(tampered, ['ui-button', 'variant-primary', 'size-md'], DESKTOP)
    const [top, , bottom] = box(d['padding'])
    assert.notEqual(top + bottom + px(d['line-height']) + 2, 44, 'the height check could not tell a changed padding from the real one')
  })
})

describe('radius and weight follow the Figma button census', () => {
  test('compact and small are 10px, medium and large are 11px; none is a pill', () => {
    assert.deepEqual(
      SIZES.map((s) => look(s, 'primary')['border-radius']),
      ['10px', '10px', '11px', '11px'],
    )
    assert.doesNotMatch(src.replace(/\/\*[\s\S]*?\*\//g, ''), /--pill-radius|999px/, 'a pill belongs to toggles and badges, not buttons')
  })

  test('the nav CTA size and the large primary are Bold (700), the rest Semi Bold (600)', () => {
    assert.equal(look('compact', 'primary')['font-weight'], '700')
    assert.equal(look('lg', 'primary')['font-weight'], '700')
    assert.equal(look('lg', 'inverse')['font-weight'], '700')
    for (const s of ['sm', 'md']) assert.equal(look(s, 'primary')['font-weight'], '600', s)
    assert.equal(look('lg', 'secondary')['font-weight'], '600')
  })

  test('label sizes are 14 / 14 / 15 / 15.5', () => {
    assert.deepEqual(
      SIZES.map((s) => look(s, 'primary')['font-size']),
      ['14px', '14px', '15px', '15.5px'],
    )
  })
})

describe('variants', () => {
  const declared = /validator:\s*\(val: string\)\s*=>\s*\[([^\]]*)\]\.includes\(val\)/.exec(src)
  const variants = [...(declared?.[1] ?? '').matchAll(/'([^']+)'/g)].map((m) => m[1])

  test('the variant set is primary, secondary, ghost, outline, inverse, inverse-outline, plus gradient kept as an alias', () => {
    assert.deepEqual(
      [...variants].sort(),
      ['gradient', 'ghost', 'inverse', 'inverse-outline', 'outline', 'primary', 'secondary'].sort(),
    )
  })

  test('size accepts compact, sm, md, lg', () => {
    const sizes = /size:\s*\{[^}]*validator:\s*\(val: string\)\s*=>\s*\[([^\]]*)\]/.exec(src)
    assert.deepEqual([...(sizes?.[1] ?? '').matchAll(/'([^']+)'/g)].map((m) => m[1]), ['compact', 'sm', 'md', 'lg'])
  })

  test('primary is the solid brand fill with a white label', () => {
    const d = look('md', 'primary')
    assert.equal(d['background'], 'var(--sc-primary)')
    assert.match(d['color'] ?? '', /^(#fff|#ffffff|white)$/i)
  })

  test('gradient renders the SAME solid fill as primary: Figma draws no gradient button', () => {
    const grad = look('lg', 'gradient')
    assert.equal(grad['background'], look('lg', 'primary')['background'])
    assert.doesNotMatch(JSON.stringify(grad), /gradient/)
  })

  test('secondary is the elevated fill WITH a 1px border; outline is transparent with the same border', () => {
    const secondary = look('md', 'secondary')
    assert.equal(secondary['background'], 'var(--sc-elevated)')
    assert.equal(secondary['border-color'], 'var(--sc-border)')
    const outline = look('md', 'outline')
    assert.equal(outline['background'], 'transparent')
    assert.equal(outline['border-color'], 'var(--sc-border)')
  })

  test('the white / outlined pair for gradient bands exists: inverse is a white fill in the brand ink, inverse-outline a 1px half-white border', () => {
    const inverse = look('lg', 'inverse')
    assert.match(inverse['background'] ?? '', /^(#fff|#ffffff|white)$/i)
    assert.equal(inverse['color'], 'var(--sc-primary)')
    const outline = look('lg', 'inverse-outline')
    assert.equal(outline['background'], 'transparent')
    assert.match(outline['border-color'] ?? '', /rgba\(255,\s*255,\s*255,\s*0?\.5\)/)
    assert.match(outline['color'] ?? '', /^(#fff|#ffffff|white)$/i)
  })

  test('every declared variant has a rule (a variant name with no style would render unstyled)', () => {
    for (const v of variants) {
      const d = look('md', v as string)
      assert.ok(d['background'] !== undefined && d['color'] !== undefined, `variant-${v} sets no background or no colour`)
    }
  })

  test('a block button fills its container (the pricing cards pass `block`, which used to do nothing)', () => {
    assert.match(src, /block:\s*\{\s*type:\s*Boolean/)
    assert.equal(effective(rules, ['ui-button', 'is-block'], DESKTOP)['width'], '100%')
    assert.match(src, /'is-block':\s*block/)
  })
})

describe('the focus ring survives forced-colors (Windows High Contrast)', () => {
  test('keyboard focus draws an OUTLINE, which forced-colors keeps, not only a box-shadow, which it removes', () => {
    const d = look('md', 'primary', DESKTOP, 'focus-visible')
    assert.match(d['outline'] ?? '', /^2px solid\b/, `focus-visible outline is "${d['outline']}"`)
    assert.ok(px(d['outline-offset']) >= 2, 'a 2px offset keeps the ring off the fill')
  })

  test('nothing switches the outline off: no `outline: none` on the button, in any state or environment', () => {
    const everything = rules.map((r) => `${r.selectors.join(',')}{${Object.entries(r.decls).map(([k, v]) => `${k}:${v}`).join(';')}}`).join('\n')
    assert.doesNotMatch(everything, /outline\s*:\s*(none|0)\b/)
    for (const env of [DESKTOP, { width: 1440, forcedColors: true }, { width: 375, pointer: 'coarse' as const }]) {
      const d = look('md', 'primary', env, 'focus-visible')
      assert.match(d['outline'] ?? '', /solid/, JSON.stringify(env))
    }
  })

  test('the ring appears AT ONCE: the transition names its properties, so the outline is never animated (transition: all flashed a white 3px ring first)', () => {
    const transition = effective(rules, ['ui-button'], DESKTOP)['transition'] ?? ''
    assert.ok(transition !== '', 'the button has no transition rule at all')
    const properties = transition.split(/,(?![^(]*\))/).map((part) => part.trim().split(/\s+/)[0] ?? '')
    assert.ok(!properties.includes('all'), `transition: ${transition}`)
    assert.ok(!properties.some((name) => name.startsWith('outline')), `the outline is transitioned: ${transition}`)
    for (const wanted of ['background-color', 'box-shadow', 'transform']) assert.ok(properties.includes(wanted), `${wanted} no longer eases: ${transition}`)
  })

  test('control: `transition: all` would be caught', () => {
    const tampered = parseCss(styleOf(src).replace(/transition:\s*background-color[^;]*;/, 'transition: all var(--transition-fast);'))
    assert.match(effective(tampered, ['ui-button'], DESKTOP)['transition'] ?? '', /^all\b/)
  })

  test('on a white or half-white band button the ring is white, so it can be seen on the gradient', () => {
    for (const v of ['inverse', 'inverse-outline']) {
      assert.equal(effective(rules, ['ui-button', `variant-${v}`], DESKTOP, 'focus-visible')['outline-color'], '#fff', v)
    }
  })

  test('control: a ring made only of box-shadow would be caught', () => {
    const shadowOnly = parseCss(
      styleOf(src).replace(/\.ui-button:focus-visible\s*\{[^}]*\}/, '.ui-button:focus-visible { box-shadow: 0 0 0 2px #000, 0 0 0 4px #fff; }'),
    )
    const d = effective(shadowOnly, ['ui-button'], DESKTOP, 'focus-visible')
    assert.doesNotMatch(d['outline'] ?? '', /^2px solid/, 'the outline check could not tell a shadow-only ring from a real one')
  })
})

describe('every label is readable on its fill (small text: 4.5:1)', () => {
  const tokenRules = [
    ...parseCss(readFileSync(new URL('../src/assets/styles/tokens.css', import.meta.url), 'utf8')),
    ...parseCss(readFileSync(new URL('../src/assets/styles/main.css', import.meta.url), 'utf8')),
  ]
  const tokens = rootProperties(tokenRules, DESKTOP)
  /** `var(--sc-x)` -> its hex; `#fff` / `white` -> #ffffff. */
  const hex = (value: string | undefined): string => {
    const v = (value ?? '').trim()
    const m = /^var\((--[\w-]+)\)$/.exec(v)
    if (m) return hex(tokens[m[1] ?? ''])
    if (/^(#fff|white)$/i.test(v)) return '#ffffff'
    if (/^#[0-9a-f]{6}$/i.test(v)) return v
    throw new Error(`cannot resolve ${value} to a colour`)
  }
  /** `rgba(0, 0, 0, 0.2)` laid over `under`, as #rrggbb. */
  const over = (rgba: string, under: string): string => {
    const m = /rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)/.exec(rgba)
    assert.ok(m, rgba)
    const [r, g, b] = hexToRgb(under)
    const a = Number.parseFloat(m?.[4] ?? '1')
    const mix = (top: string | undefined, bottom: number) => Math.round(Number.parseInt(top ?? '0', 10) * a + bottom * (1 - a))
    return '#' + [mix(m?.[1], r), mix(m?.[2], g), mix(m?.[3], b)].map((c) => c.toString(16).padStart(2, '0')).join('')
  }

  test('at rest, in every variant, on the surfaces it is used on', () => {
    const pairs: [string, string, string][] = [
      ['primary', hex(look('md', 'primary')['color']), hex(look('md', 'primary')['background'])],
      ['gradient (alias)', hex(look('md', 'gradient')['color']), hex(look('md', 'gradient')['background'])],
      ['secondary', hex(look('md', 'secondary')['color']), hex(look('md', 'secondary')['background'])],
      ['ghost on the page', hex(look('md', 'ghost')['color']), hex(tokens['--sc-base'])],
      ['ghost on a panel', hex(look('md', 'ghost')['color']), hex(tokens['--sc-surface'])],
      ['outline on the page', hex(look('md', 'outline')['color']), hex(tokens['--sc-base'])],
      ['outline on a panel', hex(look('md', 'outline')['color']), hex(tokens['--sc-surface'])],
      ['inverse (brand ink on white)', hex(look('lg', 'inverse')['color']), hex(look('lg', 'inverse')['background'])],
      // the band's lightest gradient stop is --sc-primary itself (--gradient-cta starts there)
      ['inverse-outline on the lightest band stop', hex(look('lg', 'inverse-outline')['color']), hex(tokens['--sc-primary'])],
    ]
    for (const [what, ink, fill] of pairs) {
      assert.ok(contrast(ink, fill) >= 4.5, `${what}: ${ink} on ${fill} is ${contrast(ink, fill).toFixed(2)}:1`)
    }
  })

  test('on hover: the ones that change colour keep 4.5:1, and the ones that would not are not colour changes', () => {
    const hover = (v: string) => look('md', v, DESKTOP, 'hover')
    assert.ok(contrast(hex(look('md', 'secondary')['color']), hex(hover('secondary')['background'])) >= 4.5, 'secondary')
    assert.ok(contrast(hex(look('md', 'ghost')['color']), hex(hover('ghost')['background'])) >= 4.5, 'ghost')
    assert.ok(contrast(hex(look('md', 'outline')['color']), hex(hover('outline')['background'])) >= 4.5, 'outline')
    // white over the band darkened by the hover wash: never lower than at rest
    const washed = over(hover('inverse-outline')['background'] ?? '', hex(tokens['--sc-primary']))
    assert.ok(contrast('#ffffff', washed) >= contrast('#ffffff', hex(tokens['--sc-primary'])), 'inverse-outline')
    // inverse and gradient hover with a shadow only, so the label contrast cannot move
    for (const v of ['inverse', 'gradient']) assert.equal(hover(v)['background'], undefined, `${v} hover must not change the fill`)
    // NOT asserted: the primary hover (--sc-primary-hover, 3.78:1 with the white label). Its direction is
    // held for Uma (shared-chrome-31); this file keeps the value it had.
  })

  test('control: the check bites. White on the old Design 2.0 muted ink is caught', () => {
    assert.ok(contrast('#ffffff', '#9aa4b2') < 4.5)
  })
})

describe('what did not change', () => {
  test('the 44px touch floor on phones and coarse pointers is still there (hit area, not painted size)', () => {
    assert.equal(effective(rules, ['ui-button'], { width: 375 })['min-height'], '44px')
    assert.equal(effective(rules, ['ui-button'], { width: 1440, pointer: 'coarse' })['min-height'], '44px')
    assert.equal(effective(rules, ['ui-button'], DESKTOP)['min-height'], undefined, 'a fine pointer at desktop keeps the designed heights')
  })

  test('hover colours are untouched: primary still goes to --sc-primary-hover (decision shared-chrome-31 is Uma\'s)', () => {
    assert.equal(look('md', 'primary', DESKTOP, 'hover')['background'], 'var(--sc-primary-hover)')
  })

  test('disabled still dims and ignores the pointer', () => {
    const d = effective(rules, ['ui-button', 'is-disabled'], DESKTOP)
    assert.equal(d['opacity'], '0.5')
    assert.equal(d['pointer-events'], 'none')
  })

  test('the public props are unchanged: variant, size, to, href, disabled, loading (plus block)', () => {
    for (const prop of ['variant', 'size', 'to', 'href', 'disabled', 'loading']) assert.match(src, new RegExp(`\\n  ${prop}:\\s*\\{`))
  })
})
