<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isProbablySignedIn, signOut } from '@/lib/auth/sessionStore.ts'
import { pageScrollLock } from '@/lib/ui/scrollLock.ts'
import { FOCUSABLE_SELECTOR, nextTrapIndex } from '@/lib/ui/focusTrap.ts'
import { MOBILE_QUERY } from '@/lib/ui/breakpoints.ts'

const router = useRouter()
const route = useRoute()

const isScrolled = ref(false)
const isMobileMenuOpen = ref(false)

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

const handleScroll = () => {
  isScrolled.value = window.scrollY > 10
}

/**
 * THE MOBILE SHEET (< 768px).
 *
 * Four things have to be true at once, and each has a way of quietly not being:
 *
 *  1. Focus MOVES INTO the sheet on open, is TRAPPED there (Tab / Shift+Tab wrap), and
 *     RETURNS to the hamburger on close. A sheet that leaves focus on a button now hidden
 *     behind a scrim strands keyboard and switch users.
 *  2. Escape closes it.
 *  3. The page behind does not scroll while it is open -- and scrolling is ALWAYS given
 *     back. The lock is taken in `openMobileMenu` and dropped in `closeMobileMenu`, and
 *     `closeMobileMenu` is the ONLY thing that closes: a link tap, the scrim, Escape, the
 *     close button, a route change, a viewport that grows past the breakpoint and unmount
 *     all go through it, so there is no path that closes the sheet and forgets the lock.
 *     (`pageScrollLock` is reference-counted and its release idempotent, so calling this
 *     twice is harmless.)
 *  4. It is a real modal for assistive tech: `role="dialog" aria-modal="true"`, and the
 *     hamburger carries `aria-expanded` / `aria-controls`.
 */
let releaseScrollLock: (() => void) | null = null

const openMobileMenu = () => {
  if (isMobileMenuOpen.value) return
  isMobileMenuOpen.value = true
  releaseScrollLock = pageScrollLock.acquire()
  void nextTick(() => closeEl.value?.focus())
}

const closeMobileMenu = ({ restoreFocus = true }: { restoreFocus?: boolean } = {}) => {
  releaseScrollLock?.()
  releaseScrollLock = null
  if (!isMobileMenuOpen.value) return
  isMobileMenuOpen.value = false
  if (restoreFocus) void nextTick(() => toggleEl.value?.focus())
}

const toggleMobileMenu = () => {
  if (isMobileMenuOpen.value) closeMobileMenu()
  else openMobileMenu()
}

const handleSheetKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeMobileMenu()
    return
  }
  if (event.key !== 'Tab' || !sheetEl.value) return
  const focusable = Array.from(sheetEl.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
  const target = nextTrapIndex(focusable.length, focusable.indexOf(document.activeElement as HTMLElement), event.shiftKey)
  event.preventDefault()
  if (target !== null) focusable[target]?.focus()
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
  window.addEventListener('scroll', handleScroll, { passive: true })
  window.addEventListener('pagehide', handlePageHide)
  mobileQuery = window.matchMedia(MOBILE_QUERY)
  mobileQuery.addEventListener('change', handleBreakpointChange)
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handleScroll)
  window.removeEventListener('pagehide', handlePageHide)
  mobileQuery?.removeEventListener('change', handleBreakpointChange)
  mobileQuery = null
  closeMobileMenu({ restoreFocus: false })
})
</script>

