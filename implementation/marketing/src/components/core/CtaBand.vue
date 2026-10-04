<script setup lang="ts">
import UiButton from '@/components/UiButton.vue'

/*
 * The closing band shared by Features (Figma 486:345) and About (496:181): one gradient card, a
 * heading, a line, and two actions. One component, so the wording and the destinations live in one
 * place (the claims ticket 17tnw2b0x3h edits "Download free" site-wide in one file).
 *
 * The line is Figma's with two changes the repo forces (audit features-06, about-04): "Cancel
 * anytime" is gone (no billing exists to cancel) and "go live this Sunday" is gone (nothing downloads
 * yet). It is white, not Figma's #dbe0fa: on the lighter end of the band a phone-width card puts the
 * text where #dbe0fa is 3.3:1; white holds 4.7:1 at the lightest stop.
 */
defineProps({
  title: { type: String, default: 'Ready to run your best service yet?' },
  lead: {
    type: String,
    default: 'Start with the Free plan. SelahCue keeps working offline when it matters most.',
  },
})
</script>

<template>
  <section class="cta-section">
    <div class="container">
      <div class="cta-band">
        <h2>{{ title }}</h2>
        <p>{{ lead }}</p>
        <div class="cta-actions">
          <UiButton variant="inverse" size="lg" to="/download">Download free</UiButton>
          <UiButton variant="inverse-outline" size="lg" to="/pricing">See pricing</UiButton>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.cta-section {
  padding-block: var(--section-pad);
}

.cta-band {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px 24px;
  border-radius: 20px;
  background: var(--gradient-cta);
  text-align: center;
}

.cta-band h2 {
  margin: 0;
  max-width: 760px;
  font: 700 30px/36px var(--font-family);
  color: #fff;
  text-wrap: balance;
}

.cta-band p {
  margin: 0;
  max-width: 600px;
  font-size: 16px;
  line-height: 26px;
  color: #fff;
  text-wrap: balance;
}

/* `align-items: center` on the row: a quiet large button next to a solid one is 47 against 49, and a
   stretched row would measure both 49 (the chrome review's note on this ticket). */
.cta-actions {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
  width: 100%;
  padding-top: 8px;
}

@media (min-width: 768px) {
  .cta-band {
    gap: 20px;
    padding: 48px 32px;
    border-radius: 24px;
  }
  .cta-band h2 {
    font-size: 36px;
    line-height: 42px;
  }
  .cta-band p {
    font-size: 18px;
    line-height: 27px;
  }
  .cta-actions {
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: 14px;
    width: auto;
  }
}

@media (min-width: 1200px) {
  .cta-band {
    gap: 22px;
    padding: 64px 48px;
  }
  .cta-band h2 {
    font-size: 44px;
    line-height: 50px;
  }
  .cta-band p {
    font-size: 19px;
    line-height: 28px;
  }
  .cta-actions {
    padding-top: 10px;
  }
}
</style>
