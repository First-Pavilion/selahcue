/**
 * The Sign in, Verify (V1-V6) and Reset (R1-R7) pages against the Figma frames the audit compared them with
 * (ClickUp 17tnw2b2cf1; findings signin-01..11, verify-v1-01/02, verify-v2-01, verify-v5-01/02, reset-r1-02/03,
 * reset-r2-02/03, reset-r3-01/02, reset-r7-01).
 *
 * These are the FIRST-LINE tripwires: instant, exact, no browser. They read the real tree three ways:
 *
 *   1. the stylesheet, RESOLVED (`fixtures/cssSource.ts`): a named rule must exist and declare the named value;
 *   2. the templates, as Vue's own SFC parser builds them: the copy, the link target, the slot, the props;
 *   3. a render of the small shared auth components (Vite `ssrLoadModule` + Vue's string renderer).
 *
 * WHAT NEITHER CAN SEE is the cascade, which is where the real risk is: FormField's own styles are scoped, the
 * auth card overrides them from a global stylesheet, and a rule that reads correctly here can still lose on
 * specificity in a browser. So the pixels, the focus movement and the live regions are asserted again as
 * COMPUTED values in real Chrome by `scripts/auth_pages_headless.py` (`npm run test:states`), and measured against
 * Figma by the marketing harness. This file names the rule and the value that moved; that file proves it applies.
 *
 * EVERY PREDICATE HAS ONE DEFINITION, and each group ends with a fault planted into the SAME predicate
 * (`authViews.test.ts` records why: a ban and the control that vouched for it were two copies, and the ban
 * went dead). A test that cannot fail is a decoration.
 *
 * What this pins, against the ticket's acceptance criteria:
 *   - the Sign in heading copy, the field label ink, the input well, the 7px / 18px rhythm, the 47px and 44px
 *     buttons and the 358px content column;
 *   - the V1 and V2 centring (and ONLY those two states), and the text inside V1's live region;
 *   - placeholder, hint and note ink at AA or better;
 *   - the R3 visible label, the R7 link target, the Forgot link in the label row;
 *   - the sign-up Country select announcing itself as required.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test, { after, before, describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { createSSRApp, h, type Component } from 'vue'
import { parse } from 'vue/compiler-sfc'
import { renderToString } from 'vue/server-renderer'
import { createServer, type ViteDevServer } from 'vite'

import { contrast, effectiveExact, parseCss, resolvePx, rootProperties, type Env, type Rule } from './fixtures/cssSource.ts'

const ROOT = fileURLToPath(new URL('../', import.meta.url))
const SRC = path.join(ROOT, 'src')
const read = (rel: string): string => readFileSync(path.join(SRC, rel), 'utf8')

const DESKTOP: Env = { width: 1440 }
const PHONE: Env = { width: 375 }
const NARROW: Env = { width: 320 }

// ---------------------------------------------------------------------------- reading the stylesheet

const authCss = read('assets/styles/auth.css')
const authRules = parseCss(authCss)
const tokenProps = rootProperties(parseCss(read('assets/styles/tokens.css')), DESKTOP)

/**
 * The declarations of the rules written with exactly this selector, at this environment, or a failure that
 * names the selector: a renamed or deleted rule must fail loudly, not read as "no value, nothing to compare".
 */
function declared(rules: readonly Rule[], selector: string, env: Env = DESKTOP): Record<string, string> {
  const found = effectiveExact(rules, selector, env)
  assert.ok(Object.keys(found).length > 0, `auth.css has no rule for \`${selector}\` at ${env.width}px`)
  return found
}

/** `expected` is a property map; every entry must be what the rule declares, whitespace-insensitive. */
function mismatches(rules: readonly Rule[], selector: string, expected: Record<string, string>, env: Env = DESKTOP): string[] {
  const found = declared(rules, selector, env)
  const norm = (v: string | undefined) => (v ?? '(not declared)').replace(/\s+/g, ' ').trim()
  return Object.entries(expected)
    .filter(([name, value]) => norm(found[name]) !== norm(value))
    .map(([name, value]) => `${selector} { ${name}: ${norm(found[name])} } , wanted ${value}`)
}

