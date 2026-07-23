# ADR-0016 — Out-of-process sandboxed media/font decode

- Status: Accepted
- Date: 2026-07-23
- Confidence: High
- Owner: Software Architect + Security Reviewer
- Relates: ADR-0005 (media engine), ARCHITECTURE §7/§11, threat model T12
- Raised by: Stage-5 independent review **M1** (major, merged Architecture + Security)

## Context

Untrusted, user-imported media and fonts are the primary remote-code-execution surface into the authoritative host (threat model T12, High). They are also a reliability surface: a decoder crash on malformed media, if it runs in the main/engine process, could take down rendering and **blank every output** — violating NFR-024. The Stage-5 review noted that the "structural isolation" claim in NFR-024 conflates two distinct properties: **fault isolation** (a decoder crash must not blank outputs) and **security isolation** (a decoder exploit must not compromise the host). In-process decode delivers neither.

## Decision

Decode of untrusted media and fonts runs **out-of-process** in a **sandboxed decoder worker**, separate from the render engine and the control plane:

1. **Process boundary.** The GStreamer decode pipeline (and font shaping of untrusted font files) runs in a dedicated worker process. Decoded frames are handed to the engine via shared-memory/GPU-shared surfaces (ADR-0006 interop), not by running decode inside the engine.
2. **Sandboxing posture (per platform).** Apply the OS sandbox available on each platform — macOS App Sandbox / seatbelt profile; Windows AppContainer / restricted token + job object; Linux seccomp-bpf + namespaces (or bubblewrap where present). The worker has no network, minimal filesystem (read-only access to the specific imported file), and no secret-store access.
3. **Fault handling.** A decoder-worker crash is contained: the affected media item shows the missing-media placeholder (FR-070), other outputs are unaffected, and the worker is respawned with backoff. This is exercised by the ADR-0015 fault-injection matrix (decoder fault) and included in the S2 interop fault tests.
4. **Validation before decode.** Header/type/size validation and the media-type allowlist (FR-173) run before the worker fully decodes; the import path is canonicalised (FR-138) before the file reaches the worker.

## Options considered

- **(Chosen) Out-of-process sandboxed decode.** Pros: a decoder crash or exploit is contained — no output blank, no host compromise; satisfies both fault and security isolation; matches how browsers isolate media/codecs. Cons: IPC/shared-surface complexity; a small per-frame handoff cost.
- **In-process decode with defensive parsing only.** Rejected: a memory-safety bug in a native codec still yields RCE and can crash the engine (blanking outputs). Defensive validation reduces but does not contain the risk.
- **Narrow the NFR-024 claim instead of isolating.** Considered as a fallback if per-platform sandboxing proves infeasible on a target OS: explicitly state that decoder faults are contained by process-restart with a brief placeholder, and record the residual security posture for the Stage-13 review. Preferred outcome is full sandboxing; this narrowing is the documented fallback, not the goal.

## Consequences

- **Positive:** T12 RCE is contained to an unprivileged sandbox; decoder crashes cannot blank outputs; NFR-024's isolation claim becomes true for the decode surface and is testable (ADR-0015).
- **Negative:** added IPC and per-platform sandbox engineering; zero-copy interop (ADR-0006) must work across the process boundary (shared GPU surfaces), which is factored into spike S2.
- **NFR-024 wording** is updated in ARCHITECTURE/PRD to distinguish fault isolation from security isolation for the decode surface.

## References

PRD: FR-066/067/070/138/173, NFR-024; threat T12. ADRs: 0005, 0006, 0015. Review: M1.
