<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted, useId, useSlots } from 'vue'
import UiButton from './UiButton.vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  consequences: { type: Array as () => string[], default: () => [] },
  confirmLabel: { type: String, default: 'Confirm' },
  cancelLabel: { type: String, default: 'Cancel' },
  requireType: { type: String, default: '' }, // String user must type to confirm (e.g. "cancel")
  variant: { type: String, default: 'danger' }, // 'danger' | 'warning'
  /**
   * `centered` (the default) is the existing dialog: 440px, a tinted disc icon, centred text.
   * `left` is the Manage Devices confirm (Figma D2, 754:242): 420px, a bare `!`, left-aligned
   * text, a banner under the text, two equal buttons and a hint under them. Same component,
   * same behaviour; only the look differs.
   */
  layout: {
    type: String,
    default: 'centered',
    validator: (val: string) => ['centered', 'left'].includes(val)
  },
  /** A muted line under the buttons ("Esc keeps the device active."). */
  hint: { type: String, default: '' }
})

const emit = defineEmits(['confirm', 'cancel', 'update:show'])

const typedValue = ref('')

/** Anything but an exact `left` is the existing look. */
const isLeft = computed(() => props.layout === 'left')

/** The dialog names itself and its description for assistive technology. */
const uid = useId()
const titleId = `${uid}-title`
const descId = `${uid}-desc`

/** A block under the text: the "Nothing goes dark" banner of the devices confirm. */
const slots = useSlots()
const hasBanner = computed(() => !!slots['banner'])

const card = ref<HTMLElement | null>(null)

const isConfirmDisabled = () => {
  if (props.requireType) {
    return typedValue.value.trim().toLowerCase() !== props.requireType.toLowerCase()
  }
  return false
}

const handleConfirm = () => {
  if (!isConfirmDisabled()) {
    emit('confirm')
    emit('update:show', false)
  }
}

const handleCancel = () => {
  emit('cancel')
  emit('update:show', false)
}

/*
 * Modal behaviour (GAP-FILL 7a/7b, AUTH-LANDING-PAGES-HANDOFF 7.2 and 12): the safe action,
 * Cancel, takes the initial focus; Tab and Shift+Tab stay inside the dialog; Escape is Cancel;
 * the page behind does not scroll; and focus goes back to whatever opened the dialog.
 */
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

let opener: HTMLElement | null = null
let previousOverflow = ''

const focusables = (): HTMLElement[] =>
  card.value ? Array.from(card.value.querySelectorAll<HTMLElement>(FOCUSABLE)) : []

const focusInitial = () => {
  const cancel = card.value?.querySelector<HTMLElement>('.dialog-cancel')
  ;(cancel ?? focusables()[0] ?? card.value)?.focus()
}

const trapTab = (e: KeyboardEvent) => {
  const items = focusables()
  const first = items[0]
  const last = items[items.length - 1]
  if (!first || !last) {
    e.preventDefault()
    card.value?.focus()
    return
  }
  const active = document.activeElement
  if (!card.value?.contains(active)) {
    e.preventDefault()
    ;(e.shiftKey ? last : first).focus()
  } else if (e.shiftKey && active === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && active === last) {
    e.preventDefault()
    first.focus()
  }
}

/** Focus that lands outside the dialog (a script, a click on the scrim) is brought back in. */
const keepFocusInside = (e: FocusEvent) => {
  if (props.show && card.value && e.target instanceof Node && !card.value.contains(e.target)) focusInitial()
}

const handleKeydown = (e: KeyboardEvent) => {
  if (!props.show) return
  if (e.key === 'Escape') handleCancel()
  else if (e.key === 'Tab') trapTab(e)
}

let engaged = false

const engage = () => {
  if (engaged) return
  engaged = true
  opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  document.addEventListener('focusin', keepFocusInside)
  void nextTick(focusInitial)
}

