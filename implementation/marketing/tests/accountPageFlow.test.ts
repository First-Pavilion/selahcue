/**
 * The Account page's real load and deactivate logic (`lib/accountPageFlow.ts`) against a failing
 * transport: an ended session goes to sign-in, a dead network shows the retryable error state,
 * a double press sends one request, and a retry reuses the request id.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'

import { accountOverview, deactivateOwnDevice, type AccountOverview } from '../src/lib/api/account.ts'
import { ApiError } from '../src/lib/api/graphql.ts'
import {
  DEACTIVATE_FAILED,
  LOAD_MORE_FAILED,
  createAccountPageFlow,
} from '../src/lib/accountPageFlow.ts'

const BOUND = { timeout: 5_000 }

const quota = { limit: '60', settled: '0', held: '0', carriedDebt: '0', remaining: '60', asOf: '', resetsAt: '', status: 'CURRENT_OBSERVED' }
const device = (id: string) => ({ publicId: id, displayName: id, platform: 'macos', appVersion: '', createdAt: '2026-11-15T12:00:00+00:00', status: 'ACTIVE' })
const body = (ids: string[], nextCursor: string | null = null): AccountOverview => ({
  orgName: 'Grace Chapel', displayName: 'Ada', email: 'a@b.test', role: 'ADMIN', canDeactivateDevices: true,
  license: null, allowance: { planDisplayName: 'Free', planEndsAt: null, stt: quota, notes: quota },
  devices: { nodes: ids.map(device), nextCursor },
})

type Reply = () => Promise<Response> | Response
/** Real clients over a scripted transport; each GraphQL call takes the next reply. */
function harness(replies: Reply[], session: 'live' | 'ended' | 'unreachable' = 'live') {
  const sent: { query: string; variables: Record<string, unknown> }[] = []
  const impl = (async (_url: unknown, init: RequestInit) => {
    const parsed = JSON.parse(String(init.body))
    sent.push(parsed)
    const next = replies.shift()
    if (!next) throw new Error('unexpected request')
    return next()
  }) as unknown as typeof fetch
  const ended: number[] = []
  const checks: number[] = []
  let ids = 0
  const flow = createAccountPageFlow({
    fetchOverview: (first, after, options) => accountOverview(first, after, { ...options, fetchImpl: impl }),
    deactivate: (id, requestId) => deactivateOwnDevice(id, requestId, { fetchImpl: impl }),
    onSessionEnded: () => void ended.push(1),
    confirmSession: async () => (checks.push(1), session),
    newRequestId: () => `request-id-${(ids += 1)}-0000000`,
  })
  return { flow, sent, ended, checks }
}
const ok = (data: unknown): Reply => () =>
  new Response(JSON.stringify({ data }), { status: 200, headers: { 'content-type': 'application/json' } })
const apiError = (code: string): Reply => () =>
  new Response(JSON.stringify({ errors: [{ message: 'x', extensions: { code } }], data: null }), {
    status: 200, headers: { 'content-type': 'application/json' },
  })
const down: Reply = () => { throw new TypeError('network down') }
const overviewOk = (ids: string[], cursor: string | null = null) => ok({ accountOverview: body(ids, cursor) })
const deactivated = ok({ deactivateOwnDevice: { alreadyInactive: false } })

describe('loading', () => {
  for (const code of ['UNAUTHENTICATED', 'PERMISSION_DENIED', 'NOT_FOUND']) {
    test(`${code} ends the visit and does not show a connection error`, BOUND, async () => {
      const { flow, ended } = harness([apiError(code)])
      await flow.load()
      assert.equal(ended.length, 1)
      assert.notEqual(flow.status.value, 'error')
    })
  }

  test('a network failure shows the retryable error state and does not sign out', BOUND, async () => {
    const { flow, ended } = harness([down])
    await flow.load()
    assert.equal(flow.status.value, 'error')
    assert.equal(ended.length, 0)
  })

  test('an API 500 is the error state, not a sign-out', BOUND, async () => {
    const { flow, ended } = harness([apiError('INTERNAL')])
    await flow.load()
    assert.equal(flow.status.value, 'error')
    assert.equal(ended.length, 0)
  })

  test('a retry after an error recovers', BOUND, async () => {
    const { flow } = harness([down, overviewOk(['a'])])
    await flow.load()
    await flow.load()
    assert.equal(flow.status.value, 'ready')
    assert.equal(flow.overview.value?.devices.nodes.length, 1)
  })
})

