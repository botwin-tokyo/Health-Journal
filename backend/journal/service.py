from records.validation import DomainError, clinical_time, decimal, text

SCALES = {
    "feeling": {"very_low", "low", "okay", "good", "very_good"},
    "energy": {"very_low", "low", "okay", "good", "very_good"},
    "severity": {"none", "mild", "moderate", "severe"},
}


def validate(kind, body):
    day, _ = clinical_time(body)
    visibility = body.get("visibility", "private")
    if visibility not in {"private", "shared"}:
        raise DomainError("invalid_visibility")
    common = {
        "clinical_date",
        "time_precision",
        "measured_start",
        "measured_end",
        "timezone",
        "original_offset_minutes",
        "timezone_provenance",
        "visibility",
    }
    allowed = common | (
        {
            "title",
            "text",
            "tags",
            "feeling",
            "energy",
            "severity",
            "linked_record_ids",
            "included_medication_ids",
        }
        if kind == "journal"
        else {"text", "origin_record_id"}
        if kind == "question"
        else {"name", "dose", "unit", "note", "parent_entry_id"}
    )
    if set(body) - allowed:
        raise DomainError("unknown_journal_field")
    payload = dict(body)
    if kind == "journal":
        text(body.get("title", ""), 256)
        text(body.get("text", ""), 16384)
        tags = body.get("tags", [])
        if not isinstance(tags, list) or len(tags) > 20:
            raise DomainError("invalid_tags")
        for tag in tags:
            text(tag, 64, True)
        for field, choices in SCALES.items():
            if body.get(field) is not None and body[field] not in choices:
                raise DomainError("invalid_self_report")
        if not (
            body.get("text", "").strip()
            or tags
            or any(body.get(k) for k in SCALES)
            or body.get("included_medication_ids")
        ):
            raise DomainError("empty_journal_entry")
        payload.update(
            feeling_scale="feeling-v1", energy_scale="energy-v1", severity_scale="severity-v1"
        )
    elif kind == "question":
        text(body.get("text"), 16384, True)
    else:
        text(body.get("name"), 256, True)
        text(body.get("note", ""), 16384)
        if body.get("dose") is not None:
            if decimal(body["dose"]) <= 0:
                raise DomainError("invalid_dose")
            text(body.get("unit"), 64, True)
        if visibility == "shared" and not body.get("parent_entry_id"):
            raise DomainError("shared_entry_required")
    return payload, day, visibility
