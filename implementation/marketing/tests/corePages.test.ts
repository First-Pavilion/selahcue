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
 *     Figma: owner decision). There is NO allow-listed region any more: the Pricing FAQ and its unbacked
 *     answers were removed by ClickUp 17tnw2b0x3h;
 *   - Pricing: no plan, price, comparison table, billing toggle or FAQ (plan names and prices come from the API once
 *     it serves them), no `text="Save 20%"`, no `variant="gradient"`, the billing toggle
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
  walk,
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

  test('pricing-bug-01: the page names no plan, so there is no h3 plan name to sit under the h1 (ClickUp 17tnw2b0x3h)', () => {
    assert.ok(!headingLevels(pages.pricing).includes(3), 'a plan name (h3) is back on the Pricing page; plan names come from the API')
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
  { id: 'fully offline', pattern: /fully offline|completely offline|100\s?% offline|stays offline|offline by default|offline when it matters|keeps working offline|doesn.t either/, because: 'NFR-015 backs core live functions only; sign-in, activation, hosted speech-to-text and the model download need the network (Shadow F1, Cody N20, Quinn N6)' },
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

/** The text of a page. There is no allow-listed region: the Pricing FAQ that was one is gone (ClickUp 17tnw2b0x3h). */
function claimText(page: Page): string {
  const parts: string[] = []
  const visit = (n: HtmlNode): void => {
    if (n.tag === '#text') parts.push(n.text ?? '')
    for (const c of n.children) visit(c)
  }
  visit(pages[page])
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}

describe('no claim the repo does not back is on the page', () => {
  for (const page of Object.keys(VIEWS) as Page[]) {
    test(`${page}: none of the banned strings is rendered`, () => {
      assert.deepEqual(bannedHits(claimText(page), page), [])
    })
  }

  test('no page carries an allow-listed region: the Pricing FAQ and its exception are gone, and cannot come back unnoticed', () => {
    for (const page of Object.keys(VIEWS) as Page[]) {
      assert.deepEqual(all(pages[page], (n) => n.attrs['data-region'] === 'pricing-faq'), [], `${page}: a data-region="pricing-faq" is back`)
    }
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

  test('CONTROL (review round 2, Cody N20 and Quinn N6): the sibling phrases of "fully offline" are banned too', () => {
    const must: Array<[string, Page]> = [
      ['a church presentation app that stays up, stays offline, and stays out of the way', 'about'],
      ['Offline by default', 'about'],
      ["so SelahCue doesn't either", 'about'],
      ['SelahCue keeps working offline when it matters most', 'features'],
      ['and it runs offline when it matters most', 'about'],
    ]
    for (const [text, page] of must) assert.ok(bannedHits(text, page).length > 0, `"${text}" on ${page} should be flagged`)
    for (const ok of ['Core live controls work offline', 'Core live controls keep working with no network', 'Works without a network']) {
      assert.deepEqual(bannedHits(ok, 'about'), [], `"${ok}" is the NFR-015-consistent wording`)
    }
  })

  test('CONTROL: a banned string is only banned on the pages it names', () => {
    assert.deepEqual(bannedHits('4K 60fps', 'pricing'), [])
    assert.equal(bannedHits('4K 60fps', 'features').length, 1)
  })
})

// ----------------------------------------------------------------------------------- the copy ledger

/**
 * Every block of text a page shows (an element's own text), in the order they appear. A deny-list can only catch
 * what somebody thought to ban: Quinn planted 30 plausible unbacked sentences in an About paragraph and 20 passed
 * (review round 2, Quinn N4). So the copy is an ALLOW-LIST too.
 */
function blocks(root: HtmlNode): string[] {
  const out: string[] = []
  walk(root, (n) => {
    if (n.tag === '#text') return
    const own = n.children
      .filter((c) => c.tag === '#text')
      .map((c) => c.text ?? '')
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim()
    if (own) out.push(own)
  })
  return out
}

/**
 * THE COPY LEDGER: every block of text each page may show, in order. Figma's wording where the repo backs it, the
 * backed part where Figma claims more, and the honest states (the disabled buttons, "To be confirmed"). A sentence
 * is added here, in review, or it does not ship; a reworded line fails the same way. The goal contract
 * (docs/delivery/goals/17tnw2b2cey-figma-core-pages.md) says where each wording decision comes from.
 */
const LEDGER: Readonly<Record<Page, readonly string[]>> = {
  // The plan cards, the comparison table, the billing toggle and the FAQ are gone (ClickUp 17tnw2b0x3h): plan names and prices
  // come from the API once it serves them.
  pricing: [
    "PRICING",
    "Pricing that grows with your church",
    "Plans and prices have not been published yet.",
  ],
  features: [
    "FEATURES",
    "Everything you need to run a confident service",
    "From the first slide to the final blessing, SelahCue keeps your scripture, songs, timers, stage display and streaming outputs in one offline-first console — with a phone in your hand as the remote.",
    "OUTPUTS",
    "Live presentation & outputs",
    "Stage everything in Preview, then Go Live with a single tap. Audience projector and stage display run from one deck, with live output built to stay up.",
    "Preview → Live with one Go Live",
    "Designed so a fault cannot black out live output",
    "Audience + stage from one deck",
    "OUTPUTS",
    "LIVE",
    "SCRIPTURE",
    "Scripture at your fingertips",
    "A full public-domain translation is bundled in the app. Type a reference or search by keyword — it works with no internet at all.",
    "Bundled WEB translation, no internet needed",
    "Reference parsing + keyword search",
    "Send to Preview, then push Live",
    "SCRIPTURE",
    "WEB",
    "PLANNING",
    "Service plans & timers",
    "Order your whole service ahead of time, then run it with countdown and count-up timers so you always land on time.",
    "Plan the full order of service",
    "Countdown + count-up timers",
    "Reorder on the fly, mid-service",
    "PLANNING",
    "TIMERS",
    "STAGE",
    "Stage & confidence monitor",
    "Give your platform team a clear current / next / timer view — high-contrast and independent, so a change to the audience screen never disrupts it.",
    "Current / next / timer for the platform",
    "High-contrast, glanceable layout",
    "Independent of audience output",
    "STAGE",
    "READY",
    "STREAMING",
    "NDI & multi-output",
    "Send your program over NDI straight into OBS or vMix, and drive more than one output from the same deck.",
    "Program over NDI to OBS / vMix",
    "More than one output from one deck",
    "NDI output is optional",
    "STREAMING",
    "NDI",
    "ASSIST",
    "On-device transcript & detection",
    "An optional live transcript runs on your machine. It assists the operator but never gates your core controls.",
    "Live transcript, on-device",
    "Scripture detection that assists the operator",
    "Assists — never gates — core controls",
    "ASSIST",
    "ON-DEVICE",
    "Ready to run your best service yet?",
    "Start with the Free plan. Core live controls keep working with no network.",
    "Download free",
    "See pricing",
  ],
  download: [
    "DOWNLOAD",
    "Get SelahCue for your platform",
    "Desktop installers are not available to download yet. Core live controls work with no network, and mobile control pairs over your local network.",
    "Free plan · Core live controls work offline",
    "Windows",
    "Windows desktop app · 64-bit",
    "Download for Windows",
    "Not available to download yet",
    "macOS",
    "macOS desktop app",
    "Download for macOS",
    "Not available to download yet",
    "System requirements",
    "MINIMUM",
    "requirements",
    "Processor",
    "To be confirmed",
    "Memory",
    "To be confirmed",
    "Graphics",
    "To be confirmed",
    "Storage",
    "To be confirmed",
    "Display",
    "To be confirmed",
    "RECOMMENDED",
    "requirements",
    "Processor",
    "To be confirmed",
    "Memory",
    "To be confirmed",
    "Graphics",
    "To be confirmed",
    "Storage",
    "To be confirmed",
    "Display",
    "To be confirmed",
    "MOBILE CONTROL",
    "Control from your phone",
    "The SelahCue Controller pairs with your desktop over your local network — scan a QR code and you're connected. It's a companion remote: your desktop always stays the authority, even if the phone drops off Wi-Fi.",
    "Pairs over your LAN — no internet needed",
    "iOS and Android apps are not available yet",
    "Desktop stays authoritative if the phone drops",
    "App Store",
    "Coming soon",
    "Google Play",
    "Coming soon",
    "The SelahCue Controller app is not in the App Store or Google Play yet.",
    "Controller",
    "CONNECTED",
    "ON SCREEN NOW",
    "John 3:16",
    "Go Live",
    "Blank",
    "Next",
    "Up and running in three steps",
    "01",
    "Download & install",
    "Run the installer for your platform once it is available.",
    "02",
    "Build your first plan",
    "Add scripture, songs and timers to a service plan and pick your outputs.",
    "03",
    "Go live & pair your phone",
    "Hit Go Live, then scan the QR code to pair your phone as a remote.",
  ],
  about: [
    "ABOUT",
    "Built for the people running the service",
    "SelahCue started with one conviction: the moment a congregation is worshipping is not the moment your software should fail. So we built a church presentation app that stays up, keeps its core controls working with no network, and stays out of the way.",
    "Why we built SelahCue",
    "Too many services are one crashed slide away from a blank screen — and the tools meant to help often assume a fast, always-on internet connection that a lot of churches simply don't have.",
    "We wanted the opposite: an app that stays in charge on your own computer, is designed so a fault cannot blank live output, runs every core live control with no network, and lets AI assist the operator without gating core controls.",
    "That's what SelahCue is — presentation, scripture, timers, stage display and streaming outputs in one console, with a phone in your hand as the remote, built to be dependable on the one morning you can't get a second take.",
    "What we stand for",
    "Reliability comes first",
    "Live output is designed to stay up. Every decision serves the one moment you can't repeat.",
    "Works without a network",
    "Your Sunday can't depend on the internet, so core live controls work without it.",
    "AI assists, never gates",
    "Transcript and detection help the operator but stay out of the core controls.",
    "Bounded & respectful",
    "Memory use is designed to stay within fixed limits, so SelahCue stays light.",
    "Ready to run your best service yet?",
    "Start with the Free plan. Core live controls keep working with no network.",
    "Download free",
    "See pricing",
  ],
}

/**
 * EMPTY ON PURPOSE (ClickUp 17tnw2b0x3h). This was the list of claims the live pages already made (on Pricing: "MOST POPULAR" and
 * three FAQ answers about proration, a non-profit rule and PayPal / ACH). They were removed, and a test below fails if an entry
 * is ever added. The mechanism stays so the allow-list below keeps one definition.
 */
const LIVE_CLAIMS: Readonly<Record<Page, Readonly<Record<string, string>>>> = {
  pricing: {},
  features: {},
  download: {},
  about: {},
}

/** Every block the page shows that is on neither its ledger nor its named list of live claims. */
function unlistedBlocks(root: HtmlNode, page: Page, ledger: Readonly<Record<Page, readonly string[]>> = LEDGER, claims = LIVE_CLAIMS): string[] {
  const allowed = new Set([...ledger[page], ...Object.keys(claims[page])])
  return [...new Set(blocks(root).filter((b) => !allowed.has(b)))]
}

describe('copy follows the ledger (review round 2, Quinn N4): nothing is on the page that nobody listed', () => {
  for (const page of Object.keys(VIEWS) as Page[]) {
    test(`${page}: every ledger line is on the page, in the order the ledger lists it`, () => {
      const shown = blocks(pages[page])
      let from = 0
      for (const line of LEDGER[page]) {
        const at = shown.indexOf(line, from)
        assert.ok(at !== -1, `${page} is missing (or has out of order): ${line}`)
        from = at + 1
      }
    })

    test(`${page}: nothing else is on the page: every block of text is on the ledger or on the named live claims`, () => {
      assert.deepEqual(unlistedBlocks(pages[page], page), [])
    })
  }

  // ClickUp 17tnw2b0x3h's check, executable: nothing is tolerated on these pages that the repo does not back.
  test('no claim the repo does not back is live on any page: every LIVE_CLAIMS list is empty (ClickUp 17tnw2b0x3h)', () => {
    for (const page of Object.keys(VIEWS) as Page[]) {
      assert.deepEqual(Object.keys(LIVE_CLAIMS[page]), [], `${page}: unbacked lines are still tolerated; remove the words and the entry`)
    }
  })

  test('every named live claim is still on the page (so the list shrinks when a claim is removed)', () => {
    for (const page of Object.keys(VIEWS) as Page[]) {
      const shown = new Set(blocks(pages[page]))
      for (const claim of Object.keys(LIVE_CLAIMS[page])) assert.ok(shown.has(claim), `${page}: the live claim is gone, delete it from LIVE_CLAIMS: ${claim}`)
    }
  })

  test('CONTROL: sentences nobody thought to ban are reported on every page, as is a reworded ledger line', () => {
    // Quinn's plants, review round 2 (20 of 30 passed the deny-list).
    const plants = [
      'Available now for Linux',
      'Download the macOS .dmg today',
      'Works on any computer',
      'Rated 4.9 stars',
      'Instant setup',
      'Built by pastors',
      'Never crashes',
      'Grab the installer for your platform and run it.',
      'Available',
      'Trusted by 5,000 churches.',
    ]
    for (const page of Object.keys(VIEWS) as Page[]) {
      for (const plant of plants) {
        const root = parseHtml(`<div><p>${plant}</p></div>`)
        assert.deepEqual(unlistedBlocks(root, page), [plant], `"${plant}" should be reported on ${page}`)
      }
      const reworded = (LEDGER[page][2] as string).replace(/\.$/, '!')
      assert.equal(unlistedBlocks(parseHtml(`<p>${reworded}</p>`), page).length, 1, `a reworded ledger line on ${page} should be reported`)
      assert.deepEqual(unlistedBlocks(parseHtml(`<p>${LEDGER[page][1]}</p>`), page), [], 'a ledger line is not reported')
    }
    // The claims tolerated before ClickUp 17tnw2b0x3h are reported on every page now, their old home included.
    assert.deepEqual(unlistedBlocks(parseHtml('<p>MOST POPULAR</p>'), 'pricing'), ['MOST POPULAR'], 'a removed claim is not allowed on its old page')
    assert.deepEqual(unlistedBlocks(parseHtml('<p>MOST POPULAR</p>'), 'about'), ['MOST POPULAR'], 'and not on another page')
  })
})

// ------------------------------------------------------------------------------------ Pricing

describe('Pricing', () => {
  test('hero: the PRICING eyebrow, the Figma headline and a subline', () => {
    const h1 = byTag(pages.pricing, 'h1')[0] as HtmlNode
    assert.equal(textOf(h1), 'Pricing that grows with your church')
    assert.ok(textOf(pages.pricing).includes('PRICING'), 'no PRICING eyebrow')
    const lead = byClass(pages.pricing, 'hero-lead')[0]
    assert.ok(lead && textOf(lead).length > 40, 'no subline under the headline')
    assert.equal(textOf(lead as HtmlNode), 'Plans and prices have not been published yet.')
  })

  // ClickUp 17tnw2b0x3h: plan names, prices and limits are the API catalogue's data, so until it serves them the page shows none.
  test('the page draws no plan, price, limit, comparison table, billing toggle or FAQ: it says plans and prices are not published yet', () => {
    assert.deepEqual(byClass(pages.pricing, 'pricing-card'), [], 'a plan card is back')
    assert.deepEqual(byClass(pages.pricing, 'pricing-grid'), [])
    assert.deepEqual(byTag(pages.pricing, 'table'), [], 'a comparison table is back')
    assert.deepEqual(all(pages.pricing, (n) => n.attrs['role'] === 'radiogroup'), [], 'a billing toggle is back')
    assert.deepEqual(byClass(pages.pricing, 'faq-section'), [], 'a FAQ is back')
    assert.deepEqual(byTag(pages.pricing, 'h3'), [], 'a plan name is back')
    assert.deepEqual(byClass(pages.pricing, 'ui-button'), [], 'a plan button is back')
    const text = textOf(pages.pricing)
    assert.doesNotMatch(text, /\$|\bPro\b|\bPlatinum\b|\bCore\b|\bChurch plan\b|devices?\b|NDI|watermark|prorat|PayPal|ACH|non-profit|MOST POPULAR|Monthly|Annual/i)
  })

  test('the view types no plan name and no limit: they will come from the API, not from this file', () => {
    const { descriptor } = parse(readFileSync(path.join(SRC, 'views/PricingView.vue'), 'utf8'), { filename: 'PricingView.vue' })
    const code = (descriptor.scriptSetup?.content ?? '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
    assert.doesNotMatch(code, /name:|price:|LIMITS|plans\b|rows\b|pricingFaqItems|PricingCard|SegmentedToggle/, 'PricingView holds plan data again')
    assert.doesNotMatch(descriptor.template?.content ?? '', /PricingCard|SegmentedToggle|FaqAccordion|<table/)
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

  test('review round 2, Quinn N1: a chord is the browser\'s, not the toggle\'s (Alt, Ctrl, Cmd or Shift held means unhandled)', async () => {
    const { nextIndex } = await keys()
    const on = [true, true, true]
    for (const key of ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End']) {
      for (const mod of ['alt', 'ctrl', 'meta', 'shift'] as const) {
        assert.equal(nextIndex(key, 1, on, { [mod]: true }), null, `${mod}+${key} must be left to the browser (Back and Forward, jump to the ends, selection)`)
      }
      assert.notEqual(nextIndex(key, 1, on, {}), null, `the bare ${key} is the toggle's`)
      assert.notEqual(nextIndex(key, 1, on, { alt: false, ctrl: false, meta: false, shift: false }), null, `an event with no modifier held handles ${key}`)
    }
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
    assert.deepEqual(byTag(band, 'h3').map((n) => textOf(n)), ['Reliability comes first', 'Works without a network', 'AI assists, never gates', 'Bounded & respectful'])
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
  const text = handler.body.getText()
  for (const prop of ['altKey', 'ctrlKey', 'metaKey', 'shiftKey']) {
    if (!text.includes(prop)) out.push(`onKeydown never reads ${prop}, so a chord with it held is swallowed (Alt+Left is the browser's Back)`)
  }
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

  test('N9: the toggle emits the new choice and then moves focus to it (a tripwire; the behaviour is `npm run test:core`)', () => {
    const { descriptor } = parse(read('components/core/SegmentedToggle.vue'), { filename: 'SegmentedToggle.vue' })
    assert.deepEqual(focusMovementProblems(descriptor.scriptSetup?.content ?? ''), [])
  })

  test('CONTROL (N9 and Quinn N1): the predicate flags a handler with no focus move, focus before emit, no emit, and no modifier reading', () => {
    const mods = 'const m = [e.altKey, e.ctrlKey, e.metaKey, e.shiftKey];'
    const wrap = (body: string): string => `function onKeydown(e: KeyboardEvent, at: number) { ${mods} ${body} }`
    assert.equal(focusMovementProblems(wrap("emit('update:modelValue', 'a')")).length, 1)
    assert.equal(focusMovementProblems(wrap("radios?.[to]?.focus(); emit('update:modelValue', 'a')")).length, 1)
    assert.equal(focusMovementProblems(wrap('radios?.[to]?.focus()')).length, 1)
    assert.deepEqual(focusMovementProblems(wrap("emit('update:modelValue', 'a'); radios?.[to]?.focus()")), [])
    // a handler that never reads the modifier keys swallows Alt+Left
    assert.equal(focusMovementProblems("function onKeydown(e: KeyboardEvent, at: number) { emit('update:modelValue', 'a'); radios?.[to]?.focus() }").length, 4)
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

describe('review round 2: one visually-hidden rule', () => {
  test('Cody N22: no view carries its own copy of `.sr-only`; the one rule lives in SrOnly.vue', () => {
    for (const f of ['views/PricingView.vue', 'views/FeaturesView.vue', 'views/DownloadView.vue', 'views/AboutView.vue']) {
      assert.ok(!/\.sr-only\s*\{/.test(sfcSource(read(f), f).css), `${f} declares its own .sr-only`)
    }
    assert.match(sfcSource(read('components/core/SrOnly.vue'), 'SrOnly.vue').css, /\.sr-only\s*\{[^}]*clip:/)
  })

  test('CONTROL (N22): the predicate fires on a pasted copy', () => {
    assert.ok(/\.sr-only\s*\{/.test('.sr-only { position: absolute; }'))
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
