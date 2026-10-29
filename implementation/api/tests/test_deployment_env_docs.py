"""The deployment docs and the code must name the same environment variables (17tnw2b9ab0).

THE BUG THIS PINS. `deployments.md` section 1a told operators to set `DJANGO_SECRET_KEY`,
`DJANGO_DEBUG` and `DATABASE_URL`. `selahcue_api/settings.py` reads none of them: it reads
`SECRET_KEY`, `DEBUG` and the discrete `SQL_*` variables. Nothing failed. Someone following the
doc exactly would have set a variable no code reads, left `ENVIRONMENT` at its default of `dev`,
and started a production API on the public dev signing key, which is also the HMAC pepper for
every licence-key and device-token fingerprint. Rotating it afterwards invalidates them all.

WHAT IS CHECKED, and in which direction:

1. Every variable named in a table row of the API sections of `deployments.md` (1a to 1c, 1e) and
   of `docs/ops/DEPLOYMENT.md` (section 6 to 6c) is read by the API. A documented name nothing
   reads is the original bug.
2. Every variable the API reads has a row in `deployments.md`, which is the key registry and says
   so ("single source of truth"). A knob that exists but is not written down is how an operator
   ends up not setting it.
3. Every backticked ALL-CAPS token in those API sections, row or prose, is either a variable the
   API reads or is listed in `NOT_ENV_VARIABLES` below with the reason. This is what catches a
   stale name in a default column or in a "Prod must-set" sentence, which a first-column check
   cannot.
4. Every variable in the desktop table (`deployments.md` section 3a) is read by the Rust code.
5. The "Prod must-set" line leads with `ENVIRONMENT` and says, in that clause, what happens when
   it is left unset; and every row marked `prod: yes` is named in the "Handling rules" section.
6. In those sections every table is one block with its header. A blank line inside a table makes
   the rows below it render as a paragraph of pipes, and the row-based checks above cannot see
   that (they treat any line starting with `|` as a row).

HOW THE READS ARE FOUND. By parsing the Python source with `ast`, not by grepping (see
`tests/envscan.py`, which also says what is scanned: `manage.py` and `selahcue_api/**/*.py` only).
Helpers that forward their own parameter into an environment read are DISCOVERED, not listed, so a
new helper cannot hide a read. A read whose name cannot be determined FAILS the test instead of
being skipped: skipping is how a check goes quietly vacuous.

WHY THE TEST CANNOT PASS FOR THE WRONG REASON. The "extractor itself" and "doc parser itself"
sections feed small programs and documents with known answers, and the real-file tests assert
canaries (variables known to be read and documented) and cross-check the extractor against a
naive text search, so an extractor or a parser that returns nothing fails loudly rather than
agreeing with an empty doc. The checks were mutation-verified when written: renaming one doc row,
one settings read, one row in the ops doc, or one desktop row each turned the matching test red
while the unrelated ones stayed green.

WHEN THIS RUNS. It reads files above `implementation/api` (the two docs and the desktop Rust
sources). Where those are absent, for example in the API Docker image, the real-file tests SKIP
with a loud reason, unless the `CI` environment variable is set, in which case they FAIL. CI
re-runs this only when a commit changes the docs together with a file the workflow does not
ignore: both workflow triggers carry `paths-ignore` for `docs/**` and `**.md`, so a docs-only
edit does not start CI. That edit is covered by `make api-check` and by the weekly scheduled run.
"""

import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from envscan import ENTRY_POINT_PLUMBING, UnresolvableRead, api_env_names, api_source_files, env_reads

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

# Names the docs used to tell operators to set. The API reads none of them. They may be mentioned,
# but ONLY in a sentence that says the API does not read them (the warning at the top of
# deployments.md section 1a): a retired name anywhere else, a default column or a "Prod
# must-set" line included, is the original bug. Each needs to be mentioned at least once, so the
# warning cannot be deleted without this list (and its reason) being revisited.
RETIRED_NAMES = {"DJANGO_SECRET_KEY", "DJANGO_DEBUG", "DATABASE_URL"}
RETIRED_WARNING = re.compile(r"does \*{0,2}not\*{0,2} read", re.IGNORECASE)

