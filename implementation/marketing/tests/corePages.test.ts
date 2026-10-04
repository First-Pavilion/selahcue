/**
 * The four core marketing pages (Pricing, Features, Download, About) against the Figma fidelity
 * audit (ClickUp 17tnw2b2cey; findings in `docs/design/visual-parity/marketing/findings/marketing-core.json`).
 *
 * Two kinds of check, both without a browser:
 *
 *   1. RENDER checks. Vite compiles the real views and Vue renders them to a string (the pattern
 *      `sharedComponents.test.ts` uses); `fixtures/htmlTree.ts` reads the result as a tree.
 *   2. SOURCE checks. Vue's own SFC compiler parses the views, so the AST that ships is what is read.
 *
 * What neither can see (computed colour, geometry, real focus movement) is covered by
 * `tests/core_pages_headless.py` and the visual-parity harness.
 *
 * EVERY PREDICATE HERE HAS ONE DEFINITION and its positive control consumes THAT definition, the rule
 * `authViews.test.ts` records after a ban and the control that vouched for it were two copies and the
 * ban went dead. A control that does not fail on a planted fault is a decoration.
 *
 * What these guard:
 *
 *   - the heading outline of every page never skips a level (audit pricing-bug-01: h1 then h3 on
 *     Pricing; download-bug-01: h2 then h4 on Download);
 *   - the unbacked claims the audit named stay out of the rendered text (honest content wins over
 *     Figma: owner decision). The one allow-listed region is the Pricing FAQ, whose answers belong to
 *     the claims ticket 17tnw2b0x3h and to a design decision (pricing-20, class D);
 *   - Pricing: three plan cards named by DEC-008, no price figure, plan buttons that are a link or a
 *     disabled control with a note, no `text="Save 20%"`, no `variant="gradient"`, the billing toggle
 *     is a named radio group;
 *   - the views use the shared container and carry no container rule of their own.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test, { after, before, describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import vue from '@vitejs/plugin-vue'
import ts from 'typescript'
import { createSSRApp, h, type Component } from 'vue'
import { parse } from 'vue/compiler-sfc'
import { renderToString } from 'vue/server-renderer'
import { createServer, type ViteDevServer } from 'vite'

import {
  all,
  byClass,
  byTag,
  hasClass,
  headingLevels,
  outlineProblems,
  parseHtml,
  textOf,
  type HtmlNode,
} from './fixtures/htmlTree.ts'

const ROOT = fileURLToPath(new URL('../', import.meta.url))
const SRC = path.join(ROOT, 'src')

const VIEWS = {
  pricing: 'views/PricingView.vue',
  features: 'views/FeaturesView.vue',
  download: 'views/DownloadView.vue',
  about: 'views/AboutView.vue',
} as const
type Page = keyof typeof VIEWS

const pages = {} as Record<Page, HtmlNode>

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
  for (const page of Object.keys(VIEWS) as Page[]) pages[page] = await render(VIEWS[page])
})

after(async () => {
  await server?.close()
})

async function load(file: string): Promise<Component> {
  const cached = loaded.get(file)
  if (cached) return cached
  const mod = (await server.ssrLoadModule(`/src/${file}`)) as { default: Component }
  loaded.set(file, mod.default)
  return mod.default
}

/** Render a component or a whole view the way the server renderer does, with RouterLink as an anchor. */
async function render(file: string, props: Record<string, unknown> = {}, slots: Record<string, () => unknown> = {}): Promise<HtmlNode> {
  const Comp = await load(file)
  const app = createSSRApp({ render: () => h(Comp, props, slots as never) })
  app.component('RouterLink', {
    props: { to: { type: [String, Object], required: true } },
    setup(p: { to: unknown }, { slots: s }: { slots: Record<string, () => unknown> }) {
      return () => h('a', { href: String(p.to) }, s.default?.() as never)
    },
  })
  return parseHtml(await renderToString(app))
}



const read = (rel: string): string => readFileSync(path.join(SRC, rel), 'utf8')

// ------------------------------------------------------------------------------- heading outline

describe('the heading outline never skips a level', () => {
  for (const page of Object.keys(VIEWS) as Page[]) {
    test(`${page}: one h1, and no heading more than one level below the one before it`, () => {
      assert.deepEqual(outlineProblems(headingLevels(pages[page])), [])
    })
  }

  test('pricing-bug-01: the plan names (h3) sit under an h2, not straight under the h1', () => {
    const levels = headingLevels(pages.pricing)
    const firstPlan = levels.indexOf(3)
    assert.ok(firstPlan > 0, 'the plan names are not h3 headings any more: this test no longer describes the page')
    assert.equal(levels[firstPlan - 1], 2, `the heading before the first plan name is an h${levels[firstPlan - 1]}`)
  })

  test('download-bug-01: the three install-step titles are h3 headings under the "three steps" h2', () => {
    const headings = byTag(pages.download, 'h1', 'h2', 'h3', 'h4')
    const at = headings.findIndex((n) => textOf(n) === 'Up and running in three steps')
    assert.ok(at >= 0, 'the install heading is missing')
    assert.equal((headings[at] as HtmlNode).tag, 'h2')
    const steps = headings.slice(at + 1)
    assert.equal(steps.length, 3, `expected three step titles after the heading, found ${steps.length}`)
    for (const s of steps) assert.equal(s.tag, 'h3', `step "${textOf(s)}" is an ${s.tag}`)
  })

  test('CONTROL: the same predicate flags an h1 straight to an h3, no h1, two h1s and a page that starts below the h1', () => {
    assert.equal(outlineProblems([1, 3, 3]).length, 1)
    assert.equal(outlineProblems([2, 3]).length > 0, true)
    assert.equal(outlineProblems([1, 2, 1]).length, 1)
    assert.equal(outlineProblems([1, 2, 4, 3]).length, 1)
    assert.deepEqual(outlineProblems([1, 2, 3, 3, 2, 3, 2]), [])
  })
})

// ------------------------------------------------------------------------------- unbacked claims

interface Banned {
  id: string
  pattern: RegExp
  /** Which pages it is checked on; every page when omitted. */
  pages?: readonly Page[]
  /** The audit finding or owner decision that bans it. */
  because: string
}

/**
 * Strings the audit and the owner decisions keep off these pages. Each is a claim the repo does not
 * back (or a Figma number the audit marked unbacked). A row is a regular expression over the text a
 * visitor reads, case-insensitive.
 */
