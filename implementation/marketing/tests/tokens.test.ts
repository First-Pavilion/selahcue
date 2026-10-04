/**
 * The design tokens the shared chrome and every page are built on (ClickUp 17tnw2b2cev, audit
 * findings shared-chrome-21 to 25 and pricing-25).
 *
 * Four things were wrong, and each is pinned here so it cannot drift back:
 *  - a custom property was USED and never DEFINED (`--sc-surface-alt`, `--sc-success`), so the rule
 *    silently fell back (white check marks; a band with no fill). `undefinedProperties` fails the
 *    build on the next one, whoever adds it;
 *  - `--sc-text-muted` was 3.79:1 on the surface and 3.45:1 on the elevated surface, below AA for small
 *    text on every surface it is used on, with 40+ consumers;
 *  - the content width and gutters the pages render (1140px at x=150) were not the ones Figma draws
 *    (1248px at x=96, 96/48/20px gutters), and there were three overlapping section-padding tokens;
 *  - the navbar height token was 68px against a real 69px bar, and Figma draws 79.
 *
 * Values are RESOLVED from the stylesheets (`fixtures/cssSource.ts`), media blocks included, so a later
 * override cannot make a stale value pass. The browser run (harness) is the proof of the pixels.
 */
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { contrast, effective, luminance, parseCss, resolvePx, rootProperties, stripComments, type Env } from './fixtures/cssSource.ts'

const SRC = fileURLToPath(new URL('../src/', import.meta.url))
const read = (relative: string) => readFileSync(join(SRC, relative), 'utf8')

const walk = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => (statSync(join(dir, name)).isDirectory() ? walk(join(dir, name)) : [join(dir, name)]))

const tokensCss = read('assets/styles/tokens.css')
const mainCss = read('assets/styles/main.css')
const rules = [...parseCss(tokensCss), ...parseCss(mainCss)]

const DESKTOP: Env = { width: 1440 }
const TABLET: Env = { width: 1024 }
const MOBILE: Env = { width: 375 }
const props = (env: Env) => rootProperties(rules, env)

/**
 * Custom properties that are used with no fallback and are not defined WHERE THEY ARE USED.
 *
 * "Where used" is, in order of reach:
 *  - GLOBAL: declared (`--x:`) in any file under `assets/styles/` (the design tokens and the shared
 *    stylesheets every page loads), or set from script (the name as a string literal: `setProperty('--x', ...)`,
 *    `:style="{ '--x': v }"`), which this cannot place and so treats as global;
 *  - LOCAL: declared anywhere in the SAME file (a component's own `--mark-size`, `--nav-cta-hover`).
 * A property declared only in ANOTHER component does not count: `var(--nav-cta-hover)` used from `Footer.vue`
 * resolves to nothing in a browser, because it is declared on one of Navbar's elements only. (Review of PR
 * 172: the first version of this guard asked "defined somewhere in src/", and that mistake passed it.)
 *
 * The limit that remains, stated rather than hidden: it does not prove that the DECLARING ELEMENT is an
 * ancestor of the using one inside a file (a custom property inherits down the tree, not sideways), so a
 * variable declared on one element and used on its sibling in the same file still passes. A use WITH a
 * fallback (`var(--x, 68px)`) is allowed to be undefined: that is what the fallback is for.
 */
