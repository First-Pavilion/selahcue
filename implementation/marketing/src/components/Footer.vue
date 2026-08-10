<script setup lang="ts">
// Footer component
</script>

<template>
  <footer class="footer">
    <div class="container footer-content">
      <div class="footer-top">
        <div class="brand-column">
          <router-link to="/" class="brand">
            <img src="/selahcue-logo.png" alt="SelahCue Logo" class="logo" />
            <span class="wordmark">SelahCue</span>
          </router-link>
          <p class="tagline">Church presentation, reengineered</p>
        </div>
        
        <div class="links-grid">
          <div class="link-column">
            <h4 class="column-title">Product</h4>
            <router-link to="/features" class="footer-link">Features</router-link>
            <router-link to="/pricing" class="footer-link">Pricing</router-link>
            <router-link to="/download" class="footer-link">Download</router-link>
            <router-link to="/how-it-works" class="footer-link">How it works</router-link>
          </div>
          
          <div class="link-column">
            <h4 class="column-title">Resources</h4>
            <router-link to="/docs" class="footer-link">Documentation</router-link>
            <router-link to="/support" class="footer-link">Support</router-link>
            <router-link to="/blog" class="footer-link">Blog</router-link>
            <router-link to="/changelog" class="footer-link">Changelog</router-link>
          </div>
          
          <div class="link-column">
            <h4 class="column-title">Company</h4>
            <router-link to="/about" class="footer-link">About</router-link>
            <router-link to="/careers" class="footer-link">Careers</router-link>
            <router-link to="/contact" class="footer-link">Contact</router-link>
            <router-link to="/affiliates" class="footer-link">Affiliates</router-link>
          </div>
          
          <div class="link-column">
            <h4 class="column-title">Legal</h4>
            <router-link to="/privacy" class="footer-link">Privacy Policy</router-link>
            <router-link to="/terms" class="footer-link">Terms of Service</router-link>
          </div>
        </div>
      </div>
      
      <div class="footer-bottom">
        <p class="copyright">© 2026 SelahCue. All rights reserved.</p>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  background: var(--sc-surface);
  border-top: 1px solid var(--sc-border);
  padding-top: 80px;
}

.footer-content {
  display: flex;
  flex-direction: column;
}

.footer-top {
  display: flex;
  flex-direction: column;
  gap: 48px;
  margin-bottom: 64px;
}

.brand-column {
  max-width: 300px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  text-decoration: none;
}

.logo {
  height: 32px;
  width: auto;
}

.wordmark {
  font-family: var(--font-family);
  font-weight: 700;
  font-size: 20px;
  color: var(--sc-text);
  letter-spacing: -0.02em;
}

.tagline {
  color: var(--sc-text-secondary);
  font-size: 15px;
  line-height: 1.5;
}

.links-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 40px 24px;
}

.link-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.column-title {
  color: var(--sc-text);
  font-weight: 600;
  font-size: 15px;
  margin: 0 0 4px 0;
}

.footer-link {
  color: var(--sc-text-secondary);
  font-size: 14px;
  transition: color var(--transition-fast);
  text-decoration: none;
}

.footer-link:hover {
  color: var(--sc-text);
}

.footer-bottom {
  padding-block: 32px;
  border-top: 1px solid var(--sc-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.copyright {
  color: var(--sc-text-muted);
  font-size: 14px;
  margin: 0;
}

@media (min-width: 768px) {
  .links-grid {
    grid-template-columns: repeat(4, 1fr);
  }
  
  .footer-top {
    flex-direction: row;
    justify-content: space-between;
  }
}
</style>
