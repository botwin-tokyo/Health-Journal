from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings as django_settings
from operations.models import AuditEvent, BackupSet, SecurityOutbox
from records import service
from records.http import endpoint
from records.models import Record
from records.validation import DomainError, parse_json

DEFAULTS = {
    "display_name": "",
    "time_format": "12h",
    "timezone": django_settings.TIME_ZONE,
    "weight_unit": "lb",
    "morning_sync": False,
    "nightly_upload_time": "00:00",
    "pulmonary_windows": {
        "morning": ["04:00", "11:00"],
        "noon": ["11:00", "16:00"],
        "evening": ["16:00", "24:00"],
    },
}


@endpoint({"GET", "PATCH"})
def settings(request):
    context, patient = service.owner_context(request)
    record = Record.objects.filter(
        patient=patient, kind="settings", deleted_at__isnull=True
    ).first()
    if request.method == "GET":
        if record:
            result = service.dto(context, record)
            result["data"] = {**DEFAULTS, **result["data"]}
            return result
        return {"data": DEFAULTS, "etag": '"settings-empty"', "id": None}
    body = parse_json(request.body)
    if set(body) - {
        "timezone",
        "weight_unit",
        "morning_sync",
        "pulmonary_windows",
        "display_name",
        "time_format",
    }:
        raise DomainError("invalid_setting")
    payload = {**DEFAULTS, **(service.dto(context, record)["data"] if record else {}), **body}
    try:
        ZoneInfo(payload["timezone"])
    except (ZoneInfoNotFoundError, TypeError):
        raise DomainError("invalid_timezone") from None
    if payload["weight_unit"] not in {"lb", "kg"} or type(payload["morning_sync"]) is not bool:
        raise DomainError("invalid_setting")
    if not isinstance(payload["display_name"], str) or len(payload["display_name"]) > 80:
        raise DomainError("invalid_setting")
    if payload["time_format"] not in {"12h", "24h"}:
        raise DomainError("invalid_setting")
    windows = payload["pulmonary_windows"]
    if not isinstance(windows, dict) or set(windows) != {"morning", "noon", "evening"}:
        raise DomainError("invalid_windows")
    from breathing.service import window_intervals

    window_intervals(windows)
    if not record and request.headers.get("If-Match") != '"settings-empty"':
        raise DomainError("revision_conflict", 412)

    def commit(new, revision, patient):
        if (
            not record
            and Record.objects.filter(patient=patient, kind="settings").exclude(pk=new.pk).exists()
        ):
            raise DomainError("revision_conflict", 412)

    return service.save(
        request,
        "settings",
        payload,
        date.today(),
        record.pk if record else None,
        commit_hook=commit,
    )


@endpoint({"GET"})
def security_status(request):
    service.owner_context(request)
    backup = BackupSet.objects.filter(state="complete").order_by("-finished_at").first()
    return {
        "backup": ("complete" if backup else "not_configured")
        if django_settings.HEALTH03_BACKUPS_ENABLED
        else "disabled_by_owner",
        "last_successful_backup": backup.finished_at.isoformat() if backup else None,
        "restore": "not_verified",
        "recovery_policy": "off_device"
        if django_settings.HEALTH03_BACKUPS_ENABLED
        else "local_only_no_backup",
        "ledger_pending": SecurityOutbox.objects.filter(acknowledged_at__isnull=True).count(),
        "encryption": "enabled",
        "native_integration": "not_verified",
    }


@endpoint({"GET"})
def events(request):
    service.owner_context(request)
    return {
        "items": list(
            AuditEvent.objects.order_by("-created_at").values(
                "id", "action", "outcome", "created_at"
            )[:100]
        )
    }
