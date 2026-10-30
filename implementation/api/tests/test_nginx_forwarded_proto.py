"""Guard for the nginx half of the TLS-proxy chain (17tnw2b1wtr).

Django only believes `X-Forwarded-Proto` when `SELAHCUE_TRUST_FORWARDED_PROTO=1`, and the value it
gets is whatever `implementation/marketing/nginx.conf` forwards on `/graphql/`. nginx sits behind
the TLS edge, so its own `$scheme` is `http`; the config therefore maps the edge's `https` through
and falls back to `$scheme` for anything else. Nothing else tested that file, so reverting the
`map` or the `proxy_set_header` line left every test green while production sent `http` again.

This reads the config as text (with a small brace-matching parser, so nesting is understood
rather than guessed at with regexes) and checks both its shape and, with a small evaluator for the
exact-match `map` semantics, what it sends for each client-supplied header. nginx matches `map`
strings exactly and case-insensitively, and an unmatched value takes `default`; the evaluator
mirrors only that. It needs no nginx binary and no Docker. A real `nginx -t` plus header-echo
rehearsal is a documented manual step (docs/ops/DEPLOYMENT.md section 6c).

The `api` CI filter includes this config file, so editing it re-runs this guard.
"""

import re
from pathlib import Path

import pytest

# tests/conftest.py snapshots the migration-installed catalogue in a session fixture that needs the
# test database; pytest-django only builds it when a selected test is marked. Without this the
# guard errors in setup when run on its own (`pytest tests/test_nginx_forwarded_proto.py`).
pytestmark = pytest.mark.django_db

NGINX_CONF = Path(__file__).resolve().parent.parent.parent / "marketing" / "nginx.conf"
MAP_VARIABLE = "$selahcue_client_proto"
HEADER_LINE = f"proxy_set_header X-Forwarded-Proto {MAP_VARIABLE};"


def _config() -> str:
    """Remove comments only outside quoted/escaped values, retaining quoted data."""
    output = []
    quote = None
    escaped = False
    comment = False
    for char in NGINX_CONF.read_text(encoding="utf-8"):
        if comment:
            if char == "\n":
                comment = False
                output.append(char)
        elif escaped:
            output.append(char)
            escaped = False
        elif char == "\\":
            output.append(char)
            escaped = True
        elif quote:
            output.append(char)
            if char == quote:
                quote = None
        elif char in "\"'":
            output.append(char)
            quote = char
        elif char == "#":
            comment = True
        else:
            output.append(char)
    assert quote is None and not escaped, "unterminated quoted/escaped nginx value"
    return "".join(output)


def _tokens(config: str):
    """Small lexer for this guard, not a general nginx interpreter. Quoted and
    escaped delimiters are data; each structural token is explicitly tagged.
    Thus one quoted string containing a directive can never become directives.
    """
    value = []
    start = None
    quote = None
    escaped = False
    for offset, char in enumerate(config):
        if escaped:
            value.append(char)
            escaped = False
        elif char == "\\":
            if start is None:
                start = offset
            escaped = True
        elif quote:
            if char == quote:
                quote = None
            else:
                value.append(char)
        elif char in "\"'":
            if start is None:
                start = offset
            quote = char
        elif char.isspace() or char in ";{}":
            if start is not None:
                yield "".join(value), start, False
                value = []
                start = None
            if char in ";{}":
                yield char, offset, True
        else:
            if start is None:
                start = offset
            value.append(char)
    assert quote is None and not escaped, "unterminated quoted/escaped nginx value"
    if start is not None:
        yield "".join(value), start, False


def _blocks() -> list[dict]:
    """Real block delimiters only, with their parent and source body spans."""
    config = _config()
    blocks = []
    stack = []
    words = []
    for token, offset, structural in _tokens(config):
        if structural and token == "{":
            blocks.append({"header": " ".join(words), "open": offset + 1,
                           "parent": stack[-1] if stack else None})
            stack.append(len(blocks) - 1)
            words = []
        elif structural and token == "}":
            assert stack, "unbalanced braces in nginx.conf"
            blocks[stack.pop()]["close"] = offset
            words = []
        elif structural and token == ";":
            words = []
        else:
            words.append(token)
    assert not stack, "unbalanced braces in nginx.conf"
    for block in blocks:
        block["body"] = config[block["open"]:block["close"]]
    return blocks


