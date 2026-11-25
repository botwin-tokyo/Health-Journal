from decimal import Decimal, localcontext

from access.policy import AccessDenied
from django.utils.crypto import salted_hmac
from records import service
from records.models import Designation, Record
from records.validation import DomainError, clinical_time, decimal, derived


def weight(payload):
    allowed = {
        "value",
        "unit",
        "clinical_date",
        "time_precision",
        "measured_start",
        "measured_end",
        "timezone",
        "original_offset_minutes",
        "timezone_provenance",
        "designation",
        "note_operation",
        "representative_action",
        "replacement_id",
    }
    if set(payload) - allowed:
        raise DomainError("unknown_weight_field")
    value = decimal(payload.get("value"))
    if value <= 0 or payload.get("unit") not in {"kg", "lb"}:
        raise DomainError("invalid_weight")
    day, _ = clinical_time(payload)
    with localcontext() as ctx:
        ctx.prec = 60
        kg = value if payload["unit"] == "kg" else value * Decimal("0.45359237")
    data = {
        k: v
        for k, v in payload.items()
        if k not in {"designation", "note_operation", "representative_action", "replacement_id"}
    }
    data.update(
        metric_id="weight",
        canonical_value=derived(kg),
        canonical_unit="kg",
        source_type="manual",
        qualification="reported",
        validity="valid",
        availability="available",
        method_version="mass-v1",
    )
    return data, day


def day_etag(patient, day, row=None):
    if row is None and patient.pk:
        row = Designation.objects.filter(
            patient=patient, clinical_date=day, domain="body", slot=""
        ).first()
    return (
        '"'
        + salted_hmac(
            "body-designation",
            f"{patient.owner_id}:{day}:{row.version if row else 0}:{row.record_id if row else ''}",
        ).hexdigest()
        + '"'
    )


def designate(patient, day, record, expected):
    row = (
        Designation.objects.select_for_update()
        .filter(patient=patient, clinical_date=day, domain="body", slot="")
        .first()
    )
    if expected is None:
        raise DomainError("precondition_required", 428)
    if expected != day_etag(patient, day, row):
        raise DomainError("revision_conflict", 412)
    if record and (
        record.patient_id != patient.pk
        or record.kind != "weight"
        or record.deleted_at
        or record.current.blob.clinical_date != day
    ):
        raise AccessDenied()
    if row:
        row.record = record
        row.automatic = False
        row.version += 1
        row.save()
    else:
        row = Designation.objects.create(
            patient=patient, clinical_date=day, domain="body", record=record
        )
    return day_etag(patient, day, row)


def save_weight(request, payload, record_id=None):
    previous = service.replay(request)
    if previous is not None:
        return previous
    data, day = weight(payload)
    designation = payload.get("designation", {"action": "leave_unchanged"})
    if not isinstance(designation, dict) or designation.get("action") not in {
        "leave_unchanged",
        "make_representative",
    }:
        raise DomainError("invalid_designation")
    context, patient = service.owner_context(request)
    note_payload = None
    if payload.get("note_operation"):
        from journal.service import validate
        from records.components import prepare

        note = payload["note_operation"]
        if set(note) != {"text", "visibility"} or note["visibility"] != "private":
            raise DomainError("invalid_private_note")
        note_payload, note_day, _ = validate(
            "journal",
            {
                "text": note["text"],
                "clinical_date": day.isoformat(),
                "time_precision": "day",
                "visibility": "private",
            },
        )

    if record_id and Designation.objects.filter(patient=patient, record_id=record_id).exists():
        if payload.get("representative_action") not in {"clear", "keep_corrected", "replace"}:
            raise DomainError("representative_confirmation_required", 409)

    def prepare_note(record):
        if note_payload is None:
            return None
        linked = {**note_payload, "linked_record_ids": [str(record.pk)]}
        _, save_note = prepare(context, patient, "journal", linked, note_day)
        return lambda record, revision, patient: save_note()

    def commit(record, revision, patient):
        if record_id and payload.get("representative_action") in {
            "clear",
            "keep_corrected",
            "replace",
        }:
            for row in Designation.objects.select_for_update().filter(
                patient=patient, record_id=record_id
            ):
                action = payload["representative_action"]
                if action == "keep_corrected":
                    if row.clinical_date != day:
                        raise DomainError("designation_date_changed", 409)
                    row.record = record
                elif action == "replace":
                    replacement = Record.objects.filter(
                        pk=payload.get("replacement_id"),
                        patient=patient,
                        kind="weight",
                        deleted_at__isnull=True,
                        current__blob__clinical_date=row.clinical_date,
                    ).first()
                    if not replacement:
                        raise DomainError("invalid_replacement")
                    row.record = replacement
                else:
                    row.record = None
                row.version += 1
                row.save()
        if designation["action"] == "make_representative":
            expected = designation.get("expected_etag")
            if expected is None:
                raise DomainError("precondition_required", 428)
            if expected != day_etag(patient, day):
                raise DomainError("revision_conflict", 412)
            previous = Designation.objects.filter(
                patient=patient, clinical_date=day, domain="body", record__isnull=False
            ).first()
            if (
                previous
                and previous.record_id != record.pk
                and designation.get("confirm_replacement") is not True
            ):
                raise DomainError("replacement_confirmation_required", 409)
            designate(patient, day, record, designation.get("expected_etag"))

    return service.save(
        request, "weight", data, day, record_id, commit_hook=commit, prepare_hook=prepare_note
    )
