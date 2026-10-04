<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isProbablySignedIn, signOut } from '@/lib/auth/sessionStore.ts'
import { pageScrollLock } from '@/lib/ui/scrollLock.ts'
import { pageInertLock } from '@/lib/ui/inertLock.ts'
import { FOCUSABLE_SELECTOR, nextTrapIndex } from '@/lib/ui/focusTrap.ts'
import { MOBILE_QUERY } from '@/lib/ui/breakpoints.ts'
import UiButton from '@/components/UiButton.vue'

const router = useRouter()
const route = useRoute()

const isScrolled = ref(false)
const isMobileMenuOpen = ref(false)

const sentinelEl = ref<HTMLElement | null>(null)
const toggleEl = ref<HTMLButtonElement | null>(null)
const closeEl = ref<HTMLButtonElement | null>(null)
const sheetEl = ref<HTMLElement | null>(null)

const signOutPending = ref(false)
/** Empty when there is nothing to report. Announced, because it is a failed action. */
const signOutError = ref('')

/**
 * Sign out for real, and say so honestly when it does not work.
 *
 * The session cookie is HttpOnly — JavaScript cannot delete it. Only the server can, and
 * it does that by responding to the `logout` mutation. So there is no local "clear it
 * anyway" fallback available here, and pretending otherwise would be the worst thing
 * this component could do: painting "signed out" over a browser that is still carrying a
 * working credential, on a machine that in this product is frequently a shared church
 * office PC. `signOut` rejects when the session survived, and this shows that.
 */
const SIGN_OUT_FAILED = "We couldn't sign you out. Check your connection and try again."

const handleSignOut = async () => {
  if (signOutPending.value) return
  signOutPending.value = true
  signOutError.value = ''

  // ONE call inside the try, for the same reason `SignInView`'s `submit` was rewritten
  // (PR #17, HIGH-1). `await router.push('/')` used to live in here, so a rejected
  // navigation — a lazy route whose chunk a deploy removed, a guard that threw — was
  // reported as "We couldn't sign you out" over a revocation the server had already
  // performed. That message is worse than merely wrong: this product runs on shared
  // church-office machines, and it tells someone their session is still live when it is
  // not, so they stay logged in on purpose. `tests/authViews.test.ts` refuses the shape.
  let revoked = false
  try {
    await signOut()
    revoked = true
  } catch {
    signOutError.value = SIGN_OUT_FAILED
  } finally {
    signOutPending.value = false
  }
  if (!revoked) return

  // ---- the session is GONE. Nothing below may suggest otherwise. ----
  closeMobileMenu({ restoreFocus: false })
  try {
    await router.push('/')
  } catch {
    // The revocation succeeded and only the navigation failed. A full document load is
    // both the honest outcome (they end up signed out, on the home page) and the actual
    // remedy for the usual cause, which is a running page pointing at chunks a deploy
    // has already removed.
    window.location.assign('/')
  }
}

/**
 * THE SCROLLED STATE. Observed, not read: an IntersectionObserver watches a 10px sentinel at the very top of
 * the document, so the bar is "scrolled" exactly when `window.scrollY > 10` (the old rule) without anything
 * reading `scrollY`. Reading it in `onMounted` forced a style and layout pass inside the app's first script
 * task and pushed that task over the 50ms long-task line on Pricing and Terms (+18-20ms of layout at 4x CPU,
 * performance review of PR 172), and a scroll listener fires on every wheel tick. The observer's first
 * callback reports the state the page OPENED in, so a reload in the middle of a page, a cold load onto a
 * deep anchor and back-navigation all start right, and it is delivered with the frame's own work.
 *
 * `handleScroll` is only the fallback for a browser with no IntersectionObserver, which keeps the previous
 * behaviour: a scroll listener, no read at mount.
 */
let scrollObserver: IntersectionObserver | null = null

const handleScroll = () => {
  isScrolled.value = window.scrollY > 10
}

