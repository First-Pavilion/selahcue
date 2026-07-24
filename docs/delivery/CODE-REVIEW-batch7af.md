# Code Review — Batch 7af (double-click verse to live)

- **Scope:** one webview affordance — double-clicking a verse in the chapter browser stages it and commits it live in one gesture (`86ajpwcxc`).
- **Method:** independent adversarial review via the Workflow tool (run `wf_ac212b67-bca`, 5 agents, single race-focused lens) → per-finding verification. No self-approval.
- **Raised → confirmed → unique:** **4 → 4 (A–D)** · 0 refuted. Small feature, real holes — all shared one root cause: committing live without verifying what was actually staged.

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | A **denied** stage resolves as success (Denied ≡ Ack by design on both backends), so `go_live` committed **whatever was previously in Preview** — e.g. a song going live while the status claimed a verse (reachable: an older host denying a newer translation code) | the returned view's `staged_scripture` must equal the double-clicked reference before `go_live` fires; otherwise an honest "Could not stage… nothing was sent live" |
| B | high | "→ LIVE" was announced unconditionally (`act()` never rejects) — false confirmation on transport failure or RBAC denial | `go_live` invoked directly (failures caught); LIVE is claimed only when the view confirms `live_scripture` equals the reference |
| C | med | An arrow-key stage debounced **during** the in-flight round trips could land between the stage and the commit on slow links — the *arrowed* verse went live, not the double-clicked one | `dblclickBusy` blocks debounced staging for the whole flow + a second timer cancellation before the commit |
| D | low | The status reference was recomputed after the awaits — wrong ref (or a TypeError) if the chapter changed mid-flight | the reference is captured before any await |

**Verification:** JS syntax-checked; pin tests green; operator crate clean; suites unchanged (260 desktop + 20 Flutter).
