#!/usr/bin/env python3
"""Effect-level gate on DEVELOPER AI-PROVIDER KEYS reaching the Windows installer.

Sibling of `scripts/dev_key_not_in_release.sh` + `scripts/dev_key_scan.py`, which guard a
DIFFERENT secret (the development *entitlement* signing key). Read that script's header for the
full argument; the short version is that every control which asked a question ABOUT the source
or the configuration was defeated by a spelling nobody had enumerated -- a gate left in a
comment, `cfg!(debug_assertions)` turned back on, `[profile]` written as an inline table, the
legacy `.cargo/config` filename, a valueless rustflag, a config in a parent directory, and
`RUSTFLAGS` in the environment, which nothing in-repo can see at all.

This asks the other question: ARE THE BYTES IN THE THING WE SHIP.

WHAT IT GUARDS
`selahcue-operator`'s `dev-keys` feature (off by default) compiles `src/dev_env.rs`, which reads
the repo-root `.env` at startup and loads developer provider credentials. A build carrying it
bakes the build machine's source path into the binary and will pick up a credential from a stray
`.env` on whatever machine it runs on. It must never be what we hand a church.

WHAT IT DOES NOT CLOSE, stated plainly because the sibling script's comment once overclaimed and
that is how a control gets trusted past its reach:

  * A LITERAL-FREE RUNTIME LOADER. This is a byte-substring search. A build that fetches a key
    from a URL it assembles at runtime, or reads an env var whose name it derives rather than
    spells, leaves no literal to find and this scan prints OK. That route is closed by review of
    `dev_env.rs` (whose every file-opening line is behind `dev-keys`), not by this.
  * THE COMPRESSED INSTALLER PAYLOAD. NSIS compresses what it bundles, so a signature inside the
    packaged operator is NOT a substring of `*-setup.exe`. That is exactly why the primary target
    below is the UNCOMPRESSED `selahcue-operator.exe` and the sidecar, with the installer scanned
    as a cheap secondary. Never let the installer be the only target: a clean `*-setup.exe` on its
    own is close to no evidence.
  * ANOTHER PROVIDER. The set below is a floor, not a ceiling -- see SIGNATURES.

THE POSITIVE CONTROL IS THE POINT. A scan that silently examines nothing passes forever, and this
guard family has hit that failure mode repeatedly. So this refuses to report success unless it
can show it read a real artefact: a glob that matches nothing, a path that is not a regular file,
a file it cannot read, and a file too small to be a real build output are all HARD FAILURES, and
for every artefact scanned it builds a control fixture seeded from that artefact's own bytes plus
every declared signature and proves the matcher fires on each one. If the control does not fire,
the "clean" verdict proves nothing and the build fails.

Self-test: `installer_secret_scan.py --self-test` -- runs anywhere, no build required, and is run
as its own step in `.github/workflows/windows-installer.yml` so the control's own failure modes
are exercised on every run rather than once, by hand, at review time.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import sys
import tempfile

# --------------------------------------------------------------------------------------
# THE DECLARED SET. This is the ONE place a signature is written down.
#
# ADDING A PROVIDER IS A DATA CHANGE: append a row here. Do NOT thread a literal into the
# scanning logic below -- a scanner hardcoded to today's providers is correct until the next
# one lands and silently incomplete after, which is the exact shape of control this file
# exists to replace.
#
# WHEN A PROVIDER IS ADDED, THIS SET MUST GROW WITH IT. The two tickets that add one are
# 86akby4yz (Deepgram streaming transcription) and 86akby7d8 (OpenAI sermon notes); their
# endpoints are listed below already, before the code that talks to them exists, because the
# string is knowable now and a scan already looking for it is one less thing to remember.
#
# IF A SIGNATURE EVER TURNS UP LEGITIMATELY in a default-feature build, that is a security
# decision to record. It is never a string to quietly delete. But the two endpoints differ, and
# an earlier version of this comment got one of them wrong in a way that would have misdirected
# whoever answered the alarm:
#
# THE TWO ENDPOINT ROWS ARE NOT SYMMETRIC. They look alike and they are not, and getting this
# backwards sends whoever answers the alarm hunting a breach that is not there:
#
#   * `api.openai.com` -- PERMANENT. Sermon notes ship through a PROXIED service, so this
#     endpoint never belongs in a shipped artefact under any planned architecture. A red here
#     is a real finding at any point in the future. Do not add an expiry to this row.
#
#   * `api.deepgram.com` -- HAS A SCHEDULED EXPIRY, and this gate WILL go red on a CORRECT
#     build the day it arrives. The Phase 2 design deliberately keeps audio off our
#     infrastructure: the desktop obtains a server-minted grant token (`POST /v1/stt/session`)
#     and then streams DIRECTLY to `wss://api.deepgram.com/v1/listen`. That endpoint is
#     therefore SUPPOSED to be in the shipped operator once 86akby3xu lands.
#
#     ACTION WHEN 86akby3xu LANDS: DELETE the `api.deepgram.com` row from SIGNATURES and from
#     REQUIRED_SIGNATURES. Do not suppress it, do not add an exception branch, and do not
#     override the gate -- deleting the row is the recorded decision, and it is a data change,
#     which is the whole point of this table. Sana owns the sign-off.
#
#     This is written down because a gate with a SCHEDULED FALSE POSITIVE is worse than no gate
#     at that moment: the first person to hit it learns that this gate cries wolf, and the
#     habit of overriding it outlives the one legitimate red.
#
#     The other three Deepgram-adjacent needles -- `DEEPGRAM_API_KEY`, the loader prefix and
#     the `.env` path suffix -- STAY. None of them belongs in a shipped artefact under any
#     plan; only the hostname's status changes.
# --------------------------------------------------------------------------------------
SIGNATURES: tuple[tuple[str, str], ...] = (
    ("selahcue dev-keys:", "dev_env.rs loader diagnostics (3x) — the loader's own signature"),
    # EXPIRES — see THE DEEPGRAM ROW HAS A SCHEDULED EXPIRY above. Delete this row at 86akby3xu.
    ("api.deepgram.com", "Deepgram endpoint — 86akby4yz; EXPIRES: DELETE this row at 86akby3xu"),
    # Does NOT expire: notes stay proxied, so this endpoint never belongs in a shipped build.
    ("api.openai.com", "OpenAI sermon-notes endpoint — 86akby7d8; permanent, notes stay proxied"),
    ("/../../../../.env", "REPO_ROOT_ENV_FILE — the compile-time repo-root .env path"),
    ("DEEPGRAM_API_KEY", "loadable credential variable name"),
    ("OPENAI_API_KEY", "loadable credential variable name"),
    # REDUNDANT TODAY, AND THAT IS THE POINT. Both of these are diagnostic text from the same
    # module that emits `selahcue dev-keys:`, so today anything carrying one carries that too.
    # Omitting them on that basis would make this gate depend on a COUPLING ASSUMPTION ABOUT A
    # STARTUP MESSAGE: someone tidying that `eprintln!` breaks the redundancy silently, and the
    # only detection goes with it. This repo was bitten by exactly that shape today -- a defect
    # held harmless by a consumer that then documented its own leniency as unnecessary, on the
    # strength of a guarantee that had a hole in it. A redundancy you rely on is made explicit,
    # not assumed, and here that costs one row each.
    (".env.sample", "loader diagnostics point at it — redundant with the prefix, deliberately"),
    ("repo-root .env", "loader diagnostics phrase — substring of the longer variants too"),
)

# The required floor. Asserted at run time so emptying or trimming SIGNATURES fails loudly
# instead of turning this whole gate vacuous -- the mutation "delete the string list" must go
# RED, not green.
#
# WHAT HAS ACTUALLY BEEN OBSERVED, stated precisely because a future editor of this set will
# trust this line: a `dev-keys` build carries **4 of these 6**, and a default build carries 0.
# Reproduced twice (independently, on a real 70 MB operator binary): the loader prefix, the
# `.env` path suffix, `DEEPGRAM_API_KEY` and `OPENAI_API_KEY` are present; the two ENDPOINT
# strings are in no source file at any feature state, so no build can contain them yet.
# They are PRE-EMPTIVE -- declared ahead of the code, exercised by the positive control, and
# never yet observed in an artefact. An earlier note here cited "6/6", which is not
# reproducible for this set; do not read it as evidence that all six have been seen.
REQUIRED_SIGNATURES: frozenset[str] = frozenset(
    {
        "selahcue dev-keys:",
        "api.deepgram.com",
        "api.openai.com",
        "/../../../../.env",
        "DEEPGRAM_API_KEY",
        "OPENAI_API_KEY",
        ".env.sample",
        "repo-root .env",
    }
)

# Rust string literals land in the binary as UTF-8; NSIS carries installer strings as UTF-16LE.
# Scanning both costs one extra needle per signature and closes an encoding nobody would think
# to check by hand.
ENCODINGS: tuple[str, ...] = ("utf-8", "utf-16-le")

# PINNED, for the same reason REQUIRED_SIGNATURES is. Every injection case and the positive
# control iterate ENCODINGS, so DELETING a member does not fail anything -- it silently shrinks
# coverage and the suite still passes (measured: 26 cases become 20, exit 0). A premise that
# can be removed without a red is not a control, and the claim "an NSIS-encoded string cannot
# slip past" rests on this one. `every_encoding_is_declared` in the self-test asserts it.
REQUIRED_ENCODINGS: frozenset[str] = frozenset({"utf-8", "utf-16-le"})

OPERATOR = "implementation/desktop/crates/selahcue-operator"

# The "did I actually read a build output" floor, defined ONCE. It was previously repeated as a
# literal in every target row and re-spelled as `< 1` in the control that guards it, so a row
# with `min_bytes = 1` satisfied the control while accepting any non-empty placeholder. The
# control and the table now consume the same definition, which is the only way the control can
# be said to guard the table rather than a copy of it.
MIN_ARTEFACT_BYTES = 1_000_000

# DELIBERATELY A SECOND LITERAL, and not `= MIN_ARTEFACT_BYTES`. This is the absolute floor the
# tunable above must itself satisfy.
#
# The first attempt at this control consumed MIN_ARTEFACT_BYTES, which felt right -- one
# definition, both sides -- and was wrong: lowering the constant moved the control with it, so
# `MIN_ARTEFACT_BYTES = 1` passed a green suite while every target accepted any non-empty stub.
# That is the "control reads a copy" trap, re-introduced by the fix for a different instance of
# the same trap.
#
# Sharing ONE definition is right when the control must track a CONJUNCTION in the code under
# test. It is wrong for a THRESHOLD, where the control's whole job is to be an independent
# opinion about how low the threshold may go. Lowering the real floor now requires editing this
# number too -- two edits, and this comment sits on the second one.
ARTEFACT_FLOOR_MINIMUM = 1_000_000

# NOTHING GUARDED THE GUARDS. `REQUIRED_SIGNATURES` pins `SIGNATURES`, `REQUIRED_ENCODINGS` pins
# `ENCODINGS`, `REQUIRED_TARGETS` pins `TARGETS` -- and until these floors existed, all three
# pins could themselves be shortened, taking the set they guard with them. Review demonstrated
# the set shrinking 6 -> 2 with a fully green self-test.
#
# The regress has to stop at a literal integer somewhere, so it stops here: a bare count with no
# other reason to change, in the repo's own `const _: () = assert!(LOADABLE.len() == 2)` idiom
# from dev_env.rs. Growing a set is free; shrinking one means editing a number that says what it
# is for. `the_pins_themselves_have_not_shrunk` asserts these at run time too, because `assert`
# is stripped under `python -O`.
REQUIRED_SIGNATURE_COUNT = 8
REQUIRED_ENCODING_COUNT = 2
REQUIRED_TARGET_COUNT = 4
# Floor on the self-test's own case count (see self_test_case_floor).
SELF_TEST_CASE_FLOOR = 37

# --------------------------------------------------------------------------------------
# THE DECLARED TARGETS. Also one place, and also shaped for growth.
#
# STRUCTURED FOR TWO SCANS, ONE IMPLEMENTED. The entitlement-key scan documented at
# windows-installer.yml lines 24-33 is not wired into that workflow because nothing there links
# `selahcue-licensing`. When it does (86ak5mn1d / 86ak5mn1t), it scans these same artefacts for a
# different needle: add its key bytes as another signature source, not another walk of the tree.
#
# `min_bytes` is the "did I actually read a build output" floor. A 0-byte or truncated
# placeholder matching one of these globs must FAIL, not pass silently. In a fresh worktree
# the sidecar and the NDI dll are zero-byte placeholders (see ci.yml's create-only `stage()`),
# so without this floor a glob matching one of them would "scan" nothing and report clean.
#
# WHY THIS LIST IS THE PRIMARY CONTROL AND THE INSTALLER IS NOT. Scanning the UNCOMPRESSED
# inputs is stronger than scanning `*-setup.exe`, because these are the artefacts the installer
# packages: if they are clean, the compressed copies of them are clean. That argument holds
# ONLY IF nothing is packaged that is not scanned here, so the enumeration is written down:
#
#   packaged component            | covered by
#   ------------------------------+------------------------------------------------------
#   selahcue-operator.exe         | target 1, directly
#   dist/ frontend (HTML/JS/CSS)  | target 1, TRANSITIVELY -- `frontendDist` embeds it INTO
#                                 |   the operator binary; it is not a separate bundle file
#   whisper.cpp / STT             | target 1, TRANSITIVELY -- `--features stt` links it in
#   selahcue-output-<triple>.exe  | target 2, directly
#   Processing.NDI.Lib.x64.dll    | target 3, directly
#   icons (5x png/ico)            | NOT SCANNED, deliberately -- committed source rather than
#                                 |   build output, and no accident this control models puts a
#                                 |   credential in a PNG. A decision to overturn, not an
#                                 |   oversight: an unmentioned exclusion reads as a gap.
#   STT model weights             | NOT BUNDLED -- downloaded on first use
#   NSIS stub, WebView2 bootstrap | third-party, out of scope
#
# The transitive rows are the ones that get lost. Before adding a target for a new bundle
# component, check whether it is already INSIDE one of these binaries.
# --------------------------------------------------------------------------------------
TARGETS: tuple[tuple[str, int, str], ...] = (
    # PRIMARY. Uncompressed, and the only artefact that can contain dev_env.rs's own strings.
    (f"{OPERATOR}/target/release/selahcue-operator.exe", MIN_ARTEFACT_BYTES, "operator console binary"),
    # The sidecar the installer bundles, staged by the workflow from the desktop build.
    (
        f"{OPERATOR}/binaries/selahcue-output-*.exe",
        MIN_ARTEFACT_BYTES,
        "native output window (bundled sidecar)",
    ),
    # The NDI runtime, staged into the bundle as a Tauri `resources` entry. Scanning it does
    # NOT close a credential-leak path and should not be described as one: the dll comes from
    # the public NDI redistributable, our compiler never touches it, and a `dev-keys` signature
    # cannot reach it through the feature flag. What it catches is BUILD-PLUMBING ERROR -- the
    # staging step copies whatever happens to sit at that path, so a substituted or wrong file
    # would otherwise enter the bundle unexamined. It is here so that "everything packaged is
    # scanned uncompressed" is true rather than nearly true, because that claim is what makes
    # the compression limitation above acceptable.
    (
        f"{OPERATOR}/binaries/Processing.NDI.Lib.x64.dll",
        MIN_ARTEFACT_BYTES,
        "NDI runtime (bundled resource)",
    ),
    # SECONDARY, and weak on its own: Tauri's NSIS template sets `SetCompressor /SOLID` (lzma)
    # and this repo overrides nothing, so BOTH the packaged binaries AND the install script's
    # own string table are inside the compressed block and invisible here. What this target
    # actually sees in plaintext is the stub, the PE headers/manifest and the version-info
    # resources -- which is where the UTF-16LE leg earns its place. Keep it for that, and do
    # not mistake a clean result here for a clean bundle; the three uncompressed targets above
    # are what carry that claim.
    (
        f"{OPERATOR}/target/release/bundle/nsis/*-setup.exe",
        MIN_ARTEFACT_BYTES,
        "NSIS installer bundle",
    ),
)

# PINNED, and this is the set that matters MOST. The header above says the uncompressed-inputs
# approach "holds ONLY IF nothing is packaged that is not scanned here" -- and until this
# existed, nothing enforced that sentence. Commenting out the operator-binary row left the
# self-test reporting 29 cases passed, exit 0, and a tree scanning only the compressed installer
# would print "== installer secret scan: OK ==" while proving almost nothing.
#
# This is the same defect the ENCODINGS pin closed, found one collection along, because fixing
# an instance of this pattern draws attention to the instance and not to the class. The general
# form: ANY collection the suite merely ITERATES is a premise, and a premise that can be
# shortened without a red is not a control.
#
# A target may be ADDED freely. Removing one of these requires deleting it here too, which is a
# deliberate act with a diff that says so.
REQUIRED_TARGETS: frozenset[str] = frozenset(
    {
        f"{OPERATOR}/target/release/selahcue-operator.exe",
        f"{OPERATOR}/binaries/selahcue-output-*.exe",
        f"{OPERATOR}/binaries/Processing.NDI.Lib.x64.dll",
        f"{OPERATOR}/target/release/bundle/nsis/*-setup.exe",
    }
)

assert len(REQUIRED_SIGNATURES) >= REQUIRED_SIGNATURE_COUNT
assert len(REQUIRED_ENCODINGS) >= REQUIRED_ENCODING_COUNT
assert len(REQUIRED_TARGETS) >= REQUIRED_TARGET_COUNT

CHUNK = 8 << 20  # 8 MiB. Bounded memory: an installer of any size is read in fixed-size pieces.


def declared_target_gaps(targets: tuple[tuple[str, int, str], ...]) -> set[str]:
    """REQUIRED_TARGETS absent from `targets`.

    ONE definition, consumed by `main()` on the production path and by
    `every_required_target_is_declared` in the self-test. Deliberately not re-derived in the
    control: a control that re-assembles the predicate it is guarding tests its own copy, and
    this file has already been bitten by exactly that.
    """
    return set(REQUIRED_TARGETS) - {pattern for pattern, _min_bytes, _label in targets}


class ScanError(Exception):
    """A condition under which this gate must fail rather than report success."""


def needles(signatures: tuple[tuple[str, str], ...]) -> list[tuple[bytes, str, str]]:
    """(bytes, signature, encoding) for every declared signature in every encoding."""
    out: list[tuple[bytes, str, str]] = []
    for text, _why in signatures:
        for enc in ENCODINGS:
            out.append((text.encode(enc), text, enc))
    return out


def scan_file(path: pathlib.Path, signatures: tuple[tuple[str, str], ...]) -> list[tuple[str, str, int]]:
    """Every (signature, encoding, offset) present in `path`.

    Chunked with an overlap of `max needle length - 1`, so a signature straddling a chunk
    boundary is still found. Without the overlap this scan would have a silent blind spot every
    8 MiB -- tested by `signature_across_a_chunk_boundary_is_found`.

    Any OSError is allowed to propagate to the caller, which turns it into a hard failure. A
    file we could not read is NOT a file without the signature.
    """
    probes = needles(signatures)
    if not probes:
        raise ScanError("no signatures to scan for — refusing to report a clean artefact")
    overlap = max(len(n) for n, _, _ in probes) - 1
    hits: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    tail = b""
    base = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            window = tail + chunk
            for raw, text, enc in probes:
                idx = window.find(raw)
                if idx != -1 and (text, enc) not in seen:
                    seen.add((text, enc))
                    hits.append((text, enc, base + idx))
            tail = window[-overlap:] if overlap > 0 else b""
            base += len(window) - len(tail)
    return hits


def digest(path: pathlib.Path) -> tuple[int, str]:
    """(size, sha256) — the evidence that a real file of non-trivial size was examined."""
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            h.update(chunk)
    return size, h.hexdigest()


def resolve(root: pathlib.Path, pattern: str, min_bytes: int, label: str) -> list[pathlib.Path]:
    """Files matching one declared target, or a hard failure.

    Every branch here fails CLOSED. A glob that matches nothing is the single most likely way
    this gate rots into a permanent green: the build renames an artefact, the pattern stops
    matching, and a scanner that treated "no matches" as "nothing to report" would congratulate
    itself forever.
    """
    matches = sorted(root.glob(pattern))
    if not matches:
        raise ScanError(
            f"{label}: pattern `{pattern}` matched NO file under {root}. A scan with nothing "
            f"to scan must never report success — either the build did not produce this "
            f"artefact, or it was renamed and this target needs repointing. Never delete it."
        )
    for p in matches:
        if not p.is_file():
            raise ScanError(f"{label}: `{p}` matched but is not a regular file — refusing to pass.")
        try:
            size = p.stat().st_size
        except OSError as exc:
            raise ScanError(f"{label}: cannot stat `{p}`: {exc}") from exc
        if size < min_bytes:
            raise ScanError(
                f"{label}: `{p}` is {size} bytes, below the {min_bytes}-byte floor for a real "
                f"build output. A placeholder or truncated artefact scans clean for the wrong "
                f"reason."
            )
    return matches


def positive_control(
    sample: pathlib.Path, signatures: tuple[tuple[str, str], ...], workdir: pathlib.Path
) -> None:
    """Prove the matcher fires on EVERY declared signature, in a file shaped like the real one.

    Seeded from the real artefact's own leading bytes so the control is not a synthetic string
    in a vacuum — it is this build's artefact with the signatures added. A set where only the
    first entry is verified is a set whose rest is decoration, so every signature in every
    encoding must be found or the build fails.

    NOTE: the fixture is a COPY in a temp directory. This function must never write to, append
    to, or truncate the artefact it was handed — that artefact is what we ship.
    """
    probes = needles(signatures)
    fixture = workdir / "positive-control.bin"
    with sample.open("rb") as src, fixture.open("wb") as dst:
        dst.write(src.read(1 << 20))
        for raw, _text, _enc in probes:
            dst.write(b"\x00" * 32)
            dst.write(raw)
        dst.write(b"\x00" * 32)

    found = {(text, enc) for text, enc, _off in scan_file(fixture, signatures)}
    missing = [(t, e) for _r, t, e in probes if (t, e) not in found]
    if missing:
        raise ScanError(
            "POSITIVE CONTROL FAILED: the scanner did NOT detect "
            + ", ".join(f"`{t}` ({e})" for t, e in missing)
            + " in a fixture that provably contains it. The scanner is not working, so its "
            "'artefacts are clean' verdict proves nothing. Do not trust this gate until the "
            "matcher and the declared set are fixed."
        )
    print(
        f"   positive control: {len(probes)}/{len(probes)} signature-encoding pairs detected "
        f"in a fixture seeded from {sample.name}"
    )


def run_scan(
    root: pathlib.Path,
    targets: tuple[tuple[str, int, str], ...],
    signatures: tuple[tuple[str, str], ...],
) -> None:
    """The gate. Raises ScanError on anything short of a proven-clean set of artefacts."""
    if not signatures:
        raise ScanError(
            "the signature set is EMPTY. This gate cannot pass without something to look for."
        )
    declared = {text for text, _why in signatures}
    missing_required = REQUIRED_SIGNATURES - declared
    if missing_required:
        raise ScanError(
            "the declared set has lost required signatures: "
            + ", ".join(sorted(f"`{s}`" for s in missing_required))
            + ". The set may GROW as providers are added; it must not shrink."
        )
    if not targets:
        raise ScanError("no artefact targets declared — this gate would scan nothing.")

    print(f">> scanning shipped artefacts for {len(signatures)} developer-key signatures")
    for text, why in signatures:
        print(f"   signature: `{text}`  ({why})")

    scanned: list[pathlib.Path] = []
    poisoned: list[str] = []
    with tempfile.TemporaryDirectory(prefix="selahcue-scan-") as tmp:
        workdir = pathlib.Path(tmp)
        for pattern, min_bytes, label in targets:
            for path in resolve(root, pattern, min_bytes, label):
                try:
                    before = digest(path)
                    hits = scan_file(path, signatures)
                except OSError as exc:
                    raise ScanError(
                        f"{label}: cannot READ `{path}`: {exc}. An unreadable artefact is not a "
                        f"clean artefact — this gate fails rather than assuming the best."
                    ) from exc
                print(f"== {label}: {path}")
                print(f"   {before[0]:,} bytes, sha256 {before[1]}")
                for text, enc, off in hits:
                    # Reported HERE, not buffered to the end. A later target failing to resolve
                    # used to short-circuit the drain and swallow this line entirely.
                    line = f"`{text}` ({enc}) at offset {off} in {path}"
                    print(f"  DEVELOPER KEY SIGNATURE PRESENT: {line}", file=sys.stderr)
                    poisoned.append(line)
                try:
                    positive_control(path, signatures, workdir)
                except OSError as exc:
                    # Same escape already fixed for digest(), one function along: an OSError
                    # here exited non-zero but as a raw traceback rather than this gate's
                    # banner, so nothing failed open -- the operator just could not tell what
                    # broke.
                    raise ScanError(
                        f"{label}: cannot build the positive control from `{path}`: {exc}. "
                        f"Without a working control, a clean verdict on this artefact proves "
                        f"nothing."
                    ) from exc
                try:
                    after = digest(path)
                except OSError as exc:
                    raise ScanError(
                        f"{label}: cannot re-read `{path}` after the scan: {exc}"
                    ) from exc
                if after != before:
                    raise ScanError(
                        f"{label}: `{path}` CHANGED during the scan "
                        f"({before[0]} bytes/{before[1]} -> {after[0]} bytes/{after[1]}). This "
                        f"gate reads artefacts and must never modify one — the positive control "
                        f"is built from a copy for exactly this reason."
                    )
                scanned.append(path)

    if poisoned:
        raise ScanError(
            "a developer-key signature is present in an artefact "
            "this workflow ships. A `dev-keys` build reads the repo-root `.env` at startup and "
            "bakes the build machine's source path into the binary; it must never be "
            "distributed. Check that no build step added `--features dev-keys` and that no new "
            "code embeds a provider endpoint. Details above name the artefact and the string."
        )

    print(
        f"== installer secret scan: OK == ({len(scanned)} artefact(s) read and proven scannable, "
        f"0 of {len(signatures)} signatures present)"
    )


# ======================================================================================
# SELF-TEST
#
# The mutations this ticket demanded be verified by hand -- nonexistent path, emptied string
# list, zero-byte file -- are encoded here instead, so they are re-proven on every run rather
# than once, by a person, at review time. A control whose failure modes are only ever checked
# manually is the control this file exists to replace.
#
# Every case asserts the gate goes RED. `a_clean_artefact_passes` is the paired positive
# control for the SUITE: without it, a scanner that failed unconditionally would pass every
# other case here and look thoroughly tested.
# ======================================================================================

CLEAN = b"MZ\x90\x00" + b"\xcc" * 4096 + b"benign build output, no developer keys here.\n"


def _artefact(path: pathlib.Path, payload: bytes = b"", size: int = 1_200_000) -> pathlib.Path:
    """A file big enough to clear the min_bytes floor, optionally carrying `payload`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = bytearray()
    while len(body) < size:
        body += CLEAN
    if payload:
        body[600_000:600_000] = payload
    path.write_bytes(bytes(body))
    return path


