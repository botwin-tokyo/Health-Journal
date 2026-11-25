"""Issue a persistent phone key directly to a private local handoff file."""
import hashlib
import os
import secrets
import uuid
from pathlib import Path

from accounts.models import Account
from accounts.policy import eligible
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from ingest.models import SourceConnection

from uploader.models import DeviceAPIKey, DeviceRegistration


class Command(BaseCommand):
    help = "Issue an owner-authorized non-expiring uploader key; never prints the key."

    def add_arguments(self, parser):
        parser.add_argument('--owner', required=True)
        parser.add_argument('--output', required=True)
        parser.add_argument('--label', default='mobile app phone')

    def handle(self, *args, **options):
        owner = Account.objects.get(email=options['owner'])
        if owner.role != 'owner' or not eligible(owner):
            raise CommandError('Eligible owner required')
        upload_host = settings.HEALTH03_UPLOAD_HOST
        if not upload_host:
            raise CommandError("Configure HEALTH03_UPLOAD_HOST before issuing a phone handoff")
        target = Path(options['output'])
        key = 'h03_' + secrets.token_hex(32)
        namespace = uuid.uuid4()
        # Exclusive creation prevents overwriting a handoff for an existing credential.
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'w') as output, transaction.atomic():
                device = DeviceRegistration.objects.create(owner=owner, label=options['label'])
                credential = DeviceAPIKey.objects.create(
                    device=device, digest=hashlib.sha256(key.encode()).hexdigest()
                )
                SourceConnection.objects.create(device=device, namespace=namespace)
                output.write(f'''# Health journal phone credentials — PRIVATE

Created for the owner's mobile app phone. Do not commit this file.

```json
{{
  "base_url": "https://{upload_host}",
  "upload_url": "https://{upload_host}/api/v1/ingestion/batches",
  "config_url": "https://{upload_host}/api/v1/ingestion/config",
  "assets_url": "https://{upload_host}/api/v1/ingestion/assets",
  "api_key_header": "X-API-Key",
  "api_key": "{key}",
  "device_id": "{device.pk}",
  "key_id": "{credential.pk}",
  "source_namespace": "{namespace}",
  "schema_version": "pb-health-export-1",
  "canonicalization": "jcs-rfc8785-v1",
  "timezone": "{settings.TIME_ZONE}",
  "schedule": "00:00"
}}
```

This is a persistent API key: no expiry, refresh token, rotation schedule, OAuth login, client secret, Cloudflare account/token, or database password is required by the phone. Send `X-API-Key` on every ingestion request over normal certificate-verified HTTPS. Do not send Authorization or browser cookies alongside it. It grants upload and this device's receipt/config access only. Explicit key/device revocation or disabling/deleting the owner stops access.

Import the JSON into phone settings using Android Keystore-backed encrypted storage. Keep credentials out of source, APK constants, logs, crash reports and version control. Use the same source_namespace across retries and restarts. Save new edits with increasing source_revision, and preserve exact pending batch bodies across retries.

See contracts/phone/README.md for the mobile wire contract.

Scalar stats are enabled with no separate adapter approval. A 202 response means durable intake; poll the per-item receipts for acceptance. Normal schema, unit, source, time, identity and deletion checks still apply.

To revoke this key on the Pi (only when intentionally retiring/replacing it), run from the backend repository:
```sh
.venv/bin/python backend/manage.py shell -c "from uploader.models import DeviceAPIKey; from django.utils import timezone; DeviceAPIKey.objects.filter(pk='{credential.pk}').update(revoked_at=timezone.now())"
```
After revocation, provision a replacement with `provision_phone_key`; this is optional manual revocation, not routine maintenance.
''')
                output.flush()
                os.fsync(output.fileno())
        except Exception:
            target.unlink(missing_ok=True)
            raise
        self.stdout.write('Private phone credential document created; key not printed.')
