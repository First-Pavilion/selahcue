/**
 * The five shared components the Figma fidelity audit assigned to ClickUp 17tnw2b2cew:
 * `UiBadge`, `FormField`, `FaqAccordion`, `PricingCard` and `ConfirmDialog`.
 *
 * Two kinds of check, both without a browser:
 *
 *   1. SOURCE checks, over the real tree. Vue's own SFC compiler parses every `.vue` file, so
 *      the AST that ships is what is read (not a regex over text).
 *   2. RENDER checks. Vite compiles the real components (`ssrLoadModule`) and Vue renders them
 *      to a string, the same pattern `legalPage.test.ts` uses.
 *
 * What neither can see (computed colour, geometry, real focus movement) is covered by
 * `scripts/shared_components_headless.py`, which drives the gallery in `tests/gallery/` in a
 * real browser.
 *
 * EVERY PREDICATE HERE HAS ONE DEFINITION and its positive control consumes THAT definition,
 * the rule `authViews.test.ts` records after a ban and the control that vouched for it were
 * two copies and the ban went dead. A control that does not fail on a planted fault is a
 * decoration, so each group ends with the fault planted.
 *
 * What these guard, in the order of the ticket's acceptance criteria:
 *
 *   - a view cannot pass UiBadge a variant it does not define (today `accent` and `warn` are
 *     used in about 20 places and render unstyled);
 *   - the UiBadge `text` attribute is never rendered: `PricingView` passes `text="Save 20%"`,
 *     which is an unbacked claim (audit pricing-18, class C, owner decision: honest content
 *     wins), and it has stayed invisible only because UiBadge has no such prop;
 *   - the default markup of FormField is pinned (`fixtures/formfield-default.json`). It is the
 *     markup the audit branch shipped plus exactly three named additions, each with its own
 *     test below: `aria-required` on a required field, `spellcheck`/`autocorrect`/`autocapitalize`
 *     off on a password input, and Vue's empty `v-if` placeholder (ignored by the comparison).
 *     "The look is unchanged" is proved in a browser, by `shared_components_headless.py
 *     --compare-defaults`, not here;
 *   - FAQ answers are wired to their buttons and removed from the accessibility tree when
 *     collapsed;
 *   - a plan's call to action is a link or a disabled control, never a button that does
 *     nothing;
 *   - the confirm dialog names itself and its description for assistive technology.
 */
import assert from 'node:assert/strict'
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import test, { after, before, describe, mock } from 'node:test'
import { fileURLToPath } from 'node:url'

import vue from '@vitejs/plugin-vue'
import ts from 'typescript'
import { createSSRApp, h, type Component } from 'vue'
import { parse } from 'vue/compiler-sfc'
import { renderToString } from 'vue/server-renderer'
import { createServer, type ViteDevServer } from 'vite'

import { GALLERY_TITLE, unsafeOutDir } from './gallery/outDir.ts'

const ROOT = fileURLToPath(new URL('../', import.meta.url))
const SRC = path.join(ROOT, 'src')
const GOLDEN = path.join(ROOT, 'tests', 'fixtures', 'formfield-default.json')

let server: ViteDevServer
const loaded = new Map<string, Component>()

before(async () => {
  server = await createServer({
    root: ROOT,
    configFile: false,
    logLevel: 'silent',
    appType: 'custom',
    plugins: [vue()],
    resolve: { alias: { '@': SRC } },
    server: { middlewareMode: true, hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] },
  })
})

after(async () => {
  await server?.close()
})

async function component(name: string): Promise<Component> {
  const cached = loaded.get(name)
  if (cached) return cached
  const mod = (await server.ssrLoadModule(`/src/components/${name}.vue`)) as { default: Component }
  loaded.set(name, mod.default)
  return mod.default
}

type Slots = Record<string, () => unknown>

interface Rendered {
  html: string
  /** Everything a `<Teleport to="body">` sent out of the tree. */
  teleported: string
}

async function render(name: string, props: Record<string, unknown> = {}, slots: Slots = {}): Promise<Rendered> {
  const Comp = await component(name)
  const app = createSSRApp({
    render: () => h(Comp, props, slots as never),
  })
  // vue-router's link, as an anchor carrying the destination: all these tests need to see.
  app.component('RouterLink', {
    props: { to: { type: [String, Object], required: true } },
    setup(p: { to: unknown }, { slots: s }: { slots: Record<string, () => unknown> }) {
      return () => h('a', { href: String(p.to) }, s.default?.() as never)
    },
  })
  const ctx: { teleports?: Record<string, string> } = {}
  const html = await renderToString(app, ctx)
  return { html, teleported: ctx.teleports?.['body'] ?? '' }
}

// --------------------------------------------------------------------------- tiny HTML reading

interface Tag {
  name: string
  attrs: Record<string, string>
  /** Offset of the `<` in the source string; lets a test assert DOM ORDER. */
  at: number
}

