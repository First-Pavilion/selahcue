/**
 * Reading the `?token=` off a landing URL, and the email check that guards the
 * request-a-fresh-link forms.
 */
import assert from 'node:assert/strict'
import { getEventListeners } from 'node:events'
import test, { describe } from 'node:test'

import { createLandingTokenHandoff, type LandingRouterHooks } from '../src/lib/auth/landingTokenHandoff.ts'
import { isMissingToken, readTokenFromSearch, readTokenParam } from '../src/lib/auth/tokenParam.ts'
import { EMAIL_INVALID, EMAIL_REQUIRED, validateEmail } from '../src/lib/auth/emailPolicy.ts'

describe('readTokenParam', () => {
  test('reads a plain token', () => {
    assert.equal(readTokenParam('SC-EMAILVERIFY-abc'), 'SC-EMAILVERIFY-abc')
  })

  test('trims, matching the API\'s own (raw_token or "").strip()', () => {
    // Mail clients and copy-paste routinely add whitespace around a pasted link.
    assert.equal(readTokenParam('  SC-EMAILVERIFY-abc \n'), 'SC-EMAILVERIFY-abc')
  })

  test('takes the first value when the query repeats ?token=', () => {
    // vue-router hands back an array for `?token=a&token=b`. Stringifying it would send
    // "a,b" to the API — garbage that fails for a reason nobody could diagnose.
    assert.equal(readTokenParam(['SC-A', 'SC-B']), 'SC-A')
  })

  test('absent, empty, null and whitespace-only all read as no token', () => {
    for (const value of [undefined, null, '', '   ', [], [null]]) {
      assert.equal(readTokenParam(value as never), '', `expected '' for ${JSON.stringify(value)}`)
    }
  })
})

describe('isMissingToken', () => {
  /**
   * The one token failure the client can distinguish on its own — which is why it gets
   * its own state (V6) instead of the merged failure state. Showing a red "this link
   * didn't work" to someone who simply bookmarked /verify would be a lie.
   */
  test('true for a bookmark or a stripped query', () => {
    assert.equal(isMissingToken(undefined), true)
    assert.equal(isMissingToken(''), true)
    assert.equal(isMissingToken('   '), true)
  })

  test('false when a token is present', () => {
    assert.equal(isMissingToken('SC-PASSWORDRESET-abc'), false)
  })
})

describe('readTokenFromSearch', () => {
  test('recognizes encoded names, keeps the first value and splits only at the first equals', () => {
    assert.equal(readTokenFromSearch('?tokenized=no&%74oken=+A%2BB=C+&token=ignored'), 'A+B=C')
    assert.equal(readTokenFromSearch('?token=A+B'), 'A B')
  })

  test('distinguishes a missing field from every kind of empty first value', () => {
    for (const search of ['', '?Token=ignored&next=token%3Dx', '?%74oken%ZZ=ignored']) {
      assert.equal(readTokenFromSearch(search), undefined)
    }
    for (const search of ['?token&token=ignored', '?token=&token=ignored', '?token=%20+&token=ignored']) {
      assert.equal(readTokenFromSearch(search), '')
    }
  })

  test('keeps the whole plus-normalized segment when percent decoding fails', () => {
    assert.equal(readTokenFromSearch('?token=+A%20%ZZ+B+'), 'A%20%ZZ B')
    assert.equal(readTokenFromSearch('?token=%ED%A0%80'), '%ED%A0%80')
  })
})

function setupLanding(href: string, state: unknown = null) {
  const location = new URL(href, 'https://fixture.example')
  const replacements: Array<{ state: unknown; url: string | undefined }> = []
  const history = {
    state,
    replaceState(nextState: unknown, _title: string, url?: string) {
      replacements.push({ state: nextState, url })
      this.state = nextState
      if (url !== undefined) location.href = new URL(url, location).href
    },
  }
  const page = new EventTarget()
  const handoff = createLandingTokenHandoff()
  const start = { name: undefined, fullPath: '/' }
  const before = new Set<Parameters<LandingRouterHooks['beforeEach']>[0]>()
  const after = new Set<Parameters<LandingRouterHooks['afterEach']>[0]>()
  const errors = new Set<Parameters<LandingRouterHooks['onError']>[0]>()
  function register<Callback>(callbacks: Set<Callback>) {
    return (callback: Callback) => {
      callbacks.add(callback)
      return () => { callbacks.delete(callback) }
    }
  }
  const router = { beforeEach: register(before), afterEach: register(after), onError: register(errors) }
  function prepare() {
    handoff.prepare(location, history, page)
    handoff.watchInitialNavigation(router, start)
  }
  function assertDisposed() {
    assert.equal(getEventListeners(page, 'pagehide').length, 0)
    assert.deepEqual([before.size, after.size, errors.size], [0, 0, 0])
  }
  return { location, history, replacements, page, handoff, start, before, after, errors, prepare, assertDisposed }
}

