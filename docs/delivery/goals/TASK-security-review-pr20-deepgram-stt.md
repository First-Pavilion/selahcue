# Goal Contract — TASK-security-review-pr20-deepgram-stt

## Identity

- Goal ID: TASK-security-review-pr20-deepgram-stt
- Parent goal ID: NONE
- Title: PR #20 (feat/86akby4yz-deepgram-stt-cloud) is security-reviewed at head d9a46f9 with the consent gate, credential handling, TLS single-stack claim, release containment and bounded-memory questions answered by evidence, findings posted on the PR, and a verdict reported
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby4yz
- Created: 2026-09-04
- Updated: 2026-09-04 (completed)
- Maximum iterations: 8
- Independent verification required: yes

## Objective

At head d9a46f9aad27b80891a448f4ccd13fd0d49bd9e9 (base origin/main 3f3072e, 0 behind): the
live-microphone egress path is assessed: whether streaming without consent is untestable-around
or merely tested; whether the key can reach a URL, log, or any error path including the
panic-containment path; whether the workspace genuinely carries one crypto stack (rustls/ring)
with no second backend reachable by feature; whether any route enables the crate in a
distributed artefact and whether the contacted host matches the 86akc041v literal; whether the
two buffers are bounded by controls that bite; with the complement question (present-and-
misbehaving peer) applied to each bound. Findings posted on PR #20 with a verdict.

## Baseline

PR #20 is a Draft, four commits on origin/main at 3f3072e. New crate selahcue-stt-cloud
(workspace member), no operator changes. The engineer reports three silent liveness bugs found
and fixed (unbounded pump, unbounded connect, worker-panic leaving Connecting forever) plus a
live TLS panic fixed by installing the crypto provider. Suite is loopback ws:// only — TLS is
structurally untested and review carries it. 86akc041v is being built with api.deepgram.com in
its string set.

## Inputs and evidence sources

- git show d9a46f9:<path> — never the lane worktree or shared checkout
- PR #20 description and diff; my own scratchpad worktree at d9a46f9 (sana_-prefixed), own
  CARGO_TARGET_DIR
- Workspace Cargo.toml/Cargo.lock at head for the crypto-stack and containment claims
- ci.yml/Makefile at head; PRD CON-5/NFR-018/FR-134/FR-082

## Scope

### In scope

- Consent: may_stream_cloud_audio() requiring Cloud mode AND per-provider opt-in; whether the
  no-egress property is enforced by construction (panicking/forbidden transport shape) or only
  asserted; mutation of the gate
- Credential: never-in-URL assertion mutation-tested; key across connect/handshake/panic paths;
  Debug/Display redaction; env read handling
- TLS: rustls with ring in the lockfile, one crypto backend workspace-wide, no aws-lc route via
  features; crypto-provider installation (the live panic fix)
- Containment: feature gating in workspace + crate manifests, CI/Makefile invocations, no
  artefact route; contacted host literal vs api.deepgram.com in every configuration
- Bounded memory: both buffers, their compile-time premises, and mutation of at least one bound
  per buffer; the complement question per bound (slow/dripping/flooding peer vs absent peer)
- The three fixed liveness bugs: controls that would catch their return

### Non-goals

- STT quality/latency; the operator wiring (not in this PR); modifying code; merging

### Constraints

- Exit codes captured directly; probes only in my own worktree; sana_-prefixed scratch files;
  serialise make ci (not planned); SHA-pinned reads; hang-capable mutations under kill harness

### Assumptions and unknowns

- ClickUp MCP absent all session; routed via coordinator

## Dependencies and approvals

