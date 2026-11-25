from django.test import RequestFactory
from sleep_activity.views import page


def test_partial_sleep_and_totals_survive_observation_pagination(monkeypatch):
    from records import service
    from sleep_activity import phone_totals

    day = "2020-01-02"
    sleep = {
        "id": "sleep",
        "kind": "sleep",
        "clinical_date": day,
        "data": {
            "measured_start": day + "T00:00:00Z",
            "measured_end": day + "T02:00:00Z",
            "complete": False,
            "clinical_eligible": False,
            "source_type": "direct_ring",
        },
    }

    def workout(identifier, seconds):
        return {
            "id": identifier,
            "kind": "workout",
            "clinical_date": day,
            "data": {
                "state": "completed",
                "duration_seconds": seconds,
                "timezone_provenance": "offset_only",
            },
        }

    def permitted(request, kinds, *args):
        return {
            "items": [sleep, workout("one", "1800"), workout("two", "1200")]
            if "sleep" in kinds
            else [],
            "cursor": None if "sleep" in kinds else "more-observations",
        }

    monkeypatch.setattr(service, "permitted", permitted)
    monkeypatch.setattr(
        phone_totals,
        "daily_phone_rows",
        lambda *args: [
            {
                "clinical_date": day,
                "revision_id": "steps",
                "data": {"metric_id": "phone_steps", "time_precision": "day", "value": "739"},
            }
        ],
    )
    result = page.__wrapped__(RequestFactory().get("/", {"date": day}))
    assert result["sleep"]["display_status"] == "Partial session"
    assert result["sleep"]["stage_summary"]["known_sleep_seconds"] is None
    assert result["sleep"]["stage_summary"]["span_seconds"] == 7200
    assert result["steps"]["value"] == "739"
    assert result["workout_total_seconds"] == "3000"
    assert len(result["workouts"]) == 2
    assert result["cursor"] == "more-observations"
