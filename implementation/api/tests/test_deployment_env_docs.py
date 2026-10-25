"""The deployment docs and the code must name the same environment variables (17tnw2b9ab0).

THE BUG THIS PINS. `deployments.md` section 1a told operators to set `DJANGO_SECRET_KEY`,
`DJANGO_DEBUG` and `DATABASE_URL`. `selahcue_api/settings.py` reads none of them: it reads
`SECRET_KEY`, `DEBUG` and the discrete `SQL_*` variables. Nothing failed. Someone following the
doc exactly would have set a variable no code reads, left `ENVIRONMENT` at its default of `dev`,
and started a production API on the public dev signing key, which is also the HMAC pepper for
every licence-key and device-token fingerprint. Rotating it afterwards invalidates them all.

WHAT IS CHECKED, and in which direction:

1. Every variable named in a table row of the API sections of `deployments.md` (1a to 1c) and of
   `docs/ops/DEPLOYMENT.md` (section 6 to 6c) is read by the API. A documented name nothing
   reads is the original bug.
2. Every variable the API reads has a row in `deployments.md`, which is the key registry and says
   so ("single source of truth"). A knob that exists but is not written down is how an operator
   ends up not setting it.
3. Every backticked ALL-CAPS token in those API sections, row or prose, is either a variable the
   API reads or is listed in `NOT_ENV_VARIABLES` below with the reason. This is what catches a
   stale name in a default column or in a "Prod must-set" sentence, which a first-column check
   cannot.
4. Every variable in the desktop table (`deployments.md` section 3a) is read by the Rust code.
5. The "Prod must-set" line names `ENVIRONMENT` and what happens when it is left at `dev`.

HOW THE READS ARE FOUND. By parsing the Python source with `ast`, not by grepping. Every
`os.getenv`, `os.environ.get` and `os.environ[...]` call is found, and so is any helper that
forwards its own parameter into one (`env_bool`, `env_list`, `_socket_timeout_seconds`,
`_csrf_trusted_origins` today). Helpers are DISCOVERED, not listed, so a new helper cannot hide a
read from this test. A read whose name is not a literal string that cannot be traced to a helper
parameter FAILS the test, instead of being skipped: skipping is how a check goes quietly vacuous.

WHY THE TEST CANNOT PASS FOR THE WRONG REASON. Section "the extractor itself" feeds it small
programs with known answers (including the cases above), and the real-file tests assert canaries
(variables that are known to be read and documented), so an extractor or a parser that returns
nothing fails loudly rather than agreeing with an empty doc. The mutation evidence (rename a doc
row, rename a settings read, and watch the matching test go red while its siblings stay green) is
recorded in the PR description for 17tnw2b9ab0.

The `api` CI filter includes both docs, so a docs-only edit re-runs this test.
"""

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

# tests/conftest.py snapshots the migration-installed catalogue in a session fixture that needs the
# test database; pytest-django only builds it when a selected test is marked. Without this the
# guard errors in setup when run on its own (`pytest tests/test_deployment_env_docs.py`). Same
# arrangement as tests/test_nginx_forwarded_proto.py.
pytestmark = pytest.mark.django_db

API_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = API_ROOT.parent.parent
DEPLOYMENTS_MD = REPO_ROOT / "deployments.md"
DEPLOYMENT_OPS_MD = REPO_ROOT / "docs" / "ops" / "DEPLOYMENT.md"
DESKTOP_ROOT = REPO_ROOT / "implementation" / "desktop"

# A variable name as these docs write it: upper-case letters, digits and underscores.
NAME = re.compile(r"[A-Z][A-Z0-9_]*")

# Set by the entry points themselves (`os.environ.setdefault(...)` in manage.py, wsgi.py,
# asgi.py and celery.py). It is Django plumbing, not something an operator configures, so it is
# neither required in the docs nor expected there.
ENTRY_POINT_PLUMBING = {"DJANGO_SETTINGS_MODULE"}

