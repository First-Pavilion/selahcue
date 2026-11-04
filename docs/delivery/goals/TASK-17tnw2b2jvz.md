# Goal Contract — TASK-17tnw2b2jvz

## Identity
- Goal ID: TASK-17tnw2b2jvz
- Parent goal ID: NONE
- Title: Home and Pricing show the current public catalogue with honest states
- Role: frontend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2jvz
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 7
- Independent verification required: yes

## Objective
Home and Pricing render public API plan names, weekly allowances and exact prices without hardcoded commercial data, invented claims or a non-working purchase link.

## Baseline
Verified base main013a84bc70055d63c79c1ba12212e631842fb03d. Home and Pricing currently show only unpublished empty copy. PricingCard exists with accessible disabled CTA. The public GET contract is draft PR366/source439ca56f, not merged, with mandatory HTTP/admin E2E blockers. Root has LIVE-read the task and supplied criteria. Native worktree tool failed repository identification; git created this isolated worktree. Primary user mobile lock is untouched.

## Inputs and evidence sources
- Root LIVE task read and assignment, original ticket https://app.clickup.com/t/17tnw2b2jvz.
- Public API draft366 exact439ca56f and its committed evidence; root contract /private/tmp/wave2-public-catalogue-contract.md.
- Existing PricingCard/Home/Pricing layout, copy ledgers and browser guards.

## Scope
### In scope
- Shared catalogue loader, bounded validated data and reuse of existing PricingCard.
- Loading, empty, unavailable, unpriced, zero and multiple configured offers; API-derived weekly allowances and watermark only.
- Exact decimal-string display, cancellation/race cleanup, safe text rendering and fresh fetch on route entry/retry.
- Faithful API-driven copy ledgers, unit/runtime tests, core/Home/responsive browser checks and evidence.
### Non-goals
- No API/proxy/auth/admin resolver or staff permission changes, billing/payment implementation, invented prices, default currency/interval, private device/output/NDI claims, new design or App.vue/footer changes.
- No deployment, installer dispatch, real provider/data collection, or production operation.
### Constraints
- All names/prices/limits are response data, never view or ledger literals; no arbitrary claim-ban exemption or geometry-check weakening.
- CTA disabled as Not available yet because the exact current API has no destination field.
- Comparison/table and billing toggle must not invent unavailable data; all configured offers may be displayed without selecting a commercial default, subject to root clarification.
- Root owns independent four reviews, actual CI, integration and QA. Worktree is agent-owned and other edits must be preserved.
### Assumptions and unknowns
- VERIFIED: current GET schema has no CTA destination or plan description/popularity; do not fabricate them.
- BLOCKED: real public backend/admin-mutation acceptance and dependency merge; fixtures prove frontend behavior only.
- UNKNOWN: native ClickUp write recovery. Root explicitly permits this necessary selected work with start status pending; do not claim a saved In Progress status.

## Dependencies and approvals
- User authorizes wave2 ten tickets and named implementation/review/fix loop.
- PR366 public read endpoint must satisfy its own required acceptance and merge before this frontend can merge/QA; root owns dependency disposition.
- ClickUp connector daily quota1000 exhausted and CUA inputs fail CDP deadlines; no MCP retry before16:16UTC. Exact pending start update is saved locally for root backfill.
- Existing approved design/component reused, no new design decision requested. Engine is bundled goal.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Home and Pricing render response-only names, allowances and exact current offers; distinguish absent/null from configured zero | unit contract/format tests plus real browser fixture states | alternate names/values render, max64-bit exact, no invented currency or private limits | docs/delivery/evidence/17tnw2b2jvz.md | PASS |
| C-002 | yes | Loading/unavailable/empty/unpriced and retry/navigation changes are honest, cancellable and safe | browser delayed/error/change/escape scenarios and loader tests | no stale fallback, retry updates, unmount abort, no script interpretation; disabled explained CTA | focused runtime receipt | PASS |
| C-003 | yes | Copy ledgers remain exact and claim controls detect invented data; layout/headings/responsiveness remain valid | updated real SSR and CLI negative controls; core/Home/responsive Chromium and WebKit | all checks pass with no skipped level or weakened claim/geometry controls | unit/browser logs | BLOCKED |
| C-004 | yes | Existing marketing gate passes on the actual source | make marketing-check | type-check/lint/full node suite/build exit0 | /private/tmp/17tnw2b2jvz-it7-marketing-check.log:1256passed0fail0skip plus lint/type/build | PASS |
| C-005 | yes | Public backend dependency and required actual integration acceptance are satisfied | root verifies merged366, runtime/admin E2E and frontend real-stack behavior | current deployed-like API contract and no outstanding mandatory prerequisite | root dependency evidence | BLOCKED |
| C-006 | yes | Cody, Shadow, Quinn, Vera and actual current CI pass before merge/QA | root independent reviews/CI/main/ClickUp readback | four passes, CI success, verified main before QA | root receipts | PENDING |
| C-007 | yes | The legal harness supplies only exact public catalogue GET JSON, waits readiness and still rejects real unrelated failed requests | actual legal419check gate and browser negative control through the existing guard |419pass; inserted unrelatedrequest fails the unchanged navigation console assertion | docs/delivery/evidence/17tnw2b2jvz.md | PENDING |
| C-008 | yes | Matrix navigation follows visible native controls rather than nominal viewport width | actual WebKit768 old-helper negative/current-helper positive and one full matrix | oldnominalhelper fails hidden desktop link; correctedvisiblehelper passes nativeclicks, matrix complete bothengines | iteration7-navigation/matrix JSON and retained negative logs | PASS |

