from decimal import Decimal, localcontext

from records.validation import DomainError, derived


def unit(request):
    selected = request.GET.get("weight_unit", "kg")
    if selected not in {"kg", "lb"}:
        raise DomainError("invalid_weight_unit")
    return selected


def convert(value, selected):
    if value is None:
        return None
    with localcontext() as context:
        context.prec = 60
        return derived(
            Decimal(value) / Decimal("0.45359237") if selected == "lb" else Decimal(value)
        )


def aggregate(value, selected):
    return {
        **value,
        "display_unit": selected,
        "display_value": convert(value.get("value"), selected),
        "display_p25": convert(value.get("p25"), selected),
        "display_p75": convert(value.get("p75"), selected),
    }


def record(value, selected):
    if value["kind"] == "weight":
        value["data"] = {
            **value["data"],
            "display_value": convert(value["data"].get("canonical_value"), selected),
            "display_unit": selected,
        }
    elif value["kind"] == "baseline" and value["data"].get("metric_id") == "weight":
        value["data"] = aggregate(value["data"], selected)
    return value


def comparison(context, patient, day, reference, selected):
    from access.policy import AccessDenied
    from metrics.series import definition, fingerprint
    from records import service
    from records.models import Designation

    choice = (
        Designation.objects.filter(
            patient_id=patient.pk, clinical_date=day, domain="body", record__deleted_at=None
        )
        .select_related("record__current__blob")
        .first()
    )
    if not choice or not choice.record_id or reference.get("value") is None:
        return {"value": None, "absent_reason": reference.get("absent_reason") or "not_recorded"}
    try:
        value = service.dto(context, choice.record)["data"]
    except AccessDenied:
        return {"value": None, "absent_reason": "not_in_shared_scope"}
    current_series = fingerprint(definition(value, "weight"))
    reference_series = reference.get("series_id") or next(
        iter(reference.get("series_definitions", {})), None
    )
    if reference_series and current_series != reference_series:
        return {"value": None, "absent_reason": "source_conflict"}
    with localcontext() as decimal_context:
        decimal_context.prec = 60
        delta = derived(Decimal(value["canonical_value"]) - Decimal(reference["value"]))
    start, end = reference.get("from_date"), reference.get("to_date")
    return {
        "value": delta,
        "unit": "kg",
        "display_value": convert(delta, selected),
        "display_unit": selected,
        "comparison_in_reference_period": bool(start and end and start <= day.isoformat() <= end),
        "calculation_state": reference.get("calculation_state", "current"),
    }
