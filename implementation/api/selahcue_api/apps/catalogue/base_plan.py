"""The legacy assignment/scope/fallback lookup shared by catalogue readers."""

from selahcue_api.apps.catalogue.models import LicensePlanAssignment, Plan, PlanScopeAlias


def _base_plan_for_license(license_key) -> Plan | None:
    """Assignment → legacy scope alias → designated fallback. None when none exist."""
    assignment = (
        LicensePlanAssignment.objects.select_related("plan").filter(license_key=license_key).first()
    )
    if assignment is not None:
        return assignment.plan

    scope = (getattr(license_key, "feature_scope", "") or "").strip().upper()
    if scope:
        alias = PlanScopeAlias.objects.select_related("plan").filter(feature_scope=scope).first()
        if alias is not None:
            return alias.plan

    return Plan.objects.filter(is_fallback=True).first()
