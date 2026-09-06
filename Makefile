# SelahCue — developer launch / build Makefile
#
# The Rust workspace lives in implementation/desktop; the Tauri operator shell is a
# standalone (workspace-excluded) crate under it. These targets wrap the cargo commands
# so you can launch and drive the app without remembering the paths and feature flags.
#
#   make            # show this help
#   make run        # ONE command: output window + operator shell together (NDI + STT + AI auto-on)
#   make launch     # same as `make run`
#   make run-release# same, but an OPTIMIZED build — use this to judge performance
#   make output     # just the audience output window (native + LAN control server; NDI auto)
#   make operator   # just the Tauri operator shell
#   make remote CMD=go-live   # send one command to a running output window via the CLI
#
# `make run` auto-enables NDI when the SDK is vendored (scripts/fetch_ndi_sdk.sh), STT when cmake
# is present, and the AI-assisted sermon-note path (dev-keys + openai-notes, reading a developer
# OpenAI key from the repo-root .env — see .env.sample) UNCONDITIONALLY — and runs fine without
# any of them — force with `make run NDI=1|0 STT=1|0 AI=1|0`. AI is forced OFF for any RELEASE=1
# build, structurally: see the "AI-assisted sermon notes" comment below for exactly what that
# means and its limits. This exists because a shipped, merged, four-reviewer-tested feature
# (86akby7d8) was invisible from this exact command until 86akcmzyq/86akcmzrd fixed it — do not
# reintroduce an opt-in flag for a future AI feature and expect anyone to find it.
# It also waits for the output window to actually come up before starting the operator (a
# condition, not a fixed sleep); `make run LAUNCH_TIMEOUT=600` raises the give-up backstop.

DESKTOP  := implementation/desktop
OPERATOR := $(DESKTOP)/crates/selahcue-operator
CARGO    ?= cargo
WS       := --manifest-path $(DESKTOP)/Cargo.toml
OP       := --manifest-path $(OPERATOR)/Cargo.toml
# Build profile for the RUN/BUILD targets. Debug is the default because it compiles fast and
# is what you want while iterating. Use RELEASE=1 (or the *-release targets) for anything you
# are judging PERFORMANCE by: the rasterizer is ~30x slower unoptimized, which is the difference
# between a verse appearing in ~2ms and in ~280ms. Never benchmark, demo, or run a live service
# off a debug build.
RELEASE      ?= 0
PROFILE_FLAG := $(if $(filter 1,$(RELEASE)),--release,)
PROFILE_NAME := $(if $(filter 1,$(RELEASE)),release,debug)
# THE single named registry of selahcue-operator Cargo features that must never reach a
# RELEASE=1/--release build of the operator THROUGH THIS MAKEFILE, whatever path OP_FEATURES was
# populated by (auto-detection or a direct override) -- read by `release-ai-guard` below, which is
# the actual backstop: STT_FEATURES/AI_FEATURES's own RELEASE=1 handling independently avoids
# these tokens too, but a developer bypassing that auto-detection with a raw
# `OP_FEATURES=cloud-stt RELEASE=1` still hits this guard. Named and defined in exactly one place
# so `scripts/check_launch_reachability.py` can cross-check it against selahcue-operator/
# Cargo.toml's own `RELEASE:` tags (86akd10dq remediation, Quinn's point on hand-maintained lists
# drifting): a feature tagged `RELEASE: UNSAFE` there that is missing from this list, or a token
# here with no matching `RELEASE: UNSAFE` tag, fails that check rather than drifting silently.
# `dev-keys`/`openai-notes` were here from 86akcmzrd; `cloud-stt` is added by 86akd10dq -- see the
# long comment on `STT_FEATURES` below for why cloud-stt joins this list and plain `stt` does not.
RELEASE_UNSAFE_FEATURES := dev-keys openai-notes cloud-stt
# The local endpoint file the output window writes (matches Rust's std::env::temp_dir()).
ENDPOINT := $(shell python3 -c "import tempfile,os;print(os.path.join(tempfile.gettempdir(),'selahcue-operator-endpoint.json'))" 2>/dev/null)
CMD      ?= next
SECS     ?=
# On-device STT (whisper.cpp + cpal) for the live transcript, run by the operator shell. It needs
# cmake + a C/C++ toolchain to compile whisper.cpp (and downloads the model on first use), so the
# dev RUN targets enable it AUTOMATICALLY when cmake is present and quietly skip it otherwise —
# `make run` never fails just because the STT toolchain is missing (same UX as NDI above). Force
# it with STT=1 (errors if cmake is absent) or disable with STT=0. CI/check/clippy always use the
# default (no-STT) operator build, so this never affects them.
#
# `cloud-stt` (Deepgram live transcription, 86akby7th) rides the SAME toggle rather than getting
# its own (86akd10dq — the third instance of the 86akcmzyq bug class: shipped, merged, four-
# reviewer-tested, and unreachable from this exact command). It is not an independent choice:
# `cloud-stt = ["stt", "selahcue-stt-cloud/deepgram"]` in selahcue-operator/Cargo.toml, and
# `cargo tree -e features --features cloud-stt -p selahcue-operator` confirms that pulls in
# selahcue-stt's `whisper` feature -> whisper-rs-sys -> the SAME cmake build-dependency `stt`
# needs, because mic capture (CpalSource) and resampling live in selahcue-stt regardless of which
# recognizer consumes the audio (see that Cargo.toml's comment on `cloud-stt`). So `cloud-stt`
# cannot be reachable on a machine where plain `stt` cannot -- there is no toolchain-free way to
# offer it, and a separate CLOUD_STT=auto|0|1 toggle would just be re-running STT's own cmake
# preflight a second time for no independent question. It also matches what a developer would
# expect `STT=0` to mean: "no live transcript feature, on-device or cloud" -- not "on-device off,
# but cloud silently still compiled in". Compiling `cloud-stt` in does not itself pick a recognizer:
# that stays the runtime Settings choice (`TranscriptionMode`); a build with no `DEEPGRAM_API_KEY`
# in `.env` reports `KeyMissing` (actionable) instead of `NotInBuild` (the bug this fixes) --
# `dev-keys` already carries that key by default via `AI ?= auto` below.
#
# STT_STATUS/AI_STATUS (below OP_FEATURES_WORDS further down) are derived from the FINAL, resolved
# feature list rather than from STT_FEATURES/AI_FEATURES directly, so the messages stay honest even
# when a developer bypasses this auto-detection entirely with `OP_FEATURES=<features>` — see the
# OP_FEATURES_WORDS comment for why that distinction matters.
#
# RELEASE=1 CLEARS cloud-stt (but NOT plain stt) FROM THIS COMPUTATION -- A DECISION, NOT AN
# OVERSIGHT (86akd10dq remediation, Sana S-1 / Cody Finding A / Quinn High, all three independently
# found the same gap: making cloud-stt reachable by default widened RELEASE=1's reach as a side
# effect, since nothing here or in selahcue-stt-cloud checked the profile before this fix -- Cody
# reproduced it directly: `cargo test --release -p selahcue-stt-cloud --features deepgram` with a
# shell-exported DEEPGRAM_API_KEY read `Ready`, with debug_assertions=false, in the actual binary).
#
# The BINARY-level guard is the real control either way: `selahcue-stt-cloud::credential::
# developer_key_permitted` (mirroring `selahcue_cloud::openai::direct_key_permitted`) now makes
# `developer_credential_from_env` refuse in ANY release profile, through make or a bare
# `cargo build --release --features cloud-stt`, so a RELEASE=1 binary with cloud-stt compiled in
# can never read a shell-exported DEEPGRAM_API_KEY and reports KeyMissing, not Ready -- that alone
# closes the credential leak regardless of what this Makefile does.
#
# Stripping cloud-stt here on TOP of that binary guard is the additional, separately-argued call:
# unlike plain `stt` (which ships in real release artefacts today -- windows-installer.yml
# hardcodes `--features stt`), `cloud-stt`'s ONLY credential source that exists in the tree right
# now is the developer-key path `credential.rs` itself documents as temporary ("Phase 2 replaces
# this entirely... this function is deleted rather than adapted"). Phase 2 (the server-minted
# grant-token endpoint, 86akby3xu) is `planning/todo`, unstarted, normal priority, with its own
# non-goal explicitly excluding "anything on the desktop" -- meaning the desktop-side integration
# that would let cloud-stt reach `Ready` in a release build legitimately is not even ticketed yet.
# So today, a release build carrying cloud-stt provides the user exactly ZERO functional benefit
# (with the binary guard in place it can only ever report KeyMissing) while adding real cost: the
# async/WebSocket dependency surface of `selahcue-stt-cloud`'s `deepgram` feature ships in a real
# artefact for a capability that cannot work, and the operator's Cargo.toml comment on `cloud-stt`
# already describes it the same way it describes `openai-notes` -- "deliberately throwaway...
# deleted when [Phase 2] lands" -- and `openai-notes` itself is fully release-cleared, not merely
# binary-guarded. Re-enabling cloud-stt in release once the desktop-side Phase 2 ticket exists and
# is scoped is a one-line change here, not a cost worth avoiding now by leaving a dead capability
# in a shipped binary. This is a judgement call on present evidence, not a permanent architectural
# position -- revisit it when 86akby3xu's desktop-side ticket lands (see RELEASE_UNSAFE_FEATURES
# above, which scripts/check_launch_reachability.py cross-checks against selahcue-operator/
# Cargo.toml's `RELEASE:` tags so this list and that decision cannot drift apart silently).
STT ?= auto
ifeq ($(STT),0)
STT_FEATURES :=
else ifeq ($(STT),1)
STT_FEATURES := stt $(if $(filter 1,$(RELEASE)),,cloud-stt)
else
STT_FEATURES := $(if $(shell command -v cmake 2>/dev/null),stt $(if $(filter 1,$(RELEASE)),,cloud-stt),)
endif

