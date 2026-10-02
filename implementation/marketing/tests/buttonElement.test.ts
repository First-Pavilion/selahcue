/**
 * Which element a UiButton renders. Two regressions live here: a router link losing its href
 * (round 1: unreachable by keyboard), and a DISABLED link staying keyboard-operable (round 2:
 * `aria-disabled` and `pointer-events: none` only stop the mouse and tell the screen reader).
 * The rule that closes both: a link that cannot be followed has NO href, and one that can has
 * its own.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { buttonElement } from '../src/lib/ui/buttonElement.ts'

describe('a live link keeps what makes it a link', () => {
  test('`to` renders a router-link carrying `to` and nothing that could override the router href', () => {
    const e = buttonElement({ to: '/contact' })
    assert.equal(e.tag, 'router-link')
    assert.deepEqual({ ...e.attrs }, { to: '/contact' })
    assert.ok(!('href' in e.attrs), 'an href key (even undefined) would override the router-computed one')
  })

  test('an object location works the same', () => {
    assert.deepEqual({ ...buttonElement({ to: { name: 'home' } }).attrs }, { to: { name: 'home' } })
  })

  test('`href` renders a plain anchor with that href', () => {
    const e = buttonElement({ href: 'https://example.com/x' })
    assert.equal(e.tag, 'a')
    assert.deepEqual({ ...e.attrs }, { href: 'https://example.com/x' })
  })
})

describe('a disabled or loading link cannot be tabbed to or followed', () => {
  for (const flag of ['disabled', 'loading'] as const) {
    test(`${flag}: to`, () => {
      const e = buttonElement({ to: '/contact', [flag]: true })
      assert.equal(e.tag, 'a', 'not a router-link: that would navigate on Enter')
      assert.ok(!('href' in e.attrs) && !('to' in e.attrs), 'no destination, so it is not focusable and Enter does nothing')
      assert.equal(e.attrs['aria-disabled'], 'true')
      assert.equal(e.attrs.role, 'link')
      assert.ok(!('tabindex' in e.attrs))
    })

    test(`${flag}: href`, () => {
      const e = buttonElement({ href: 'https://example.com', [flag]: true })
      assert.equal(e.tag, 'a')
      assert.ok(!('href' in e.attrs))
      assert.equal(e.attrs['aria-disabled'], 'true')
    })
  }

  test('false flags leave the link live (the control is not stuck)', () => {
    assert.equal(buttonElement({ to: '/x', disabled: false, loading: false }).tag, 'router-link')
    assert.equal(buttonElement({ href: 'https://e.x', disabled: false }).tag, 'a')
  })
})

describe('a native button is disabled by the browser', () => {
  test('plain, disabled and loading', () => {
    assert.deepEqual(buttonElement({}), { tag: 'button', attrs: { disabled: false } })
    assert.deepEqual(buttonElement({ disabled: true }), { tag: 'button', attrs: { disabled: true } })
    assert.deepEqual(buttonElement({ loading: true }), { tag: 'button', attrs: { disabled: true } })
  })
})

describe('UiButton uses it, and its public props are unchanged', () => {
  const src = readFileSync(fileURLToPath(new URL('../src/components/UiButton.vue', import.meta.url)), 'utf8')

  test('the template binds the element and attributes the function chose', () => {
    assert.match(src, /import \{ buttonElement \} from '@\/lib\/ui\/buttonElement\.ts'/)
    assert.match(src, /:is="element\.tag"/)
    assert.match(src, /v-bind="element\.attrs"/)
    assert.ok(!/:href="/.test(src) && !/:to="/.test(src), 'UiButton must not bind :href / :to itself again')
  })

  test('the public props are exactly the ones callers already use', () => {
    const block = /defineProps\(\{([\s\S]*?)\n\}\)/.exec(src)?.[1] ?? ''
    const keys = [...block.matchAll(/^ {2}(\w+): \{/gm)].map((m) => m[1])
    assert.deepEqual(keys, ['variant', 'size', 'to', 'href', 'disabled', 'loading'])
  })
})