# Backticked ALL-CAPS tokens that appear in the API sections of the docs and are NOT environment
# variables the API reads. Each needs a reason; the test refuses an entry that is not actually
# used, so this list cannot grow stale on its own.
NOT_ENV_VARIABLES = {
    # Django / Celery settings, not variables an operator sets.
    "SECURE_PROXY_SSL_HEADER": "Django setting the TLS-proxy flag sets in settings.py",
    "SILENCED_SYSTEM_CHECKS": "Django setting an operator may add to silence W002",
    "LOGGING": "Django setting; the docs say the repo configures none",
    "CELERY_BROKER_TRANSPORT_OPTIONS": "Celery setting; the docs say settings.py sets none",
    # Fixed budgets, edited in settings.py itself; the docs say so on purpose.
    "SELAHCUE_THROTTLE_ACTIVATION": "fixed budget in settings.py, not an environment variable",
    "SELAHCUE_THROTTLE_SESSION_LOGIN": "fixed budget in settings.py, not an environment variable",
    "SELAHCUE_RESEND_DEGRADED_SEND_CEILING": "fixed ceiling in settings.py, not an environment variable",
    "SELAHCUE_RESET_SEND_DEGRADED_CEILING": "fixed ceiling in settings.py, not an environment variable",
    # Real names the docs mention only to say that nothing reads them.
    "DJANGO_SECRET_KEY": "retired name, quoted only to warn that the API does not read it",
    "DJANGO_DEBUG": "retired name, quoted only to warn that the API does not read it",
    "DATABASE_URL": "retired name, quoted only to warn that the API does not read it",
    # Protocol terms, wire values and commands that happen to be upper case.
    "REMOTE_ADDR": "WSGI request key the rate limiter reads, not an environment variable",
    "UNAUTHENTICATED": "GraphQL error code",
    "RATE_LIMITED": "GraphQL error code",
    "HTTPS": "URL scheme",
    "FLUSHDB": "Redis command",
    "EXISTS": "Redis command",
    "INCR": "Redis command",
    "EXPIRE": "Redis command",
    "SELECT": "Redis command",
}


# =============================== reading env reads out of Python ===============================


class UnresolvableRead(Exception):
    """An environment read whose variable name cannot be determined from the source."""


@dataclass(frozen=True)
class Read:
    name: str
    where: str


def _is_environ(node: ast.AST) -> bool:
    """`os.environ` or a bare `environ` (from os import environ)."""
    if isinstance(node, ast.Attribute):
        return node.attr == "environ" and isinstance(node.value, ast.Name) and node.value.id == "os"
    return isinstance(node, ast.Name) and node.id == "environ"


def _read_name_arg(node: ast.AST) -> ast.AST | None:
    """The expression holding the variable name if `node` reads the environment, else None.

    `os.environ.setdefault` is a write-if-absent, not a read of operator configuration, so it is
    deliberately not matched. `os.environ.pop` is treated as a read: it consumes the value.
    """
    if isinstance(node, ast.Call) and node.args:
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr == "getenv" and isinstance(func.value, ast.Name) and func.value.id == "os":
                return node.args[0]
            if func.attr in {"get", "pop"} and _is_environ(func.value):
                return node.args[0]
        if isinstance(func, ast.Name) and func.id == "getenv":
            return node.args[0]
    if isinstance(node, ast.Subscript) and _is_environ(node.value):
        return node.slice
    return None


