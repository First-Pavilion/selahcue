<script setup lang="ts">
import PublicDownloads from '@/components/PublicDownloads.vue'
import UiBadge from '@/components/UiBadge.vue'
import PageHero from '@/components/core/PageHero.vue'
import ToneChip from '@/components/core/ToneChip.vue'
import ControllerMock from '@/components/core/ControllerMock.vue'
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
      Choose the desktop installer for your platform when downloads are available.
      <template #after>
        <p class="trust-line">Free plan · Core live controls work offline</p>
      </template>
    </PageHero>

    <PublicDownloads />

    <!-- Figma 489:124: pad 64/96, gap 64; the controller mock is 280 wide beside a 904 text block. -->
    <section class="mobile-section">
      <div class="container mobile-layout">
        <div class="mobile-text">
          <ToneChip kind="row" tone="brand">MOBILE CONTROL</ToneChip>
          <h2>Control from your phone</h2>
          <p class="mobile-lead">
            If you already have the SelahCue Controller, you can pair it over your local network. Scan the QR code and approve the phone on the desktop. You can keep running the service from the desktop if the phone disconnects.
          </p>
          <ul class="mobile-bullets">
            <li>
              <svg class="tick" viewBox="0 0 16 19" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.3 9.6l3.1 3.2 6.9-7.3" /></svg>
              <span>Pairs over your LAN — no internet needed</span>
            </li>
            <li>
              <svg class="tick" viewBox="0 0 16 19" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.3 9.6l3.1 3.2 6.9-7.3" /></svg>
              <span>iOS and Android apps are not available yet</span>
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
            <p>Choose the installer for your computer and open it after it downloads.</p>
          </div>
          <div class="step-card">
            <span class="step-num">02</span>
            <h3>Set up your account</h3>
            <p>Create an account and verify your email, then open SelahCue and sign in.</p>
          </div>
          <div class="step-card">
            <span class="step-num">03</span>
            <h3>Build a service plan &amp; go live</h3>
            <p>Add scripture and presentations, choose your outputs, and go live.</p>
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

.steps-section h2 {
  margin: 0 0 24px;
  text-align: center;
  font: 700 26px/32px var(--font-family);
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
  .steps-section h2 {
    font-size: 32px;
    line-height: 39px;
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
