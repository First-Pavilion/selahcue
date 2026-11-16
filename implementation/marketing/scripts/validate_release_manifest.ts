import { closeSync, constants, fstatSync, lstatSync, openSync, readSync } from 'node:fs'
import { isAbsolute, join, parse, sep } from 'node:path'
import { parseReleaseManifest } from '../src/lib/releases/downloads.ts'

const maxBytes = 64 * 1024

function readManifest(path: string): string {
  const root = isAbsolute(path) ? parse(path).root : process.cwd()
  const components = path.slice(isAbsolute(path) ? root.length : 0).split(sep)
  if (components.includes('..')) throw new Error('Invalid manifest path')

  let current = root
  for (const component of components) {
    current = join(current, component)
    if (lstatSync(current).isSymbolicLink()) throw new Error('Symlink in manifest path')
  }

  const fd = openSync(current, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK)
  try {
    const before = fstatSync(fd, { bigint: true })
    if (!before.isFile() || before.size > maxBytes) throw new Error('Invalid manifest file')
    const bytes = Buffer.alloc(Number(before.size))
    let offset = 0
    while (offset < bytes.length) {
      const length = readSync(fd, bytes, offset, bytes.length - offset, null)
      if (length === 0) throw new Error('Manifest length changed')
      offset += length
    }
    const after = fstatSync(fd, { bigint: true })
    const linked = lstatSync(current, { bigint: true })
    for (const observed of [after, linked]) {
      if (before.dev !== observed.dev || before.ino !== observed.ino || before.size !== observed.size ||
          before.mtimeNs !== observed.mtimeNs || before.ctimeNs !== observed.ctimeNs) {
        throw new Error('Manifest file changed')
      }
    }
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } finally {
    closeSync(fd)
  }
}

function requireUniqueKeys(raw: string): void {
  // JSON.parse has already checked syntax. Inspect only nesting and decoded object keys
  // because JSON.parse would otherwise keep the last occurrence of a repeated key.
  const objects: Set<string>[] = []
  for (const [token, quoted, colon] of raw.matchAll(/("(?:[^"\\]|\\.)*")([ \t\r\n]*:)?|[{}]/gu)) {
    if (token === '{') {
      objects.push(new Set())
    } else if (token === '}') {
      objects.pop()
    } else if (colon !== undefined) {
      const key = JSON.parse(quoted!) as string
      const keys = objects.at(-1)!
      if (keys.has(key)) throw new Error('Duplicate manifest key')
      keys.add(key)
    }
  }
}

try {
  const [path, ...extra] = process.argv.slice(2)
  if (!path || extra.length) throw new Error('Expected one manifest file')
  const raw = readManifest(path)
  const value: unknown = JSON.parse(raw)
  requireUniqueKeys(raw)
  parseReleaseManifest(value)
  console.log('Valid release manifest')
} catch {
  console.error('Invalid release manifest or input path')
  process.exitCode = 2
}