def _targets(pattern: str, min_bytes: int = 1_000_000) -> tuple[tuple[str, int, str], ...]:
    return ((pattern, min_bytes, "self-test artefact"),)


def _expect_red(fn, case: str) -> tuple[str | None, ScanError | None]:
    """Run a case that MUST fail.

    Returns (complaint, exception). The complaint is None when the case failed as required;
    the exception comes back so a caller can assert on the MESSAGE without re-running the
    scan — a red build whose message names neither the artefact nor the string tells the
    person reading it nothing.
    """
    try:
        fn()
    except ScanError as exc:
        return None, exc
    return f"{case}: expected the gate to FAIL, but it passed", None


# Deliberately one long flat function: a reader auditing this gate should be able to see
# every case it covers in one pass, without chasing helpers.
def self_test() -> int:
    failures: list[str] = []
    cases = 0

    with tempfile.TemporaryDirectory(prefix="selahcue-scan-selftest-") as tmp:
        root = pathlib.Path(tmp)
        quiet = open(os.devnull, "w")  # closed at the end of this `with` block

        poison_log: list[str] = []

        def scan(targets, signatures=SIGNATURES):
            """Run the gate with its output captured.

            stderr is captured too, and kept in `poison_log`, so the two dozen
            "DEVELOPER KEY SIGNATURE PRESENT" lines the expected-red cases produce do not
            read as a fire in a PASSING self-test log — while still being available to
            assert against.
            """
            import contextlib
            import io

            buf = io.StringIO()
            poison_log.clear()
            try:
                with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(buf):
                    run_scan(root, targets, signatures)
            finally:
                poison_log.append(buf.getvalue())

        # --- the suite's own positive control -------------------------------------------
        cases += 1
        _artefact(root / "clean" / "selahcue-operator.exe")
        try:
            scan(_targets("clean/selahcue-operator.exe"))
        except ScanError as exc:
            failures.append(f"a_clean_artefact_passes: a benign artefact was rejected: {exc}")

        # --- every declared target has a real floor -------------------------------------
        # Pinning the premise: `zero_byte_artefact` below proves the floor bites, but only for
        # the target IT declares. A target added with `min_bytes=0` would match a fresh
        # worktree's zero-byte placeholder and scan nothing while reporting clean -- this
        # repo's exact recurring defect, a control that cannot fail. This makes that
        # unaddable rather than merely unlikely.
        cases += 1
        # Asserted against the INDEPENDENT literal, on the DEPLOYED table. Comparing against
        # MIN_ARTEFACT_BYTES made this vacuous, and driving it through `_targets()` would test
        # the helper's default rather than what actually ships.
        floorless = [
            (pat, mb, lbl) for pat, mb, lbl in TARGETS if mb < ARTEFACT_FLOOR_MINIMUM
        ]
        if floorless:
            failures.append(
                "every_target_has_a_size_floor: these DEPLOYED targets accept an artefact "
                f"below ARTEFACT_FLOOR_MINIMUM ({ARTEFACT_FLOOR_MINIMUM:,} bytes), so a "
                f"placeholder or truncated stub would scan clean: {floorless}"
            )

        # --- EVERY file a glob matches is scanned, not just the first ---------------------
        # `resolve()` returning `matches[:1]` survived the whole suite: every case used a glob
        # matching exactly one file, so "scans all matches" was never expressed. A second
        # sidecar -- or a stale build output beside a fresh one -- would have gone unread.
        cases += 1
        multi = root / "multi"
        # resolve() sorts, so the POISONED file must sort LAST or `matches[:1]` still finds it
        # and the case proves nothing. "aarch64" < "x86_64", so the clean one goes first.
        # (First attempt had these the other way round and the mutation survived.)
        _artefact(multi / "selahcue-output-aarch64-pc-windows-msvc.exe")
        _artefact(multi / "selahcue-output-x86_64-pc-windows-msvc.exe", b"selahcue dev-keys: x")
        assert sorted(q.name for q in multi.iterdir())[-1].startswith("selahcue-output-x86_64")
        c, exc = _expect_red(
            lambda: scan(_targets("multi/selahcue-output-*.exe")),
            "every_glob_match_is_scanned",
        )
        if c:
            failures.append(
                "every_glob_match_is_scanned: a glob matched two artefacts and the poisoned "
                "SECOND one was not read — resolve() is dropping matches."
            )

        # --- the pins themselves have not shrunk -----------------------------------------
        cases += 1
        undersized = [
            f"{name} has {have}, floor is {want}"
            for name, have, want in (
                ("REQUIRED_SIGNATURES", len(REQUIRED_SIGNATURES), REQUIRED_SIGNATURE_COUNT),
                ("REQUIRED_ENCODINGS", len(REQUIRED_ENCODINGS), REQUIRED_ENCODING_COUNT),
                ("REQUIRED_TARGETS", len(REQUIRED_TARGETS), REQUIRED_TARGET_COUNT),
            )
            if have < want
        ]
        if undersized:
            failures.append(
                "the_pins_themselves_have_not_shrunk: " + "; ".join(undersized)
                + ". A pin that can be shortened does not pin anything."
            )

        # --- H1: the TARGET set has not shrunk -------------------------------------------
        # The set the whole design argument rests on. Consumes declared_target_gaps() rather
        # than re-deriving the comparison, so mutating that predicate breaks this case too.
        cases += 1
        target_gaps = declared_target_gaps(TARGETS)
        if target_gaps:
            failures.append(
                "every_required_target_is_declared: TARGETS no longer covers "
                + ", ".join(sorted(target_gaps))
                + ". Everything packaged must be scanned uncompressed — dropping a target "
                "leaves a component in the bundle that nothing reads."
            )

        # --- the ENCODING set has not shrunk either ---------------------------------------
        cases += 1
        missing_enc = REQUIRED_ENCODINGS - set(ENCODINGS)
        if missing_enc:
            failures.append(
                "every_encoding_is_declared: ENCODINGS lost "
                + ", ".join(sorted(missing_enc))
                + ". Dropping an encoding shrinks every injection case and the positive control "
                "silently -- the suite would still pass while covering less."
            )
        # And the needle FLOOR, so the "12 needles" the verification story leans on is a
        # measured number rather than an assertion in a comment.
        cases += 1
        probes = len(needles(SIGNATURES))
        floor = len(REQUIRED_SIGNATURES) * len(REQUIRED_ENCODINGS)
        if probes < floor:
            failures.append(
                f"needle_floor: the scan builds {probes} needles, below the required {floor} "
                f"({len(REQUIRED_SIGNATURES)} signatures x {len(REQUIRED_ENCODINGS)} encodings)."
            )

        # --- the declared set has not shrunk --------------------------------------------
        cases += 1
        declared = {text for text, _why in SIGNATURES}
        missing = REQUIRED_SIGNATURES - declared
        if missing:
            failures.append(
                "required_signatures_are_declared: the set lost " + ", ".join(sorted(missing))
            )

        # --- every signature, in every encoding, is caught when injected ----------------
        # NOT just the first entry: a set where only one member is verified is a set whose
        # rest is decoration.
        for text, _why in SIGNATURES:
            for enc in ENCODINGS:
                cases += 1
                slug = f"{abs(hash((text, enc)))}"
                p = _artefact(root / f"hot-{slug}" / "selahcue-operator.exe", text.encode(enc))
                complaint, exc = _expect_red(
                    lambda: scan(_targets(f"hot-{slug}/selahcue-operator.exe")),
                    f"injected_signature_is_caught[{text}/{enc}]",
                )
                if complaint:
                    failures.append(complaint)
                    continue
                # The failure must NAME the artefact and the string. A gate that goes red
                # without saying which file and which signature sends the reader hunting.
                reported = str(exc) + "".join(poison_log)
                if str(p) not in reported or text not in reported:
                    failures.append(
                        f"failure_message[{text}/{enc}]: the failure named "
                        f"{'the path' if str(p) in reported else 'NO path'} and "
                        f"{'the string' if text in reported else 'NO string'}"
                    )

        # --- "I read no artefact" is a FAILURE, not a pass ------------------------------
        cases += 1
        c, _exc = _expect_red(
            lambda: scan(_targets("does/not/exist/selahcue-operator.exe")), "missing_target"
        )
        if c:
            failures.append(c)

        cases += 1
        c, _exc = _expect_red(lambda: scan(_targets("clean/*-setup.exe")), "glob_matches_nothing")
        if c:
            failures.append(c)

        # This case asserts the MESSAGE, not merely that something went red. A mutation
        # battery caught it reading the wrong mechanism: with the `is_file()` guard deleted
        # the directory still failed — at the read, with a different error — so the case
        # stayed green and vouched for a guard that was gone. Consuming the guard's own
        # verdict is what makes it bite.
        cases += 1
        (root / "adir" / "selahcue-operator.exe").mkdir(parents=True, exist_ok=True)
        c, exc = _expect_red(
            lambda: scan(_targets("adir/selahcue-operator.exe")), "target_is_a_directory"
        )
        if c:
            failures.append(c)
        elif "is not a regular file" not in str(exc):
            failures.append(
                "target_is_a_directory: the run failed, but NOT via the is_file() guard "
                f"(got: {str(exc)[:100]}). The guard this case names may be gone."
            )

        # --- an unreadable artefact is not a clean artefact ------------------------------
        # Skipped LOUDLY where the platform does not enforce the mode (Windows, or running as
        # root), rather than silently passing and inflating the case count.
        unreadable = _artefact(root / "locked" / "selahcue-operator.exe")
        os.chmod(unreadable, 0o000)
        enforced = True
        try:
            with unreadable.open("rb") as fh:
                fh.read(1)
        except OSError:
            pass
        else:
            enforced = False
        if enforced:
            cases += 1
            c, _exc = _expect_red(lambda: scan(_targets("locked/selahcue-operator.exe")), "unreadable_file")
            if c:
                failures.append(c)
        else:
            print("   unreadable_file: SKIPPED — this platform/user ignores mode 000 "
                  "(the directory case above covers the same fail-closed branch)")
        os.chmod(unreadable, 0o644)

        # --- a zero-byte or truncated artefact is not a clean artefact -------------------
        cases += 1
        (root / "empty").mkdir(parents=True, exist_ok=True)
        (root / "empty" / "selahcue-operator.exe").write_bytes(b"")
        c, _exc = _expect_red(lambda: scan(_targets("empty/selahcue-operator.exe")), "zero_byte_artefact")
        if c:
            failures.append(c)

        cases += 1
        _artefact(root / "small" / "selahcue-operator.exe", size=1024)
        c, _exc = _expect_red(lambda: scan(_targets("small/selahcue-operator.exe")), "undersized_artefact")
        if c:
            failures.append(c)

        # --- emptying or trimming the string list must go RED ----------------------------
        cases += 1
        c, _exc = _expect_red(
            lambda: scan(_targets("clean/selahcue-operator.exe"), ()), "empty_signature_set"
        )
        if c:
            failures.append(c)

        cases += 1
        # The victim is DERIVED, not named. This case used to hardcode `api.deepgram.com` --
        # the exact row the expiry note above instructs a future maintainer to delete -- so
        # following that instruction broke this case and made the "it is a data change" claim
        # false. Any single required row can now be removed without repointing this.
        victim = sorted(REQUIRED_SIGNATURES)[0]
        trimmed = tuple(s for s in SIGNATURES if s[0] != victim)
        c, _exc = _expect_red(
            lambda: scan(_targets("clean/selahcue-operator.exe"), trimmed), "shrunken_signature_set"
        )
        if c:
            failures.append(c)

        cases += 1
        c, _exc = _expect_red(lambda: scan((), SIGNATURES), "no_targets_declared")
        if c:
            failures.append(c)

        # --- IF THE POSITIVE CONTROL DOES NOT FIRE, THE BUILD FAILS ----------------------
        # Mutation, executed: replace the matcher with one that finds nothing and confirm the
        # control refuses to certify the artefact. Without this case, "the positive control
        # protects us" would itself be an untested claim.
        cases += 1
        real_scan_file = globals()["scan_file"]
        globals()["scan_file"] = lambda path, signatures: []
        try:
            c, _exc = _expect_red(
                lambda: scan(_targets("clean/selahcue-operator.exe")), "dead_matcher_fails_closed"
            )
            if c:
                failures.append(c)
        finally:
            globals()["scan_file"] = real_scan_file

        # --- H2: the positive control verifies EVERY signature, not just the first --------
        # `dead_matcher_fails_closed` kills the matcher entirely, so it cannot tell "verifies
        # 12 pairs" from "verifies 1". This one can: the matcher is made to report only the
        # FIRST needle it finds. A control that checked `probes[:1]` would be satisfied and go
        # green; the real one must notice the other eleven are unaccounted for.
        cases += 1
        _real_sf = globals()["scan_file"]
        globals()["scan_file"] = lambda path, signatures: _real_sf(path, signatures)[:1]
        try:
            c, exc = _expect_red(
                lambda: scan(_targets("clean/selahcue-operator.exe")),
                "positive_control_covers_every_signature",
            )
            if c:
                failures.append(
                    "positive_control_covers_every_signature: the control accepted a matcher "
                    "that reported ONE signature-encoding pair out of "
                    f"{len(needles(SIGNATURES))}. Its own docstring calls a set where only the "
                    "first entry is verified 'a set whose rest is decoration' — that is "
                    "currently what it is."
                )
            elif "POSITIVE CONTROL FAILED" not in str(exc):
                failures.append(
                    "positive_control_covers_every_signature: went red, but not via the "
                    f"positive control (got: {str(exc)[:100]})"
                )
        finally:
            globals()["scan_file"] = _real_sf

        # --- a signature straddling a chunk boundary is still found ----------------------
        # Without the overlap in scan_file, this scan would have a silent blind spot every
        # CHUNK bytes. CHUNK is shrunk here so the case is fast rather than 8 MiB of I/O.
        # Two things the previous version got wrong, both caught in review:
        #   * it re-spelled the chunk size as a bare `512` beside `globals()["CHUNK"] = 512`,
        #     so the placement was a COPY of the value under test and an unrelated edit could
        #     silently disarm it;
        #   * it used a SHORT needle and pinned only that an overlap EXISTS, not that it is big
        #     enough. `overlap = max - 2` survived it, and that is a real blind spot: the
        #     longest needle placed at exactly CHUNK - len + 1 straddles by the maximum and is
        #     missed entirely.
        # Both the chunk size and the needle are now derived from what is under test.
        cases += 1
        real_chunk = globals()["CHUNK"]
        probe_chunk = 512
        globals()["CHUNK"] = probe_chunk
        try:
            longest, longest_text, longest_enc = max(
                needles(SIGNATURES), key=lambda probe: len(probe[0])
            )
            # The single worst placement: one byte of the needle lands in the first chunk, so
            # only an overlap of at least len-1 can recover it.
            prefix = probe_chunk - len(longest) + 1
            straddle = root / "boundary" / "selahcue-operator.exe"
            straddle.parent.mkdir(parents=True, exist_ok=True)
            straddle.write_bytes(
                b"\xcc" * prefix + longest + b"\xcc" * (probe_chunk * 2)
            )
            hits = real_scan_file(straddle, SIGNATURES)
            if not any(t == longest_text and e == longest_enc for t, e, _o in hits):
                failures.append(
                    "signature_across_a_chunk_boundary_is_found: MISSED the longest needle "
                    f"(`{longest_text}` / {longest_enc}, {len(longest)} bytes) placed at "
                    f"offset {prefix} of a {probe_chunk}-byte chunk. The overlap in scan_file "
                    f"is smaller than the longest needle, so this scan has a blind spot every "
                    f"CHUNK bytes."
                )
        finally:
            globals()["CHUNK"] = real_chunk

        # --- NON-TRUNCATION: the gate reads artefacts; it must never write to one ---------
        # The positive control APPENDS signature bytes. If it ever did that in place instead of
        # to a copy, it would corrupt the artefact we ship — and, at the path below, an
        # owner-supplied file that cannot be regenerated. Create-only/read-only is the entire
        # safety mechanism, and a read-only implementation and a mutating one are
        # indistinguishable until the day the file matters. So: put a NON-EMPTY file at that
        # exact path, run the whole gate over it, and assert size, digest and bytes unchanged.
        cases += 1
        precious = root / "precious" / "Processing.NDI.Lib.x64.dll"
        _artefact(precious, b"owner-supplied payload that cannot be regenerated")
        before_bytes = precious.read_bytes()
        before = (len(before_bytes), hashlib.sha256(before_bytes).hexdigest())
        try:
            scan(_targets("precious/Processing.NDI.Lib.x64.dll"))
        except ScanError as exc:
            failures.append(f"scan_never_mutates_the_artefact: gate failed unexpectedly: {exc}")
        after_bytes = precious.read_bytes()
        after = (len(after_bytes), hashlib.sha256(after_bytes).hexdigest())
        if after != before or after_bytes != before_bytes:
            failures.append(
                "scan_never_mutates_the_artefact: the artefact CHANGED across the scan "
                f"({before} -> {after}). The positive control must build its fixture from a "
                "COPY; writing, appending or truncating in place destroys what we ship."
            )

        quiet.close()

    # The last unguarded collection in this file: the suite's own case count. Deleting a whole
    # case block lowers the total and the run stays green, which is this pattern one final level
    # up. Raise this floor when cases are added; it is only ever allowed to go up.
    if cases < SELF_TEST_CASE_FLOOR:
        failures.append(
            f"self_test_case_floor: ran {cases} cases, floor is {SELF_TEST_CASE_FLOOR}. "
            "A case block was removed — restore it or lower the floor deliberately."
        )

    if failures:
        print("installer_secret_scan self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"installer_secret_scan self-test: {cases} cases passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--self-test", action="store_true", help="exercise this gate's own failure modes"
    )
    ap.add_argument("--root", default=None, help="repository root (default: this script's parent)")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    root = pathlib.Path(args.root) if args.root else pathlib.Path(__file__).resolve().parent.parent
    # Checked on the DEPLOYED table, which the self-test never touches: every self-test case
    # drives run_scan() with synthetic targets, so this cannot live inside run_scan() without
    # breaking all of them. Without it, deleting a row from TARGETS left the gate reporting OK
    # on whatever remained.
    gaps = declared_target_gaps(TARGETS)
    if gaps:
        print(
            "INSTALLER SECRET SCAN FAILED: TARGETS no longer covers "
            + ", ".join(sorted(gaps))
            + ". Everything packaged must be scanned uncompressed; a dropped target leaves a "
            "bundled component that nothing reads.",
            file=sys.stderr,
        )
        return 1
    try:
        run_scan(root, TARGETS, SIGNATURES)
    except ScanError as exc:
        print(f"INSTALLER SECRET SCAN FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
