#!/bin/sh
# Disk-space tooling for the hosted Linux runner (ClickUp 17tnw2b2k23).
#
# WHY THIS EXISTS. From about 21:00 UTC on 2026-10-04 `rust (ubuntu-latest)` failed on every
# run, with the same code, the same runner image and the same Rust cache that had passed an
# hour earlier. Measured on 2026-10-04 (image ubuntu-24.04 20260927.320.1, runner agent
# 2.337.0): the runner has ONE 72 GB disk (/mnt is not a separate volume), 59 GB of it already
# used by the image, so 13.3 GB free. The job writes about 16.4 GB in all: the Rust `target`
# dir is 3.3 GB after the cache restore, 11 GB after the workspace tests, 14 GB after the LAN
# and app server tests and 16 GB at the end. Counted from the 35.0 GB free measured after
# freeing, the workspace tests end at 11.7 GB written and the LAN and app server tests at
# 14.7 GB written. So a disk with 13.3 GB free is full after 13.3 GB written, which falls
# inside the LAN and app server step (it spans 11.7 to 14.7 GB written): exactly where every
# failed run died.
#
# WHAT A FULL DISK DESTROYS. The runner agent writes its own log to the same disk. When that
# write fails the agent crashes ("System.IO.IOException: No space left on device" against
# its _diag log). Observed on a control run (37242363893): the step logs are never uploaded
# (GitHub answers BlobNotFound for the whole job) and the `::notice` annotations this script
# prints are lost with them. What was observed to survive is the name and result of every
# step that finished successfully before the crash. So the instrumentation works two ways:
#
#   - `report`, `check` and `end` print where the disk stands, for the runs that do not
#     crash: the log, plus an annotation, at each checkpoint.
#   - `check` is a HEADROOM ALARM. It fails its own step when free space on / is below a
#     floor, while there is still room to write, so the next disk problem is a red,
#     named "Disk space ..." step ahead of the crash and not an unreadable crash two steps
#     later. A red check does not stop the steps after it (they run under `!cancelled()`),
#     so it names the problem; it does not prevent the crash.
#
# FLOORS. Each checkpoint has its own floor (env CI_DISK_MIN_FREE_GB, default 5), set in the
# workflow from what the step AFTER the checkpoint writes. Measured, GB written between
# checkpoints: cache restore to after clippy 0.3; after clippy to after the workspace tests
# 7.1 (the workspace test step alone); after the workspace tests to after the LAN and app
# server tests 3.0 (five steps); after those to job end 1.7. Healthy runs show 30.7 GB free
# before the gates, 30.4 after clippy, 23.3 after the workspace tests and 20.3 after the LAN
# step. So the two early checks use 10 GB (above the 7.1 GB the next step writes, with 2.9 GB
# to spare, and 20 GB under a healthy reading) and the two later ones use 5 GB (above the 3.0
# and 1.7 GB still to come). A run that reaches a check with less than its floor has no
# margin for what follows, even if the next step might just squeeze through.
#
# EARLY WARNING. `end` runs at job end and never fails: it prints the report, emits a
# `::warning` when free space on / is below CI_DISK_WARN_FREE_GB (default 10; the healthy end
# reading is 18.6 GB) and appends one line (free GB, target dir size, runner image) to
# $GITHUB_STEP_SUMMARY so the trend can be read run to run.
#
# THE FIX ITSELF. `free` deletes the preinstalled software this repo never uses (Android SDK,
# .NET, GHC, CodeQL) before anything is built. Sizes on that image: Android 11 GB, .NET
# 5.8 GB, ghcup 3.7 GB, CodeQL 1.4 GB, together 21.7 GB. The step takes about 80 seconds
# (77 to 81 s on both runners measured; the deletion alone 41 to 77 s). Left alone, with
# their sizes, in case the list ever has to grow: /usr/share/swift 3.5 GB, hostedtoolcache
# Python 1.6 GB, /usr/lib/jvm 1.5 GB, julia 1.1 GB, docker images 1.9 GB, Go 0.8 GB.
#
# Usage:
#   ci_disk.sh report <label>   print free space, inodes and the big build directories, then
#                               the same figures as one annotation. Never fails.
#   ci_disk.sh check <label>    report, then exit 1 if free space on / is below the floor
#                               CI_DISK_MIN_FREE_GB (whole GB, default 5)
#   ci_disk.sh end <label>      report, warn below CI_DISK_WARN_FREE_GB (whole GB, default
#                               10), append one summary line. Never fails.
#   ci_disk.sh free             report, delete the unused preinstalled software, report again
#
# `free` DELETES SYSTEM DIRECTORIES, so it refuses (exit 2, deletes nothing) unless it is on a
# GitHub-HOSTED runner: GITHUB_ACTIONS=true AND RUNNER_ENVIRONMENT=github-hosted. Either
# variable alone is not enough: self-hosted runners and `act` also set GITHUB_ACTIONS=true.
# It does nothing on a non-Linux runner. A developer who runs it on their own machine must
# not lose their Android SDK. If RUNNER_ENVIRONMENT were ever absent on a hosted runner the
# step fails loudly and, being in the setup zone, skips everything after it; the log prints
# the value it saw.
#
# `set -u` WITHOUT `-e` IS DELIBERATE, although the sibling scripts use `set -eu`. `report`
# and `end` must never fail the job, so a failing df, du or sudo must not abort them; `check`
# fails only through its explicit `return 1`, and `free` carries on if one deletion fails (and
# says so). Do not add `-e`.
set -u

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target_dir="$root/implementation/desktop/target"
cargo_home="${CARGO_HOME:-${HOME:-/nonexistent}/.cargo}"
rustup_home="${RUSTUP_HOME:-${HOME:-/nonexistent}/.rustup}"
min_free_gb="${CI_DISK_MIN_FREE_GB:-5}"
warn_free_gb="${CI_DISK_WARN_FREE_GB:-10}"

