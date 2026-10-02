/**
 * Just enough `document` for the legal head handling: a head that holds meta elements, a
 * title, and the one selector LegalHead ever asks for. Shared by the LegalHead unit tests
 * and by the rendering tests that put it on `globalThis.document` so the REAL wiring from
 * LegalPage to the robots tag can be asserted without a browser.
 */
import assert from 'node:assert/strict'
import { NOINDEX_SELECTOR, type HeadHost } from '../../src/lib/legal/head.ts'

export function fakeHost(initialTitle = 'SelahCue') {
  interface FakeMeta {
    attrs: Map<string, string>
    parent: FakeMeta[] | null
    setAttribute(k: string, v: string): void
    remove(): void
  }
  const metas: FakeMeta[] = []
  const host = {
    title: initialTitle,
    head: {
      appendChild(node: FakeMeta) {
        node.parent = metas
        metas.push(node)
        return node
      },
    },
    createElement(): FakeMeta {
      const node: FakeMeta = {
        attrs: new Map(),
        parent: null,
        setAttribute(k, v) {
          this.attrs.set(k, v)
        },
        remove() {
          const at = metas.indexOf(this)
          if (at !== -1) metas.splice(at, 1)
        },
      }
      return node
    },
    querySelector(selector: string): FakeMeta | null {
      assert.equal(selector, NOINDEX_SELECTOR)
      return metas.find((m) => m.attrs.get('name') === 'robots' && m.attrs.has('data-legal-noindex')) ?? null
    },
  }
  return { host: host as unknown as HeadHost, metas, raw: host }
}
