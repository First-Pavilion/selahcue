#!/bin/sh
# Structural merge gates for the presentation importer (selahcue-import).
#
# These are the two properties the security review asked to be made STRUCTURAL rather than
# aspirational, and they are one-line checks only because the importer is its own crate — inside
# the Tauri operator, whose graph legitimately contains a TLS stack via the scripture download
# feature and the cloud client, neither property would even be stateable.
#
#   B2 — "the importer's dependency graph contains no network crate." A document must never be
#        able to cause network I/O: that is a security defect (an XXE fetch is the exfiltration
#        channel) AND, in an offline-first app, a privacy defect on its own.
#   §14 — NO FILESYSTEM PRIMITIVE IS REACHABLE FROM HAND-WRITTEN IMPORTER CODE. Every effect is
#        injected through ByteSource / MediaSink, so file disclosure through a parser bug is
#        impossible rather than merely defended against.
#
#        Stated that way on purpose. The stronger-sounding claim this used to make — "the importer
#        performs no filesystem I/O at all" — is not true of the linked graph and never was:
#        selahcue-engine pulls cosmic-text for text layout, which pulls fontdb, which links
#        `memmap2` (it memory-maps system font files) and `rayon` (it enumerates them in parallel).
#        Both are in the allowlist below, deliberately. What the grep below actually asserts is the
#        property that matters and that a reviewer can check: nothing in `selahcue-import/src` can
#        name a file, so no path derived from a hostile document can reach one.
#
# Run from the repository root. Exits non-zero on a violation, with the offending line.

set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DESKTOP="$ROOT/implementation/desktop"
SRC="$DESKTOP/crates/selahcue-import/src"
CARGO=${CARGO:-cargo}

fail() {
  echo "IMPORT GUARD FAILED: $1" >&2
  exit 1
}

# --- B2: the importer's normal dependency graph is an ALLOWLIST ---------------------------
# `-e normal` excludes dev- and build-dependencies: the test builder may legitimately use
# whatever it likes, but nothing the SHIPPED importer links may be able to open a socket.
#
# This was a denylist of fifteen crate names. A denylist answers "is it one of the fifteen network
# crates we thought of in 2026", which is not the property B2 states: the graph is transitive, so a
# routine bump of any dependency can pull in a sixteenth — an async runtime behind a feature, a
# telemetry shim, a crate that grew an HTTP client — and the check would pass while the property
# it exists to protect had quietly stopped holding. It also cannot see a crate arriving under a
# name nobody listed, which is the only way this realistically goes wrong.
#
# An allowlist inverts that. Anything new in the graph, from any depth and under any name, fails
# here and has to be looked at and added deliberately. Adding a line is a two-second change; the
# point is that a human has to make it, and the diff shows a reviewer exactly what entered the
# graph of the crate that parses hostile files.
echo ">> checking selahcue-import's dependency graph against the allowlist (B2)"
TREE=$("$CARGO" tree --manifest-path "$DESKTOP/Cargo.toml" -p selahcue-import -e normal --prefix none)

# Every crate the importer is permitted to link, transitively. Keep sorted; add with a reason.
ALLOWED=$(cat <<'EOF'
adler2
arrayvec
bitflags
bytemuck
bytemuck_derive
cfg-if
cosmic-text
crc32fast
crossbeam-deque
crossbeam-epoch
crossbeam-utils
either
fdeflate
flate2
font-types
fontdb
jpeg-decoder
libc
libm
log
memchr
memmap2
miniz_oxide
png
proc-macro2
qrcode
quick-xml
quote
rangemap
rayon
rayon-core
read-fonts
rustc-hash
rustybuzz
selahcue-core
selahcue-engine
selahcue-import
selahcue-present
self_cell
serde
serde_core
serde_derive
simd-adler32
skrifa
slotmap
smallvec
swash
syn
sys-locale
tinyvec
tinyvec_macros
ttf-parser
unicode-bidi
unicode-bidi-mirroring
unicode-ccc
unicode-ident
unicode-linebreak
unicode-properties
unicode-script
unicode-segmentation
yazi
zeno
EOF
)

# `cargo tree` prints "name vX.Y.Z [(path)] [(*)]"; the first field is the crate name.
UNEXPECTED=$(echo "$TREE" | awk 'NF {print $1}' | sort -u | grep -vxF "$ALLOWED" || true)
if [ -n "$UNEXPECTED" ]; then
  echo "unexpected crates in selahcue-import's normal dependency graph:" >&2
  echo "$UNEXPECTED" >&2
  fail "the importer's dependency graph grew. A document must never be able to cause network I/O, and this crate parses hostile input — review each addition and add it to ALLOWED in this script if it is intended"
fi

# The named network crates stay called out explicitly as well. The allowlist already excludes them,
# but a future maintainer pasting a name into ALLOWED to make the build go green should have to
# delete this too, and see why.
for crate in reqwest hyper ureq curl isahc surf attohttpc rustls native-tls openssl tokio async-std smol socket2 mio; do
  if echo "$TREE" | awk '{print $1}' | grep -qx "$crate"; then
    echo "$TREE" | grep -n "^$crate" >&2
    fail "'$crate' is in selahcue-import's dependency graph — a document must never be able to cause network I/O"
  fi
done