<template>
  <header :class="['navbar-header', { 'is-scrolled': isScrolled }]">
    <div class="navbar-container">
      <!-- Left Group: Brand Logo + Nav Links -->
      <div class="left-group">
        <router-link to="/" class="brand">
          <img src="/selahcue-logo.png" alt="SelahCue Logo" class="brand-logo" />
          <span class="brand-wordmark">SelahCue</span>
        </router-link>

        <nav class="desktop-nav" aria-label="Primary">
          <router-link to="/features" class="nav-item" active-class="active">Features</router-link>
          <a href="#how-it-works" class="nav-item">How it works</a>
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
        <router-link to="/download" class="download-cta">Download free</router-link>
      </div>

      <!-- Mobile Hamburger Toggle (< 768px) -->
      <button
        ref="toggleEl"
        type="button"
        class="mobile-toggle"
        :aria-expanded="isMobileMenuOpen"
        aria-controls="mobile-nav-sheet"
        aria-haspopup="dialog"
        :aria-label="isMobileMenuOpen ? 'Close menu' : 'Open menu'"
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
       clipped to the 68px bar instead of covering the viewport. -->
  <Teleport to="body">
    <Transition name="nav-sheet">
      <div v-if="isMobileMenuOpen" class="mobile-layer" @keydown="handleSheetKeydown">
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
            <a href="#how-it-works" class="mobile-link" @click="closeMobileMenu()">How it works</a>
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
.navbar-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #090a0f;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  transition: background 0.2s ease, backdrop-filter 0.2s ease;
}

.navbar-header.is-scrolled {
  background: rgba(9, 10, 15, 0.9);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.navbar-container {
  max-width: 1240px;
  margin: 0 auto;
  /* The bar keeps 24px through tablet (denser than the page gutter on purpose: the
     signed-in state -- Account, Sign out, CTA -- only fits 768px at 24) and 20px on mobile. */
  padding: 0 24px;
  height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Left Group */
.left-group {
  display: flex;
  align-items: center;
  gap: 44px;
  min-width: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  /* 44px: the touch target is the whole lockup, not just the glyphs. */
  min-height: 44px;
}

.brand-logo {
  height: 24px;
  width: auto;
}

.brand-wordmark {
  font-size: 19px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.01em;
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
  color: #9aa4b2;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.15s ease;
}

.nav-item:hover,
.nav-item.active {
  color: #ffffff;
}

/* Right Group */
.right-group {
  display: none;
  align-items: center;
  gap: 24px;
}

.signin-btn {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  color: #9aa4b2;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.15s ease;
}

.signin-btn:hover {
  color: #ffffff;
}

/* Matches `.signin-btn`'s ink and weight so the pair reads as one control group, but it
   is a real <button> because it performs an action rather than navigating. */
.signout-btn {
  background: none;
  border: none;
  padding: 0;
  min-height: 44px;
  color: #9aa4b2;
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s ease;
}

.signout-btn:hover:not(:disabled) {
  color: #ffffff;
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

.download-cta {
  display: inline-flex;
  align-items: center;
  background: #5b6bd6;
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  padding: 9px 20px;
  border-radius: 999px;
  text-decoration: none;
  white-space: nowrap;
  transition: background 0.15s ease, transform 0.15s ease;
}

.download-cta:hover {
  background: #4f5ec7;
}

.download-cta:active {
  transform: scale(0.98);
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

.mobile-toggle:focus-visible,
.sheet-close:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
}

.hamburger {
  width: 22px;
  height: 2px;
  background: #ffffff;
  position: relative;
}

.hamburger::before,
.hamburger::after {
  content: '';
  position: absolute;
  left: 0;
  width: 100%;
  height: 2px;
  background: #ffffff;
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

@media (max-width: 767px) {
  .navbar-container { padding: 0 20px; }
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

@media (min-width: 768px) and (max-width: 1199px) {
  .left-group { gap: 20px; margin-right: 16px; }
  .desktop-nav { gap: 12px; }
  .right-group { gap: 12px; }
  .nav-item, .signin-btn, .signout-btn { font-size: 13.5px; }
  .download-cta { padding: 9px 14px; font-size: 13.5px; }
}

/* Coarse pointers above the breakpoint (tablets) get the 44px target on the CTA too;
   a fine pointer keeps the designed 38px pill, so the desktop is visually unchanged. */
@media (min-width: 768px) and (pointer: coarse) {
  .download-cta { min-height: 44px; }
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