def _parameters(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = func.args
    return [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]


def _enclosing_function(parents: dict[int, ast.AST], node: ast.AST):
    current = parents.get(id(node))
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
        current = parents.get(id(current))
    return None


def _call_argument(call: ast.Call, index: int, parameter: str) -> ast.AST | None:
    """The expression passed for a helper's name parameter, positionally or by keyword."""
    if index < len(call.args):
        return call.args[index]
    for keyword in call.keywords:
        if keyword.arg == parameter:
            return keyword.value
    return None


def env_reads(sources: dict[str, str]) -> set[Read]:
    """Every environment variable read by `sources` ({label: python source}), helpers included.

    Raises `UnresolvableRead` for a read whose name is not a literal string and cannot be traced
    to a helper's parameter, so a dynamically named read can never be silently missed.
    """
    trees = {label: ast.parse(text, filename=label) for label, text in sources.items()}
    parents: dict[int, ast.AST] = {}
    for tree in trees.values():
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[id(child)] = parent

    # helper name -> (index, parameter) of the parameter that ends up as an environment name.
    helpers: dict[str, tuple[int, str]] = {}

    def forwarded_parameter(name_arg: ast.AST, node: ast.AST):
        """(function, parameter) if `name_arg` is just a parameter of the function around it."""
        func = _enclosing_function(parents, node)
        if func is not None and isinstance(name_arg, ast.Name) and name_arg.id in _parameters(func):
            return func, name_arg.id
        return None

    changed = True
    while changed:  # fixpoint: a helper that calls a helper is a helper too
        changed = False
        for tree in trees.values():
            for node in ast.walk(tree):
                name_arg = _read_name_arg(node)
                callee_helper = None
                if name_arg is None and isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    callee_helper = helpers.get(node.func.id)
                    if callee_helper is not None:
                        name_arg = _call_argument(node, *callee_helper)
                if name_arg is None:
                    continue
                found = forwarded_parameter(name_arg, node)
                if found is None:
                    continue
                func, parameter = found
                entry = (_parameters(func).index(parameter), parameter)
                if helpers.get(func.name) != entry:
                    helpers[func.name] = entry
                    changed = True

    reads: set[Read] = set()
    for label, tree in trees.items():
        for node in ast.walk(tree):
            name_arg = _read_name_arg(node)
            if name_arg is None and isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                helper = helpers.get(node.func.id)
                if helper is not None:
                    name_arg = _call_argument(node, *helper)
            if name_arg is None:
                continue
            where = f"{label}:{node.lineno}"
            if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str):
                reads.add(Read(name_arg.value, where))
            elif forwarded_parameter(name_arg, node) is None:
                raise UnresolvableRead(
                    f"{where}: environment variable name is not a string literal "
                    f"({ast.unparse(name_arg)!r}); read it with a literal name, or from a helper "
                    "whose parameter is the name, so the deployment docs can be checked against it"
                )
    return reads


def api_source_files() -> dict[str, str]:
    """The API's own Python outside tests: the package and manage.py."""
    files = {}
    for path in [API_ROOT / "manage.py", *sorted((API_ROOT / "selahcue_api").rglob("*.py"))]:
        files[str(path.relative_to(API_ROOT))] = path.read_text(encoding="utf-8")
    return files


def api_env_names() -> set[str]:
    return {read.name for read in env_reads(api_source_files())} - ENTRY_POINT_PLUMBING


# ================================= reading variable names out of docs =================================


@dataclass(frozen=True)
class Mention:
    name: str
    section: str
    is_row: bool  # first cell of a table row, i.e. a documented variable
    line: int


HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
BACKTICKED = re.compile(r"`([^`\n]+)`")


def _token_names(token: str) -> list[str]:
    """The variable name in one backticked span: `NAME` or `NAME=value`, and nothing else. A span
    such as `POST /v1/sessions` or `X-Forwarded-Proto` is prose, not a variable."""
    candidate = token.strip().split("=", 1)[0].strip()
    return [candidate] if NAME.fullmatch(candidate) else []


def doc_mentions(text: str, in_scope) -> list[Mention]:
    """Backticked ALL-CAPS names in the sections `in_scope(heading_stack)` selects.

    A name in the first cell of a table row is `is_row`. Anything inside a fenced code block is
    skipped: those are commands and examples, not documentation of a key.
    """
    mentions: list[Mention] = []
    stack: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading.group(2)))
            continue
        if not in_scope([title for _, title in stack]):
            continue
        section = stack[-1][1] if stack else ""
        stripped = line.strip()
        first_cell_end = None  # index in `line` where the first table cell ends, else None
        if stripped.startswith("|"):
            start = line.index("|") + 1
            end = line.find("|", start)
            first_cell_end = end if end != -1 else len(line)
            if re.fullmatch(r"[\s:\-]*", line[start:first_cell_end]):
                continue  # the |---|---| separator row
        for span in BACKTICKED.finditer(line):
            is_row = first_cell_end is not None and span.start() < first_cell_end
            for name in _token_names(span.group(1)):
                mentions.append(Mention(name, section, is_row, number))
    return mentions


