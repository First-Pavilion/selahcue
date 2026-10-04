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
  headingsOf,
  outlineProblems,
  renderView,
  startViewServer,
  tagsOf,
  textOf,
  withClass,
  type Heading,
} from './fixtures/viewRender.ts'

/** Grows as each page is brought to its frame; the final list is all nine. */
const PAGES = [
  { file: 'ContactView.vue', route: '/contact' },
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

