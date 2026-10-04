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
  { file: 'ChangelogView.vue', route: '/changelog' },
  { file: 'BlogView.vue', route: '/blog' },
  { file: 'CareersView.vue', route: '/careers' },
  { file: 'PrivacyView.vue', route: '/privacy' },
  { file: 'TermsView.vue', route: '/terms' },
  { file: 'AffiliatesView.vue', route: '/affiliates' },
] as const

/** The pages that render the generated legal drafts. */
const LEGAL_PAGES: ReadonlySet<string> = new Set(['PrivacyView.vue', 'TermsView.vue'])

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
  'careers@selahcue.app',
  "We're a small, remote team",
  'Ship features churches use live',
  'Sustainable pace',
  'Senior Rust Engineer',
  'Flutter / Mobile Engineer',
  'Product Designer',
  'Developer Advocate',
  'Support Specialist',
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

    // The two legal pages render the generated legal drafts, which are owned by ClickUp 17tnw2b0x3g and
    // checked by `npm run check:legal`: their text is not this ticket's and may contain any of these words
    // in its own context (the Terms mention "10 minutes" of a different thing).
    if (!LEGAL_PAGES.has(file)) {
      test(`${file}: no claim the audit marks unbacked is added`, async () => {
        assert.deepEqual(addedClaims(textOf(await html(file))), [], `${file} shows a string Figma draws and the repo does not back`)
      })
    }
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
    const css = styleOf(readSrc('views/DocsView.vue'))
    assert.equal(declaration(css, '.docs-content', 'background'), undefined, 'the content column is no longer a card (no fill)')
    assert.equal(declaration(css, '.docs-content', 'border'), undefined, 'and has no border')
    assert.ok(page.indexOf('Documentation</h1>') < page.indexOf('class="docs-content"'), 'the hero is outside the column')
    assert.equal(withClass(page, 'breadcrumb').length, 0, 'the frame draws no breadcrumb')
    assert.ok(page.indexOf('Documentation</h1>') < page.indexOf('docs-sidebar'), 'the hero is above the sidebar')
  })

  test('the sections keep the class the global anchor rule uses, so a typed #hash lands below the navbar', async () => {
    const anchors = readSrc('assets/styles/anchors.css')
    assert.match(anchors, /\.docs-content \.topic/, 'anchors.css still gives `.docs-content .topic` its scroll margin')
    const page = await html('DocsView.vue')
    const column = withClass(page, 'docs-content')
    assert.equal(column.length, 1)
    assert.equal(withClass(page, 'topic').filter((t) => t.at > column[0]!.at).length, 6, 'all six sections sit inside it')
  })

  test('no link in the hub claims aria-current=page: the router would mark every same-page hash link as the current page', async () => {
    const page = await html('DocsView.vue')
    assert.equal(tagsOf(page).filter((t) => t.name === 'a' && t.attrs['aria-current'] === 'page').length, 0)
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

// --------------------------------------------------------------------------- Changelog

/** Every `<span class="ui-badge variant-X ...">text</span>` in the markup, as [variant, text, classes]. */
function badgesOf(page: string): Array<{ variant: string; text: string; classes: string[] }> {
  const out: Array<{ variant: string; text: string; classes: string[] }> = []
  for (const m of page.matchAll(/<span class="([^"]*\bui-badge\b[^"]*)"[^>]*>([\s\S]*?)<\/span>/g)) {
    const classes = (m[1] ?? '').split(/\s+/)
    const variant = classes.find((c) => c.startsWith('variant-'))?.slice('variant-'.length) ?? ''
    out.push({ variant, text: textOf(m[2] ?? ''), classes })
  }
  return out
}

describe('Changelog (501:124): hero, then one grouped card per release', () => {
  test('the hero is a CHANGELOG pill and the h1 "What\'s new" (changelog-01)', async () => {
    const page = await html('ChangelogView.vue')
    const [h1] = headingsOf(page)
    assert.equal(h1?.text, "What's new")
    assert.ok(textOf(page).includes('CHANGELOG'))
  })

  test('the subline does not promise free updates or an always-latest version (changelog-05 is the owner\'s call)', async () => {
    const text = textOf(await html('ChangelogView.vue')).toLowerCase()
    assert.ok(!text.includes('free on your plan'))
    assert.ok(!text.includes('always on the latest'))
  })

  test('one card per release, each led by an h2 version, and no sticky meta column (changelog-02, changelog-bug-01)', async () => {
    const page = await html('ChangelogView.vue')
    const cards = withClass(page, 'release-card')
    assert.equal(cards.length, 3)
    assert.equal(withClass(page, 'timeline-meta').length, 0, 'the left meta column is gone')
    const heads = headingsOf(page)
    assert.deepEqual(heads.filter((h) => h.level === 2).map((h) => h.text), ['v1.2.0', 'v1.1.0', 'v1.0.0'])
    assert.ok(heads.filter((h) => h.level === 3).length >= 8, 'the per-change titles stay h3')
    assert.deepEqual(outlineProblems(heads), [])
  })

  test('changes are grouped by type: one label per group, not one per change (changelog-02)', async () => {
    const page = await html('ChangelogView.vue')
    const labels = badgesOf(page).filter((b) => b.classes.includes('change-label'))
    assert.deepEqual(labels.map((b) => b.text), ['New', 'Improved', 'Fixed', 'New', 'Improved', 'Fixed', 'New'])
    assert.equal(withClass(page, 'change-group').length, 7)
  })

  test('the type labels use the variants PR 173 defined: New preview, Improved accent, Fixed warn (changelog-03)', async () => {
    const page = await html('ChangelogView.vue')
    const labels = badgesOf(page).filter((b) => b.classes.includes('change-label'))
    const variantOf = (text: string): Set<string> => new Set(labels.filter((b) => b.text === text).map((b) => b.variant))
    assert.deepEqual([...variantOf('New')], ['preview'])
    assert.deepEqual([...variantOf('Improved')], ['accent'])
    assert.deepEqual([...variantOf('Fixed')], ['warn'])
  })

  test('only the newest release carries a tag pill beside its date', async () => {
    const page = await html('ChangelogView.vue')
    const tags = badgesOf(page).filter((b) => !b.classes.includes('change-label') && b.variant !== 'featured')
    assert.equal(tags.length, 1, 'one pill, on the newest release')
    const cards = withClass(page, 'release-card')
    const firstEnd = page.indexOf('</article>', cards[0]!.at)
    assert.ok(page.indexOf('release-tag') > 0 && page.indexOf('release-tag') < firstEnd, 'and it sits in the first card')
  })

  test('the release date is in the secondary ink, 14px (changelog-06)', () => {
    const css = styleOf(readSrc('views/ChangelogView.vue'))
    assert.match(css, /\.release-date\s*\{[^}]*font-size:\s*14px[^}]*color:\s*var\(--sc-text-secondary\)/)
  })

  test('the release column is 900 wide and centred on the shared container', () => {
    const css = styleOf(readSrc('views/ChangelogView.vue'))
    assert.match(css, /\.release-list\s*\{[^}]*max-width:\s*900px[^}]*margin-inline:\s*auto/)
  })
})