function assertRule(selector: string, expected: Record<string, string>, env: Env = DESKTOP, rules: readonly Rule[] = authRules): void {
  assert.deepEqual(mismatches(rules, selector, expected, env), [])
}

// ---------------------------------------------------------------------------- reading the templates

interface AttrProp {
  type: 6
  name: string
  value?: { content: string }
}
interface DirectiveProp {
  type: 7
  name: string
  rawName?: string
  arg?: { content: string }
  exp?: { content: string }
}
interface ElementNode {
  type: 1
  tag: string
  props: Array<AttrProp | DirectiveProp>
  children: Node[]
}
interface TextNode {
  type: 2
  content: string
}
type Node = ElementNode | TextNode | { type: number; children?: Node[]; content?: unknown }

function rootOf(sfc: string, filename: string): Node[] {
  const { descriptor, errors } = parse(sfc, { filename })
  assert.equal(errors.length, 0, `${filename} did not parse: ${errors.map(String).join('; ')}`)
  return ((descriptor.template?.ast as { children?: Node[] } | undefined)?.children ?? []) as Node[]
}

function elementsIn(nodes: readonly Node[]): ElementNode[] {
  const found: ElementNode[] = []
  const walk = (node: Node): void => {
    if (node.type === 1) found.push(node as ElementNode)
    for (const child of (node as { children?: Node[] }).children ?? []) if (typeof child === 'object') walk(child)
  }
  for (const n of nodes) walk(n)
  return found
}

const elementsOf = (sfc: string, filename: string): ElementNode[] => elementsIn(rootOf(sfc, filename))

const attr = (el: ElementNode, name: string): string | undefined => {
  const p = el.props.find((x): x is AttrProp => x.type === 6 && x.name === name)
  return p ? (p.value?.content ?? '') : undefined
}
const directive = (el: ElementNode, name: string): DirectiveProp | undefined =>
  el.props.find((x): x is DirectiveProp => x.type === 7 && x.name === name)
const bound = (el: ElementNode, name: string): string | undefined =>
  el.props.find((x): x is DirectiveProp => x.type === 7 && x.name === 'bind' && x.arg?.content === name)?.exp?.content

/** The static text under a node, whitespace-collapsed; an interpolation is shown as `{{…}}` so it cannot pass as copy. */
function textOf(node: Node): string {
  if (node.type === 2) return (node as TextNode).content
  if (node.type === 5) return '{{…}}'
  return ((node as { children?: Node[] }).children ?? []).map((c) => (typeof c === 'object' ? textOf(c) : '')).join('')
}
const textContent = (el: ElementNode): string => textOf(el).replace(/\s+/g, ' ').trim()

// ================================================================================== the stylesheet

describe('the auth card: 358px of content, as Figma draws it (signin-11)', () => {
  test('the card is padded 35px, so with its 1px border the content column is 358px (430 - 2 x 36)', () => {
    const card = declared(authRules, '.au-card')
    const padding = resolvePx(card['padding'] ?? '', {})
    const border = resolvePx((card['border'] ?? '').split(/\s+/)[0] ?? '', {})
    assert.equal(padding, 35, '.au-card padding')
    assert.equal(border, 1, '.au-card border')
    assert.equal(430 - 2 * (padding + border), 358, 'the content column of a 430px card')
    assert.equal(card['max-width'], '430px')
  })

  test('the phone paddings keep the same 1px compensation (24 -> 23, 20/18 -> 19/17)', () => {
    assertRule('.au-card', { padding: '23px' }, PHONE)
    assertRule('.au-card', { padding: '19px 17px' }, NARROW)
  })
})