# Backticked ALL-CAPS tokens that appear in the API sections of the docs and are NOT environment
# variables the API reads. Each needs a reason; the test refuses an entry that is not actually
# used, so this list cannot grow stale on its own.
NOT_ENV_VARIABLES = {
    # Django / Celery settings, not variables an operator sets.
    "SECURE_PROXY_SSL_HEADER": "Django setting the TLS-proxy flag sets in settings.py",
    "SILENCED_SYSTEM_CHECKS": "Django setting an operator may add to silence W002",
    "LOGGING": "Django setting; the docs say the repo configures none",
    "CELERY_BROKER_TRANSPORT_OPTIONS": "Python Celery setting populated by the explicit broker socket environment variables",
    # Fixed budgets, edited in settings.py itself; the docs say so on purpose.
    "SELAHCUE_THROTTLE_ACTIVATION": "fixed budget in settings.py, not an environment variable",
    "SELAHCUE_THROTTLE_SESSION_LOGIN": "fixed budget in settings.py, not an environment variable",
    "SELAHCUE_RESEND_DEGRADED_SEND_CEILING": "fixed ceiling in settings.py, not an environment variable",
    "SELAHCUE_RESET_SEND_DEGRADED_CEILING": "fixed ceiling in settings.py, not an environment variable",
    "SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE": "fixed brake in settings.py, not an environment variable",
    "SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE_ACCOUNT": "fixed allowance in settings.py, not an environment variable",
    "SELAHCUE_RESET_CONFIRM_TRACE_DEGRADED_CEILING": "fixed ceiling in settings.py, not an environment variable",
    "SELAHCUE_RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING": "fixed ceiling in settings.py, not an environment variable",
    "SECRET_KEY_FALLBACKS": "Django setting; the runbook says the failed-confirm pseudonym does not consult it",
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


# ================================= reading variable names out of docs =================================


@dataclass(frozen=True)
class Mention:
    name: str
    section: str
    is_row: bool  # first cell of a table row, i.e. a documented variable
    line: int
    text: str = ""  # the whole line it was found on


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
                mentions.append(Mention(name, section, is_row, number, line))
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


DELIMITER_CELL = re.compile(r"\s*:?-+:?\s*")
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


def _table_cells(line: str) -> list[str]:
    """The cells of one table row: leading and trailing pipe dropped, split on unescaped pipes."""
    row = line.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
    return UNESCAPED_PIPE.split(row)


def _is_delimiter_row(line: str, header: str) -> bool:
    """GitHub renders a table only when the second line is a delimiter row (every cell `-`s with
    optional `:` alignment, ONE hyphen or more) with as many cells as the header."""
    cells = _table_cells(line)
    return len(cells) == len(_table_cells(header)) and all(DELIMITER_CELL.fullmatch(c) for c in cells)




def table_problems(text: str, in_scope) -> list[str]:
    """Tables in the scoped sections that would not render as tables.

    A table is a block of consecutive lines starting with `|`, and Markdown renders it only when
    its SECOND line is the `---` separator. A blank line or a quoted paragraph in the middle of
    one ends the table; the rows after it become a block with no header, which renders as a
    paragraph of pipes. That is what happened to the six ACCOUNT_* rows in
    docs/ops/DEPLOYMENT.md, and the row-based checks cannot see it.
    """
    problems: list[str] = []
    stack: list[tuple[int, str]] = []
    in_fence = False
    block: list[tuple[int, str]] = []

    def close(block):
        if block and not (len(block) >= 2 and _is_delimiter_row(block[1][1], block[0][1])):
            first = block[0][0]
            problems.append(
                f"line {first}: `{block[0][1].strip()[:60]}` starts a block of table rows with no "
                "header and matching delimiter row above it (a blank line or quoted text inside the table, or a header and delimiter of different widths?)"
            )

    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            close(block)
            block = []
            continue
        if in_fence:
            continue
        heading = HEADING.match(line)
        if heading:
            close(block)
            block = []
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading.group(2)))
            continue
        if line.strip().startswith("|") and in_scope([title for _, title in stack]):
            block.append((number, line))
        else:
            close(block)
            block = []
    close(block)
    return problems


