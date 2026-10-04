<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  required: { type: Boolean, default: false },
  error: { type: String, default: '' },
  hint: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  maxLength: { type: Number, default: 0 },
  // Required by AUTH-LANDING-PAGES-HANDOFF §12: `email` on every email field and
  // `new-password` on both /reset fields, so password managers offer to generate and
  // store rather than autofilling the old password into a "choose a new one" box.
  autocomplete: { type: String, default: undefined },
  id: { type: String, default: () => 'field-' + Math.random().toString(36).substr(2, 9) },
  /**
   * How a password field's reveal control looks. `icon` (the default) is the eye in a 28px
   * button, as on /signin; `text` is the word Show / Hide, as the reset frames draw it
   * (AUTH-LANDING-PAGES-HANDOFF 5.1, 8.2, 12). Either way it is a real button with
   * `aria-pressed` and an accessible name that says what it does.
   */
  revealStyle: {
    type: String,
    default: 'icon',
    validator: (val: string) => ['icon', 'text'].includes(val)
  },
  /**
   * How an error begins. `icon` (the default) is the circle-exclamation SVG; `glyph` is a
   * visible cross at the start of the message ("✕ Password must be ..."), because the auth
   * handoff wants the cue to be in the text itself, not an image (section 12).
   */
  errorStyle: {
    type: String,
    default: 'icon',
    validator: (val: string) => ['icon', 'glyph'].includes(val)
  }
})

const emit = defineEmits(['update:modelValue', 'blur', 'focus'])

const showPassword = ref(false)

/** Anything but an exact `text` / `glyph` is the existing look; no third style by accident. */
const textReveal = computed(() => props.revealStyle === 'text')
const glyphError = computed(() => props.errorStyle === 'glyph')

const inputType = computed(() => {
  if (props.type === 'password') {
    return showPassword.value ? 'text' : 'password'
  }
  return props.type
})

const charCount = computed(() => {
  return String(props.modelValue || '').length
})

/**
 * A password field is never spell-checked, auto-corrected or auto-capitalised, hidden OR shown
 * (review of PR 173, Shadow 1). Pressing Show turns the input into `type="text"`, and a text
 * field is sent to the browser's spell checker (Chrome's Enhanced Spell Check and Edge's
 * Microsoft Editor upload what is typed) and learned by a phone keyboard.
 *
 * Known and left alone (Shadow 2): Vue also writes the typed value into the `value` ATTRIBUTE
 * (vuejs/core#6007, framework behaviour). Nothing on the site serialises the DOM today (no
 * analytics, session replay or crash reporting). Whoever adds such a tool must mask by field
 * (`.form-field`, `autocomplete*="password"`), not by `input[type=password]`, which a revealed
 * password no longer matches.
 */
const isPassword = computed(() => props.type === 'password')

const handleInput = (event: Event) => {
  const val = (event.target as HTMLInputElement).value
  emit('update:modelValue', val)
}
</script>

<template>
  <div :class="['form-field', { 'has-error': !!error, 'is-disabled': disabled, 'has-label-action': !!$slots['label-action'] }]">
    <label v-if="label" :for="id" class="field-label">
      {{ label }}
      <span v-if="required" class="required-star" aria-hidden="true">*</span>
    </label>

    <div class="input-wrapper">
      <textarea
        v-if="type === 'textarea'"
        :id="id"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :maxlength="maxLength > 0 ? maxLength : undefined"
        :aria-required="required ? 'true' : undefined"
        :aria-invalid="!!error"
        :aria-describedby="error ? `${id}-error` : hint ? `${id}-hint` : undefined"
        class="field-input field-textarea"
        @input="handleInput"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      ></textarea>

      <input
        v-else
        :id="id"
        :type="inputType"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :autocomplete="autocomplete"
        :spellcheck="isPassword ? 'false' : undefined"
        :autocorrect="isPassword ? 'off' : undefined"
        :autocapitalize="isPassword ? 'off' : undefined"
        :aria-required="required ? 'true' : undefined"
        :aria-invalid="!!error"
        :aria-describedby="error ? `${id}-error` : hint ? `${id}-hint` : undefined"
        :class="['field-input', { 'has-reveal-text': textReveal && type === 'password' }]"
        @input="handleInput"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      />

      <button
        v-if="type === 'password'"
        type="button"
        :class="['password-toggle', { 'is-text': textReveal }]"
        :aria-label="showPassword ? 'Hide password' : 'Show password'"
        :aria-pressed="showPassword"
        @click="showPassword = !showPassword"
      >
        <span v-if="textReveal" class="reveal-text">{{ showPassword ? 'Hide' : 'Show' }}</span>
        <svg v-else-if="showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
          <line x1="1" y1="1" x2="23" y2="23" />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      </button>
    </div>

    <div v-if="$slots['label-action']" class="label-action">
      <slot name="label-action"></slot>
    </div>

    <div class="field-meta">
      <p v-if="error" :id="`${id}-error`" :class="['field-error', { 'is-glyph': glyphError }]" role="alert">
        <span v-if="glyphError" class="error-glyph" aria-hidden="true">✕ </span>
        <svg v-else viewBox="0 0 20 20" fill="currentColor" class="error-icon">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>
        {{ error }}
      </p>
      <p v-else-if="hint" :id="`${id}-hint`" class="field-hint">
        {{ hint }}
      </p>
      
      <span v-if="type === 'textarea' && maxLength > 0" class="char-count" :class="{ 'at-limit': charCount >= maxLength }">
        {{ charCount }}/{{ maxLength }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
  text-align: left;
}

