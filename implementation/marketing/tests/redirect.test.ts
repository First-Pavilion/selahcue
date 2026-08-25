/**
 * The `?next=` sanitiser.
 *
 * The guard bounces a signed-out visitor to `/signin?next=<where they were going>` and
 * sends them there once they sign in. Unchecked, that is a textbook open redirect, and a
 * good one: the victim signs in on the real SelahCue, with the real domain and the real
 * padlock, and lands wherever the attacker's link said. Nothing about the sign-in was
 * fake, which is exactly what makes it work.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'

import { safeNextPath } from '../src/lib/auth/redirect.ts'

const FALLBACK = '/account'

describe('safe same-site paths are honoured', () => {
  test('a plain path is returned unchanged', () => {
    // The positive control. Without it, every refusal below is satisfied just as well by
    // a function that returns the fallback unconditionally — which would be a silently
    // broken feature rather than a security control.
    assert.equal(safeNextPath('/account', FALLBACK), '/account')
    assert.equal(safeNextPath('/account/devices', FALLBACK), '/account/devices')
  })

  test('a query string and a hash survive', () => {
    assert.equal(safeNextPath('/account?tab=license', FALLBACK), '/account?tab=license')
    assert.equal(safeNextPath('/account#devices', FALLBACK), '/account#devices')
  })

  test('vue-router\'s repeated-parameter array takes the first entry', () => {
    assert.equal(safeNextPath(['/account', '/elsewhere'], FALLBACK), '/account')
  })
})

describe('anything that could leave this origin is refused', () => {
  test('a protocol-relative path is refused', () => {
    // THE case. `//evil.example/pay` starts with a slash and is a URL to another origin;
    // a naive `startsWith('/')` check passes it straight through.
    assert.equal(safeNextPath('//evil.example/pay', FALLBACK), FALLBACK)
    assert.equal(safeNextPath('///evil.example', FALLBACK), FALLBACK)
  })

  test('a backslash form of the same attack is refused', () => {
    // Several parsers normalise `\` to `/`, so `/\evil.example` is `//evil.example`.
    assert.equal(safeNextPath('/\\evil.example/pay', FALLBACK), FALLBACK)
    assert.equal(safeNextPath('/account\\@evil.example', FALLBACK), FALLBACK)
  })

  test('an absolute URL is refused, http and https alike', () => {
    for (const candidate of [
      'https://evil.example/pay',
      'http://evil.example/pay',
      'javascript:alert(1)',
      'data:text/html,<script>1</script>',
      'evil.example/pay',
    ]) {
      assert.equal(safeNextPath(candidate, FALLBACK), FALLBACK, `should have refused ${candidate}`)
    }
  })

  test('a control character is refused', () => {
    // Written as ESCAPES, never as literal bytes. A raw NUL in the source makes git
    // classify the whole file as binary, so it stops turning up in diffs, and a test
    // nobody can review is most of the way to a test nobody maintains. (This file was
    // committed that way once, which is how the rule was learned.)
    assert.equal(safeNextPath('/account\nSet-Cookie: x=1', FALLBACK), FALLBACK)
    assert.equal(safeNextPath('/account\u0000', FALLBACK), FALLBACK)
    assert.equal(safeNextPath('/account\u007f', FALLBACK), FALLBACK)
    assert.equal(safeNextPath('/acc\u0009ount', FALLBACK), FALLBACK)
  })
})

describe('non-values and loops', () => {
  test('missing, empty and non-string values fall back', () => {
    assert.equal(safeNextPath(undefined, FALLBACK), FALLBACK)
    assert.equal(safeNextPath(null, FALLBACK), FALLBACK)
    assert.equal(safeNextPath('', FALLBACK), FALLBACK)
    assert.equal(safeNextPath('   ', FALLBACK), FALLBACK)
    assert.equal(safeNextPath([], FALLBACK), FALLBACK)
  })

  test('the auth routes are refused as destinations', () => {
    // Not for safety — for termination. `/signin?next=/signin` signs someone in and
    // returns them to the sign-in page, where nothing tells them why they are back.
    for (const route of ['/signin', '/signup', '/forgot-password', '/verify', '/reset']) {
      assert.equal(safeNextPath(route, FALLBACK), FALLBACK, `${route} must not be a destination`)
      assert.equal(safeNextPath(`${route}?x=1`, FALLBACK), FALLBACK)
    }
  })

  test('a route that merely starts with an auth route name is still allowed', () => {
    // The refusal is on the whole path, not a prefix, so a legitimate future route is not
    // caught by accident.
    assert.equal(safeNextPath('/signing-up-guide', FALLBACK), '/signing-up-guide')
  })
})