// --------------------------------------------------------------------------- Blog

describe('Blog (502:124): hero, featured post with a media panel, three-column grid with thumbnails', () => {
  test('the hero is a BLOG pill, the h1 "The SelahCue blog" and the frame\'s subline (blog-01)', async () => {
    const page = await html('BlogView.vue')
    const [h1] = headingsOf(page)
    assert.equal(h1?.text, 'The SelahCue blog')
    const text = textOf(page)
    assert.ok(text.includes('BLOG'))
    assert.ok(text.includes('Practical notes on running a confident service'))
  })

  test('the featured post is a two-column card: a media panel with an SVG tile, a category pill and a Featured label (blog-02)', async () => {
    const page = await html('BlogView.vue')
    const card = withClass(page, 'featured-card')
    assert.equal(card.length, 1)
    const media = withClass(page, 'featured-media')
    assert.equal(media.length, 1, 'the media panel is there')
    const inner = page.slice(media[0]!.at, page.indexOf('</div></div>', media[0]!.at))
    assert.ok(/<svg[\s>]/.test(inner), 'it holds an inline SVG icon')
    assert.ok(withClass(page, 'featured-label').length === 1 && textOf(page).includes('Featured'), 'the small Featured label')
    const badges = badgesOf(page)
    assert.ok(!badges.some((b) => b.variant === 'live'), 'no red LIVE-status badge on a blog post')
    assert.ok(!textOf(page).includes('Featured Article'), 'the red Featured Article badge is gone')
  })

  test('the featured card has no button: the title is the link to the post (blog-02)', async () => {
    const page = await html('BlogView.vue')
    assert.ok(!textOf(page).includes('Read story'), 'no Read story button')
    const title = withClass(page, 'featured-title')[0]
    assert.ok(title)
    const after = page.slice(title.at, page.indexOf('</h2>', title.at))
    assert.match(after, /<a [^>]*href="\/blog\/why-offline-first-matters-for-sunday-morning"/)
  })

  test('the grid is three columns of cards, each with a thumbnail panel holding an icon tile (blog-03)', async () => {
    const page = await html('BlogView.vue')
    const cards = withClass(page, 'blog-card')
    assert.equal(cards.length, 4, 'the four non-featured posts (blog-04 is the owner\'s call on the count)')
    const media = withClass(page, 'card-media')
    assert.equal(media.length, 4)
    for (const m of media) {
      const inner = page.slice(m.at, page.indexOf('</div></div>', m.at))
      assert.ok(/<svg[\s>]/.test(inner), 'each thumbnail holds an inline SVG icon')
    }
    assert.match(styleOf(readSrc('views/BlogView.vue')), /\.blog-grid\s*\{[^}]*grid-template-columns:\s*repeat\(3, minmax\(0, 1fr\)\)/)
  })

  test('category pills are not all one colour, and none is the red LIVE look (blog-03)', async () => {
    const page = await html('BlogView.vue')
    const pills = badgesOf(page).filter((b) => b.classes.includes('card-category'))
    assert.equal(pills.length, 4)
    assert.ok(new Set(pills.map((b) => b.variant)).size >= 3, 'at least three different pill variants across the four categories')
    assert.ok(!pills.some((b) => b.variant === 'live'))
  })

  test('every card meta line starts with the team, then the date and the read time (blog-06)', async () => {
    const page = await html('BlogView.vue')
    const text = textOf(page)
    const metas = text.match(/SelahCue Team · \d+ [A-Z][a-z]{2} \d{4} · \d+ min( read)?/g) ?? []
    assert.equal(metas.length, 5, 'the featured card and four grid cards')
  })

  test('the meta text is in the secondary ink, 12.5px on cards (blog-07, blog-06)', () => {
    const css = styleOf(readSrc('views/BlogView.vue'))
    assert.match(css, /\.card-meta\s*\{[^}]*font-size:\s*12\.5px[^}]*color:\s*var\(--sc-text-secondary\)/)
    assert.match(css, /\.featured-meta\s*\{[^}]*color:\s*var\(--sc-text-secondary\)/)
  })

  test('each card keeps ONE link to its post, named with the title (blog-03: the Read link stays; blog-04 is a decision)', async () => {
    const page = await html('BlogView.vue')
    for (const card of withClass(page, 'blog-card')) {
      const end = page.indexOf('</article>', card.at)
      const links = tagsOf(page.slice(card.at, end)).filter((t) => t.name === 'a')
      assert.equal(links.length, 1)
      assert.match(links[0]!.attrs['href'] ?? '', /^\/blog\/[a-z0-9-]+$/)
    }
  })
})