const release = () => {
  if (!engaged) return
  engaged = false
  document.removeEventListener('focusin', keepFocusInside)
  document.body.style.overflow = previousOverflow
  const back = opener
  opener = null
  if (back?.isConnected) back.focus()
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    typedValue.value = ''
    engage()
  } else {
    release()
  }
})

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  if (props.show) engage()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  release()
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="show" class="dialog-scrim" :class="{ 'layout-left': isLeft }" @click.self="handleCancel">
        <div
          ref="card"
          class="dialog-card"
          role="alertdialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          :aria-describedby="description ? descId : undefined"
          tabindex="-1"
        >
          <div v-if="!isLeft" class="dialog-icon-wrapper" :class="variant">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="dialog-icon">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <div v-else class="dialog-glyph" :class="variant" aria-hidden="true">!</div>

          <h3 :id="titleId" class="dialog-title">{{ title }}</h3>
          <p v-if="description" :id="descId" class="dialog-desc">{{ description }}</p>

          <ul v-if="consequences.length > 0" class="consequence-list">
            <li v-for="(item, idx) in consequences" :key="idx" class="consequence-item">
              <span class="bullet">•</span> {{ item }}
            </li>
          </ul>

          <div v-if="hasBanner" class="dialog-banner">
            <slot name="banner"></slot>
          </div>

          <div v-if="requireType" class="type-confirm-wrapper">
            <label class="type-label">
              Type <strong>"{{ requireType }}"</strong> to confirm:
            </label>
            <input 
              v-model="typedValue"
              type="text"
              class="type-input"
              :placeholder="requireType"
              @keyup.enter="handleConfirm"
            />
          </div>

          <div class="dialog-actions">
            <UiButton variant="ghost" class="dialog-cancel" @click="handleCancel">
              {{ cancelLabel }}
            </UiButton>
            <UiButton 
              :variant="variant === 'danger' ? 'primary' : 'secondary'"
              :disabled="isConfirmDisabled()"
              class="confirm-btn"
              :class="variant"
              @click="handleConfirm"
            >
              {{ confirmLabel }}
            </UiButton>
          </div>

          <p v-if="hint" class="dialog-hint">{{ hint }}</p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.dialog-scrim {
  position: fixed;
  inset: 0;
  background: rgba(11, 13, 18, 0.75);
  backdrop-filter: blur(8px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.dialog-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  max-width: 440px;
  width: 100%;
  padding: 32px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  text-align: center;
  animation: slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  /* A tall dialog (consequence list + type-to-confirm) on a short landscape phone scrolls
     inside itself instead of running off the top and bottom of the screen. */
  max-height: 100%;
  overflow-y: auto;
}

.dialog-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  margin: 0 auto 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-icon-wrapper.danger {
  background: var(--sc-live-soft);
  color: var(--sc-live);
  border: 1px solid var(--sc-live-border);
}

.dialog-icon-wrapper.warning {
  background: var(--sc-warn-soft);
  color: var(--sc-warn);
  border: 1px solid var(--sc-warn-border);
}

.dialog-icon {
  width: 24px;
  height: 24px;
}

.dialog-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0 0 12px 0;
}

.dialog-desc {
  font-size: 15px;
  color: var(--sc-text-secondary);
  line-height: 1.5;
  margin: 0 0 20px 0;
}

.consequence-list {
  list-style: none;
  padding: 0;
  margin: 0 0 24px 0;
  text-align: left;
  background: var(--sc-elevated);
  border-radius: 10px;
  padding: 16px;
  border: 1px solid var(--sc-border);
}

