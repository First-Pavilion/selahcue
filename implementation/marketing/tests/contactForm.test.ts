/**
 * The Contact form's email rule (ClickUp 17tnw2b2cez, review round 2: Vera 1).
 *
 * `/\S+@\S+\.\S+/` is unanchored and its `\S+` runs overlap, so on a long value with many `@` signs it backtracks
 * far beyond linear time: about 0.75 s at 2,000 characters, 5.7 s at 4,000, 100 s at 10,000. The form checks the
 * email every time the field loses focus, so a pasted value could freeze the tab. `lib/contactForm.ts` refuses
 * anything longer than 254 characters (the longest valid address) BEFORE the pattern runs.
 *
 * Three kinds of test, so that none of them can be satisfied by the others:
 *   - what the rule ACCEPTS did not change (it still accepts `x y@z.com`; the anchored pattern that is fast would not),
 *   - the cap's own boundary (254 in, 255 out), which fails the moment the guard is removed or moved,
 *   - speed: a 4,000-character value finishes inside a small bound in this thread, and a 10,000-character value (which
 *     would run for minutes without the guard) answers inside a few seconds in a WORKER the test can terminate, so
 *     a missing guard fails the test instead of hanging the suite. A control proves the worker harness itself reports
 *     a call that never returns.
 */
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test, { describe } from 'node:test'
import { Worker } from 'node:worker_threads'

import { EMAIL_MAX_LENGTH, looksLikeEmail } from '../src/lib/contactForm.ts'
import { SRC } from './fixtures/viewRender.ts'

const MODULE_URL = new URL('../src/lib/contactForm.ts', import.meta.url).href

type WorkerResult = { timedOut: true; elapsed: number } | { timedOut: false; value: unknown; ms: number; elapsed: number }

/**
 * Run `body` (the text of an async function body that returns a value) in a worker thread with the module's URL in
 * scope as `moduleUrl` and `value` as the input. If it has not answered within `limitMs` the worker is terminated and
 * the result says so: the main thread is never blocked by the code under test.
 */
function inWorker(body: string, value: string, limitMs: number): Promise<WorkerResult> {
  const code = `
    const { parentPort, workerData } = require('node:worker_threads')
    ;(async () => {
      const { moduleUrl, value } = workerData
      const run = async () => { ${body} }
      const t0 = performance.now()
      const out = await run()
      parentPort.postMessage({ value: out, ms: performance.now() - t0 })
    })()
  `
  return new Promise((resolve) => {
    const started = performance.now()
    const worker = new Worker(code, { eval: true, workerData: { moduleUrl: MODULE_URL, value } })
    worker.unref()
    const timer = setTimeout(() => {
      void worker.terminate()
      resolve({ timedOut: true, elapsed: performance.now() - started })
    }, limitMs)
    worker.once('message', (m: { value: unknown; ms: number }) => {
      clearTimeout(timer)
      void worker.terminate()
      resolve({ timedOut: false, value: m.value, ms: m.ms, elapsed: performance.now() - started })
    })
    worker.once('error', () => {
      clearTimeout(timer)
      resolve({ timedOut: true, elapsed: performance.now() - started })
    })
  })
}

/** The real call: import the module inside the worker and ask it. */
const ASK_THE_MODULE = `const m = await import(moduleUrl); const t = performance.now(); const r = m.looksLikeEmail(value); return { r, ms: performance.now() - t }`

describe('the Contact email rule: what it accepts is unchanged', () => {
  test('it accepts the shapes it always accepted, including ones the stricter sign-in rule refuses', () => {
    for (const ok of ['jane@yourchurch.org', 'a@b.c', 'x y@z.com', 'first.last+tag@sub.domain.example', 'münchen@exämple.de']) {
      assert.equal(looksLikeEmail(ok), true, ok)
    }
  })

  test('it refuses a value with no @, no dot after it, or nothing on a side', () => {
    for (const bad of ['', 'plain', 'jane@yourchurch', '@yourchurch.org', 'jane@.org', 'jane@yourchurch.', ' @ . ']) {
      assert.equal(looksLikeEmail(bad), false, JSON.stringify(bad))
    }
  })

  test('the cap is the longest valid address: 254 characters in, 255 out (and the same shape is accepted just under it)', () => {
    assert.equal(EMAIL_MAX_LENGTH, 254)
    const at = (len: number): string => 'a'.repeat(len - '@b.com'.length) + '@b.com'
    assert.equal(at(254).length, 254)
    assert.equal(looksLikeEmail(at(254)), true, '254 characters, otherwise fine')
    assert.equal(looksLikeEmail(at(255)), false, '255 characters is longer than any address can be')
    assert.equal(looksLikeEmail(at(300)), false)
  })
})

