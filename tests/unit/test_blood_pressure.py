from copy import deepcopy

import pytest
from django.test import RequestFactory
from ingest.mapping import normalize
from records.validation import DomainError
from sleep_activity.blood_pressure import page


def item(metric="blood_pressure_systolic", verified=True):
    return {
        "kind": "scalar_observation",
        "operation": "upsert",
        "source_record_id": "bp:one:" + metric,
        "source_revision": 1,
        "payload": {
            "metric_id": metric,
            "value": "118",
            "unit": "mmHg",
            "source_type": "direct_device",
            "validity": "valid",
            "clinical_date": "2020-01-02",
            "measured_start": "2020-01-02T10:00:00-05:00",
            "time_precision": "second",
            "timezone": "EST5EDT",
            "timezone_provenance": "source",
            "original_offset_minutes": -300,
            "timestamp_basis": "measurement" if verified else "phone_received",
            "measurement_time_verified": verified,
            "measurement_group_id": "one",
            "native_record": {"deviceTime": "2020-01-02 10:00:00"},
        },
    }


def test_verified_pressure_maps_to_dedicated_history_kind():
    kind, category, day, data = normalize(item())
    assert (kind, category, str(day)) == ("blood_pressure", "sleep_activity", "2020-01-02")
    assert data["clinical_eligible"] is True
    assert data["measurement_group_id"] == "one"


def test_unknown_dates_and_monitor_flags_remain_evidence():
    raw = item(verified=False)
    saved = deepcopy(raw)
    data = normalize(raw)[3]
    assert data["clinical_eligible"] is False
    assert "measurement_time_unverified" in data["evidence_reasons"]
    assert raw == saved
    raw = item()
    raw["payload"]["native_record"]["cuffLoose"] = True
    assert "monitor_quality_flag" in normalize(raw)[3]["evidence_reasons"]


def test_units_and_pulse_are_validated():
    raw = item("blood_pressure_pulse")
    raw["payload"].update(value="73", unit="beats/min")
    assert normalize(raw)[0] == "blood_pressure"
    raw["payload"]["unit"] = "kg"
    with pytest.raises(DomainError):
        normalize(raw)


def test_page_uses_authorized_current_records_and_preserves_cursor(monkeypatch):
    from records import service

    calls = []

    def permitted(*args):
        calls.append(args)
        return {"items": [], "cursor": "next"}

    monkeypatch.setattr(service, "permitted", permitted)
    result = page.__wrapped__(
        RequestFactory().get("/", {"from": "2020-01-01", "to": "2020-01-28", "cursor": "before"})
    )
    assert result["cursor"] == "next"
    assert calls[0][1:] == (["blood_pressure"], "2020-01-01", "2020-01-28", 200, "before")
    with pytest.raises(DomainError):
        page.__wrapped__(RequestFactory().get("/", {"from": "2020-02-01", "to": "2020-01-01"}))