def _scope_matching(*patterns: str):
    compiled = [re.compile(p) for p in patterns]

    def in_scope(titles: list[str]) -> bool:
        return any(c.match(title) for c in compiled for title in titles)

    return in_scope


# deployments.md: the WIRED API sections, plus the closing rules (the "Prod must-set" line).
DEPLOYMENTS_API_SCOPE = _scope_matching(r"1a\.", r"1b\.", r"1c\.", r"1e\.", r"Handling rules")
# DEPLOYMENT.md: the Platform API runtime sections only. The rest is Apple, NDI and GitHub secrets.
OPS_API_SCOPE = _scope_matching(r"6\. ", r"6a\.", r"6b\.", r"6c\.")
DEPLOYMENTS_DESKTOP_SCOPE = _scope_matching(r"3a\.")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def deployments_mentions() -> list[Mention]:
    return doc_mentions(_read(DEPLOYMENTS_MD), DEPLOYMENTS_API_SCOPE)


def ops_mentions() -> list[Mention]:
    return doc_mentions(_read(DEPLOYMENT_OPS_MD), OPS_API_SCOPE)


# ===================================== reading env reads out of Rust =====================================

RUST_ENV_READ = re.compile(r"""(?:env::var(?:_os)?|option_env!)\(\s*"([A-Z][A-Z0-9_]*)"\s*\)""")
SKIPPED_DIRS = {"target", "node_modules", ".git", "vendor"}


def desktop_env_names() -> set[str]:
    names: set[str] = set()
    for directory, subdirs, files in os.walk(DESKTOP_ROOT):
        subdirs[:] = [d for d in subdirs if d not in SKIPPED_DIRS]
        for file in files:
            if file.endswith(".rs"):
                text = (Path(directory) / file).read_text(encoding="utf-8", errors="replace")
                names.update(RUST_ENV_READ.findall(text))
    return names


# =================================================== the real files ===================================================

# Known to be both read by settings.py and documented. If the extractor or a parser ever returns
# nothing, these fail first, so an empty result cannot be mistaken for "nothing is out of step".
API_CANARIES = {"SECRET_KEY", "ENVIRONMENT", "DEBUG", "SQL_ENGINE", "SQL_PASSWORD", "DJANGO_ALLOWED_HOSTS"}
DESKTOP_CANARIES = {"SELAHCUE_PASSPHRASE"}


def _rows(mentions: list[Mention]) -> set[str]:
    return {m.name for m in mentions if m.is_row}


def _describe(mentions: list[Mention], names) -> str:
    where = {}
    for m in mentions:
        if m.name in names:
            where.setdefault(m.name, f"line {m.line} ({m.section})")
    return "; ".join(f"{name} at {where[name]}" for name in sorted(where))


def test_the_extractor_sees_the_real_settings_file():
    """Canaries: the variables below are read by settings.py today. If this fails the extractor
    is broken (or one of them was renamed, in which case update the docs and this list)."""
    names = api_env_names()
    missing = API_CANARIES - names
    assert not missing, f"the extractor did not find {sorted(missing)} in the API source"
    assert len(names) >= 40, f"suspiciously few environment reads found: {len(names)}"


def test_the_doc_parsers_see_the_real_docs():
    assert API_CANARIES <= _rows(deployments_mentions()), "deployments.md sections 1a-1c and 1e lost a canary row"
    assert {"SECRET_KEY", "ENVIRONMENT", "SQL_ENGINE"} <= _rows(ops_mentions()), (
        "docs/ops/DEPLOYMENT.md section 6 lost a canary row"
    )
    assert DESKTOP_CANARIES <= _rows(
        doc_mentions(_read(DEPLOYMENTS_MD), DEPLOYMENTS_DESKTOP_SCOPE)
    ), "deployments.md section 3a lost its desktop rows"