@pytest.fixture
def repo_docs():
    """The real-file tests read the two docs and the desktop sources, which sit above
    implementation/api. Where they are absent (the API Docker image mounts only that directory)
    skip loudly, but never in CI: there, absent files mean the checkout is wrong, and a skip
    would read as a pass."""
    missing = [str(path) for path in (DEPLOYMENTS_MD, DEPLOYMENT_OPS_MD, DESKTOP_ROOT) if not path.exists()]
    if not missing:
        return
    reason = (
        "the deployment-docs drift check CANNOT RUN here, so nothing is being checked: missing "
        + ", ".join(missing)
        + " (only implementation/api is present?)"
    )
    if os.environ.get("CI"):
        pytest.fail(reason)
    pytest.skip(reason)


def prod_required_names(mentions: list[Mention]) -> set[str]:
    """Rows whose Required cell says they are needed in production ("prod: yes", "prod behind a
    TLS proxy: yes"). The Required cell is the second one in the row."""
    names = set()
    for m in mentions:
        if not m.is_row:
            continue
        cells = m.text.strip().strip("|").split("|")
        if len(cells) > 1 and re.search(r"prod\b[^|]*:\s*yes", cells[1], re.IGNORECASE):
            names.add(m.name)
    return names


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


# A deliberately naive second opinion on what the API reads: a text search for the common shapes
# with a literal name. The AST extractor must find at least everything this finds; if it does not,
# the extractor has gone blind to something, which a hard-coded "at least N reads" would not notice
# until N happened to be crossed.
NAIVE_READ = re.compile(
    r"""(?:\b(?:getenv|env_bool|env_list|_socket_timeout_seconds|_csrf_trusted_origins)\(|environ\.get\(|environ\[)"""
    r"""\s*["']([A-Z][A-Z0-9_]*)["']"""
)


def naive_read_names(source: str) -> set[str]:
    """Names the naive search finds in `source`, ignoring whole-line comments: a comment that
    mentions `os.getenv("OLD")` is not a read, and counting it would fail this check with a
    message about the extractor when the extractor is right."""
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    return set(NAIVE_READ.findall(code))


def test_the_extractor_sees_the_real_settings_file():
    """Canaries: the variables below are read by settings.py today. If this fails the extractor
    is broken (or one of them was renamed, in which case update the docs and this list)."""
    names = api_env_names()
    missing = API_CANARIES - names
    assert not missing, f"the extractor did not find {sorted(missing)} in the API source"
    naive = {
        name for source in api_source_files().values() for name in naive_read_names(source)
    } - ENTRY_POINT_PLUMBING
    assert naive >= API_CANARIES, "the naive search is blind too: this check no longer checks anything"
    assert naive <= names, f"the extractor missed variables a plain text search finds: {sorted(naive - names)}"


def test_the_doc_parsers_see_the_real_docs(repo_docs):
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
def test_every_documented_api_variable_is_read_by_the_api(repo_docs, label, mentions):
    """The original bug: a documented name that nothing reads."""
    read = api_env_names()
    documented = mentions()
    unread = sorted(_rows(documented) - read)
    assert not unread, (
        f"{label} documents API variables that nothing in implementation/api reads: "
        f"{_describe(documented, unread)}. An operator who sets these configures nothing. "
        "Fix the doc to the name the code reads (settings.py is the source of truth)."
    )


def test_every_variable_the_api_reads_has_a_row_in_deployments_md(repo_docs):
    """deployments.md is the key registry, so a knob that exists but has no row is a gap."""
    rows = _rows(deployments_mentions())
    undocumented = sorted(api_env_names() - rows)
    reads = {r.name: r.where for r in env_reads(api_source_files())}
    assert not undocumented, (
        "the API reads variables that deployments.md (sections 1a-1c and 1e) has no row for: "
        + "; ".join(f"{name} read at {reads[name]}" for name in undocumented)
        + ". Add a row in the same change that adds the read."
    )


def test_no_stale_or_unknown_variable_name_appears_in_the_api_sections(repo_docs):
    """Catches a stale name in prose or in a default column, which a first-column check misses
    (the `= DJANGO_DEBUG` default and the "Prod must-set" sentence were exactly that)."""
    read = api_env_names()
    unknown = []
    for label, mentions in (("deployments.md", deployments_mentions()), ("DEPLOYMENT.md", ops_mentions())):
        for m in mentions:
            if m.name in read or m.name in NOT_ENV_VARIABLES:
                continue
            if m.name in RETIRED_NAMES and RETIRED_WARNING.search(m.text):
                continue  # the one place a retired name may appear: saying it is not read
            unknown.append(f"{label}:{m.line} `{m.name}` ({m.section})")
    assert not unknown, (
        "names in the API sections of the deployment docs that the API does not read and that are "
        "not on the NOT_ENV_VARIABLES list (a retired name is allowed only in a sentence saying "
        "the API does not read it): " + "; ".join(unknown)
    )


