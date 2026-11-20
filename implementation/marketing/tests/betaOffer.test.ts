import assert from 'node:assert/strict'
import test, { after, before } from 'node:test'

import { findAll, parseHtml, startRenderServer, textOf, type RenderServer } from './fixtures/renderPage.ts'

let server: RenderServer

before(async () => { server = await startRenderServer() })
after(async () => { await server?.close() })

const summary = 'The SelahCue public beta is free and includes every feature until 5 May 2027: up to 10 devices, no watermark, and 3 hours of cloud transcription and 5 sermon notes per church each week.'
const afterBeta = 'After the beta, your church keeps using SelahCue on the Free plan, which runs on one computer: the first one you set up. Paid plans will be announced before the beta ends.'

for (const view of ['HomeView', 'PricingView']) {
  test(`${view} explains the public beta and what follows, and links to the public acquisition journey`, async () => {
    const page = parseHtml(await server.render(`views/${view}.vue`))
    const text = textOf(page)
    const destinations = findAll(page, (element) => element.tag === 'a').map((link) => link.attrs.href)

    assert.ok(text.includes(summary), 'beta summary is shown')
    assert.ok(text.includes(afterBeta), 'after-beta wording is shown')
    assert.doesNotMatch(text, /pilot|free trial|\$\s*\d|checkout|provider access expires/i)
    assert.ok(destinations.includes('/signup'), 'an account can be created from the public offer')
    assert.ok(destinations.includes('/download#public-downloads'), 'installer discovery has a real destination')
    assert.ok(!destinations.some((href) => /pilot|checkout|billing/i.test(href ?? '')))
  })
}

test('the beta display data keeps the agreed values and destinations together', async () => {
  const { betaOffer } = await import('../src/lib/content/betaOffer.ts')
  assert.equal(betaOffer.endsOn, '5 May 2027')
  assert.equal(betaOffer.cloudTranscriptionHours, 3)
  assert.equal(betaOffer.sermonNotes, 5)
  assert.equal(betaOffer.devices, 10)
  assert.equal(betaOffer.summary, summary)
  assert.equal(betaOffer.afterBeta, afterBeta)
  assert.equal(betaOffer.signupTo, '/signup')
  assert.equal(betaOffer.downloadTo, '/download#public-downloads')
  assert.ok(Object.isFrozen(betaOffer))
})
