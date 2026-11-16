"""Temporary PostgreSQL and mutation qualification for staff extension generations."""

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


MAX_OUTPUT = 1024 * 1024
WHOLE_SECONDS = 450
CLEANUP_SECONDS = 5
REVIEWED_SHA = "01413d07e6377c017d5f2d2cbff4244ec4460017"
REVIEWED_API_TREE = "0410de586e948265ca1d20d69281ba950c5490d1"
API = Path("implementation/api")
# Binding temporary qualification manifest. All 493 original identities still
# require a passing canonical full API result.
BASELINE_SELECTORS = (
    "tests/test_free_license_lifecycle.py::test_expiring_free_refresh_keeps_live_bearer_and_commits_one_audit",
    "tests/test_free_license_concurrency_postgres.py::test_free_writer_refusal_rolls_back_and_leaves_one_denial",
    "tests/test_license_revoke_extend.py::test_extension_replay_refusal_and_failure_do_not_advance_generation[ACTIVATED]",
    "tests/test_license_revoke_extend.py::test_extension_replay_refusal_and_failure_do_not_advance_generation[EXPIRING]",
    "tests/test_license_revoke_extend.py::test_token_issuance_snapshots_latest_staff_generation",
    "tests/test_free_license_concurrency_postgres.py::test_frozen_clock_two_extensions_then_free_catchup_requires_replacement",
    "tests/test_concurrency_postgres.py::test_ordinary_refresh_does_not_wait_on_licence_write_lock",
)
ORDINARY_REFRESH_SELECTOR = "tests/test_concurrency_postgres.py::test_ordinary_refresh_does_not_wait_on_licence_write_lock"

SERVICES = {
    "SQL_ENGINE": "django.db.backends.postgresql",
    "SQL_DATABASE": "selahcue_test",
    "SQL_USER": "selahcue",
    "SQL_HOST": "localhost",
    "SQL_PORT": "5432",
    "CACHE_URL": "redis://localhost:6379/1",
    "CELERY_BROKER_URL": "redis://localhost:6379/2",
    "TEST_STT_REDIS_URL": "redis://localhost:6379/3",
}
PYTEST_FLAGS = (
    "-q", "-rfEs", "--tb=short", "--maxfail=0", "--capture=tee-sys",
    "-p", "pytest_django.plugin", "-p", "no:cacheprovider", "-o", "junit_logging=no",
    "--ds=qualification_settings",
)


@dataclass(frozen=True)
class Recipe:
    name: str
    file: str
    before: bytes
    after: bytes
    failures: dict[str, tuple[str, str]]


EXTENSION_CASE = (
    "tests/test_license_revoke_extend.py::"
    "test_extension_replay_refusal_and_failure_do_not_advance_generation"
)
RECIPES = (
    Recipe(
        "free-writer",
        "selahcue_api/apps/license_keys/free_lifecycle.py",
        b"                allow_wrapping_transaction=True,\n", b"",
        {
            "tests/test_free_license_lifecycle.py::"
            "test_expiring_free_refresh_keeps_live_bearer_and_commits_one_audit":
                ("assert response.status_code == 200", r"\b500 == 200\b"),
            "tests/test_free_license_concurrency_postgres.py::"
            "test_free_writer_refusal_rolls_back_and_leaves_one_denial":
                ("assert response.status_code == 409", r"\b500 == 409\b"),
        },
    ),
    Recipe(
        "staff-increment",
        "selahcue_api/apps/license_keys/services.py",
        b"    locked.staff_extension_generation += 1\n", b"",
        {
            f"{EXTENSION_CASE}[{status}]": (
                "assert result.changed and _fresh(key).staff_extension_generation == 1", r"\b0 == 1\b",
            )
            for status in ("ACTIVATED", "EXPIRING")
        },
    ),
    Recipe(
        "token-snapshot",
        "selahcue_api/apps/devices/services.py",
        b"        staff_extension_generation=license_key.staff_extension_generation,\n",
        b"        staff_extension_generation=0,\n",
        {
            "tests/test_license_revoke_extend.py::test_token_issuance_snapshots_latest_staff_generation":
                ("assert original.staff_extension_generation == 1", r"\b0 == 1\b"),
        },
    ),
    Recipe(
        "pending-catchup",
        "selahcue_api/apps/license_keys/free_lifecycle.py",
        b"    extend_token = allow_token_catchup and (renewed or (",
        b"    extend_token = (renewed or (",
        {
            "tests/test_free_license_concurrency_postgres.py::"
            "test_frozen_clock_two_extensions_then_free_catchup_requires_replacement": (
                'assert legacy.json()["token"]["expires_at"] == old_expiry.isoformat()',
                r"2029-02-28T12:00:00\+00:00['\"]? == ['\"]?2028-03-02T12:00:00\+00:00",
            ),
        },
    ),
)
REQUIRED = tuple(selector for recipe in RECIPES for selector in recipe.failures)