.field-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--sc-text);
  display: flex;
  align-items: center;
  gap: 4px;
}

.required-star {
  color: var(--sc-live);
}

.input-wrapper {
  position: relative;
  width: 100%;
}

.field-input {
  width: 100%;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 10px;
  padding: 12px 16px;
  font-family: var(--font-family);
  font-size: 15px;
  color: var(--sc-text);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  box-sizing: border-box;
}

.field-input::placeholder {
  color: var(--sc-text-muted);
}

.field-input:focus {
  outline: none;
  border-color: var(--sc-primary);
  box-shadow: 0 0 0 3px rgba(110, 92, 240, 0.25);
}

.field-textarea {
  min-height: 110px;
  resize: vertical;
  line-height: 1.5;
}

.has-error .field-input {
  border-color: var(--sc-live);
}

.has-error .field-input:focus {
  box-shadow: 0 0 0 3px rgba(255, 77, 77, 0.2);
}

.is-disabled .field-input {
  opacity: 0.5;
  cursor: not-allowed;
}

.password-toggle {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--sc-text-muted);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color var(--transition-fast);
}

.password-toggle:hover {
  color: var(--sc-text);
}

.password-toggle svg {
  width: 20px;
  height: 20px;
}

/* The word Show / Hide in place of the eye (reset frames): 12.5px/500 on the secondary ink,
   a 44px-tall target whose text ends 14px from the field's edge (Figma: input right edge 899,
   text right edge 885; here 4px + 10px padding), and room in the field so a long password
   never runs under it. */
.password-toggle.is-text {
  right: 4px;
  height: 44px;
  padding: 0 10px;
  font-family: var(--font-family);
  font-size: 12.5px;
  font-weight: 500;
  color: var(--sc-text-secondary);
}

.password-toggle.is-text:hover {
  color: var(--sc-text);
}

.field-input.has-reveal-text {
  padding-right: 64px;
}

/* 44x44 on phones and coarse pointers (the desktop keeps the compact 28px control), and
   16px field text so iOS Safari does not zoom the page on focus. */
@media (max-width: 767.98px), (pointer: coarse) {
  .password-toggle {
    right: 2px;
    width: 44px;
    height: 44px;
    padding: 0;
  }
  .field-input { font-size: 16px; }
  .password-toggle.is-text {
    right: 4px;
    width: auto;
    min-width: 44px;
    padding: 0 10px;
  }
}

/* The label row: label on the left, an action ("Forgot?") on the right. The action comes
   AFTER the input in the DOM (tab order) and is placed on row 1 here. Only a field that is
   given the slot becomes a grid; every other field keeps the column it always was. */
.form-field.has-label-action {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 6px 12px;
}

.has-label-action .field-label { grid-column: 1; grid-row: 1; }
.has-label-action .label-action { grid-column: 2; grid-row: 1; align-self: center; }
.has-label-action .input-wrapper { grid-column: 1 / -1; grid-row: 2; }
.has-label-action .field-meta { grid-column: 1 / -1; grid-row: 3; }

.label-action :slotted(a),
.label-action :slotted(button) {
  font-family: var(--font-family);
  font-size: 13px;
  font-weight: 500;
  color: var(--sc-primary);
  text-decoration: none;
}

.label-action :slotted(a:hover),
.label-action :slotted(button:hover) {
  text-decoration: underline;
}

@media (max-width: 767.98px), (pointer: coarse) {
  .label-action :slotted(a),
  .label-action :slotted(button) {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
  }
}

.field-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  min-height: 20px;
}

.field-error {
  color: var(--sc-live);
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0;
  font-weight: 500;
}

/* "✕ message": the cross is text at the start of the message, so the message sits flush with
   the field's edge. 12.5px/500 on a 17px line (Figma reset-r2). */
.field-error.is-glyph {
  display: block;
  font-size: 12.5px;
  line-height: 17px;
}

.error-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.field-hint {
  color: var(--sc-text-muted);
  margin: 0;
}

.char-count {
  color: var(--sc-text-muted);
  font-size: 12px;
  margin-left: auto;
}

.char-count.at-limit {
  color: var(--sc-live);
  font-weight: 600;
}
</style>
