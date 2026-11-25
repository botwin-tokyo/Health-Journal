import hashlib
import json
import uuid
from datetime import timedelta

import pytest
from accounts.models import Account
from allauth.account.models import EmailAddress
from django.utils import timezone
from ingest.canonical import commit_item
from ingest.models import SourceConnection
from jobs.models import Job
from records.models import Designation, Record
from uploader.models import DeviceRegistration


@pytest.mark.django_db
def test_authenticated_phone_weight_and_sleep_commit_automatically(monkeypatch):
    owner = Account.objects.create_user('phone-domain@example.invalid', role='owner', enrollment_complete=True)
    EmailAddress.objects.create(user=owner, email=owner.email, verified=True)
    device = DeviceRegistration.objects.create(owner=owner, label='Test')
    source = SourceConnection.objects.create(device=device, namespace=uuid.uuid4())
    job = Job.objects.create(kind='ingest', reference=uuid.uuid4(), deduplication_key='test',
                             state='running', lease_token=uuid.uuid4(), lease_until=timezone.now()+timedelta(minutes=5))
    class KMS:
        def identity_digest(self, *args):
            return hashlib.sha256(str(args).encode()).hexdigest()
    stored = {}
    def write(raw, identity, authorize):
        assert authorize(identity, 'write')
        stored[identity.revision_id if hasattr(identity, 'revision_id') else str(identity)] = json.loads(raw)
        return uuid.uuid4().hex+'.enc', hashlib.sha256(raw).hexdigest(), len(raw)
    monkeypatch.setattr('ingest.canonical.TransitKMS', KMS)
    monkeypatch.setattr('ingest.canonical.store.write', write)
    def send(key, kind, payload):
        return commit_item(source, {'source_record_id': key, 'source_revision': 1,
            'kind': kind, 'operation': 'upsert', 'payload': payload}, job)
    common = {'source_type': 'direct_device', 'clinical_date': '2026-11-09', 'time_precision': 'second',
              'timezone': 'EST5EDT', 'original_offset_minutes': -300,
              'timezone_provenance': 'source'}
    weight = {**common, 'measured_start': '2026-11-09T08:00:00-05:00',
              'metric_id': 'weight', 'value': '70', 'unit': 'kg', 'source_type': 'direct_scale'}
    outcome, pk, _ = send('scale:1', 'scalar_observation', weight)
    assert outcome == 'accepted'
    assert Record.objects.get(pk=pk).kind == 'weight'
    choice = Designation.objects.get(domain='body')
    assert choice.record_id == pk and choice.automatic
    assert send('scale:1', 'scalar_observation', weight)[0] == 'duplicate'
    outcome, sleep_pk, _ = send('sleep:1', 'sleep_session', {**common,
        'measured_start': '2026-11-08T22:00:00-05:00', 'measured_end': '2026-11-09T06:00:00-05:00',
        'sleep_seconds': 25000, 'complete': True, 'stages': []})
    sleep = Record.objects.get(pk=sleep_pk)
    assert outcome == 'accepted' and sleep.kind == 'sleep'
    assert str(sleep.current.blob.clinical_date) == '2026-11-09'
    assert Record.objects.count() == 2