@pytest.mark.parametrize(
    "label, mentions",
    [("deployments.md", deployments_mentions), ("docs/ops/DEPLOYMENT.md", ops_mentions)],
)
def test_every_documented_api_variable_is_read_by_the_api(label, mentions):
    """The original bug: a documented name that nothing reads."""
    read = api_env_names()
    documented = mentions()
    unread = sorted(_rows(documented) - read)
    assert not unread, (
        f"{label} documents API variables that nothing in implementation/api reads: "
        f"{_describe(documented, unread)}. An operator who sets these configures nothing. "
        "Fix the doc to the name the code reads (settings.py is the source of truth)."
    )


def test_every_variable_the_api_reads_has_a_row_in_deployments_md():
    """deployments.md is the key registry, so a knob that exists but has no row is a gap."""
    rows = _rows(deployments_mentions())
    undocumented = sorted(api_env_names() - rows)
    reads = {r.name: r.where for r in env_reads(api_source_files())}
    assert not undocumented, (
        "the API reads variables that deployments.md (sections 1a-1c and 1e) has no row for: "
        + "; ".join(f"{name} read at {reads[name]}" for name in undocumented)
        + ". Add a row in the same change that adds the read."
    )


def test_no_stale_or_unknown_variable_name_appears_in_the_api_sections():
    """Catches a stale name in prose or in a default column, which a first-column check misses
    (the `= DJANGO_DEBUG` default and the "Prod must-set" sentence were exactly that)."""
    read = api_env_names()
    unknown = []
    for label, mentions in (("deployments.md", deployments_mentions()), ("DEPLOYMENT.md", ops_mentions())):
        for m in mentions:
            if m.name not in read and m.name not in NOT_ENV_VARIABLES:
                unknown.append(f"{label}:{m.line} `{m.name}` ({m.section})")
    assert not unknown, (
        "names in the API sections of the deployment docs that the API does not read and that are "
        "not on the NOT_ENV_VARIABLES list: " + "; ".join(unknown)
    )


def test_the_not_env_variables_list_has_no_dead_entries():
    mentioned = {m.name for m in (*deployments_mentions(), *ops_mentions())}
    dead = sorted(set(NOT_ENV_VARIABLES) - mentioned)
    assert not dead, f"NOT_ENV_VARIABLES lists names no doc mentions any more: {dead}"
    now_read = sorted(set(NOT_ENV_VARIABLES) & api_env_names())
    assert not now_read, f"NOT_ENV_VARIABLES lists names the API now reads: {now_read}"


def test_every_documented_desktop_variable_is_read_by_the_desktop_code():
    documented = doc_mentions(_read(DEPLOYMENTS_MD), DEPLOYMENTS_DESKTOP_SCOPE)
    rows = _rows(documented)
    assert rows, "no desktop rows found in deployments.md section 3a"
    read = desktop_env_names()
    assert DESKTOP_CANARIES <= read, "the Rust scan found no env reads: wrong directory or pattern"
    unread = sorted(rows - read)
    assert not unread, (
        f"deployments.md section 3a documents desktop variables the Rust code never reads: "
        f"{_describe(documented, unread)}"
    )


def test_prod_must_set_names_environment_and_what_dev_means():
    """The ticket's second criterion: an operator who stops at the line must learn that leaving
    ENVIRONMENT at `dev` is what keeps the public dev key in use."""
    text = _read(DEPLOYMENTS_MD)
    line = next((l for l in text.splitlines() if "Prod must-set" in l), None)
    assert line is not None, "deployments.md lost its 'Prod must-set' line"
    names = {n for span in BACKTICKED.findall(line) for n in _token_names(span)}
    assert {"ENVIRONMENT", "SECRET_KEY", "DEBUG", "DJANGO_ALLOWED_HOSTS"} <= names, line
    assert "SQL_ENGINE" in names, line
    assert "dev" in line and "refuse" in line.lower(), (
        "the Prod must-set line must say what happens when ENVIRONMENT is left at `dev`"
    )


