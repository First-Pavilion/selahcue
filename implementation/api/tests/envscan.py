"""Which environment variables does the API read? Found by parsing the Python, not by grepping.

Shared by `test_deployment_env_docs.py` (the deployment docs must name exactly these variables)
and `test_deployment_guards.py` (a test of settings.py must not inherit any of them from the
machine running the suite). Both need the SAME list, derived the same way, so that neither can
go stale when a variable is added: a hand-written list of "variables to clear" is exactly how the
SQL_ENGINE a CI runner exports leaked into a test of the SQLite fallback.

Not a test module (no `test_` prefix, nothing collected). pytest puts this directory on
`sys.path`, so both test modules do `import envscan`.

WHAT IT FINDS. Every `os.getenv`, `os.environ.get`, `os.environ.pop` and `os.environ[...]` read
with a literal name, plus any helper that forwards its own parameter(s) into one (`env_bool`,
`env_list`, `_socket_timeout_seconds`, `_csrf_trusted_origins` today). Helpers are DISCOVERED, not
listed, so a new helper cannot hide a read: its calls are read whether written `helper("X")`,
`module.helper("X")` or `self.helper("X")`, and a helper's name used any other way (assigned to
another name, passed to `map`, stored in a dict) is a failure, because the calls through that
other name cannot be followed. A read whose name cannot be determined (a computed
name, `dict(os.environ)`, `getattr(os, "getenv")`, `os.getenv(*args)`, a call with no name at all)
RAISES `UnresolvableRead`: skipping it would let a variable hide, and a check that skips what it
cannot read is vacuous.

SCOPE. `manage.py` and every `.py` under `selahcue_api/`. A configuration file outside those (a
`gunicorn.conf.py`, a script at the API root) is not scanned; add its path to `api_source_files`
if one ever reads the environment.
"""

import ast
import functools
from dataclasses import dataclass
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent

# Set by the entry points themselves (`os.environ.setdefault(...)` in manage.py, wsgi.py,
# asgi.py and celery.py). It is Django plumbing, not something an operator configures, so it is
# neither required in the docs nor expected there.
ENTRY_POINT_PLUMBING = {"DJANGO_SETTINGS_MODULE"}

SETTINGS_LABEL = "selahcue_api/settings.py"


class UnresolvableRead(Exception):
    """An environment read whose variable name cannot be determined from the source."""


@dataclass(frozen=True)
class Read:
    name: str
    where: str


@dataclass(frozen=True)
class Aliases:
    """Names that stand for `os.environ` / `os.getenv` after `from os import environ as e`."""

    environ: frozenset = frozenset({"environ"})
    getenv: frozenset = frozenset({"getenv"})


# Returned by `_read_name_arg` for a call that reads the environment but passes no usable name.
_UNNAMED = object()


def _aliases(trees) -> Aliases:
    environ, getenv = {"environ"}, {"getenv"}
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "os":
                for alias in node.names:
                    if alias.name == "environ":
                        environ.add(alias.asname or alias.name)
                    if alias.name == "getenv":
                        getenv.add(alias.asname or alias.name)
    return Aliases(frozenset(environ), frozenset(getenv))


def _is_environ(node: ast.AST, aliases: Aliases) -> bool:
    """`<anything>.environ` or a bare name bound to os.environ. The receiver is deliberately not
    checked: `import os as _os` or `import os as operating_system` must not hide a read, and
    over-detecting costs a doc row, where under-detecting costs the whole check."""
    if isinstance(node, ast.Attribute):
        return node.attr == "environ"
    return isinstance(node, ast.Name) and node.id in aliases.environ


def _is_getenv(node: ast.AST, aliases: Aliases) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == "getenv"
    return isinstance(node, ast.Name) and node.id in aliases.getenv


def _name_from_call(call: ast.Call):
    """The name argument of `os.getenv(key, ...)` / `os.environ.get(key, ...)`: the first
    positional argument, or `key=`. `_UNNAMED` when neither is there (`os.getenv()`,
    `os.getenv(**kwargs)`), which the caller turns into a failure."""
    if call.args:
        return call.args[0]
    for keyword in call.keywords:
        if keyword.arg == "key":
            return keyword.value
    return _UNNAMED


def _read_name_arg(node: ast.AST, aliases: Aliases):
    """The expression holding the variable name if `node` reads the environment, `_UNNAMED` if it
    reads it without a usable name, else None.

    `os.environ.setdefault` is a write-if-absent, not a read of operator configuration, so it is
    deliberately not matched. `os.environ.pop` is treated as a read: it consumes the value. A
    subscript that assigns or deletes (`os.environ["X"] = ...`) is a write, not a read.
    """
    if isinstance(node, ast.Call):
        func = node.func
        if _is_getenv(func, aliases):
            return _name_from_call(node)
        if isinstance(func, ast.Attribute) and func.attr in {"get", "pop"} and _is_environ(func.value, aliases):
            return _name_from_call(node)
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.ctx, ast.Load)
        and _is_environ(node.value, aliases)
    ):
        return node.slice
    return None


