"""The mutation harness's own guards (86ak1090r, rounds 3 and 4).

`docs/delivery/goals/86ak1090r-evidence/mutate.py` mutates production files, and its copy step
deletes `<sandbox>/api` before copying. Aimed at the repository (`--sandbox implementation`, or `.`
from inside it) that would delete the real API tree and every untracked file in it, the venv
included. These tests pin the refusal, and the two matching rules a result depends on.

NON-DESTRUCTIVE BY CONSTRUCTION. A test of a delete guard must not be able to do the deleting if
the guard regresses, and this suite runs in `make api-check` and in CI, on somebody's real
checkout. So every test that goes through `sandbox_copy` runs against a FAKE repository built in
`tmp_path` (the harness's `REPO` and `API` are pointed at it), and `shutil.rmtree` / `copytree`
are fenced to that directory: a regressed guard destroys the fake tree, fails the assertion, and
never reaches the real one. A control proves the fence itself holds.

Outside a full checkout (the Docker image copies only `implementation/api`, so `docs/` and `.git`
are absent) the harness file cannot be found and these tests skip loudly, but never in CI, where
a missing file means the checkout is wrong and a skip would read as a pass.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

# The conftest's session-wide catalogue snapshot needs the test database to exist, even for a
# test that never queries it.
pytestmark = pytest.mark.django_db

_PARENTS = pathlib.Path(__file__).resolve().parents
_DEFAULT_HARNESS = (
    _PARENTS[3] / "docs" / "delivery" / "goals" / "86ak1090r-evidence" / "mutate.py"
    if len(_PARENTS) > 3
    else None
)
# MUTATE_HARNESS_UNDER_TEST points the suite at another copy of the harness, so the guards can be
# shown to bite against a deliberately broken one without editing the real file.
HARNESS = (
    pathlib.Path(os.environ["MUTATE_HARNESS_UNDER_TEST"])
    if os.environ.get("MUTATE_HARNESS_UNDER_TEST")
    else _DEFAULT_HARNESS
)


def missing_harness_reason(path: pathlib.Path | None) -> str | None:
    if path is not None and path.is_file():
        return None
    return (
        "the mutation-harness guard tests CANNOT RUN here, so nothing is being checked: "
        f"{path or 'the repository root'} is missing (only implementation/api is present?)"
    )


@pytest.fixture(scope="module")
def harness():
    reason = missing_harness_reason(HARNESS)
    if reason:
        if os.environ.get("CI"):
            pytest.fail(reason)
        pytest.skip(reason)
    spec = importlib.util.spec_from_file_location("mutate_86ak1090r", HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot(root: pathlib.Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): path.read_text() if path.is_file() else "<dir>"
        for path in sorted(root.rglob("*"))
        if not path.is_symlink()
    }


@pytest.fixture
def fake_repo(harness, tmp_path, monkeypatch):
    """A stand-in repository under tmp_path, with the things whose loss would hurt (a venv, an
    untracked file), the harness pointed at it, and deletion fenced to tmp_path."""
    repo = tmp_path / "fake-repo"
    api = repo / "implementation" / "api"
    (api / "selahcue_api").mkdir(parents=True)
    (api / "selahcue_api" / "services.py").write_text("production code\n")
    (api / ".venv-api-check" / "bin").mkdir(parents=True)
    (api / ".venv-api-check" / "bin" / "python").write_text("a venv the harness must never delete\n")
    (api / "untracked-notes.txt").write_text("work nobody has committed\n")
    (repo / "docs").mkdir()
    monkeypatch.setattr(harness, "REPO", repo)
    monkeypatch.setattr(harness, "API", api)

    fence = tmp_path.resolve()
    real_rmtree, real_copytree = shutil.rmtree, shutil.copytree

    def inside_the_fence(path) -> None:
        resolved = pathlib.Path(path).resolve()
        if resolved != fence and fence not in resolved.parents:
            raise AssertionError(f"the harness tried to touch {resolved}, outside the test's fence {fence}")

    def fenced_rmtree(path, *args, **kwargs):
        inside_the_fence(path)
        return real_rmtree(path, *args, **kwargs)

    def fenced_copytree(src, dst, *args, **kwargs):
        inside_the_fence(dst)
        return real_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", fenced_rmtree)
    monkeypatch.setattr(shutil, "copytree", fenced_copytree)
    return repo


def test_the_fence_itself_holds(fake_repo):
    """Control: without it the tests below would only prove that the fake tree survived."""
    with pytest.raises(AssertionError, match="outside the test's fence"):
        shutil.rmtree("/nonexistent-outside-the-fence-86ak1090r")
    with pytest.raises(AssertionError, match="outside the test's fence"):
        shutil.copytree(fake_repo, "/nonexistent-outside-the-fence-86ak1090r")


@pytest.mark.parametrize(
    "where",
    ["api", "api-parent", "repository", "inside-the-repository", "above-the-repository"],
)
def test_a_sandbox_that_is_or_touches_the_repository_is_refused(harness, fake_repo, where):
    choices = {
        "api": fake_repo / "implementation" / "api",
        "api-parent": fake_repo / "implementation",
        "repository": fake_repo,
        "inside-the-repository": fake_repo / "docs",
        "above-the-repository": fake_repo.parent,
    }
    with pytest.raises(harness.UnsafeSandbox):
        harness.check_sandbox_holder(choices[where])


@pytest.mark.parametrize("where", ["implementation", "api", "repository"])
def test_a_refused_sandbox_leaves_the_tree_untouched_through_the_copy_step_too(harness, fake_repo, where):
    """`sandbox_copy` is the function that deletes. Aimed at the fake repository it must refuse
    before it deletes anything; if it did not, the fake tree would be gone and the real one
    would still be there."""
    before = _snapshot(fake_repo)
    target = {
        "implementation": fake_repo / "implementation",
        "api": fake_repo / "implementation" / "api",
        "repository": fake_repo,
    }[where]

    with pytest.raises(harness.UnsafeSandbox):
        harness.sandbox_copy(target)

    assert _snapshot(fake_repo) == before


def test_a_non_empty_directory_the_harness_did_not_create_is_refused_and_not_touched(harness, fake_repo, tmp_path):
    foreign = tmp_path / "somebody-elses-work"
    (foreign / "api").mkdir(parents=True)
    (foreign / "api" / "precious.txt").write_text("not the harness's\n")

    with pytest.raises(harness.UnsafeSandbox):
        harness.sandbox_copy(foreign)

    assert (foreign / "api" / "precious.txt").read_text() == "not the harness's\n"


def test_a_symlinked_api_directory_is_refused_not_followed_and_not_a_traceback(harness, fake_repo, tmp_path):
    """`shutil.rmtree` refuses a symlink with an OSError; that must surface as a refusal, and the
    place the link points to must stay exactly as it was."""
    elsewhere = tmp_path / "the-link-points-here"
    elsewhere.mkdir()
    (elsewhere / "precious.txt").write_text("behind a symlink\n")
    holder = tmp_path / "marked-holder"
    holder.mkdir()
    (holder / harness.SANDBOX_MARKER).write_text("created by mutate.py\n")
    (holder / "api").symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(harness.UnsafeSandbox, match="symbolic link"):
        harness.sandbox_copy(holder)

    assert (elsewhere / "precious.txt").read_text() == "behind a symlink\n"
    assert (holder / "api").is_symlink()


def test_an_operating_system_error_while_preparing_the_sandbox_is_a_refusal(harness, fake_repo, tmp_path, monkeypatch):
    holder = tmp_path / "fresh-holder"

    def broken_copytree(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(shutil, "copytree", broken_copytree)
    with pytest.raises(harness.UnsafeSandbox, match="could not prepare"):
        harness.sandbox_copy(holder)


def test_new_empty_and_marked_directories_are_accepted(harness, fake_repo, tmp_path):
    harness.check_sandbox_holder(tmp_path / "fresh")
    empty = tmp_path / "empty"
    empty.mkdir()
    harness.check_sandbox_holder(empty)
    marked = tmp_path / "marked"
    marked.mkdir()
    (marked / harness.SANDBOX_MARKER).write_text("created by mutate.py\n")
    (marked / "left-over").write_text("x")
    harness.check_sandbox_holder(marked)


def test_a_good_sandbox_is_copied_and_leaves_the_source_tree_alone(harness, fake_repo, tmp_path):
    before = _snapshot(fake_repo)
    holder = tmp_path / "good-holder"

    copied = harness.sandbox_copy(holder)

    assert (copied / "selahcue_api" / "services.py").read_text() == "production code\n"
    assert not (copied / ".venv-api-check").exists(), "the venv is left out of the copy"
    assert _snapshot(fake_repo) == before


def test_the_self_check_passes(harness):
    """Runs the harness's own `--self-check` against this checkout. It only ASKS whether paths
    are acceptable (`check_sandbox_holder`); it never deletes."""
    result = subprocess.run([sys.executable, str(HARNESS), "--self-check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_missing_interpreter_is_reported_not_a_traceback(harness):
    result = subprocess.run(
        [sys.executable, str(HARNESS), "--python", "./no-such-python", "--only", "D5"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2 and "not found or not executable" in result.stdout


def test_the_harness_imports_and_lists_without_git(harness, tmp_path):
    """A harness that cannot be imported without git cannot be listed or tested in a container
    or a tarball. With an empty PATH `git` does not exist."""
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    result = subprocess.run(
        [sys.executable, str(HARNESS), "--list"],
        capture_output=True, text=True, env={"PATH": str(empty_bin)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "T1-tripwire-removed" in result.stdout


def test_an_intended_test_is_matched_on_its_own_name_not_on_its_path(harness):
    node = "tests/test_license_revoke_extend.py::test_the_writer_refuses_to_run[param-1]"
    assert harness.node_name(node) == "test_the_writer_refuses_to_run[param-1]"
    assert harness.killed_by_an_intended_test([node], ["refuses_to_run"])
    # Fragments that occur only in the file path must not count as a kill.
    assert not harness.killed_by_an_intended_test([node], ["license_revoke_extend", "tests/", ".py"])
    assert not harness.killed_by_an_intended_test([], ["anything"])


def test_a_missing_harness_file_is_reported_as_a_reason_not_an_error(tmp_path):
    assert missing_harness_reason(tmp_path / "nope" / "mutate.py") is not None
    assert missing_harness_reason(None) is not None
    present = tmp_path / "mutate.py"
    present.write_text("x")
    assert missing_harness_reason(present) is None


def test_every_mutant_names_intended_tests_that_exist_in_the_files_it_runs(harness):
    """A fragment that matches no test in the files a mutant runs could never be satisfied; the
    mutant would then be reported KILLED-ELSEWHERE forever, or worse, the typo would go unnoticed
    when the fragment is loose. Checked by collecting the test names, which needs no mutation. It
    reads the real API tree and changes nothing."""
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
