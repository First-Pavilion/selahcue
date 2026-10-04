/**
 * The shared chrome every page frame carries: navbar, footer and the app shell (ClickUp 17tnw2b2cev,
 * audit findings shared-chrome-01 to 09, 14 to 18, 20, 34).
 *
 * Source tripwires, resolved rather than grepped where a value is involved (`fixtures/cssSource.ts`
 * walks the media blocks and the cascade). Node cannot lay a page out, so the proof of the pixels is the
 * browser: the marketing harness (`visual_parity.py --suite marketing` + `vp_style_diff.py`) and
 * `scripts/responsive_sweep.py`. Each group below names the finding it guards.
 *
 * What is NOT pinned, on purpose: decisions held for the owner or Uma (the signed-in nav, the nav
 * underline, the hover colours, the footer tagline and legal wording, the document titles). The footer
 * wording is asserted to stay what the repo can back, so a Figma claim cannot slip in unnoticed.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { describe } from 'node:test'

import { contrast, effective, parseCss, resolvePx, rootProperties, stripComments, styleOf, type Env } from './fixtures/cssSource.ts'

const SRC = new URL('../src/', import.meta.url)
const read = (relative: string) => readFileSync(new URL(relative, SRC), 'utf8')

const navbar = read('components/Navbar.vue')
const footer = read('components/Footer.vue')
const app = read('App.vue')
const router = read('router/index.ts') + '\n' + read('router/articleRoutes.ts')

const globalRules = [...parseCss(read('assets/styles/tokens.css')), ...parseCss(read('assets/styles/main.css'))]
const navRules = parseCss(styleOf(navbar))
const footerRules = parseCss(styleOf(footer))
const appRules = parseCss(styleOf(app))

const DESKTOP: Env = { width: 1440 }
const TABLET: Env = { width: 1024 }
const MOBILE: Env = { width: 375 }
const tokens = (env: Env) => rootProperties(globalRules, env)

const nav = (classes: string[], env: Env = DESKTOP, pseudo: string | null = null) => effective(navRules, classes, env, pseudo)
const foot = (classes: string[], env: Env = DESKTOP, pseudo: string | null = null) => effective(footerRules, classes, env, pseudo)

/** Every static path the router serves: the catch-all and parameterised article routes excluded. */
const routerPaths = new Set([...router.matchAll(/\{\s*path:\s*'([^':]+)'/g)].map((m) => m[1] as string))

describe('the router table the links are walked against', () => {
  test('is read correctly: the routes the chrome links to are in it, the catch-all is not', () => {
    for (const path of ['/', '/features', '/pricing', '/download', '/docs', '/support', '/changelog', '/privacy', '/terms']) {
      assert.ok(routerPaths.has(path), `${path} not found in the parsed router table`)
    }
    assert.ok(routerPaths.size > 15, 'the router parse found suspiciously few routes')
    assert.ok(![...routerPaths].some((p) => p.includes('pathMatch')))
  })
})

// ---------------------------------------------------------------------------------------------
describe('navbar: geometry (shared-chrome-01, 02, 03)', () => {
  test('the bar is the height token, border included: 79px at 1440 (Figma 468:126), 69px on the phone bar', () => {
    for (const [env, bar, total] of [
      [DESKTOP, 78, 79],
      [TABLET, 78, 79],
      [{ width: 768 }, 78, 79],
      [MOBILE, 68, 69],
    ] as const) {
      const container = nav(['navbar-container'], env)
      assert.equal(resolvePx(container['height'] ?? '', tokens(env)), bar, `bar content height at ${env.width}`)
      assert.equal(
        resolvePx(container['height'] ?? '', tokens(env)) + resolvePx(nav(['navbar-header'], env)['border-bottom']?.split(' ')[0] ?? '', {}),
        total,
        `header height at ${env.width}`,
      )
      assert.equal(resolvePx(tokens(env)['--nav-height'] ?? '', {}), total, `--nav-height at ${env.width}`)
    }
  })

  test('the content runs at 48px gutters at 1440 (not inset to x=124 by a 1240px cap), 24px on tablet, 20px on mobile', () => {
    const gutter = (env: Env) => resolvePx((nav(['navbar-container'], env)['padding'] ?? '').split(/\s+/)[1] ?? '', tokens(env))
    assert.deepEqual([DESKTOP, TABLET, MOBILE].map(gutter), [48, 24, 20])
    assert.doesNotMatch(styleOf(navbar), /max-width:\s*1240px/)
    assert.equal(nav(['navbar-container'])['max-width'], '1440px', 'the bar is the 1440 design; beyond it the content centres instead of stretching edge to edge')
    assert.equal(nav(['navbar-container'])['margin'], '0 auto')
  })

  test('the lockup is 8px between mark and wordmark, 40px to the links; the links are 28px apart', () => {
    assert.equal(nav(['brand'])['gap'], '8px')
    assert.equal(nav(['left-group'])['gap'], '40px')
    assert.equal(nav(['desktop-nav'])['gap'], '28px')
  })

  test('the mark is a 32px square (the logo file carries ~33% transparent padding, the shared .brand-mark crops it)', () => {
    assert.match(navbar, /<span class="brand-mark"[^>]*>\s*<img src="\/selahcue-logo\.png" alt="" aria-hidden="true"/)
    const main = parseCss(read('assets/styles/main.css'))
    const mark = effective(main, ['brand-mark'], DESKTOP)
    assert.equal(mark['width'], 'var(--mark-size, 32px)')
    assert.equal(mark['height'], 'var(--mark-size, 32px)')
    assert.equal(mark['overflow'], 'hidden')
  })

  test('the wordmark is 19px Bold in the primary text colour with no tracking', () => {
    const w = nav(['brand-wordmark'])
    assert.equal(w['font-size'], '19px')
    assert.equal(w['font-weight'], '700')
    assert.equal(w['color'], 'var(--sc-text)')
    assert.equal(w['letter-spacing'], '0')
  })

  test('the tablet steps are unchanged (responsive layout belongs to 17tnw2b0q9g)', () => {
    assert.equal(nav(['left-group'], TABLET)['gap'], '20px')
    assert.equal(nav(['desktop-nav'], TABLET)['gap'], '12px')
    assert.equal(nav(['right-group'], TABLET)['gap'], '12px')
  })
})

describe('navbar: ink and weight (shared-chrome-04, 05)', () => {
  test('the active route is Semi Bold in the primary text colour; inactive links are Medium in the secondary ink', () => {
    const active = nav(['nav-item', 'active'])
    assert.equal(active['font-weight'], '600')
    assert.equal(active['color'], 'var(--sc-text)')
    const idle = nav(['nav-item'])
    assert.equal(idle['font-weight'], '500')
    assert.equal(idle['color'], 'var(--sc-text-secondary)')
  })

  test('Sign in and Sign out are in the primary text colour, with an 18px gap to the CTA', () => {
    assert.equal(nav(['signin-btn'])['color'], 'var(--sc-text)')
    assert.equal(nav(['signout-btn'])['color'], 'var(--sc-text)')
    assert.equal(nav(['right-group'])['gap'], '18px')
  })

  test('no pure white ink on the bar: #ffffff is reserved for text on a coloured fill', () => {
    for (const cls of ['brand-wordmark', 'signin-btn', 'signout-btn']) assert.doesNotMatch(nav([cls])['color'] ?? '', /#fff/i, cls)
    assert.doesNotMatch(nav(['nav-item', 'active'])['color'] ?? '', /#fff/i)
  })
})

describe('navbar: the Download free button (shared-chrome-06, 25)', () => {
  test('it is rendered by UiButton, compact, so the nav no longer carries a private copy of the button', () => {
    const tag = /<UiButton[^>]*class="download-cta"[^>]*>/.exec(navbar)?.[0] ?? ''
    assert.ok(tag, 'the navbar CTA is not a UiButton with class download-cta')
    assert.match(tag, /to="\/download"/)
    assert.match(tag, /size="compact"/)
    assert.match(navbar, /import UiButton from '@\/components\/UiButton\.vue'/)
  })

  test('it carries no rule of its own for radius, weight, padding or fill, hover included: those come from UiButton', () => {
    for (const rule of navRules) {
      if (!rule.selectors.some((s) => /\.download-cta/.test(s))) continue
      for (const banned of ['border-radius', 'font-weight', 'background', 'background-color', 'padding']) {
        // the tablet step trims the side padding to fit the signed-in state at 768; nothing else may
        if (banned === 'padding' && /size-compact/.test(rule.selectors.join(','))) continue
        assert.equal(rule.decls[banned], undefined, `${rule.selectors.join(',')} sets ${banned}`)
      }
    }
  })

  test('its hover is the ONE primary hover (an AA fill, reset-r2-04): no private hover colour is left in the bar', () => {
    assert.doesNotMatch(styleOf(navbar), /--nav-cta-hover/)
    assert.deepEqual(effective(navRules, ['download-cta', 'variant-primary'], DESKTOP, 'hover'), {})
  })
})

describe('navbar: surface and tokens (shared-chrome-09, 25)', () => {
  test('the bar sits on the page colour with the token border, not a hard-coded darker band', () => {
    const header = nav(['navbar-header'])
    assert.equal(header['background'], 'var(--sc-base)')
    assert.equal(header['border-bottom'], '1px solid var(--sc-border)')
  })

  test('the scrolled state is the same token at 90% over a blur', () => {
    const scrolled = nav(['navbar-header', 'is-scrolled'])
    assert.match(scrolled['background'] ?? '', /^color-mix\(in srgb, var\(--sc-base\) 90%, transparent\)$/)
    assert.match(scrolled['backdrop-filter'] ?? '', /blur\(16px\)/)
    // Written by hand next to the unprefixed property, `-webkit-backdrop-filter` made the production CSS
    // minifier keep ONLY the prefixed one, and Chrome has no prefixed alias: the scrolled bar had no
    // blur at all outside Safari. The minifier adds the prefix itself where a target needs it.
    assert.equal(scrolled['-webkit-backdrop-filter'], undefined, 'drop the hand-written prefix; the build adds it')
  })

  test('the scrolled state is OBSERVED, not read: an IntersectionObserver on a 10px sentinel at the document top, so nothing forces a layout in the first script task', () => {
    const mounted = /onMounted\(\(\) => \{([\s\S]*?)\n\}\)/.exec(navbar)?.[1] ?? ''
    const code = stripComments(mounted)
    assert.match(code, /new IntersectionObserver\(/)
    assert.match(code, /\.observe\(sentinelEl\.value\)/)
    // `window.scrollY` forces a style and layout pass; read synchronously in onMounted it pushed the app's first task over the
    // 50ms long-task line on Pricing and Terms (+18-20ms layout at 4x CPU, performance review of PR 172).
    assert.doesNotMatch(code, /scrollY/, 'onMounted reads window.scrollY')
    assert.doesNotMatch(code.replace(/addEventListener\('scroll', handleScroll[^)]*\)/, ''), /\bhandleScroll\(/, 'onMounted calls handleScroll() synchronously')
    assert.match(navbar, /<div ref="sentinelEl" class="scroll-sentinel" aria-hidden="true"><\/div>/)
  })

  test('the sentinel is the old "scrollY > 10" rule exactly: 10px tall at the very top of the DOCUMENT, out of flow, invisible to the pointer', () => {
    const d = nav(['scroll-sentinel'])
    assert.equal(d['position'], 'absolute')
    assert.equal(d['top'], '0')
    assert.equal(d['height'], '10px')
    assert.equal(d['pointer-events'], 'none')
    // absolute against the initial containing block, so no positioned ancestor may sit above it
    assert.equal(effective(parseCss(styleOf(app)), ['app-shell'], DESKTOP)['position'], undefined)
    assert.match(navbar, /isScrolled\.value = !\(entry\?\.isIntersecting \?\? true\)/)
  })

  test('the observer is disconnected on unmount, and old browsers without IntersectionObserver keep the scroll listener (also removed)', () => {
    const unmounting = /onBeforeUnmount\(\(\) => \{([\s\S]*?)\n\}\)/.exec(navbar)?.[1] ?? ''
    assert.match(unmounting, /scrollObserver\?\.disconnect\(\)/)
    assert.match(unmounting, /removeEventListener\('scroll', handleScroll\)/)
    assert.match(navbar, /typeof IntersectionObserver === 'function'/)
  })

  test('control: the check bites. A synchronous read in onMounted is reported', () => {
    const tampered = navbar.replace(/(onMounted\(\(\) => \{)/, '$1\n  handleScroll()')
    const mounted = /onMounted\(\(\) => \{([\s\S]*?)\n\}\)/.exec(tampered)?.[1] ?? ''
    assert.match(stripComments(mounted).replace(/addEventListener\('scroll', handleScroll[^)]*\)/, ''), /\bhandleScroll\(/)
  })

  test('no hard-coded brand or neutral colour is left in the bar: the token layer is used', () => {
    const style = stripComments(styleOf(navbar))
    for (const literal of ['#090a0f', '#9aa4b2', '#5b6bd6', '#4f5ec7', 'rgba(255, 255, 255, 0.08)']) {
      assert.ok(!style.includes(literal), `${literal} is hard-coded in Navbar.vue`)
    }
  })
})

describe('navbar: keyboard focus (shared-chrome-08)', () => {
  test('the brand, every link and the sign-out button show a 2px brand ring with a 2px offset', () => {
    for (const cls of ['brand', 'nav-item', 'signin-btn', 'signout-btn']) {
      const d = nav([cls], DESKTOP, 'focus-visible')
      assert.match(d['outline'] ?? '', /^2px solid var\(--sc-primary\)$/, cls)
      assert.equal(d['outline-offset'], '2px', cls)
    }
  })

  test('the CTA gets its ring from UiButton, and a zero-specificity global default covers anything a component forgets', () => {
    const main = read('assets/styles/main.css')
    assert.match(main, /:where\(a, button[^)]*\):focus-visible\s*\{[^}]*outline:\s*2px solid var\(--sc-primary\)/)
    assert.match(main, /:where\([^)]*\):focus-visible\s*\{[^}]*outline-offset:\s*2px/)
  })
})

describe('navbar: How it works is a real link (shared-chrome-07)', () => {
  test('desktop and the mobile sheet both link to the Home route WITH the hash, so it works from every page', () => {
    const links = [...navbar.matchAll(/<router-link[^>]*:to="\{ path: '\/', hash: '#how-it-works' \}"[^>]*>/g)]
    assert.equal(links.length, 2, 'expected the desktop link and the sheet link')
    assert.doesNotMatch(navbar, /<a href="#how-it-works"/, 'a bare #how-it-works anchor only works on Home and does nothing there')
  })

  test('it is never the "current page": a custom router-link that renders a plain <a>, so no aria-current and no active class (Home is "/", and the router ignores the hash)', () => {
    const tags = [...navbar.matchAll(/<router-link[^>]*hash: '#how-it-works'[^>]*>/g)]
    assert.equal(tags.length, 2)
    for (const tag of tags) assert.match(tag[0], /\bcustom\b/, 'a default router-link sets aria-current="page" on Home')
    // the slot renders a plain anchor that the link only navigates, and never forwards aria-current
    const slots = [...navbar.matchAll(/<router-link[^>]*hash: '#how-it-works'[^>]*>\s*<a :href="href" class="(nav-item|mobile-link)"[^>]*@click="navigate[(")]/g)]
    assert.deepEqual(slots.map((m) => m[1]).sort(), ['mobile-link', 'nav-item'])
    const region = tags.map((t) => navbar.slice(t.index, navbar.indexOf('</router-link>', t.index))).join('\n')
    assert.doesNotMatch(region, /aria-current/)
  })

  test('control: the check bites. A default router-link (no custom) is reported', () => {
    const tampered = navbar.replace(/ custom v-slot="\{ href, navigate \}"/, '')
    const tag = [...tampered.matchAll(/<router-link[^>]*hash: '#how-it-works'[^>]*>/g)][0]?.[0] ?? ''
    assert.doesNotMatch(tag, /\bcustom\b/)
  })

  test('every other navbar link goes to a real route', () => {
    const links = [...navbar.matchAll(/<(?:router-link|UiButton)\b[^>]*>/g)].map((m) => m[0])
    const targets = links.flatMap((tag) => [...tag.matchAll(/(?<![:\w])to="([^"]+)"/g)].map((m) => m[1] as string))
    assert.ok(targets.length >= 8)
    for (const to of targets) assert.ok(routerPaths.has(to), `navbar links to ${to}, which the router does not serve`)
  })
})

// ---------------------------------------------------------------------------------------------
/** The footer link data, read from the SFC source: `{ to, label }` entries per `title`. */
function footerColumns(source: string): { title: string; links: { to: string; label: string }[] }[] {
  const block = /const columns = \[([\s\S]*?)\n\]\n/.exec(source)?.[1] ?? ''
  return [...block.matchAll(/title:\s*'([^']+)',\s*links:\s*\[([\s\S]*?)\],?\s*\}/g)].map((m) => ({
    title: m[1] as string,
    links: [...(m[2] ?? '').matchAll(/\{\s*to:\s*'([^']+)',\s*label:\s*'([^']+)'\s*\}/g)].map((l) => ({ to: l[1] as string, label: l[2] as string })),
  }))
}

function legalLinks(source: string): { to: string; label: string }[] {
  const block = /const legalLinks = \[([\s\S]*?)\n\]\n/.exec(source)?.[1] ?? ''
  return [...block.matchAll(/\{\s*to:\s*'([^']+)',\s*label:\s*'([^']+)'\s*\}/g)].map((l) => ({ to: l[1] as string, label: l[2] as string }))
}

describe('footer: Figma\'s three columns and bottom bar (shared-chrome-14, 15)', () => {
  const columns = footerColumns(footer)

  test('three columns, in order: Product, Resources, Company, with exactly the entries and targets Figma draws', () => {
    assert.deepEqual(columns, [
      {
        title: 'Product',
        links: [
          { to: '/features', label: 'Features' },
          { to: '/pricing', label: 'Pricing' },
          { to: '/download', label: 'Download' },
          { to: '/changelog', label: 'Changelog' },
        ],
      },
      {
        title: 'Resources',
        links: [
          { to: '/docs', label: 'Documentation' },
          { to: '/docs', label: 'Setup guides' },
          { to: '/features', label: 'NDI & streaming' },
          { to: '/support', label: 'Support' },
        ],
      },
      {
        title: 'Company',
        links: [
          { to: '/about', label: 'About' },
          { to: '/blog', label: 'Blog' },
          { to: '/contact', label: 'Contact' },
          { to: '/careers', label: 'Careers' },
          { to: '/affiliates', label: 'Affiliates' },
        ],
      },
    ])
  })

  test('there is no Legal column, and Privacy and Terms are short bottom-bar links', () => {
    assert.ok(!columns.some((c) => c.title === 'Legal'))
    assert.deepEqual(legalLinks(footer), [
      { to: '/privacy', label: 'Privacy' },
      { to: '/terms', label: 'Terms' },
    ])
    assert.match(footer, /<footer[\s\S]*class="footer-bottom"[\s\S]*v-for="link in legalLinks"/)
  })

  test('the bottom bar names the platforms the build ships for', () => {
    assert.match(footer, /Windows · macOS/)
  })

  test('EVERY footer link resolves to a real route: none is /how-it-works, none falls to the 404 page', () => {
    const all = [...columns.flatMap((c) => c.links), ...legalLinks(footer)]
    assert.ok(all.length >= 15, 'the footer link parse found suspiciously few links')
    for (const link of all) assert.ok(routerPaths.has(link.to), `footer "${link.label}" -> ${link.to} is not a route`)
    assert.ok(!all.some((l) => l.to === '/how-it-works'))
  })

  test('control: the walk bites. A link to a path with no route is reported', () => {
    const tampered = footer.replace("{ to: '/changelog', label: 'Changelog' }", "{ to: '/how-it-works', label: 'How it works' }")
    const all = footerColumns(tampered).flatMap((c) => c.links)
    assert.ok(all.some((l) => !routerPaths.has(l.to)), 'the route walk could not tell a missing route from a real one')
  })

  test('links that share a target keep their own keys (Documentation and Setup guides are both /docs)', () => {
    assert.match(footer, /v-for="link in column\.links" :key="link\.label"/)
  })

  test('the wording is what the repo can back: no subscription or cancellation claim has been adopted (decision 19 is pending)', () => {
    assert.match(footer, /Church presentation, reengineered/)
    assert.match(footer, /© 2026 SelahCue\. All rights reserved\./)
    assert.doesNotMatch(footer, /subscription-simple|Cancel anytime/i)
  })
})

describe('footer: layout and type (shared-chrome-16, 17, 18)', () => {
  test('the footer is the page colour with the token top border; the first heading is 56px from the top (55 + the 1px border, as Figma\'s stroke is inside its padding), 40px below', () => {
    const f = foot(['footer'])
    assert.equal(f['background'], 'var(--sc-base)')
    assert.equal(f['border-top'], '1px solid var(--sc-border)')
    assert.equal(f['padding-top'], '55px')
    assert.equal(f['padding-bottom'], '40px')
  })

  test('it is built on the shared container, so the content runs 96..1344 at 1440', () => {
    assert.match(footer, /<div class="container footer-content">/)
    assert.equal(effective(globalRules, ['container'], DESKTOP)['padding-inline'], 'var(--gutter)')
  })

  test('on desktop the three columns hug their content at 64px gaps, flush right; tablet and mobile keep their grid', () => {
    const d = foot(['links-grid'])
    assert.equal(d['display'], 'flex')
    assert.equal(d['gap'], '64px')
    assert.equal(d['justify-content'], 'flex-end')
    assert.equal(foot(['links-grid'], TABLET)['display'], 'grid')
    assert.match(styleOf(footer), /\.footer\.is-mobile \.links-grid \{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/)
  })

  test('headings are 12px Bold capitals in the secondary ink with 0.1px tracking, 28px above the first link', () => {
    const h = foot(['column-title'])
    assert.equal(h['font-size'], '12px')
    assert.equal(h['font-weight'], '700')
    assert.equal(h['text-transform'], 'uppercase')
    assert.equal(h['letter-spacing'], '0.1px')
    assert.equal(h['color'], 'var(--sc-text-secondary)')
    assert.equal(h['line-height'], '15px')
    assert.equal(foot(['link-column'])['gap'], '13px')
  })

  test('links are 14px in the primary text colour on a 17px line and a 13px gap: the 30px pitch Figma draws', () => {
    const l = foot(['footer-link'])
    assert.equal(l['color'], 'var(--sc-text)')
    assert.equal(l['font-size'], '14px')
    assert.equal(l['line-height'], '17px')
    assert.equal(foot(['column-links'])['gap'], '13px')
  })

  test('the lockup is a 28px mark, 8px gap, 18px Bold wordmark with no tracking, 12px above the tagline', () => {
    assert.match(footer, /<span class="brand-mark brand-mark-footer"[^>]*>\s*<img src="\/selahcue-logo\.png" alt="" aria-hidden="true"/)
    assert.equal(foot(['brand-mark-footer'])['--mark-size'], '28px')
    assert.equal(foot(['brand'])['gap'], '8px')
    assert.equal(foot(['brand'])['margin-bottom'], '12px')
    const w = foot(['wordmark'])
    assert.equal(w['font-size'], '18px')
    assert.equal(w['letter-spacing'], '0')
    assert.equal(w['color'], 'var(--sc-text)')
  })

  test('the tagline is 14px on a 21px line in the secondary ink, in a 300px box', () => {
    const t = foot(['tagline'])
    assert.equal(t['font-size'], '14px')
    assert.equal(t['line-height'], '21px')
    assert.equal(t['color'], 'var(--sc-text-secondary)')
    assert.equal(foot(['brand-column'])['max-width'], '300px')
  })

  test('the divider and bottom row: 40px between columns and divider, 40px under it; 13px text in the secondary ink', () => {
    assert.equal(foot(['footer-top'])['margin-bottom'], '40px')
    const bottom = foot(['footer-bottom'])
    assert.equal(bottom['border-top'], '1px solid var(--sc-border)')
    assert.equal(bottom['padding-top'], '40px')
    for (const cls of ['copyright', 'legal-link', 'platforms']) {
      assert.equal(foot([cls])['font-size'], '13px', cls)
      assert.equal(foot([cls])['color'], 'var(--sc-text-secondary)', cls)
    }
    assert.equal(foot(['legal-links'])['column-gap'], '22px')
  })

  test('every footer link and the brand show the 2px brand ring', () => {
    for (const cls of ['footer-link', 'legal-link', 'brand', 'column-toggle']) {
      assert.match(foot([cls], DESKTOP, 'focus-visible')['outline'] ?? '', /^2px solid var\(--sc-primary\)$/, cls)
    }
  })

  test('the mobile sections keep their 44px rows and the legal links get 44px targets too', () => {
    const style = styleOf(footer)
    assert.match(style, /\.footer\.is-mobile \.footer-link \{[^}]*min-height:\s*44px/)
    // judged on the smaller side, and "Terms" is only 37px wide as text: both axes need the floor
    assert.match(style, /\.footer\.is-mobile \.legal-link \{[^}]*min-height:\s*44px[^}]*min-width:\s*44px/)
  })
})

// ---------------------------------------------------------------------------------------------
describe('contrast of the small text in the chrome (shared-chrome-20, 21, 34)', () => {
  const p = tokens(DESKTOP)
  const resolveInk = (value: string | undefined): string => {
    const m = /^var\((--[\w-]+)\)$/.exec(value ?? '')
    assert.ok(m, `not a token reference: ${value}`)
    return p[m?.[1] ?? ''] ?? ''
  }

  test('nothing in the navbar, footer or app shell uses --sc-text-muted: the chrome uses the inks Figma maps', () => {
    for (const [name, source] of [['Navbar.vue', navbar], ['Footer.vue', footer], ['App.vue', app]] as const) {
      assert.doesNotMatch(stripComments(styleOf(source)), /--sc-text-muted/, name)
    }
  })

  test('every small-text ink and fill pair in the chrome is at least 4.5:1', () => {
    const base = p['--sc-base'] ?? ''
    const pairs: [string, string, string][] = [
      ['footer copyright', resolveInk(foot(['copyright'])['color']), base],
      ['footer legal links', resolveInk(foot(['legal-link'])['color']), base],
      ['footer platforms', resolveInk(foot(['platforms'])['color']), base],
      ['footer headings', resolveInk(foot(['column-title'])['color']), base],
      ['footer links', resolveInk(foot(['footer-link'])['color']), base],
      ['footer tagline', resolveInk(foot(['tagline'])['color']), base],
      ['nav links', resolveInk(nav(['nav-item'])['color']), base],
      ['nav active', resolveInk(nav(['nav-item', 'active'])['color']), base],
      ['nav Sign in', resolveInk(nav(['signin-btn'])['color']), base],
      ['nav wordmark', resolveInk(nav(['brand-wordmark'])['color']), base],
      ['route loading fallback', resolveInk(effective(appRules, ['loading'], DESKTOP)['color']), base],
      ['nav CTA label (white on brand)', '#ffffff', p['--sc-primary'] ?? ''],
      ['nav CTA label on hover (the shared primary hover fill)', '#ffffff', p['--sc-primary-hover-fill'] ?? ''],
    ]
    for (const [what, ink, fill] of pairs) {
      const ratio = contrast(ink, fill)
      assert.ok(ratio >= 4.5, `${what}: ${ink} on ${fill} is ${ratio.toFixed(2)}:1`)
    }
  })
})

describe('app shell (shared-chrome-34)', () => {
  test('the route-loading fallback is announced politely and readable', () => {
    assert.match(app, /<div class="loading" role="status">Loading\.\.\.<\/div>/)
    assert.equal(effective(appRules, ['loading'], DESKTOP)['color'], 'var(--sc-text-secondary)')
  })
})