// --------------------------------------------------------------------------- Careers

describe('Careers (503:124): hero, four icon-tile culture cards, a full-bleed roles band', () => {
  test('the hero is a CAREERS pill and the h1 "Build tools churches rely on" at the frame\'s 50/56 (careers-01)', async () => {
    const page = await html('CareersView.vue')
    const [h1] = headingsOf(page)
    assert.equal(h1?.text, 'Build tools churches rely on')
    assert.ok(textOf(page).includes('CAREERS'))
    const css = styleOf(readSrc('views/CareersView.vue'))
    assert.match(css, /@media \(min-width: 1200px\)\s*\{\s*\.hero-title\s*\{[^}]*font-size:\s*50px[^}]*line-height:\s*56px/)
    assert.match(css, /\.hero-title\s*\{[^}]*max-width:\s*500px/)
  })

  test('four culture cards with a coloured icon tile holding an SVG, no emoji, no extra heading above them (careers-03)', async () => {
    const page = await html('CareersView.vue')
    const cards = withClass(page, 'culture-card')
    assert.equal(cards.length, 4)
    const tiles = withClass(page, 'culture-icon')
    assert.equal(tiles.length, 4)
    for (const tile of tiles) {
      const inner = page.slice(tile.at, page.indexOf('</div></div>', tile.at))
      assert.ok(/<svg[\s>]/.test(inner), 'each tile holds an inline SVG')
    }
    assert.ok(!/\p{Extended_Pictographic}/u.test(textOf(page)), 'no emoji remains')
    assert.ok(!textOf(page).includes('Why Work With Us'), 'the frame draws no heading over the strip')
    assert.match(styleOf(readSrc('views/CareersView.vue')), /\.culture-grid\s*\{[^}]*grid-template-columns:\s*repeat\(4, minmax\(0, 1fr\)\)/)
  })

  test('the roles sit in a full-bleed band under a centred "Open roles" heading (careers-04)', async () => {
    const page = await html('CareersView.vue')
    assert.ok(headingsOf(page).some((h) => h.level === 2 && h.text === 'Open roles'))
    assert.equal(withClass(page, 'roles-band').length, 1)
    const css = styleOf(readSrc('views/CareersView.vue'))
    assert.match(css, /\.roles-band\s*\{[^}]*background:\s*var\(--sc-surface-alt\)/)
    assert.match(css, /\.roles-list\s*\{[^}]*max-width:\s*940px/)
  })

  test('each role row has three tag pills (department, place, type) and no single meta line (careers-04, careers-05)', async () => {
    const page = await html('CareersView.vue')
    const rows = withClass(page, 'role-row')
    assert.equal(rows.length, 3, 'the roles the build already shows; the Figma roles are not added (careers-07)')
    assert.equal(withClass(page, 'role-tag').length, 9)
    assert.equal(withClass(page, 'role-meta').length, 0)
    const css = styleOf(readSrc('views/CareersView.vue'))
    assert.match(css, /\.role-tag\s*\{[^}]*color:\s*var\(--sc-text-secondary\)/)
    assert.match(css, /\.role-tag\s*\{[^}]*background:\s*var\(--sc-elevated\)/)
  })

  test('the Apply links are distinct: each name carries its role, and still contains the visible text (careers-06)', async () => {
    const page = await html('CareersView.vue')
    const names: string[] = []
    for (const row of withClass(page, 'role-row')) {
      const slice = page.slice(row.at, page.indexOf('</article>', row.at))
      const link = /<a [^>]*>([\s\S]*?)<\/a>/.exec(slice)
      assert.ok(link, 'the row has a link')
      names.push(textOf(link[1] ?? ''))
    }
    assert.equal(new Set(names).size, 3, 'three different accessible names')
    for (const name of names) assert.ok(/^Apply/i.test(name), 'the visible label leads the name')
    const roleTitles = headingsOf(page).filter((h) => h.level === 3).map((h) => h.text)
    roleTitles.forEach((title, i) => assert.ok((names[i] ?? '').includes(title), `link ${i} names its role "${title}"`))
  })

  test('the closing line is plain text: no link to a form that sends nothing, and no mailbox (careers-04, careers-08, review round 1 M1)', async () => {
    const page = await html('CareersView.vue')
    const note = withClass(page, 'roles-note')[0]
    assert.ok(note, 'the closing line is there')
    const line = page.slice(note.at, page.indexOf('</p>', note.at))
    assert.ok(textOf(line).startsWith("Don't see your role?"))
    assert.ok(!/<a[\s>]/.test(line), 'it carries no link: this line is new, and the contact page is a form that sends nothing')
    assert.ok(!/@selahcue/.test(textOf(page).replace('support@selahcue', '')), 'no invented mailbox')
    // The Apply links already existed (to the contact page) and keep that interim destination.
    const apply = tagsOf(page).filter((t) => t.name === 'a' && (t.attrs['href'] ?? '') === '/contact')
    assert.equal(apply.length, 3, 'the three role buttons keep the destination they had')
  })
})