# AI-assisted sermon notes (`openai-notes`) plus the developer `.env` key loader that feeds it
# (`dev-keys`). Both are real, merged, four-reviewer-tested code (86akby6yy / 86akby7d8) behind
# Cargo features that default OFF at the crate level — correctly, since a release build must never
# carry a direct-to-OpenAI path or a loader that can pick a credential off a stray `.env` (see
# `openai-notes`'/`dev-keys`'s own comments in selahcue-operator/Cargo.toml). The bug this fixes
# (86akcmzyq) was that `make launch`/`make operator` requested NEITHER, so a feature that had
# already shipped and merged stayed unreachable from the one command a developer actually runs —
# the console correctly, but misleadingly, reported "isn't available in this build yet."
#
# RESOLUTION (owner decision, 86akcmzrd): these dev launch targets turn BOTH features on by
# default — the same shape as `STT ?= auto` above — chosen deliberately over an opt-in flag,
# because an opt-in flag is how this bug happened in the first place: a feature ships, merges, and
# stays invisible to anyone who doesn't already know the flag exists. Unlike STT there is no
# native toolchain to probe for (reqwest/rustls, no OpenSSL, no cmake), so "auto" is
# unconditionally on; force off with `make launch AI=0`.
#
# THE RELEASE BOUNDARY IS STRUCTURAL, NOT A DEFAULT THAT HAPPENS TO POINT THE RIGHT WAY:
#   1. RELEASE=1 hard-clears AI_FEATURES below, unconditionally. `make launch RELEASE=1` and
#      `make run-release` can never request dev-keys/openai-notes THROUGH THIS MAKEFILE, no matter
#      what AI is set to — `AI=1 RELEASE=1` still resolves to no AI features. This is an override,
#      not a different default.
#   2. That still leaves a BARE `cargo build --release --features dev-keys` (bypassing Make
#      entirely) as a Cargo-feature-only decision — a Makefile default cannot stop that. So
#      dev_env.rs's `load()` additionally checks `cfg!(debug_assertions)` and no-ops in any
#      `--release` profile regardless of which features were requested — see that file for the
#      full reasoning and its stated limits (a `[profile.release] debug-assertions = true` or a
#      RUSTFLAGS override can still defeat a debug_assertions check, exactly as it can for
#      selahcue-licensing's analogous development-entitlement-key guard). The independent,
#      byte-level backstop for that residual case on shipped installers already exists:
#      scripts/installer_secret_scan.py (86akc041v).
#   3. Neither `make ci`/`check`/`clippy`/`build`/`build-operator` (bare, no RELEASE/AI/STT
#      arguments) nor the one workflow that ships a real artefact
#      (.github/workflows/windows-installer.yml, which hardcodes its own `--features stt` and
#      never reads OP_FEATURES/AI at all) is affected by this default.
AI ?= auto
ifeq ($(AI),0)
AI_FEATURES :=
else ifeq ($(filter 1,$(RELEASE)),1)
AI_FEATURES :=
else
AI_FEATURES := dev-keys openai-notes
endif

# The actual --features list the dev launch targets build with: STT + AI, comma-joined, with
# empty slices dropped so e.g. `STT=0 AI=0` still produces a bare `cargo run` (no trailing/leading
# comma, no --features flag at all). OP_FEATURES=<features> on the command line still overrides
# this outright, exactly as it did before this change — it is a `?=` like everything above.
EMPTY :=
SPACE := $(EMPTY) $(EMPTY)
COMMA := ,
OP_FEATURES ?= $(subst $(SPACE),$(COMMA),$(strip $(STT_FEATURES) $(AI_FEATURES)))
OPRUN       := $(if $(strip $(OP_FEATURES)),--features $(strip $(OP_FEATURES)),)
# Word-list view of the FINAL feature set (whether auto-computed above or supplied directly via
# OP_FEATURES=...) — this, not STT_FEATURES/AI_FEATURES, is what stt-preflight, release-ai-guard
# and the status messages below react to, so a developer who bypasses the AI/STT auto-detection
# with a raw OP_FEATURES= override still gets an honest "what's actually being built" answer
# instead of one describing the auto-detection that never ran. `stt` is matched as a whole TOKEN,
# not a substring, so a raw `OP_FEATURES=cloud-stt` (naming only `cloud-stt`, relying on Cargo's
# own `cloud-stt = ["stt", ...]` implication to pull `stt` in) is not mistaken for the plain `stt`
# token by accident — the two are matched independently below on purpose, not because one of them
# is toolchain-free: CORRECTION (86akd10dq) — a prior version of this comment claimed `cloud-stt`
# "needs no whisper.cpp/cmake toolchain at all". That was wrong, and stale by the time `cloud-stt`
# merged: `cargo tree -e features --features cloud-stt -p selahcue-operator` shows it pulls in
# selahcue-stt's `whisper` feature -> whisper-rs-sys -> cmake, same as plain `stt` (see the
# `cloud-stt` comment above). `stt-preflight` below checks for EITHER token for exactly that
# reason — the wrong comment, left uncorrected, would have kept a raw `OP_FEATURES=cloud-stt`
# invocation skipping the cmake check it actually needs.
OP_FEATURES_WORDS := $(subst $(COMMA),$(SPACE),$(OP_FEATURES))
ifneq ($(filter stt cloud-stt,$(OP_FEATURES_WORDS)),)
STT_STATUS := on ($(strip $(filter stt cloud-stt,$(OP_FEATURES_WORDS))))
else
STT_STATUS := off (run with STT=1, or `brew install cmake`, to enable the live transcript)
endif
ifneq ($(strip $(filter dev-keys openai-notes,$(OP_FEATURES_WORDS))),)
AI_STATUS := on ($(strip $(filter dev-keys openai-notes,$(OP_FEATURES_WORDS))) — reads an OpenAI key from the repo-root .env; see .env.sample)
else ifeq ($(filter 1,$(RELEASE)),1)
AI_STATUS := off (RELEASE=1 never enables dev-keys/openai-notes — see the comment above)
else
AI_STATUS := off (run with AI=1, or unset AI, to enable sermon-note generation)
endif