def _directives(config: str):
    """Yield actual directive words, their offset and block depth."""
    words = []
    start = None
    depth = 0
    for token, offset, structural in _tokens(config):
        if structural:
            if token == ";" and words:
                yield tuple(words), start, depth
            elif token == "{":
                depth += 1
            elif token == "}":
                depth -= 1
                assert depth >= 0, "unbalanced braces in nginx.conf"
            words = []
            start = None
        else:
            if start is None:
                start = offset
            words.append(token)
    assert depth == 0, "unbalanced braces in nginx.conf"


def _statements(body: str) -> list[tuple[str, ...]]:
    # A nested location's header cannot satisfy its parent's own proxy guard.
    return [words for words, _, depth in _directives(body) if depth == 0]


def _map_entries() -> dict[str, str]:
    maps = [
        block for block in _blocks()
        if re.fullmatch(r"map \$http_x_forwarded_proto " + re.escape(MAP_VARIABLE), block["header"])
    ]
    assert len(maps) == 1, "expected exactly one X-Forwarded-Proto map block"
    entries = {}
    for statement in _statements(maps[0]["body"]):
        assert len(statement) == 2, "expected a literal map key/value pair"
        key, value = statement
        assert key not in entries, f"duplicate map entry {key!r}"
        entries[key] = value
    return entries


def _client_proto(header: str | None, scheme: str = "http") -> str:
    """What the map yields for a client-supplied header, given the scheme nginx itself saw."""
    entries = _map_entries()
    chosen = entries.get(header.lower()) if header is not None else None
    if chosen is None:
        chosen = entries["default"]
    return scheme if chosen == "$scheme" else chosen


def test_the_map_has_a_scheme_default_and_exactly_one_literal_exception():
    """No catch-all, no regex, no pass-through of the client's header: the only value that may
    override what nginx itself saw is the literal `https`."""
    assert _map_entries() == {"default": "$scheme", "https": "https"}


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "http"),
        ("https", "https"),
        ("HTTPS", "https"),  # nginx map matching is case-insensitive; the output is the literal
        ("http", "http"),
        ("", "http"),
        ("https, http", "http"),
        ("http, https", "http"),
        ("https,http", "http"),
        ("evil", "http"),
        ("https://", "http"),
        ("wss", "http"),
    ],
)
def test_a_client_supplied_header_cannot_turn_a_plain_hop_into_anything_but_http_or_https(
    header, expected
):
    assert _client_proto(header) == expected


def test_when_nginx_itself_terminated_tls_the_fallback_is_https():
    """`default $scheme` keeps a directly-TLS nginx honest: no header, https scheme -> https."""
    assert _client_proto(None, scheme="https") == "https"
    assert _client_proto("http", scheme="https") == "https"


def _enclosing_location(blocks: list[dict], offset: int) -> dict | None:
    """The nearest `location` block (innermost outwards) that contains character `offset`."""
    containing = [b for b in blocks if b["open"] <= offset < b["close"]]
    for block in sorted(containing, key=lambda b: b["close"] - b["open"]):
        if block["header"].startswith("location "):
            return block
    return None


def test_every_location_that_proxies_sends_the_mapped_value():
    """The guard must not depend on which location happens to carry `proxy_pass` today: a new
    `location /v1/ { proxy_pass ...; }` that forgets the header would forward nginx's own `http`
    (or, worse, whatever the client sent) to Django. Every `proxy_pass` must sit inside a location
    whose own directives include the exact mapped `proxy_set_header` line."""
    config = _config()
    blocks = _blocks()
    proxied = [offset for words, offset, _ in _directives(config) if words[0] == "proxy_pass"]
    assert proxied, "expected at least one proxy_pass (the /graphql/ proxy)"

    for offset in proxied:
        location = _enclosing_location(blocks, offset)
        assert location is not None, "a proxy_pass sits outside any location block"
        assert tuple(HEADER_LINE.rstrip(";").split()) in _statements(location["body"]), (
            f"{location['header']!r} proxies without {HEADER_LINE}"
        )


def test_the_graphql_proxy_is_one_of_them_and_nothing_else_sets_the_header():
    config = _config()
    graphql = [b for b in _blocks() if b["header"] == "location /graphql/"]
    assert len(graphql) == 1, "expected exactly one /graphql/ location"
    assert any(words[0] == "proxy_pass" for words in _statements(graphql[0]["body"]))

    # Every X-Forwarded-Proto setter in the whole file must be that one line: a second directive,
    # or one using $scheme / $http_x_forwarded_proto / $proxy_add_..., would change what Django sees.
    setters = {
        words for words, _, _ in _directives(config)
        if words[0] == "proxy_set_header" and len(words) > 1
        and words[1].lower() == "x-forwarded-proto"
    }
    assert setters == {tuple(HEADER_LINE.rstrip(";").split())}


