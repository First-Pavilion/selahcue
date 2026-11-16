import assert from 'node:assert/strict'
import test, { after, before } from 'node:test'

import { findAll, parseHtml, startRenderServer, textOf, type RenderServer } from './fixtures/renderPage.ts'

let server: RenderServer

before(async () => { server = await startRenderServer() })
after(async () => { await server?.close() })

const allowance = /ongoing Free plan includes 20 cloud transcription minutes and 1 sermon note per church per week/i

for (const view of ['HomeView', 'PricingView']) {
  test(`${view} explains the ongoing church-wide weekly offer and links to the public acquisition journey`, async () => {
    const page = parseHtml(await server.render(`views/${view}.vue`))
    const text = textOf(page)
    const destinations = findAll(page, (element) => element.tag === 'a').map((link) => link.attrs.href)

    assert.match(text, allowance)
    assert.match(text, /Paid subscriptions will come later\./)
    assert.doesNotMatch(text, /pilot|free trial|\$\s*\d|checkout|provider access expires/i)
    assert.ok(destinations.includes('/signup'), 'an account can be created from the public offer')
    assert.ok(destinations.includes('/download#public-downloads'), 'installer discovery has a real destination')
    assert.ok(!destinations.some((href) => /pilot|checkout|billing/i.test(href ?? '')))
  })
}

test('the Free display data keeps the agreed values and destinations together', async () => {
  const { freeOffer } = await import('../src/lib/content/freeOffer.ts')
  assert.equal(freeOffer.cloudTranscriptionMinutes, 20)
  assert.equal(freeOffer.sermonNotes, 1)
  assert.equal(freeOffer.signupTo, '/signup')
  assert.equal(freeOffer.downloadTo, '/download#public-downloads')
  assert.ok(Object.isFrozen(freeOffer))
})