const BANNED: readonly Banned[] = [
  // Currency-agnostic (review round 1, Cody N8): a dollar sign alone let "£19 per month" and a naira price through.
  { id: 'a price or currency amount', pattern: /[$€£¥₦₹]\s?\d|\b(usd|eur|gbp|ngn|naira|dollars?|pounds?|euros?)\b|\bper\s+(month|year|seat|user|device)\b|\/\s?(mo|yr|month|year)\b/, because: 'pricing-15, owner decision: no price until D1 closes' },
  { id: 'an annual discount', pattern: /save\s*\d+\s*%|\d+\s*%\s*yearly/, because: 'pricing-18: no annual plan exists' },
  { id: 'a trial', pattern: /\btrial\b/, because: 'pricing-17: no trial is decided' },
  { id: 'a Custom or Church tier', pattern: /\bcustom\b|\bchurch\s+(plan|tier)\b/, because: 'pricing-02, -15: no Church tier until D1 decides' },
  { id: 'an SLA', pattern: /\bsla\b|24\/7/, because: 'pricing-09: no SLA exists' },
  { id: 'priority support, onboarding or site licensing', pattern: /priority (support|response|queue|service|access)|response time|respond within|within 24 hours|dedicated (support|manager)|onboarding|site licensing|multi-campus|unlimited campuses|custom integrations|enterprise deployment/, because: 'pricing-09, -12, -16: no source' },
  { id: 'an enterprise, compliance or customer-proof claim', pattern: /\benterprise\b|\bsoc\s?2\b|\bgdpr\b|certified|compliant|trusted by|\baward/, because: 'no source in the repo' },
  { id: 'an uptime or percentage claim', pattern: /uptime|\d+(\.\d+)?\s?%/, because: 'no measurement backs a percentage, and no SLA is decided' },
  { id: 'a guarantee', pattern: /\bguarantee/, because: 'NFR-024 is failure isolation, not a guarantee (review round 1, Cody N19)' },
  { id: 'never blanks (stronger than NFR-024)', pattern: /never[- ]blank|never blanks/, because: 'say it is designed so a fault cannot black out live output (Cody N19)' },
  { id: 'forever or lifetime', pattern: /\bforever\b|lifetime/, because: 'pricing-15: "free forever" is not decided' },
  { id: 'fully offline', pattern: /fully offline|completely offline|100\s?% offline/, because: 'NFR-015 backs core live functions only; sign-in, activation, hosted speech-to-text and the model download need the network (Shadow F1)' },
  { id: 'cloud transcription', pattern: /\bcloud\b/, because: 'cloud-stt is RELEASE: UNSAFE and stripped from release builds (Cody N4)' },
  { id: 'jargon the owner did not choose', pattern: /compositor|desktop-authoritative/, because: 'plain English (Cody N19)' },
  { id: 'unlimited outputs', pattern: /unlimited/, because: 'features-10, pricing-16: DEC-008 caps outputs at 2, 5 and 10' },
  { id: 'always on the latest version', pattern: /latest version/, because: 'pricing-09: no source' },
  { id: 'cancel anytime or a refund', pattern: /\bcancel|refund|money.back/, because: 'no billing exists to cancel or refund (pricing-18)' },
  { id: 'a community or customer count', pattern: /thousands of|join thousands|\d[\d,]*\+? (churches|members|users)/, because: 'about-04: no evidence of any customer count' },
  { id: 'NDI 5', pattern: /ndi 5\b/, pages: ['features'], because: 'features-07: the PRD cites NDI 6.x' },
  { id: 'a resolution or frame rate', pattern: /\b4k\b|1080p|720p|60\s?fps/, pages: ['features'], because: 'features-07: no figure exists' },
  { id: 'alpha channel or zero latency', pattern: /alpha channel|zero capture-card latency|zero latency|gigabit/, pages: ['features'], because: 'features-07' },
  { id: 'a vendor the repo does not name', pattern: /wirecast|whisper|pastor john/, pages: ['features'], because: 'features-07: invented person and product names' },
  { id: 'an internal requirement id', pattern: /\bnfr-\d+|\bfr-\d+/, pages: ['features', 'about'], because: 'features-12: an internal PRD identifier in customer copy' },
  { id: 'per-output theme and framing', pattern: /per-output|own theme and framing/, pages: ['features'], because: 'features-10: not shipped (FR-038 is R2)' },
  // Every page (review round 1, Cody N12): the Copy rule names it for all four, not only Features.
  { id: 'nothing leaves the machine', pattern: /nothing leaves|never leaves|entirely on the machine|zero cloud|stays on your (machine|computer|device)/, because: 'features-11: stated as absolute, and not backed' },
  { id: 'an installer version, format or size', pattern: /\bv\d+\.\d|\.msi\b|\.dmg\b|\bnsis\b|~\s?\d+\s?mb|universal/, pages: ['download'], because: 'download-04: no release exists' },
  { id: 'an OS floor', pattern: /windows 1[01]|macos\s+1\d|monterey|or later/, pages: ['download'], because: 'download-04: no documented minimum' },
  { id: 'a hardware requirement', pattern: /\d+\s?(gb|mb|ghz)\b|dual-core|quad-core|intel|apple silicon|directx|integrated gpu|discrete gpu|\bssd\b/, pages: ['download'], because: 'download-05: no single backed figure' },
  { id: 'no account required', pattern: /no account|no internet or account|without an account/, pages: ['download', 'about'], because: 'download-01, about-08: not evidenced' },
  { id: 'store availability', pattern: /available for ios|download on\b|app store badge/, pages: ['download'], because: 'download-09: the apps are not in the stores' },
  { id: 'a placeholder phone', pattern: /mobile app mockup/, pages: ['download'], because: 'download-07: a visible placeholder' },
  { id: 'a pairing speed', pattern: /in seconds/, pages: ['download'], because: 'no evidence of a pairing time' },
  { id: 'a setup time', pattern: /within 5 minutes|5 minutes/, pages: ['about'], because: 'about-03: METRIC-006 is 10 minutes, and a target is not a claim' },
  { id: 'cold start or tracking claims', pattern: /cold start|tracking/, pages: ['about'], because: 'about-08: not evidenced' },
  { id: 'rights and entitlement claims', pattern: /entitled|encrypted/, pages: ['about'], because: 'about-03: copyrighted translations are R4 / API only' },
]

function bannedHits(text: string, page: Page): string[] {
  const lower = text.toLowerCase()
  return BANNED.filter((b) => (b.pages ? b.pages.includes(page) : true) && b.pattern.test(lower)).map((b) => `${b.id} (${b.because})`)
}

