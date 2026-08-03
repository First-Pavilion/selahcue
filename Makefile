# SelahCue — developer launch / build Makefile
#
# The Rust workspace lives in implementation/desktop; the Tauri operator shell is a
# standalone (workspace-excluded) crate under it. These targets wrap the cargo commands
# so you can launch and drive the app without remembering the paths and feature flags.
#
#   make            # show this help
#   make launch     # start the output window + operator shell (operator drives the window)
#   make output     # just the audience output window (native + LAN control server)
#   make operator   # just the Tauri operator shell
#   make remote CMD=go-live   # send one command to a running output window via the CLI

DESKTOP  := implementation/desktop
OPERATOR := $(DESKTOP)/crates/selahcue-operator
CARGO    ?= cargo
WS       := --manifest-path $(DESKTOP)/Cargo.toml
OP       := --manifest-path $(OPERATOR)/Cargo.toml
# The local endpoint file the output window writes (matches Rust's std::env::temp_dir()).
ENDPOINT := $(shell python3 -c "import tempfile,os;print(os.path.join(tempfile.gettempdir(),'selahcue-operator-endpoint.json'))" 2>/dev/null)
CMD      ?= next
SECS     ?=
# On-device STT (whisper.cpp + cpal) for the live transcript. ON by default for the dev RUN
# targets (launch/run/operator/build-operator) so one command brings up live transcription.
# It needs cmake + a C/C++ toolchain to compile whisper.cpp, and downloads the model on first
# use. Skip it (e.g. no cmake) with:  make launch OP_FEATURES=
# CI/check/clippy always use the default (no-STT) operator build, so this never affects them.
OP_FEATURES ?= stt
OPRUN       := $(if $(strip $(OP_FEATURES)),--features $(strip $(OP_FEATURES)),)

# On macOS the operator runs from a signed .app bundle so the on-device STT worker can get
# microphone access — a raw `cargo run` binary has no bundle identity, so macOS never prompts
# and mic capture silently returns silence. Everywhere else, run it directly with cargo.
UNAME := $(shell uname)
ifeq ($(UNAME),Darwin)
OPERATOR_RUN := sh scripts/run_operator_macapp.sh $(OPRUN)
else
OPERATOR_RUN := $(CARGO) run $(OP) $(OPRUN)
endif

.DEFAULT_GOAL := help
.PHONY: help launch run output operator operator-headless stt-preflight remote timer stop-timer demo mobile mobile-test ci nfr build build-operator test check clippy fmt clean

stt-preflight: ## (internal) verify the toolchain needed for --features stt is present
ifneq ($(strip $(OP_FEATURES)),)
	@command -v cmake >/dev/null 2>&1 || { \
	  echo "ERROR: on-device STT (--features $(OP_FEATURES)) needs cmake + a C/C++ toolchain to build whisper.cpp."; \
	  echo "  macOS:         brew install cmake"; \
	  echo "  Debian/Ubuntu: sudo apt-get install -y cmake build-essential"; \
	  echo "  Or run without on-device STT:  make $(MAKECMDGOALS) OP_FEATURES="; \
	  exit 1; }
endif

help: ## Show this help
	@echo "SelahCue — make targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

launch: stt-preflight build build-operator ## Launch output window + operator shell together (on-device STT on; OP_FEATURES= to skip)
	@echo ">> clearing any stale endpoint and starting the output window…"
	@rm -f "$(ENDPOINT)"; \
	$(CARGO) run -q $(WS) -p selahcue-desktop & \
	OUT_PID=$$!; \
	trap 'kill $$OUT_PID 2>/dev/null' EXIT INT TERM; \
	echo ">> waiting for the output window to advertise its endpoint…"; \
	for i in $$(seq 1 40); do [ -f "$(ENDPOINT)" ] && break; sleep 0.25; done; \
	echo ">> starting the operator shell (its buttons drive the output window)…"; \
	$(OPERATOR_RUN); \
	echo ">> operator closed; stopping the output window."; \
	kill $$OUT_PID 2>/dev/null || true

run: launch ## Alias for `launch`

output: ## Run only the output window (native audience output + LAN control server)
	$(CARGO) run $(WS) -p selahcue-desktop

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

ci: ## Run the CI gate locally (same gates as .github/workflows/ci.yml, minus the CI-only audit)
	cd $(DESKTOP) && $(CARGO) fmt --check
	cd $(OPERATOR) && $(CARGO) fmt --check
	$(CARGO) clippy $(WS) --workspace --all-targets -- -D warnings
	$(CARGO) clippy $(WS) -p selahcue-lan --features server --all-targets -- -D warnings
	$(CARGO) clippy $(WS) -p selahcue-app --features server --all-targets -- -D warnings
	$(CARGO) clippy $(OP) -- -D warnings
	$(CARGO) test $(WS) --workspace
	$(CARGO) test $(WS) -p selahcue-lan --features server
	$(CARGO) test $(WS) -p selahcue-app --features server
	$(CARGO) test $(WS) -p selahcue-data --features encryption
	$(CARGO) test $(WS) -p selahcue-desktop --features encryption
	$(CARGO) check $(OP)
	python3 scripts/operator_headless.py
	cd $(MOBILE) && $(FLUTTER) analyze && $(FLUTTER) test
	@echo ""
	@echo "== local CI gate: ALL GREEN =="

nfr: ## Measure the walking-skeleton NFRs (idle memory / cold start) on a release build
	sh scripts/measure_nfr.sh

build: ## Build the desktop workspace
	$(CARGO) build $(WS)

build-operator: stt-preflight ## Build the Tauri operator shell crate
	$(CARGO) build $(OP) $(OPRUN)

test: ## Run the workspace test suite
	$(CARGO) test $(WS)

check: ## Type-check the workspace + the operator shell
	$(CARGO) check $(WS)
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
