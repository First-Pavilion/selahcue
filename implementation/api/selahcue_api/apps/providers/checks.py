"""Inspect configuration syntax without opening any provider mount."""
from django.conf import settings
from django.core.checks import Error

from .configuration import PATH_SETTINGS, path_is_valid, selected_role
from .contracts import ProviderConfigurationError


def check_provider_settings(**_kwargs):
    errors = []
    try:
        selected_role()
    except ProviderConfigurationError as error:
        errors.append(Error(str(error), id="selahcue_providers.E001"))
    for name in PATH_SETTINGS.values():
        if not path_is_valid(getattr(settings, name)):
            errors.append(Error(f"{name} requires an absolute path or an empty value.", id="selahcue_providers.E002"))
    return errors
