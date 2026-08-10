<script setup lang="ts">
import UiButton from '@/components/UiButton.vue'
</script>

<template>
  <div class="download-view">
    <section class="hero">
      <div class="container">
        <h1>Download SelahCue</h1>
        <p>Start presenting with total confidence.</p>
      </div>
    </section>

    <section class="platforms-section">
      <div class="container">
        <div class="platforms-grid">
          <div class="platform-card">
            <div class="icon">🪟</div>
            <h2>Windows</h2>
            <p>Windows 10 / 11 (64-bit)</p>
            <UiButton variant="primary">Download for Windows</UiButton>
            <span class="version">Version 1.2.0 (Stable)</span>
          </div>
          <div class="platform-card">
            <div class="icon">🍎</div>
            <h2>macOS</h2>
            <p>macOS 11.0 or later (Intel & Apple Silicon)</p>
            <UiButton variant="primary">Download for macOS</UiButton>
            <span class="version">Version 1.2.0 (Stable)</span>
          </div>
        </div>
      </div>
    </section>

    <section class="requirements-section">
      <div class="container">
        <h2>System Requirements</h2>
        <div class="req-grid">
          <div class="req-col">
            <h3>Minimum</h3>
            <ul>
              <li><strong>OS:</strong> Windows 10 / macOS 11</li>
              <li><strong>CPU:</strong> Intel Core i3 or equivalent</li>
              <li><strong>RAM:</strong> 4GB</li>
              <li><strong>Storage:</strong> 500MB available space</li>
              <li><strong>Graphics:</strong> DirectX 10 capable</li>
            </ul>
          </div>
          <div class="req-col">
            <h3>Recommended</h3>
            <ul>
              <li><strong>OS:</strong> Windows 11 / macOS 13+</li>
              <li><strong>CPU:</strong> Intel Core i5 / Apple M1 or better</li>
              <li><strong>RAM:</strong> 8GB+</li>
              <li><strong>Storage:</strong> 2GB available space (SSD)</li>
              <li><strong>Graphics:</strong> Dedicated GPU for NDI output</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <section class="mobile-section">
      <div class="container mobile-layout">
        <div class="mobile-text">
          <h2>Mobile Control</h2>
          <p>Control your presentation from anywhere on the stage or in the auditorium using our mobile apps. Connects seamlessly over your local network.</p>
          <div class="app-badges">
            <div class="badge-placeholder">App Store</div>
            <div class="badge-placeholder">Google Play</div>
          </div>
        </div>
        <div class="mobile-visual">
          <div class="phone-mockup">Mobile App Mockup</div>
        </div>
      </div>
    </section>

    <section class="install-guide">
      <div class="container">
        <h2>Installation Guide</h2>
        <div class="steps">
          <div class="step">
            <div class="step-num">1</div>
            <h4>Download the installer</h4>
            <p>Choose the right version for your operating system.</p>
          </div>
          <div class="step">
            <div class="step-num">2</div>
            <h4>Run the setup wizard</h4>
            <p>Follow the on-screen instructions to install the app.</p>
          </div>
          <div class="step">
            <div class="step-num">3</div>
            <h4>Launch and start presenting</h4>
            <p>Open SelahCue and set up your first service.</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

.hero {
  padding: 5rem 0 3rem;
  text-align: center;
}
.hero h1 {
  font-size: 3rem;
  margin-bottom: 1rem;
}
.hero p {
  font-size: 1.25rem;
  color: var(--sc-text-muted);
}

.platforms-grid {
  display: flex;
  gap: 2rem;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 5rem;
}
.platform-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  padding: 3rem;
  text-align: center;
  flex: 1;
  min-width: 300px;
  max-width: 400px;
}
.platform-card .icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}
.platform-card h2 {
  margin-bottom: 0.5rem;
}
.platform-card p {
  color: var(--sc-text-muted);
  margin-bottom: 2rem;
}
.platform-card .version {
  display: block;
  margin-top: 1rem;
  font-size: 0.875rem;
  color: var(--sc-text-muted);
}

.requirements-section {
  padding: 5rem 0;
  background: var(--sc-surface-alt);
}
.requirements-section h2 {
  text-align: center;
  margin-bottom: 3rem;
}
.req-grid {
  display: flex;
  gap: 4rem;
  justify-content: center;
}
.req-col {
  background: var(--sc-surface);
  padding: 2rem;
  border-radius: 12px;
  border: 1px solid var(--sc-border);
  flex: 1;
  max-width: 400px;
}
.req-col h3 {
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--sc-border);
  padding-bottom: 0.5rem;
}
.req-col ul {
  list-style: none;
  padding: 0;
}
.req-col li {
  margin-bottom: 0.75rem;
}

.mobile-section {
  padding: 5rem 0;
}
.mobile-layout {
  display: flex;
  align-items: center;
  gap: 4rem;
}
.mobile-text {
  flex: 1;
}
.mobile-text h2 {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}
.mobile-text p {
  font-size: 1.1rem;
  color: var(--sc-text-muted);
  margin-bottom: 2rem;
}
.app-badges {
  display: flex;
  gap: 1rem;
}
.badge-placeholder {
  padding: 0.75rem 1.5rem;
  background: #000;
  color: #fff;
  border-radius: 8px;
  font-weight: bold;
}
.mobile-visual {
  flex: 1;
}
.phone-mockup {
  width: 300px;
  height: 600px;
  margin: 0 auto;
  border: 12px solid #333;
  border-radius: 36px;
  background: var(--sc-surface-alt);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: var(--sc-text-muted);
}

.install-guide {
  padding: 5rem 0;
  background: var(--sc-surface);
  text-align: center;
}
.install-guide h2 {
  margin-bottom: 3rem;
}
.steps {
  display: flex;
  justify-content: center;
  gap: 2rem;
  flex-wrap: wrap;
}
.step {
  flex: 1;
  min-width: 250px;
  max-width: 300px;
}
.step-num {
  width: 48px;
  height: 48px;
  background: var(--sc-primary);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: bold;
  margin: 0 auto 1.5rem;
}
.step h4 {
  margin-bottom: 0.5rem;
}
.step p {
  color: var(--sc-text-muted);
}

@media (max-width: 768px) {
  .req-grid, .mobile-layout {
    flex-direction: column;
  }
}
</style>
