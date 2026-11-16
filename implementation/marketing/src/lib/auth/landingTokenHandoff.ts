import { readTokenFromSearch } from './tokenParam.ts'

type LandingName = 'verify' | 'reset'
type Destination = { readonly name?: unknown; readonly fullPath: string }
type LandingHistory = {
  readonly state: unknown
  replaceState(state: unknown, unused: string, url?: string): void
}

export interface LandingRouterHooks {
  beforeEach(handler: (to: Destination, from: Destination) => void): () => void
  afterEach(handler: (to: Destination, from: Destination, failure?: unknown) => void): () => void
  onError(handler: (error: unknown, to: Destination, from: Destination) => void): () => void
}

function landingName(path: string): LandingName | undefined {
  switch (path.toLowerCase()) {
    case '/verify':
    case '/verify/':
      return 'verify'
    case '/reset':
    case '/reset/':
      return 'reset'
  }
  return undefined
}

function cleanLandingHistory(state: unknown): unknown {
  if (state === null || typeof state !== 'object') return state
  const fields = state as Record<string, unknown>
  let cleaned: Record<string, unknown> | undefined
  for (const key of ['back', 'current', 'forward']) {
    const value = fields[key]
    if (typeof value !== 'string' || !Object.hasOwn(fields, key)) continue
    const pathAndSearch = value.split('#', 1)[0] ?? ''
    const queryStart = pathAndSearch.indexOf('?')
    if (queryStart < 0) continue
    const path = pathAndSearch.slice(0, queryStart)
    if (!landingName(path) || readTokenFromSearch(pathAndSearch.slice(queryStart)) === undefined) continue
    cleaned ??= { ...fields }
    cleaned[key] = path
  }
  return cleaned ?? state
}

export function createLandingTokenHandoff() {
  let pending: {
    token: string
    name: LandingName
    path: string
    destination?: Destination
    removePageHide: () => void
    removeRouterHooks?: () => void
  } | undefined

  function discard() {
    const capture = pending
    pending = undefined
    capture?.removePageHide()
    capture?.removeRouterHooks?.()
  }

  function prepare(
    location: Pick<Location, 'pathname' | 'search'>,
    history: LandingHistory,
    page: EventTarget,
  ): void {
    discard()
    const path = location.pathname
    const name = landingName(path)
    if (!name) return

    const token = readTokenFromSearch(location.search)
    const state = history.state
    const cleanedState = cleanLandingHistory(state)
    if (token !== undefined || !Object.is(cleanedState, state)) {
      try {
        history.replaceState(cleanedState, '', token === undefined ? undefined : path)
      } catch {
        throw new Error('Unable to sanitize the auth landing URL')
      }
    }

    if (!token) return
    pending = { token, name, path, removePageHide: () => page.removeEventListener('pagehide', discard) }
    page.addEventListener('pagehide', discard)
  }

  function watchInitialNavigation(router: LandingRouterHooks, start: Destination): void {
    if (!pending) return

    function discardFailure(to: Destination, from: Destination) {
      // Duplicate attempts can fail before beforeEach after the initial route commits.
      if (pending && (!pending.destination || pending.destination === to || pending.destination === from)) discard()
    }

    const removeBefore = router.beforeEach((to, from) => {
      if (!pending) return
      // The installer is the only initiator of the first navigation from START_LOCATION.
      if (pending.destination || from !== start || to.name !== pending.name || to.fullPath !== pending.path) {
        discard()
        return
      }
      pending.destination = to
    })
    const removeAfter = router.afterEach((to, from, failure) => {
      if (failure) discardFailure(to, from)
    })
    const removeError = router.onError((_error, to, from) => discardFailure(to, from))
    pending.removeRouterHooks = () => {
      removeBefore()
      removeAfter()
      removeError()
    }
  }

  function take(destination: Destination): string {
    const capture = pending
    if (!capture || capture.destination !== destination) return ''
    discard()
    return capture.token
  }

  return { prepare, watchInitialNavigation, take }
}

export const landingTokenHandoff = createLandingTokenHandoff()
