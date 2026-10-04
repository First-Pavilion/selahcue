<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import PageHero from '@/components/core/PageHero.vue'
import ToneChip from '@/components/core/ToneChip.vue'
import ControllerMock from '@/components/core/ControllerMock.vue'

/*
 * Figma 487:124. Layout and styling follow the frame; the wording follows the repo, because the frame's
 * numbers are not backed (audit download-04, -05, -09, and the Copy rule on ClickUp 17tnw2b2cey):
 *
 *  - no installer version, format or size: the repo packages one Windows NSIS installer, there is no
 *    .msi, no macOS bundle and no recorded size, and no release exists;
 *  - no OS floor: no document states a minimum Windows or macOS version;
 *  - no hardware figures: Figma, the PRD (Tier A: 8 GB) and the owner requirement (4 GB) disagree, so each
 *    value reads "To be confirmed" until the owner chooses (download-05);
 *  - the apps are not in the stores (download-09), so the bullet and the badges say so.
 *
 * The download buttons stay DISABLED (ClickUp 17tnw2b0q9j, PR 134; `tests/downloadView.test.ts`). The
 * product confirmed on 2026-10-04 that the app is available for Windows, Linux and macOS, but it is not
 * known that a downloadable installer exists for each, so no page may claim a macOS or Linux installer
 * and Linux is not drawn (Figma draws two cards).
 */
</script>

<template>
  <div class="download-view">
    <PageHero
      title="Get SelahCue for your platform"
      :pad-top="96"
      :pad-bottom="40"
      :gap="20"
      :title-max="480"
      :lead-max="720"
    >
      <template #eyebrow>
        <UiBadge variant="featured">DOWNLOAD</UiBadge>
      </template>
      Desktop installers are not available to download yet. SelahCue runs fully offline, and mobile control pairs with your desktop over your local network.
      <template #after>
        <p class="trust-line">Free plan · Works fully offline</p>
      </template>
    </PageHero>

    <section class="platforms-section">
      <div class="container">
        <div class="platforms-grid">
          <div class="platform-card">
            <span class="platform-tile" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></svg>
            </span>
            <h2>Windows</h2>
            <p class="platform-sub">Windows desktop app · 64-bit</p>
            <!--
              No installer is served from this page yet: the downloads backend is not built
              (ClickUp 86ak10afm) and both of its endpoints still return 501. So the button is
              honestly disabled rather than a button that does nothing, and the version line
              that claimed a stable release is replaced with the real status. Wire this to the
              downloads backend when that lands.
            -->
            <UiButton
              class="platform-action"
              variant="primary"
              disabled
              aria-disabled="true"
              aria-describedby="windows-availability"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11M7 11l5 5 5-5M5 20h14" /></svg>
              Download for Windows
            </UiButton>
            <span id="windows-availability" class="platform-status">Not available to download yet</span>
          </div>

          <div class="platform-card">
            <span class="platform-tile" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="5" width="15" height="10.5" rx="1.8" /><path d="M2.5 19.5h19" /></svg>
            </span>
            <h2>macOS</h2>
            <p class="platform-sub">macOS desktop app</p>
            <UiButton
              class="platform-action"
              variant="primary"
              disabled
              aria-disabled="true"
              aria-describedby="macos-availability"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11M7 11l5 5 5-5M5 20h14" /></svg>
              Download for macOS
            </UiButton>
            <span id="macos-availability" class="platform-status">Not available to download yet</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Figma 488:124: a full-width band (fill #171b22 = --sc-surface), pad 48/96, gap 28. -->
    <section class="requirements-section">
      <div class="container">
        <h2>System requirements</h2>
        <div class="req-grid">
          <div class="req-card">
            <h3 class="req-title"><ToneChip kind="req" tone="muted">MINIMUM</ToneChip></h3>
            <dl class="req-rows">
              <div class="req-row"><dt>Processor</dt><dd>To be confirmed</dd></div>
              <div class="req-row"><dt>Memory</dt><dd>To be confirmed</dd></div>
              <div class="req-row"><dt>Graphics</dt><dd>To be confirmed</dd></div>
              <div class="req-row"><dt>Storage</dt><dd>To be confirmed</dd></div>
              <div class="req-row"><dt>Display</dt><dd>To be confirmed</dd></div>
            </dl>
          </div>
          <div class="req-card">
            <h3 class="req-title"><ToneChip kind="req" tone="ready">RECOMMENDED</ToneChip></h3>
            <dl class="req-rows">
              <div class="req-row"><dt>Processor</dt><dd>To be confirmed</dd></div>
              <div class="req-row"><dt>Memory</dt><dd>To be confirmed</dd></div>
              <div class="req-row"><dt>Graphics</dt><dd>To be confirmed</dd></div>
              <div class="req-row"><dt>Storage</dt><dd>To be confirmed</dd></div>
              <div class="req-row"><dt>Display</dt><dd>To be confirmed</dd></div>
            </dl>
          </div>
        </div>
      </div>
    </section>

    <!-- Figma 489:124: pad 64/96, gap 64; the controller mock is 280 wide beside a 904 text block. -->
    <section class="mobile-section">
      <div class="container mobile-layout">
        <div class="mobile-text">
          <ToneChip kind="row" tone="brand">MOBILE CONTROL</ToneChip>
          <h2>Control from your phone</h2>
          <p class="mobile-lead">
            The SelahCue Controller pairs with your desktop over your local network — scan a QR code and you're connected. It's a companion remote: your desktop always stays the authority, even if the phone drops off Wi-Fi.
          </p>
          <ul class="mobile-bullets">
            <li>
              <svg class="tick" viewBox="0 0 16 19" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.3 9.6l3.1 3.2 6.9-7.3" /></svg>
              <span>Pairs over your LAN — no internet needed</span>
            </li>
            <li>
              <svg class="tick" viewBox="0 0 16 19" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.3 9.6l3.1 3.2 6.9-7.3" /></svg>
              <span>iOS and Android apps coming soon</span>
            </li>
            <li>
              <svg class="tick" viewBox="0 0 16 19" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.3 9.6l3.1 3.2 6.9-7.3" /></svg>
              <span>Desktop stays authoritative if the phone drops</span>
            </li>
          </ul>
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
          <ControllerMock />
        </div>
      </div>
    </section>

    <!-- Figma 489:174: pad 48/96/64, gap 28; three 400x197 cards. -->
    <section class="steps-section">
      <div class="container">
        <h2>Up and running in three steps</h2>
        <div class="steps">
          <div class="step-card">
            <span class="step-num">01</span>
            <h3>Download &amp; install</h3>
            <p>Get the installer for your platform and run it.</p>
          </div>
          <div class="step-card">
            <span class="step-num">02</span>
            <h3>Build your first plan</h3>
            <p>Add scripture, songs and timers to a service plan and pick your outputs.</p>
          </div>
          <div class="step-card">
            <span class="step-num">03</span>
            <h3>Go live &amp; pair your phone</h3>
            <p>Hit Go Live, then scan the QR code to pair your phone as a remote.</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.trust-line {
  margin: 0;
  font-size: 14px;
  line-height: 17px;
  color: var(--sc-text-secondary);
}

/* ---- platform cards (Figma 487:146: two 610x316 cards, 28 apart, padding 32, 18 between blocks) ---- */
.platforms-section {
  padding-block: 0 40px;
}

.platforms-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 20px;
}

