import os

from django.core.wsgi import get_wsgi_application

from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "selahcue_api.settings")

_application = get_wsgi_application()
initialize_provider_runtime(entrypoint="wsgi")
application = _application
