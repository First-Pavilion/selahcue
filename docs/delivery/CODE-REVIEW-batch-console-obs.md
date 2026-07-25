# Code Review — Operator console OBS-studio layout (86ajpztgr)

- **Scope:** implement the approved Figma **165:124** ("Operator Console — OBS studio") layout in the Tauri operator console (`crates/selahcue-operator/dist/index.html`). Owner request. Executed via the `/goal` engine (`TASK-86ajpztgr-console-obs-layout.md`, validator `--require-complete` PASS, 5/5).
- **Method:** an independent adversarial review agent read the actual file + the `8f092b8..HEAD` diff, enumerating every JS reference and layout risk. No self-approval.
- **Outcome:** **0 high / 0 medium findings; 2 low** (1 closed, 1 accepted).

## What shipped

The console `<main>` was restructured into the 3-zone OBS layout — **LEFT** Service Plan + Live Transcript · **CENTER** OBS Preview | Live (side by side) + GO LIVE + Scriptures · **RIGHT** Service Timer + Recent Detections + Outputs · always-on emergency footer. The change is a pure re-parenting of existing DOM subtrees into three `.zone` wrappers plus two new panels; **the entire `<script>` is byte-unchanged** and all 41 wired element ids are preserved (the only removed node is the unreferenced `#rightcol` wrapper; the dead `#rightcol`/`.side-h` CSS was cleaned up).

The **Live Transcript** and **Recent Detections** panels are forward-looking UI with **honest empty states** ("On-device transcription arrives with R3" / "Auto-detected scriptures arrive with R4") — no fabricated data is ever shown as real. They wire to the R3 (transcription) + R4 (scripture-intelligence) backends later.

## Review findings

| Sev | Finding | Disposition |
|---|---|---|
| — | JS wiring — all 54 `getElementById` targets + the `#{which}-panel .surface` querySelector resolve to surviving elements (incl. the `.big`/`.cap`/`#*-title`/`#*-cap`/`#live-black` children `setPanel` writes) | **clean** |
| — | Dropped controls — every plan/scripture/preview-live/golive/timer/outputs/emergency control present | **clean** |
| — | Emergency invariant (safety-critical) — `#emergency` footer still a direct `<body>` child, outside all zones; capture-phase keydown + modal-pierce chords intact (unchanged `<script>`) | **clean** |
| — | Honest placeholders — `#transcript`/`#detections` show only the R3/R4 empty states, no fake data | **clean** |
| low | `#outputs` lost the old `#rightcol` overflow safety-net — at an absurdly short window with many display roles it couldn't scroll (it's bounded to 2 roles today, so it can't manifest) | **fixed** — added `overflow-y: auto` to `#outputs` |
| low | Both asides carry an unused `.side-panel` class (styled by the bare `aside {}` rule) | **accepted** — a harmless semantic hook, not dead-ref rot |

## Verification

- **Pinned invariants green:** `test_keymap` (keymap JS logic + capture-phase + modal-pierce ordering) + `test_tokens` (emergency/preview-panel/live-panel/translation/verse-list + the new OBS-zone + honest-panel pins).
- **Layout:** a headless-Chrome render (with `window.__TAURI__` stubbed) matches the 165:124 design — the three zones, the OBS Preview|Live row, and the honest empty states.
- Full workspace tests green; fmt clean; the operator shell builds; CI green.

## Residual / follow-ups

- The transcript + detections panels are UI shells; wiring them to real data is the **R3/R4** epics (not this story). On-device visual QA of the console is owner-run.
