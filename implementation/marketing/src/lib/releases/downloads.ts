/** Public installer presentation data. Artifact provenance is checked by the release publisher. */
const targets = ['windows-x64', 'macos-arm64', 'macos-x64', 'ubuntu-24.04-x64'] as const
const architectures = ['x64', 'arm64'] as const
const appSignatures = ['unsigned', 'ad_hoc', 'verified', 'not_applicable'] as const
const packageSignatures = ['unsigned', 'verified'] as const
const notarizations = ['not_notarized', 'verified', 'not_applicable'] as const
const origin = 'https://selahcue-installers.sfo3.digitaloceanspaces.com'
const maxBytes = 64 * 1024

export type ReleaseTarget = typeof targets[number]
export type ReleaseArchitecture = typeof architectures[number]
export type AppSignature = typeof appSignatures[number]
export type PackageSignature = typeof packageSignatures[number]
export type Notarization = typeof notarizations[number]

export interface ReleaseArtifact {
  target: ReleaseTarget
  architectures: ReleaseArchitecture[]
  url: string
  filename: string
  size_bytes: number
  sha256: string
  app_signature: AppSignature
  package_signature: PackageSignature
  notarization: Notarization
  publisher: string | null
}

export type ReleaseManifest =
  | { schema_version: 1; status: 'unpublished'; artifacts: [] }
  | {
    schema_version: 1
    status: 'published'
    release_id: string
    version: string
    source_commit: string
    artifacts: [ReleaseArtifact, ReleaseArtifact, ReleaseArtifact, ReleaseArtifact]
  }

function invalid(): never {
  throw new Error('Installer availability could not be verified.')
}

function record(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return invalid()
  if (Object.keys(value).length !== keys.length || keys.some((key) => !Object.hasOwn(value, key))) return invalid()
  return value as Record<string, unknown>
}

function hasControlCharacters(value: string): boolean {
  for (const character of value) {
    const code = character.charCodeAt(0)
    if (code < 32 || (code >= 127 && code <= 159)) return true
  }
  return false
}

function text(value: unknown): string {
  if (typeof value !== 'string' || !value || value.length > maxBytes ||
      value.trim() !== value || hasControlCharacters(value)) return invalid()
  return value
}

function enumValue<T extends string>(value: unknown, choices: readonly T[]): T {
  const match = choices.find((choice) => value === choice)
  return match ?? invalid()
}

function hex(value: unknown, length: number): string {
  if (typeof value !== 'string' || value.length !== length || /[^0-9a-f]/u.test(value)) return invalid()
  return value
}

function isObjectSegment(value: string): boolean {
  return value !== '' && value !== '.' && value !== '..' && !/[/\\]/u.test(value) && !hasControlCharacters(value)
}

