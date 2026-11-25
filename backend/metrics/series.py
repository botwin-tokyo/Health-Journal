import hashlib
import json

from access.policy import AccessDenied
from records import service
from records.models import Designation
from records.validation import DomainError

from .calculations import baseline


def definition(payload, metric, slot=None):
    return {
        "metric": metric,
        "source_type": payload.get("source_type"),
        "device": payload.get("device_id", payload.get("device", "manual")),
        "statistic": payload.get(
            "statistic", "selected_real_trial" if metric != "weight" else "designated_morning"
        ),
        "algorithm_version": payload.get(
            "algorithm_version", payload.get("method_version", "manual-entry-v1")
        ),
        "profile_revision": payload.get("profile_revision"),
        "unit": payload.get(
            "canonical_unit", payload.get("units", {}).get(metric, payload.get("unit"))
        ),
        "slot": slot,
    }


def fingerprint(definition):
    return hashlib.sha256(
        json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def contributors(context, patient, metric, start, end, slot=None, series_id=None):
    domain = "body" if metric == "weight" else "breathing"
    if domain == "breathing" and slot not in {"morning", "noon", "evening"}:
        raise DomainError("slot_required")
    selected = (
        Designation.objects.filter(
            patient=patient,
            domain=domain,
            slot=slot or "",
            clinical_date__range=(start, end),
            record__isnull=False,
            record__deleted_at__isnull=True,
        )
        .select_related("record__current__blob")
        .order_by("clinical_date")
    )
    rows = []
    deps = []
    definitions = {}
    for choice in selected[:367]:
        dto = service.dto(context, choice.record)
        payload = dto["data"]
        value = (
            payload.get("canonical_value")
            if metric == "weight"
            else payload.get("values", {}).get(metric)
        )
        if value is None or payload.get("clinical_eligible") is False or payload.get("validity") not in {"valid", "reported"}:
            continue
        item = definition(payload, metric, slot)
        key = fingerprint(item)
        definitions[key] = item
        if series_id and key != series_id:
            continue
        rows.append(
            {
                "date": choice.clinical_date,
                "series_id": key,
                "value": value,
                "revision_id": dto["revision_id"],
            }
        )
        deps.append(choice.record.current.blob)
    if not series_id and len({r["series_id"] for r in rows}) > 1:
        raise DomainError("series_selection_required", 409)
    return rows, deps, definitions


def recent(context, patient, metric, day, slot=None, series_id=None):
    from datetime import timedelta

    from .aggregates import read

    cached = None if series_id else read(context, patient, metric, day, slot=slot or "")
    if cached is not None:
        return cached
    try:
        rows, _, series_definitions = contributors(
            context,
            patient,
            metric,
            day - timedelta(days=28),
            day - timedelta(days=1),
            slot,
            series_id,
        )
        result = baseline(rows, day, "recent")
        result["series_definitions"] = series_definitions
        return result
    except AccessDenied:
        return {"value": None, "absent_reason": "not_in_shared_scope"}
    except DomainError as error:
        if error.code != "series_selection_required":
            raise
        return {"value": None, "absent_reason": "source_conflict"}