# A floor that is not a whole number would be read differently by dash and by bash (a value
# of -1 would silently switch the check off), so refuse it up front. At most 9 digits, so the
# GB to KB arithmetic below cannot overflow.
for setting in "CI_DISK_MIN_FREE_GB=$min_free_gb" "CI_DISK_WARN_FREE_GB=$warn_free_gb"; do
    value=${setting#*=}
    case "$value" in
        '' | *[!0-9]*)
            echo "ci_disk: ${setting%%=*} must be a whole number of GB, 0 or more; got '$value'." >&2
            exit 2
            ;;
    esac
    if [ "${#value}" -gt 9 ]; then
        echo "ci_disk: ${setting%%=*} has more than 9 digits ('$value')." >&2
        exit 2
    fi
done

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
        echo "::error title=low disk headroom ($label)::only $(avail_gb /) GB free on /, below the $min_free_gb GB floor for this checkpoint. The steps after it may fill the disk and crash the runner, which loses the step logs"
        echo "ci_disk: only $(avail_gb /) GB free on /, below the $min_free_gb GB floor (CI_DISK_MIN_FREE_GB) for checkpoint '$label'." >&2
        return 1
    fi
    return 0
}

end() {
    label=$1
    report "$label"
    free_gb=$(avail_gb /)
    free_kb=$(avail_kb /)
    warn_kb=$((warn_free_gb * 1048576))
    if [ "$free_kb" -lt "$warn_kb" ]; then
        echo "::warning title=low disk headroom ($label)::only $free_gb GB free on / at the end of the job, below the $warn_free_gb GB warning level. The job passed, but it is getting close to running out of disk"
    fi
    line="disk at $label: free $free_gb GB on /, target dir $(size_of "$target_dir"), runner image ${ImageOS:-unknown} ${ImageVersion:-unknown}"
    echo "$line"
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        echo "- $line" >> "$GITHUB_STEP_SUMMARY" 2>/dev/null || echo "ci_disk: could not write the step summary" >&2
    fi
    return 0
}

# Refuse the whole deletion list: nothing has been deleted when this is called.
refuse_path() {
    echo "ci_disk: refusing to delete anything: '$1' $2." >&2
    exit 2
}

free_space() {
    # Print what the guard sees BEFORE judging it, so a refusal can be read from the log.
    echo "ci_disk: GITHUB_ACTIONS=${GITHUB_ACTIONS:-<unset>} RUNNER_ENVIRONMENT=${RUNNER_ENVIRONMENT:-<unset>} OS=$(uname -s)"
    if [ "${GITHUB_ACTIONS:-}" != "true" ]; then
        echo "ci_disk: 'free' deletes system directories and only runs on a GitHub Actions runner." >&2
        exit 2
    fi
    if [ "${RUNNER_ENVIRONMENT:-}" != "github-hosted" ]; then
        echo "ci_disk: 'free' deletes system directories and only runs on a GitHub-hosted runner (RUNNER_ENVIRONMENT=github-hosted); saw '${RUNNER_ENVIRONMENT:-<unset>}'. Self-hosted runners and 'act' also set GITHUB_ACTIONS=true." >&2
        exit 2
    fi
    if [ "$(uname -s)" != "Linux" ]; then
        echo "ci_disk: nothing to free on $(uname -s); the preinstalled-software problem is the Linux image's."
        exit 0
    fi

    # Preinstalled software this repo never uses: the Android SDK/NDK (the mobile job is
    # separate and sets up its own), .NET, the Haskell toolchain (two spellings, by image
    # generation) and the CodeQL bundles.
    #
    # THIS LIST MUST STAY LITERAL ABSOLUTE PATHS: no variable, no command substitution, no
    # glob, no trailing slash, no space. It is checked below, and the whole list is refused if
    # any entry is not of the shape /dir/dir[/...]. An entry built from an expansion that came
    # out empty would otherwise become a path nobody meant to delete.
    doomed="/usr/local/lib/android /usr/share/dotnet /opt/ghc /usr/local/.ghcup /opt/hostedtoolcache/CodeQL"
    tab=$(printf '\t')
    set -f # no globbing while the list is split into words, so a glob character cannot expand
    for d in $doomed; do
        case "$d" in
            /*/*) ;;
            *) refuse_path "$d" "is not an absolute path with at least two components" ;;
        esac
        case "$d" in
            *" "* | *"$tab"* | *\** | *\?* | *\[* | *\]*)
                refuse_path "$d" "contains a space or a glob character"
                ;;
            */ | */. | */./* | */.. | */../*)
                refuse_path "$d" "has a trailing slash or a dot segment"
                ;;
        esac
    done

    report "job start before freeing"
    before=$(avail_kb /)

    # Deleted in parallel; each deletion is waited on by pid so a failure names its path (a
    # bare `wait` always returns 0).
    pairs=""
    for d in $doomed; do
        if [ -e "$d" ]; then
            sudo rm -rf "$d" &
            pairs="$pairs $!:$d"
        fi
    done
    for pair in $pairs; do
        pid=${pair%%:*}
        path=${pair#*:}
        if ! wait "$pid"; then
            echo "::warning title=deletion failed::could not delete $path; less disk was freed than expected"
        fi
    done
    set +f

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
    end)
        end "${2:-unlabelled}"
        ;;
    free)
        free_space
        ;;
    *)
        echo "usage: ci_disk.sh report <label> | check <label> | end <label> | free" >&2
        exit 2
        ;;
esac
