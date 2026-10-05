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
#     so it names the problem; it does not prevent the crash. Observed on a throwaway run
#     (run 37245715215, attempt 2: the after-clippy check with its floor set to 100000 GB):
#     only that step went red, every later gate step still ran, the job-end step ran, and
#     the macOS and Windows legs were unaffected. That a red check step would also survive an
#     actual runner crash is inferred from the successful steps that did; it was not tested.
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
# 5.8 GB, ghcup 3.7 GB, CodeQL 1.4 GB, together 21.7 GB. The step takes about 40 to 90
# seconds (42, 78, 81 and 87 s on four runs; the deletion is most of it). Left alone, with
# their sizes, in case the list ever has to grow: /usr/share/swift 3.5 GB, hostedtoolcache
# Python 1.6 GB, /usr/lib/jvm 1.5 GB, julia 1.1 GB, docker images 1.9 GB, Go 0.8 GB.
#
# WHEN IT RUNS: ONLY ON A SMALL RUNNER. After the guards below, `free` measures free space
# on / and SKIPS the deletion ("skipped: N GB free on /, at or above the M GB threshold;
# nothing deleted", exit 0) when it is at or above CI_DISK_SKIP_FREE_AT_GB (whole GB, default
# 40). Below it, `free` behaves as it always did. Why 40, from the logged figures: the job
# writes about 16.4 GB and is growing; the check floors need 10 GB free at the two early
# checkpoints (the first is after 4.3 GB written, the second after 4.6) and 5 GB at the two
# later ones (14.7 GB written), so a runner needs about 19.7 GB at the start to pass every
# floor, and about 26.4 GB to end with the 10 GB job-end warning silent. The pool that failed
# on 2026-10-04 had 13.3 GB free at the start (below every one of those figures; freeing
# 21.7 GB gave 35.0 GB and the job ended with 18.6 GB); the pool seen on 2026-10-05 has
# 86.0 GB free. 40 GB is the 26.4 GB above plus 13.6 GB (83 percent of what the job writes
# today) of growth, so a runner at or above it finishes with the warning silent even after
# the job has grown by four fifths. Below 40 GB the deletion runs as MARGIN, not because the
# job is bound to fail: a runner with 26.4 to 40 GB free passes today without it. When the
# deletion does run, it emits a `::warning title=small runner` naming the free space and the
# threshold, so a pool that shrank shows on the Checks page and not only in the log.
#
# CONSEQUENCE, stated plainly: on today's runners (86 GB free) the deletion does not run in
# CI at all. It was proven on real runners on 2026-10-04 (freed 21.7 GB; runs 37241095086 and
# 37243123097) and in container tests with fake directories. It matters again only if the
# pool shrinks; until then the check floors and the job-end warning are the early warning.
#
# The skip comes AFTER every guard, never before: a skip taken before the guards would make
# the guards untestable (the skip would win) and a mistake in it could not be told from a
# working guard. Nothing is deleted on any path that reaches the skip.
#
# Usage:
#   ci_disk.sh report <label>   print free space, inodes and the big build directories, then
#                               the same figures as one annotation. Never fails.
#   ci_disk.sh check <label>    report, then exit 1 if free space on / is below the floor
#                               CI_DISK_MIN_FREE_GB (whole GB, default 5)
#   ci_disk.sh end <label>      report, warn below CI_DISK_WARN_FREE_GB (whole GB, default
#                               10), append one summary line. Never fails.
#   ci_disk.sh free             report; then, only if free space on / is below
#                               CI_DISK_SKIP_FREE_AT_GB (whole GB, default 40), delete the
#                               unused preinstalled software and report again
#
# `free` DELETES SYSTEM DIRECTORIES, so it refuses (exit 2, deletes nothing) unless it is on a
# GitHub-HOSTED runner: GITHUB_ACTIONS=true AND RUNNER_ENVIRONMENT=github-hosted. Either
# variable alone is not enough: self-hosted runners and `act` also set GITHUB_ACTIONS=true.
# It does nothing on a non-Linux runner. A developer who runs it on their own machine must
# not lose their Android SDK. If RUNNER_ENVIRONMENT were ever absent on a hosted runner the
# step would fail, and the setup steps after it (toolchain install, pin check, cache restore)
# would be skipped; every gate step still runs under `!cancelled()`, without the pin check.
# The guards sit before the skip, so on a big runner that would turn a job red where nothing
# would have been deleted. That is deliberate (the guards come first, always), and the
# variable is seen set on hosted runners. The log prints the value the guard saw.
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
skip_free_at_gb="${CI_DISK_SKIP_FREE_AT_GB:-40}"

