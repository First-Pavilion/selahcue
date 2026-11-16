# WebKit chronology and rejected-module observation: binding design

2026-11-16. **Accepted by coordinator for the authorized PR415 review remediation, after independent buildability review. No implementation or successor capture has run.** This is a bounded continuation of PR415. It does not reset the exhausted final-capture contract or authorize an unchanged rerun. Source inspected: `/Users/m.oluwole/.codex/worktrees/selahcue-account-overview-20261116/scph`, verified HEAD `9fac081ac736aff5bd206c676b7802f97bce8338`.

## Evidence and decision

Read first: the archived `pr415-webkit-fault-preflight-20261116.md` and the archived `ci-43956051794-home-webkit-capture-triage.md` for [normal run43956051794](https://github.com/First-Pavilion/selahcue/actions/runs/43956051794). Run43956051794 remains terminal **FAIL**, solely the WebKit Responsive gate at `/privacy`, nominal1024×800, cell135/205. Its geometry and70 subsequent cells did not execute. Home and GPU actual assertions passed independently. No cause is established.

Binding source contracts are `docs/superpowers/specs/2026-11-16-native-fault-capture-design.md`, its implementation plan, and `docs/superpowers/specs/2026-11-16-webkit-failure-probe-receipt.md`. Source inspection covered the progressive sampler, `SettleDiagnostic`, failure/probe/teardown paths, collector parser/correlation/export/identity child, existing controls and workflow selection. The12-second/24-event rich ledger loses first lifecycle timestamps, although bounded before/during counts survive. `module_policy` refuses the row before TID/boot/time/PC comparison. **It also precedes producer-ending and CPU-range validation.** An observed `module_policy` does not therefore prove every other grammar check passed.

Recommend two small observation additions: a host-only fixed chronology receipt, and a finite classification of existing module-policy refusals. Neither establishes page↔PID ownership or a root cause. No application repair is justified yet.

## Approaches considered

1. **Fixed terminal chronology plus finite rejection summary — recommended.** Keep one active cell, one retained failed cell and fixed sweep anchors in memory; emit one bounded terminal line after existing Playwright teardown. Classify refused module rows within the existing collector. This answers the retained trial's timing/rejection questions with no new browser operations or callback output. A killed/stuck host may never emit a terminal receipt; that remains unknown.
2. **Bounded streamed cell checkpoints plus the same rejection summary.** Emit a fixed start record for each of205cells and terminal/failure markers, with explicit205-record/cumulative-byte limits. This could retain the active-cell start if the harness dies before terminal output, but introduces205extra writes and scheduler perturbation. The observed trial reached exception handling and normal wrapper cleanup; there is no evidence that terminal-loss coverage warrants this addition. Defer it unless a new accepted capture actually loses the terminal receipt.

Native page/PID association, a heartbeat process and system resource sampling are excluded here. They need different evidence contracts and do not fix either identified loss with a smaller change. Raising rich-ledger duration or repeatedly printing raw messages is not an acceptable alternative.

Coordinator ruling: accept the recommended terminal chronology and finite rejection observation. The user authorized iterative technical remediation; this adds no product behavior or deployment. Independent buildability review found nothing important left to clarify. Cost if wrong: bounded fixture/design rework or one inconclusive hosted observation, with no original gate waived. Implementation may proceed; the single successor capture still requires completed source reviews, custody and parent admission.

The parent reports a fresh host sample at21:36:39–43UTC:16GiB RAM,13,234.25MiB swap used, pageouts+5/swapins+4 in4seconds. The heavy/native/browser/service hold remains. Its last standalone collector suite took approximately27.5seconds under an existing30-second outer deadline. New fixtures must use pure metadata/fake clocks or reuse already-required controlled-child cases; do not add sleeps, long-lived children, new timeout tests duplicating existing supervision, or raise the30-second admission. The implementing owner must measure and preserve that bound when the parent admits verification. The next normal capture is hosted only and **is not yet authorized**.

## Invariants and source ownership

One implementing owner writes sequentially, preserving other writers' edits. Own only:

- `implementation/marketing/scripts/responsive_sweep.py`: host chronology and its integration into existing callbacks/stages/unwind.
- `implementation/marketing/tests/responsive_diagnostic_regression.py`: inert clocks/lifecycle/main-path controls; preserve real-WebKit controls.
- `implementation/marketing/scripts/webkit_crash_journal.py`: one shared parse path, private refusal classification, existing identity-child private envelope, safe optional export.
- `implementation/marketing/tests/test_webkit_crash_journal.py`: offline parser/correlation/identity/export controls.
- `.github/workflows/ci.yml`: add only the new inert chronology test class to the existing selected controls; collector tests already run as a complete file. No new job or changed gate command.

No production application/Rust/GPU/Home changes. No version, backend, runner, cache, dependency, protocol, browser lifetime, context lifetime, route ordering, actions, geometry/assertions, polling, timeout or failure-exit change. Preserve all205cells, the one sweep browser, width contexts and fresh sequential pages. Keep navigation20000ms, visible-content10000ms, settlement10000ms, the existing single failure probe timeout1000/polling100 and original exits0/1/2/3. No new probe, sleeps, retry, core, debugger, downloaded symbols, installation, service, platform or runtime. Existing observers remain, including13samples/12seconds,24events, existing32KiB trace-body limit and768-byte probe protocol. No change to the browser JS strings is needed.

Collector limits remain:256KiB coredump plus one probe byte;64KiB kernel plus one probe byte;4096ASCII-byte kernel line;3eligible records;64indexed TIDs/record;12retained sanitized frames/thread;3exported stacks/record;16module identities; current boot; inclusive window≤3600seconds. Preserve4s/2s queries,8s metadata/2s existing identity phase,10s combined ceiling,0.15s TERM/0.5s reap,256MiB identity file/1MiB chunks and notes/128headers, and one ASCII JSON line≤24KiB including newline. No new query, subprocess, retry or extra identity phase. Candidate completeness, global ambiguity, accepted fault attribution and truncation meanings remain unchanged.

## A. Fixed host chronology

### Clock contract

Add `sample_host_stamp() -> dict | None`, implemented solely with stdlib clocks, never browser values. Read `monotonic_ns`, `time_ns`, `monotonic_ns` in that order. Return exactly `{utc_us, mono_before_us, mono_after_us}` using integer floor division by1000. Admit only true integers0..9007199254740991 and `mono_after_us >= mono_before_us`; otherwise return null and latch the observer's `clock_error`. No fabricated conversion from the browser's `performance.now()`, GitHub log timestamps or configured timeout.

Each stamp pairs the host UTC sample with an independently read monotonic interval. This brackets sampling overhead without asserting simultaneous reads or stable UTC offset. Ordering uses disjoint monotonic brackets; overlapping brackets are indeterminate at this resolution. UTC can jump. Compare each UTC/monotonic anchor's offset interval before lining up journal time; inconsistent intervals preclude an exact UTC interpolation. UTC correspondence alone never proves process/page association.

`settle_start` records immediately before invoking the unchanged wait. The configured10,000ms budget is a reference interval `[mono_before_us + 10000000, mono_after_us + 10000000]`, **not a recorded Playwright deadline or guaranteed wall-clock return time**. An early crash callback receipt implies an event was delivered before that reference; a late callback does not prove the native event occurred late. Callbacks can be delayed while the synchronous API pumps messages. Exception-catch time is also host observation time.

### Interfaces and lifecycle

Keep `SettleDiagnostic(page,path,width)` compatible; an optional keyword-only `chronology_cell=None` connects its already-installed crash/close callbacks to the independent host object. Invoke its lifecycle recorder **before** either the rich-ledger cutoff or `closed` checks, and independently of probe-phase state. Do not reopen rich collection. Keep old probe lifecycle counts unchanged.

Add a small `SweepChronology` in the same source file, not a generic framework:

- `SweepChronology()` creates fixed state; its methods are best effort and must not throw into the gate. Guard observer construction too; unavailable observer state cannot prevent the original sweep from running.
- `begin_cell(ordinal:int, route_index:int, width_index:int|None) -> CellChronology`: indices are1-based into the unchanged static `ROUTES`/`WIDTHS`; ordinal is the actual planned selected-cell execution ordinal1..205. Capture before `context.new_page()`; attach page listeners immediately after page creation through the existing diagnostic setup. No URL/path/query/fragment is copied.
- `mark(name)` on a cell accepts exactly `settle_start`, `exception_catch`, `probe_start`, `page_close_start`; `cell_start` is initialized by `begin_cell`. Each slot is first-write only. Mark exception entry before formatting/printing the original exception. Mark probe immediately before the existing probe call. Normal `page.close()` retains its exact original position; mark immediately before it, never call an additional close.
- `observe_lifecycle(kind)` accepts only `crash`/`close`, first occurrence only. It records a host stamp and seen flag; it makes no page/property/API query and does not print.
- `retain_failure(cell, kind)` accepts `infra`, `exception`, `assertion`. Retain the first assertion-failed cell only if no terminal failure exists; any terminal infra/exception replaces that earlier nonterminal cell with the active failing cell. At most active+retained objects exist. A callback closes over its original cell, never a mutable active-cell lookup. A successful cell is discarded after its existing close; discard obsolete records and detach only newly owned listeners where needed. Existing successful-cell traces keep their current selection.
- `observe_disconnect()` is registered once on the browser immediately after launch, with an independent guarded registration from page listeners. Record first host receipt and the active ordinal then (or null during behavior checks/after the sweep). Browser disconnect is sweep-scoped evidence, never assigned to a page by that ordinal.
- `mark_sweep(name)` accepts `sweep_start`, `browser_ready`, `teardown_start`, `teardown_end`. Set start before the existing Playwright context entry, ready after launch. Set teardown start in a nested `finally` immediately before Playwright context unwind, or immediately before the existing explicit final `browser.close()` on the normal path, whichever comes first. Set teardown end in the existing outer `finally` after the context has exited, before existing server shutdown. Add no close/wait/action. A close/unwind exception must retain original propagation.
- `emit_terminal(outcome)` emits at most once in that outer `finally`, after teardown-end stamping and before server shutdown. The outcome is the already-known gate result (`pass`, `assertion_failure`, `infra_failure`, `engine_unavailable`, `exception`, `unknown`); it cannot determine the gate result. Keep the failed cell reachable through teardown so close/disconnect delivered during existing unwind can be observed. Do not drain events or wait for them. If the host never reaches finally, no receipt is promised.

Register crash and close independently so one observer setup failure cannot suppress the other, and expose separate armed booleans. A first event with a failed clock has `seen:true, stamp:null`; it must not be replaced by a later successfully timestamped event. A callback after the13thsecond or after `end_probe_observation` still updates its first-event scalar. No new timers, threads, JS, event pumping or browser liveness reads.

After each ordinary page close, clear that diagnostic's optional chronology-cell reference; do not leave closed-page listener closures retaining every successful cell. Implement the new callback linkage by reading that diagnostic's optional reference, not by creating another lambda that permanently captures the cell. The reference can transition only from its original cell to null; never reassign it to a later active cell. When replacing a retained failure, drop the old scalar reference and clear any old optional diagnostic linkage. Keep at most the active cell and the selected failed-cell scalar record. The original crash/close listeners and probe counters retain their old semantics. For terminal failure, keep the optional reference until existing context unwind finishes. Failure of observer-reference cleanup is diagnostic-only and must not invoke any extra page close or change exception propagation.

Every added construction, clock read, registration, mark, cleanup and terminal-export call has its own guarded diagnostic boundary, including operations in `finally`. Do not add a `return` in `finally`, wrap/replace an original exception, or let a diagnostic exception prevent existing server shutdown. An original exception remains the same object and propagates through the same original teardown; original return values remain unchanged. A missing receipt is preferable to masking that outcome.

### Closed output and bounds

Emit one line with prefix `WEBKIT_HOST_CHRONOLOGY ` and ASCII JSON. Limit **4096bytes for the entire line including prefix and newline**. At most one line/sweep; Chromium emits none. Schema has exactly:

```
version: 1
engine: "webkit"
outcome: pass | assertion_failure | infra_failure | engine_unavailable | exception | unknown
planned_cells: integer 0..205
sweep: {sweep_start, browser_ready, teardown_start, teardown_end}  // Stamp|null
disconnect: {armed:bool, seen:bool, active_ordinal:1..205|null, stamp:Stamp|null}
failed_cell: null | {
  ordinal:1..205, route_index:1..41, width_index:1..5|null,
  kind:infra|exception|assertion,
  cell_start:Stamp|null, settle_start:Stamp|null, exception_catch:Stamp|null,
  probe_start:Stamp|null, page_close_start:Stamp|null,
  crash:{armed:bool, seen:bool, stamp:Stamp|null},
  close:{armed:bool, seen:bool, stamp:Stamp|null}
}
observer_errors: {clock:bool, registration:bool, serialization:bool}
```

The default sweep must report planned_cells205; route/width indices map to source-owned static lists in the archived candidate. With existing subset options, map back to those static lists; unknown/custom width uses null `width_index`. An oversized/noncanonical selected matrix emits the bounded fallback schema below; do not alter the original CLI/gate. Do not derive indices by parsing current page URLs. No raw route, nonce, error, request, message, source code, token, PID or module is added here. The existing original logs are outside this additive schema and are not expanded.

Validate exact keys/types/finite enums at export. On invalid/oversized data, emit only `{"version":1,"engine":"webkit","outcome":"unknown","observer_errors":{"clock":false,"registration":false,"serialization":true}}` under the same prefix/cap; document this exact alternative schema. Use existing `emit_diagnostic_line`; swallow encoding/output errors without replacing an original return/exception. Output failure may produce no receipt and is unknown, never success. Keep fixed-state serialization bounded; no looping over event history.

### What these fields discriminate

| Observation | Useful distinction | Does not establish |
| --- | --- | --- |
| Ordinal/static route+width indices, cell-start stamp | Which planned cell was active, its absolute host start, time spent before settlement | Executed geometry or page/PID identity |
| Settle-start versus catch monotonic brackets | Configured wait boundary versus actual catch delay, including the previously unexplained gap | Exact scheduler/native timeout deadline or cause of delay |
| First crash/close receipt and seen/armed state | Host observed lifecycle loss before catch, probe or teardown; absent registration versus no delivered event | Native occurrence timestamp, healthy page from absence, or ownership of a journal PID |
| Probe-start | Before-probe versus during-probe callback receipt without extrapolating from a10s timeout | Successful probe/document association |
| Page-close/sweep-teardown boundaries and disconnect | Explicit normal close/context unwind ordering versus callback receipt | Whether an earlier underlying native event was delivered late |
| Paired UTC/monotonic brackets | Journal-window overlap and clock-consistency checks | A precise UTC mapping across clock jumps or a causal join |
| Seen stamp null/errors | Failed timing observation versus a missing event | A zero timestamp or a later event substituted for the first |

## B. Finite observation of module-policy refusals

### One parse and unchanged refusal

Replace internal parsing implementation with `_kernel_message_details(message, parity_names=()) -> (event_or_none, rejection_stage_or_none, rejected_detail_or_none)`. `_parse_kernel_message` remains the compatibility wrapper returning its first two values; `parse_kernel_message` retains its existing result. `correlate_kernel` calls the detailed function once per row. All paths share the same regex/number validation; no second relaxed regex/parser, replay parsing pass, new accepted token or normalization of a kernel module.

Accepted event behavior and rejection-stage priority stay byte-for-byte equivalent. For `module_policy` only, continue the **existing** producer-ending/CPU checks in a private observation branch. Return private detail exactly `{tid, pc, module_token, non_module_valid}` after existing text/prefix/suffix/TID validation. The original result remains `event=None, stage=module_policy`, `kernel_unsupported_format`, incomplete scan and null ownership. Unsupported three-number/no-CPU and invalid CPU/core/socket stay refused and get `non_module_valid:false`; they cannot enter private candidate comparison. Raw TASK/error/address/SP/etc. are never retained. Transient token remains bounded by existing4096-byte line and is discarded after classification.

Factor the existing candidate comparison into `_kernel_candidate_check(event,boot_id,timestamp,record,thread,*,compare_module:bool) -> excluded|missing_boot|missing_zero|match`, reused by accepted correlation (`compare_module=True`) and refusal observation (`False`). Keep exact TID indexing, record SIGSEGV requirement, boot equality, `[crash_us,crash_us+2000000)` interval, original unambiguous frame-zero PC equality, and existing module comparison for accepted candidates. Preserve existing reason emission and ambiguity counts in the accepted caller. A rejected-row comparison **intentionally omits module equality only to investigate that refusal**; it cannot create an accepted event, pair count, selected frame, changed completeness or fault attribution.

For each otherwise valid refused row classify against all currently retained/indexed eligible records/TIDs (up to3×64), before export selection:

- `no_retained_candidate`: every examined candidate is excluded.
- `one_retained_candidate`: exactly one complete private match, no unresolved potentially matching retained candidate.
- `multiple_retained_candidates`: at least two complete matches, no unresolved potentially matching retained candidate.
- `indeterminate`: a potentially matching retained candidate has missing/conflicting/filtered original#0 or missing boot; diagnostic comparison failed or was not completed.
- `structurally_invalid`: `non_module_valid:false`; do not compare at all.

These names deliberately refer to retained candidates. Existing incomplete coredump population is still incomplete; `one_retained_candidate` never means globally unique. Rejected rows cannot repair `_frame_zero` or use first retained frame as#0. No TID/boot/PC/delta/module/raw message is exported by this new observation, even when a comparison matches.

### Exact resolved alias without a new probe

Current installed identity is exported under canonical `WPE_MODULE`; it does not reveal the resolved basename. Merely comparing against that canonical string cannot answer the preflight's alias question. Reusing `approved_module` would establish only a version-family spelling, not equality to the installed file.

Minimal variation: extend existing `read_elf_identity(path,*,expected_root,include_resolved_basename=False)` with an optional **private** `_resolved_basename` return only after all current open/hash/inode/size/mtime/re-resolution checks succeed. Default callers return their unchanged `{sha256,build_id}`. The existing fixed child calls it with the flag, still emits≤1024bytes to its parent under its existing2s ceiling; no new child or filesystem pass. `installed_identity(...,private_observation=None)` keeps its current `(public_identity,reasons)` return and fills only the private sink after strict child-envelope validation. Validate basename is exactly canonical WPE or an already admitted `VERSIONED_MODULE` whose base is WPE, with no slash/control/extra fields; non-WebKit profiles discard it. Public `installed_identity` stays unchanged. A successful identity is installed-file evidence, not crash-mapped identity.

Because identity runs **after** correlation, retain only a bounded pending summary in the collector's existing process:

- Tokens that cannot be an already admitted WPE version-family basename are immediately `other_rejected`; discard the token. No new module-family expansion.
- For possible versioned WPE aliases, retain at most8distinct tokens, each≤64ASCII bytes, privately with five saturated counters corresponding to the relations above. No raw row, PC, TID, boot, timestamp or candidate reference survives this aggregation.
- A ninth distinct possible alias is assigned to `unknown_alias` with its already computed relation, and latches observation truncation; never evict/relabel earlier data. Continue the existing full bounded kernel scan and accepted correlation. New cap does not change old candidate semantics.
- Finalize after the one existing identity phase: exact token equality to validated resolved basename becomes `resolved_wpe_alias`; other retained possible aliases become `other_rejected`. Missing/denied/mutated/timed-out identity makes them `unknown_alias`. Offline replay never consults the host; its default is unavailable alias identity. Unit tests can pass a synthetic validated private basename directly at the existing helper seam; no new CLI path or live fallback.

Use `_observe_module_rejection(state,detail,relation)` and `_finalize_module_rejections(state,resolved_wpe_basename)` as collector-local functions. State has fixed3buckets×5counters plus≤8private tokens×5counters and one truncation bit. Counters saturate at2, meaning0none/1one/2two-or-more. Repeated rows count as repeated observations; no deduplication that manufactures uniqueness. Each relevant row performs at most the already bounded3×64candidate checks, then constant bounded aggregation. Existing watchdog covers the work; no deadline extension.

### Closed optional output

Only the WebKit profile emits optional top-level `kernel_module_policy_observation`, version1; collector schema_version remains2. Emit when a module-policy refusal was seen; absence means no such summary was retained, not proof no refusal existed. GPU profile behavior/output remains unchanged. Exact fields:

```
version: 1
coverage: "complete" | "partial"
alias_resolution: "available" | "unavailable"
pending_alias_limit_hit: bool
buckets: {
  resolved_wpe_alias: RelationCounts,
  other_rejected: RelationCounts,
  unknown_alias: RelationCounts
}
RelationCounts = {
  structurally_invalid: 0|1|2,
  no_retained_candidate: 0|1|2,
  one_retained_candidate: 0|1|2,
  multiple_retained_candidates: 0|1|2,
  indeterminate: 0|1|2
}
```

`coverage=complete` means all retrieved bounded kernel rows were classifiable for this observation and no relevant observation was lost. It is independent of `candidate_scan_complete`; module rejection keeps that false. Raw/kernel overflow, malformed relevant projection, incomplete query, deadline, observation error or alias-slot overflow makes coverage partial. Missing alias resolution alone yields unknown_alias but is not a claim of a truncated kernel scan. Full population/boot/source uncertainty remains in existing fields. A wholly timed-out existing safe fallback may omit this object; it must not re-traverse pending state or invent completeness.

Object maximum1024ASCII bytes; exact export validation rejects hostile/extra keys and wrong types, including bool-as-int. Public export only copies the fixed schema, never private state or child envelope. It consumes the **existing24KiB line budget**; existing peer/extra-record trimming priority remains, with proven accepted frame-zero protected as before. If an invalid/oversized observation appears, omit it, leave old result semantics intact and mark existing `partial:true`; do not invent a kernel rejection reason or change attribution. No new raw log/artifact.

### What these fields discriminate

| Classification | Supported conclusion | Limit |
| --- | --- | --- |
| resolved_wpe_alias + structurally valid relation | A refused spelling exactly equals the privately validated installed WPE basename | Does not establish that crash mapped that file |
| resolved_wpe_alias + one_retained_candidate | The rejection is associated through existing private TID/boot/time/#0-PC tests with one retained candidate; concrete policy discrepancy for later review | Not accepted attribution, global uniqueness, page ownership or causation |
| other_rejected | Refused token is not that resolved installed alias (or cannot be in its admitted family) | Does not reveal/identify a driver, module or repair |
| no_retained_candidate | No match among completely checked retained candidates | Cannot exclude omitted records or a missing kernel event |
| structurally_invalid | Module policy masked another existing grammar/range refusal | Allowlist repair alone would not admit this row |
| unknown_alias / indeterminate / partial | Required identity, original#0, candidate or observation evidence is unavailable | No guessed token, generalized normalizer or cause claim |

## Preflight sufficiency and nonclaims

This is the minimum variation that can answer the preflight's actual questions. Timestamps alone cannot supply native occurrence time or page/PID association; late callback delivery stays ambiguous. A boolean `module_policy` plus canonical installed SONAME cannot distinguish a resolved alias; the private child basename is required. Comparing a prefix without completing existing non-module checks risks treating a malformed producer line as a candidate. These limits are explicit rather than reasons to widen collection.

Even perfect chronology plus resolved-alias/private-candidate evidence does not explain why a process faulted. It may justify a separately reviewed parser-policy amendment, never automatic token admission or an application workaround. If exact page ownership becomes necessary, stop and design that evidence separately. A current passing sweep with incidental native records remains a valid counterexample to time-window attribution.

## Single-capture evaluation and stop contract

The previous run43956051794 remains failed. For the successor, record original gate result first, including last completed/failed cell and unexecuted cells. Full original205cell and assertion success is acceptance evidence for that source only; a pass alone explains no historical failure. Home/GPU remain separate gate results and are not instrumented again by this proposal.

Evaluate the new receipt in this order:

1. Verify exact source/capture identity externally using the existing receipt/archival scheme; verify schema/caps and clocks. Missing or invalid receipt is missing evidence, not a reason to repeat.
2. Establish host-observed cell/settle/catch/probe/cleanup ordering with monotonic brackets. Report UTC overlap with journal records only when clock anchors support it. Preserve callback-delivery/native-occurrence uncertainty and absent events.
3. Read finite rejection buckets with candidate/population completeness alongside them. A valid resolved alias plus retained-candidate comparison identifies an evidenced collector policy discrepancy for separate repair design. It does not authorize admission or fault attribution. Other/unknown/invalid classifications retain the appropriate unknown; do not infer a driver spelling.
4. Stop after interpretation whether pass, fail, unavailable, incomplete or inconclusive. No automatic second capture. A further change requires a new concrete discrimination or evidenced repair, accepted design and review. If no repairable issue is established, report the remaining gate blocker/unknowns rather than applying CSS/backend/lifetime/timeouts changes.

## Accepted design provenance

The immutable external design is `webkit-successor-design-20261116.md`, SHA256 `6e8f80fb6a4e585fe19c7b5b5e0112594fe3d31a998facae54fb4a0d1da70e81`. The coordinator fully read that document, its retention/resource amendments, and the independent `webkit-successor-builder-review-20261116.md`. Both are retained under release-evidence/open-pr-review. The independent review found no important unresolved design defect. The original diagnostic plan completed its one corrected capture; this successor is a new, specifically reviewed observation change and does not erase or rerun the old result.
