"""Mutation harness for 86ak5r2pt (failed password-reset confirm trace).

Each mutant is one textual change (occasionally a few, in one file) to production code. The
sibling test files named for it run IN FULL (no -x, no --exact), the mutant must turn at least one
test RED, and the file is then restored from its original bytes and compared with `cmp`. A
mutant whose pattern no longer matches exactly once is reported NOT APPLIED, never as a pass.

    python3 docs/delivery/goals/86ak5r2pt-evidence/mutate.py [--out results.txt] [--only L3,B2,T1]

Needs `make api-install` once (it uses the `.venv-api-check` that target builds) and whatever
`python3` and `PATH` your shell has. Refuses to start unless the files it mutates are identical to
HEAD, and exits non-zero if any mutant survives, fails to apply, or is not restored byte for byte.
Takes about 1 to 1.5 minutes per mutant. The checked-in results are in mutation-results.txt,
produced by this script on the head that carries it.

WARNING: THIS EDITS PRODUCTION FILES IN PLACE. Run it only in your OWN worktree, never in a
checkout another session is using, and do not run two copies at once. The file under mutation is
restored from a copy in a `finally`, on normal exit, on an exception, and on SIGINT or SIGTERM
(handlers below). SIGKILL, a power cut or a crashed terminal cannot be handled: if the run dies
that way, the recovery is

    git checkout -- implementation/api/selahcue_api

(or `git diff` first to see what was left mutated). The script refuses to start while any file it
mutates differs from HEAD, so a leftover mutation can never be mistaken for your own change.
"""

import argparse
import atexit
import filecmp
import os
import shutil
import signal
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
ROOT = os.path.join(REPO, "implementation", "api")
PY = os.path.join(ROOT, ".venv-api-check", "bin", "python")
TESTS = ["tests/test_customer_auth_slice.py", "tests/test_password_reset_throttle.py"]

SVC = "selahcue_api/apps/accounts/services.py"
RED = "selahcue_api/graphql/redaction.py"
THR = "selahcue_api/apps/throttling/services.py"
GRD = "selahcue_api/apps/throttling/guards.py"

DEVICE_TESTS = TESTS + ["tests/test_activation_licence_transition.py", "tests/test_device_token_remint.py"]

BUDGET_CALL = """    limiter_degraded = enforce_budget_reporting_outage(
        "password_reset_confirm_ip",
        source,
        "SELAHCUE_THROTTLE_RESET_CONFIRM",
        RESET_CONFIRM_IP_BUDGET,
    )
    trace = _ResetConfirmTrace()
    try:
        return _consume_reset_token(raw_token, new_password, trace)"""
NOBUDGET = """    limiter_degraded = False
    trace = _ResetConfirmTrace()
    try:
        return _consume_reset_token(raw_token, new_password, trace)"""
REC_SIG = "def _record_failed_reset_confirm(trace: _ResetConfirmTrace, source: str) -> None:"
LEAK_ID_OLD = "                request_id=uuid.uuid4().hex,\n                result=AuditResult.DENIED,"
LEAK_ID_NEW = '                request_id=getattr(trace, "fp", "") or uuid.uuid4().hex,\n                result=AuditResult.DENIED,'
FP_LINE = (
    "    fingerprint = _fingerprint(token_value)\n    now = djtz.now()\n    with transaction.atomic():\n        try:\n"
    "            token = (\n                CredentialToken.objects.select_for_update()\n"
    "                .select_related(\"customer_user\")\n                .get(token_fingerprint=fingerprint)\n"
    "            )\n        except CredentialToken.DoesNotExist as error:\n            trace.refused"
)

def leak_fp(expr):
    return [(LEAK_ID_OLD, LEAK_ID_NEW), (FP_LINE, FP_LINE.replace("    now =", f"    trace.fp = {expr}\n    now =", 1))]

