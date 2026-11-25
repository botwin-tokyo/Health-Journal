from records.validation import DomainError, decimal, text


def review(body):
    if body.get("patient_match_confirmed") is not True:
        raise DomainError("patient_match_required")
    if body.get("source_report_status") not in {"preliminary", "final", "corrected", "unknown"}:
        raise DomainError("invalid_report_status")
    rows = body.get("results", [])
    if not isinstance(rows, list) or len(rows) > 5000:
        raise DomainError("invalid_result_count")
    for row in rows:
        text(row.get("label"), 256, True)
        text(row.get("raw_result_text"), 16384, True)
        if row.get("excluded"):
            text(row.get("exclusion_reason"), 256, True)
            continue
        if row.get("ambiguous"):
            raise DomainError("unresolved_extraction")
        if row.get("value_kind") not in {"numeric", "text", "coded"}:
            raise DomainError("invalid_result_kind")
        if row["value_kind"] == "numeric":
            decimal(row.get("value"))
            if row.get("operator") not in {"eq", "lt", "le", "gt", "ge"}:
                raise DomainError("invalid_result_operator")
        elif row.get("value") is not None:
            raise DomainError("text_result_is_not_numeric")
        for field in ["unit", "reference_text", "lab_flag", "specimen", "method"]:
            if row.get(field) is not None:
                text(row[field], 1024)
    if not rows and not body.get("document_only"):
        raise DomainError("empty_lab_review")
    return body


def analyte_series(row):
    import hashlib
    import json

    label = (
        row.get("mapped_code")
        if row.get("mapping_verified") is True
        else row.get("original_code") or row["label"]
    )
    definition = {
        "analyte": label,
        "mapping_verified": row.get("mapping_verified") is True,
        "specimen": row.get("specimen"),
        "method": row.get("method"),
        "unit": row.get("unit"),
    }
    return hashlib.sha256(
        json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def convert_mass_volume(value, unit, target):
    from decimal import Decimal, localcontext

    from records.validation import DomainError, decimal, derived

    # Identical analyte/specimen/method must be checked by the caller. No molar conversions.
    factors = {
        "g/L": Decimal("1"),
        "mg/L": Decimal(".001"),
        "mg/dL": Decimal(".01"),
        "ug/L": Decimal(".000001"),
    }
    if unit not in factors or target not in factors:
        raise DomainError("unsupported_unit_conversion")
    with localcontext() as context:
        context.prec = 60
        return derived(decimal(value) * factors[unit] / factors[target])
