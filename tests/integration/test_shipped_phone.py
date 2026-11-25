"""The existing exporter names are inputs, never requirements for a phone rewrite."""

import pytest
from ingest.mapping import normalize
from ingest.phone_wire import compact_assets

TIME = {
    "measured_start": "2020-01-02T08:00:00-05:00",
    "source_type": "manual",
    "timezone": "EST5EDT",
}


def mapped(kind, **data):
    return normalize({"kind": kind, "payload": {**TIME, **data}})


@pytest.mark.parametrize(
    "kind,native,expected",
    [
        (
            "body_profile",
            {"id": "p", "revision": 1, "heightCm": "180", "birthDate": "1980-01-01"},
            "body_context",
        ),
        ("body_goals", {"profileId": "p", "weightKg": "80", "fatPercent": None}, "body_context"),
        ("body_circumference", {"profileId": "p", "site": "waist", "cm": "85"}, "body_observation"),
    ],
)
def test_native_body_names(kind, native, expected):
    result = mapped(kind, native_record=native)
    assert result[0] == expected
    assert result[3]["native_record"] == native


def test_shipped_sleep_and_scale():
    result = mapped(
        "sleep_session",
        source_type="direct_ring",
        measured_end="2020-01-03T08:00:00-05:00",
        complete=True,
        sleep_seconds="20000",
        native_record={
            "source": "DIRECT_RING",
            "receivedAt": 1578056400000,
            "acquisition": "DIRECT_RING_DOWNLOAD",
        },
    )
    assert result[3]["clinical_eligible"] and str(result[2]) == "2020-01-03"
    assert (
        mapped(
            "scalar_observation", source_type="direct_scale", metric_id="bmi", unit="", value="24"
        )[0]
        == "body_observation"
    )
    assert (
        mapped(
            "scalar_observation",
            source_type="direct_scale",
            metric_id="weight",
            unit="kg",
            value="80",
        )[0]
        == "weight"
    )


def test_shipped_native_mir_trials_and_chunk_projection():
    native = {
        "source": "MIR_BLE",
        "trials": [
            {
                "id": "t",
                "at": 1577970000000,
                "metrics": {"fvc": "4", "fev1": "3"},
                "complete": True,
                "flowVolume": [{"x": "1", "y": "-2"}],
                "volumeTime": [{"x": "1", "y": "3"}],
            }
        ],
    }
    result = mapped(
        "pulmonary_session",
        source_type="direct_device",
        status="SAVED",
        values={"fvc": "4"},
        native_record=native,
    )
    data = result[3]
    assert data["clinical_eligible"] and data["values"]["fev1"] == "3"
    assert data["trials"][0]["flow_volume"]["points"][0]["y"] == "-2"
    data["native_record_assets"] = {"ids": ["asset"]}
    compact_assets(data)
    assert "native_record" not in data and "flow_volume" not in data["trials"][0]
    assert data["trials"][0]["asset_ids"] == ["asset"]


def test_shipped_workout_details():
    result = mapped(
        "workout",
        source_type="manual",
        state="completed",
        activity="walk",
        measured_start="2020-01-02T13:00:00Z",
        measured_end="2020-01-02T14:00:00Z",
        timezone="Etc/UTC",
        timezone_provenance="offset_only",
        duration_seconds="3600",
        native_record={
            "details": {
                "intervals": [
                    {"wallStart": 1577970000000, "wallEnd": 1577973600000, "kind": "WORK"}
                ],
                "sets": [],
            }
        },
    )
    assert result[3]["clinical_eligible"]
    assert result[3]["intervals"][0]["kind"] == "work"


def test_java_minute_precision_and_tiny_curve_values():
    result = mapped(
        "sleep_session",
        source_type="direct_ring",
        measured_start="2020-01-02T22:00-05:00",
        measured_end="2020-01-03T06:00-05:00",
        complete=True,
        stages=[
            {"start": "2020-01-02T22:00-05:00", "end": "2020-01-03T06:00-05:00", "stage": "light"}
        ],
    )
    assert result[3]["clinical_eligible"]
    assert result[3]["measured_start"] == "2020-01-02T22:00:00-05:00"


def test_phone_celsius_unit_spelling():
    result = mapped(
        "scalar_observation",
        metric_id="skin_temperature_processed",
        unit="C",
        value="35",
        source_type="direct_device",
    )
    assert result[3]["clinical_eligible"]
    assert result[3]["unit"] == "°C" and result[3]["original_unit"] == "C"
