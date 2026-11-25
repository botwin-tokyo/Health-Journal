"""Shared JSON cache: no process-local counters or pickle deserialization."""

from datetime import timedelta

from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache
from django.db import IntegrityError, transaction
from django.utils import timezone


class PostgresJSONCache(BaseCache):
    def __init__(self, location, params):
        super().__init__(params)

    @property
    def model(self):
        from .models import CacheEntry

        return CacheEntry

    def expiry(self, timeout):
        if timeout is DEFAULT_TIMEOUT:
            timeout = self.default_timeout
        return None if timeout is None else timezone.now() + timedelta(seconds=timeout)

    def get(self, key, default=None, version=None):
        row = self.model.objects.filter(pk=self.make_and_validate_key(key, version)).first()
        if row is None or (row.expires_at and row.expires_at <= timezone.now()):
            return default
        return row.value

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        self.model.objects.update_or_create(
            pk=self.make_and_validate_key(key, version),
            defaults={"value": value, "expires_at": self.expiry(timeout)},
        )

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version)
        with transaction.atomic():
            self.model.objects.filter(pk=key, expires_at__lte=timezone.now()).delete()
            try:
                with transaction.atomic():
                    self.model.objects.create(key=key, value=value, expires_at=self.expiry(timeout))
                return True
            except IntegrityError:
                return False

    def incr(self, key, delta=1, version=None):
        with transaction.atomic():
            row = (
                self.model.objects.select_for_update()
                .filter(pk=self.make_and_validate_key(key, version))
                .first()
            )
            if row is None or (row.expires_at and row.expires_at <= timezone.now()):
                raise ValueError("Key is absent or expired")
            row.value += delta
            row.save(update_fields=["value"])
            return row.value

    def delete(self, key, version=None):
        return bool(
            self.model.objects.filter(pk=self.make_and_validate_key(key, version)).delete()[0]
        )

    def clear(self):
        self.model.objects.filter(key__startswith=self.make_key("", version=None)).delete()
        return True
