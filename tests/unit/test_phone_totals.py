from datetime import date

from sleep_activity.phone_totals import recorded_day_total


def test_day_total_preserves_zero_and_requires_one_complete_phone_source():
    day = date(2026, 11, 9)
    row = {'clinical_date': day.isoformat(), 'revision_id': 'r1',
           'data': {'metric_id': 'phone_steps', 'time_precision': 'day', 'value': '0'}}
    assert recorded_day_total([row], day, 'phone')['value'] == '0'
    assert recorded_day_total([row], day, 'ring') is None
    assert recorded_day_total([row], day, 'phone', partial=True) is None
    assert recorded_day_total([row, row], day, 'phone')['absent_reason'] == 'source_conflict'
