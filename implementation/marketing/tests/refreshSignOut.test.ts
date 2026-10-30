/** ClickUp 17tnw2b2ka9: exercise the real store/API seam, including response-cookie ordering. */
import assert from 'node:assert/strict'
import test from 'node:test'

import { ApiError } from '../src/lib/api/graphql.ts'
import {
  confirmSession,
  isProbablySignedIn,
  refreshIfExpiringSoon,
  sessionHint,
  signIn,
  signOut,
} from '../src/lib/auth/sessionStore.ts'

const BOUND = { timeout: 5_000 }
const DAY = 86_400_000

function deferred() {
  let resolve!: () => void
  const promise = new Promise<void>((done) => { resolve = done })
  return { promise, resolve }
}

const settle = () => new Promise<void>((resolve) => setImmediate(resolve))
const json = (body: unknown) => new Response(JSON.stringify(body), {
  headers: { 'Content-Type': 'application/json' },
})
const unauthenticated = () => json({ errors: [{ extensions: { code: 'UNAUTHENTICATED' } }] })

interface FixtureOptions {
  days?: number
  holdLogout?: boolean
  refreshFailure?: 'network' | 'unreadable'
  failFirstLogout?: boolean
}

/**
 * Scripted transport, not a claim of a native/browser cookie integration test. It models the
 * inspected services.py/account_schema.py contract: refresh revokes the presented token and
 * creates a successor BEFORE its response; the browser installs the response cookie before
 * fetch returns; Logout authenticates the cookie captured when that request was sent. A
 * failed authenticate returns UNAUTHENTICATED without reaching response.delete_cookie.
 * The store never sees or reads these test-only cookie values.
 */
function fixture(config: FixtureOptions = {}) {
  const now = Date.now()
  const expiresAt = new Date(now + (config.days ?? 3) * DAY).toISOString()
  const rotatedExpiry = new Date(now + 30 * DAY).toISOString()
  const refreshReply = deferred()
  const logoutReply = deferred()
  const refreshStarted = deferred()
  const logoutStarted = deferred()
  const active = new Set<string>()
  let cookie: string | null = null
  let rotations = 0
  const requests: { operation: string; cookie: string | null }[] = []
  const fetchImpl: typeof fetch = async (url, init) => {
    assert.equal(String(url), '/graphql/account')
    assert.equal(init?.credentials, 'same-origin')
    const body = JSON.parse(String(init?.body)) as { query: string }
    const operation = /\b(?:mutation|query)\s+(\w+)/.exec(body.query)?.[1]
    assert.ok(operation, 'real account document has an operation name')
    const presented = cookie // Browser credentials are captured at request dispatch, not later.
    requests.push({ operation, cookie: presented })
    if (operation === 'Login') {
      cookie = 'signed-in-cookie'
      active.add(cookie)
      return json({ data: { login: { role: 'ADMIN', orgId: 'org-race-test', expiresAt } } })
    }
    if (operation === 'RefreshSession') {
      refreshStarted.resolve()
      if (config.refreshFailure === 'network') {
        await refreshReply.promise
        throw new TypeError('Failed to fetch')
      }
      if (presented === null || !active.has(presented)) return unauthenticated()
      active.delete(presented)
      const successor = `rotated-cookie-${++rotations}`
      active.add(successor)
      await refreshReply.promise
      cookie = successor // HttpOnly Set-Cookie applies even if later JSON parsing fails.
      if (config.refreshFailure === 'unreadable') {
        return new Response('not JSON', { headers: { 'Content-Type': 'application/json' } })
      }
      return json({ data: { refreshSession: { expiresAt: rotatedExpiry } } })
    }
    if (operation === 'Logout') {
      logoutStarted.resolve()
      if (config.holdLogout) await logoutReply.promise
      const attempts = requests.filter((r) => r.operation === 'Logout').length
      if (config.failFirstLogout && attempts === 1) throw new TypeError('Failed to fetch')
      if (presented === null || !active.has(presented)) return unauthenticated()
      active.delete(presented)
      cookie = null
      return json({ data: { logout: { revoked: true } } })
    }
    if (operation === 'AccountViewer') {
      return cookie !== null && active.has(cookie)
        ? json({ data: { accountViewer: { surface: 'account', actorId: 'owner', orgId: 'org-race-test', role: 'ADMIN' } } })
        : unauthenticated()
    }
    throw new Error(`unhandled account operation ${operation}`)
  }
  const options = { fetchImpl }
  const calls = (operation: string) => requests.filter((r) => r.operation === operation)
  return {
    now, expiresAt, rotatedExpiry, options, calls, refreshReply, logoutReply, refreshStarted, logoutStarted,
    cookieHasLiveSession: () => cookie !== null && active.has(cookie),
    expireSession: () => active.clear(),
    seed: () => signIn('owner@example.org', 'a-test-passphrase', options),
    async cleanup(work: Promise<unknown>[] = []) {
      refreshReply.resolve()
      logoutReply.resolve()
      await Promise.allSettled(work)
      await signOut(options).catch(() => {})
    },
  }
}

test('held refresh then sign-out leaves no live rotated cookie and no resurrected hint', BOUND, async () => {
  const f = fixture()
  await f.seed()
  const refresh = refreshIfExpiringSoon(f.now, f.options)
  await f.refreshStarted.promise
  const logout = signOut(f.options)
  try {
    await settle()
    const earlyLogouts = f.calls('Logout').length
    f.refreshReply.resolve()
    await Promise.all([refresh, logout])
    assert.equal(f.cookieHasLiveSession(), false, 'hint-only suppression cannot hide a live rotated cookie')
    assert.equal(earlyLogouts, 0, 'logout waits until the refresh response installs its cookie')
    assert.deepEqual(f.calls('Logout').map((r) => r.cookie), ['rotated-cookie-1'])
    assert.equal(sessionHint.value, null, 'late refresh must not restore the signed-out hint')
    assert.equal(isProbablySignedIn.value, false)
    assert.equal(await confirmSession(f.options), 'ended', 'the real viewer seam confirms no live session')
  } finally {
    await f.cleanup([refresh, logout])
  }
})

