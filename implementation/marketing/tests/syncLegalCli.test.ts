/**
 * `scripts/sync_legal.ts` as a command: the exit codes CI and a developer actually see.
 *
 * Two silent failures this pins:
 *  - a typo such as `--chek` used to fall through into WRITE mode and exit 0;
 *  - run through a symlinked path, the entry-point guard compared an unresolved path with
 *    a resolved one, never ran `main`, and `check:legal` exited 0 having checked nothing.
 */
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test, { after, describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { REPO_ROOT, TARGETS, sameContent } from '../scripts/sync_legal.ts'

const SCRIPT = fileURLToPath(new URL('../scripts/sync_legal.ts', import.meta.url))
const GENERATED = fileURLToPath(new URL('../src/lib/legal/', import.meta.url))
const DOCS_PRESENT = TARGETS.every((t) => existsSync(`${REPO_ROOT}/${t.source}`))

const scratch = mkdtempSync(join(tmpdir(), 'sync-legal-'))
after(() => rmSync(scratch, { recursive: true, force: true }))

function run(entry: string, args: string[]) {
  const r = spawnSync(process.execPath, [entry, ...args], { encoding: 'utf8' })
  return { code: r.status, out: `${r.stdout}${r.stderr}` }
}

function snapshot(): string {
  return readdirSync(GENERATED)
    .filter((f) => f.endsWith('.generated.ts'))
    .map((f) => `${f}:${readFileSync(join(GENERATED, f), 'utf8').length}`)
    .join('|')
}

/** A copy of the real drafts with one word changed in the Privacy Policy. */
function mutatedDrafts(): string {
  const dir = mkdtempSync(join(scratch, 'drafts-'))
  for (const t of TARGETS) {
    const file = t.source.split('/').pop() ?? ''
    copyFileSync(`${REPO_ROOT}/${t.source}`, join(dir, file))
  }
  const privacy = join(dir, TARGETS[0]?.source.split('/').pop() ?? '')
  const text = readFileSync(privacy, 'utf8')
  assert.ok(text.includes("stays on your church's computers"))
  writeFileSync(privacy, text.replace("stays on your church's computers", "stays on your church's machines"))
  return dir
}

describe('arguments are strict', () => {
  test('an unknown flag (a typo for --check) exits 2 with usage, and writes nothing', () => {
    const before = snapshot()
    const r = run(SCRIPT, ['--chek'])
    assert.equal(r.code, 2)
    assert.match(r.out, /unknown argument "--chek"/)
    assert.match(r.out, /usage:/)
    assert.equal(snapshot(), before, 'no generated file may be touched by a rejected invocation')
  })

  test('a stray positional argument and a flag with no value are refused too', () => {
    assert.equal(run(SCRIPT, ['check']).code, 2)
    assert.equal(run(SCRIPT, ['--src']).code, 2)
    assert.equal(run(SCRIPT, ['--out', '--check']).code, 2)
  })
})

describe('check mode really checks', { skip: !DOCS_PRESENT && 'docs/legal is not present' }, () => {
  test('exit 0 and "ok" for both files on the committed tree', () => {
    const r = run(SCRIPT, ['--check'])
    assert.equal(r.code, 0, r.out)
    assert.equal(r.out.match(/^ok /gm)?.length, 2)
  })

  test('exit 1 and STALE when a draft differs, with the instruction to run sync:legal', () => {
    const r = run(SCRIPT, ['--check', '--src', mutatedDrafts()])
    assert.equal(r.code, 1, r.out)
    assert.match(r.out, /STALE/)
    assert.match(r.out, /npm run sync:legal/)
  })

  test('the SAME holds through a symlinked path (the guard must not silently skip main)', () => {
    const dir = mkdtempSync(join(scratch, 'link-'))
    mkdirSync(dir, { recursive: true })
    const link = join(dir, 'sync_legal_link.ts')
    symlinkSync(SCRIPT, link)
    const stale = run(link, ['--check', '--src', mutatedDrafts()])
    assert.equal(stale.code, 1, `a stale tree must fail under a symlink too: ${stale.out}`)
    assert.match(stale.out, /STALE/)
    const fine = run(link, ['--check'])
    assert.equal(fine.code, 0, fine.out)
    assert.equal(fine.out.match(/^ok /gm)?.length, 2, 'and it must actually have checked both files')
  })
})

describe('line endings do not decide drift', () => {
  test('a CRLF copy of a generated file is the same content; a real difference is not', () => {
    const lf = 'export const x = 1\nexport const y = 2\n'
    assert.equal(sameContent(lf.replace(/\n/g, '\r\n'), lf), true)
    assert.equal(sameContent(lf, lf.replace(/\n/g, '\r\n')), true)
    assert.equal(sameContent('export const x = 2\n', lf), false)
    assert.equal(sameContent(null, lf), false)
  })
})