describe('the Contact email rule: a long value cannot freeze the page', () => {
  test('a 4,000-character value of repeated a@ is answered in a few milliseconds (the unguarded pattern took 5.7 s)', () => {
    const value = 'a@'.repeat(2000)
    assert.equal(value.length, 4000)
    const t0 = performance.now()
    const got = looksLikeEmail(value)
    const ms = performance.now() - t0
    assert.equal(got, false)
    assert.ok(ms < 100, `a 4,000-character value took ${ms.toFixed(1)} ms (limit 100)`)
  })

  test('the worst value the cap lets through (254 characters of a@) is still fast', () => {
    const value = 'a@'.repeat(127)
    const t0 = performance.now()
    looksLikeEmail(value)
    const ms = performance.now() - t0
    assert.ok(ms < 250, `254 characters of a@ took ${ms.toFixed(1)} ms (about 9 ms unloaded; limit 250)`)
  })

  test('a 10,000-character value answers inside 4 s in a worker (without the guard it runs for about 100 s)', async () => {
    const res = await inWorker(ASK_THE_MODULE, 'a@'.repeat(5000), 4000)
    assert.equal(res.timedOut, false, 'the check did not finish in 4 s: the length guard is missing or sits after the pattern')
    if (!res.timedOut) {
      const v = res.value as { r: boolean; ms: number }
      assert.equal(v.r, false)
      assert.ok(v.ms < 100, `the call itself took ${v.ms.toFixed(1)} ms`)
    }
  })

  test('CONTROL: the worker harness reports a call that never returns, and gets control back', async () => {
    const res = await inWorker('while (true) {}', '', 300)
    assert.equal(res.timedOut, true)
    assert.ok(res.elapsed < 3000, `control returned after ${res.elapsed.toFixed(0)} ms`)
  })

  test('CONTROL: the worker harness returns a real answer for a quick call', async () => {
    const res = await inWorker(ASK_THE_MODULE, 'jane@yourchurch.org', 4000)
    assert.equal(res.timedOut, false)
    if (!res.timedOut) assert.equal((res.value as { r: boolean }).r, true)
  })
})

describe('the permissive pattern lives in one place', () => {
  /** Every source file under src (ts and vue), as [relative path, code lines only: comments are not code]. */
  function codeFiles(dir: string, out: Array<[string, string]> = []): Array<[string, string]> {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) codeFiles(full, out)
      else if (/\.(ts|vue)$/.test(entry.name)) {
        const code = readFileSync(full, 'utf8')
          .split('\n')
          .filter((l) => !/^\s*(\*|\/\/|\/\*|<!--)/.test(l))
          .join('\n')
        out.push([path.relative(SRC, full), code])
      }
    }
    return out
  }

  test('no file other than lib/contactForm.ts carries the unanchored /\\S+@\\S+\\.\\S+/ pattern in code', () => {
    const found = codeFiles(SRC)
      .filter(([, code]) => code.includes('\\S+@\\S+'))
      .map(([file]) => file)
    assert.deepEqual(found, ['lib/contactForm.ts'])
  })

  test('CONTROL: the scan sees the pattern where it is, and skips a comment that merely names it', () => {
    const files = codeFiles(SRC)
    assert.ok(files.length > 20, `only ${files.length} files were scanned`)
    const own = files.find(([f]) => f === 'lib/contactForm.ts')
    assert.ok(own?.[1].includes('\\S+@\\S+'), 'the real pattern is found in code')
    const policy = files.find(([f]) => f === path.join('lib', 'auth', 'emailPolicy.ts'))
    assert.ok(policy, 'the auth email policy was scanned')
    assert.ok(readFileSync(path.join(SRC, 'lib/auth/emailPolicy.ts'), 'utf8').includes('\\S+@\\S+'), 'its header comment names the old pattern')
    assert.ok(!policy[1].includes('\\S+@\\S+'), 'and that comment is not counted as code')
  })
})
