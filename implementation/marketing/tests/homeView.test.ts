/**
 * The Home page against Figma frame 468:125 and the audit's findings for it (ClickUp 17tnw2b2cex).
 *
 * Two kinds of check, both without a browser:
 *
 *   1. RENDER checks. Vite compiles the real `HomeView.vue` and its components, Vue renders them to a
 *      string, and `fixtures/renderPage.ts` reads the string as a tree. What is asked of the tree is
 *      structural (what is a heading, what assistive technology can read, which control is disabled),
 *      never "this markup string contains that substring".
 *   2. SOURCE checks over the six files this ticket owns, read with Vue's SFC parser and the chrome
 *      tests' CSS reader: no literal colour that is not a token or a documented Figma literal, no
 *      `!important`, no local container, the layout numbers the audit measured.
 *
 * What neither can see (computed geometry, real focus order, real scroll) is measured in a real
 * browser by `home_page_headless.py` beside this file and by the visual-parity harness.
 *
 * EVERY PREDICATE HAS ONE DEFINITION and its positive control consumes THAT definition: a check that
 * does not fail on a planted fault is a decoration, so each group ends with the fault planted.
 *
 * The copy ledger below is the contract's, line by line. Where Figma overclaims, the ledger keeps the
 * backed part only; the FORBIDDEN list is the claims this page may not make (owner decision: honest content
 * wins). The claims the live page used to make (the price, the plan tiers, "cancel anytime", the testimonials, the platform
 * versions) were removed by ClickUp 17tnw2b0x3h: `LIVE_CLAIMS` is empty, and FORBIDDEN bans each of them from coming back.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test, { after, before, describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { parse } from 'vue/compiler-sfc'

import { effective, effectiveExact, parseCss, px, resolvePx, rootProperties, styleOf, contrast } from './fixtures/cssSource.ts'
import {
  type El,
  type RenderServer,
  ancestors,
  findAll,
  hasClass,
  parseHtml,
  startRenderServer,
  textOf,
  walk,
} from './fixtures/renderPage.ts'

const ROOT = fileURLToPath(new URL('../', import.meta.url))
const SRC = path.join(ROOT, 'src')
const read = (rel: string): string => readFileSync(path.join(SRC, rel), 'utf8')

const FILES = [
  'views/HomeView.vue',
  'components/ConsoleMockup.vue',
  'components/OutputManagerMockup.vue',
  'components/FeatureCard.vue',
  'components/ReliabilityPillar.vue',
  'components/home/HomeIcon.vue',
] as const

let server: RenderServer
let page: El

before(async () => {
  server = await startRenderServer()
  page = parseHtml(await server.render('views/HomeView.vue'))
})

after(async () => {
  await server?.close()
})

// --------------------------------------------------------------------------- predicates

/** Every problem with the heading outline of a tree. Empty when sound. */
function headingProblems(root: El): string[] {
  const out: string[] = []
  const hs = findAll(root, (e) => /^h[1-6]$/.test(e.tag))
  const h1s = hs.filter((h) => h.tag === 'h1')
  if (h1s.length !== 1) out.push(`expected exactly one h1, found ${h1s.length}`)
  let prev = 0
  for (const h of hs) {
    const level = Number(h.tag.slice(1))
    if (prev === 0 && level !== 1) out.push(`the outline starts at ${h.tag} "${textOf(h)}"`)
    if (prev !== 0 && level > prev + 1) out.push(`${h.tag} "${textOf(h)}" follows an h${prev}: a level is skipped`)
    prev = level
  }
  return out
}

/** A text glyph used as an icon: emoji, dingbat ticks, the status dot, the play triangle. */
const GLYPH = /[\p{Extended_Pictographic}✓✔●▶✨]/u

function glyphProblems(root: El): string[] {
  const out: string[] = []
  const bad = textOf(root).match(new RegExp(GLYPH.source, 'gu'))
  if (bad) out.push(`text glyph(s) used as icons: ${[...new Set(bad)].join(' ')}`)
  return out
}

/** An inline SVG that assistive technology would announce. */
function svgProblems(root: El): string[] {
  return findAll(root, (e) => e.tag === 'svg')
    .filter((s) => s.attrs['aria-hidden'] !== 'true')
    .map((s) => `an svg (viewBox ${s.attrs['viewBox'] ?? '?'}) is not aria-hidden`)
}

/** Every control that does nothing and does not say so. */
function controlProblems(root: El): string[] {
  const out: string[] = []
  const ids = new Map<string, El>()
  walk(root, (e) => {
    if (e.attrs['id']) ids.set(e.attrs['id'], e)
  })
  for (const a of findAll(root, (e) => e.tag === 'a')) {
    const href = a.attrs['href']
    const label = textOf(a)
    if (href === undefined) {
      if (a.attrs['aria-disabled'] !== 'true') out.push(`link "${label}" has no destination and is not marked disabled`)
      continue
    }
    if (href === '' || href === '#' || /^javascript:/i.test(href)) out.push(`link "${label}" goes nowhere (href="${href}")`)
  }
  for (const b of findAll(root, (e) => e.tag === 'button')) {
    const label = textOf(b)
    const disabled = b.attrs['disabled'] !== undefined
    if (!disabled) {
      if (b.attrs['aria-expanded'] === undefined) out.push(`button "${label}" is enabled and is not a disclosure: nothing is attached to it`)
      continue
    }
    const ref = b.attrs['aria-describedby']
    const note = ref ? ids.get(ref) : undefined
    if (!note || textOf(note) === '') out.push(`disabled button "${label}" does not point at a visible or spoken reason (aria-describedby="${ref ?? ''}")`)
  }
  return out
}

/** `#fragment` links whose element does not exist on the page. */
function fragmentProblems(root: El, extraTargets: readonly string[] = []): string[] {
  const ids = new Set<string>()
  walk(root, (e) => {
    if (e.attrs['id']) ids.add(e.attrs['id'])
  })
  const wanted = new Set<string>(extraTargets)
  for (const a of findAll(root, (e) => e.tag === 'a')) {
    const href = a.attrs['href']
    if (href?.startsWith('#') && href.length > 1) wanted.add(href.slice(1))
  }
  return [...wanted].filter((id) => !ids.has(id)).map((id) => `#${id} points at nothing on this page`)
}

const section = (root: El, cls: string): El => {
  const found = findAll(root, (e) => e.tag === 'section' && hasClass(e, cls))
  assert.equal(found.length, 1, `exactly one <section class="${cls}">, found ${found.length}`)
  return found[0] as El
}

// --------------------------------------------------------------------------- the structure

const SECTION_ORDER = [
  'hero-section',
  'features-section',
  'reliability-section',
  'outputs-section',
  'steps-section',
  'pricing-section',
  'faq-section',
  'final-cta-section',
] as const

describe('the page is the eight designed sections, in Figma\'s order (the testimonials section is gone: ClickUp 17tnw2b0x3h), on the shared container', () => {
  test('eight sections, in order, each inside the shared .container (the local container rule is gone)', () => {
    const sections = findAll(page, (e) => e.tag === 'section')
    assert.deepEqual(
      sections.map((s) => (s.attrs['class'] ?? '').split(/\s+/)[0]),
      [...SECTION_ORDER],
    )
    for (const s of sections) {
      assert.ok(findAll(s, (e) => hasClass(e, 'container')).length >= 1, `${s.attrs['class']} has no .container`)
    }
    const css = styleOf(read('views/HomeView.vue'))
    assert.doesNotMatch(css, /(^|[\s,}])\.container\s*[{,]/, 'HomeView still declares its own .container, which overrides the shared one (1092px of content instead of 1248)')
  })

  test('the section headings are Figma\'s, in order', () => {
    const h2 = findAll(page, (e) => e.tag === 'h2').map((h) => textOf(h))
    assert.deepEqual(h2, [
      'Everything you need to run the service',
      "Built for the one moment you can't repeat",
      'One live moment, every output',
      'Live in three steps',
      'Plans and pricing',
      'Questions, answered',
      'Ready to run your best service yet?',
    ])
    assert.equal(textOf(findAll(page, (e) => e.tag === 'h1')[0] as El), 'Run your service with total confidence.')
  })
})

describe('the five section labels are plain eyebrows, not chips', () => {
  test('FEATURES, WHY SELAHCUE, SCREENS & OUTPUTS, HOW IT WORKS and PRICING use variant eyebrow', () => {
    const eyebrows = findAll(page, (e) => hasClass(e, 'variant-eyebrow')).map((e) => textOf(e))
    assert.deepEqual(eyebrows, ['FEATURES', 'WHY SELAHCUE', 'SCREENS & OUTPUTS', 'HOW IT WORKS', 'PRICING'])
  })

  test('no filled "accent" chip is left (the MOST POPULAR chip went with the plan cards), and no gradient button remains', () => {
    const chips = findAll(page, (e) => hasClass(e, 'variant-accent')).map((e) => textOf(e))
    assert.deepEqual(chips, [])
    assert.deepEqual(findAll(page, (e) => hasClass(e, 'variant-gradient')).map((e) => textOf(e)), [], 'variant="gradient" is a temporary alias; use primary')
    assert.doesNotMatch(read('views/HomeView.vue'), /variant="gradient"/)
  })
})