/**
 * THE MOBILE SHEET (< 768px).
 *
 * Five things have to be true at once, and each has a way of quietly not being:
 *
 *  1. Focus MOVES INTO the sheet on open, is TRAPPED there (Tab / Shift+Tab wrap), and
 *     RETURNS to the hamburger on close. A sheet that leaves focus on a button now hidden
 *     behind a scrim strands keyboard and switch users.
 *  2. Escape closes it -- and keeps closing it after the visitor clicks EMPTY space inside
 *     the sheet. That click moves `document.activeElement` to <body>, which is OUTSIDE the
 *     sheet, so a `keydown` handler on the sheet element never hears the next Escape or Tab
 *     (and in WebKit Tab then walks out of the page and never comes back). So the handler is
 *     on `document` for exactly as long as the sheet is open, and is removed by the one
 *     function that closes it.
 *  3. The page behind does not scroll while it is open -- and scrolling is ALWAYS given
 *     back. The lock is taken in `openMobileMenu` and dropped in `closeMobileMenu`, and
 *     `closeMobileMenu` is the ONLY thing that closes: a link tap, the scrim, Escape, the
 *     close button, a route change, a viewport that grows past the breakpoint, `pagehide`
 *     and unmount all go through it, so there is no path that closes the sheet and forgets
 *     the lock. (`pageScrollLock` is reference-counted and its release idempotent and
 *     generation-checked, so calling this twice is harmless.)
 *  4. The page behind is `inert` while it is open (same lifetime as the scroll lock, same
 *     single release point): out of the tab order and the accessibility tree, so neither a
 *     stray Tab nor a screen-reader cursor can reach it. The sheet is teleported to <body>,
 *     outside `#app`, so it stays live.
 *  5. It is a real modal for assistive tech: `role="dialog" aria-modal="true"`, and the
 *     hamburger carries `aria-expanded` / `aria-controls`.
 */
let releaseScrollLock: (() => void) | null = null
let releaseInert: (() => void) | null = null

const handleSheetKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeMobileMenu()
    return
  }
  if (event.key !== 'Tab' || !sheetEl.value) return
  const focusable = Array.from(sheetEl.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
  // `indexOf` is -1 when focus is on <body> (after a click on blank space): the trap then
  // pulls it back in at the matching end instead of letting Tab leave the page.
  const target = nextTrapIndex(focusable.length, focusable.indexOf(document.activeElement as HTMLElement), event.shiftKey)
  event.preventDefault()
  if (target !== null) focusable[target]?.focus()
}

const openMobileMenu = () => {
  if (isMobileMenuOpen.value) return
  isMobileMenuOpen.value = true
  releaseScrollLock = pageScrollLock.acquire()
  releaseInert = pageInertLock.acquire()
  document.addEventListener('keydown', handleSheetKeydown)
  void nextTick(() => closeEl.value?.focus())
}

const closeMobileMenu = ({ restoreFocus = true }: { restoreFocus?: boolean } = {}) => {
  releaseScrollLock?.()
  releaseScrollLock = null
  releaseInert?.()
  releaseInert = null
  document.removeEventListener('keydown', handleSheetKeydown)
  if (!isMobileMenuOpen.value) return
  isMobileMenuOpen.value = false
  if (restoreFocus) void nextTick(() => toggleEl.value?.focus())
}

const toggleMobileMenu = () => {
  if (isMobileMenuOpen.value) closeMobileMenu()
  else openMobileMenu()
}

// Any navigation closes the sheet, including one that did not come from a sheet link
// (back/forward, a programmatic redirect). Focus is left where the new page put it.
watch(
  () => route.fullPath,
  () => closeMobileMenu({ restoreFocus: false }),
)

let mobileQuery: MediaQueryList | null = null
const handleBreakpointChange = (event: MediaQueryListEvent) => {
  // Rotating a tablet or resizing a window past 768px hides the sheet with CSS; without
  // this the lock would stay held under a page that no longer shows a reason for it.
  if (!event.matches) closeMobileMenu({ restoreFocus: false })
}

const handlePageHide = () => closeMobileMenu({ restoreFocus: false })

onMounted(() => {
  if (typeof IntersectionObserver === 'function' && sentinelEl.value) {
    scrollObserver = new IntersectionObserver(([entry]) => {
      isScrolled.value = !(entry?.isIntersecting ?? true)
    })
    scrollObserver.observe(sentinelEl.value)
  } else {
    window.addEventListener('scroll', handleScroll, { passive: true })
  }
  window.addEventListener('pagehide', handlePageHide)
  mobileQuery = window.matchMedia(MOBILE_QUERY)
  mobileQuery.addEventListener('change', handleBreakpointChange)
})

onBeforeUnmount(() => {
  scrollObserver?.disconnect()
  scrollObserver = null
  window.removeEventListener('scroll', handleScroll)
  window.removeEventListener('pagehide', handlePageHide)
  mobileQuery?.removeEventListener('change', handleBreakpointChange)
  mobileQuery = null
  closeMobileMenu({ restoreFocus: false })
})
</script>

