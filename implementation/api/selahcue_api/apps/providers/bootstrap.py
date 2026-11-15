"""Role checks at real web, worker and operator process boundaries."""
import sys
from typing import Literal

from django.conf import settings

from .configuration import _initialized_entrypoint, _load, _reset_cache_lock_after_fork, get_provider_configuration, selected_role
from .contracts import ConfigErrorCode as Code, ConfigSource as Source, ProviderConfiguration, ProviderConfigurationError

Entrypoint = Literal["wsgi", "asgi", "celery_worker", "celery_beat", "operator"]
_WORKER_QUEUES = {
    "usage": "provider_usage",
    "provisioner": "provider_provisioning",
    "notes": "notes",
    "maintenance": "celery",
}


def initialize_provider_runtime(*, entrypoint: Entrypoint) -> ProviderConfiguration:
    role = selected_role()
    if entrypoint in ("wsgi", "asgi"):
        public = settings.SELAHCUE_CLOUD_STT_ENABLED or settings.SELAHCUE_CLOUD_NOTES_ENABLED
        accepted = role == "web" or (role == "maintenance" and not public)
    elif entrypoint == "celery_worker":
        accepted = role in _WORKER_QUEUES
    elif entrypoint == "celery_beat":
        accepted = role == "maintenance"
    else:
        accepted = entrypoint == "operator" and role == "provisioner"

    if not accepted:
        raise ProviderConfigurationError(Code.PCFG_ROLE_MISMATCH, Source.SETTINGS)
    if role == "notes" or (role == "web" and settings.SELAHCUE_CLOUD_NOTES_ENABLED):
        raise ProviderConfigurationError(Code.PCFG_NOTES_RUNTIME_UNAVAILABLE)
    return _load(role, entrypoint=entrypoint)


def get_initialized_provider_entrypoint() -> Entrypoint | None:
    return _initialized_entrypoint()


def _fatal(error: ProviderConfigurationError) -> None:
    print(str(error), file=sys.stderr)
    # Celery catches Exception from signal receivers and continues. Exit before bootsteps.
    raise SystemExit(78) from None


def _worker_init(sender, **_kwargs) -> None:
    try:
        role = selected_role()
        if role not in _WORKER_QUEUES:
            raise ProviderConfigurationError(Code.PCFG_ROLE_MISMATCH, Source.SETTINGS)
        if sender.options.get("beat") or set(sender.app.amqp.queues.consume_from) != {_WORKER_QUEUES[role]}:
            raise ProviderConfigurationError(Code.PCFG_QUEUE_MISMATCH)
        initialize_provider_runtime(entrypoint="celery_worker")
    except ProviderConfigurationError as error:
        _fatal(error)
    except Exception:
        _fatal(ProviderConfigurationError(Code.PCFG_INTERNAL_FAILURE))


def _worker_process_init(**_kwargs) -> None:
    _reset_cache_lock_after_fork()
    try:
        try:
            get_provider_configuration(required_role=selected_role())
        except ProviderConfigurationError as error:
            if error.code != Code.PCFG_NOT_INITIALIZED:
                raise
            initialize_provider_runtime(entrypoint="celery_worker")
    except ProviderConfigurationError as error:
        _fatal(error)
    except Exception:
        _fatal(ProviderConfigurationError(Code.PCFG_INTERNAL_FAILURE))


def _beat_init(**_kwargs) -> None:
    try:
        initialize_provider_runtime(entrypoint="celery_beat")
    except ProviderConfigurationError as error:
        _fatal(error)
    except Exception:
        _fatal(ProviderConfigurationError(Code.PCFG_INTERNAL_FAILURE))


def register_celery_provider_hooks() -> None:
    from celery.signals import beat_init, worker_init, worker_process_init

    worker_init.connect(_worker_init, weak=False, dispatch_uid="selahcue-provider-worker")
    worker_process_init.connect(_worker_process_init, weak=False, dispatch_uid="selahcue-provider-worker-child")
    beat_init.connect(_beat_init, weak=False, dispatch_uid="selahcue-provider-beat")