# A floor that is not a whole number would be read differently by dash and by bash (a value
# of -1 would silently switch the check off), so refuse it up front. A leading zero is
# refused too (except the value 0 itself): shell arithmetic reads 0400 as octal 256, and 09
# aborts `end`, which must never fail. At most 9 digits, so the GB to KB arithmetic below
# cannot overflow.
for setting in "CI_DISK_MIN_FREE_GB=$min_free_gb" "CI_DISK_WARN_FREE_GB=$warn_free_gb" \
               "CI_DISK_SKIP_FREE_AT_GB=$skip_free_at_gb"; do
    value=${setting#*=}
    case "$value" in
        '' | *[!0-9]* | 0?*)
            echo "ci_disk: ${setting%%=*} must be a whole number of GB, 0 or more, with no leading zero; got '$value'." >&2
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

# Free space on a path in KB, or 0 if df cannot say. Anything that is not a whole number
# counts as 0 too, so a caller's `[ ... -ge ... ]` never meets a non-number: a broken
# measurement reads as "no space", which is the safe direction for every caller (the skip does
# not skip, `check` fails, `end` warns).
avail_kb() {
    out=$(df -Pk "$1" 2>/dev/null | awk 'NR==2 { print $4 }')
    case "$out" in
        '' | *[!0-9]*) echo 0 ;;
        *) echo "$out" ;;
    esac
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
        echo "::warning title=low disk headroom ($label)::only $free_gb GB free on / at the end of the job, below the $warn_free_gb GB warning level. This step runs even in a failed job; the runner is getting close to running out of disk"
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
    #
    # KEEP THE NEXT LINE'S FORM (one line, four spaces of indent, `doomed="..."`): the
    # "Disk script contract" step in .github/workflows/ci.yml reads the list from it, by
    # that exact shape, to check that a refused or skipped `free` deleted none of these. If
    # the line changes shape the step fails loudly ("could not read the deletion list").
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
            */ | */. | */./* | */.. | */../* | *//*)
                # `//usr` matches /*/* above and rm treats it as /usr: one component.
                refuse_path "$d" "has a trailing slash, an empty segment (//) or a dot segment"
                ;;
        esac
    done

    report "job start before freeing"
    before=$(avail_kb /)

    # THE SKIP. It sits after every guard and after the path-shape check above (so a bad list
    # is refused on every run, even one where nothing would be deleted), and before the first
    # deletion. If df cannot say, or prints something that is not a whole number, avail_kb
    # returns 0: the runner counts as small and `free` goes ahead (at a threshold of 0 it
    # skips, 0 being at or above 0). It has passed the hosted-runner guards, and the deletion
    # is the safe direction for the job.
    skip_kb=$((skip_free_at_gb * 1048576))
    if [ "$before" -ge "$skip_kb" ]; then
        set +f
        echo "skipped: $(avail_gb /) GB free on /, at or above the $skip_free_at_gb GB threshold; nothing deleted"
        return 0
    fi
    # The deletion is about to run, so the runner is below the threshold: say so as an
    # annotation (never a failure), so a pool that shrank is not silent.
    echo "::warning title=small runner::only $(avail_gb /) GB free on / at job start, below the $skip_free_at_gb GB threshold: deleting preinstalled software to make room. The runner pool may have shrunk"

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
