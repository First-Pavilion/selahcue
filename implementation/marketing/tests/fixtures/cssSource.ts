/**
 * A small, honest CSS reader for the source tripwires in the chrome tests.
 *
 * Node cannot lay a page out, so a test that wants to say "the navbar bar is 79px tall at 1440"
 * or "a medium button is 44px" has to RESOLVE the stylesheet rather than grep it: find the rules
 * that apply to a given set of classes at a given viewport, let the more specific / later one win,
 * and do the arithmetic. A grep for `height: 78px` would pass on a rule that a later media block
 * overrides, and on a rule for the wrong selector. This is deliberately limited to what the chrome
 * uses: compound class selectors (with one optional pseudo-class), plain `@media` width queries,
 * and px / custom-property arithmetic. Anything it cannot read it SKIPS, and the tests that use it
 * assert that the rule they care about was found, so an unreadable rule fails loudly instead of
 * vacuously passing.
 *
 * The proof that the pixels are right is the browser run (the harness and the responsive sweep);
 * this is the cheap first-line guard that names the value and the rule that moved.
 */

export interface Rule {
  /** The selector as written, one entry per comma-separated selector. */
  readonly selectors: readonly string[]
  readonly decls: Readonly<Record<string, string>>
  /** The `@media` prelude this rule sits in, or null at the top level. */
  readonly media: string | null
  readonly order: number
}

export interface Env {
  readonly width: number
  readonly pointer?: 'fine' | 'coarse'
  readonly forcedColors?: boolean
  readonly reducedMotion?: boolean
}

export function stripComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '')
}

/** The text of every `<style>` block of an SFC, joined. */
export function styleOf(sfc: string): string {
  return [...sfc.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1] ?? '').join('\n')
}

export function parseDecls(body: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const part of body.split(';')) {
    const at = part.indexOf(':')
    if (at === -1) continue
    const name = part.slice(0, at).trim().toLowerCase()
    const value = part.slice(at + 1).trim()
    if (name) out[name] = value
  }
  return out
}

/** Index of the `}` that closes the `{` at `open`. */
function closing(text: string, open: number): number {
  let depth = 0
  for (let i = open; i < text.length; i++) {
    if (text[i] === '{') depth++
    else if (text[i] === '}' && --depth === 0) return i
  }
  return text.length
}

/** Split a selector list at its top-level commas: `:where(a, button), .x` is two selectors, not four. */
export function splitSelectors(prelude: string): string[] {
  const out: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < prelude.length; i++) {
    const ch = prelude[i]
    if (ch === '(' || ch === '[') depth++
    else if (ch === ')' || ch === ']') depth--
    else if (ch === ',' && depth === 0) {
      out.push(prelude.slice(start, i))
      start = i + 1
    }
  }
  out.push(prelude.slice(start))
  return out.map((s) => s.trim()).filter(Boolean)
}

export function parseCss(css: string): Rule[] {
  const rules: Rule[] = []
  let order = 0
  const walk = (text: string, media: string | null) => {
    let i = 0
    while (i < text.length) {
      const open = text.indexOf('{', i)
      if (open === -1) break
      const prelude = text.slice(i, open).trim()
      const end = closing(text, open)
      const body = text.slice(open + 1, end)
      if (/^@media\b/i.test(prelude)) walk(body, prelude.replace(/^@media\s*/i, ''))
      else if (/^@(keyframes|font-face|supports|-webkit-keyframes)\b/i.test(prelude)) {
        // not part of the geometry the chrome tests resolve
      } else if (prelude) {
        rules.push({
          selectors: splitSelectors(prelude),
          decls: parseDecls(body),
          media,
          order: order++,
        })
      }
      i = end + 1
    }
  }
  walk(stripComments(css), null)
  return rules
}

/** Does an `@media` prelude hold in this environment? Only width / pointer / forced-colors / motion. */
export function mediaMatches(prelude: string | null, env: Env): boolean {
  if (prelude === null) return true
  return prelude.split(/\s*,\s*/).some((query) =>
    query.split(/\s+and\s+/i).every((raw) => {
      const feature = raw.trim().replace(/^\(|\)$/g, '')
      const [name, value] = feature.split(':').map((s) => s.trim())
      if (name === 'min-width') return env.width >= Number.parseFloat(value ?? '')
      if (name === 'max-width') return env.width <= Number.parseFloat(value ?? '')
      if (name === 'pointer') return (env.pointer ?? 'fine') === value
      if (name === 'forced-colors') return (env.forcedColors ?? false) === (value === 'active')
      if (name === 'prefers-reduced-motion') return (env.reducedMotion ?? false) === (value === 'reduce')
      return false
    }),
  )
}

