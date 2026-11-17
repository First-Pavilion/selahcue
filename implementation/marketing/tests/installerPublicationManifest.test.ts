import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readdirSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { parseReleaseManifest } from '../src/lib/releases/downloads.ts'

const validator = fileURLToPath(new URL('../scripts/validate_release_manifest.ts', import.meta.url))
const version = '0.0.0-synthetic'
const digest = 'a'.repeat(64)
const origin = 'https://selahcue-installers.sfo3.digitaloceanspaces.com'

function artifact(target: string, filename: string) {
  const mac = target.startsWith('macos-')
  return {
    target, filename, architectures: mac ? ['arm64', 'x64'] : ['x64'],
    url: `${origin}/installers/${version}/${digest}/${encodeURIComponent(filename)}`,
    size_bytes: 123, sha256: digest, app_signature: mac ? 'ad_hoc' : 'unsigned',
    package_signature: 'unsigned', notarization: mac ? 'not_notarized' : 'not_applicable',
    publisher: null,
  }
}

function published() {
  const mac = artifact('macos-arm64', 'Synthetic Universal.dmg')
  return {
    schema_version: 1, status: 'published', release_id: 'synthetic',
    version, source_commit: 'b'.repeat(40), artifacts: [
      artifact('windows-x64', 'Synthetic Installer.exe'), mac,
      { ...mac, target: 'macos-x64' }, artifact('ubuntu-24.04-x64', 'synthetic.deb'),
    ],
  }
}

function validate(raw: string | Buffer, extraArgs: string[] = []) {
  const directory = mkdtempSync(join(realpathSync(tmpdir()), 'installer-manifest-test-'))
  try {
    const path = join(directory, 'synthetic.json')
    writeFileSync(path, raw)
    const result = spawnSync(process.execPath, [validator, path, ...extraArgs], {
      encoding: 'utf8', timeout: 5000,
    })
    assert.ifError(result.error)
    assert.deepEqual(readdirSync(directory), ['synthetic.json'])
    return result
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
}

test('the validator accepts the actual parser’s published and unpublished schemas', () => {
  for (const value of [published(), { schema_version: 1, status: 'unpublished', artifacts: [] }]) {
    assert.deepEqual(parseReleaseManifest(value), value)
    const result = validate(JSON.stringify(value))
    assert.equal(result.status, 0, result.stderr)
    assert.match(result.stdout, /valid release manifest/i)
  }
})

const mutations: [string, (value: ReturnType<typeof published>) => void][] = [
  ['wrong host', (value) => { value.artifacts[0]!.url = value.artifacts[0]!.url.replace(origin, 'https://example.invalid') }],
  ['duplicate target', (value) => { value.artifacts[2]!.target = 'macos-arm64' }],
  ['altered shared mac metadata', (value) => { value.artifacts[2]!.size_bytes += 1 }],
  ['thin Mac record claiming a shared object', (value) => { value.artifacts[1]!.architectures = ['arm64'] }],
  ['unexpected field', (value) => { Object.assign(value.artifacts[0]!, { unexpected: true }) }],
]

for (const [name, mutate] of mutations) {
  test(`validator delegates rejection of ${name} to the actual parser`, () => {
    const value = published()
    mutate(value)
    assert.throws(() => parseReleaseManifest(value))
    const result = validate(JSON.stringify(value))
    assert.equal(result.status, 2, result.stderr)
    assert.equal(result.stdout, '')
  })
}

test('validator rejects duplicate keys, excessive bytes, invalid UTF-8, and extra arguments', () => {
  const valid = JSON.stringify(published())
  const duplicate = valid.replace('"schema_version":1', '"schema_version":1,"schema_versi\\u006fn":1')
  const atLimit = valid.padEnd(64 * 1024)
  assert.equal(validate(atLimit).status, 0)
  for (const result of [
    validate(duplicate), validate(atLimit + ' '), validate(Buffer.from([0xff])),
    validate(valid, ['--force']),
  ]) {
    assert.equal(result.status, 2, result.stderr)
    assert.equal(result.stdout, '')
  }
})