## Verification plan
- Focused verification: real contract parser/decimal display tests, request/cancellation and Vue/browser fixture states with adverse responses and changed values.
- Broader regression verification: make marketing-check; core/Home/responsive both engines; preserve old claim bans and test their negative controls against inserted invented values.
- Independent verifier: root coordinates Cody, Shadow, Quinn and Vera; author cannot self-approve.
- Required environment: installed pinned Node/Vue dependencies and Playwright Chromium/WebKit; local synthetic fixtures, not real customer data.

## Iteration ledger
### Iteration1
- Target criterion: C-001 through C-004 baseline and failing regression.
- Hypothesis: one shared API catalogue component can supply both views while reusing accessible PricingCard and exact data-driven ledgers.
- Change or investigation: inspect current components/tests and public GET contract, create goal, then establish test baseline and failing behavior before production edits.
- Verifier executed: goal validator, npm test, real SSR loading test RED/GREEN, retained preimplementation build and browser RED.
- Result: structural validator passed; isolated pinned npm ci offline passed; baseline full Node1250passed. Real initial Home SSR loading behavior failed before product changes and passed afterward. Preimplementation browser bundle also fails missing loading state; first loopback launch sandbox-denied, authorized escalation executed, no external account.
- New evidence: both views are currently static empty states; existing old guards explicitly forbid any cards until the API follow-up.
- Decision: iterate

## Risks and rollback
- Risks: stale/cached commercial data, precision loss, response-based claims hidden from ledgers, untrusted rendering, shared layout drift and required backend dependency unavailable.
- Rollback or recovery: revert this isolated frontend change; no data/schema/runtime configuration changes.

## Pause and escalation conditions
- Original maxima4/5 and all prior ledgers remain recorded. Root explicitly authorizes iteration6 only for the confirmed nominal-width matrix navigation helper bug, its actual old-helper negative/current-helper positive and ONE full matrix. No further full WebKit responsive retry, production/bundle/style/breakpoint/tolerance change or silent reset. Stop after iteration6 or publication rejection.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b2jvz.md
- Validator result: structural validation passed; completion validation intentionally exits1 with mandatory C-003/C-005 blocked and C-006 pending.
- Independent verification result: Shadow identified actual old-head legal failure; verified fixture remediation ready for root four-review refresh. No all-four/currentCI pass claimed.
- Terminal state: BLOCKED.
- Remaining failed or blocked criteria: C-003 current matrix7partial/old nominal navigation helper and separate fullWebKit20s/Page.goto UNKNOWN; C-005 backend/admin E2E blocked; C-006 fourreviews/currenthostedCI/mergeQA pending; C-008 attempted helper positive failed and was explicitly rolled back. C-007 legal419/strict actualnegative passes. Current1256/Home262/core304/Chromium2379 passed; no current fullmatrix/fullWebKit pass.
- ClickUp final evidence comment: native start/status writes pending recovery; prepared payload /private/tmp/17tnw2b2jvz-clickup-start.md.

