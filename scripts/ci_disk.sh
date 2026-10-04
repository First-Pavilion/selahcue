#!/bin/sh
# Disk-space tooling for the hosted Linux runner (ClickUp 17tnw2b2k23).
#
# WHY THIS EXISTS. From about 21:00 UTC on 2026-10-04 `rust (ubuntu-latest)` failed on every
# run, with the same code, the same runner image and the same Rust cache that had passed an
# hour earlier: the runner's disk filled up (the check-run annotation reads "System.IO.
# IOException: No space left on device" against the runner agent's own _diag log). A runner
# that cannot write its own log cannot upload the step logs either, so the logs of every
# failed run are gone (GitHub answers BlobNotFound) and there was nothing to read the cause
# from. Two things follow, and this script is both of them:
#
#   1. The job must print where the disk stands as it goes, and ALSO as annotations
#      (`::notice`), because annotations are sent from memory and survive a full disk where
#      the log blob does not. A future failure is then readable instead of silent.
#   2. The job must start with enough headroom. A hosted ubuntu runner ships with tens of
#      GB of toolchains this repo never touches (Android SDK, .NET, GHC, CodeQL), sitting on
#      the same disk the Rust build writes to. `free` deletes them before the build starts.
#
# Usage:
#   ci_disk.sh report <label>   print free space, inodes and the big build directories, then
#                               the same figures as one annotation
#   ci_disk.sh free             report, delete the unused preinstalled software, report again
#
# `report` only reads. `free` DELETES SYSTEM DIRECTORIES, so it refuses to run anywhere but a
# GitHub Actions runner (GITHUB_ACTIONS=true) and does nothing on a non-Linux runner: a
# developer who runs it on their own machine must not lose their Android SDK.
#
# Neither command ever fails the job: this is instrumentation and housekeeping, and a
# diagnostic that turns a green build red has the wrong priorities. (`free` refusing to run
# outside Actions is the one non-zero exit, and that is a misuse, not a runner condition.)
set -u

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target_dir="$root/implementation/desktop/target"
cargo_home="${CARGO_HOME:-$HOME/.cargo}"
rustup_home="${RUSTUP_HOME:-$HOME/.rustup}"

# Free space on a path in GB with one decimal, or "n/a" if df cannot say.
avail_gb() {
    out=$(df -Pk "$1" 2>/dev/null | awk 'NR==2 { printf "%.1f", $4 / 1048576 }')
    echo "${out:-n/a}"
}

# Free space on a path in KB, or 0 if df cannot say.
avail_kb() {
    out=$(df -Pk "$1" 2>/dev/null | awk 'NR==2 { print $4 }')
    echo "${out:-0}"
}

# Size of a path as `du -sh` prints it, or "absent".
size_of() {
    if [ -e "$1" ]; then
        du -sh "$1" 2>/dev/null | awk '{ print $1 }'
    else
        echo absent
    fi
}

report() {
    label=$1
    echo "=== disk space: $label ==="
    df -h / /mnt "$root" 2>/dev/null
    echo "--- inodes on /"
    df -Pi / 2>/dev/null
    echo "--- build directories"
    for p in "$target_dir" "$cargo_home/registry" "$cargo_home/git" "$rustup_home/toolchains" \
             "${RUNNER_TEMP:-/nonexistent}"; do
        [ -e "$p" ] && du -sh "$p" 2>/dev/null
    done
    # One line, no percent sign (the workflow-command parser decodes it). Annotations are
    # posted from memory, so this survives a disk too full to upload the step log.
    echo "::notice title=disk space ($label)::free on / $(avail_gb /) GB, on /mnt $(avail_gb /mnt) GB, target dir $(size_of "$target_dir")"
    return 0
}

free_space() {
    if [ "${GITHUB_ACTIONS:-}" != "true" ]; then
        echo "ci_disk: 'free' deletes system directories and only runs on a GitHub Actions runner." >&2
        exit 2
    fi
    if [ "$(uname -s)" != "Linux" ]; then
        echo "ci_disk: nothing to free on $(uname -s); the preinstalled-software problem is the Linux image's."
        exit 0
    fi

    report "job start before freeing"
    before=$(avail_kb /)

    # Preinstalled software this repo never uses. Each is a directory on the image that the
    # Rust build has no business with: the Android SDK/NDK (the mobile job is separate and
    # uses its own setup), .NET, the Haskell toolchain (two spellings, by image generation)
    # and the CodeQL bundles. Sizes are printed BEFORE deleting so the next person tuning
    # this list has the numbers.
    doomed="/usr/local/lib/android /usr/share/dotnet /opt/ghc /usr/local/.ghcup /opt/hostedtoolcache/CodeQL"
    echo "--- preinstalled software removed by this step (size before deleting)"
    for d in $doomed; do
        if [ -e "$d" ]; then
            sudo du -sh "$d" 2>/dev/null
        else
            echo "absent  $d"
        fi
    done
    echo "--- left alone, listed for reference (size)"
    sudo du -sh /opt/hostedtoolcache/* /usr/share/swift /usr/local/share/boost /usr/lib/jvm \
        /usr/local/julia* /usr/local/share/chromium /opt/microsoft /opt/az 2>/dev/null
    echo "--- docker images (left alone)"
    docker system df 2>/dev/null

    for d in $doomed; do
        if [ -e "$d" ]; then
            sudo rm -rf "$d" &
        fi
    done
    wait

    after=$(avail_kb /)
    freed_gb=$(awk -v a="$after" -v b="$before" 'BEGIN { printf "%.1f", (a - b) / 1048576 }')
    echo "freed $freed_gb GB on /"
    report "job start after freeing"
    # A free that frees nothing (the image dropped these paths, say) must say so out loud,
    # not leave the next failure to be read as a mystery again.
    if [ "${after:-0}" -lt 20971520 ]; then
        echo "::warning title=low disk after freeing::only $(avail_gb /) GB free on / after freeing preinstalled software ($freed_gb GB freed); the Rust build may not fit"
    fi
    return 0
}

case "${1:-}" in
    report)
        report "${2:-unlabelled}"
        ;;
    free)
        free_space
        ;;
    *)
        echo "usage: ci_disk.sh report <label> | ci_disk.sh free" >&2
        exit 2
        ;;
esac
