<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import PageHero from '@/components/core/PageHero.vue'

// Commercial data is read only by the shared public catalogue component (17tnw2b2jvz).
import CataloguePlans from '@/components/CataloguePlans.vue'

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
        <h2 id="plans-heading" class="plans-heading">Plans and pricing</h2>
        <CataloguePlans />
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

</style>
