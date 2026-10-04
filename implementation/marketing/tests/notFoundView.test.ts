/**
 * The not-found page (ClickUp 17tnw2b0x3h, audit shared-chrome-32): it opens no second <main> inside the site shell's, and it says
 * nothing about the visitor's account or devices, which it cannot know anything about. Its way onward (the home page and the
 * support page) stays: `scripts/auth_pages_headless.py` and `scripts/article_pages_headless.py` assert the same links.
 */
import assert from 'node:assert/strict'
import test, { after, before, describe } from 'node:test'

import type { ViteDevServer } from 'vite'

import { headingsOf, renderView, startViewServer, tagsOf, textOf } from './fixtures/viewRender.ts'

let server: ViteDevServer
let page = ''

before(async () => {
  server = await startViewServer()
  page = await renderView(server, 'NotFoundView.vue', '/nowhere')
})

after(async () => {
  await server?.close()
})

describe('the not-found page', () => {
  test('it is a div inside the shell, never a second <main> (shared-chrome-32)', () => {
    assert.equal(tagsOf(page).filter((t) => t.name === 'main').length, 0)
    assert.ok(tagsOf(page).some((t) => t.name === 'div' && (t.attrs['class'] ?? '').split(/\s+/).includes('nf-page')))
  })

  test('the heading and the way onward are kept: the home page and the support page', () => {
    const [h1] = headingsOf(page)
    assert.equal(h1?.level, 1)
    assert.equal(h1?.text, "We couldn't find that page")
    const hrefs = tagsOf(page).filter((t) => t.name === 'a').map((t) => t.attrs['href'])
    assert.deepEqual(hrefs, ['/', '/support'])
  })

  test('it says nothing about the visitor\'s account or devices (it cannot know)', () => {
    const text = textOf(page)
    assert.doesNotMatch(text, /account|device|activated|presenting/i)
    assert.match(text, /The link may be out of date, or the address may have a typo in it\./)
  })
})