const COMPOUND = /^((?:\.[\w-]+)+)(?::([\w-]+))?$/

/**
 * The winning declarations for an element carrying exactly `classes`, in `pseudo` state, at `env`.
 * Specificity here is the number of classes (+1 for the pseudo-class); later wins a tie.
 */
export function effective(
  rules: readonly Rule[],
  classes: readonly string[],
  env: Env,
  pseudo: string | null = null,
): Record<string, string> {
  const set = new Set(classes)
  const hits: { spec: number; order: number; decls: Readonly<Record<string, string>> }[] = []
  for (const rule of rules) {
    if (!mediaMatches(rule.media, env)) continue
    for (const selector of rule.selectors) {
      const m = COMPOUND.exec(selector)
      if (!m) continue
      const wanted = (m[1] ?? '').split('.').filter(Boolean)
      if ((m[2] ?? null) !== pseudo) continue
      if (!wanted.every((c) => set.has(c))) continue
      hits.push({ spec: wanted.length + (pseudo ? 1 : 0), order: rule.order, decls: rule.decls })
    }
  }
  hits.sort((a, b) => a.spec - b.spec || a.order - b.order)
  const out: Record<string, string> = {}
  for (const hit of hits) Object.assign(out, hit.decls)
  return out
}

const normalise = (selector: string) => selector.replace(/\s+/g, ' ').replace(/\s*([>+~,()])\s*/g, '$1').trim()

/**
 * The winning declarations of the rules written with EXACTLY this selector (whitespace-insensitive), at `env`.
 * For the selectors `effective()` cannot match against an element: an id (`#how-it-works`), a `:where()`
 * list, a descendant (`.brand-mark img`). A rule wrapped in a media block that does not hold at `env` is
 * ignored, so a rule that can never apply (an unreachable `@media (min-width: 99999px)`) reads as absent.
 * Later rules win; returns `{}` when no rule applies, which a test must treat as a failure.
 */
export function effectiveExact(rules: readonly Rule[], selector: string, env: Env): Record<string, string> {
  const wanted = normalise(selector)
  const out: Record<string, string> = {}
  for (const rule of rules) {
    if (!mediaMatches(rule.media, env)) continue
    if (rule.selectors.some((s) => normalise(s) === wanted)) Object.assign(out, rule.decls)
  }
  return out
}

/** `12px` -> 12; anything else -> NaN (so an arithmetic test fails instead of reading 0). */
export function px(value: string | undefined): number {
  const m = /^(-?\d+(?:\.\d+)?)px$/.exec((value ?? '').trim())
  return m ? Number.parseFloat(m[1] ?? '') : Number.NaN
}

/** CSS shorthand box values (`1`, `2`, `3` or `4` px values) -> [top, right, bottom, left]. */
export function box(value: string | undefined): [number, number, number, number] {
  const parts = (value ?? '').trim().split(/\s+/).map(px)
  const [a = Number.NaN, b = a, c = a, d = b] = parts
  return [a, b, c, d]
}

/** Custom properties declared on `:root`, with `@media` overrides applied for `env`. */
export function rootProperties(rules: readonly Rule[], env: Env): Record<string, string> {
  const out: Record<string, string> = {}
  for (const rule of rules) {
    if (!rule.selectors.includes(':root') || !mediaMatches(rule.media, env)) continue
    for (const [name, value] of Object.entries(rule.decls)) if (name.startsWith('--')) out[name] = value
  }
  return out
}

/** `var(--a)` / `calc(var(--a) - 1px)` / literals, resolved against `props`. NaN when it cannot. */
export function resolvePx(value: string, props: Readonly<Record<string, string>>): number {
  let v = value.trim()
  for (let i = 0; i < 6 && /var\(/.test(v); i++) {
    v = v.replace(/var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)/g, (_m, name: string) => props[name] ?? 'NaN')
  }
  const calc = /^calc\((.*)\)$/.exec(v)
  if (calc) {
    const expr = (calc[1] ?? '').replace(/(-?\d+(?:\.\d+)?)px/g, '$1')
    if (!/^[\d\s+\-*/().]+$/.test(expr)) return Number.NaN
    return Function(`"use strict"; return (${expr})`)() as number
  }
  return px(v)
}

// ---- colour ------------------------------------------------------------------------------

export function hexToRgb(hex: string): [number, number, number] {
  const m = /^#([0-9a-f]{6})$/i.exec(hex.trim())
  if (!m) throw new Error(`not a #rrggbb colour: ${hex}`)
  const n = Number.parseInt(m[1] ?? '', 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

export function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map((c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }) as [number, number, number]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}
