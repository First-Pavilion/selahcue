/**
 * Read a single-file component the way Vue's own compiler does, so a test asserts on what
 * ships (the template AST, the style blocks) and not on a regex over text.
 *
 * Used by `tests/secondaryPages.test.ts` (ClickUp 17tnw2b2cez).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'

import { parse } from 'vue/compiler-sfc'

import { SRC } from './viewRender.ts'

export interface AttrProp {
  type: 6
  name: string
  value?: { content: string }
}
export interface DirectiveProp {
  type: 7
  name: string
  arg?: { content: string }
  exp?: { content: string }
}
export interface ElementNode {
  type: 1
  tag: string
  props: Array<AttrProp | DirectiveProp>
  children: unknown[]
}

export const readSrc = (rel: string): string => readFileSync(path.join(SRC, rel), 'utf8')

export function descriptorOf(source: string, filename = 'fixture.vue') {
  const { descriptor, errors } = parse(source, { filename })
  assert.equal(errors.length, 0, `${filename} did not parse: ${errors.map(String).join('; ')}`)
  return descriptor
}

/** Every element of the template, in document order. */
export function elementsOf(source: string, filename = 'fixture.vue'): ElementNode[] {
  const root = descriptorOf(source, filename).template?.ast as { children: unknown[] } | undefined
  assert.ok(root, `${filename} has no template`)
  const found: ElementNode[] = []
  const walk = (node: unknown): void => {
    const n = node as { type?: number; children?: unknown[] }
    if (n && typeof n === 'object') {
      if (n.type === 1) found.push(node as ElementNode)
      for (const child of n.children ?? []) walk(child)
    }
  }
  for (const child of root.children) walk(child)
  return found
}

/** A static attribute, or a `:name` / `v-bind:name` binding, with this name. */
export function prop(el: ElementNode, name: string): AttrProp | DirectiveProp | undefined {
  return el.props.find((p) => (p.type === 6 ? p.name === name : p.name === 'bind' && p.arg?.content === name))
}

/** The value of a static attribute, or of a bound string literal such as `:variant="'gradient'"`. */
export function valueOf(p: AttrProp | DirectiveProp | undefined): string | undefined {
  if (!p) return undefined
  if (p.type === 6) return p.value?.content ?? ''
  const exp = p.exp?.content?.trim() ?? ''
  const quoted = /^(['"])(.*)\1$/.exec(exp)
  return quoted ? quoted[2] : exp
}

/** The concatenated `<style>` blocks of the component. */
export function styleOf(source: string, filename = 'fixture.vue'): string {
  return descriptorOf(source, filename)
    .styles.map((s) => s.content)
    .join('\n')
}