.consequence-item {
  font-size: 14px;
  color: var(--sc-text-secondary);
  margin-bottom: 8px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.consequence-item:last-child {
  margin-bottom: 0;
}

.bullet {
  color: var(--sc-live);
  font-weight: bold;
}

.type-confirm-wrapper {
  margin-bottom: 24px;
  text-align: left;
}

.type-label {
  font-size: 13px;
  color: var(--sc-text-secondary);
  display: block;
  margin-bottom: 8px;
}

.type-input {
  width: 100%;
  background: var(--sc-inset);
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  padding: 10px 14px;
  font-family: var(--font-family);
  font-size: 14px;
  color: var(--sc-text);
  box-sizing: border-box;
}

.type-input:focus {
  outline: none;
  border-color: var(--sc-primary);
}

.dialog-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

@media (max-width: 767.98px) {
  .dialog-scrim { padding: 16px; }
  .dialog-card { padding: 24px 20px; }
  .dialog-actions { flex-direction: column-reverse; }
  .dialog-actions > * { width: 100%; }
  .type-input { min-height: 44px; font-size: 16px; }
}

.confirm-btn.danger {
  background: var(--sc-live) !important;
  color: white !important;
}

.confirm-btn.danger:hover {
  background: #ff3333 !important;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

@keyframes slideUp {
  from { transform: translateY(12px) scale(0.97); opacity: 0; }
  to { transform: translateY(0) scale(1); opacity: 1; }
}
.dialog-hint {
  margin: 16px 0 0;
  font-size: 12px;
  line-height: 15px;
  color: var(--sc-text-secondary);
}

/*
 * layout="left": the Manage Devices confirm (Figma D2, 754:242). Everything here is opt-in;
 * the dialogs above are untouched. 420px, --sc-elevated, padding 28/28/24/28, 16px between
 * blocks; scrim --sc-base at 72% and no blur (none is drawn).
 */
.layout-left {
  background: rgba(11, 13, 18, 0.72);
  backdrop-filter: none;
}

.layout-left .dialog-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 420px;
  padding: 28px 28px 24px;
  background: var(--sc-elevated);
  text-align: left;
}

.layout-left .dialog-title,
.layout-left .dialog-desc,
.layout-left .consequence-list,
.layout-left .type-confirm-wrapper,
.layout-left .dialog-hint {
  margin: 0;
}

/* The bare `!` (30/700, no disc), in the variant's tone. */
.dialog-glyph {
  font-size: 30px;
  font-weight: 700;
  line-height: 36px;
}

.dialog-glyph.warning {
  color: var(--sc-warn);
}

.dialog-glyph.danger {
  color: var(--sc-live);
}

.layout-left .dialog-title {
  font-size: 18px;
  font-weight: 600;
  line-height: 22px;
}

.layout-left .dialog-desc {
  font-size: 14px;
  line-height: 20px;
}

/*
 * Two equal buttons. Cancel is the outline with the 1.5px brand ring; Confirm is the live
 * red. 44px tall, not the drawn 41px: the handoff (section 12) and the responsive sweep both
 * hold every target to 44.
 *
 * THE CONFIRM LABEL: Figma draws white on #ef4444, 3.76:1, which fails WCAG AA (audit
 * account-31, class D: Uma chooses the accessible destructive button). The accessible dark
 * ink stays until she does (--sc-base on --sc-live is 5.9:1). The fill and the ink are each
 * one property, `--dialog-destructive-fill` and `--dialog-destructive-ink`, deliberately not
 * declared here so that a line in tokens.css sets them. `!important` is the existing
 * `.confirm-btn.danger` rule's own, which this has to outrank.
 */
.layout-left .dialog-actions {
  gap: 10px;
  justify-content: stretch;
}

.layout-left .dialog-actions > * {
  flex: 1 1 0;
  min-width: 0;
  height: 44px;
  min-height: 44px;
  padding: 0 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
}

.layout-left .dialog-actions .dialog-cancel {
  border: 1.5px solid var(--sc-primary);
  background: transparent;
  color: var(--sc-text);
}

.layout-left .dialog-actions .dialog-cancel:hover {
  background: var(--sc-accent-soft);
}

.layout-left .dialog-actions .confirm-btn {
  background: var(--dialog-destructive-fill, var(--sc-live)) !important;
  color: var(--dialog-destructive-ink, var(--sc-base)) !important;
}

.layout-left .dialog-actions .confirm-btn:hover {
  filter: brightness(1.08);
}

@media (max-width: 767.98px) {
  .layout-left .dialog-card { padding: 24px 20px 20px; }
  .layout-left .dialog-actions { flex-direction: row; }
}

/* Below 480px two buttons side by side stop fitting a longer label: stack them, Cancel last
   in the DOM order reversed so the safe action is still the first thing the eye lands on. */
@media (max-width: 479.98px) {
  .layout-left .dialog-actions { flex-direction: column-reverse; }
  .layout-left .dialog-actions > * { flex: 0 0 auto; width: 100%; }
}
</style>
