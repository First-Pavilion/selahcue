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
 * backed part only; the FORBIDDEN list is the claims no change to this page may add (owner decision:
 * honest content wins). Claims the live page already made and no finding replaces (the price, the
 * testimonials, the platform versions) are deliberately NOT pinned here, in either direction: removing
 * them is ClickUp 17tnw2b0x3h, and a test that vouched for them would hold a bug in place.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test, { after, before, describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { parse } from 'vue/compiler-sfc'

import { effective, parseCss, resolvePx, rootProperties, styleOf, contrast } from './fixtures/cssSource.ts'
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
  'components/TestimonialCard.vue',
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
  'testimonials-section',
  'faq-section',
  'final-cta-section',
] as const

describe('the page is the nine designed sections, in Figma\'s order, on the shared container', () => {
  test('nine sections, in order, each inside the shared .container (the local container rule is gone)', () => {
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
      'Simple pricing. Cancel anytime.',
      'Run by volunteers. Trusted on Sunday.',
      'Questions, answered',
      'Ready to run your best service yet?',
    ])
    assert.equal(textOf(findAll(page, (e) => e.tag === 'h1')[0] as El), 'Run your service with total confidence.')
  })
})

describe('the six section labels are plain eyebrows, not chips', () => {
  test('FEATURES, WHY SELAHCUE, SCREENS & OUTPUTS, HOW IT WORKS, PRICING and TESTIMONIALS use variant eyebrow', () => {
    const eyebrows = findAll(page, (e) => hasClass(e, 'variant-eyebrow')).map((e) => textOf(e))
    assert.deepEqual(eyebrows, ['FEATURES', 'WHY SELAHCUE', 'SCREENS & OUTPUTS', 'HOW IT WORKS', 'PRICING', 'TESTIMONIALS'])
  })

  test('no filled "accent" chip is left except the shared MOST POPULAR chip, and no gradient button remains', () => {
    const chips = findAll(page, (e) => hasClass(e, 'variant-accent')).map((e) => textOf(e))
    assert.deepEqual(chips.filter((c) => c !== 'MOST POPULAR'), [])
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

  test('card, step and plan titles are h3 under their section h2; output rows and testimonial names are not headings at all', () => {
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
      'Control from anywhere',
      'Free',
      'Pro',
      'Church',
    ])
    assert.deepEqual(findAll(page, (e) => e.tag === 'h4' || e.tag === 'h5' || e.tag === 'h6'), [])
    for (const name of ['Sarah Jenkins', 'Mark Davis', 'Pastor Paul Miller', 'Audience — Main', 'Stage Display', 'Livestream Program']) {
      const asHeading = findAll(page, (e) => /^h[1-6]$/.test(e.tag) && textOf(e) === name)
      assert.deepEqual(asHeading, [], `${name} is a heading`)
    }
  })

  test('the two mocks add no heading to the outline', () => {
    for (const mock of findAll(page, (e) => e.attrs['role'] === 'img')) {
      assert.deepEqual(findAll(mock, (e) => /^h[1-6]$/.test(e.tag)), [], textOf(mock).slice(0, 40))
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
    assert.match(mark.attrs['style'] ?? '', /--mark-size:\s*18px/)
    assert.equal(textOf(pill), 'Church presentation, reengineered')
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
    assert.match(textOf(note), /not available yet/i)
    assert.equal(findAll(page, (e) => e.tag === 'a' && e.attrs['href'] === '#demo').length, 0)
  })

  test('the plans: Free goes to /download, Church to /contact, Pro has no destination and says "Not available yet"', () => {
    const cards = findAll(section(page, 'pricing-section'), (e) => hasClass(e, 'pricing-card'))
    assert.equal(cards.length, 3)
    const cta = (card: El): El => findAll(card, (e) => hasClass(e, 'ui-button'))[0] as El
    const [free, pro, church] = cards as [El, El, El]
    assert.equal(cta(free).tag, 'a')
    assert.equal(cta(free).attrs['href'], '/download')
    assert.equal(textOf(cta(free)), 'Download free')
    assert.equal(cta(church).tag, 'a')
    assert.equal(cta(church).attrs['href'], '/contact')
    assert.equal(textOf(cta(church)), 'Talk to us')
    assert.equal(cta(pro).tag, 'button')
    assert.ok(cta(pro).attrs['disabled'] !== undefined)
    assert.equal(textOf(cta(pro)), 'Get Pro')
    assert.match(textOf(pro), /Not available yet/)
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

/** The page's words, per section, joined; the ledger is compared against these. */
const words = (cls: string): string => textOf(section(page, cls))

describe('copy follows the ledger: Figma\'s wording where the repo backs it', () => {
  test('hero', () => {
    const t = words('hero-section')
    for (const line of [
      'Church presentation, reengineered',
      'SelahCue is the offline-first presentation & ministry-assistance app that never blanks the screen — scripture, songs, timers, stage display, and NDI outputs, controlled from anywhere.',
      'Download free',
      'Watch 2-min demo',
      'Free to start · Works fully offline · Windows, macOS & mobile control',
    ]) assert.ok(t.includes(line), `hero is missing: ${line}`)
  })

  test('features (home-20): the subtitle and six blurbs, with the two overclaims narrowed', () => {
    const t = words('features-section')
    for (const line of [
      'One app for the whole ministry moment — from planning the order of service to the last slide, on stage and online.',
      'Stage scripture, songs, and slides in Preview, then Go Live to the audience — the output never blanks, even on a fault.',
      'A bundled public-domain Bible with instant reference parsing and keyword search.',
      'Build the order of service, run countdowns, and keep every segment on time from the console or your phone.',
      "A dedicated speaker view — current line, what's next, and the service timer — that the audience never sees.",
      'Broadcast your program as an NDI source for OBS or vMix, with per-output orientation, scaling, mirror, and visible layers.',
      'AI that assists but never gates: a live transcript and spoken-scripture suggestions, on your machine by default.',
    ]) assert.ok(t.includes(line), `features is missing: ${line}`)
  })

  test('reliability (home-21): eyebrow, subtitle and three pillars, with no NFR id, no number and no metric badge', () => {
    const t = words('reliability-section')
    for (const line of [
      'WHY SELAHCUE',
      "Sunday morning doesn't wait for a spinning cursor. SelahCue is engineered so the audience output is always up — reliable, offline, and fast.",
      'No component failure — a bad slide, a lost GPU, a dropped controller — is ever allowed to black the live output.',
      'Everything runs on-device — no internet and no cloud dependency during the service. It just works.',
      'Starts fast and keeps memory bounded. No runaway caches, no creeping slowdown.',
    ]) assert.ok(t.includes(line), `reliability is missing: ${line}`)
    assert.doesNotMatch(t, /NFR-/)
    for (const metric of ['0 Blanks', '100% Offline', '≤3s Start']) assert.ok(!t.toLowerCase().includes(metric.toLowerCase()), `the frame draws no metric badge: ${metric}`)
  })

  test('showcase (home-24): body and the three one-line checks', () => {
    const t = words('outputs-section')
    for (const line of [
      'SCREENS & OUTPUTS',
      'One live moment, every output',
      'Send the same live content to your projector, a stage confidence monitor, and an NDI stream — each with its own theme, orientation, scaling, and visible layers.',
      'Audience projector — the program the room sees',
      'Stage display — current, next & timer, for the speaker only',
      'NDI output — broadcast to OBS, vMix, or another machine',
    ]) assert.ok(t.includes(line), `showcase is missing: ${line}`)
    const items = findAll(section(page, 'outputs-section'), (e) => e.tag === 'li').map((li) => textOf(li))
    assert.equal(items.length, 3, 'three single-line checks, no second line')
  })

  test('how it works (home-28): subtitle and three step bodies, as an ordered list', () => {
    const steps = section(page, 'steps-section')
    const t = textOf(steps)
    for (const line of [
      'From an empty plan to a running service in minutes — no manual, no setup weekend.',
      'Add songs, scripture, and sections to the order of service. Set countdowns and give any item its own theme.',
      'Stage the next item in Preview, then Go Live. The audience, stage, and NDI outputs all update together.',
      'Drive it from the console — or pair your phone over the local network. No internet, no lag, no surprises.',
    ]) assert.ok(t.includes(line), `steps is missing: ${line}`)
    assert.equal(findAll(steps, (e) => e.tag === 'ol').length, 1, 'the steps are an ordered list')
    assert.equal(findAll(steps, (e) => e.tag === 'li').length, 3)
  })

  test('pricing (home-29, home-31): $0 / forever, Figma\'s descriptions and the bullets the repo backs', () => {
    const cards = findAll(section(page, 'pricing-section'), (e) => hasClass(e, 'pricing-card')).map((c) => textOf(c))
    assert.match(textOf(section(page, 'pricing-section')), /Start free, upgrade when you're ready, and cancel anytime — it still runs fully offline on Sunday\./)
    const [free, pro, church] = cards as [string, string, string]
    assert.ok(free.includes('$0 / forever'), `Free reads: ${free.slice(0, 60)}`)
    assert.ok(!free.includes('/ month'), 'Free is not a monthly charge')
    for (const line of ['Everything to run a service on one machine.', 'Live audience output + stage display', 'Bundled public-domain scripture + search', 'Service plans, timers & themes']) assert.ok(free.includes(line), `Free is missing: ${line}`)
    for (const line of ['For multi-output and streaming churches.', 'Everything in Free', 'NDI + multiple simultaneous outputs', 'Mobile control over your local network']) assert.ok(pro.includes(line), `Pro is missing: ${line}`)
    for (const line of ['For multi-site teams and larger ministries.', 'Everything in Pro', 'Multi-campus / site licensing']) assert.ok(church.includes(line), `Church is missing: ${line}`)
  })

  test('testimonials (home-35): typographic quotes and the "·" role format; the label stays TESTIMONIALS', () => {
    const t = section(page, 'testimonials-section')
    const quotes = findAll(t, (e) => e.tag === 'blockquote').map((q) => textOf(q))
    assert.equal(quotes.length, 3)
    for (const q of quotes) assert.match(q, /^“.+”$/, `a quote without typographic marks: ${q}`)
    const roles = findAll(t, (e) => e.tag === 'figcaption').map((c) => textOf(c))
    for (const r of roles) assert.match(r, / · /, `role without the "·" format: ${r}`)
    assert.ok(!roles.join().includes(' @ '), 'the "@" format is gone')
    assert.ok(textOf(t).includes('TESTIMONIALS'))
    assert.ok(!textOf(t).includes('FROM THE TECH BOOTH'), 'that label would attribute the quotes to tech teams (home-36 is open)')
  })

  test('faq (home-38): the five Figma questions, in order, with the answers the repo backs', () => {
    const faq = section(page, 'faq-section')
    const qs = findAll(faq, (e) => e.tag === 'button').map((b) => textOf(b))
    assert.deepEqual(qs, [
      'Do I need an internet connection?',
      'Which platforms are supported?',
      'Can I use my own songs, slides, and designs?',
      'What is NDI, and do I need it?',
      'How does billing work?',
    ])
    const t = textOf(faq)
    for (const line of [
      'No. SelahCue is offline-first — the whole service runs on-device, so a dropped internet connection never stops it.',
      'Yes. Build multi-slide song lyrics, stage any scripture, and design your own slide templates in the Theme Designer.',
      "NDI sends your program video over the local network to software like OBS or vMix — no capture card required. It's optional.",
      'SelahCue Pro is a simple monthly subscription; the Free plan is free forever. Cancel anytime — and the app keeps running fully offline during your service either way.',
    ]) assert.ok(t.includes(line), `faq is missing: ${line}`)
    assert.ok(t.includes('Additionally, you can pair any iOS or Android phone'), 'the platforms answer is kept as it is (home-38, 40, 45 are open)')
  })

  test('final band: heading, sub, and the two buttons', () => {
    const t = words('final-cta-section')
    for (const line of ['Ready to run your best service yet?', 'Start free and go live this Sunday. Cancel anytime — and it runs fully offline when it matters most.', 'Download free', 'See pricing']) {
      assert.ok(t.includes(line), `final band is missing: ${line}`)
    }
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
  { re: /Linux/i, why: 'Linux is not drawn in Figma and no installer is confirmed', sample: 'Linux is on the roadmap' },
  { re: /installer|\.msi|\.dmg|\.exe/i, why: 'no downloadable installer is claimed', sample: 'download the installer' },
  { re: /FROM THE TECH BOOTH/i, why: 'attributes the live quotes to tech teams (home-36)', sample: 'FROM THE TECH BOOTH' },
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
    const honest = 'Starts fast and keeps memory bounded. NDI output for OBS or vMix. Free plan is free forever.'
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

function hexProblems(css: string): string[] {
  const found = new Set([...css.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/#[0-9a-fA-F]{3,8}\b/g)].map((m) => m[0].toLowerCase()))
  return [...found].filter((h) => !(h in HEX_ALLOWED)).map((h) => `literal colour ${h} is not a token or a documented Figma literal`)
}

describe('the six files take their colour, weight and size from tokens (home-06, home-07, home-08)', () => {
  test('no off-token colour literal in any of the files (the grey #8c97a8, the ink #717d93, the grounds #090a0f and #12151e are gone)', () => {
    for (const f of FILES) assert.deepEqual(hexProblems(sfcStyles(f)), [], f)
  })

  test('no !important and no 800-weight heading in any of the files', () => {
    for (const f of FILES) {
      const css = sfcStyles(f)
      assert.doesNotMatch(css, /!important/, `${f} uses !important`)
      assert.doesNotMatch(css, /font-weight:\s*800/, `${f} sets weight 800 (Figma: Bold 700)`)
    }
  })

  test('CONTROL: the colour check reports a stray literal and passes tokens, rgba and the documented ones', () => {
    assert.deepEqual(hexProblems('.a { color: #8c97a8; } .b { color: #FFF }'), ['literal colour #8c97a8 is not a token or a documented Figma literal'])
    assert.deepEqual(hexProblems('.a { color: var(--sc-text-secondary); background: rgba(110, 92, 240, 0.15); border: 1px solid #fff; }'), [])
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

  test('section rhythm: 88 on Features and How it works, 90 on the rest (the two bands 89 inside a 1px rule), hero 96 above and 72 below', () => {
    assert.equal(padBlock(at(['features-section'])), 88)
    assert.equal(padBlock(at(['steps-section'])), 88)
    for (const c of ['outputs-section', 'pricing-section', 'faq-section', 'final-cta-section']) {
      assert.equal(padBlock(at([c])), 90, c)
    }
    // The two bands have a 1px edge rule, and Figma draws the stroke inside the frame: 89 + 1 = 90.
    for (const c of ['reliability-section', 'testimonials-section']) assert.equal(padBlock(at([c])), 89, c)
    const hero = at(['hero-section'])
    assert.deepEqual(hero['padding'], '96px 0 72px', 'hero padding')
  })

  test('grid gaps: features 20, reliability 28, steps 28, pricing 24, testimonials 24; showcase columns 470 and the rest at gap 72', () => {
    const gap = (c: string): number => resolvePx(at([c])['gap'] ?? '', props)
    assert.equal(gap('features-grid'), 20)
    assert.equal(gap('reliability-grid'), 28)
    assert.equal(gap('steps-grid'), 28)
    assert.equal(gap('pricing-grid'), 24)
    assert.equal(gap('testimonials-grid'), 24)
    const outputs = at(['outputs-layout'])
    assert.equal(outputs['grid-template-columns'], '470px minmax(0, 1fr)')
    assert.equal(resolvePx(outputs['gap'] ?? '', props), 72)
    assert.equal(outputs['align-items'], 'center', 'Figma centres the columns: the 306px window sits 15px below the 336px text column\'s top')
  })

  test('Reliability and Testimonials are full-width panel bands with edge rules; their cards sit on the base ground', () => {
    for (const c of ['reliability-section', 'testimonials-section']) {
      const d = at([c])
      assert.equal(d['background'], 'var(--sc-surface)', c)
      assert.match(d['border-block'] ?? `${d['border-top'] ?? ''} ${d['border-bottom'] ?? ''}`, /1px solid var\(--sc-border\)/, c)
    }
    assert.equal(effective(parseCss(sfcStyles('components/ReliabilityPillar.vue')), ['pillar-card'], env)['background'], 'var(--sc-base)')
    assert.equal(effective(parseCss(sfcStyles('components/TestimonialCard.vue')), ['testimonial-card'], env)['background'], 'var(--sc-base)')
  })

  test('type: H1 is the 60/64 Bold token; section titles are Bold 700 at 40, 42 (Reliability) and 38 (Testimonials, FAQ); the CTA title is 44/50', () => {
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

describe('contrast of the inks the page chooses (home-07, home-44)', () => {
  const tokens = readFileSync(path.join(SRC, 'assets/styles/tokens.css'), 'utf8')
  const t = (name: string): string => new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`).exec(tokens)?.[1] as string

  test('secondary copy on the base, surface and elevated grounds, and white on the brand fill, clear 4.5:1', () => {
    for (const ground of ['--sc-base', '--sc-surface', '--sc-elevated']) {
      assert.ok(contrast(t('--sc-text-secondary'), t(ground)) >= 4.5, `secondary on ${ground}`)
    }
    assert.ok(contrast('#ffffff', t('--sc-primary')) >= 4.5, 'white on --sc-primary (step markers, blue avatar)')
    assert.ok(contrast(t('--sc-primary'), '#ffffff') >= 4.5, 'the inverse button label')
  })

  test('the status inks on the elevated chip, and the dark initials on the green and gold avatars, clear 4.5:1', () => {
    for (const ink of ['--sc-live', '--sc-preview', '--sc-warn']) assert.ok(contrast(t(ink), t('--sc-elevated')) >= 4.5, `${ink} on --sc-elevated`)
    for (const fill of ['--sc-preview', '--sc-gold']) assert.ok(contrast(t('--sc-base'), t(fill)) >= 4.5, `dark initials on ${fill}`)
    assert.ok(contrast('#a5b4fc', '#0d0f14') >= 4.5, 'the hero pill ink on its darkened pill')
  })

  test('the avatar initials: white on the brand fill, the dark ink on the green and gold fills (as styled, not only as computed)', () => {
    const css = parseCss(sfcStyles('components/TestimonialCard.vue'))
    const env = { width: 1440 }
    assert.equal(effective(css, ['avatar-circle'], env)['color'], '#fff')
    assert.equal(effective(css, ['avatar-circle', 'blue'], env)['background'], 'var(--sc-primary)')
    for (const tone of ['green', 'amber']) assert.equal(effective(css, ['avatar-circle', tone], env)['color'], 'var(--sc-base)', tone)
  })

  test('the CTA band copy is white: Figma\'s #dbe0fa is 3.61:1 on the lightest end of the gradient, white is 4.7:1', () => {
    assert.ok(contrast('#dbe0fa', t('--sc-primary')) < 4.5, 'the reason for the deviation still holds')
    assert.ok(contrast('#ffffff', t('--sc-primary')) >= 4.5)
    assert.doesNotMatch(sfcStyles('views/HomeView.vue').replace(/\/\*[\s\S]*?\*\//g, ''), /#dbe0fa/i, 'the sub copy uses Figma\'s lighter ink again')
  })
})
