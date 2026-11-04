import assert from 'node:assert/strict'
import test from 'node:test'
import { startRenderServer, parseHtml, findAll, textOf } from './fixtures/renderPage.ts'

test('Home and Pricing announce loading without inventing plans before the public response arrives', async () => {
  const server = await startRenderServer()
  try {
    for (const file of ['views/HomeView.vue', 'views/PricingView.vue']) {
      const tree = parseHtml(await server.render(file))
      const statuses = findAll(tree, node => node.attrs.role === 'status')
      assert.ok(statuses.some(node => textOf(node) === 'Loading plans…'), file + ' must show an announced catalogue loading state')
      assert.equal(findAll(tree, node => (node.attrs.class ?? '').split(' ').includes('pricing-card')).length, 0)
    }
  } finally { await server.close() }
})

// Hand-derived fixtures: these names, amounts and allowances are synthetic test data only.
import { parseCatalogue, offerText, planFeatures, intervalOptions } from '../src/lib/catalogue/publicCatalogue.ts'
const plan = () => ({ key: 'HARBOUR', name: 'Harbour', price_state: 'unpriced', offers: [] as unknown[], cloud_transcript_minutes_per_week: 7, sermon_notes_per_week: 11, watermark: true })
const offer = (amount: string | null, exponent = 2, currency = 'USD', interval = 'MONTH') => ({ currency, interval, price_state: amount === null ? 'unpriced' : 'priced', amount_minor: amount, minor_unit_exponent: exponent })

test('commercial text uses response values and preserves zero, null, ISO exponents and signed64-bit precision', () => {
  const data = parseCatalogue({ plans: [{ ...plan(), price_state: 'priced', offers: [offer('0'), offer('9223372036854775807', 4, 'CLF', 'YEAR'), offer(null, 0, 'JPY', 'WEEK')] }] })
  assert.equal(data[0]?.name, 'Harbour')
  assert.deepEqual(data[0]?.offers.map(offerText), ['USD 0.00 / month', 'CLF 922337203685477.5807 / year', 'JPY / week: Price not announced yet'])
  assert.deepEqual(planFeatures(data[0]!), ['7 cloud transcript minutes per week', '11 sermon notes per week', 'Watermark included'])
  const alternate = parseCatalogue({ plans: [{ ...plan(), name: 'Gather', cloud_transcript_minutes_per_week: 13, sermon_notes_per_week: 17, watermark: false }] })
  assert.deepEqual(planFeatures(alternate[0]!), ['13 cloud transcript minutes per week', '17 sermon notes per week', 'No watermark'])
  assert.equal(offerText(offer('6', 0, 'JPY') as never), 'JPY 6 / month')
  assert.equal(offerText(offer('5', 3, 'BHD') as never), 'BHD 0.005 / month')
})

test('billing switching requires multiple actual priced intervals; all intervals avoids choosing a currency or commercial default', () => {
  assert.deepEqual(intervalOptions(parseCatalogue({ plans: [plan()] })), [])
  assert.deepEqual(intervalOptions(parseCatalogue({ plans: [{ ...plan(), price_state: 'priced', offers: [offer('1'), offer('2', 2, 'EUR')] }] })), [])
  const plans = parseCatalogue({ plans: [{ ...plan(), price_state: 'priced', offers: [offer('1'), offer('2', 2, 'EUR', 'YEAR')] }] })
  assert.deepEqual(intervalOptions(plans), [{ value: '', label: 'All intervals' }, { value: 'MONTH', label: 'Per month' }, { value: 'YEAR', label: 'Per year' }])
})

test('malformed, inconsistent or private data refuses the whole projection instead of inventing defaults', () => {
  const malformed = [
    null, {}, { plans: null }, { plans: [plan()], internal_id: 1 },
    { plans: [{ ...plan(), device_limit: 3 }] }, { plans: [{ ...plan(), watermark: 'false' }] },
    { plans: [{ ...plan(), cloud_transcript_minutes_per_week: Number.MAX_SAFE_INTEGER + 1 }] },
    { plans: [{ ...plan(), sermon_notes_per_week: -1 }] }, { plans: [{ ...plan(), name: '' }] },
    { plans: [plan(), plan()] }, { plans: Array.from({ length: 65 }, (_, i) => ({ ...plan(), key: String(i) })) },
    ...[offer('1.5'), offer('-1'), offer('9223372036854775808'), offer('0', 5), offer('1', 2, 'usd'), offer('1', 2, 'USD', 'DAY'), { ...offer(null), price_state: 'priced' }].map(o => ({ plans: [{ ...plan(), price_state: 'priced', offers: [o] }] })),
    { plans: [{ ...plan(), price_state: 'priced', offers: [] }] },
    { plans: [{ ...plan(), offers: [offer('1')] }] },
    { plans: [{ ...plan(), price_state: 'priced', offers: [offer('1'), offer('2')] }] },
  ]
  for (const data of malformed) assert.throws(() => parseCatalogue(data), /Catalogue unavailable/, JSON.stringify(data))
  assert.deepEqual(parseCatalogue({ plans: [] }), [])
})

import { fetchCatalogue } from '../src/lib/catalogue/publicCatalogue.ts'
test('public transport sends no credentials or cache and refuses error/HTML/oversized/invalid UTF8 bodies', async () => {
  const original = globalThis.fetch
  const signal = new AbortController().signal
  try {
    globalThis.fetch = async (url, init) => {
      assert.equal(url, '/v1/catalogue/plans')
      assert.deepEqual(init, { method: 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error', headers: { Accept: 'application/json' }, signal })
      return new Response(JSON.stringify({ plans: [plan()] }), { headers: { 'Content-Type': 'application/json; charset=utf-8' } })
    }
    assert.equal((await fetchCatalogue(signal))[0]?.name, 'Harbour')
    for (const response of [new Response('private server error', { status: 503 }), new Response('<html>not JSON</html>', { headers: { 'Content-Type': 'text/html' } }), new Response('{"plans":', { headers: { 'Content-Type': 'application/json' } }), new Response(new Uint8Array([255]), { headers: { 'Content-Type': 'application/json' } })]) {
      globalThis.fetch = async () => response
      await assert.rejects(fetchCatalogue(signal))
    }
    let cancelled = false
    globalThis.fetch = async () => new Response(new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(1024 * 1024 + 1)) }, cancel() { cancelled = true } }), { headers: { 'Content-Type': 'application/json' } })
    await assert.rejects(fetchCatalogue(signal), /Catalogue unavailable/)
    assert.equal(cancelled, true, 'oversized stream must stop instead of reading the whole body')
  } finally { globalThis.fetch = original }
})

test('refusing a server error cancels its unread body instead of retaining network work', async () => {
  const original = globalThis.fetch
  let cancelled = false
  try {
    globalThis.fetch = async () => new Response(new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('private diagnostic')) }, cancel() { cancelled = true } }), { status: 503 })
    await assert.rejects(fetchCatalogue(new AbortController().signal), /Catalogue unavailable/)
    assert.equal(cancelled, true)
  } finally { globalThis.fetch = original }
})
