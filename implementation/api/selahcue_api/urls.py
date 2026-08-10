from django.conf import settings
from django.urls import include, path

from selahcue_api.graphql.account_schema import schema as account_schema
from selahcue_api.graphql.admin_schema import schema as admin_schema
from selahcue_api.graphql.views import AccountGraphQLView, AdminGraphQLView
from selahcue_api.platform.views import billing_webhook_not_implemented


graphql_view_options = {
    "allow_queries_via_get": settings.GRAPHQL_ALLOW_QUERIES_VIA_GET,
    "graphql_ide": settings.GRAPHQL_IDE,
    "multipart_uploads_enabled": settings.GRAPHQL_MULTIPART_UPLOADS_ENABLED,
}

urlpatterns = [
    path(
        "graphql/admin",
        AdminGraphQLView.as_view(schema=admin_schema, **graphql_view_options),
        name="admin-graphql",
    ),
    path(
        "graphql/account",
        AccountGraphQLView.as_view(schema=account_schema, **graphql_view_options),
        name="account-graphql",
    ),
    path("v1/", include("selahcue_api.platform.urls")),
    path("webhooks/billing/<str:provider>", billing_webhook_not_implemented, name="billing-webhook"),
]