### Iteration2
- Target criterion: C-001 through C-004.
- Hypothesis: shared strict projection validation/exact decimal strings and lifecycle-owned fresh fetch can render both pages without commercial defaults.
- Change or investigation: implemented shared loader/component, reused PricingCard price slot and existing interval toggle with neutral All intervals; added unit wire/precision/bounds checks and synthetic browser state matrix. Replaced obsolete SSR empty copy with loading, retained claim bans; fixed truthful FAQ text and exact ledger. Root confirmed conditional interval support; comparison table omitted because no additional comparison contract is required, public weekly data is in cards.
- Verifier executed: loading SSR GREEN; affected149 unit tests pass; type-check/lint and production build pass. Initial ledger failures caught obsolete FAQ line and ellipsis control assumption; exact copy/control corrected. Initial browser test used hidden desktop Pricing link on mobile and failed locator visibility; test now uses actual mobile menu, not force click.
- Result: implementation/unit green; current full browser and regression gates pending.
- New evidence: exact64-bit maximum retained, zero/null separate, all configured currencies preserved. Native write and backend dependency remain blocked; no source/proxy/backend changes.
- Decision: iterate

### Iteration3
- Target criterion: C-001 through C-004 runtime/regression.
- Hypothesis: wrapping response labels at the actual card heading and cancelling refused unread bodies removes observed overflow/resource retention without weakening guards.
- Change or investigation: actual320px mixed-offer long-name browser failed overflow. Added min-width0/overflow-wrap:anywhere to existing card name; short-name design unchanged. Added actual CSS-removal negative control and lifecycle abort-signal observation. New real Response-stream test demonstrated unread503 body was not cancelled (RED); refusal now cancels it. Exact API-driven card-copy ledger compares every card line against response data plus approved labels, with independent Python integer formatting, not production helpers.
- Verifier executed: prior full marketing gate passed; prior core304checks0fail, final core frame regression completing at record. Cancel-body RED verified. Updated final browser/full/regression gates pending after source correction.
- Result: new concrete bugs identified and narrowly fixed; no tolerance, claim ban, strict CSP or backend changes. A ledger append command used the wrong relative docs path after source edits; source edits applied and ledger was separately updated at repository root; no verification success inferred from that command.
- New evidence: /private/tmp/17tnw2b2jvz-overflow-red.log actual overflow failure, /private/tmp/17tnw2b2jvz-error-cancel-red.log actualFalsevsTrue. Normal fast-forward of source baseline to reviewed current main85f1fbe7 only adds checker/docs outside marketing.
- Decision: iterate

### Iteration4
- Target criterion: C-001 through C-003 final bounded browser set; C-004 already passes current production source.
- Hypothesis: actual page-asset readiness and route-root observation, with a stable built bundle and serialized verifiers, allow the required checks to observe the intended product state without masking overflow.
- Change or investigation: no further production edits authorized in this final iteration. Root explicitly authorized exactly one serialized full catalogue matrix, final Home/core and full WebKit sweep, with no timeout/budget changes or further retries. Current source is frozen on main85f1fbe7. Prior iteration3 full responsive Chromium2379checks0fail is retained only for identical source; WebKit exited2 at320/admin/licenses20second navigation INFRA, never counted passed. Initial tablet2-column source was corrected to existing1-column below1200 design. Dormant literal Pro-first rule is superseded by API-authoritative visual order because the wire has no popularity flag; its check remains exact against synthetic data, not removed.
- Verifier executed: final set pending. Focused corrected WebKit768 scenario39checksPASS on unchanged production source validates actual loading/mixed offers/escaped text/copy/negative controls/retry/abort. Previous fullmatrix retry-state timeout cause remains UNKNOWN; this scoped pass does not prove that cause. Diagnostics now record exact scenario/DOM/request counts and progress. Earlier WebKit overflow diagnostic showed native-size1254px logo IMG, not card bounds; test now awaits actual asset load, without hiding/clipping or changing overflow allowance. Pending route callbacks are explicitly aborted/reaped at cleanup.
- Result: pending final one-shot set; no further automatic retry after a mandatory verifier failure.
- New evidence: /private/tmp/17tnw2b2jvz-retry-diagnostic.json39PASS; /private/tmp/17tnw2b2jvz-webkit-style-readiness.json; earlier infra/error logs retained. Complete make marketing-check1256tests/lint/type/build passed after all production corrections.
- Decision: gate-review

