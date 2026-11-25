"""Bounded wire parsing and exact clinical decimal/time primitives."""

import json
import re
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from zoneinfo import ZoneInfo


class DomainError(Exception):
    def __init__(self, code, status=422):
        self.code, self.status = code, status
        super().__init__(code)


def decimal(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d{1,18})?", value):
        raise DomainError("invalid_decimal")
    if len(value.replace("-", "").replace(".", "").lstrip("0")) > 36:
        raise DomainError("decimal_precision_exceeded")
    return Decimal(value)


def derived(value):
    with localcontext() as ctx:
        ctx.prec = 60
        return (
            format(value.quantize(Decimal("0.000000000000000001"), rounding=ROUND_HALF_EVEN), "f")
            .rstrip("0")
            .rstrip(".")
            if value
            else "0"
        )


def text(value, maximum, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise DomainError("invalid_text")
    return value


def parse_json(raw):
    if len(raw) > 5 * 1024 * 1024:
        raise DomainError("body_too_large", 413)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise DomainError("duplicate_json_key", 400)
            result[key] = value
        return result

    def invalid(value):
        raise DomainError("invalid_json_number", 400)

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)

        def bound(item, depth=0):
            if depth > 20:
                raise DomainError("json_too_deep", 400)
            if isinstance(item, dict):
                for child in item.values():
                    bound(child, depth + 1)
            elif isinstance(item, list):
                for child in item:
                    bound(child, depth + 1)

        bound(value)
        if not isinstance(value, dict):
            raise DomainError("invalid_json", 400)
        return value
    except (ValueError, RecursionError, UnicodeError):
        raise DomainError("invalid_json", 400) from None


def clinical_time(payload, allow_unknown=False):
    precision = payload.get("time_precision", "day")
    day = payload.get("clinical_date")
    if precision == "unknown" and allow_unknown and day is None:
        return None, None
    try:
        day = date.fromisoformat(day)
        if precision == "day":
            if payload.get("measured_start") or payload.get("measured_end"):
                raise ValueError
            return day, None
        if precision not in {"second", "minute"}:
            raise ValueError
        instant = datetime.fromisoformat(payload["measured_start"])
        if instant.utcoffset() is None:
            raise ValueError
        offset = payload["original_offset_minutes"]
        if type(offset) is not int or offset != instant.utcoffset().total_seconds() / 60:
            raise ValueError
        if payload.get("timezone_provenance") != "offset_only":
            local = instant.astimezone(ZoneInfo(payload["timezone"]))
            if local.utcoffset() != instant.utcoffset():
                raise ValueError
        if instant.date() != day:
            raise ValueError
        if payload.get("measured_end"):
            end = datetime.fromisoformat(payload["measured_end"])
            if end.utcoffset() is None or end <= instant:
                raise ValueError
        return day, instant
    except (ValueError, TypeError, KeyError):
        raise DomainError("invalid_clinical_time") from None
