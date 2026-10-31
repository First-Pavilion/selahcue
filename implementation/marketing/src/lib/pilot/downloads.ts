/** Public nonsecret presentation configuration; never an authorization boundary.
 * Only the n8n form is navigable here. P13/P12 enforce persistence/receipts/grants server-side.
 */
export const platforms = ['Windows', 'Ubuntu', 'macOS'] as const
export type Platform = typeof platforms[number]
export const architectures = ['x64', 'arm64'] as const
export type Architecture = typeof architectures[number]
export interface PilotEntry {
  platform: Platform
  architecture: Architecture
  version: string
  release_id: string
  expires_at: string
  available: boolean
  registration_url: string
}
export interface PilotNotice {
  approved: true
  version: string
  url: string
  data_owner: string
  retention_days: number
}
export interface PilotConfig {
  enabled: boolean
  notice?: PilotNotice
  entries: PilotEntry[]
}
const invalid = (): never => { throw new Error('Pilot download configuration is not ready.') }
function record(value: unknown, keys: string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid()
  const row = value as Record<string, unknown>
  if (Object.keys(row).some(key => !keys.includes(key))) return invalid()
  return row
}
function text(value: unknown, max = 160): string {
  if (typeof value !== 'string' || !value.trim() || value !== value.trim() || value.length > max || [...value].some(char => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127)) return invalid()
  return value
}
function https(value: unknown): URL {
  const url = new URL(text(value, 2048))
  if (url.protocol !== 'https:' || url.username || url.password || url.hash) return invalid()
  return url
}
function utc(value: unknown): string {
  const date = text(value)
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(date) || !Number.isFinite(Date.parse(date)) || new Date(date).toISOString() !== date.replace('Z', '.000Z')) return invalid()
  return date
}
export function parsePilotConfig(value: unknown): PilotConfig {
  const root = record(value, ['schema_version', 'enabled', 'form_origin', 'notice', 'entries'])
  if (root.schema_version !== 1 || typeof root.enabled !== 'boolean') return invalid()
  if (!root.enabled) return { enabled: false, entries: [] }
  const origin = https(root.form_origin)
  if (origin.href !== origin.origin + '/') return invalid()
  const n = record(root.notice, ['approved', 'version', 'url', 'data_owner', 'retention_days'])
  const version = text(n.version)
  if (n.approved !== true || /draft|placeholder|pending/i.test(version) || !Number.isSafeInteger(n.retention_days) || Number(n.retention_days) < 1 || Number(n.retention_days) > 3650) return invalid()
  const notice: PilotNotice = { approved: true, version, url: https(n.url).href, data_owner: text(n.data_owner), retention_days: Number(n.retention_days) }
  if (!Array.isArray(root.entries) || root.entries.length > 6) return invalid()
  const seen = new Set<string>()
  const entries = root.entries.map((item): PilotEntry => {
    const entry = record(item, ['platform', 'architecture', 'version', 'release_id', 'expires_at', 'available', 'registration_url'])
    if (!platforms.includes(entry.platform as Platform) || !architectures.includes(entry.architecture as Architecture) || typeof entry.available !== 'boolean') return invalid()
    const key = `${entry.platform}:${entry.architecture}`
    if (seen.has(key)) return invalid()
    seen.add(key)
    const url = https(entry.registration_url)
    // Complete opaque production n8n form URL supplied by deployment, without invented
    // platform/release/receipt query parameters. The hosted form confirms the selection.
    if (url.origin !== origin.origin || !/^\/form\/[a-zA-Z0-9_-]+$/.test(url.pathname) || url.search) return invalid()
    return { platform: entry.platform as Platform, architecture: entry.architecture as Architecture, version: text(entry.version), release_id: text(entry.release_id), expires_at: utc(entry.expires_at), available: entry.available, registration_url: url.href }
  })
  return { enabled: true, notice, entries }
}
export function pilotEntryState(config: PilotConfig, platform: Platform, architecture: Architecture, now: number): { status: 'ready' | 'expired' | 'unavailable'; entry?: PilotEntry; url?: string } {
  const entry = config.entries.find(item => item.platform === platform && item.architecture === architecture)
  if (!config.enabled || !entry || !entry.available) return { status: 'unavailable', entry }
  if (!Number.isFinite(now) || now >= Date.parse(entry.expires_at)) return { status: 'expired', entry }
  return { status: 'ready', entry, url: entry.registration_url }
}
export async function loadPilotConfig(fetcher: typeof fetch = fetch, signal?: AbortSignal): Promise<PilotConfig> {
  const timeout = AbortSignal.timeout(10000)
  const response = await fetcher('/pilot-downloads.json', { cache: 'no-store', credentials: 'omit', redirect: 'error', signal: signal ? AbortSignal.any([signal, timeout]) : timeout })
  if (!response.ok || response.headers.get('Content-Type')?.split(';')[0]?.trim().toLowerCase() !== 'application/json') return invalid()
  // Bound streamed input too: a misleading/missing Content-Length must not bypass the limit.
  const reader = response.body?.getReader()
  if (!reader) return invalid()
  const chunks: Uint8Array[] = []
  let size = 0
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      size += value.length
      if (size > 32768) { await reader.cancel(); return invalid() }
      chunks.push(value)
    }
  } finally { reader.releaseLock() }
  const bytes = new Uint8Array(size)
  let offset = 0
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length }
  return parsePilotConfig(JSON.parse(new TextDecoder().decode(bytes)))
}

const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
/** Retry identity only, never a registration receipt or download authorization. */
export function registrationIdentity(storage: Pick<Storage, 'getItem' | 'setItem'>, attempt: string, generate: () => string, reset = false): string {
  const key = `selahcue-pilot-attempt:${attempt}`
  const existing = storage.getItem(key)
  if (existing !== null && !reset) {
    if (!uuidV4.test(existing)) return invalid()
    return existing
  }
  const id = generate()
  if (!uuidV4.test(id)) return invalid()
  storage.setItem(key, id)
  return id
}
export function registrationLink(base: string, platform: Platform, id: string): string {
  if (!uuidV4.test(id) || !platforms.includes(platform)) return invalid()
  const url = https(base)
  if (!/^\/form\/[a-zA-Z0-9_-]+$/.test(url.pathname) || url.search) return invalid()
  url.searchParams.set('registration_id', id)
  url.searchParams.set('platform', platform)
  return url.href
}