<template>
  <!-- Zero-size marker at the top of the document: the bar is "scrolled" when it is out of view (see `scrollObserver`). -->
  <div ref="sentinelEl" class="scroll-sentinel" aria-hidden="true"></div>
  <header :class="['navbar-header', { 'is-scrolled': isScrolled }]">
    <div class="navbar-container">
      <!-- Left Group: Brand Logo + Nav Links -->
      <div class="left-group">
        <router-link to="/" class="brand">
          <!-- The wordmark names the link; the mark is decoration, so it is hidden from assistive tech
               (announcing "SelahCue Logo" and then "SelahCue" said it twice). -->
          <span class="brand-mark"><img src="/selahcue-logo.png" alt="" aria-hidden="true" /></span>
          <span class="brand-wordmark">SelahCue</span>
        </router-link>

        <nav class="desktop-nav" aria-label="Primary">
          <router-link to="/features" class="nav-item" active-class="active">Features</router-link>
          <!-- To the Home route WITH the hash: a bare #how-it-works only works on Home, and on every other
               page it just appended the fragment to the URL. Never "current": the router matches the PATH
               and ignores the hash, so on Home a default router-link carries aria-current="page" (and the
               active class) while sighted users see no active state. `custom` renders the plain <a> below,
               which only navigates. -->
          <router-link :to="{ path: '/', hash: '#how-it-works' }" custom v-slot="{ href, navigate }">
            <a :href="href" class="nav-item" @click="navigate">How it works</a>
          </router-link>
          <router-link to="/pricing" class="nav-item" active-class="active">Pricing</router-link>
          <router-link to="/download" class="nav-item" active-class="active">Download</router-link>
        </nav>
      </div>

      <!-- Right Group: account state + Download Free CTA -->
      <!-- `isProbablySignedIn` is the session HINT, not an authorisation check. It is
           allowed to be wrong here and costs nothing when it is: the worst case is a
           visitor clicking Account and being redirected to sign in by the route guard,
           which asks the server. Waiting for that round trip before painting the navbar
           would flash "Sign in" at every signed-in user on every page load. -->
      <div class="right-group">
        <template v-if="isProbablySignedIn">
          <router-link to="/account" class="signin-btn">Account</router-link>
          <button
            type="button"
            class="signout-btn"
            :disabled="signOutPending"
            @click="handleSignOut"
          >
            {{ signOutPending ? 'Signing out…' : 'Sign out' }}
          </button>
        </template>
        <router-link v-else to="/signin" class="signin-btn">Sign in</router-link>
        <UiButton to="/download" size="compact" class="download-cta">Download free</UiButton>
      </div>

      <!-- Mobile Hamburger Toggle (< 768px) -->
      <button
        ref="toggleEl"
        type="button"
        class="mobile-toggle"
        :aria-expanded="isMobileMenuOpen"
        aria-controls="mobile-nav-sheet"
        aria-haspopup="dialog"
        aria-label="Menu"
        @click="toggleMobileMenu"
      >
        <span class="hamburger" aria-hidden="true"></span>
      </button>
    </div>

    <!-- Announced: a sign-out that silently did nothing is the failure most worth
         hearing about, and the button returns to its resting label either way. While the
         sheet is open the header is behind the scrim, so the same message is rendered
         inside the sheet instead (never both at once). -->
    <p v-if="signOutError && !isMobileMenuOpen" class="signout-error" role="alert">{{ signOutError }}</p>
  </header>

  <!-- Mobile sheet. Teleported to <body> because the header is `backdrop-filter`ed once
       scrolled, and a `backdrop-filter` makes its element the containing block for
       `position: fixed` descendants -- a fixed sheet left inside the header would be
       clipped to the bar instead of covering the viewport. -->
  <Teleport to="body">
    <Transition name="nav-sheet">
      <div v-if="isMobileMenuOpen" class="mobile-layer">
        <div class="mobile-scrim" aria-hidden="true" @click="closeMobileMenu()"></div>
        <div id="mobile-nav-sheet" ref="sheetEl" class="mobile-sheet" role="dialog" aria-modal="true" aria-label="Site menu">
          <div class="sheet-top">
            <span class="sheet-title">Menu</span>
            <button ref="closeEl" type="button" class="sheet-close" aria-label="Close menu" @click="closeMobileMenu()">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </div>

          <nav class="sheet-links" aria-label="Primary">
            <router-link to="/features" class="mobile-link" @click="closeMobileMenu()">Features</router-link>
            <router-link :to="{ path: '/', hash: '#how-it-works' }" custom v-slot="{ href, navigate }">
              <a :href="href" class="mobile-link" @click="navigate($event); closeMobileMenu()">How it works</a>
            </router-link>
            <router-link to="/pricing" class="mobile-link" @click="closeMobileMenu()">Pricing</router-link>
            <router-link to="/download" class="mobile-link" @click="closeMobileMenu()">Download</router-link>
          </nav>

          <div class="mobile-actions">
            <p v-if="signOutError" class="signout-error" role="alert">{{ signOutError }}</p>
            <template v-if="isProbablySignedIn">
              <router-link to="/account" class="mobile-link account-link" @click="closeMobileMenu()">Account</router-link>
              <button
                type="button"
                class="mobile-link signout-row"
                :disabled="signOutPending"
                @click="handleSignOut"
              >
                {{ signOutPending ? 'Signing out…' : 'Sign out' }}
              </button>
            </template>
            <router-link v-else to="/signin" class="mobile-link account-link" @click="closeMobileMenu()">Sign in</router-link>
            <router-link to="/download" class="sheet-cta" @click="closeMobileMenu()">Download free</router-link>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Absolute against the initial containing block (nothing above it is positioned), so it sits at the very top of
   the DOCUMENT and scrolls away with it. 10px tall = the old `scrollY > 10`. Out of flow: no layout effect. */