test('logout is not dispatched while refresh is held before response cookies arrive', BOUND, async () => {
  const f = fixture()
  await f.seed()
  const refresh = refreshIfExpiringSoon(f.now, f.options)
  await f.refreshStarted.promise
  const logout = signOut(f.options)
  try {
    await settle()
    assert.equal(f.calls('Logout').length, 0, 'old-cookie UNAUTHENTICATED is not sign-out success during refresh')
    assert.notEqual(sessionHint.value, null, 'waiting for rotation must not claim the still-pending logout succeeded')
  } finally {
    await f.cleanup([refresh, logout])
  }
})

test('concurrent opportunistic refresh callers share one rotation', BOUND, async () => {
  const f = fixture()
  await f.seed()
  const first = refreshIfExpiringSoon(f.now, f.options)
  await f.refreshStarted.promise
  const second = refreshIfExpiringSoon(f.now, f.options)
  try {
    await settle()
    assert.equal(f.calls('RefreshSession').length, 1, 'one in-flight rotation, not two old-cookie requests')
    f.refreshReply.resolve()
    assert.deepEqual(await Promise.all([first, second]), [true, true])
    assert.equal(sessionHint.value?.expiresAt, f.rotatedExpiry, 'an ordinary refresh still remembers its new expiry')
  } finally {
    await f.cleanup([first, second])
  }
})

test('a pending logout closes admission to new refresh requests', BOUND, async () => {
  const f = fixture({ holdLogout: true })
  await f.seed()
  const logout = signOut(f.options)
  await f.logoutStarted.promise
  const refresh = refreshIfExpiringSoon(f.now, f.options)
  try {
    await settle()
    assert.equal(f.calls('RefreshSession').length, 0, 'a route check cannot rotate underneath a pending logout')
    assert.equal(await refresh, false)
    f.logoutReply.resolve()
    await logout
    assert.equal(f.cookieHasLiveSession(), false)
    assert.equal(sessionHint.value, null)
  } finally {
    await f.cleanup([refresh, logout])
  }
})

for (const refreshFailure of ['network', 'unreadable'] as const) {
  test(`refresh ${refreshFailure} failure still settles before logout and cannot leave a live cookie`, BOUND, async () => {
    const f = fixture({ refreshFailure })
    await f.seed()
    const refresh = refreshIfExpiringSoon(f.now, f.options)
    await f.refreshStarted.promise
    const logout = signOut(f.options)
    try {
      await settle()
      const earlyLogouts = f.calls('Logout').length
      f.refreshReply.resolve()
      assert.equal(await refresh, false)
      await logout
      assert.equal(earlyLogouts, 0, 'a failed/unknown refresh result does not bypass the rotation barrier')
      assert.equal(f.cookieHasLiveSession(), false, 'a Set-Cookie received before a JSON failure must also be revoked')
      assert.equal(sessionHint.value, null)
    } finally {
      await f.cleanup([refresh, logout])
    }
  })
}

test('refresh completion during a failed logout does not rewrite hints and logout remains retryable', BOUND, async () => {
  const f = fixture({ failFirstLogout: true, holdLogout: true })
  await f.seed()
  const refresh = refreshIfExpiringSoon(f.now, f.options)
  await f.refreshStarted.promise
  const logoutResult = signOut(f.options).then(() => null, (error: unknown) => error)
  try {
    f.refreshReply.resolve()
    await refresh
    await f.logoutStarted.promise
    assert.equal(sessionHint.value?.expiresAt, f.expiresAt, 'finishing refresh does not rewrite a hint after sign-out began')
    f.logoutReply.resolve()
    const error = await logoutResult
    assert.ok(error instanceof ApiError)
    assert.equal(error.code, 'NETWORK')
    assert.equal(f.cookieHasLiveSession(), true, 'failed revocation leaves the real session live')
    assert.notEqual(sessionHint.value, null, 'failure cannot paint the user signed out')
    assert.equal(isProbablySignedIn.value, true)
    await signOut(f.options)
    assert.deepEqual(f.calls('Logout').map((r) => r.cookie), ['rotated-cookie-1', 'rotated-cookie-1'])
    assert.equal(f.cookieHasLiveSession(), false)
    assert.equal(sessionHint.value, null)
  } finally {
    await f.cleanup([refresh, logoutResult])
  }
})

test('a session with weeks left does not refresh and signs out directly', BOUND, async () => {
  const f = fixture({ days: 30 })
  await f.seed()
  try {
    assert.equal(await refreshIfExpiringSoon(f.now, f.options), false)
    assert.equal(f.calls('RefreshSession').length, 0, 'threshold positive control: do not rotate on every route')
    await signOut(f.options)
    assert.deepEqual(f.calls('Logout').map((r) => r.cookie), ['signed-in-cookie'])
    assert.equal(f.cookieHasLiveSession(), false)
    assert.equal(sessionHint.value, null)
  } finally {
    await f.cleanup()
  }
})

test('UNAUTHENTICATED without any refresh still means the session already ended', BOUND, async () => {
  const f = fixture()
  await f.seed()
  f.expireSession()
  try {
    await signOut(f.options)
    assert.equal(f.calls('RefreshSession').length, 0)
    assert.equal(f.cookieHasLiveSession(), false)
    assert.equal(sessionHint.value, null)
    assert.equal(isProbablySignedIn.value, false)
  } finally {
    await f.cleanup()
  }
})
