"""Executable phone contract. No network schema resolution or adapter approval."""

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from records.validation import DomainError

ROOT = Path(__file__).resolve().parents[2] / "contracts/phone"
VERSION = "health03-phone-2026-11-09"


@lru_cache
def schema():
    return json.loads((ROOT / "batch.schema.json").read_text())


@lru_cache
def registry():
    return json.loads((ROOT / "metrics.json").read_text())


@lru_cache
def validator():
    document = schema()
    return Draft202012Validator(
        {"$ref": "#/$defs/item", "$defs": document["$defs"]}, format_checker=FormatChecker()
    )


def validate_item(item):
    errors = sorted(validator().iter_errors(item), key=lambda error: str(list(error.absolute_path)))
    if errors:
        error = errors[0]
        field = str(list(error.absolute_path)[-1]) if error.absolute_path else "item"
        known = {
            "source_type",
            "unit",
            "value",
            "measured_start",
            "measured_end",
            "clinical_date",
            "trials",
            "stages",
            "state",
            "status",
            "payload",
            "source_revision",
            "source_record_id",
        }
        raise DomainError("invalid_" + (field if field in known else "item_schema"))