.scroll-sentinel {
  position: absolute;
  top: 0;
  left: 0;
  width: 1px;
  height: 10px;
  pointer-events: none;
}

.navbar-header {
  position: sticky;
  top: 0;
  z-index: 100;
  /* The page colour with the token border, as Figma draws it (468:126 has no fill of its own). */
  background: var(--sc-base);
  border-bottom: 1px solid var(--sc-border);
  transition: background 0.2s ease, backdrop-filter 0.2s ease;
}

.navbar-header.is-scrolled {
  background: color-mix(in srgb, var(--sc-base) 90%, transparent);
  backdrop-filter: blur(16px);
}

/* The bar is the height token, border included: 79px from 768px up (Figma), 69px on the phone bar.
   Gutters are the --nav-gutter token (48 desktop, 24 tablet, 20 mobile; the bar stays denser than the
   page on purpose: the signed-in state -- Account, Sign out, CTA -- only fits 768px at 24). The 1440
   cap is the design width: past it the content centres instead of stretching edge to edge. */
.navbar-container {
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 var(--nav-gutter);
  height: calc(var(--nav-height) - 1px);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Left Group */
.left-group {
  display: flex;
  align-items: center;
  gap: 40px;
  min-width: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  /* 44px: the touch target is the whole lockup, not just the glyphs. */
  min-height: 44px;
}

/* The 32px mark is `.brand-mark` (main.css), which crops the logo file's transparent padding. */
.brand-wordmark {
  font-size: 19px;
  font-weight: 700;
  color: var(--sc-text);
  letter-spacing: 0;
}

.desktop-nav {
  display: none;
  align-items: center;
  gap: 28px;
}

.nav-item {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  color: var(--sc-text-secondary);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.15s ease;
}

.nav-item:hover {
  color: var(--sc-text);
}

/* The current route: Semi Bold in the primary text colour (Figma 485:125). No underline is drawn in
   any frame; whether it should carry one is a held decision (shared-chrome-11, Uma). */
.nav-item.active {
  color: var(--sc-text);
  font-weight: 600;
}

/* Right Group */
.right-group {
  display: none;
  align-items: center;
  gap: 18px;
}

.signin-btn {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  color: var(--sc-text);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
}

/* Already the brightest ink, so the hover cue cannot be a colour change. */
.signin-btn:hover,
.signout-btn:hover:not(:disabled) {
  text-decoration: underline;
  text-underline-offset: 4px;
}

/* Matches `.signin-btn`'s ink and weight so the pair reads as one control group, but it
   is a real <button> because it performs an action rather than navigating. */
.signout-btn {
  background: none;
  border: none;
  padding: 0;
  min-height: 44px;
  color: var(--sc-text);
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.signout-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.signout-error {
  margin: 0;
  padding: 8px 24px;
  background: var(--sc-live-soft);
  color: var(--sc-text);
  font-size: 13px;
  text-align: center;
}

/* The CTA is a UiButton (primary, compact: 39px, 10px radius, 14/700, brand fill), so the bar carries
   no private copy of the button. Only what is the bar's own is here. */
.download-cta {
  white-space: nowrap;
  /* The hover keeps the value this button had (#4f5ec7, 5.59:1 with the white label). UiButton's own
     primary hover (--sc-primary-hover) is 3.78:1 and so is not used here. Which hover every primary
     gets is a decision for Uma (shared-chrome-31); until then this value is kept, by name. */
  --nav-cta-hover: #4f5ec7;
}

.download-cta.variant-primary:hover {
  background: var(--nav-cta-hover);
}

/* Mobile Toggle: 44x44, the minimum touch target. */
.mobile-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin-right: -10px; /* optically align the bars with the page gutter */
  background: none;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.brand:focus-visible,
.nav-item:focus-visible,
.signin-btn:focus-visible,
.signout-btn:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
  border-radius: 6px;
}

.mobile-toggle:focus-visible,
.sheet-close:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
}