.platform-card {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 18px;
  min-width: 0;
  /* Figma pads from the OUTER edge (stroke inside the frame): the 1px border comes off the padding. */
  padding: 23px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
}

.platform-tile {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: var(--sc-primary);
  color: #fff;
}

.platform-card h2 {
  margin: 0;
  font: 700 26px/31px var(--font-family);
  color: var(--sc-text);
}

.platform-sub {
  margin: 0;
  font: var(--font-small);
  color: var(--sc-text-secondary);
}

/* UiButton has no 47px solid size (md is 44, lg 49): the frame's action is 47 tall, full width and
   radius 12, so the page sets it. The selector outranks UiButton's own size rules. The disabled look
   (half opacity, no pointer) is UiButton's. */
.platform-card .platform-action {
  width: 100%;
  height: 47px;
  padding-block: 0;
  border-radius: 12px;
  font-size: 15.5px;
  font-weight: 600;
}
.platform-card .platform-action :deep(.content) {
  gap: 10px;
}

/* The status line carries information (the button is disabled and this says why), so it uses the
   secondary text colour, which clears AA on the card surface. */
.platform-status {
  font-size: 13px;
  line-height: 16px;
  color: var(--sc-text-secondary);
}

/* ---- system requirements (Figma 488:124) ---- */
.requirements-section {
  padding-block: 40px;
  background: var(--sc-surface);
}

.requirements-section h2,
.steps-section h2 {
  margin: 0 0 24px;
  text-align: center;
  font: 700 26px/32px var(--font-family);
  color: var(--sc-text);
}

.req-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 20px;
}

.req-card {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  padding: 23px 19px;
  background: var(--sc-base);
  border: 1px solid var(--sc-border);
  border-radius: 18px;
}

.req-title {
  margin: 0;
  display: flex;
}

.req-rows {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 0;
}