MUTANTS = [
    # ---- the throttle ----
    ("T1 budget call removed", SVC, [(BUDGET_CALL, NOBUDGET)]),
    ("T2 budget spent after the token lookup", SVC, [
        (BUDGET_CALL, NOBUDGET),
        ("        if not hmac.compare_digest(token.token_fingerprint, fingerprint):\n            trace.refused(ResetConfirmOutcome.UNKNOWN_TOKEN)\n            raise _validation_error()\n",
         "        if not hmac.compare_digest(token.token_fingerprint, fingerprint):\n            trace.refused(ResetConfirmOutcome.UNKNOWN_TOKEN)\n            raise _validation_error()\n        enforce_budget(\"password_reset_confirm_ip\", \"x\", \"SELAHCUE_THROTTLE_RESET_CONFIRM\", RESET_CONFIRM_IP_BUDGET)\n")]),
    ("T3 budget not keyed per source", SVC, [(BUDGET_CALL, BUDGET_CALL.replace("        source,\n", '        "one-bucket",\n'))]),
    ("T4 shipped confirm budget inflated", SVC, [("RESET_CONFIRM_IP_BUDGET = (20, 3600)", "RESET_CONFIRM_IP_BUDGET = (20000, 3600)")]),
    ("T5 limiter fails closed", GRD, [("return spend_budget(scope, identity, setting_name, default) is not BudgetOutcome.DENIED", "return spend_budget(scope, identity, setting_name, default) is BudgetOutcome.ALLOWED")]),
    ("T6 X-Forwarded-For trusted at proxy count 0", THR, [("    if hops > 0:\n        forwarded = request.META", "    hops = max(hops, 1)\n    if hops > 0:\n        forwarded = request.META")]),
    ("T7 X-Forwarded-For never honoured", THR, [('    hops = int(getattr(settings, "SELAHCUE_TRUSTED_PROXY_COUNT", 0))\n    if hops > 0:', '    hops = 0\n    if hops > 0:')]),
    ("T8 refused attempt is recorded too", SVC, [(BUDGET_CALL, """    limiter_degraded = False
    trace = _ResetConfirmTrace()
    try:
        limiter_degraded = enforce_budget_reporting_outage(
            "password_reset_confirm_ip",
            source,
            "SELAHCUE_THROTTLE_RESET_CONFIRM",
            RESET_CONFIRM_IP_BUDGET,
        )
        return _consume_reset_token(raw_token, new_password, trace)""")]),
    ("T9 trace brake default inflated", SVC, [("RESET_CONFIRM_TRACE_BUDGET = (1000, 3600)", "RESET_CONFIRM_TRACE_BUDGET = (1000000, 3600)")]),
    ("T10 outage ceiling default inflated", SVC, [("RESET_CONFIRM_TRACE_DEGRADED_CEILING = (200, 3600)", "RESET_CONFIRM_TRACE_DEGRADED_CEILING = (200000, 3600)")]),
    # ---- the redaction guard ----
    ("R1 all three names removed from the deny-list", RED, [('        "reset_token",\n        "raw_token",\n        "token_hash",\n', "")]),
    ("R2a reset_token removed", RED, [('        "reset_token",\n', "")]),
    ("R2b raw_token removed", RED, [('        "raw_token",\n', "")]),
    ("R2c token_hash removed", RED, [('        "token_hash",\n', "")]),
    ("R3 token_fingerprint put back in the deny-list", RED, [('        "reset_token",\n', '        "reset_token",\n        "token_fingerprint",\n')], DEVICE_TESTS),
    # ---- token / address leaks a careless change would make ----
    ("L1 fingerprint used as the attempt id", SVC, leak_fp("fingerprint")),
    ("L2 masked token used as the attempt id", SVC, leak_fp("_mask(token_value)[2]")),
    ("L3 raw token written to the log on failure", SVC, [("    except SafeAPIError:\n        _trace_failed_confirm(trace, source, limiter_degraded)\n        raise", '    except SafeAPIError:\n        logger.warning("confirm failed for %s", raw_token)\n        _trace_failed_confirm(trace, source, limiter_degraded)\n        raise')]),
    ("L4 raw token put in after under an unlisted key", SVC, [
        ('                after={"outcome": outcome.value},', '                after={"outcome": outcome.value, "probe": getattr(trace, "fp", "")},'),
        (FP_LINE, FP_LINE.replace("    now =", "    trace.fp = token_value\n    now =", 1))]),
    ("L5 the raw address is the actor id", SVC, [("        actor_id = audit_source_pseudonym(source)\n", "        actor_id = source\n")]),
    ("L6 the address is also kept in after", SVC, [('                after={"outcome": outcome.value},', '                after={"outcome": outcome.value, "source": source},')]),
    ("L7 pseudonym is a bare hash, not keyed", SVC, [('    digest = salted_hmac(_AUDIT_SOURCE_KEY_SALT, value, algorithm="sha256").hexdigest()', "    digest = hashlib.sha256(value.encode(\"utf-8\")).hexdigest()")]),
    ("L8 pseudonym does not rotate", SVC, [('    value = f"{(day or _audit_source_day()).isoformat()}|{source}"', '    value = f"2000-01-01|{source}"')]),
    ("L9 pseudonym truncated to 16", SVC, [("    return AUDIT_SOURCE_VERSIONED_PREFIX + digest[:32]", "    return AUDIT_SOURCE_VERSIONED_PREFIX + digest[:16]")]),
    ("L10 operator helper does not bucket", SVC, [("    return audit_source_pseudonym(bucket_for_throttling(ipaddress.ip_address(address.strip())), day)", "    return audit_source_pseudonym(address.strip(), day)")]),
    ("L1b a 20-character prefix of the fingerprint used as the attempt id", SVC, leak_fp("fingerprint[:20]")),
    ("L3b a 22-character slice of the raw token written to the log", SVC, [("    except SafeAPIError:\n        _trace_failed_confirm(trace, source, limiter_degraded)\n        raise", '    except SafeAPIError:\n        logger.warning("confirm failed for %s", raw_token[:22])\n        _trace_failed_confirm(trace, source, limiter_degraded)\n        raise')]),
    ("L3c a 20-character prefix of the fingerprint written to the log", SVC, [("    except SafeAPIError:\n        _trace_failed_confirm(trace, source, limiter_degraded)\n        raise", '    except SafeAPIError:\n        logger.warning("confirm failed for %s", _fingerprint((raw_token or "").strip())[:20])\n        _trace_failed_confirm(trace, source, limiter_degraded)\n        raise')]),
    ("L3d the first 6 characters of the submitted password written to the log", SVC, [("    except SafeAPIError:\n        _trace_failed_confirm(trace, source, limiter_degraded)\n        raise", '    except SafeAPIError:\n        logger.warning("confirm failed for %s", new_password[:6])\n        _trace_failed_confirm(trace, source, limiter_degraded)\n        raise')]),
    ("Q04 a consumed token is labelled before a wrong-purpose one", SVC, [("    if token.purpose != CredentialTokenPurpose.PASSWORD_RESET:\n        return ResetConfirmOutcome.WRONG_PURPOSE\n    if token.consumed_at is not None:\n        return ResetConfirmOutcome.CONSUMED\n", "    if token.consumed_at is not None:\n        return ResetConfirmOutcome.CONSUMED\n    if token.purpose != CredentialTokenPurpose.PASSWORD_RESET:\n        return ResetConfirmOutcome.WRONG_PURPOSE\n")]),
    # ---- the trace ----
    ("B1 nothing is recorded", SVC, [("    outcome = trace.outcome or ResetConfirmOutcome.UNCLASSIFIED\n    user_id = trace.customer_user_id\n", "    return\n    outcome = trace.outcome or ResetConfirmOutcome.UNCLASSIFIED\n    user_id = trace.customer_user_id\n")]),
    ("B2 a failed write is no longer swallowed", SVC, [('    except Exception as error:  # noqa: BLE001 -- see "WHY IT SWALLOWS"', "    except ZeroDivisionError as error:")]),
    ("B3 row written inside the rolled-back transaction", SVC, [
        ("        self.outcome = outcome\n        if customer_user_id is not None:\n            self.customer_user_id = customer_user_id\n", "        self.outcome = outcome\n        if customer_user_id is not None:\n            self.customer_user_id = customer_user_id\n        _record_failed_reset_confirm(self, \"127.0.0.1\")\n"),
        ("    except SafeAPIError:\n        _trace_failed_confirm(trace, source, limiter_degraded)\n        raise", "    except SafeAPIError:\n        raise")]),
    ("B4 every dead token labelled consumed", SVC, [("        return ResetConfirmOutcome.WRONG_PURPOSE\n", "        return ResetConfirmOutcome.CONSUMED\n"), ("        return ResetConfirmOutcome.EXPIRED\n    return ResetConfirmOutcome.UNCLASSIFIED", "        return ResetConfirmOutcome.CONSUMED\n    return ResetConfirmOutcome.UNCLASSIFIED")]),
    ("B5a refused() ignores the user id", SVC, [("        if customer_user_id is not None:\n            self.customer_user_id = customer_user_id\n", "        pass\n")]),
    ("B5b resolved() records nothing", SVC, [("        self.customer_user_id = customer_user_id\n\n    def refused", "        pass\n\n    def refused")]),
    ("B7 unresolved source pseudonymised like an address", SVC, [("_UNATTRIBUTED_SOURCES = frozenset({UNRESOLVED_CLIENT_IP, \"unknown\"})", "_UNATTRIBUTED_SOURCES = frozenset({\"unknown\"})")]),
    ("B8 a rejected password is not recorded", SVC, [("            trace.refused(ResetConfirmOutcome.PASSWORD_REJECTED, customer_user_id=token.customer_user_id)\n", "            pass\n")]),
    ("B9 FR-529: a consumed token answers with a different code", SVC, [("            trace.refused(_dead_token_outcome(token, now), customer_user_id=token.customer_user_id)\n            raise _validation_error()", "            trace.refused(_dead_token_outcome(token, now), customer_user_id=token.customer_user_id)\n            raise SafeAPIError(ErrorCode.NOT_FOUND)")]),
    ("B10 audit actor kind is CUSTOMER", SVC, [("ActorContext(kind=ActorKind.ANONYMOUS, actor_id=actor_id)", "ActorContext(kind=ActorKind.CUSTOMER, actor_id=actor_id)")]),
    ("B11 the success audit row is renamed", SVC, [('            action="customer_user.password_reset_completed",', '            action="customer_user.password_reset_completed_X",')]),
    ("B12 INTERNAL_ERROR labelled unclassified", SVC, [("        self.outcome = ResetConfirmOutcome.INTERNAL_ERROR", "        self.outcome = ResetConfirmOutcome.UNCLASSIFIED")]),
    # ---- the second-round changes ----
    # ---- round 2: the two allowances, the whole-body protection, the key derivation ----
    ("Q1 named outcomes spend the shared brake again", SVC, [("    account_id = trace.customer_user_id\n    if account_id is None:\n        budget = (", "    account_id = trace.customer_user_id\n    if True:\n        budget = (")]),
    ("Q2 the per-account allowance is not keyed by account", SVC, [("            str(account_id),\n            \"SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE_ACCOUNT\"", "            \"all\",\n            \"SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE_ACCOUNT\"")]),
    ("Q3 the per-account allowance reads the wrong setting", SVC, [("            \"SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE_ACCOUNT\",\n            RESET_CONFIRM_TRACE_ACCOUNT_BUDGET,", "            \"W2_NOT_A_SETTING\",\n            RESET_CONFIRM_TRACE_ACCOUNT_BUDGET,")]),
    ("Q4 the outage allowance for named outcomes is the shared one", SVC, [("            return _reset_confirm_trace_account_ceilings.claim(account_id)", "            return _reset_confirm_trace_ceiling.claim()")]),
    ("Q5 the per-account outage table never evicts", SVC, [("                while len(self._windows) > self._max_entries:\n                    self._windows.popitem(last=False)\n", "                while False:\n                    self._windows.popitem(last=False)\n")]),
    ("Q6 the skip report's account set is uncapped", SVC, [("            if account_id is not None and len(self._accounts) < _TRACE_REPORT_ACCOUNTS_MAX:", "            if account_id is not None:")]),
    ("Q7 the skip report does not list accounts", SVC, [('                f"; accounts {accounts}" if accounts else "",', '                "",')]),
    ("Q8 only the INSERT is protected, not the whole trace body", SVC, [("    except Exception as error:  # noqa: BLE001 -- see the docstring\n        _note_lost_trace(error, outcome, source)", "    except ZeroDivisionError as error:  # noqa: BLE001 -- see the docstring\n        _note_lost_trace(error, outcome, source)")]),
    ("Q9 a brake's spent budget logs the shared guard's false RATE_LIMITED warning", SVC, [("        outcome = spend_budget(*budget, report_denial=False)", "        outcome = spend_budget(*budget)")]),
    ("Q10 the audit day is the local date of the clock's own zone", SVC, [("    return djtz.now().astimezone(dt_timezone.utc).date()", "    return djtz.now().date()")]),
    ("Q11 the audit day is the machine's today", SVC, [("    return djtz.now().astimezone(dt_timezone.utc).date()", "    return date.today()")]),
    ("Q12 an unencodable token is no longer labelled malformed", SVC, [("    except UnicodeEncodeError:\n        # Lone surrogates", "    except ZeroDivisionError:\n        # Lone surrogates")]),
    ("Q13 the pseudonym is a credential-style fingerprint", SVC, [('    digest = salted_hmac(_AUDIT_SOURCE_KEY_SALT, value, algorithm="sha256").hexdigest()', "    digest = _fingerprint(value)")]),
    ("Q14 the pseudonym carries no scheme version", SVC, [('AUDIT_SOURCE_VERSIONED_PREFIX = "src:v1:"', 'AUDIT_SOURCE_VERSIONED_PREFIX = "src:"')]),
    ("N1 unencodable passwords accepted again", SVC, [('    try:\n        password.encode("utf-8")\n    except UnicodeEncodeError:\n        raise SafeAPIError(code) from None\n', "")]),
    ("N2 unexpected exceptions not recorded", SVC, [("    except Exception:\n        # Not a coded refusal", "    except ZeroDivisionError:\n        # Not a coded refusal")]),
    ("N3 outage not reported to the trace", SVC, [("    trace = _ResetConfirmTrace()\n    try:\n        return _consume_reset_token(raw_token, new_password, trace)", "    limiter_degraded = False\n    trace = _ResetConfirmTrace()\n    try:\n        return _consume_reset_token(raw_token, new_password, trace)")]),
    ("N4 no shared or per-account budget ever refuses a row", SVC, [("        if outcome is BudgetOutcome.DENIED:\n            return spent\n", "        if outcome is BudgetOutcome.DENIED:\n            return None\n")]),
    ("N5 brake keyed per call (unbounded keys)", SVC, [('            RESET_CONFIRM_TRACE_SCOPE,\n            "all",', '            RESET_CONFIRM_TRACE_SCOPE,\n            uuid.uuid4().hex,')]),
    ("N6 no outage ceiling is ever claimed", SVC, [("    if limiter_degraded and not claim_in_process():", "    if False and not claim_in_process():")]),
    ("N7 tally keeps a per-event list", SVC, [("            if self._count == 0:\n                self._first = detail[:_TRACE_REPORT_DETAIL_MAX]\n", "            if self._count == 0:\n                self._first = detail[:_TRACE_REPORT_DETAIL_MAX]\n            self._seen = getattr(self, \"_seen\", []) + [detail]\n")]),
    ("N8 tally detail not capped", SVC, [("                self._first = detail[:_TRACE_REPORT_DETAIL_MAX]\n", "                self._first = detail\n")]),
    ("N9 lost-trace report carries a traceback", SVC, [('            logger.warning(\n                "could not write the audit row for %d failed', '            logger.exception(\n                "could not write the audit row for %d failed')]),
    ("N10 report count not carried", SVC, [("            released = (self._count, self._first)", "            released = (1, self._first)")]),
    ("N11 recorder write not in its own atomic()", SVC, [("        with transaction.atomic():\n            record_audit_event(\n                ActorContext(kind=ActorKind.ANONYMOUS", "        with threading.Lock():\n            record_audit_event(\n                ActorContext(kind=ActorKind.ANONYMOUS")]),
]



