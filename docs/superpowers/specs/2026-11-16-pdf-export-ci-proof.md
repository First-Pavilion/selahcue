# Operator PDF export CI proof

The open dependency reviews require actual output verification after the HarfRust caller repair. The existing ignored `notes_export_tests::author_pdf_inspection_fixtures` already exercises the real renderer and independent parser, but ordinary CI never invokes it. Local runtime remains held for paging. The user's review/fix/merge instruction authorizes adding this missing hosted validation.

## Decision

Use the existing Linux operator job: its compilation, native dependencies and warm test binary are already owned by normal CI. A separate duplicate native build would cost more; enabling every ignored test would run unrelated helpers. Add only the named authoring test, its isolated Python parser environment, Poppler renders and a short-lived artifact. Existing Windows coverage stays in the repository's Windows tier; no macOS job is added.

This is validation wiring, not a new PDF implementation or a claimed layout fix. The HarfRust task has actual historical compiler RED. This task does not invent a behavioral RED for an already existing oracle or add a test that merely mirrors YAML text.

## Binding behavior

- Implementation ownership is only `.github/workflows/ci.yml`, in the existing `operator` job. Preserve all existing gates, conditions, permissions, timeouts, OS selection, toolchain pins and production source. Preserve frozen delivery evidence and the PDF test/oracle verbatim.
- Before the first Format gate, on Linux only, set up the same `actions/setup-python@v7` used elsewhere with Python `3.14`; create a fresh virtual environment at `$RUNNER_TEMP/selahcue-pdf-oracle`; install only binary distributions with exact direct versions `pypdf==6.21.4` and `pdfplumber==0.11.9`. Record the resolved installed versions with `pip freeze`. Limit this parser setup step to five minutes. Add `poppler-utils` to the existing Linux apt package list.
- After the existing default Test step, add a Linux-only gate under `!cancelled()` with a five-minute step limit. Set `C4_PDF_FIXTURES` to `${{ runner.temp }}/selahcue-pdf-fixtures`, and `C4_PDF_PYTHON` to `${{ runner.temp }}/selahcue-pdf-oracle/bin/python`. Run exactly `cargo test --locked --bin selahcue-operator notes_export_tests::author_pdf_inspection_fixtures -- --ignored --exact --nocapture` from the existing operator working directory.
- The existing oracle must succeed, asserting the complete normal and long text, rejected negative controls, embedded font, NFC/NFD names, bounds and one/eight pages. Then render both produced PDFs with `pdftoppm -r 144 -png`, using distinct `saved-a-unicode` and `saved-long` output prefixes in the same owned fixture directory. Missing output or renderer failure must fail the gate. No replacement renderer, retries, relaxed assertions, fallbacks, or `continue-on-error`.
- Print `pdfinfo` for both files and SHA-256 receipts for the actual PDFs and expected JSON. The generated directory is fixed synthetic content. Refuse an artifact directory larger than 20 MiB. Do not capture environment variables, credentials, live transcripts or unrelated workspace files.
- Upload only that fixture directory with the repository's existing `actions/upload-artifact@v7`, a unique name using run ID and attempt, `retention-days: 7`, `if-no-files-found: error`, and no overwrite. Run upload only on Linux after a successful PDF proof step; an upload failure remains a job failure. PDFs, PNG pages and expected JSON are review inputs, not published downloads.
- Root runs the PDF skill's operation marker exactly once with expected output count two immediately before the first remote authoring dispatch. Root retrieves and visually inspects all nine rendered pages and verifies hashes and native test results. A successful test alone is not visual acceptance.
- Local runtime remains held: no project tests, builds, imports, installs or browsers. Static YAML/shell inspection, existing actionlint and Git checks are allowed. Root owns push, CI and reviews. One source implementer; preserve others' work and sibling plans.

## Verification and limits

Current hosted actionlint/minutes/security checks must pass. The Linux operator job must execute the single ignored fixture case successfully, upload the artifacts and retain the existing default/feature checks. Root checks all pages for attached marks, clipping, wrapping, heading hierarchy, footer placement, pagination and final caveat. The Windows tier must separately run the existing file publication/NTFS and operator build checks required by PR395. This does not establish installed native Save/cancel behavior, target-device peak memory, macOS qualification, or public installer readiness.

Primary package metadata was checked at https://pypi.org/pypi/pypdf/6.21.4/json and https://pypi.org/pypi/pdfplumber/0.11.9/json. The version choices match the recorded prior oracle environment; the new resolved environment and output are fresh evidence, not an update to the historical receipt.