# On macOS the operator runs from a signed .app bundle so the on-device STT worker can get
# microphone access — a raw `cargo run` binary has no bundle identity, so macOS never prompts
# and mic capture silently returns silence. Everywhere else, run it directly with cargo.
UNAME := $(shell uname)
ifeq ($(UNAME),Darwin)
OPERATOR_RUN := sh scripts/run_operator_macapp.sh $(OPRUN) $(PROFILE_FLAG)
else
OPERATOR_RUN := $(CARGO) run $(OP) $(OPRUN) $(PROFILE_FLAG)
endif

# NDI OUTPUT (Screens page): broadcast a composed audience feed as an NDI source, built against
# the REPO-VENDORED NDI SDK so the build is self-contained (no system-installed SDK, no reliance
# on another app's copy). `make run`/`launch`/`output` enable NDI AUTOMATICALLY when the SDK has
# been vendored (scripts/fetch_ndi_sdk.sh) and run cleanly without it otherwise; `output-ndi`
# forces NDI and errors if it isn't vendored. `make ci` never builds the feature (stays
# native-free). See implementation/desktop/vendor/ndi/README.md.
ifeq ($(UNAME),Darwin)
NDI_OS := macos
else ifeq ($(UNAME),Linux)
NDI_OS := linux
else
NDI_OS := windows
endif
NDI_DIR := $(abspath $(DESKTOP)/vendor/ndi/$(NDI_OS))
ifeq ($(UNAME),Darwin)
NDI_LOADER := DYLD_FALLBACK_LIBRARY_PATH="$(NDI_DIR)/lib"
else ifeq ($(UNAME),Linux)
NDI_LOADER := LD_LIBRARY_PATH="$(NDI_DIR)/lib/x86_64-linux-gnu"
else
NDI_LOADER :=
endif

# Auto-enable NDI for the dev run targets when the SDK has been vendored, so ONE `make run` brings
# up the output window + operator WITH NDI when it's available — and still runs (NDI off) when it
# isn't, with a one-line note. Force NDI (or force-off) explicitly with `make run NDI=1` / `NDI=0`.
NDI ?= auto
ifeq ($(NDI),0)
NDI_ON :=
else ifeq ($(NDI),1)
NDI_ON := 1
else
NDI_ON := $(wildcard $(NDI_DIR)/include/Processing.NDI.Lib.h)
endif
ifeq ($(strip $(NDI_ON)),)
DESKTOP_FEATURES :=
DESKTOP_ENV :=
NDI_STATUS := off (no vendored SDK — run scripts/fetch_ndi_sdk.sh to enable NDI output)
else
DESKTOP_FEATURES := --features ndi
DESKTOP_ENV := NDI_SDK_DIR="$(NDI_DIR)" $(NDI_LOADER)
NDI_STATUS := on (vendored SDK)
endif

.DEFAULT_GOAL := help
.PHONY: help launch run run-release launch-release output-release output output-ndi ndi-preflight operator operator-headless stt-preflight release-ai-guard stage-operator-binaries verify-stage-operator-binaries-create-only remote timer stop-timer demo mobile mobile-test ci nfr build build-output build-operator test test-stt-real-model check clippy fmt clean

# Recursive-make calls that must NOT get GNU Make's special "$(MAKE) literal text" handling
# (documented in the GNU Make manual, "How the MAKE Variable Works": a recipe LINE containing
# the exact substring "$(MAKE)" or "${MAKE}" is force-executed even under `-n`/`-t`/`-q`,
# specifically so a dry run of a genuinely recursive build stays meaningful). Every other line
# in `ci` is an ordinary command `-n` correctly leaves unexecuted; the two operator-placeholder
# calls below, and the nested calls inside verify-stage-operator-binaries-create-only's own
# recipe, used to be the only things in this file that violated that -- `make -n ci` regressed
# from a clean preview to a hard `exit 2` (FAIL(A): sidecar placeholder was not created),
# because the OUTER call was force-executed for real, called INTO a script that made real
# assertions, while the INNER nested call two levels down correctly stayed dry (its own line
# has no $(MAKE) reference to re-trigger the exemption) and created nothing. Root-caused with
# an isolated probe Makefile, not by reading the manual and guessing (86akc2kmh, PR #29).
#
# Using $(MAKE_RECURSE) here instead of the literal text sidesteps the exemption rule entirely:
# real execution is unaffected (identical expansion, jobserver fds still inherited via the
# environment the same as any child process), but under `-n`/`-t`/`-q` the line is printed as
# preview text and never run at all -- restoring the SAME "printed, not executed" contract
# every other line in this file already keeps under `-n`, rather than adding a second,
# target-local mechanism that behaves differently from its surroundings. Verified directly: a
# probe using this indirection stays fully dry under `-n` (zero subprocess spawned, zero side
# effect), and still passes jobserver fds cleanly under `-j` (no warnings, side effect happens).
#
# This is NOT the only tool for this class of problem -- a MAKEFLAGS-based guard
# (`ifneq ($(findstring n,$(filter-out --%,$(MAKEFLAGS))),)`, skip the real logic under a dry
# run) also verified correctly here, and is the right choice for a recursive call that must
# genuinely DO something useful under `-n` (a real preview action), which indirection cannot
# give you since it makes the call vanish under `-n` rather than run a dry-run-aware branch of
# it. This case needs no such preview -- a dry run of a regression test should do nothing -- so
# indirection is the smaller, more durable fix: it depends on one of GNU Make's oldest and most
# stable documented behaviours, not on this machine's particular MAKEFLAGS serialization format
# (which does vary by version/platform, and would need its own re-verification on every one).
#
# Pre-existing $(MAKE) calls elsewhere in this file (run-release, output-release, timer,
# stop-timer) are deliberately NOT switched to this indirection: those genuinely want `-n` to
# cascade into what the target they call would do, and none of them make an assertion whose
# failure depends on a grandchild that -n keeps dry.
#
# THE RULE FOR A FIFTH CALL SITE (Cody, PR #29 review -- stated directly so this is a check,
# not a judgement call): does this line's text contain BOTH a $(MAKE) reference AND other
# logic whose correctness depends on actually running, rather than merely being echoed? If
# yes, it needs $(MAKE_RECURSE). If the entire recipe is nothing but the recursive call
# itself, the literal $(MAKE) is not merely harmless but CORRECT -- it is what lets `-n`
# cascade into a genuine preview of the child target, which is exactly what run-release/
# output-release/timer/stop-timer want and why they keep the literal form.
#
# What counts as "a line" is what makes this checkable rather than approximate: GNU Make's
# exemption matches the recipe LINE AS MAKE PARSES IT, and a backslash-continued shell block --
# however many physical lines or `;`-separated statements it spans -- is ONE such line. That is
# exactly why verify-stage-operator-binaries-create-only's OLD recipe tripped this: its
# assertions and its nested $(MAKE) call shared a single logical line, so the whole block was
# force-executed together, assertions included. A target whose recipe is nothing but
# `$(MAKE) ... sometarget` cannot trip it for the same reason in reverse -- there is no other
# logic on that line to force-execute alongside the call.
MAKE_RECURSE := $(MAKE)