describe('auth titles, notes and banners carry the Figma metrics (verify-v2-01, verify-v5-01, card heights)', () => {
  test('a title is one 29px line (26px form titles: 31px), the height Figma draws, so a two-line title is 58px and not 60px', () => {
    assertRule('.au-title', { 'line-height': '29px' })
    assertRule('.au-title-form', { 'line-height': '31px' })
  })

  test('the note under a button is 12.5px on a 17px line in the secondary ink (it was 13/20 in the muted ink: 3.79:1)', () => {
    assertRule('.au-note', { color: 'var(--sc-text-secondary)', 'font-size': '12.5px', 'line-height': '17px' })
  })

  test('banners: 12px between glyph and copy, glyph 15px, title 13px/16px with a 3px gap, body 12.5px/17px', () => {
    assertRule('.au-banner', { gap: '12px' })
    assertRule('.au-banner-glyph', { 'font-size': '15px', 'line-height': '18px' })
    assertRule('.au-banner-title', { 'font-size': '13px', 'line-height': '16px', margin: '0 0 3px' })
    assertRule('.au-banner-body', { 'font-size': '12.5px', 'line-height': '17px' })
  })
})

describe('auth fields: label, input well, stroke and rhythm (signin-06, -07, -09, -08, reset-r1-03)', () => {
  test('the label is 13px / 500 on a 16px line in the secondary ink, not 14px / 600 in the primary ink', () => {
    assertRule('.au-card form .field-label', {
      'font-size': '13px',
      'font-weight': '500',
      'line-height': '16px',
      color: 'var(--sc-text-secondary)',
    })
  })

  test('the input is 44px tall on the inset well, not the elevated chip', () => {
    assertRule('.au-card form .field-input', { background: 'var(--sc-inset)', height: '44px' })
  })

  test('a field is label 16 + 7 + input 44 + (7 + 17 when a hint or error shows), fields 18px apart; the empty meta row is gone', () => {
    assertRule('.au-card form .form-field', { gap: '7px', 'margin-bottom': '0' })
    assertRule('.au-card form .form-field.has-label-action', { gap: '7px 12px' })
    assertRule('.au-card form', { display: 'flex', 'flex-direction': 'column', gap: '18px' })
    assertRule('.au-card form .field-meta', { 'min-height': '0' })
    assertRule('.au-card form .field-meta:empty', { display: 'none' })
  })

  test('focus and error are a 1.5px stroke (a 1px border plus a 0.5px inset ring) and the 3px halo is gone', () => {
    assertRule('.au-card form .field-input:focus', { 'border-color': 'var(--sc-primary)', 'box-shadow': 'inset 0 0 0 0.5px var(--sc-primary)' })
    assertRule('.au-card form .has-error .field-input', { 'border-color': 'var(--sc-live)', 'box-shadow': 'inset 0 0 0 0.5px var(--sc-live)' })
    // A focused field in error keeps the error stroke: FormField's own rule for that state is a halo.
    assertRule('.au-card form .has-error .field-input:focus', { 'border-color': 'var(--sc-live)', 'box-shadow': 'inset 0 0 0 0.5px var(--sc-live)' })
    for (const selector of ['.au-card form .field-input:focus', '.au-card form .has-error .field-input', '.au-card form .has-error .field-input:focus']) {
      assert.doesNotMatch(declared(authRules, selector)['box-shadow'] ?? '', /\b3px\b/, `${selector} still draws the 3px halo`)
    }
  })

  test('the text Show / Hide toggle keeps its room: the input is padded 64px on the right under the new padding', () => {
    assertRule('.au-card form .field-input.has-reveal-text', { 'padding-right': '64px' })
  })

  test('placeholder, hint and note are the secondary ink and clear 4.5:1 on every surface they sit on', () => {
    assertRule('.au-card form .field-input::placeholder', { color: 'var(--sc-text-secondary)' })
    assertRule('.au-card form .field-hint', { color: 'var(--sc-text-secondary)', 'font-size': '12.5px', 'line-height': '17px' })
    const hex = (name: string): string => {
      const v = tokenProps[name]
      assert.ok(v && /^#[0-9a-f]{6}$/i.test(v), `${name} is not a plain hex token: ${v}`)
      return v
    }
    const ink = hex('--sc-text-secondary')
    for (const [what, ground] of [
      ['placeholder on the inset well', '--sc-inset'],
      ['placeholder on a disabled (dimmed) field is judged at rest, on the inset well too', '--sc-inset'],
      ['hint and note on the card', '--sc-surface'],
      ['note on the card page', '--sc-base'],
    ] as const) {
      const ratio = contrast(ink, hex(ground))
      assert.ok(ratio >= 4.5, `${what}: ${ratio.toFixed(2)}:1 is below 4.5:1`)
    }
  })

  test('forced-colors mode keeps a focus outline, because it deletes the ring that replaced the halo', () => {
    const forced: Env = { width: 1440, forcedColors: true }
    assertRule('.au-card form .field-input:focus', { outline: '2px solid Highlight' }, forced)
    assert.equal(effectiveExact(authRules, '.au-card form .field-input:focus', DESKTOP)['outline'], undefined, 'the outline is for forced colours only')
  })

  test('the select on sign-up is drawn like the input it sits beside: inset well, 1.5px stroke', () => {
    assertRule('.au-card form .au-select', { background: 'var(--sc-inset)', height: '44px' })
    assertRule('.au-card form .au-select:focus', { 'border-color': 'var(--sc-primary)', 'box-shadow': 'inset 0 0 0 0.5px var(--sc-primary)' })
  })
})

describe('auth buttons: 47px primary, 44px secondary with a border, the label stays visible while loading (signin-10, reset-r3-01)', () => {
  test('primary is 47px at weight 600, secondary 44px with a 1px hairline; padding cannot grow them', () => {
    assertRule('.au-card .au-btn.ui-button', { width: '100%', 'border-radius': '12px' })
    assertRule('.au-card .au-btn.ui-button.au-btn-primary', { height: '47px', 'min-height': '47px', 'padding-block': '0', 'font-size': '15.5px', 'font-weight': '600' })
    assertRule('.au-card .au-btn.ui-button.au-btn-secondary', { height: '44px', 'min-height': '44px', 'padding-block': '0', 'font-size': '14.5px', border: '1px solid var(--sc-border)' })
  })

  test('a button that is loading keeps its label at full strength, hides the generic spinner and dims once to 50%', () => {
    assertRule('.au-card .au-btn.is-loading .content', { opacity: '1' })
    assertRule('.au-card .au-btn.is-loading .spinner', { display: 'none' })
    assertRule('.au-card .au-btn.is-loading', { opacity: '0.5' })
  })

  test('a button held by field errors (R2) is 45% opaque, by its aria-disabled attribute', () => {
    assertRule('.au-card .au-btn[aria-disabled="true"]', { opacity: '0.45' })
  })

  test('the ↻ glyph is 14px / 700 and stays a static mark under reduced motion', () => {
    assertRule('.au-btn .au-spinner', { 'font-size': '14px', 'font-weight': '700' })
    const motion = authCss.slice(authCss.indexOf('prefers-reduced-motion'))
    assert.match(motion, /\.au-spinner[\s\S]*animation:\s*none/)
  })
})

describe('V1 and V2 centre the disc, title and body, and nothing else does (verify-v1-01)', () => {
  test('the centred modifier centres the disc, the title and the body', () => {
    assertRule('.au-card-center .au-disc', { 'align-self': 'center' })
    assertRule('.au-card-center .au-title', { 'text-align': 'center' })
    assertRule('.au-card-center .au-body', { 'text-align': 'center' })
  })

  test('the card itself stays left-aligned, so banners, buttons, notes and the footer are untouched', () => {
    assertRule('.au-card', { 'text-align': 'left' })
    const centred = authRules.filter((r) => r.selectors.some((s) => s.includes('.au-card-center')))
    for (const r of centred) {
      for (const s of r.selectors) assert.match(s, /\.au-(disc|title|body)$/, `${s}: the centring may only reach the disc, the title and the body`)
    }
  })

  test('the screen-reader-only text used inside V1\'s live region is clipped, not display:none (which would silence it)', () => {
    const sr = declared(authRules, '.au-sr-only')
    assert.equal(sr['position'], 'absolute')
    assert.notEqual(sr['display'], 'none')
    assert.notEqual(sr['visibility'], 'hidden')
  })
})

describe('the planted faults: each predicate above turns red on the fault it names', () => {
  const plant = (from: RegExp, to: string): Rule[] => parseCss(authCss.replace(from, to))

  test('label ink put back to the primary ink', () => {
    const faulty = plant(/(\.au-card form \.field-label\s*\{[^}]*?color:\s*)var\(--sc-text-secondary\)/, '$1var(--sc-text)')
    assert.notDeepEqual(mismatches(faulty, '.au-card form .field-label', { color: 'var(--sc-text-secondary)' }), [])
  })

  test('card padding put back to 36px', () => {
    const faulty = plant(/(\.au-card\s*\{[^}]*?padding:\s*)35px/, '$136px')
    assert.notDeepEqual(mismatches(faulty, '.au-card', { padding: '35px' }), [])
  })

  test('the halo put back on focus', () => {
    const faulty = plant(/(\.au-card form \.field-input:focus\s*\{[^}]*?box-shadow:\s*)[^;]+/, '$10 0 0 3px rgba(110, 92, 240, 0.25)')
    assert.notDeepEqual(mismatches(faulty, '.au-card form .field-input:focus', { 'box-shadow': 'inset 0 0 0 0.5px var(--sc-primary)' }), [])
  })

  test('the loading label hidden again', () => {
    const faulty = plant(/(\.au-card \.au-btn\.is-loading \.content\s*\{[^}]*?opacity:\s*)1/, '$10')
    assert.notDeepEqual(mismatches(faulty, '.au-card .au-btn.is-loading .content', { opacity: '1' }), [])
  })

  test('a missing rule is reported by name, not read as an empty value', () => {
    assert.throws(() => declared(parseCss('.nothing { color: red }'), '.au-card form .field-label'), /no rule for `\.au-card form \.field-label`/)
  })
})

// ================================================================================== the templates

const signIn = elementsOf(read('views/SignInView.vue'), 'views/SignInView.vue')
const verify = elementsOf(read('views/VerifyView.vue'), 'views/VerifyView.vue')
const reset = elementsOf(read('views/ResetView.vue'), 'views/ResetView.vue')
const signUp = elementsOf(read('views/SignUpView.vue'), 'views/SignUpView.vue')

/** The Sign in heading of the form state: the one with the form's title class. */
function signInHeading(els: readonly ElementNode[]): string[] {
  return els.filter((e) => e.tag === 'h1' && (attr(e, 'class') ?? '').includes('au-title-form')).map(textContent)
}

describe('Sign in: the heading and the Forgot link (signin-01, signin-05)', () => {
  test('the form state is headed "Welcome back" (Figma 505:124), not the desktop A1 title', () => {
    assert.deepEqual(signInHeading(signIn), ['Welcome back'])
  })

  test('the Forgot link is a link in the Password label row: visible "Forgot?", named "Forgot your password?", to /forgot-password', () => {
    const password = signIn.find((e) => e.tag === 'FormField' && attr(e, 'label') === 'Password')
    assert.ok(password, 'no Password FormField on Sign in')
    const slot = password.children.find((c): c is ElementNode => c.type === 1 && (c as ElementNode).tag === 'template' && directive(c as ElementNode, 'slot')?.arg?.content === 'label-action')
    assert.ok(slot, 'the Password field has no #label-action slot')
    const link = elementsIn(slot.children).find((e) => e.tag === 'router-link' || e.tag === 'RouterLink')
    assert.ok(link, 'the label-action slot holds no router-link')
    assert.equal(attr(link, 'to'), '/forgot-password')
    assert.equal(attr(link, 'aria-label'), 'Forgot your password?')
    assert.equal(textContent(link), 'Forgot?')
  })

  test('the row below the field is gone: there is exactly one Forgot link on the page', () => {
    const links = signIn.filter((e) => (e.tag === 'router-link' || e.tag === 'RouterLink') && attr(e, 'to') === '/forgot-password')
    assert.equal(links.length, 1)
    assert.equal(signIn.filter((e) => (attr(e, 'class') ?? '').includes('au-inline-link')).length, 0)
  })

  test('Sign in keeps the eye icon (Figma draws no reveal control; the gap-fill spec says the eye) and no field takes the text reveal', () => {
    for (const el of signIn.filter((e) => e.tag === 'FormField')) {
      assert.equal(attr(el, 'reveal-style') ?? bound(el, 'reveal-style'), undefined, `Sign in field "${attr(el, 'label')}" must keep the default reveal`)
    }
  })

  test('no Continue with Google, and no field is marked required (Figma draws no required marker on Sign in)', () => {
    assert.equal(rootOf(read('views/SignInView.vue'), 'SignInView.vue').map(textOf).join('').includes('Google'), false)
    for (const els of [signIn, verify, reset]) assert.equal(els.filter((e) => e.tag === 'FormField' && attr(e, 'required') !== undefined).length, 0)
  })
})

describe('Verify: V1 and V2 centre, the others do not; the V1 live region has text; the envelope is a text glyph', () => {
  const STATES = ['verifying', 'verified', 'invalid', 'missing', 'sent', 'unreachable'] as const

  /**
   * What `<AuthShell :align=…>` produces in a state, by evaluating the template expression itself (the view
   * keeps its state in a ref, so `state` in the template is `state.value` in script).
   */
  function alignWith(els: readonly ElementNode[], state: string): string | undefined {
    const shell = els.find((e) => e.tag === 'AuthShell')
    assert.ok(shell, 'no AuthShell in VerifyView')
    const expression = bound(shell, 'align')
    if (expression === undefined) return attr(shell, 'align')
    return new Function('state', `return (${expression.replace(/\bstate\b/g, 'state.value')})`)({ value: state }) as string | undefined
  }

  test('only the verifying and verified states ask the shell for the centred card', () => {
    const centred = STATES.filter((s) => alignWith(verify, s) === 'center')
    assert.deepEqual(centred, ['verifying', 'verified'])
  })

  test('V1\'s live region holds announcing text, not only a bar', () => {
    const region = verify.find((e) => attr(e, 'role') === 'status')
    assert.ok(region, 'V1 has no role="status" region')
    assert.equal(attr(region, 'aria-live'), 'polite')
    assert.match(textContent(region), /Verifying your email address/)
  })

  test('the envelope disc is the text glyph (U+2709 U+FE0E), not the emoji-or-fallback one, in all three views', () => {
    for (const view of ['views/VerifyView.vue', 'views/ResetView.vue', 'views/SignInView.vue']) {
      const discs = elementsOf(read(view), view).filter((e) => e.tag === 'StatusDisc' && (attr(e, 'glyph') ?? '').startsWith('✉'))
      assert.ok(discs.length > 0, `${view} has no envelope disc`)
      for (const d of discs) assert.equal(attr(d, 'glyph'), '✉︎', `${view}: the envelope has no text-presentation selector`)
    }
  })
})

describe('Reset: Show/Hide and the cross on both password fields, the loading label, the R7 link (reset-r1-01/r2-01 adopted, reset-r3-01, reset-r7-01)', () => {
  test('both password fields ask FormField for the text reveal and the visible cross', () => {
    const fields = reset.filter((e) => e.tag === 'FormField' && attr(e, 'type') === 'password')
    assert.equal(fields.length, 2)
    for (const f of fields) {
      assert.equal(attr(f, 'reveal-style'), 'text', `"${attr(f, 'label')}" reveal`)
      assert.equal(attr(f, 'error-style'), 'glyph', `"${attr(f, 'label')}" error`)
    }
  })

  test('the submitting label shows the ↻ glyph and the words "Updating password…", both in the button', () => {
    const buttons = reset.filter((e) => e.tag === 'UiButton' && (attr(e, 'class') ?? '').includes('au-btn-primary'))
    const submitting = elementsIn(buttons.flatMap((b) => b.children)).find((e) => e.tag === 'template' && /Updating password…/.test(textContent(e)))
    assert.ok(submitting, 'the button has no "Updating password…" branch')
    const glyph = elementsIn(submitting.children).find((e) => (attr(e, 'class') ?? '').includes('au-spinner'))
    assert.ok(glyph, 'the submitting label has no au-spinner glyph')
    assert.equal(textContent(glyph), '↻')
    assert.equal(attr(glyph, 'aria-hidden'), 'true')
  })

  test('the R7 footer asks for a new reset link at /forgot-password, not Sign in', () => {
    const footer = reset.find((e) => e.tag === 'template' && directive(e, 'slot')?.arg?.content === 'footer')
    assert.ok(footer, 'no #footer slot')
    const branch = elementsIn(footer.children).find((e) => e.tag === 'template' && /serverError/.test(directive(e, 'else-if')?.exp?.content ?? ''))
    assert.ok(branch, 'the footer has no serverError branch')
    const link = elementsIn(branch.children).find((e) => e.tag === 'router-link' || e.tag === 'RouterLink')
    assert.ok(link, 'the R7 footer has no link')
    assert.equal(textContent(link), 'Request a new reset link')
    assert.equal(attr(link, 'to'), '/forgot-password')
  })

  test('nothing on R7 or anywhere on Reset says Sign in is the way out of a link that still works', () => {
    const footer = reset.find((e) => e.tag === 'template' && directive(e, 'slot')?.arg?.content === 'footer') as ElementNode
    const branch = elementsIn(footer.children).find((e) => e.tag === 'template' && /serverError/.test(directive(e, 'else-if')?.exp?.content ?? '')) as ElementNode
    assert.equal(elementsIn(branch.children).filter((e) => (e.tag === 'router-link' || e.tag === 'RouterLink') && attr(e, 'to') === '/signin').length, 0)
  })
})

describe('sign-up Country select is announced as required (shared components review N3)', () => {
  const country = signUp.find((e) => e.tag === 'select' && attr(e, 'id') === 'signup-country')

  test('it carries aria-required="true"', () => {
    assert.ok(country, 'the Country select was not found')
    assert.equal(attr(country, 'aria-required'), 'true')
  })

  test('and not the native `required` attribute, which would put the browser\'s own bubble ahead of the form\'s validation', () => {
    assert.ok(country)
    assert.equal(attr(country, 'required'), undefined)
    assert.equal(bound(country, 'required'), undefined)
  })
})

describe('no account-existence oracle is introduced (AUTH-LANDING-PAGES-HANDOFF 1 and 10; signin-15)', () => {
  /** Script code without comments, so the view's own prose about why it checks no length cannot trip the rule. */
  const scriptOf = (view: string): string =>
    (parse(read(view), { filename: view }).descriptor.scriptSetup?.content ?? '')
      .replace(/\/\*[\s\S]*?\*\//g, ' ')
      .replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1 ')

  /** The ways Sign in could tell a visitor how long a password has to be. Empty when it cannot. */
  function lengthHints(view: string): string[] {
    const script = scriptOf(view)
    const copy = rootOf(read(view), view).map(textOf).join(' ')
    const found: string[] = []
    if (/passwordPolicy|MIN_PASSWORD_LENGTH|MAX_PASSWORD_LENGTH|PASSWORD_TOO_SHORT/.test(script)) found.push('imports the password policy')
    if (/password\.value\.length|codePointLength\s*\(\s*password/.test(script)) found.push('measures the password')
    if (/\b\d+\s*characters?\b|at least \d+/i.test(copy + script)) found.push('says a number of characters')
    return found
  }

  test('Sign in neither imports the password policy, measures the password, nor says how long one must be', () => {
    assert.deepEqual(lengthHints('views/SignInView.vue'), [])
  })

  test('the control: a Sign in that checked the length, or said so, is found', () => {
    assert.notDeepEqual(lengthHints('views/ResetView.vue'), [], 'Reset states the rule by design, so the detector must see it there')
  })
})

describe('the planted faults in the templates', () => {
  test('a Sign in heading that says the old words is found', () => {
    const faulty = elementsOf(read('views/SignInView.vue').replace('>Welcome back</h1>', '>Sign in to SelahCue</h1>'), 'fault.vue')
    assert.notDeepEqual(signInHeading(faulty), ['Welcome back'])
  })

  test('an R7 footer that points at /signin is found', () => {
    const source = read('views/ResetView.vue').replace(/to="\/forgot-password">Request a new reset link/, 'to="/signin">Request a new reset link')
    const els = elementsOf(source, 'fault.vue')
    const footer = els.find((e) => e.tag === 'template' && directive(e, 'slot')?.arg?.content === 'footer') as ElementNode
    const branch = elementsIn(footer.children).find((e) => e.tag === 'template' && /serverError/.test(directive(e, 'else-if')?.exp?.content ?? '')) as ElementNode
    const link = elementsIn(branch.children).find((e) => e.tag === 'router-link' || e.tag === 'RouterLink') as ElementNode
    assert.notEqual(attr(link, 'to'), '/forgot-password')
  })
})

// ================================================================================== the components

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

async function authComponent(name: string): Promise<Component> {
  const cached = loaded.get(name)
  if (cached) return cached
  const mod = (await server.ssrLoadModule(`/src/components/auth/${name}.vue`)) as { default: Component }
  loaded.set(name, mod.default)
  return mod.default
}

async function renderAuth(name: string, props: Record<string, unknown> = {}, slots: Record<string, () => unknown> = {}): Promise<string> {
  const Comp = await authComponent(name)
  return renderToString(createSSRApp({ render: () => h(Comp, props, slots as never) }))
}

const classesOf = (html: string, id: 'au-card'): string[] => {
  const m = new RegExp(`<div class="([^"]*\\b${id}\\b[^"]*)"`).exec(html)
  return (m?.[1] ?? '').split(/\s+/)
}

describe('AuthShell: the centred card is opt-in (verify-v1-01)', () => {
  test('by default the card is the left-aligned card it always was', async () => {
    const html = await renderAuth('AuthShell', {}, { default: () => h('p', 'x') })
    assert.deepEqual(classesOf(html, 'au-card'), ['au-card'])
  })

  test('align="center" adds the one modifier class; "start" and anything else do not', async () => {
    assert.ok(classesOf(await renderAuth('AuthShell', { align: 'center' }), 'au-card').includes('au-card-center'))
    assert.deepEqual(classesOf(await renderAuth('AuthShell', { align: 'start' }), 'au-card'), ['au-card'])
    assert.deepEqual(classesOf(await renderAuth('AuthShell', { align: 'banana' }), 'au-card'), ['au-card'])
  })

  test('the footer slot is still rendered outside the card', async () => {
    const html = await renderAuth('AuthShell', {}, { default: () => h('p', 'in'), footer: () => h('span', 'out') })
    const card = /<div class="au-card[^"]*">(.*?)<\/div>/s.exec(html)?.[1] ?? ''
    assert.ok(card.includes('in') && !card.includes('out'), 'the footer text is inside the card')
    assert.match(html, /<p class="au-footer-link">(?:<!--.*?-->)*<span>out<\/span>/)
  })
})
