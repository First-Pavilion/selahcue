// ESLint flat config for the marketing site (Vue 3 SFCs + TypeScript).
//
// Deliberately the stock recommended sets and nothing else. The gate exists so that real
// defects (unused/undefined bindings, bad v-for keys, unsafe v-html, `any` creep) fail a
// build; it is not a style police. Formatting rules are intentionally absent -- there is no
// formatter configured for this package, and adding one is a separate decision.
//
// `npm run lint` passes --max-warnings 0, so a rule set to "warn" still fails the gate.
// A warning that cannot fail anything is how a lint run ends up ignored.
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    // Build output and installed packages are not source. `.tmp` holds tsbuildinfo only.
    ignores: ['dist/**', 'node_modules/**'],
  },

  js.configs.recommended,
  tseslint.configs.recommended,
  // `essential` is the error-prevention tier only. The `recommended` and
  // `strongly-recommended` tiers add attribute-per-line, hyphenation and line-break rules
  // that are formatting, and flag ~1,300 existing sites for it.
  pluginVue.configs['flat/essential'],

  {
    // `.vue` files carry TypeScript in <script setup lang="ts">; hand the script block to
    // the TypeScript parser (vue-eslint-parser owns the SFC, this owns the script inside).
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: tseslint.parser },
    },
  },

  {
    files: ['**/*.{ts,vue}'],
    rules: {
      // The TypeScript compiler (vue-tsc, run by `npm run type-check`) already reports an
      // undefined name as an error, and understands ambient types and browser/node globals
      // that this rule does not. typescript-eslint's own FAQ recommends turning it off for
      // TS code; it is switched off for .vue here because the stock config only does so
      // for .ts files.
      'no-undef': 'off',
    },
  },

  {
    files: ['src/**/*.vue'],
    rules: {
      // Guards against `<Footer>` colliding with the HTML `<footer>` element. That collision
      // only happens in in-DOM templates (a template written inside the page's own HTML),
      // and this app compiles every template from an SFC, so it cannot occur. Footer,
      // Navbar and Toast are established single-word component names imported all over the
      // app; renaming them would be churn with no safety gain.
      'vue/multi-word-component-names': 'off',
    },
  },
)