## Final iteration4 outcome
- The authorized single serialized set finished: full catalogue matrix476checks/12scenarios both enginesPASS; Home262plus strict frame/overflow controlsPASS; core304plus20nominal/20actualoverflow negativesPASS. WebKit full sweep exited2 on375px/signin Page.goto20second timeout; exact cause UNKNOWN. No further retry, source edit, budget increase or assertion waiver occurred.
- Full Chromium2379/0 remains relevant for unchanged production inputs; current117default bundle files match the artifact used for it.144frozen production inputs reverified unchanged. All verifiers reaped. Current node gate1256/lint/type/build passes.
- C-003/C-005 BLOCKED; C-006 pending root. Goal maximum4 reached. Draft source can be inspected with these explicit blockers, not merged/QA or called complete.

### Iteration5 — explicit review remediation, same Goal
- Target criterion: C-007 and parent-owned C-006 review/CI, preserving blockedC-003/C-005.
- Hypothesis: the existing legal fixture server returns SPAHTML to the newly mounted public catalogue fetch; supplying only the exact anonymousGET JSON and waiting for actual card readiness removes the request failure without suppressing its guard.
- Change or investigation: root authorized maximum4to5 for ONE narrowly bounded legal-fixture fix/verification after Shadow Changesrequested. Actual hosted legal41848524912/job126638280109 observed417pass2fail/419, both navigation console assertions list exactcatalogue net::ERR_ABORTED. Inspected the complete legal routing/request-failure guard and new loader; cancellation remains correct production behavior. Normal merge of reviewed main1488d310; target85→1488 marketing subtree is identical638bfeb9454ea315b01e456b064692e8c1597f38. No API/proxy/lock/runtime frontend change. Earlier1256/476/Home262/core304/Chromium2379 evidence retained for byte-identical production inputs only.
- Verifier executed: structural validation and deterministic missing-fixture browser RED pending; narrow actual legal419 and unrelatedfailedrequest negative proof planned. No full WebKit sweep or API rehearsal.
- Result: pending.
- New evidence: /private/tmp/wave2-shadow-367.md and actual hosted failed-step log; no independent reviewer Pass or full acceptance inferred.
- Decision: iterate

#### Iteration5 explicit target expansion
Root subsequently merged fully reviewed footer361 to main2f4dcc25. Normal merge preserved target App.vue byte-for-byte and responsive resolved-child wait together with this branch's API fixtures/order assertions; no hand conflict or own App edit. Because App readiness is a relevant new frontend input, old complete browser evidence is historical unless its scope is proven unaffected. Root explicitly broadens this SAME iteration5 (maximum remains5, all original1–4 retained) to ONE serialized current make/build, corrected complete legal419, actual unrelated-aborted-request negative, full catalogue matrix/Home/core and complete responsive both engines on the new frozen bundle. No additional retry or budget change is authorized after that set. Existing C-003/C-005 remain blocked until their actual verifiers complete; backend dependency is not waived.
Deterministic pre-fix response probe reproduced exact catalogue GET200/text-html/index989bytes and failed application-json assertion. This establishes the missing fixture independently of browser-specific abort timing; no claim the precise hostedERR_ABORTED was reproduced locally. The first probe-file command used a wrong relative working-directory path and never created/executed the probe; it is not counted as a failing behavioral check. Corrected probe executes the real legal harness/server and frontend bundle.

## Final iteration5 outcome
- Current main2f4dcc25 was integrated normally; target App.vue remains byte-identical and own API-order/fixture changes plus resolved-childwait coexist. Current make1256/lint/type/buildPASS, corrected complete legal419/0PASS, actual unrelated net::ERR_ABORTED correctly fails the ORIGINAL navigation console guard (expectednegativePASS). Current Home262plusframePASS, core304plusframePASS, Chromium fullresponsive2379/0PASS. All219 frozen inputs stayed unchanged throughout the serialized set.
- One-shot current matrix failed WebKit/Home768 when its nominalwidth helper clicked a hidden desktop Pricing link; all six Chromium scenarios plus WebKitHome320 completed. Full WebKit responsive separately exited2 on375px/affiliates/payouts Page.goto20s; UNKNOWN cause, not explained by the link helper. No test was retried in iteration5.
- After all suites finished, root authorized a single read-only layout probe. Observed requested/innerWidth768 but clientWidth756, mobileMediaTRUE, desktopnone/zero rect, desktopPricingnotvisible, Menuvisible, navbar69px; screenshot inspected. This confirms a test-helper selection bug, without changing production CSS/viewport. Existing NavbarCSS hidesdesktop by default and exposesit at actual min-width768; helper incorrectly trusts the requested dimension.

