import pytest
from ingest.canonical import qualified
from ingest.mapping import normalize
from records.validation import DomainError


def item(**changes):
    return {'kind': 'scalar_observation', 'payload': {
        'metric_id': 'bpm', 'value': '68', 'unit': 'beats/min', 'validity': 'valid',
        'clinical_date': '2026-11-09', 'time_precision': 'day',
        'source_type': 'direct_device', **changes,
    }}


def test_phone_stats_have_no_capability_or_provenance_gate():
    for changes in [{'source_type': 'direct_scale'}, {'metric_id': 'new_phone_metric'},
                    {'extra_evidence': {'source': 'phone'}}, {'metric_id': 'skin_deviation', 'value': '-2', 'unit': '°C'},
                    {'validity': 'source_reported', 'unit': 'bpm'}]:
        assert qualified(item(**changes))[0] == 'observation'


@pytest.mark.parametrize('changes', [{'value': 'NaN'}, {'clinical_date': 'not-a-date'}])
def test_unreadable_values_are_not_invented(changes):
    with pytest.raises(DomainError):
        qualified(item(**changes))


def test_direct_scale_weight_maps_to_weight_page_and_keeps_original():
    mapped, category, day, data = normalize(item(metric_id='weight', value='150', unit='lb',
                                               source_type='direct_scale', extra_evidence='retained'))
    assert (mapped, category, str(day)) == ('weight', 'body', '2026-11-09')
    assert data['canonical_value'] == '68.0388555'
    assert data['value'] == '150' and data['extra_evidence'] == 'retained'


def test_sleep_is_recorded_on_wake_date_without_processing_receipt_gate():
    data = {'source_type': 'direct_device', 'measured_start': '2026-11-08T22:00:00-05:00',
            'measured_end': '2026-11-09T06:00:00-05:00', 'clinical_date': '2026-11-09',
            'time_precision': 'second', 'original_offset_minutes': -300,
            'timezone': 'EST5EDT', 'timezone_provenance': 'source',
            'sleep_seconds': 27000, 'stages': [], 'complete': True}
    mapped, category, day, output = normalize({'kind': 'sleep_session', 'payload': data})
    assert (mapped, category, str(day)) == ('sleep', 'sleep_activity', '2026-11-09')
    assert output['sleep_seconds'] == '27000'
