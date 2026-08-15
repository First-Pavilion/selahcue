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
  id: { type: String, default: () => 'field-' + Math.random().toString(36).substr(2, 9) }
})

const emit = defineEmits(['update:modelValue', 'blur', 'focus'])

const showPassword = ref(false)

const inputType = computed(() => {
  if (props.type === 'password') {
    return showPassword.value ? 'text' : 'password'
  }
  return props.type
})

const charCount = computed(() => {
  return String(props.modelValue || '').length
})

const handleInput = (event: Event) => {
  const val = (event.target as HTMLInputElement).value
  emit('update:modelValue', val)
}
</script>

<template>
  <div :class="['form-field', { 'has-error': !!error, 'is-disabled': disabled }]">
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
        :aria-invalid="!!error"
        :aria-describedby="error ? `${id}-error` : hint ? `${id}-hint` : undefined"
        class="field-input"
        @input="handleInput"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      />

      <button
        v-if="type === 'password'"
        type="button"
        class="password-toggle"
        :aria-label="showPassword ? 'Hide password' : 'Show password'"
        :aria-pressed="showPassword"
        @click="showPassword = !showPassword"
      >
        <svg v-if="showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
          <line x1="1" y1="1" x2="23" y2="23" />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      </button>
    </div>

    <div class="field-meta">
      <p v-if="error" :id="`${id}-error`" class="field-error" role="alert">
        <svg viewBox="0 0 20 20" fill="currentColor" class="error-icon">
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
