<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { isProbablySignedIn, signOut } from '@/lib/auth/sessionStore.ts'

const router = useRouter()

const isScrolled = ref(false)
const isMobileMenuOpen = ref(false)

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
const handleSignOut = async () => {
  if (signOutPending.value) return
  signOutPending.value = true
  signOutError.value = ''
  try {
    await signOut()
    isMobileMenuOpen.value = false
    await router.push('/')
  } catch {
    signOutError.value = "We couldn't sign you out. Check your connection and try again."
  } finally {
    signOutPending.value = false
  }
}

const handleScroll = () => {
  isScrolled.value = window.scrollY > 10
}

const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
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

        <nav class="desktop-nav">
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

      <!-- Mobile Hamburger Toggle -->
      <button class="mobile-toggle" @click="toggleMobileMenu" aria-label="Toggle menu">
        <span class="hamburger"></span>
      </button>
    </div>

    <!-- Mobile Drawer Menu -->
    <div v-if="isMobileMenuOpen" class="mobile-drawer">
      <router-link to="/features" class="mobile-link" @click="toggleMobileMenu">Features</router-link>
      <a href="#how-it-works" class="mobile-link" @click="toggleMobileMenu">How it works</a>
      <router-link to="/pricing" class="mobile-link" @click="toggleMobileMenu">Pricing</router-link>
      <router-link to="/download" class="mobile-link" @click="toggleMobileMenu">Download</router-link>
      <div class="mobile-actions">
        <template v-if="isProbablySignedIn">
          <router-link to="/account" class="signin-btn" @click="toggleMobileMenu">Account</router-link>
          <button
            type="button"
            class="signout-btn"
            :disabled="signOutPending"
            @click="handleSignOut"
          >
            {{ signOutPending ? 'Signing out…' : 'Sign out' }}
          </button>
        </template>
        <router-link v-else to="/signin" class="signin-btn" @click="toggleMobileMenu">Sign in</router-link>
        <router-link to="/download" class="download-cta" @click="toggleMobileMenu">Download free</router-link>
      </div>
    </div>

    <!-- Announced: a sign-out that silently did nothing is the failure most worth
         hearing about, and the button returns to its resting label either way. -->
    <p v-if="signOutError" class="signout-error" role="alert">{{ signOutError }}</p>
  </header>
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
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
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
  padding: 6px 0;
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
  background: #5b6bd6;
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  padding: 9px 20px;
  border-radius: 999px;
  text-decoration: none;
  transition: background 0.15s ease, transform 0.15s ease;
}

.download-cta:hover {
  background: #4f5ec7;
}

.download-cta:active {
  transform: scale(0.98);
}

/* Mobile Toggle */
.mobile-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: none;
  border: none;
  cursor: pointer;
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

/* Mobile Drawer */
.mobile-drawer {
  position: fixed;
  top: 68px;
  left: 0;
  right: 0;
  bottom: 0;
  background: #090a0f;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  z-index: 99;
}

.mobile-link {
  color: #ffffff;
  font-size: 17px;
  font-weight: 600;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  text-decoration: none;
}

.mobile-actions {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

@media (min-width: 768px) {
  .desktop-nav,
  .right-group {
    display: flex;
  }
  .mobile-toggle,
  .mobile-drawer {
    display: none;
  }
}
</style>
