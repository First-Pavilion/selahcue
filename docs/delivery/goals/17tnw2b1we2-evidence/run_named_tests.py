"""Run named tests and FAIL when a name selects nothing.

`cargo test <filter>` exits 0 when the filter matches no test, so a verifier that names a test
which was later renamed passes silently. This lists the tests in one test binary, requires every
given name (a substring filter) to match at least one test, runs exactly the matched tests, and
exits non-zero unless all of them passed.

  python3 run_named_tests.py <package> <test-binary> <name> [<name> ...] [--features F]

Example (Goal Contract C-003):
  python3 docs/delivery/goals/17tnw2b1we2-evidence/run_named_tests.py selahcue-licensing test_client \
      the_source_names_no_cookie_csrf_origin_or_graphql_route \
      every_request_is_a_v1_post_and_only_the_session_activation_carries_a_bearer
  python3 docs/delivery/goals/17tnw2b1we2-evidence/run_named_tests.py --self-test
"""
import re
import subprocess
import sys


def select(listing, names):
    """(matched test names, filters that matched nothing) from `cargo test -- --list` output."""
    tests = [m.group(1) for m in re.finditer(r"^(\S+): test$", listing, re.M)]
    matched, empty = [], []
    for name in names:
        hits = [t for t in tests if name in t]
        if not hits:
            empty.append(name)
        matched.extend(t for t in hits if t not in matched)
    return matched, empty


def passed_count(output):
    counts = re.findall(r"test result: (\w+)\. (\d+) passed; (\d+) failed", output)
    return sum(int(p) for _, p, _ in counts), sum(int(f) for _, _, f in counts)


def self_test():
    listing = "alpha_one: test\nalpha_two: test\nbeta: test\n\n3 tests, 0 benchmarks\n"
    assert select(listing, ["alpha"]) == (["alpha_one", "alpha_two"], [])
    assert select(listing, ["beta", "gone"]) == (["beta"], ["gone"])
    assert select(listing, ["gone"]) == ([], ["gone"])
    assert select("", ["x"]) == ([], ["x"])
    assert passed_count("test result: ok. 2 passed; 0 failed; 0 ignored") == (2, 0)
    assert passed_count("test result: FAILED. 1 passed; 1 failed;") == (1, 1)
    assert passed_count("nothing") == (0, 0)
    print("self-test passed")
    return 0


def main(argv):
    if argv == ["--self-test"]:
        return self_test()
    features = []
    if "--features" in argv:
        i = argv.index("--features")
        features = ["--features", argv[i + 1]]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) < 3:
        print(__doc__)
        return 2
    package, binary, names = argv[0], argv[1], argv[2:]
    base = ["cargo", "test", "-p", package, *features, "--test", binary]
    listing = subprocess.run(base + ["--", "--list"], capture_output=True, text=True)
    if listing.returncode != 0:
        print(listing.stdout + listing.stderr)
        return 2
    matched, empty = select(listing.stdout, names)
    for name in empty:
        print(f"NO TEST MATCHES {name!r} in {package}/{binary}: a renamed or deleted test would otherwise pass silently")
    if empty:
        return 2
    run = subprocess.run(base + ["--", "--exact", *matched], capture_output=True, text=True)
    passed, failed = passed_count(run.stdout + run.stderr)
    print(f"selected {len(matched)} test(s): " + ", ".join(matched))
    print(f"passed {passed}, failed {failed}, cargo exit {run.returncode}")
    if run.returncode != 0 or failed or passed != len(matched):
        print(run.stdout + run.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
