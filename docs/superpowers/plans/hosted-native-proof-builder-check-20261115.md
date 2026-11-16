# Hosted native proof — independent builder check

Reviewed 2026-11-15. Documentation-only review using the Superpowers brainstorming builder-check prompt and writing-plans self-review rubric. No source edits, staging, preparation, native execution, dependency installation, provider/network access, CI dispatch or subagents.

Reviewed complete amendment SHA256 `3b18f7b9befe532d38bcb69e14bba43423c94380385e42f2ade079d9887159f1` and plan SHA256 `f50638b2e964ba2e3a4cd21e338b26d5d9b9b99a044df4288af3c1db23025071`; both matched the supplied identities. Read the predecessor hosted preflight, named native/finite preparation receipts, immutable builder/main/manifest, selected compiler/contract and fixture interfaces, and owning workflow validation entry points. No historical session reconstruction or new constructor measurement was performed.

## Questions still requiring disposition

1. **Which memory/output guarantee applies to the immutable builder's internally buffered Cargo output?** Amendment **Runner phases and resource limits §3** and plan **Task2 Step5** require bounded stdout/stderr pumping so a runaway process cannot exhaust memory before a size check. However, immutable `O/native-golden/build_pinned.py`, function `command`, uses `subprocess.run(..., capture_output=True)` for Cargo. That buffering occurs inside the builder; the proposed outer orchestrator cannot cap those bytes by pumping the builder's own streams. During a Cargo invocation the orchestrator receives no such bytes until that invocation finishes. Paging samples every five seconds, with two rising samples required, are a different protection and do not make the internal output bounded.

   **Why it changes the plan:** the worker must either add an independently enforced process-tree memory mechanism that works on the target runner, or state the narrower guarantee honestly. They cannot modify the frozen builder, and outer stream tests alone would misleadingly prove the stronger claim.

   **Smallest disposition:** before Task2 orchestration implementation, explicitly scope the byte limits to directly captured native/output streams and state that frozen Cargo internal buffering is controlled only by the stated resource/timeout policy, if that is the intended accepted limit. If prevention of memory exhaustion remains mandatory, define a compatible enforceable memory limit and add a fake-child/internal-buffering failure test. Keep builder bytes and `--frozen --jobs 2` unchanged. This does not require another user authorization or block Task1 fixture reconstruction.

2. **What exact interface performs the mandatory post-upload cleanup step?** Plan **Task2 Interfaces** closes the CLI to `admit`, `setup`, `prove`, `finalize`; **Task3 Interfaces** fixes a sequence ending in always-finalize, always-upload, then always-owned-cleanup. No cleanup function/CLI mode is defined, while **Task3 Step3** requires exact fixed commands and rejects changed commands. Implementing cleanup inside `finalize` would move it before upload; adding a command would contradict the closed CLI contract.

   **Why it changes the plan:** the worker has to change one of the declared interfaces or the exact workflow shape. Guessing here can also discard the receipts needed for upload or make cleanup bypass the same ownership/no-follow validation tested elsewhere.

   **Smallest disposition:** add `cleanup() -> dict` and a fixed `cleanup` CLI subcommand owned by `scripts/macos_native_proof.py`; identify that it removes only successfully recorded job-owned staging/cache/target paths, retains the receipt export until upload completes, tolerates absent stage state after an early failure, and refuses non-owned/symlinked paths. Carry its exact command into both validators and test cleanup after failed admission, setup, proof and upload. Resolve before Task2/Task3 implementation; no new execution permission is implied.

## Scope of the remaining gates

I found no further consequential unanswered planning question in the frozen path/source identities, detached normative source, exact 56 registry tuples and lock custody, finite 11-batch/1,111-frame/47-rejection scope, historical matrix/wrapper pins, setup-versus-offline trust boundary, exact workflow exception, synthetic private input custody, receipt-only transport, or later bridge/Q evidence boundaries.

Official distribution/action pins and remaining constructed batch digests are correctly assigned as implementation and pre-execution evidence gates. They are not facts established by this review. Task1's independent constructor reproduction and semantic comparator review must still pass; a mismatch must stop rather than refresh historical expected outputs. The new runner is explicitly distinguished from the unrecovered historical test file and historical native binary. Root's existing authorization remains sufficient for the bounded route described; this review introduces no user permission gate.

Verdict: two narrow dispositions above remain before the affected orchestration/workflow source work; not “nothing important left.”

## Scoped re-review — 2026-11-15

Reviewed the two revised contracts only, including their associated task interfaces, workflow ordering and failure tests. Verified exact revised file identities:

- Amendment: SHA256 `0af84b147bda7174f4709fd1cc8ec96461f4446dd1544747a459913c12db32ca`.
- Plan: SHA256 `8df9cbe0c2c815527bcdb21dc754220e18a083633e85f93f4087285117886597`.

**Finding 1 — ADDRESSED.** Amendment **Eleven batches** and **Runner phases and resource limits §3**, plus plan **Task2 Steps5–6**, now explicitly confine outer stream caps and fake overflow tests to directly captured output. They preserve the immutable builder's internal `capture_output=True` behavior and state that resource sampling/deadlines do not prevent every instantaneous OOM. No new memory-limiter mechanism or stronger memory guarantee is implied. This implements root's narrower accepted guarantee without changing frozen build bytes or flags.

**Finding 2 — ADDRESSED.** Amendment **Runner phases and resource limits §4 / Receipts, transport and later use** and plan **Task2 Interfaces/Steps5–6 / Task3 Interfaces/Step1** consistently define `cleanup() -> dict`, permit the fixed `cleanup` subcommand, and require exactly `python3 scripts/macos_native_proof.py cleanup` after upload. Both validators must enforce this order and always-execution. The contract retains receipts through upload completion, derives removal authority only from successfully recorded job ownership, refuses foreign/symlinked/unrecorded paths, tolerates absent early-stage state, and tests admission/setup/proof/upload failures without changing their failed outcomes.

No new consequential inconsistency found in these revised contracts. Scoped verdict: **nothing important left**. This closes both documentation findings only; implementation, official pin acquisition, independent constructor reproduction, source review and actual hosted evidence remain future gates. No source/preparation/execution/network activity was performed during this re-review.