/** Opening tags of well-formed, double-quoted SSR output. Not a general HTML parser. */
function tags(html: string): Tag[] {
  const out: Tag[] = []
  for (const m of html.matchAll(/<([a-zA-Z][\w-]*)((?:\s+[^\s=>/]+(?:="[^"]*")?)*)\s*\/?>/g)) {
    const attrs: Record<string, string> = {}
    for (const a of (m[2] ?? '').matchAll(/([^\s=>/]+)(?:="([^"]*)")?/g)) attrs[a[1] as string] = a[2] ?? ''
    out.push({ name: m[1] as string, attrs, at: m.index ?? 0 })
  }
  return out
}

const withClass = (html: string, cls: string): Tag[] =>
  tags(html).filter((t) => (t.attrs['class'] ?? '').split(/\s+/).includes(cls))

const has = (t: Tag, attr: string): boolean => Object.prototype.hasOwnProperty.call(t.attrs, attr)

function textOf(html: string): string {
  return html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

// ---------------------------------------------------------------- reading the template sources

interface AttrProp {
  type: 6
  name: string
  value?: { content: string }
}
interface DirectiveProp {
  type: 7
  name: string
  arg?: { content: string }
  exp?: { content: string }
}
interface ElementNode {
  type: 1
  tag: string
  props: Array<AttrProp | DirectiveProp>
  children: Node[]
}
type Node = ElementNode | { type: number; children?: Node[] }

function elementsOf(sfc: string, filename = 'fixture.vue'): ElementNode[] {
  const { descriptor, errors } = parse(sfc, { filename })
  assert.equal(errors.length, 0, `${filename} did not parse: ${errors.map(String).join('; ')}`)
  const root = descriptor.template?.ast as { children: Node[] } | undefined
  if (!root) return []
  const found: ElementNode[] = []
  const walk = (node: Node): void => {
    if (node.type === 1) found.push(node as ElementNode)
    for (const child of (node as { children?: Node[] }).children ?? []) {
      if (typeof child === 'object') walk(child)
    }
  }
  for (const child of root.children) walk(child)
  return found
}

function prop(el: ElementNode, name: string): AttrProp | DirectiveProp | undefined {
  return el.props.find((p) => (p.type === 6 ? p.name === name : p.name === 'bind' && p.arg?.content === name))
}

function allVueFiles(dir: string): string[] {
  return readdirSync(dir, { recursive: true, withFileTypes: true })
    .filter((e) => e.isFile() && e.name.endsWith('.vue'))
    .map((e) => path.join(e.parentPath, e.name))
}

const read = (rel: string): string => readFileSync(path.join(SRC, rel), 'utf8')

// ------------------------------------------------------------------------------------ UiBadge

const isUiBadge = (tag: string): boolean => tag === 'UiBadge' || tag === 'ui-badge'

/**
 * Every value a ternary chain can produce, or `null` when some branch is not a string
 * literal (an identifier, a call, a member access): that cannot be checked statically, and
 * "cannot check" must fail, not pass.
 */
function resultsOf(expression: string): string[] | null {
  const file = ts.createSourceFile('expr.ts', `(${expression})`, ts.ScriptTarget.ES2023, true)
  const stmt = file.statements[0]
  if (!stmt || !ts.isExpressionStatement(stmt)) return null
  const walk = (node: ts.Expression): string[] | null => {
    if (ts.isParenthesizedExpression(node)) return walk(node.expression)
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return [node.text]
    if (ts.isConditionalExpression(node)) {
      const a = walk(node.whenTrue)
      const b = walk(node.whenFalse)
      return a && b ? [...a, ...b] : null
    }
    return null
  }
  return walk(stmt.expression)
}

/** The variants and sizes a UiBadge allows, read from its own validators. */
function badgeContract(source: string): { variants: string[]; sizes: string[]; css: string } {
  const { descriptor } = parse(source, { filename: 'UiBadge.vue' })
  const script = descriptor.scriptSetup?.content ?? ''
  const list = (key: string): string[] => {
    const m = script.match(new RegExp(`${key}:\\s*\\{[\\s\\S]*?validator:[^\\[]*\\[([^\\]]*)\\]`))
    assert.ok(m, `UiBadge.vue has no \`${key}\` validator list to read`)
    return [...(m[1] as string).matchAll(/'([\w-]+)'/g)].map((x) => x[1] as string)
  }
  return { variants: list('variant'), sizes: list('size'), css: descriptor.styles.map((s) => s.content.replace(/\/\*[\s\S]*?\*\//g, '')).join('\n') }
}

/** Every way a template uses UiBadge that the component does not define. Empty when clean. */
function badgeViolations(sfc: string, allowed: { variants: string[]; sizes: string[] }, where: string): string[] {
  const out: string[] = []
  for (const el of elementsOf(sfc, where).filter((e) => isUiBadge(e.tag))) {
    for (const [name, set] of [
      ['variant', allowed.variants],
      ['size', allowed.sizes],
    ] as const) {
      const p = prop(el, name)
      if (!p) continue
      const found = p.type === 6 ? [p.value?.content ?? ''] : resultsOf((p.exp?.content ?? '').trim())
      if (!found) {
        out.push(`${where}: <UiBadge :${name}="${(p as DirectiveProp).exp?.content}"> is not a plain choice between literals, so it cannot be checked`)
        continue
      }
      for (const v of found) if (!set.includes(v)) out.push(`${where}: <UiBadge ${name}="${v}"> is not defined by UiBadge (allowed: ${set.join(', ')})`)
    }
  }
  return out
}

describe('UiBadge: a view cannot pass a variant the badge does not define', () => {
  const contract = badgeContract(read('components/UiBadge.vue'))

  test('besides the six it had, UiBadge defines accent, warn and eyebrow', () => {
    for (const v of ['live', 'preview', 'ready', 'ndi', 'featured', 'new', 'accent', 'warn', 'eyebrow']) {
      assert.ok(contract.variants.includes(v), `UiBadge does not allow variant "${v}" (allowed: ${contract.variants.join(', ')})`)
    }
  })

  test('every allowed variant has a style rule, and every style rule is an allowed variant', () => {
    const ruled = new Set([...contract.css.matchAll(/\.variant-([\w-]+)/g)].map((m) => m[1] as string))
    for (const v of contract.variants) assert.ok(ruled.has(v), `variant "${v}" is allowed but has no \`.variant-${v}\` rule, so it would render unstyled`)
    for (const v of ruled) assert.ok(contract.variants.includes(v), `a \`.variant-${v}\` rule exists for a variant the validator does not allow`)
  })

  test('REAL TREE: every UiBadge in every view and component uses a defined variant and size', () => {
    const problems: string[] = []
    let badges = 0
    for (const file of allVueFiles(SRC)) {
      const sfc = readFileSync(file, 'utf8')
      badges += elementsOf(sfc, file).filter((e) => isUiBadge(e.tag)).length
      problems.push(...badgeViolations(sfc, contract, path.relative(SRC, file)))
    }
    assert.ok(badges > 40, `only ${badges} UiBadge uses were found: the scan is looking in the wrong place`)
    assert.deepEqual(problems, [])
  })

  test('CONTROL: the same predicate flags an undefined variant, an undefined size and an unverifiable binding', () => {
    const bad = (t: string): string[] => badgeViolations(`<template><div>${t}</div></template>`, contract, 'fixture.vue')
    assert.equal(bad('<UiBadge variant="accentt">x</UiBadge>').length, 1)
    assert.equal(bad('<UiBadge variant="accent" size="xl">x</UiBadge>').length, 1)
    assert.equal(bad(`<UiBadge :variant="s === 'a' ? 'preview' : s === 'b' ? 'success' : 'warn'">x</UiBadge>`).length, 1)
    assert.equal(bad('<UiBadge :variant="someVariable">x</UiBadge>').length, 1)
    assert.equal(bad(`<UiBadge :variant="s === 'a' ? 'preview' : 'warn'" size="sm">x</UiBadge>`).length, 0)
  })
})

describe('UiBadge: rendering', () => {
  test('a variant renders its class and the slot content', async () => {
    const { html } = await render('UiBadge', { variant: 'accent' }, { default: () => 'MOST POPULAR' })
    const [badge] = withClass(html, 'ui-badge')
    assert.ok(badge, html)
    assert.ok((badge.attrs['class'] as string).includes('variant-accent'))
    assert.equal(textOf(html), 'MOST POPULAR')
  })

  test('the `text` attribute is NOT rendered, and development says why', async () => {
    const warn = mock.method(console, 'warn', () => undefined)
    try {
      const { html } = await render('UiBadge', { variant: 'accent', text: 'Save 20%' })
      assert.ok(!html.includes('Save 20%'), `the unbacked claim reached the markup: ${html}`)
      assert.equal(textOf(html), '', 'no text content: the slot is the only content API')
      assert.ok(
        warn.mock.calls.some((c) => String(c.arguments[0]).includes('UiBadge') && String(c.arguments[0]).includes('text')),
        'passing `text` must warn, not be dropped silently',
      )
    } finally {
      warn.mock.restore()
    }
  })

  test('the slot form of the same badge DOES render (the control for the test above)', async () => {
    const { html } = await render('UiBadge', { variant: 'accent' }, { default: () => 'Save 20%' })
    assert.ok(html.includes('Save 20%'))
  })
})

describe('UiBadge: the brand ink is one overridable custom property', () => {
  const css = badgeContract(read('components/UiBadge.vue')).css
  const rule = (variant: string): string => {
    const m = css.match(new RegExp(`\\.variant-${variant}\\s*\\{([^}]*)\\}`))
    assert.ok(m, `no .variant-${variant} rule`)
    return m[1] as string
  }

  test('featured, accent and eyebrow take their ink from --ui-badge-ink, each falling back to what it renders today', () => {
    for (const v of ['featured', 'accent', 'eyebrow']) {
      assert.match(rule(v), /color:\s*var\(--ui-badge-ink,\s*var\(--sc-[a-z-]+\)\)/, `.variant-${v} does not read the single ink property`)
      assert.ok(!/#[0-9a-f]{3,8}\b/i.test(rule(v).replace(/background[^;]*;/, '')), `.variant-${v} hard-codes a colour next to the ink property`)
    }
  })

  test('the property is declared nowhere in the component, so a single line outside it (the token file) sets it', () => {
    assert.ok(!/--ui-badge-ink\s*:/.test(css), 'declaring the property inside UiBadge would make it impossible to override from outside')
  })
})

// ---------------------------------------------------------------------------------- FaqAccordion

const FAQ_ITEMS = [
  { question: 'First?', answer: 'Answer one.' },
  { question: 'Second?', answer: 'Answer two.' },
  { question: 'Third?', answer: 'Answer three.' },
]

/** Every accessibility wiring fault in rendered accordion markup. Empty when sound. */
function faqProblems(html: string, openIndex: number | null): string[] {
  const out: string[] = []
  const all = tags(html)
  const buttons = all.filter((t) => t.name === 'button')
  const regions = all.filter((t) => t.attrs['role'] === 'region')
  if (buttons.length === 0) return ['no question buttons']
  if (regions.length !== buttons.length) out.push(`${buttons.length} buttons but ${regions.length} regions`)
  const ids = new Set(all.map((t) => t.attrs['id']).filter(Boolean))
  buttons.forEach((b, i) => {
    const controls = b.attrs['aria-controls']
    const region = regions[i]
    if (!controls) out.push(`button ${i} has no aria-controls`)
    else if (!region || region.attrs['id'] !== controls) out.push(`button ${i} aria-controls="${controls}" is not the id of its region`)
    if (!b.attrs['id']) out.push(`button ${i} has no id for the region to be labelled by`)
    if (region && region.attrs['aria-labelledby'] !== b.attrs['id']) out.push(`region ${i} is not labelled by its button`)
    const expanded = b.attrs['aria-expanded']
    if (expanded !== (i === openIndex ? 'true' : 'false')) out.push(`button ${i} aria-expanded="${expanded}"`)
    if (region) {
      const hidden = has(region, 'inert') && region.attrs['aria-hidden'] === 'true'
      if (i === openIndex && (has(region, 'inert') || has(region, 'aria-hidden'))) out.push(`the OPEN answer ${i} is hidden from assistive technology`)
      if (i !== openIndex && !hidden) out.push(`collapsed answer ${i} is still exposed to assistive technology (needs inert and aria-hidden)`)
    }
  })
  if (new Set(buttons.map((b) => b.attrs['id'])).size !== buttons.length) out.push('button ids are not unique')
  for (const id of ids) if (html.split(`id="${id}"`).length > 2) out.push(`id "${id}" appears more than once`)
  return out
}

describe('FaqAccordion: each answer is wired to its question and hidden when collapsed', () => {
  test('the first item open: aria-controls, region, aria-labelledby, aria-expanded, collapsed answers out of the tree', async () => {
    const { html } = await render('FaqAccordion', { items: FAQ_ITEMS, defaultOpen: 0 })
    assert.deepEqual(faqProblems(html, 0), [])
  })

  test('nothing open: every answer is hidden', async () => {
    const { html } = await render('FaqAccordion', { items: FAQ_ITEMS, defaultOpen: -1 })
    assert.deepEqual(faqProblems(html, null), [])
  })

  test('two accordions on one page never share an id', async () => {
    const Comp = await component('FaqAccordion')
    const app = createSSRApp({ render: () => h('div', [h(Comp, { items: FAQ_ITEMS }), h(Comp, { items: FAQ_ITEMS })]) })
    const html = await renderToString(app)
    const ids = tags(html).map((t) => t.attrs['id']).filter(Boolean)
    assert.equal(ids.length, 12)
    assert.equal(new Set(ids).size, 12, `duplicate ids: ${ids.join(', ')}`)
  })

  test('the plain accordion is the default and the boxed style is opt-in', async () => {
    const plain = await render('FaqAccordion', { items: FAQ_ITEMS })
    const boxed = await render('FaqAccordion', { items: FAQ_ITEMS, boxed: true })
    assert.equal(withClass(plain.html, 'is-boxed').length, 0)
    assert.equal(withClass(boxed.html, 'is-boxed').length, 1)
    assert.deepEqual(faqProblems(boxed.html, 0), [], 'the boxed style keeps the same wiring')
  })

  test('the toggle icon is hidden from assistive technology', async () => {
    const { html } = await render('FaqAccordion', { items: FAQ_ITEMS })
    const svgs = tags(html).filter((t) => t.name === 'svg')
    assert.equal(svgs.length, 3)
    for (const s of svgs) assert.equal(s.attrs['aria-hidden'], 'true')
  })

  test('CONTROL: the predicate flags each fault when it is planted', async () => {
    const { html } = await render('FaqAccordion', { items: FAQ_ITEMS, defaultOpen: 0 })
    assert.ok(faqProblems(html.replaceAll(/ aria-controls="[^"]*"/g, ''), 0).some((p) => p.includes('aria-controls')))
    assert.ok(faqProblems(html.replaceAll(' inert', ''), 0).some((p) => p.includes('exposed')))
    assert.ok(faqProblems(html.replaceAll(' aria-hidden="true"', ' aria-hidden="false"'), 0).some((p) => p.includes('exposed')))
    assert.ok(faqProblems(html.replaceAll('role="region"', 'role="group"'), 0).some((p) => p.includes('regions')))
    assert.ok(faqProblems(html.replaceAll('aria-expanded="true"', 'aria-expanded="false"'), 0).some((p) => p.includes('aria-expanded')))
  })
})

// ----------------------------------------------------------------------------------- PricingCard

const PLAN = {
  name: 'Pro',
  price: 19,
  period: 'month',
  description: 'For multi-output churches.',
  features: ['One', 'Two', 'Three'],
  cta: 'Get Pro',
}

/**
 * Every control in a template that would do nothing when activated. A "button" is a native
 * `<button>` or a `<UiButton>` without `to`/`href`; it is fine when disabled or when it has a
 * click handler. (`downloadView.test.ts` states the same rule for the Download page.)
 */
function deadControls(sfc: string): string[] {
  const out: string[] = []
  for (const el of elementsOf(sfc)) {
    const isButton = el.tag === 'button' || el.tag === 'UiButton' || el.tag === 'ui-button'
    if (!isButton) continue
    const link = prop(el, 'to') || prop(el, 'href')
    const disabled = prop(el, 'disabled')
    const click = el.props.some((p) => p.type === 7 && p.name === 'on' && p.arg?.content === 'click')
    if (!link && !disabled && !click) out.push(`<${el.tag}> has no destination, no disabled state and no click handler`)
  }
  return out
}

describe('PricingCard: a plan button is a link or an honest disabled control, never a dead button', () => {
  test('SOURCE: the template has no control without an action', () => {
    assert.deepEqual(deadControls(read('components/PricingCard.vue')), [])
  })

  test('CONTROL: the source predicate flags the template the audit found (UiButton with only `block`)', () => {
    const before = '<template><div><UiButton :variant="v" size="md" block>{{ cta }}</UiButton></div></template>'
    assert.equal(deadControls(before).length, 1)
    assert.equal(deadControls('<template><UiButton :to="to">x</UiButton></template>').length, 0)
    assert.equal(deadControls('<template><UiButton disabled>x</UiButton></template>').length, 0)
    assert.equal(deadControls('<template><button @click="go">x</button></template>').length, 0)
  })

  test('with a destination the CTA is a link to it and there is no button at all', async () => {
    const { html } = await render('PricingCard', { ...PLAN, to: '/contact' })
    const links = tags(html).filter((t) => t.name === 'a')
    assert.equal(links.length, 1)
    assert.equal(links[0]?.attrs['href'], '/contact')
    assert.equal(tags(html).filter((t) => t.name === 'button').length, 0)
    assert.ok(textOf(html).includes('Get Pro'))
  })

  test('without one the CTA is a DISABLED control, says so in words, and is described by that note', async () => {
    const { html } = await render('PricingCard', PLAN)
    const buttons = tags(html).filter((t) => t.name === 'button')
    assert.equal(buttons.length, 1)
    const [button] = buttons
    assert.ok(button && has(button, 'disabled'), 'an enabled button with no action')
    const note = tags(html).find((t) => t.attrs['id'] === button.attrs['aria-describedby'])
    assert.ok(note, 'the disabled CTA is not described by anything')
    assert.match(textOf(html), /Not available yet/)
    assert.equal(tags(html).filter((t) => t.name === 'a').length, 0)
  })

  test('the `block` prop UiButton never had is no longer passed (it reached the DOM as an attribute)', async () => {
    const { html } = await render('PricingCard', { ...PLAN, to: '/contact' })
    assert.ok(!tags(html).some((t) => has(t, 'block')))
  })

  test('the popular tag is a chip in the card header row, not an absolutely positioned tag over the border', async () => {
    const { html } = await render('PricingCard', { ...PLAN, popular: true, to: '/pricing' })
    assert.equal(withClass(html, 'popular-tag').length, 0, 'the floating tag wrapper is gone')
    const header = withClass(html, 'plan-header')[0]
    assert.ok(header, 'no header row')
    const name = tags(html).find((t) => t.name === 'h3')
    const chip = withClass(html, 'ui-badge')[0]
    assert.ok(name && chip)
    assert.ok(name.at > header.at && chip.at > name.at, 'the chip must sit after the plan name, in the same header row')
    const afterHeader = html.slice(header.at)
    assert.ok(afterHeader.indexOf('MOST POPULAR') < afterHeader.indexOf('plan-price-box'), 'the chip is inside the header, above the price')
    assert.ok((chip.attrs['class'] as string).includes('variant-accent'))
  })

  test('the free and church cards have no chip', async () => {
    const { html } = await render('PricingCard', PLAN)
    assert.ok(!html.includes('MOST POPULAR'))
    assert.equal(withClass(html, 'ui-badge').length, 0)
  })

  test('the call to action comes before the divider and the ticks are SVG, not a text glyph', async () => {
    const { html } = await render('PricingCard', { ...PLAN, to: '/contact' })
    assert.ok(html.indexOf('Get Pro') < html.indexOf('features-divider'))
    assert.ok(!html.includes('✓'))
    const ticks = tags(html).filter((t) => t.name === 'svg' && (t.attrs['class'] ?? '').includes('check-icon'))
    assert.equal(ticks.length, 3)
    for (const t of ticks) assert.equal(t.attrs['aria-hidden'], 'true')
  })

  test('REAL TREE: every PricingCard in a view still passes the props the card requires', () => {
    const required = ['name', 'price', 'description', 'features', 'cta']
    let uses = 0
    for (const file of allVueFiles(path.join(SRC, 'views'))) {
      for (const el of elementsOf(readFileSync(file, 'utf8'), file).filter((e) => e.tag === 'PricingCard')) {
        uses++
        for (const r of required) assert.ok(prop(el, r), `${path.relative(SRC, file)}: <PricingCard> has no ${r}`)
      }
    }
    assert.ok(uses >= 2, 'the scan found fewer PricingCard uses than Home and Pricing')
  })
})

// -------------------------------------------------------------------------------------- FormField

const GOLDEN_CASES: Record<string, Record<string, unknown>> = {
  plain: { id: 'f1', label: 'Email', modelValue: '' },
  'required-with-placeholder': { id: 'f2', label: 'Name', modelValue: 'Ada', required: true, placeholder: 'Your name', autocomplete: 'name' },
  'with-error': { id: 'f3', label: 'Email', type: 'email', modelValue: 'x', error: 'Enter a valid email address.' },
  'with-hint': { id: 'f4', label: 'Church', modelValue: '', hint: 'Optional.' },
  textarea: { id: 'f5', label: 'Message', type: 'textarea', modelValue: 'hello', maxLength: 2000 },
  password: { id: 'f6', label: 'Password', type: 'password', modelValue: 'secret', autocomplete: 'current-password' },
  'password-with-error': { id: 'f7', label: 'Password', type: 'password', modelValue: '', error: 'Enter your password.' },
  disabled: { id: 'f8', label: 'Locked', modelValue: 'x', disabled: true },
}

/**
 * What is not part of "the markup" when two renders are compared: the empty comment Vue leaves
 * where a `v-if` is false (adding the label-row slot adds one to every field: no content, no
 * attribute, no layout) and the `data-v-xxxxxxxx` scope hash, which the Vue plugin derives from
 * the file's PATH in development but also from its SOURCE in a production build, so it must not
 * decide whether a field changed.
 */
function bare(html: string): string {
  return html.replaceAll('<!---->', '').replace(/ data-v-[0-9a-f]{8}/g, '')
}

/** The cases whose markup differs, by name. Empty when the render matches the recording. */
function goldenDifferences(got: Record<string, string>, want: Record<string, string>): string[] {
  const names = [...new Set([...Object.keys(got), ...Object.keys(want)])].sort()
  return names.filter((n) => got[n] === undefined || want[n] === undefined || bare(got[n]) !== bare(want[n]))
}

async function renderGoldenCases(): Promise<Record<string, string>> {
  const got: Record<string, string> = {}
  for (const [name, props] of Object.entries(GOLDEN_CASES)) got[name] = bare((await render('FormField', props)).html)
  return got
}

describe('FormField: the default markup of every existing form is pinned', () => {
  test('GOLDEN: default props render what was recorded', async () => {
    const got = await renderGoldenCases()
    if (process.env['UPDATE_GOLDEN'] === '1') {
      writeFileSync(GOLDEN, JSON.stringify(got, null, 2) + '\n')
      return
    }
    assert.ok(existsSync(GOLDEN), 'tests/fixtures/formfield-default.json is missing; record it with UPDATE_GOLDEN=1')
    const want = JSON.parse(readFileSync(GOLDEN, 'utf8')) as Record<string, string>
    assert.deepEqual(goldenDifferences(got, want), [], 'default markup changed for these cases')
  })

  test('CONTROL: the comparison itself reports a planted difference, a missing case and an extra case, and passes an identical render', async () => {
    const want = JSON.parse(readFileSync(GOLDEN, 'utf8')) as Record<string, string>
    const same = { ...want }
    assert.deepEqual(goldenDifferences(same, want), [])
    // placeholders and the scope hash are ignored, in both directions
    assert.deepEqual(goldenDifferences({ ...want, plain: (want['plain'] as string).replace('<div ', '<!----><div ').replace('class="form-field"', 'class="form-field" data-v-deadbeef') }, want), [])
    // one attribute changed
    assert.deepEqual(goldenDifferences({ ...want, 'with-error': (want['with-error'] as string).replace('role="alert"', 'role="status"') }, want), ['with-error'])
    // a case dropped, a case added
    const { disabled: _dropped, ...rest } = want
    void _dropped
    assert.deepEqual(goldenDifferences(rest, want), ['disabled'])
    assert.deepEqual(goldenDifferences({ ...want, extra: '<div></div>' }, want), ['extra'])
  })

  test('the hardening and the required attribute are exactly the named additions, and nowhere else', async () => {
    const got = await renderGoldenCases()
    for (const [name, html] of Object.entries(got)) {
      const inputs = tags(html).filter((t) => t.name === 'input' || t.name === 'textarea')
      const required = name === 'required-with-placeholder'
      const password = name.startsWith('password')
      for (const el of inputs) {
        assert.equal(has(el, 'aria-required'), required, `${name}: aria-required only on a required field`)
        for (const a of ['spellcheck', 'autocorrect', 'autocapitalize']) assert.equal(has(el, a), password, `${name}: ${a} only on a password field`)
      }
    }
  })
})

describe('FormField: a required field is announced as required, a password is never spell-checked', () => {
  test('required puts aria-required="true" on the input and on the textarea, and not otherwise', async () => {
    for (const type of ['text', 'email', 'password', 'textarea']) {
      const yes = tags((await render('FormField', { id: 'q', label: 'L', type, modelValue: '', required: true })).html).find((t) => t.name === (type === 'textarea' ? 'textarea' : 'input'))
      assert.equal(yes?.attrs['aria-required'], 'true', `${type} required`)
      const no = tags((await render('FormField', { id: 'q', label: 'L', type, modelValue: '' })).html).find((t) => t.name === (type === 'textarea' ? 'textarea' : 'input'))
      assert.ok(no && !has(no, 'aria-required'), `${type} not required`)
    }
  })

  test('required does NOT add the native `required` attribute (it would put the browser\'s own bubbles in front of the form\'s validation)', async () => {
    const input = tags((await render('FormField', { id: 'q', label: 'L', modelValue: '', required: true })).html).find((t) => t.name === 'input')
    assert.ok(input && !has(input, 'required'))
  })

  test('a password input is not spell-checked, auto-corrected or auto-capitalised (shown or hidden is the browser test)', async () => {
    const pw = tags((await render('FormField', { id: 'q', label: 'P', type: 'password', modelValue: 'x' })).html).find((t) => t.name === 'input')
    assert.equal(pw?.attrs['type'], 'password')
    assert.deepEqual([pw?.attrs['spellcheck'], pw?.attrs['autocorrect'], pw?.attrs['autocapitalize']], ['false', 'off', 'off'])
    for (const type of ['text', 'email']) {
      const el = tags((await render('FormField', { id: 'q', label: 'L', type, modelValue: 'x' })).html).find((t) => t.name === 'input')
      assert.ok(el && !has(el, 'spellcheck') && !has(el, 'autocorrect') && !has(el, 'autocapitalize'), `${type} keeps the browser's defaults`)
    }
  })
})

describe('FormField: the label-row slot keeps the DOM order, so the tab order is Email, Password, Forgot', () => {
  const forgot = (): unknown => h('a', { href: '/forgot-password', 'aria-label': 'Forgot your password?' }, 'Forgot?')

  test('the slot renders after the input in the DOM and the field carries a layout class', async () => {
    const { html } = await render('FormField', { id: 'p1', label: 'Password', type: 'password', modelValue: '' }, { 'label-action': forgot })
    const all = tags(html)
    const label = all.find((t) => t.name === 'label')
    const input = all.find((t) => t.name === 'input')
    const link = all.find((t) => t.name === 'a')
    assert.ok(label && input && link)
    assert.ok(label.at < input.at && input.at < link.at, 'the link must come AFTER the input in the DOM; CSS moves it to the label row')
    assert.equal(link.attrs['aria-label'], 'Forgot your password?')
    assert.equal(withClass(html, 'has-label-action').length, 1)
    assert.equal(withClass(html, 'label-action').length, 1)
  })

  test('without the slot there is no wrapper and no class: nothing for the default look to inherit', async () => {
    const { html } = await render('FormField', { id: 'p2', label: 'Password', type: 'password', modelValue: '' })
    assert.equal(withClass(html, 'has-label-action').length, 0)
    assert.equal(withClass(html, 'label-action').length, 0)
  })
})

describe('FormField: the text reveal option', () => {
  const base = { id: 'r1', label: 'New password', type: 'password', modelValue: 'abc' }

  test('revealStyle="text" draws the word Show, keeps the accessible name and pressed state, and has no icon', async () => {
    const { html } = await render('FormField', { ...base, revealStyle: 'text' })
    const toggle = withClass(html, 'password-toggle')[0]
    assert.ok(toggle)
    assert.equal(toggle.attrs['aria-label'], 'Show password')
    assert.equal(toggle.attrs['aria-pressed'], 'false')
    assert.equal(toggle.attrs['type'], 'button')
    const inside = html.slice(toggle.at, html.indexOf('</button>', toggle.at))
    assert.equal(textOf(inside), 'Show')
    assert.ok(!inside.includes('<svg'))
  })

  test('the default is still the icon with no visible word', async () => {
    const { html } = await render('FormField', base)
    const toggle = withClass(html, 'password-toggle')[0]
    assert.ok(toggle)
    const inside = html.slice(toggle.at, html.indexOf('</button>', toggle.at))
    assert.ok(inside.includes('<svg'))
    assert.equal(textOf(inside), '')
  })

  test('an unknown value falls back to the icon rather than inventing a third look', async () => {
    const { html } = await render('FormField', { ...base, revealStyle: 'banana' })
    const toggle = withClass(html, 'password-toggle')[0] as Tag
    assert.ok(html.slice(toggle.at, html.indexOf('</button>', toggle.at)).includes('<svg'))
  })
})

describe('FormField: the visible cross in the error', () => {
  const base = { id: 'e1', label: 'Password', type: 'password', modelValue: 'a', error: 'Password must be at least 10 characters.' }

  test('errorStyle="glyph" begins the message with a visible cross, hidden from screen readers, and keeps role=alert', async () => {
    const { html } = await render('FormField', { ...base, errorStyle: 'glyph' })
    const error = withClass(html, 'field-error')[0]
    assert.ok(error)
    assert.equal(error.attrs['role'], 'alert')
    assert.equal(error.attrs['id'], 'e1-error')
    const inside = html.slice(error.at, html.indexOf('</p>', error.at))
    assert.ok(!inside.includes('<svg'))
    const glyph = withClass(inside, 'error-glyph')[0]
    assert.ok(glyph, 'no glyph element')
    assert.equal(glyph.attrs['aria-hidden'], 'true')
    assert.equal(textOf(inside), '✕ Password must be at least 10 characters.')
  })

  test('the default is still the icon and the plain message', async () => {
    const { html } = await render('FormField', base)
    const error = withClass(html, 'field-error')[0] as Tag
    const inside = html.slice(error.at, html.indexOf('</p>', error.at))
    assert.ok(inside.includes('<svg'))
    assert.ok(!inside.includes('✕'))
  })
})

// ---------------------------------------------------------------------------------- ConfirmDialog

describe('ConfirmDialog: names itself and its description for assistive technology', () => {
  const props = { show: true, title: 'Deactivate Youth Hall PC?', description: 'This frees one of your 5 device slots.', confirmLabel: 'Deactivate', cancelLabel: 'Keep active', variant: 'warning' }

  test('role, modal, aria-labelledby the title and aria-describedby the description; no bare aria-label', async () => {
    const { teleported } = await render('ConfirmDialog', props)
    const dialog = withClass(teleported, 'dialog-card')[0]
    assert.ok(dialog, teleported)
    assert.equal(dialog.attrs['role'], 'alertdialog')
    assert.equal(dialog.attrs['aria-modal'], 'true')
    assert.ok(!has(dialog, 'aria-label'), 'aria-labelledby replaces the duplicated aria-label')
    const title = tags(teleported).find((t) => t.attrs['id'] === dialog.attrs['aria-labelledby'])
    const desc = tags(teleported).find((t) => t.attrs['id'] === dialog.attrs['aria-describedby'])
    assert.ok(title && title.name === 'h3', 'aria-labelledby does not point at the title')
    assert.ok(desc && desc.name === 'p', 'aria-describedby does not point at the description')
    assert.ok(textOf(teleported.slice(title.at)).startsWith('Deactivate Youth Hall PC?'))
  })

  test('the cancel action is the first action in the DOM and is marked as the initial focus', async () => {
    const { teleported } = await render('ConfirmDialog', props)
    const buttons = tags(teleported).filter((t) => t.name === 'button')
    assert.equal(buttons.length, 2)
    assert.ok((buttons[0]?.attrs['class'] ?? '').split(/\s+/).includes('dialog-cancel'))
    assert.match(textOf(teleported.slice(buttons[0]?.at)), /^Keep active/)
  })

  test('the default layout has no banner, no hint and no left layout class: it looks as it did', async () => {
    const { teleported } = await render('ConfirmDialog', props)
    assert.equal(withClass(teleported, 'dialog-banner').length, 0)
    assert.equal(withClass(teleported, 'dialog-hint').length, 0)
    assert.equal(withClass(teleported, 'layout-left').length, 0)
    assert.equal(withClass(teleported, 'dialog-icon-wrapper').length, 1, 'the disc icon of the existing dialogs is kept')
  })

  test('layout="left" renders the glyph without a disc, the banner slot and the hint after the actions', async () => {
    const { teleported } = await render(
      'ConfirmDialog',
      { ...props, layout: 'left', hint: 'Esc keeps the device active.' },
      { banner: () => h('div', { class: 'probe-banner' }, 'Nothing goes dark') },
    )
    assert.equal(withClass(teleported, 'layout-left').length, 1)
    assert.equal(withClass(teleported, 'dialog-icon-wrapper').length, 0, 'no disc in the left layout')
    assert.equal(withClass(teleported, 'dialog-glyph').length, 1)
    assert.equal(withClass(teleported, 'dialog-banner').length, 1)
    const banner = teleported.indexOf('Nothing goes dark')
    const actions = withClass(teleported, 'dialog-actions')[0] as Tag
    const hint = teleported.indexOf('Esc keeps the device active.')
    assert.ok(banner > -1 && hint > -1)
    assert.ok(banner < actions.at && actions.at < hint, 'order must be description, banner, actions, hint')
    const dialog = withClass(teleported, 'dialog-card')[0] as Tag
    assert.ok(tags(teleported).some((t) => t.attrs['id'] === dialog.attrs['aria-describedby']))
  })

  test('hidden when `show` is false: nothing is teleported', async () => {
    const { teleported } = await render('ConfirmDialog', { ...props, show: false })
    assert.equal(withClass(teleported, 'dialog-card').length, 0)
  })

  test('an unknown layout falls back to the existing centred dialog', async () => {
    const { teleported } = await render('ConfirmDialog', { ...props, layout: 'banana' })
    assert.equal(withClass(teleported, 'layout-left').length, 0)
    assert.equal(withClass(teleported, 'dialog-icon-wrapper').length, 1)
  })
})

describe('REAL TREE: every required field on the sign-up, forgot-password and contact pages is announced as required', () => {
  /** The props a view gives one FormField, where they are written as plain attributes. */
  function staticProps(el: ElementNode): Record<string, unknown> {
    const props: Record<string, unknown> = {}
    for (const p of el.props) if (p.type === 6) props[p.name === 'required' ? 'required' : p.name.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase())] = p.name === 'required' ? true : (p.value?.content ?? '')
    return props
  }

  test('the FormFields those views mark `required`, rendered with the props the views give them, carry aria-required and not the native attribute', async () => {
    let seen = 0
    for (const view of ['views/SignUpView.vue', 'views/ForgotPasswordView.vue', 'views/ContactView.vue']) {
      const fields = elementsOf(read(view), view).filter((e) => e.tag === 'FormField' && e.props.some((p) => p.type === 6 && p.name === 'required'))
      for (const el of fields) {
        seen++
        const props = { ...staticProps(el), id: `f${seen}`, modelValue: '' }
        const { html } = await render('FormField', props)
        const control = tags(html).find((t) => t.name === 'input' || t.name === 'textarea')
        assert.equal(control?.attrs['aria-required'], 'true', `${view}: <FormField label="${String(props['label'])}" required> is not announced as required`)
        assert.ok(control && !has(control, 'required'), `${view}: the native required attribute would put the browser's own bubble ahead of the form's validation`)
      }
    }
    assert.ok(seen >= 8, `only ${seen} required fields were found (sign-up 4, forgot-password 1, contact 3): the scan is looking in the wrong place`)
  })
})

describe('ConfirmDialog: the type-to-confirm field has a name, and the page lock is the shared one', () => {
  test('the "Type cancel to confirm" label is tied to the input, so the field has an accessible name beyond its placeholder', async () => {
    const { teleported } = await render('ConfirmDialog', { show: true, title: 'T', description: 'D', requireType: 'cancel', variant: 'danger' })
    const label = tags(teleported).find((t) => t.name === 'label' && (t.attrs['class'] ?? '').includes('type-label'))
    const input = tags(teleported).find((t) => t.name === 'input')
    assert.ok(label && input)
    assert.ok(input.attrs['id'], 'the input has an id for the label to point at')
    assert.equal(label.attrs['for'], input.attrs['id'])
  })

  test('TRIPWIRE: the dialog takes the repo\'s reference-counted page lock and writes no overflow of its own', () => {
    const sfc = parse(read('components/ConfirmDialog.vue'), { filename: 'ConfirmDialog.vue' }).descriptor
    const script = `${sfc.script?.content ?? ''}\n${sfc.scriptSetup?.content ?? ''}`
    assert.match(script, /import \{ pageScrollLock \} from '@\/lib\/ui\/scrollLock\.ts'/)
    assert.match(script, /pageScrollLock\.acquire\(\)/)
    assert.ok(!/\.style\.overflow\s*=/.test(script), 'a dialog that sets `style.overflow` itself leaks the lock when two are open (Vera 1)')
  })

  test('a banner slot or a label-row slot that appears after the first render is read from $slots in the template, not cached', () => {
    // The behaviour is proved in a browser (`shared_components_headless.py`, "a slot added after
    // the first render"); this is the cheap tripwire for the cause: `useSlots()` is not reactive.
    for (const file of ['components/FormField.vue', 'components/ConfirmDialog.vue']) {
      const sfc = parse(read(file), { filename: file }).descriptor
      assert.ok(!/useSlots/.test(sfc.scriptSetup?.content ?? ''), `${file} caches its slots with useSlots()`)
    }
  })
})

// ------------------------------------------------------------------------ the gallery's output folder

describe('the gallery build refuses to empty a folder that is not a gallery build', () => {
  const made: string[] = []
  const tmp = (): string => {
    const d = mkdtempSync(path.join(tmpdir(), 'gallery-out-'))
    made.push(d)
    return d
  }
  after(() => {
    for (const d of made) rmSync(d, { recursive: true, force: true })
  })

  test('a missing folder, an empty folder and an earlier gallery build are fine; anything else is refused with the reason', () => {
    const base = tmp()
    assert.equal(unsafeOutDir(path.join(base, 'does-not-exist')), null)
    assert.equal(unsafeOutDir(base), null, 'empty')
    const earlier = path.join(base, 'earlier')
    mkdirSync(earlier)
    writeFileSync(path.join(earlier, 'index.html'), `<!doctype html><head>${GALLERY_TITLE}</head>`)
    assert.equal(unsafeOutDir(earlier), null, 'a previous gallery build')
    const other = path.join(base, 'other')
    mkdirSync(other)
    writeFileSync(path.join(other, 'precious.txt'), 'keep me')
    assert.match(unsafeOutDir(other) ?? '', /not empty and does not hold a gallery build/)
    const lookalike = path.join(base, 'lookalike')
    mkdirSync(lookalike)
    writeFileSync(path.join(lookalike, 'index.html'), '<title>My site</title>')
    assert.match(unsafeOutDir(lookalike) ?? '', /not empty/, 'an index.html that is not this gallery\'s')
    const file = path.join(base, 'afile')
    writeFileSync(file, 'x')
    assert.match(unsafeOutDir(file) ?? '', /not a directory/)
  })

  const build = (out: string): { status: number | null; output: string } => {
    const run = spawnSync(process.execPath, [path.join(ROOT, 'node_modules/vite/bin/vite.js'), 'build', '--config', path.join(ROOT, 'tests/gallery/vite.config.ts')], {
      cwd: ROOT,
      env: { ...process.env, GALLERY_OUT: out },
      encoding: 'utf8',
    })
    return { status: run.status, output: `${run.stdout}${run.stderr}` }
  }

  test('REAL BUILD: `vite build` with GALLERY_OUT on a folder holding a file exits non-zero and the file survives', () => {
    const victim = tmp()
    writeFileSync(path.join(victim, 'precious.txt'), 'keep me')
    const run = build(victim)
    assert.notEqual(run.status, 0, run.output)
    assert.match(run.output, /GALLERY_OUT refused/)
    assert.equal(readFileSync(path.join(victim, 'precious.txt'), 'utf8'), 'keep me')
  })

  test('CONTROL: the same build into an empty folder succeeds and writes the gallery (so the refusal above is the guard, not a broken build)', () => {
    const empty = tmp()
    const run = build(empty)
    assert.equal(run.status, 0, run.output)
    assert.ok(readFileSync(path.join(empty, 'index.html'), 'utf8').includes(GALLERY_TITLE))
  })
})