def test_the_map_is_declared_at_http_level_not_inside_a_server_block():
    """`map` is only valid in the http context; conf.d files are included there. A `map` inside
    `server {` (or any other block) would stop nginx loading the config, so no map may have an
    enclosing block, whatever order the blocks appear in."""
    blocks = _blocks()
    maps = [block for block in blocks if block["header"].startswith("map ")]
    assert maps, "expected the X-Forwarded-Proto map"
    for block in maps:
        assert block["parent"] is None, f"{block['header']!r} is nested inside another block"
    assert any(block["header"] == "server" for block in blocks)


def test_no_set_override_or_uninspected_server_include_can_bypass_the_map():
    config = _config()
    servers = [block for block in _blocks() if block["header"] == "server"]
    for words, offset, _ in _directives(config):
        assert not (words[0] == "set" and len(words) > 1 and words[1] == MAP_VARIABLE), (
            "set must not override the trusted client-proto map"
        )
        if words[0] == "include":
            assert not any(server["open"] <= offset < server["close"] for server in servers), (
                "server includes can hide unchecked proxy/header directives"
            )


# 17tnw2b9adv: these are valid nginx configurations, not arbitrary corrupt
# text. The bounded hosted diagnostic additionally runs nginx -t on every
# fixture before interpreting a guard failure as meaningful sensitivity.
def _bypass_config(original: str, case: str) -> str:
    assert original.count("server {") == 1
    assert original.count(HEADER_LINE) == 1
    if case == "quoted-hash":
        return original.replace("server {", """server {
    location /unguarded/ {
        add_header X-Note "#1"; proxy_pass http://api:8000;
    }
""", 1)
    if case == "quoted-header":
        return original.replace(HEADER_LINE, f'set $note "; {HEADER_LINE} ";', 1)
    if case == "map-override":
        return original.replace("server {", "server {\n    set $selahcue_client_proto $http_x_forwarded_proto;", 1)
    if case == "server-include":
        return original.replace("server {", "server {\n    include /etc/nginx/diagnostic/override.conf;", 1)
    raise AssertionError(f"unknown bypass case: {case}")


BYPASS_CASES = ["quoted-hash", "quoted-header", "map-override", "server-include"]


def _assert_proxy_guard():
    # Invoke the same checks the real fixture gets, rather than asserting on
    # a copied parser or inventing a test-only acceptance oracle.
    test_the_map_has_a_scheme_default_and_exactly_one_literal_exception()
    test_every_location_that_proxies_sends_the_mapped_value()
    test_the_graphql_proxy_is_one_of_them_and_nothing_else_sets_the_header()
    test_the_map_is_declared_at_http_level_not_inside_a_server_block()
    test_no_set_override_or_uninspected_server_include_can_bypass_the_map()


@pytest.mark.parametrize("case", BYPASS_CASES)
def test_guard_refuses_each_valid_nginx_trust_bypass(case, monkeypatch, tmp_path):
    original = NGINX_CONF.read_text(encoding="utf-8")
    fixture = tmp_path / "nginx.conf"
    fixture.write_text(_bypass_config(original, case), encoding="utf-8")
    monkeypatch.setitem(globals(), "NGINX_CONF", fixture)
    expected = {
        "quoted-hash": "proxies without",
        "quoted-header": "proxies without",
        "map-override": "set must not override",
        "server-include": "server includes",
    }[case]
    with pytest.raises(AssertionError, match=expected):
        _assert_proxy_guard()


@pytest.mark.parametrize("note", [
    'add_header X-Note "#1; {literal}";',
    "add_header X-Note '#1; {literal}';",
    'set $note "escaped\\"#1; {literal}";',
])
def test_guard_accepts_benign_quoted_values_and_real_header(note, monkeypatch, tmp_path):
    original = NGINX_CONF.read_text(encoding="utf-8")
    fixture = tmp_path / "nginx.conf"
    fixture.write_text(original.replace("server {", f"server {{\n    {note}", 1), encoding="utf-8")
    monkeypatch.setitem(globals(), "NGINX_CONF", fixture)
    _assert_proxy_guard()


def test_guard_strips_only_unquoted_comments(monkeypatch, tmp_path):
    fixture = tmp_path / "nginx.conf"
    fixture.write_text('add_header X-Note "#kept"; #removed\n', encoding="utf-8")
    monkeypatch.setitem(globals(), "NGINX_CONF", fixture)
    assert '#kept' in _config()
    assert '#removed' not in _config()
