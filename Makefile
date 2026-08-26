# SelahCue — developer launch / build Makefile
#
# The Rust workspace lives in implementation/desktop; the Tauri operator shell is a
# standalone (workspace-excluded) crate under it. These targets wrap the cargo commands
# so you can launch and drive the app without remembering the paths and feature flags.
#
#   make            # show this help
#   make run        # ONE command: output window + operator shell together (NDI + STT auto-on)
#   make launch     # same as `make run`
#   make run-release# same, but an OPTIMIZED build — use this to judge performance
#   make output     # just the audience output window (native + LAN control server; NDI auto)
#   make operator   # just the Tauri operator shell
#   make remote CMD=go-live   # send one command to a running output window via the CLI
#
# `make run` auto-enables NDI when the SDK is vendored (scripts/fetch_ndi_sdk.sh) and STT when
# cmake is present, and runs fine without either — force with `make run NDI=1|0 STT=1|0`.
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
# it with STT=1 (errors if cmake is absent) or disable with STT=0; OP_FEATURES=<features> still
# overrides the operator build directly. CI/check/clippy always use the default (no-STT) operator
# build, so this never affects them.
STT ?= auto
ifeq ($(STT),0)
OP_FEATURES ?=
else ifeq ($(STT),1)
OP_FEATURES ?= stt
else
OP_FEATURES ?= $(if $(shell command -v cmake 2>/dev/null),stt,)
endif
OPRUN       := $(if $(strip $(OP_FEATURES)),--features $(strip $(OP_FEATURES)),)
ifeq ($(strip $(OP_FEATURES)),)
STT_STATUS  := off (run with STT=1, or `brew install cmake`, to enable the live transcript)
else
STT_STATUS  := on ($(strip $(OP_FEATURES)))
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
.PHONY: help launch run run-release launch-release output-release output output-ndi ndi-preflight operator operator-headless stt-preflight remote timer stop-timer demo mobile mobile-test ci nfr build build-output build-operator test check clippy fmt clean

stt-preflight: ## (internal) verify the toolchain needed for --features stt is present
ifneq ($(strip $(OP_FEATURES)),)
	@command -v cmake >/dev/null 2>&1 || { \
	  echo "ERROR: on-device STT (--features $(OP_FEATURES)) needs cmake + a C/C++ toolchain to build whisper.cpp."; \
	  echo "  macOS:         brew install cmake"; \
	  echo "  Debian/Ubuntu: sudo apt-get install -y cmake build-essential"; \
	  echo "  Or run without on-device STT:  make $(MAKECMDGOALS) STT=0"; \
	  exit 1; }
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

launch: stt-preflight build-output build-operator ## Launch EVERYTHING — output window (NDI auto) + operator shell (STT on; OP_FEATURES= to skip)
	@echo ">> build profile: $(PROFILE_NAME)$(if $(filter 1,$(RELEASE)),, — use \`make run-release\` to judge performance)"
	@echo ">> NDI output: $(NDI_STATUS)"
	@echo ">> on-device STT: $(STT_STATUS)"
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

operator: stt-preflight ## Run only the operator shell (connects to a running output window, else a standalone demo)
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
	$(CARGO) clippy $(OP) --all-targets -- -D warnings
	$(CARGO) test $(WS) --workspace --no-fail-fast
	sh scripts/import_guards.sh
	$(CARGO) test $(WS) -p selahcue-licensing --release --no-fail-fast
	$(CARGO) test $(WS) -p selahcue-lan --features server --no-fail-fast
	$(CARGO) test $(WS) -p selahcue-app --features server --no-fail-fast
	$(CARGO) test $(WS) -p selahcue-data --features encryption --no-fail-fast
	$(CARGO) test $(WS) -p selahcue-desktop --features encryption --no-fail-fast
	$(CARGO) test $(WS) -p selahcue-scripture --features download --no-fail-fast
	$(CARGO) check $(OP)
	$(CARGO) test $(OP) --no-fail-fast
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

build-operator: stt-preflight ## Build the Tauri operator shell crate
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
