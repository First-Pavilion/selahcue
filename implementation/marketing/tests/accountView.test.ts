/**
 * The Account page shows the church's real account (ClickUp 17tnw2bhkd2), and nothing else.
 *
 * The page is server-rendered from the REAL `AccountView.vue` with a real router. The overview
 * is produced by the REAL `accountOverview` client against an injected transport answering with
 * the API's response shape, so what the page is handed is what the API would hand it. Server
 * rendering cannot run `onMounted` or click, so the view's own bindings are set to the state a
 * load or a click would have produced (see `fixtures/viewRender.ts`); a renamed binding throws.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { after, before, describe } from 'node:test'

import type { ViteDevServer } from 'vite'

import { accountOverview, type AccountOverview } from '../src/lib/api/account.ts'
import { renderView, startViewServer, textOf } from './fixtures/viewRender.ts'

let server: ViteDevServer
before(async () => {
  server = await startViewServer()
})
after(async () => {
  await server.close()
})

const quota = (limit: string, remaining: string) => ({
  limit,
  settled: '0',
  held: '0',
  carriedDebt: '0',
  remaining,
  asOf: '2026-11-15T12:00:00+00:00',
  resetsAt: '2026-11-16T00:00:00+00:00',
  status: 'CURRENT_OBSERVED',
})

function overviewBody(over: Partial<AccountOverview> = {}): AccountOverview {
  return {
    orgName: 'Grace Chapel',
    displayName: 'Ada',
    email: 'admin@grace.example.test',
    role: 'ADMIN',
    canDeactivateDevices: true,
    license: {
      status: 'ACTIVATED',
      startsAt: '2026-11-04T10:00:00+00:00',
      expiresAt: '2027-05-06T00:00:00+00:00',
      validNow: true,
      renewal: 'NOT_MANAGED',
      deviceLimit: 10,
      activeDeviceCount: '2',
    },
    allowance: {
      planDisplayName: 'Beta',
      planEndsAt: '2027-05-06T00:00:00+00:00',
      stt: { ...quota('10800', '7200'), settled: '3600' },
      notes: { ...quota('3', '1'), settled: '2' },
    },
    devices: {
      nodes: [
        { publicId: 'dev-a', displayName: 'Main booth', platform: 'macos', appVersion: '1.2.0', createdAt: '2026-11-15T12:00:00+00:00', status: 'ACTIVE' },
        { publicId: 'dev-b', displayName: 'Youth room PC', platform: 'windows', appVersion: '', createdAt: '2026-11-16T09:30:00+00:00', status: 'ACTIVE' },
      ],
      nextCursor: null,
    },
    ...over,
  }
}

/** Run the real client against a transport that answers with `body`, the way the API would. */
async function fetched(body: AccountOverview): Promise<AccountOverview> {
  const impl = (async () =>
    new Response(JSON.stringify({ data: { accountOverview: body } }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    })) as unknown as typeof fetch
  return accountOverview(undefined, undefined, { fetchImpl: impl })
}

const render = async (set: Record<string, unknown>) => textOf(await renderView(server, 'AccountView.vue', '/account', { set }))
const renderHtml = (set: Record<string, unknown>) => renderView(server, 'AccountView.vue', '/account', { set })

/** Words that only the removed mock page ever said. */
const MOCK_RESIDUE = [/sc_live_/i, /\bPro\b/, /invoice/i, /Sarah Jenkins/, /Grace Community Church/, /reverts to Free tier/i, /Bibles?\b/, /Billing/i, /\$\d/]

