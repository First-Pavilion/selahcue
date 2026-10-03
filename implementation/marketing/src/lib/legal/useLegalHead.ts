import { onBeforeUnmount, watchEffect } from 'vue'
import { LegalHead, type HeadClaim } from './head.ts'

let shared: LegalHead | null = null

/** One `LegalHead` per document; created lazily so SSR/test imports never touch `document`. */
function head(): LegalHead {
  shared ??= new LegalHead(document as unknown as ConstructorParameters<typeof LegalHead>[0])
  return shared
}

/** Forget the shared head (tests give each render its own fake document). */
export function resetLegalHead(): void {
  shared = null
}

/**
 * Set `document.title` and, while `noindex()` is true, the robots `noindex` tag for the
 * lifetime of the calling page. Reactive: when `noindex()` flips (it is derived from
 * `legalPageState`, document.ts: placeholders, the DRAFT banner, or a version status other
 * than `final`) the tag follows. See `head.ts` for why this is claim-based.
 */
export function useLegalHead(title: () => string, noindex: () => boolean): void {
  if (typeof document === 'undefined') return
  let claim: HeadClaim | null = null
  watchEffect(() => {
    const next = { title: title(), noindex: noindex() }
    if (claim) claim.update(next)
    else claim = head().claim(next)
  })
  onBeforeUnmount(() => {
    claim?.release()
    claim = null
  })
}