# --- no filesystem or process primitives reachable from the parsers -----------------------
echo ">> checking no filesystem primitive is reachable from selahcue-import/src"
# Prose is filtered out: several module docs NAME these primitives to explain why they are
# absent, and a guard that could be silenced by deleting a comment would be measuring the wrong
# thing. Only real code counts.
#
# The patterns are REGEXES, not fixed strings, because `std::fs` alone does not find the way
# anyone would actually write it. `use std::{fs, io::Read};` followed by `fs::read(path)` contains
# neither the literal `std::fs` nor `File::open`, so the whole guard was blind to the single most
# idiomatic form of the thing it exists to forbid. Two rules close it: a braced `use std::{...}`
# naming one of these modules, and a bare `fs::` / `net::` / `process::` / `env::` call site
# wherever the import came from.
PATTERNS='
std::fs
std::net
std::process
std::env
File::open
OpenOptions
Command::new
use[[:space:]]+std::\{[^}]*\b(fs|net|process|env)\b
(^|[^[:alnum:]_:])(fs|net|process|env)::
'
echo "$PATTERNS" | while IFS= read -r pattern; do
  [ -n "$pattern" ] || continue
  # The trailing `|| true` keeps `set -e` from treating "no matches" as a failure. Comment lines
  # are filtered because several module docs NAME these primitives to explain why they are absent
  # — a guard that could be silenced by deleting a comment would be measuring the wrong thing.
  HITS=$(grep -rnE --include='*.rs' -- "$pattern" "$SRC" 2>/dev/null | grep -v ':[[:space:]]*//' || true)
  if [ -n "$HITS" ]; then
    echo "$HITS" >&2
    fail "'$pattern' appears in selahcue-import/src — no filesystem primitive may be reachable from the importer's own code (the shell injects every effect)"
  fi
done
# `while` above runs in a subshell, so `fail`'s exit does not leave this script. Re-check the
# whole set once more in THIS shell and exit properly if anything matched.
echo "$PATTERNS" | while IFS= read -r pattern; do
  [ -n "$pattern" ] || continue
  grep -rnE --include='*.rs' -- "$pattern" "$SRC" 2>/dev/null | grep -v ':[[:space:]]*//' || true
done | grep -q . && fail "a filesystem primitive is reachable from selahcue-import/src (see above)"


# --- the crate really is a workspace member, so `cargo test --workspace` covers it ---------
echo ">> checking selahcue-import is covered by the workspace test run"
grep -q '"crates/selahcue-import"' "$DESKTOP/Cargo.toml" \
  || fail "selahcue-import is not a workspace member — its hostile-input battery would not run in CI"

# --- selahcue-licensing is a workspace member, so the default test run covers it ----------
# The licensing crate deliberately has NO Cargo features of its own: its network transport
# and secret store are selahcue-cloud's feature-gated impls, injected by the shell. The
# whole argument for that design is that 100% of its logic is therefore exercised by the
# plain `cargo test --workspace` — which rests entirely on it BEING a workspace member.
#
# Drop the member line and `--workspace` silently stops running its tests while the gate
# stays green: the never-blank closure guard, the credential-redaction sweep and the
# trust-store bounds all quietly stop protecting anything. This cannot be checked from
# inside the crate — `cargo test -p selahcue-licensing` fails to resolve the package, so a
# test living there never runs to report it. Same reasoning as the selahcue-import check
# above, and the same one-line fix.
echo ">> checking selahcue-licensing is covered by the workspace test run"
grep -q '"crates/selahcue-licensing"' "$DESKTOP/Cargo.toml" \
  || fail "selahcue-licensing is not a workspace member — its activation, custody, trust-store and never-blank guards would not run in CI"

# --- the JPEG decoder stays pinned, scalar-only and rayon-free ----------------------------
# The determinism contract (ADR-0025 decision 3) is a property of the PIN, not of the format:
# without `platform_independent` the crate does runtime SSSE3/NEON dispatch and the same binary
# produces different pixels on different CPUs, which would break the golden tests on some CI
# runners only.
echo ">> checking the JPEG decoder pin and features (ADR-0025)"
ENGINE_TOML="$DESKTOP/crates/selahcue-engine/Cargo.toml"
grep -q 'jpeg-decoder = { version = "=' "$ENGINE_TOML" \
  || fail "jpeg-decoder must be pinned to an EXACT version — a bump is a golden-test-affecting change"
grep -q 'default-features = false' "$ENGINE_TOML" \
  || fail "jpeg-decoder must be built with default-features = false (no rayon)"
grep -q '"platform_independent"' "$ENGINE_TOML" \
  || fail "jpeg-decoder must enable platform_independent — scalar only, no runtime SIMD dispatch"

# --- the XML parser stays pinned too -------------------------------------------------------
# ADR-0024 pins it. `quick-xml = "0.41"` is a caret RANGE, not a pin: a `cargo update` moves the
# parser that reads hostile XML out of every imported deck — the one dependency in this crate that
# touches untrusted input directly — with no diff to review. The jpeg-decoder pin was enforced here
# and this one was not, which is how it came to be written as a range in the first place.
echo ">> checking the XML parser pin (ADR-0024)"
IMPORT_TOML="$DESKTOP/crates/selahcue-import/Cargo.toml"
grep -q 'quick-xml = { version = "=' "$IMPORT_TOML" \
  || fail "quick-xml must be pinned to an EXACT version — it parses untrusted XML, and a range lets it move without review"
grep -q 'quick-xml = {.*default-features = false' "$IMPORT_TOML" \
  || fail "quick-xml must be built with default-features = false (no serialize/encoding/async-tokio)"

echo "== import guards: OK =="