describe('with the real account loaded', () => {
  test('a Beta church sees its plan, its end date, its allowance and both computers', async () => {
    const text = await render({ status: 'ready', overview: await fetched(overviewBody()) })
    assert.match(text, /\bBeta\b/)
    assert.match(text, /until 5 May 2027/)
    assert.match(text, /120 min left of 180/)
    assert.match(text, /Main booth/)
    assert.match(text, /Youth room PC/)
    assert.match(text, /Grace Chapel/)
    assert.match(text, /Ada/)
    assert.match(text, /admin@grace\.example\.test/)
    assert.match(text, /2 of 10 computers/)
    assert.match(text, /resets 16 Nov 2026/i)
    assert.match(text, /1 left of 3/)
    for (const re of MOCK_RESIDUE) assert.doesNotMatch(text, re, `mock text survived: ${re}`)
  })

  test('a Free church with no end date shows "Free" and no end date', async () => {
    const body = overviewBody({
      license: null,
      allowance: { planDisplayName: 'Free', planEndsAt: null, stt: quota('1200', '1200'), notes: quota('1', '1') },
    })
    const text = await render({ status: 'ready', overview: await fetched(body) })
    assert.match(text, /\bFree\b/)
    assert.doesNotMatch(text, /until /)
    assert.doesNotMatch(text, /undefined|null|NaN|Invalid/)
    assert.match(text, /20 min left of 20/)
  })

  test('a church with no licence and no allowance still renders, with honest empty text', async () => {
    const body = overviewBody({ license: null, allowance: null, devices: { nodes: [], nextCursor: null } })
    const text = await render({ status: 'ready', overview: await fetched(body) })
    assert.match(text, /No computers are registered yet/)
    assert.doesNotMatch(text, /undefined|null|NaN|Invalid/)
  })

  test('an unnamed computer is still identifiable', async () => {
    const body = overviewBody()
    body.devices.nodes[1]!.displayName = ''
    const text = await render({ status: 'ready', overview: await fetched(body) })
    assert.match(text, /Unnamed computer \(windows\)/)
  })

  test('the page has no tabs and no mock sections', async () => {
    const html = await renderHtml({ status: 'ready', overview: await fetched(overviewBody()) })
    assert.doesNotMatch(html, /portal-tabs|tab-btn/)
  })
})

describe('deactivating a computer', () => {
  const deactivateButtons = (html: string) =>
    [...html.matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/g)].map((m) => textOf(m[1] ?? '')).filter((t) => /^Deactivate\b/.test(t))

  test('an administrator gets one Deactivate button per computer', async () => {
    const html = await renderHtml({ status: 'ready', overview: await fetched(overviewBody()) })
    assert.equal(deactivateButtons(html).length, 2)
  })

  test('a member who may not deactivate gets none', async () => {
    const html = await renderHtml({
      status: 'ready',
      overview: await fetched(overviewBody({ role: 'MEMBER', canDeactivateDevices: false })),
    })
    assert.equal(deactivateButtons(html).length, 0)
  })

  test('the confirm step is in the page, a second button, naming the computer', async () => {
    const text = await render({ status: 'ready', overview: await fetched(overviewBody()), confirmingId: 'dev-a' })
    assert.match(text, /Deactivate this computer\?/)
    assert.match(text, /Yes, deactivate/)
    assert.match(text, /Cancel/)
  })

  test('without a pending choice there is no confirm step', async () => {
    const text = await render({ status: 'ready', overview: await fetched(overviewBody()) })
    assert.doesNotMatch(text, /Deactivate this computer\?|Yes, deactivate/)
  })

  test('a failed deactivation is announced', async () => {
    const html = await renderHtml({
      status: 'ready',
      overview: await fetched(overviewBody()),
      deactivateError: 'We could not deactivate that computer. Please try again.',
    })
    assert.match(html, /role="alert"[^>]*>[^<]*We could not deactivate that computer/)
  })

  test('the view never uses window.confirm', () => {
    const source = readFileSync(new URL('../src/views/AccountView.vue', import.meta.url), 'utf8')
    assert.doesNotMatch(source, /\bconfirm\s*\(/)
    assert.doesNotMatch(source, /ConfirmDialog/)
  })
})

describe('loading and error', () => {
  test('while loading it says so and shows no account figures', async () => {
    const html = await renderHtml({ status: 'loading' })
    assert.match(textOf(html), /Loading your account/)
    assert.doesNotMatch(textOf(html), /\bBeta\b|\bFree\b|min left/)
  })

  test('on an API error it shows the error state and none of the old mock values', async () => {
    const html = await renderHtml({ status: 'error' })
    const text = textOf(html)
    assert.match(html, /role="alert"/)
    assert.match(text, /couldn't load your account/i)
    for (const re of MOCK_RESIDUE) assert.doesNotMatch(text, re, `mock text survived: ${re}`)
    assert.doesNotMatch(text, /min left|computers/)
  })

  test('the header (with Sign out) stays in every state', async () => {
    for (const status of ['loading', 'error']) {
      assert.match(textOf(await renderHtml({ status })), /Sign out/, status)
    }
  })
})
