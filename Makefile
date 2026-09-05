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
# STT_STATUS/AI_STATUS (below OP_FEATURES_WORDS further down) are derived from the FINAL, resolved
# feature list rather than from STT_FEATURES/AI_FEATURES directly, so the messages stay honest even
# when a developer bypasses this auto-detection entirely with `OP_FEATURES=<features>` — see the
# OP_FEATURES_WORDS comment for why that distinction matters.
STT ?= auto
ifeq ($(STT),0)
STT_FEATURES :=
else ifeq ($(STT),1)
STT_FEATURES := stt
else
STT_FEATURES := $(if $(shell command -v cmake 2>/dev/null),stt,)
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
# not a substring: `cloud-stt` (86akby7th, in review) contains "stt" as a substring but needs no
# whisper.cpp/cmake toolchain at all.
OP_FEATURES_WORDS := $(subst $(COMMA),$(SPACE),$(OP_FEATURES))
ifneq ($(filter stt,$(OP_FEATURES_WORDS)),)
STT_STATUS := on (stt)
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
.PHONY: help launch run run-release launch-release output-release output output-ndi ndi-preflight operator operator-headless stt-preflight release-ai-guard remote timer stop-timer demo mobile mobile-test ci nfr build build-output build-operator test check clippy fmt clean

stt-preflight: ## (internal) verify the toolchain needed for --features stt is present
ifneq ($(filter stt,$(OP_FEATURES_WORDS)),)
	@command -v cmake >/dev/null 2>&1 || { \
	  echo "ERROR: on-device STT (--features stt, full set: $(OP_FEATURES)) needs cmake + a C/C++ toolchain to build whisper.cpp."; \
	  echo "  macOS:         brew install cmake"; \
	  echo "  Debian/Ubuntu: sudo apt-get install -y cmake build-essential"; \
	  echo "  Or run without on-device STT:  make $(MAKECMDGOALS) STT=0"; \
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
release-ai-guard: ## (internal) refuse any --release build of selahcue-operator that carries dev-keys/openai-notes
ifeq ($(filter 1,$(RELEASE)),1)
ifneq ($(strip $(filter dev-keys openai-notes,$(OP_FEATURES_WORDS))),)
	@echo "ERROR: refusing to build selahcue-operator --release with $(strip $(filter dev-keys openai-notes,$(OP_FEATURES_WORDS)))."; \
	  echo "  A RELEASE=1 (or --release) build of the operator must never carry the repo-root"; \
	  echo "  .env developer-key loader or a direct-to-OpenAI path — see this Makefile's"; \
	  echo "  \"AI-assisted sermon notes\" comment and selahcue-operator/src/dev_env.rs for why."; \
	  echo "  You passed: OP_FEATURES=$(OP_FEATURES) RELEASE=$(RELEASE)"; \
	  echo "  Drop RELEASE=1, or remove dev-keys/openai-notes from OP_FEATURES."; \
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
	@echo ">> on-device STT: $(STT_STATUS)"
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

operator: stt-preflight release-ai-guard ## Run only the operator shell (connects to a running output window, else a standalone demo)
	@echo ">> on-device STT: $(STT_STATUS)"
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
	# The Deepgram streaming transport (86akby4yz) is behind an off-by-default feature, so the
	# workspace run above does NOT build it. Lint + test it explicitly: an off-by-default feature
	# that no gate ever compiles is exactly how selahcue-stt ended up linted by nothing. The
	# suite here talks to a local stub socket on loopback, never to the live Deepgram service.
	$(CARGO) test $(WS) -p selahcue-stt-cloud --features deepgram --no-fail-fast
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

build-operator: stt-preflight release-ai-guard ## Build the Tauri operator shell crate
	$(CARGO) build $(OP) $(OPRUN) $(PROFILE_FLAG)

test: ## Run the workspace test suite
	$(CARGO) test $(WS)

check: ## Type-check the workspace + the operator shell
	$(CARGO) check $(WS)
# A workspace build unifies features across members, so a crate that is missing a `cfg` on
# something feature-gated still compiles here and only fails when someone builds it alone.
# That is how an ungated `RemoteOperator` holding a `server`-only `ControlClient` survived.
# `-p` narrows unification to the one package, which is the resolution a bare build gets.
	$(CARGO) check $(WS) -p selahcue-app --all-targets
	$(CARGO) check $(OP)

clippy: ## Lint the workspace + the operator shell
	$(CARGO) clippy $(WS) --all-targets
	$(CARGO) clippy $(OP)

fmt: ## Format all code
	cd $(DESKTOP) && $(CARGO) fmt
	cd $(OPERATOR) && $(CARGO) fmt

clean: ## Remove build artifacts
	$(CARGO) clean $(WS)
	$(CARGO) clean $(OP)
