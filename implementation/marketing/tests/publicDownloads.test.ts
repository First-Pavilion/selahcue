import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, test } from 'node:test'
import { downloadForTarget, loadReleaseManifest, parseReleaseManifest } from '../src/lib/releases/downloads.ts'

const origin = 'https://selahcue-installers.sfo3.digitaloceanspaces.com'
const version = '0.0.0-synthetic'
const sha256 = 'a'.repeat(64)
const unpublished = { schema_version: 1, status: 'unpublished', artifacts: [] }

function artifact(target: string, architectures: string[]) {
  const isMac = target.startsWith('macos')
  const filename = `Synthetic-${target}.${isMac ? 'dmg' : target.startsWith('windows') ? 'exe' : 'deb'}`
  return {
    target, architectures, filename, sha256,
    url: `${origin}/Synthetic/Builds/${version}/${sha256}/${filename}`,
    size_bytes: 123456,
    app_signature: isMac ? 'ad_hoc' : 'not_applicable',
    package_signature: 'unsigned',
    notarization: isMac ? 'not_notarized' : 'not_applicable',
    publisher: null as string | null,
  }
}

function published() {
  return {
    schema_version: 1, status: 'published', version,
    release_id: 'synthetic-release', source_commit: 'b'.repeat(40),
    artifacts: [
      artifact('windows-x64', ['x64']), artifact('macos-arm64', ['arm64']),
      artifact('macos-x64', ['x64']), artifact('ubuntu-24.04-x64', ['x64']),
    ],
  }
}