/** The text of a page with the one allow-listed region removed. */
function claimText(page: Page): string {
  const root = pages[page]
  const exempt = all(root, (n) => n.attrs['data-region'] === 'pricing-faq')
  if (page !== 'pricing') assert.equal(exempt.length, 0, 'only the Pricing page may carry the allow-listed FAQ region')
  const skip = new Set(exempt)
  const parts: string[] = []
  const visit = (n: HtmlNode): void => {
    if (skip.has(n)) return
    if (n.tag === '#text') parts.push(n.text ?? '')
    for (const c of n.children) visit(c)
  }
  visit(root)
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}

describe('no claim the repo does not back is on the page', () => {
  for (const page of Object.keys(VIEWS) as Page[]) {
    test(`${page}: none of the banned strings is rendered`, () => {
      assert.deepEqual(bannedHits(claimText(page), page), [])
    })
  }

  test('the Pricing FAQ is the one allow-listed region, so the exception cannot outlive the section', () => {
    const faq = all(pages.pricing, (n) => n.attrs['data-region'] === 'pricing-faq')
    assert.equal(
      faq.length,
      1,
      'the Pricing FAQ region is gone or renamed: delete this exception (and `data-region`) if the FAQ was removed on purpose',
    )
  })

  test('CONTROL: every banned pattern fires on a string that contains it, and a clean string passes', () => {
    const planted: Record<string, { text: string; page: Page }> = {
      'a price or currency amount': { text: 'Pro $19 / month', page: 'pricing' },
      'an annual discount': { text: 'Annual · save 20%', page: 'pricing' },
      'a trial': { text: 'Start free trial', page: 'pricing' },
      'a Custom or Church tier': { text: 'Church Custom', page: 'pricing' },
      'an SLA': { text: 'Custom SLA and 24/7 support', page: 'pricing' },
      'priority support, onboarding or site licensing': { text: 'Priority support', page: 'pricing' },
      'unlimited outputs': { text: 'Unlimited virtual outputs', page: 'features' },
      'always on the latest version': { text: 'Always on the latest version', page: 'pricing' },
      'cancel anytime or a refund': { text: 'Cancel anytime', page: 'about' },
      'a community or customer count': { text: 'Join thousands of churches', page: 'about' },
      'NDI 5': { text: 'NDI 5 & Multi-Output', page: 'features' },
      'a resolution or frame rate': { text: 'Audience Output · 4K 60fps', page: 'features' },
      'alpha channel or zero latency': { text: 'Alpha channel transparency', page: 'features' },
      'a vendor the repo does not name': { text: 'Pastor John Davies', page: 'features' },
      'an internal requirement id': { text: 'Never-blank guarantee (NFR-024)', page: 'features' },
      'per-output theme and framing': { text: 'Per-output theme & framing', page: 'features' },
      'nothing leaves the machine': { text: 'Nothing leaves your machine', page: 'download' },
      'an enterprise, compliance or customer-proof claim': { text: 'Trusted by enterprise teams', page: 'pricing' },
      'an uptime or percentage claim': { text: '99.9% uptime', page: 'pricing' },
      'a guarantee': { text: 'Never-blank guarantee', page: 'features' },
      'never blanks (stronger than NFR-024)': { text: 'The screen never blanks.', page: 'about' },
      'forever or lifetime': { text: 'Start free forever', page: 'pricing' },
      'fully offline': { text: 'SelahCue runs fully offline', page: 'download' },
      'cloud transcription': { text: 'Cloud transcription only if you turn it on', page: 'features' },
      'jargon the owner did not choose': { text: 'where the compositor never blanks', page: 'about' },
      'an installer version, format or size': { text: 'v1.0 · .msi installer · ~84 MB', page: 'download' },
      'an OS floor': { text: 'macOS 12 Monterey+', page: 'download' },
      'a hardware requirement': { text: '4 GB RAM', page: 'download' },
      'no account required': { text: 'No account required', page: 'download' },
      'store availability': { text: 'Available for iOS and Android', page: 'download' },
      'a placeholder phone': { text: 'Mobile App Mockup', page: 'download' },
      'a pairing speed': { text: 'pairs over your local network in seconds', page: 'download' },
      'a setup time': { text: 'run a service within 5 minutes', page: 'about' },
      'cold start or tracking claims': { text: 'fast cold start', page: 'about' },
      'rights and entitlement claims': { text: 'safely entitled and encrypted', page: 'about' },
    }
    assert.deepEqual(
      BANNED.map((b) => b.id).filter((id) => !(id in planted)),
      [],
      'a banned pattern has no planted control',
    )
    for (const [id, { text, page }] of Object.entries(planted)) {
      assert.ok(
        bannedHits(text, page).some((hit) => hit.startsWith(id)),
        `"${text}" should be flagged as ${id}`,
      )
    }
    assert.deepEqual(bannedHits('Pricing that grows with your church. Up to 2 outputs. To be confirmed.', 'pricing'), [])
  })

  test('CONTROL (review round 1, Cody N8 and N12): the price ban is currency-agnostic and the deny-list reaches the phrases that slipped through', () => {
    const must: Array<[string, Page]> = [
      ['£19 per month', 'pricing'],
      ['USD 19', 'pricing'],
      ['₦15,000 a month', 'pricing'],
      ['19 naira', 'pricing'],
      ['€19', 'pricing'],
      ['billed per year', 'pricing'],
      ['$19/mo', 'pricing'],
      ['30 day trial', 'pricing'],
      ['Priority response', 'pricing'],
      ['99.9% uptime guarantee', 'pricing'],
      ['Nothing leaves your machine', 'download'],
      ['Nothing leaves the machine', 'about'],
      ['Nothing leaves the machine', 'pricing'],
      ['Works fully offline', 'download'],
      ['Works fully offline', 'about'],
      ['Works fully offline', 'features'],
    ]
    for (const [text, page] of must) assert.ok(bannedHits(text, page).length > 0, `"${text}" on ${page} should be flagged`)
    // ...and ordinary copy that happens to contain a word nearby is not.
    for (const ok of ['Monthly', 'Up to 5 outputs', 'Annual billing is not available yet.', 'monthly allowance', 'OBS / vMix', 'current / next / timer']) {
      assert.deepEqual(bannedHits(ok, 'pricing'), [], `"${ok}" is ordinary copy`)
    }
  })

  test('CONTROL: a banned string is only banned on the pages it names', () => {
    assert.deepEqual(bannedHits('4K 60fps', 'pricing'), [])
    assert.equal(bannedHits('4K 60fps', 'features').length, 1)
  })
})

// ------------------------------------------------------------------------------------ Pricing