def test_the_retired_names_are_still_warned_about(repo_docs):
    mentioned = {m.name for m in deployments_mentions() if RETIRED_WARNING.search(m.text)}
    assert RETIRED_NAMES <= mentioned, (
        f"deployments.md no longer warns that the API does not read {sorted(RETIRED_NAMES - mentioned)}"
    )
    assert not (RETIRED_NAMES & api_env_names()), "the API reads a name on RETIRED_NAMES now: update the docs"


def test_the_not_env_variables_list_has_no_dead_entries(repo_docs):
    mentioned = {m.name for m in (*deployments_mentions(), *ops_mentions())}
    dead = sorted(set(NOT_ENV_VARIABLES) - mentioned)
    assert not dead, f"NOT_ENV_VARIABLES lists names no doc mentions any more: {dead}"
    now_read = sorted(set(NOT_ENV_VARIABLES) & api_env_names())
    assert not now_read, f"NOT_ENV_VARIABLES lists names the API now reads: {now_read}"


def test_every_documented_desktop_variable_is_read_by_the_desktop_code(repo_docs):
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


def _prod_must_set_line() -> str:
    line = next((l for l in _read(DEPLOYMENTS_MD).splitlines() if "Prod must-set" in l), None)
    assert line is not None, "deployments.md lost its 'Prod must-set' line"
    return line


def test_prod_must_set_leads_with_environment_and_says_what_unset_means(repo_docs):
    """The ticket's second criterion. An operator who stops after the first clause must learn
    that leaving ENVIRONMENT unset is what keeps the public dev key in use, without any error.
    The ENVIRONMENT clause is checked on its own, up to where SECRET_KEY is named: the SECRET_KEY
    clause also says 'dev' and 'refuses', so a looser check passes with the ENVIRONMENT
    explanation deleted."""
    line = _prod_must_set_line()
    assert line.startswith("- **Prod must-set:** `ENVIRONMENT`"), f"ENVIRONMENT must come first: {line}"
    clause = line[: line.index("`SECRET_KEY`")]
    assert "left unset it is `dev`" in clause, f"the ENVIRONMENT clause lost its explanation: {clause}"
    assert "public dev signing key" in clause and "without any error" in clause, clause
    ordered = [n for span in BACKTICKED.findall(line) for n in _token_names(span)]
    assert {"SECRET_KEY", "DEBUG", "DJANGO_ALLOWED_HOSTS", "SQL_ENGINE"} <= set(ordered), line


def test_every_prod_required_row_is_named_in_the_handling_rules(repo_docs):
    """The Prod must-set list is what an operator copies from, so it cannot lag the tables: any
    row whose Required cell says `prod: yes` has to be named in the Handling rules section."""
    mentions = deployments_mentions()
    required = prod_required_names(mentions)
    assert {"ENVIRONMENT", "SECRET_KEY", "CACHE_URL", "SQL_PASSWORD"} <= required, (
        f"the Required-cell parser found too little: {sorted(required)}"
    )
    named = {m.name for m in mentions if m.section == "Handling rules"}
    missing = sorted(required - named)
    assert not missing, (
        f"rows marked prod: yes that the Handling rules (Prod must-set) never name: {missing}"
    )


@pytest.mark.parametrize(
    "label, text_of, scope",
    [
        ("deployments.md", lambda: _read(DEPLOYMENTS_MD), DEPLOYMENTS_API_SCOPE),
        ("docs/ops/DEPLOYMENT.md", lambda: _read(DEPLOYMENT_OPS_MD), OPS_API_SCOPE),
    ],
)
def test_every_table_in_the_api_sections_renders_as_one_table(repo_docs, label, text_of, scope):
    problems = table_problems(text_of(), scope)
    assert not problems, f"{label}: " + "; ".join(problems)


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


def test_extractor_ignores_writes_and_unrelated_calls():
    source = """
import os
os.environ.setdefault("NOT_A_READ", "x")
os.environ["ALSO_NOT"] = "y"
del os.environ["NOR_THIS"]
settings.get("NOR_THAT")
cache.pop("OR_THIS")
"""
    assert _names(source) == set()


