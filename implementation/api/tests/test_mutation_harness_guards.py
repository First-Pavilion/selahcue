"""The mutation harness's own guards (86ak1090r, round 3).

`docs/delivery/goals/86ak1090r-evidence/mutate.py` mutates production files, and its copy step
deletes `<sandbox>/api` before copying. Aimed at the repository (`--sandbox implementation`, or `.`
from inside it) that would delete the real API tree and every untracked file in it, the venv
included. These tests pin the refusal, and the two matching rules a result depends on, so a harness
that gets those wrong fails here instead of quietly reporting kills or deleting work.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import pytest

# The conftest's session-wide catalogue snapshot needs the test database to exist, even for a
# test that never queries it.
pytestmark = pytest.mark.django_db

HARNESS = (
    pathlib.Path(__file__).resolve().parents[3]
    / "docs"
    / "delivery"
    / "goals"
    / "86ak1090r-evidence"
    / "mutate.py"
)


@pytest.fixture(scope="module")
def harness():
    spec = importlib.util.spec_from_file_location("mutate_86ak1090r", HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "target",
    ["api", "api-parent", "repository", "inside-the-repository", "above-the-repository"],
)
def test_a_sandbox_that_is_or_touches_the_repository_is_refused(harness, target):
    choices = {
        "api": harness.API,
        "api-parent": harness.API.parent,
        "repository": harness.REPO,
        "inside-the-repository": harness.REPO / "docs",
        "above-the-repository": harness.REPO.parent,
    }
    with pytest.raises(harness.UnsafeSandbox):
        harness.check_sandbox_holder(choices[target])


def test_a_refused_sandbox_leaves_the_real_api_tree_untouched(harness):
    before = sorted(p.name for p in harness.API.iterdir())
    with pytest.raises(harness.UnsafeSandbox):
        harness.sandbox_copy(harness.API.parent)
    assert sorted(p.name for p in harness.API.iterdir()) == before
    assert (harness.API / "selahcue_api").is_dir()


def test_a_non_empty_directory_the_harness_did_not_create_is_refused_and_not_touched(harness, tmp_path):
    foreign = tmp_path / "somebody-elses-work"
    (foreign / "api").mkdir(parents=True)
    (foreign / "api" / "precious.txt").write_text("not the harness's\n")

    with pytest.raises(harness.UnsafeSandbox):
        harness.sandbox_copy(foreign)

    assert (foreign / "api" / "precious.txt").read_text() == "not the harness's\n"


def test_new_empty_and_marked_directories_are_accepted(harness, tmp_path):
    harness.check_sandbox_holder(tmp_path / "fresh")
    empty = tmp_path / "empty"
    empty.mkdir()
    harness.check_sandbox_holder(empty)
    marked = tmp_path / "marked"
    marked.mkdir()
    (marked / harness.SANDBOX_MARKER).write_text("created by mutate.py\n")
    (marked / "left-over").write_text("x")
    harness.check_sandbox_holder(marked)


def test_the_self_check_passes():
    result = subprocess.run([sys.executable, str(HARNESS), "--self-check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_missing_interpreter_is_reported_not_a_traceback():
    result = subprocess.run(
        [sys.executable, str(HARNESS), "--python", "./no-such-python", "--only", "D5"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2 and "not found or not executable" in result.stdout


def test_an_intended_test_is_matched_on_its_own_name_not_on_its_path(harness):
    node = "tests/test_license_revoke_extend.py::test_the_writer_refuses_to_run[param-1]"
    assert harness.node_name(node) == "test_the_writer_refuses_to_run[param-1]"
    assert harness.killed_by_an_intended_test([node], ["refuses_to_run"])
    # Fragments that occur only in the file path must not count as a kill.
    assert not harness.killed_by_an_intended_test([node], ["license_revoke_extend", "tests/", ".py"])
    assert not harness.killed_by_an_intended_test([], ["anything"])


def test_every_mutant_names_intended_tests_that_exist_in_the_files_it_runs(harness):
    """A fragment that matches no test in the files a mutant runs could never be satisfied; the
    mutant would then be reported KILLED-ELSEWHERE forever, or worse, the typo would go unnoticed
    when the fragment is loose. Checked by collecting the test names, which needs no mutation."""
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         *sorted({f for spec in harness.MUTANTS.values() for f in spec["tests"]})],
        cwd=harness.API, capture_output=True, text=True,
    )
    names_by_file: dict[str, list[str]] = {}
    for line in collected.stdout.splitlines():
        if "::" in line:
            path, name = line.split("::", 1)
            names_by_file.setdefault(path, []).append(name)
    unmatched = []
    for mid, spec in harness.MUTANTS.items():
        if not spec["kill"]:
            continue
        names = [n for f in spec["tests"] for n in names_by_file.get(f, [])]
        if not names:
            unmatched.append((mid, "no tests collected from " + ", ".join(spec["tests"])))
        elif not any(fragment in name for fragment in spec["kill"] for name in names):
            unmatched.append((mid, spec["kill"]))
    assert unmatched == [], unmatched
