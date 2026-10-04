#!/bin/sh
# Disk-space tooling for the hosted Linux runner (ClickUp 17tnw2b2k23).
#
# WHY THIS EXISTS. From about 21:00 UTC on 2026-10-04 `rust (ubuntu-latest)` failed on every
# run, with the same code, the same runner image and the same Rust cache that had passed an
# hour earlier. Measured on 2026-10-04 (image ubuntu-24.04 20260927.320.1, runner agent
# 2.337.0): the runner has ONE 72 GB disk (/mnt is not a separate volume), 59 GB of it already
# used by the image, so 13.3 GB free. The job writes about 16.4 GB (the Rust `target` dir
# grows 3.3 GB after the cache restore, 11 GB after the workspace tests, 14 GB after the LAN
# and app server tests, 16 GB at the end), so it runs out of disk about 14.7 GB in -- inside
# the "LAN server + app server features" step, exactly where every failed run died.
#
# WHAT A FULL DISK DESTROYS. The runner agent writes its own log to the same disk. When that
# write fails the agent crashes ("System.IO.IOException: No space left on device" against
# its _diag log) and, verified on a control run: the step logs are never uploaded (GitHub
# answers BlobNotFound for the whole job), and the `::notice` annotations this script prints
# are lost with them. What DOES survive is each step's name and result for every step that
# finished before the crash. So the instrumentation here works in two ways:
#
#   - `report` and `check` print where the disk stands, for the runs that do not crash
#     (the log, plus an annotation, at each checkpoint).
#   - `check` also FAILS its own step when free space is below a floor, while there is still
#     room to write. A red "Disk space ..." step before the crash is what the next person
#     sees, instead of an unreadable crash two steps later.
#
# And the fix itself: `free` deletes the preinstalled software this repo never uses (Android
# SDK, .NET, GHC, CodeQL) before anything is built. Sizes on that image: Android 11 GB, .NET
# 5.8 GB, ghcup 3.7 GB, CodeQL 1.4 GB, together 21.7 GB freed in about 40 seconds. Left alone,
# with their sizes, in case the list ever has to grow: /usr/share/swift 3.5 GB, hostedtoolcache
# Python 1.6 GB, /usr/lib/jvm 1.5 GB, julia 1.1 GB, docker images 1.9 GB, Go 0.8 GB.
#
# Usage:
#   ci_disk.sh report <label>   print free space, inodes and the big build directories, then
#                               the same figures as one annotation. Never fails.
#   ci_disk.sh check <label>    report, then exit 1 if free space on / is below the floor
#                               (CI_DISK_MIN_FREE_GB, default 5: the largest remaining step
#                               after the workspace tests adds about 3 GB)
#   ci_disk.sh free             report, delete the unused preinstalled software, report again
#
# `free` DELETES SYSTEM DIRECTORIES, so it refuses to run anywhere but a GitHub Actions runner
# (GITHUB_ACTIONS=true) and does nothing on a non-Linux runner: a developer who runs it on
# their own machine must not lose their Android SDK. `report` only reads and never fails the
# job: instrumentation that turns a green build red has the wrong priorities. `check` is the
# one deliberate failure, and only in the case where the job is about to die anyway.
set -u

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target_dir="$root/implementation/desktop/target"
cargo_home="${CARGO_HOME:-$HOME/.cargo}"
rustup_home="${RUSTUP_HOME:-$HOME/.rustup}"
min_free_gb="${CI_DISK_MIN_FREE_GB:-5}"

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
    df -h /
    # Say out loud whether /mnt is a second volume: on the 2026-10-04 runners it is not, so
    # pointing CARGO_TARGET_DIR at /mnt adds no space there.
    root_dev=$(df -P / 2>/dev/null | awk 'NR==2 { print $1 }')
    mnt_dev=$(df -P /mnt 2>/dev/null | awk 'NR==2 { print $1 }')
    if [ -n "$mnt_dev" ] && [ "$mnt_dev" != "$root_dev" ]; then
        df -h /mnt
    else
        echo "/mnt is not a separate volume (same device as /, or absent)"
    fi
    echo "--- inodes on /"
    df -Pi /
    echo "--- build directories"
    for p in "$target_dir" "$cargo_home/registry" "$cargo_home/git" "$rustup_home/toolchains" \
             "${RUNNER_TEMP:-/nonexistent}"; do
        [ -e "$p" ] && du -sh "$p" 2>/dev/null
    done
    # One line, no percent sign (the workflow-command parser decodes it).
    echo "::notice title=disk space ($label)::free on / $(avail_gb /) GB, target dir $(size_of "$target_dir")"
    return 0
}

check() {
    label=$1
    report "$label"
    free_kb=$(avail_kb /)
    floor_kb=$((min_free_gb * 1048576))
    if [ "$free_kb" -lt "$floor_kb" ]; then
        echo "::error title=disk almost full ($label)::only $(avail_gb /) GB free on /, below the $min_free_gb GB floor. The next build step can fill the disk and crash the runner, which loses the step logs"
        echo "ci_disk: only $(avail_gb /) GB free on /, below the $min_free_gb GB floor (CI_DISK_MIN_FREE_GB)." >&2
        return 1
    fi
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

    # Preinstalled software this repo never uses: the Android SDK/NDK (the mobile job is
    # separate and sets up its own), .NET, the Haskell toolchain (two spellings, by image
    # generation) and the CodeQL bundles. Deleted in parallel.
    doomed="/usr/local/lib/android /usr/share/dotnet /opt/ghc /usr/local/.ghcup /opt/hostedtoolcache/CodeQL"
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
    # not leave the next failure to be read as a mystery again. 20 GB = the 16.4 GB the job
    # was measured to write, plus headroom.
    if [ "${after:-0}" -lt 20971520 ]; then
        echo "::warning title=low disk after freeing::only $(avail_gb /) GB free on / after freeing preinstalled software ($freed_gb GB freed); the Rust build wrote 16.4 GB when measured"
    fi
    return 0
}

case "${1:-}" in
    report)
        report "${2:-unlabelled}"
        ;;
    check)
        check "${2:-unlabelled}"
        ;;
    free)
        free_space
        ;;
    *)
        echo "usage: ci_disk.sh report <label> | ci_disk.sh check <label> | ci_disk.sh free" >&2
        exit 2
        ;;
esac
