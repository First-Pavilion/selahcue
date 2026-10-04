/**
 * The nine secondary pages (Contact, Support, Docs, Changelog, Blog, Careers, Privacy, Terms,
 * Affiliates) against the Figma fidelity audit's findings: ClickUp 17tnw2b2cez.
 *
 * Source checks (Vue's own SFC compiler reads the real files) and render checks (Vite compiles
 * the real views, Vue renders them to a string, a real router is installed). What neither can
 * see (computed colour, geometry, real focus movement) is asserted in a browser by
 * `tests/secondary_pages_headless.py` and measured by the marketing visual-parity harness.
 *
 * EVERY PREDICATE HERE HAS ONE DEFINITION and its positive control consumes THAT definition
 * (the rule `authViews.test.ts` records after a ban and the control that vouched for it were two
 * copies and the ban went dead). A control that does not fail on a planted fault is decoration,
 * so each group ends with the fault planted.
 *
 * What is guarded, in the order of the ticket:
 *
 *   - no heading level is skipped on any of the nine pages (Contact went h1 to h4 and Changelog
 *     h1 to h3: contact-bug-01, changelog-bug-01);
 *   - no page passes `variant="gradient"` to a button (a temporary alias PR 172 left for these
 *     pages to leave), and none declares its own container rule (1140, 1200 and 1000 wide
 *     before; the shared `.container` is 1248 with 96/48/20 gutters);
 *   - no page ADDS a claim: the strings the audit marks unbacked in Figma (addresses nobody
 *     confirmed, reply times, commission rates) are absent. Removing claims that were already
 *     live is ClickUp 17tnw2b0x3h and is not asserted here;
 *   - each page has the structure its Figma frame draws.
 */
import assert from 'node:assert/strict'
import test, { after, before, describe } from 'node:test'

import type { ViteDevServer } from 'vite'

import { elementsOf, prop, readSrc, styleOf, valueOf } from './fixtures/sfcSource.ts'
import {
  classesOf,
  headingsOf,
  outlineProblems,
  renderView,
  startViewServer,
  tagsOf,
  textOf,
  withClass,
  type Heading,
  type Tag,
} from './fixtures/viewRender.ts'

/** Grows as each page is brought to its frame; the final list is all nine. */
const PAGES = [
  { file: 'ContactView.vue', route: '/contact' },
  { file: 'SupportView.vue', route: '/support' },
  { file: 'DocsView.vue', route: '/docs' },
] as const

let server: ViteDevServer
const rendered = new Map<string, string>()

before(async () => {
  server = await startViewServer()
})

after(async () => {
  await server?.close()
})

async function html(file: string): Promise<string> {
  const known = rendered.get(file)
  if (known !== undefined) return known
  const page = PAGES.find((p) => p.file === file)
  assert.ok(page, `${file} is not one of the nine pages`)
  const out = await renderView(server, file, page.route)
  rendered.set(file, out)
  return out
}

// --------------------------------------------------------------------------- shared predicates

/** `<UiButton variant="gradient">`, static or as a bound literal. One definition, used by the control. */
function gradientButtons(sfc: string): string[] {
  return elementsOf(sfc)
    .filter((el) => el.tag === 'UiButton' || el.tag === 'ui-button')
    .filter((el) => valueOf(prop(el, 'variant')) === 'gradient')
    .map((el) => `<UiButton variant="gradient"> (${el.tag})`)
}

/**
 * A rule in the view's own <style> whose selector is the shared container's name. The page must
 * adopt the global `.container` (1248 content, stepped gutters), not redeclare it.
 */