# ======================================= the extractor itself, on known programs =======================================


def _names(source: str) -> set[str]:
    return {r.name for r in env_reads({"snippet.py": source})}


def test_extractor_finds_each_way_of_reading_the_environment():
    source = """
import os
from os import environ, getenv
a = os.getenv("A_ONE")
b = os.environ.get("B_TWO", "x")
c = os.environ["C_THREE"]
d = environ.get("D_FOUR")
e = getenv("E_FIVE")
f = environ["F_SIX"]
g = os.environ.pop("G_SEVEN", None)
"""
    assert _names(source) == {
        "A_ONE", "B_TWO", "C_THREE", "D_FOUR", "E_FIVE", "F_SIX", "G_SEVEN",
    }


def test_extractor_follows_helpers_that_forward_their_name_parameter():
    source = """
import os
def env_bool(name, default):
    return os.getenv(name) is not None
def outer(label, other):
    return env_bool(label, other)
def outermost(first, second=None):
    return outer(first, True)
a = env_bool("HELPER_ONE", False)
b = outer("HELPER_TWO", 1)
c = outermost(second=3, first="HELPER_THREE")
d = env_bool(name="HELPER_FOUR", default=True)
"""
    assert _names(source) == {"HELPER_ONE", "HELPER_TWO", "HELPER_THREE", "HELPER_FOUR"}


def test_extractor_ignores_setdefault_and_unrelated_calls():
    source = """
import os
os.environ.setdefault("NOT_A_READ", "x")
settings.get("ALSO_NOT")
other.getenv("NOR_THIS")
"""
    assert _names(source) == set()


def test_extractor_refuses_a_read_it_cannot_name():
    """A dynamic name must fail the test, not be skipped: skipping would hide a variable."""
    with pytest.raises(UnresolvableRead):
        _names('import os\nPREFIX = "A_"\nx = os.getenv(PREFIX + "B")\n')
    with pytest.raises(UnresolvableRead):
        _names('import os\nx = os.getenv(f"SELAHCUE_{kind}")\n')
    with pytest.raises(UnresolvableRead):
        _names('import os\ndef f():\n    return os.getenv(name_from_elsewhere)\n')


def test_extractor_reads_a_name_inside_a_literal_argument_to_a_helper():
    source = """
import os
def env_list(name, default=""):
    return os.getenv(name, default).split()
CSRF = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
"""
    assert _names(source) == {"DJANGO_CSRF_TRUSTED_ORIGINS"}


# =================================== the doc parser itself, on known documents ===================================


def test_doc_parser_separates_rows_from_prose_and_respects_scope():
    text = """
## In scope

| Key | Default |
|---|---|
| `ROW_ONE` | `DEFAULT_MENTION` |
| `ROW_TWO` / `ROW_THREE` | x |
| `ROW_FOUR=1` | y |

Prose naming `PROSE_ONLY` here.

```
`FENCED_NAME`
```

## Out of scope

| `OUTSIDE_ROW` | x |
"""
    found = doc_mentions(text, _scope_matching(r"In scope"))
    assert {m.name for m in found if m.is_row} == {"ROW_ONE", "ROW_TWO", "ROW_THREE", "ROW_FOUR"}
    assert {m.name for m in found if not m.is_row} == {"DEFAULT_MENTION", "PROSE_ONLY"}
    assert "FENCED_NAME" not in {m.name for m in found}
    assert "OUTSIDE_ROW" not in {m.name for m in found}


def test_doc_parser_scopes_by_enclosing_heading_not_only_the_nearest_one():
    text = "## 6. Runtime\n\n### Subsection\n\n| `NESTED_ROW` | x |\n\n## 7. Next\n\n| `AFTER_ROW` | x |\n"
    found = doc_mentions(text, _scope_matching(r"6\. "))
    assert {m.name for m in found} == {"NESTED_ROW"}
