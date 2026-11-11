from django.conf import settings
from django.urls import include, path

from selahcue_api.graphql.account_schema import schema as account_schema
from selahcue_api.graphql.admin_schema import schema as admin_schema
from selahcue_api.graphql.views import AccountGraphQLView, AdminGraphQLView, csrf_bootstrap
from selahcue_api.platform.views import billing_webhook_not_implemented
from selahcue_api.apps.catalogue.views import plans as public_catalogue_plans
from selahcue_api.apps.pilot_downloads import views as pilot_registration_views
from selahcue_api.apps.pilot_downloads import grant_views as pilot_grant_views


graphql_view_options = {
    "allow_queries_via_get": settings.GRAPHQL_ALLOW_QUERIES_VIA_GET,
    "graphql_ide": settings.GRAPHQL_IDE,
    "multipart_uploads_enabled": settings.GRAPHQL_MULTIPART_UPLOADS_ENABLED,
}

urlpatterns = [
    path("v1/catalogue/plans", public_catalogue_plans, name="public-catalogue-plans"),
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
    # Seeds the csrftoken cookie for the two surfaces above. Sits beside them, not under /v1/:
    # /v1 is the device-token desktop surface and is csrf_exempt, so it needs nothing from this.
    path("graphql/csrf", csrf_bootstrap, name="csrf-bootstrap"),
    path("v1/", include("selahcue_api.platform.urls")),
    path("v1/pilot/registrations:reserve", pilot_registration_views.reserve, name="pilot-registration-reserve"),
    path("v1/pilot/registrations:confirm", pilot_registration_views.confirm, name="pilot-registration-confirm"),
    path("v1/pilot/downloads:grant", pilot_grant_views.grant, name="pilot-download-grant"),
    path("webhooks/billing/<str:provider>", billing_webhook_not_implemented, name="billing-webhook"),
]
