#!/bin/sh
# Run the SelahCue operator from a minimal, signed .app bundle (macOS only).
#
# Why: the on-device STT worker opens the microphone via cpal, which needs a TCC grant. Only a
# LaunchServices-started .app is its own "responsible process" for TCC, so macOS prompts for
# the app; a raw `cargo run` binary (or a binary exec'd from a shell) makes the *terminal*
# responsible — macOS never prompts and the app never appears in System Settings → Microphone,
# so capture silently returns silence. So: build → wrap in a signed .app → launch it via `open`.
#
# Any arguments are passed through to `cargo build` (e.g. `--features stt`, `--release`), and the
# bundled binary is taken from the matching target dir so a release run bundles the release build
# rather than a stale debug one.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OP="$ROOT/implementation/desktop/crates/selahcue-operator"
# Mirror cargo's own profile→directory mapping from the pass-through args.
PROFILE_DIR=debug
for arg in "$@"; do
  case "$arg" in
    --release) PROFILE_DIR=release ;;
  esac
done
BIN="$OP/target/$PROFILE_DIR/selahcue-operator"
APP="$OP/target/SelahCueOperator.app"   # no space → avoids LaunchServices path quirks
CONTENTS="$APP/Contents"

echo ">> building the operator ($PROFILE_DIR)…" >&2
cargo build --manifest-path "$OP/Cargo.toml" "$@"

echo ">> assembling the .app bundle (microphone-capable)…" >&2
rm -rf "$APP"
mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources"
cp "$OP/Info.plist" "$CONTENTS/Info.plist"
cp "$BIN" "$CONTENTS/MacOS/selahcue-operator"
chmod +x "$CONTENTS/MacOS/selahcue-operator"
# App icon: the SelahCue logo (icons/icon.icns). Info.plist's CFBundleIconFile=icon points here,
# so the dock/Finder/cmd-tab show the logo instead of the generic app icon.
cp "$OP/icons/icon.icns" "$CONTENTS/Resources/icon.icns"
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
