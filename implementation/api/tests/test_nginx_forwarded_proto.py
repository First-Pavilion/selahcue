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
    """The config with `#` comments removed, so a commented-out line cannot satisfy a check."""
    return re.sub(r"#[^\n]*", "", NGINX_CONF.read_text(encoding="utf-8"))


def _blocks() -> list[dict]:
    """Every `{ ... }` block in the config, outermost first within each nest: its header (the
    directive text before the brace), its body text (nested blocks included), its character span
    and the index of its enclosing block (None at top level). nginx directives end in `;` and
    blocks in `}`, so the header is the text since the last `;`, `{` or `}`."""
    config = _config()
    blocks: list[dict] = []
    stack: list[int] = []
    start = 0
    for index, char in enumerate(config):
        if char == "{":
            blocks.append(
                {
                    "header": " ".join(config[start:index].split()),
                    "open": index + 1,
                    "parent": stack[-1] if stack else None,
                }
            )
            stack.append(len(blocks) - 1)
            start = index + 1
        elif char == "}":
            blocks[stack.pop()]["close"] = index
            start = index + 1
        elif char == ";":
            start = index + 1
    assert not stack, "unbalanced braces in nginx.conf"
    for block in blocks:
        block["body"] = config[block["open"] : block["close"]]
    return blocks


def _statements(body: str) -> list[str]:
    return [" ".join(part.split()) for part in body.split(";") if part.strip()]


def _map_entries() -> dict[str, str]:
    maps = [
        block
        for block in _blocks()
        if re.fullmatch(r"map \$http_x_forwarded_proto " + re.escape(MAP_VARIABLE), block["header"])
    ]
    assert len(maps) == 1, "expected exactly one X-Forwarded-Proto map block"
    entries = {}
    for statement in filter(None, (part.strip() for part in maps[0]["body"].split(";"))):
        key, _, value = statement.partition(" ")
        key, value = key.strip().strip('"\''), value.strip().strip('"\'')
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
    proxied = [match.start() for match in re.finditer(r"\bproxy_pass\b", config)]
    assert proxied, "expected at least one proxy_pass (the /graphql/ proxy)"

    for offset in proxied:
        location = _enclosing_location(blocks, offset)
        assert location is not None, "a proxy_pass sits outside any location block"
        assert HEADER_LINE.rstrip(";") in _statements(location["body"]), (
            f"{location['header']!r} proxies without {HEADER_LINE}"
        )


def test_the_graphql_proxy_is_one_of_them_and_nothing_else_sets_the_header():
    config = _config()
    graphql = [b for b in _blocks() if b["header"] == "location /graphql/"]
    assert len(graphql) == 1, "expected exactly one /graphql/ location"
    assert "proxy_pass" in graphql[0]["body"]

    # Every X-Forwarded-Proto setter in the whole file must be that one line: a second directive,
    # or one using $scheme / $http_x_forwarded_proto / $proxy_add_..., would change what Django sees.
    setters = re.findall(r"proxy_set_header\s+X-Forwarded-Proto[^;]*;", config, flags=re.IGNORECASE)
    assert {" ".join(setter.split()) for setter in setters} == {HEADER_LINE}


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


@pytest.mark.parametrize("case", BYPASS_CASES)
def test_guard_refuses_each_valid_nginx_trust_bypass(case, monkeypatch, tmp_path):
    original = NGINX_CONF.read_text(encoding="utf-8")
    fixture = tmp_path / "nginx.conf"
    fixture.write_text(_bypass_config(original, case), encoding="utf-8")
    monkeypatch.setitem(globals(), "NGINX_CONF", fixture)
    with pytest.raises(AssertionError):
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
