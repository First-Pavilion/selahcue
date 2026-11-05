/** Public GET wire contract; no commercial defaults or private entitlements. */
export type Interval = 'WEEK' | 'MONTH' | 'YEAR'
export interface Offer {
  currency: string
  interval: Interval
  price_state: 'priced' | 'unpriced'
  amount_minor: string | null
  minor_unit_exponent: number
}
export interface PublicPlan {
  key: string
  name: string
  price_state: 'priced' | 'unpriced'
  offers: Offer[]
  cloud_transcript_minutes_per_week: number
  sermon_notes_per_week: number
  watermark: boolean
}
const LIMIT = 1024 * 1024
const INTERVALS = ['WEEK', 'MONTH', 'YEAR'] as const
const PERIOD: Record<Interval, string> = { WEEK: 'week', MONTH: 'month', YEAR: 'year' }
const invalid = (): never => { throw new Error('Catalogue unavailable') }
function record(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid()
  const object = value as Record<string, unknown>
  if (Object.keys(object).sort().join(',') !== [...keys].sort().join(',')) return invalid()
  return object
}
function text(value: unknown, max: number): string {
  if (typeof value !== 'string' || !value.trim() || value.length > max) return invalid()
  return value
}
function allowance(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) return invalid()
  return value
}
export function parseCatalogue(value: unknown): PublicPlan[] {
  const root = record(value, ['plans'])
  if (!Array.isArray(root.plans) || root.plans.length > 64) return invalid()
  const keys = new Set<string>()
  return root.plans.map(value => {
    const plan = record(value, ['key', 'name', 'price_state', 'offers', 'cloud_transcript_minutes_per_week', 'sermon_notes_per_week', 'watermark'])
    const key = text(plan.key, 128)
    if (keys.has(key)) return invalid()
    keys.add(key)
    if (!Array.isArray(plan.offers) || plan.offers.length > 128) return invalid()
    const pairs = new Set<string>()
    const offers = plan.offers.map(value => {
      const offer = record(value, ['currency', 'interval', 'price_state', 'amount_minor', 'minor_unit_exponent'])
      if (typeof offer.currency !== 'string' || !/^[A-Z]{3}$/.test(offer.currency) ||
          !INTERVALS.includes(offer.interval as Interval) ||
          !Number.isInteger(offer.minor_unit_exponent) || (offer.minor_unit_exponent as number) < 0 || (offer.minor_unit_exponent as number) > 4) return invalid()
      const pair = `${offer.currency}/${offer.interval}`
      if (pairs.has(pair)) return invalid()
      pairs.add(pair)
      if (offer.price_state === 'unpriced') {
        if (offer.amount_minor !== null) return invalid()
      } else if (offer.price_state === 'priced') {
        if (typeof offer.amount_minor !== 'string' || !/^(0|[1-9][0-9]{0,18})$/.test(offer.amount_minor) || BigInt(offer.amount_minor) > 9223372036854775807n) return invalid()
      } else return invalid()
      return { ...offer } as unknown as Offer
    })
    const expected = offers.some(offer => offer.price_state === 'priced') ? 'priced' : 'unpriced'
    if (plan.price_state !== expected || typeof plan.watermark !== 'boolean') return invalid()
    return {
      key, name: text(plan.name, 256), price_state: expected, offers,
      cloud_transcript_minutes_per_week: allowance(plan.cloud_transcript_minutes_per_week),
      sermon_notes_per_week: allowance(plan.sermon_notes_per_week), watermark: plan.watermark,
    }
  })
}
/** Insert the decimal point as text: Number would round signed64-bit API amounts. */
export function offerText(offer: Offer): string {
  if (offer.amount_minor === null) return `${offer.currency} / ${PERIOD[offer.interval]}: Price not announced yet`
  const digits = offer.amount_minor.padStart(offer.minor_unit_exponent + 1, '0')
  const point = digits.length - offer.minor_unit_exponent
  const amount = offer.minor_unit_exponent ? `${digits.slice(0, point)}.${digits.slice(point)}` : digits
  return `${offer.currency} ${amount} / ${PERIOD[offer.interval]}`
}
export function planFeatures(plan: PublicPlan): string[] {
  return [
    `${plan.cloud_transcript_minutes_per_week} cloud transcript minutes per week`,
    `${plan.sermon_notes_per_week} sermon notes per week`,
    plan.watermark ? 'Watermark included' : 'No watermark',
  ]
}
export function intervalOptions(plans: PublicPlan[]): { value: string, label: string }[] {
  // A single offer, or several currencies for one interval, does not invent a billing switch.
  const multiple = plans.some(plan => new Set(plan.offers.filter(offer => offer.price_state === 'priced').map(offer => offer.interval)).size > 1)
  if (!multiple) return []
  return [{ value: '', label: 'All intervals' }, ...INTERVALS.filter(interval => plans.some(plan => plan.offers.some(offer => offer.interval === interval)))
    .map(interval => ({ value: interval, label: `Per ${PERIOD[interval]}` }))]
}
/** Fresh same-origin data; bounded streamed bytes, no cookies or persistent stale cache. */
export async function fetchCatalogue(signal: AbortSignal): Promise<PublicPlan[]> {
  const response = await fetch('/v1/catalogue/plans', { method: 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error', headers: { Accept: 'application/json' }, signal })
  if (!response.ok || response.headers.get('content-type')?.split(';')[0]?.trim().toLowerCase() !== 'application/json' || !response.body) {
    await response.body?.cancel()
    return invalid()
  }
  const reader = response.body.getReader()
  const chunks: Uint8Array[] = []
  let size = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      size += value.byteLength
      if (size > LIMIT) { await reader.cancel(); return invalid() }
      chunks.push(value)
    }
  } finally { reader.releaseLock() }
  const bytes = new Uint8Array(size)
  let at = 0
  for (const chunk of chunks) { bytes.set(chunk, at); at += chunk.byteLength }
  return parseCatalogue(JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)))
}