# selahcue-operator's build.rs (tauri_build::build()) validates that the externalBin sidecar
# (`selahcue-output-<triple>`) and the NDI resource dll declared in tauri.conf.json exist on
# disk -- even for a bare `cargo check`/`clippy` that never bundles the app. Both live under
# $(OPERATOR)/binaries/, which is gitignored (selahcue-operator/.gitignore:11), so a fresh
# clone or a fresh `git worktree` -- the very isolation the operating contract mandates for
# every ticket -- never has them, and every target below that touches the operator crate dies
# on `resource path 'binaries/selahcue-output-<triple>' doesn't exist`, on a crate the diff
# usually never touched, with no hint the fix is a one-line touch (86akc2kmh).
#
# .github/workflows/ci.yml stages the identical placeholders for the identical reason (see its
# "Stage Tauri sidecar/resource placeholders" step) -- its own comment calls itself "the
# snippet people copy to reproduce CI locally". This target IS that reproduction, kept in sync
# by hand: it makes the local gate documented at the top of this file actually work from a
# clean checkout. It does not touch ci.yml's step, which is correct as-is and stays untouched.
#
# CREATE-ONLY, ON PURPOSE -- DO NOT MAKE THIS UNCONDITIONAL. `: > file` TRUNCATES, and one of
# these two names is `Processing.NDI.Lib.x64.dll` -- the real NDI SDK redistributable an owner
# vendors by hand (scripts/fetch_ndi_sdk.sh), never built by this repo. `binaries/` is
# gitignored, so truncating a real dll there is SILENT and GIT-UNRECOVERABLE: nothing tracks
# it, nothing can restore it. Harmless on an ephemeral CI runner; not harmless on a developer's
# machine, which is exactly where this target runs. The `[ -e "$$f" ] || [ -h "$$f" ]` guard on
# each file is the entire safety property -- never drop it, and never replace `stage()`'s body
# with an unconditional `: >` or `touch`. The `-h` half matters on its own: a DANGLING symlink
# (e.g. the dll symlinked to an SDK path on a volume that is not currently mounted) reads false
# under `-e` alone, so without `-h` too, `: >` would follow the link and create an empty file
# wherever it points -- outside `binaries/`, possibly outside the repo. Create-only still holds
# either way (no existing file is touched), but the intent is "skip anything already spoken
# for", not just "skip anything `-e` can see" (Sana, PR #29 F1).
#
# Quiet on the common case (a machine that already has real files staged, or ran this before):
# prints only when it actually creates a placeholder, so this adds no noise to every
# `make ci`/`check`/`clippy`/`operator`/`build-operator` invocation.
#
# Fails LOUD if rustc is missing or unusable, matching `stt-preflight`/`ndi-preflight`'s
# `command -v X || { echo ERROR; exit 1; }` style rather than silently staging a garbage
# `selahcue-output-` (empty triple) and reporting success anyway (Cody, PR #29 High: without
# this, `make stage-operator-binaries` exited 0 with a misleading "staged" message, and the
# real cause only surfaced later as cargo's confusing `resource path ... doesn't exist`).
#
# `ci` deliberately does NOT list this target as a prerequisite -- a same-level prerequisite
# resolves before `ci`'s own recipe body runs, which would put this check AHEAD of
# `sh scripts/check_toolchain.sh`, the one script whose own header says it must run "BEFORE
# running any gate" (86ak5rc9c's nine-day-red-main lesson) and gives the fuller diagnostic for
# a broken rustc (mismatched pin, missing component, etc.). So `ci` calls this target
# explicitly, as a recipe line, AFTER that check -- see `ci:` below. Every other prerequisite
# of this target (`check`/`clippy`/`operator`/`build-operator`/`test-stt-real-model`) has no
# such ordering conflict, since none of them run `check_toolchain.sh` themselves.
stage-operator-binaries: ## (internal) create-only placeholders for the operator's gitignored sidecar/NDI dll, so a fresh worktree can compile it (86akc2kmh)
	@command -v rustc >/dev/null 2>&1 || { \
	  echo "ERROR: rustc is not on PATH -- needed to resolve the platform triple for"; \
	  echo "  selahcue-operator's gitignored sidecar/NDI placeholders. Install the pinned"; \
	  echo "  toolchain via rustup (see rust-toolchain.toml), or run 'make ci', whose own"; \
	  echo "  toolchain check gives the fuller diagnostic if rustc is present but misconfigured."; \
	  exit 1; }
	@triple="$$(rustc -vV 2>/dev/null | sed -n 's/^host: //p')"; \
	[ -n "$$triple" ] || { echo "ERROR: 'rustc -vV' produced no 'host:' line -- cannot resolve the platform triple for selahcue-operator's sidecar placeholder. Run 'rustc -vV' directly to see its actual output."; exit 1; }; \
	dir="$(OPERATOR)/binaries"; \
	mkdir -p "$$dir"; \
	case "$$triple" in \
	  *windows*) bin="$$dir/selahcue-output-$${triple}.exe" ;; \
	  *) bin="$$dir/selahcue-output-$${triple}" ;; \
	esac; \
	ndi="$$dir/Processing.NDI.Lib.x64.dll"; \
	staged=""; \
	for f in "$$bin" "$$ndi"; do \
	  [ -e "$$f" ] || [ -h "$$f" ] || { : > "$$f"; staged="$$staged $$(basename "$$f")"; }; \
	done; \
	if [ -n "$$staged" ]; then echo ">> staged selahcue-operator compile-check placeholder(s) (gitignored, create-only, safe to delete):$$staged"; fi

