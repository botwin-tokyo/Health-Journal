"""Bounded dual indexes. Version one remains required by retained protocol receipts."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from records.validation import DomainError

from .models import SourceIdentity, SourceLookup


def versions():
    values = tuple(settings.HEALTH03_SOURCE_LOOKUP_VERSIONS)
    if (
        not 1 <= len(values) <= 2
        or len(set(values)) != len(values)
        or 1 not in values
        or any(type(v) is not int or v < 1 for v in values)
    ):
        raise ImproperlyConfigured(
            "Use one or two lookup versions; retained v1 receipts and tombstones require version 1."
        )
    return values


def digests(kms, source, kind, source_id):
    return {
        version: kms.identity_digest(
            source.device.owner_id, kind, source_id, str(source.namespace), version
        )
        for version in versions()
    }


def resolve(source, kind, values):
    query = Q(source=source, kind=kind, digest=values[1], lookup_version=1)
    for version, digest in values.items():
        query |= Q(
            source=source, kind=kind, lookups__lookup_version=version, lookups__digest=digest
        )
    matches = list(SourceIdentity.objects.filter(query).distinct().select_related("record")[:2])
    if len(matches) > 1:
        raise DomainError("lookup_identity_conflict", 409)
    return matches[0] if matches else None


def index(identity, values):
    for version, digest in values.items():
        entry, _ = SourceLookup.objects.get_or_create(
            source=identity.source,
            kind=identity.kind,
            lookup_version=version,
            digest=digest,
            defaults={"identity": identity},
        )
        if entry.identity_id != identity.pk:
            raise DomainError("lookup_identity_conflict", 409)