- gh CLI — available

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The consent gate is assessed: both conditions required, untestable-around or not, and a gate mutation dies | code read + mutation | explicit verdict; RED at a named control | Verdict: stronger than PR #19's runtime gate — type-level. StreamAuthorization has a private unit field and exactly one constructor consuming may_stream_cloud_audio() (no re-derived conjunction; the 86ak643rc lesson cited in its docs); grep finds no constructor outside session.rs. M1 (gate always passes): RED, four named consent tests including revoking_consent_revokes_the_ability_to_stream and authorisation_follows_the_cores_own_egress_predicate. Untestable-around at the type level; the runtime tests additionally bite | PASS |
| C-002 | yes | The key cannot reach a URL or any error path: never-in-URL control mutation-tested; connect/handshake/panic paths traced | code read + mutations | explicit per-path verdict; REDs recorded | M2 (credential appended to URL): RED at exactly the_url_carries_the_parameters_and_never_the_credential. M3 (scrub dropped): RED at every_error_variant_renders_without_the_secret and transport_details_are_scrubbed_of_the_secret_without_losing_the_diagnostic (positive control built into the name). Credential: no derived Debug/Display/PartialEq, hand-written redacting Debug, header-injection refused at construction (control/non-ASCII/space), MIN_SECRET_LEN premise tied to scrubber safety; tungstenite Error::Http Display verified to print status only (registry source), so non-401 upgrade rejections echo no body; scrub-at-constructor leaves no free-text Transport constructor; panic-containment message is a fixed string | PASS |
| C-003 | yes | One crypto stack: ring-backed rustls only, in lockfile and features, matching selahcue-lan | lockfile/manifest analysis with positive controls | verdict or a named second stack | ring present exactly once in the workspace lock at head, aws-lc absent (0 hits, ring as positive control); rustls 0.23 direct dep with features [ring,std,tls12,logging] default-features off; tokio-tungstenite rustls-tls-webpki-roots resolves without aws-lc per the lockfile; install once per process via Once with already-installed treated as success. One crypto stack, matching selahcue-lan; suite blindness to TLS acknowledged — review carried it | PASS |
| C-004 | yes | Containment: no artefact route enables the crate; contacted host equals the 86akc041v literal in every configuration | manifest/CI/Makefile reads + greps with positive controls + host-construction read | verdict; any divergent host named | nothing depends on selahcue-stt-cloud (members line only; operator wiring is 86akby7th); deepgram off by default; new gate lines are clippy/test only; exactly one env read (credential.rs); example never prints the credential; DEEPGRAM_LISTEN_URL is wss://api.deepgram.com/v1/listen so the 86akc041v literal api.deepgram.com matches in every configuration — custom endpoints are code-only and cleartext non-loopback is refused at RequestSpec::build (typo-squat loopback shapes 127.0.0.1@evil / 127.0.0.1.evil / localhost.evil all refused by the parser, verified by read) | PASS |
| C-005 | yes | Both buffers bounded by controls that bite; complement question applied per bound | code read + at least two mutations | explicit verdict per buffer | both buffers: count+byte bounds, oldest-first, per-key dropped_for_bound, per-entity retains_* accessors, compile-time independently-reachable premises, single bound predicate consumed by eviction and tests. M4 (queue eviction removed): RED at both flood tests. M5 (liveness reset removed): RED at exactly a_slow_but_steady_peer_is_healthy_rather_than_stalled while the stall and idle tests stay green — the drip discrimination reproduces. Complement applied to the WRITE side found F-1 (Medium): a peer that stops reading wedges socket.send().await inside the ticker branch; stall check unreachable, stop flag unread, Drop joins the wedged worker. Demonstrated empirically with a non-reading stub peer: session sat at Streaming for 10s against a 300ms stall bound, probe RED with its named message (sana_p20_backpressure.log). Memory stayed bounded throughout (ring drops oldest); the defect is liveness + a hanging stop() | PASS |
| C-006 | yes | The three silent-failure fixes have controls that would catch their return | code read of the named tests | verdict per bug | connect: a_peer_that_accepts_but_never_answers_times_out_instead_of_hanging_forever (asserts the stub accepted — cannot pass by refusal); stall: a_stream_that_goes_quiet_mid_sermon_is_noticed_rather_than_waited_on_forever; panic: a_panic_inside_the_worker_becomes_a_terminal_state_not_an_eternal_connecting via a genuinely reachable panic. All three returns are pinned. The fourth (F-1) is the write-side sibling and needs its own | PASS |
| C-007 | yes | Findings posted on PR #20 with a verdict | gh pr review / gh api | review visible | consolidated review posted on PR #20, verified via gh api | PASS |
| C-008 | yes | Verdict and finding count reported to the coordinator | final response | stated | verdict: clear with one named condition — F-1 (Medium) fixed in this PR with bounded writes incl. the stop-path close-flush, regression test provided; 0 blocking; reported in final response | PASS |

## Verification plan

- Focused: SHA-pinned reads; isolated worktree; targeted cargo test on the new crate; mutations
  with siblings, hang-capable ones under a kill wrapper
- Independent verifier: coordinator and remaining reviewers
- Environment: pinned toolchain, gh CLI

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-006
- Change or investigation: full SHA-pinned read of the crate; tungstenite Display verified from registry source; lockfile crypto analysis; worktree at d9a46f9 with own target dir; baselines 73/83 green; mutations M1-M5 all RED at named controls; the write-side complement probed empirically with a non-reading stub peer — F-1 demonstrated (probe RED, 10s at Streaming vs 300ms bound); probe file removed, worktree restored clean
- Verifier executed: exit codes captured directly; hang-capable runs under a kill harness
- Result: five controls verified biting; one Medium finding with an empirically validated demonstration
- New evidence: scratchpad sana_p20_base_*.log, sana_p20_M1..M5 logs, sana_p20_backpressure.log
- Decision: iterate

### Iteration 2

- Target criterion: C-007, C-008
- Change or investigation: posted the consolidated review; reported to the coordinator; CI at head confirmed green
- Result: PASS
- Decision: complete

## Risks and rollback

- Probes isolated; worktree removed at end; review is additive commentary
- Live keys exist in the shared checkout .env — tests under review must be checked for real-key
  or network usage before running (suite is claimed loopback-only; verify before executing)

## Final evaluation

- Validator command: python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-security-review-pr20-deepgram-stt.md --completion
- Validator result: recorded on the run below
- Independent verification result: coordinator and remaining reviewers on the same PR
- Terminal state: VERIFIED_COMPLETE (review deliverable); PR remains Draft pending the gate
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: PENDING — MCP absent; routed via the coordinator