# Regression-tests the create-only guarantee `stage-operator-binaries` promises (86akc2kmh's own
# acceptance criterion: "write it as a real check, not an eyeball" -- Quinn, PR #29 QA review).
# Runs the EXACT shipped recipe (never a duplicate copy that could drift) against two disposable
# temp directories via OPERATOR=, so nothing here can ever put a real dll at risk:
#
#   (A) a REAL existing file at the NDI slot must survive byte-for-byte, and the sidecar slot
#       (genuinely missing) must still get created -- the base create-only property plus "it
#       still does its job" on the happy path.
#   (B) a DANGLING symlink at the NDI slot (Sana's PR #29 F1) must be left alone -- nothing is
#       created at the link's target and the link itself is not replaced -- while the sidecar
#       slot still gets created normally alongside it. Kept in its own temp dir and its own
#       assertions so a regression in (A) or (B) fails on its own signal rather than being
#       masked by the other slot succeeding.
#
# Mutation-verified by hand before this comment was written: dropping `stage-operator-binaries`'s
# `[ -e "$$f" ] ||` turns scenario (A)'s hash into the well-known empty-file SHA-256
# (e3b0c442...) and this target catches it immediately; dropping the `[ -h "$$f" ] ||` half
# makes scenario (B) create a file at the dangling link's target and this target catches that
# too. Both were restored after confirming the RED.
verify-stage-operator-binaries-create-only: ## (internal) regression-test stage-operator-binaries' create-only guarantee, incl. the dangling-symlink guard (86akc2kmh)
	@tmp="$$(mktemp -d)"; trap 'rm -rf "$$tmp"' EXIT; \
	mkdir -p "$$tmp/binaries"; \
	printf 'KNOWN-PAYLOAD-DO-NOT-TRUNCATE-%s' "$$$$" > "$$tmp/binaries/Processing.NDI.Lib.x64.dll"; \
	before="$$(shasum -a 256 "$$tmp/binaries/Processing.NDI.Lib.x64.dll" | awk '{print $$1}')"; \
	$(MAKE_RECURSE) --no-print-directory stage-operator-binaries OPERATOR="$$tmp" >/dev/null; \
	after="$$(shasum -a 256 "$$tmp/binaries/Processing.NDI.Lib.x64.dll" | awk '{print $$1}')"; \
	[ "$$before" = "$$after" ] || { echo "FAIL(A): stage-operator-binaries truncated an existing file"; exit 1; }; \
	sidecar="$$(find "$$tmp/binaries" -name 'selahcue-output-*' 2>/dev/null | head -1)"; \
	[ -n "$$sidecar" ] && [ -e "$$sidecar" ] || { echo "FAIL(A): sidecar placeholder was not created for a genuinely-missing file"; exit 1; }; \
	echo ">> (A) create-only + real-creation property verified"; \
	tmp2="$$(mktemp -d)"; trap 'rm -rf "$$tmp" "$$tmp2"' EXIT; \
	mkdir -p "$$tmp2/binaries"; \
	dangle_target="$$tmp2/outside-the-binaries-dir.dll"; \
	ln -s "$$dangle_target" "$$tmp2/binaries/Processing.NDI.Lib.x64.dll"; \
	$(MAKE_RECURSE) --no-print-directory stage-operator-binaries OPERATOR="$$tmp2" >/dev/null; \
	[ ! -e "$$dangle_target" ] || { echo "FAIL(B): a dangling symlink's target got created (Sana PR #29 F1 regressed)"; exit 1; }; \
	[ -h "$$tmp2/binaries/Processing.NDI.Lib.x64.dll" ] || { echo "FAIL(B): the dangling symlink itself was replaced"; exit 1; }; \
	sidecar2="$$(find "$$tmp2/binaries" -name 'selahcue-output-*' 2>/dev/null | head -1)"; \
	[ -n "$$sidecar2" ] && [ -e "$$sidecar2" ] || { echo "FAIL(B): sidecar placeholder was not created alongside the skipped dangling symlink"; exit 1; }; \
	echo ">> (B) dangling-symlink guard verified"; \
	echo ">> stage-operator-binaries create-only property fully verified"

stt-preflight: ## (internal) verify the toolchain needed for --features stt/cloud-stt is present
ifneq ($(filter stt cloud-stt,$(OP_FEATURES_WORDS)),)
	@command -v cmake >/dev/null 2>&1 || { \
	  echo "ERROR: $(strip $(filter stt cloud-stt,$(OP_FEATURES_WORDS))) (full set: $(OP_FEATURES)) needs cmake + a C/C++ toolchain to build whisper.cpp -- cloud-stt implies stt, so it needs the same toolchain (mic capture lives in selahcue-stt regardless of which recognizer consumes it)."; \
	  echo "  macOS:         brew install cmake"; \
	  echo "  Debian/Ubuntu: sudo apt-get install -y cmake build-essential"; \
	  echo "  Or run without live transcription:  make $(MAKECMDGOALS) STT=0"; \
	  exit 1; }
endif

# (internal) THE STRUCTURAL HALF of the RELEASE=1 guarantee described in the "AI-assisted sermon
# notes" comment above. That comment's point 1 only clears the AUTO-COMPUTED AI_FEATURES when
# RELEASE=1 — it says nothing about a developer who bypasses the auto-detection entirely with
# `OP_FEATURES=dev-keys,openai-notes` directly, which skips AI_FEATURES/AI= altogether (OP_FEATURES
# is a `?=`, so a command-line value for it wins over everything computed above). Checking the
# FINAL, resolved feature list — however it was populated — rather than the auto-detection inputs
# is what makes this a guard on the outcome instead of a guard on one path to it. This still only
# covers "through make"; see dev_env.rs's debug_assertions check for the bare-`cargo build` case
# this cannot see.
#
# DO NOT VERIFY THIS GUARD WITH `make -n` ALONE (Quinn) — a dry run prints every recipe LINE
# unconditionally, including the `exit 1` inside this guard's shell block and the cargo build
# line that follows it in the file, because `-n` never actually evaluates the shell conditional
# that would stop it. That makes `make -n build-operator RELEASE=1 OP_FEATURES=stt,cloud-stt`
# LOOK like the guard's error is printed and then a cargo build still happens — it does not. The
# real invocation (`make build-operator RELEASE=1 OP_FEATURES=stt,cloud-stt`) exits 2 at this
# guard's own `exit 1` and never reaches the cargo line at all; verified by running both and
# diffing what each actually does, not by reading the dry run.
release-ai-guard: ## (internal) refuse any --release build of selahcue-operator carrying a RELEASE_UNSAFE_FEATURES token
ifeq ($(filter 1,$(RELEASE)),1)
ifneq ($(strip $(filter $(RELEASE_UNSAFE_FEATURES),$(OP_FEATURES_WORDS))),)
	@echo "ERROR: refusing to build selahcue-operator --release with $(strip $(filter $(RELEASE_UNSAFE_FEATURES),$(OP_FEATURES_WORDS)))."; \
	  echo "  A RELEASE=1 (or --release) build of the operator must never carry: $(RELEASE_UNSAFE_FEATURES)"; \
	  echo "  -- the repo-root .env developer-key loader, a direct-to-OpenAI path, or the"; \
	  echo "  developer-key Deepgram path. See this Makefile's RELEASE_UNSAFE_FEATURES comment,"; \
	  echo "  the \"AI-assisted sermon notes\" comment, and selahcue-operator/src/dev_env.rs for why."; \
	  echo "  You passed: OP_FEATURES=$(OP_FEATURES) RELEASE=$(RELEASE)"; \
	  echo "  Drop RELEASE=1, or remove $(RELEASE_UNSAFE_FEATURES) from OP_FEATURES."; \
	  exit 1
endif
endif

help: ## Show this help
	@echo "SelahCue — make targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# LAUNCH ORCHESTRATION. `make run` used to be a race, and lost it on any cold/changed cache:
#
#   * its prerequisite built the workspace with the DEFAULT feature set while the recipe then ran
#     `-p selahcue-desktop $(DESKTOP_FEATURES)` — a different cargo cache entry, so the real
#     compile (grafton-ndi, relinking the output window) happened INSIDE the backgrounded job,
#     silenced by `-q` and with nobody checking its exit status; and
#   * the recipe then waited a flat 10 seconds for the endpoint file and started the operator
#     regardless of whether it ever appeared.
#
# That mattered more than a slow start: the operator resolves its backend exactly ONCE, at
# startup. If the endpoint file is missing at that instant it falls back to the built-in demo
# plan permanently — no retry, no reconnect — so the operator would come up looking fine while
# being wired to nothing, and the real plan never appeared even after the output window did.
#
# So: build EXACTLY what we are about to run (same crate, same features, same profile) so the
# backgrounded `cargo run` is a cache hit; then wait on the real CONDITION (the endpoint file
# exists and is complete) while the output process is still alive, instead of on a stopwatch.
#
# The backstop below is only a last resort for a wedged process — a slow-but-healthy start must
# never lose the race, so raise it rather than reduce it: `make run LAUNCH_TIMEOUT=600`.
LAUNCH_TIMEOUT ?= 180

launch: stt-preflight release-ai-guard build-output build-operator ## Launch EVERYTHING — output window (NDI auto) + operator shell (STT + AI on; AI=0/STT=0 to skip)
	@echo ">> build profile: $(PROFILE_NAME)$(if $(filter 1,$(RELEASE)),, — use \`make run-release\` to judge performance)"
	@echo ">> NDI output: $(NDI_STATUS)"
	@echo ">> live transcript (STT): $(STT_STATUS)"
	@echo ">> AI-assisted sermon notes: $(AI_STATUS)"
	@echo ">> clearing any stale endpoint and starting the output window…"
	@rm -f "$(ENDPOINT)"; \
	$(DESKTOP_ENV) $(CARGO) run $(WS) -p selahcue-desktop $(DESKTOP_FEATURES) $(PROFILE_FLAG) & \
	OUT_PID=$$!; \
	trap 'kill $$OUT_PID 2>/dev/null' EXIT INT TERM; \
	echo ">> waiting for the output window to advertise its endpoint…"; \
	TICKS=0; LIMIT=$$(( $(LAUNCH_TIMEOUT) * 4 )); \
	while :; do \
	  [ -s "$(ENDPOINT)" ] && grep -q '}' "$(ENDPOINT)" 2>/dev/null && break; \
	  OUT_STATE=$$(ps -o state= -p $$OUT_PID 2>/dev/null || true); \
	  case "$$OUT_STATE" in \
	    ''|Z*) \
	      wait $$OUT_PID 2>/dev/null; STATUS=$$?; \
	      echo ""; \
	      echo "ERROR: the output window exited (status $$STATUS) before advertising its endpoint."; \
	      echo "  Its cargo output is above — that is the real failure; fix it and re-run."; \
	      echo "  Not starting the operator: it resolves its backend ONCE at startup, so it would"; \
	      echo "  silently fall back to the built-in demo plan for the whole session."; \
	      exit 1;; \
	  esac; \
	  if [ $$TICKS -ge $$LIMIT ]; then \
	    echo ""; \
	    echo "ERROR: the output window is alive but has not advertised its endpoint in $(LAUNCH_TIMEOUT)s."; \
	    echo "  Stopping it rather than starting an operator that would be stuck on the demo plan."; \
	    echo "  If this machine is simply slow:  make run LAUNCH_TIMEOUT=600"; \
	    echo "  To see what it is doing, run the two halves separately:  make output  /  make operator"; \
	    exit 1; \
	  fi; \
	  sleep 0.25; TICKS=$$((TICKS + 1)); \
	done; \
	echo ">> endpoint is up; starting the operator shell (its buttons drive the output window)…"; \
	$(OPERATOR_RUN); \
	echo ">> operator closed; stopping the output window."; \
	kill $$OUT_PID 2>/dev/null || true; \
	wait $$OUT_PID 2>/dev/null || true

run: launch ## Run EVERYTHING with one command (alias for `launch` — output window + operator, NDI auto)

run-release: ## Run EVERYTHING as an OPTIMIZED release build — use this to judge real performance
	@$(MAKE) --no-print-directory launch RELEASE=1

launch-release: run-release ## Alias for `run-release` (optimized output window + operator)

output-release: ## Run only the output window as an optimized release build
	@$(MAKE) --no-print-directory output RELEASE=1

output: ## Run only the output window (native audience output + LAN control server; NDI auto)
	$(DESKTOP_ENV) $(CARGO) run $(WS) -p selahcue-desktop $(DESKTOP_FEATURES) $(PROFILE_FLAG)

ndi-preflight: ## (internal) verify the repo-vendored NDI SDK is populated for this OS
	@test -f "$(NDI_DIR)/include/Processing.NDI.Lib.h" || { \
	  echo "ERROR: the NDI SDK is not vendored at $(NDI_DIR)."; \
	  echo "  Install/unzip the NDI SDK (https://ndi.video/), then vendor it into the repo:"; \
	  echo "      scripts/fetch_ndi_sdk.sh            # or pass the SDK path as an argument"; \
	  echo "  Details: implementation/desktop/vendor/ndi/README.md"; \
	  exit 1; }

output-ndi: ndi-preflight ## Force the output window WITH NDI (errors if the SDK isn't vendored; `make run` enables NDI automatically)
	NDI_SDK_DIR="$(NDI_DIR)" $(NDI_LOADER) $(CARGO) run $(WS) -p selahcue-desktop --features ndi $(PROFILE_FLAG)

operator: stt-preflight release-ai-guard stage-operator-binaries ## Run only the operator shell (connects to a running output window, else a standalone demo)
	@echo ">> live transcript (STT): $(STT_STATUS)"
	@echo ">> AI-assisted sermon notes: $(AI_STATUS)"
	$(OPERATOR_RUN)

operator-headless: ## Run the committed operator-webview behavioural check (headless Chrome; skips if Chrome absent)
	python3 scripts/operator_headless.py

remote: ## Send one command to a running output window (e.g. make remote CMD=go-live, or CMD=timer SECS=300)
	@test -n "$(ENDPOINT)" && test -f "$(ENDPOINT)" || \
	  { echo "No endpoint file at '$(ENDPOINT)'. Start the output window first: make output"; exit 1; }
	@python3 -c "import json;d=json.load(open('$(ENDPOINT)'));print(d['addr'],d['pin'],d['device'],d['token'])" | \
	  while read A P D T; do \
	    $(CARGO) run -q $(WS) -p selahcue-lan --example remote --features server -- $$A $$P $$D $$T $(CMD) $(SECS); \
	  done

timer: ## Start a countdown on a running output window (make timer SECS=300)
	@$(MAKE) --no-print-directory remote CMD=timer SECS=$(or $(SECS),300)

stop-timer: ## Stop the countdown on a running output window
	@$(MAKE) --no-print-directory remote CMD=stop-timer

demo: ## Run the headless LAN foundation demo
	$(CARGO) run $(WS) -p selahcue-lan --example demo --features server

MOBILE  := implementation/mobile/selahcue_controller
FLUTTER ?= flutter

mobile: ## Run the Flutter controller on this Mac (pair it with a running `make output` via P)
	cd $(MOBILE) && $(FLUTTER) run

mobile-test: ## Analyze + unit-test the Flutter controller
	cd $(MOBILE) && $(FLUTTER) analyze && $(FLUTTER) test