### Iteration6 — explicit bounded navigation-helper remediation, same Goal
- Target criterion: C-008/current matrix; preserve separate C-003 fullresponsiveWebKit UNKNOWN and C-005 backend blockers.
- Hypothesis: choosing the actual visible Menu button (otherwise native desktop link) follows rendered UI when native scrollbar reservation makes the CSS viewport differ from nominal768.
- Change or investigation: root explicitly extends maximum5to6 after the actual read-only metrics. Only the navigation helper and meaningful old-helper restoration proof may change. Normal clicks only; no forceclick, CSS/viewport/breakpoint/tolerance or production change. Root permits focused real WebKit768 oldnominalnegative/newpositive then ONE full both-engine matrix, unchanged built application; no additional full responsive WebKit retry or automatic iteration.
- Verifier executed: structural validator, old-helper negative/new-helper positive and full matrix pending. Earlier legal419/negative and current1256/Home262/core304/Chromium2379 retained only for unchanged relevant inputs; WebKit fullsweep remains failed/blocked.
- Result: pending. Otto is pausing only his owned native Cargo work before this short browser set; no benchmark/SLA inference.
- New evidence: /private/tmp/17tnw2b2jvz-nav768.json/png/log and matrix7completed diagnostic; no assumption about old independent Page.goto timeouts.
- Decision: iterate

## Final iteration6 outcome and explicit cleanup disposition
- Actual restored-old-helper WebKit768 negative failed on hidden desktop Pricing link as expected. The corrected visible-control attempt selected real Menu but its sheet Pricing link was outsideviewport and detached during normal30second click. Positive FAILED; no full matrix or further retry followed. No post-open metrics confirmed a production cause. Static scroll-lock/breakpoint interaction is a hypothesis only.
- Root explicitly disposed cleanup, NOT a new iteration: revert ONLY own unverified helper conditional to the prior source and exclude failed new navigation proof from the public patch. Copies/failure receipts stay in /private/tmp/17tnw2b2jvz-unverified-visible-helper.patch, -unverified-navigation-proof.py and -it6-navigation* files. Successful legal fixture/proof is retained. All219 iteration5 source/test inputs match their frozen manifest again after this rollback; no application/bundle change or additional test/build occurred.
- Current actual target2f App.vue remains unchanged from reviewed main and responsive resolved-childwait remains combined with API fixtures/order checks. Verified currenttarget gates: make1256/lint/type/build, legal419, actual unrelatedERR_ABORTED guard rejection, Home262+frame, core304+frame, Chromium2379 PASS. Current fullmatrix remains7partial; fullWebKit375/affiliates/payouts20s failure remains UNKNOWN; backendC005 remains blocked. C008 FAIL, not silently deferred or markedpassed. Root will track observed nativeWebKit768 menu issue separately after dedup and own all4 final source reviews/currentCI.
- Maximum6 exhausted with full1–6 ledger retained. All local processes were reaped; Otto notified to resume his owned paused Cargo work. No merge, QA, provider, deploy or installer action. Completion validator must remain non-green while mandatory criteria are unresolved.


### Iteration7 — explicit LOCAL affected remediation, same Goal
- Target criterion: C008 corrected native navigation/current matrix, with C003/C005/C006 remaining independently gated.
- Hypothesis: normally integrating the separately reviewed exact menu commit ec0e82923dea88303ce071c723117f9049b59445 and selecting actually rendered controls fixes the evidenced current WebKit768 helper failure without changing product contracts.
- Change or investigation: coordinator explicitly extends maximum6to7 only for this PRIVATE worktree from exactpublished8bf09ded. Normally merge actualmain a6cbd07dd4684621ffb8bb8d6f08f790fa6946d3 then local exactmenu ec0. Resolve only adjacent package-script conflict by retaining menu test:components and cards test:core/test:catalogue chains; menu source/verification/docs stay byte-exact. Correct only navigate helper nominalwidth condition to actualMenu visibility. All iterations1–6 and failed receipts remain unchanged.
- Verifier executed: structural validator; ONE make/build; actualoldhelpernegative at nativeWebKit768 with currentmenufix, correctedhelperpositive, then ONCE full both-engine12scenario matrix. No full responsive sweep retry, forced click, skip, CSS/breakpoint/tolerance/deadline change.
- Result: pending. Oldhosted2379each belongs oldNavbar8bf and is not current combined fullresponsive evidence.
- New evidence: pending local receipts17tnw2b2jvz-it7-* and source/bundle input manifests.
- Decision: stop after this bounded set on any runtime/verifier failure; no iteration8 without new explicit disposition.

