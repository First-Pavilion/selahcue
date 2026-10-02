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
            <!--
              No installer is served from this page yet: the downloads backend is not built
              (ClickUp 86ak10afm) and both of its endpoints still return 501. So the button is
              honestly disabled rather than a button that does nothing, and the version line
              that claimed a stable release is replaced with the real status. Wire this to the
              downloads backend when that lands.
            -->
            <UiButton
              variant="primary"
              disabled
              aria-disabled="true"
              aria-describedby="windows-availability"
            >Download for Windows</UiButton>
            <span id="windows-availability" class="version availability">Not available to download yet</span>
          </div>
          <div class="platform-card">
            <div class="icon">🍎</div>
            <h2>macOS</h2>
            <p>macOS 11.0 or later (Intel & Apple Silicon)</p>
            <UiButton
              variant="primary"
              disabled
              aria-disabled="true"
              aria-describedby="macos-availability"
            >Download for macOS</UiButton>
            <span id="macos-availability" class="version availability">Not available to download yet</span>
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
          <!--
            Neither store listing exists yet (mobile store publishing is still open work:
            signing, store accounts, legal sign-off), so these are honest disabled states, not
            links. No href, no handler. They are native disabled buttons on purpose: that gives
            assistive tech the real "unavailable" state, keeps them out of the tab order (a tab
            stop that does nothing is noise), and the visible "Coming soon" text plus the note
            below carry the meaning for everyone, not just screen-reader users.
            When a listing goes live, turn the matching badge into a real <a> to that URL.
          -->
          <div class="app-badges" role="group" aria-label="Mobile app availability">
            <button
              type="button"
              class="store-badge"
              disabled
              aria-disabled="true"
              aria-describedby="store-availability"
            >
              <span class="store-name">App Store</span>
              <span class="store-status">Coming soon</span>
            </button>
            <button
              type="button"
              class="store-badge"
              disabled
              aria-disabled="true"
              aria-describedby="store-availability"
            >
              <span class="store-name">Google Play</span>
              <span class="store-status">Coming soon</span>
            </button>
          </div>
          <p id="store-availability" class="store-note">
            The SelahCue Controller app is not in the App Store or Google Play yet.
          </p>
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
  padding: 0 var(--page-gutter);
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
  /* `min()` so the card can shrink below 300px inside a 320px viewport's gutters. */
  min-width: min(300px, 100%);
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
/* The status line now carries information (the button is disabled and this says why), so it
   uses the secondary text colour, which clears AA on the card surface; the muted token does not. */
.platform-card .availability {
  color: var(--sc-text-secondary);
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
/* Deliberately NOT styled like a filled button: transparent with a dashed outline, no hover,
   not-allowed cursor, so nothing here reads as something to click. The status text uses the
   secondary text colour (not opacity) so "Coming soon" keeps readable contrast. */
.store-badge {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 0.75rem 1.5rem;
  background: transparent;
  border: 1px dashed var(--sc-border-strong);
  border-radius: 8px;
  color: var(--sc-text);
  font: inherit;
  text-align: left;
  cursor: not-allowed;
}
.store-name {
  font-weight: 700;
}
.store-status {
  font-size: 0.8125rem;
  color: var(--sc-text-secondary);
}
.mobile-text .store-note {
  margin: 1rem 0 0;
  font-size: 0.9375rem;
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
  min-width: min(250px, 100%);
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

/* Tablet: the two platform cards stay side by side, with tighter gaps. */
@media (max-width: 1199.98px) {
  .req-grid { gap: 2rem; }
  .mobile-layout { gap: 2rem; }
  .requirements-section, .mobile-section, .install-guide { padding: var(--section-pad) 0; }
}

@media (max-width: 767.98px) {
  .hero { padding: 3rem 0 2rem; }
  .hero h1 { font-size: 36px; line-height: 40px; }
  .hero p { font-size: 1.1rem; }
  .platforms-grid { flex-direction: column; align-items: stretch; margin-bottom: 3rem; }
  .platform-card { flex: 0 0 auto; max-width: none; padding: 2rem 1.5rem; }
  .req-grid, .mobile-layout {
    flex-direction: column;
  }
  .req-col { max-width: none; width: 100%; padding: 1.5rem; }
  .mobile-layout { gap: 2.5rem; align-items: stretch; }
  .mobile-text h2 { font-size: 2rem; }
  .phone-mockup { width: min(260px, 100%); height: 480px; }
  .requirements-section, .mobile-section, .install-guide { padding: var(--section-pad) 0; }
  .requirements-section h2, .install-guide h2 { margin-bottom: 2rem; }
}
</style>