# Mirrors the Rust/Flutter gates in .github/workflows/ci.yml. It does NOT cover
# everything CI runs -- see the "Not covered here" list below and in CLAUDE.md.
#
# The FIRST line is load-bearing: it asserts the running toolchain is the one
# rust-toolchain.toml pins, which is the same assertion CI makes. Without it this
# target could pass on one compiler while CI failed on another -- which is exactly
# how `main` went nine days without a green run while this printed ALL GREEN (86ak5rc9c).
#
# Not covered here (CI-only): cargo audit / cargo deny (supply chain), the
# Playwright WebKit engine smoke, launch-smoke + `make nfr`, the Android APK
# compile-check, and the `api (django)` and `marketing (vue spa)` jobs entirely.
# Run those areas' own tooling before pushing changes to them.
#
# One masking difference from CI, deliberate and not yet closed: CI now runs the
# steps after Clippy under `if: !cancelled()`, so one failing gate no longer hides
# the rest. Make still aborts the target at the first failing recipe line, so a
# clippy failure here still stops you seeing the test results. The test commands
# below carry --no-fail-fast (measured: it surfaces a second failing test binary
# that would otherwise be hidden), but line-level aborts remain. Tracked on
# 86ak5rjh7 -- fixing it means restructuring this target, which is not a change to
# smuggle into a toolchain fix.
ci: ## Run the local Rust/Flutter CI gate (see the header for what CI runs that this does not)
	sh scripts/check_toolchain.sh
	# Stage the operator's gitignored sidecar/NDI placeholders (86akc2kmh) as an explicit recipe
	# line, deliberately AFTER the toolchain check above and NOT as a same-level prerequisite of
	# `ci` -- a prerequisite would resolve before this recipe body starts, putting a plain
	# "rustc not found" message ahead of check_toolchain.sh's richer, purpose-built diagnostic
	# (Cody, PR #29 High). Reuses the exact target other callers use, via recursive make, so
	# there is exactly one definition of the staging logic.
	$(MAKE_RECURSE) --no-print-directory stage-operator-binaries
	$(MAKE_RECURSE) --no-print-directory verify-stage-operator-binaries-create-only
	# Quinn's process finding on PR #24 (86akcmzyq): the PR template's feature-flag-reachability
	# section is three checkboxes a human ticks, unenforced by CI -- exactly the human step that
	# let 86akby7d8 ship, merge, and stay invisible from `make launch` in the first place. This
	# makes it a build failure instead: asserts `make -n launch`/`make -n operator`'s resolved
	# feature list is a superset of the features the product has decided must be default-
	# reachable (currently dev-keys/openai-notes, 86akcmzrd). Self-test first (fixture-driven,
	# no `make`/cargo dependency) so the comparison LOGIC itself is covered before trusting it
	# against the real Makefile.
	python3 scripts/check_launch_reachability.py --self-test
	python3 scripts/check_launch_reachability.py
	cd $(DESKTOP) && $(CARGO) fmt --check
	cd $(OPERATOR) && $(CARGO) fmt --check
	$(CARGO) clippy $(WS) --workspace --all-targets -- -D warnings
	$(CARGO) clippy $(WS) -p selahcue-lan --features server --all-targets -- -D warnings
	$(CARGO) clippy $(WS) -p selahcue-app --features server --all-targets -- -D warnings
	$(CARGO) clippy $(WS) -p selahcue-scripture --features download --all-targets -- -D warnings
	$(CARGO) clippy $(WS) -p selahcue-cloud --features openai --all-targets -- -D warnings
	$(CARGO) clippy $(WS) -p selahcue-stt-cloud --features deepgram --all-targets -- -D warnings
	$(CARGO) clippy $(OP) --all-targets -- -D warnings
	# The operator's `openai-notes` feature gates the provider construction and the four-state
	# status derivation. Without this line NOTHING compiles it -- which is exactly the
	# selahcue-stt problem this PR cites as its own justification for the cloud-side line above.
	$(CARGO) clippy $(OP) --features openai-notes --all-targets -- -D warnings
	$(CARGO) test $(WS) --workspace --no-fail-fast
	sh scripts/import_guards.sh
	$(CARGO) test $(WS) -p selahcue-licensing --release --no-fail-fast
	$(CARGO) clippy $(WS) -p selahcue-licensing --release --all-targets -- -D warnings
	sh scripts/dev_key_not_in_release.sh
	$(CARGO) test $(WS) -p selahcue-lan --features server --no-fail-fast
	$(CARGO) test $(WS) -p selahcue-app --features server --no-fail-fast
	$(CARGO) test $(WS) -p selahcue-data --features encryption --no-fail-fast
	$(CARGO) test $(WS) -p selahcue-desktop --features encryption --no-fail-fast
	$(CARGO) test $(WS) -p selahcue-scripture --features download --no-fail-fast
	# The OpenAI note provider (86akby7d8) is behind an off-by-default feature, so the default
	# workspace run above does NOT cover it. Lint + test it explicitly: an off-by-default feature
	# that no gate ever compiles is exactly how selahcue-stt ended up linted by nothing.
	$(CARGO) test $(WS) -p selahcue-cloud --features openai --no-fail-fast
	# THE release-profile half of the boundary named in Cody's High finding on PR #24
	# (86akcmzyq): `OpenAiNoteProvider::from_env` reads OPENAI_API_KEY with no profile check at
	# all until `direct_key_permitted` (openai.rs) was added -- a bare `cargo build --release
	# --features openai-notes`, with no `dev-keys` and bypassing `make` entirely, built a working
	# direct-to-OpenAI release binary from whatever key happened to already be exported. Debug
	# above does not exercise the release arm of `direct_key_permitted`/`from_env`'s `iff` tests;
	# this is the licensing-crate pattern (`test -p selahcue-licensing --release`) applied here.
	$(CARGO) test $(WS) -p selahcue-cloud --features openai --release --no-fail-fast
	$(CARGO) clippy $(WS) -p selahcue-cloud --features openai --release --all-targets -- -D warnings
	# The Deepgram streaming transport (86akby4yz) is behind an off-by-default feature, so the
	# workspace run above does NOT build it. Lint + test it explicitly: an off-by-default feature
	# that no gate ever compiles is exactly how selahcue-stt ended up linted by nothing. The
	# suite here talks to a local stub socket on loopback, never to the live Deepgram service.
	$(CARGO) test $(WS) -p selahcue-stt-cloud --features deepgram --no-fail-fast
	# THE release-profile half of the boundary named in Sana S-1 / Cody Finding A / Quinn High on
	# the `cloud-stt` reachability PR (86akd10dq): `developer_credential_from_env` read
	# DEEPGRAM_API_KEY with no profile check at all until `developer_key_permitted`
	# (credential.rs) was added -- a bare `cargo build --release --features deepgram` (or, after
	# this PR made cloud-stt reachable by default, plain `make launch RELEASE=1`/`make
	# run-release`) built a working direct-to-Deepgram release binary from whatever key happened
	# to already be exported. Debug above does not exercise the release arm of
	# `developer_key_permitted`/`developer_credential_from_env`'s `iff` test; this is the exact
	# `selahcue-cloud --features openai --release` pattern a few lines above, applied here -- this
	# line is the actual remediation for HOW the gap was missed, not a nice-to-have alongside it.
	$(CARGO) test $(WS) -p selahcue-stt-cloud --features deepgram --release --no-fail-fast
	$(CARGO) clippy $(WS) -p selahcue-stt-cloud --features deepgram --release --all-targets -- -D warnings
	$(CARGO) check $(OP)
	$(CARGO) test $(OP) --no-fail-fast
	$(CARGO) test $(OP) --features dev-keys --no-fail-fast
	$(CARGO) test $(OP) --features openai-notes --no-fail-fast
	# `dev-keys` (86akby6yy) supplies a developer key from `.env`; `openai-notes` (86akby7d8)
	# consumes it to build the real OpenAI provider and derive the four-state Providers &
	# Privacy status. The two lines above compile and test each feature ALONE -- neither
	# builds them together, so the combination is exactly as unlinted as selahcue-stt until
	# this line: it is also the one build where this PR's shared `ENV_LOCK` has two
	# independently-authored env-mutating test modules (dev_env's and the model-override
	# tests') actually running in the same process, which is the race the lock exists to
	# prevent. A developer running it by hand and getting green (97/97) is not a gate --
	# nothing catches a regression here without a line that runs on every push.
	$(CARGO) clippy $(OP) --features dev-keys,openai-notes --all-targets -- -D warnings
	$(CARGO) test $(OP) --features dev-keys,openai-notes --no-fail-fast
	# THE release-profile gate on the operator crate itself (Sana's Medium-Low finding on PR #24,
	# 86akcmzyq): every operator test above runs in DEBUG only, so `dev_env.rs`'s
	# `loads_the_env_file_iff_this_is_a_debug_build` and main.rs's
	# `the_environment_reaches_the_view_not_only_the_request` never exercised their RELEASE arm
	# in any gate -- a hardcoded argument, an inverted `!`, or a deleted early return in either
	# guard's call site passed every automated check green. Same shape as the licensing crate's
	# `test -p selahcue-licensing --release` pair above; `selahcue-operator` is excluded from the
	# workspace so it needs its own explicit lines.
	$(CARGO) test $(OP) --features dev-keys,openai-notes --release --no-fail-fast
	$(CARGO) clippy $(OP) --features dev-keys,openai-notes --release --all-targets -- -D warnings
	# Cloud (Deepgram) live transcription (86akby7th): the operator's `cloud-stt` feature wires
	# the already-tested `selahcue-stt-cloud` streaming session into `listening.rs`'s capture
	# path. `cloud-stt` implies `stt` (mic capture lives in `selahcue-stt` regardless of which
	# recognizer consumes it), so this line is the FIRST place `stt` itself -- and therefore all
	# of `listening.rs` -- is compiled and linted under `-D warnings` in this gate at all: `stt`
	# alone was never turned on above (`check`/`clippy $(OP)` are bare, `stt-preflight` guards
	# only the interactive `operator`/`launch` targets). Without this line, `listening.rs` --
	# where the routing decision this ticket exists to fix actually lives -- would be exactly as
	# unlinted as `selahcue-stt` itself. Needs the whisper/cpal native toolchain (`stt-preflight`
	# checks for it locally; GitHub-hosted runners carry cmake by default).
	$(CARGO) clippy $(OP) --features stt,cloud-stt --all-targets -- -D warnings
	$(CARGO) test $(OP) --features stt,cloud-stt --no-fail-fast
	# The real-model on-device STT integration test (86akd1jcc, Vera Q4) is `#[ignore]`d, so the
	# line above never runs it -- it needs a real ~1.6GB whisper model, which the default debug
	# profile hashes at ~18-19x release speed (SHA-256 over 1.6GB: ~63s debug / ~3s release,
	# measured directly -- a build-profile fact, not machine contention, despite three reviewers
	# and this ticket's own earlier comments attributing it to load). Run it explicitly, in
	# release, here: real integration coverage for ~3s instead of an ignored test nobody
	# remembers to run, or an unignored one silently taxing every debug `make ci`.
	#
	# On a machine without the model cached: this line still reports `test result: ok. 1
	# passed`, in well under a second -- NOT a skip, NOT `0 passed`. The test's own early
	# `return` (see its doc comment) is not a no-op in the sense `cargo test`'s summary can
	# show; the harness has no concept of a runtime-decided skip without `#[ignore]`, so a test
	# that returns early without panicking is indistinguishable, in that summary line, from one
	# that actually verified something (Cody, 86akd1jcc round 4, caught an earlier version of
	# this exact comment claiming `0 passed; 0 filtered`, which is not real `cargo test` output
	# at all -- forced the branch and got `1 passed`, confirmed independently before this fix).
	# This is precisely the fact that made this whole ticket's CI-vacuity finding possible in
	# the first place, so getting the wording right here is not cosmetic.
	$(CARGO) test $(OP) --release --features stt -- --ignored a_real_cold_start_backlog_no_longer_trips_the_notice
	python3 scripts/operator_headless.py
	cd $(MOBILE) && $(FLUTTER) analyze && $(FLUTTER) test
	@echo ""
	@echo "== local Rust/Flutter gate: ALL GREEN (see the ci: header for CI-only gates) =="

