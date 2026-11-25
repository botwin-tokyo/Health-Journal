import hashlib
import json
import secrets
from datetime import date, datetime, timezone

from django.core.cache import cache
from django.db.models import DateField, DateTimeField, Q, Value
from django.db.models.functions import Coalesce

from .validation import DomainError


def window(query, context, kinds, start, end, after, limit, filters=None):
    from django.utils.crypto import salted_hmac

    fingerprint = salted_hmac(
        "records-cursor-filter",
        json.dumps([sorted(kinds), str(start), str(end), filters], sort_keys=True),
    ).hexdigest()
    epoch = context.epoch()
    query = query.annotate(
        sort_day=Coalesce(
            "current__blob__clinical_date", Value(date(9999, 12, 31)), output_field=DateField()
        ),
        sort_time=Coalesce(
            "current__measured_start",
            Value(datetime(9999, 12, 31, tzinfo=timezone.utc)),
            output_field=DateTimeField(),
        ),
    )
    if after:
        if not isinstance(after, str) or len(after) > 100:
            raise DomainError("invalid_cursor", 400)
        state = cache.get("records-cursor:" + hashlib.sha256(after.encode()).hexdigest())
        if not state or state["epoch"] != epoch or state["filter"] != fingerprint:
            raise DomainError("cursor_expired", 409)
        day = date.fromisoformat(state["day"])
        instant = datetime.fromisoformat(state["time"])
        identifier = state["id"]
        query = query.filter(
            Q(sort_day__gt=day)
            | Q(sort_day=day, sort_time__gt=instant)
            | Q(sort_day=day, sort_time=instant, id__gt=identifier)
        )

    def cursor(record):
        token = secrets.token_urlsafe(32)
        cache.set(
            "records-cursor:" + hashlib.sha256(token.encode()).hexdigest(),
            {
                "epoch": epoch,
                "filter": fingerprint,
                "day": record.sort_day.isoformat(),
                "time": record.sort_time.isoformat(),
                "id": str(record.pk),
            },
            3600,
        )
        return token

    return query.order_by("sort_day", "sort_time", "id")[: max(200, limit) + 1], cursor