.hamburger {
  width: 22px;
  height: 2px;
  background: var(--sc-text);
  position: relative;
}

.hamburger::before,
.hamburger::after {
  content: '';
  position: absolute;
  left: 0;
  width: 100%;
  height: 2px;
  background: var(--sc-text);
}

.hamburger::before { top: -6px; }
.hamburger::after { bottom: -6px; }

/* ---- Mobile sheet ------------------------------------------------------------------
   Slides in from the right (design 8b): --sc-surface, full viewport height, scrim behind
   it. It only exists below 768px; the v-if never renders it above that, and the media
   rule below is the belt to that pair of braces for a resize mid-open. */
.mobile-layer {
  position: fixed;
  inset: 0;
  z-index: 200;
}

.mobile-scrim {
  position: absolute;
  inset: 0;
  background: rgba(5, 6, 10, 0.72);
}

.mobile-sheet {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(86vw, 360px);
  display: flex;
  flex-direction: column;
  background: var(--sc-surface);
  border-left: 1px solid var(--sc-border);
  box-shadow: -24px 0 60px rgba(0, 0, 0, 0.5);
  padding: 0 20px;
  padding-bottom: max(24px, env(safe-area-inset-bottom));
  overflow-y: auto;
  overscroll-behavior: contain;
}

.sheet-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 68px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--sc-border);
}

.sheet-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--sc-text-secondary);
}

.sheet-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin-right: -10px;
  background: none;
  border: none;
  border-radius: 8px;
  color: var(--sc-text);
  cursor: pointer;
}

.sheet-links {
  display: flex;
  flex-direction: column;
}

.mobile-link {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 56px;
  padding: 0;
  background: none;
  border: none;
  border-bottom: 1px solid var(--sc-border);
  color: var(--sc-text);
  font-family: inherit;
  font-size: 17px;
  font-weight: 600;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
}

.mobile-link:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: -2px;
}

.mobile-link.router-link-active,
.mobile-link.router-link-exact-active {
  color: var(--sc-primary-hover);
}

.mobile-link:disabled {
  opacity: 0.6;
  cursor: default;
}

.mobile-actions {
  margin-top: auto;
  padding-top: 24px;
  display: flex;
  flex-direction: column;
}

.mobile-actions .signout-error {
  margin-bottom: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  text-align: left;
}

.account-link,
.signout-row {
  color: var(--sc-text-secondary);
  font-weight: 500;
  font-size: 15px;
}

.sheet-cta {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 52px;
  margin-top: 20px;
  border-radius: 999px;
  background: var(--gradient-cta);
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  text-decoration: none;
}

.sheet-cta:focus-visible {
  outline: 2px solid #ffffff;
  outline-offset: 3px;
}

.nav-sheet-enter-active,
.nav-sheet-leave-active {
  transition: opacity 0.2s ease;
}

.nav-sheet-enter-active .mobile-sheet,
.nav-sheet-leave-active .mobile-sheet {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.nav-sheet-enter-from,
.nav-sheet-leave-to {
  opacity: 0;
}

.nav-sheet-enter-from .mobile-sheet,
.nav-sheet-leave-to .mobile-sheet {
  transform: translateX(100%);
}

@media (max-width: 767.98px) {
  .signout-error { padding-inline: 20px; }
}

/* Tablet (768-1199): the same bar, tighter. The CTA keeps its label; what gives is the
   spacing, which is what actually has to give to fit the signed-in state at 768. */
@media (min-width: 768px) {
  .desktop-nav,
  .right-group {
    display: flex;
  }
  .mobile-toggle,
  .mobile-layer {
    display: none;
  }
}

@media (min-width: 768px) and (max-width: 1199.98px) {
  .left-group { gap: 20px; margin-right: 16px; }
  .desktop-nav { gap: 12px; }
  .right-group { gap: 12px; }
  .nav-item, .signin-btn, .signout-btn { font-size: 13.5px; }
  .download-cta.size-compact { padding-inline: 14px; font-size: 13.5px; }
}

@media (prefers-reduced-motion: reduce) {
  .nav-sheet-enter-active,
  .nav-sheet-leave-active,
  .nav-sheet-enter-active .mobile-sheet,
  .nav-sheet-leave-active .mobile-sheet {
    transition: none;
  }
}
</style>
