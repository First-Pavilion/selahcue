<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import UiButton from '@/components/UiButton.vue'
import {
  downloadForTarget, loadReleaseManifest,
  type AppSignature, type Notarization, type PackageSignature, type ReleaseManifest, type ReleaseTarget,
} from '@/lib/releases/downloads.ts'

const platforms: { name: string; options: { target: ReleaseTarget; label: string }[] }[] = [
  { name: 'Windows', options: [{ target: 'windows-x64', label: 'Windows x64' }] },
  { name: 'macOS', options: [
    { target: 'macos-arm64', label: 'macOS Apple silicon (arm64)' },
    { target: 'macos-x64', label: 'macOS Intel (x64)' },
  ] },
  { name: 'Ubuntu', options: [{ target: 'ubuntu-24.04-x64', label: 'Ubuntu 24.04 x64' }] },
]

const appSignature: Record<AppSignature, string> = {
  unsigned: 'Unsigned', ad_hoc: 'Ad hoc', verified: 'Verified', not_applicable: 'Not applicable',
}
const packageSignature: Record<PackageSignature, string> = { unsigned: 'Unsigned', verified: 'Verified' }
const notarization: Record<Notarization, string> = {
  not_notarized: 'Not notarized', verified: 'Verified', not_applicable: 'Not applicable',
}
const byteCount = new Intl.NumberFormat('en-US')

type State =
  | { status: 'checking' | 'error' }
  | ReleaseManifest

const state = ref<State>({ status: 'checking' })
const heading = ref<HTMLHeadingElement | null>(null)
const retryButton = ref<HTMLButtonElement | null>(null)
const retrying = ref(false)
const lifetime = new AbortController()

const cards = computed(() => {
  const manifest = state.value
  return platforms.map(({ name, options }) => ({
    name,
    options: options.map(({ target, label }) => ({
      target, label,
      artifact: manifest.status === 'published' ? downloadForTarget(manifest, target) : null,
    })),
  }))
})

const statusText = computed(() => {
  switch (state.value.status) {
    case 'error': return 'We couldn’t check installer availability. Please retry.'
    case 'unpublished': return 'Desktop installers are not available to download yet.'
    case 'published': return `Version ${state.value.version}`
    default: return 'Checking installer availability…'
  }
})

async function checkAvailability() {
  try {
    state.value = await loadReleaseManifest(fetch, lifetime.signal)
    return true
  } catch {
    if (!lifetime.signal.aborted) state.value = { status: 'error' }
    return false
  }
}

async function retryAvailability() {
  if (state.value.status !== 'error') return
  retrying.value = true
  state.value = { status: 'checking' }
  const available = await checkAvailability()
  if (lifetime.signal.aborted) return
  const restoreFocus = available && document.activeElement === retryButton.value
  retrying.value = false
  if (restoreFocus) {
    await nextTick()
    heading.value?.focus()
  }
}

onMounted(checkAvailability)
onUnmounted(() => lifetime.abort())
</script>

<template>
  <section id="public-downloads" class="platforms-section" aria-labelledby="public-download-heading">
    <div class="container">
      <h2 id="public-download-heading" ref="heading" class="platforms-heading" tabindex="-1">Desktop installers</h2>
      <p class="platform-status" role="status">{{ statusText }}</p>
      <button
        v-if="state.status === 'error' || retrying"
        ref="retryButton"
        type="button"
        class="retry-action"
        :aria-disabled="retrying"
        @click="retryAvailability"
      >
        Retry availability check
      </button>

      <div class="platforms-grid">
        <div v-for="card in cards" :key="card.name" class="platform-card">
          <span class="platform-tile" aria-hidden="true">
            <svg v-if="card.name === 'Windows'" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></svg>
            <svg v-else-if="card.name === 'macOS'" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="5" width="15" height="10.5" rx="1.8" /><path d="M2.5 19.5h19" /></svg>
            <svg v-else viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m7 9 3 3-3 3m6 0h4" /></svg>
          </span>
          <h3>{{ card.name }}</h3>
          <div v-for="{ target, label, artifact } in card.options" :key="target" class="platform-option">
            <template v-if="artifact && state.status === 'published'">
              <UiButton class="platform-action" :href="artifact.url" referrerpolicy="no-referrer">
                Download for {{ label }}
              </UiButton>
              <dl class="release-details" :aria-label="`${label} installer details`">
                <div><dt>Version</dt><dd>{{ state.version }}</dd></div>
                <div><dt>Size</dt><dd>{{ byteCount.format(artifact.size_bytes) }} bytes</dd></div>
                <div><dt>SHA-256</dt><dd><code>{{ artifact.sha256 }}</code></dd></div>
                <div><dt>App signature</dt><dd>{{ appSignature[artifact.app_signature] }}</dd></div>
                <div><dt>Package signature</dt><dd>{{ packageSignature[artifact.package_signature] }}</dd></div>
                <div><dt>Notarization</dt><dd>{{ notarization[artifact.notarization] }}</dd></div>
                <div v-if="artifact.publisher"><dt>Verified publisher</dt><dd>{{ artifact.publisher }}</dd></div>
              </dl>
              <p v-if="artifact.app_signature === 'ad_hoc'" class="platform-sub">
                This app has an ad hoc signature. macOS may warn you when you open it.
              </p>
            </template>
            <p v-else class="platform-sub">{{ label }}</p>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.platforms-section {
  padding-block: 0 40px;
}

.platforms-section,
.platforms-heading,
.retry-action,
.platform-action {
  scroll-margin-top: var(--sc-anchor-offset);
}

.platforms-heading {
  margin: 0 0 12px;
  font: 700 26px/32px var(--font-family);
  color: var(--sc-text);
}

.platform-status,
.platform-sub {
  margin: 0;
  font: var(--font-small);
  color: var(--sc-text-secondary);
  overflow-wrap: anywhere;
}

.platform-status {
  margin-bottom: 20px;
}

.retry-action {
  min-height: 44px;
  margin-bottom: 20px;
  padding: 8px 16px;
  color: var(--sc-text);
  background: var(--sc-surface);
  border: 1px solid var(--sc-border-strong);
  border-radius: 12px;
  font: inherit;
  cursor: pointer;
}

.retry-action[aria-disabled='true'] {
  cursor: wait;
}

.retry-action:focus-visible,
.platforms-heading:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 3px;
}

.platforms-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 20px;
}

.platform-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
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

.platform-card h3 {
  margin: 0;
  font: 700 26px/31px var(--font-family);
  color: var(--sc-text);
}

.platform-option + .platform-option {
  padding-top: 16px;
  border-top: 1px solid var(--sc-border);
}

.platform-card .platform-action {
  width: 100%;
  min-height: 47px;
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 15.5px;
  text-align: center;
}

.release-details {
  display: grid;
  gap: 8px;
  margin: 14px 0;
  font: var(--font-small);
  overflow-wrap: anywhere;
}

.release-details dt {
  color: var(--sc-text-secondary);
}

.release-details dd {
  margin: 0;
  color: var(--sc-text);
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
}

@media (min-width: 1200px) {
  .platforms-section {
    padding-block: 32px 40px;
  }
  .platforms-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