// --------------------------------------------------------------------------- the anchor target

describe('"How it works" has a target (home-11)', () => {
  test('the steps section carries id="how-it-works"', () => {
    assert.equal(section(page, 'steps-section').attrs['id'], 'how-it-works')
    assert.equal(findAll(page, (e) => e.attrs['id'] === 'how-it-works').length, 1, 'the id must be unique')
  })

  test('the heading of that section is the "Live in three steps" heading (the id is on the right section)', () => {
    const steps = section(page, 'steps-section')
    assert.equal(textOf(findAll(steps, (e) => e.tag === 'h2')[0] as El), 'Live in three steps')
  })

  test('every #fragment the chrome links to on Home exists on Home (no dangling link)', () => {
    const chrome = ['components/Navbar.vue', 'components/Footer.vue'].map(read).join('\n')
    const targets = [...chrome.matchAll(/hash:\s*'#([\w-]+)'/g)].map((m) => m[1] as string)
    assert.ok(targets.includes('how-it-works'), 'the navbar no longer links to #how-it-works: update this test with the link')
    assert.deepEqual(fragmentProblems(page, targets), [])
  })

  test('CONTROL: the check reports a link to an id that is not there', () => {
    const planted = parseHtml('<div><a href="#demo">Watch</a><section id="a"></section></div>')
    assert.deepEqual(fragmentProblems(planted, ['nope']), ['#nope points at nothing on this page', '#demo points at nothing on this page'])
    assert.deepEqual(fragmentProblems(parseHtml('<div><a href="#a">x</a><i id="a"></i></div>')), [])
  })
})

// --------------------------------------------------------------------------- headings

describe('the heading outline never skips a level (home-bug-01)', () => {
  test('one h1, and every heading is at most one level below the one before it', () => {
    assert.deepEqual(headingProblems(page), [])
  })

  test('card and step titles are h3 under their section h2; the output rows are not headings at all', () => {
    const h3 = findAll(page, (e) => e.tag === 'h3').map((h) => textOf(h))
    assert.deepEqual(h3, [
      'Live presentation & outputs',
      'Scripture at your fingertips',
      'Service plans & timers',
      'Stage & confidence monitor',
      'NDI & multi-output',
      'On-device transcript',
      'Never blanks the screen',
      'Works fully offline',
      'Fast & bounded',
      'Plan your service',
      'Go live with one tap',
      'Control from the console or phone',
    ])
    assert.deepEqual(findAll(page, (e) => e.tag === 'h4' || e.tag === 'h5' || e.tag === 'h6'), [])
    for (const name of ['Audience — Main', 'Stage Display', 'Livestream Program']) {
      const asHeading = findAll(page, (e) => /^h[1-6]$/.test(e.tag) && textOf(e) === name)
      assert.deepEqual(asHeading, [], `${name} is a heading`)
    }
  })

  test('the two mocks add no heading to the outline', () => {
    for (const mock of findAll(page, (e) => e.attrs['role'] === 'img')) {
      assert.deepEqual(findAll(mock, (e) => /^h[1-6]$/.test(e.tag)), [], textOf(mock).slice(0, 40))
    }
  })

  test('a designed line break leaves the words apart for anything that reads the text without drawing it (search, copy, a reader that ignores <br>)', () => {
    const joined = (el: El): string => {
      // Text nodes only, in order, with NO spacing for the <br> in between: what textContent gives.
      let out = ''
      const go = (e: El): void => {
        for (const c of e.children) {
          if (typeof c === 'string') out += c
          else go(c)
        }
      }
      go(el)
      return out.replace(/\s+/g, ' ').trim()
    }
    const withBreak = findAll(page, (e) => /^h[1-6]$/.test(e.tag) && findAll(e, (c) => c.tag === 'br').length > 0)
    assert.deepEqual(
      withBreak.map((h) => textOf(h)),
      ['Run your service with total confidence.', "Built for the one moment you can't repeat", 'One live moment, every output'],
      'the hero, Reliability and Screens & Outputs titles have the break Figma draws',
    )
    for (const h of withBreak) assert.equal(joined(h), textOf(h), `"${textOf(h)}" runs two words together without its <br>`)
  })

  test('the designed breaks are the frame\'s: the Screens & Outputs title breaks after "moment,", and every designed break is hidden on a phone', () => {
    const showcase = findAll(page, (e) => hasClass(e, 'outputs-title'))[0] as El
    const parts = showcase.children.map((c) => (typeof c === 'string' ? c : '<br>'))
    assert.deepEqual(parts, ['One live moment, ', '<br>', 'every output'])
    const css = parseCss(sfcStyles('views/HomeView.vue'))
    for (const selector of ['.hero-title br', '.section-title br', '.outputs-title br']) {
      assert.equal(effectiveExact(css, selector, { width: 375 })['display'], 'none', `${selector} at 375`)
      assert.equal(effectiveExact(css, selector, { width: 1440 })['display'], undefined, `${selector} at 1440`)
    }
  })

  test('CONTROL: a skipped level, a second h1 and an outline that starts below h1 are each reported', () => {
    assert.deepEqual(headingProblems(parseHtml('<main><h1>A</h1><h2>B</h2><h4>C</h4></main>')), ['h4 "C" follows an h2: a level is skipped'])
    assert.deepEqual(headingProblems(parseHtml('<main><h1>A</h1><h1>B</h1></main>')), ['expected exactly one h1, found 2'])
    assert.deepEqual(headingProblems(parseHtml('<main><h2>B</h2></main>')), ['expected exactly one h1, found 0', 'the outline starts at h2 "B"'])
    assert.deepEqual(headingProblems(parseHtml('<main><h1>A</h1><h2>B</h2><h3>C</h3><h2>D</h2></main>')), [])
  })
})

// --------------------------------------------------------------------------- icons

describe('icons are the feather-style SVG set (home-09, home-14, home-17)', () => {
  test('no emoji, tick glyph, status dot or play triangle is used as an icon anywhere in the rendered page', () => {
    assert.deepEqual(glyphProblems(page), [])
  })

  test('every inline SVG is hidden from assistive technology (they all sit beside text that says the same thing)', () => {
    assert.deepEqual(svgProblems(page), [])
  })

  test('the six feature icons, three reliability icons, three showcase ticks and the play mark are the Figma set, in order', () => {
    const names = (el: El): string[] => findAll(el, (e) => e.tag === 'svg' && e.attrs['data-icon'] !== undefined).map((e) => e.attrs['data-icon'] as string)
    assert.deepEqual(names(section(page, 'features-section')), ['monitor', 'book', 'list', 'layout', 'radio', 'mic'])
    assert.deepEqual(names(section(page, 'reliability-section')), ['shield-check', 'wifi-off', 'zap'])
    assert.deepEqual(names(section(page, 'outputs-section')), ['check', 'check', 'check'])
    assert.deepEqual(names(section(page, 'hero-section')), ['play'])
  })

  test('the reliability tiles are filled brand, preview and warn, as drawn', () => {
    const tiles = findAll(section(page, 'reliability-section'), (e) => hasClass(e, 'icon-box')).map((e) => (e.attrs['class'] ?? '').split(/\s+/).filter((c) => c !== 'icon-box'))
    assert.deepEqual(tiles, [['primary'], ['preview'], ['warn']])
  })

  test('the hero eyebrow carries the brand logo mark, not a sparkle', () => {
    const pill = findAll(section(page, 'hero-section'), (e) => hasClass(e, 'hero-eyebrow'))[0] as El
    assert.ok(pill, 'no .hero-eyebrow')
    const mark = findAll(pill, (e) => hasClass(e, 'brand-mark'))[0] as El
    assert.ok(mark, 'the eyebrow has no .brand-mark')
    const img = findAll(mark, (e) => e.tag === 'img')[0] as El
    assert.equal(img.attrs['src'], '/selahcue-logo.png')
    assert.equal(img.attrs['alt'], '', 'the logo sits beside the words, so it is decorative')
    assert.equal(mark.attrs['style'], undefined, 'the 18px size is a scoped rule, not a style attribute')
    assert.equal(effectiveExact(parseCss(sfcStyles('views/HomeView.vue')), '.hero-eyebrow .brand-mark', { width: 1440 })['--mark-size'], '18px')
    assert.equal(textOf(pill), 'Church presentation, reengineered')
  })

  test('no element on the page carries a style attribute (a strict style-src would drop it, and the mark would fall back to 32px)', () => {
    assert.deepEqual(findAll(page, (e) => e.attrs['style'] !== undefined).map((e) => `<${e.tag} class="${e.attrs['class'] ?? ''}">`), [])
  })

  test('CONTROL: each fault is reported', () => {
    assert.match(glyphProblems(parseHtml('<p>📊 Live</p>')).join(), /📊/)
    assert.match(glyphProblems(parseHtml('<p>✨ Hi</p>')).join(), /✨/)
    assert.match(glyphProblems(parseHtml('<p>✓ item</p>')).join(), /✓/)
    assert.match(glyphProblems(parseHtml('<p>● LIVE</p>')).join(), /●/)
    assert.match(glyphProblems(parseHtml('<span>▶</span>')).join(), /▶/)
    assert.deepEqual(glyphProblems(parseHtml('<p>Live — "ok" · 1920 × 1080 …</p>')), [], 'ordinary punctuation is not a glyph icon')
    assert.equal(svgProblems(parseHtml('<svg viewBox="0 0 24 24"></svg>')).length, 1)
    assert.deepEqual(svgProblems(parseHtml('<svg aria-hidden="true" viewBox="0 0 24 24"></svg>')), [])
  })
})