def test_extractor_sees_through_import_aliases():
    """`import os as _os` and `from os import environ as e` must not hide a read: this is the gap
    the mutation run found in the first version of this module."""
    source = """
import os as _os
import os as operating_system
from os import environ as e, getenv as g
a = _os.getenv("ALIAS_ONE")
b = operating_system.environ.get("ALIAS_TWO")
c = e["ALIAS_THREE"]
d = g("ALIAS_FOUR")
f = e.get("ALIAS_FIVE")
"""
    assert _names(source) == {"ALIAS_ONE", "ALIAS_TWO", "ALIAS_THREE", "ALIAS_FOUR", "ALIAS_FIVE"}


@pytest.mark.parametrize(
    "source",
    [
        "import os\nx = dict(os.environ)\n",
        "import os\nx = {**os.environ}\n",
        "import os\nfor k in os.environ:\n    pass\n",
        "import os\nx = os.environ.copy()\n",
        "import os\nfrom os import environ\nx = list(environ.items())\n",
        "import os\nf = os.getenv\nx = f('A')\n",
        "import os\nx = getattr(os, 'getenv')('A')\n",
    ],
)
def test_extractor_refuses_whole_or_indirect_use_of_the_environment(source):
    with pytest.raises(UnresolvableRead):
        _names(source)


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


def _run_with_deadline(function, seconds=5.0):
    """Run `function` in a daemon thread and fail, rather than hang the suite, if it does not
    finish: CI's api job has a 15 minute timeout and a non-terminating extractor would burn all of
    it. (pytest-timeout is not a dependency of this project.)"""
    outcome = {}

    def target():
        try:
            outcome["value"] = function()
        except BaseException as error:  # re-raised below, in the test's own thread
            outcome["error"] = error

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    assert not thread.is_alive(), f"did not finish within {seconds}s: a fixpoint that does not terminate?"
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


def test_extractor_terminates_and_reads_both_names_of_a_helper_that_forwards_two_parameters():
    """A helper that forwards TWO of its own parameters used to flip its single stored entry
    between them forever. Each read must be found, and it must finish."""
    source = """
import os
def both(first, second):
    return os.getenv(first), os.getenv(second)
def chained(a, b):
    return both(b, a)
x = both("TWO_ONE", "TWO_TWO")
y = chained("TWO_THREE", "TWO_FOUR")
"""
    assert _run_with_deadline(lambda: _names(source)) == {"TWO_ONE", "TWO_TWO", "TWO_THREE", "TWO_FOUR"}


def test_extractor_reads_keyword_name_arguments():
    source = """
import os
a = os.getenv(key="KW_ONE")
b = os.environ.get(key="KW_TWO", default="x")
c = os.environ.pop(key="KW_THREE")
"""
    assert _names(source) == {"KW_ONE", "KW_TWO", "KW_THREE"}


@pytest.mark.parametrize(
    "source",
    [
        "import os\nx = os.getenv()\n",
        "import os\nx = os.getenv(**options)\n",
        "import os\nx = os.environ.get(default='x')\n",
        "import os\nx = os.getenv(*names)\n",
        "import os\nx = os.getenv(key=name_from_elsewhere)\n",
    ],
)
def test_extractor_refuses_a_read_with_no_findable_name(source):
    with pytest.raises(UnresolvableRead):
        _names(source)


HELPER_PRELUDE = """
import os
import util
def env_bool(name, default):
    return os.getenv(name) is not None
class Config:
    def rd(self, name):
        return os.getenv(name)
    @staticmethod
    def sd(name):
        return os.getenv(name)
"""


def test_extractor_finds_helper_calls_that_are_not_plain_names():
    """A helper is discovered by its definition, so every way of CALLING it has to be read too:
    `util.env_bool("X")`, `self.rd("X")` (the call omits `self`), `Config.sd("X")`. A call site
    that returned no name and no error would let a variable hide behind a helper."""
    source = HELPER_PRELUDE + """
class Loader:
    def load(self, config):
        return config.rd("METHOD_CALLED"), Config.sd("STATIC_CALLED")
x = util.env_bool("ATTR_CALLED", False)
y = util.env_bool(name="ATTR_KEYWORD", default=True)
"""
    assert _names(source) == {"METHOD_CALLED", "STATIC_CALLED", "ATTR_CALLED", "ATTR_KEYWORD"}


