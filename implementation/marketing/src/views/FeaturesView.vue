<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import PageHero from '@/components/core/PageHero.vue'
import FeatureRow from '@/components/core/FeatureRow.vue'
import CtaBand from '@/components/core/CtaBand.vue'

/*
 * Figma 485:124: a hero, six capability rows with abstract skeleton panels, a closing band. The
 * words are Figma's except where the repo does not back them (audit features-10, -11, -12, and the
 * Copy rule on ClickUp 17tnw2b2cey):
 *
 *  - "Unlimited virtual outputs" and "Per-output theme & framing" are not shipped: DEC-008 caps
 *    outputs at 2, 5 and 10 by plan, and per-output configuration is R2 (FR-038). The NDI row says
 *    what ships.
 *  - "nothing leaves the machine / entirely on the machine" is stated as absolute. The row says what a
 *    release build does: transcription runs on the machine (FR-101). It does NOT advertise cloud
 *    transcription: `cloud-stt` is RELEASE: UNSAFE and stripped from release builds (selahcue-operator
 *    Cargo.toml, Makefile `release-ai-guard`), so a release has no cloud path to describe (review round 1,
 *    Cody N4). Bring it back only when a release ships it.
 *  - "Never-blank guarantee" and "the screen never blanks" are stronger than NFR-024 (failure isolation;
 *    the emergency blackout exists), so the row says it is designed so a fault cannot black out live
 *    output (review round 1, Cody N19).
 *  - The internal requirement id "NFR-024" is not customer copy (features-12).
 *
 * The invented capability claims the old build carried ("NDI 5", "4K 60fps", "1080p60", alpha channel,
 * "zero latency", a named pastor) go with the old mockups (features-03, features-07).
 */
</script>

<template>
  <div class="features-view">
    <PageHero
      title="Everything you need to run a confident service"
      :pad-top="96"
      :pad-bottom="64"
      :gap="22"
      :title-max="720"
    >
      <template #eyebrow>
        <UiBadge variant="featured">FEATURES</UiBadge>
      </template>
      From the first slide to the final blessing, SelahCue keeps your scripture, songs, timers, stage display and streaming outputs in one offline-first console — with a phone in your hand as the remote.
    </PageHero>

    <div class="feature-rows">
      <FeatureRow
        tone="live"
        eyebrow="OUTPUTS"
        title="Live presentation & outputs"
        text="Stage everything in Preview, then Go Live with a single tap. Audience projector and stage display run from the same deck, and live output is designed to stay up when something else fails."
        :bullets="['Preview → Live with one Go Live', 'Designed so a fault cannot black out live output', 'Audience + stage from one deck']"
        panel-title="OUTPUTS"
        panel-chip="LIVE"
      >
        <template #icon>
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></svg>
        </template>
      </FeatureRow>

      <FeatureRow
        tone="brand"
        eyebrow="SCRIPTURE"
        title="Scripture at your fingertips"
        text="A full public-domain translation is bundled in the app. Type a reference or search by keyword — it works with no internet at all."
        :bullets="['Bundled WEB translation, no internet needed', 'Reference parsing + keyword search', 'Send to Preview, then push Live']"
        panel-title="SCRIPTURE"
        panel-chip="WEB"
        reverse
      >
        <template #icon>
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z" /><path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3M9 7h6" /></svg>
        </template>
      </FeatureRow>

      <FeatureRow
        tone="warn"
        eyebrow="PLANNING"
        title="Service plans & timers"
        text="Order your whole service ahead of time, then run it with countdown and count-up timers so you always land on time."
        :bullets="['Plan the full order of service', 'Countdown + count-up timers', 'Reorder on the fly, mid-service']"
        panel-title="PLANNING"
        panel-chip="TIMERS"
      >
        <template #icon>
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" /></svg>
        </template>
      </FeatureRow>

      <FeatureRow
        tone="ready"
        eyebrow="STAGE"
        title="Stage & confidence monitor"
        text="Give your platform team a clear current / next / timer view — high-contrast and independent, so a change to the audience screen never disrupts it."
        :bullets="['Current / next / timer for the platform', 'High-contrast, glanceable layout', 'Independent of audience output']"
        panel-title="STAGE"
        panel-chip="READY"
        reverse
      >
        <template #icon>
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 3l4 4 4-4" /></svg>
        </template>
      </FeatureRow>

      <FeatureRow
        tone="brand"
        eyebrow="STREAMING"
        title="NDI & multi-output"
        text="Send your program over NDI straight into OBS or vMix, and drive more than one output from the same deck."
        :bullets="['Program over NDI to OBS / vMix', 'More outputs on higher plans', 'NDI output on the Pro and Platinum plans']"
        panel-title="STREAMING"
        panel-chip="NDI"
      >
        <template #icon>
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2" /><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4M4.9 4.9a10 10 0 0 0 0 14.2M19.1 4.9a10 10 0 0 1 0 14.2" /></svg>
        </template>
      </FeatureRow>

      <FeatureRow
        tone="ready"
        eyebrow="ASSIST"
        title="On-device transcript & detection"
        text="An optional live transcript runs on your machine. It assists the operator but never gates your core controls."
        :bullets="['Live transcript, on-device', 'Scripture detection that assists the operator', 'Assists — never gates — core controls']"
        panel-title="ASSIST"
        panel-chip="ON-DEVICE"
        reverse
      >
        <template #icon>
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
        </template>
      </FeatureRow>
    </div>

    <CtaBand />
  </div>
</template>

<style scoped>
.features-view {
  background: var(--sc-base);
}

.feature-rows {
  display: flex;
  flex-direction: column;
}
</style>