describe('show more', () => {
  test('a failed page has its own message and does not sign out', BOUND, async () => {
    const { flow, ended } = harness([overviewOk(['a'], 'c1'), down])
    await flow.load()
    await flow.loadMore()
    assert.equal(flow.loadMoreError.value, LOAD_MORE_FAILED)
    assert.equal(ended.length, 0)
  })

  test('a signed-out code asks the server first; only a confirmed end signs out', BOUND, async () => {
    const h = harness([overviewOk(['a'], 'c1'), apiError('UNAUTHENTICATED')], 'ended')
    await h.flow.load()
    await h.flow.loadMore()
    assert.equal(h.checks.length, 1)
    assert.equal(h.ended.length, 1)
  })

  for (const code of ['UNAUTHENTICATED', 'PERMISSION_DENIED', 'NOT_FOUND']) {
    test(`${code} on show more with a live session shows the message and reloads, no sign-out`, BOUND, async () => {
      const h = harness([overviewOk(['a'], 'c1'), apiError(code), overviewOk(['a', 'b'])], 'live')
      await h.flow.load()
      await h.flow.loadMore()
      assert.equal(h.checks.length, 1)
      assert.equal(h.ended.length, 0)
      assert.equal(h.flow.loadMoreError.value, LOAD_MORE_FAILED)
      assert.equal(h.flow.overview.value?.devices.nodes.length, 2)
    })
  }

  test('an unreachable check is not a sign-out either', BOUND, async () => {
    const h = harness([overviewOk(['a'], 'c1'), apiError('UNAUTHENTICATED'), overviewOk(['a'])], 'unreachable')
    await h.flow.load()
    await h.flow.loadMore()
    assert.equal(h.ended.length, 0)
  })

  test('a late failure after the page was left neither redirects nor sets state', BOUND, async () => {
    let release!: () => void
    const late: Reply = () => new Promise<Response>((resolve) => { release = () => resolve(apiError('UNAUTHENTICATED')()) })
    const h = harness([overviewOk(['a'], 'c1'), late], 'ended')
    await h.flow.load()
    const pending = h.flow.loadMore()
    await new Promise((r) => setImmediate(r))
    h.flow.abort()
    release()
    await pending
    assert.equal(h.ended.length, 0)
    assert.equal(h.checks.length, 0)
    assert.equal(h.flow.loadMoreError.value, '')
  })

  test('a good page is appended', BOUND, async () => {
    const { flow } = harness([overviewOk(['a'], 'c1'), overviewOk(['b'])])
    await flow.load()
    await flow.loadMore()
    assert.deepEqual(flow.overview.value?.devices.nodes.map((d) => d.publicId), ['a', 'b'])
  })
})

