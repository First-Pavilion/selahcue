<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import PricingCard from '@/components/PricingCard.vue'
import UiButton from '@/components/UiButton.vue'
import SegmentedToggle from '@/components/core/SegmentedToggle.vue'
import { fetchCatalogue, intervalOptions, offerText, planFeatures, type PublicPlan } from '@/lib/catalogue/publicCatalogue.ts'

const plans = ref<PublicPlan[]>([])
const state = ref<'loading' | 'ready' | 'unavailable'>('loading')
const selectedInterval = ref('')
const options = computed(() => intervalOptions(plans.value))
let controller: AbortController | undefined
let timeout: ReturnType<typeof setTimeout> | undefined
let generation = 0
let disposed = false
async function load(): Promise<void> {
  const current = ++generation
  controller?.abort()
  clearTimeout(timeout)
  controller = new AbortController()
  const signal = controller.signal
  timeout = setTimeout(() => controller?.abort(), 10_000)
  plans.value = []
  selectedInterval.value = ''
  state.value = 'loading'
  try {
    const response = await fetchCatalogue(signal)
    if (disposed || current !== generation) return
    plans.value = response
    state.value = 'ready'
  } catch {
    if (!disposed && current === generation) state.value = 'unavailable'
  } finally {
    if (current === generation) clearTimeout(timeout)
  }
}
onMounted(load)
onBeforeUnmount(() => { disposed = true; generation++; controller?.abort(); clearTimeout(timeout) })
</script>

<template>
  <div class="catalogue-plans" :aria-busy="state === 'loading' ? 'true' : 'false'">
    <p v-if="state === 'loading'" class="catalogue-message" role="status">Loading plans…</p>
    <div v-else-if="state === 'unavailable'" class="catalogue-message">
      <p role="alert">Plans could not be loaded. Please try again.</p>
      <UiButton variant="outline" @click="load">Retry loading plans</UiButton>
    </div>
    <p v-else-if="plans.length === 0" class="catalogue-message" role="status">No plans have been published yet.</p>
    <template v-else>
      <div v-if="options.length" class="catalogue-intervals">
        <SegmentedToggle v-model="selectedInterval" :options="options" label="Billing interval" />
      </div>
      <div class="pricing-grid">
        <PricingCard v-for="plan in plans" :key="plan.key" :name="plan.name" price="" description="" :features="planFeatures(plan)" cta="Not available yet">
          <template #price>
            <ul v-if="plan.offers.some(offer => !selectedInterval || offer.interval === selectedInterval)" class="catalogue-offers" aria-label="Current prices">
              <li v-for="offer in plan.offers.filter(offer => !selectedInterval || offer.interval === selectedInterval)" :key="`${offer.currency}/${offer.interval}`">{{ offerText(offer) }}</li>
            </ul>
            <span v-else class="catalogue-unpriced">{{ selectedInterval ? 'No price announced for this interval.' : 'Price not announced yet' }}</span>
          </template>
        </PricingCard>
      </div>
    </template>
  </div>
</template>

<style scoped>
.catalogue-message { margin: 0 auto; padding: 32px 20px; max-width: 900px; text-align: center; color: var(--sc-text-secondary); font-size: 17px; line-height: 26px; }
.catalogue-message p { margin: 0 0 16px; }
.pricing-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; }
.catalogue-intervals { display: flex; justify-content: center; margin-bottom: 24px; }
.catalogue-offers { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; font-size: 22px; line-height: 30px; font-weight: 600; color: var(--sc-text); overflow-wrap: anywhere; }
.catalogue-unpriced { font-size: 22px; line-height: 30px; font-weight: 600; color: var(--sc-text); }
@media (max-width: 1199.98px) { .pricing-grid { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 767.98px) { .catalogue-intervals { overflow-x: auto; justify-content: flex-start; } }
</style>
