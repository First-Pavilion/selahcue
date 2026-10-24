# 17tnw2b1we2 evidence: how to reproduce the live run and the mutation results

Everything here is throwaway tooling for the Goal Contract `../17tnw2b1we2-native-signin.md`.
Nothing in this directory is built or run by `make ci`.

Files: `seed_live_api.py` (seeds a throwaway API database), `live_harness_main.rs` (the live run),
`mutate.py` (mutation runner), `run_named_tests.py` (runs named tests and fails if a name selects none).

## Live run: the real desktop client against a running API

Safety first. `seed_live_api.py` creates administrator accounts, so it REFUSES to run unless the
database is SQLite AND `SQL_DATABASE` is set explicitly to a path under the system temp directory
(`/tmp` or `$TMPDIR`, symlinks resolved), `ENVIRONMENT` is `dev`, and `SEED_OUT` is also under temp.
The password is random per run and exists only in the 0600 `SEED_OUT` file, which the harness reads.
Prove the refusal before seeding anything:

   `python3 docs/delivery/goals/17tnw2b1we2-evidence/seed_live_api.py --self-test`   (hostile and benign environments; exit 0)
   `python3 docs/delivery/goals/17tnw2b1we2-evidence/seed_live_api.py --check`       (dry run of THIS environment; exit 1 with a reason when refused)

1. API environment (Python 3.12 or newer; versions as pinned in `implementation/api/pyproject.toml`):
   `python3 -m venv /tmp/live-venv && /tmp/live-venv/bin/pip install "Django==6.1.1" "strawberry-graphql-django==0.92.0" "strawberry-graphql==0.328.0" "graphql-core==3.3.0" "cross-web==0.7.0" "cryptography==50.0.2" "celery[redis]==5.6.3"`
2. From `implementation/api`:
   `export SQL_DATABASE=/tmp/live.sqlite3 API_DIR=$PWD SEED_OUT=/tmp/live-seed.json`
   `python3 ../../docs/delivery/goals/17tnw2b1we2-evidence/seed_live_api.py --check`
   `/tmp/live-venv/bin/python manage.py migrate`
   `/tmp/live-venv/bin/python ../../docs/delivery/goals/17tnw2b1we2-evidence/seed_live_api.py`
   `/tmp/live-venv/bin/python manage.py runserver 127.0.0.1:8765 --noreload`
3. Harness: make a directory outside the repo, copy `live_harness_main.rs` to `src/main.rs`, and give
   it this `Cargo.toml` (replace `<repo>`; the empty `[workspace]` keeps it out of the repo workspace):

   ```
   [package]
   name = "live-harness"
   version = "0.0.0"
   edition = "2021"
   publish = false

   [dependencies]
   selahcue-licensing = { path = "<repo>/implementation/desktop/crates/selahcue-licensing" }
   selahcue-cloud = { path = "<repo>/implementation/desktop/crates/selahcue-cloud", features = ["http"] }
   serde_json = "1"

   [workspace]
   ```

   Copy `<repo>/implementation/desktop/Cargo.lock` and `rust-toolchain.toml` beside it, then
   `cargo run -- http://127.0.0.1:8765 /tmp/live-seed.json`.
   The harness prints outcomes only: never a token, password or response body.

## Mutation results

`mutate.py` edits source files IN PLACE, so it refuses to start unless the current directory is a
dedicated linked git worktree (not the main checkout other sessions share) with a clean tree
(commit first), restores each file in a `finally` block, and exits non-zero unless every mutation is
KILLED (a survivor, a compile error, a pattern that no longer matches, or a dirty tree afterwards
all fail the run). From a dedicated worktree at the commit under test:

   `git worktree add --detach ../mutation-check <commit> && cd ../mutation-check`
   `python3 docs/delivery/goals/17tnw2b1we2-evidence/mutate.py`            (optionally with name prefixes, e.g. `S1 W`)
   `python3 docs/delivery/goals/17tnw2b1we2-evidence/mutate.py --self-test` (the guard; edits nothing)

## Named tests that must exist

`cargo test <filter>` exits 0 when the filter matches nothing, so a verifier naming a renamed test
passes silently. `run_named_tests.py` lists the tests, fails if any name selects none, and fails unless
every selected test passed:

   `python3 docs/delivery/goals/17tnw2b1we2-evidence/run_named_tests.py selahcue-licensing test_client <name> [<name> ...]`