describe('deactivating', () => {
  test('a double press sends one mutation', BOUND, async () => {
    let release!: () => void
    const held: Reply = () => new Promise<Response>((resolve) => { release = () => resolve(deactivated() as Response) })
    const { flow, sent } = harness([overviewOk(['a', 'b']), held, overviewOk(['a', 'b'])])
    await flow.load()
    flow.askDeactivate('a')
    const first = flow.confirmDeactivate('a')
    const second = flow.confirmDeactivate('a')
    await new Promise((r) => setImmediate(r))
    assert.equal(sent.filter((s) => s.query.startsWith('mutation')).length, 1)
    release()
    await first
    await second
  })

  test('a failed attempt is retried with the SAME request id; success gets a fresh one next time', BOUND, async () => {
    const { flow, sent } = harness([overviewOk(['a']), down, deactivated, overviewOk(['a'])])
    await flow.load()
    await flow.confirmDeactivate('a')
    assert.equal(flow.deactivateError.value, DEACTIVATE_FAILED)
    await flow.confirmDeactivate('a')
    const ids = sent.filter((s) => s.query.startsWith('mutation')).map((s) => s.variables['requestId'])
    assert.equal(ids.length, 2)
    assert.equal(ids[0], ids[1])
  })

  test('an ended session during deactivation goes to sign-in', BOUND, async () => {
    const { flow, ended } = harness([overviewOk(['a']), apiError('UNAUTHENTICATED')])
    await flow.load()
    await flow.confirmDeactivate('a')
    assert.equal(ended.length, 1)
    assert.equal(flow.deactivateError.value, '')
  })

  test('NOT_FOUND means the computer is already gone: success notice, quiet reload, no sign-out', BOUND, async () => {
    const h = harness([overviewOk(['a', 'b']), apiError('NOT_FOUND'), overviewOk(['b'])], 'ended')
    await h.flow.load()
    await h.flow.confirmDeactivate('a')
    assert.equal(h.ended.length, 0)
    assert.equal(h.checks.length, 0)
    assert.equal(h.flow.deactivateError.value, '')
    assert.match(h.flow.notice.value, /was deactivated/)
    assert.deepEqual(h.flow.overview.value?.devices.nodes.map((d) => d.publicId), ['b'])
  })

  test('PERMISSION_DENIED with a confirmed ended session signs out', BOUND, async () => {
    const h = harness([overviewOk(['a']), apiError('PERMISSION_DENIED')], 'ended')
    await h.flow.load()
    await h.flow.confirmDeactivate('a')
    assert.equal(h.checks.length, 1)
    assert.equal(h.ended.length, 1)
  })

  test('PERMISSION_DENIED with a live session shows DEACTIVATE_FAILED and reloads the list', BOUND, async () => {
    const h = harness([overviewOk(['a', 'b']), apiError('PERMISSION_DENIED'), overviewOk(['b'])], 'live')
    await h.flow.load()
    await h.flow.confirmDeactivate('a')
    assert.equal(h.ended.length, 0)
    assert.equal(h.flow.deactivateError.value, DEACTIVATE_FAILED)
    assert.deepEqual(h.flow.overview.value?.devices.nodes.map((d) => d.publicId), ['b'])
  })

  test('UNAUTHENTICATED on deactivate signs out directly, without asking', BOUND, async () => {
    const h = harness([overviewOk(['a']), apiError('UNAUTHENTICATED')], 'live')
    await h.flow.load()
    await h.flow.confirmDeactivate('a')
    assert.equal(h.checks.length, 0)
    assert.equal(h.ended.length, 1)
  })

  test('if the reload after success fails the computer is shown deactivated, not active', BOUND, async () => {
    const { flow } = harness([overviewOk(['a', 'b']), deactivated, down])
    await flow.load()
    await flow.confirmDeactivate('a')
    const nodes = flow.overview.value!.devices.nodes
    assert.equal(nodes.find((d) => d.publicId === 'a')?.status, 'REVOKED')
    assert.equal(nodes.find((d) => d.publicId === 'b')?.status, 'ACTIVE')
    assert.equal(flow.status.value, 'ready')
  })

  test('the reload asks for as many computers as were already loaded (at least 20)', BOUND, async () => {
    const { flow, sent } = harness([overviewOk(['a']), deactivated, overviewOk(['a'])])
    await flow.load()
    await flow.confirmDeactivate('a')
    assert.equal(sent[sent.length - 1]!.variables['first'], 20)
  })
})

test('ApiError is what the API client raises', () => {
  assert.ok(new ApiError('UNAUTHENTICATED') instanceof Error)
})