describe('public release manifest', () => {
  test('source manifest is explicitly unpublished and resolves no installer', () => {
    const committed = JSON.parse(readFileSync(new URL('../public/releases/current.json', import.meta.url), 'utf8'))
    assert.deepEqual(committed, unpublished)
    assert.equal(downloadForTarget(parseReleaseManifest(committed), 'windows-x64'), null)
  })

  test('projects all four targets and preserves publisher-chosen URL path case', () => {
    const input = published()
    input.artifacts[0]!.filename = 'Synthetic Installer.EXE'
    input.artifacts[0]!.url = `${origin}/Synthetic/Builds/${version}/${sha256}/Synthetic%20Installer.EXE`
    const manifest = parseReleaseManifest(input)
    assert.deepEqual(manifest, input)
    assert.equal(downloadForTarget(manifest, 'windows-x64')?.url, input.artifacts[0]!.url)
  })

  const invalidRoot: Record<string, () => unknown> = {
    'missing manifest': () => undefined,
    'extra unpublished fields': () => ({ ...unpublished, release_id: 'synthetic' }),
    'unpublished inventory': () => ({ ...unpublished, artifacts: [artifact('windows-x64', ['x64'])] }),
    'unknown schema': () => ({ ...published(), schema_version: 2 }),
    'unknown root field': () => ({ ...published(), expiry: 'synthetic' }),
    'missing field': () => ({ ...published(), release_id: undefined }),
    'malformed source commit': () => ({ ...published(), source_commit: 'B'.repeat(40) }),
    'partial publish': () => ({ ...published(), artifacts: published().artifacts.slice(0, 3) }),
    'duplicate target': () => ({ ...published(), artifacts: Array(4).fill(artifact('windows-x64', ['x64'])) }),
    'more than four artifacts': () => ({ ...published(), artifacts: [...published().artifacts, artifact('macos-x64', ['x64'])] }),
  }
  for (const [name, input] of Object.entries(invalidRoot)) {
    test(`rejects ${name}`, () => assert.throws(() => parseReleaseManifest(input())))
  }

  const sample = published().artifacts[0]!
  const invalidArtifact: Record<string, Record<string, unknown>> = {
    'unsupported target': { target: 'linux-x64' },
    'non-HTTPS URL': { url: sample.url.replace('https:', 'http:') },
    'malformed URL': { url: 'no-url' },
    'credentialled URL': { url: sample.url.replace('https://', 'https://user:password@') },
    'empty URL credentials': { url: sample.url.replace('https://', 'https://@') },
    'query-bearing URL': { url: sample.url + '?token=fixture' },
    'empty query delimiter': { url: sample.url + '?' },
    'fragment-bearing URL': { url: sample.url + '#' },
    'custom port': { url: sample.url.replace(origin, origin + ':444') },
    'wrong host': { url: sample.url.replace(origin, origin + '.example.org') },
    'mutable root key': { url: origin + '/' },
    'wrong version segment': { url: sample.url.replace(version, version + '-old') },
    'wrong digest segment': { url: sample.url.replace(sha256, '0'.repeat(64)) },
    'wrong decoded filename': { url: sample.url.replace(sample.filename, 'synthetic-old.exe') },
    'invalid URL path escape': { url: sample.url.replace('/Synthetic/', '/%ny/') },
    'encoded path separator': { url: sample.url.replace('/Synthetic/', '/Synthetic%2fBuilds/') },
    'literal path traversal': { url: sample.url.replace('/Synthetic/', '/Synthetic/../') },
    'encoded path traversal': { url: sample.url.replace('/Synthetic/', '/Synthetic/%2e./') },
    'invalid filename path': { filename: 'bad/file.exe' },
    'control character in filename': { filename: 'fixture\u0000.exe' },
    'non-lowercase digest': { sha256: 'A'.repeat(64) },
    'incorrect digest length': { sha256: 'a'.repeat(63) },
    'zero bytes': { size_bytes: 0 },
    'fractional bytes': { size_bytes: 2.5 },
    'unsafe byte count': { size_bytes: Number.MAX_SAFE_INTEGER + 1 },
    'wrong architecture': { architectures: ['arm64'] },
    'unrecognized architecture': { architectures: ['x86'] },
    'duplicate architecture': { architectures: ['x64', 'x64'] },
    'unknown signature state': { package_signature: 'signed' },
    'inapplicable ad hoc Windows signature': { app_signature: 'ad_hoc' },
    'inapplicable Windows notarization': { notarization: 'not_notarized' },
    'verified signature without verified publisher': { package_signature: 'verified' },
    'unverified signer label': { publisher: 'Synthetic unverified signer' },
    'unexpected artifact field': { checksum_url: 'https://example.org' },
  }
  for (const [name, patch] of Object.entries(invalidArtifact)) {
    test(`rejects ${name}`, () => {
      const input = published()
      Object.assign(input.artifacts[0]!, patch)
      assert.throws(() => parseReleaseManifest(input))
    })
  }

  test('enforces the selected macOS signing and notarization states', () => {
    for (const patch of [
      { app_signature: 'unsigned' },
      { package_signature: 'verified', publisher: 'Synthetic signer' },
      { notarization: 'verified', publisher: 'Synthetic signer' },
      { architectures: ['x64'] },
    ]) {
      const input = published()
      Object.assign(input.artifacts[1]!, patch)
      assert.throws(() => parseReleaseManifest(input))
    }
  })

  test('accepts a verified Windows package signer', () => {
    const input = published()
    Object.assign(input.artifacts[0]!, { app_signature: 'verified', package_signature: 'verified', publisher: 'Synthetic signer' })
    assert.equal(downloadForTarget(parseReleaseManifest(input), 'windows-x64')?.publisher, 'Synthetic signer')
  })

  test('does not mistake two URL encodings of one object key for separate installers', () => {
    const input = published()
    const arm = input.artifacts[1]!
    input.artifacts[2] = {
      ...arm, target: 'macos-x64', architectures: ['x64'],
      url: arm.url.replace('/Synthetic/', '/%53ynthetic/'),
    }
    assert.throws(() => parseReleaseManifest(input))
  })

  test('bounds the parsed manifest as well as the network response', () => {
    assert.throws(() => parseReleaseManifest({ ...published(), release_id: 'x'.repeat(64 * 1024) }))
  })

  test('requires matching metadata and both verified slices when macOS targets share one URL', () => {
    const input = published()
    const arm = input.artifacts[1]!
    const filename = 'Synthetic-Mac.dmg'
    Object.assign(arm, { filename, url: arm.url.replace(arm.filename, filename), architectures: ['arm64', 'x64'] })
    input.artifacts[2] = { ...arm, architectures: ['x64', 'arm64'], target: 'macos-x64' }
    const manifest = parseReleaseManifest(input)
    assert.equal(downloadForTarget(manifest, 'macos-arm64')?.url, downloadForTarget(manifest, 'macos-x64')?.url)
    input.artifacts[2].size_bytes += 1
    assert.throws(() => parseReleaseManifest(input))
    input.artifacts[2].size_bytes = arm.size_bytes
    input.artifacts[2].architectures = ['x64']
    assert.throws(() => parseReleaseManifest(input))
  })
})

