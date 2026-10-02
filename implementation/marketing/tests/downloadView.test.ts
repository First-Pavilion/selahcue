/**
 * The Download page may not show a control that looks clickable and does nothing.
 *
 * 17tnw2b0q9j. `/download` shipped two store badges as plain boxes and two download
 * buttons with no link and no handler; nothing in the build noticed, because a button that
 * does nothing is valid markup and valid TypeScript. They are disabled now, with visible
 * text that says why. This file is the control that stops them quietly turning back into
 * dead buttons — or the explanation being orphaned — without anyone deciding to.
 *
 * It parses the real `DownloadView.vue` with Vue's own SFC compiler rather than
 * pattern-matching its text: a template is full of apostrophes, line wraps and attribute
 * orderings that make a regex a guess, and the compiler's AST is exactly what ships.
 *
 * What it asserts about the page:
 *
 *   1. Every button is either disabled or has a click handler. A "button" here is a
 *      native `<button>`, or a `<UiButton>` with no `to`/`href` (with one it renders a
 *      link, which is an action on its own).
 *   2. Every disabled control also says so to assistive tech with `aria-disabled="true"`.
 *   3. Every `aria-describedby` points at an `id` that exists in the template and has
 *      visible text — the explanation is the point of the disabled state, so a dangling
 *      reference is the same bug as no explanation.
 *   4. No fake link: no `href` of `""`, `#` or `javascript:`, and no `<a>` without one.
 *
 * The positive controls at the bottom run the same checks over small templates that are
 * known to be wrong, so a predicate that quietly accepted everything fails here instead of
 * leaving the page checks above passing for the wrong reason.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'
import { readFileSync } from 'node:fs'
import { parse } from 'vue/compiler-sfc'

/** Just the parts of Vue's template AST this file reads; avoids a transitive type import. */
interface AttrProp {
  type: 6
  name: string
  value?: { content: string }
}
interface DirectiveProp {
  type: 7
  name: string
  arg?: { content: string }
}
interface ElementNode {
  type: 1
  tag: string
  props: Array<AttrProp | DirectiveProp>
  children: Node[]
}
interface TextNode {
  type: 2 | 5
  content?: unknown
}
type Node = ElementNode | TextNode | { type: number; children?: Node[] }

