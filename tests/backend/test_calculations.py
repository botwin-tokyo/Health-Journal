import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from body.service import weight
from breathing.service import manual, normalize_pef, representative
from metrics.calculations import baseline, percentile
from records.validation import DomainError, clinical_time, decimal, parse_json
from sleep_activity.calculations import calories, clock_variation, sleep_summary


@pytest.mark.parametrize(
    "value", ["NaN", "1e3", "1,000", "1.1234567890123456789", "0" * 100, "9" * 37]
)
def test_decimal_rejects_ambiguous_or_unbounded_values(value):
    with pytest.raises(DomainError):
        decimal(value)


def test_json_duplicate_keys_and_nan_rejected():
    for raw in [b'{"x":1,"x":2}', b'{"x":NaN}', b"[]"]:
        with pytest.raises(DomainError):
            parse_json(raw)


def test_exact_weight_and_no_invented_time():
    result, day = weight(
        {"value": "156.2", "unit": "lb", "clinical_date": "2026-11-07", "time_precision": "day"}
    )
    assert Decimal(result["canonical_value"]) == Decimal("156.2") * Decimal("0.45359237")
    assert day == date(2026, 11, 7) and "measured_start" not in result
    with pytest.raises(DomainError):
        clinical_time(
            {
                "clinical_date": "2026-11-07",
                "time_precision": "day",
                "measured_start": "2026-11-07T00:00:00Z",
            }
        )


def test_pulmonary_real_trial_ratio_and_pef():
    result, _ = manual(
        {
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "values": {"fev1": "3", "fvc": "4"},
        }
    )
    assert (
        result["values"]["fev1_fvc"] == "75" and result["slot"] is None and result["curves"] is None
    )
    assert normalize_pef("5", "L/s") == "300" and normalize_pef("300", "L/min") == "300"
    trials = [
        {"id": "b", "sequence": 2, "fvc": "4", "fev1": "3", "capture_status": "complete"},
        {"id": "a", "sequence": 1, "fvc": "4", "fev1": "3", "capture_status": "complete"},
    ]
    assert representative(trials)["id"] == "a"


def test_baseline_r7_current_exclusion_and_fixture_mean():
    assert percentile(["1", "2", "3", "4"], ".25") == Decimal("1.75")
    day = date(2026, 11, 7)
    rows = [
        {"date": day - timedelta(days=i), "value": "10", "series_id": "one", "revision_id": str(i)}
        for i in range(14)
    ]
    assert baseline(rows, day)["eligible"] is False
    rows.append(
        {"date": day - timedelta(days=14), "value": "10", "series_id": "one", "revision_id": "14"}
    )
    result = baseline(rows, day)
    assert (
        result["eligible"]
        and result["contributor_day_count"] == 14
        and "0" not in result["revision_ids"]
    )
    fixture = json.loads(Path("tests/fixtures/synthetic/backend-v1.json").read_text())
    values = [Decimal(row["value"]) for row in fixture["weights"][-7:]]
    assert sum(values) / 7 == Decimal("156.6")
    assert percentile([row["value"] for row in fixture["weights"]], ".5") == Decimal("157.0")


def test_sleep_dst_unknown_and_overlap():
    result = sleep_summary("2026-11-01T00:30:00-04:00", "2026-11-01T02:30:00-05:00", [])
    assert result["span_seconds"] == 10800 and result["stage_seconds"]["unknown"] == 10800
    with pytest.raises(DomainError):
        sleep_summary(
            "2026-11-07T00:00:00Z",
            "2026-11-07T02:00:00Z",
            [
                {"start": "2026-11-07T00:00:00Z", "end": "2026-11-07T01:00:00Z", "stage": "light"},
                {"start": "2026-11-07T00:30:00Z", "end": "2026-11-07T01:30:00Z", "stage": "deep"},
            ],
        )
    assert clock_variation([0, 43200]) is None
    assert calories("met-active-v1", "70", "30", "1") == "0"
