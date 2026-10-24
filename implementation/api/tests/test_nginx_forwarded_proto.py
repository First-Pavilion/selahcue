"""Guard for the nginx half of the TLS-proxy chain (17tnw2b1wtr).

Django only believes `X-Forwarded-Proto` when `SELAHCUE_TRUST_FORWARDED_PROTO=1`, and the value it
gets is whatever `implementation/marketing/nginx.conf` forwards on `/graphql/`. nginx sits behind
the TLS edge, so its own `$scheme` is `http`; the config therefore maps the edge's `https` through
and falls back to `$scheme` for anything else. Nothing else tested that file, so reverting the
`map` or the `proxy_set_header` line left every test green while production sent `http` again.

This reads the config as text and checks both its shape and, with a small evaluator for the
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


def _map_entries() -> dict[str, str]:
    blocks = re.findall(
        r"map\s+\$http_x_forwarded_proto\s+" + re.escape(MAP_VARIABLE) + r"\s*\{([^}]*)\}",
        _config(),
    )
    assert len(blocks) == 1, "expected exactly one X-Forwarded-Proto map block"
    entries = {}
    for statement in filter(None, (part.strip() for part in blocks[0].split(";"))):
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
        (" https", "http"),  # not an exact match (nginx strips leading space itself in practice)
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


def test_the_graphql_proxy_sends_the_mapped_value_and_nothing_else_sets_the_header():
    config = _config()
    locations = re.findall(r"location\s+/graphql/\s*\{([^}]*)\}", config)
    assert len(locations) == 1, "expected exactly one /graphql/ location"

    statements = [" ".join(line.split()) for line in locations[0].split(";")]
    assert HEADER_LINE.rstrip(";") in statements

    # Every X-Forwarded-Proto setter in the whole file must be that one line: a second directive,
    # or one using $scheme / $http_x_forwarded_proto / $proxy_add_..., would change what Django sees.
    setters = re.findall(r"proxy_set_header\s+X-Forwarded-Proto[^;]*;", config, flags=re.IGNORECASE)
    assert [" ".join(setter.split()) for setter in setters] == [HEADER_LINE]


def test_the_map_is_declared_at_http_level_not_inside_a_server_block():
    """`map` is only valid in the http context; conf.d files are included there, so it must sit
    before (outside) the `server {` block."""
    config = _config()
    assert config.index("map ") < config.index("server {")
