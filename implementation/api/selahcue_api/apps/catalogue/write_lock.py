"""One lock order for managed catalogue writers: revision before catalogue data."""
from django.db import connection

from selahcue_api.apps.catalogue.models import CatalogueRevision


def lock_catalogue_revision():
    if not connection.in_atomic_block:
        raise RuntimeError('Catalogue write lock requires an atomic transaction.')
    CatalogueRevision.objects.get_or_create(pk=CatalogueRevision.SINGLETON_PK, defaults={'revision': 0})
    return CatalogueRevision.objects.select_for_update().get(pk=CatalogueRevision.SINGLETON_PK)
