#!/bin/sh
# Run the SelahCue operator from a minimal, signed .app bundle (macOS only).
#
# Why: the on-device STT worker opens the microphone via cpal, which needs a TCC grant. Only a
# LaunchServices-started .app is its own "responsible process" for TCC, so macOS prompts for
# the app; a raw `cargo run` binary (or a binary exec'd from a shell) makes the *terminal*
# responsible — macOS never prompts and the app never appears in System Settings → Microphone,
# so capture silently returns silence. So: build → wrap in a signed .app → launch it via `open`.
#
# Any arguments are passed through to `cargo build` (e.g. `--features stt`).
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OP="$ROOT/implementation/desktop/crates/selahcue-operator"
BIN="$OP/target/debug/selahcue-operator"
APP="$OP/target/SelahCueOperator.app"   # no space → avoids LaunchServices path quirks
CONTENTS="$APP/Contents"

echo ">> building the operator…" >&2
cargo build --manifest-path "$OP/Cargo.toml" "$@"

echo ">> assembling the .app bundle (microphone-capable)…" >&2
rm -rf "$APP"
mkdir -p "$CONTENTS/MacOS"
cp "$OP/Info.plist" "$CONTENTS/Info.plist"
cp "$BIN" "$CONTENTS/MacOS/selahcue-operator"
chmod +x "$CONTENTS/MacOS/selahcue-operator"
xattr -cr "$APP" 2>/dev/null || true    # clear any quarantine so LaunchServices will launch it

# Ad-hoc sign with a STABLE identifier so the mic grant is attributed to com.selahcue.operator.
if ! codesign --force --sign - --identifier com.selahcue.operator "$APP" 2>/dev/null; then
  echo ">> warning: codesign failed; the microphone prompt may not appear." >&2
fi

# Make sure LaunchServices knows about this freshly-built bundle before we open it.
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP" 2>/dev/null || true

echo ">> launching SelahCueOperator.app — approve the microphone prompt when it appears." >&2
echo ">>   watch STT logs with:" >&2
echo "     log stream --style compact --predicate 'senderImagePath CONTAINS \"selahcue-operator\"'" >&2
# LaunchServices launch (`open`) so the .app is the TCC responsible process; -W blocks until it
# quits (so `make launch` tears down the output window afterwards). NOTE: we deliberately do NOT
# pass --stdout/--stderr — combined with -W they trip LaunchServices error -10810 on current
# macOS. The app's stderr (the `SelahCue STT:` diagnostics) goes to the unified log instead; the
# mic level + download % are also shown live in the operator UI.
exec open -n -W "$APP"
