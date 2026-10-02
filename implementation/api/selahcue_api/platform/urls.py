from django.urls import path

from selahcue_api.platform import views


urlpatterns = [
    path("activations", views.activate_device, name="activation"),
    # Native-client account sign-in (86ak5t1gw, ADR-0027). The browser equivalents live on
    # `/graphql/account`, which stays CSRF-enforced.
    path("sessions", views.create_session, name="session-create"),
    path("activations:with-session", views.activate_device_with_session, name="activation-with-session"),
    path("license:refresh", views.refresh_license, name="license-refresh"),
    path("entitlements/manifest", views.entitlement_manifest, name="entitlement-manifest"),
    path("downloads:prepare", views.download_prepare_not_implemented, name="download-prepare"),
    path("downloads/<str:lease_id>:complete", views.download_complete_not_implemented, name="download-complete"),
    path("usage-events:batch", views.usage_events_not_implemented, name="usage-events"),
]
