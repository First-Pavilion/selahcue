<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const isScrolled = ref(false)
const isMobileMenuOpen = ref(false)

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

      <!-- Right Group: Sign In + Download Free CTA -->
      <div class="right-group">
        <router-link to="/signin" class="signin-btn">Sign in</router-link>
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
        <router-link to="/signin" class="signin-btn" @click="toggleMobileMenu">Sign in</router-link>
        <router-link to="/download" class="download-cta" @click="toggleMobileMenu">Download free</router-link>
      </div>
    </div>
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