nfr: ## Measure the walking-skeleton NFRs (idle memory / cold start) on a release build
	sh scripts/measure_nfr.sh

build: ## Build the desktop workspace
	$(CARGO) build $(WS) $(PROFILE_FLAG)

# Build the output window the way `make launch` RUNS it. This exists so the two cannot drift:
# the launch recipe backgrounds `cargo run` with $(DESKTOP_FEATURES) and $(PROFILE_FLAG), and a
# prerequisite that builds anything else (the plain workspace build, say, which has no `ndi`)
# is a different cargo cache entry — it leaves the real compile to happen inside the background
# job, where a failure is easy to miss and a long link looks like a hung start. Same crate, same
# features, same profile, same env (grafton-ndi's build script needs NDI_SDK_DIR) — so by the
# time we background it, `cargo run` has nothing left to do but launch.
# `make ci`/`check`/`clippy` deliberately do NOT use this: they stay on the default, native-free
# build so CI never needs the NDI SDK.
build-output: ## Build just the output window with the same features/profile `make run` uses
	$(DESKTOP_ENV) $(CARGO) build $(WS) -p selahcue-desktop $(DESKTOP_FEATURES) $(PROFILE_FLAG)

build-operator: stt-preflight release-ai-guard stage-operator-binaries ## Build the Tauri operator shell crate
	$(CARGO) build $(OP) $(OPRUN) $(PROFILE_FLAG)

test: ## Run the workspace test suite
	$(CARGO) test $(WS)

test-stt-real-model: stage-operator-binaries ## Run the `#[ignore]`d real-model on-device STT integration test (release, ~3s)
	$(CARGO) test $(OP) --release --features stt -- --ignored a_real_cold_start_backlog_no_longer_trips_the_notice

check: stage-operator-binaries ## Type-check the workspace + the operator shell
	$(CARGO) check $(WS)
# A workspace build unifies features across members, so a crate that is missing a `cfg` on
# something feature-gated still compiles here and only fails when someone builds it alone.
# That is how an ungated `RemoteOperator` holding a `server`-only `ControlClient` survived.
# `-p` narrows unification to the one package, which is the resolution a bare build gets.
	$(CARGO) check $(WS) -p selahcue-app --all-targets
	$(CARGO) check $(OP)

clippy: stage-operator-binaries ## Lint the workspace + the operator shell
	$(CARGO) clippy $(WS) --all-targets
	$(CARGO) clippy $(OP)

fmt: ## Format all code
	cd $(DESKTOP) && $(CARGO) fmt
	cd $(OPERATOR) && $(CARGO) fmt

clean: ## Remove build artifacts
	$(CARGO) clean $(WS)
	$(CARGO) clean $(OP)
