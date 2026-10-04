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
 *   - no page makes a claim the repo does not back: the strings the audit marks unbacked (addresses
 *     nobody confirmed, reply times, commission rates, invented releases and roles) are absent, the
 *     ledger's `unbacked` list is empty on every page, and the claims removed by ClickUp 17tnw2b0x3h
 *     are banned from coming back (`NAMED_CLAIMS`);
 *   - each page has the structure its Figma frame draws.
 */
import assert from 'node:assert/strict'
import { readdirSync } from 'node:fs'
import path from 'node:path'
import test, { after, before, describe } from 'node:test'

import type { ViteDevServer } from 'vite'

import { docsArticles, docsCategories } from '../src/lib/content/docs.ts'
import { blogPosts } from '../src/lib/content/blog.ts'
import { searchSupport, supportArticles, supportCategories } from '../src/lib/content/support.ts'
import { LEDGER, NAMED_CLAIMS, PROMISE_PATTERN, type Entry } from './fixtures/copyLedger.ts'
import { descriptorOf, elementsOf, prop, readSrc, styleOf, valueOf, type DirectiveProp } from './fixtures/sfcSource.ts'
import {
  attributeRunsOf,
  classesOf,
  copyRunsOf,
  headingsOf,
  outlineProblems,
  renderView,
  SRC,
  startViewServer,
  tagsOf,
  textOf,
  withClass,
  type Heading,
  type Tag,
  type ViewState,
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

/**
 * The copy ledger (see `fixtures/copyLedger.ts`). A piece of copy a visitor can read or hear is allowed when the CONTENT LAYER
 * owns it, or it is on the page's ledger as new copy (reviewed: no promise), as an UNBACKED line (live before this PR, claims
 * something the repo does not back; removed by the claims ticket 17tnw2b0x3h) or as a HARMLESS one. Anything else is a sentence
 * nobody listed.
 */
const CONTENT_TEXT: ReadonlySet<string> = new Set([
  ...[...docsCategories, ...supportCategories].flatMap((c) => [c.title, c.desc]),
  ...[...docsArticles, ...supportArticles].flatMap((a) => [a.title, a.summary]),
  ...blogPosts.flatMap((p) => [p.title, p.summary, p.category]),
])

const entryMatches = (e: Entry, run: string): boolean => (typeof e === 'string' ? e === run : e.test(run))

/** Every entry of a page's ledger, whichever list it is on. */
const listed = (page: string): Entry[] => {
  const l = LEDGER[page]
  assert.ok(l, `no ledger for ${page}`)
  return [...l.newCopy, ...l.unbacked, ...l.harmless]
}

/** The runs the ledger does not account for. One definition, used by the page checks and by the planted-promise controls. */
function unlistedRuns(runs: readonly string[], page: string, content: ReadonlySet<string> = CONTENT_TEXT): string[] {
  const all = listed(page)
  return runs.filter((r) => !content.has(r) && !all.some((e) => entryMatches(e, r)))
}

/**
 * The states each page is read in, besides the one it opens in. Server rendering cannot click, so each state is the view's OWN
 * bindings set where the interaction would put them (`renderView` throws on a name the view does not declare). The Support
 * queries come from the content layer, so the three result lines (one, several, none) are always the ones that really render.
 */
const SUPPORT_ONE = supportArticles.map((a) => a.title).find((t) => searchSupport(t)?.length === 1) ?? ''
const SUPPORT_MANY = ['a', 'e', 'the', 'obs', 'sound'].find((q) => (searchSupport(q)?.length ?? 0) > 1) ?? ''

interface PageState {
  readonly label: string
  readonly state: ViewState
  /** What the markup must show for the state to count as reached: a state that silently rendered the default page would pass the ledger for the wrong reason. */
  readonly reached: RegExp
}
const STATES: Readonly<Record<string, readonly PageState[]>> = {
  Contact: [
    { label: 'submitted empty: every required message', state: { call: [['handleSubmit']] }, reached: /Name is required[\s\S]*Email is required[\s\S]*Message is required/ },
    {
      label: 'submitted with bad values: the length and email messages',
      state: { set: { name: 'x'.repeat(101), email: 'nope', org: 'y'.repeat(101) }, call: [['handleSubmit']] },
      reached: /Name must be 100 characters or fewer[\s\S]*Please enter a valid email address[\s\S]*Church \/ organization must be 100/,
    },
  ],
  Support: [
    { label: 'search with one result', state: { set: { searchQuery: SUPPORT_ONE } }, reached: /1 help article matches your search\./ },
    { label: 'search with several results', state: { set: { searchQuery: SUPPORT_MANY } }, reached: /\d+ help articles match your search\./ },
    { label: 'search with no result', state: { set: { searchQuery: 'zzzzqqqqxx' } }, reached: /No help articles match that search\./ },
  ],
}

interface Reading {
  readonly label: string
  readonly markup: string
  readonly runs: string[]
  /** Undefined for the page as it opens. */
  readonly reached?: RegExp
}
const stateRendered = new Map<string, string>()
/** Every state the ledger reads a page in: the default render first, then each interaction state. */
async function readings(file: string): Promise<Reading[]> {
  const page = PAGES.find((p) => p.file === file)
  assert.ok(page, `${file} is not one of the nine pages`)
  const opened = await html(file)
  const out: Reading[] = [{ label: 'the page as it opens', markup: opened, runs: copyRunsOf(opened) }]
  for (const { label, state, reached } of STATES[ledgerKey(file)] ?? []) {
    const key = `${file}|${label}`
    let markup = stateRendered.get(key)
    if (markup === undefined) {
      markup = await renderView(server, file, page.route, state)
      stateRendered.set(key, markup)
    }
    out.push({ label, markup, runs: copyRunsOf(markup), reached })
  }
  return out
}

const ledgerKey = (file: string): string => file.replace(/View\.vue$/, '')

/**
 * The FormFields of a view that do NOT clear their own error when their value changes, as readable names. A field is
 * covered when it has `v-model="x"` and an `update:modelValue` listener whose expression is `clearError('x')`. One
 * definition, used by the Contact test and by its planted-fault control (review round 2, Quinn Q1).
 */
function fieldsWithoutClearOnInput(sfc: string, view = 'fixture.vue'): string[] {
  const out: string[] = []
  for (const el of elementsOf(sfc, view).filter((e) => e.tag === 'FormField')) {
    const model = el.props.find((p): p is DirectiveProp => p.type === 7 && p.name === 'model')
    const field = model?.exp?.content.trim() ?? '(no v-model)'
    const listener = el.props.find(
      (p): p is DirectiveProp => p.type === 7 && p.name === 'on' && (p.arg?.content ?? '').replace(/-/g, '').toLowerCase() === 'update:modelvalue',
    )
    if (listener?.exp?.content.trim() !== `clearError('${field}')`) out.push(field)
  }
  return out
}

/** A rule in the view's own <style> that gives every focusable control of the page the shared anchor offset as its scroll margin. */
function focusScrollMarginRules(sfc: string): string[] {
  const out: string[] = []
  for (const m of styleOf(sfc).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selector = (m[1] ?? '').trim()
    const covers = /:is\([^)]*\ba\[href\][^)]*\bbutton\b[^)]*\binput\b[^)]*\btextarea\b[^)]*\)/.test(selector)
    if (covers && /(^|[;\s])scroll-margin-top\s*:\s*var\(--sc-anchor-offset\)/.test(m[2] ?? '')) out.push(selector)
  }
  return out
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

    // The two legal pages render the generated legal drafts (ClickUp 17tnw2b0x3g, `npm run check:legal`): their text is
    // not this ticket's. The other seven are held to the copy ledger.
    if (!LEGAL_PAGES.has(file)) {
      test(`${file}: every line it shows or says, in every state, is on the copy ledger or in the content layer`, async () => {
        for (const { label, runs } of await readings(file)) {
          const stray = unlistedRuns(runs, ledgerKey(file))
          assert.deepEqual(stray, [], `${file} (${label}) shows copy nobody listed: add it to tests/fixtures/copyLedger.ts as new copy only if it carries no promise`)
        }
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

  test('CONTROL: the gradient and container predicates fire on a planted fault', () => {
    const planted = `<template><UiButton variant="gradient">Go</UiButton><UiButton :variant="'gradient'">Go</UiButton><UiButton variant="primary">ok</UiButton></template>
<style scoped>.container { max-width: 1140px; }</style>`
    assert.equal(gradientButtons(planted).length, 2)
    assert.equal(localContainerRules(planted).length, 1)
    assert.equal(localContainerRules('<template><p/></template><style scoped>.container-fluid { margin: 0 }\n.page .info-container { x: y }</style>').length, 0, 'a different class that merely contains the word is not the shared container')
    assert.ok(!usesSharedContainer('<template><div class="contact-page"><p/></div></template>'))
    assert.ok(usesSharedContainer('<template><div class="hero container"><p/></div></template>'))
  })
})

// --------------------------------------------------------------------------- the copy ledger

/** A `content:` value that draws nothing. Anything else (a string with characters, `attr()`, `counter()`) is copy a text scan cannot see. */
const EMPTY_CONTENT = /^(?:''|""|none|normal)$/i

/** Every `content:` declaration in a component's style blocks whose value draws something, as readable strings. One definition, used by the scan and its control. */
function drawnCssContent(sfc: string, name = 'fixture.vue'): string[] {
  const css = styleOf(sfc, name).replace(/\/\*[\s\S]*?\*\//g, '')
  const out: string[] = []
  for (const m of css.matchAll(/(?<![\w-])content\s*:\s*([^;}]+)/g)) {
    const value = (m[1] ?? '').trim().replace(/\s*!important$/i, '')
    if (!EMPTY_CONTENT.test(value)) out.push(`content: ${value}`)
  }
  return out
}

/** Every `.vue` file this ticket owns: the nine views and the legal and article components. */
function ownedVueFiles(): string[] {
  const files = PAGES.map((p) => `views/${p.file}`)
  for (const dir of ['components/legal', 'components/article']) {
    for (const f of readdirSync(path.join(SRC, dir))) if (f.endsWith('.vue')) files.push(`${dir}/${f}`)
  }
  return files
}

describe('the copy ledger: no sentence appears on the seven pages that nobody listed', () => {
  const pages = PAGES.filter((p) => !LEGAL_PAGES.has(p.file))

  test('the ledger covers exactly the seven non-legal pages', () => {
    assert.deepEqual(Object.keys(LEDGER).sort(), pages.map((p) => ledgerKey(p.file)).sort())
  })

  for (const { file } of pages) {
    const key = ledgerKey(file)

    test(`${key}: every state the ledger reads was reached, not silently rendered as the default page`, async () => {
      const all = await readings(file)
      assert.equal(all.length, 1 + (STATES[key]?.length ?? 0))
      for (const r of all) if (r.reached) assert.match(r.markup, r.reached, `${key}: the state "${r.label}" did not show what it should`)
    })

    test(`${key}: every ledger entry is still shown in some state, so the unbacked list can only shrink`, async () => {
      const runs = (await readings(file)).flatMap((r) => r.runs)
      const dead = listed(key).filter((e) => !runs.some((r) => entryMatches(e, r)))
      assert.deepEqual(dead.map(String), [], `${key}: entries nothing on the page matches (delete them: the words are gone)`)
    })

    test(`${key}: no entry is on two lists, and none is listed twice`, () => {
      const names = listed(key).map(String)
      assert.equal(new Set(names).size, names.length, `${key}: an entry appears twice`)
    })

    test(`${key}: new copy and harmless lines carry no time, money, reply or privacy promise`, () => {
      const l = LEDGER[key]!
      const promising = [...l.newCopy, ...l.harmless].filter((e) => typeof e === 'string' && PROMISE_PATTERN.test(e))
      assert.deepEqual(promising, [], `${key}: a promise-shaped line is on newCopy or harmless; a claim belongs on unbacked, where the claims ticket removes it`)
    })
  }

  // ClickUp 17tnw2b0x3h's check, executable: the `unbacked` list is what the page may NOT say, so it is empty on every page.
  test('no page has an `unbacked` entry: every claim the repo does not back is gone (ClickUp 17tnw2b0x3h)', () => {
    for (const { file } of pages) {
      const key = ledgerKey(file)
      assert.deepEqual(LEDGER[key]!.unbacked.map(String), [], `${key}: unbacked lines are still live; remove the words and the entry`)
    }
  })

  // The strings removed from the pages cannot return: not on any list, and not in any run any state renders.
  test('the claims the reviewers named are banned: on no ledger list and rendered by no page state', async () => {
    for (const [page, sample] of NAMED_CLAIMS) {
      const onAList = listed(page).filter((e) => entryMatches(e, sample))
      assert.deepEqual(onAList.map(String), [], `${page}: "${sample}" is on a ledger list; a removed claim must not be allow-listed`)
      const runs = (await readings(`${page}View.vue`)).flatMap((r) => r.runs)
      assert.deepEqual(runs.filter((r) => r === sample || r.includes(sample)), [], `${page}: "${sample}" is rendered again`)
    }
  })

  test('no scoped style of a view or of the legal and article components draws text with CSS `content`', () => {
    const files = ownedVueFiles()
    assert.ok(files.length >= 15, `only ${files.length} files were scanned`)
    const found = files.flatMap((f) => drawnCssContent(readSrc(f), f).map((c) => `${f}: ${c}`))
    assert.deepEqual(found, [], 'CSS `content` draws words the ledger cannot read: write them in the template')
  })

  test('CONTROL: the CSS content scan fires on a drawn string, a counter and attr(), and passes empty content and justify-content', () => {
    const sfc = (rule: string): string => `<template><p/></template><style scoped>${rule}</style>`
    assert.deepEqual(drawnCssContent(sfc(".x::after { content: 'Free for life'; }")), ["content: 'Free for life'"])
    assert.deepEqual(drawnCssContent(sfc('.x::before { content: "Guaranteed"; color: red }')), ['content: "Guaranteed"'])
    assert.equal(drawnCssContent(sfc('.x::after { content: attr(data-promise); }')).length, 1)
    assert.equal(drawnCssContent(sfc('.x::before { content: counter(step) ". "; }')).length, 1)
    assert.equal(drawnCssContent(sfc(".x::after { content: ''; position: absolute }")).length, 0)
    assert.equal(drawnCssContent(sfc('.x::after { content: ""; }')).length, 0)
    assert.equal(drawnCssContent(sfc('.x { justify-content: center; align-content: start; place-content: center }')).length, 0)
    assert.equal(drawnCssContent(sfc("/* content: 'in a comment' */ .x { color: red }")).length, 0)
    assert.equal(drawnCssContent(sfc('.x::after { content: none }')).length, 0)
  })

  test('CONTROL: three planted promises in plain words are all unlisted (they stayed green under the old 16-string ban)', () => {
    const plant = (page: string, line: string): string[] => unlistedRuns([line], page)
    assert.deepEqual(plant('Support', 'We reply within one hour'), ['We reply within one hour'])
    assert.deepEqual(plant('Changelog', 'Every update is free for life and ships weekly'), ['Every update is free for life and ships weekly'])
    assert.deepEqual(plant('Affiliates', 'Earn guaranteed recurring commission for life'), ['Earn guaranteed recurring commission for life'])
    assert.deepEqual(plant('Careers', 'Open roles'), [], 'a listed line passes')
    assert.deepEqual(plant('Support', 'Nothing is showing on the audience screen'), [], 'a content-layer title passes')
    assert.deepEqual(plant('Support', '2 articles'), [], 'a computed count passes')
  })

  test('CONTROL: promises planted where the old ledger could not look are unlisted: a success card, a status line, a validation message, an attribute', () => {
    const plant = (page: string, line: string): string[] => unlistedRuns([line], page)
    assert.deepEqual(plant('Contact', 'We reply within one hour, guaranteed.'), ['We reply within one hour, guaranteed.'], 'the Contact success card (Quinn planted this one)')
    assert.deepEqual(plant('Contact', 'Thank you for reaching out, Ana. We will reply in one hour.'), ['Thank you for reaching out, Ana. We will reply in one hour.'], 'the success sentence edited')
    assert.deepEqual(plant('Support', 'We answer within a minute.'), ['We answer within a minute.'], 'a Support status line')
    assert.deepEqual(plant('Contact', 'Your message is encrypted end to end'), ['Your message is encrypted end to end'], 'a validation message')
    const tooltip = attributeRunsOf('<a href="/x" title="Free for life" aria-label="Always online"><img alt="Earn 20%"></a>')
    assert.deepEqual(tooltip, ['Free for life', 'Always online', 'Earn 20%'], 'title, aria-label and alt are read')
    assert.deepEqual(unlistedRuns(tooltip, 'Careers'), tooltip, 'and none of them is listed')
    assert.deepEqual(attributeRunsOf('<input placeholder="Jane Pastor" aria-label="Contact us" class="x" data-note="not copy" value="typed">'), ['Contact us', 'Jane Pastor'], 'placeholder and aria-label yes; a class, a data attribute and a typed value no')
    assert.deepEqual(plant('Contact', 'Contact us'), [], 'a listed accessible name passes')
  })

  test('CONTROL: the promise pattern catches a time, a figure, a reply, an earnings word and a privacy promise, and passes ordinary copy', () => {
    for (const bad of [
      'We reply within one hour',
      'Free for life',
      'Earn 20% recurring',
      'Paid monthly',
      'Guaranteed',
      'Pay $50',
      'Our team will respond',
      'Commission on every sale',
      'We always answer every message.',
      'We never share your data.',
      'Instant help',
      'Replies are instant',
      'We answer every message',
      'Immediate support',
      'We will never sell your details',
    ]) {
      assert.ok(PROMISE_PATTERN.test(bad), bad)
    }
    for (const ok of [
      'Apply to join the SelahCue affiliate program.',
      'Guides, answers and troubleshooting for running SelahCue on Sunday.',
      'Not available yet',
      'Refer a church',
      "Don't see your role? We're glad to meet thoughtful people.",
    ]) {
      assert.ok(!PROMISE_PATTERN.test(ok), ok)
    }
  })

  test('CONTROL: a removed claim moved back into the new copy is caught by the promise pattern (the ledger cannot launder a claim)', () => {
    // The `unbacked` list is empty now, so this reads the removed claims themselves: a ban list the pattern must still catch.
    const claims = NAMED_CLAIMS.filter(([page]) => page === 'Affiliates').map(([, sample]) => sample).filter((s) => /20%|\$50|60 Days|Earn|Payouts/.test(s))
    assert.ok(claims.length >= 4, `only ${claims.length} removed Affiliates claims were read; the control is vacuous`)
    for (const claim of claims) assert.ok(PROMISE_PATTERN.test(claim), `${claim} would be caught`)
  })

  test('CONTROL: every state\'s marker is shown by that state and not by the default page (the markers can tell them apart)', async () => {
    for (const key of Object.keys(STATES)) {
      const file = `${key}View.vue`
      const all = await readings(file)
      for (const r of all.slice(1)) assert.doesNotMatch(all[0]!.markup, r.reached!, `${key}: "${r.label}" shows its marker on the default page too`)
    }
  })
})

// --------------------------------------------------------------------------- CategoryIcon names

/** The icon names `CategoryIcon.vue` has an entry for, read from its own table. */
function iconTable(source: string): string[] {
  const script = descriptorOf(source, 'CategoryIcon.vue').scriptSetup?.content ?? ''
  const body = script.slice(script.indexOf('const ICONS'), script.indexOf('const props'))
  return [...body.matchAll(/^ {2}'?([a-z][a-z-]*)'?: \[/gm)].map((m) => m[1] as string)
}

/**
 * Every icon name a view asks CategoryIcon for. A static `name="x"` is read from the template; a bound `:name` takes its
 * values from where the view gets them: `icon: 'x'` pairs in its own script, or the content layer's category ids (Support
 * and Docs draw the tile for each help category by its id).
 */
function namesAsked(view: string, sfc: string): string[] {
  const tags = elementsOf(sfc, view).filter((el) => el.tag === 'CategoryIcon')
  if (tags.length === 0) return []
  const names = new Set<string>()
  const script = descriptorOf(sfc, view).scriptSetup?.content ?? ''
  for (const el of tags) {
    const p = prop(el, 'name')
    if (p?.type === 6) names.add(p.value?.content ?? '')
    else if (p) {
      for (const m of script.matchAll(/\bicon:\s*'([a-z][a-z-]*)'/g)) names.add(m[1] as string)
      if (/\.id\b/.test((p as { exp?: { content: string } }).exp?.content ?? '')) {
        const ids = view === 'SupportView.vue' ? supportCategories : view === 'DocsView.vue' ? docsCategories : []
        for (const c of ids) names.add(c.id)
      }
    }
  }
  return [...names]
}

describe('CategoryIcon: every name a view asks for has its own icon, and every icon is asked for (review round 1 M7)', () => {
  const table = iconTable(readSrc('components/article/CategoryIcon.vue'))
  const views = PAGES.map((p) => p.file).filter((f) => !LEGAL_PAGES.has(f))
  const asked = new Map(views.map((v) => [v, namesAsked(v, readSrc(`views/${v}`))] as const))

  test('the table was read: it has entries and no duplicates', () => {
    assert.ok(table.length >= 15, `only ${table.length} icons were found: the reader is looking in the wrong place`)
    assert.equal(new Set(table).size, table.length)
  })

  test('the reader finds the names each view uses (so a view cannot stop being checked)', () => {
    assert.deepEqual([...asked.get('ContactView.vue')!].sort(), ['mail'])
    assert.ok(asked.get('SupportView.vue')!.length >= 6, 'the six help categories')
    assert.ok(asked.get('DocsView.vue')!.includes('getting-started') && asked.get('DocsView.vue')!.length >= 6)
    assert.ok(asked.get('BlogView.vue')!.includes('shield-check'))
    assert.deepEqual([...asked.get('CareersView.vue')!].sort(), [], 'Careers draws no icon now that its culture strip is gone (17tnw2b0x3h)')
    assert.deepEqual([...asked.get('AffiliatesView.vue')!].sort(), ['briefcase', 'package', 'users', 'video'])
  })

  test('every icon name any view asks for is in the table (a typo silently drew the lightning bolt)', () => {
    const unknown = [...asked].flatMap(([view, names]) => names.filter((n) => !table.includes(n)).map((n) => `${view}: "${n}"`))
    assert.deepEqual(unknown, [], 'a name CategoryIcon has no entry for')
  })

  test('every icon in the table is asked for by some view (no dead icon)', () => {
    const used = new Set([...asked.values()].flat())
    assert.deepEqual(table.filter((n) => !used.has(n)), [], 'icons no view draws: delete them')
  })

  test('Contact draws its one method tile with CategoryIcon, not inline paths', async () => {
    const sfc = readSrc('views/ContactView.vue')
    assert.equal(elementsOf(sfc).filter((el) => el.tag === 'CategoryIcon').length, 1)
    assert.ok(!elementsOf(sfc).some((el) => el.tag === 'svg'), 'no inline svg is left in the view')
  })

  test('CONTROL: the reader reports a misspelt name in a view and a misspelt key in the table', () => {
    const view = '<script setup lang="ts">\nconst x = [{ icon: \'globee\' }]\n</script>\n<template><CategoryIcon :name="x.icon" /><CategoryIcon name="vidro" /></template>'
    assert.deepEqual(namesAsked('FakeView.vue', view).sort(), ['globee', 'vidro'])
    const tbl = iconTable("<script setup lang=\"ts\">\nconst ICONS = {\n  globee: [['circle', {}]],\n  'wifi-off': [['line', {}]]\n}\nconst props = 1\n</script>")
    assert.deepEqual(tbl, ['globee', 'wifi-off'])
    assert.ok(!tbl.includes('globe'), 'a table with the typo does not contain the real name')
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
    assert.equal(cards.length, 1, 'one channel works today, the email address; the Discord and enterprise cards claimed channels that do not exist (17tnw2b0x3h)')
    const heads = headingsOf(page)
    assert.deepEqual(outlineProblems(heads), [])
    assert.ok(!heads.some((h) => h.level >= 4), 'no h4 left on the page')
  })

  test('the method cards carry an icon tile with an SVG, not an emoji (contact-03)', async () => {
    const page = await html('ContactView.vue')
    const tiles = withClass(page, 'method-icon')
    assert.equal(tiles.length, 1)
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

  test('the hero has no promise of a reply or of a person: the sentence is reworded (contact-01, honest content)', async () => {
    const text = textOf(await html('ContactView.vue')).toLowerCase()
    assert.ok(!text.includes('real person'), 'Figma says "a real person"; the repo does not back who answers')
  })

  // ClickUp 17tnw2b0x3h. The form sends nothing (there is no endpoint), so the page must never say it did.
  test('nothing is sent and the page says so: Send is disabled and described by a visible note; there is no success card, no timer and no reply promise', async () => {
    const page = await html('ContactView.vue')
    const sfc = readSrc('views/ContactView.vue')
    const send = elementsOf(sfc).find((el) => el.tag === 'UiButton' && valueOf(prop(el, 'size')) === 'lg')
    assert.ok(send && prop(send, 'disabled'), 'the Send button is disabled until a send exists')
    assert.equal(valueOf(prop(send, 'aria-describedby')), 'send-note', 'and described by the note')
    assert.ok(tagsOf(page).some((t) => t.attrs['id'] === 'send-note'), 'the note is on the page')
    assert.ok(textOf(page).includes('The contact form is not available yet.'), 'and says the form is not available')
    const script = descriptorOf(sfc, 'ContactView.vue').scriptSetup?.content ?? ''
    assert.doesNotMatch(script, /setTimeout|isSubmitted|isSubmitting/, 'no fake send: no timer and no submitted state')
    assert.doesNotMatch(sfc, /success-state|Message Received|respond within/i, 'no success card and no reply promise')
  })

  test('the only link on the page is the one address the owner confirmed; no link goes nowhere', async () => {
    const hrefs = tagsOf(await html('ContactView.vue')).filter((t) => t.name === 'a').map((t) => t.attrs['href'])
    assert.deepEqual(hrefs, ['mailto:support@selahcueapp.com'])
  })

  test('every field takes its own error away when its value changes, and the form hears the pointer go down (review round 2, Quinn Q1)', () => {
    const sfc = readSrc('views/ContactView.vue')
    assert.equal(elementsOf(sfc).filter((el) => el.tag === 'FormField').length, 4, 'name, email, church and message')
    assert.deepEqual(fieldsWithoutClearOnInput(sfc, 'ContactView.vue'), [], 'a field that keeps its error until blur moves the Send button when it blurs')
    const form = elementsOf(sfc).find((el) => el.tag === 'form')
    assert.ok(form?.props.some((p) => p.type === 7 && p.name === 'on' && p.arg?.content === 'pointerdown'), 'the form notes when the pointer goes down on Send, so the blur that follows does not move it')
  })

  test('every focusable control of the page has the shared anchor offset as its scroll margin (review round 2, Quinn Q2)', () => {
    assert.equal(focusScrollMarginRules(readSrc('views/ContactView.vue')).length, 1, 'Tab from Send to the first card link must not stop under the sticky navbar')
  })

  test('the email check is the length-capped rule from lib/contactForm.ts, not a pattern written in the view (review round 2, Vera 1)', () => {
    const script = descriptorOf(readSrc('views/ContactView.vue'), 'ContactView.vue').scriptSetup?.content ?? ''
    assert.ok(script.includes("from '@/lib/contactForm.ts'") && script.includes('looksLikeEmail(email.value)'))
  })

  test('CONTROL: the clear-on-input and scroll-margin predicates fire on a planted fault', () => {
    const ok = `<template><form @pointerdown="x"><FormField v-model="name" @update:model-value="clearError('name')" /><FormField v-model="org" @update:modelValue="clearError('org')" /></form></template>`
    assert.deepEqual(fieldsWithoutClearOnInput(ok), [])
    assert.deepEqual(fieldsWithoutClearOnInput(ok.replace(`clearError('org')`, `clearError('name')`)), ['org'], 'a listener that clears another field')
    assert.deepEqual(fieldsWithoutClearOnInput(ok.replace(' @update:modelValue="clearError(\'org\')"', '')), ['org'], 'a field with no listener')
    assert.deepEqual(fieldsWithoutClearOnInput('<template><FormField @blur="x" /></template>'), ['(no v-model)'])
    const css = '<template><p/></template><style scoped>.contact-page :deep(:is(a[href], button, input, select, textarea)) { scroll-margin-top: var(--sc-anchor-offset); }</style>'
    assert.equal(focusScrollMarginRules(css).length, 1)
    assert.equal(focusScrollMarginRules(css.replace('--sc-anchor-offset', '--nav-height')).length, 0, 'a different offset is not the shared one')
    assert.equal(focusScrollMarginRules(css.replace(' button,', '')).length, 0, 'a rule that leaves out the button')
    assert.equal(focusScrollMarginRules(css.replace('scroll-margin-top', 'margin-top')).length, 0)
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

  test('no two h2 on the page read the same: the hub heading is not the Getting Started category heading (review round 1 M8)', async () => {
    const h2 = headingsOf(await html('DocsView.vue')).filter((h) => h.level === 2).map((h) => h.text.toLowerCase())
    assert.ok(h2.length >= 7, 'the hub heading and the six category sections')
    assert.deepEqual(h2.filter((t, i) => h2.indexOf(t) !== i), [], 'a repeated h2 text')
  })

  test('the current item is marked by a border, which forced colors keeps, not a box-shadow, which it deletes (review round 1 M8)', () => {
    const css = styleOf(readSrc('views/DocsView.vue'))
    assert.equal(declaration(css, '.nav-item.is-active', 'border-left'), '3px solid var(--sc-primary)')
    assert.equal(declaration(css, '.nav-item.is-active', 'padding-left'), '7px', 'the border takes 3px of the 10px padding, so no row moves')
    assert.equal(declaration(css, '.nav-item.is-active', 'box-shadow'), undefined, 'a shadow is the cue forced colors removes')
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
    assert.ok(heads.some((h) => h.level === 2 && h.text === 'Getting started with SelahCue'), 'the hub heading (Figma: Getting started), made distinct from the Getting Started category section')
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

/**
 * FIXTURE releases, only to render the card layout the page keeps for its first real release (Figma 501:154). They are test
 * data, not copy: they never go through the ledger, and no real release looks like these.
 */
const FIXTURE_RELEASES = [
  { version: 'v9.9.9', date: 'January 1, 2000', tag: 'Fixture tag', highlights: [
    { type: 'new', title: 'Fixture change one', desc: 'Fixture text one.' },
    { type: 'new', title: 'Fixture change two', desc: 'Fixture text two.' },
    { type: 'improved', title: 'Fixture change three', desc: 'Fixture text three.' },
    { type: 'fixed', title: 'Fixture change four', desc: 'Fixture text four.' },
  ] },
  { version: 'v9.9.8', date: 'January 2, 2000', tag: 'Fixture tag', highlights: [
    { type: 'new', title: 'Fixture change five', desc: 'Fixture text five.' },
    { type: 'improved', title: 'Fixture change six', desc: 'Fixture text six.' },
    { type: 'fixed', title: 'Fixture change seven', desc: 'Fixture text seven.' },
  ] },
  { version: 'v9.9.7', date: 'January 3, 2000', tag: 'Fixture tag', highlights: [{ type: 'new', title: 'Fixture change eight', desc: 'Fixture text eight.' }] },
]
const changelogWithReleases = (): Promise<string> => renderView(server, 'ChangelogView.vue', '/changelog', { set: { releases: FIXTURE_RELEASES } })

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

  // ClickUp 17tnw2b0x3h: nothing has shipped, so the page lists no release, no date and no "latest" tag.
  test('with no release shipped the page shows an honest empty state, not an invented release', async () => {
    const page = await html('ChangelogView.vue')
    assert.equal(withClass(page, 'release-card').length, 0, 'no release card')
    assert.equal(withClass(page, 'release-empty').length, 1, 'one empty state')
    const heads = headingsOf(page)
    assert.deepEqual(heads.filter((h) => h.level === 2).map((h) => h.text), ['No release notes yet'])
    assert.deepEqual(outlineProblems(heads), [])
    assert.doesNotMatch(textOf(page), /\bv\d+\.\d+\.\d+\b|Latest Release/i, 'no version number and no "latest" tag')
  })

  test('the release list in the source is empty: an invented release cannot return without a deliberate edit', () => {
    const script = descriptorOf(readSrc('views/ChangelogView.vue'), 'ChangelogView.vue').scriptSetup?.content ?? ''
    assert.match(script, /const releases: Release\[\] = \[\]/, 'the releases array must stay empty until a real release ships')
  })

  test('one card per release, each led by an h2 version, and no sticky meta column (changelog-02, changelog-bug-01)', async () => {
    const page = await changelogWithReleases()
    const cards = withClass(page, 'release-card')
    assert.equal(cards.length, 3)
    assert.equal(withClass(page, 'release-empty').length, 0, 'the empty state is gone once a release exists')
    assert.equal(withClass(page, 'timeline-meta').length, 0, 'the left meta column is gone')
    const heads = headingsOf(page)
    assert.deepEqual(heads.filter((h) => h.level === 2).map((h) => h.text), ['v9.9.9', 'v9.9.8', 'v9.9.7'])
    assert.ok(heads.filter((h) => h.level === 3).length >= 8, 'the per-change titles stay h3')
    assert.deepEqual(outlineProblems(heads), [])
  })

  test('changes are grouped by type: one label per group, not one per change (changelog-02)', async () => {
    const page = await changelogWithReleases()
    const labels = badgesOf(page).filter((b) => b.classes.includes('change-label'))
    assert.deepEqual(labels.map((b) => b.text), ['New', 'Improved', 'Fixed', 'New', 'Improved', 'Fixed', 'New'])
    assert.equal(withClass(page, 'change-group').length, 7)
  })

  test('the type labels use the variants PR 173 defined: New preview, Improved accent, Fixed warn (changelog-03)', async () => {
    const page = await changelogWithReleases()
    const labels = badgesOf(page).filter((b) => b.classes.includes('change-label'))
    const variantOf = (text: string): Set<string> => new Set(labels.filter((b) => b.text === text).map((b) => b.variant))
    assert.deepEqual([...variantOf('New')], ['preview'])
    assert.deepEqual([...variantOf('Improved')], ['accent'])
    assert.deepEqual([...variantOf('Fixed')], ['warn'])
  })

  test('only the newest release carries a tag pill beside its date', async () => {
    const page = await changelogWithReleases()
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

/**
 * FIXTURE roles, only to render the row layout the page keeps for its first real role (Figma 503:173). Test data, not copy:
 * they never go through the ledger, and no real role looks like these.
 */
const FIXTURE_ROLES = [
  { title: 'Fixture role one', dept: 'Fixture dept A', location: 'Fixture place', type: 'Fixture type' },
  { title: 'Fixture role two', dept: 'Fixture dept B', location: 'Fixture place', type: 'Fixture type' },
  { title: 'Fixture role three', dept: 'Fixture dept C', location: 'Fixture place', type: 'Fixture type' },
]
const careersWithRoles = (): Promise<string> => renderView(server, 'CareersView.vue', '/careers', { set: { roles: FIXTURE_ROLES } })

describe('Careers (503:124): hero and a full-bleed roles band', () => {
  test('the hero is a CAREERS pill and the h1 "Build tools churches rely on" at the frame\'s 50/56 (careers-01)', async () => {
    const page = await html('CareersView.vue')
    const [h1] = headingsOf(page)
    assert.equal(h1?.text, 'Build tools churches rely on')
    assert.ok(textOf(page).includes('CAREERS'))
    const css = styleOf(readSrc('views/CareersView.vue'))
    assert.match(css, /@media \(min-width: 1200px\)\s*\{\s*\.hero-title\s*\{[^}]*font-size:\s*50px[^}]*line-height:\s*56px/)
    assert.match(css, /\.hero-title\s*\{[^}]*max-width:\s*500px/)
  })

  // ClickUp 17tnw2b0x3h: no company claim the repo does not back (remote-first, "zero compromise", "thousands of volunteer tech teams").
  test('the page makes no company claim: the culture strip is gone and the hero names only the product', async () => {
    const page = await html('CareersView.vue')
    assert.equal(withClass(page, 'culture-card').length, 0)
    assert.equal(withClass(page, 'culture-grid').length, 0)
    const text = textOf(page)
    assert.doesNotMatch(text, /remote|thousands|zero compromise|every single Sunday|flexible hours/i)
    assert.ok(!/\p{Extended_Pictographic}/u.test(text), 'no emoji')
    assert.doesNotMatch(styleOf(readSrc('views/CareersView.vue')), /culture/, 'and no style is left for it')
  })

  test('the roles sit in a full-bleed band under a centred "Open roles" heading (careers-04)', async () => {
    const page = await html('CareersView.vue')
    assert.ok(headingsOf(page).some((h) => h.level === 2 && h.text === 'Open roles'))
    assert.equal(withClass(page, 'roles-band').length, 1)
    const css = styleOf(readSrc('views/CareersView.vue'))
    assert.match(css, /\.roles-band\s*\{[^}]*background:\s*var\(--sc-surface-alt\)/)
    assert.match(css, /\.roles-list\s*\{[^}]*max-width:\s*940px/)
  })

  test('with no role open the band says so: no role, no tag, no Apply button, no "don\'t see your role" invitation', async () => {
    const page = await html('CareersView.vue')
    assert.equal(withClass(page, 'role-row').length, 0)
    assert.equal(withClass(page, 'role-tag').length, 0)
    assert.equal(withClass(page, 'roles-note').length, 0, 'the closing line invites people to a role that does not exist')
    const empty = withClass(page, 'roles-empty')[0]
    assert.ok(empty, 'the empty line is there')
    assert.ok(textOf(page.slice(empty.at, page.indexOf('</p>', empty.at))).startsWith('There are no open roles right now.'))
    assert.ok(!tagsOf(page).some((t) => t.name === 'a'), 'and nothing on the page links anywhere')
    assert.deepEqual(outlineProblems(headingsOf(page)), [])
  })

  test('the role list in the source is empty: an invented role cannot return without a deliberate edit', () => {
    const script = descriptorOf(readSrc('views/CareersView.vue'), 'CareersView.vue').scriptSetup?.content ?? ''
    assert.match(script, /const roles: Role\[\] = \[\]/, 'the roles array must stay empty until a real role opens')
  })

  test('each role row has three tag pills (department, place, type) and no single meta line (careers-04, careers-05)', async () => {
    const page = await careersWithRoles()
    const rows = withClass(page, 'role-row')
    assert.equal(rows.length, 3)
    assert.equal(withClass(page, 'role-tag').length, 9)
    assert.equal(withClass(page, 'role-meta').length, 0)
    assert.equal(withClass(page, 'roles-empty').length, 0, 'the empty line is gone once a role exists')
    const css = styleOf(readSrc('views/CareersView.vue'))
    assert.match(css, /\.role-tag\s*\{[^}]*color:\s*var\(--sc-text-secondary\)/)
    assert.match(css, /\.role-tag\s*\{[^}]*background:\s*var\(--sc-elevated\)/)
  })

  test('the Apply links are distinct: each name carries its role, and still contains the visible text (careers-06)', async () => {
    const page = await careersWithRoles()
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

  test('the closing line is plain text: no link to a form that cannot send, and no mailbox (careers-04, careers-08, review round 1 M1)', async () => {
    const page = await careersWithRoles()
    const note = withClass(page, 'roles-note')[0]
    assert.ok(note, 'the closing line is there')
    const line = page.slice(note.at, page.indexOf('</p>', note.at))
    assert.ok(textOf(line).startsWith("Don't see your role?"))
    assert.ok(!/reach out|contact us|get in touch|write to|email|apply/i.test(textOf(line)), 'it names no way to reach anyone')
    assert.ok(!/<a[\s>]/.test(line), 'it carries no link')
    assert.ok(!/@selahcue/.test(textOf(page)), 'no invented mailbox')
    const apply = tagsOf(page).filter((t) => t.name === 'a' && (t.attrs['href'] ?? '') === '/contact')
    assert.equal(apply.length, 3, 'the role buttons keep their destination, the contact page')
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

  test('the text column is 780 wide: the shell is sized for the contents column, its gap and the 780 (privacy-09, terms-09, review round 1 M13)', () => {
    assert.equal(declaration(page, '.legal-text', 'max-width'), '780px')
    // 24 + 24 gutters at desktop + 260 contents + 48 gap + 780 text = 1136. A narrower shell leaves the grid, not max-width, to
    // set the column, and 1120 measured 764.
    assert.equal(declaration(page, '.legal-shell', 'max-width'), '1136px')
    assert.equal(declaration(page, '.legal-layout', 'grid-template-columns'), '260px minmax(0, 1fr)')
    assert.equal(declaration(page, '.legal-layout', 'gap'), '48px')
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
