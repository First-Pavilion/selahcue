# P04 scanner review correction — Q-P04-03

Ticket: https://app.clickup.com/t/17tnw2bbhwz . PR340. Original reviewed head b6f4b852a086175db94b338b1adf7910a11c2870, main/base4e2ce4374713956a498978fdf6383c74c2c548cb.

## Scope and authorization

The current delivery request authorizes MR fixes. Root explicitly extended the existing Goal Contract from maximum5to6 before coding, solely for confirmed recursive-inventory defect Q-P04-03. Original criteria/ledgers remain. No native hooks, extraction driver, packaging, real credentials or provider calls were added.

## RED observed

On Python3.9.6/macOS as the normal user, `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_pilot_installer_scan.py` ran33controls and failed2. The actual task-owned mode000 unlisted-directory test failed because `PolicyError` was not raised; `rglob` omitted the hidden extra member. The deterministic recursive-enumeration refusal expected `package-unreadable` but observed `package-inventory`. Permissions were restored0700 in finally and the owned temporary tree was cleaned up.

## Correction and GREEN observed

`verify_inventory` now enumerates through explicit streaming depth-first `os.scandir`; errors are no longer swallowed by pathlib. The existing error handler converts recursive OSError to fixed `package-unreadable` with suppressed context. The consumer validates time, symlink, depth, file-count, bytes, hash and unchanged metadata before descent/acceptance. No list of directory entries is buffered; recursion is bounded by the existing16component depth limit.

Executed affected suites after the correction:

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_pilot_installer_scan.py`:33passed,0skipped. Actual permission regression and deterministic recursive syscall refusal both passed. With readable traversal, the extra file is refused; removing it returns the exact expected inventory. Full rendered exception excludes every8character private-canary fragment.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_pilot_asset_provenance.py`:15passed,0skipped.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/installer_secret_scan.py --self-test`:45passed; legacy scanner source unchanged.
- Goal Contract structural validation and `git diff --check`:passed.

These are local source checks, not an independent review or native/installer execution. Whole C002 native retention, C004 produced-installer proof, C005 actual provider approval remain BLOCKED; C006 four current reviews/exact-head CI pending root coordination. No ticket transition or main merge performed.
