import os

from django.core.asgi import get_asgi_application

from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "selahcue_api.settings")

_application = get_asgi_application()
initialize_provider_runtime(entrypoint="asgi")
application = _application
