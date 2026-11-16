<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import UiButton from '@/components/UiButton.vue'
import ToneChip from '@/components/core/ToneChip.vue'
import { architectures, platforms, loadPilotConfig, pilotEntryState, registrationIdentity, registrationLink, type Architecture, type Platform, type PilotConfig } from '@/lib/pilot/downloads.ts'

const platform = ref<Platform>('Windows')
const architecture = ref<Architecture>('x64')
const config = ref<PilotConfig>({ enabled: false, entries: [] })
const loading = ref(true)
const failed = ref(false)
const now = ref(Date.now())
const state = computed(() => pilotEntryState(config.value, platform.value, architecture.value, now.value))
const handoff = ref<string>()
const identityError = ref(false)
const attempt = computed(() => state.value.status === 'ready' && state.value.entry ? JSON.stringify([platform.value, architecture.value, state.value.entry.release_id, state.value.entry.registration_url]) : undefined)
function prepareRegistration(reset = false) {
  handoff.value = undefined
  identityError.value = false
  if (!attempt.value || !state.value.url) return
  try {
    const id = registrationIdentity(sessionStorage, attempt.value, () => crypto.randomUUID(), reset)
    handoff.value = registrationLink(state.value.url, platform.value, id)
  } catch { identityError.value = true }
}
watch(attempt, () => prepareRegistration())
let request: AbortController | undefined
let timer: ReturnType<typeof setInterval> | undefined
let disposed = false
async function retry() {
  request?.abort()
  const current = new AbortController()
  request = current
  loading.value = true
  failed.value = false
  config.value = { enabled: false, entries: [] }
  try {
    const result = await loadPilotConfig(fetch, current.signal)
    if (!disposed && request === current) config.value = result
  } catch {
    if (!disposed && request === current) failed.value = true
  } finally {
    if (!disposed && request === current) loading.value = false
  }
}
function guardNavigation(event: MouseEvent) {
  // Check wall time again on activation: a tab can be suspended across expiry.
  now.value = Date.now()
  if (state.value.status !== 'ready' || !handoff.value || identityError.value) event.preventDefault()
}
onMounted(() => { void retry(); timer = setInterval(() => { now.value = Date.now() }, 1000) })
onUnmounted(() => { disposed = true; request?.abort(); clearInterval(timer) })
</script>

