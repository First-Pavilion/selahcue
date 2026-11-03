# P15 pilot registration notice evidence

Ticket: [Pilot collection notice](https://app.clickup.com/t/17tnw2bbhxn). Branch `codex/17tnw2bbhxn-pilot-data-notice`, base `4e2ce4374713956a498978fdf6383c74c2c548cb`. Root owns independent reviews, status and merge. No collection, deployment, Google access or deletion execution was performed.

## Implemented source

One authored `docs/release/pilot-registration/notice.json` is consumed by both the marketing `/pilot-privacy` view and the generated n8n pre-submit `formDescription`. Vue interpolates plain text; the generator HTML-escapes each title/paragraph. The Download pilot panel links the notice before registration even while disabled. Existing enabled-config labels accurately distinguish the collection administrator and attempt/receipt lifetime from the fixed record-deletion policy.

The approved notice records purpose/necessary fields, optional phone, n8n/Google Sheets handling, tester ownership of supplied church data, restricted collection administration, pilot end30April2027 and final deletion29July2027 at23:59:59UTC, earlier requests through legal@selahcueapp.com or support@selahcueapp.com, optional separate marketing and separate application cloud consent. No account/payment prerequisite or legal-controller classification was added.

`DATA-HANDLING.md` assigns the procedure to SelahCue support operations, requires an identified restricted administrator before activation, documents verified-contact request handling, retire-before-clear, fixed Sheet row clearing/no allocation recycling, eventual pseudonymous ledger disposal, execution/support/backup copies and exact live activation prerequisites. The fixed deadline is a manual product-policy commitment; no purge automation or backup-erasure guarantee is claimed. Existing per-registration retention_days only retires attempts/receipts and must not be advertised as a Sheet purge.

## Verification

- Exact committed npm lock dependencies installed in this worktree. `npm run build` (including vue-tsc), `npm run lint`: pass. `npm test`:1246passed,0failed. Initial route-inventory failure was corrected by adding the actual route to the responsive sweep inventory; historical failure is not counted as green.
- Deterministic Python generator import/export equality; graph inactive; successful/error execution payload saving disabled; same9form fields and optional phone; committed marketing enabled:false: pass. All shared paragraphs are in the generated pre-submit description. No graph/field/auth/credential changes.
- Actual CUA Chrome at localhost5197 rendered all6notice sections, notice version, fixed date, contact mailto links, ownership and separate-consent language. This proves the built Vue page, not a deployed public site.
- Focused responsive sweep over `/pilot-privacy` and `/download`,375px and1440px: Chromium42checks and WebKit42checks,0failures after correction. Initial both-engine failure found an18/19px back-link target; actual link and contact links now have44pxminimum height. Screenshots/logs are under `/private/tmp/farah-p03-wave1/p15-{chromium,webkit}` and matching `.log` files. Browser fixtures do not submit real personal data or contact remote services.
- `git diff --check` and Goal structural validator: pass.

## Remaining gates and limits

Four independent reviewers and exact-head hosted CI are pending. The pre-submit description is generated into the real inactive graph; an actual pinned n8n rendering check is coordinated with Kenji's synthetic fixture and is distinct from marketing-browser proof. Restricted Sheet/account/credential/mailbox operations, calendared/rehearsed actual deletion and the P11/P12/P13/P14 live end-to-end installer journey remain activation gates. The source does not enable collection or downloads and does not claim those operational prerequisites are complete.