class QualificationError(Exception):
    """The qualification evidence cannot support a pass."""


def verify_results(junit, collected, returncode, *, selectors, failures=None):
    """Read the pytest evidence and prove the requested tests actually ran."""
    expected_exit = 0 if failures is None else 1
    if returncode != expected_exit:
        raise QualificationError(f"pytest exited {returncode}, expected {expected_exit}")

    try:
        receipt = json.loads(read_bounded(collected))
        xml = read_bounded(junit).decode("utf-8")
        if "<!DOCTYPE" in xml:
            raise QualificationError("unexpected JUnit document type")
        root = ET.fromstring(xml)
    except (OSError, ValueError, ET.ParseError) as error:
        raise QualificationError(f"invalid collection or JUnit evidence ({type(error).__name__})") from None

    if not isinstance(receipt, dict) or set(receipt) != {"nodes", "calls", "deselected"}:
        raise QualificationError("invalid collection receipt")
    nodes = receipt["nodes"]
    calls = receipt["calls"]
    if (
        not isinstance(nodes, list) or not nodes
        or not all(isinstance(node, str) and node.count("::") >= 1 for node in nodes)
        or len(nodes) != len(set(nodes))
        or receipt["deselected"] != 0
    ):
        raise QualificationError("empty, invalid or duplicate collected test identities")

    if len(nodes) != len(selectors) or set(nodes) != set(selectors):
        raise QualificationError("collected cases differ from the exact selector manifest")
    if failures is not None and set(nodes) != set(failures):
        raise QualificationError("mutant collection differs from the exact recipe selectors")
    expected_call = "passed" if failures is None else "failed"
    if (
        not isinstance(calls, list)
        or not all(isinstance(call, list) and len(call) == 2 and isinstance(call[0], str) for call in calls)
        or len(calls) != len(nodes)
        or {call[0] for call in calls} != set(nodes)
        or any(call[1] != expected_call for call in calls)
    ):
        raise QualificationError("collection does not match pytest call-phase outcomes")

    if root.tag == "testsuites" and len(root) == 1:
        root = root[0]
    if root.tag != "testsuite":
        raise QualificationError("expected exactly one pytest JUnit suite")
    cases = root.findall("testcase")
    if len(cases) != sum(1 for _ in root.iter("testcase")):
        raise QualificationError("nested JUnit testcase is outside the expected suite")

    expected = {junit_address(node): node for node in nodes}
    if len(expected) != len(nodes):
        raise QualificationError("collected test identities collide in JUnit")
    seen = set()
    assertions = {}
    for case in cases:
        address = case.get("classname"), case.get("name")
        if address not in expected or address in seen:
            raise QualificationError("unexpected or duplicate JUnit testcase")
        seen.add(address)
        outcomes = [entry for entry in case if entry.tag in {"error", "skipped", "failure"}]
        if failures is None:
            if outcomes:
                raise QualificationError("baseline contains failed, errored or skipped cases")
            continue
        if len(outcomes) != 1 or outcomes[0].tag != "failure":
            raise QualificationError("mutant case lacks exactly one call failure")
        failure = outcomes[0]
        selector = expected[address]
        expression, mismatch = failures[selector]
        observed = re.search(mismatch, failure.get("message", ""))
        trace_line = next(
            (line.strip() for line in (failure.text or "").splitlines() if line.strip() == expression),
            None,
        )
        if observed is None or trace_line is None:
            raise QualificationError("mutant failed at an unexpected assertion")
        assertions[selector] = {"expression": trace_line, "mismatch": observed.group()}

    if seen != set(expected):
        raise QualificationError("JUnit does not contain every collected test")
    totals = {
        "tests": len(seen), "failures": len(failures or {}), "errors": 0, "skipped": 0,
    }
    if any(root.get(key) != str(value) for key, value in totals.items()):
        raise QualificationError("JUnit summary differs from verified case outcomes")
    by_file = Counter(node.split("::", 1)[0] for node in nodes)
    return {"files": dict(sorted(by_file.items())), "assertions": assertions}


