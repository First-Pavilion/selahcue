from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphQLEndpointContract:
    surface: str
    path: str
    schema_name: str
    auth_context: str
    allow_queries_via_get: bool
    multipart_uploads_enabled: bool
    graphql_ide: str | None


@dataclass(frozen=True)
class CommandEndpointContract:
    surface: str
    path: str
    method: str
    auth_context: str


def graphql_endpoint_contracts(*, debug: bool) -> tuple[GraphQLEndpointContract, ...]:
    graphql_ide = "graphiql" if debug else None
    return (
        GraphQLEndpointContract(
            surface="admin",
            path="graphql/admin",
            schema_name="admin_schema",
            auth_context="staff_session_with_csrf",
            allow_queries_via_get=False,
            multipart_uploads_enabled=False,
            graphql_ide=graphql_ide,
        ),
        GraphQLEndpointContract(
            surface="account",
            path="graphql/account",
            schema_name="account_schema",
            auth_context="customer_session_with_csrf",
            allow_queries_via_get=False,
            multipart_uploads_enabled=False,
            graphql_ide=graphql_ide,
        ),
    )


def desktop_command_contracts() -> tuple[CommandEndpointContract, ...]:
    return (
        CommandEndpointContract("desktop", "v1/activations", "POST", "app_key_then_device_token"),
        CommandEndpointContract("desktop", "v1/license:refresh", "POST", "device_token"),
        CommandEndpointContract("desktop", "v1/entitlements/manifest", "GET", "device_token"),
        CommandEndpointContract("desktop", "v1/downloads:prepare", "POST", "device_token"),
        CommandEndpointContract("desktop", "v1/downloads/<lease_id>:complete", "POST", "device_token"),
        CommandEndpointContract("desktop", "v1/usage-events:batch", "POST", "device_token"),
    )


def browser_bootstrap_contract() -> CommandEndpointContract:
    """The GET that issues the `csrftoken` cookie both browser surfaces require.

    Declared here like every other route so the contract module stays a complete inventory.
    `auth_context` is "none" because a CSRF token is not a credential — it is only meaningful
    paired with the cookie of the browser that asked for it.
    """
    return CommandEndpointContract(
        surface="browser",
        path="graphql/csrf",
        method="GET",
        auth_context="none_issues_csrf_cookie",
    )


def billing_webhook_contract() -> CommandEndpointContract:
    return CommandEndpointContract(
        surface="billing_provider",
        path="webhooks/billing/<provider>",
        method="POST",
        auth_context="provider_signature",
    )
