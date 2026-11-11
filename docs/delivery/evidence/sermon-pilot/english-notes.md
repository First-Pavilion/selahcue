# C3 English sermon notes — redacted source evidence

2026-11-11. Task: [17tnw2bey5u](https://app.clickup.com/t/17tnw2bey5u). Base: `940cb1f1b70f6ec18d2a3a1a16dcf3d7da6cb65b`, reviewed C2 above C1. This patch owns C3 only; combined-stack integration and review remain required before merge.

The OpenAI request now explicitly requests English narrative notes preserving English/Yoruba/Igbo/Hausa meaning and language changes, treats source as data, and prohibits presenting translations as verbatim quotations. No schema, model, provider, threshold, consent or privacy policy changed. On terminal generation failure the Transcripts UI retains rendered prior notes, disclosures and pending Confirm/Discard controls, and offers the existing Regenerate → review → Confirm retry path.

## Verification

All provider material is synthetic, with an in-memory HTTP transport. No credentials, environment fallback, live provider or congregation content was accessed.

- Request regression was red before the exact language instruction and green after it. It asserts developer/user roles, exact multilingual source bytes including instruction-looking text, selected WEB naming and existing grounding.
- Browser tests were red before the retained-notes fix: accepted content and pending Confirm/Discard disappeared. Production JavaScript now passes these regressions, including backend terminal quota refusal and rejected IPC, repeated failure, explicit retry, no retry on reconnect/idle/navigation and a fresh UI reopening a saved synthetic multilingual fixture.
- Native configured-provider consent control makes three explicit denied attempts with zero transport calls and exact transcript/accepted/pending preservation, then enables consent and sends exactly one request on the same route. Native terminal quota failure sends one request, performs no save/stage, preserves all saved state and permits explicit successful retry through normal staging.
- A real file-backed app/controller test ends a multilingual transcript through `BatchingTranscriptWriter`, saves accepted notes and stages distinct pending notes, drops all old controller/store/database handles, then reopens the database and loads via a fresh controller. Transcript and full accepted/pending repository records compare exactly. This is database/controller reopen evidence, not packaged app reboot evidence.
- Native pilot construction has a provider-ready before-cutoff positive control (one mocked request) and exact/after-cutoff refusal (no client, zero requests). Existing strict cutoff/earliest-provider-expiry coverage remains. PR330's active wall/monotonic/in-flight behavior is not part of this base; its integrated acceptance checks remain open. Hosted-account routing is unchanged.
- Existing real cloud transport-error local fallback, requested-empty sections, truncation disclosures, native app durability and C1/C2 siblings are retained in the affected suites.

Commands run with `CARGO_TARGET_DIR=/private/tmp/selahcue-pilot-a1-target`:

| Command | Result |
| --- | --- |
| `cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-cloud --features openai --test test_openai` | 50 passed |
| `cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-cloud --features openai` | 103 passed |
| `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --features openai-notes` | 469 passed; 1 existing ignored child helper |
| `cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-app --features server` | 369 passed; 1 existing ignored measurement probe |
| `SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py` | 2,973 checks; zero failures |

The app run includes 26 sermon-note durability cases, 11 file-backed/TLS remote cases (including the added actual controller/database reopen), and seven transcript durability cases. All full affected suites exited zero; scoped `rustfmt --check` and `git diff --check` also passed. The ignored operator child helper is launched by its parent test; the app probe is a separate release measurement, not a C3 test.

Exact RED/GREEN commands and local log paths are in the local, ignored `.superpowers/sdd/2026-11-11-sermon-pilot-notes/task-3-report.md` execution report. The browser's mock English response is orchestration evidence only. The evaluation plan and outstanding fluent-speaker/provider outcomes are recorded in [notes-evaluation.md](../../../quality/sermon-pilot/notes-evaluation.md).

## Remaining acceptance gates

Actual English/Yoruba/Igbo/Hausa and mixed-language provider fidelity, fluent-speaker assessment, real provider/data and consent-copy decisions, packaged WebView/platform verification, hosted CI, PR330 integrated admission checks and combined-stack review remain unverified. No push, merge, deployment, external ticket mutation or real provider use is included in this source evidence.