def _refuse_indirect_access(trees, parents: dict[int, ast.AST], aliases: Aliases) -> None:
    """Fail on any use of the environment that this module cannot see into: `dict(os.environ)`,
    `**os.environ`, iterating it, `f = os.getenv; f("X")`, `getattr(os, "getenv")`. Each could
    read a variable the docs never hear about, so each is a failure, not a skip."""
    for label, tree in trees.items():
        for node in ast.walk(tree):
            where = f"{label}:{getattr(node, 'lineno', '?')}"
            if _is_environ(node, aliases) and not isinstance(node, ast.Name) or (
                isinstance(node, ast.Name) and node.id in aliases.environ and isinstance(node.ctx, ast.Load)
            ):
                parent = parents.get(id(node))
                grandparent = parents.get(id(parent)) if parent is not None else None
                via_method = (
                    isinstance(parent, ast.Attribute)
                    and parent.value is node
                    and parent.attr in {"get", "pop", "setdefault"}
                    and isinstance(grandparent, ast.Call)
                    and grandparent.func is parent
                )
                via_subscript = isinstance(parent, ast.Subscript) and parent.value is node
                if not (via_method or via_subscript):
                    raise UnresolvableRead(
                        f"{where}: the environment is used as a whole or indirectly "
                        f"({ast.unparse(parent) if parent is not None else 'os.environ'!r}); "
                        "read each variable by a literal name so the deployment docs can be checked"
                    )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in {"environ", "getenv"}
            ):
                raise UnresolvableRead(f"{where}: the environment is reached through getattr")
            if _is_getenv(node, aliases) and (
                isinstance(node, ast.Attribute) or (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load))
            ):
                parent = parents.get(id(node))
                if not (isinstance(parent, ast.Call) and parent.func is node):
                    raise UnresolvableRead(
                        f"{where}: getenv is referenced without being called directly "
                        f"({ast.unparse(parent) if parent is not None else 'getenv'!r})"
                    )


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


def _is_method(func, parents: dict[int, ast.AST]) -> bool:
    """A function defined directly in a class body and not a staticmethod: its first parameter is
    the receiver, which a call written `obj.method(...)` does not pass."""
    if not isinstance(parents.get(id(func)), ast.ClassDef) or not _parameters(func):
        return False
    return not any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in func.decorator_list)


def _callee_name(call: ast.Call) -> tuple[str | None, bool]:
    """(name, via_attribute) of what a call invokes: `f(...)` is ("f", False), `x.f(...)` is
    ("f", True), anything else (a call of a call, a subscript) is (None, False)."""
    if isinstance(call.func, ast.Name):
        return call.func.id, False
    if isinstance(call.func, ast.Attribute):
        return call.func.attr, True
    return None, False


def _refuse_indirect_helper_use(trees, parents: dict[int, ast.AST], helper_names) -> None:
    """A discovered helper's name may appear only as the callee of a call (or in its own `def`).
    Assigned to another name, passed to `map`, or stored in a dict, it can reach the environment
    through a name this module cannot follow, so it is a failure, like `f = os.getenv`."""
    for label, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                name = node.id
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                name = node.attr
            else:
                continue
            if name not in helper_names:
                continue
            parent = parents.get(id(node))
            if isinstance(parent, ast.Call) and parent.func is node:
                continue
            raise UnresolvableRead(
                f"{label}:{node.lineno}: `{name}` forwards a parameter to an environment read, but it "
                f"is used other than as a direct call ({ast.unparse(parent) if parent is not None else name!r}); "
                "call it directly with a literal name so the deployment docs can be checked"
            )


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
    aliases = _aliases(trees.values())
    _refuse_indirect_access(trees, parents, aliases)

    # helper function name -> the set of (index, parameter, is_method) that end up as environment
    # names. A SET, because one helper can forward more than one parameter (`def both(a, b)`); it
    # only ever grows, so the fixpoint below terminates (a single stored entry that two reads kept
    # overwriting made it loop forever).
    helpers: dict[str, set[tuple[int, str, bool]]] = {}

    def name_args_at(node: ast.AST) -> list:
        """Every expression at `node` that is used as an environment variable name."""
        direct = _read_name_arg(node, aliases)
        if direct is not None:
            return [direct]
        if isinstance(node, ast.Call):
            callee, via_attribute = _callee_name(node)
            found = []
            for index, parameter, is_method in sorted(helpers.get(callee, ())):
                # `obj.method("X")` does not pass `self`, so the parameter is one place earlier.
                shift = 1 if (is_method and via_attribute) else 0
                arg = _call_argument(node, index - shift, parameter)
                if arg is not None:
                    found.append(arg)
            return found
        return []

    def forwarded_parameter(name_arg, node: ast.AST):
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
                for name_arg in name_args_at(node):
                    found = forwarded_parameter(name_arg, node)
                    if found is None:
                        continue
                    func, parameter = found
                    entry = (_parameters(func).index(parameter), parameter, _is_method(func, parents))
                    entries = helpers.setdefault(func.name, set())
                    if entry not in entries:
                        entries.add(entry)
                        changed = True

    _refuse_indirect_helper_use(trees, parents, set(helpers))

    reads: set[Read] = set()
    for label, tree in trees.items():
        for node in ast.walk(tree):
            for name_arg in name_args_at(node):
                where = f"{label}:{node.lineno}"
                if name_arg is _UNNAMED:
                    raise UnresolvableRead(
                        f"{where}: environment read with no variable name that can be found "
                        "(no first argument and no key=); read it with a literal name"
                    )
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
    """Every variable the API reads (settings.py and any other module), entry-point plumbing aside."""
    return {read.name for read in env_reads(api_source_files())} - ENTRY_POINT_PLUMBING


@functools.cache
def settings_env_names() -> frozenset[str]:
    """Every variable `selahcue_api/settings.py` reads: what a test of settings.py must not inherit.

    Cached, and reads only settings.py: the guard tests call this once per case, and parsing every
    API file each time was most of what each case cost."""
    text = (API_ROOT / SETTINGS_LABEL).read_text(encoding="utf-8")
    return frozenset({read.name for read in env_reads({SETTINGS_LABEL: text})} - ENTRY_POINT_PLUMBING)
