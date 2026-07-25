# QA Review — Batch 7ar (foundation-demo milestone re-score)

- **Scope:** milestone `86ajp0bpn` — re-score the Stage-7 foundation demo against current evidence (the prior review was 7t-era, last updated at 7y; batches 7u–7aq had closed most of its gap list). Executed via the `/goal` engine (`TASK-86ajp0bpn-foundation-demo-rescore.md`, validator `--require-complete` PASS, 5/5). Docs + ClickUp only — no code.
- **Method (no self-scoring):** 9 fresh-context auditors — one per demo step — via a Workflow fan-out (`wf_4e58027d-bb3`, 323 tool calls). The auditors **re-ran the cited test suites** (test_controller 36/36, test_plan_repo 11/11, the feature-gated wire E2Es) and **pulled live CI runner logs** (the SMOKE OK lines, the gated NFR figures, the verbatim Windows 522 ms launch from run 30141199818) rather than trusting documents. Upgrades required concrete new evidence; downgrades were allowed and occurred.

## Outcome

**V2 score: 2 PASS · 7 PASS (scoped) · 0 PARTIAL · 0 FAIL** — from the 7t-era 2 · 5 · 2 · 0.

| Step | Movement |
|---|---|
| 1 Launch on 3 OSes | **PARTIAL → PASS (scoped)** — launch-smoke CI green on Linux+macOS; Windows launch runner-log-confirmed once; NFR budgets now gate |
| 5 Countdown → TIME UP | **PASS (scoped) → PASS** — the owner personally QA'd + closed `86ajphu98` (the scripted steps include the stage readout) |
| 8 Pair mobile + advance | **PARTIAL → PASS (scoped)** — mDNS + SAS + MulticastLock + the revamp (12 → 39 Flutter tests) |
| 9 Force-kill + recover | **PASS → PASS (scoped)** — an honest label refinement: substance strengthened, but the live kill-walk is 7u-era and no process-level test exists |
| 2/3/4/6/7 | labels unchanged; scoped remainders substantially narrowed; one **wording correction** (the plan "library" is data-layer + tests only — no shipped client exposes it) |

## Remaining gaps (classed; none is a FAIL)

- **[owner-QA]** — hardware in the owner's hands, steps already posted as list-form QA: real camera QR scan + on-device mDNS (`86ajp0b0t`), the 2+-display walk, the physical-keys cable-out emergency demo (`86ajp0awx`), visual re-confirmations post-restyle.
- **[toolchain]** — Windows encryption tests (perl/nasm), Windows NFR (POSIX script), Windows launch-smoke excluded after one recorded success (documented flake).
- **[descoped — tracked]** — per-layer clearing (R2 `86ajpy59e`), pagination, stage verse text, translation persistence in recovery, the 7ad dialog deltas.
- **[missing → follow-up `86ajpzbxf`]** — cross-language pairing E2E, process-level kill-9 test, a library user surface (or explicit descope), one doc relocation.

## Disposition recommendation (the decision is the owner's)

**Conditionally met.** Every step passes; the automatable evidence is exhausted. Recommended: the owner runs the posted on-device/multi-monitor QA; if green, close the milestone + Stage 7 and open the Stage-8 planning gate.

## Verification integrity

The v2 table was synthesized solely from the auditors' cited outputs — including their corrections *against* the prior review's wording (the library overstatement; the step-9 label). No claim in the v2 section exceeds its audit evidence.