function localContainerRules(sfc: string): string[] {
  const css = styleOf(sfc)
  const found: string[] = []
  for (const m of css.matchAll(/(^|[},\s])(\.container)\s*(?:[,{:.[ >+~])/g)) found.push(m[2] as string)
  return found
}

/**
 * A rule in the view's own <style> that colours text with `--sc-text-muted`. Figma's text/muted
 * (#9aa4b2) maps to `--sc-text-secondary` (AUTH-LANDING-PAGES-HANDOFF 2.2); the build's muted token
 * is a quieter grey that the audit found in the wrong role on meta lines, dates, placeholders and
 * counters (contact-13, support-10, careers-05, docs-07, changelog-06, blog-07).
 */
function mutedInkRules(sfc: string): string[] {
  const out: string[] = []
  for (const m of styleOf(sfc).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (/(^|[;\s])color\s*:\s*var\(--sc-text-muted\)/.test(m[2] ?? '')) out.push((m[1] ?? '').trim())
  }
  return out
}

/** Whether the template puts the shared `.container` on any element. */
function usesSharedContainer(sfc: string): boolean {
  return elementsOf(sfc).some((el) => (valueOf(prop(el, 'class')) ?? '').split(/\s+/).includes('container'))
}

/** Strings the audit marks unbacked in a Figma frame; none may be added to a page. */
const UNBACKED_FIGMA_STRINGS = [
  'hello@selahcue.app',
  'community.selahcue.app',
  'within one business day',
  'We usually reply',
  'Response time',
  '10 minutes',
  'Windows & macOS install',
] as const

function addedClaims(text: string): string[] {
  const lower = text.toLowerCase()
  return UNBACKED_FIGMA_STRINGS.filter((s) => lower.includes(s.toLowerCase()))
}

// --------------------------------------------------------------------------- every page

describe('the nine pages: heading outline, buttons and container', () => {
  for (const { file } of PAGES) {
    test(`${file}: no heading level is skipped, and there is one h1`, async () => {
      const problems = outlineProblems(headingsOf(await html(file)))
      assert.deepEqual(problems, [], `${file}: ${problems.join('; ')}`)
    })

    test(`${file}: no button asks for the legacy gradient variant`, () => {
      assert.deepEqual(gradientButtons(readSrc(`views/${file}`)), [], `${file} still passes variant="gradient" (PR 172 left it as a temporary alias)`)
    })

    test(`${file}: no local container rule`, () => {
      assert.deepEqual(localContainerRules(readSrc(`views/${file}`)), [], `${file} redeclares .container in its own style block`)
    })

    test(`${file}: no text is coloured with the muted ink (the secondary ink is Figma's text/muted)`, () => {
      assert.deepEqual(mutedInkRules(readSrc(`views/${file}`)), [], `${file} colours text with --sc-text-muted`)
    })

    test(`${file}: no claim the audit marks unbacked is added`, async () => {
      assert.deepEqual(addedClaims(textOf(await html(file))), [], `${file} shows a string Figma draws and the repo does not back`)
    })
  }

  for (const { file } of PAGES.filter((p) => p.file !== 'PrivacyView.vue' && p.file !== 'TermsView.vue')) {
    test(`${file}: the page body sits in the shared .container`, () => {
      assert.ok(usesSharedContainer(readSrc(`views/${file}`)), `${file} does not use the shared .container`)
    })
  }

  test('CONTROL: the outline predicate reports a skipped level, a second h1 and a page that starts below h1', () => {
    const h = (level: number, text = `h${level}`): Heading => ({ level, text, at: 0 })
    assert.deepEqual(outlineProblems([h(1), h(2), h(3), h(2), h(3)]), [])
    assert.equal(outlineProblems([h(1), h(4)]).length, 1, 'h1 then h4 must be reported (contact-bug-01)')
    assert.equal(outlineProblems([h(1), h(3), h(3)]).length, 1, 'h1 then h3 must be reported (changelog-bug-01), once, not once per h3')
    assert.equal(outlineProblems([h(1), h(2), h(1)]).length, 1, 'a second h1 is reported')
    assert.equal(outlineProblems([h(2), h(3)]).length, 2, 'a page that starts at h2 is reported twice: no h1, and not first')
    assert.deepEqual(outlineProblems([]), ['the page has no headings at all'])
  })

  test('CONTROL: headingsOf reads nested markup and attributes', () => {
    const got = headingsOf('<h1 class="a" id="x">Let<span> us</span> talk</h1><div><h2>Two</h2></div>')
    assert.deepEqual(got.map((x) => [x.level, x.text]), [[1, 'Let us talk'], [2, 'Two']])
  })

  test('CONTROL: the muted-ink predicate fires on a planted rule and not on a border or background', () => {
    assert.deepEqual(mutedInkRules('<template><p/></template><style scoped>.meta { font-size: 13px; color: var(--sc-text-muted); }\n.ok { color: var(--sc-text-secondary); }\n.b { border-color: var(--sc-text-muted); }</style>'), ['.meta'])
  })

  test('CONTROL: the gradient, container and claim predicates fire on a planted fault', () => {
    const planted = `<template><UiButton variant="gradient">Go</UiButton><UiButton :variant="'gradient'">Go</UiButton><UiButton variant="primary">ok</UiButton></template>
<style scoped>.container { max-width: 1140px; }</style>`
    assert.equal(gradientButtons(planted).length, 2)
    assert.equal(localContainerRules(planted).length, 1)
    assert.equal(localContainerRules('<template><p/></template><style scoped>.container-fluid { margin: 0 }\n.page .info-container { x: y }</style>').length, 0, 'a different class that merely contains the word is not the shared container')
    assert.ok(!usesSharedContainer('<template><div class="contact-page"><p/></div></template>'))
    assert.ok(usesSharedContainer('<template><div class="hero container"><p/></div></template>'))
    assert.deepEqual(addedClaims('Mail hello@selahcue.app, we usually reply fast. Mon-Fri, Within one business day.'), ['hello@selahcue.app', 'within one business day', 'We usually reply'])
    assert.deepEqual(addedClaims('Nothing here is a claim.'), [])
  })
})

// --------------------------------------------------------------------------- Contact

describe('Contact (497:124): centred hero, then the form, then the method cards', () => {
  test('the page opens with the centred hero: a CONTACT pill, h1 "Let\'s talk" and a subline (contact-01)', async () => {
    const page = await html('ContactView.vue')
    const [h1] = headingsOf(page)
    assert.equal(h1?.level, 1)
    assert.equal(h1?.text, "Let's talk")
    const text = textOf(page)
    assert.ok(text.includes('CONTACT'), 'the eyebrow pill reads CONTACT')
    // The hero comes before the form and before every method card.
    assert.ok(page.indexOf("Let's talk") < page.indexOf('<form'), 'the hero is above the form')
  })

  test('the form is first in the DOM, so Tab order is form then cards (contact-02)', async () => {
    const page = await html('ContactView.vue')
    const formAt = page.indexOf('<form')
    const firstCardLink = tagsOf(page).find((t) => t.name === 'a' && (t.attrs['href'] ?? '') !== '' && t.at > formAt)
    const firstControl = tagsOf(page).find((t) => t.name === 'input' || t.name === 'textarea')
    assert.ok(formAt > 0 && firstControl && firstCardLink, 'form, a control and a card link all exist')
    assert.ok(firstControl.at < firstCardLink.at, 'the first field comes before the first card link')
    // Nothing focusable precedes the first field except the (absent here) site chrome.
    const before = tagsOf(page).filter((t) => t.at < firstControl.at && (t.name === 'a' || t.name === 'button'))
    assert.deepEqual(before.map((t) => t.name), [], 'no link or button sits between the hero and the first field')
  })

  test('the method-card titles are h2 and every other heading follows (contact-bug-01)', async () => {
    const page = await html('ContactView.vue')
    const cards = withClass(page, 'method-card')
    assert.equal(cards.length, 3, 'the three channels the build already shows stay (contact-04, 07 are decisions)')
    const heads = headingsOf(page)
    assert.deepEqual(outlineProblems(heads), [])
    assert.ok(!heads.some((h) => h.level >= 4), 'no h4 left on the page')
  })

  test('the method cards carry an icon tile with an SVG, not an emoji (contact-03)', async () => {
    const page = await html('ContactView.vue')
    const tiles = withClass(page, 'method-icon')
    assert.equal(tiles.length, 3)
    for (const tile of tiles) {
      const after = page.slice(tile.at, page.indexOf('</div>', tile.at))
      assert.ok(/<svg[\s>]/.test(after), 'each tile holds an inline SVG')
      assert.ok(/aria-hidden="true"/.test(after), 'the decorative icon is hidden from assistive technology')
    }
    assert.ok(!/\p{Extended_Pictographic}/u.test(textOf(page)), 'no emoji remains on the page')
  })

  test('the form uses the Figma labels, placeholders and button label (contact-09)', async () => {
    const page = await html('ContactView.vue')
    const text = textOf(page)
    for (const label of ['Full name', 'Email', 'Church / organization', 'How can we help?']) assert.ok(text.includes(label), `label "${label}"`)
    const placeholders = tagsOf(page).filter((t) => t.name === 'input' || t.name === 'textarea').map((t) => t.attrs['placeholder'])
    assert.deepEqual(placeholders, ['Jane Pastor', 'jane@yourchurch.org', 'Grace Community Church', 'Tell us a little about what you need…'])
    assert.ok(/>\s*Send message\s*</.test(page), 'the button reads "Send message"')
    assert.ok(!text.includes('(Optional)'), 'no "(Optional)" suffix: the frame draws none')
  })

  test('the form is named, its required fields are announced, and the send button is a block primary (contact-12, contact-08)', async () => {
    const page = await html('ContactView.vue')
    const form = tagsOf(page).find((t) => t.name === 'form')
    assert.equal(form?.attrs['aria-label'], 'Contact us')
    const required = tagsOf(page).filter((t) => (t.name === 'input' || t.name === 'textarea') && t.attrs['aria-required'] === 'true')
    assert.equal(required.length, 3, 'name, email and message are aria-required')
    const sfc = readSrc('views/ContactView.vue')
    const send = elementsOf(sfc).find((el) => el.tag === 'UiButton' && valueOf(prop(el, 'size')) === 'lg')
    assert.ok(send, 'the Send button is a large UiButton')
    assert.equal(valueOf(prop(send, 'variant')), 'primary')
    assert.ok(prop(send, 'block'), 'it fills the card')
  })

  test('no claim is added: no address, reply time or note the audit marks unbacked (contact-04, 05, 06)', async () => {
    assert.deepEqual(addedClaims(textOf(await html('ContactView.vue'))), [])
  })

  test('the hero has no promise of a reply or of a person: the sentence is reworded (contact-01, honest content)', async () => {
    const text = textOf(await html('ContactView.vue')).toLowerCase()
    assert.ok(!text.includes('real person'), 'Figma says "a real person"; the repo does not back who answers')
  })
})


// --------------------------------------------------------------------------- Support

describe('Support (498:124): hero, search, category cards, one grouped article panel', () => {
  test('the hero is a HELP CENTER pill, "How can we help?" and the subline, with no radial glow (support-01)', async () => {
    const page = await html('SupportView.vue')
    const [h1] = headingsOf(page)
    assert.equal(h1?.text, 'How can we help?')
    const text = textOf(page)
    assert.ok(text.includes('HELP CENTER'))
    assert.ok(text.includes('Guides, answers and troubleshooting for running SelahCue on Sunday.'))
    assert.ok(!/radial-gradient/.test(styleOf(readSrc('views/SupportView.vue'))), 'the frame draws a flat background')
  })

  test('the search field keeps type=search, role=search and its label, with the frame placeholder (support-02)', async () => {
    const page = await html('SupportView.vue')
    const input = tagsOf(page).find((t) => t.name === 'input')
    assert.equal(input?.attrs['type'], 'search')
    assert.equal(input?.attrs['aria-label'], 'Search help articles')
    assert.equal(input?.attrs['placeholder'], 'Search help articles…')
    assert.ok(tagsOf(page).some((t) => t.attrs['role'] === 'search'))
  })

  test('the placeholder is not the browser grey and focus draws a ring, not only a border (support-03)', () => {
    const css = styleOf(readSrc('views/SupportView.vue'))
    assert.match(css, /\.search-input::placeholder\s*\{[^}]*color:\s*var\(--sc-text-secondary\)/)
    assert.match(css, /\.search-input:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--sc-primary\)/)
    assert.ok(!/\.search-input:focus\s*\{[^}]*outline:\s*none/.test(css), 'focus must not remove the outline')
  })

  test('six category cards with a coloured icon tile holding an SVG, no emoji, no section heading above them (support-04)', async () => {
    const page = await html('SupportView.vue')
    const cards = withClass(page, 'category-card')
    assert.equal(cards.length, 6)
    const tiles = withClass(page, 'cat-icon')
    assert.equal(tiles.length, 6)
    for (const tile of tiles) {
      const inner = page.slice(tile.at, page.indexOf('</div>', tile.at))
      assert.ok(/<svg[\s>]/.test(inner), 'each tile holds an inline SVG')
    }
    assert.ok(!/\p{Extended_Pictographic}/u.test(textOf(page)), 'no emoji remains')
    assert.ok(!textOf(page).includes('Knowledge Base Categories'), 'the frame draws no heading above the grid')
    const heads = headingsOf(page)
    assert.ok(heads.filter((h) => h.level === 2).length >= 7, 'six card titles and Start here are h2')
  })

  test('the Start here articles are ONE grouped panel of whole-row links with a chevron (support-07)', async () => {
    const page = await html('SupportView.vue')
    const panels = withClass(page, 'articles-panel')
    assert.equal(panels.length, 1, 'one grouped panel, not a stack of cards')
    const rows = withClass(page, 'article-row')
    assert.ok(rows.length >= 2)
    for (const row of rows) {
      assert.equal(row.name, 'a', 'the whole row is the link')
      assert.ok((row.attrs['href'] ?? '').startsWith('/support/'), 'and it goes to the article')
    }
    assert.ok(!textOf(page).includes('Read article'), 'no separate Read article button inside the row')
  })

  test('the article list sits in a full-width band', () => {
    const css = styleOf(readSrc('views/SupportView.vue'))
    assert.match(css, /\.articles-band\s*\{[^}]*background:\s*var\(--sc-surface-alt\)/)
  })

  test('the category counts and article meta are not in the brand ink (support-10)', () => {
    const css = styleOf(readSrc('views/SupportView.vue'))
    assert.match(css, /\.cat-count\s*\{[^}]*color:\s*var\(--sc-text-secondary\)/)
  })

  test('the build\'s own content layer stays: counts, article lists, search results (support-05, 09 are decisions)', async () => {
    const page = await html('SupportView.vue')
    assert.ok(/\d+ articles?/.test(textOf(page)))
    assert.ok(withClass(page, 'cat-article-link').length >= 11, 'every real article is still linked from its category card')
  })
})