def pytest_env():
    # The same scrubbed environment `make api-check` uses.
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "SQL_DATABASE": ":memory:",
    }


def run_tests(log_path, tests):
    with open(log_path, "w") as log:
        proc = subprocess.run(
            [PY, "-m", "pytest", "-p", "no:cacheprovider", *tests, "-q", "-rf"],
            cwd=ROOT, env=pytest_env(), stdout=log, stderr=subprocess.STDOUT,
        )
    failed, summary = [], ""
    with open(log_path) as log:
        for line in log:
            if line.startswith("FAILED "):
                failed.append(line.split(" - ")[0].strip()[7:].split("::", 1)[-1])
            if " passed" in line or " failed" in line:
                summary = line.strip()
    return proc.returncode, failed, summary


# The file currently mutated and its original bytes, so that an exit or a signal can put it back.
_ACTIVE = {"path": None, "original": None}


def _restore_active():
    if _ACTIVE["path"] is not None:
        with open(_ACTIVE["path"], "wb") as handle:
            handle.write(_ACTIVE["original"])
        _ACTIVE["path"] = None


def _on_signal(signum, _frame):
    _restore_active()
    sys.exit(128 + signum)


def main():
    atexit.register(_restore_active)
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, _on_signal)
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    parser.add_argument("--only", default="", help="comma-separated mutant ids, e.g. L3,B2")
    args = parser.parse_args()
    only = {item.strip() for item in args.only.split(",") if item.strip()}

    if not os.path.exists(PY):
        sys.exit("run `make api-install` first")
    touched = sorted({spec[1] for spec in MUTANTS})
    dirty = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--", *[os.path.join("implementation/api", f) for f in touched]],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        sys.exit(f"refusing to start: files to be mutated differ from HEAD:\n{dirty}")

    work = tempfile.mkdtemp(prefix="mutate-86ak5r2pt-")
    lines, survivors = [], 0
    code, failed, summary = run_tests(os.path.join(work, "baseline.log"), TESTS + DEVICE_TESTS[2:])
    lines.append(f"BASELINE (unmutated, all four files): exit {code}; {summary}")
    print(lines[-1], flush=True)
    if code != 0:
        sys.exit("baseline is not green; nothing to mutate")

    for index, spec in enumerate(MUTANTS):
        name, rel, edits = spec[:3]
        tests = spec[3] if len(spec) > 3 else TESTS
        if only and name.split(" ", 1)[0] not in only:
            continue
        path = os.path.join(ROOT, rel)
        backup = os.path.join(work, f"orig-{index}.bak")
        shutil.copyfile(path, backup)
        original = open(path, "rb").read()
        text = original.decode("utf-8")
        verdict, failed, summary = "NOT APPLIED", [], ""
        _ACTIVE["path"], _ACTIVE["original"] = path, original
        try:
            for old, new in edits:
                if text.count(old) != 1:
                    raise RuntimeError(f"pattern matched {text.count(old)} times: {old[:60]!r}")
                text = text.replace(old, new)
            open(path, "wb").write(text.encode("utf-8"))
            code, failed, summary = run_tests(os.path.join(work, f"mutant-{index}.log"), tests)
            verdict = "RED" if code != 0 else "SURVIVED"
        except RuntimeError as error:
            summary = str(error)
        finally:
            _restore_active()
        restored = filecmp.cmp(backup, path, shallow=False)
        if verdict != "RED" or not restored:
            survivors += 1
        killers = ", ".join(failed[:3]) + (f", +{len(failed) - 3} more" if len(failed) > 3 else "")
        lines.append(f"{name} -> {verdict} ({len(failed)} failed) restored-identical={restored} | {killers or summary}")
        print(lines[-1], flush=True)

    lines.append(f"SUMMARY: {len(lines) - 1} mutants run, {survivors} not RED or not restored")
    print(lines[-1])
    if args.out:
        open(args.out, "w").write("\n".join(lines) + "\n")
    shutil.rmtree(work, ignore_errors=True)
    sys.exit(1 if survivors else 0)


if __name__ == "__main__":
    main()