<template>
  <section id="pilot-downloads" class="pilot-section" aria-labelledby="pilot-heading">
    <div class="container">
      <div class="pilot-card">
        <ToneChip kind="row" tone="brand">FIELD TEST PILOT</ToneChip>
        <h2 id="pilot-heading" tabindex="-1">Try SelahCue at your church</h2>
        <p>Choose your desktop platform. Before downloading, complete the hosted registration form with your details and your church details. Confirm your platform on the form.</p>
        <p>Core live controls work offline. Pilot Deepgram transcription and OpenAI assistance require internet access and consent. Pilot provider access ends at the pilot end date; core offline controls remain available.</p>
        <div class="pilot-selectors">
          <div><label for="pilot-platform">Operating system</label><select id="pilot-platform" v-model="platform"><option v-for="item in platforms" :key="item">{{ item }}</option></select></div>
          <div><label for="pilot-architecture">Processor architecture</label><select id="pilot-architecture" v-model="architecture"><option v-for="item in architectures" :key="item" :value="item">{{ item === 'x64' ? 'x64 (Intel / AMD 64-bit)' : 'ARM64 (including Apple silicon)' }}</option></select></div>
        </div>
        <div id="pilot-status" role="status" aria-live="polite" aria-atomic="true">
          <p v-if="loading">Checking pilot availability…</p>
          <p v-else-if="failed">We couldn’t check pilot availability. Please retry. No registration or download has started.</p>
          <p v-else-if="!config.enabled">Pilot registration is not open yet. Download and registration details are being prepared.</p>
          <template v-else>
            <p v-if="state.status === 'expired'">This pilot package has expired. Registration for this package is closed.</p>
            <p v-else-if="state.status === 'unavailable'">No pilot package is available for this platform and architecture yet.</p>
            <p v-else>Available for pilot registration. Complete the form before downloading.</p>
            <dl v-if="state.entry" class="pilot-metadata">
              <div><dt>Version</dt><dd>{{ state.entry.version }}</dd></div>
              <div><dt>Pilot expires (UTC)</dt><dd><time :datetime="state.entry.expires_at">{{ state.entry.expires_at.replace('T', ' ').replace('Z', ' UTC') }}</time></dd></div>
            </dl>
          </template>
        </div>
        <UiButton v-if="failed" variant="secondary" @click="retry">Retry availability check</UiButton>
        <UiButton v-else :href="!loading && state.status === 'ready' ? handoff : undefined" :disabled="loading || state.status !== 'ready' || !handoff" :aria-disabled="loading || state.status !== 'ready' || !handoff" referrerpolicy="no-referrer" aria-describedby="pilot-status pilot-form-note" class="pilot-action" @click="guardNavigation">Continue to registration</UiButton>
        <div v-if="identityError" role="alert">
          <p>We couldn’t safely retain your registration attempt. Allow session storage, then retry. An existing attempt will not be replaced automatically.</p>
          <UiButton variant="secondary" @click="prepareRegistration()">Retry registration setup</UiButton>
        </div>
        <div v-if="!loading && state.status === 'ready'" class="pilot-note">
          <p id="pilot-reset-note">Returning after a failed submission? Continue to registration reuses your attempt. Start a new registration only when you intend to replace it; this may create another registration record.</p>
          <UiButton variant="ghost" aria-describedby="pilot-reset-note" @click="prepareRegistration(true)">Start a new registration</UiButton>
        </div>
        <p class="pilot-note"><router-link to="/pilot-privacy">Read how pilot registration details are handled and how to request deletion</router-link>. Registration does not create an account, require payment or subscribe you to marketing. Cloud audio consent is separate.</p>
        <p id="pilot-form-note" class="pilot-note">The registration form opens in this tab. If it cannot save your details or start your download, follow its retry instructions.</p>
        <p v-if="config.enabled && config.notice" class="pilot-note">Collection administrator: {{ config.notice.data_owner }}. Registration attempt lifetime: {{ config.notice.retention_days }} days. Download receipts expire separately after a short period. The pilot data notice gives the fixed record deletion deadline. <a :href="config.notice.url" referrerpolicy="no-referrer">Read the pilot data notice</a> ({{ config.notice.version }}).</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.pilot-section { padding-block: 32px 48px; scroll-margin-top: var(--sc-anchor-offset); }
.pilot-card { display: flex; flex-direction: column; align-items: flex-start; gap: 18px; padding: 32px; border: 1px solid var(--sc-border); border-radius: 20px; background: var(--sc-surface); min-width: 0; }
h2 { margin: 0; font: 700 32px/1.2 var(--font-family); }
p { margin: 0; color: var(--sc-text-secondary); line-height: 1.6; max-width: 80ch; }
.pilot-selectors { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; width: 100%; }
.pilot-selectors > div { min-width: 0; }
label { display: block; margin-bottom: 8px; font-weight: 600; }
select { appearance: none; width: 100%; min-height: 48px; background-image: linear-gradient(45deg, transparent 50%, currentColor 50%), linear-gradient(135deg, currentColor 50%, transparent 50%); background-position: calc(100% - 18px) 50%, calc(100% - 13px) 50%; background-size: 5px 5px; background-repeat: no-repeat; padding-right: 32px; padding: 12px; background: var(--sc-elevated); color: var(--sc-text); border: 1px solid var(--sc-border); border-radius: 10px; font: inherit; }
select:focus-visible, a:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 3px; }
.pilot-metadata { display: flex; flex-wrap: wrap; gap: 16px 32px; margin: 18px 0 0; }
dt { color: var(--sc-text-secondary); font-size: 13px; }
dd { margin: 4px 0 0; overflow-wrap: anywhere; }
.pilot-note { font-size: 14px; overflow-wrap: anywhere; }
a { color: var(--sc-text); text-decoration: underline; }
@media (max-width: 599.98px) { .pilot-card { padding: 24px; } .pilot-selectors { grid-template-columns: minmax(0, 1fr); } h2 { font-size: 26px; } .pilot-action { width: 100%; } }
</style>
