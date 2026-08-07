#!/usr/bin/env bash
# Populate the repo-vendored NDI SDK used by `--features ndi` (see
# implementation/desktop/vendor/ndi/README.md). Copies the headers + platform library from an
# already-installed NDI SDK into the vendor layout so the build is self-contained (no reliance on
# a system-wide SDK path or another app's copy). It does NOT download the SDK — the NDI SDK is
# distributed under a licence agreement from https://ndi.video/ ; install it (or unzip it) first,
# then run this to vendor it.
#
# Usage:
#   scripts/fetch_ndi_sdk.sh                       # auto-detect an installed SDK for this OS
#   scripts/fetch_ndi_sdk.sh "/path/to/NDI SDK"    # copy from an explicit SDK root
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$REPO_ROOT/implementation/desktop/vendor/ndi"

uname_s="$(uname -s)"
case "$uname_s" in
  Darwin) OS=macos ;;
  Linux)  OS=linux ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  *) echo "Unsupported OS: $uname_s"; exit 1 ;;
esac

# Candidate SDK roots (arg wins; else the standard install locations grafton-ndi also searches).
CANDIDATES=()
[ "${1:-}" != "" ] && CANDIDATES+=("$1")
if [ "$OS" = macos ]; then
  CANDIDATES+=("/Library/NDI SDK for macOS" "/Library/NDI SDK for Apple" "/Library/NDI 6 SDK" "/Applications/NDI SDK for Apple")
elif [ "$OS" = linux ]; then
  CANDIDATES+=("/usr/share/NDI SDK for Linux" "/usr/share/NDI Advanced SDK for Linux")
else
  CANDIDATES+=("/c/Program Files/NDI/NDI 6 SDK" "C:\\Program Files\\NDI\\NDI 6 SDK")
fi

SDK=""
for c in "${CANDIDATES[@]}"; do
  if [ -f "$c/include/Processing.NDI.Lib.h" ]; then SDK="$c"; break; fi
done
if [ -z "$SDK" ]; then
  echo "ERROR: no NDI SDK found (looked for include/Processing.NDI.Lib.h)."
  echo "Install the NDI SDK from https://ndi.video/ and re-run, or pass its path:"
  echo "  scripts/fetch_ndi_sdk.sh \"/path/to/NDI SDK for macOS\""
  exit 1
fi
echo ">> using NDI SDK at: $SDK"

DEST="$VENDOR/$OS"
mkdir -p "$DEST/include" "$DEST/lib"
cp -f "$SDK"/include/Processing.NDI.*.h "$DEST/include/"

case "$OS" in
  macos)
    src_lib=""
    for p in "$SDK/lib/macOS/libndi.dylib" "$SDK/lib/libndi.dylib"; do [ -f "$p" ] && src_lib="$p" && break; done
    [ -z "$src_lib" ] && { echo "ERROR: libndi.dylib not found under $SDK/lib"; exit 1; }
    cp -f "$src_lib" "$DEST/lib/libndi.dylib"
    ;;
  linux)
    mkdir -p "$DEST/lib/x86_64-linux-gnu"
    src_lib="$(find "$SDK/lib" -name 'libndi.so*' | head -1)"
    [ -z "$src_lib" ] && { echo "ERROR: libndi.so not found under $SDK/lib"; exit 1; }
    cp -f "$src_lib" "$DEST/lib/x86_64-linux-gnu/libndi.so"
    ;;
  windows)
    mkdir -p "$DEST/lib/x64"
    cp -f "$SDK"/Lib/x64/Processing.NDI.Lib.x64.lib "$DEST/lib/x64/" 2>/dev/null || true
    cp -f "$SDK"/Bin/x64/Processing.NDI.Lib.x64.dll "$DEST/lib/x64/" 2>/dev/null || true
    ;;
esac

echo ">> vendored into: $DEST"
echo "   $(ls "$DEST/include" | wc -l | tr -d ' ') headers, lib:"
find "$DEST/lib" -maxdepth 2 -type f -print
echo ">> done. Build with NDI:  make ndi-preflight && make output-ndi"