describe('initial landing history', () => {
  test('replaces the address and classic history paths while preserving other metadata', () => {
    const state = {
      back: '/VeRiFy/?%74oken#back',
      current: '/ReSeT/?token=synthetic-current&next=drop#current',
      forward: '/reset?token=&token=synthetic-forward#forward',
      position: 3,
      scroll: { left: 1, top: 2 },
      extra: '/verify?token=unrelated-metadata#keep',
    }
    const fixture = setupLanding('/ReSeT/?token=synthetic-input&next=drop#drop', state)

    fixture.prepare()

    assert.equal(fixture.location.href, 'https://fixture.example/ReSeT/')
    assert.deepEqual(fixture.replacements, [{
      state: { ...state, back: '/VeRiFy/', current: '/ReSeT/', forward: '/reset' },
      url: '/ReSeT/',
    }])
    assert.equal(state.back, '/VeRiFy/?%74oken#back')
    assert.equal(state.current, '/ReSeT/?token=synthetic-current&next=drop#current')
    assert.equal(state.forward, '/reset?token=&token=synthetic-forward#forward')
  })

  test('leaves non-landing and tokenless URLs and unrelated history paths intact', () => {
    const state = {
      back: '//other.example/verify?token=other#keep',
      current: '/reset?next=help#keep',
      forward: '/verify/child?token=subpath#keep',
    }
    for (const href of [
      '/reset?next=help#keep',
      '/signin?token=unrelated#keep',
      '/reset/child?token=unrelated#keep',
      '/verify//?token=unrelated#keep',
    ]) {
      const fixture = setupLanding(href, state)
      fixture.prepare()
      assert.equal(fixture.location.href, 'https://fixture.example' + href)
      assert.deepEqual(fixture.replacements, [])
      fixture.assertDisposed()
    }
  })

  test('cleans an old history field on a tokenless landing and preserves the current URL', () => {
    const fixture = setupLanding('/verify?__scenario=missing#keep', { back: '/reset?token=old#drop' })
    fixture.prepare()
    assert.deepEqual(fixture.replacements, [{ state: { back: '/reset' }, url: undefined }])
    assert.equal(fixture.location.href, 'https://fixture.example/verify?__scenario=missing#keep')
    fixture.assertDisposed()
  })

  test('scrubs a bare or empty first token without preparing a handoff', () => {
    for (const field of ['token', 'token=', 'token=%20+']) {
      const fixture = setupLanding('/verify?' + field + '&token=ignored#drop')
      fixture.prepare()
      assert.deepEqual(fixture.replacements, [{ state: null, url: '/verify' }])
      fixture.assertDisposed()
    }
  })

  test('refuses bootstrap with a fixed message when history replacement throws', () => {
    const fixture = setupLanding('/verify?token=stale')
    fixture.prepare()
    fixture.history.replaceState = () => { throw new Error('/reset?token=synthetic-refused') }

    assert.throws(
      () => fixture.handoff.prepare(new URL('https://fixture.example/reset?token=synthetic-refused'),
        fixture.history, fixture.page),
      new Error('Unable to sanitize the auth landing URL'),
    )
    fixture.assertDisposed()
    assert.equal(fixture.handoff.take({ name: 'reset', fullPath: '/reset' }), '')
  })
})

