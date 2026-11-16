import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { after, before } from 'node:test'
import ts from 'typescript'

import { findAll, parseHtml, startRenderServer, textOf, type RenderServer } from './fixtures/renderPage.ts'

let server: RenderServer

before(async () => { server = await startRenderServer() })
after(async () => { await server?.close() })

test('public router imports neither of the excluded mock portals', () => {
  const file = readFileSync(new URL('../src/router/index.ts', import.meta.url), 'utf8')
  const imports = ts.preProcessFile(file, true, true).importedFiles.map(({ fileName }) => fileName)
  assert.ok(imports.includes('@/views/NotFoundView.vue'), 'the import scanner sees the catch-all lazy import')
  assert.deepEqual(imports.filter((path) => /\/views\/(admin|affiliates)\//.test(path)), [])
})

test('bookmarked pilot download fragment targets a section with the public installer cards', async () => {
  const page = parseHtml(await server.render('views/DownloadView.vue'))
  const [publicSection] = findAll(page, (element) => element.attrs.id === 'public-downloads')
  assert.ok(publicSection)
  assert.equal(findAll(publicSection, (element) => element.attrs.id === 'pilot-downloads').length, 1)
  assert.match(textOf(publicSection), /Windows x64/)
  assert.doesNotMatch(textOf(page), /Register for the pilot/i)
})

test('the archived pilot notice preserves the historical policy and contacts without acquisition controls', async () => {
  const page = parseHtml(await server.render('views/PilotPrivacyView.vue'))
  const text = textOf(page)
  const notice = JSON.parse(readFileSync(
    new URL('../../../docs/release/pilot-registration/notice.json', import.meta.url), 'utf8',
  )) as { title: string; version: string; sections: { paragraphs: string[] }[]; primary_contact: string; alternate_contact: string }

  assert.match(text, /archived pilot/i)
  assert.ok(text.includes(notice.title))
  assert.ok(text.includes(notice.version))
  for (const section of notice.sections) {
    for (const paragraph of section.paragraphs) assert.ok(text.includes(paragraph))
  }
  assert.deepEqual(findAll(page, (node) => node.tag === 'a').map((node) => node.attrs.href), [
    `mailto:${notice.primary_contact}`,
    `mailto:${notice.alternate_contact}`,
  ])
  assert.deepEqual(findAll(page, (node) => ['button', 'form', 'input'].includes(node.tag)), [])
})