function elementsOf(sfc: string): ElementNode[] {
  const { descriptor, errors } = parse(sfc, { filename: 'fixture.vue' })
  assert.equal(errors.length, 0, `the SFC did not parse: ${errors.map(String).join('; ')}`)
  const root = descriptor.template?.ast as { children: Node[] } | undefined
  assert.ok(root, 'the SFC has no <template>')
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

/** A static attribute, or a `:name`/`v-bind:name` binding, with this name. */
function prop(el: ElementNode, name: string): AttrProp | DirectiveProp | undefined {
  return el.props.find((p) =>
    p.type === 6 ? p.name === name : p.name === 'bind' && p.arg?.content === name,
  )
}

function staticValue(p: AttrProp | DirectiveProp | undefined): string | undefined {
  return p && p.type === 6 ? (p.value?.content ?? '') : undefined
}

function hasClickHandler(el: ElementNode): boolean {
  return el.props.some((p) => p.type === 7 && p.name === 'on' && p.arg?.content === 'click')
}

function visibleText(el: ElementNode): string {
  let text = ''
  const walk = (node: Node): void => {
    if (node.type === 2 || node.type === 5) text += String((node as TextNode).content ?? '')
    for (const child of (node as { children?: Node[] }).children ?? []) {
      if (typeof child === 'object') walk(child)
    }
  }
  for (const child of el.children) walk(child)
  return text.trim()
}

const isUiButton = (tag: string): boolean => tag === 'UiButton' || tag === 'ui-button'

/** Buttons that would do something on click if they were enabled; links are not buttons. */
function buttonsOf(els: ElementNode[]): ElementNode[] {
  return els.filter(
    (el) =>
      el.tag === 'button' ||
      (isUiButton(el.tag) && !prop(el, 'to') && !prop(el, 'href')),
  )
}

/** Every way the template breaks the rules above, as readable sentences. Empty when clean. */
function violations(sfc: string): string[] {
  const els = elementsOf(sfc)
  const out: string[] = []
  const label = (el: ElementNode): string => `<${el.tag}> "${visibleText(el) || '(no text)'}"`

  for (const el of buttonsOf(els)) {
    const disabled = prop(el, 'disabled')
    if (!disabled && !hasClickHandler(el)) {
      out.push(`${label(el)} is neither disabled nor wired to a click handler`)
    }
    if (disabled) {
      const aria = prop(el, 'aria-disabled')
      if (!aria) out.push(`${label(el)} is disabled but has no aria-disabled`)
      else if (staticValue(aria) !== undefined && staticValue(aria) !== 'true') {
        out.push(`${label(el)} has aria-disabled="${staticValue(aria)}" while disabled`)
      }
    }
  }

  const ids = new Map<string, ElementNode>()
  for (const el of els) {
    const id = staticValue(prop(el, 'id'))
    if (id) ids.set(id, el)
  }
  for (const el of els) {
    const described = staticValue(prop(el, 'aria-describedby'))
    if (described === undefined) continue
    for (const id of described.split(/\s+/).filter(Boolean)) {
      const target = ids.get(id)
      if (!target) out.push(`${label(el)} is described by #${id}, which is not in the template`)
      else if (!visibleText(target)) out.push(`#${id} describes ${label(el)} but has no text`)
    }
  }

  for (const el of els) {
    const href = prop(el, 'href')
    const value = staticValue(href)
    if (value !== undefined && (value === '' || value === '#' || /^\s*javascript:/i.test(value))) {
      out.push(`${label(el)} has a fake href="${value}"`)
    }
    if (el.tag === 'a' && !href && !hasClickHandler(el)) {
      out.push(`${label(el)} is an <a> with no href`)
    }
  }
  return out
}

const DOWNLOAD_VIEW = readFileSync(
  new URL('../src/views/DownloadView.vue', import.meta.url),
  'utf8',
)

describe('the Download page shows no control that looks clickable and does nothing', () => {
  test('the page has buttons to check, so the assertions below cannot pass vacuously', () => {
    assert.ok(buttonsOf(elementsOf(DOWNLOAD_VIEW)).length > 0, 'found no buttons on /download')
  })

  test('every button is disabled or has a click handler, and says so to assistive tech', () => {
    assert.deepEqual(violations(DOWNLOAD_VIEW), [])
  })
})

describe('the checks themselves reject what they are meant to reject', () => {
  const wrap = (inner: string): string => `<template><div>${inner}</div></template>`

  test('a bare button with no handler is flagged', () => {
    assert.match(violations(wrap('<button type="button">App Store</button>')).join('\n'), /neither disabled/)
  })

  test('a bare UiButton with no `to`, `href` or handler is flagged', () => {
    assert.match(violations(wrap('<UiButton variant="primary">Download</UiButton>')).join('\n'), /neither disabled/)
  })

  test('a disabled button with no aria-disabled is flagged', () => {
    assert.match(violations(wrap('<button disabled>App Store</button>')).join('\n'), /no aria-disabled/)
  })

  test('aria-describedby pointing at a missing id is flagged', () => {
    const bad = wrap('<button disabled aria-disabled="true" aria-describedby="nope">A</button><p id="here">x</p>')
    assert.match(violations(bad).join('\n'), /#nope, which is not in the template/)
  })

  test('aria-describedby pointing at an empty element is flagged', () => {
    const bad = wrap('<button disabled aria-disabled="true" aria-describedby="n">A</button><p id="n"></p>')
    assert.match(violations(bad).join('\n'), /has no text/)
  })

  test('a fake href, and an <a> with no href, are flagged', () => {
    assert.match(violations(wrap('<a href="#">Download</a>')).join('\n'), /fake href/)
    assert.match(violations(wrap('<a>Download</a>')).join('\n'), /no href/)
  })

  test('honest controls are accepted', () => {
    const good = wrap(
      '<button disabled aria-disabled="true" aria-describedby="n">A</button><p id="n">Not yet</p>' +
        '<button @click="go">B</button>' +
        '<UiButton to="/pricing">C</UiButton><UiButton href="https://example.com">D</UiButton>' +
        '<a href="/features">E</a>',
    )
    assert.deepEqual(violations(good), [])
  })
})
