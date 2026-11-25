import json
import os
import uuid
from pathlib import Path

from crypto.envelopes import EnvelopeService, Identity, TransitKMS
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a fictional encrypted canary for backup verification; never a health record."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        identity = Identity(uuid.uuid4(), "derived_snapshot", uuid.uuid4(), uuid.uuid4(), 1)
        kms = TransitKMS()

        def permit(selected, action):
            return selected == identity and action == "write"

        envelope = EnvelopeService(kms).encrypt(
            b"health03 synthetic recovery canary v1", identity, permit
        )
        with os.fdopen(
            os.open(Path(options["output"]), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
        ) as stream:
            json.dump(
                {
                    "owner": str(identity.owner_id),
                    "object": str(identity.object_id),
                    "revision": str(identity.revision_id),
                    "envelope": envelope,
                },
                stream,
            )
        kms.close()
        self.stdout.write("Encrypted synthetic recovery canary created.")