export function undefinedProperties(files: Readonly<Record<string, string>>): string[] {
  const clean = (raw: string) => stripComments(raw).replace(/<!--[\s\S]*?-->/g, '')
  const isGlobalSheet = (path: string) => path.startsWith('assets/styles/')
  const global = new Set<string>()
  const local = new Map<string, Set<string>>()
  for (const [path, raw] of Object.entries(files)) {
    const text = clean(raw)
    const mine = new Set<string>()
    for (const m of text.matchAll(/(--[\w-]+)\s*:/g)) (isGlobalSheet(path) ? global : mine).add(m[1] ?? '')
    for (const m of text.matchAll(/['"](--[\w-]+)['"]/g)) global.add(m[1] ?? '')
    local.set(path, mine)
  }
  const problems: string[] = []
  for (const [path, raw] of Object.entries(files)) {
    const seen = new Set<string>()
    for (const m of clean(raw).matchAll(/var\(\s*(--[\w-]+)\s*\)/g)) {
      const name = m[1] ?? ''
      if (seen.has(name) || global.has(name) || local.get(path)?.has(name)) continue
      seen.add(name)
      problems.push(`${name} (used in ${path}, defined nowhere that reaches it)`)
    }
  }
  return problems
}

describe('every custom property that is used is defined', () => {
  test('nothing in src/ uses a var(--x) that no file defines', () => {
    const files: Record<string, string> = {}
    for (const f of walk(SRC).filter((p) => /\.(vue|css|ts)$/.test(p))) files[f.slice(SRC.length)] = readFileSync(f, 'utf8')
    assert.deepEqual(undefinedProperties(files), [])
  })

  test('--sc-surface-alt and --sc-success, used today and defined nowhere, are defined', () => {
    const p = props(DESKTOP)
    assert.ok(p['--sc-surface-alt'], '--sc-surface-alt (the Download requirements band) is undefined')
    assert.ok(p['--sc-success'], '--sc-success (the Pricing check marks) is undefined')
  })

  describe('the guard itself (checked on in-memory files)', () => {
    test('an undefined use is reported with the file that uses it', () => {
      assert.deepEqual(undefinedProperties({ 'assets/styles/a.css': ':root { --a: 1px; } .x { margin: var(--a); color: var(--nope); }' }), [
        '--nope (used in assets/styles/a.css, defined nowhere that reaches it)',
      ])
    })

    test('a definition in a shared stylesheet counts everywhere; a fallback is allowed; a JS-set property counts', () => {
      assert.deepEqual(undefinedProperties({ 'views/A.vue': '<style>.x { color: var(--b); }</style>', 'assets/styles/tokens.css': ':root { --b: red; }' }), [])
      assert.deepEqual(undefinedProperties({ 'views/A.vue': '<style>.x { top: var(--n, 68px); }</style>' }), [])
      assert.deepEqual(undefinedProperties({ 'views/A.vue': '<style>.x { top: var(--live); }</style>', 'lib/a.ts': "el.style.setProperty('--live', '1px')" }), [])
    })

    test('a definition in the SAME component counts, in ANOTHER component does not: var(--nav-cta-hover) from the footer fails', () => {
      const navbar = '<style scoped>.download-cta { --nav-cta-hover: #4f5ec7; } .download-cta:hover { background: var(--nav-cta-hover); }</style>'
      assert.deepEqual(undefinedProperties({ 'components/Navbar.vue': navbar }), [])
      assert.deepEqual(undefinedProperties({ 'components/Navbar.vue': navbar, 'components/Footer.vue': '<style scoped>.link:hover { color: var(--nav-cta-hover); }</style>' }), [
        '--nav-cta-hover (used in components/Footer.vue, defined nowhere that reaches it)',
      ])
    })

    test('the stated limit holds: a sibling in the same file is not told apart from a descendant (documented, not hidden)', () => {
      assert.deepEqual(undefinedProperties({ 'components/A.vue': '<style>.a { --k: 1px; } .b { top: var(--k); }</style>' }), [])
    })

    test('a use that only appears in a comment is ignored', () => {
      assert.deepEqual(undefinedProperties({ 'assets/styles/a.css': '/* color: var(--ghost); */ .x { color: red; }' }), [])
    })
  })
})

describe('muted text is readable (shared-chrome-21, pricing-25)', () => {
  const p = props(DESKTOP)
  const muted = p['--sc-text-muted'] ?? ''

  test('--sc-text-muted clears 4.5:1 on every surface text sits on', () => {
    for (const surface of ['--sc-base', '--sc-inset', '--sc-surface', '--sc-elevated']) {
      const ratio = contrast(muted, p[surface] ?? '')
      assert.ok(ratio >= 4.5, `${muted} on ${surface} ${p[surface]} is ${ratio.toFixed(2)}:1, below AA for small text`)
    }
  })

  test('it is still quieter than the secondary ink, so the three-step hierarchy survives', () => {
    const surface = p['--sc-surface'] ?? ''
    assert.ok(contrast(muted, surface) < contrast(p['--sc-text-secondary'] ?? '', surface))
    assert.ok(contrast(p['--sc-text-secondary'] ?? '', surface) < contrast(p['--sc-text'] ?? '', surface))
  })

  test('the Figma-mapped inks the chrome uses (text, secondary) pass on the page colour', () => {
    for (const ink of ['--sc-text', '--sc-text-secondary']) assert.ok(contrast(p[ink] ?? '', p['--sc-base'] ?? '') >= 7, ink)
  })

  test('control: the old muted value is caught by this check', () => {
    assert.ok(contrast('#6b7383', p['--sc-surface'] ?? '') < 4.5, 'the ratio function cannot tell 3.79:1 from a pass')
  })
})

describe('one content width, three gutters, one container (shared-chrome-22)', () => {
  test('the content width is the 1248px Figma draws, not the 1140 / 1200 / 1240 the pages invented', () => {
    assert.equal(props(DESKTOP)['--content-max'], '1248px')
  })

  test('gutters are 96px on desktop, 48px on tablet and 20px on mobile', () => {
    assert.deepEqual(
      [DESKTOP, TABLET, MOBILE].map((env) => props(env)['--gutter']),
      ['96px', '48px', '20px'],
    )
  })

  test('the shared .container is the content width plus both gutters, centred, padded by the gutter', () => {
    const d = effective(rules, ['container'], DESKTOP)
    assert.equal(d['margin-inline'], 'auto')
    assert.equal(d['padding-inline'], 'var(--gutter)')
    assert.equal(resolvePx(d['max-width'] ?? '', props(DESKTOP)), 1248 + 2 * 96, 'at 1440 the container is the frame, so content runs 96..1344')
    assert.equal(resolvePx(d['max-width'] ?? '', props(TABLET)), 1248 + 2 * 48)
  })

  test('the navbar gutter is a token too: 48px on desktop (Figma), 24px on tablet, 20px on mobile', () => {
    assert.deepEqual(
      [DESKTOP, TABLET, MOBILE].map((env) => props(env)['--nav-gutter']),
      ['48px', '24px', '20px'],
    )
  })
})

describe('section padding (shared-chrome-23)', () => {
  test('the desktop section padding is 88px, the handoff value, and steps down on tablet and mobile', () => {
    assert.deepEqual(
      [DESKTOP, TABLET, MOBILE].map((env) => props(env)['--section-pad']),
      ['88px', '72px', '56px'],
    )
  })

  test('the third overlapping token, --section-padding, is gone, and .section uses the one that remains', () => {
    assert.equal(props(DESKTOP)['--section-padding'], undefined)
    assert.equal(effective(rules, ['section'], DESKTOP)['padding-block'], 'var(--section-pad)')
  })
})

describe('the type ramp can be consumed (shared-chrome-24)', () => {
  test('sub-page heroes have a token: 52/58 Bold, stepping down with the viewport', () => {
    assert.equal(props(DESKTOP)['--font-h1-page'], '700 52px/58px var(--font-family)')
    assert.notEqual(props(TABLET)['--font-h1-page'], props(DESKTOP)['--font-h1-page'])
    assert.notEqual(props(MOBILE)['--font-h1-page'], props(TABLET)['--font-h1-page'])
  })

  test('headings are weight 700 in the ramp, and the eyebrow carries its 0.3px tracking', () => {
    const p = props(DESKTOP)
    for (const heading of ['--font-h1', '--font-h2', '--font-h1-page']) assert.match(p[heading] ?? '', /^700 /, heading)
    assert.equal(p['--letter-spacing-eyebrow'], '0.3px')
    assert.equal(effective(rules, ['font-eyebrow'], DESKTOP)['letter-spacing'], 'var(--letter-spacing-eyebrow)')
    assert.equal(effective(rules, ['font-h1-page'], DESKTOP)['font'], 'var(--font-h1-page)')
  })
})

describe('the primary button hover fill is AA (reset-r2-04)', () => {
  const p = props(DESKTOP)

  test('--sc-primary-hover-fill is darker than the rest fill and holds the white label at 4.5:1 (the old hover was 3.78:1)', () => {
    const fill = p['--sc-primary-hover-fill'] ?? ''
    assert.match(fill, /^#[0-9a-f]{6}$/i)
    assert.ok(contrast('#ffffff', fill) >= 4.5, `${fill} is ${contrast('#ffffff', fill).toFixed(2)}:1 with white`)
    assert.ok(luminance(fill) < luminance(p['--sc-primary'] ?? ''), 'must be darker than --sc-primary')
    assert.ok(contrast('#ffffff', p['--sc-primary-hover'] ?? '') < 4.5, 'control: the old hover really was below AA')
  })

  test('the platform --sc-primary-hover (link ink on dark surfaces, 14 consumers) is unchanged', () => {
    assert.equal(p['--sc-primary-hover'], '#7e6eff')
  })
})

describe('the navbar height token is the real bar (shared-chrome-01)', () => {
  test('79px from 768px up, where Figma draws the bar with its links; 69px on the phone bar', () => {
    assert.deepEqual(
      [DESKTOP, { width: 1024 }, { width: 768 }, { width: 767 }, MOBILE].map((env) => props(env)['--nav-height']),
      ['79px', '79px', '79px', '69px', '69px'],
    )
  })
})

describe('brand ink is spelled once (shared-chrome-25)', () => {
  test('the CTA gradient is derived from the brand token, not a fourth indigo', () => {
    assert.match(props(DESKTOP)['--gradient-cta'] ?? '', /var\(--sc-primary\)/)
    assert.doesNotMatch(props(DESKTOP)['--gradient-cta'] ?? '', /#5b6bd6/i)
  })
})
