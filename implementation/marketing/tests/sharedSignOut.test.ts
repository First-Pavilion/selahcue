/** Runtime composition regression for ClickUp 17tnw2b2ka8; no Vite/browser server required. */
import assert from 'node:assert/strict'
import test from 'node:test'

import { createApp, effectScope } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useSignOut } from '../src/lib/auth/useSignOut.ts'
import { SIGN_OUT_FAILED } from '../src/lib/auth/signOutFlow.ts'

const BOUND = { timeout: 5_000 }

function deferred() {
  let resolve!: () => void
  const promise = new Promise<void>((done) => { resolve = done })
  return { promise, resolve }
}

async function appHarness() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:p(.*)*', component: { render: () => null } }],
  })
  await router.push('/account')
  await router.isReady()
  const app = createApp({ render: () => null })
  app.use(router)
  function consumer(revoke?: () => Promise<void>) {
    const scope = effectScope()
    const flow = app.runWithContext(() => scope.run(() => useSignOut(undefined, revoke)))
    assert.ok(flow)
    return { flow, scope }
  }
  return { router, consumer }
}

test('the default composable revokes through the real session store and account HTTP seam', BOUND, async (t) => {
  // These top-level tests run serially in this file's own Node test process. Restore the
  // transport automatically after this test; the composable receives no replacement revoke.
  const calls: { url: string; init?: RequestInit }[] = []
  t.mock.method(globalThis, 'fetch', async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init })
    return new Response(JSON.stringify({ data: { logout: { revoked: true } } }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  const harness = await appHarness()
  const caller = harness.consumer()
  try {
    assert.equal(await caller.flow.run(), true)
    assert.equal(calls.length, 1, 'a no-op default revoke must fail this node test')
    const sent = calls[0]!
    assert.equal(sent.url, '/graphql/account')
    assert.equal(sent.init?.method, 'POST')
    assert.equal(sent.init?.credentials, 'same-origin')
    const body = JSON.parse(String(sent.init?.body)) as { query: string; variables: unknown }
    assert.match(body.query, /mutation Logout\b/)
    assert.deepEqual(body.variables, { allSessions: false })
    assert.equal(harness.router.currentRoute.value.path, '/signin')
  } finally {
    caller.scope.stop()
  }
})

test('same-router consumers send one revoke and share pending through navigation', BOUND, async () => {
  const held = deferred()
  const navigation = deferred()
  const navigating = deferred()
  const harness = await appHarness()
  let requests = 0
  const revoke = async () => { requests += 1; await held.promise }
  const account = harness.consumer(revoke)
  const navbar = harness.consumer(revoke)
  const removeGuard = harness.router.beforeEach(async (to) => {
    if (to.path === '/signin') {
      navigating.resolve()
      await navigation.promise
    }
  })
  const first = account.flow.run()
  const second = navbar.flow.run() // Never await a held second press before checking its guard.
  try {
    assert.equal(requests, 1, 'simultaneous Account and navbar presses send exactly one logout')
    assert.equal(navbar.flow.pending.value, true, 'navbar observes the Account request')
    assert.equal(account.flow.pending, navbar.flow.pending, 'both controls observe the same pending ref')
    held.resolve()
    await navigating.promise
    assert.equal(navbar.flow.pending.value, true, 'pending includes lazy route/guard navigation')
    const third = navbar.flow.run()
    assert.equal(requests, 1, 'a press during navigation cannot send another logout')
    navigation.resolve()
    assert.equal(await first, true)
    assert.equal(await second, false)
    assert.equal(await third, false)
    assert.equal(harness.router.currentRoute.value.path, '/signin')
    assert.equal(navbar.flow.pending.value, false)
  } finally {
    held.resolve()
    navigation.resolve()
    removeGuard()
    await Promise.allSettled([first, second])
    account.scope.stop()
    navbar.scope.stop()
  }
})

test('surviving chrome reports a failure after Account leaves, clears pending and can retry', BOUND, async () => {
  const held = deferred()
  const retryHeld = deferred()
  const harness = await appHarness()
  let requests = 0
  const revoke = async () => {
    requests += 1
    if (requests === 1) {
      await held.promise
      throw new TypeError('Failed to fetch')
    }
    await retryHeld.promise
  }
  const account = harness.consumer(revoke)
  const navbar = harness.consumer(revoke)
  const first = account.flow.run()
  try {
    await harness.router.push('/pricing')
    account.scope.stop()
    held.resolve()
    assert.equal(await first, false)
    assert.equal(navbar.flow.error.value, SIGN_OUT_FAILED)
    assert.equal(account.flow.error, navbar.flow.error, 'one shared failure, not independent copies')
    assert.equal(navbar.flow.pending.value, false, 'disposal cannot strand shared chrome')
    assert.equal(harness.router.currentRoute.value.path, '/pricing', 'failure does not redirect')
    assert.equal(await account.flow.run(), false, 'disposed callers cannot start another request')
    assert.equal(requests, 1)
    const retry = navbar.flow.run()
    try {
      assert.equal(navbar.flow.error.value, '', 'retry clears the previous shared failure')
      assert.equal(navbar.flow.pending.value, true)
      assert.equal(requests, 2)
      retryHeld.resolve()
      assert.equal(await retry, true)
      assert.equal(harness.router.currentRoute.value.path, '/signin')
    } finally {
      retryHeld.resolve()
      await retry
    }
  } finally {
    held.resolve()
    retryHeld.resolve()
    await first
    account.scope.stop()
    navbar.scope.stop()
  }
})

test('late success after Account leaves releases the state for surviving and remounted consumers', BOUND, async () => {
  const held = deferred()
  const harness = await appHarness()
  const account = harness.consumer(() => held.promise)
  const navbar = harness.consumer(async () => {})
  const first = account.flow.run()
  try {
    await harness.router.push('/pricing')
    account.scope.stop()
    held.resolve()
    assert.equal(await first, true)
    assert.equal(harness.router.currentRoute.value.path, '/pricing')
    assert.equal(navbar.flow.pending.value, false)
    const remounted = harness.consumer(async () => {})
    try {
      assert.equal(remounted.flow.pending, navbar.flow.pending)
      assert.equal(remounted.flow.pending.value, false)
      assert.equal(remounted.flow.error.value, '')
    } finally {
      remounted.scope.stop()
    }
  } finally {
    held.resolve()
    await first
    account.scope.stop()
    navbar.scope.stop()
  }
})

test('a request in one router does not block another app/router', BOUND, async () => {
  const held = deferred()
  const firstApp = await appHarness()
  const secondApp = await appHarness()
  const first = firstApp.consumer(() => held.promise)
  let secondRequests = 0
  const second = secondApp.consumer(async () => { secondRequests += 1 })
  const pending = first.flow.run()
  try {
    assert.equal(second.flow.pending.value, false, 'SSR/app instances do not share operation state')
    assert.equal(await second.flow.run(), true)
    assert.equal(secondRequests, 1)
    assert.equal(first.flow.pending.value, true)
    assert.equal(firstApp.router.currentRoute.value.path, '/account')
    assert.equal(secondApp.router.currentRoute.value.path, '/signin')
  } finally {
    held.resolve()
    await pending
    first.scope.stop()
    second.scope.stop()
  }
})