def junit_address(node):
    # Pytest retains parameter punctuation in the testcase name. Only the path
    # and any class segments are translated to a dotted classname.
    path_and_names, bracket, parameter = node.partition("[")
    path, *names = path_and_names.split("::")
    classname = ".".join([path.removesuffix(".py").replace("/", "."), *names[:-1]])
    return classname, names[-1] + bracket + parameter


def read_bounded(path):
    with path.open("rb") as stream:
        data = stream.read(MAX_OUTPUT + 1)
    if len(data) > MAX_OUTPUT:
        raise QualificationError(f"{path.name} exceeded 1 MiB")
    return data


def seconds_left(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise QualificationError("child deadline expired")
    return remaining


def stop_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    finally:
        try:
            process.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            raise QualificationError("owned child could not be reaped") from None


def run_child(command, *, cwd, env, deadline, stdout, stderr):
    """Run a child with separate retained streams."""
    seconds_left(deadline)
    with stdout.open("wb") as out, stderr.open("wb") as err, selectors.DefaultSelector() as ready:
        process = subprocess.Popen(
            command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, start_new_session=True,
        )
        complete = False
        try:
            streams = (process.stdout, process.stderr)
            for pipe, log in zip(streams, (out, err)):
                ready.register(pipe, selectors.EVENT_READ, log)
            while ready.get_map():
                for event, _ in ready.select(timeout=seconds_left(deadline)):
                    log = event.data
                    remaining = MAX_OUTPUT - log.tell()
                    data = os.read(event.fd, min(65536, remaining + 1))
                    if not data:
                        ready.unregister(event.fileobj)
                    else:
                        log.write(data[:remaining])
                        if len(data) > remaining:
                            raise QualificationError("child output exceeded 1 MiB per stream")
            returncode = process.wait(timeout=seconds_left(deadline))
            complete = True
            return returncode
        except subprocess.TimeoutExpired:
            raise QualificationError("child deadline expired") from None
        finally:
            for pipe in (process.stdout, process.stderr):
                pipe.close()
            if not complete:
                stop_group(process)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_restoration(originals):
    if any(sha256(read_bounded(path)) != sha256(data) for path, data in originals.items()):
        raise QualificationError("qualification source restoration did not match saved hashes")


@contextmanager
def mutation(path, before, after, originals):
    """Apply the recipe to a disposable source copy."""
    verify_restoration(originals)
    original = originals[path]
    if original.count(before) != 1:
        raise QualificationError("mutation requires one exact source match")
    try:
        path.write_bytes(original.replace(before, after, 1))
        yield
    finally:
        path.write_bytes(original)
        verify_restoration(originals)

# Only the child executes this script. The stdlib fixture imports the supervisor
# without loading the editable project, Django or pytest.
BOOTSTRAP = '''
import hashlib
import json
import math
from pathlib import Path
import re
import resource
import sys
import time

api, settings_path, receipt_dir, database = sys.argv[1:5]
api = Path(api).resolve()
receipt_dir = Path(receipt_dir)
sys.path[:0] = [str(api), settings_path]
resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))

import selahcue_api

if Path(selahcue_api.__file__).resolve() != api / "selahcue_api" / "__init__.py":
    raise RuntimeError("qualification did not import the disposable application")

import pytest


class Evidence:
    MANIFEST_LIMIT = 128 * 1024
    PROGRESS_LIMIT = 384 * 1024
    PHASES = frozenset({"setup", "call", "teardown"})
    OUTCOMES = frozenset({"passed", "failed", "skipped", "xfail"})
    CASE_NAME = re.compile(r"tests/test_[a-z0-9_]{1,64}[.]py::test_[A-Za-z0-9_]{1,144}")
    TRUNCATED = '\\nLICQ ["progress-truncated"]\\n'

    def __init__(self):
        self.nodes = []
        self.calls = []
        self.deselected = 0
        self.indices = {}
        self.started_ns = time.monotonic_ns()
        self.progress_bytes = 0
        self.progress_closed = False

    def identity(self, nodeid):
        base, bracket, _ = nodeid.partition("[")
        if self.CASE_NAME.fullmatch(base):
            if not bracket:
                return base
            digest = hashlib.sha256(nodeid.encode("utf-8", "surrogatepass")).hexdigest()
            return f"{base}[sha256={digest}]"
        digest = hashlib.sha256(nodeid.encode("utf-8", "surrogatepass")).hexdigest()
        return f"node-sha256:{digest}"

    def progress(self, event):
        if self.progress_closed:
            return
        # Write independently of pytest's capture and prefix a newline because its
        # terminal progress indicator may already be on the current line.
        line = "\\nLICQ " + json.dumps(event, separators=(",", ":")) + "\\n"
        if self.progress_bytes + len(line) + len(self.TRUNCATED) > self.PROGRESS_LIMIT:
            line = self.TRUNCATED
            self.progress_closed = True
        try:
            sys.__stdout__.write(line)
            sys.__stdout__.flush()
            self.progress_bytes += len(line)
        except (OSError, ValueError):
            # Telemetry is diagnostic. A broken progress sink cannot change a test outcome.
            self.progress_closed = True

    def elapsed_us(self):
        return min(450_000_000, (time.monotonic_ns() - self.started_ns) // 1000)

    def phase_start(self, item, phase):
        index = self.indices.get(item.nodeid)
        if index is not None:
            self.progress(["start", index, phase, self.elapsed_us()])

    def pytest_collection_finish(self, session):
        self.nodes = [item.nodeid for item in session.items]
        self.indices = {nodeid: index for index, nodeid in enumerate(self.nodes)}
        identities = []
        manifest_bytes = 0
        for nodeid in self.nodes:
            identity = self.identity(nodeid)
            # All emitted identities are ASCII with no JSON escape characters.
            manifest_bytes += len(identity) + 3
            if manifest_bytes > self.MANIFEST_LIMIT:
                break
            identities.append(identity)
        self.progress(["collection", len(self.nodes), identities, len(identities) != len(self.nodes)])

    def pytest_deselected(self, items):
        self.deselected += len(items)

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_setup(self, item):
        self.phase_start(item, "setup")
        return (yield)

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_call(self, item):
        self.phase_start(item, "call")
        return (yield)

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_teardown(self, item):
        self.phase_start(item, "teardown")
        return (yield)

    def pytest_runtest_logreport(self, report):
        outcome = "xfail" if hasattr(report, "wasxfail") else report.outcome
        if report.when == "call":
            self.calls.append((report.nodeid, outcome))
        index = self.indices.get(report.nodeid)
        if index is not None and report.when in self.PHASES:
            duration = report.duration
            duration_us = (
                round(duration * 1_000_000)
                if isinstance(duration, (int, float)) and 0 <= duration <= 450 and math.isfinite(duration)
                else None
            )
            safe_outcome = outcome if outcome in self.OUTCOMES else "unknown"
            self.progress(["result", index, report.when, safe_outcome, duration_us, self.elapsed_us()])

    def pytest_sessionfinish(self):
        receipt = {"nodes": self.nodes, "calls": self.calls, "deselected": self.deselected}
        (receipt_dir / "collected.json").write_text(json.dumps(receipt), encoding="utf-8")

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(self, fixturedef, request):
        result = yield
        if fixturedef.argname == "django_db_setup":
            from django.db import connection

            if connection.vendor != "postgresql":
                raise RuntimeError("qualification requires PostgreSQL")
            with request.getfixturevalue("django_db_blocker").unblock():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_database(), current_setting('server_version_num')")
                    name, version = cursor.fetchone()
            if name != database or not 160000 <= int(version) < 170000:
                raise RuntimeError("qualification database or PostgreSQL major version differs")
            receipt = {
                "vendor": connection.vendor, "database": name, "server_version_num": int(version),
                "installed_app": str(Path(selahcue_api.__file__).resolve()),
            }
            (receipt_dir / "backend.json").write_text(json.dumps(receipt), encoding="utf-8")
        return result


raise SystemExit(pytest.main(sys.argv[5:], plugins=[Evidence()]))
'''

LOG_CREDENTIALS = re.compile(
    rb"SC-[A-Z0-9_]+-(?:[A-Za-z0-9_-]{43,}|(?:[A-Za-z0-9]{4}-){4,}[A-Za-z0-9]{4})"
)
LOG_BEARERS = re.compile(rb"(?i)\bBearer ([A-Za-z0-9_.-]{16,})")
LOG_SECRETS = re.compile(
    rb"""(?i)(\b(?:SQL_PASSWORD|SECRET_KEY|AWS_SECRET_ACCESS_KEY|[A-Z0-9_]+_API_KEY)"""
    rb"""(?:['"]|&quot;|&apos;)?\s*[=:]\s*(?:['"]|&quot;|&apos;)?)"""
    rb"""[^\s<>&"']+"""
)


def redact_evidence(data):
    data = LOG_CREDENTIALS.sub(b"[credential redacted]", data)
    data = LOG_BEARERS.sub(b"Bearer [credential redacted]", data)
    return LOG_SECRETS.sub(rb"\1[credential redacted]", data)


def hosted_environment():
    if any(os.environ.get(key) != value for key, value in SERVICES.items()) or not os.environ.get("SQL_PASSWORD"):
        raise QualificationError("the canonical PostgreSQL and Redis job environment is required")
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TZ") if key in os.environ}
    env.update(SERVICES, SQL_PASSWORD=os.environ["SQL_PASSWORD"])
    env["DJANGO_SETTINGS_MODULE"] = "qualification_settings"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def database_name(index):
    parts = (os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"], str(os.getpid()))
    if not all(re.fullmatch(r"[0-9]{1,16}", part) for part in parts) or index not in range(5):
        raise QualificationError("invalid qualification database name components")
    name = f"test_licq_{'_'.join(parts)}_{index}"
    if len(name) > 63:
        raise QualificationError("qualification database name exceeds PostgreSQL identifier limit")
    return name


def git(repo, scratch, deadline, *arguments):
    out = scratch / "git.stdout.log"
    err = scratch / "git.stderr.log"
    env = {"PATH": os.environ["PATH"], "GIT_OPTIONAL_LOCKS": "0"}
    returncode = run_child(
        ["git", *arguments], cwd=repo, env=env, deadline=min(deadline, time.monotonic() + 3),
        stdout=out, stderr=err,
    )
    if returncode != 0:
        raise QualificationError(f"canonical checkout proof failed at git {arguments[0]} (exit {returncode})")
    return read_bounded(out)


def checkout_state(repo, scratch, deadline):
    # Inspect both working-tree and staged changes. Ignored environments are not
    # source inputs and are never copied.
    git(repo, scratch, deadline, "diff", "--quiet", "--no-ext-diff", "HEAD", "--")
    git(repo, scratch, deadline, "diff", "--cached", "--quiet", "--no-ext-diff", "HEAD", "--")
    sha, tree, api_tree = git(
        repo, scratch, deadline, "rev-parse", "HEAD", "HEAD^{tree}", f"HEAD:{API}",
    ).decode("ascii").splitlines()
    if (
        not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (sha, tree, api_tree))
        or sha != os.environ.get("GITHUB_SHA") or api_tree != REVIEWED_API_TREE
    ):
        raise QualificationError("checkout SHA or reviewed API subtree identity differs")
    return {"sha": sha, "tree": tree, "api_tree": api_tree, "reviewed_source": REVIEWED_SHA}


def copy_api(repo, copy, scratch, snapshot, deadline):
    listing = git(repo, scratch, deadline, "ls-tree", "-rz", snapshot["sha"], "--", str(API))
    entries = listing.rstrip(b"\0").split(b"\0")
    for entry in entries:
        seconds_left(deadline)
        header, encoded_path = entry.split(b"\t", 1)
        mode, kind, blob = header.decode("ascii").split()
        relative = Path(encoded_path.decode("utf-8"))
        if (
            mode not in {"100644", "100755"} or kind != "blob"
            or ".." in relative.parts or not relative.is_relative_to(API)
        ):
            raise QualificationError("unexpected entry in reviewed API subtree")
        source = repo / relative
        if source.resolve(strict=True) != source or not source.is_file():
            raise QualificationError("non-regular path in canonical API subtree")
        data = read_bounded(source)
        object_header = f"blob {len(data)}\0".encode("ascii")
        actual_blob = hashlib.sha1(object_header + data, usedforsecurity=False).hexdigest()
        if actual_blob != blob:
            raise QualificationError("canonical API source content differs from its tracked blob")
        destination = copy / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(0o755 if mode == "100755" else 0o644)
    return len(entries)


def publish_child(stage, evidence, name):
    # Only this fixed file inventory is eligible for upload. Runtime settings,
    # source and raw directories stay out of the artifact.
    files = {
        "stdout.log": "stdout.log", "stderr.log": "stderr.log", "junit.xml": "junit.xml",
        "collected.json": "collected.json", "backend.json": "backend.json",
    }
    problem = False
    for source, suffix in files.items():
        path = stage / source
        if path.is_symlink():
            problem = True
            continue
        if path.is_file():
            try:
                data = redact_evidence(read_bounded(path))
                if len(data) > MAX_OUTPUT:
                    raise QualificationError("redacted child evidence exceeded 1 MiB")
                (evidence / f"{name}.{suffix}").write_bytes(data)
            except QualificationError:
                problem = True
    if problem:
        raise QualificationError("some child evidence exceeded its byte bound or was not a regular file")


def retain_receipt(evidence, receipt):
    (evidence / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def run_stage(name, command, *, cwd, env, stage, evidence, receipt, deadline):
    started = time.monotonic()
    record = {"stage": name, "status": "unverified"}
    receipt["children"].append(record)
    retain_receipt(evidence, receipt)
    try:
        returncode = run_child(
            command, cwd=cwd, env=env, deadline=deadline,
            stdout=stage / "stdout.log", stderr=stage / "stderr.log",
        )
        record["exit"] = returncode
        return returncode, record
    except (QualificationError, OSError) as error:
        record.update(status="failed", reason=str(error))
        raise
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        retain_receipt(evidence, receipt)
        publish_child(stage, evidence, name)


def verify_backend(stage, api, database):
    observed = json.loads(read_bounded(stage / "backend.json"))
    expected_module = str(api / "selahcue_api" / "__init__.py")
    if (
        not isinstance(observed, dict) or observed.get("vendor") != "postgresql"
        or observed.get("database") != database or observed.get("installed_app") != expected_module
        or not isinstance(observed.get("server_version_num"), int)
        or not 160000 <= observed["server_version_num"] < 170000
    ):
        raise QualificationError("child database or source identity evidence differs")
    return observed


def qualify_child(api, scratch, evidence, receipt, *, deadline, index, recipe=None):
    name = recipe.name if recipe is not None else "baseline"
    stage = scratch / name
    stage.mkdir()
    database = database_name(index)
    (stage / "qualification_settings.py").write_text(
        "from selahcue_api.settings import *\n"
        "DATABASES = {**DATABASES, 'default': {**DATABASES['default']}}\n"
        f"DATABASES['default']['TEST'] = {{**DATABASES['default'].get('TEST', {{}}), 'NAME': {database!r}}}\n",
        encoding="utf-8",
    )
    selectors_for_child = tuple(recipe.failures) if recipe is not None else BASELINE_SELECTORS
    if recipe is None:
        required = set(REQUIRED)
        if (
            len(required) != 6
            or len(BASELINE_SELECTORS) != 7
            or len(set(BASELINE_SELECTORS)) != len(BASELINE_SELECTORS)
            or set(BASELINE_SELECTORS) != required | {ORDINARY_REFRESH_SELECTOR}
        ):
            raise QualificationError(
                "baseline manifest must contain exactly six unique mutant controls and ordinary refresh"
            )
    timeout = 60 if recipe is not None else 180
    command = [
        sys.executable, "-I", "-B", "-c", BOOTSTRAP, str(api), str(stage), str(stage), database,
        *PYTEST_FLAGS, "--junitxml", str(stage / "junit.xml"), *selectors_for_child,
    ]
    returncode, record = run_stage(
        name, command, cwd=api, env=hosted_environment(), stage=stage, evidence=evidence,
        receipt=receipt, deadline=min(deadline, time.monotonic() + timeout),
    )
    try:
        result = verify_results(
            stage / "junit.xml", stage / "collected.json", returncode,
            selectors=selectors_for_child,
            failures=recipe.failures if recipe is not None else None,
        )
        record.update(result)
        record["backend"] = verify_backend(stage, api, database)
        if recipe is None:
            stdout = read_bounded(stage / "stdout.log").decode("utf-8", errors="replace")
            for label, pattern in (
                ("sql_statements", r"\bordinary refresh SQL statements: ([0-9]+)"),
                ("ordinary_refresh_elapsed_seconds", r"\bordinary refresh elapsed seconds: ([0-9]+\.[0-9]+)"),
            ):
                measurements = re.findall(pattern, stdout)
                if len(measurements) != 1:
                    raise QualificationError("ordinary refresh did not report both distinct measurements")
                record[label] = measurements[0]
            print(
                f"Ordinary refresh SQL statements: {record['sql_statements']}\n"
                f"Ordinary refresh elapsed seconds: {record['ordinary_refresh_elapsed_seconds']}",
                flush=True,
            )
        record["status"] = "baseline-passed" if recipe is None else "mutant-failed-as-required"
        print(f"{name}: {record['status']}, exit {returncode}, {sum(result['files'].values())} cases", flush=True)
        for case, failure in result["assertions"].items():
            print(f"{case}: {failure['expression']} ({failure['mismatch']})", flush=True)
    except (QualificationError, OSError, ValueError) as error:
        record.update(status="failed", reason=str(error))
        raise
    finally:
        retain_receipt(evidence, receipt)


def provision_paths():
    repo = Path(__file__).resolve().parents[2]
    temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    if temp.is_relative_to(repo):
        raise QualificationError("qualification scratch must be outside the canonical checkout")
    area = Path(tempfile.mkdtemp(prefix="license-generation-qualification-", dir=temp))
    scratch = area / "scratch"
    evidence = area / "evidence"
    scratch.mkdir()
    evidence.mkdir()
    # Github output includes only the fresh evidence path, with no shell expansion.
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"evidence={evidence}\n")
    return repo, scratch, evidence


def run_qualification(deadline):
    repo, scratch, evidence = provision_paths()
    receipt = {"status": "failed", "children": [], "restorations": []}
    snapshot = None
    error = None
    complete = False
    try:
        working_deadline = deadline - CLEANUP_SECONDS
        snapshot = checkout_state(repo, scratch, working_deadline)
        receipt["canonical"] = snapshot
        retain_receipt(evidence, receipt)
        print(f"Qualification checkout: {snapshot['sha']} tree {snapshot['tree']} API {snapshot['api_tree']}", flush=True)
        fixtures = scratch / "fixtures"
        fixtures.mkdir()
        fixture_status, record = run_stage(
            "fixtures", [sys.executable, "-B", str(Path(__file__).with_name("test_qualify_license_generation.py")), "-v"],
            cwd=fixtures, env={"PATH": os.environ["PATH"], "TMPDIR": str(fixtures)},
            stage=fixtures, evidence=evidence,
            receipt=receipt, deadline=min(working_deadline, time.monotonic() + 30),
        )
        if fixture_status != 0:
            record["status"] = "failed"
            raise QualificationError("standalone qualification fixtures failed")
        record["status"] = "passed"

        copy = scratch / "checkout"
        receipt["copied_tracked_files"] = copy_api(repo, copy, scratch, snapshot, working_deadline)
        api = copy / API
        originals = {api / recipe.file: read_bounded(api / recipe.file) for recipe in RECIPES}
        hashes = {str(path.relative_to(api)): sha256(data) for path, data in originals.items()}
        receipt["source_sha256"] = hashes
        try:
            qualify_child(api, scratch, evidence, receipt, deadline=working_deadline, index=0)
        finally:
            verify_restoration(originals)
        for index, recipe in enumerate(RECIPES, start=1):
            try:
                with mutation(api / recipe.file, recipe.before, recipe.after, originals):
                    qualify_child(
                        api, scratch, evidence, receipt,
                        deadline=working_deadline, index=index, recipe=recipe,
                    )
            finally:
                verify_restoration(originals)
                receipt["restorations"].append({"stage": recipe.name, "sha256": hashes})
                retain_receipt(evidence, receipt)
        complete = True
    except (QualificationError, OSError, ValueError, KeyError) as failure:
        error = failure
    finally:
        try:
            if snapshot is not None:
                if checkout_state(repo, scratch, deadline) != snapshot:
                    raise QualificationError("canonical checkout changed during qualification")
                receipt["canonical_unchanged"] = True
        except (QualificationError, OSError, ValueError) as cleanup_failure:
            receipt["canonical_unchanged"] = False
            receipt["canonical_error"] = str(cleanup_failure)
            if error is None:
                error = cleanup_failure
        finally:
            shutil.rmtree(scratch)
        if complete and error is None:
            receipt["status"] = "passed"
        elif error is not None:
            receipt["error"] = str(error)
        retain_receipt(evidence, receipt)

    if error is not None:
        raise error
    print("PostgreSQL baseline, all four mutations and canonical source custody verified", flush=True)


def interrupted(signum, _frame):
    message = "qualification reached the 450-second deadline" if signum == signal.SIGALRM else "qualification interrupted"
    raise QualificationError(message)


def main():
    if len(sys.argv) != 1:
        sys.exit("qualification accepts no arguments")
    started = time.monotonic()
    for event in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(event, interrupted)
    signal.setitimer(signal.ITIMER_REAL, WHOLE_SECONDS)
    try:
        run_qualification(started + WHOLE_SECONDS)
    except (QualificationError, OSError, ValueError, KeyError) as error:
        print(f"Qualification failed: {error}", file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