describe('same-origin release manifest loader', () => {
  test('does one credential-free, revalidating fetch with redirects disabled', async () => {
    let requests = 0
    const fetcher: typeof fetch = async (path, init) => {
      requests += 1
      assert.equal(path, '/releases/current.json')
      assert.equal(init?.credentials, 'omit')
      assert.equal(init?.cache, 'no-cache')
      assert.equal(init?.redirect, 'error')
      return Response.json(published())
    }
    assert.equal((await loadReleaseManifest(fetcher)).status, 'published')
    assert.equal(requests, 1)
  })

  test('rejects missing, unparseable, non-JSON and network responses without echoing payloads', async () => {
    for (const fetcher of [
      async () => new Response('Synthetic debug detail', { status: 404 }),
      async () => new Response('Synthetic debug detail', { headers: { 'Content-Type': 'application/json' } }),
      async () => new Response(JSON.stringify(unpublished)),
      async () => { throw new Error('Synthetic debug detail') },
    ]) {
      await assert.rejects(loadReleaseManifest(fetcher), (error: Error) =>
        error instanceof Error && !error.message.includes('Synthetic') && !error.message.includes('debug'),
      )
    }
  })

  test('rejects oversized streamed bytes despite a misleading Content-Length', async () => {
    let cancelled = false
    const bytes = new Uint8Array(32 * 1024 + 1).fill(32)
    const fetcher = async () => new Response(new ReadableStream({
      start(controller) { controller.enqueue(bytes); controller.enqueue(bytes) },
      cancel() { cancelled = true },
    }), { headers: { 'Content-Type': 'application/json', 'Content-Length': '20' } })
    await assert.rejects(loadReleaseManifest(fetcher))
    assert.equal(cancelled, true)
  })

  test('aborts a stalled body on the five-second timeout', async (t) => {
    let expire: (() => void) | undefined
    t.mock.method(globalThis, 'setTimeout', (callback: () => void, delay: number) => {
      assert.equal(delay, 5000)
      expire = callback
    })
    let cancelled = false
    let requestSignal: AbortSignal | null | undefined
    const fetcher: typeof fetch = async (_, options) => {
      requestSignal = options?.signal
      return new Response(new ReadableStream({ cancel() { cancelled = true } }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }
    const pending = loadReleaseManifest(fetcher)
    await Promise.resolve()
    assert.equal(requestSignal?.aborted, false)
    assert.ok(expire)
    expire()
    await assert.rejects(pending)
    assert.equal(requestSignal?.aborted, true)
    assert.equal(cancelled, true)
  })

  test('caller abort propagates to the fetch and rejects a stalled request', async () => {
    const caller = new AbortController()
    let requestSignal: AbortSignal | null | undefined
    const pending = loadReleaseManifest((_, options) => {
      requestSignal = options?.signal
      return new Promise(() => {})
    }, caller.signal)
    caller.abort()
    await assert.rejects(pending)
    assert.equal(requestSignal?.aborted, true)
  })
})
