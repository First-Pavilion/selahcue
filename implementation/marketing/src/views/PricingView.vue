<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import PageHero from '@/components/core/PageHero.vue'
import { freeOffer } from '@/lib/content/freeOffer.ts'
</script>

<template>
  <div class="pricing-view">
    <PageHero
      title="Pricing that grows with your church"
      :pad-top="80"
      :pad-bottom="40"
      :gap="16"
      :title-size="52"
      :title-line="56"
      :title-max="520"
    >
      <template #eyebrow>
        <UiBadge variant="eyebrow">PRICING</UiBadge>
      </template>
    </PageHero>

    <!-- The h2 keeps the outline from jumping from the h1 to the footer's h3 headings (audit pricing-bug-01). -->
    <section class="plans-section" aria-labelledby="plans-heading">
      <div class="container">
        <h2 id="plans-heading" class="plans-heading">SelahCue Free</h2>
        <div class="free-plan">
          <p>{{ freeOffer.summary }}</p>
          <p>{{ freeOffer.paidLater }}</p>
          <div class="free-actions">
            <UiButton :to="freeOffer.downloadTo" variant="primary" size="lg">View downloads</UiButton>
            <UiButton :to="freeOffer.signupTo" variant="secondary" size="lg">Create an account</UiButton>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.plans-section {
  padding-block: 24px var(--section-pad);
}

.plans-heading {
  margin: 0 0 24px;
  text-align: center;
  font: 700 26px/32px var(--font-family);
  color: var(--sc-text);
}

.free-plan {
  max-width: 900px;
  margin-inline: auto;
  padding: 47px 29px;
  text-align: center;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
}

.free-plan p {
  margin: 0;
  font-size: 17px;
  line-height: 26px;
  color: var(--sc-text-secondary);
}

.free-plan p + p {
  margin-top: 8px;
}

.free-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 24px;
}

@media (max-width: 767.98px) {
  .free-plan {
    padding: 31px 19px;
    border-radius: 16px;
  }
}
</style>