describe('initial landing token handoff', () => {
  const destination = { name: 'verify', fullPath: '/VeRiFy/' }

  function preparedLanding() {
    const fixture = setupLanding('/VeRiFy/?token=synthetic-input')
    fixture.prepare()
    return fixture
  }

  test('a successful initial navigation transfers only once to the actual route object', () => {
    const fixture = preparedLanding()
    assert.equal(fixture.handoff.take(destination), '')
    for (const guard of fixture.before) guard(destination, fixture.start)
    for (const hook of fixture.after) hook(destination, fixture.start, undefined)
    assert.equal(fixture.handoff.take({ ...destination }), '')
    assert.equal(fixture.handoff.take(destination), 'synthetic-input')
    assert.equal(fixture.handoff.take(destination), '')
    fixture.assertDisposed()
  })

  test('a different route name, full path or start location discards the capture', () => {
    const mismatches = [
      [{ ...destination, name: 'reset' }, undefined],
      [{ ...destination, fullPath: '/VeRiFy/?next=help' }, undefined],
      [destination, { name: undefined, fullPath: '/' }],
    ] as const
    for (const [to, from] of mismatches) {
      const fixture = preparedLanding()
      for (const guard of fixture.before) guard(to, from ?? fixture.start)
      for (const guard of fixture.before) guard(destination, fixture.start)
      assert.equal(fixture.handoff.take(destination), '')
      fixture.assertDisposed()
    }
  })

  test('an attempted re-entry to the same URL cannot claim the initial capture', () => {
    const fixture = preparedLanding()
    const later = { ...destination }
    for (const guard of fixture.before) guard(destination, fixture.start)
    for (const guard of fixture.before) guard(later, fixture.start)
    assert.equal(fixture.handoff.take(later), '')
    assert.equal(fixture.handoff.take(destination), '')
    fixture.assertDisposed()
  })

  test('a late failure for an unrelated route cannot discard the matching capture', () => {
    const fixture = preparedLanding()
    for (const guard of fixture.before) guard(destination, fixture.start)
    for (const hook of fixture.after) hook({ ...destination }, fixture.start, new Error('other navigation'))
    for (const hook of fixture.errors) hook(new Error('other navigation'), { ...destination }, fixture.start)
    assert.equal(fixture.handoff.take(destination), 'synthetic-input')
    fixture.assertDisposed()
  })

  test('a duplicate attempt after commitment discards before the view can take the capture', () => {
    const fixture = preparedLanding()
    for (const guard of fixture.before) guard(destination, fixture.start)
    for (const hook of fixture.after) hook(destination, fixture.start, undefined)
    // Router reports a duplicate without reaching beforeEach.
    for (const hook of fixture.after) hook({ ...destination }, destination, new Error('duplicate navigation'))
    assert.equal(fixture.handoff.take(destination), '')
    fixture.assertDisposed()
  })

  test('cancellation, a navigation error or pagehide each permanently discard the capture', () => {
    for (const reason of ['canceled', 'error', 'pagehide']) {
      const fixture = preparedLanding()
      for (const guard of fixture.before) guard(destination, fixture.start)
      if (reason === 'canceled') {
        for (const hook of fixture.after) hook(destination, fixture.start, new Error('navigation canceled'))
      } else if (reason === 'error') {
        for (const hook of fixture.errors) hook(new Error('lazy module unavailable'), destination, fixture.start)
      } else {
        assert.equal(getEventListeners(fixture.page, 'pagehide').length, 1)
        assert.equal(fixture.page.dispatchEvent(new Event('pagehide', { cancelable: true })), true)
        fixture.page.dispatchEvent(new Event('pageshow'))
      }
      assert.equal(fixture.handoff.take(destination), '')
      fixture.assertDisposed()
    }
  })
})

describe('validateEmail', () => {
  test('an empty address asks for one', () => {
    assert.equal(validateEmail(''), EMAIL_REQUIRED)
    assert.equal(validateEmail('   '), EMAIL_REQUIRED)
  })

  test('obvious nonsense is caught on the field, not by the API', () => {
    // `_require_valid_email` raises the SAME VALIDATION_FAILED as every token failure, so
    // an unchecked malformed address produces an error the page cannot attribute.
    assert.equal(validateEmail('not-an-email'), EMAIL_INVALID)
    assert.equal(validateEmail('missing@domain'), EMAIL_INVALID)
  })

  test('real-world addresses are accepted — the check must not lock people out', () => {
    for (const address of [
      'pastor@church.org',
      'first.last+tag@yourchurch.co.uk',
      'a@b.io',
      'admin@grace-community.church',
    ]) {
      assert.equal(validateEmail(address), '', `${address} should be accepted`)
    }
  })

  test('surrounding whitespace is tolerated', () => {
    assert.equal(validateEmail('  pastor@church.org  '), '')
  })
})
