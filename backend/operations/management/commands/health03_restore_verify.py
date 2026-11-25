import json

from django.core.management.base import BaseCommand, CommandError

from operations.restore import restore


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--environment", required=True, choices=["restore"])
        parser.add_argument("--backup-set", required=True)

    def handle(self, *args, **options):
        result = restore(options["backup_set"])
        self.stdout.write(json.dumps(result))
        if not result.get("decryption_verified"):
            raise CommandError(
                "Candidate remains closed: isolated KMS restore/unseal and decrypting verification required"
            )
