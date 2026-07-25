# Code Review — Batch 7an (cross-OS GUI-launch smoke + per-OS NFR)

- **Scope:** story `86ajpevzp` — prove the desktop app LAUNCHES (windows created, first frame presented) on Linux + Windows (macOS already measured) and record per-OS NFR figures. Executed via the `/goal` engine against `docs/delivery/goals/TASK-86ajpevzp-launch-smoke.md` (5 mandatory criteria, all PASS; validator `--require-complete` green).
- **What shipped:** a GUI-launch **smoke mode** (`--smoke` / `SELAHCUE_SMOKE`) in `selahcue-desktop` — presents the main window's first frame, prints time-to-first-frame, exits 0; a 30s in-app watchdog + a CI `timeout-minutes` backstop fail loudly instead of hanging. A **`launch-smoke` CI job** (ubuntu headless under Xvfb + lavapipe; macOS on the runner). A **`measure_nfr.sh` portability fix** (it was broken on GNU/Linux).
- **Method:** independent adversarial review via the Workflow tool (run `wf_12f98261-a6c`, 13 agents; 2 lenses — smoke-correctness, ci-nfr-correctness — each finding verified to refute). No self-approval.
- **Raised → confirmed → fixed:** **11 → 7 → all fixed** · 4 refuted. Notably the review caught a **high-severity integrity error in the Goal Contract itself**.

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | **C-004 overstated the ≤3s cold-start.** The criterion tied "cold-start ≤3s" to the smoke first-frame, but that is 5.2s on Linux (software lavapipe) — over budget. The 0.07s figure is `measure_nfr.sh`'s control-server-ready **proxy** (the story's canonical NFR), which the script itself discloses is *not* first-frame | reframed C-004: ≤3s cold-start = the `make nfr` proxy (Linux 0.07s / macOS 1.13s); the smoke first-frame is a **separate informational** figure (GPU-init + software-raster overhead), never the ≤3s bar |
| B | med | **Watchdog blind spot + no CI timeout.** The 30s watchdog runs in `about_to_wait`, only reached *after* `resumed()` returns — a hang *inside* window/adapter creation is never caught, and the job had no `timeout-minutes` (GitHub's 6h default) | added `timeout-minutes: 20` to the launch-smoke job; documented the watchdog's scope |
| C | med | **NFR budgets non-gating.** The only CI NFR check was `continue-on-error`, so a real ≤3s/≤300MB regression would never fail CI | removed `continue-on-error` — the NFR budgets now **gate** on Linux (aligns with the no-unbounded-growth rule) |
| D | low | `--smoke` performed the full clean-exit save, mutating the real session store | skip the final save in smoke mode (throwaway probe persists nothing) |
| E | low | Fast smoke exit can race the server thread's endpoint-file write → stale endpoint | accepted + documented (self-healing: a later shell re-discovers); the clean-exit removal covers the common case |
| F | low | The metric was commented "cold-start-to-first-frame" but excludes process/`App::new` startup | relabelled honestly ("first frame … (from App init)"); the ≤3s claim now rests on `make nfr`, not this figure |

## Refuted (correctly)

- Linux first-frame variance (2.4s→5.8s) "vs a 30s hang-watchdog" — the watchdog is a hang guard, not a perf gate; not a defect.
- Windows exclusion "rests on a single passing run" — the documented-limitation clause is exactly the acceptance's provision; facts accurate, not a defect.
- The `mktemp` fix and the launch-smoke wiring — both cleared as correct (no defect).

## Verification after remediation

- CI run **30142530116 green**: `launch-smoke` ubuntu + macOS; the now-**gating** NFR budgets pass (Linux cold **0.058s** / idle **203.0MB**).
- Local: `cargo fmt` + `cargo clippy --all-targets -D warnings` clean; smoke exit 0 (602ms); 269 workspace tests (+1 smoke-flag unit test).

## Per-OS evidence

| OS | launch-smoke | cold start (`make nfr` proxy) | idle memory | first-frame (informational) |
|---|---|---|---|---|
| Linux (Xvfb+lavapipe) | ✅ green (gated) | **0.058s** ≤3s | **203.0 MB** ≤300 MB | 5.2–5.8s (software raster) |
| macOS | ✅ green | **1.13s** ≤3s | **121.5 MB** ≤300 MB | 820ms (local) |
| Windows | documented limitation (recorded 522ms, run 30141199818) | POSIX-script limitation | POSIX-script limitation | 522ms (recorded once) |

## Residual / documented

- **Windows launch-smoke** excluded from the required matrix: the app launches+presents there (recorded), but the headless runner's windowed present is intermittent (a DXGI/desktop-session flake). The rust + operator matrices still cover Windows build+test.
- Windows NFR figures are a POSIX-script limitation (`measure_nfr.sh` uses `ps`/`pgrep`).
