"""Deterministic fictional inputs; never a native capability receipt."""

import uuid
from datetime import datetime, timedelta


def supplemental_records():
    day = "2026-11-07"
    common = {
        "clinical_date": day,
        "time_precision": "day",
        "source_type": "manual",
        "validity": "valid",
        "synthetic_only": True,
    }
    records = [
        (
            "journal",
            {
                **common,
                "title": "Fictional daily note",
                "text": "Synthetic fixture only.",
                "visibility": "private",
            },
        ),
        ("question", {**common, "text": "Fictional appointment question", "visibility": "private"}),
        (
            "lab",
            {
                **common,
                "label": "Fictional analyte",
                "raw_result_text": "<5",
                "value_kind": "numeric",
                "value": "5",
                "operator": "lt",
                "unit": "mg/L",
                "review_status": "reviewed",
                "source_report_status": "final",
            },
        ),
        (
            "settings",
            {
                "timezone": "EST5EDT",
                "weight_unit": "lb",
                "morning_sync": False,
                "nightly_upload_time": "00:00",
            },
        ),
    ]
    from breathing.service import manual

    pulmonary, _ = manual(
        {**common, "values": {"fev1": "3.82", "fvc": "4.87", "pef": "510"}, "slot": "morning"}
    )
    pulmonary["synthetic_only"] = True
    records.append(("pulmonary", pulmonary))
    start = datetime.fromisoformat("2026-11-06T21:00:00-05:00")
    stages = []
    point = start
    for minutes, stage in [
        (226, "light"),
        (24, "awake"),
        (70, "deep"),
        (112, "rem"),
        (18, "unknown"),
    ]:
        end = point + timedelta(minutes=minutes)
        stages.append({"start": point.isoformat(), "end": end.isoformat(), "stage": stage})
        point = end
    records.append(
        (
            "sleep",
            {
                **common,
                "source_type": "direct_device",
                "complete": True,
                "main_session": True,
                "measured_start": start.isoformat(),
                "measured_end": point.isoformat(),
                "timezone": "EST5EDT",
                "stages": stages,
            },
        )
    )
    for index in range(27):
        instant = datetime.fromisoformat("2026-11-07T05:00:00-05:00") + timedelta(
            minutes=15 * index
        )
        records.append(
            (
                "observation",
                {
                    **common,
                    "metric_id": "bpm",
                    "source_type": "direct_device",
                    "statistic": "requested_sample",
                    "value": "68",
                    "unit": "beats/min",
                    "qualification": "reported",
                    "measured_start": instant.isoformat(),
                    "timezone": "EST5EDT",
                },
            )
        )
    records.append(
        (
            "observation",
            {
                **common,
                "metric_id": "phone_steps",
                "source_type": "phone_recording",
                "value": "7420",
                "unit": "count",
                "measured_start": "2026-11-07T05:00:00-05:00",
                "measured_end": "2026-11-07T19:00:00-05:00",
                "timezone": "EST5EDT",
            },
        )
    )
    records.append(
        (
            "workout",
            {
                **common,
                "state": "completed",
                "timezone": "EST5EDT",
                "intervals": [
                    {
                        "start": "2026-11-07T08:00:00-05:00",
                        "end": "2026-11-07T08:34:00-05:00",
                        "kind": "work",
                    }
                ],
            },
        )
    )
    return [
        (uuid.uuid5(uuid.NAMESPACE_URL, f"health03-supplement-{index}"), kind, payload)
        for index, (kind, payload) in enumerate(records)
    ]