#### Iteration7 publication and dependency boundaries
- Exactmenu ec0 public push was actually rejected before execution; specific public publication approval question is pending without answer. This private combined branch MUST NOT be pushed, published through another branch, or presented as publicPR/CI/main. Localfouraffectedreviews only until root explicitly authorizes publication after exactmenu approval.
- Native17tnw2b2jvz is now In Progress, saved/read back by coordinator. Prior failed status attempts remain historical.
- PR366/C005 actualbackend/adminmutation E2E remains BLOCKED; syntheticHTTP fixtures/servicewrites do not substitute. No backendauthscope expansion or publicAPI localdraft carryover.


## Private iteration7 final outcome
- The authorized set completed once: actual oldnominalhelper negative exit1/WebKitHome768 hiddenDesktop; actualvisiblehelper positive39checksPASS; fullbothengine catalogue matrix476checks/12scenariosPASS on the exact combinedbundle. All238frozen source/test/script/public/configuration map entries and117bundlefiles match after the entire set. No browser/server/subprocess remains running.
- Sole make marketing-check completes1256passed0failed0skipped pluslint/type/build. The initial npmci command used repo-root rather than marketingCWD and failedbeforeinstall; corrected isolated offlineinstall succeeded. No test/setup failure was presented as green.
- Published8bf source tree remains clean/exact8bf. Maina6 and exactreviewedmenu ec0 are real normal localmerge ancestors. The package conflict was only adjacent scriptlines; both independentchains retained. Navbar/menuverifier/docs remain byte-exact ec0. Own new change is the one visible-control condition plus its oldnegative/currentpositive verification driver and evidence.
- C008 PASS on current private source; C001/C002 currentruntime reaffirmed. C004 currentmake PASS. C003 remainsBLOCKED without currentcombined fullresponsive evidence/authorizedretention disposition; old2379each is not currentNavbarwholepass. C005 backend/admin E2E BLOCKED, C006 allfouraffectedreviews/currenthostedCI/main/QA pending. C007 originallegal fixture/guard evidence remains historical scoped8bf, not a new wholelegal pass on this privatebundle.
- Maximum7 consumed, original1–6 retained. Root owns fouraffectedreviews, exactpublicapprovalboundary and futureintegration. No push, alternativepublication, publicPR/CI, mainmerge or QA action was attempted for this combinedsource. Terminalstate BLOCKED for those externalgates, not VERIFIED_COMPLETE.


## Authorized publication/freshness phase after iteration7

- This phase records authorization and input freshness; it is NOT an implementation iteration8, product correction, build or test retry. Maximum7 and all original1–7ledgers/failures remain unchanged.
- User explicitly approved exactCSP6297 and exactmenu ec0 publication. Root verified those payloads were published first, then fully reviewed integrations merged: CSP PR373/mainb5 and menuPR374/main36486b9b63a98ff5fd952c3584cabb005bd56cf0. Their earlier actual auto-review rejection/private-hold labels above remain historical truth; the specific rejected-menu-export boundary is now resolved.
- Root explicitly authorizes this already-four-reviewed d31 cards fix to fast-forward the EXISTING PR367/source codex/17tnw2b2jvz-api-cards after normal currentmain integration. No force push or alternate PR; original8bf worktree remains clean. A future actual auto-review rejection must stop publication without workaround.
- Normal main364 merge succeeded and actual364/8bf ancestry is verified. Its incoming delta from reviewed d31 contains seven CSP Goal/evidence files and exactly two frontend verification files: changed security_headers_headless.py and added security_headers_wait_regression.py. All compiledsrc/public/package/lock/config, matrix/tests/runtime imports and localnavigation driver remain byte-exact d31. The matrix import closure does not import either changed/new CSP verification module.
- Current selectedinput map is239entries, explicitly one changed old CSP script plus one added CSP script versus the historic238 map, zero removals. Do NOT claim old238 map is all current. All117 actual dist files remain byte-exact the artifact consumed by the successful scoped39/final476check12scenario tests. Retain those scoped observed results only within this proved identity; no build, fullmatrix, fullresponsive or wholelegal rerun is performed in this phase.
- Freshness map/imports/hash proof: docs/delivery/evidence/17tnw2b2jvz/publication-retention.json. Root owns final four affected scope/freshness disposition and actual hosted CI on the newly published source, which must close broader C003/C007. C005 actualbackend/admin E2E remainsBLOCKED, never substituted with synthetic fixtures or servicewrites. No merge/QA clearance is granted by publication.
