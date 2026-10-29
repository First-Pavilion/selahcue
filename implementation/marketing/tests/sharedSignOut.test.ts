/** Runtime composition regression for ClickUp 17tnw2b2ka8; no Vite/browser server required. */
import assert from 'node:assert/strict'
import test from 'node:test'

import { createApp, effectScope } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useSignOut } from '../src/lib/auth/useSignOut.ts'

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
  function consumer(revoke: () => Promise<void>) {
    const scope = effectScope()
    const flow = app.runWithContext(() => scope.run(() => useSignOut('/signin', revoke)))
    assert.ok(flow)
    return { flow, scope }
  }
  return { router, consumer }
}

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