describe('HomeIcon draws every name it accepts, as a decorative stroke icon', () => {
  const NAMES = ['monitor', 'book', 'list', 'layout', 'radio', 'mic', 'shield-check', 'wifi-off', 'zap', 'check', 'play']

  test('each name renders one aria-hidden svg with shapes in it and a data-icon naming it', async () => {
    for (const name of NAMES) {
      const svg = findAll(parseHtml(await server.render('components/home/HomeIcon.vue', { name })), (e) => e.tag === 'svg')
      assert.equal(svg.length, 1, name)
      const el = svg[0] as El
      assert.equal(el.attrs['aria-hidden'], 'true', name)
      assert.equal(el.attrs['focusable'], 'false', `${name}: IE and old Edge made every svg a tab stop`)
      assert.equal(el.attrs['data-icon'], name)
      assert.ok(findAll(el, (e) => ['path', 'rect', 'circle', 'line', 'polygon', 'polyline'].includes(e.tag)).length >= 1, `${name} draws nothing`)
    }
  })

  test('an unknown name draws nothing instead of a blank box (and the validator names the set)', async () => {
    const html = await server.render('components/home/HomeIcon.vue', { name: 'sparkle' })
    assert.equal(findAll(parseHtml(html), (e) => e.tag === 'svg' && findAll(e, (c) => c.tag === 'path').length > 0).length, 0)
    assert.match(read('components/home/HomeIcon.vue'), /validator/)
  })

  test('a name that is a property of every object (__proto__, constructor, toString, hasOwnProperty, valueOf) draws nothing: the lookup is by own property', async () => {
    for (const name of ['__proto__', 'constructor', 'toString', 'hasOwnProperty', 'valueOf']) {
      const html = await server.render('components/home/HomeIcon.vue', { name })
      assert.deepEqual(findAll(parseHtml(html), (e) => e.tag === 'svg').map((e) => e.attrs['viewBox']), [], `${name} drew an svg`)
    }
  })
})

// --------------------------------------------------------------------------- the two mocks

describe('the hero console and the Screens & Outputs window are the designed product windows (home-12, home-13, home-25)', () => {
  const mocks = (): El[] => findAll(page, (e) => e.attrs['role'] === 'img')

  test('exactly two images: each is named, and the name says what the mock shows', () => {
    const m = mocks()
    assert.equal(m.length, 2)
    assert.match(m[0]?.attrs['aria-label'] ?? '', /operator console.*Preview.*Live/i)
    assert.match(m[1]?.attrs['aria-label'] ?? '', /Screens.*Outputs.*(projector|audience).*stage.*NDI/i)
    assert.ok(ancestors(m[0] as El).some((a) => hasClass(a, 'hero-section')))
    assert.ok(ancestors(m[1] as El).some((a) => hasClass(a, 'outputs-section')))
  })

  test('the console shows the title bar and LIVE chip, then the PREVIEW pane, then the LIVE pane, with Figma\'s content', () => {
    const text = textOf(mocks()[0] as El)
    assert.match(
      text,
      /SelahCue — Live Console.*LIVE.*PREVIEW.*1920 × 1080.*PSALM 46:10.*Be still, and know that I am God\..*LIVE.*1920 × 1080.*JOHN 3:16.*For God so loved the world…/,
    )
    assert.doesNotMatch(text, /MAIN OUTPUT|STAGE DISPLAY|WEB BIBLE|CURRENT|NEXT|THAT HE GAVE/, 'the old console content is gone')
  })

  test('the output window shows the title, the Add output button, and three rows with a tag and a separate status each', () => {
    const text = textOf(mocks()[1] as El)
    assert.match(
      text,
      /Screens & Outputs.*\+ Add output.*Audience — Main.*MAIN.*LIVE.*Stage Display.*STAGE.*READY.*Livestream Program.*NDI.*BROADCASTING/,
    )
    assert.doesNotMatch(text, /OUTPUT MANAGER|OUTPUTS ACTIVE|60fps|1920x1080|Alpha|NDI 5|Confidence View|Audience - Main/, 'the old rows and their unbacked sub-lines are gone')
  })

  test('the words inside each mock are hidden outright (aria-hidden), not only presentational: not every reader prunes the children of an image', () => {
    for (const mock of mocks()) {
      const kids = mock.children.filter((c): c is El => typeof c !== 'string')
      assert.ok(kids.length >= 1)
      for (const k of kids) assert.equal(k.attrs['aria-hidden'], 'true', `<${k.tag}> inside the image is exposed`)
    }
  })

  test('nothing inside a mock can be operated or focused: no link, button, input or tab stop (the "+ Add output" button is a picture of one)', () => {
    for (const mock of mocks()) {
      const live = findAll(mock, (e) => ['a', 'button', 'input', 'select', 'textarea', 'summary'].includes(e.tag) || e.attrs['tabindex'] !== undefined)
      assert.deepEqual(live.map((e) => e.tag), [])
    }
  })

  test('assistive technology reads the two names and none of the fake UI text', () => {
    const exposed = textOf(page, { exposed: true })
    for (const fake of ['PSALM 46:10', 'JOHN 3:16', '1920 × 1080', '+ Add output', 'Livestream Program', 'BROADCASTING', 'Live Console']) {
      assert.ok(!exposed.includes(fake), `"${fake}" is read out as page content`)
    }
    assert.ok(/operator console/i.test(exposed))
  })

  test('CONTROL: the exposed-text reading hides aria-hidden subtrees and reads a role=img as its label only', () => {
    const t = parseHtml('<div><p aria-hidden="true">secret</p><div role="img" aria-label="Named"><span>inner</span></div><p>open</p></div>')
    assert.equal(textOf(t, { exposed: true }), 'Named open')
    assert.equal(textOf(t), 'secret inner open')
  })
})

// --------------------------------------------------------------------------- controls and plan links