function objectUrl(value: unknown, version: string, digest: string, filename: string): string {
  const raw = text(value)
  if (!raw.startsWith(origin + '/') || /[?#\s\\]/u.test(raw)) return invalid()
  let parts: string[]
  try {
    // Check the raw path before URL parsing can silently remove dot segments.
    parts = raw.slice(origin.length + 1).split('/').map(decodeURIComponent)
  } catch {
    return invalid()
  }
  if (!parts.every(isObjectSegment) || parts.pop() !== filename ||
      !parts.includes(version) || !parts.includes(digest) || new URL(raw).href !== raw) return invalid()
  return raw
}

function parseArtifact(value: unknown, version: string): ReleaseArtifact {
  const row = record(value, [
    'target', 'architectures', 'url', 'filename', 'size_bytes', 'sha256',
    'app_signature', 'package_signature', 'notarization', 'publisher',
  ])
  const target = enumValue(row.target, targets)
  const isMac = target.startsWith('macos-')
  const slices = row.architectures
  if (!Array.isArray(slices) || slices.length < 1 || slices.length > (isMac ? 2 : 1)) return invalid()
  const actualSlices = Array.from(slices, (slice: unknown) => enumValue(slice, architectures))
  if (new Set(actualSlices).size !== actualSlices.length ||
      !actualSlices.includes(target === 'macos-arm64' ? 'arm64' : 'x64')) return invalid()

  const filename = text(row.filename)
  const size = row.size_bytes
  const sha256 = hex(row.sha256, 64)
  if (!isObjectSegment(filename) || typeof size !== 'number' || !Number.isSafeInteger(size) || size < 1) return invalid()
  const url = objectUrl(row.url, version, sha256, filename)

  const appSignature = enumValue(row.app_signature, appSignatures)
  const packageSignature = enumValue(row.package_signature, packageSignatures)
  const notarization = enumValue(row.notarization, notarizations)
  const publisher = row.publisher === null ? null : text(row.publisher)
  if (isMac) {
    if (appSignature !== 'ad_hoc' || packageSignature !== 'unsigned' || notarization !== 'not_notarized') return invalid()
  } else if (appSignature === 'ad_hoc' || notarization !== 'not_applicable') return invalid()
  const hasVerifiedSigner = appSignature === 'verified' || packageSignature === 'verified'
  if (hasVerifiedSigner !== (publisher !== null)) return invalid()

  return {
    target, architectures: actualSlices, url, filename, size_bytes: size, sha256,
    app_signature: appSignature, package_signature: packageSignature, notarization, publisher,
  }
}

/** A single URL can represent two targets only with identical universal macOS metadata. */
function sameUniversalArtifact(first: ReleaseArtifact, second: ReleaseArtifact): boolean {
  return first.target.startsWith('macos-') && second.target.startsWith('macos-') &&
    first.architectures.length === 2 && second.architectures.length === 2 &&
    first.filename === second.filename && first.size_bytes === second.size_bytes &&
    first.sha256 === second.sha256 && first.app_signature === second.app_signature &&
    first.package_signature === second.package_signature &&
    first.notarization === second.notarization && first.publisher === second.publisher
}

export function parseReleaseManifest(value: unknown): ReleaseManifest {
  const keys = ['schema_version', 'status', 'artifacts']
  if (typeof value === 'object' && value !== null && 'status' in value && value.status === 'unpublished') {
    const root = record(value, keys)
    if (root.schema_version !== 1 || !Array.isArray(root.artifacts) || root.artifacts.length !== 0) return invalid()
    return { schema_version: 1, status: 'unpublished', artifacts: [] }
  }

  const root = record(value, [...keys, 'release_id', 'version', 'source_commit'])
  if (root.schema_version !== 1 || root.status !== 'published' ||
      !Array.isArray(root.artifacts) || root.artifacts.length !== targets.length) return invalid()
  const version = text(root.version)
  const [first, second, third, fourth] = root.artifacts
  const artifacts: Extract<ReleaseManifest, { status: 'published' }>['artifacts'] = [
    parseArtifact(first, version), parseArtifact(second, version),
    parseArtifact(third, version), parseArtifact(fourth, version),
  ]
  if (new Set(artifacts.map((artifact) => artifact.target)).size !== targets.length) return invalid()
  const byObjectKey = new Map<string, ReleaseArtifact>()
  for (const artifact of artifacts) {
    // Validated URLs with different percent-encoding can address the same object.
    const key = decodeURIComponent(artifact.url.slice(origin.length + 1))
    const previous = byObjectKey.get(key)
    if (previous && (previous.url !== artifact.url || !sameUniversalArtifact(previous, artifact))) return invalid()
    byObjectKey.set(key, artifact)
  }

  const manifest: ReleaseManifest = {
    schema_version: 1, status: 'published', release_id: text(root.release_id),
    version, source_commit: hex(root.source_commit, 40), artifacts,
  }
  if (new TextEncoder().encode(JSON.stringify(manifest)).length > maxBytes) return invalid()
  return manifest
}

export function downloadForTarget(manifest: ReleaseManifest, target: ReleaseTarget): ReleaseArtifact | null {
  return manifest.artifacts.find((artifact) => artifact.target === target) ?? null
}

async function readManifest(response: Response, signal: AbortSignal): Promise<ReleaseManifest> {
  const contentType = response.headers.get('Content-Type')?.split(';')[0]?.trim().toLowerCase()
  if (!response.ok || contentType !== 'application/json' || !response.body) {
    void response.body?.cancel().catch(() => {})
    return invalid()
  }
  const reader = response.body.getReader()
  const cancel = () => { void reader.cancel().catch(() => {}) }
  signal.addEventListener('abort', cancel, { once: true })
  const buffer = new Uint8Array(maxBytes)
  let size = 0
  try {
    for (;;) {
      signal.throwIfAborted()
      const { done, value } = await reader.read()
      if (done) break
      if (size + value.length > maxBytes) {
        cancel()
        return invalid()
      }
      buffer.set(value, size)
      size += value.length
    }
    signal.throwIfAborted()
    const body = new TextDecoder('utf-8', { fatal: true }).decode(buffer.subarray(0, size))
    return parseReleaseManifest(JSON.parse(body))
  } finally {
    signal.removeEventListener('abort', cancel)
    reader.releaseLock()
  }
}

export async function loadReleaseManifest(
  fetchImpl: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<ReleaseManifest> {
  const timeout = new AbortController()
  const requestSignal = signal ? AbortSignal.any([signal, timeout.signal]) : timeout.signal
  const timer = setTimeout(() => timeout.abort(), 5000)
  let rejectOnAbort: (() => void) | undefined
  try {
    requestSignal.throwIfAborted()
    const aborted = new Promise<never>((_, reject) => {
      rejectOnAbort = () => reject(requestSignal.reason)
      requestSignal.addEventListener('abort', rejectOnAbort, { once: true })
    })
    const read = async () => {
      const response = await fetchImpl('/releases/current.json', {
        cache: 'no-cache', credentials: 'omit', redirect: 'error', signal: requestSignal,
      })
      requestSignal.throwIfAborted()
      return readManifest(response, requestSignal)
    }
    return await Promise.race([read(), aborted])
  } catch {
    return invalid()
  } finally {
    clearTimeout(timer)
    if (rejectOnAbort) requestSignal.removeEventListener('abort', rejectOnAbort)
  }
}