.req-row {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 38px;
  padding-block: 10px;
}
/* Figma draws the hairline as each later row's own top stroke, 16px below the row above. */
.req-row + .req-row {
  padding-top: 9px;
  border-top: 1px solid var(--sc-border);
}

.req-row dt {
  font-size: 14.5px;
  line-height: 18px;
  color: var(--sc-text-secondary);
}
.req-row dd {
  margin: 0;
  font-size: 14.5px;
  font-weight: 600;
  line-height: 18px;
  text-align: right;
  color: var(--sc-text);
}

/* ---- mobile control (Figma 489:124) ---- */
.mobile-section {
  padding-block: 40px;
}

.mobile-layout {
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.mobile-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 18px;
  min-width: 0;
}

.mobile-text h2 {
  margin: 0;
  font: 700 28px/34px var(--font-family);
  color: var(--sc-text);
}

.mobile-lead {
  margin: 0;
  font-size: 16px;
  line-height: 26px;
  color: var(--sc-text-secondary);
}

.mobile-bullets {
  display: flex;
  flex-direction: column;
  gap: 11px;
}
.mobile-bullets li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 15.5px;
  line-height: 19px;
  color: var(--sc-text);
}
.tick {
  flex-shrink: 0;
  width: 16px;
  height: 19px;
  color: var(--sc-preview);
}

.mobile-visual {
  display: flex;
  justify-content: center;
}

.app-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 6px;
}
/* Deliberately NOT styled like a filled button: transparent with a dashed outline, no hover,
   not-allowed cursor, so nothing here reads as something to click. The status text uses the
   secondary text colour (not opacity) so "Coming soon" keeps readable contrast. The Figma badge
   (a filled box, "Download on") is the live state; this is the honest disabled one (audit download-08, B). */
.store-badge {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 12px 18px;
  background: transparent;
  border: 1px dashed var(--sc-border-strong);
  border-radius: 12px;
  color: var(--sc-text);
  font: inherit;
  text-align: left;
  cursor: not-allowed;
}
.store-name {
  font-size: 15px;
  font-weight: 600;
  line-height: 18px;
}
.store-status {
  font-size: 13px;
  line-height: 16px;
  color: var(--sc-text-secondary);
}
.mobile-text .store-note {
  margin: -6px 0 0;
  font-size: 15px;
  line-height: 22px;
  color: var(--sc-text-secondary);
}

/* ---- install steps (Figma 489:174) ---- */
.steps-section {
  padding-block: 8px 48px;
}

.steps {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

.step-card {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
  min-width: 0;
  padding: 23px 21px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 18px;
}

/* The number (Figma 17/700 brand ink on the elevated tile: 3.4:1, below AA). It reads the single
   brand-ink property UiBadge reads and falls back to the readable text colour: Uma's one-line change. */
.step-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--sc-elevated);
  font-size: 17px;
  font-weight: 700;
  line-height: 21px;
  color: var(--ui-badge-ink, var(--sc-text));
}

.step-card h3 {
  margin: 0;
  font: 600 19px/23px var(--font-family);
  color: var(--sc-text);
}

.step-card p {
  margin: 0;
  font-size: 15px;
  line-height: 23px;
  color: var(--sc-text-secondary);
}

@media (min-width: 768px) {
  .platforms-section {
    padding-block: 0 56px;
  }
  .platforms-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 28px;
  }
  .platform-card {
    padding: 31px;
  }
  .requirements-section {
    padding-block: 48px;
  }
  .requirements-section h2,
  .steps-section h2 {
    font-size: 32px;
    line-height: 39px;
  }
  .req-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 28px;
  }
  .req-card {
    padding: 27px;
  }
  .mobile-section {
    padding-block: 56px;
  }
  .mobile-layout {
    flex-direction: row;
    align-items: center;
    gap: 40px;
  }
  .mobile-text {
    flex: 1 1 0;
  }
  .mobile-text h2 {
    font-size: 34px;
    line-height: 40px;
  }
  .mobile-lead {
    font-size: 17px;
    line-height: 27px;
  }
  .mobile-visual {
    flex: 0 0 280px;
  }
  .steps-section {
    padding-block: 16px 64px;
  }
  .steps {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 20px;
  }
  .step-card {
    padding: 27px 25px;
  }
}

@media (min-width: 1200px) {
  .platforms-section {
    padding-block: 32px 40px;
  }
  .requirements-section h2,
  .steps-section h2 {
    margin-bottom: 28px;
  }
  .mobile-section {
    padding-block: 64px;
  }
  .mobile-layout {
    gap: 64px;
  }
  .steps-section {
    padding-block: 48px 64px;
  }
  .steps {
    gap: 24px;
  }
}
</style>