describe('Pricing', () => {
  const cards = (): HtmlNode[] => byClass(pages.pricing, 'pricing-card')
  const plan = (card: HtmlNode): string => textOf(byClass(card, 'plan-name')[0] as HtmlNode)

  test('hero: the PRICING eyebrow, the Figma headline and a subline', () => {
    const h1 = byTag(pages.pricing, 'h1')[0] as HtmlNode
    assert.equal(textOf(h1), 'Pricing that grows with your church')
    assert.ok(textOf(pages.pricing).includes('PRICING'), 'no PRICING eyebrow')
    const lead = byClass(pages.pricing, 'hero-lead')[0]
    assert.ok(lead && textOf(lead).length > 40, 'no subline under the headline')
  })

  test('the plans are Free, Pro and Platinum (DEC-008), never Church, and none prints a price figure', () => {
    assert.deepEqual(cards().map(plan), ['Free', 'Pro', 'Platinum'])
    for (const c of cards()) assert.ok(!/\$/.test(textOf(c)), `a price figure in the ${plan(c)} card: ${textOf(c)}`)
  })

  test('pricing-02: no card reads "$0 / month" or a per-month price of any kind', () => {
    for (const c of cards()) assert.ok(!/\/\s*month|\/\s*forever/.test(textOf(c)), `${plan(c)}: ${textOf(c)}`)
  })

  test('every plan button is a link to a real destination or a disabled control with a visible note', () => {
    const buttons = cards().map((c) => ({ c, btn: byClass(c, 'ui-button')[0] as HtmlNode }))
    for (const { c, btn } of buttons) {
      assert.ok(btn, `${plan(c)} has no call to action`)
      if (btn.tag === 'a') {
        assert.match(btn.attrs['href'] ?? '', /^\//, `${plan(c)}: the link has no internal destination`)
      } else {
        assert.equal(btn.tag, 'button')
        assert.ok('disabled' in btn.attrs, `${plan(c)}: an enabled button that goes nowhere`)
        const note = btn.attrs['aria-describedby']
        assert.ok(note && all(c, (n) => n.attrs['id'] === note && textOf(n).length > 0).length === 1, `${plan(c)}: the disabled button has no visible reason`)
      }
    }
  })

  test('Free goes to /download; Pro (no billing) and Platinum (the contact form sends nothing) are disabled and say "Not available yet"', () => {
    const [free, pro, third] = cards().map((c) => byClass(c, 'ui-button')[0] as HtmlNode) as [HtmlNode, HtmlNode, HtmlNode]
    assert.equal(free.attrs['href'], '/download')
    for (const [name, btn, card] of [['Pro', pro, cards()[1]], ['Platinum', third, cards()[2]]] as const) {
      assert.equal(btn.tag, 'button', `${name} has a destination`)
      assert.ok('disabled' in btn.attrs, `${name}'s button is not disabled`)
      assert.ok(textOf(card as HtmlNode).includes('Not available yet'), `${name} does not say why`)
    }
  })

  test('review round 1, Cody B1: no plan button leads to /contact, which shows "Message Received" and sends nothing', () => {
    const hrefs = cards().flatMap((c) => byClass(c, 'ui-button').map((b) => b.attrs['href']))
    assert.ok(!hrefs.includes('/contact'), `a plan button links to /contact: ${hrefs.join(', ')}`)
    const { descriptor } = parse(readFileSync(path.join(SRC, 'views/PricingView.vue'), 'utf8'), { filename: 'PricingView.vue' })
    const code = (descriptor.scriptSetup?.content ?? '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
    assert.ok(!/to:\s*['"]\/contact['"]/.test(code), 'PricingView passes to: /contact again')
  })

  // The expected text is typed here independently of PricingView's `LIMITS`, so the cards and the table cannot
  // drift together without this file noticing (review round 1, Cody N7: four changed limits stayed green).
  const DEC008_CARDS: Record<string, string[]> = {
    Free: ['1 device', 'Up to 2 outputs', 'Hosted speech-to-text, monthly allowance'],
    Pro: [
      'Everything in Free, without the watermark',
      '3 devices',
      'Up to 5 outputs',
      'Up to 5 NDI outputs',
      'A larger monthly allowance of hosted speech-to-text',
    ],
    Platinum: [
      'Everything in Pro',
      '7 devices',
      'Up to 10 outputs',
      'Up to 10 NDI outputs',
      'The largest monthly allowance of hosted speech-to-text',
    ],
  }

  test('the card bullets are exactly DEC-008\'s limits (devices 1/3/7, outputs 2/5/10, NDI 5/10), nothing else', () => {
    const got = Object.fromEntries(cards().map((c) => [plan(c), byTag(c, 'li').map((li) => textOf(li))]))
    assert.deepEqual(got, DEC008_CARDS)
  })

  test('review round 1, Shadow F2: the allowance is named as the HOSTED path, and a note says on-device transcription is not metered', () => {
    for (const [name, bullets] of Object.entries(DEC008_CARDS)) {
      assert.ok(bullets.some((b) => /hosted speech-to-text/i.test(b)), `${name}: no bullet names hosted speech-to-text`)
    }
    const row = byTag(byTag(byTag(pages.pricing, 'table')[0] as HtmlNode, 'tbody')[0] as HtmlNode, 'tr').find((r) => /speech-to-text/i.test(textOf(byTag(r, 'th')[0] as HtmlNode)))
    assert.ok(row, 'no speech-to-text row')
    assert.match(textOf(byTag(row as HtmlNode, 'th')[0] as HtmlNode), /^Hosted speech-to-text/)
    const note = byClass(pages.pricing, 'table-note')[0]
    assert.ok(note, 'no note under the table')
    assert.match(textOf(note as HtmlNode), /on-device transcription is not metered/i)
  })

  test('the Free plan says its output carries a watermark (DEC-008), and Pro says it does not', () => {
    const [free, pro] = cards()
    assert.match(textOf(free as HtmlNode).toLowerCase(), /watermark/)
    assert.match(textOf(pro as HtmlNode).toLowerCase(), /without the watermark|no watermark/)
  })

  test('the cards are three across in a grid the responsive sweep reads, with Pro marked popular', () => {
    const grid = byClass(pages.pricing, 'pricing-grid')[0] as HtmlNode
    assert.equal(grid.children.filter((c) => c.tag !== '#text').length, 3)
    assert.deepEqual(cards().map((c) => hasClass(c, 'popular')), [false, true, false])
  })

  describe('the billing toggle', () => {
    const group = (): HtmlNode => all(pages.pricing, (n) => n.attrs['role'] === 'radiogroup')[0] as HtmlNode

    test('pricing-06: a radio group with a name, two radios, exactly one checked', () => {
      assert.ok(group(), 'no radio group')
      assert.ok((group().attrs['aria-label'] ?? '').length > 0, 'the group has no name')
      const radios = all(group(), (n) => n.attrs['role'] === 'radio')
      assert.deepEqual(radios.map((r) => textOf(r)), ['Monthly', 'Annual'])
      assert.equal(radios.filter((r) => r.attrs['aria-checked'] === 'true').length, 1)
      assert.equal(radios[0]?.attrs['aria-checked'], 'true', 'Monthly is the drawn state')
    })

    test('roving tabindex: only the checked radio is in the tab order', () => {
      const radios = all(group(), (n) => n.attrs['role'] === 'radio')
      assert.deepEqual(radios.map((r) => r.attrs['tabindex']), ['0', '-1'])
    })

    test('pricing-05, pricing-18: the labels are plain Monthly and Annual, with no discount and no badge', () => {
      assert.ok(!/save|%|off/i.test(textOf(group())), textOf(group()))
      assert.equal(all(group(), (n) => hasClass(n, 'ui-badge')).length, 0)
    })

    test('a live region is there from the first render, so a later message is announced', () => {
      const live = all(pages.pricing, (n) => n.attrs['aria-live'] === 'polite' && hasClass(n, 'billing-note'))
      assert.equal(live.length, 1)
    })
  })

  describe('the comparison table', () => {
    const table = (): HtmlNode => byTag(pages.pricing, 'table')[0] as HtmlNode

    test('pricing-10: the heading is "Compare every plan", and the table sits in a card, not a full-bleed band', () => {
      assert.ok(byTag(pages.pricing, 'h2').some((n) => textOf(n) === 'Compare every plan'))
      assert.ok(byClass(pages.pricing, 'comparison-card').length === 1, 'no .comparison-card')
    })

    test('the header names the three plans in order, over column headers', () => {
      const cols = byTag(byTag(table(), 'thead')[0] as HtmlNode, 'th')
      assert.deepEqual(cols.map((c) => textOf(c)), ['PLANS', 'Free', 'Pro', 'Platinum'])
      for (const c of cols) assert.equal(c.attrs['scope'], 'col')
    })

    test('pricing-12: every row has a row header and three value cells, and no row is one the repo cannot back', () => {
      const rows = byTag(byTag(table(), 'tbody')[0] as HtmlNode, 'tr')
      assert.ok(rows.length >= 6 && rows.length <= 10, `${rows.length} rows`)
      for (const r of rows) {
        assert.equal(byTag(r, 'th').length, 1, `row without one row header: ${textOf(r)}`)
        assert.equal((byTag(r, 'th')[0] as HtmlNode).attrs['scope'], 'row')
        assert.equal(byTag(r, 'td').length, 3, `row "${textOf(r)}" does not have three value cells`)
      }
    })

    test('pricing-11: a tick is an SVG with the words "Included", a dash says "Not included"; no bare glyph', () => {
      const cells = byTag(byTag(table(), 'tbody')[0] as HtmlNode, 'td')
      for (const c of cells) {
        const words = textOf(c)
        assert.ok(!/[✓—]/.test(words), `a bare glyph in a cell: ${words}`)
        if (/Included/.test(words) && !/Not included/.test(words)) assert.equal(byTag(c, 'svg').length, 1, `a tick with no icon: ${words}`)
        assert.ok(words.length > 0, 'an empty cell')
      }
      assert.ok(cells.some((c) => /Not included/.test(textOf(c))), 'no dash cell: the Free column has nothing it lacks, so the table is not telling the difference')
    })

    test('the plan limits agree with DEC-008: outputs 2, 5, 10; NDI none, 5, 10; devices 1, 3, 7', () => {
      const row = (label: RegExp): string[] => {
        const r = byTag(byTag(table(), 'tbody')[0] as HtmlNode, 'tr').find((x) => label.test(textOf(byTag(x, 'th')[0] as HtmlNode)))
        assert.ok(r, `no row matching ${label}`)
        return byTag(r as HtmlNode, 'td').map((c) => textOf(c))
      }
      assert.deepEqual(row(/outputs/i).map((t) => t.replace(/\D/g, '')), ['2', '5', '10'])
      assert.deepEqual(row(/ndi/i), ['Not included', '5', '10'])
      assert.deepEqual(row(/devices/i).map((t) => t.replace(/\D/g, '')), ['1', '3', '7'])
    })
  })
})

// ----------------------------------------------------------------------------- The billing keys

describe('the segmented toggle keyboard rules', () => {
  const keys = async (): Promise<typeof import('../src/components/core/segmentedKeys.ts')> => import('../src/components/core/segmentedKeys.ts')

  test('Right and Down move forward, Left and Up move back, and the ends wrap', async () => {
    const { nextIndex } = await keys()
    const on = [true, true, true]
    assert.equal(nextIndex('ArrowRight', 0, on), 1)
    assert.equal(nextIndex('ArrowDown', 1, on), 2)
    assert.equal(nextIndex('ArrowRight', 2, on), 0)
    assert.equal(nextIndex('ArrowLeft', 0, on), 2)
    assert.equal(nextIndex('ArrowUp', 2, on), 1)
  })

  test('Home and End jump to the first and last enabled option', async () => {
    const { nextIndex } = await keys()
    assert.equal(nextIndex('Home', 2, [true, true, true]), 0)
    assert.equal(nextIndex('End', 0, [true, true, true]), 2)
    assert.equal(nextIndex('Home', 2, [false, true, true]), 1)
    assert.equal(nextIndex('End', 0, [true, true, false]), 1)
  })

  test('a disabled option is skipped, and a lone enabled option stays put', async () => {
    const { nextIndex } = await keys()
    assert.equal(nextIndex('ArrowRight', 0, [true, false, true]), 2)
    assert.equal(nextIndex('ArrowLeft', 0, [true, false, true]), 2)
    assert.equal(nextIndex('ArrowRight', 0, [true, false, false]), 0)
  })

  test('any other key does nothing', async () => {
    const { nextIndex } = await keys()
    assert.equal(nextIndex('Enter', 0, [true, true]), null)
    assert.equal(nextIndex('a', 0, [true, true]), null)
    assert.equal(nextIndex('Tab', 0, [true, true]), null)
  })

  test('the toggle renders its options as radios with a roving tabindex, and honours a disabled option', async () => {
    const root = await render('components/core/SegmentedToggle.vue', {
      modelValue: 'b',
      label: 'Billing period',
      options: [
        { value: 'a', label: 'One' },
        { value: 'b', label: 'Two' },
        { value: 'c', label: 'Three', disabled: true },
      ],
    })
    const g = all(root, (n) => n.attrs['role'] === 'radiogroup')[0] as HtmlNode
    assert.equal(g.attrs['aria-label'], 'Billing period')
    const radios = all(g, (n) => n.attrs['role'] === 'radio')
    assert.deepEqual(radios.map((r) => r.attrs['aria-checked']), ['false', 'true', 'false'])
    assert.deepEqual(radios.map((r) => r.attrs['tabindex']), ['-1', '0', '-1'])
    assert.ok('disabled' in (radios[2] as HtmlNode).attrs)
  })
})

// ------------------------------------------------------------------------------------ Features

describe('Features', () => {
  const rows = (): HtmlNode[] => byClass(pages.features, 'feature-row')

  test('features-01: the FEATURES eyebrow, the Figma headline and subline', () => {
    assert.equal(textOf(byTag(pages.features, 'h1')[0] as HtmlNode), 'Everything you need to run a confident service')
    assert.ok(textOf(pages.features).includes('FEATURES'))
    assert.match(textOf(byClass(pages.features, 'hero-lead')[0] as HtmlNode), /^From the first slide to the final blessing/)
  })

  test('features-02: six rows with Figma headings, in Figma order', () => {
    assert.deepEqual(
      rows().map((r) => textOf(byTag(r, 'h2')[0] as HtmlNode)),
      [
        'Live presentation & outputs',
        'Scripture at your fingertips',
        'Service plans & timers',
        'Stage & confidence monitor',
        'NDI & multi-output',
        'On-device transcript & detection',
      ],
    )
  })

  test('features-02: every row has a paragraph and three bullets', () => {
    for (const r of rows()) {
      assert.equal(byTag(r, 'p').filter((p) => hasClass(p, 'row-text')).length, 1)
      assert.equal(byTag(r, 'li').length, 3, textOf(r))
    }
  })

  test('features-05: the row eyebrows are the six Figma labels', () => {
    assert.deepEqual(
      rows().map((r) => textOf(byClass(r, 'row-eyebrow')[0] as HtmlNode)),
      ['OUTPUTS', 'SCRIPTURE', 'PLANNING', 'STAGE', 'STREAMING', 'ASSIST'],
    )
  })

  test('features-03: the product panels are abstract skeletons, hidden from assistive technology, with no mock content', () => {
    const panels = byClass(pages.features, 'feature-panel')
    assert.equal(panels.length, 6)
    for (const p of panels) {
      assert.equal(p.attrs['aria-hidden'], 'true')
      assert.equal(byClass(p, 'skeleton-bar').length, 2)
    }
    assert.equal(byClass(pages.features, 'mock-card').length, 0)
  })

  test('features-04: the rows alternate, text first then panel on the odd rows, panel first on the even rows', () => {
    assert.deepEqual(rows().map((r) => hasClass(r, 'reverse')), [false, true, false, true, false, true])
  })

  test('features-06: the closing band has Figma wording and two links, Download free and See pricing', () => {
    const band = byClass(pages.features, 'cta-band')[0] as HtmlNode
    assert.equal(textOf(byTag(band, 'h2')[0] as HtmlNode), 'Ready to run your best service yet?')
    const links = byTag(band, 'a')
    assert.deepEqual(links.map((l) => [textOf(l), l.attrs['href']]), [
      ['Download free', '/download'],
      ['See pricing', '/pricing'],
    ])
  })

  test('features-11 and review round 1, Cody N4: the transcript row says the transcript runs on the machine and mentions no cloud path (cloud-stt is stripped from release builds)', () => {
    const last = textOf(rows()[5] as HtmlNode).toLowerCase()
    assert.match(last, /on-device|on your machine/)
    assert.match(last, /never gates/)
    assert.doesNotMatch(last, /cloud/)
  })
})

// ------------------------------------------------------------------------------------ Download

describe('Download', () => {
  test('download-01: the DOWNLOAD eyebrow, the Figma headline, a paragraph and a trust line', () => {
    assert.equal(textOf(byTag(pages.download, 'h1')[0] as HtmlNode), 'Get SelahCue for your platform')
    assert.ok(textOf(pages.download).includes('DOWNLOAD'))
    assert.ok(byClass(pages.download, 'hero-lead').length === 1)
    assert.ok(byClass(pages.download, 'trust-line').length === 1)
  })

  test('download-02: two platform cards, Windows and macOS, no Linux card is added', () => {
    const cards = byClass(pages.download, 'platform-card')
    assert.deepEqual(cards.map((c) => textOf(byTag(c, 'h2')[0] as HtmlNode)), ['Windows', 'macOS'])
    assert.ok(!/linux/i.test(textOf(pages.download)), 'Linux is not drawn in Figma and no page may claim a Linux installer')
  })

  test('PR 134 stays: both download buttons are disabled, say so, and name the status that explains them', () => {
    for (const c of byClass(pages.download, 'platform-card')) {
      const btn = byClass(c, 'ui-button')[0] as HtmlNode
      assert.equal(btn.tag, 'button')
      assert.ok('disabled' in btn.attrs)
      assert.equal(btn.attrs['aria-disabled'], 'true')
      const status = all(c, (n) => n.attrs['id'] === btn.attrs['aria-describedby'])[0] as HtmlNode
      assert.equal(textOf(status), 'Not available to download yet')
    }
  })

  test('download-06: two requirement cards, MINIMUM and RECOMMENDED, with five rows each and no invented figure', () => {
    const cards = byClass(pages.download, 'req-card')
    // The chip is the visible label; the heading reads "MINIMUM requirements" (review round 1, Cody N15).
    assert.deepEqual(cards.map((c) => textOf(byTag(c, 'h3')[0] as HtmlNode)), ['MINIMUM requirements', 'RECOMMENDED requirements'])
    for (const c of cards) {
      const rows = byTag(c, 'dt').map((t) => textOf(t))
      assert.deepEqual(rows, ['Processor', 'Memory', 'Graphics', 'Storage', 'Display'])
      assert.deepEqual(byTag(c, 'dd').map((d) => textOf(d)), Array(5).fill('To be confirmed'))
    }
  })

  test('download-07: the mobile section has the pill, the heading, three bullets and the controller mock, and no placeholder phone', () => {
    const section = byClass(pages.download, 'mobile-section')[0] as HtmlNode
    assert.ok(textOf(section).includes('MOBILE CONTROL'))
    assert.ok(byTag(section, 'h2').some((n) => textOf(n) === 'Control from your phone'))
    assert.equal(byTag(section, 'li').length, 3)
    assert.equal(byClass(section, 'controller-mock').length, 1)
    assert.equal(byClass(section, 'phone-mockup').length, 0)
  })

  test('download-08, download-09: the store badges are still disabled, with the note that explains them', () => {
    const badges = byClass(pages.download, 'store-badge')
    assert.equal(badges.length, 2)
    for (const b of badges) {
      assert.ok('disabled' in b.attrs)
      assert.equal(b.attrs['aria-describedby'], 'store-availability')
    }
    assert.match(textOf(all(pages.download, (n) => n.attrs['id'] === 'store-availability')[0] as HtmlNode), /not in the App Store or Google Play yet/)
  })

  test('download-10: three steps, with Figma titles, numbered 01 to 03', () => {
    const steps = byClass(pages.download, 'step-card')
    assert.deepEqual(steps.map((s) => textOf(byTag(s, 'h3')[0] as HtmlNode)), ['Download & install', 'Build your first plan', 'Go live & pair your phone'])
    assert.deepEqual(steps.map((s) => textOf(byClass(s, 'step-num')[0] as HtmlNode)), ['01', '02', '03'])
  })
})

// --------------------------------------------------------------------------------------- About

describe('About', () => {
  test('about-01: the ABOUT eyebrow, the Figma headline and subline', () => {
    assert.equal(textOf(byTag(pages.about, 'h1')[0] as HtmlNode), 'Built for the people running the service')
    assert.ok(textOf(pages.about).includes('ABOUT'))
    assert.match(textOf(byClass(pages.about, 'hero-lead')[0] as HtmlNode), /^SelahCue started with one conviction/)
  })

  test('about-02: the "Why we built SelahCue" story has a heading and three paragraphs', () => {
    const story = byClass(pages.about, 'story-section')[0] as HtmlNode
    assert.equal(textOf(byTag(story, 'h2')[0] as HtmlNode), 'Why we built SelahCue')
    assert.equal(byTag(story, 'p').length, 3)
  })

  test('about-03: "What we stand for" has Figma\'s four values in one row', () => {
    const band = byClass(pages.about, 'values-band')[0] as HtmlNode
    assert.equal(textOf(byTag(band, 'h2')[0] as HtmlNode), 'What we stand for')
    assert.deepEqual(byTag(band, 'h3').map((n) => textOf(n)), ['Reliability comes first', 'Offline by default', 'AI assists, never gates', 'Bounded & respectful'])
    for (const card of byClass(band, 'value-card')) assert.equal(byTag(card, 'p').length, 1)
  })

  test('about-08: the fourth value ships only the backed part (memory is capped)', () => {
    const card = byClass(pages.about, 'value-card')[3] as HtmlNode
    assert.match(textOf(card).toLowerCase(), /memory/)
  })

  test('about-04: the closing band has Figma wording and goes to /download and /pricing', () => {
    const band = byClass(pages.about, 'cta-band')[0] as HtmlNode
    assert.equal(textOf(byTag(band, 'h2')[0] as HtmlNode), 'Ready to run your best service yet?')
    assert.deepEqual(byTag(band, 'a').map((l) => [textOf(l), l.attrs['href']]), [
      ['Download free', '/download'],
      ['See pricing', '/pricing'],
    ])
  })
})

// ------------------------------------------------------------------------- source: shared layout

interface SfcSource {
  template: string
  css: string
}

function sfcSource(sfc: string, filename: string): SfcSource {
  const { descriptor, errors } = parse(sfc, { filename })
  assert.equal(errors.length, 0, `${filename} did not parse`)
  return {
    template: descriptor.template?.content ?? '',
    css: descriptor.styles.map((s) => s.content.replace(/\/\*[\s\S]*?\*\//g, '')).join('\n'),
  }
}

/** Every way a view brings its own layout instead of the shared one. */
function layoutProblems(sfc: string, where: string): string[] {
  const { template, css } = sfcSource(sfc, where)
  const out: string[] = []
  if (/(^|[\s,}])\.container\s*[{,]/.test(css)) out.push(`${where}: declares its own .container rule (the shared one is in main.css)`)
  if (/\.container[^{]*\{[^}]*max-width/.test(css)) out.push(`${where}: sets a max-width on .container`)
  if (/max-width:\s*(1140|1200)px/.test(css)) out.push(`${where}: a 1140 or 1200px column (the content width is 1248)`)
  if (/variant="gradient"/.test(template)) out.push(`${where}: passes variant="gradient" (a legacy alias of primary)`)
  if (/<UiBadge\b[^>]*\btext=/.test(template)) out.push(`${where}: passes a \`text\` attribute to UiBadge (it never rendered it)`)
  return out
}

// ------------------------------------------------ review round 1: guards that only a browser used to give

/** Every `<section>` must hold the shared `.container` as a direct child (the 1248 column and its gutters). */
function sectionProblems(root: HtmlNode, where: string): string[] {
  const out: string[] = []
  for (const sec of all(root, (n) => n.tag === 'section')) {
    const direct = sec.children.some((c) => c.tag !== '#text' && hasClass(c, 'container'))
    if (!direct) out.push(`${where}: <section class="${sec.attrs['class'] ?? ''}"> has no shared .container child`)
  }
  return out
}

/** The live note must not be `display: none` when empty: a region absent from the accessibility tree is often not announced. */
function liveRegionProblems(css: string): string[] {
  const out: string[] = []
  for (const m of css.matchAll(/\.billing-note[^{]*\{([^}]*)\}/g)) {
    if (/display:\s*none/.test(m[1] as string)) out.push('a .billing-note rule sets display: none, so the live region leaves the accessibility tree while empty')
  }
  return out
}

/**
 * A tripwire, not a behaviour test (the behaviour is `npm run test:core`): the key handler must emit the new
 * choice and then move focus to that radio, in that order. Removing the `.focus()` line strands a keyboard user on
 * a radio that is no longer in the tab order, and type-check, lint and every node test used to stay green.
 */
function focusMovementProblems(script: string): string[] {
  const file = ts.createSourceFile('toggle.ts', script, ts.ScriptTarget.ES2023, true)
  let handler: ts.FunctionDeclaration | undefined
  file.forEachChild((n) => {
    if (ts.isFunctionDeclaration(n) && n.name?.text === 'onKeydown') handler = n
  })
  if (!handler || !handler.body) return ['no onKeydown function to read']
  let emitAt = -1
  let focusAt = -1
  const walk = (n: ts.Node): void => {
    if (ts.isCallExpression(n)) {
      if (ts.isIdentifier(n.expression) && n.expression.text === 'emit') emitAt = emitAt === -1 ? n.getStart() : emitAt
      if (ts.isPropertyAccessExpression(n.expression) && n.expression.name.text === 'focus') focusAt = n.getStart()
    }
    n.forEachChild(walk)
  }
  walk(handler.body)
  const out: string[] = []
  if (emitAt === -1) out.push('onKeydown never emits the new choice')
  if (focusAt === -1) out.push('onKeydown never moves focus to the chosen radio (the keyboard user is stranded on a radio that left the tab order)')
  else if (emitAt !== -1 && focusAt < emitAt) out.push('onKeydown moves focus before it emits the choice')
  return out
}

describe('review round 1: guards that only a browser used to give', () => {
  test('N11: every section of the four pages holds the shared .container as a direct child', () => {
    const problems = (Object.keys(VIEWS) as Page[]).flatMap((p) => sectionProblems(pages[p], p))
    assert.deepEqual(problems, [])
    assert.ok(all(pages.about, (n) => n.tag === 'section').length >= 4, 'About has too few sections: the scan is not reading the page')
  })

  test('CONTROL (N11): a section without the container is flagged, and one with it is not', () => {
    assert.equal(sectionProblems(parseHtml('<div><section class="s"><div class="x"></div></section></div>'), 'f').length, 1)
    assert.equal(sectionProblems(parseHtml('<section class="s"><div class="container x"></div></section>'), 'f').length, 0)
  })

  test('N6: the billing note is a polite status region that is never display: none (source), and is rendered from the first render', () => {
    const { css } = sfcSource(read('views/PricingView.vue'), 'PricingView.vue')
    assert.deepEqual(liveRegionProblems(css), [])
    assert.equal(all(pages.pricing, (n) => n.attrs['role'] === 'status' && n.attrs['aria-live'] === 'polite' && hasClass(n, 'billing-note')).length, 1)
  })

  test('CONTROL (N6): the predicate flags display: none on the note, and accepts a visually hidden one', () => {
    assert.equal(liveRegionProblems('.billing-note:empty { display: none; }').length, 1)
    assert.deepEqual(liveRegionProblems('.billing-note:empty { position: absolute; clip: rect(0,0,0,0); }'), [])
  })

  test('N9: the toggle emits the new choice and then moves focus to it (a tripwire; the behaviour is `npm run test:core`)', () => {
    const { descriptor } = parse(read('components/core/SegmentedToggle.vue'), { filename: 'SegmentedToggle.vue' })
    assert.deepEqual(focusMovementProblems(descriptor.scriptSetup?.content ?? ''), [])
  })

  test('CONTROL (N9): the predicate flags a handler with no focus move, focus before emit, and no emit', () => {
    const wrap = (body: string): string => `function onKeydown(e: KeyboardEvent, at: number) { ${body} }`
    assert.equal(focusMovementProblems(wrap("emit('update:modelValue', 'a')")).length, 1)
    assert.equal(focusMovementProblems(wrap("radios?.[to]?.focus(); emit('update:modelValue', 'a')")).length, 1)
    assert.equal(focusMovementProblems(wrap('radios?.[to]?.focus()')).length, 1)
    assert.deepEqual(focusMovementProblems(wrap("emit('update:modelValue', 'a'); radios?.[to]?.focus()")), [])
  })

  test('Shadow F3: no static style attribute ships in the templates (Vue hoists it into markup a style-src policy would drop)', () => {
    const files = [...['Pricing', 'Features', 'Download', 'About'].map((n) => `views/${n}View.vue`), ...['ControllerMock', 'CtaBand', 'FeatureRow', 'PageHero', 'SegmentedToggle', 'ToneChip'].map((n) => `components/core/${n}.vue`)]
    const bad = files.filter((f) => /(^|[\s<])style="/.test(sfcSource(read(f), f).template))
    assert.deepEqual(bad, [], 'a template has a static style="..." attribute; move it to a scoped rule')
  })

  test('Cody N16: no view reaches into UiButton\'s private classes, and the mock names its one hard-coded red once', () => {
    for (const f of ['views/DownloadView.vue', 'views/PricingView.vue']) assert.ok(!/:deep\(\s*\.content/.test(sfcSource(read(f), f).css), `${f} reaches into UiButton's .content`)
    const mock = sfcSource(read('components/core/ControllerMock.vue'), 'ControllerMock.vue').css
    assert.equal((mock.match(/#a3283a/gi) ?? []).length, 1, 'the BLACKOUT red must appear once, as --mock-blank')
    assert.match(mock, /--mock-blank:\s*#a3283a/)
    assert.match(mock, /background:\s*var\(--mock-blank\)/)
  })

  test('CONTROL: the static-style and private-class predicates fire on planted source', () => {
    assert.ok(/(^|[\s<])style="/.test('<span class="brand-mark" style="--mark-size: 16px">'))
    assert.ok(!/(^|[\s<])style="/.test('<section :style="vars">'))
    assert.ok(/:deep\(\s*\.content/.test('.x :deep(.content) { gap: 10px }'))
  })
})

describe('the views use the shared layout', () => {
  const files = ['views/PricingView.vue', 'views/FeaturesView.vue', 'views/DownloadView.vue', 'views/AboutView.vue']

  test('REAL TREE: no local container rule, no 1140 or 1200px column, no gradient variant, no `text` attribute', () => {
    const problems = files.flatMap((f) => layoutProblems(read(f), f))
    assert.deepEqual(problems, [])
  })

  test('REAL TREE: every view puts its sections inside the shared .container', () => {
    for (const f of files) {
      const { template, css } = sfcSource(read(f), f)
      const direct = /class="[^"]*\bcontainer\b/.test(template) || /<(PageHero|CtaBand)\b/.test(template)
      assert.ok(direct, `${f} never uses the shared container`)
      assert.ok(!/padding(-inline)?:[^;]*var\(--page-gutter\)/.test(css), `${f} re-implements the gutter`)
    }
  })

  test('REAL TREE: Pricing does not pass `annual` to the cards (the invented 80% maths stays off)', () => {
    const { template } = sfcSource(read('views/PricingView.vue'), 'PricingView.vue')
    assert.ok(!/:annual=|\bannual="/.test(template), 'the invented 80% maths is switched on')
  })

  test('CONTROL: the same predicate flags each of those faults when planted', () => {
    const wrap = (style: string, template = '<div />'): string => `<template>${template}</template><style scoped>${style}</style>`
    assert.equal(layoutProblems(wrap('.container { max-width: 1200px; }'), 'x').length >= 2, true)
    assert.equal(layoutProblems(wrap('.hero { max-width: 1140px }'), 'x').length, 1)
    assert.equal(layoutProblems(wrap('', '<UiButton variant="gradient">x</UiButton>'), 'x').length, 1)
    assert.equal(layoutProblems(wrap('', '<UiBadge text="Save 20%" />'), 'x').length, 1)
    assert.deepEqual(layoutProblems(wrap('.hero { padding: 0 }'), 'x'), [])
  })
})
