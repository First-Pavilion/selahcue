/**
 * The Account page's load and deactivate logic (ClickUp 17tnw2bhkd2), out of the view so it runs
 * under `node --test` against a failing transport.
 *
 * Failure rules:
 *   - the three codes `confirmSession` reads as "no session" (UNAUTHENTICATED, PERMISSION_DENIED,
 *     NOT_FOUND) end the visit: the hint is dropped and the visitor goes to sign-in. Retrying can
 *     never fix those, so they are never shown as "check your connection".
 *   - except where a stale list could be the cause (a computer that is already gone answers
 *     NOT_FOUND; PERMISSION_DENIED can mean the role changed): there the server is asked whether the
 *     session is really over (`confirmSession`) and only then is the visitor signed out. A working
 *     user is never sent to sign-in because of an out-of-date list. UNAUTHENTICATED on deactivate
 *     signs out directly.
 *   - a computer already gone (NOT_FOUND on deactivate) counts as deactivated.
 *   - anything else is an error state the visitor can retry. A cancelled request is no failure.
 *   - the API's own messages are never rendered.
 */
import { ref } from 'vue'

import { ApiError, type GraphQLRequestOptions } from './api/graphql.ts'
import type { AccountOverview } from './api/account.ts'
import { deviceLabel } from './accountDisplay.ts'

export const LOAD_FAILED = "We couldn't load your account. Check your connection and try again."
export const DEACTIVATE_FAILED = 'We could not deactivate that computer. Please try again.'
export const LOAD_MORE_FAILED = "Couldn't load more computers. Try again."

const SESSION_ENDED_CODES = ['UNAUTHENTICATED', 'PERMISSION_DENIED', 'NOT_FOUND']

export function isSessionEnded(error: unknown): boolean {
  return error instanceof ApiError && SESSION_ENDED_CODES.includes(error.code)
}

export interface AccountPageDeps {
  fetchOverview: (first?: number, after?: string, options?: GraphQLRequestOptions) => Promise<AccountOverview>
  deactivate: (devicePublicId: string, requestId: string) => Promise<{ alreadyInactive: boolean }>
  /** Drop the session hint and go to sign-in (the same as the route guard does). */
  onSessionEnded: () => void
  /** Ask the server whether the session is really over (`confirmSession`). */
  confirmSession: () => Promise<'live' | 'ended' | 'unreachable'>
  newRequestId: () => string
}

const PAGE = 20
const MAX_PAGE = 100

export function createAccountPageFlow(deps: AccountPageDeps) {
  const status = ref<'loading' | 'ready' | 'error'>('loading')
  const overview = ref<AccountOverview | null>(null)
  const loadingMore = ref(false)
  const loadMoreError = ref('')
  const confirmingId = ref('')
  const deactivatingId = ref('')
  const deactivateError = ref('')
  const notice = ref('')
  let controller: AbortController | null = null
  let moreController: AbortController | null = null
  // One request id per computer per attempt: a retry after a timeout must converge on the first request.
  const requestIds = new Map<string, string>()

  async function load(quiet = false, first?: number): Promise<void> {
    controller?.abort()
    const mine = new AbortController()
    controller = mine
    if (!quiet) status.value = 'loading'
    try {
      const next = await deps.fetchOverview(first, undefined, { signal: mine.signal })
      if (mine.signal.aborted) return
      const before = overview.value
      // Keep devices loaded beyond what one request can return (the server caps a page at 100).
      overview.value =
        quiet && before && before.devices.nodes.length > MAX_PAGE ? { ...next, devices: before.devices } : next
      status.value = 'ready'
    } catch (error) {
      if (mine.signal.aborted) return
      if (isSessionEnded(error)) return deps.onSessionEnded()
      // A failed quiet refresh leaves what the visitor already sees.
      if (quiet && overview.value) return
      status.value = 'error'
    }
  }

  const reloadSize = () =>
    Math.min(MAX_PAGE, Math.max(PAGE, overview.value?.devices.nodes.length ?? PAGE))

  /** True when the server confirms the session is over (and the visitor has been sent to sign-in). */
  async function endedAfterCheck(signal?: AbortSignal): Promise<boolean> {
    const check = await deps.confirmSession()
    if (signal?.aborted) return false
    if (check !== 'ended') return false
    deps.onSessionEnded()
    return true
  }

  async function loadMore(): Promise<void> {
    const current = overview.value
    const cursor = current?.devices.nextCursor
    if (!current || !cursor || loadingMore.value) return
    moreController?.abort()
    const mine = new AbortController()
    moreController = mine
    loadingMore.value = true
    loadMoreError.value = ''
    try {
      const page = await deps.fetchOverview(undefined, cursor, { signal: mine.signal })
      if (mine.signal.aborted) return
      current.devices = {
        nodes: [...current.devices.nodes, ...page.devices.nodes],
        nextCursor: page.devices.nextCursor,
      }
    } catch (error) {
      // A late answer after the visitor left must not redirect or write state.
      if (mine.signal.aborted) return
      // A stale cursor can fail like a signed-out request: ask before signing anyone out.
      if (isSessionEnded(error) && (await endedAfterCheck(mine.signal))) return
      if (mine.signal.aborted) return
      loadMoreError.value = LOAD_MORE_FAILED
      if (isSessionEnded(error)) await load(true, reloadSize())
    } finally {
      loadingMore.value = false
    }
  }

  function askDeactivate(id: string): void {
    deactivateError.value = ''
    notice.value = ''
    confirmingId.value = id
  }

  function cancelDeactivate(): void {
    confirmingId.value = ''
  }

  async function confirmDeactivate(id: string): Promise<void> {
    if (deactivatingId.value !== '') return
    deactivatingId.value = id
    deactivateError.value = ''
    let requestId = requestIds.get(id)
    if (requestId === undefined) {
      requestId = deps.newRequestId()
      requestIds.set(id, requestId)
    }
    try {
      await deps.deactivate(id, requestId)
    } catch (error) {
      const code = error instanceof ApiError ? error.code : ''
      // NOT_FOUND: the computer is already gone, which is what was asked for. Fall through as success.
      if (code !== 'NOT_FOUND') {
        confirmingId.value = ''
        deactivatingId.value = ''
        if (code === 'UNAUTHENTICATED') return deps.onSessionEnded()
        if (code === 'PERMISSION_DENIED' && (await endedAfterCheck())) return
        deactivateError.value = DEACTIVATE_FAILED
        // The list may be stale (role or computers changed): refresh it rather than leave it wrong.
        if (code === 'PERMISSION_DENIED') await load(true, reloadSize())
        return
      }
    }
    requestIds.delete(id)
    confirmingId.value = ''
    const current = overview.value
    const device = current?.devices.nodes.find((d) => d.publicId === id)
    if (device) device.status = 'REVOKED' // never leave a deactivated computer looking active
    notice.value = `${deviceLabel(device ?? { displayName: '', platform: '' })} was deactivated.`
    deactivatingId.value = ''
    const loaded = current?.devices.nodes.length ?? PAGE
    await load(true, Math.min(MAX_PAGE, Math.max(PAGE, loaded)))
  }

  return {
    status,
    overview,
    loadingMore,
    loadMoreError,
    confirmingId,
    deactivatingId,
    deactivateError,
    notice,
    load,
    loadMore,
    askDeactivate,
    cancelDeactivate,
    confirmDeactivate,
    abort: () => {
      controller?.abort()
      moreController?.abort()
    },
  }
}