// --------------------------------------------------------------------------- Privacy and Terms

/** The CSS of one legal component, from its own style blocks. */
const legalCss = (name: string): string => styleOf(readSrc(`components/legal/${name}.vue`), `${name}.vue`)

/** The value of one declaration in the FIRST rule whose selector is exactly `selector`; undefined when absent. */
function declaration(css: string, selector: string, property: string): string | undefined {
  const bare = css.replace(/\/\*[\s\S]*?\*\//g, '')
  for (const m of bare.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if ((m[1] ?? '').trim() !== selector) continue
    const d = new RegExp(`(?:^|[;\\s])${property}\\s*:\\s*([^;]+)`).exec(m[2] ?? '')
    if (d) return (d[1] ?? '').trim()
  }
  return undefined
}

describe('Privacy and Terms (504:124, 504:203): type scale, header spacing, markers (the document and the contents sidebar stay)', () => {
  const page = legalCss('LegalPage')

  test('the page title is 44/700 on a 50px line, 16px above the version line (privacy-05, terms-05)', () => {
    assert.equal(declaration(page, '.legal-title', 'font-size'), '44px')
    assert.equal(declaration(page, '.legal-title', 'font-weight'), '700')
    assert.equal(declaration(page, '.legal-title', 'line-height'), '50px')
    assert.equal(declaration(page, '.legal-title', 'margin'), '16px 0 16px')
  })

  test('the title keeps a smaller size on a phone', () => {
    assert.match(page, /@media \(max-width: 767\.98px\)\s*\{[^}]*\.legal-title\s*\{[^}]*font-size:\s*30px/)
  })

  test('the header sits 96px below the navbar and has no divider rule (privacy-07, terms-07)', () => {
    assert.match(declaration(page, '.legal-page', 'padding') ?? '', /^96px 0 /)
    assert.equal(declaration(page, '.legal-header', 'border-bottom'), undefined, 'the rule under the header is gone')
    assert.equal(declaration(page, '.legal-header', 'padding-bottom'), '0')
    assert.equal(declaration(page, '.legal-header', 'margin-bottom'), '40px')
  })

  test('the section headings are 20/600 on a 26px line with the number in the heading ink (privacy-08, terms-08)', () => {
    assert.equal(declaration(page, '.sec-main', 'font-size'), '20px')
    assert.equal(declaration(page, '.sec-main', 'font-weight'), '600')
    assert.equal(declaration(page, '.sec-main', 'line-height'), '26px')
    assert.equal(declaration(page, '.sec-main', 'margin'), '28px 0 10px')
    assert.equal(declaration(page, '.sec-num', 'color'), 'inherit')
  })

  test('the text column is 780 wide (privacy-09, terms-09)', () => {
    assert.equal(declaration(page, '.legal-text', 'max-width'), '780px')
  })

  test('body paragraphs and list items are 16px on a 26px line (privacy-09, terms-09)', () => {
    const blocks = legalCss('LegalBlocks')
    assert.equal(declaration(blocks, '.lb-p', 'font-size'), '16px')
    assert.equal(declaration(blocks, '.lb-p', 'line-height'), '26px')
    const list = legalCss('LegalList')
    assert.equal(declaration(list, '.ll-item', 'font-size'), '16px')
    assert.equal(declaration(list, '.ll-item', 'line-height'), '26px')
  })

  test('list markers are the primary colour, flush left, 10px from the text (terms-11)', () => {
    const list = legalCss('LegalList')
    assert.equal(declaration(list, '.ll-item::before', 'background'), 'var(--sc-primary)')
    assert.equal(declaration(list, '.ll-item::before', 'left'), '0')
    assert.equal(declaration(list, '.ll-item', 'padding-left'), '15px')
  })

  for (const { file, label, children } of [
    { file: 'PrivacyView.vue', label: 'privacy', children: 11 },
    { file: 'TermsView.vue', label: 'terms', children: 0 },
  ]) {
    test(`${label}: the eyebrow is the page pill reading LEGAL, not the green status badge (${label}-06)`, async () => {
      const out = await html(file)
      const badge = badgesOf(out).find((b) => b.text === 'LEGAL')
      assert.ok(badge, 'a pill reading LEGAL')
      assert.equal(badge?.variant, 'featured')
      assert.ok(!badgesOf(out).some((b) => b.variant === 'preview' && /Legal/.test(b.text)), 'no green Legal badge')
    })

    test(`${label}: every section heading carries the section class, and child headings do not (${label}-08)`, async () => {
      const out = await html(file)
      const sections = withClass(out, 'sec-main')
      assert.ok(sections.length >= 13, 'every numbered section')
      for (const h of sections) assert.match(h.name, /^h[23]$/)
      const kids = withClass(out, 'sec-child')
      assert.equal(kids.length, children, `${children} child headings (the generated draft's sub-sections)`)
      assert.ok(kids.every((h) => h.name === 'h3'))
      assert.ok(kids.every((h) => !classesOf(h).includes('sec-main')), 'a child heading is never the section style')
    })
  }

  test('the document text itself is untouched: the generated files are not part of this change', () => {
    // check:legal and test:legal-pages are the gates; this only pins that the views still pass the generated document.
    assert.match(readSrc('views/PrivacyView.vue'), /privacyPolicy/)
    assert.match(readSrc('views/TermsView.vue'), /termsOfService/)
  })

  test('CONTROL: declaration() reads the first matching rule and reports an absent property', () => {
    const css = '/* a note */\n.a { color: red; font-size: 10px; }\n.b .a { font-size: 99px; }\n.a { font-size: 77px; }'
    assert.equal(declaration(css, '.a', 'font-size'), '10px', 'a comment above the rule is not part of its selector')
    assert.equal(declaration(css, '.a', 'margin'), undefined)
    assert.equal(declaration(css, '.b .a', 'font-size'), '99px')
  })
})

// --------------------------------------------------------------------------- Affiliates

/** The markup of one `<section class="...">` of the rendered page (to the section's close), by its class. */
function sectionOf(page: string, cls: string): string {
  const tag = withClass(page, cls)[0]
  assert.ok(tag, `a section with class ${cls}`)
  return page.slice(tag.at, page.indexOf('</section>', tag.at))
}

/** Programme figures: a percentage, a dollar amount, a day count or a month count. */
const hasFigure = (text: string): boolean => /\d+\s*%|\$\s*\d|\d+[- ]days?\b|\d+[- ]months?\b/i.test(text)

describe('Affiliates (541:124): hero and CTAs, four stat cards, How it works, audiences, checklist, boxed FAQ, closing band', () => {
  test('the hero is an AFFILIATE PROGRAM pill and the h1 at the frame\'s 54/60 (affiliates-05, affiliates-11)', async () => {
    const page = await html('AffiliatesView.vue')
    assert.ok(textOf(page).includes('AFFILIATE PROGRAM'))
    const css = styleOf(readSrc('views/AffiliatesView.vue'))
    assert.match(css, /@media \(min-width: 1200px\)\s*\{\s*\.hero-title\s*\{[^}]*font-size:\s*54px[^}]*line-height:\s*60px/)
    assert.equal(declaration(css, '.hero-title', 'max-width'), '880px', 'two lines for the build\'s sentence')
    assert.equal(declaration(css, '.hero-sub', 'font-size'), '19px')
    assert.equal(declaration(css, '.hero-sub', 'line-height'), '30px')
    assert.equal(declaration(css, '.hero-sub', 'max-width'), '760px')
  })

  /**
   * Every link and every button destination on /affiliates. The affiliate Apply and Sign in screens do not exist, and the
   * only affiliate pages (`/affiliates/dashboard` and its family) are presentation shells full of sample churches and
   * a sample balance that read as a live account. No control on this page may send anyone to the customer sign-in or into
   * those shells. One definition, used by the page checks and by the control below it.
   */
  function forbiddenDestinations(links: ReadonlyArray<{ href: string; text: string }>): string[] {
    return links
      .filter((l) => /^\/signin(\/|\?|#|$)/.test(l.href) || /^\/affiliates\/[^/]/.test(l.href))
      .map((l) => `"${l.text}" goes to ${l.href}`)
  }

  const linksIn = (markup: string): Array<{ href: string; text: string }> =>
    [...markup.matchAll(/<a [^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/g)].map((m) => ({ href: m[1] ?? '', text: textOf(m[2] ?? '') }))

  test('the hero has Apply now as a link and Affiliate sign in as a DISABLED button that says why (affiliates-06, owner review round 1)', async () => {
    const page = await html('AffiliatesView.vue')
    const hero = sectionOf(page, 'hero-section')
    assert.deepEqual(linksIn(hero).map((l) => [l.text, l.href]), [['Apply now', '/contact']], 'one link: the interim Apply, which already existed as a CTA')
    const signIn = tagsOf(hero).find((t) => t.name === 'button')
    assert.ok(signIn, 'Affiliate sign in is a button, not a link')
    assert.ok('disabled' in signIn.attrs, 'and it is disabled')
    const note = signIn.attrs['aria-describedby']
    assert.ok(note && hero.includes(`id="${note}"`), 'tied to a visible explanation')
    assert.match(textOf(hero), /Affiliate sign in: not available yet/)
    assert.ok(!textOf(page).includes('Calculate Earnings'))
    const sfc = readSrc('views/AffiliatesView.vue')
    const buttons = elementsOf(sfc).filter((el) => el.tag === 'UiButton')
    const apply = buttons.find((el) => valueOf(prop(el, 'size')) === 'lg' && valueOf(prop(el, 'variant')) === 'primary')
    assert.ok(apply, 'Apply now is a large primary button')
  })

  test('no link or button on /affiliates goes to the customer sign-in or into the affiliate portal shells', async () => {
    const page = await html('AffiliatesView.vue')
    assert.deepEqual(forbiddenDestinations(linksIn(page)), [])
    const sfc = readSrc('views/AffiliatesView.vue')
    const targets = elementsOf(sfc)
      .filter((el) => el.tag === 'UiButton' || el.tag === 'router-link' || el.tag === 'RouterLink' || el.tag === 'a')
      .flatMap((el) => [prop(el, 'to'), prop(el, 'href')])
      .map((p) => valueOf(p))
      .filter((v): v is string => typeof v === 'string' && v !== '')
      .map((href) => ({ href, text: href }))
    assert.deepEqual(forbiddenDestinations(targets), [], 'the template source names none either')
  })

  test('CONTROL: forbiddenDestinations() rejects the sign-in, the dashboard and every sibling of it, and passes the contact page', () => {
    const f = (href: string) => forbiddenDestinations([{ href, text: 'x' }]).length
    for (const bad of ['/signin', '/signin?next=/account', '/affiliates/dashboard', '/affiliates/payouts', '/affiliates/referrals', '/affiliates/resources', '/affiliates/settings', '/affiliates/help']) assert.equal(f(bad), 1, bad)
    for (const good of ['/contact', '/affiliates', '/affiliates#faq', '/signing-off']) assert.equal(f(good), 0, good)
  })

  test('the footnote line under the buttons is not shipped: it is made of the unbacked terms (affiliates-13)', async () => {
    const text = textOf(await html('AffiliatesView.vue'))
    for (const bad of ['Free to join', 'No audience minimum', 'PayPal, Wise or bank']) assert.ok(!text.includes(bad), bad)
  })

  test('four stat cards, left aligned, with no h3 inside them (affiliates-07)', async () => {
    const page = await html('AffiliatesView.vue')
    const cards = withClass(page, 'highlight-card')
    assert.equal(cards.length, 4)
    for (const card of cards) {
      const inner = page.slice(card.at, page.indexOf('</p>', card.at))
      assert.ok(/<p[\s>]/.test(inner) && !/<h3[\s>]/.test(inner), 'the caption is a paragraph, so heading order stays h1 then h2')
    }
    const css = styleOf(readSrc('views/AffiliatesView.vue'))
    assert.match(css, /\.highlights-grid\s*\{[^}]*grid-template-columns:\s*repeat\(4, minmax\(0, 1fr\)\)[^}]*gap:\s*22px/)
    assert.ok(!/\.highlight-card\s*\{[^}]*text-align:\s*center/.test(css))
  })

  test('How it works: an h2, a line under it and three numbered step cards with h3 titles and no figure (affiliates-01, affiliates-13)', async () => {
    const page = await html('AffiliatesView.vue')
    assert.ok(headingsOf(page).some((h) => h.level === 2 && h.text === 'How it works'))
    const section = sectionOf(page, 'steps-section')
    const cards = withClass(section, 'step-card')
    assert.equal(cards.length, 3)
    assert.ok(['01', '02', '03'].every((n) => section.includes(`>${n}<`)), 'the 01, 02 and 03 chips')
    assert.ok(!hasFigure(textOf(section)), 'no commission rate, threshold, window or review time in the steps')
    for (const bad of ['within a couple of days', 'ready-made banners', 'pass $50']) assert.ok(!textOf(section).includes(bad), bad)
  })

  test('Made for people who talk to churches: four icon-tile cards with the frame\'s titles (affiliates-02)', async () => {
    const page = await html('AffiliatesView.vue')
    assert.ok(headingsOf(page).some((h) => h.level === 2 && h.text === 'Made for people who talk to churches'))
    const section = sectionOf(page, 'audience-section')
    const cards = withClass(section, 'audience-card')
    assert.equal(cards.length, 4)
    for (const c of cards) {
      const inner = section.slice(c.at, section.indexOf('</article>', c.at))
      assert.ok(/<svg[\s>]/.test(inner), 'an inline SVG icon in the tile')
    }
    const titles = headingsOf(section).filter((h) => h.level === 3).map((h) => h.text)
    assert.deepEqual(titles, ['Church tech creators', 'AV & gear resellers', 'Ministry networks', 'Consultants & integrators'])
  })

  test('Why it is easy to recommend: only the two lines the repo backs, each with a check (affiliates-03, affiliates-15)', async () => {
    const page = await html('AffiliatesView.vue')
    assert.ok(headingsOf(page).some((h) => h.level === 2 && h.text === "Why it's easy to recommend"))
    const section = sectionOf(page, 'why-section')
    assert.equal(withClass(section, 'check-row').length, 2)
    const text = textOf(section)
    assert.ok(text.includes('with no network'), 'the offline line says what runs offline, in the repo\'s own terms')
    assert.ok(!/no internet/i.test(textOf(page)), 'nowhere on the page: a new activation or a licensed download needs the network once, so "no internet" says too much')
    assert.match(text, /Designed so a fault never blanks the live screen/)
    for (const bad of ['actually keep using', 'Recurring commission for a year', 'Banners, links and email copy']) assert.ok(!text.includes(bad), bad)
  })

  test('the calculator stays beside the checklist, with a named slider (affiliates-10 is a decision; the unnamed input is a defect)', async () => {
    const page = await html('AffiliatesView.vue')
    const section = sectionOf(page, 'why-section')
    assert.equal(withClass(section, 'calc-card').length, 1, 'the existing calculator sits in the right column')
    const range = tagsOf(section).find((t) => t.name === 'input' && t.attrs['type'] === 'range')
    assert.ok(range, 'the slider')
    const labelled = range.attrs['aria-labelledby'] ?? ''
    assert.ok(labelled && section.includes(`id="${labelled}"`), 'the slider is named by visible text on the page')
  })

  test('the FAQ is the boxed accordion under its own h2 "Affiliate FAQ" (affiliates-08, affiliates-09)', async () => {
    const page = await html('AffiliatesView.vue')
    assert.ok(headingsOf(page).some((h) => h.level === 2 && h.text === 'Affiliate FAQ'))
    assert.ok(withClass(page, 'is-boxed').length === 1, 'FaqAccordion rendered with the boxed option')
    const buttons = tagsOf(page).filter((t) => t.name === 'button' && t.attrs['aria-controls'])
    assert.ok(buttons.length >= 4, 'each question controls its answer')
    const sfc = readSrc('views/AffiliatesView.vue')
    const faq = elementsOf(sfc).find((el) => el.tag === 'FaqAccordion')
    assert.ok(faq && prop(faq, 'boxed'), 'the view opts into boxed')
  })

  test('the closing band: gradient card, h2, a white Apply now that is disabled and says why, no Read the terms (affiliates-04, affiliates-14)', async () => {
    const page = await html('AffiliatesView.vue')
    assert.ok(headingsOf(page).some((h) => h.level === 2 && h.text === 'Ready to get started?'))
    const band = sectionOf(page, 'cta-section')
    const text = textOf(page)
    assert.ok(!text.includes('Read the terms'))
    const sfc = readSrc('views/AffiliatesView.vue')
    const inverse = elementsOf(sfc).filter((el) => el.tag === 'UiButton' && valueOf(prop(el, 'variant')) === 'inverse')
    assert.equal(inverse.length, 1, 'one white button on the band')
    assert.ok(!prop(inverse[0]!, 'to') && !prop(inverse[0]!, 'href'), 'it has no destination: the page newly added this button and the contact form sends nothing')
    assert.ok(prop(inverse[0]!, 'disabled'), 'so it is disabled')
    const btn = tagsOf(band).find((t) => t.name === 'button')
    assert.ok(btn && 'disabled' in btn.attrs, 'a real disabled button in the markup')
    assert.ok(band.includes(`id="${btn.attrs['aria-describedby']}"`) && textOf(band).includes('Not available yet'), 'with a visible reason')
    assert.equal(linksIn(band).length, 0, 'no link in the band')
    assert.match(styleOf(sfc), /\.cta-band\s*\{[^}]*background:\s*var\(--gradient-cta\)/)
    assert.ok(!/free/i.test(textOf(band)), 'the band does not promise a free programme')
    assert.ok(!/recurring|earning|income/i.test(textOf(band)), 'and does not restate the programme promise (that claim is the live page\'s, removed by the claims ticket)')
  })

  test('the new Affiliates sections restate no earnings promise: the steps and the section lines say what the visitor does', async () => {
    const page = await html('AffiliatesView.vue')
    const steps = textOf(sectionOf(page, 'steps-section'))
    assert.ok(!/earn|commission|income|recurring|paid|payout/i.test(steps), 'the How it works section has no earning, commission or payout words')
    assert.match(steps, /Refer a church/)
  })

  test('the section order follows the frame', async () => {
    const page = await html('AffiliatesView.vue')
    const at = (cls: string): number => withClass(page, cls)[0]?.at ?? -1
    const order = ['hero-section', 'highlights-section', 'steps-section', 'audience-section', 'why-section', 'faq-section', 'cta-section'].map(at)
    assert.ok(order.every((n) => n > 0), 'every section exists')
    assert.deepEqual([...order].sort((a, b) => a - b), order)
  })

  test('CONTROL: hasFigure() recognises each kind of programme figure and passes ordinary words', () => {
    for (const t of ['Earn 20% recurring', 'a $50 threshold', 'a 60-day window', 'for 12 months', 'in 3 days']) assert.ok(hasFigure(t), t)
    for (const t of ['Tell us how you will share SelahCue.', 'Step 03 of the process', 'Share it anywhere']) assert.ok(!hasFigure(t), t)
  })
})