// --------------------------------------------------------------------------- Docs

describe('Docs (499:124): centred hero, grouped sidebar with an active item, getting-started hub', () => {
  test('the hero is a DOCS pill, h1 "Documentation" and a lead, outside any card (docs-01)', async () => {
    const page = await html('DocsView.vue')
    const [h1] = headingsOf(page)
    assert.equal(h1?.level, 1)
    assert.equal(h1?.text, 'Documentation')
    assert.ok(textOf(page).includes('DOCS'))
    assert.equal(withClass(page, 'docs-content').length, 0, 'the old one-card wrapper is gone')
    assert.equal(withClass(page, 'breadcrumb').length, 0, 'the frame draws no breadcrumb')
    assert.ok(page.indexOf('Documentation</h1>') < page.indexOf('docs-sidebar'), 'the hero is above the sidebar')
  })

  test('the lead makes no promise the content layer does not back (docs-01, docs-04)', async () => {
    const text = textOf(await html('DocsView.vue'))
    assert.ok(!/Everything you need to install/i.test(text), 'Figma says "install"; there is no installation article')
  })

  test('the sidebar is grouped GETTING STARTED / GUIDES / REFERENCE and holds every real category once (docs-02)', async () => {
    const page = await html('DocsView.vue')
    const labels = withClass(page, 'group-label')
    const text = textOf(page)
    assert.deepEqual(labels.map((t) => t.name), ['p', 'p', 'p'])
    for (const label of ['GETTING STARTED', 'GUIDES', 'REFERENCE']) assert.ok(text.includes(label), label)
    const items = withClass(page, 'nav-item')
    assert.equal(items.length, 6)
    assert.deepEqual(
      items.map((t) => t.attrs['href']),
      ['/docs#getting-started', '/docs#display-outputs', '/docs#scripture-bibles', '/docs#timers-plans', '/docs#mobile-control', '/docs#troubleshooting'],
    )
  })

  test('exactly one sidebar item is the current one, programmatically and visibly (docs-02)', async () => {
    const page = await html('DocsView.vue')
    const items = withClass(page, 'nav-item')
    const current = items.filter((t) => t.attrs['aria-current'] !== undefined && t.attrs['aria-current'] !== 'false')
    assert.equal(current.length, 1, 'one item carries aria-current')
    assert.equal(current[0]?.attrs['aria-current'], 'location')
    assert.ok(classesOf(current[0] as Tag).includes('is-active'), 'and the same item has the visible active class')
    assert.equal(withClass(page, 'is-active').length, 1)
    assert.ok(!/aria-current-value/.test(page), 'the junk attribute is gone')
    const css = styleOf(readSrc('views/DocsView.vue'))
    assert.match(css, /\.nav-item\.is-active\s*\{[^}]*font-weight:\s*600/)
  })

  test('the sidebar is 248 wide and the content column follows it at a 40px gap (docs-08)', () => {
    const css = styleOf(readSrc('views/DocsView.vue'))
    assert.match(css, /grid-template-columns:\s*248px minmax\(0, 1fr\)/)
    assert.match(css, /\.docs-layout\s*\{[^}]*gap:\s*40px/)
  })

  test('the group labels are not in the muted ink (docs-07)', () => {
    const css = styleOf(readSrc('views/DocsView.vue'))
    assert.match(css, /\.group-label\s*\{[^}]*color:\s*var\(--sc-text-secondary\)/)
  })

  test('the getting-started hub: h2, intro, a callout that goes to a real article, and a tile for every category (docs-03)', async () => {
    const page = await html('DocsView.vue')
    const heads = headingsOf(page)
    assert.ok(heads.some((h) => h.level === 2 && h.text === 'Getting started'))
    const callout = withClass(page, 'start-callout')
    assert.equal(callout.length, 1)
    const startLink = tagsOf(page).find((t) => t.name === 'a' && classesOf(t).includes('start-button'))
    assert.ok(startLink && /^\/docs\/[a-z-]+\/[a-z-]+$/.test(startLink.attrs['href'] ?? ''), 'Start guide links to a real article')
    assert.ok(textOf(page).includes('Start guide'))
    const tiles = withClass(page, 'topic-tile')
    assert.equal(tiles.length, 6)
    for (const tile of tiles) {
      assert.equal(tile.name, 'a')
      assert.ok((tile.attrs['href'] ?? '').startsWith('/docs#'), 'a tile goes to its category section')
    }
    assert.ok(!heads.some((h) => h.level >= 4))
  })

  test('the callout and tiles claim nothing the repo does not back (docs-04): no 10 minutes, no install or audio copy', async () => {
    const text = textOf(await html('DocsView.vue'))
    for (const bad of ['10 minutes', 'Windows & macOS install', 'audio, and per-output']) assert.ok(!text.includes(bad), bad)
  })

  test('the build\'s own article index stays under the hub (docs-05, 06 are decisions)', async () => {
    const page = await html('DocsView.vue')
    assert.ok(withClass(page, 'topic-link').length >= 11)
    assert.equal(withClass(page, 'topic').length, 6)
  })
})
