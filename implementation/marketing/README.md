# Vue 3 + TypeScript + Vite

This template should help get you started developing with Vue 3 and TypeScript in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about the recommended Project Setup and IDE Support in the [Vue Docs TypeScript Guide](https://vuejs.org/guide/typescript/overview.html#project-setup).

## Legal pages (`/privacy`, `/terms`)

The Privacy Policy and Terms of Service are **not written in this package**. The source of truth is
`docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md` and `docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md`.
`scripts/sync_legal.ts` turns them into typed content in `src/lib/legal/*.generated.ts` (committed, because
the Docker build context is this folder only and cannot read `docs/`). The pages render that content with
templates only (no `v-html`).

- **After editing a draft in `docs/legal`, run `npm run sync:legal` and commit the regenerated files.**
  `npm run check:legal` reports whether they are in step (exit 0 ok, 1 stale, 2 could not run).
  The `legal-drift` workflow runs it on every change to `docs/legal/**`, because `ci.yml` ignores docs.
- The generator **throws, naming file and line, on any markdown it does not support** instead of dropping
  it. It understands headings, numbered clauses (`3.8 ...`), `-` lists, tables, bold, inline code, safe
  links and the DRAFT blockquote; see the header of `scripts/legal_markdown.ts`.
- **A draft fails closed.** A page shows the draft banner, highlights placeholders and sends `noindex`
  while ANY of these holds: a `{{PLACEHOLDER}}` remains, the document still has its DRAFT banner, or its
  version status is anything other than exactly `final` (so `final draft`, `pending review` or a typo stay drafts). Filling every placeholder is not publishing.
- **To publish** (only once the launch-readiness conditions in `docs/legal/LEGAL-DRAFT-NOTES.md`
  section 4 are met): in the markdown, delete the DRAFT `>` banner, make sure a
  `Version X.Y (final, YYYY-MM-DD).` paragraph sits directly under the `#` title (generation fails if there
  is no version line, so "Last updated" cannot silently disappear), and fill every placeholder; then run
  `npm run sync:legal`. No code changes.
- Tests: `npm test` (content pipeline, drift, rendering). `npm run test:legal-pages` builds the site and
  drives `/privacy` and `/terms` in real Chrome at five widths (needs `pip install playwright`).
