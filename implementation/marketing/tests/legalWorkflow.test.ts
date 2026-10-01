/**
 * The legal-drift workflow is the only thing that runs the drift guard when a draft in
 * `docs/legal` is edited (ci.yml ignores docs). A workflow that quietly stopped doing so
 * would be a green no-op, so its load-bearing properties are pinned here as text checks.
 * (Syntax and expression errors are actionlint's job, which ci.yml runs over every workflow.)
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

const REPO = fileURLToPath(new URL('../../../', import.meta.url))
const WORKFLOW = `${REPO}.github/workflows/legal-drift.yml`
const PACKAGE = fileURLToPath(new URL('../package.json', import.meta.url))
const PRESENT = existsSync(WORKFLOW)

describe('legal-drift workflow', { skip: !PRESENT && 'repository workflows are not present (build context without the repo)' }, () => {
  const text = PRESENT ? readFileSync(WORKFLOW, 'utf8') : ''
  const scripts = (JSON.parse(readFileSync(PACKAGE, 'utf8')) as { scripts: Record<string, string> }).scripts

  test('is triggered by edits to docs/legal and to the generated/renderer files, on PRs and on main', () => {
    assert.match(text, /^on:\s*\n\s+pull_request:\s*\n\s+paths:/m)
    assert.match(text, /^\s+push:\s*\n\s+branches: \[main\]\s*\n\s+paths:/m)
    for (const p of ['docs/legal/**', 'implementation/marketing/src/lib/legal/**', 'implementation/marketing/scripts/*legal*']) {
      assert.equal(text.split(`"${p}"`).length - 1, 2, `${p} must trigger both pull_request and push`)
    }
  })

  test('least privilege: contents read only, no persisted credentials, no secrets', () => {
    assert.match(text, /^permissions:\s*\n\s+contents: read\s*$/m)
    assert.match(text, /persist-credentials: false/)
    assert.ok(!/\bsecrets\./.test(text), 'this workflow needs no secrets')
    assert.ok(!/pull_request_target/.test(text), 'pull_request_target would run untrusted code with a token')
  })

  test('actually runs the drift check, the legal tests and the real-browser check', () => {
    assert.match(text, /run: npm run check:legal/)
    assert.match(text, /tests\/legal\.test\.ts/)
    assert.match(text, /tests\/syncLegalCli\.test\.ts/)
    assert.match(text, /run: npm run test:legal-pages/)
  })

  test('the browser step fails closed: a missing Playwright or Chrome is a failure, not a skip', () => {
    assert.match(text, /SELAHCUE_HEADLESS_REQUIRE: "1"/)
  })

  test('the npm scripts the workflow calls exist', () => {
    assert.equal(scripts['check:legal'], 'node scripts/sync_legal.ts --check')
    assert.equal(scripts['sync:legal'], 'node scripts/sync_legal.ts')
    assert.match(scripts['test:legal-pages'] ?? '', /^npm run build && python3 scripts\/legal_pages_headless\.py$/)
  })

  test('does not live in ci.yml: the marketing job there is edited by other PRs', () => {
    const ci = readFileSync(`${REPO}.github/workflows/ci.yml`, 'utf8')
    assert.ok(!ci.includes('check:legal'), 'keep the drift guard in its own workflow')
  })
})