@pytest.mark.parametrize(
    "use",
    [
        pytest.param("flag = env_bool\nflag('ALIASED_HELPER', False)\n", id="aliased-by-assignment"),
        pytest.param("values = list(map(env_bool, ['A_ONE', 'B_TWO']))\n", id="passed-as-a-callback"),
        pytest.param("table = {'flag': env_bool}\n", id="stored-in-a-dict"),
        pytest.param("flag = util.env_bool\nflag('ALIASED_ATTRIBUTE', False)\n", id="attribute-aliased"),
        pytest.param("reader = Config().rd\nreader('BOUND_METHOD')\n", id="bound-method-aliased"),
        pytest.param("values = list(map(Config.sd, ['A_ONE']))\n", id="static-method-as-callback"),
    ],
)
def test_extractor_refuses_a_helper_used_other_than_as_a_direct_call(use):
    """The same rule as for `getenv`: a discovered helper that appears anywhere other than as the
    callee of a call could be reaching the environment through a name this module cannot follow,
    so it is a failure, not a skip."""
    with pytest.raises(UnresolvableRead):
        _names(HELPER_PRELUDE + use)


def test_extractor_accepts_a_helper_that_is_only_defined_and_called_directly():
    """The negative control for the refusal above: definitions, direct calls and recursion are not
    'other uses'."""
    source = HELPER_PRELUDE + """
def retry(name, tries):
    return retry(name, tries - 1) if tries else env_bool(name, False)
z = retry("RECURSIVE_ONE", 3)
"""
    assert _names(source) == {"RECURSIVE_ONE"}


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


def test_table_check_accepts_a_proper_table_and_flags_a_split_one():
    good = "## S\n\n| A | B |\n|---|---|\n| `ONE` | x |\n| `TWO` | y |\n"
    assert table_problems(good, _scope_matching(r"S")) == []

    split = "## S\n\n| A | B |\n|---|---|\n| `ONE` | x |\n\n| `TWO` | y |\n| `THREE` | z |\n"
    problems = table_problems(split, _scope_matching(r"S"))
    assert len(problems) == 1 and "line 7" in problems[0], problems

    interrupted = "## S\n\n| A | B |\n|---|---|\n| `ONE` | x |\n> a quoted note\n| `TWO` | y |\n"
    assert len(table_problems(interrupted, _scope_matching(r"S"))) == 1

    headerless = "## S\n\n| `ONE` | x |\n| `TWO` | y |\n"
    assert len(table_problems(headerless, _scope_matching(r"S"))) == 1

    out_of_scope = "## Other\n\n| `ONE` | x |\n"
    assert table_problems(out_of_scope, _scope_matching(r"S")) == []


@pytest.mark.parametrize(
    "separator", ["|---|---|", "|--|--|", "|-|-|", "|:--|--:|", "| :-: | --- |", "|:-|-:|"]
)
def test_table_check_accepts_every_separator_row_github_renders(separator):
    text = f"## S\n\n| A | B |\n{separator}\n| `ONE` | x |\n"
    assert table_problems(text, _scope_matching(r"S")) == []


def test_table_check_flags_a_header_and_separator_with_different_widths():
    """GitHub does not render a table whose header and delimiter rows differ in cell count."""
    wider = "## S\n\n| A | B | C |\n|---|---|\n| `ONE` | x |\n"
    assert len(table_problems(wider, _scope_matching(r"S"))) == 1
    narrower = "## S\n\n| A | B |\n|---|---|---|\n| `ONE` | x |\n"
    assert len(table_problems(narrower, _scope_matching(r"S"))) == 1


def test_table_check_flags_a_second_row_that_is_not_a_separator():
    text = "## S\n\n| A | B |\n| `ONE` | x |\n| `TWO` | y |\n"
    assert len(table_problems(text, _scope_matching(r"S"))) == 1


def test_the_naive_search_ignores_comment_lines():
    source = '# was os.getenv("OLD_NAME")\n    # env_bool("ALSO_OLD", False)\nx = os.getenv("NEW_NAME")\n'
    assert naive_read_names(source) == {"NEW_NAME"}
