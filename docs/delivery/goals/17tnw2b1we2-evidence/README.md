# 17tnw2b1we2 evidence: how to reproduce the live run and the mutation results

Everything here is throwaway tooling for the Goal Contract `../17tnw2b1we2-native-signin.md`.
Nothing in this directory is built or run by `make ci`. Use a THROWAWAY database; the seed
creates users with a known password.

## Live run: the real desktop client against a running API

1. API environment (Python 3.12 or newer; versions as pinned in `implementation/api/pyproject.toml`):
   `python3 -m venv /tmp/live-venv && /tmp/live-venv/bin/pip install "Django==6.1.1" "strawberry-graphql-django==0.92.0" "strawberry-graphql==0.328.0" "graphql-core==3.3.0" "cross-web==0.7.0" "cryptography==50.0.2" "celery[redis]==5.6.3"`
2. From `implementation/api`:
   `export SQL_DATABASE=/tmp/live.sqlite3 API_DIR=$PWD SEED_OUT=/tmp/live-seed.json`
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

Commit the tree first, then from the repo root:
`python3 docs/delivery/goals/17tnw2b1we2-evidence/mutate.py`
(optionally with name prefixes, e.g. `S1 W`). Each mutation is applied to one source file, the
licensing (or cloud wire) tests run, and the file is restored. Every line must end in `KILLED`.