describe('no control on Home is a dead end (home-32, home-18)', () => {
  test('every link goes somewhere, every enabled button is a disclosure, every disabled button says why', () => {
    assert.deepEqual(controlProblems(page), [])
  })

  test('the hero: Download free goes to /download; the demo button is disabled and described, not a link to #demo', () => {
    const hero = section(page, 'hero-section')
    const buttons = findAll(hero, (e) => hasClass(e, 'ui-button'))
    const dl = buttons.find((b) => textOf(b) === 'Download free') as El
    assert.equal(dl.tag, 'a')
    assert.equal(dl.attrs['href'], '/download')
    assert.ok(hasClass(dl, 'variant-primary'), 'the hero button is primary, not the gradient alias')
    const demo = buttons.find((b) => textOf(b) === 'Watch 2-min demo') as El
    assert.ok(demo, 'the demo button is still drawn, as Figma has it')
    assert.equal(demo.tag, 'button')
    assert.ok(demo.attrs['disabled'] !== undefined)
    assert.ok(hasClass(demo, 'variant-secondary'), 'Figma draws it as the elevated secondary button')
    const note = findAll(hero, (e) => e.attrs['id'] === demo.attrs['aria-describedby'])[0] as El
    assert.equal(textOf(note), 'Demo video not available yet')
    assert.equal(findAll(page, (e) => e.tag === 'a' && e.attrs['href'] === '#demo').length, 0)
  })

  test('the demo button\'s reason is VISIBLE to everyone, as the Pro plan\'s note is (not only spoken): a plain sibling of the button, not hidden, not clipped', () => {
    const hero = section(page, 'hero-section')
    const demo = findAll(hero, (e) => hasClass(e, 'ui-button') && textOf(e) === 'Watch 2-min demo')[0] as El
    const note = findAll(hero, (e) => e.attrs['id'] === demo.attrs['aria-describedby'])[0] as El
    assert.ok(note, 'the button points at a note')
    assert.equal(note.parent, demo.parent, 'the note sits beside the button it explains')
    for (const el of [note, ...ancestors(note)]) {
      assert.notEqual(el.attrs['aria-hidden'], 'true', 'the note is hidden from assistive technology')
      assert.ok(!/visually-hidden|sr-only/.test(el.attrs['class'] ?? ''), `the note (or an ancestor) is a screen-reader-only class: ${el.attrs['class']}`)
    }
    // The class that styles it must not take it off the screen.
    const rule = effective(parseCss(sfcStyles('views/HomeView.vue')), ['demo-note'], { width: 1440 })
    assert.ok(rule['font-size'] !== undefined && px(rule['font-size']) >= 12, `the note is at least 12px: ${rule['font-size']}`)
    for (const hidden of ['clip', 'clip-path', 'display', 'opacity', 'visibility', 'width', 'height']) {
      const v = rule[hidden]
      assert.ok(v === undefined || !/^(rect\(|inset\(50%|none|0|1px|hidden)/.test(v), `the note is taken off the screen by ${hidden}: ${v}`)
    }
    assert.equal(rule['color'], 'var(--sc-text-secondary)')
  })

  // ClickUp 17tnw2b0x3h: plan names and prices come from the API, so until it serves them the page draws no plan, no price and no billing term.
  test('the pricing section draws no plan card, no price and no plan button: it says plans and prices are not published yet', () => {
    const pricing = section(page, 'pricing-section')
    assert.equal(findAll(pricing, (e) => hasClass(e, 'pricing-card')).length, 0)
    assert.equal(findAll(pricing, (e) => hasClass(e, 'ui-button')).length, 0, 'no plan button')
    assert.equal(findAll(pricing, (e) => e.tag === 'a').length, 0, 'and nothing in the section links anywhere')
    assert.deepEqual(findAll(pricing, (e) => e.tag === 'h3'), [], 'no plan name')
    assert.match(textOf(pricing), /Plans and prices have not been published yet\./)
    assert.doesNotMatch(textOf(pricing), /\$|\bFree\b|\bPro\b|\bChurch\b|month|year|forever/i, 'no price, tier name or billing period')
    assert.equal(findAll(page, (e) => e.tag === 'a' && e.attrs['href'] === '/contact').length, 0, 'nothing on Home sends a visitor to the contact form')
  })

  test('the final band: Download free and See pricing, as the white and outlined buttons for a gradient card', () => {
    const band = section(page, 'final-cta-section')
    const [dl, pricing] = findAll(band, (e) => hasClass(e, 'ui-button')) as [El, El]
    assert.deepEqual([textOf(dl), dl.attrs['href'], hasClass(dl, 'variant-inverse')], ['Download free', '/download', true])
    assert.deepEqual([textOf(pricing), pricing.attrs['href'], hasClass(pricing, 'variant-inverse-outline')], ['See pricing', '/pricing', true])
  })

  test('CONTROL: each dead end is reported', () => {
    assert.match(controlProblems(parseHtml('<a href="#">x</a>')).join(), /goes nowhere/)
    assert.match(controlProblems(parseHtml('<a href="">x</a>')).join(), /goes nowhere/)
    assert.match(controlProblems(parseHtml('<a href="javascript:void(0)">x</a>')).join(), /goes nowhere/)
    assert.match(controlProblems(parseHtml('<a>x</a>')).join(), /no destination/)
    assert.match(controlProblems(parseHtml('<button>Get Pro</button>')).join(), /nothing is attached/)
    assert.match(controlProblems(parseHtml('<button disabled>Get Pro</button>')).join(), /does not point at/)
    assert.match(controlProblems(parseHtml('<button disabled aria-describedby="n">Get Pro</button><p id="n"></p>')).join(), /does not point at/)
    assert.deepEqual(controlProblems(parseHtml('<button disabled aria-describedby="n">Get Pro</button><p id="n">Soon</p>')), [])
    assert.deepEqual(controlProblems(parseHtml('<a role="link" aria-disabled="true">x</a><button aria-expanded="false">Q</button>')), [])
  })
})

// --------------------------------------------------------------------------- the copy

/** Attributes whose value a screen reader announces, or a visitor reads on hover: they are copy too. */
const ANNOUNCED_ATTRS = ['aria-label', 'aria-description', 'aria-roledescription', 'title', 'alt', 'placeholder'] as const

/**
 * The blocks of copy of an element, in order: each element's own text nodes joined, trimmed, whitespace
 * collapsed, empty ones dropped, followed by the value of every attribute that is announced or shown on hover
 * (`aria-label`, `title`, `alt` and the like; an empty one, like a decorative `alt=""`, is not copy). A heading
 * with a designed <br> is one block ("Run your service with total confidence."), a button is its label, a quote
 * is the quote with its marks, a mock's `aria-label` is a block of its own.
 */
function blocks(root: El): string[] {
  const out: string[] = []
  walk(root, (e) => {
    const own = e.children
      .filter((c): c is string => typeof c === 'string')
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim()
    if (own) out.push(own)
    for (const name of ANNOUNCED_ATTRS) {
      const value = (e.attrs[name] ?? '').replace(/\s+/g, ' ').trim()
      if (value) out.push(value)
    }
  })
  return out
}

type SectionClass = (typeof SECTION_ORDER)[number]

/**
 * THE COPY LEDGER: every block of text the Home page may show, per section. The contract
 * (docs/delivery/goals/17tnw2b2cex-figma-home.md, "Copy ledger") says where each comes from: Figma's
 * wording where the repo backs it, the backed part where Figma claims more. The page must show every line
 * (the section tests below) and NOTHING ELSE (the allow-list test), so a sentence cannot be added by
 * accident, whatever it says.
 */
const LEDGER: Readonly<Record<SectionClass, readonly string[]>> = {
  'hero-section': [
    'Church presentation, reengineered',
    'Run your service with total confidence.',
    // "controlled from anywhere" is gone: PRD NG-5 says mobile control is LAN-based (ClickUp 17tnw2b0x3h).
    'SelahCue is the offline-first presentation & ministry-assistance app that never blanks the screen — scripture, songs, timers, stage display, and NDI outputs.',
    'Download free',
    'Watch 2-min demo',
    // The reason the demo button is disabled, VISIBLE as the Pro plan's note is (owner decision, 2026-10-04).
    'Demo video not available yet',
    'Free to start · Works fully offline · Windows, macOS & mobile control',
    // The console mock (Figma 470:124): one named image for assistive technology, its drawing hidden from it.
    'SelahCue operator console showing a Preview and a Live scripture slide',
    'SelahCue — Live Console',
    'LIVE',
    'PREVIEW',
    '1920 × 1080',
    'PSALM 46:10',
    'Be still, and know that I am God.',
    'JOHN 3:16',
    'For God so loved the world…',
  ],
  'features-section': [
    'FEATURES',
    'Everything you need to run the service',
    'One app for the whole ministry moment — from planning the order of service to the last slide, on stage and online.',
    'Live presentation & outputs',
    'Stage scripture, songs, and slides in Preview, then Go Live to the audience — the output never blanks, even on a fault.',
    'Scripture at your fingertips',
    'A bundled public-domain Bible with instant reference parsing and keyword search.',
    'Service plans & timers',
    'Build the order of service, run countdowns, and keep every segment on time from the console or your phone.',
    'Stage & confidence monitor',
    "A dedicated speaker view — current line, what's next, and the service timer — that the audience never sees.",
    'NDI & multi-output',
    'Broadcast your program as an NDI source for OBS or vMix, with per-output orientation, scaling, mirror, and visible layers.',
    'On-device transcript',
    'AI that assists but never gates: a live transcript and spoken-scripture suggestions, on your machine by default.',
  ],
  'reliability-section': [
    'WHY SELAHCUE',
    "Built for the one moment you can't repeat",
    "Sunday morning doesn't wait for a spinning cursor. SelahCue is engineered so the audience output is always up — reliable, offline, and fast.",
    'Never blanks the screen',
    'No component failure — a bad slide, a lost GPU, a dropped controller — is ever allowed to black the live output.',
    'Works fully offline',
    // NFR-015 is "all core live functions operate with the network disabled", not "everything".
    'Every core live control works with no internet and no cloud dependency during the service. It just works.',
    'Fast & bounded',
    'Starts fast and keeps memory bounded. No runaway caches, no creeping slowdown.',
  ],
  'outputs-section': [
    'SCREENS & OUTPUTS',
    'One live moment, every output',
    // "each with its own theme" is gone: per-output theme is FR-038 (R2) and whether it ships today is unknown.
    'Send the same live content to your projector, a stage confidence monitor, and an NDI stream — each with its own orientation, scaling, and visible layers.',
    'Audience projector — the program the room sees',
    'Stage display — current, next & timer, for the speaker only',
    'NDI output — broadcast to OBS, vMix, or another machine',
    // The output window mock (Figma 475:142): one named image, its drawing hidden from assistive technology.
    'Screens & Outputs window listing three outputs: the audience projector, the stage display and an NDI stream',
    'Screens & Outputs',
    '+ Add output',
    'Audience — Main',
    'MAIN',
    'LIVE',
    'Stage Display',
    'STAGE',
    'READY',
    'Livestream Program',
    'NDI',
    'BROADCASTING',
  ],
  'steps-section': [
    'HOW IT WORKS',
    'Live in three steps',
    // The old "in minutes — no manual, no setup weekend" was a PRD target (G-4, METRIC-006), not a measured result.
    'From an empty plan to a running service in three steps.',
    '1',
    'Plan your service',
    // "give any item its own theme" is gone: specified, whether it ships today is unknown.
    'Add songs, scripture, and sections to the order of service. Set countdowns.',
    '2',
    'Go live with one tap',
    'Stage the next item in Preview, then Go Live. The audience, stage, and NDI outputs all update together.',
    '3',
    // "Control from anywhere" is gone: mobile control is LAN-based (PRD NG-5). "No lag" went earlier: unmeasured (NFR-009).
    'Control from the console or phone',
    'Drive it from the console — or pair your phone over the local network. No internet needed.',
  ],
  // The plan cards, prices, tier names, "MOST POPULAR" and "Cancel anytime" are gone (ClickUp 17tnw2b0x3h): plan names and
  // prices come from the API once it serves them.
  'pricing-section': [
    'PRICING',
    'Plans and pricing',
    'Plans and prices have not been published yet.',
  ],
  'faq-section': [
    'Questions, answered',
    'Do I need an internet connection?',
    // NFR-015: core live controls work with the network off. Sign-in, activation and the first speech-model download need it.
    'No. SelahCue is offline-first — every core live control works with no internet, so a dropped connection never stops the service.',
    'Which platforms are supported?',
    // No version number, architecture or file format: the product is available for Windows, macOS and Linux (owner, 2026-10-04).
    'SelahCue is available for Windows, macOS and Linux. Additionally, you can pair any iOS or Android phone over your local Wi-Fi network to control slides remotely.',
    'Can I use my own songs, slides, and designs?',
    'Yes. Build multi-slide song lyrics, stage any scripture, and design your own slide templates in the Theme Designer.',
    'What is NDI, and do I need it?',
    "NDI sends your program video over the local network to software like OBS or vMix — no capture card required. It's optional.",
    'How does billing work?',
    'Plans and prices have not been published yet.',
  ],
  'final-cta-section': [
    'Ready to run your best service yet?',
    'Start free. Core live controls keep working with no network.',
    'Download free',
    'See pricing',
  ],
}

/**
 * EMPTY ON PURPOSE (ClickUp 17tnw2b0x3h). This was the list of copy the repo does not back that the live page still made: the
 * plan tiers and prices, "MOST POPULAR", "Cancel anytime", the invented testimonials, "controlled from anywhere", the OS
 * version numbers and the unmeasured "in minutes" line. All of it was removed or reworded, and a test below fails if an entry
 * is ever added. The mechanism stays so the allow-list below keeps one definition.
 */
const LIVE_CLAIMS: Readonly<Record<string, string>> = {}

const ALLOWED_BLOCKS: ReadonlySet<string> = new Set([...Object.values(LEDGER).flat(), ...Object.keys(LIVE_CLAIMS)])

/** Every block of text the page shows that is on neither the ledger nor the named live-claims list. */
function unlistedBlocks(root: El, allowed: ReadonlySet<string> = ALLOWED_BLOCKS): string[] {
  return [...new Set(blocks(root).filter((b) => !allowed.has(b)))]
}

describe('copy follows the ledger: Figma\'s wording where the repo backs it', () => {
  for (const cls of SECTION_ORDER) {
    test(`${cls}: every ledger line is on the page, in the order the ledger lists it`, () => {
      const shown = blocks(section(page, cls))
      const lines = LEDGER[cls]
      let from = 0
      for (const line of lines) {
        const at = shown.indexOf(line, from)
        assert.ok(at !== -1, `${cls} is missing (or has out of order): ${line}`)
        from = at + 1
      }
    })
  }

  test('nothing else is on the page: every block of text is on the ledger or on the named list of claims the live page already made', () => {
    assert.deepEqual(unlistedBlocks(page), [])
  })

  test('CONTROL: a sentence nobody thought to ban ("Trusted by 5,000 churches.") is reported, in any section, as is a reworded ledger line', () => {
    const planted = parseHtml('<section class="final-cta-section"><p>Trusted by 5,000 churches.</p><p>Start free. Core live controls keep working with no network.</p></section>')
    assert.deepEqual(unlistedBlocks(planted), ['Trusted by 5,000 churches.'])
    const reworded = parseHtml('<p>Start free. Core live controls keep working with no network!</p>')
    assert.equal(unlistedBlocks(reworded).length, 1)
    assert.deepEqual(unlistedBlocks(parseHtml('<p>Download free</p><p>See pricing</p>')), [])
    // The claims that were tolerated before ClickUp 17tnw2b0x3h are now reported, not allow-listed.
    assert.deepEqual(unlistedBlocks(parseHtml('<p>$19</p><p>MOST POPULAR</p><p>Sarah Jenkins</p>')), ['$19', 'MOST POPULAR', 'Sarah Jenkins'])
  })

  test('CONTROL: copy that is only announced or shown on hover (aria-label, title, alt, aria-description, placeholder) is read too; an empty alt is not copy', () => {
    for (const attr of ANNOUNCED_ATTRS) {
      const planted = parseHtml(`<div ${attr}="Trusted by 5,000 churches"></div>`)
      assert.deepEqual(unlistedBlocks(planted), ['Trusted by 5,000 churches'], attr)
    }
    assert.deepEqual(unlistedBlocks(parseHtml('<img src="/selahcue-logo.png" alt="" aria-hidden="true">')), [])
    assert.deepEqual(unlistedBlocks(parseHtml('<span role="img" aria-label="SelahCue operator console showing a Preview and a Live scripture slide"></span>')), [])
  })

  test('the two mock images are named on the ledger, so an announced claim cannot hide in their labels', () => {
    const labels = findAll(page, (e) => e.attrs['role'] === 'img').map((e) => e.attrs['aria-label'])
    assert.equal(labels.length, 2)
    for (const label of labels) assert.ok(Object.values(LEDGER).flat().includes(label as string), `${label} is not on the ledger`)
  })

  test('the list of claims the page does not back is not the ledger: none of its entries is also on the ledger (the test file does not vouch for them)', () => {
    const ledger = new Set(Object.values(LEDGER).flat())
    assert.deepEqual(Object.keys(LIVE_CLAIMS).filter((k) => ledger.has(k)), [])
    for (const [text, reason] of Object.entries(LIVE_CLAIMS)) assert.ok(reason.length > 10, `no reason for: ${text}`)
  })

  // ClickUp 17tnw2b0x3h's check, executable: nothing is tolerated on Home that the repo does not back.
  test('no claim the repo does not back is live: LIVE_CLAIMS is empty (ClickUp 17tnw2b0x3h)', () => {
    assert.deepEqual(Object.keys(LIVE_CLAIMS), [], 'unbacked Home lines are still tolerated; remove the words and the entry')
  })

  test('hero trust line: each of the three items is held together (no breakable space inside one), so a narrow phone breaks BETWEEN items, never inside one', () => {
    const trust = findAll(section(page, 'hero-section'), (e) => hasClass(e, 'hero-trust'))[0] as El
    assert.ok(trust, 'no .hero-trust')
    const raw = trust.children.filter((c): c is string => typeof c === 'string').join('')
    for (const item of ['Free to start', 'Works fully offline', 'Windows, macOS & mobile control']) {
      const joined = item.replace(/ /g, '\u00a0')
      assert.ok(raw.includes(joined), `"${item}" can break inside itself: ${JSON.stringify(raw)}`)
    }
    // ...and a real space (a place to break) follows each separator.
    assert.equal((raw.match(/·\u00a0 /g) ?? []).length, 2, 'a breakable space after each dot')
    assert.equal(raw.replace(/\u00a0/g, ' ').replace(/\s+/g, ' '), 'Free to start · Works fully offline · Windows, macOS & mobile control')
  })

  test('showcase (home-24): three single-line checks', () => {
    const items = findAll(section(page, 'outputs-section'), (e) => e.tag === 'li').map((li) => textOf(li))
    assert.equal(items.length, 3, 'three single-line checks, no second line')
  })

  test('how it works (home-28): the steps are an ordered list of three', () => {
    const steps = section(page, 'steps-section')
    assert.equal(findAll(steps, (e) => e.tag === 'ol').length, 1, 'the steps are an ordered list')
    assert.equal(findAll(steps, (e) => e.tag === 'li').length, 3)
  })

  test('there is no testimonials section: the quotes, names and churches were invented, so nothing replaces them (ClickUp 17tnw2b0x3h)', () => {
    assert.equal(findAll(page, (e) => e.tag === 'section' && hasClass(e, 'testimonials-section')).length, 0)
    assert.equal(findAll(page, (e) => e.tag === 'blockquote' || e.tag === 'figcaption').length, 0, 'no quote and no attribution')
    assert.doesNotMatch(textOf(page), /TESTIMONIALS|Trusted on Sunday/)
    assert.doesNotMatch(read('views/HomeView.vue'), /TestimonialCard|<blockquote|testimonials-section|testimonials-grid/, 'and the view uses no testimonial component and styles none')
  })

  test('faq (home-38): the five Figma questions, in order', () => {
    const faq = section(page, 'faq-section')
    assert.deepEqual(findAll(faq, (e) => e.tag === 'button').map((b) => textOf(b)), [
      'Do I need an internet connection?',
      'Which platforms are supported?',
      'Can I use my own songs, slides, and designs?',
      'What is NDI, and do I need it?',
      'How does billing work?',
    ])
  })
})

/** Claims no change to this page may add. Each is the specific overclaim the audit or the owner named, with a planted sample the check must catch. */
const FORBIDDEN: ReadonlyArray<{ re: RegExp; why: string; sample: string }> = [
  { re: /NDI 5/i, why: 'a version of NDI the repo does not pin (home-42)', sample: 'Direct NDI 5 streams' },
  { re: /Wirecast/i, why: 'a product Figma never names (home-42)', sample: 'OBS, vMix and Wirecast' },
  { re: /\b4K\b/, why: 'a resolution nothing backs (home-42)', sample: 'Full 4K resolution' },
  { re: /60\s?fps/i, why: 'a frame rate nothing backs (home-42)', sample: 'Display 2 · 1920x1080 · 60fps' },
  { re: /alpha channel|transparent lower thirds?/i, why: 'alpha output (home-42)', sample: 'Direct IP feed with alpha channel transparency' },
  { re: /NFR-\d+/, why: 'an internal requirement id (home-21, home-42)', sample: 'holds the last-good image (NFR-024)' },
  { re: /Whisper/i, why: 'an engine name (home-42)', sample: 'powered by local Whisper AI' },
  { re: /zero lag|zero-blank|hardware frame buffer/i, why: 'unmeasured or unbuilt (home-21, home-42)', sample: 'and zero lag when triggering' },
  { re: /sub-3-second|≤\s?3\s?s|cold start/i, why: 'a start-up time that is a proxy measurement (home-23)', sample: 'Sub-3-second cold start' },
  { re: /Add more translations/i, why: 'licensed translations are later (PRD CON-3)', sample: 'Add more translations any time.' },
  { re: /Billed monthly, or save|save 20%|annual/i, why: 'there is no annual plan', sample: 'Billed monthly, or save 20% yearly.' },
  { re: /Priority support|Guided onboarding|Solutions Architect|Bible entitlement|Venue Device/i, why: 'services and SKUs that do not exist (home-34)', sample: 'Priority support' },
  { re: /Always on the latest version/i, why: 'no update channel ships', sample: 'Always on the latest version' },
  { re: /One physical output|Single display projector/i, why: 'DEC-008 gives Free two outputs (home-34)', sample: 'One physical output' },
  { re: /\bno account\b/i, why: 'account sign-in is the primary activation path (DEC-007)', sample: 'no internet, no account, no cloud' },
  { re: /Linux is on the roadmap|roadmap/i, why: 'the product is available on Linux (owner, 2026-10-04); Figma\'s "on the roadmap" is wrong (home-45)', sample: 'Linux is on the roadmap' },
  { re: /Windows\s*1[01]|macOS\s*1\d|64-bit|Apple Silicon|\bIntel\b|\bARM\b/i, why: 'OS versions and architectures with no source in the repo (home-40)', sample: 'Windows 10/11 (64-bit) and macOS 12+ (Apple Silicon & Intel)' },
  { re: /cancel anytime/i, why: 'no billing exists, so there is nothing to cancel (home-33)', sample: 'Simple pricing. Cancel anytime.' },
  { re: /\$\s?\d|\/\s?month|\bper month\b/i, why: 'a price or billing period: prices are undecided and come from the API (home-33)', sample: '$19 / month' },
  { re: /MOST POPULAR/, why: 'Pro cannot be bought yet (home-33)', sample: 'MOST POPULAR' },
  { re: /Multi-campus|site licensing|Church tier/i, why: 'a tier that no decision defines (home-33, home-34)', sample: 'Multi-campus / site licensing' },
  { re: /Sarah Jenkins|Mark Davis|Paul Miller|Grace Community|Redeemer Church|Hope Chapel/, why: 'invented people and churches (home-36)', sample: 'Sarah Jenkins, Worship Director · Grace Community' },
  { re: /controlled from anywhere|control from anywhere/i, why: 'mobile control is LAN-based (PRD NG-5)', sample: 'controlled from anywhere' },
  { re: /go live this Sunday/i, why: '/download says nothing downloads yet', sample: 'Start free and go live this Sunday.' },
  { re: /simple monthly subscription|free forever/i, why: 'a billing cadence nobody decided', sample: 'SelahCue Pro is a simple monthly subscription' },
  { re: /in minutes|setup weekend/i, why: 'a PRD target, not a measured result (G-4, METRIC-006)', sample: 'in minutes — no manual, no setup weekend' },
  { re: /its own theme/i, why: 'per-output and per-item theme are specified, and whether they ship is unknown', sample: 'each with its own theme' },
  { re: /installer|\.msi|\.dmg|\.exe/i, why: 'no downloadable installer is claimed', sample: 'download the installer' },
  { re: /FROM THE TECH BOOTH/i, why: 'attributes the live quotes to tech teams (home-36)', sample: 'FROM THE TECH BOOTH' },
  { re: /Everything runs on-device/i, why: 'NFR-015 is "all core live functions operate with the network disabled", not everything (sign-in, activation and the first speech-model download need the network)', sample: 'Everything runs on-device — no internet and no cloud dependency' },
  { re: /whole service runs on-device/i, why: 'the same overreach, in the FAQ', sample: 'the whole service runs on-device, so a dropped connection never stops it' },
  { re: /\bno lag\b/i, why: 'an unmeasured promise (the PRD targets under 200 ms on the LAN, NFR-009); "zero lag" is banned for the same reason', sample: 'No internet, no lag, no surprises.' },
]

describe('no unbacked claim is added', () => {
  const allStrings = (): string => {
    const parts: string[] = [textOf(page)]
    walk(page, (e) => {
      for (const k of ['aria-label', 'title', 'alt']) if (e.attrs[k]) parts.push(e.attrs[k] as string)
    })
    return parts.join('\n')
  }

  test('none of the named overclaims appears in any rendered text or accessible name', () => {
    const everything = allStrings()
    const hits = FORBIDDEN.filter(({ re }) => re.test(everything)).map(({ re, why }) => `${re}: ${why}`)
    assert.deepEqual(hits, [])
  })

  test('CONTROL: the list catches a planted claim of each kind, and passes the honest wording', () => {
    for (const { re, why, sample } of FORBIDDEN) assert.ok(re.test(sample), `${re} does not catch "${sample}" (${why})`)
    const honest = 'Starts fast and keeps memory bounded. NDI output for OBS or vMix. Plans and prices have not been published yet.'
    assert.deepEqual(FORBIDDEN.filter(({ re }) => re.test(honest)), [])
  })
})

// --------------------------------------------------------------------------- source

function sfcStyles(file: string): string {
  return parse(read(file)).descriptor.styles.map((s) => s.content).join('\n')
}

/**
 * Hex colours that may appear in these files, with why. Everything else must be a token (`var(--sc-*)`
 * or a legacy Figma variable the code already carries). `rgba()` is not scanned: it is how a token is
 * given an alpha.
 */
const HEX_ALLOWED: Readonly<Record<string, string>> = {
  '#fff': 'pure white, Figma\'s own non-token colour, only for text and icons on a coloured fill (markers, avatars, the band, the slide)',
  '#000': 'Figma draws the feature icon tiles pure black',
  '#080a17': 'the mock slide canvas (content shown on the projector, not site chrome)',
  '#241c4a': 'Audience output thumbnail canvas (Figma 475:149)',
  '#0f121a': 'Stage output thumbnail canvas (Figma 475:160)',
  '#0d1221': 'NDI output thumbnail canvas (Figma 475:171)',
  '#a5b4fc': 'the hero pill ink: accessible light indigo kept instead of Figma\'s #5b6bd6 (3.7:1; home-15, class B; 9.6:1 here)',
}

/**
 * `rgb()` and `rgba()` literals that may appear: black, for the shadow and the darkened pill, and Figma's
 * shadow ink #05080f. A brand colour with an alpha is `color-mix()` of the token, not a copy of its channels
 * (the hero glow was `rgba(110, 92, 240, 0.15)`, the brand colour typed out).
 */
const RGB_ALLOWED: ReadonlySet<string> = new Set(['0, 0, 0', '5, 8, 15'])

/** The CSS named colours (Color Module 4). A name is a literal colour exactly as a hex is. */
const NAMED_COLOURS: ReadonlySet<string> = new Set(
  (
    'aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen'
  ).split(' '),
)

/** Properties whose value is (or holds) a colour. */
const COLOUR_PROPERTY = /^(color|background(-color|-image)?|border(-(top|right|bottom|left|block|inline)(-(start|end))?)?(-color)?|outline(-color)?|box-shadow|text-shadow|fill|stroke|caret-color|accent-color|text-decoration(-color)?|column-rule(-color)?|stop-color)$/

/** The text inside the parentheses that open at `open`, and the index after the closing one. */
function balanced(text: string, open: number): [string, number] {
  let depth = 0
  for (let i = open; i < text.length; i++) {
    if (text[i] === '(') depth++
    else if (text[i] === ')' && --depth === 0) return [text.slice(open + 1, i), i + 1]
  }
  return [text.slice(open + 1), text.length]
}

/**
 * What is wrong with ONE colour-bearing value. The allow-list is the point: `var(--token)`, `color-mix()` made of
 * tokens, `transparent`, `currentColor`, the documented hexes and the documented `rgba()` channels. Anything else
 * that is a colour, in any notation (a hex, a name, `rgb()`, `hsl()`, `hwb()`, `lab()`, `lch()`, `oklab()`,
 * `oklch()`, `color()`, `light-dark()`), is reported, so a notation nobody listed cannot slip in.
 */
function valueColourProblems(value: string): string[] {
  const out: string[] = []
  let i = 0
  while (i < value.length) {
    const rest = value.slice(i)
    const fn = /^([a-zA-Z-]+)\(/.exec(rest)
    if (fn) {
      const name = (fn[1] as string).toLowerCase()
      const [args, next] = balanced(value, i + (fn[0].length - 1))
      if (name === 'var') {
        if (!/^\s*--[\w-]+\s*(,[^]*)?$/.test(args)) out.push(`var(${args}) is not a custom property`)
        // A fallback after the comma is a colour literal too.
        const fallback = /,([^]*)$/.exec(args)
        if (fallback) out.push(...valueColourProblems(fallback[1] as string))
      } else if (name === 'color-mix' || /gradient$/.test(name)) {
        out.push(...valueColourProblems(args))
      } else if (name === 'rgb' || name === 'rgba') {
        const channels = args.split(/[,/]/).slice(0, 3).map((c) => c.trim()).join(', ')
        if (!RGB_ALLOWED.has(channels)) out.push(`${name}(${args})`)
      } else if (['url', 'calc', 'min', 'max', 'clamp', 'translate', 'rotate', 'scale'].includes(name)) {
        // not a colour
      } else {
        out.push(`${name}(${args})`)
      }
      i = next
      continue
    }
    const hex = /^#[0-9a-fA-F]{3,8}\b/.exec(rest)
    if (hex) {
      if (!(hex[0].toLowerCase() in HEX_ALLOWED)) out.push(hex[0])
      i += hex[0].length
      continue
    }
    const word = /^[a-zA-Z][a-zA-Z0-9-]*/.exec(rest)
    if (word) {
      const w = word[0].toLowerCase()
      if (NAMED_COLOURS.has(w)) out.push(word[0])
      i += word[0].length
      continue
    }
    i++
  }
  return out
}

/** Every colour in a stylesheet that is not on the allow-list, one line each. */
function literalColourProblems(css: string): string[] {
  const problems: string[] = []
  for (const rule of parseCss(css)) {
    for (const [prop, value] of Object.entries(rule.decls)) {
      if (!COLOUR_PROPERTY.test(prop)) continue
      for (const bad of valueColourProblems(value)) problems.push(`${prop}: literal colour ${bad} is not a token or a documented literal (in ${rule.selectors[0] ?? '?'})`)
    }
  }
  return [...new Set(problems)]
}

/** `fill=` and `stroke=` written in a template are colours too: only `none` and `currentColor` are allowed. */
function attributeColourProblems(template: string): string[] {
  const out: string[] = []
  for (const m of template.matchAll(/(?:^|\s):?(fill|stroke|stop-color|flood-color|color)="([^"]*)"/g)) {
    const values = [...(m[2] as string).matchAll(/'([^']*)'/g)].map((x) => x[1] as string)
    for (const v of values.length ? values : [m[2] as string]) if (!['none', 'currentColor', 'currentcolor'].includes(v) && !/[?:=.\w]+\./.test(v) && /^[#a-zA-Z]/.test(v) && !/^(icon|props)\./.test(v)) out.push(`${m[1]}="${v}"`)
  }
  return out
}

describe('the six files take their colour, weight and size from tokens (home-06, home-07, home-08)', () => {
  test('no off-token colour literal in any of the files (the grey #8c97a8, the ink #717d93, the grounds #090a0f and #12151e are gone)', () => {
    for (const f of FILES) assert.deepEqual(literalColourProblems(sfcStyles(f)), [], f)
  })

  test('no !important and no 800-weight heading in any of the files', () => {
    for (const f of FILES) {
      const css = sfcStyles(f)
      assert.doesNotMatch(css, /!important/, `${f} uses !important`)
      assert.doesNotMatch(css, /font-weight:\s*800/, `${f} sets weight 800 (Figma: Bold 700)`)
    }
  })

  test('CONTROL: the colour check reports a literal in ANY notation (hex, name, rgb, hsl, hwb, lab, lch, oklab, oklch, color, light-dark, inside color-mix, in a var fallback) and passes only the allow-list', () => {
    const bad = (css: string, count = 1): void => assert.equal(literalColourProblems(css).length, count, css)
    bad('.a { color: #8c97a8; }')
    bad('.g { background: radial-gradient(circle, rgba(110, 92, 240, 0.15) 0%, transparent 70%); }')
    bad('.h { color: hsl(250 80% 60%); }')
    bad('.h { color: hwb(250 10% 10%); }')
    // three notations, three problems
    assert.equal(literalColourProblems('.l { color: lab(50% 40 59); } .m { color: lch(50% 40 59); } .n { color: oklab(0.6 0.1 0.1); }').length, 3)
    bad('.o { color: oklch(0.62 0.19 285); }')
    bad('.n { background: rebeccapurple; }')
    bad('.n { border: 1px solid red; }')
    bad('.n { box-shadow: 0 1px 2px Tomato; }')
    bad('.m { background: color-mix(in srgb, #123456 10%, red); }', 2)
    bad('.l { background: light-dark(#fff, #000); }')
    bad('.c { color: color(display-p3 1 0 0); }')
    bad('.v { color: var(--x, #123456); }')
    bad('.v { color: var(--x, tomato); }')
    bad('.v { color: var(oops); }')
    assert.match(literalColourProblems('.a { color: #8c97a8; }')[0] as string, /#8c97a8/)
    // the allow-list
    assert.deepEqual(
      literalColourProblems(
        [
          '.a { color: var(--sc-text-secondary); background: rgba(0, 0, 0, 0.1); box-shadow: 0 1px rgba(5, 8, 15, .7); border: 1px solid #fff; }',
          '.b { fill: color-mix(in srgb, var(--sc-primary) 15%, transparent); color: currentColor; background: transparent; }',
          '.c { background: linear-gradient(135deg, var(--sc-primary), transparent); border: 1px solid var(--sc-border); outline: 2px solid var(--sc-primary); }',
          '.d { color: var(--sc-text, var(--x)); background: url(/a.png) no-repeat center / cover; margin: 0 auto; transform: translateX(-50%); }',
          '.e { border: none; color: inherit; background: none; fill: none; }',
        ].join('\n'),
      ),
      [],
    )
  })

  test('CONTROL: a literal colour in a template attribute is reported; none and currentColor are not', () => {
    assert.deepEqual(attributeColourProblems('<svg fill="red" stroke="#123456"></svg>'), ['fill="red"', 'stroke="#123456"'])
    assert.deepEqual(attributeColourProblems('<svg fill="none" stroke="currentColor"></svg>'), [])
    assert.deepEqual(attributeColourProblems(`<svg :fill="icon.solid ? 'currentColor' : 'none'" :stroke="icon.solid ? 'none' : 'currentColor'"></svg>`), [])
    assert.deepEqual(attributeColourProblems(`<svg :fill="icon.solid ? 'tomato' : 'none'"></svg>`), ['fill="tomato"'])
  })

  test('no template in the files writes a literal colour into fill, stroke or color', () => {
    for (const f of FILES) assert.deepEqual(attributeColourProblems(parse(read(f)).descriptor.template?.content ?? ''), [], f)
  })
})

describe('the layout numbers the audit measured (home-04, 05, 06, 08, 16, 26, 41), at 1440 wide', () => {
  const env = { width: 1440 } as const
  const root = (css: string[]): Record<string, string> => rootProperties(parseCss(css.join('\n')), env)
  const tokens = readFileSync(path.join(SRC, 'assets/styles/tokens.css'), 'utf8')
  const main = readFileSync(path.join(SRC, 'assets/styles/main.css'), 'utf8')
  const home = parseCss(sfcStyles('views/HomeView.vue'))
  const props = root([tokens, main])
  const at = (classes: string[]): Record<string, string> => effective(home, classes, env)
  const padBlock = (d: Record<string, string>): number => {
    const v = d['padding-block'] ?? d['padding']?.split(/\s+/)[0] ?? ''
    return resolvePx(v, props)
  }

  test('the container resolves to 1248 of content at 1440 (the shared rule, 96px gutters)', () => {
    const sharedContainer = effective(parseCss(main), ['container'], env)
    assert.equal(resolvePx((sharedContainer['max-width'] as string), props), 1440)
    assert.equal(resolvePx(props['--gutter'] as string, props), 96)
    assert.equal(resolvePx(props['--content-max'] as string, props), 1248)
  })

  test('section rhythm: 88 on Features and How it works, 90 on the rest (the one band 89 inside a 1px rule), hero 96 above and 72 below', () => {
    assert.equal(padBlock(at(['features-section'])), 88)
    assert.equal(padBlock(at(['steps-section'])), 88)
    for (const c of ['outputs-section', 'pricing-section', 'faq-section', 'final-cta-section']) {
      assert.equal(padBlock(at([c])), 90, c)
    }
    // The two bands have a 1px edge rule, and Figma draws the stroke inside the frame: 89 + 1 = 90.
    for (const c of ['reliability-section']) assert.equal(padBlock(at([c])), 89, c)
    const hero = at(['hero-section'])
    assert.deepEqual(hero['padding'], '96px 0 72px', 'hero padding')
  })

  test('grid gaps: features 20, reliability 28, steps 28; showcase columns 470 and the rest at gap 72', () => {
    const gap = (c: string): number => resolvePx(at([c])['gap'] ?? '', props)
    assert.equal(gap('features-grid'), 20)
    assert.equal(gap('reliability-grid'), 28)
    assert.equal(gap('steps-grid'), 28)
    const outputs = at(['outputs-layout'])
    assert.equal(outputs['grid-template-columns'], '470px minmax(0, 1fr)')
    assert.equal(resolvePx(outputs['gap'] ?? '', props), 72)
    assert.equal(outputs['align-items'], 'center', 'Figma centres the columns: the 306px window sits 15px below the 336px text column\'s top')
  })

  test('Reliability is a full-width panel band with edge rules; its cards sit on the base ground', () => {
    for (const c of ['reliability-section']) {
      const d = at([c])
      assert.equal(d['background'], 'var(--sc-surface)', c)
      assert.match(d['border-block'] ?? `${d['border-top'] ?? ''} ${d['border-bottom'] ?? ''}`, /1px solid var\(--sc-border\)/, c)
    }
    assert.equal(effective(parseCss(sfcStyles('components/ReliabilityPillar.vue')), ['pillar-card'], env)['background'], 'var(--sc-base)')
  })

  test('type: H1 is the 60/64 Bold token; section titles are Bold 700 at 40, 42 (Reliability) and 38 (FAQ); the CTA title is 44/50', () => {
    assert.equal(at(['hero-title'])['font'], 'var(--font-h1)')
    assert.equal(at(['hero-title'])['letter-spacing'], '0')
    const size = (c: string): string => at([c])['font-size'] ?? ''
    const weight = (c: string): string => at([c])['font-weight'] ?? ''
    assert.equal(size('section-title'), '40px')
    assert.equal(weight('section-title'), '700')
    assert.equal(at(['section-title', 'is-reliability'])['font'] ?? at(['section-title', 'is-reliability'])['font-size'], 'var(--font-h2)')
    assert.equal(at(['section-title', 'is-compact'])['font-size'], '38px')
    assert.equal(size('outputs-title'), '40px')
    assert.equal(size('cta-title'), '44px')
    assert.equal(at(['cta-title'])['line-height'], '50px')
    assert.equal(weight('cta-title'), '700')
  })

  test('the final band is the CTA gradient token with no outer shadow, 1248 wide, radius 24', () => {
    const d = at(['final-cta-card'])
    assert.equal(d['background'], 'var(--gradient-cta)')
    assert.equal(d['box-shadow'], undefined)
    assert.equal(d['border-radius'], '24px')
    assert.equal(d['padding'], '64px 48px')
  })

  test('the hero button row is centred, so the quiet 47px button is not stretched to the 49px solid one (Cody, PR 172)', () => {
    assert.equal(at(['hero-actions'])['align-items'], 'center')
    assert.equal(at(['cta-btn-group'])['align-items'], 'center')
  })
})

describe('the FAQ skin: Home draws the Figma rows over the shared accordion until its defaults change', () => {
  const skin = parseCss(sfcStyles('views/HomeView.vue'))
  const rule = (selector: string): Record<string, string> => effectiveExact(skin, selector, { width: 1440 })

  test('the three overrides exist with Figma\'s numbers (478:155: questions 18/600, answers 15.5/24, 10px under an open question)', () => {
    assert.equal(rule('.faq-wrapper :deep(.faq-question)')['font-size'], '18px')
    assert.equal(rule('.faq-wrapper :deep(.faq-item.open .faq-question)')['padding-bottom'], '10px')
    const answer = rule('.faq-wrapper :deep(.faq-answer p)')
    assert.deepEqual([answer['font-size'], answer['line-height']], ['15.5px', '24px'])
  })

  test('every class the skin reaches into exists in the rendered accordion, so renaming one in FaqAccordion fails here instead of silently dropping the skin', () => {
    const faq = findAll(page, (e) => hasClass(e, 'faq-wrapper'))[0] as El
    assert.ok(faq, 'no .faq-wrapper')
    assert.ok(findAll(faq, (e) => hasClass(e, 'faq-question') && e.tag === 'button').length === 5, '.faq-question buttons')
    assert.ok(findAll(faq, (e) => hasClass(e, 'faq-item') && hasClass(e, 'open')).length === 1, 'one open .faq-item')
    assert.ok(findAll(faq, (e) => hasClass(e, 'faq-item') && hasClass(e, 'open')).every((item) => findAll(item, (e) => hasClass(e, 'faq-question')).length === 1), 'an open item holds its .faq-question')
    assert.ok(findAll(faq, (e) => hasClass(e, 'faq-answer')).every((a) => findAll(a, (e) => e.tag === 'p').length === 1), '.faq-answer holds a p')
    assert.equal(findAll(faq, (e) => hasClass(e, 'faq-answer')).length, 5)
  })
})

describe('contrast of the inks the page chooses (home-07, home-44)', () => {
  const tokens = readFileSync(path.join(SRC, 'assets/styles/tokens.css'), 'utf8')
  const t = (name: string): string => new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`).exec(tokens)?.[1] as string

  test('secondary copy on the base, surface and elevated grounds, and white on the brand fill, clear 4.5:1', () => {
    for (const ground of ['--sc-base', '--sc-surface', '--sc-elevated']) {
      assert.ok(contrast(t('--sc-text-secondary'), t(ground)) >= 4.5, `secondary on ${ground}`)
    }
    assert.ok(contrast('#ffffff', t('--sc-primary')) >= 4.5, 'white on --sc-primary (step markers)')
    assert.ok(contrast(t('--sc-primary'), '#ffffff') >= 4.5, 'the inverse button label')
  })

  test('the status inks on the elevated chip, and the dark ink on the green and gold fills, clear 4.5:1', () => {
    for (const ink of ['--sc-live', '--sc-preview', '--sc-warn']) assert.ok(contrast(t(ink), t('--sc-elevated')) >= 4.5, `${ink} on --sc-elevated`)
    for (const fill of ['--sc-preview', '--sc-gold']) assert.ok(contrast(t('--sc-base'), t(fill)) >= 4.5, `dark ink on ${fill}`)
    assert.ok(contrast('#a5b4fc', '#0d0f14') >= 4.5, 'the hero pill ink on its darkened pill')
  })

  test('the CTA band copy is white: Figma\'s #dbe0fa is 3.61:1 on the lightest end of the gradient, white is 4.7:1', () => {
    assert.ok(contrast('#dbe0fa', t('--sc-primary')) < 4.5, 'the reason for the deviation still holds')
    assert.ok(contrast('#ffffff', t('--sc-primary')) >= 4.5)
    assert.doesNotMatch(sfcStyles('views/HomeView.vue').replace(/\/\*[\s\S]*?\*\//g, ''), /#dbe0fa/i, 'the sub copy uses Figma\'s lighter ink again')
  })
})
